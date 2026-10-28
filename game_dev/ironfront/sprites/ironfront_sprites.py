"""
IRONFRONT sprite bank - bank file for tools/sprites/sprite_tool.py.

Vehicles are hand-drawn facing N, NE and E; the other five headings are
mirrors and flips. Rifle squads come in 3/2/1-soldier strengths with one shared
frame layout. Explosions are procedural, cursors are hires.

Build:  python tools/sprites/sprite_tool.py game_dev/ironfront/sprites/ironfront_sprites.py
"""
import math

from sprite_tool import (DIRS, H, HR_W, MC_W, Sprite, animate, art, blank, flip_v, hires_canvas, hires_from,
                         mirror_c, mirror_h, noise, stamp, to_rows)

TITLE = "IRONFRONT"
MC0 = 0       # black: outlines, tread gaps
MC1 = 1       # white: barrels, tracks, metal, canopies
PLAYER = 7    # yellow
ENEMY = 6     # blue
TERRAIN = 8   # brown: preview ground colour only
ASM_NOTES = [
    "Sprite colour = faction colour where sprite_colours is $FF",
    "Vehicles + heli: index = base + dir*2 + frame, dir 0..7 = N NE E SE S SW W NW",
    "Squads: SPR_SQUAD3/2/1 share one 15-frame layout (walk N,E,S,W x2, fire E,W x2, die x3)",
]


# ---------------------------------------------------------------- vehicles
# Each vehicle is hand-drawn facing N, NE and E (21 rows x 12 cells, pivot at
# cell column 6, row 10). The other five headings are mirrors/flips.
# Extra legend for vehicle art:  t  track link   s  spinning harvester scoop
# Both animate: alternate G/K along `axis` ("row" or "col"), shifted by phase.

LIGHT_TANK = {
    "N": art(
        "......G.....",
        "......G.....",
        "......G.....",
        "...tKKGKKt..",
        "...tFFGFFt..",
        "...tFKGKFt..",
        "...tKFGFKt..",
        "...tKFGFKt..",
        "...tKGFFKt..",
        "...tKFFFKt..",
        "...tFKKKFt..",
        "...tFFFFFt..",
        "...tFGFGFt..",
        "...tFGFGFt..",
        "...tFFFFFt..",
        "...tKKKKKt..",
        top=1),
    "NE": art(
        "............",
        "......t.....",
        ".....tFK..G.",
        ".....tFK.G..",
        "....tFFFKG..",
        "....tFFFG...",
        "...tFFFFGK..",
        "...tFKKGFK..",
        "..tFKFFGKFK.",
        "..tFKGFFKFK.",
        ".tFFKFFFKFFt",
        "..KFFKFKFFt.",
        "..KFFKKKFFt.",
        "...KFFFFFt..",
        "...KFGFGFt..",
        "....KFGFt...",
        "....KFFFt...",
        ".....KFt....",
        ".....KKt....",
        "......t....."),
    "E": art(
        "...ttttttt..",
        "...ttttttt..",
        "...KFFFFFK..",
        "...KFFKKKK..",
        "...KGFKGFK..",
        "...KFFKFFK..",
        "...KGFKFGGGG",
        "...KFFKFGGGG",
        "...KGFKFFK..",
        "...KFFKFFK..",
        "...KFFKKKK..",
        "...KFFFFFK..",
        "...ttttttt..",
        "...ttttttt..",
        top=4),
}

RECON_BUGGY = {
    "N": art(
        "......G.....",
        ".....FGF....",
        "...t.FGF.t..",
        "...tFFGFFt..",
        "...tKKGKKt..",
        "....FGGGF...",
        "....FKGKF...",
        "....FFFFF...",
        "...tFFFFFt..",
        "...tFGFGFt..",
        "...tFFFFFt..",
        ".....KKK....",
        top=4),
    "NE": art(
        "......t.....",
        ".....ttF....",
        ".....tFK.G..",
        ".....KFFG...",
        "....GFKFG...",
        "....GFKGFK..",
        "...tFGFGFK..",
        "...tKGGKFFK.",
        "..ttFFGFKFt.",
        "..KFFKGFKtt.",
        "...KFFFGFt..",
        "...KGFFGF...",
        "....KGFFF...",
        "....KFGF....",
        ".....KFt....",
        ".....Ktt....",
        "......t.....",
        top=2),
    "E": art(
        ".....tt.tt..",
        ".....tt.tt..",
        "....KFFFKF..",
        "....KGKGKF..",
        "....KFKGKF..",
        "....KFFGKF..",
        "....KFGGGGGG",
        "....KFGGGGGG",
        "....KFFGKF..",
        "....KFKGKF..",
        "....KGKGKF..",
        "....KFFFKF..",
        ".....tt.tt..",
        ".....tt.tt..",
        top=4),
}

