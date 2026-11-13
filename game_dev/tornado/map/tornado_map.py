"""
TORNADO archipelago - tileset file for tools/charset/tileset_tool.py.

Ocean and tropical islands in multicolor characters with auto-generated rounded
coastlines, surf foam, and 3D south-east cliff drop-shadows:
  $D021 = 6 (deep blue ocean), $D022 = 14 (light blue surf/sky), $D023 = 0 (black shadow)
  Per-tile colour: cyan (3) for waves, yellow (7) for beaches/helipad,
  green (5) for grass/palms, red (2) for volcanic rocks.
  Home base has a 4x4 Helipad and 4x4 Control Tower.
"""
TITLE = "TORNADO"
OUTPUT = "tornado"
BG = (6, 14, 0)                # deep blue, light blue, black
RED, GREEN, CYAN, WHITE, BLACK, YELLOW = 2, 5, 3, 1, 0, 7

# Tile flags (read by the game)
LAND = 0x01                    # island ground (valid for crate spawns)
BASE = 0x02                    # home base / helipad
HAZARD = 0x04                  # rocky peak
CONSTS = {"TF_LAND": LAND, "TF_BASE": BASE, "TF_HAZARD": HAZARD}

# Multicolor 8x16 char pairs (2x2 chars per 16x16 tile):
#   '.' = $D021 (deep blue sea)
#   ',' = $D022 (light blue surf / foam)
#   '#' = $D023 (black outline / cliff shadow)
#   'o' = colour RAM (yellow sand, green grass, red rock, cyan wave)
TILES = [
    ("SEA1", [
        "........", "........", "........", "........", "........", "........", "........", "........",
        "........", "........", "........", "........", "........", "........", "........", "........",
    ], CYAN, 0),
    ("SEA2", [
        "........", "..o,....", "........", "........", "........", "........", "........", "........",
        "........", "........", "........", "....o,..", "........", "........", "........", "........",
    ], CYAN, 0),
    ("SEA3", [
        "........", "........", "........", "....o...", "........", "........", "........", "........",
        "........", "........", "........", "........", "........", ".,......", "........", "........",
    ], CYAN, 0),
    ("BEACH1", [
        "oooooooo", "oooooooo", "oooo,ooo", "oooooooo", "oooooooo", "o,oooooo", "oooooooo", "oooooooo",
        "oooooooo", "oooooooo", "ooo,oooo", "oooooooo", "oooooooo", "oooooo,o", "oooooooo", "oooooooo",
    ], YELLOW, LAND),
    ("BEACH2", [
        "oooooooo", "oooooooo", "oo,ooooo", "oooooooo", "oooooooo", "ooooo,oo", "oooooooo", "oooooooo",
        "oooooooo", "oooooooo", "oooooo,o", "oooooooo", "oooooooo", "o,oooooo", "oooooooo", "oooooooo",
    ], YELLOW, LAND),
    ("GRASS1", [
        "oooooooo", "oo#ooooo", "oooooooo", "oooooooo", "ooooo#oo", "oooooooo", "oooooooo", "o#oooooo",
        "oooooooo", "oooo#ooo", "oooooooo", "oooooooo", "oo#ooooo", "oooooooo", "oooooooo", "oooooo#o",
    ], GREEN, LAND),
    ("GRASS2", [
        "oooooooo", "oooooooo", "ooo#oooo", "oooooooo", "oooooooo", "o#oooooo", "oooooooo", "ooooo#oo",
        "oooooooo", "oooooooo", "oooooo#o", "oooooooo", "oooooooo", "ooo#oooo", "oooooooo", "o#oooooo",
    ], GREEN, LAND),
    ("PALM1", [
        "..#..#..", ".#o##o#.", "#oo##oo#", "#o.##.o#", "...##...", "...##...", "..o##o..", ".oooooo.",
        "...##...", "..o##o..", "..#oo#..", ".#oooo#.", "oooooooo", "oo#ooooo", "oooooooo", "oooooooo",
    ], GREEN, LAND),
    ("PALM2", [
        "........", "..#..#..", ".#o##o#.", "#oo##oo#", "...##...", "...##...", "..o##o..", ".oooooo.",
        "...##...", "..#oo#..", ".#oooo#.", "oooooooo", "ooooo#oo", "oooooooo", "oooooooo", "oooooooo",
    ], GREEN, LAND),
    ("ROCK1", [
        "..####..", ".#oooo#.", "#oo##oo#", "#o####o#", "#oooooo#", ".#oooo#.", "..####..", "........",
        "...##...", "..#oo#..", ".#oooo#.", "#oo##oo#", "#oooooo#", ".######.", "........", "........",
    ], RED, LAND | HAZARD),
    ("PADTILE", [
        "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo",
        "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo", "oooooooo",
    ], YELLOW, LAND | BASE),
    # Coastline tiles with surf foam (',') & 3D cliff shadow ('#')
    ("COAST_N", [
        "........", "........", ",,,,,,,,", "oooooooo", "oooooooo", "oooo,ooo", "oooooooo", "oooooooo",
        "oooooooo", "oooooooo", "ooo,oooo", "oooooooo", "oooooooo", "oooooo,o", "oooooooo", "oooooooo",
    ], YELLOW, LAND),
    ("COAST_S", [
        "oooooooo", "oooooooo", "ooo,oooo", "oooooooo", "oooooooo", "oooooo,o", "oooooooo", "oooooooo",
        "oooooooo", "oooooooo", "oooooooo", "oooooooo", "########", "########", ",,,,,,,,", "........",
    ], YELLOW, LAND),
    ("COAST_W", [
        ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo",
        ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo",
    ], YELLOW, LAND),
    ("COAST_E", [
        "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.",
        "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.",
    ], YELLOW, LAND),
    ("COAST_NW", [
        "........", "........", "....,,,,", "..,,oooo", ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo",
        ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo", ".,oooooo",
    ], YELLOW, LAND),
    ("COAST_NE", [
        "........", "........", ",,,,....", "oooo,,..", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,",
        "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,",
    ], YELLOW, LAND),
    ("COAST_SW", [
        ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", ".,oooooo",
        ".,oooooo", ".,oooooo", "..oooooo", ".,oooooo", "..,,####", "...,,###", "....,,,,", "........",
    ], YELLOW, LAND),
    ("COAST_SE", [
        "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "oooooo#.",
        "oooooo#,", "oooooo#.", "oooooo#,", "oooooo#,", "#####,,,", "####,,,.", ",,,,....", "........",
    ], YELLOW, LAND),
]

