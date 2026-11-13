"""
Game projects for the studio: what kind of file is this, which build.py does it belong
to, and starter files for everything a game is made of. No GUI in here.
"""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Optional

from .gamedev import tools_root

# kinds of .py file, each built by the game tool of the same name
DEFINITION_KINDS = ("sprites", "tileset", "koala", "song", "levels")
BUILD_ORDER = {kind: i for i, kind in enumerate(DEFINITION_KINDS)}

KIND_LABELS = {
    "build": "GAME BUILD SCRIPT (BUILD.PY)",
    "sprites": "SPRITE BANK",
    "tileset": "TILES + MAP",
    "koala": "KOALA SCREEN",
    "song": "SID SONG",
    "sid": "SID MUSIC SOURCE (MOS 6581/8580 PSID)",
    "levels": "LEVEL TABLES",
    "python": "PYTHON SOURCE (MOS 6502 DIALECT)",
    "c": "C / C++ SOURCE (OSCAR64 / CC65)",
    "asm": "6502 ASSEMBLY",
}
# where a new file of each kind goes inside a project
KIND_FOLDERS = {"sprites": "sprites", "tileset": "map", "koala": "screens", "song": "music", "levels": "map"}
KIND_FILES = {"sprites": "sprites_new.py", "tileset": "tiles_new.py", "koala": "screen_new.py",
              "song": "song_new.py", "levels": "levels_new.py"}

NEW_ASM_TEMPLATE = """// ============================================================================
// COMMODORE 64 - MOS 6502 / 6510 KICKASSEMBLER SOURCE
// F7 builds this file, F5 builds it and runs it on the C64U
// ============================================================================

BasicUpstart2(start)

.const VIC_BORDER_COLOR = $D020
.const VIC_BG_COLOR0    = $D021
.const VIC_RASTER_LINE  = $D012

* = $0810 "Main Program"

start:
    sei
    lda #$0e            // Light Blue border
    sta VIC_BORDER_COLOR
    lda #$06            // Dark Blue background
    sta VIC_BG_COLOR0
    cli

main_loop:
    lda #$fb            // Wait for raster line 251
!wait:
    cmp VIC_RASTER_LINE
    bne !wait-

    inc VIC_BORDER_COLOR
    nop
    nop
    nop
    dec VIC_BORDER_COLOR
    jmp main_loop
"""

_SPRITES = '''"""
{title} sprite bank - build with F7: writes sprites.asm for the game to #import.

Multicolor cells:  .  transparent   K  $D025 (MC0)   F  sprite colour   G  $D026 (MC1)
Each frame is 21 rows of 12 cells.
"""
from sprite_tool import Sprite

TITLE = "{title}"
MC0 = 0     # black
MC1 = 1     # white

SHIP = [
    "............",
    ".....KK.....",
    ".....GG.....",
    "....KFFK....",
    "....KFFK....",
    "...KFGGFK...",
    "...KFGGFK...",
    "..KFFGGFFK..",
    "..KFFFFFFK..",
    ".KFFFFFFFFK.",
    ".KFFKFFKFFK.",
    "KFFK.KK.KFFK",
    "KFK......KFK",
    "KK........KK",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
    "............",
]


def ship():
    return [Sprite("SHIP", "ship", SHIP, color=7)]


# (name in the game: SPR_SHIP, title, function returning the frames)
GROUPS = [("SHIP", "Player ship", ship)]
'''

_TILESET = '''"""
{title} tileset - build with F7: writes a charset, tile tables and a map, and opens a review page.

Multicolor pixels:  .  $D021   ,  $D022   #  $D023   o  colour RAM (the tile's colour)
A tile is 16 rows of 8 pixels (2x2 characters).
"""
TITLE = "{title}"
BLACK, WHITE, RED, CYAN, PURPLE, GREEN, BLUE, YELLOW = range(8)
BG = (0, 9, 8)      # $D021, $D022, $D023

SKY = ["........"] * 16
GROUND = [
    "oooooooo", "oo,ooooo", "oooooo,o", "o,oooooo",
    "ooooo,oo", "oooooooo", ",ooooooo", "oooo,ooo",
] * 2

# (name, art, colour, flags: yours to define, the game reads them from tile_flags)
TILES = [
    ("SKY", SKY, BLUE, 0),
    ("GROUND", GROUND, GREEN, 1),
]
LEGEND = {{".": "SKY", "#": "GROUND"}}
MAP = [
    "................",
    "................",
    ".......##.......",
    "################",
]
'''

