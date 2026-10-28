#!/usr/bin/env python3
"""
Koala screen tool: compose a C64 multicolor bitmap in Python, enforce the
hardware colour rule, and write a Koala Painter file.

The canvas is 160x100 "art pixels": each is one multicolor pixel wide and two
rasterlines tall (a 2x2 block on screen), so 4x4 art pixels make one 4x8 cell.
After composing, every cell keeps the background colour plus its three most
used colours; other pixels move to the nearest allowed colour, and those cells
are reported so they can be reviewed.

A scene is a Python file that defines:
  compose(cv)              draw onto the Canvas; return a dict of extras (or None)
optional:
  OUTPUT                   base name for outputs (default: the scene file's stem)
  BG                       background colour index (default 0, black)
  write_review(result)     build a review page; result has .final .raw .clashes
                           .extras .here .palette .bg and .hexrows(px)

Outputs next to the scene: <OUTPUT>.kla (load address $6000), plus a 2x
preview PNG with --png.

  python koala_tool.py ../../game_dev/ironfront/loading/loading_scene.py --png preview.png
"""
import argparse
import importlib.util
import math
import pathlib
import struct
import sys
import types
import zlib

PALETTE = [
    "#000000", "#FFFFFF", "#68372B", "#70A4B2", "#6F3D86", "#588D43", "#352879", "#B8C76F",
    "#6F4F25", "#433900", "#9A6759", "#444444", "#6C6C6C", "#9AD284", "#6C5EB5", "#959595",
]
RGB = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in PALETTE]
W, H = 160, 100  # art pixels

BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = 0, 1, 2, 3, 4, 5, 6, 7
ORANGE, BROWN, LRED, DGREY, GREY, LGREEN, LBLUE, LGREY = 8, 9, 10, 11, 12, 13, 14, 15

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def bayer(x, y):
    return (BAYER[y % 4][x % 4] + 0.5) / 16


def noise(x, y, k=0):
    n = (x * 374761393 + y * 668265263 + k * 1442695041) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n & 0xFFFF) / 0xFFFF


def smooth_noise(x, y, k=0, scale=4.0):
    # bilinear value noise: soft, billowing variation instead of per-pixel speckle
    fx, fy = x / scale, y / scale
    ix, iy = math.floor(fx), math.floor(fy)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a, b = noise(ix, iy, k), noise(ix + 1, iy, k)
    c, d = noise(ix, iy + 1, k), noise(ix + 1, iy + 1, k)
    return (a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty


# ---------------------------------------------------------------- PNG in/out
def read_png(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, plte = 8, b"", None
    while pos < len(data):
        ln, = struct.unpack(">I", data[pos:pos + 4])
        tag, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            plte = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif tag == b"IDAT":
            idat += body
    assert depth == 8 and interlace == 0, "only 8-bit non-interlaced PNGs"
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw, stride = zlib.decompress(idat), w * ch
    prev, i, px = bytearray(stride), 0, []
    for _ in range(h):
        f = raw[i]
        line = bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        for x in range(stride):
            a = line[x - ch] if x >= ch else 0
            b = prev[x]
            c = prev[x - ch] if x >= ch else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        row = []
        for x in range(w):
            v = line[x * ch:(x + 1) * ch]
            if ctype == 3:
                row.append((plte[v[0]], 255))
            elif ctype in (2, 6):
                row.append((tuple(v[:3]), v[3] if ctype == 6 else 255))
            else:
                row.append(((v[0],) * 3, v[1] if ctype == 4 else 255))
        px.append(row)
        prev = line
    return w, h, px


def write_png(path, idx_rows, sx, sy):
    h, w = len(idx_rows), len(idx_rows[0])
    raw = b""
    for row in idx_rows:
        line = b"".join(bytes(RGB[c]) * sx for c in row)
        raw += (b"\x00" + line) * sy

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * sx, h * sy, 8, 2, 0, 0, 0))
    path.write_bytes(png + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, bg=BLACK):
        self.bg = bg
        self.px = [[bg] * W for _ in range(H)]

    def put(self, x, y, c):
        if 0 <= x < W and 0 <= y < H and c is not None:
            self.px[y][x] = c

    def blit(self, art, ox, oy, colours):
        for r, line in enumerate(art):
            for c, ch in enumerate(line):
                if ch != ".":
                    self.put(ox + c, oy + r, colours[ch])


