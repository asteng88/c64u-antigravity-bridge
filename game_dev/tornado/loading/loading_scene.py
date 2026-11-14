"""
TORNADO loading screen - scene file for tools/bitmap/koala_tool.py (full 160x200).

A storm sky spirals down into a huge wind-whipped tornado over the sea. The
yellow rescue helicopter banks round the funnel toward the viewer, a survivor
clinging to its winch rope, under the TORNADO logo, with the prompt and the
Station88 Retro credit.

Shapes are worked out in 320x200 screen units (sx = 2 * art x, sy = art y), so
circles stay round on the 2:1 multicolor pixels. Each area keeps to three
colours plus black so the 4x8 cells hold them: sky purple/blue + cloud greys,
tornado greys, sea blues, helicopter yellow/orange/cyan, survivor reds.
"""
import math

from koala_tool import (BLACK, BLUE, BROWN, CYAN, DGREY, FONT3, GREY, GREEN,
                        LBLUE, LGREY, LRED, ORANGE, PURPLE, RED, WHITE,
                        YELLOW, bayer, noise, smooth_noise)

FULL_RES = True
OUTPUT = "loading"
BG = BLACK

FONT3.update({
    "8": ["###", "#.#", "###", "#.#", "###"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "N": ["###", "#.#", "#.#", "#.#", "#.#"],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"],
})

# 6x7 bold logo letters
LOGO_FONT = {
    "T": ["######", "######", "..##..", "..##..", "..##..", "..##..", "..##.."],
    "O": [".####.", "######", "##..##", "##..##", "##..##", "######", ".####."],
    "R": ["#####.", "######", "##..##", "#####.", "####..", "##.##.", "##..##"],
    "N": ["##..##", "###.##", "######", "######", "##.###", "##..##", "##..##"],
    "A": ["..##..", ".####.", "##..##", "##..##", "######", "######", "##..##"],
    "D": ["#####.", "######", "##..##", "##..##", "##..##", "######", "#####."],
}

HORIZON = 150
FUNNEL_X = 232                  # screen units
FUNNEL_TOP, FUNNEL_BASE = 44, 168


def each(cv, y0=0, y1=None):
    """Every art pixel (rows y0..y1) with the centre of its screen area."""
    for y in range(y0, cv.h if y1 is None else y1):
        for x in range(cv.w):
            yield x, y, 2 * x + 1, y + 0.5


def dither(a, b, f, x, y):
    """Colour b on a share f of pixels (ordered dither), else a."""
    return b if f > bayer(x, y) else a


# ---------------------------------------------------------------- sky
def sky(cv):
    for x, y, sx, sy in each(cv, 0, HORIZON):
        if y < 46:
            c = dither(BLACK, BLUE, (y - 30) / 16, x, y)
        elif y < 70:
            c = dither(BLUE, PURPLE, (y - 46) / 24, x, y)
        elif y < 120:
            c = PURPLE
        else:
            c = dither(PURPLE, DGREY, (y - 120) / 30, x, y)
        cv.put(x, y, c)
    # storm clouds spiralling into the funnel: greys over the flat purple
    cx, cy = FUNNEL_X, 40
    for x, y, sx, sy in each(cv, 34, 112):
        dx, dy = sx - cx, (sy - cy) * 2.4
        r = math.hypot(dx, dy) + 1
        a = math.atan2(dy, dx)
        spiral = math.sin(a * 2 + math.log(r) * 4.6)
        billow = smooth_noise(sx / 7, sy / 3, 7, 3.0)
        v = spiral * 0.5 + billow * 0.85 - r / 300
        if v > 0.72:
            cv.put(x, y, GREY)
        elif v > 0.5:
            cv.put(x, y, dither(DGREY, GREY, (v - 0.5) * 4.5, x, y))
        elif v > 0.36:
            cv.put(x, y, dither(cv.px[y][x], DGREY, (v - 0.36) * 7, x, y))
    # distant lightning on the left
    x, y, k = 34.0, 56.0, 3
    while y < HORIZON - 3:
        nx = x + (noise(int(y), 0, k) - 0.45) * 10
        ny = y + 3 + noise(int(y), 1, k) * 4
        steps = int(max(abs(nx - x), abs(ny - y)) * 2) + 1
        for s in range(steps):
            px, py = x + (nx - x) * s / steps, y + (ny - y) * s / steps
            cv.put(int(px / 2), int(py), WHITE)
            cv.put(int(px / 2) - 1, int(py), LBLUE)
        x, y = nx, ny


# ---------------------------------------------------------------- sea
def sea(cv):
    for x, y, sx, sy in each(cv, HORIZON):
        depth = (y - HORIZON) / (cv.h - HORIZON)
        wave = math.sin(sx * (0.08 - depth * 0.045) + y * 0.85 + math.sin(sx * 0.021) * 2.2)
        chop = smooth_noise(sx / 4, y, 11, 2.5)
        if wave + chop * 0.6 > 1.3 - depth * 0.45:
            c = WHITE if chop > 0.72 else LBLUE
        elif wave > 0.5:
            c = dither(BLUE, LBLUE, 0.45, x, y)
        else:
            c = BLUE
        cv.put(x, y, c)
    # a low island on the left horizon with a palm bent by the wind
    for sx in range(0, 64):
        h = int(5 * math.sin(sx * math.pi / 64))
        for sy in range(HORIZON - h, HORIZON + 1):
            cv.put(sx // 2, sy, BROWN)
    trunk = [(26 + t * 1.0 + t * t * 0.035, HORIZON - 4 - t) for t in range(13)]
    for tx, ty in trunk:
        cv.put(int(tx / 2), int(ty), BROWN)
    fx, fy = trunk[-1]
    for k in range(5):
        for t in range(7):
            cv.put(int((fx + t * 2.3) / 2), int(fy + (k - 2) * 1.2 + t * (k - 1) * 0.35), GREEN)


# ---------------------------------------------------------------- tornado
def funnel_shape(sy):
    """Centre and half width of the funnel at screen row sy."""
    t = min(1.0, max(0.0, (sy - FUNNEL_TOP) / (FUNNEL_BASE - FUNNEL_TOP)))
    sway = math.sin(t * 3.4 + 0.6) * (8 + 16 * t)
    half = 11 + 86 * (1 - t) ** 1.8
    return FUNNEL_X + sway - 18 * t, half


def tornado(cv):
    for x, y, sx, sy in each(cv, FUNNEL_TOP - 10, FUNNEL_BASE + 3):
        cx, half = funnel_shape(sy)
        ragged = half * (1 + (smooth_noise(sy / 2, 0, 5, 2.0) - 0.5) * 0.3)
        u = (sx - cx) / ragged                     # -1 left edge .. 1 right edge
        if abs(u) > 1:
            continue
        if sy < FUNNEL_TOP and noise(x, y, 9) > (FUNNEL_TOP + 2 - sy) / 12:
            continue
        light = 0.95 - (u + 1) * 0.45              # lit from the left
        band = math.sin(u * 2.6 - sy * 0.21 + math.asin(u) * 2.2)
        v = light + band * 0.24 + (smooth_noise(sx / 3, sy, 13, 2.0) - 0.5) * 0.2
        if v > 0.74:
            c = dither(GREY, LGREY, (v - 0.74) * 5, x, y)
        elif v > 0.42:
            c = dither(DGREY, GREY, (v - 0.42) * 3.2, x, y)
        elif v > 0.18:
            c = dither(BLACK, DGREY, (v - 0.18) * 4, x, y)
        else:
            c = BLACK
        cv.put(x, y, c)
    # spray boiling up round the base
    bx, _ = funnel_shape(FUNNEL_BASE)
    for x, y, sx, sy in each(cv, FUNNEL_BASE - 26, FUNNEL_BASE + 12):
        dx, dy = (sx - bx) / 74, (sy - FUNNEL_BASE + 6) / 17
        d = dx * dx + dy * dy
        if d < 1:
            n = smooth_noise(sx / 3, sy / 1.5, 21, 2.0)
            if n > d * 0.85 + 0.28:
                cv.put(x, y, WHITE if n > 0.78 else LGREY)


def wind(cv):
    """Streaks whipping round the funnel and debris caught in them."""
    for k in range(16):
        sy0 = FUNNEL_TOP + 6 + k * 7.5
        cx, half = funnel_shape(sy0)
        rx = half + 10 + (k % 3) * 10
        ry = 4 + (k % 4) * 1.5
        a0 = noise(k, 1, 4) * 6.28
        span = 1.8 + noise(k, 2, 4) * 1.6
        steps = int(rx * span / 1.4)
        for s in range(steps):
            a = a0 + span * s / steps
            px = cx + math.cos(a) * rx
            py = sy0 + math.sin(a) * ry - s * 0.05
            if math.sin(a) < 0 and abs(px - cx) < half * 0.95:
                continue                          # behind the funnel
            if noise(s, k, 5) > 0.9:
                continue
            fade = s / steps
            cv.put(int(px / 2), int(py), WHITE if fade > 0.5 else LGREY)
    for k in range(46):
        a = noise(k, 3, 6) * 6.28
        sy = FUNNEL_TOP + 12 + noise(k, 4, 6) * 108
        cx, half = funnel_shape(sy)
        r = half + 6 + noise(k, 5, 6) * 44
        px, py = cx + math.cos(a) * r, sy + math.sin(a) * 5
        c = (BLACK, DGREY, BLACK, LGREY)[k % 4]
        cv.put(int(px / 2), int(py), c)
        if k % 3 == 0:
            cv.put(int(px / 2) + 1, int(py) + 1, c)


# ---------------------------------------------------------------- helicopter
HELI_X, HELI_Y = 100, 92        # fuselage centre, screen units
TILT = math.radians(-16)        # banked into the turn round the funnel


def to_local(sx, sy):
    dx, dy = sx - HELI_X, sy - HELI_Y
    c, s = math.cos(-TILT), math.sin(-TILT)
    return dx * c - dy * s, dx * s + dy * c


def to_screen(u, v):
    c, s = math.cos(TILT), math.sin(TILT)
    return HELI_X + u * c - v * s, HELI_Y + u * s + v * c


def _ell(u, v, cu, cv_, ru, rv):
    a, b = (u - cu) / ru, (v - cv_) / rv
    return a * a + b * b


def _poly(u, v, pts):
    """(inside, distance to the nearest edge) for a convex polygon."""
    inside = True
    best = 1e9
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sign = 1 if area > 0 else -1
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        ln = math.hypot(ex, ey)
        cross = (ex * (v - y0) - ey * (u - x0)) / ln * sign
        if cross < 0:
            inside = False
        t = max(0.0, min(1.0, ((u - x0) * ex + (v - y0) * ey) / (ln * ln)))
        best = min(best, math.hypot(u - (x0 + ex * t), v - (y0 + ey * t)))
    return inside, best


# Sea King, three-quarter front view: the long boat-hulled cabin side faces the
# viewer's left, the stepped cockpit nose comes toward the viewer on the right,
# twin engines sit on top under the five-blade rotor, the tail boom sweeps back
# and up to the tail rotor pylon. u right, v down, cabin centre at 0, 0.
SIDE = [(-48, -16), (10, -19), (10, 15), (-12, 16), (-40, 11), (-48, 4)]
NOSE = [(10, -19), (32, -17), (49, -6), (53, 8), (43, 17), (10, 15)]
GLASS = [(13, -16), (31, -14.5), (46, -4), (14, -3)]
ENGINES = [(-32, -16), (8, -19), (4, -29), (-27, -28)]
DOOR = (-38, -18, -12, 11)                      # u0, u1, v0, v1 of the open door
HOIST = (-42, -19)                              # end of the rescue hoist arm


def heli_pixel(u, v):
    """Colour at local (u, v) or None."""
    # cockpit nose and glazing
    inside, d = _poly(u, v, NOSE)
    if inside:
        if d < 1.3:
            return BLACK
        g_in, g_d = _poly(u, v, GLASS)
        if g_in:
            if g_d < 1.0 or any(abs(u - fu + (v + 9) * k) < 0.9 for fu, k in ((22, 0.2), (30, 0.35), (38, 0.6))):
                return BLACK                     # four-pane windscreen frames
            if 15 < u < 21 and -14 < v < -7:
                return WHITE                     # sky glint
            return CYAN if u < 31 else LBLUE
        if v > 9:
            return ORANGE                        # chin under the nose
        return YELLOW if u < 40 else ORANGE
    # cabin side: boat hull, door, windows
    inside, d = _poly(u, v, SIDE)
    if inside:
        if d < 1.3:
            return BLACK
        u0, u1, v0, v1 = DOOR
        if u0 <= u <= u1 and v0 <= v <= v1:
            if u < u0 + 1.5 or u > u1 - 1.5 or v < v0 + 1.5:
                return ORANGE                    # door frame
            return BLACK                         # dark cabin inside
        if -45 <= u <= -41 and -11 <= v <= -4:   # cabin window behind the door
            return WHITE if v < -9 else BLACK
        if -6 <= u <= 6 and -15 <= v <= -5:      # side cockpit window
            return CYAN if v > -13 else WHITE
        if v > 8 - (u + 48) * 0.05:
            return ORANGE                        # hull bottom
        if abs(v - 1) < 0.8:
            return ORANGE                        # rubbing strake along the side
        return YELLOW
    # twin engine fairing on top, intakes at the front, exhaust at the back
    inside, d = _poly(u, v, ENGINES)
    if inside:
        if d < 1.2:
            return BLACK
        if _ell(u, v, 1, -23.5, 3, 2.5) <= 1 or _ell(u, v, -7, -24, 3, 2.5) <= 1:
            return BLACK                         # twin air intakes
        if u < -22:
            return DGREY                         # exhausts
        return YELLOW if v < -24 else ORANGE
    # rescue hoist above the door
    hu, hv = HOIST
    if hu <= u <= -30 and abs(v - (hv + (u - hu) * 0.1)) <= 1.4:
        return ORANGE if abs(v - hv) < 0.7 else BLACK
    if -34 <= u <= -27 and -24 <= v <= -17:
        return BLACK if (u < -33 or v < -23) else ORANGE
    # sponson float with its wheel
    sp = _ell(u, v, -10, 15, 12, 5)
    if sp <= 1:
        return BLACK if sp > 0.7 else (YELLOW if v < 15 else ORANGE)
    wh = _ell(u, v, -10, 22, 3.5, 3.5)
    if wh <= 1:
        return DGREY if wh < 0.4 else BLACK
    # rotor mast
    if -13 <= u <= -7 and -39 <= v <= -28:
        return BLACK
    return None


def rotor_pixel(u, v):
    """Main rotor: five blades blurred into a tilted disc above everything."""
    disc = _ell(u, v, -8, -40, 104, 13)
    if disc <= 1:
        if disc > 0.9:
            return LGREY if u < 0 else GREY
        ang = math.atan2((v + 40) / 13, (u + 8) / 104)
        if abs(math.sin(ang * 2.5 + 0.5)) > 0.985:
            return WHITE                         # blade streaks
        return GREY if (int(u) // 2 + int(v)) % 2 == 0 else BLACK
    return None


def tail_pixel(u, v):
    """Tail boom sweeping back and up, tail pylon, stabiliser and tail rotor."""
    t = (-46 - u) / 36                             # 0 at the cabin .. 1 at the pylon
    if 0 <= t <= 1:
        vc = -6 - t * 30                           # foreshortened: back and up
        w = 9 - t * 5
        d = v - vc
        if abs(d) <= w:
            if abs(d) > w - 1.4:
                return BLACK
            return YELLOW if d < 1 else ORANGE
    inside, d = _poly(u, v, [(-88, -38), (-80, -38), (-84, -60), (-90, -60)])
    if inside:
        return BLACK if d < 1.2 else YELLOW        # tail pylon
    if -98 <= u <= -80 and abs(v - (-39 - (u + 80) * 0.15)) <= 1.4:
        return ORANGE                              # horizontal stabiliser
    rotor = _ell(u, v, -82, -55, 10, 10)
    if 0.5 < rotor <= 1:
        return LGREY
    if rotor <= 0.12:
        return BLACK
    return None


def helicopter(cv):
    mask = {}
    for x, y, sx, sy in each(cv, 40, 160):
        u, v = to_local(sx, sy)
        if not (-118 < u < 112 and -66 < v < 42):
            continue
        c = heli_pixel(u, v)                    # cabin in front,
        if c is None:
            c = tail_pixel(u, v)                # then the tail boom,
        if c is None:
            c = rotor_pixel(u, v)               # then the rotor disc behind them
        if c is not None:
            mask[(x, y)] = c
    # black halo so the helicopter's cells keep their colours apart from the sky
    for (x, y) in list(mask):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (x + dx, y + dy) not in mask:
                cv.put(x + dx, y + dy, BLACK)
    for (x, y), c in mask.items():
        cv.put(x, y, c)


# survivor pixel art (art pixels): hands at the top on the rope, legs swept by
# the wind. K black, W white, R skin, Y/O life jacket, G legs
SURVIVOR = [
    "....KK....",
    "...RKKR...",
    "...R..R...",
    "..RR..RR..",
    "..R....R..",
    "..R.WW.R..",
    "..RWWWWR..",
    "...WWWW...",
    "...RRRR...",
    "...RKRK...",
    "...RRRR...",
    "....RR....",
    "..YYYYYY..",
    ".YYYYYYYO.",
    ".YYYKKYYO.",
    ".YYYYYYYO.",
    ".YYYYYYOO.",
    "..YYYYYO..",
    "..YYYYYO..",
    "..YYYYOO..",
    "..GG..GG..",
    "..GG...GG.",
    "..GG...GG.",
    "...GG...GG",
    "...GG...GG",
    "....GG...G",
    "....KK...K",
]
SURVIVOR_COL = {"K": BLACK, "W": WHITE, "R": LRED, "Y": YELLOW, "O": ORANGE, "G": DGREY}


def survivor(cv):
    """Winch rope from the door, bowing in the wind, down to the survivor's
    hands; the survivor is swung sideways by the wind."""
    ox, oy = to_screen(-22, 13)                    # (where the old door winch was)
    hx, hy = ox - 10, oy + 16                      # hands, screen units: unchanged
    ax, ay = to_screen(*HOIST)                     # rope comes off the hoist arm
    figure = {}
    for s in range(60):
        t = s / 59
        sx = ax + (hx - ax) * t - math.sin(t * math.pi) * 7
        figure[(int(sx / 2), int(ay + (hy - ay) * t))] = WHITE
    x0 = int(hx / 2) - 5
    for r, line in enumerate(SURVIVOR):
        shift = r // 7                              # the wind swings the legs out
        for c, ch in enumerate(line):
            if ch != ".":
                for dy in (0, 1):                   # art rows are one rasterline: double up
                    figure[(x0 + c + shift, int(hy) + r * 2 + dy)] = SURVIVOR_COL[ch]
    for (x, y) in list(figure):
        for dx, dy in ((-1, 0), (1, 0), (0, 1), (0, -1)):
            if (x + dx, y + dy) not in figure:
                cv.put(x + dx, y + dy, BLACK)
    for (x, y), c in figure.items():
        cv.put(x, y, c)


# ---------------------------------------------------------------- text
def small(cv, s, x0, y0, sx, sy, colour):
    pitch = 4 * sx
    for i, ch in enumerate(s):
        for r, line in enumerate(FONT3[ch]):
            for c, bit in enumerate(line):
                if bit == "#":
                    for dy in range(sy):
                        for dx in range(sx):
                            cv.put(x0 + i * pitch + c * sx + dx, y0 + r * sy + dy, colour)


def logo(cv):
    sx, sy, gap = 3, 4, 3
    word = "TORNADO"
    pitch = 6 * sx + gap
    width = len(word) * pitch - gap
    x0, y0 = (cv.w - width) // 2, 4
    for y in range(0, y0 + 7 * sy + 6):
        for x in range(cv.w):
            cv.put(x, y, BLACK)
    ramp = [WHITE] * 5 + [CYAN] * 10 + [BLUE] * 13
    pix = {}
    for i, ch in enumerate(word):
        for r, line in enumerate(LOGO_FONT[ch]):
            for c, bit in enumerate(line):
                if bit != "#":
                    continue
                for dy in range(sy):
                    row = r * sy + dy
                    shift = (7 * sy - row) // 6            # wind-swept slant
                    for dx in range(sx):
                        pix[(x0 + i * pitch + c * sx + dx + shift, y0 + row)] = ramp[row]
    for (x, y) in pix:                                       # drop shadow
        if (x + 1, y + 2) not in pix:
            cv.put(x + 1, y + 2, BLUE)
    for (x, y), c in pix.items():
        cv.put(x, y, c)
    # wind lines streaking through the logo
    for k, (y, a, b) in enumerate(((8, 0, 40), (15, 30, 90), (22, 70, 130), (28, 100, 158))):
        for x in range(a, b):
            if cv.px[y][x] == BLACK and noise(x, y, 33) > 0.3:
                cv.put(x, y, BLUE if k % 2 else CYAN)


def captions(cv):
    # credit under the logo, double height so it reads at C64 resolution
    credit = "BY STATION88 RETRO"
    w = len(credit) * 4 - 1
    x0 = (cv.w - w) // 2
    for y in range(37, 49):
        for x in range(x0 - 3, x0 + w + 3):
            cv.put(x, y, BLACK)
    small(cv, credit, x0, 38, 1, 2, LGREY)
    # prompt along the bottom
    for y in range(184, 200):
        for x in range(cv.w):
            cv.put(x, y, BLACK)
    prompt = "PRESS FIRE TO LAUNCH"
    small(cv, prompt, (cv.w - (len(prompt) * 8 - 2)) // 2, 187, 2, 2, YELLOW)


def compose(cv):
    sky(cv)
    sea(cv)
    tornado(cv)
    wind(cv)
    helicopter(cv)
    survivor(cv)
    logo(cv)
    captions(cv)