_KOALA = '''"""
{title} screen - build with F7: writes a Koala bitmap, 160 x 100 pixels.

Each 4x4 pixel cell can hold the background and three other colours; the tool
fixes any cell that breaks the rule and reports it.
"""
from koala_tool import BLUE, WHITE, YELLOW, small_text

OUTPUT = "{stem}"
BG = BLUE


def compose(cv):
    small_text(cv, "{title}", 40, 40, YELLOW)
    small_text(cv, "PRESS FIRE", 44, 60, WHITE)
'''

_SONG = '''"""
{title} song - build with F7: writes the music data and a .sid. F5 plays it on the C64U.

One pattern row = one sixteenth note at the driver's fixed 125 BPM.
"""
TITLE = "{title}"
ASM = "music.asm"
SID = dict(name="{title}", author="", released="", file="{stem}.sid")

INSTRUMENTS = {{
    "lead": dict(ad=0x37, sr=0xA8, pw=0x0500, pws=0x30, vib=1, wave=[(0x41, 0)], loop=None),
    "bass": dict(ad=0x05, sr=0x88, pw=0x0300, pws=0x20, vib=0, wave=[(0x41, 0)], loop=None),
}}

# (instrument, note or None for a rest, rows)
PATTERNS = {{
    "melody": [("lead", "C5", 4), ("lead", "E5", 4), ("lead", "G5", 4), ("lead", "E5", 4)],
    "bassline": [("bass", "C3", 8), ("bass", "G2", 8)],
    "rest": [("lead", None, 16)],
}}

# one (sequence of patterns, position to loop back to) per voice
ORDERS = [
    (["melody"], 0),
    (["bassline"], 0),
    (["rest"], 0),
]
FILTER_CUTOFF = 0x60
FILTER_ROUTING = 0x00
SIM_FRAMES = 300
'''

_MUSIC_ASM = """// Music block: driver + song. music_init = $1000, music_play = $1003.
#import "music_config.asm"

* = $1000 "Music"
#import "{driver}"
#import "music_data.asm"
"""

_LEVELS = '''"""
{title} levels - build with F7: writes tables for the game to #import, and a review page.

Each level is a dict. TABLES turns a key into one byte per level.
"""
TITLE = "{title}"


def level(n):
    return {{"speed": 1 + n // 2, "enemies": min(2 + n, 8)}}


LEVELS = [level(n) for n in range(10)]
TABLES = [("lv_speed", "speed"), ("lv_enemies", "enemies")]


def CHECK(levels):
    assert all(a["enemies"] <= b["enemies"] for a, b in zip(levels, levels[1:])), "levels must not get easier"
'''

_MANIFEST = '''"""
{title} build manifest. F7 runs these steps in order, F5 also runs the game on the C64U.

Each step is (tool, path relative to this file). Tools: sprites, tileset, koala, song,
levels, asm, and hyperload (after asm, with the .prg as its path) for a fast tape.
"""
TITLE = "{title}"
STEPS = [
{steps}]
'''

_TEMPLATES = {"sprites": _SPRITES, "tileset": _TILESET, "koala": _KOALA, "song": _SONG, "levels": _LEVELS}