# ---------------------------------------------------------------- text
FONT3 = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"], "C": ["###", "#..", "#..", "#..", "###"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."], "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."], "I": ["###", ".#.", ".#.", ".#.", "###"],
    "L": ["#..", "#..", "#..", "#..", "###"], "O": ["###", "#.#", "#.#", "#.#", "###"],
    "P": ["###", "#.#", "###", "#..", "#.."], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": ["###", "#..", "###", "..#", "###"], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "W": ["#.#", "#.#", "#.#", "###", "#.#"], "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    " ": ["...", "...", "...", "...", "..."],
}


def small_text(cv, text, x0, y0, colour):
    for i, ch in enumerate(text):
        for r, line in enumerate(FONT3[ch]):
            for c, bit in enumerate(line):
                if bit == "#":
                    cv.put(x0 + i * 4 + c, y0 + r, colour)


def big_text(cv, text, font, y0, scale, gap, ramp):
    """Centred text from a fixed-width font, scaled; ramp gives a colour per pixel row."""
    width = len(font[text[0]][0])
    pitch = width * scale + gap
    x0 = (W - (len(text) * pitch - gap)) // 2
    for i, ch in enumerate(text):
        for r, line in enumerate(font[ch]):
            for c, bit in enumerate(line):
                if bit == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            cv.put(x0 + i * pitch + c * scale + dx, y0 + r * scale + dy, ramp[r * scale + dy])


# ---------------------------------------------------------------- C64 limits
def fit_cells(cv):
    """Keep BG + the 3 most-used colours per 4x8 cell (4x4 art pixels)."""
    cells, clashes = [], []
    for cy in range(H // 4):
        for cx in range(W // 4):
            counts = {}
            for y in range(cy * 4, cy * 4 + 4):
                for x in range(cx * 4, cx * 4 + 4):
                    c = cv.px[y][x]
                    if c != cv.bg:
                        counts[c] = counts.get(c, 0) + 1
            keep = sorted(counts, key=lambda c: (-counts[c], c))[:3]
            if len(counts) > 3:
                clashes.append(cy * (W // 4) + cx)
                allowed = keep + [cv.bg]
                for y in range(cy * 4, cy * 4 + 4):
                    for x in range(cx * 4, cx * 4 + 4):
                        c = cv.px[y][x]
                        if c not in allowed:
                            cv.px[y][x] = min(allowed, key=lambda a: sum((p - q) ** 2 for p, q in zip(RGB[a], RGB[c])))
            cells.append(keep + [cv.bg] * (3 - len(keep)))
    return cells, clashes


def koala(cv, cells):
    """Koala layout: $6000 load address, 8000 bitmap, 1000 screen, 1000 colour, bg."""
    bitmap = bytearray(8000)
    screen = bytearray(1000)
    colour = bytearray(1000)
    for ci, (c1, c2, c3) in enumerate(cells):
        cy, cx = divmod(ci, 40)
        screen[ci] = (c1 << 4) | c2
        colour[ci] = c3
        code = {cv.bg: 0}
        for n, c in ((1, c1), (2, c2), (3, c3)):
            code.setdefault(c, n)
        for line in range(8):
            y = cy * 4 + line // 2
            byte = 0
            for k in range(4):
                byte = (byte << 2) | code[cv.px[y][cx * 4 + k]]
            bitmap[ci * 8 + line] = byte
    return bytes([0x00, 0x60]) + bytes(bitmap) + bytes(screen) + bytes(colour) + bytes([cv.bg])


def load_scene(path):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render(scene_path, png=None):
    scene = load_scene(scene_path)
    cv = Canvas(getattr(scene, "BG", BLACK))
    extras = scene.compose(cv) or {}
    raw = [row[:] for row in cv.px]
    cells, clashes = fit_cells(cv)
    here = scene_path.parent
    out = here / (getattr(scene, "OUTPUT", scene_path.stem) + ".kla")
    out.write_bytes(koala(cv, cells))
    print(f"wrote {out.name}: {len(clashes)} of 1000 cells needed colour fixes")
    if png:
        write_png(png, cv.px, 4, 4)
    if hasattr(scene, "write_review"):
        result = types.SimpleNamespace(final=cv.px, raw=raw, clashes=clashes, extras=extras, here=here,
                                       palette=PALETTE, bg=cv.bg,
                                       hexrows=lambda px: ["".join("%x" % c for c in row) for row in px])
        page = scene.write_review(result)
        if page:
            print(f"wrote {pathlib.Path(page).name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scene", type=pathlib.Path)
    ap.add_argument("--png", type=pathlib.Path, help="also write a 2x preview PNG here")
    args = ap.parse_args()
    render(args.scene.resolve(), args.png)


if __name__ == "__main__":
    main()
