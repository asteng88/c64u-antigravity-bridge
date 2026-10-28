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

from .env import find_project_root


@dataclass(frozen=True)
class GameTool:
    key: str
    label: str                  # menu text
    script: str                 # path relative to the repository root
    suffixes: tuple[str, ...]   # target file types the tool accepts
    describe: str               # one line for logs and the help guide
    extra_args: tuple[str, ...] = field(default_factory=tuple)
    run_result: bool = False    # push the .prg it builds to the C64U afterwards


GAME_TOOLS: dict[str, GameTool] = {
    tool.key: tool
    for tool in (
        GameTool("sprites", "SPRITE BANK", "tools/sprites/sprite_tool.py", (".py",),
                 "Build a sprite bank file into KickAssembler data and a review page"),
        GameTool("tileset", "TILES + MAP", "tools/charset/tileset_tool.py", (".py",),
                 "Build a tileset file into a multicolor charset, tile/building tables, a map and a review page"),
        GameTool("koala", "KOALA SCREEN", "tools/bitmap/koala_tool.py", (".py",),
                 "Render a scene file into a Koala multicolor bitmap and a review page"),
        GameTool("song", "SONG → SID", "tools/sid/song_tool.py", (".py",),
                 "Compile a song file, assemble it with the SID driver, emulate it and export .sid",
                 ("--build",)),
        GameTool("build", "BUILD GAME", "tools/build/build_tool.py", (".py",),
                 "Rebuild a game from its build.py manifest (assets + KickAssembler) and run it on the C64U",
                 run_result=True),
        GameTool("c64sim", "C64 SCREENSHOT", "tools/c64sim/c64sim.py", (".prg",),
                 "Run a PRG headless (VIC-II, raster IRQs, sprites) for 300 frames and save a screenshot",
                 ("--frames", "300", "--scale", "2")),
        GameTool("sim", "6502 SID PROFILE", "tools/sim6502/sim6502.py", (".sid", ".prg"),
                 "Run a music PRG or SID in the 6502 emulator and report CPU time per frame"),
    )
}

WROTE = re.compile(r"^wrote (\S+?):?(?=\s|$)", re.MULTILINE)  # "wrote x.asm: 12 bytes" -> x.asm


def tools_root() -> Path:
    """Repository root that holds tools/ (package location first, then the working directory)."""
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
    return [sys.executable, str(tools_root() / tool.script), str(target), *tool.extra_args]


@dataclass
class ToolResult:
    ok: bool
    output: str
    produced: list[Path]

    def first(self, suffix: str) -> Optional[Path]:
        return next((p for p in self.produced if p.suffix.lower() == suffix), None)


def run_tool(key: str, target: Path, timeout: float = 600) -> ToolResult:
    """Run a tool on a target file and collect its output and the files it wrote."""
    try:
        res = subprocess.run(tool_command(key, target), cwd=tools_root(), capture_output=True, text=True,
                             timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ToolResult(False, str(exc), [])
    output = (res.stdout + res.stderr).strip()
    produced = [target.parent / name for name in WROTE.findall(res.stdout)]
    return ToolResult(res.returncode == 0, output, produced)
