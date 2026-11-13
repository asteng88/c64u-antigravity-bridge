"""
TORNADO loading screen - scene file for tools/bitmap/koala_tool.py.

Stormy twilight ocean with a giant swirling tornado funnel, a tropical island,
and a yellow rescue helicopter flying in, with the TORNADO logo and prompt.
"""
import math

from koala_tool import (BLACK, BLUE, BROWN, CYAN, DGREY, FONT3, GREY, H,
                        LBLUE, LGREY, ORANGE, PURPLE, RED, W, WHITE, YELLOW,
                        bayer, big_text, noise, small_text)

FONT3.update({
    "8": ["###", "#.#", "###", "#.#", "###"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "G": ["###", "#..", "#.#", "#.#", "###"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["###", "#.#", "#.#", "#.#", "#.#"],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
})

OUTPUT = "loading"


def sky(cv):
    bands = [(0, BLACK), (18, BLACK), (32, BLUE), (48, DGREY), (64, PURPLE), (74, LBLUE)]
    for y in range(74):
        for (y0, a), (y1, b) in zip(bands, bands[1:]):
            if y0 <= y < y1:
                f = (y - y0) / (y1 - y0)
                for x in range(W):
                    cv.px[y][x] = b if f > bayer(x, y) else a
    # Storm cloud bank
    for y in range(20, 36):
        for x in range(W):
            n = noise(x // 2, y // 2, 3)
            if n > 0.55 and (y - 20) < 14:
                cv.put(x, y, GREY if n > 0.72 else DGREY)


def ocean_and_island(cv):
    for y in range(74, H):
        for x in range(W):
            wave = math.sin(x * 0.25 + y * 0.6)
            if wave > 0.75:
                cv.put(x, y, CYAN)
            elif wave > 0.2:
                cv.put(x, y, LBLUE)
            else:
                cv.put(x, y, BLUE)
    # Left tropical island silhouette
    for x in range(6, 52):
        h = 74 - int(7 * math.sin((x - 6) * math.pi / 46))
        for y in range(h, 76):
            cv.put(x, y, YELLOW if y >= 73 else BROWN)


def tornado_funnel(cv):
    cx0 = 116
    for y in range(24, 86):
        t = (y - 24) / 62.0
        half_w = 24 * ((1.0 - t) ** 1.4) + 3
        sway = math.sin(y * 0.22) * (4.0 * t + 1.5)
        cx = cx0 + sway
        for x in range(int(cx - half_w), int(cx + half_w) + 1):
            if 0 <= x < W:
                dx = abs(x - cx)
                swirl = math.sin(y * 0.5 + (x - cx) * 0.35)
                if dx > half_w - 2:
                    cv.put(x, y, WHITE if (y % 3 == 0) else CYAN)
                elif swirl > 0.3:
                    cv.put(x, y, LGREY)
                elif swirl < -0.35:
                    cv.put(x, y, DGREY)
                else:
                    cv.put(x, y, GREY)
    # Spray at base
    for i in range(30):
        px = int(cx0 + math.sin(i * 1.7) * 16)
        py = int(84 + math.cos(i * 2.3) * 4)
        if 0 <= px < W and 0 <= py < H:
            cv.put(px, py, WHITE)


def chopper(cv):
    # Simple bold yellow rescue helicopter at (34, 48)
    ox, oy = 34, 48
    # Rotor
    for x in range(ox - 16, ox + 17):
        cv.put(x, oy - 5, WHITE if x % 2 == 0 else LGREY)
    for y in range(oy - 4, oy):
        cv.put(ox, y, BLACK)
    # Body
    for y in range(oy, oy + 7):
        for x in range(ox - 7, ox + 9):
            if abs(x - ox) + abs(y - (oy + 3)) < 10:
                cv.put(x, y, YELLOW)
    # Cockpit
    for y in range(oy + 1, oy + 4):
        for x in range(ox + 2, ox + 7):
            cv.put(x, y, CYAN)
    # Tail boom
    for x in range(ox - 17, ox - 6):
        cv.put(x, oy + 2, YELLOW)
        cv.put(x, oy + 3, ORANGE)
    cv.put(ox - 17, oy, RED)
    cv.put(ox - 17, oy + 1, RED)
    # Skids
    for x in range(ox - 6, ox + 7):
        cv.put(x, oy + 8, LGREY)


def text_band(cv, text, x0, y0, colour):
    for y in range(y0 - 1, min(H, y0 + 6)):
        for x in range(x0 - 2, x0 + len(text) * 4 + 1):
            if 0 <= x < W:
                cv.put(x, y, BLACK)
    small_text(cv, text, x0, y0, colour)


def compose(cv):
    sky(cv)
    ocean_and_island(cv)
    tornado_funnel(cv)
    chopper(cv)
    ramp = [WHITE] + [CYAN] * 8 + [LBLUE] * 6 + [BLUE] * 5
    big_text(cv, "TORNADO", FONT3, y0=2, scale=4, gap=2, ramp=ramp)
    text_band(cv, "CYCLONE RESCUE", 50, 87, YELLOW)
    text_band(cv, "PRESS FIRE TO LAUNCH", 38, 93, WHITE)
