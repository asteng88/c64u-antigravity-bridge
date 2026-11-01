"""
HELISCAPE world art - tileset file for tools/charset/tileset_tool.py.

Everything is a BLOCK. The parallax layers are simply very wide blocks, so
block_chars holds them row-major and the game reads them directly with col & 127.

Screen layout (the raster splits in src/irq.asm change $D021-$D023 per band):

  rows  0-1   clouds     slow parallax      .  sky   ,  next sky band   #  under-lit   o  cloud
  row   2-8   sky + sun  static, dithered gradient between bands
  rows  9-12  mesas      1/4 speed          .  sky   ,  lit face        #  shadow      o  rock
  rows 13-15  dunes      1/2 speed          .  mesa  ,  dune body       #  crest       o  shade
  rows 16-19  plain and buildings, full speed   .  plain  ,  black      #  concrete    o  per block
  rows 20-21  ground, full speed            .  sand  ,  dark sand       #  light       o  per block
  rows 22-24  HUD, hires font

Build:  python tools/charset/tileset_tool.py game_dev/Heliscape/map/heliscape_map.py
"""
import math

TITLE = "HELISCAPE"
OUTPUT = "heliscape"
BG = (8, 9, 10)
BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = range(8)

WORLD_COLS = 256
FAR_W, FAR_H = 128, 4
MID_W, MID_H = 128, 3
CLOUD_W, CLOUD_H = 128, 2
PLAIN_W, PLAIN_H = 128, 4
GROUND_W, GROUND_H = 128, 2

CONSTS = {
    "WORLD_COLS": WORLD_COLS,
    "FAR_W": FAR_W, "FAR_H": FAR_H, "MID_W": MID_W, "MID_H": MID_H,
    "CLOUD_W": CLOUD_W, "CLOUD_H": CLOUD_H, "PLAIN_W": PLAIN_W, "PLAIN_H": PLAIN_H,
    "GROUND_W": GROUND_W, "GROUND_H": GROUND_H,
}


def h(c, r, k=0):
    n = (c * 374761393 + r * 668265263 + k * 2147483647) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return (n >> 8) & 0xFFFF


class Canvas:
    """Pixel canvas in multicolor pixels; .art gives the rows for a BLOCK."""

    def __init__(self, w, h_, fill="."):
        self.w, self.h = w, h_
        self.px = [[fill] * w for _ in range(h_)]

    def put(self, x, y, ch):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = ch

    def rect(self, x0, y0, x1, y1, ch):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, ch)

    def stamp(self, x, y, rows):
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                if ch != " ":
                    self.put(x + c, y + r, ch)

    @property
    def art(self):
        return ["".join(r) for r in self.px]


def stands_on_ground(rows):
    """The colours of "," and "#" change during the line above the ground (src/irq.asm)."""
    return rows[:-1] + [rows[-1].replace(",", ".").replace("#", ".")]


def tile_row(canvas, cx, cy, rows):
    canvas.stamp(cx * 4, cy * 8, rows)


# ---------------------------------------------------------------- sky
# their last two lines are solid: the raster split changes the sky colour behind them
DITHER_A = ["....", "...,", "....", ".,.,", ",.,.", ".,,,", ",,,,", ",,,,"]
DITHER_B = ["....", ".,..", "....", ",.,.", ".,.,", ",,.,", ",,,,", ",,,,"]


def clouds():
    """Long thin dusk clouds: rows of a few reusable cap/body/end chars."""
    cap_l = ["....", "....", "....", "....", "...o", "..oo", ".ooo", "oooo"]
    cap = ["....", "....", "....", "..oo", ".ooo", "oooo", "oooo", "oooo"]
    cap2 = ["....", "....", "ooo.", "oooo", "oooo", "oooo", "oooo", "oooo"]
    cap_r = ["....", "....", "....", "....", "o...", "oo..", "ooo.", "oooo"]
    body = ["oooo", "oooo", "oooo", "oooo", "oooo", "#o#o", "####", "#.#."]
    end_l = ["oooo", "oooo", ".ooo", ".#oo", "..##", "....", "....", "...."]
    end_r = ["oooo", "oooo", "ooo.", "oo#.", "##..", "....", "....", "...."]
    empty = ["...."] * 8
    c = Canvas(CLOUD_W * 4, CLOUD_H * 8)
    # (start column, length) of each cloud bank on the 128-column loop
    for start, length, row in ((6, 9, 0), (34, 5, 0), (58, 12, 0), (92, 7, 0), (116, 6, 0)):
        for i in range(length):
            x = start + i
            pick = cap_l if i == 0 else cap_r if i == length - 1 else (cap2 if h(x, 1) & 1 else cap)
            tile_row(c, x % CLOUD_W, row, pick)
            pick = end_l if i == 0 else end_r if i == length - 1 else body
            tile_row(c, x % CLOUD_W, row + 1, pick)
    return c.art


