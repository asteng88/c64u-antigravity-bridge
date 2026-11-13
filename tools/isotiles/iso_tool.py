#!/usr/bin/env python3
"""
Isometric terrain tool: build a C64 multicolor charset, character lookup tables
and a staggered isometric map from one Python definition file.

The world is drawn with 32x16 pixel diamonds (4x2 characters) in staggered rows
8 pixels apart; odd rows are shifted 16 pixels right. Every screen character
then lies between exactly one diamond above it (U, row j = char row) and one
below it (L, row j + 1), split by a 2:1 diagonal in one of four positions q:

    q0 /  low     q1 /  high     q2 \\ high     q3 \\ low

so a character is fully described by (q, U, L). The tool paints every (q, U, L)
that occurs in the map, de-duplicates the results and writes two 256-byte
lookup tables indexed by q*64 + U*8 + L: iso_chr (screen code) and iso_col
(colour RAM). At most 8 terrain types.

Finding (q, U, L) for character (cx, cy), with s = cy & 1:
    a = cx + 4 - 2*s,  q = a & 3,  i = a >> 2
    U = iso_map[cy][i + (q >> 1)],  L = iso_map[cy + 1][i + s]
(iso_map rows carry one margin diamond on the left, so indexes never go negative.)

A definition file defines:
  BG        ($D021, $D022, $D023) shared colours
  TERRAINS  [dict(name=, elev=, flags=, surface=f, deco=f|None, face=(left, right)), ...]
            surface(lx, ly) and deco(lx, ly) return a pixel (deco: or None):
            "." $D021, "," $D022, "#" $D023, or 0..7 = colour RAM colour.
            lx, ly: offset of the multicolor pixel's centre from the diamond's
            centre in hires pixels (lx odd, ly = n + 0.5; the diamond is
            |lx|/16 + |ly|/8 <= 1). Deco may cover the whole 32x16 box around the
            diamond, so trees and rocks can rise above it (up to 8 px over the
            centre: higher pixels belong to the row above and are not drawn).
            face: pixels for the left / right cliff faces shown below a diamond
            that is higher (elev) than the one in front of it.
  ISO_W, ISO_H  diamonds per row, rows
  TERRAIN_AT(i, j) -> terrain name for diamond i of row j (centre at
            x = 32*i + 16*(j & 1), y = 8*j world pixels)
optional: HIRES, FONT, CONSTS, OUTPUT, TITLE (as in tools/charset/tileset_tool.py)

Outputs next to the definition file:
  <OUTPUT>_charset.bin  2048 bytes
  <OUTPUT>_iso.asm      TR_ constants, terrain_flags, iso_chr, iso_col,
                        iso_map ((ISO_H + 1) rows x (ISO_W + 2), row tables)
  <OUTPUT>_iso_review.html  rendered world, charset sheet, terrain list

  python iso_tool.py ../../game_dev/tornado/map/tornado_iso.py
"""
import argparse
import base64
import html
import importlib.util
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "charset"))
import tileset_tool as tt  # noqa: E402  (font, hires glyphs, charset store, PNG writer)

MC_BITS = {".": 0, ",": 1, "#": 2}


def load_def(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)
    return mod


def line_y(q, x):
    """y of the U/L boundary at hires x (0..8) inside a q-character."""
    return (8 - x / 2, 4 - x / 2, x / 2, 4 + x / 2)[q]


# centres of U and L relative to the character's top-left corner, by q
U_CX = (0, -8, 16, 8)
L_CX = (16, 8, 0, -8)


