"""
HELISCAPE levels - level file for tools/levels/level_tool.py.

255 levels (the most one byte can count; see the memory map in heliscape.asm for what
is left over). Each is generated from its number, so every run of the build gives the
same game. Difficulty climbs fast at first and keeps climbing to the last level:
d = (level / last) ** CURVE. CHECK makes the build fail if any level is not harder
than the one before.

Layout record per level:  camps, (column, POWs) x camps, units, (column, type) x units
where a unit's type is 0 turret, 1 tank, 2 fast tank.

Build:  python tools/levels/level_tool.py game_dev/Heliscape/map/heliscape_levels.py
"""
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from heliscape_map import OBJECTS, PALETTES  # noqa: E402

TITLE = "HELISCAPE"
OUTPUT = "heliscape"
COUNT = 255
CURVE = 0.55
FIRST_COL, LAST_COL = 40, 246      # east of the home base; a camp is 8 columns wide
SCENERY_W = {"PALM": 3, "ROCK": 3, "WRECK": 2}
CONSTS = {"PALETTES": PALETTES}


def lerp(a, b, d):
    return int(round(a + (b - a) * d))


def scenery_cols(palette):
    cols = set()
    for kind, col, mask, _ in OBJECTS:
        if mask >> palette & 1:
            cols.update(range(col, col + SCENERY_W[kind]))
    return cols


def place_camps(rng, count, palette):
    """Spread the camps along the map, jittered, clear of this palette's scenery."""
    busy = scenery_cols(palette)
    span = (LAST_COL - FIRST_COL) / count
    out = []
    for i in range(count):
        low = int(FIRST_COL + i * span)
        high = int(FIRST_COL + (i + 1) * span) - 16
        spots = [c for c in range(low, max(high, low) + 1) if not busy & set(range(c, c + 8))]
        out.append(rng.choice(spots or [low]))
    return out


def split_pows(total, camps):
    base, extra = divmod(total, camps)
    return [base + (i < extra) for i in range(camps)]


def place_units(rng, turrets, tanks, fast, camps):
    """Turrets stand clear of the camps; tanks start anywhere and will come to you."""
    units = []
    for _ in range(turrets):
        spots = [c for c in range(FIRST_COL, LAST_COL) if all(not -3 <= c - k < 10 for k in camps)
                 and all(abs(c - u) > 6 for u, _ in units)]
        units.append((rng.choice(spots), 0))
    for i in range(tanks):
        units.append((rng.randrange(FIRST_COL + 8, LAST_COL), 2 if i < fast else 1))
    return units


def make_level(n):
    d = (n / (COUNT - 1)) ** CURVE
    rng = random.Random(1983 + n)
    palette = n % PALETTES
    camps_n = 3 + round(2 * d)
    pows = min(16 + round(24 * d), camps_n * 8)
    units_n = 2 + round(4 * d)
    turrets = 0 if n < 3 else 1 + round(2 * d)
    tanks = max(units_n - turrets, 1)
    fast = round(tanks * d)
    camps = place_camps(rng, camps_n, palette)
    units = place_units(rng, turrets, tanks, fast, camps)
    layout = [camps_n]
    for col, p in zip(camps, split_pows(pows, camps_n)):
        layout += [col, p]
    layout += [len(units)]
    for col, kind in units:
        layout += [col, kind]
    percent = lerp(50, 85, d)
    need = (pows * percent + 99) // 100
    return {
        "pows": pows,
        "camps": camps_n,
        "turrets": turrets,
        "tanks": tanks,
        "fast": fast,
        "percent": percent,
        "need": need,
        "reload_tank": lerp(150, 30, d),
        "reload_turret": lerp(100, 25, d),
        "shot_speed": lerp(0, 4, d),
        "jet_delay": lerp(220, 30, d),
        "heli_delay": 0 if n < 1 else lerp(250, 30, d),
        "tank_hp": lerp(2, 5, d),
        "turret_hp": lerp(4, 10, d),
        "camp_hp": lerp(8, 16, d),
        "air_hp": lerp(1, 3, d),
        "dmg": lerp(0, 2, d),
        "repair": 31 if d < 0.34 else 63 if d < 0.67 else 127,
        "layout": layout,
    }


LEVELS = [make_level(n) for n in range(COUNT)]

# bigger is harder for these; the rest are countdowns, where smaller is harder
HARDER_UP = ("pows", "percent", "camps", "turrets", "fast", "shot_speed", "tank_hp", "turret_hp", "camp_hp",
             "air_hp", "dmg", "repair")
HARDER_DOWN = ("reload_tank", "reload_turret", "jet_delay", "heli_delay")


def harder_by(a, b):
    """How many settings got harder from level a to level b."""
    moved = sum(b[k] > a[k] for k in HARDER_UP)
    moved += sum(b[k] < a[k] for k in HARDER_DOWN if a[k])
    return moved + (a["heli_delay"] == 0 and b["heli_delay"] > 0)


# The curve flattens late on, so rounding can leave two neighbours equal: when it
# does, shave the longest enemy timer so that every level really is harder.
for _a, _b in zip(LEVELS, LEVELS[1:]):
    for _k in HARDER_DOWN:
        if _a[_k]:
            _b[_k] = min(_b[_k], _a[_k])
    if not harder_by(_a, _b):
        _k = max((k for k in HARDER_DOWN if _b[k]), key=lambda k: _b[k])
        _b[_k] -= 1

TABLES = [(f"lv_{k}", k) for k in ("need", "reload_tank", "reload_turret", "shot_speed", "jet_delay", "heli_delay",
                                   "tank_hp", "turret_hp", "camp_hp", "air_hp", "dmg", "repair")]
RECORDS = [("lv_layout", "layout")]
COLUMNS = ["pows", "percent", "need", "camps", "tanks", "fast", "turrets", "reload_tank", "reload_turret", "shot_speed",
           "jet_delay", "heli_delay", "tank_hp", "turret_hp", "camp_hp", "air_hp", "dmg", "repair"]

def CHECK(levels):
    for i, (a, b) in enumerate(zip(levels, levels[1:]), 2):
        for key in HARDER_UP:
            assert b[key] >= a[key], f"level {i} eases {key}"
        for key in HARDER_DOWN:
            assert a[key] == 0 or b[key] <= a[key], f"level {i} eases {key}"
        assert a["tanks"] + a["turrets"] <= b["tanks"] + b["turrets"], f"level {i} has fewer units"
        assert harder_by(a, b), f"level {i} is no harder than level {i - 1}"
    for i, lv in enumerate(levels, 1):
        assert lv["tanks"] + lv["turrets"] <= 6, f"level {i}: more units than the game has slots"
        assert lv["camps"] <= 5 and lv["pows"] <= 99 and lv["need"] <= lv["pows"], f"level {i}"
        assert len(lv["layout"]) == 2 + 2 * lv["camps"] + 2 * (lv["tanks"] + lv["turrets"]), f"level {i}"
        assert min(lv[k] for k in ("reload_tank", "reload_turret", "jet_delay")) >= 10, f"level {i}: timers too short"
