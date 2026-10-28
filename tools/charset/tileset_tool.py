#!/usr/bin/env python3
"""
Tileset tool: build a C64 multicolor charset, 2x2-char tiles, multi-char
blocks (buildings) and a tile map from one Python definition file.

A tileset file defines:
  BG         ($D021, $D022, $D023) shared colours
  TILES      [(NAME, art, colour, flags), ...]  art = 16 rows x 8 multicolor pixels
  MAP        rows of single characters, one per tile
  LEGEND     {char: NAME or [NAME, ...]}  a list picks a variant per cell (stable hash)
optional:
  BLOCKS     [(NAME, art, colour), ...]   art = 8*h rows x 4*w pixels (any size in chars)
  HIRES      {code or NAME: 8 rows x 8 pixels}  single hires chars (UI glyphs)
  FONT       True: put the built-in bold font at screen codes 0-63 (default True)
  CONSTS     {NAME: value} extra .const lines
  OBJECTS    [(KIND, a, b, c), ...] emitted as `map_objects` (4 bytes each, $FF end)
  KINDS      [KIND, ...] names for OBJECTS kinds (emitted as K_<NAME> constants)
  PREVIEW    function(tile_x, tile_y) -> None, or a list of (BLOCK, tx, ty, colour) to draw
  OUTPUT     output prefix (default: the file's stem)

Multicolor legend:  .  $D021   ,  $D022   #  $D023   o  colour RAM (the tile colour)
Hires legend:       .  background   #  colour RAM

Characters are de-duplicated. Outputs next to the definition file:
  <OUTPUT>_charset.bin  2048 bytes, import with .import binary
  <OUTPUT>_tiles.asm    T_/B_/H_ constants, tile tables (tile_c0..c3, tile_col,
                        tile_flags), block_chars, map_tiles (MAP_W x MAP_H)
  <OUTPUT>_review.html  map preview, charset sheet and tile list

  python tileset_tool.py ../../game_dev/ironfront/map/ironfront_map.py
"""
import argparse
import base64
import html
import importlib.util
import pathlib
import struct
import sys
import zlib

PALETTE = [
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
]
MC_BITS = {".": "00", ",": "01", "#": "10", "o": "11"}