# 4x4-char buildings (16 x 32 multicolor pixels), o = owner colour
BLOCKS = [
    ("HELIPAD", [
        "oooooooooooooooo", "oooooooooooooooo", "oo############oo", "o#oooooooooooo#o",
        "#oo##########oo#", "#o#,,,,,,,,,,#o#", "#o#,oo,,,,oo,#o#", "#o#,oo,,,,oo,#o#",
        "#o#,oo,,,,oo,#o#", "#o#,oooooooo,#o#", "#o#,oooooooo,#o#", "#o#,oo,,,,oo,#o#",
        "#o#,oo,,,,oo,#o#", "#o#,oo,,,,oo,#o#", "#o#,,,,,,,,,,#o#", "#oo##########oo#",
        "o#oooooooooooo#o", "oo############oo", "oooooooooooooooo", "oo#o#oooooo#o#oo",
        "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo",
        "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo",
        "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo",
    ], YELLOW),
    ("TOWER", [
        "################", "#ooooooo#oooooo#", "#oooooo#o#ooooo#", "#oo##########oo#",
        "#o#oooooooooo#o#", "#o#o########o#o#", "#o#o#,,,,,,#o#o#", "#o#o########o#o#",
        "#oo##########oo#", "#oooo#oooo#oooo#", "#oooo#oooo#oooo#", "#oooo#o##o#oooo#",
        "#oooo#oooo#oooo#", "#oooo#oooo#oooo#", "#oooo#o##o#oooo#", "#oooo#oooo#oooo#",
        "#ooo########ooo#", "#oo#oooooooo#oo#", "#oo#o######o#oo#", "#oo#oooooooo#oo#",
        "#oo##########oo#", "#oooooooooooooo#", "#oo##oooooo##oo#", "#oooooooooooooo#",
        "################", "################", "oooooooooooooooo", "oooooooooooooooo",
        "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo", "oooooooooooooooo",
    ], CYAN),
]

