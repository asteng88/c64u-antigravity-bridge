"""
TORNADO sprite bank - bank file for tools/sprites/sprite_tool.py.

Sprites:
  HELI       8 directions x 2 rotor frames = 16 multicolor sprites
  SHADOW     8 directions = 8 hires black shadow sprites
  TORNADO    4 animated swirling funnel frames (multicolor, expanded in-game)
  CRATE      2 pulsing rescue crate frames (multicolor)
  EXPLOSION  6 procedural explosion/splash frames (multicolor)
"""
import math

from sprite_tool import (DIRS, H, MC_W, Sprite, art, blank, flip_v, hires_canvas,
                         mirror_c, mirror_h, noise, stamp, to_rows)

TITLE = "TORNADO"
MC0 = 0       # black: outlines
MC1 = 1       # white: rotor highlights, funnel foam, crate cross
HELI_COL = 7  # yellow rescue chopper
TORN_COL = 3  # cyan/white swirling cyclone
CRATE_COL = 10  # light red / orange rescue crate

ASM_NOTES = [
    "Multicolor shared: $D025 = 0 (black), $D026 = 1 (white)",
    "HELI: index = SPR_HELI + dir*2 + frame, dir 0..7 = N NE E SE S SW W NW",
    "TORNADO: 4 frames (SPR_TORNADO + 0..3), CRATE: 2 frames, EXPLOSION: 6 frames",
]


# ---------------------------------------------------------------- helicopter
HELI_BODY = {
    "N": art(
        "....KKKK....",
        "...KGGGGK...",
        "..KGGFFGGK..",
        "..KFFFFFFK..",
        ".KKFFFFFFKK.",
        ".K.KFFFFK.K.",
        ".K.KFFFFK.K.",
        ".K.KFFFFK.K.",
        ".KKFFFFFFKK.",
        "...KFFFFK...",
        "....KFFK....",
        "....KFFK....",
        "....KFK.....",
        "....KFK.....",
        "...KKKKK....",
        "..KFFFFFK...",
        "...KKKKK....",
        "....KFK.....",
        top=2),
    "NE": art(
        ".......KKKK.",
        "......KGGGFK",
        ".....KGGFFFK",
        "....KFFFFFFK",
        "...KFFFFFFK.",
        "...KFFFFFK..",
        "...KFFFFK...",
        "..KKFFKK....",
        "..KFFKK.....",
        ".KFFK.......",
        "KFFK........",
        "KKK.........",
        ".K..........",
        top=3),
    "E": art(
        "KK..........",
        "KFK..KKKKK..",
        "KFFKKFFFFFK.",
        ".KFFFFFFFGGK",
        ".KKKKKKKKFGK",
        "...KFFFFFFFK",
        "...KFFFFFFK.",
        "....KKKKKK..",
        ".....K..K...",
        "...KKKKKKKK.",
        top=5),
}

ROTOR_CENTER = {
    "N": (5.5, 7.0), "NE": (6.0, 7.0), "E": (6.0, 6.0), "SE": (6.0, 12.0),
    "S": (5.5, 13.0), "SW": (5.0, 12.0), "W": (5.0, 6.0), "NW": (5.0, 7.0),
}


def _rotor(c, ox, oy, a0, a1):
    for a in (a0, a1):
        for r in range(-5, 6):
            x = int(round(ox + r * math.cos(a)))
            y = int(round(oy + r * math.sin(a) * 1.15))
            if 0 <= x < MC_W and 0 <= y < H:
                c[y][x] = "G" if abs(r) >= 4 or r == 0 else "K"


def _heli_dir(d):
    if d in HELI_BODY:
        return [row[:] for row in HELI_BODY[d]]
    if d == "SE":
        return flip_v(HELI_BODY["NE"])
    if d == "S":
        return flip_v(HELI_BODY["N"])
    if d == "SW":
        return mirror_h(flip_v(HELI_BODY["NE"]))
    if d == "W":
        return mirror_h(HELI_BODY["E"])
    if d == "NW":
        return mirror_h(HELI_BODY["NE"])
    return blank()


def heli_set():
    out = []
    for d in DIRS:
        base = _heli_dir(d)
        ox, oy = ROTOR_CENTER[d]
        for ph in range(2):
            c = [list(row) for row in base]
            a0 = 0.25 + ph * 0.785
            _rotor(c, ox, oy, a0, a0 + math.pi / 2)
            out.append(Sprite("HELI", f"{d}-{ph}", to_rows(c), mode="mc", color=HELI_COL, delay=3))
    return out


def heli_shadow_set():
    out = []
    for d in DIRS:
        base = _heli_dir(d)
        rows = ["".join("##" if ch != "." else ".." for ch in row) for row in base]
        out.append(Sprite("SHADOW", d, rows, mode="hr", color=0))
    return out


