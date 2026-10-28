#!/usr/bin/env python3
"""
Sprite bank tool: build C64 sprite banks from Python art files.

A bank is a Python file that defines:
  GROUPS     [(KEY, "Title", builder), ...]; each builder returns a list of Sprite
optional:
  TITLE      name used in generated comments (default: the file's stem)
  MC0, MC1   shared multicolor registers $D025 / $D026 (default 0 black, 1 white)
  PLAYER, ENEMY, TERRAIN   preview colours for the review page (7, 6, 8)
  ASM_NOTES  extra comment lines for the top of the .asm file
  TEMPLATE   review page template next to the bank (default review_template.html);
             its /*SPRITE_DATA*/null placeholder receives the bank as JSON
  OUTPUT_ASM, OUTPUT_HTML  output names (default sprites.asm, sprite_review.html)

Outputs next to the bank: KickAssembler data (.align 64, SPR_<KEY> index
constants, per-frame colour and multicolor tables), the review page, and with
--png a contact sheet.

Multicolor cell legend:  .  transparent   K  $D025 (MC0, bits 01)
                         F  sprite colour (bits 10)   G  $D026 (MC1, bits 11)
                         t  track link, s  scoop: animated G/K (see animate)
Hires cell legend:       .  transparent   #  sprite colour

  python sprite_tool.py ../../game_dev/ironfront/sprites/ironfront_sprites.py --png sheet.png
"""
import argparse
import importlib.util
import json
import pathlib
import struct
import sys
import zlib

# Pepto PAL palette
PALETTE = [
    "#000000", "#FFFFFF", "#68372B", "#70A4B2", "#6F3D86", "#588D43", "#352879", "#B8C76F",
    "#6F4F25", "#433900", "#9A6759", "#444444", "#6C6C6C", "#9AD284", "#6C5EB5", "#959595",
]
DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
MC_W, HR_W, H = 12, 24, 21


class Sprite:
    def __init__(self, group, name, rows, mode="mc", color=None, delay=8):
        assert len(rows) == H, (group, name, len(rows))
        width = MC_W if mode == "mc" else HR_W
        assert all(len(r) == width for r in rows), (group, name)
        self.group, self.name, self.rows = group, name, rows
        self.mode = mode
        self.color = color  # None = faction colour chosen at runtime
        self.delay = delay

    def bytes(self):
        out = []
        for row in self.rows:
            bits = ""
            if self.mode == "mc":
                for ch in row:
                    bits += {".": "00", "K": "01", "F": "10", "G": "11"}[ch]
            else:
                for ch in row:
                    bits += "1" if ch == "#" else "0"
            out += [int(bits[i:i + 8], 2) for i in range(0, 24, 8)]
        return out + [0]


def blank(width=MC_W):
    return [["."] * width for _ in range(H)]


def to_rows(grid):
    return ["".join(r) for r in grid]


def mirror_h(rows):
    return [r[::-1] for r in rows]


def stamp(grid, art, col, row):
    for r, line in enumerate(art):
        for c, ch in enumerate(line):
            if ch != "." and 0 <= row + r < H and 0 <= col + c < len(grid[0]):
                grid[row + r][col + c] = ch



# ---------------------------------------------------------------- art helpers
# Directional art is drawn on 21 rows x 12 cells with the pivot at cell
# column 6, row 10, so mirrors and flips keep the unit centred.
def art(*lines, top=0):
    rows = ["." * MC_W] * top + list(lines)
    return rows + ["." * MC_W] * (H - len(rows))


def flip_v(rows):
    return rows[::-1]


def mirror_c(rows):
    # mirror about cell column 6 so the pivot stays put (column 0 is dropped)
    return ["." + "".join(r[12 - c] for c in range(1, MC_W)) for r in rows]


def animate(rows, phase, t_axis, s_axis):
    out = []
    for r, line in enumerate(rows):
        cells = []
        for c, ch in enumerate(line):
            if ch in "ts":
                k = r if (t_axis if ch == "t" else s_axis) == "row" else c
                ch = "G" if (k + phase) % 2 == 0 else "K"
            cells.append(ch)
        out.append("".join(cells))
    return out


def hires_from(art):
    rows = [line.ljust(HR_W, ".") for line in art]
    return rows + ["." * HR_W] * (H - len(rows))


def hires_canvas(fn):
    grid = [["."] * HR_W for _ in range(H)]
    for r in range(H):
        for c in range(HR_W):
            if fn(c - 11.5, r - 10):
                grid[r][c] = "#"
    return to_rows(grid)