# Bold 7x7 font, screen-code order. Each glyph: 7 rows of 7 columns (8th column
# and row stay blank for spacing).
_FONT_ROWS = {
    "A": [" #### ", "##  ##", "##  ##", "######", "##  ##", "##  ##", "##  ##"],
    "B": ["##### ", "##  ##", "##  ##", "##### ", "##  ##", "##  ##", "##### "],
    "C": [" #### ", "##  ##", "##    ", "##    ", "##    ", "##  ##", " #### "],
    "D": ["####  ", "## ## ", "##  ##", "##  ##", "##  ##", "## ## ", "####  "],
    "E": ["######", "##    ", "##    ", "##### ", "##    ", "##    ", "######"],
    "F": ["######", "##    ", "##    ", "##### ", "##    ", "##    ", "##    "],
    "G": [" #### ", "##  ##", "##    ", "## ###", "##  ##", "##  ##", " #####"],
    "H": ["##  ##", "##  ##", "##  ##", "######", "##  ##", "##  ##", "##  ##"],
    "I": [" #### ", "  ##  ", "  ##  ", "  ##  ", "  ##  ", "  ##  ", " #### "],
    "J": ["   ###", "    ##", "    ##", "    ##", "##  ##", "##  ##", " #### "],
    "K": ["##  ##", "## ## ", "####  ", "###   ", "####  ", "## ## ", "##  ##"],
    "L": ["##    ", "##    ", "##    ", "##    ", "##    ", "##    ", "######"],
    "M": ["##   ##", "### ###", "#######", "## # ##", "##   ##", "##   ##", "##   ##"],
    "N": ["##  ##", "### ##", "######", "######", "## ###", "##  ##", "##  ##"],
    "O": [" #### ", "##  ##", "##  ##", "##  ##", "##  ##", "##  ##", " #### "],
    "P": ["##### ", "##  ##", "##  ##", "##### ", "##    ", "##    ", "##    "],
    "Q": [" #### ", "##  ##", "##  ##", "##  ##", "##  ##", "## ## ", " ## ##"],
    "R": ["##### ", "##  ##", "##  ##", "##### ", "####  ", "## ## ", "##  ##"],
    "S": [" #### ", "##  ##", "##    ", " #### ", "    ##", "##  ##", " #### "],
    "T": ["######", "  ##  ", "  ##  ", "  ##  ", "  ##  ", "  ##  ", "  ##  "],
    "U": ["##  ##", "##  ##", "##  ##", "##  ##", "##  ##", "##  ##", " #### "],
    "V": ["##  ##", "##  ##", "##  ##", "##  ##", "##  ##", " #### ", "  ##  "],
    "W": ["##   ##", "##   ##", "##   ##", "## # ##", "#######", "### ###", "##   ##"],
    "X": ["##  ##", "##  ##", " #### ", "  ##  ", " #### ", "##  ##", "##  ##"],
    "Y": ["##  ##", "##  ##", "##  ##", " #### ", "  ##  ", "  ##  ", "  ##  "],
    "Z": ["######", "    ##", "   ## ", "  ##  ", " ##   ", "##    ", "######"],
    "0": [" #### ", "##  ##", "## ###", "######", "### ##", "##  ##", " #### "],
    "1": ["  ##  ", " ###  ", "  ##  ", "  ##  ", "  ##  ", "  ##  ", "######"],
    "2": [" #### ", "##  ##", "    ##", "  ### ", " ##   ", "##    ", "######"],
    "3": [" #### ", "##  ##", "    ##", "  ### ", "    ##", "##  ##", " #### "],
    "4": ["   ###", "  ####", " ## ##", "##  ##", "#######", "    ##", "    ##"],
    "5": ["######", "##    ", "##### ", "    ##", "    ##", "##  ##", " #### "],
    "6": [" #### ", "##    ", "##### ", "##  ##", "##  ##", "##  ##", " #### "],
    "7": ["######", "    ##", "   ## ", "  ##  ", "  ##  ", "  ##  ", "  ##  "],
    "8": [" #### ", "##  ##", "##  ##", " #### ", "##  ##", "##  ##", " #### "],
    "9": [" #### ", "##  ##", "##  ##", " #####", "    ##", "   ## ", " ###  "],
    " ": [""] * 7,
    ".": ["", "", "", "", "", "  ##  ", "  ##  "],
    ",": ["", "", "", "", "  ##  ", "  ##  ", " ##   "],
    ":": ["", "  ##  ", "  ##  ", "", "  ##  ", "  ##  ", ""],
    "-": ["", "", "", "######", "", "", ""],
    "!": ["  ##  ", "  ##  ", "  ##  ", "  ##  ", "", "  ##  ", ""],
    "?": [" #### ", "##  ##", "   ## ", "  ##  ", "  ##  ", "", "  ##  "],
    "$": ["  ##  ", " #####", "##    ", " #### ", "    ##", "##### ", "  ##  "],
    "/": ["     ##", "    ## ", "   ##  ", "  ##   ", " ##    ", "##     ", ""],
    "+": ["", "  ##  ", "  ##  ", "######", "  ##  ", "  ##  ", ""],
    "=": ["", "", "######", "", "######", "", ""],
    ">": ["##    ", " ##   ", "  ##  ", "   ## ", "  ##  ", " ##   ", "##    "],
    "<": ["    ##", "   ## ", "  ##  ", " ##   ", "  ##  ", "   ## ", "    ##"],
    "(": ["   ## ", "  ##  ", " ##   ", " ##   ", " ##   ", "  ##  ", "   ## "],
    ")": [" ##   ", "  ##  ", "   ## ", "   ## ", "   ## ", "  ##  ", " ##   "],
    "'": ["  ##  ", "  ##  ", " ##   ", "", "", "", ""],
    "%": ["##   #", "##  ##", "   ## ", "  ##  ", " ##   ", "##  ##", "#   ##"],
}


