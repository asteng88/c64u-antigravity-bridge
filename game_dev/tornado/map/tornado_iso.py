"""
TORNADO archipelago - isometric terrain for tools/isotiles/iso_tool.py.

Same islands as tornado_map.py, with smoothed coastlines, drawn as raised
isometric land: sand beaches sit just above the sea, grass a little higher, and
the island interiors rise in 16 px steps to hills (one level inland, two in the
middle of the big islands) with sandstone cliff walls: lit on the left, in
shadow on the right. Palms and rocks rise above their diamonds.

Colours: $D021 = 6 deep blue sea, $D022 = 7 sand yellow, $D023 = 0 black;
colour RAM per character: cyan waves, green grass/palms, red lips and rock.
"""
import math

import tornado_map as base

TITLE = "TORNADO"
OUTPUT = "tornado"
BG = (6, 7, 0)
WHITE, RED, CYAN, GREEN = 1, 2, 3, 5

LAND, BASE, HAZARD = 0x01, 0x02, 0x04
CONSTS = {"TF_LAND": LAND, "TF_BASE": BASE, "TF_HAZARD": HAZARD}

ISO_W, ISO_H = 32, 128           # 1024 x 1024 world pixels
FONT_KEEP = " !+-./:=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _inside(lx, ly, k=1.0):
    return abs(lx) / 16 + abs(ly) / 8 <= k


# ---------------------------------------------------------------- surfaces
def calm(lx, ly):
    return "."


def sea(lx, ly):
    # short wave crests in two staggered rows
    if ly == 2.5 and -9 <= lx <= -3:
        return CYAN
    if ly == -3.5 and 5 <= lx <= 11:
        return CYAN
    return "."


def sand(lx, ly):
    if (lx, ly) in ((-5, 0.5), (7, -2.5), (1, 3.5)):
        return RED
    return ","


def grass(lx, ly):
    if (lx, ly) in ((-7, -0.5), (5, 1.5), (-1, -4.5), (9, -1.5)):
        return "#"
    if (lx, ly) in ((3, -2.5), (-9, 1.5)):
        return ","
    return GREEN


# The helipad: one big diamond (64x32) made of four diamonds - top, left,
# right, bottom - each painting its quarter of a white H inside a white circle
# on yellow concrete with a dark edge (circle black, H white).
PAD_TOP = (64, 880)             # centre of the top diamond; the pad's centre is 8 px below
PAD_PARTS = {"PAD_T": (0, -8), "PAD_L": (-16, 0), "PAD_R": (16, 0), "PAD_B": (0, 8)}


def pad_art(gx, gy):
    """Pixel at (gx, gy) from the pad's centre."""
    if abs(gx) / 32 + abs(gy) / 16 > 0.9:
        return "#"                                 # dark rim
    e = (gx / 23) ** 2 + (gy / 11.5) ** 2
    if 0.62 < e <= 1:
        return "#"                                 # the circle (no colour RAM needed)
    if (5 <= abs(gx) <= 9 and abs(gy) <= 6.5) or (abs(gx) <= 9 and abs(gy) <= 1.5):
        return WHITE                               # the H
    return ","


def _pad_part(ox, oy):
    return lambda lx, ly: pad_art(lx + ox, ly + oy)


def _speck(lx, ly, k):
    return (int(lx * 3 + ly * 7 + k) % 11) == 0


def wall_left(lx, ly):
    """Sunlit cliff: sandstone yellow with a few dark rock specks."""
    return "#" if _speck(lx, ly, 0) else ","


def wall_right(lx, ly):
    """Shaded cliff: black with a few sunlit specks."""
    return RED if _speck(lx, ly, 5) else "#"


# Building walls: in both half-diamonds of a wall segment,
# v = ly -+ lx/2 runs -8 (top of the storey) .. 8 (bottom) and lx mod 16 is
# the same column, so windows line up across the halves of every storey.
def _storey(lx, ly, left):
    v = ly - lx / 2 if left else ly + lx / 2
    return v, lx % 16


