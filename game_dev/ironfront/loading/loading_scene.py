"""
IRONFRONT loading screen - scene file for tools/bitmap/koala_tool.py.

A dusk battlefield: the IRONFRONT logo across the top, the gunship from
heli_ref.png coming in low, a fireball with a rifle squad silhouetted against
it, the player tank in front, and the PRESS FIRE TO DEPLOY prompt.

Build:  python tools/bitmap/koala_tool.py game_dev/ironfront/loading/loading_scene.py
Writes loading.kla and loading_review.html. The review page embeds the title
march preview from ../music, so build the song first.
"""
import base64
import json
import math
import pathlib

from koala_tool import (BLACK, BLUE, BROWN, DGREY, GREY, H, LGREY, LRED, ORANGE, PURPLE, RED, W, WHITE, YELLOW,
                        bayer, big_text, noise, read_png, small_text, smooth_noise)

HERE = pathlib.Path(__file__).resolve().parent
OUTPUT = "loading"
HELI_REF = HERE / "heli_ref.png"


# ---------------------------------------------------------------- scene parts
def sky(cv):
    # night at the top, through blue and purple, to a red dusk at the horizon
    bands = [(0, BLACK), (16, BLACK), (26, BLUE), (38, PURPLE), (50, RED), (62, LRED)]
    for y in range(62):
        for (y0, a), (y1, b) in zip(bands, bands[1:]):
            if y0 <= y < y1:
                f = (y - y0) / (y1 - y0)
                for x in range(W):
                    cv.px[y][x] = b if f > bayer(x, y) else a
    for x, y in ((6, 27), (22, 30), (70, 26), (100, 28), (114, 24), (136, 27), (154, 30)):
        cv.put(x, y, WHITE)


def ground(cv):
    # distant ridge, then dirt getting darker toward the viewer, lit by the blast
    for x in range(W):
        ridge = 59 + int(2.2 * math.sin(x / 9.0) + 1.5 * math.sin(x / 3.7 + 1))
        for y in range(ridge, 63):
            cv.px[y][x] = BROWN
    for y in range(63, H):
        for x in range(W):
            depth = (y - 63) / (H - 63)
            c = ORANGE if depth * 1.6 < bayer(x, y) + 0.2 else BROWN
            if depth > 0.7 and noise(x, y, 5) < (depth - 0.7) * 1.6:
                c = BLACK
            glow = 1 - math.hypot((x - 45) / 1.6, (y - 66) * 1.4) / 30
            if glow > bayer(x, y) * 0.9 + 0.05:
                c = LRED
            cv.px[y][x] = c
    for cx, cy, r in ((128, 80, 5), (20, 92, 4), (150, 94, 6), (104, 70, 3)):
        for y in range(cy - r, cy + r):
            for x in range(cx - 2 * r, cx + 2 * r):
                if ((x - cx) / 2) ** 2 + (y - cy) ** 2 * 1.6 < r * r * 0.5 + noise(x, y, 2) * 3:
                    cv.put(x, y, BLACK)


FIRE = [(44, 54, 16), (32, 52, 10), (56, 50, 11), (45, 43, 11), (35, 62, 9), (55, 61, 9), (45, 64, 8)]
SMOKE = [(42, 41, 12), (54, 38, 10), (64, 34, 8), (74, 31, 6), (83, 29, 4)]  # blown to the right


def explosion(cv):
    def field(puffs, x, y):
        return max(1 - math.hypot(x - cx, y - cy) / r for cx, cy, r in puffs)

    for y in range(4, 70):
        for x in range(10, 100):
            s = field(SMOKE, x, y) + (smooth_noise(x, y, 7, 3.0) - 0.5) * 0.5
            if s > 0:
                cv.px[y][x] = GREY if s > 0.5 + bayer(x, y) * 0.15 else DGREY if s > 0.1 else BLACK
            h = field(FIRE, x, y) + (smooth_noise(x, y, 3, 3.5) - 0.5) * 0.45
            if h > 0:
                t = h + (bayer(x, y) - 0.5) * 0.08  # dither the ring edges a little
                cv.px[y][x] = (WHITE if t > 0.78 else YELLOW if t > 0.58 else LRED if t > 0.36
                               else ORANGE if t > 0.17 else RED)
    # debris arcing out of the fireball
    for i in range(14):
        a = -math.pi * (0.1 + 0.8 * noise(i, 1, 9))
        d = 18 + 10 * noise(i, 2, 9)
        cv.put(int(45 + math.cos(a) * d * 1.3), int(52 + math.sin(a) * d), BLACK if i % 3 else YELLOW)