def paint_char(q, U, L, terrains):
    """Return (bitmap 8 bytes, colour RAM colour) for a q-character between
    terrains U (above) and L (below)."""
    tu, tl = terrains[U], terrains[L]
    drop = tu["elev"] - tl["elev"]          # cliff face height below U's edge
    pix = []
    for y in range(8):
        row = []
        for px in range(4):
            x = 2 * px + 1
            yc = y + 0.5
            ux, uy = x - U_CX[q], yc          # local to U (centre at band top)
            lx, ly = x - L_CX[q], yc - 8      # local to L (centre at band bottom)
            edge = line_y(q, x)
            if yc < edge:
                p = tu["surface"](ux, uy)
            else:
                p = tl["surface"](lx, ly)
                if drop > 0 and yc - edge < drop:
                    p = tu["face"][1 if q < 2 else 0]
            for t, (dx, dy) in ((tu, (ux, uy)), (tl, (lx, ly))):
                if t.get("deco"):
                    d = t["deco"](dx, dy)
                    if d is not None:
                        p = d
            row.append(p)
        pix.append(row)
    want = Counter(p for r in pix for p in r if isinstance(p, int))
    colour = want.most_common(1)[0][0] if want else 1
    data = []
    for r in pix:
        v = 0
        for p in r:
            if isinstance(p, int):
                bits = 3 if p == colour else 2       # other colour-RAM wishes fall back to $D023
            else:
                bits = MC_BITS[p]
            v = v << 2 | bits
        data.append(v)
    return bytes(data), colour | 8


def build(d):
    terrains = d.TERRAINS
    assert len(terrains) <= 8, "at most 8 terrain types"
    names = {t["name"]: n for n, t in enumerate(terrains)}
    w, h = d.ISO_W, d.ISO_H
    grid = [[names[d.TERRAIN_AT(i, j)] for i in range(w)] for j in range(h)]
    sea = 0
    # stored rows: one margin diamond left and right, one margin row at the bottom
    stored = [[sea] + row + [sea] for row in grid] + [[sea] * (w + 2)]

    reserved = tt.font_chars() if getattr(d, "FONT", True) else {}
    hires = getattr(d, "HIRES", {})
    for key, rows in hires.items():
        if isinstance(key, int):
            reserved[key] = tt.hires_char(rows)
    cs = tt.Charset(reserved)
    cs.next = 64 if reserved else 0
    named_hires = {k: cs.add(tt.hires_char(r)) for k, r in hires.items() if not isinstance(k, int)}

    chr_tab = [0] * 256
    col_tab = [8] * 256
    seen = {}
    # every character of the world: paint each (q, U, L) once, at its first position
    world_w = 4 * w
    for cy in range(h):
        s = cy & 1
        for cx in range(world_w):
            a = cx + 4 - 2 * s
            q, i = a & 3, a >> 2
            U = stored[cy][i + (q >> 1)]
            L = stored[cy + 1][i + s]
            key = (q, U, L)
            if key in seen:
                continue
            b, col = paint_char(q, U, L, terrains)
            code = cs.add(b)
            seen[key] = (code, col)
            chr_tab[q * 64 + U * 8 + L] = code
            col_tab[q * 64 + U * 8 + L] = col
    return cs, grid, stored, chr_tab, col_tab, named_hires, len(seen)


def write_asm(d, title, cs, stored, chr_tab, col_tab, named_hires, path):
    bl = tt.bytes_lines
    bg = d.BG
    w = d.ISO_W + 2
    out = [f"// {title} isometric terrain - generated by tools/isotiles/iso_tool.py, do not edit by hand",
           f"// {len(cs.data)} characters, map {d.ISO_W}x{d.ISO_H} diamonds",
           f".const BG0 = ${bg[0]:02X}", f".const BG1 = ${bg[1]:02X}", f".const BG2 = ${bg[2]:02X}",
           f".const ISO_W = {d.ISO_W}", f".const ISO_H = {d.ISO_H}", f".const ISO_STRIDE = {w}"]
    for n, t in enumerate(d.TERRAINS):
        out.append(f".const TR_{tt.asm_name(t['name'])} = {n}")
    for name, code in named_hires.items():
        out.append(f".const H_{tt.asm_name(name)} = ${code:02X}")
    for name, value in getattr(d, "CONSTS", {}).items():
        out.append(f".const {name} = {value}")
    out += ["", "terrain_flags:"] + bl([t["flags"] for t in d.TERRAINS])
    out += ["// iso_chr / iso_col: index q*64 + U*8 + L", "iso_chr:"] + bl(chr_tab)
    out += ["iso_col:"] + bl(col_tab)
    out += [f"iso_row_lo: .fill {len(stored)}, <(iso_map + i * ISO_STRIDE)",
            f"iso_row_hi: .fill {len(stored)}, >(iso_map + i * ISO_STRIDE)", "iso_map:"]
    for row in stored:
        out += bl(row, w)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def render_world(d, cs, stored, chr_tab, col_tab):
    h, cw = d.ISO_H, 4 * d.ISO_W
    img = [[0] * (cw * 8) for _ in range(h * 8)]
    for cy in range(h):
        s = cy & 1
        for cx in range(cw):
            a = cx + 4 - 2 * s
            q, i = a & 3, a >> 2
            idx = q * 64 + stored[cy][i + (q >> 1)] * 8 + stored[cy + 1][i + s]
            tt.render_char(img, cx * 8, cy * 8, cs.data[chr_tab[idx]], col_tab[idx], d.BG)
    return img