HARVESTER = {
    "N": art(
        "..sssssssss.",
        "..KKKKKKKKK.",
        "...K.....K..",
        "..tKFFFFFKt.",
        "..tFGGGKKFt.",
        "..tFGKGFFFt.",
        "..tFGGGFFFt.",
        "..tFGGGKKKt.",
        "..tFKGKFFFt.",
        "..tFGGGFGFt.",
        "..tFGGGFFFt.",
        "..tFGKGFGFt.",
        "..tFGGGFFFt.",
        "..tFGGGFGFt.",
        "..tFKGKFFFt.",
        "..tFGGGFFFt.",
        "..tFFFFFFFt.",
        "..tKKKKKKKt.",
        top=1),
    "NE": art(
        "......ss....",
        ".......s....",
        ".....tFss...",
        ".....tFKs...",
        "....tFFFss..",
        "....tFGG.s..",
        "...tFFGGFss.",
        "...tFGKGG.s.",
        "..tFFGGGFKss",
        "..tFGGGGFKKs",
        "..KFGKGFKFKs",
        "...KGGGFKFt.",
        "...KGGFFFKt.",
        "....KGFFFt..",
        "....KFFFFt..",
        ".....KFFt...",
        ".....KFFt...",
        "......Kt....",
        ".......t....",
        top=1),
    "E": art(
        "..tttttttt..",
        "..tttttttt..",
        "..KFFFFFFFKs",
        "..KFFFFFFFKs",
        "..KFGGGGGF.s",
        "..KFGKGKGF.s",
        "..KFGGGGGF.s",
        "..KFGGGGGF.s",
        "..KFGKGKGF.s",
        "..KFGGGGGF.s",
        "..KFFFFFKF.s",
        "..KFGFGFKK.s",
        "..KFFFFFKK.s",
        "..KFGFGFKF.s",
        "..KFFFFFFFKs",
        "..KFFFFFFFKs",
        "..tttttttt..",
        "..tttttttt..",
        top=1),
}


def vehicle_set(group, model):
    n, ne, e = model["N"], model["NE"], model["E"]
    # heading: (art, track link axis, scoop axis)
    heads = {
        "N": (n, "row", "col"), "NE": (ne, "row", "row"), "E": (e, "col", "row"),
        "SE": (flip_v(ne), "row", "row"), "S": (flip_v(n), "row", "col"),
        "SW": (flip_v(mirror_c(ne)), "row", "row"), "W": (mirror_c(e), "col", "row"),
        "NW": (mirror_c(ne), "row", "row"),
    }
    out = []
    for name in DIRS:
        rows, t_axis, s_axis = heads[name]
        for ph in (0, 1):
            out.append(Sprite(group, f"{name}-{ph}", animate(rows, ph, t_axis, s_axis), delay=6))
    return out


# ---------------------------------------------------------------- infantry
SOLDIER = {
    "S0": [".F..", ".K..", "FFF.", "FGF.", ".F..", ".K..", "K.K.", "K.K."],
    "S1": [".F..", ".K..", "FFF.", "FGF.", ".F..", ".K..", ".K..", ".K.."],
    "N0": [".F..", ".F..", "FFF.", "FGF.", ".F..", ".K..", "K.K.", "K.K."],
    "N1": [".F..", ".F..", "FFF.", "FGF.", ".F..", ".K..", ".K..", ".K.."],
    "E0": [".F..", ".FK.", "FFF.", ".FGG", ".F..", ".KK.", "K..K", "K..K"],
    "E1": [".F..", ".FK.", "FFF.", ".FGG", ".F..", ".K..", ".K..", ".KK."],
    "F0": [".F...", ".FK..", "FFF.G", ".FGGG", ".F..G", ".K...", "K.K..", "K.K.."],
    "F1": [".F...", ".FK..", "FFF..", ".FGG.", ".F...", ".K...", "K.K..", "K.K.."],
    "D0": ["....", ".F..", "FKF.", ".FF.", ".F..", ".K..", "K.K.", "K.K."],
    "D1": ["....", "....", "....", ".F..", "FFK.", ".FF.", ".KK.", "K.K."],
    "D2": ["....", "....", "....", "....", "....", "....", "KFFF", ".KGK"],
}
# (col, row) of each rifleman by squad strength; survivors regroup on the pivot
SQUAD_SLOTS = {
    3: [(5, 2), (1, 11), (7, 10)],
    2: [(2, 5), (6, 9)],
    1: [(5, 6)],
}


