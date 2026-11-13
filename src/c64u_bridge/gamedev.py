"""
Game development tool registry for the studio's GAME DEV menu.

Each tool is a standalone script under the repository's tools/ folder. The
studio runs it with the current Python in a subprocess, passing a target file
(a sprite bank, a Koala scene, a song, a PRG/SID...). Tools report the files
they produce on stdout as "wrote <name>" lines, which the studio picks up to
open review pages or remember a freshly built .sid.
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .env import (
    find_default_kickass_jar,
    find_project_root,
    get_app_root,
    is_frozen,
    prepend_local_tool_paths,
)


@dataclass(frozen=True)
class GameTool:
    key: str
    label: str                  # menu text
    script: str                 # path relative to the repository root
    suffixes: tuple[str, ...]   # target file types the tool accepts
    describe: str               # one line for logs and the help guide
    extra_args: tuple[str, ...] = field(default_factory=tuple)


GAME_TOOLS: dict[str, GameTool] = {
    tool.key: tool
    for tool in (
        GameTool("sprites", "SPRITE BANK", "tools/sprites/sprite_tool.py", (".py",),
                 "Build a sprite bank file into KickAssembler data and a review page"),
        GameTool("tileset", "TILES + MAP", "tools/charset/tileset_tool.py", (".py",),
                 "Build a tileset file into a multicolor charset, tile/building tables, a map and a review page"),
        GameTool("isotiles", "ISO TERRAIN", "tools/isotiles/iso_tool.py", (".py",),
                 "Build an isometric terrain file into a multicolor charset, character lookup tables, a staggered map and a review page"),
        GameTool("koala", "KOALA SCREEN", "tools/bitmap/koala_tool.py", (".py",),
                 "Render a scene file into a Koala multicolor bitmap and a review page"),
        GameTool("song", "SONG → SID", "tools/sid/song_tool.py", (".py",),
                 "Compile a song file, assemble it with the SID driver, emulate it and export .sid",
                 ("--build",)),
        GameTool("levels", "LEVEL TABLES", "tools/levels/level_tool.py", (".py",),
                 "Compile a level file into KickAssembler tables and a difficulty review page"),
        GameTool("build", "BUILD GAME", "tools/build/build_tool.py", (".py",),
                 "Rebuild a game from its build.py manifest (assets + KickAssembler)"),
        GameTool("hyperload", "HYPERLOAD TAPE", "tools/hyperload/hyperload_tool.py", (".prg",),
                 "Turn a PRG into a HYPERLOAD .tap: a fast loader with border stripes"),
        GameTool("c64sim", "C64 SCREENSHOT", "tools/c64sim/c64sim.py", (".prg",),
                 "Run a PRG headless (VIC-II, raster IRQs, sprites) for 300 frames and save a screenshot",
                 ("--frames", "300", "--scale", "2")),
        GameTool("sim", "6502 SID PROFILE", "tools/sim6502/sim6502.py", (".sid", ".prg"),
                 "Run a music PRG or SID in the 6502 emulator and report CPU time per frame"),
    )
}

WROTE = re.compile(r"^wrote (\S+?):?(?=\s|$)", re.MULTILINE)  # "wrote x.asm: 12 bytes" -> x.asm


def tools_root() -> Path:
    """Repository root that holds tools/ (frozen app root first, then package/cwd)."""
    if is_frozen():
        app_root = get_app_root()
        if (app_root / "tools").is_dir():
            return app_root
    for start in (Path(__file__).resolve().parent, Path.cwd()):
        root = find_project_root(start)
        if (root / "tools").is_dir():
            return root
    return find_project_root()


def default_target_dir() -> Path:
    root = tools_root()
    return root / "game_dev" if (root / "game_dev").is_dir() else root


def tool_command(key: str, target: Path) -> list[str]:
    tool = GAME_TOOLS[key]
    script_path = str(tools_root() / tool.script)
    if is_frozen():
        return [sys.executable, "--run-script", script_path, str(target), *tool.extra_args]
    return [sys.executable, script_path, str(target), *tool.extra_args]


@dataclass
class ToolResult:
    ok: bool
    output: str
    produced: list[Path]

    def first(self, suffix: str) -> Optional[Path]:
        return next((p for p in self.produced if p.suffix.lower() == suffix), None)


def run_tool(key: str, target: Path, timeout: float = 600, args: tuple[str, ...] = ()) -> ToolResult:
    """Run a tool on a target file and collect its output and the files it wrote."""
    import os

    root = tools_root()
    env = prepend_local_tool_paths(os.environ.copy(), root)
    src_dir = root / "src"
    if src_dir.is_dir():
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{existing_pp}" if existing_pp else str(src_dir)
    jar = find_default_kickass_jar()
    if jar is not None:
        env["KICKASS_JAR"] = str(jar)

    try:
        res = subprocess.run(
            [*tool_command(key, target), *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolResult(False, str(exc), [])
    output = (res.stdout + res.stderr).strip()
    produced: list[Path] = []
    for name in WROTE.findall(res.stdout):
        cand = Path(name)
        resolved = cand if cand.is_absolute() else (target.parent / name)
        produced.append(resolved)
    return ToolResult(res.returncode == 0, output, produced)
