"""
HELISCAPE sprite bank - for tools/sprites/sprite_tool.py.

Everything is multicolor: K = $D025 (black outline), G = $D026 (white highlight),
F = the per-frame colour. Cells are 2 px wide and 1 px tall, so art looks squeezed
in ASCII; check the contact sheet (--png) rather than the source.

The gunship is two sprites side by side (24 cells = 48 px). Each pose is drawn
once on a 24-cell canvas and split, so frames come in A/B pairs:

  CHOP_R / CHOP_L    level flight   3 rotor phases x 2 parts
  TILT_R / TILT_L    nose down      3 rotor phases x 2 parts
  CHOP_F             head-on        3 rotor phases x 2 parts
  GEAR_R/L/F         wheels down    3 rotor phases x 2 parts

Build:  python tools/sprites/sprite_tool.py game_dev/Heliscape/sprites/heliscape_sprites.py --png sheet.png
"""
from sprite_tool import Sprite, H, MC_W, mirror_h, noise

TITLE = "HELISCAPE"
MC0, MC1 = 0, 1
PLAYER, ENEMY, TERRAIN = 5, 2, 8
ASM_NOTES = ["Gunship frames are A/B pairs: phase * 2 + part"]

BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = range(8)
ORANGE, BROWN, LRED, DGREY, GREY, LGREEN, LBLUE, LGREY = range(8, 16)

GUNSHIP = GREY
W2 = MC_W * 2


def pad(rows, width=MC_W, top=0):
    """Pad ASCII art to a full sprite, bottom-aligned art uses top=."""
    rows = [r.ljust(width, ".") for r in rows]
    return ["." * width] * top + rows + ["." * width] * (H - top - len(rows))


def bottom(rows, width=MC_W):
    return pad(rows, width, top=H - len(rows))


def sprite(group, name, rows, color):
    return Sprite(group, name, pad(rows), color=color)


# ---------------------------------------------------------------- gunship, 24 cells wide
# An Airwolf-style combat helicopter, facing right: gunmetal top (F) over a white
# belly (G), dark wraparound canopy, sharp nose, twin intakes on the engine hump,
# stub wings with forward cannon pods, slim boom and a T-tail. Gear is retracted in
# flight; GEAR frames lower the wheels near the ground (row 18 touches it).
BODY_SIDE = [
    "........................",
    "........................",
    "........................",
    "............KKKKK.......",
    "KKKKKK.....KFFFFFKK.....",
    "..KFK.....KFKKFKKFFKK...",
    "..KFFK...KFFFFFFFFFKKK..",
    "...KFFKKKFFFFFFFFFKKGKK.",
    "....KFFFFFFFFFFFFFFKGKKK",
    ".....KKFFFFFFFFFFFFFKKKK",
    ".......KKKGGGGGGGGGGGGKK",
    "..........KGGGGGGGGGKK..",
    "...........KKGGGGGGKK...",
    "..........KFFFFFK.......",
    ".........KFGGGGFKKKKKKKG",
    "..........KKKKKK........",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]
GEAR_SIDE = {
    15: "..........KKKKKK...K....",
    16: "............K......K....",
    17: "...........KKK....KKK...",
    18: "...........KGK....KGK...",
}
BODY_FRONT = [
    "........................",
    "........................",
    "........................",
    "..........KKKK..........",
    ".........KFFFFK.........",
    "........KFKFFKFK........",
    ".......KFFFFFFFFK.......",
    ".......KKKKKKKKKK.......",
    ".......KKGKKKKGKK.......",
    ".......KKKKFFKKKK.......",
    "........KGGGGGGK........",
    "...KKKKKKGGGGGGKKKKKK...",
    "...KFFFFFKGGGGKFFFFFK...",
    "..KFGFK...KGGK...KFGFK..",
    "..KKKKK....KK....KKKKK..",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
    "........................",
]
GEAR_FRONT = {
    15: ".........K....K.........",
    16: ".........K....K.........",
    17: "........KKK..KKK........",
    18: "........KGK..KGK........",
}
ROTOR_SIDE = [
    ("..KGGGGGGGGGGGGGGGGGGGGK", ".............KK........."),
    (".....GGGGGGGGGGGGGGGGG..", ".............KK........."),
    ("........KGGGGGGGGGK.....", ".............KK........."),
]
ROTOR_FRONT = [
    ("KGGGGGGGGGGGGGGGGGGGGGGK", "...........KK..........."),
    ("....GGGGGGGGGGGGGGGG....", "...........KK..........."),
    ("........KGGGGGGK........", "...........KK..........."),
]
# (row, column, cell) overlays: the tail rotor flickers beside the fin
TAIL_ROTOR = [
    [(3, 0, "G"), (4, 0, "K"), (5, 0, "G"), (6, 0, "K"), (7, 0, "G")],
    [(4, 0, "G"), (5, 0, "G"), (6, 0, "G")],
    [(3, 0, "K"), (5, 0, "G"), (7, 0, "K")],
]