def sun():
    """Low sun over the mesas: five rows, banded toward the horizon."""
    w, ht = 6 * 4, 5 * 8
    c = Canvas(w, ht)
    cx, cy, rad = (w - 1) / 2, 20.5, 19.0
    for y in range(ht):
        for x in range(w):
            dx, dy = (x - cx) * 2, y - cy
            d = math.hypot(dx, dy)
            if d > rad:
                continue
            ch = "o"
            if d > rad - 3.2:
                ch = "#"
            if y >= 24 and (y - 24) % 5 >= 3:          # retro bands, widening
                ch = "."
            elif y >= 14 and d > rad - 6 and (x + y) % 2:
                ch = "#"
            c.put(x, y, ch)
    return c.art


# ---------------------------------------------------------------- terrain profiles
def shape_char(a, b, base, style, tex=0):
    """One char of terrain. a/b = surface height in pixels at the char's edges, base = height of its bottom row."""
    rows = [["."] * 4 for _ in range(8)]
    for x in range(4):
        surface = int(round(a + (b - a) * (x + 0.5) / 4))
        for y in range(8):
            above_ground = base + 7 - y
            if above_ground < surface:
                rows[y][x] = style(surface - 1 - above_ground, y, x, b - a, tex)
    return ["".join(r) for r in rows]


def far_style(depth, y, x, slope, tex):
    if depth == 0:
        return ","                                   # sunlit rim
    if slope > 0 and depth <= 2:
        return ","                                   # lit west face
    if slope < 0 and depth <= 2:
        return "#"                                   # shadowed east face
    if tex and y == tex:
        return "#"                                   # rock strata
    return "o"


def mid_style(depth, y, x, slope, tex):
    if depth == 0:
        return "#"                                   # crest catches the sun
    if depth == 1:
        return "o"                                   # shade under the crest
    if tex and y == 3 and x == 1:
        return "o"
    return ","


def profile_layer(heights, width, rows, style, tex_every):
    """heights[c] is the height in pixels at the left edge of column c (looped)."""
    c = Canvas(width * 4, rows * 8)
    for col in range(width):
        a, b = heights[col], heights[(col + 1) % width]
        for row in range(rows):
            base = (rows - 1 - row) * 8
            if max(a, b) <= base:
                continue
            tex = 0
            if min(a, b) >= base + 8:
                v = h(col, row, 11)
                tex = (3 + 2 * ((v >> 4) % 2)) if v % tex_every == 0 else 0
            tile_row(c, col, row, shape_char(a, b, base, style, tex))
    return c.art


def far_heights():
    """Flat-topped mesas with steep sides, quantised so few distinct chars result."""
    # (height, columns) runs; heights move in 4-pixel steps so shapes stay reusable
    runs = [(4, 5), (8, 2), (16, 3), (24, 2), (28, 8), (24, 1), (16, 2), (8, 2), (4, 6), (8, 3), (12, 2), (20, 5),
            (20, 2), (16, 2), (8, 2), (4, 4), (8, 2), (20, 2), (28, 2), (28, 9), (32, 3), (28, 2), (16, 2), (12, 4),
            (8, 3), (4, 5), (8, 2), (12, 5), (20, 3), (24, 6), (16, 2), (8, 4), (4, 8), (8, 4), (4, 4)]
    out = []
    for height, n in runs:
        out += [height] * n
    return (out + [4] * FAR_W)[:FAR_W]