def squad(poses, size):
    grid = blank()
    for (col, row), pose in zip(SQUAD_SLOTS[size], poses):
        stamp(grid, SOLDIER[pose], col, row)
    return to_rows(grid)


def squad_set(size):
    # same 15-frame layout for every strength, so frame = SPR_SQUADn + offset
    group = f"SQUAD{size}"
    out = []

    def walk(d, f):
        return squad([f"{d}{(f + i) % 2}" for i in range(size)], size)

    for d in ("N", "E", "S"):
        for f in (0, 1):
            out.append(Sprite(group, f"WALK-{d}-{f}", walk(d, f)))
    for f in (0, 1):
        out.append(Sprite(group, f"WALK-W-{f}", mirror_h(walk("E", f))))
    for f in (0, 1):
        out.append(Sprite(group, f"FIRE-E-{f}", squad([f"F{(f + i) % 2}" for i in range(size)], size), delay=5))
    for f in (0, 1):
        out.append(Sprite(group, f"FIRE-W-{f}", mirror_h(out[-2].rows), delay=5))
    for f in range(3):
        poses = [f"D{min(2, f + st)}" for st in (0, 1, 0)[:size]]
        out.append(Sprite(group, f"DIE-{f}", squad(poses, size), delay=10))
    return out


# ---------------------------------------------------------------- helicopter
# Side-on gunship in the style of the reference art. Drawn: N (tail toward
# camera), NE, E (profile), SE, S (nose toward camera); W/NW/SW are mirrors.
# The main rotor row is generated (long blade / short blade frames) and
# q cells are the tail rotor blur, flickering G/K each frame.
HELI = {
    "N": [
        "......K.....",
        ".....KFK....",
        "....KFFFK...",
        "...KKFFFKK..",
        ".KFKFFFFFKFK",
        ".KGKFFKFFKGK",
        "...KKFFFKK..",
        "..KKK.F.KKK.",
        "......F.....",
        ".....qKq....",
        "......K.....",
    ],
    "NE": [
        "......K.....",
        ".....KFFK...",
        "....KFFFGK..",
        "....KFFFFK..",
        "...KFFFFFK..",
        "..KFKKFFKK..",
        ".KFK.K..K...",
        "qFK..KKKKK..",
        "qGq.........",
        ".q..........",
    ],
    "E": [
        "K.....K.....",
        "q....KFFK...",
        "qGK.KFFFFGK.",
        "KFFKFFFFFGGK",
        "q.KKFFFFKFGK",
        "....KFFFFFFK",
        "....KKGGKKKK",
        "....K....K..",
        "...KKKKKKKK.",
    ],
    "SE": [
        "q.....K.....",
        "qK...KFK....",
        "qGFFKFFFK...",
        ".K.KFFFFGK..",
        "....KFFFGGK.",
        "...KFKFFGGGK",
        "...KGKKFFFK.",
        "....KK.KKK..",
        ".....K...K..",
        "....KKKKKKK.",
    ],
    "S": [
        "......K.....",
        ".....KFK....",
        "....KGFGK...",
        "...KKGFGKK..",
        ".KFKFFFFFKFK",
        ".KGKFFFFFKGK",
        "...KKFFFKK..",
        "....K.K.K...",
        "..KKK...KKK.",
    ],
}


def heli_frame(body, phase):
    span = 5 if phase == 0 else 2  # blade seen edge-on vs. side-on
    rotor = "".join("G" if c == 6 else "K" if abs(c - 6) <= span else "." for c in range(MC_W))
    rows = [rotor] + body
    rows = [line.replace("q", "G" if (r + phase) % 2 else "K") for r, line in enumerate(rows)]
    return art(*rows, top=4)


def heli_views():
    views = {d: [heli_frame(HELI[d], ph) for ph in (0, 1)] for d in HELI}
    for src, dst in (("E", "W"), ("NE", "NW"), ("SE", "SW")):
        views[dst] = [mirror_c(v) for v in views[src]]
    return views


def heli_set():
    views = heli_views()
    return [Sprite("HELI", f"{d}-{ph}", views[d][ph], delay=2) for d in DIRS for ph in (0, 1)]


SHADOW_COLOUR = 0


def heli_shadow_set():
    # hires checkerboard silhouette of the airframe (no main rotor), one per
    # heading; the game draws it on the ground below-right of the helicopter
    out = []
    views = heli_views()
    for d in DIRS:
        body = views[d][0]
        grid = [["."] * HR_W for _ in range(H)]
        for r, line in enumerate(body):
            if r == 4:  # rotor row
                continue
            for c, ch in enumerate(line):
                if ch != ".":
                    for x in (2 * c, 2 * c + 1):
                        if (x + r) % 2 == 0:
                            grid[r][x] = "#"
        out.append(Sprite("SHADOW", d, to_rows(grid), mode="hr", color=SHADOW_COLOUR))
    return out