def with_rotor(body, phase, rotor=ROTOR_SIDE, tail=True, gear=None):
    g = [list(r) for r in body]
    for r, line in (gear or {}).items():
        for c, ch in enumerate(line):
            if ch != ".":
                g[r][c] = ch
    for r, line in enumerate(rotor[phase]):
        for c, ch in enumerate(line):
            if ch != ".":
                g[r + 1][c] = ch
    if tail:
        for r, c, ch in TAIL_ROTOR[phase]:
            if g[r][c] == ".":
                g[r][c] = ch
    return ["".join(r) for r in g]


def shear(rows, slope):
    """Nose-down tilt: push cells down toward the nose (column 23)."""
    g = [["."] * W2 for _ in range(H)]
    for r, line in enumerate(rows):
        for c, ch in enumerate(line):
            if ch != ".":
                y = r + round((c - 12) * slope)
                if 0 <= y < H:
                    g[y][c] = ch
    return ["".join(r) for r in g]


def split(group, name, rows, color=GUNSHIP):
    return [Sprite(group, name + "a", [r[:MC_W] for r in rows], color=color),
            Sprite(group, name + "b", [r[MC_W:] for r in rows], color=color)]


def poses(name, art):
    out = []
    for p in range(3):
        out += split("gunship", f"{name}{p}", art(p))
    return out


def chop_right():
    return poses("right", lambda p: with_rotor(BODY_SIDE, p))


def chop_left():
    return poses("left", lambda p: mirror_h(with_rotor(BODY_SIDE, p)))


def tilt_right():
    return poses("tilt_r", lambda p: shear(with_rotor(BODY_SIDE, p), 1 / 6))


def tilt_left():
    return poses("tilt_l", lambda p: mirror_h(shear(with_rotor(BODY_SIDE, p), 1 / 6)))


def chop_front():
    return poses("front", lambda p: with_rotor(BODY_FRONT, p, ROTOR_FRONT, tail=False))


def gear_right():
    return poses("gear_r", lambda p: with_rotor(BODY_SIDE, p, gear=GEAR_SIDE))


def gear_left():
    return poses("gear_l", lambda p: mirror_h(with_rotor(BODY_SIDE, p, gear=GEAR_SIDE)))


def gear_front():
    return poses("gear_f", lambda p: with_rotor(BODY_FRONT, p, ROTOR_FRONT, tail=False, gear=GEAR_FRONT))


# ---------------------------------------------------------------- ground shadow
def shadows():
    wide = ["...KKKKKK...", ".KKKKKKKKKK.", "...KKKKKK..."]
    mid = ["....KKKK....", "..KKKKKKKK..", "....KKKK...."]
    small = [".....KK.....", "...KKKKKK...", ".....KK....."]
    return [Sprite("shadow", n, bottom(a), color=BLACK) for n, a in
            (("wide", wide), ("mid", mid), ("small", small))]


def dust():
    a = ["..G....G..G.", ".G.F..G.F...", "G.F.FF.F.F.G", ".FFFFFFFFFF."]
    b = [".G...G....G.", "G..F...FG..G", ".F.F.FF.F.F.", "F.FFFFFFFF.F"]
    return [Sprite("dust", "a", bottom(a), color=LGREY), Sprite("dust", "b", bottom(b), color=LGREY)]


# ---------------------------------------------------------------- tank
# Five barrel angles (left, up-left, up, up-right, right) x 2 track frames.
TANK_HULL = [
    "...KKFFFFKK.",
    ".KKFFFFFFFFK",
    "KFFFFFFFFFFK",
    "KKKKKKKKKKKK",
]
TRACK = [["KGKKGKKGKKGK", ".KKKKKKKKKK."], ["KKGKKGKKGKKK", ".KKKKKKKKKK."]]
BARRELS = [
    ["............", "............", "KKKKK.......", "KGGKK......."],     # left
    ["............", ".KK.........", "..KK........", "...KK......."],     # up-left
    ["......K.....", "......K.....", "......K.....", "......K....."],    # up
    ["............", ".........KK.", "........KK..", ".......KK..."],     # up-right
    ["............", "............", ".......KKKKK", ".......KKGGK"],     # right
]