def mid_heights():
    out = []
    for c in range(MID_W):
        a = math.sin(c * 2 * math.pi / MID_W * 3) * 5
        b = math.sin(c * 2 * math.pi / MID_W * 7 + 1.3) * 3
        out.append(int(round((14 + a + b) / 2)) * 2)
    return out


# ---------------------------------------------------------------- near ground
def plain():
    streak_a = ["....", "....", "....", "....", "....", "....", ".oo.", "...."]
    streak_b = ["....", "....", "oo..", "....", "....", "...o", "....", "...."]
    streak_c = ["....", ".o..", "....", "....", "..oo", "....", "....", "...."]
    dense_a = ["....", ".oo.", "....", "o..o", "....", ".oo.", "o...", "..oo"]
    dense_b = ["..o.", "....", "oo..", "....", "..oo", "o...", "..o.", "oo.o"]
    empty = ["...."] * 8
    c = Canvas(PLAIN_W * 4, PLAIN_H * 8)
    for col in range(PLAIN_W):
        for row in range(PLAIN_H):
            v = h(col, row, 3) % 16
            if row == 3:
                pick = dense_a if v % 2 else dense_b
            elif row == 2:
                pick = (streak_a, streak_b, streak_c, dense_a)[v % 4]
            elif row == 1:
                pick = (streak_a, empty, streak_b, empty, streak_c, empty)[v % 6]
            else:
                pick = streak_a if v == 0 else streak_b if v == 1 else empty
            tile_row(c, col, row, pick)
    return c.art


def ground():
    # top two lines and bottom line all $D022: see the raster notes in src/irq.asm
    top_a = [",,,,", ",,,,", ",,.,", ".,.,", ",...", "...,", "....", "...."]
    top_b = [",,,,", ",,,,", ".,,,", ",.,.", "...,", ",...", "....", "...."]
    top_c = [",,,,", ",,,,", ",.,,", ".,.,", "..,.", "....", ".#..", "...."]
    low_a = ["....", ".##.", "....", "...,", "..,.", "....", ",.,.", ",,,,"]
    low_b = ["....", "....", "#...", "....", ".,..", ",..,", ".,,.", ",,,,"]
    low_c = ["..#.", "....", "....", "o...", "....", ".,.,", ",.,.", ",,,,"]
    c = Canvas(GROUND_W * 4, GROUND_H * 8)
    for col in range(GROUND_W):
        tile_row(c, col, 0, (top_a, top_b, top_c)[h(col, 0, 5) % 3])
        tile_row(c, col, 1, (low_a, low_b, low_c)[h(col, 1, 5) % 3])
    return c.art


# ---------------------------------------------------------------- buildings (concrete # on black , with o detail)
def compound():
    """POW camp: 8x3 chars. Blockhouse with barred windows, a guard tower and a flag."""
    c = Canvas(32, 24)
    # guard tower on the left
    c.rect(1, 2, 7, 3, ",")
    c.rect(2, 4, 6, 8, "#")
    c.rect(3, 5, 5, 6, ",")
    c.rect(2, 9, 2, 23, ",")
    c.rect(6, 9, 6, 23, ",")
    for y in range(10, 23, 4):
        for i in range(3):
            c.put(3 + i, y + i, ",")
    # blockhouse
    c.rect(9, 8, 31, 9, "o")
    c.rect(8, 10, 31, 23, "#")
    c.rect(8, 10, 31, 10, ",")
    c.rect(8, 23, 31, 23, ",")
    for x in (11, 19):                                  # barred windows
        c.rect(x, 13, x + 4, 18, ",")
        for bx in (x + 1, x + 3):
            c.rect(bx, 13, bx, 18, "o")
    c.rect(27, 13, 30, 23, ",")                         # door
    c.rect(28, 14, 29, 22, "o")
    # flag
    c.rect(20, 0, 20, 7, ",")
    c.rect(21, 0, 26, 3, "o")
    return c.art