def _top_level_names(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
    return names


def classify_source(source: str) -> str:
    """The kind of .py file, from the names it defines. The file is not run."""
    try:
        names = _top_level_names(source)
    except (SyntaxError, ValueError):
        return "python"
    if "STEPS" in names:
        return "build"
    if "GROUPS" in names:
        return "sprites"
    if "LEVELS" in names:
        return "levels"
    if "PATTERNS" in names and "ORDERS" in names:
        return "song"
    if "TILES" in names:
        return "tileset"
    if "compose" in names:
        return "koala"
    return "python"


def classify_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".asm", ".s"):
        return "asm"
    if ext in (".c", ".cpp", ".cc", ".cxx", ".h"):
        return "c"
    if ext != ".py":
        return ext.lstrip(".")
    if path.name.lower() == "build.py":
        return "build"
    try:
        return classify_source(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return "python"


def find_manifest(path: Path) -> Optional[Path]:
    """The build.py of the project this file belongs to, looking upward from it."""
    for folder in path.resolve().parents:
        candidate = folder / "build.py"
        if candidate.is_file() and classify_file(candidate) == "build":
            return candidate
        if folder.name == "game_dev" or (folder / ".git").exists():
            return None
    return None


def _title(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9 ]+", " ", name).strip().upper() or "UNTITLED"


def _manifest_text(title: str, steps: list[tuple[str, str]]) -> str:
    lines = "".join(f'    ("{tool}", "{rel}"),\n' for tool, rel in steps)
    return _MANIFEST.format(title=title, steps=lines)


def scan_steps(folder: Path) -> list[tuple[str, str]]:
    """Build steps for what is already in a folder: assets first, then the main program."""
    found: list[tuple[int, str, str]] = []
    mains: list[str] = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(folder).as_posix()
        kind = classify_file(path)
        if kind in BUILD_ORDER:
            found.append((BUILD_ORDER[kind], kind, rel))
        elif kind == "asm" and "BasicUpstart" in path.read_text(encoding="utf-8", errors="replace"):
            mains.append(rel)
    steps = [(kind, rel) for _, kind, rel in sorted(found)]
    # the file named after the folder is the game; otherwise the first one found
    named = [m for m in mains if Path(m).stem.lower() == folder.name.lower()]
    main = (named or mains or [None])[0]
    if main:
        steps.append(("asm", main))
    return steps


def create_manifest(folder: Path) -> Path:
    """Write a build.py for an existing folder from what is in it. An existing one is kept."""
    manifest = folder / "build.py"
    if not manifest.exists():
        manifest.write_text(_manifest_text(_title(folder.name), scan_steps(folder)), encoding="utf-8")
    return manifest


def create_game(name: str, games_dir: Path) -> Path:
    """Start a game: a folder with a build.py and a program that runs. Returns the build.py."""
    stem = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    if not stem:
        raise ValueError("the game needs a name with letters or digits in it")
    folder = games_dir / stem
    if folder.exists():
        raise FileExistsError(f"{folder} already exists")
    folder.mkdir(parents=True)
    (folder / f"{stem}.asm").write_text(NEW_ASM_TEMPLATE, encoding="utf-8")
    manifest = folder / "build.py"
    manifest.write_text(_manifest_text(_title(name), [("asm", f"{stem}.asm")]), encoding="utf-8")
    return manifest


def add_step(manifest: Path, tool: str, target: Path) -> bool:
    """Add a step to a build.py ahead of the assembly step. False if it was already there."""
    rel = Path(os.path.relpath(target, manifest.parent)).as_posix()
    text = manifest.read_text(encoding="utf-8")
    if f'"{rel}"' in text:
        return False
    line = f'    ("{tool}", "{rel}"),\n'
    asm = re.search(r'^[ \t]*\("asm",', text, re.MULTILINE)
    end = asm or re.search(r"^\]", text, re.MULTILINE)
    if end is None:
        raise ValueError(f"no STEPS list found in {manifest}")
    manifest.write_text(text[:end.start()] + line + text[end.start():], encoding="utf-8")
    return True


def _driver_import(folder: Path) -> str:
    driver = tools_root() / "tools" / "sid" / "sid_player.asm"
    try:
        return Path(os.path.relpath(driver, folder)).as_posix()
    except ValueError:      # another drive on Windows
        return driver.as_posix()


def create_definition(kind: str, path: Path) -> Path:
    """Write a starter file of this kind that builds as it stands, and any file it needs."""
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TEMPLATES[kind].format(title=_title(path.stem), stem=path.stem), encoding="utf-8")
    if kind == "song":
        music = path.parent / "music.asm"
        if not music.exists():
            music.write_text(_MUSIC_ASM.format(driver=_driver_import(path.parent)), encoding="utf-8")
    return path