def tanks():
    out = []
    for i, barrel in enumerate(BARRELS):
        for t in (0, 1):
            art = barrel + TANK_HULL + TRACK[t]
            out.append(Sprite("tank", f"aim{i}_t{t}", bottom(art), color=DGREY))
    return out


def turrets():
    base = ["...KFFFFK...", "..KFFFFFFK..", ".KFFGFFGFFK.", "KFFFFFFFFFFK", "KKKKKKKKKKKK", "KFKFKFKFKFKF"]
    out = []
    for i, barrel in enumerate(BARRELS):
        out.append(Sprite("turret", f"aim{i}", bottom(barrel + base), color=RED))
    return out


# ---------------------------------------------------------------- POW squads
# 1, 2 or 3 figures in one sprite (the ground band has 4 hardware slots).
# Layout per count: run right x2, run left x2, wave x2.
PERSON = {
    "run_a": ["G..", "FF.", "FFG", "FF.", "K.K", "K..K"],
    "run_b": ["G..", "FF.", "GFF", "FF.", ".K.", ".KK."],
    "wave_a": ["G.G", "FFG", "FF.", "FF.", "K.K", "K.K"],
    "wave_b": ["G..", "FF.", "FFG", "FF.", "K.K", "K.K"],
}


def people(kind, count, flip=False, stagger=False):
    rows = [["."] * MC_W for _ in range(H)]
    art = PERSON[kind]
    h = len(art)
    for n in range(count):
        col = 1 + n * 4
        lift = 1 if stagger and n % 2 else 0
        for r, line in enumerate(art):
            for c, ch in enumerate(line):
                if ch != "." and col + c < MC_W:
                    rows[H - h + r - lift][col + c] = ch
    out = ["".join(r) for r in rows]
    return mirror_h(out) if flip else out


def pows():
    out = []
    for count in (1, 2, 3):
        for kind, flip in (("run_a", False), ("run_b", False), ("run_a", True), ("run_b", True),
                           ("wave_a", False), ("wave_b", False)):
            out.append(Sprite("pow", f"{count}_{kind}{'L' if flip else 'R'}",
                              people(kind, count, flip, stagger=True), color=YELLOW))
    return out


# ---------------------------------------------------------------- aircraft
JET = [
    "..........K.",
    ".........KFK",
    "........KFFK",
    "...KKK..KFFK",
    "..KGGKKKKFFK",
    ".KGGKFFFFFFK",
    "KFFFFFFFFFFK",
    "KFFFFFFGGFFK",
    ".KKFFFFFFFKK",
    "...KKFFFFK..",
    ".....KFFK...",
    "......KK....",
]
FLAME = [("G.", "KF"), ("GG", ".K")]


def jets():
    out = []
    for f in (0, 1):
        art = [r for r in JET]
        art[6] = art[6]
        left = pad(art, top=4)
        # the exhaust flickers in the last cell of the fuselage rows
        rows = [list(r) for r in left]
        rows[11][11] = FLAME[f][0][0]
        rows[12][11] = FLAME[f][0][1] if FLAME[f][0][1] != "." else "G"
        left = ["".join(r) for r in rows]
        out.append(("L", f, left))
    sprites = [Sprite("jet", f"left{f}", rows, color=LBLUE) for _, f, rows in out]
    sprites += [Sprite("jet", f"right{f}", mirror_h(rows), color=LBLUE) for _, f, rows in out]
    return sprites


def enemy_helis():
    """Hostile gunship, one sprite: humped body, canopy to the left, skids, tail fin."""
    body = [
        ".....KK.....",
        "...KKFFKK..K",
        "..KGGFFFFK.K",
        ".KGGKFFFFFKK",
        "KFFFFFFFFFFK",
        "KFFFFFFFKKKK",
        ".KKFFFFK..K.",
        "...KKKK.....",
        "..K....K....",
        ".KGGGGGGK...",
    ]
    rotors = ["KGGGGGGGGGGK", "...GGGGGG..."]
    frames = [pad([rotors[f]] + body, top=5) for f in (0, 1)]
    return ([Sprite("heli", f"left{f}", frames[f], color=LRED) for f in (0, 1)]
            + [Sprite("heli", f"right{f}", mirror_h(frames[f]), color=LRED) for f in (0, 1)])