def rubble():
    """Same footprint after the walls come down."""
    c = Canvas(32, 24)
    heights = [2, 3, 5, 4, 7, 9, 6, 4, 5, 8, 11, 8, 5, 3, 6, 9, 7, 5, 8, 10, 7, 4, 6, 3, 4, 7, 5, 4, 3, 2, 3, 2]
    for x, ht in enumerate(heights):
        for i in range(ht):
            y = 23 - i
            ch = "#"
            if i == ht - 1:
                ch = "o" if (x * 3) % 7 < 2 else "#"
            elif (x * 5 + i * 3) % 7 == 0:
                ch = ","
            c.put(x, y, ch)
    for x in (9, 10, 18, 19):                           # charred stumps
        c.rect(x, 9, x, 16, ",")
    return c.art


def hangar():
    """Home base: 12x4 chars, arched roof with a big open door."""
    c = Canvas(48, 32)
    for x in range(48):
        arch = 10 - (x - 23.5) ** 2 / 58
        top = int(round(12 - arch))
        for y in range(top, 32):
            c.put(x, y, "#" if y < 31 else ",")
        c.put(x, top, ",")
        if top + 1 < 12:
            c.put(x, top + 1, "o")
    c.rect(0, 12, 47, 12, ",")
    # door with the people-sized dark interior
    c.rect(5, 15, 30, 31, ",")
    for x in range(8, 30, 8):
        c.rect(x, 16, x, 19, "#")
    # marking on the wall: a cross
    c.rect(37, 17, 42, 26, "o")
    c.rect(35, 20, 44, 23, "o")
    return c.art


def tower():
    """Control tower: 3x4 chars."""
    c = Canvas(12, 32)
    c.rect(5, 0, 6, 4, ",")
    c.rect(1, 5, 10, 6, ",")
    c.rect(0, 7, 11, 11, "o")
    c.rect(2, 8, 2, 10, ",")
    c.rect(5, 8, 5, 10, ",")
    c.rect(8, 8, 8, 10, ",")
    c.rect(0, 12, 11, 12, ",")
    c.rect(3, 13, 8, 31, "#")
    c.rect(3, 13, 3, 31, ",")
    c.rect(8, 13, 8, 31, ",")
    for y in range(18, 30, 8):
        c.rect(5, y, 6, y + 1, ",")
    return c.art


def palm():
    """Palm tree: 3x3 chars (scenery, not solid)."""
    return [
        "............", "..o..oo.....", ".ooo.ooo.oo.", "oo.oo.oooooo", "o...ooooo..o", "...oooooo...",
        "..oo.o.ooo..", ".oo..,..ooo.", ".o...,...oo.", ".....,....o.", ".....,......", ".....,......",
        ".....,......", ".....,......", "....,.......", "....,.......",
        "....,.......", "....,.......", "....,.......", "....,.......", "....,.......", "....,.......",
        "....,.......", "....,.......",
    ]


def rock():
    """Boulders: 3x1."""
    return [
        "............", "....##......", "...####.....", "..##o###....", ".##o####.##.", ".#o###,#####",
        "######,#####", ",,,,,,,,,,,,",
    ]


def wreck():
    """Burnt-out truck: 2x1."""
    return [
        "..,,,...", ".####,,.", ".#,,#,,o", ".####,,,", ",,,,,,,,", ".,,...,,", ".,,...,,", "........",
    ]


def pad():
    """Helipad painted on the sand: 10x1 chars on the top ground row."""
    c = Canvas(40, 8)
    c.rect(0, 0, 39, 7, ",")                            # from the top line: see ground()
    c.rect(1, 2, 38, 2, "#")
    for x in range(4, 36, 8):
        c.rect(x, 4, x + 3, 5, "o")
    return c.art


# ---------------------------------------------------------------- title logo
# Letters are drawn on a coarse 7x6 grid (the 8th column is the gap); each cell is
# 2x4 multicolor pixels, so a char is one of 16 quads and the logo needs few characters.
LETTERS = {
    "H": ["##...##", "##...##", "#######", "##...##", "##...##", "##...##"],
    "E": ["#######", "##.....", "#####..", "##.....", "##.....", "#######"],
    "L": ["##.....", "##.....", "##.....", "##.....", "##.....", "#######"],
    "I": ["..###..", "...#...", "...#...", "...#...", "...#...", "..###.."],
    "S": [".######", "##.....", ".#####.", ".....##", ".....##", "######."],
    "C": [".######", "##.....", "##.....", "##.....", "##.....", ".######"],
    "A": [".#####.", "##...##", "##...##", "#######", "##...##", "##...##"],
    "P": ["######.", "##...##", "##...##", "######.", "##.....", "##....."],
}


