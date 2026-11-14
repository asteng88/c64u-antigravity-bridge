#!/usr/bin/env python3
"""
Isometric terrain tool: build a C64 multicolor charset, character lookup tables
and a staggered isometric map, with raised ground, from one Python definition file.

The world is drawn with 32x16 pixel diamonds (4x2 characters) in staggered rows
8 pixels apart; odd rows are shifted 16 pixels right. Every screen character
lies between one diamond above it (U, row j = char row) and one below it
(L, row j + 1), split by a 2:1 diagonal in one of four positions q, and it only
ever sees one half (left or right of the centre line) of each:

    q0 /  low   U right half, L left half      q2 \\ high  U left half, L right half
    q1 /  high  U right half, L left half      q3 \\ low   U left half, L right half

Heights: a diamond raised by n levels (16 px each) is drawn 2n rows higher, and
its walls fill whole half-diamonds below it (the left wall = the right half of
the up-left neighbour and the left half of the diamond itself, one row pair per
level). So the tool projects the height map (painter's algorithm, back to
front) into a map of half-diamonds, and a character is still fully described by
(q, U half, L half). Every map byte holds two half types: left << 4 | right.

The tool paints every (q, U half, L half) that occurs and writes:
  iso_chr   1024 bytes, index q*256 + Uh*16 + Lh -> screen code
  char_col  256 bytes, screen code -> colour RAM (one colour per character)

Finding the character at world char (cx, cy), with s = cy & 1:
    a = cx + 4 - 2*s,  q = a & 3,  i = a >> 2
    q < 2:  U = iso_map[cy][i] & $0F (right half),  L = iso_map[cy+1][i+s] >> 4 (left)
    q >= 2: U = iso_map[cy][i+1] >> 4 (left half),  L = iso_map[cy+1][i+s] & $0F (right)
(iso_map rows carry one margin diamond on the left, so indexes never go negative.)

A definition file defines:
  BG        ($D021, $D022, $D023) shared colours
  TERRAINS  [dict(name=, elev=, flags=, surface=f, deco=f|None, face=(left, right),
                  fallback=pixel), ...]   at most 16; the first also fills the margins
            surface(lx, ly) and deco(lx, ly) return a pixel (deco: or None):
            "." $D021, "," $D022, "#" $D023, or 0..7 = colour RAM colour.
            lx, ly: offset of the multicolor pixel's centre from the diamond's
            centre in hires pixels (lx odd, ly = n + 0.5; the diamond is
            |lx|/16 + |ly|/8 <= 1). Deco may cover the whole 32x16 box around the
            diamond, so trees and rocks can rise above it.
            face: pixels for the small lip shown below a diamond with a higher
            elev than the one in front of it (beach edges and the like).
            fallback: what a colour-RAM pixel turns into when another colour
            wins the character (default "#").
            rim: pixel for a 1-2 px highlight along the front edges of a raised
            top (where the half below is a wall). Wall terrains set wall=True.
  ISO_W, ISO_H  diamonds per row, rows
  TERRAIN_AT(i, j) -> terrain name for ground diamond i of row j (centre at
            x = 32*i + 16*(j & 1), y = 8*j world pixels)
optional:
  HEIGHT_AT(i, j) -> levels (16 px each) the diamond is raised; needs WALLS
  WALLS     (left wall terrain name, right wall terrain name): their surface()
            gets the half-diamond's local coordinates like any other terrain
  EXTRA_ASM(world) -> list of asm lines, written to <OUTPUT>_extra.asm; world
            has terrain_at(x, y) (name of the terrain shown at world pixel x, y)
            and ground_level(x, y) (height level of the ground diamond under it),
            for game data that depends on the finished map (spawn points, ...)
  WALLS_AT(i, j) -> (left, right) wall terrain names for that raised diamond,
            a list of such pairs (one per level, bottom first), or None for
            WALLS (buildings, tree trunks, a tree on a hill, ...); its top is
            still TERRAIN_AT(i, j)
  FONT_KEEP string of characters: reserve only these font glyphs (frees the
            rest of screen codes 0-63 for terrain)
  HIRES, FONT, CONSTS, OUTPUT, TITLE (as in tools/charset/tileset_tool.py)

Outputs next to the definition file:
  <OUTPUT>_charset.bin      2048 bytes
  <OUTPUT>_iso.asm          TR_ constants, terrain_flags, iso_chr, char_col,
                            iso_map ((ISO_H + 1) rows x (ISO_W + 2)), row tables
  <OUTPUT>_heights.asm      (with HEIGHT_AT) iso_height: ground level 0-3 of
                            every diamond, 2 bits each, and its row tables
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
LEVEL_ROWS = 2      # one height level = 16 px = 2 staggered rows


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
    """Return (bitmap 8 bytes, colour) for a q-character between half types
    U (above) and L (below)."""
    tu, tl = terrains[U], terrains[L]
    drop = tu["elev"] - tl["elev"]          # lip height below U's edge
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
                p, src = tu["surface"](ux, uy), tu
            else:
                p, src = tl["surface"](lx, ly), tl
                if drop > 0 and yc - edge < drop:
                    p, src = tu["face"][1 if q < 2 else 0], tu
            # rim: a highlight along the front edge of a raised top (U over a wall)
            if tl.get("wall") and not tu.get("wall") and tu.get("rim") and edge - 1.5 <= yc < edge:
                p, src = tu["rim"], tu
            for t, (dx, dy) in ((tu, (ux, uy)), (tl, (lx, ly))):
                if t.get("deco"):
                    d = t["deco"](dx, dy)
                    if d is not None:
                        p, src = d, t
            row.append((p, src.get("fallback", "#")))
        pix.append(row)
    want = Counter(p for r in pix for p, _ in r if isinstance(p, int))
    colour = want.most_common(1)[0][0] if want else None
    data = []
    for r in pix:
        v = 0
        for p, fb in r:
            if isinstance(p, int) and p != colour:
                p = fb if not isinstance(fb, int) else "#"
            v = v << 2 | (3 if isinstance(p, int) else MC_BITS[p])
        data.append(v)
    return bytes(data), colour


def project(d, names):
    """Ground terrain + heights -> visible half types [row][diamond] = [left, right]."""
    w, h = d.ISO_W, d.ISO_H
    ground = [[names[d.TERRAIN_AT(i, j)] for i in range(w)] for j in range(h)]
    vis = [[[t, t] for t in row] for row in ground]
    height_at = getattr(d, "HEIGHT_AT", None)
    if height_at is None:
        return vis
    default_walls = tuple(names[n] for n in d.WALLS)
    walls_at = getattr(d, "WALLS_AT", None)

    def put(row, x, half, t):
        if 0 <= row < h:
            i, rem = divmod(x - 16 * (row & 1), 32)
            if rem == 0 and 0 <= i < w:
                vis[row][i][half] = t

    for j in range(h):                      # back (top of screen) to front
        for i in range(w):
            n = height_at(i, j)
            if n <= 0:
                continue
            x = 32 * i + 16 * (j & 1)
            wl, wr = default_walls
            per_level = [(wl, wr)] * n
            if walls_at is not None:
                spec = walls_at(i, j)
                if spec:
                    if isinstance(spec[0], str):
                        spec = [spec] * n
                    per_level = [(names[a], names[b]) for a, b in spec]
            for k in range(n):              # one wall segment per level
                wl, wr = per_level[k]
                top = j - LEVEL_ROWS * (k + 1)
                put(top + 1, x - 16, 1, wl)
                put(top + 2, x, 0, wl)
                put(top + 1, x + 16, 0, wr)
                put(top + 2, x, 1, wr)
            top = j - LEVEL_ROWS * n
            put(top, x, 0, ground[j][i])
            put(top, x, 1, ground[j][i])
    return vis


def halves(stored, cy, cx):
    """(q, U half type, L half type) of world character (cx, cy)."""
    s = cy & 1
    a = cx + 4 - 2 * s
    q, i = a & 3, a >> 2
    if q < 2:
        return q, stored[cy][i] & 15, stored[cy + 1][i + s] >> 4
    return q, stored[cy][i + 1] >> 4, stored[cy + 1][i + s] & 15


class ColourCharset(tt.Charset):
    """Characters de-duplicated by bitmap and, if they use colour RAM, colour."""

    def __init__(self, reserved):
        super().__init__(reserved)
        self.colour = {}

    def add_coloured(self, b, colour):
        uses = any((v >> s) & 3 == 3 for v in b for s in (0, 2, 4, 6))
        for code, existing in self.data.items():
            if existing == b and code not in self.reserved:
                if not uses or self.colour.get(code) == colour:
                    return code
        while self.next in self.data:
            self.next += 1
        assert self.next < 256, "charset full (256 characters)"
        self.data[self.next] = b
        self.colour[self.next] = colour if (uses and colour is not None) else 1
        return self.next


def build(d):
    terrains = d.TERRAINS
    assert len(terrains) <= 16, "at most 16 terrain (half) types"
    names = {t["name"]: n for n, t in enumerate(terrains)}
    w, h = d.ISO_W, d.ISO_H
    vis = project(d, names)
    sea = 0
    stored = [[sea * 17] + [hl << 4 | hr for hl, hr in row] + [sea * 17] for row in vis]
    stored.append([sea * 17] * (w + 2))

    reserved = tt.font_chars() if getattr(d, "FONT", True) else {}
    keep = getattr(d, "FONT_KEEP", None)
    if keep is not None:
        codes = {tt.screen_code(c) for c in keep}
        reserved = {c: b for c, b in reserved.items() if c in codes}
    hires = getattr(d, "HIRES", {})
    for key, rows in hires.items():
        if isinstance(key, int):
            reserved[key] = tt.hires_char(rows)
    cs = ColourCharset(reserved)
    cs.next = 0
    named_hires = {k: cs.add_coloured(tt.hires_char(r), 1) for k, r in hires.items() if not isinstance(k, int)}

    chr_tab = [0] * 1024
    seen = {}
    for cy in range(h):
        for cx in range(4 * w):
            key = halves(stored, cy, cx)
            if key in seen:
                continue
            q, U, L = key
            b, col = paint_char(q, U, L, terrains)
            code = cs.add_coloured(b, col)
            seen[key] = code
            chr_tab[q * 256 + U * 16 + L] = code
    col_tab = [(cs.colour.get(c, 1) & 7) | 8 for c in range(256)]
    return cs, stored, chr_tab, col_tab, named_hires, len(seen)


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
    flags = [t["flags"] for t in d.TERRAINS] + [0] * (16 - len(d.TERRAINS))
    out += ["", "// iso_chr: index q*256 + U*16 + L (4 pages, one per q)", ".align $100", "iso_chr:"] + bl(chr_tab)
    out += ["// char_col: colour RAM value of every screen code", "char_col:"] + bl(col_tab)
    out += ["terrain_flags:"] + bl(flags)
    out += [f"iso_row_lo: .fill {len(stored)}, <(iso_map + i * ISO_STRIDE)",
            f"iso_row_hi: .fill {len(stored)}, >(iso_map + i * ISO_STRIDE)", "iso_map:"]
    for row in stored:
        out += bl(row, w)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# rows of a q-character (by q, hires x 0..7) that belong to the upper diamond
LINE_THR = [[8, 7, 7, 6, 6, 5, 5, 4], [4, 3, 3, 2, 2, 1, 1, 0],
            [0, 1, 1, 2, 2, 3, 3, 4], [4, 5, 5, 6, 6, 7, 7, 8]]


class World:
    """Look-ups on the finished map for EXTRA_ASM."""

    def __init__(self, d, stored):
        self.d, self.stored = d, stored
        self.names = [t["name"] for t in d.TERRAINS]

    def _cell(self, x, y):
        cy, yb, cx, xb = int(y) >> 3, int(y) & 7, int(x) >> 3, int(x) & 7
        s = cy & 1
        a = cx + 4 - 2 * s
        q, i = a & 3, a >> 2
        if yb < LINE_THR[q][xb]:
            return cy, i + (q >> 1), 1 if q < 2 else 0
        return cy + 1, i + s, 0 if q < 2 else 1

    def terrain_at(self, x, y):
        row, idx, half = self._cell(x, y)
        b = self.stored[row][idx]
        return self.names[(b & 15) if half else (b >> 4)]

    def ground_level(self, x, y):
        row, idx, _ = self._cell(x, y)
        if not (0 <= row < self.d.ISO_H and 1 <= idx <= self.d.ISO_W):
            return 0
        return self.d.HEIGHT_AT(idx - 1, row) if getattr(self.d, "HEIGHT_AT", None) else 0


def write_heights(d, title, path):
    """Ground height of every diamond, 2 bits each (levels 0-3, 4 per byte,
    diamond i in bits (i & 3) * 2 of byte i >> 2), plus one zero row."""
    w = d.ISO_W
    stride = (w + 3) // 4
    rows = []
    for j in range(d.ISO_H):
        row = [0] * stride
        for i in range(w):
            row[i >> 2] |= min(3, max(0, d.HEIGHT_AT(i, j))) << ((i & 3) * 2)
        rows.append(row)
    rows.append([0] * stride)
    out = [f"// {title} ground heights - generated by tools/isotiles/iso_tool.py, do not edit by hand",
           f".const ISO_HSTRIDE = {stride}",
           f"iso_hrow_lo: .fill {len(rows)}, <(iso_height + i * ISO_HSTRIDE)",
           f"iso_hrow_hi: .fill {len(rows)}, >(iso_height + i * ISO_HSTRIDE)", "iso_height:"]
    for row in rows:
        out += tt.bytes_lines(row, stride)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def render_world(d, cs, stored, chr_tab, col_tab):
    h, cw = d.ISO_H, 4 * d.ISO_W
    img = [[0] * (cw * 8) for _ in range(h * 8)]
    for cy in range(h):
        for cx in range(cw):
            q, U, L = halves(stored, cy, cx)
            code = chr_tab[q * 256 + U * 16 + L]
            tt.render_char(img, cx * 8, cy * 8, cs.data[code], col_tab[code], d.BG)
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
<p>{len(cs.data)} of 256 characters used &middot; {n_combos} half-diamond pairs &middot;
map {d.ISO_W}&times;{d.ISO_H} diamonds</p>
<h2>World</h2><img src="{uri(world_png)}" alt="Whole world rendered from the character tables" width="1024">
<h2>Charset</h2><img src="{uri(sheet_png)}" alt="Character set" width="576">
<h2>Terrains</h2><table><tr><td>#</td><td>name</td><td>lip height</td><td>flags</td></tr>{rows}</table>
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
    cs, stored, chr_tab, col_tab, named_hires, n = build(d)
    here = src.parent
    (here / f"{prefix}_charset.bin").write_bytes(cs.binary())
    print(f"wrote {prefix}_charset.bin: {len(cs.data)} characters ({n} half-diamond pairs)")
    asm = here / f"{prefix}_iso.asm"
    write_asm(d, title, cs, stored, chr_tab, col_tab, named_hires, asm)
    print(f"wrote {asm.name}: {d.ISO_W}x{d.ISO_H} diamonds, {len(d.TERRAINS)} terrains")
    extra = getattr(d, "EXTRA_ASM", None)
    if extra is not None:
        easm = here / f"{prefix}_extra.asm"
        lines = extra(World(d, stored))
        easm.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {easm.name}: {len(lines)} lines")
    if getattr(d, "HEIGHT_AT", None) is not None:
        hasm = here / f"{prefix}_heights.asm"
        write_heights(d, title, hasm)
        print(f"wrote {hasm.name}: ground heights, 2 bits per diamond")
    world_png = tt.png_bytes(render_world(d, cs, stored, chr_tab, col_tab))
    sheet_png = tt.png_bytes(tt.render_charset(cs, d.BG, {c: col_tab[c] for c in range(256)}), 2)
    page = here / f"{prefix}_iso_review.html"
    write_review(title, cs, d, n, world_png, sheet_png, page)
    print(f"wrote {page.name}")


if __name__ == "__main__":
    main()