def bld_left(lx, ly):
    """Sunlit building wall: pale stone with a dark window per storey."""
    v, u = _storey(lx, ly, True)
    if v > 6.5:
        return "#"                 # floor ledge
    if -4 <= v <= 1 and 5 <= u <= 11:
        return "#"                 # window
    return ","


def bld_right(lx, ly):
    """Shaded building wall: dark with a lit window per storey."""
    v, u = _storey(lx, ly, False)
    if -4 <= v <= 1 and 5 <= u <= 11:
        return ","                 # lit window
    return "#"


def roof(lx, ly):
    """Flat red roof with a dark parapet."""
    if not _inside(lx, ly, 0.75):
        return "#"
    if abs(ly + lx / 4) < 0.6:
        return "#"                 # ridge line
    return RED


# ---------------------------------------------------------------- decorations
def palm(lx, ly):
    """Palm tree: a wide drooping crown on a trunk, rising above the diamond."""
    e = (lx / 13) ** 2 + ((ly + 5) / 3.6) ** 2
    if e <= 1:
        if e > 0.7:
            return "#"             # crown outline
        if lx < -2 and ly < -5:
            return ","             # sunlit fronds
        if ly > -4.5 or lx > 6:
            return "#"             # shaded underside
        return GREEN
    if 11 <= abs(lx) <= 15 and -3 <= ly <= -1:
        return "#"                 # drooping frond tips
    if abs(lx) <= 1 and -2 <= ly <= 3:
        return "#" if lx > 0 else ","
    if ((lx - 3) / 7) ** 2 + ((ly - 4) / 1.5) ** 2 <= 1:
        return "#"                 # shadow on the ground
    return None


def rock(lx, ly):
    """Dark volcanic boulder standing on the grass."""
    e = (lx / 9) ** 2 + ((ly + 1.5) / 5.5) ** 2
    if e > 1:
        return None
    if lx < -1 and ly < -2.5 and e < 0.55:
        return ","                 # sunlit top-left
    return "#" if e > 0.75 or lx > 3 else RED


TERRAINS = [
    dict(name="SEA", elev=0, flags=0, surface=calm, face=("#", "#")),
    dict(name="WAVES", elev=0, flags=0, surface=sea, face=("#", "#"), fallback="."),
    dict(name="SAND", elev=2, flags=LAND, surface=sand, face=(RED, "#"), fallback=","),
    dict(name="GRASS", elev=4, flags=LAND, surface=grass, face=(RED, "#"), fallback="#", rim=","),
    dict(name="PALM", elev=4, flags=LAND, surface=grass, deco=palm, face=(RED, "#"), fallback="#", rim=","),
    dict(name="ROCK", elev=4, flags=LAND | HAZARD, surface=grass, deco=rock, face=(RED, "#"), fallback="#", rim=","),
    dict(name="PAD_T", elev=4, flags=LAND | BASE, surface=_pad_part(*PAD_PARTS["PAD_T"]), face=(RED, "#"), fallback=","),
    dict(name="PAD_L", elev=4, flags=LAND | BASE, surface=_pad_part(*PAD_PARTS["PAD_L"]), face=(RED, "#"), fallback=","),
    dict(name="PAD_R", elev=4, flags=LAND | BASE, surface=_pad_part(*PAD_PARTS["PAD_R"]), face=(RED, "#"), fallback=","),
    dict(name="PAD_B", elev=4, flags=LAND | BASE, surface=_pad_part(*PAD_PARTS["PAD_B"]), face=(RED, "#"), fallback=","),
    dict(name="WALL_L", elev=4, flags=LAND | HAZARD, surface=wall_left, face=("#", "#"), wall=True),
    dict(name="WALL_R", elev=4, flags=LAND | HAZARD, surface=wall_right, face=("#", "#"), wall=True, fallback="#"),
    dict(name="BLD_L", elev=4, flags=LAND | HAZARD, surface=bld_left, face=("#", "#"), wall=True),
    dict(name="BLD_R", elev=4, flags=LAND | HAZARD, surface=bld_right, face=("#", "#"), wall=True),
    dict(name="ROOF", elev=4, flags=LAND | HAZARD, surface=roof, face=("#", "#"), fallback="#"),
]
WALLS = ("WALL_L", "WALL_R")