# ---------------------------------------------------------------- tornado funnel
def tornado_set():
    out = []
    for f in range(4):
        c = blank()
        phase = f * math.pi / 2
        for y in range(H):
            # Funnel tapers from wide top (y=0) to narrow base (y=20)
            t = y / (H - 1)
            half_w = 5.2 * (1.0 - t * 0.75) + 0.8
            sway = math.sin(phase + y * 0.45) * (1.1 + t * 0.8)
            cx = 5.5 + sway
            for x in range(MC_W):
                dx = abs(x - cx)
                if dx <= half_w:
                    # Swirling bands of white foam and cyan/black core
                    swirl = math.sin(phase * 1.5 + y * 0.7 + (x - cx) * 0.9)
                    if dx > half_w - 1.1:
                        c[y][x] = "K" if (y + f) % 2 == 0 else "F"
                    elif swirl > 0.25:
                        c[y][x] = "G"
                    elif swirl < -0.45:
                        c[y][x] = "K"
                    else:
                        c[y][x] = "F"
        out.append(Sprite("TORNADO", f"SWIRL-{f}", to_rows(c), mode="mc", color=TORN_COL, delay=4))
    return out


# ---------------------------------------------------------------- rescue crate
def crate_set():
    base0 = art(
        "............",
        "...KKKKKK...",
        "..KFFFFFFK..",
        "..KFGGGGFK..",
        "..KFGFGGFK..",
        "..KFGGGGFK..",
        "..KFFFFFFK..",
        "...KKKKKK...",
        top=6)
    base1 = art(
        "....G..G....",
        "...KKKKKK...",
        "..KGGGGGGK..",
        "..KGFGGFGK..",
        "..KGGGGGGK..",
        "..KGFGGFGK..",
        "..KGGGGGGK..",
        "...KKKKKK...",
        "....G..G....",
        top=5)
    return [
        Sprite("CRATE", "IDLE-0", to_rows(base0), mode="mc", color=CRATE_COL, delay=10),
        Sprite("CRATE", "IDLE-1", to_rows(base1), mode="mc", color=CRATE_COL, delay=10),
    ]


# ---------------------------------------------------------------- explosion
def explosion_set():
    out = []
    for f in range(6):
        c = blank()
        rad = 2.0 + f * 1.45
        for y in range(H):
            for x in range(MC_W):
                d = math.hypot(x - 5.5, (y - 10) * 0.7)
                n = noise(x + f * 7, y + f * 3, 1) * 2.2
                if d + n < rad:
                    if f >= 4 and d < rad * 0.45:
                        continue
                    c[y][x] = "G" if d < rad * 0.45 else ("F" if d < rad * 0.8 else "K")
        col = 7 if f < 2 else (8 if f < 4 else 2)
        out.append(Sprite("EXPLOSION", f"FRAME-{f}", to_rows(c), mode="mc", color=col, delay=4))
    return out


# ---------------------------------------------------------------- waving survivor & winch hook
def person_set():
    wave0 = art(
        "..K.....K...",
        "..F.KKK.F...",
        "...KFGFK....",
        "....KFK.....",
        "....KFK.....",
        "....K.K.....",
        "...KK.KK....",
        top=10)
    wave1 = art(
        "..K.........",
        "..F.KKK.....",
        "...KFGFK....",
        "....KFKF....",
        "....KFK.K...",
        "....K.K.....",
        "...KK.KK....",
        top=10)
    wave2 = art(
        "............",
        "....KKK.....",
        "....KGFK....",
        "...KKFKK....",
        "..K.KFK.K...",
        "....K.K.....",
        "...KK.KK....",
        top=10)
    wave3 = art(
        "........K...",
        "....KKK.F...",
        "...KFGFK....",
        "...FKFK.....",
        "..K.KFK.....",
        "....K.K.....",
        "...KK.KK....",
        top=10)
    return [
        Sprite("PERSON", "WAVE-0", to_rows(wave0), mode="mc", color=CRATE_COL, delay=5),
        Sprite("PERSON", "WAVE-1", to_rows(wave1), mode="mc", color=CRATE_COL, delay=5),
        Sprite("PERSON", "WAVE-2", to_rows(wave2), mode="mc", color=CRATE_COL, delay=5),
        Sprite("PERSON", "WAVE-3", to_rows(wave3), mode="mc", color=CRATE_COL, delay=5),
    ]


def hook_set():
    rows = [
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "...........##...........",
        "..........####..........",
        ".........##..##.........",
        ".........##..##.........",
        ".............##.........",
        "..........####..........",
        "........................",
        "........................",
    ]
    return [Sprite("HOOK", "WINCH", rows, mode="hr", color=1)]


GROUPS = [
    ("HELI", "Rescue Helicopter", heli_set),
    ("SHADOW", "Helicopter Shadow", heli_shadow_set),
    ("TORNADO", "Tornado Cyclone", tornado_set),
    ("CRATE", "Supply Crate", crate_set),
    ("PERSON", "Waving Survivor", person_set),
    ("HOOK", "Rescue Winch Hook", hook_set),
    ("EXPLOSION", "Explosion", explosion_set),
]