def screen_code(ch):
    if "A" <= ch <= "Z":
        return ord(ch) - 64
    if ch == "@":
        return 0
    return ord(ch)  # space .. ? map to themselves (32-63)


def font_chars():
    out = {}
    for ch, rows in _FONT_ROWS.items():
        data = []
        for r in range(8):
            line = rows[r] if r < 7 else ""
            line = (line + " " * 8)[:8]
            data.append(int("".join("1" if c == "#" else "0" for c in line), 2))
        out[screen_code(ch)] = bytes(data)
    return out


def mc_char(rows):
    assert len(rows) == 8 and all(len(r) == 4 for r in rows), rows
    return bytes(int("".join(MC_BITS[c] for c in r), 2) for r in rows)


def hires_char(rows):
    assert len(rows) == 8 and all(len(r) == 8 for r in rows), rows
    return bytes(int("".join("1" if c == "#" else "0" for c in r), 2) for r in rows)


def slice_art(art, w_chars, h_chars):
    """Split multicolor art (8*h rows x 4*w pixels) into chars, row-major."""
    assert len(art) == 8 * h_chars and all(len(r) == 4 * w_chars for r in art), "art size"
    return [mc_char([art[cy * 8 + r][cx * 4:cx * 4 + 4] for r in range(8)])
            for cy in range(h_chars) for cx in range(w_chars)]


class Charset:
    def __init__(self, reserved):
        self.data = {}
        self.reserved = dict(reserved)
        for code, b in reserved.items():
            self.data[code] = b
        self.next = 0

    def add(self, b):
        for code, existing in self.data.items():
            if existing == b and code not in self.reserved:
                return code
        while self.next in self.data:
            self.next += 1
        assert self.next < 256, "charset full (256 characters)"
        self.data[self.next] = b
        return self.next

    def binary(self):
        return b"".join(self.data.get(c, bytes(8)) for c in range(256))


def load_def(path):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(d):
    reserved = font_chars() if getattr(d, "FONT", True) else {}
    hires = getattr(d, "HIRES", {})
    named_hires = {}
    for key, rows in hires.items():
        if isinstance(key, int):
            reserved[key] = hires_char(rows)
    cs = Charset(reserved)
    cs.next = 64 if reserved else 0
    for key, rows in hires.items():
        if not isinstance(key, int):
            named_hires[key] = cs.add(hires_char(rows))
    tiles = []
    for name, art, colour, flags in d.TILES:
        codes = [cs.add(b) for b in slice_art(art, 2, 2)]
        tiles.append({"name": name, "codes": codes, "col": colour | 8, "flags": flags})
    blocks = []
    for name, art, colour in getattr(d, "BLOCKS", []):
        w, h = len(art[0]) // 4, len(art) // 8
        codes = [cs.add(b) for b in slice_art(art, w, h)]
        blocks.append({"name": name, "w": w, "h": h, "codes": codes, "col": colour | 8})
    index = {t["name"]: i for i, t in enumerate(tiles)}
    grid = []
    for y, row in enumerate(d.MAP):
        out = []
        for x, ch in enumerate(row):
            choice = d.LEGEND[ch]
            if isinstance(choice, (list, tuple)):
                choice = choice[(x * 7919 + y * 104729 + (x * y) * 31) % len(choice)]
            out.append(index[choice])
        grid.append(out)
    assert len({len(r) for r in grid}) == 1, "map rows differ in length"
    return cs, tiles, blocks, named_hires, grid


def asm_name(name):
    return "".join(c if c.isalnum() else "_" for c in name.upper())


def bytes_lines(values, per=16):
    return ["    .byte " + ",".join(f"${v:02X}" for v in values[i:i + per]) for i in range(0, len(values), per)]