# ---------------------------------------------------------------- map
def _land(x, y):
    tx, ty = int(x) // 16, int(y) // 16
    if not (0 <= tx < 64 and 0 <= ty < 64):
        return False
    return base._RAW_MAP[ty][tx] != "~"


_RING = [(0, 0)] + [(r * math.cos(a), r * math.sin(a) * 0.6)
                    for r in (12, 22) for a in [k * math.pi / 4 for k in range(8)]]


def _land_score(x, y):
    """Share of land around (x, y): smooths the square tiles into round coasts."""
    return sum(_land(x + dx, y + dy) for dx, dy in _RING) / len(_RING)


def _coast_dist(x, y):
    """Distance (px, iso-squashed) from (x, y) to the nearest sea tile, up to 80."""
    best = 80.0
    for ty in range(max(0, int(y) // 16 - 5), min(64, int(y) // 16 + 6)):
        for tx in range(max(0, int(x) // 16 - 5), min(64, int(x) // 16 + 6)):
            if base._RAW_MAP[ty][tx] == "~":
                cx, cy = tx * 16 + 8, ty * 16 + 8
                best = min(best, math.hypot(cx - x, (cy - y) * 1.6))
    return best


_RAW = {"~": "SEA", ".": "SAND", ",": "GRASS", "P": "PALM", "R": "ROCK", "H": "GRASS"}


def _cell(x, y):
    """Diamond (i, j) whose centre is nearest to world pixel (x, y)."""
    best = None
    for j in range(max(0, int(y) // 8 - 2), min(ISO_H, int(y) // 8 + 3)):
        for i in range(ISO_W):
            cx, cy = 32 * i + 16 * (j & 1), 8 * j
            d = abs(cx - x) / 2 + abs(cy - y)
            if best is None or d < best[0]:
                best = (d, i, j)
    return best[1], best[2]


# Buildings: ground diamond -> storeys (16 px each). Survivor huts stand a
# little up-left of each survivor so they never hide them.
SURVIVOR_FEET = [(91, 816), (207, 182), (495, 316), (841, 194), (841, 914)]
BUILDINGS = {_cell(128, 920): 3,                # base control tower, front corner of the base
             _cell(104, 856): 1, _cell(120, 848): 1}   # hangar north-east of the pad
_huts_done = False


def _place_huts():
    """A hut up-left of each survivor, on the nearest spot no higher than one
    hill level (a hut on a 2-level hill would be as tall as the tower, which
    the helicopter cannot fly over)."""
    global _huts_done
    if _huts_done:
        return
    _huts_done = True
    h = _heights_grid()
    for fx, fy in SURVIVOR_FEET:
        best = None
        for j in range(max(0, (fy - 60) // 8), min(ISO_H, (fy - 8) // 8)):
            for i in range(ISO_W):
                x, y = _centre(i, j)
                if y > fy - 16 or abs(x - fx) < 14 or h[j][i] > 1:
                    continue
                if _ground_terrain(i, j) not in ("GRASS", "SAND", "PALM"):
                    continue
                d = math.hypot(x - (fx - 22), y - (fy - 20))
                if d < 40 and (best is None or d < best[0]):
                    best = (d, i, j)
        if best:
            BUILDINGS.setdefault((best[1], best[2]), 1)


def _centre(i, j):
    return 32 * i + 16 * (j & 1), 8 * j


def _pad_cells():
    tx, ty = PAD_TOP
    out = {}
    for name, (ox, oy) in PAD_PARTS.items():
        x, y = tx + ox, ty + 8 + oy
        j = y // 8
        out[((x - 16 * (j & 1)) // 32, j)] = name
    return out


PAD_CELLS = _pad_cells()


def TERRAIN_AT(i, j):
    _place_huts()
    if (i, j) in PAD_CELLS:
        return PAD_CELLS[(i, j)]
    if (i, j) in BUILDINGS:
        return "ROOF"
    return _ground_terrain(i, j)


def _ground_terrain(i, j):
    """Terrain ignoring buildings (what a building stands on)."""
    x, y = _centre(i, j)
    raw = _RAW[base._RAW_MAP[min(63, y // 16)][min(63, x // 16)]]
    score = _land_score(x, y)
    if (i, j) in PAD_CELLS:
        return PAD_CELLS[(i, j)]
    if score < 0.5:
        return "WAVES" if (i * 7 + j * 13 + (i * j) % 5) % 3 == 0 else "SEA"
    if raw in ("PALM", "ROCK"):
        return raw
    return "SAND" if score < 0.88 else "GRASS"


PAD_CENTRE = (PAD_TOP[0], PAD_TOP[1] + 8)    # home base helipad


def _ground_height(i, j):
    x, y = _centre(i, j)
    if _ground_terrain(i, j) in ("SEA", "WAVES", "SAND") or (i, j) in PAD_CELLS:
        return 0
    if math.hypot(x - PAD_CENTRE[0], (y - PAD_CENTRE[1]) * 1.6) < 100:
        return 0                    # keep the base flat so no hill hides the pad
    d = _coast_dist(x, y)
    if d >= 70:
        return 2
    if d >= 46:
        return 1
    return 0


def _heights():
    """Height map with gaps filled: a diamond whose two opposite diagonal
    neighbours are both raised is raised too, so hills have no thin notches."""
    h = [[_ground_height(i, j) for i in range(ISO_W)] for j in range(ISO_H)]

    def at(i, j):
        return h[j][i] if 0 <= j < ISO_H and 0 <= i < ISO_W else 0

    changed = True
    while changed:
        changed = False
        for j in range(ISO_H):
            o = j & 1                       # neighbours in rows j +- 1: i - 1 + o, i + o
            for i in range(ISO_W):
                if _ground_terrain(i, j) in ("SEA", "WAVES"):
                    continue
                nw, ne = at(i - 1 + o, j - 1), at(i + o, j - 1)
                sw, se = at(i - 1 + o, j + 1), at(i + o, j + 1)
                want = max(min(nw, se), min(ne, sw), min(at(i, j - 2), at(i, j + 2)))
                if want > h[j][i]:
                    h[j][i] = want
                    changed = True
    return h


_H = None


def _heights_grid():
    global _H
    if _H is None:
        _H = _heights()
    return _H


def HEIGHT_AT(i, j):
    """Hill levels, or a building's storeys on top of them."""
    _heights_grid()
    _place_huts()
    if (i, j) in BUILDINGS:
        return _H[j][i] + BUILDINGS[(i, j)]   # storeys on top of the hill
    return _H[j][i]


def WALLS_AT(i, j):
    _place_huts()
    if (i, j) in BUILDINGS:
        HEIGHT_AT(i, j)
        return [("WALL_L", "WALL_R")] * _H[j][i] + [("BLD_L", "BLD_R")] * BUILDINGS[(i, j)]
    return None



# ---------------------------------------------------------------- map glyphs
# Tactical map: 2x2 "quarter block" characters (bit 0 top-left, 1 top-right,
# 2 bottom-left, 3 bottom-right) draw the islands at four times the detail of
# one character per cell, and a tiny figure marks each survivor.
HIRES = dict(base.HIRES)
for _m in range(16):
    _top = ("####" if _m & 1 else "....") + ("####" if _m & 2 else "....")
    _bot = ("####" if _m & 4 else "....") + ("####" if _m & 8 else "....")
    HIRES[f"QB{_m}"] = [_top] * 4 + [_bot] * 4
HIRES["MAN"] = ["...##...", "...##...", ".######.", "#..##..#",
                "...##...", "..#..#..", ".#....#.", "........"]


# ---------------------------------------------------------------- survivor spots
def _islands():
    """Connected land areas of the island layout: tile -> island number."""
    raw = base._RAW_MAP
    comp = {}
    n = 0
    for ty in range(64):
        for tx in range(64):
            if raw[ty][tx] == "~" or (tx, ty) in comp:
                continue
            stack = [(tx, ty)]
            comp[(tx, ty)] = n
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < 64 and 0 <= ny < 64 and raw[ny][nx] != "~" and (nx, ny) not in comp:
                        comp[(nx, ny)] = n
                        stack.append((nx, ny))
            n += 1
    return comp


SPOTS_PER_ISLAND = 4
HELI_MIN, HELI_MAX = 16, 1007     # the game clamps the heli's world position to this
HOVER_MARGIN = 10                 # px of room around the hover point inside those limits


def _reachable(x, y):
    """The heli picks a survivor at (x, y) up hovering at about (x, y - 9),
    give or take 6 px: that point must lie well inside its flight limits."""
    lo, hi = HELI_MIN + HOVER_MARGIN, HELI_MAX - HOVER_MARGIN
    return lo <= x <= hi and lo <= y - 9 <= hi


def EXTRA_ASM(world):
    """Survivor spots, grouped by island (never the base island): the feet and
    the ground around them are open grass or sand at ground level, so no cliff
    or roof hides them and the winch logic sees flat ground."""
    comp = _islands()
    base_island = comp[(3, 55)]
    groups = {}
    for y in range(8, 1000, 6):
        for x in range(8, 1000, 6):
            if not _reachable(x, y):
                continue
            fx, fy = x + 11, y + 16
            isl = comp.get((fx // 16, fy // 16))
            if isl is None or isl == base_island:
                continue
            if world.ground_level(fx, fy) != 0:
                continue
            if not all(world.terrain_at(fx + dx, fy + dy) in ("GRASS", "SAND")
                       for dx in (-6, 0, 6) for dy in (-4, 0, 2)):
                continue
            spots = groups.setdefault(isl, [])
            if len(spots) < SPOTS_PER_ISLAND and all(abs(x - a) + abs(y - b) >= 34 for a, b in spots):
                spots.append((x, y))
    order = sorted(groups)
    first, count, xs, ys = [], [], [], []
    for isl in order:
        first.append(len(xs))
        count.append(len(groups[isl]))
        for x, y in groups[isl]:
            xs.append(x)
            ys.append(y)

    def bl(name, vals):
        return [f"{name}:"] + ["    .byte " + ",".join(f"${v:02X}" for v in vals[i:i + 16])
                               for i in range(0, len(vals), 16)]
    # survivors go to every SPOT_STEP-th island: a step sharing no factor with
    # the island count visits every island before any repeats
    n = len(order)
    step = next(k for k in (5, 7, 11, 13, 3, 2, 1) if k < n and math.gcd(k, n) == 1)
    out = ["// TORNADO survivor spots - generated from tornado_iso.py EXTRA_ASM",
           f".const SPOT_ISLANDS = {n}", f".const SPOT_COUNT = {len(xs)}",
           f".const SPOT_STEP = {step}"]
    out += bl("isl_first", first) + bl("isl_count", count)
    out += bl("spot_x_lo", [v & 255 for v in xs]) + bl("spot_x_hi", [v >> 8 for v in xs])
    out += bl("spot_y_lo", [v & 255 for v in ys]) + bl("spot_y_hi", [v >> 8 for v in ys])
    return out