TANK = [
    "...............KKKKKKKKKK.....................",
    "..............KYYYYYYYYYYK....................",
    ".............KYYYYYYYYYYYYKKKKKKKKKKKKKKKKKKKK",
    ".............KYYKKYYYYYYYYYYYYYYYYYYYYYYYYYYYK",
    ".............KYYKKYYYYYYYYBBBBBBBBBBBBBBBBBBBK",
    ".............KBYYYYYYYYYYBKKKKKKKKKKKKKKKKKKKK",
    "..............KBBBBBBBBBBK....................",
    "....KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK........",
    "...KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYK.......",
    "..KYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYK......",
    ".KBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBK.....",
    "KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK....",
    "KGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGK....",
    "KGKKKGKKKGKKKGKKKGKKKGKKKGKKKGKKKGKKKGKKGK....",
    ".KGGGKKGGGKKGGGKKGGGKKGGGKKGGGKKGGGKKGGGK.....",
    "..KGKKKKKGKKKKKGKKKKKGKKKKKGKKKKKGKKKKKGK......",
    "...KKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKKK.......",
]

SOLDIER = [
    [
        "....KK....",
        "...KKKK...",
        "....KK....",
        "...KKKK...",
        "..KKKKKKKK",
        ".KKKKKK...",
        ".K.KKKK...",
        "...KKK....",
        "...KKKK...",
        "..KK..KK..",
        ".KK....KK.",
        "KK......K.",
        "K.........",
    ],
    [
        "....KK....",
        "...KKKK...",
        "....KK....",
        "...KKKK...",
        "..KKKKKKKK",
        "..KKKKK...",
        "...KKKK...",
        "...KKK....",
        "...KKK....",
        "...KKKK...",
        "..KK.KK...",
        "..K...K...",
        "..K...KK..",
    ],
]


def units(cv):
    # soldiers silhouetted against the fireball, charging right behind the tank
    for i, (x, y) in enumerate(((14, 64), (26, 67), (40, 65), (55, 68))):
        cv.blit(SOLDIER[i % 2], x, y, {"K": BLACK})
    for x in range(52, 98):
        for y in (87, 88):
            if noise(x, y, 4) < 0.85:
                cv.put(x, y, BLACK)
    cv.blit(TANK, 54, 71, {"K": BLACK, "Y": YELLOW, "B": BROWN, "G": GREY})


def heli_art(path):
    # reference is 1024x1024 at 16 px per art pixel; map its blue-greys to C64 greys
    w, h, px = read_png(path)
    cells = []
    for gy in range(h // 16):
        row = []
        for gx in range(w // 16):
            (r, g, b), a = px[gy * 16 + 8][gx * 16 + 8]
            if a < 128:
                row.append(None)
                continue
            lum = 0.3 * r + 0.59 * g + 0.11 * b
            row.append(BLACK if lum < 16 else DGREY if lum < 44 else GREY if lum < 95 else LGREY)
        cells.append(row)
    ys = [y for y, row in enumerate(cells) if any(c is not None for c in row)]
    xs = [x for row in cells for x, c in enumerate(row) if c is not None]
    return [row[min(xs):max(xs) + 1] for row in cells[min(ys):max(ys) + 1]]


def helicopter(cv, art, oy=16):
    ox = W - len(art[0])
    for r, row in enumerate(art):
        for c, col in enumerate(row):
            cv.put(ox + c, oy + r, col)
    return [ox, oy, len(art[0]), len(art)]


FONT5 = {
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
}


def logo(cv):
    # white top edge, yellow body, orange then brown toward the base
    ramp = [WHITE] + [YELLOW] * 11 + [ORANGE] * 6 + [BROWN] * 3
    big_text(cv, "IRONFRONT", FONT5, y0=2, scale=3, gap=2, ramp=ramp)


def compose(cv):
    sky(cv)
    ground(cv)
    explosion(cv)
    heli_box = helicopter(cv, heli_art(HELI_REF), oy=25)
    units(cv)
    logo(cv)
    small_text(cv, "PRESS FIRE TO DEPLOY", 41, 93, WHITE)
    return {"heli": heli_box}


def music_preview():
    """Song summary plus one pass of SID register writes from ../music (tools/sid/song_tool.py --build)."""
    music = HERE.parent / "music"
    song = json.loads((music / "music.json").read_text(encoding="utf-8"))
    log = json.loads((music / "sid_log.json").read_text(encoding="utf-8"))
    frames = song["bars"] * 16 * 6
    assert log["frames"] >= frames, "rebuild the song with more SIM_FRAMES"
    return {"song": song, "maxCycles": log["maxCycles"], "regs": log["regs"][:frames]}


def write_review(r):
    data = {"palette": r.palette, "bg": r.bg, "final": r.hexrows(r.final), "raw": r.hexrows(r.raw),
            "clashes": r.clashes, "heli": r.extras["heli"]}
    template = (HERE / "review_template.html").read_text(encoding="utf-8")
    page = HERE / "loading_review.html"
    page.write_text(
        template.replace("/*SCREEN_DATA*/null", json.dumps(data, separators=(",", ":")))
        .replace("/*REF_URI*/", "data:image/png;base64," + base64.b64encode(HELI_REF.read_bytes()).decode())
        .replace("/*MUSIC_DATA*/null", json.dumps(music_preview(), separators=(",", ":"))),
        encoding="utf-8")
    return page