def write_asm(d, title, cs, tiles, blocks, named_hires, grid, path):
    bg = d.BG
    out = [f"// {title} tileset - generated by tools/charset/tileset_tool.py, do not edit by hand",
           f"// {len(cs.data)} characters, {len(tiles)} tiles, {len(blocks)} blocks, map {len(grid[0])}x{len(grid)} tiles",
           f".const BG0 = ${bg[0]:02X}", f".const BG1 = ${bg[1]:02X}", f".const BG2 = ${bg[2]:02X}",
           f".const MAP_W = {len(grid[0])}", f".const MAP_H = {len(grid)}", f".const TILE_COUNT = {len(tiles)}"]
    for i, t in enumerate(tiles):
        out.append(f".const T_{asm_name(t['name'])} = {i}")
    for i, b in enumerate(blocks):
        out.append(f".const B_{asm_name(b['name'])} = {i}  // {b['w']}x{b['h']} chars")
    for name, code in named_hires.items():
        out.append(f".const H_{asm_name(name)} = ${code:02X}")
    for name, value in getattr(d, "CONSTS", {}).items():
        out.append(f".const {name} = {value}")
    for i, k in enumerate(getattr(d, "KINDS", [])):
        out.append(f".const K_{asm_name(k)} = {i}")
    out.append("")
    for n in range(4):
        out.append(f"tile_c{n}:")
        out += bytes_lines([t["codes"][n] for t in tiles])
    out.append("tile_col:")
    out += bytes_lines([t["col"] for t in tiles])
    out.append("tile_flags:")
    out += bytes_lines([t["flags"] for t in tiles])
    if blocks:
        out.append("// block_chars: row-major char codes of each block; block_col: default colour")
        out.append("block_col:")
        out += bytes_lines([b["col"] for b in blocks])
        offs = 0
        out.append("block_lo:")
        lo, hi = [], []
        for b in blocks:
            lo.append(f"<(block_chars+{offs})")
            hi.append(f">(block_chars+{offs})")
            offs += len(b["codes"])
        out.append("    .byte " + ",".join(lo))
        out.append("block_hi:")
        out.append("    .byte " + ",".join(hi))
        out.append("block_chars:")
        for b in blocks:
            out.append(f"    // {b['name']}")
            out += bytes_lines(b["codes"], b["w"])
    objects = getattr(d, "OBJECTS", None)
    if objects is not None:
        kinds = getattr(d, "KINDS", [])
        out.append("map_objects:")
        for obj in objects:
            kind = kinds.index(obj[0]) if isinstance(obj[0], str) else obj[0]
            out.append(f"    .byte {kind},{obj[1]},{obj[2]},{obj[3]}")
        out.append("    .byte $FF")
    out.append("map_tiles:")
    for row in grid:
        out += bytes_lines(row, 32)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- preview
def render_char(img, x0, y0, b, colour, bg, scale_w=1):
    mc = colour & 8
    c3 = colour & 7
    for r in range(8):
        bits = b[r]
        for p in range(8):
            if mc:
                pair = bits >> (6 - (p & 6)) & 3
                col = (bg[0], bg[1], bg[2], c3)[pair]
            else:
                col = c3 if bits >> (7 - p) & 1 else bg[0]
            img[y0 + r][x0 + p] = col