def write_review(title, cs, d, n_combos, world_png, sheet_png, path):
    def uri(png):
        return "data:image/png;base64," + base64.b64encode(png).decode()
    rows = "".join(f"<tr><td>{n}</td><td>{html.escape(t['name'])}</td><td>{t['elev']}</td>"
                   f"<td>${t['flags']:02X}</td></tr>" for n, t in enumerate(d.TERRAINS))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} Iso Terrain</title>
<style>
:root{{--bg:#16130f;--fg:#efe6d4;--muted:#a89a80;--line:#3a3227;--acc:#e0a040}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f6f1e7;--fg:#241d12;--muted:#6d604a;--line:#d9cdb5;--acc:#a8650a}}}}
:root[data-theme="dark"]{{--bg:#16130f;--fg:#efe6d4;--muted:#a89a80;--line:#3a3227;--acc:#e0a040}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px;color:var(--acc)}}
p{{color:var(--muted);margin:0 0 12px}}
img{{image-rendering:pixelated;max-width:100%;height:auto;border:1px solid var(--line)}}
table{{border-collapse:collapse;font-size:13px}} td{{padding:2px 10px;border-bottom:1px solid var(--line)}}
</style></head><body><main>
<h1>{html.escape(title)} isometric terrain</h1>
<p>{len(cs.data)} of 256 characters used &middot; {n_combos} terrain-pair characters &middot;
map {d.ISO_W}&times;{d.ISO_H} diamonds</p>
<h2>World</h2><img src="{uri(world_png)}" alt="Whole world rendered from the character tables" width="1024">
<h2>Charset</h2><img src="{uri(sheet_png)}" alt="Character set" width="576">
<h2>Terrains</h2><table><tr><td>#</td><td>name</td><td>height</td><td>flags</td></tr>{rows}</table>
</main></body></html>"""
    path.write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("terrain", type=pathlib.Path)
    args = ap.parse_args()
    src = args.terrain.resolve()
    d = load_def(src)
    title = getattr(d, "TITLE", src.stem)
    prefix = getattr(d, "OUTPUT", src.stem)
    cs, grid, stored, chr_tab, col_tab, named_hires, n = build(d)
    here = src.parent
    (here / f"{prefix}_charset.bin").write_bytes(cs.binary())
    print(f"wrote {prefix}_charset.bin: {len(cs.data)} characters ({n} terrain combinations)")
    asm = here / f"{prefix}_iso.asm"
    write_asm(d, title, cs, stored, chr_tab, col_tab, named_hires, asm)
    print(f"wrote {asm.name}: {d.ISO_W}x{d.ISO_H} diamonds, {len(d.TERRAINS)} terrains")
    world_png = tt.png_bytes(render_world(d, cs, stored, chr_tab, col_tab))
    colours = {}
    for idx, code in enumerate(chr_tab):
        colours.setdefault(code, col_tab[idx])
    sheet_png = tt.png_bytes(tt.render_charset(cs, d.BG, colours), 2)
    page = here / f"{prefix}_iso_review.html"
    write_review(title, cs, d, n, world_png, sheet_png, page)
    print(f"wrote {page.name}")


if __name__ == "__main__":
    main()