# ---------------------------------------------------------------- explosion
# per frame: fire radius, smoke radius, hollow radius, sprite colour
BLAST = [(2.5, 4.0, 0, 1), (4.5, 6.5, 0, 7), (6.5, 8.5, 0, 7),
         (6.0, 9.5, 2.5, 8), (4.0, 10.0, 5.0, 2), (0, 10.0, 7.0, 11)]


def explosion_set():
    out = []
    for k, (fire, smoke, hollow, colour) in enumerate(BLAST):
        grid = blank()
        for r in range(H):
            for c in range(MC_W):
                d = math.hypot((2 * c + 1 - 12) * 1.0, (r + 0.5 - 10.5))
                j = (noise(c, r, k) - 0.5) * 2.4
                dd = d + j
                if dd < hollow:
                    continue
                if dd < fire:
                    grid[r][c] = "F"
                elif dd < smoke:
                    grid[r][c] = "G" if noise(c, r, k + 9) > 0.25 else "K"
                elif dd < smoke + 1.2 and noise(c, r, k + 3) > 0.7:
                    grid[r][c] = "K"
        out.append(Sprite("EXPLOSION", f"BLAST-{k}", to_rows(grid), color=colour, delay=5))
    return out


# ---------------------------------------------------------------- cursors
POINTER = [
    "#", "##", "###", "####", "#####", "######", "#######", "########",
    "#########", "#########", "####.##", "###..##", "##....##", "#.....##", "......##",
]


def move_cursor(gap):
    # four arrowheads pointing in at the destination
    def fn(x, y):
        for along, across in ((y, x), (-y, x), (x, y), (-x, y)):
            d = -along - gap  # 0 at the tip, growing outward
            if 0 <= d <= 3.5 and abs(across) <= d + 0.4:
                return True
        return False
    return hires_canvas(fn)


def attack_cursor(rad):
    def fn(x, y):
        d = math.hypot(x, y)
        ring = abs(d - rad) < 0.65 and min(abs(x), abs(y)) > 1.5
        tick = (abs(x) < 0.6 and rad - 3 <= abs(y) <= rad + 2.5) or (abs(y) < 0.6 and rad - 3 <= abs(x) <= rad + 2.5)
        return ring or tick or (abs(x) < 0.6 and abs(y) < 0.6)
    return hires_canvas(fn)


def no_cursor():
    def fn(x, y):
        d = math.hypot(x, y)
        return abs(d - 7) < 0.8 or (d < 7 and abs(x - y) < 1.0)
    return hires_canvas(fn)


def select_bracket():
    def fn(x, y):
        ax, ay = abs(x), abs(y)
        edge_x = ax > 10.6 and ay > 5.5 and ay <= 10
        edge_y = ay > 9.4 and ax > 6.5 and ax <= 12
        return edge_x or edge_y
    return hires_canvas(fn)


def cursor_set():
    return [
        Sprite("CURSOR", "POINTER", hires_from(POINTER), mode="hr", color=1),
        Sprite("CURSOR", "MOVE-0", move_cursor(6), mode="hr", color=13, delay=10),
        Sprite("CURSOR", "MOVE-1", move_cursor(3.5), mode="hr", color=13, delay=10),
        Sprite("CURSOR", "ATTACK-0", attack_cursor(7.5), mode="hr", color=10, delay=10),
        Sprite("CURSOR", "ATTACK-1", attack_cursor(6), mode="hr", color=10, delay=10),
        Sprite("CURSOR", "NO-GO", no_cursor(), mode="hr", color=2),
        Sprite("CURSOR", "SELECT", select_bracket(), mode="hr", color=1),
    ]


# ---------------------------------------------------------------- output
GROUPS = [
    ("TANK", "Light Tank", lambda: vehicle_set("TANK", LIGHT_TANK)),
    ("BUGGY", "Recon Buggy", lambda: vehicle_set("BUGGY", RECON_BUGGY)),
    ("HARVESTER", "Harvester", lambda: vehicle_set("HARVESTER", HARVESTER)),
    ("HELI", "Attack Helicopter", heli_set),
    ("SHADOW", "Helicopter Shadow", heli_shadow_set),
    ("SQUAD3", "Rifle Squad x3", lambda: squad_set(3)),
    ("SQUAD2", "Rifle Squad x2", lambda: squad_set(2)),
    ("SQUAD1", "Rifle Squad x1", lambda: squad_set(1)),
    ("EXPLOSION", "Explosion", explosion_set),
    ("CURSOR", "Cursors", cursor_set),
]