def render_map(cs, tiles, blocks, grid, bg, extra):
    h, w = len(grid) * 16, len(grid[0]) * 16
    img = [[0] * w for _ in range(h)]
    for ty, row in enumerate(grid):
        for tx, t in enumerate(row):
            tile = tiles[t]
            for n, code in enumerate(tile["codes"]):
                render_char(img, tx * 16 + (n & 1) * 8, ty * 16 + (n >> 1) * 8, cs.data[code], tile["col"], bg)
    names = {b["name"]: b for b in blocks}
    for name, tx, ty, colour in extra:
        b = names[name]
        for n, code in enumerate(b["codes"]):
            render_char(img, tx * 16 + (n % b["w"]) * 8, ty * 16 + (n // b["w"]) * 8, cs.data[code], colour | 8, bg)
    return img


def render_charset(cs, bg, colours):
    img = [[11] * (16 * 9) for _ in range(16 * 9)]
    for code in range(256):
        x0, y0 = (code % 16) * 9, (code // 16) * 9
        b = cs.data.get(code)
        if b is None:
            continue
        render_char(img, x0, y0, b, colours.get(code, 1), bg)
    return img


def png_bytes(rows, scale=1):
    h, w = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(c for c in r for _ in range(scale)) for r in rows for _ in range(scale))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 3, 0, 0, 0))
            + chunk(b"PLTE", b"".join(bytes(c) for c in PALETTE))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def write_review(title, cs, tiles, blocks, map_png, sheet_png, path):
    def uri(png):
        return "data:image/png;base64," + base64.b64encode(png).decode()
    rows = "".join(f"<tr><td>{i}</td><td>{html.escape(t['name'])}</td><td>{t['col'] & 7}</td>"
                   f"<td>${t['flags']:02X}</td></tr>" for i, t in enumerate(tiles))
    brows = "".join(f"<tr><td>{i}</td><td>{html.escape(b['name'])}</td><td>{b['w']}x{b['h']}</td></tr>"
                    for i, b in enumerate(blocks))
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} Tileset</title>
<style>
:root{{--bg:#16130f;--fg:#efe6d4;--muted:#a89a80;--line:#3a3227;--acc:#e0a040}}
@media (prefers-color-scheme: light){{:root:not([data-theme="dark"]){{--bg:#f6f1e7;--fg:#241d12;--muted:#6d604a;--line:#d9cdb5;--acc:#a8650a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px;color:var(--acc)}}
p{{color:var(--muted);margin:0 0 12px}}
img{{image-rendering:pixelated;max-width:100%;height:auto;border:1px solid var(--line)}}
table{{border-collapse:collapse;font-size:13px}} td{{padding:2px 10px;border-bottom:1px solid var(--line)}}
.cols{{display:flex;gap:32px;flex-wrap:wrap}}
</style></head><body><main>
<h1>{html.escape(title)} tileset</h1>
<p>{len(cs.data)} of 256 characters used &middot; {len(tiles)} tiles &middot; {len(blocks)} blocks</p>
<h2>Map</h2><img src="{uri(map_png)}" alt="Full map preview" width="1024">
<h2>Charset</h2><img src="{uri(sheet_png)}" alt="Character set" width="576">
<div class="cols"><div><h2>Tiles</h2><table><tr><td>#</td><td>name</td><td>colour</td><td>flags</td></tr>{rows}</table></div>
<div><h2>Blocks</h2><table><tr><td>#</td><td>name</td><td>size</td></tr>{brows}</table></div></div>
</main></body></html>"""
    path.write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tileset", type=pathlib.Path)
    args = ap.parse_args()
    src = args.tileset.resolve()
    d = load_def(src)
    title = getattr(d, "TITLE", src.stem)
    prefix = getattr(d, "OUTPUT", src.stem)
    cs, tiles, blocks, named_hires, grid = build(d)
    here = src.parent
    (here / f"{prefix}_charset.bin").write_bytes(cs.binary())
    print(f"wrote {prefix}_charset.bin: {len(cs.data)} characters")
    asm = here / f"{prefix}_tiles.asm"
    write_asm(d, title, cs, tiles, blocks, named_hires, grid, asm)
    print(f"wrote {asm.name}: {len(tiles)} tiles, {len(blocks)} blocks, map {len(grid[0])}x{len(grid)}")
    preview = getattr(d, "PREVIEW", None)
    extra = preview() if callable(preview) else (preview or [])
    map_png = png_bytes(render_map(cs, tiles, blocks, grid, d.BG, extra))
    colours = {}
    for t in tiles:
        for c in t["codes"]:
            colours[c] = t["col"]
    for b in blocks:
        for c in b["codes"]:
            colours[c] = b["col"]
    sheet_png = png_bytes(render_charset(cs, d.BG, colours), 2)
    page = here / f"{prefix}_review.html"
    write_review(title, cs, tiles, blocks, map_png, sheet_png, page)
    print(f"wrote {page.name}")


if __name__ == "__main__":
    main()