def letter(ch):
    c = Canvas(16, 24)
    for gy, line in enumerate(LETTERS[ch]):
        for gx, cell in enumerate(line):
            if cell == "#":
                c.rect(gx * 2, gy * 4, gx * 2 + 1, gy * 4 + 3, "o")
                if gy % 2:
                    c.rect(gx * 2, gy * 4 + 3, gx * 2 + 1, gy * 4 + 3, "#")   # chrome line, once per char
    return c.art


# ---------------------------------------------------------------- HUD glyphs (hires)
HIRES = {
    "BAR": ["........", "#######.", "#######.", "#######.", "#######.", "#######.", "#######.", "........"],
    "BAR_OFF": ["........", "#.#.#.#.", "........", "#.....#.", "........", "#.....#.", "#.#.#.#.", "........"],
    "R_DOT": ["........", "........", "........", "...#....", "........", "........", "........", "........"],
    "R_BLIP": ["........", "........", "..###...", "..###...", "..###...", "........", "........", "........"],
    "R_CHOP": ["........", ".#####..", "...#....", "#.####..", "#######.", "..####..", "..#..#..", ".#####.."],
    "R_CAMP": ["........", ".######.", ".#.##.#.", ".#.##.#.", ".######.", ".#....#.", ".#....#.", "........"],
    "R_BASE": ["...#....", "..###...", ".#####..", "#######.", ".#####..", ".#.#.#..", ".#.#.#..", "........"],
    "LIFE": ["........", "#######.", "...#....", "#.####..", "#######.", "..####..", ".#####..", "........"],
}

# ---------------------------------------------------------------- the world
TILES = [("UNUSED", ["...."[:4] * 2] * 16, GREEN, 0)]   # the game only uses blocks
MAP = ["."]
LEGEND = {".": "UNUSED"}

BLOCKS = [
    ("DITHER_A", DITHER_A, BLUE),
    ("DITHER_B", DITHER_B, BLUE),
    ("CLOUDS", clouds(), PURPLE),
    ("SUN", sun(), WHITE),
    ("FAR", profile_layer(far_heights(), FAR_W, FAR_H, far_style, 6), PURPLE),
    ("MID", profile_layer(mid_heights(), MID_W, MID_H, mid_style, 5), RED),
    ("PLAIN", plain(), RED),
    ("GROUND", ground(), YELLOW),
    ("COMPOUND", stands_on_ground(compound()), RED),
    ("RUBBLE", stands_on_ground(rubble()), RED),
    ("HANGAR", stands_on_ground(hangar()), CYAN),
    ("TOWER", stands_on_ground(tower()), CYAN),
    ("PALM", stands_on_ground(palm()), GREEN),
    ("ROCK", stands_on_ground(rock()), RED),
    ("WRECK", stands_on_ground(wreck()), RED),
    ("PAD", pad(), WHITE),
] + [(f"L_{ch}", letter(ch), WHITE) for ch in "HELISCAP"]

# Scenery is shared by all levels with the same palette. Camps, tanks and turrets are
# per level, in heliscape_levels.py (which keeps them clear of this scenery).
KINDS = ["PALM", "ROCK", "WRECK"]
PALETTES = 6
# the game walks this table with a one-byte index: at most 63 entries (4 bytes each)
_SPOTS = [36, 42, 52, 92, 118, 146, 186, 196, 218, 245]
_SETS = [
    "PPRWPRPWRPPR",
    "RPPWRPPRWRPP",
    "PPWRPPRWPRPR",
    "RWPPRWPPRPWR",
    "PRPPWRPRPWPR",
    "WPRPPRWPPRPP",
]
_NAMES = {"P": "PALM", "R": "ROCK", "W": "WRECK"}
OBJECTS = [(_NAMES[ch], col, 1 << pal, 0) for pal, row in enumerate(_SETS) for col, ch in zip(_SPOTS, row)]
assert len(OBJECTS) <= 63


def PREVIEW():
    return []