# Sidebar / UI glyphs (hires, in colour RAM's colour)
HIRES = {
    "VLINE": ["##......"] * 8,
    "HLINE": ["........", "........", "........", "########", "########", "........", "........", "........"],
    "BAR1": ["........", "#.......", "#.......", "#.......", "#.......", "#.......", "#.......", "........"],
    "BAR2": ["........", "##......", "##......", "##......", "##......", "##......", "##......", "........"],
    "BAR3": ["........", "###.....", "###.....", "###.....", "###.....", "###.....", "###.....", "........"],
    "BAR4": ["........", "####....", "####....", "####....", "####....", "####....", "####....", "........"],
    "BAR5": ["........", "#####...", "#####...", "#####...", "#####...", "#####...", "#####...", "........"],
    "BAR6": ["........", "######..", "######..", "######..", "######..", "######..", "######..", "........"],
    "BAR7": ["........", "#######.", "#######.", "#######.", "#######.", "#######.", "#######.", "........"],
    "BAR8": ["........", "########", "########", "########", "########", "########", "########", "........"],
    "SOLID": ["########"] * 8,
    "DOT":   ["........", "........", "...##...", "...##...", "........", "........", "........", "........"],
    "RING":  ["........", ".######.", ".#....#.", ".#....#.", ".#....#.", ".#....#.", ".######.", "........"],
}

LEGEND = {
    "~": ["SEA1", "SEA1", "SEA2", "SEA3"],
    ".": ["BEACH1", "BEACH2"],
    ",": ["GRASS1", "GRASS2"],
    "P": ["PALM1", "PALM2"],
    "R": ["ROCK1"],
    "H": ["PADTILE"],
    "n": ["COAST_N"],
    "s": ["COAST_S"],
    "w": ["COAST_W"],
    "e": ["COAST_E"],
    "7": ["COAST_NW"],
    "9": ["COAST_NE"],
    "1": ["COAST_SW"],
    "3": ["COAST_SE"],
}