def noise(c, r, k):
    n = (c * 374761393 + r * 668265263 + k * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 0xFFFF


# ---------------------------------------------------------------- output
def load_bank(path):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(bank):
    sprites, groups = [], []
    for key, title, fn in bank.GROUPS:
        items = fn()
        groups.append({"key": key, "title": title, "base": len(sprites), "count": len(items)})
        sprites += items
    return sprites, groups


def setting(bank, name, default):
    return getattr(bank, name, default)


def write_asm(bank, sprites, groups, path):
    lines = [
        f"// {setting(bank, 'TITLE', path.stem)} sprite bank - generated by tools/sprites/sprite_tool.py, do not edit by hand",
        f"// {len(sprites)} sprites x 64 bytes = {len(sprites) * 64} bytes",
        f"// Multicolor: $D025 = {setting(bank, 'MC0', 0)} (MC0), $D026 = {setting(bank, 'MC1', 1)} (MC1)",
    ]
    lines += [f"// {note}" for note in setting(bank, "ASM_NOTES", [])]
    lines += ["", f".const SPR_COUNT = {len(sprites)}"]
    for g in groups:
        lines.append(f".const SPR_{g['key']} = {g['base']}  // {g['count']} frames")
    lines += ["", "// Fixed sprite colours per frame ($FF = faction colour)", "sprite_colours:"]
    cols = [s.color if s.color is not None else 0xFF for s in sprites]
    for i in range(0, len(cols), 16):
        lines.append("    .byte " + ",".join(f"${c:02X}" for c in cols[i:i + 16]))
    lines.append("sprite_multicolor:")
    mcs = [1 if s.mode == "mc" else 0 for s in sprites]
    for i in range(0, len(mcs), 16):
        lines.append("    .byte " + ",".join(str(m) for m in mcs[i:i + 16]))
    lines += ["", ".align 64", "sprite_bank:"]
    for i, s in enumerate(sprites):
        lines.append(f"// {i:3d}  {s.group} {s.name}")
        data = s.bytes()
        for j in range(0, 64, 16):
            lines.append("    .byte " + ",".join(f"${b:02X}" for b in data[j:j + 16]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(bank, sprites, groups, template, path):
    data = {
        "palette": PALETTE,
        "mc0": setting(bank, "MC0", 0), "mc1": setting(bank, "MC1", 1),
        "player": setting(bank, "PLAYER", 7), "enemy": setting(bank, "ENEMY", 6),
        "terrain": setting(bank, "TERRAIN", 8),
        "dirs": DIRS,
        "groups": groups,
        "sprites": [
            {"g": s.group, "n": s.name, "m": s.mode, "c": s.color, "d": s.delay, "r": s.rows}
            for s in sprites
        ],
    }
    html = template.read_text(encoding="utf-8").replace("/*SPRITE_DATA*/null", json.dumps(data, separators=(",", ":")))
    path.write_text(html, encoding="utf-8")


def write_png(sprites, path, scale=3, per_row=16, mc0=0, mc1=1, faction=7):
    bg = (0x58, 0x8D, 0x43)
    rgb = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in PALETTE]
    cell_w, cell_h = (HR_W + 2) * scale, (H + 2) * scale
    rows_n = (len(sprites) + per_row - 1) // per_row
    W, Hh = per_row * cell_w, rows_n * cell_h
    px = [[bg] * W for _ in range(Hh)]
    for i, s in enumerate(sprites):
        ox, oy = (i % per_row) * cell_w + scale, (i // per_row) * cell_h + scale
        colour = rgb[s.color if s.color is not None else faction]
        for r, line in enumerate(s.rows):
            for c, ch in enumerate(line):
                if ch == ".":
                    continue
                if s.mode == "mc":
                    col = {"K": rgb[mc0], "G": rgb[mc1], "F": colour}[ch]
                    xs = (2 * c, 2 * c + 1)
                else:
                    col, xs = colour, (c,)
                for x in xs:
                    for yy in range(scale):
                        for xx in range(scale):
                            px[oy + r * scale + yy][ox + x * scale + xx] = col
    raw = b"".join(b"\x00" + bytes(v for p in row for v in p) for row in px)

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, Hh, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bank", type=pathlib.Path)
    ap.add_argument("--png", type=pathlib.Path, help="also write a contact-sheet PNG here")
    args = ap.parse_args()
    bank_path = args.bank.resolve()
    here = bank_path.parent
    bank = load_bank(bank_path)
    sprites, groups = build(bank)
    asm = here / setting(bank, "OUTPUT_ASM", "sprites.asm")
    write_asm(bank, sprites, groups, asm)
    print(f"wrote {asm.name}: {len(sprites)} sprites, {len(sprites) * 64} bytes")
    template = here / setting(bank, "TEMPLATE", "review_template.html")
    if template.is_file():
        page = here / setting(bank, "OUTPUT_HTML", "sprite_review.html")
        write_html(bank, sprites, groups, template, page)
        print(f"wrote {page.name}")
    if args.png:
        write_png(sprites, args.png, mc0=setting(bank, "MC0", 0), mc1=setting(bank, "MC1", 1),
                  faction=setting(bank, "PLAYER", 7))


if __name__ == "__main__":
    main()
