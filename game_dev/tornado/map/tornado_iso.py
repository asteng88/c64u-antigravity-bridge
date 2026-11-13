"""
TORNADO archipelago - isometric terrain for tools/isotiles/iso_tool.py.

Same islands as tornado_map.py (sampled at every diamond's centre), drawn as
raised isometric plateaus: sand beaches stand above the sea, grass stands above
the sand, and each step down shows a cliff face (lit left face, dark right
face). Palms and rocks rise above their diamonds.

Colours: $D021 = 6 deep blue sea, $D022 = 7 sand yellow, $D023 = 0 black;
colour RAM per character: cyan waves, green grass/palms, red cliff faces.
"""
import tornado_map as base

TITLE = "TORNADO"
OUTPUT = "tornado"
BG = (6, 7, 0)
RED, CYAN, GREEN = 2, 3, 5

LAND, BASE, HAZARD = 0x01, 0x02, 0x04
CONSTS = {"TF_LAND": LAND, "TF_BASE": BASE, "TF_HAZARD": HAZARD}

ISO_W, ISO_H = 32, 128           # 1024 x 1024 world pixels


def _inside(lx, ly, k=1.0):
    return abs(lx) / 16 + abs(ly) / 8 <= k


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


def pad(lx, ly):
    # concrete with a dark border just inside the diamond edge
    if not _inside(lx, ly, 0.78):
        return "#"
    return ","


def palm(lx, ly):
    """Palm tree rising from the diamond centre: a wide crown on a trunk."""
    e = (lx / 11) ** 2 + ((ly + 5) / 3.4) ** 2
    if e <= 1:
        if e > 0.68:
            return "#"             # crown outline
        if lx < -2 and ly < -5:
            return ","             # sunlit fronds
        if ly > -4.5 or lx > 5:
            return "#"             # shaded underside / far side
        return GREEN
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
    dict(name="WAVES", elev=0, flags=0, surface=sea, face=("#", "#")),
    dict(name="SAND", elev=2, flags=LAND, surface=sand, face=(RED, "#")),
    dict(name="GRASS", elev=4, flags=LAND, surface=grass, face=(RED, "#")),
    dict(name="PALM", elev=4, flags=LAND, surface=grass, deco=palm, face=(RED, "#")),
    dict(name="ROCK", elev=4, flags=LAND | HAZARD, surface=grass, deco=rock, face=(RED, "#")),
    dict(name="PAD", elev=4, flags=LAND | BASE, surface=pad, face=(RED, "#")),
]

_RAW = {"~": "SEA", ".": "SAND", ",": "GRASS", "P": "PALM", "R": "ROCK", "H": "PAD"}


def TERRAIN_AT(i, j):
    x = 32 * i + 16 * (j & 1)
    y = 8 * j
    tx, ty = min(63, x // 16), min(63, y // 16)
    name = _RAW[base._RAW_MAP[ty][tx]]
    if name == "SEA" and (i * 7 + j * 13 + (i * j) % 5) % 3 == 0:
        name = "WAVES"
    return name


HIRES = base.HIRES