# ---------------------------------------------------------------- projectiles (art is centred at cell 6, row 10)
def centred(art):
    top = 10 - len(art) // 2
    rows = []
    for r in art:
        left = 6 - len(r) // 2
        rows.append("." * left + r)
    return pad(rows, top=top)


def bullets():
    return [Sprite("bullet", "tracer", centred(["GGG", "FFF"]), color=YELLOW)]


def bombs():
    return [Sprite("bomb", "bomb", centred(["G", "F", "F", "K"]), color=LGREY)]


# nose to the left: outlined white body, fins, yellow exhaust. Three rows tall, because
# one row reads as a stray line on the screen at this speed.
MISSILE = [".KKKKK.K", "KGGGGGKF", ".KKKKK.K"]


def shots():
    return [Sprite("shot", "flak0", centred([".G.", "GFG", ".G."]), color=ORANGE),
            Sprite("shot", "flak1", centred(["F.F", ".G.", "F.F"]), color=RED),
            Sprite("shot", "missile_l", centred(MISSILE), color=YELLOW),
            Sprite("shot", "missile_r", centred([r[::-1] for r in MISSILE]), color=YELLOW),
            Sprite("shot", "bomb", centred(["F", "G", "F"]), color=RED)]


# ---------------------------------------------------------------- explosions and smoke
def blast(radius, core, seed, ragged=0.45):
    rows = []
    for r in range(H):
        line = ""
        for c in range(MC_W):
            dx, dy = (c - 5.5) * 2, r - 10
            d = (dx * dx + dy * dy) ** 0.5 + (noise(c, r, seed) - 0.5) * radius * ragged
            if d < core:
                line += "G"
            elif d < radius * 0.72:
                line += "F"
            elif d < radius:
                line += "K" if noise(c, r, seed + 7) < 0.55 else "F"
            else:
                line += "."
        rows.append(line)
    return rows


def explosions():
    stages = [(4, 3, YELLOW), (7, 5, YELLOW), (10, 5, ORANGE), (11, 3, ORANGE), (11, 0, RED), (10, 0, DGREY)]
    out = []
    for i, (radius, core, col) in enumerate(stages):
        rows = blast(radius, core, i + 3, 0.5 + i * 0.12)
        if i >= 4:   # thinning out into smoke
            rows = ["".join(ch if noise(c, r, 40 + i) < 0.72 - (i - 4) * 0.25 else "."
                            for c, ch in enumerate(line)) for r, line in enumerate(rows)]
        out.append(Sprite("explosion", f"stage{i}", rows, color=col))
    return out


def small_blasts():
    out = []
    for i, (radius, core, col) in enumerate([(3, 2, YELLOW), (5, 2, ORANGE), (5, 0, DGREY)]):
        out.append(Sprite("spark", f"stage{i}", blast(radius, core, i + 20), color=col))
    return out


def smoke():
    out = []
    for i, radius in enumerate((3, 5, 6)):
        rows = blast(radius, 0, 30 + i, 0.6)
        rows = ["".join("." if (ch == "." or noise(c, r, 50 + i) > 0.8 - i * 0.2) else "F"
                        for c, ch in enumerate(line)) for r, line in enumerate(rows)]
        out.append(Sprite("smoke", f"puff{i}", rows, color=GREY))
    return out


GROUPS = [
    ("CHOP_R", "Gunship right", chop_right),
    ("CHOP_L", "Gunship left", chop_left),
    ("TILT_R", "Gunship tilted right", tilt_right),
    ("TILT_L", "Gunship tilted left", tilt_left),
    ("CHOP_F", "Gunship head-on", chop_front),
    ("GEAR_R", "Gunship right, wheels down", gear_right),
    ("GEAR_L", "Gunship left, wheels down", gear_left),
    ("GEAR_F", "Gunship head-on, wheels down", gear_front),
    ("SHADOW", "Ground shadow", shadows),
    ("DUST", "Rotor dust", dust),
    ("TANK", "Tank", tanks),
    ("TURRET", "Flak turret", turrets),
    ("POW", "POW squads (1,2,3 x run R,run R,run L,run L,wave,wave)", pows),
    ("JET", "Jet", jets),
    ("HELI", "Enemy helicopter", enemy_helis),
    ("BULLET", "Tracer", bullets),
    ("BOMB", "Bomb", bombs),
    ("SHOT", "Enemy shots", shots),
    ("EXPLOSION", "Explosion", explosions),
    ("SPARK", "Small blast", small_blasts),
    ("SMOKE", "Smoke", smoke),
]