_RAW_MAP = [
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~.....~~~~~~~~~~......~~~~~~~~~~~~~~~~~~~~~~.....~~~~~~~~~~~~~",
    "~~.,PP,.~~~~~~~~~.,PPP,.~~~~~~~~~~~~~~~~~~~~~.,PP,.~~~~~~~~~~~~~",
    "~~.,RR,.~~~~~~~~~.,R,,R.~~~~~~~~....~~~~~~~~~.,RR,.~~~~~~~~~~~~~",
    "~~.,,...~~~~~~~~~.,,.,..~~~~~~~.,PP,.~~~~~~~~~.,,..~~~~~~~~~~~~~",
    "~~~.....~~~~~~~~~~......~~~~~~~.,R,,.~~~~~~~~~~...~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~......~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.......~~~~~~~~~",
    "~~~~~~~~.,PPP,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,PP,PP,.~~~~~~~~",
    "~~~~~~~~.,R,R,.~~~~~~~~~~~~~.....~~~~~~~~~~~~~~.,R,,,R,.~~~~~~~~",
    "~~~~~~~~.,,.,,.~~~~~~~~~~~~.,PP,.~~~~~~~~~~~~~~.,,,,,,..~~~~~~~~",
    "~~~~~~~~~......~~~~~~~~~~~~.,R,,.~~~~~~~~~~~~~~~.......~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.....~~~~~",
    "~~.,PP,.~~~~~~~~~~~~~~~~~~~~.......~~~~~~~~~~~~~~~~~~.,PP,.~~~~~",
    "~~.,R,,.~~~~~~~~~~~~~~~~~~~.,PP,PP,.~~~~~~~~~~~~~~~~~.,R,,.~~~~~",
    "~~..,,.~~~~~~~~~~~~~~~~~~~.,R,,RR,,.~~~~~~~~~~~~~~~~~..,,.~~~~~~",
    "~~~....~~~~~~~~~~~~~~~~~~~.,,P,,P,,.~~~~~~~~~~~~~~~~~~....~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~.,,,,,,..~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~.......~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~.....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~.,PP,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~......~~~~~~~~~",
    "~~~~~~~~~~~~~.,R,,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,PPP,.~~~~~~~~~",
    "~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,R,R,.~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,,,,,,~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~......~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.....~~~~~~~~~~~~~~~~~~~~",
    "~~~~.......~~~~~~~~~~~~~~~~~~~~~~~~~~~.,PP,.~~~~~~~~~~~~~~~~~~~~",
    "~~~.,PP,PP,.~~~~~~~~~~~~~~~~~~~~~~~~~~.,R,,.~~~~~~~~~~~~~~~~~~~~",
    "~~~.,R,,R,,.~~~~~~~~~~~......~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~",
    "~~~.,,,,,,..~~~~~~~~~~.,PPP,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~.......~~~~~~~~~~~.,R,R,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~.,,,,,,~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~......~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.....~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,PP,.~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.......~~~~~~~~~~~~~~.,R,,.~~~~~~",
    "~~~~~....~~~~~~~~~~~~~~~~~~~~~.,PP,PP,.~~~~~~~~~~~~~~....~~~~~~~",
    "~~~~.,PP,.~~~~~~~~~~~~~~~~~~~~.,R,RR,,.~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~.,R,,.~~~~~~~~~~~~~~~~~~~~.,,,,,,..~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~....~~~~~~~~~~~~~~~~~~~~~~.......~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~.....~~~~~~~~~~~~~~~~",
    "~~~~....~~~~~~.,PP,.~~~~~~~~~~~~~~~~~~~~~~.,PP,.~~~~~~~~~~~~~~~~",
    "~~~.,PP,.~~~~~.,R,,.~~~~~~~~~~~~~~~~~~~~~~.,R,,.~~~~~~~~~~~~~~~~",
    "~~~.,,..~~~~~~~....~~~~~~~~~~~~~~~~~~~~~~~~....~~~~~~~~~~~~~~~~~",
    "~~~.....~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~.......~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~..,,,,,,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~.,,,,,,..~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.....~~~~~~~~",
    "~.,HH,,,,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,PP,.~~~~~~~~",
    "~.,HH,P,,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.,R,,.~~~~~~~~",
    "~..,,,,,,.~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~....~~~~~~~~~",
    "~~.......~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
    "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
]


def _auto_coastline(raw):
    h, w = len(raw), len(raw[0])
    out = []
    for y in range(h):
        row = []
        for x in range(w):
            ch = raw[y][x]
            if ch != ".":
                row.append(ch)
                continue
            n_sea = y == 0 or raw[y - 1][x] == "~"
            s_sea = y == h - 1 or raw[y + 1][x] == "~"
            w_sea = x == 0 or raw[y][x - 1] == "~"
            e_sea = x == w - 1 or raw[y][x + 1] == "~"
            if n_sea and w_sea:
                row.append("7")
            elif n_sea and e_sea:
                row.append("9")
            elif s_sea and w_sea:
                row.append("1")
            elif s_sea and e_sea:
                row.append("3")
            elif n_sea:
                row.append("n")
            elif s_sea:
                row.append("s")
            elif w_sea:
                row.append("w")
            elif e_sea:
                row.append("e")
            else:
                row.append(".")
        out.append("".join(row))
    return out


MAP = _auto_coastline(_RAW_MAP)
