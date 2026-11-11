#!/usr/bin/env python3
"""
Game build tool: rebuild a whole game from its build manifest.

Runs the asset tools in order (sprite bank, tileset/map, Koala screens, songs),
then assembles the main program with KickAssembler. Stops at the first step
that fails.

A manifest (usually build.py in the game folder) defines:
  STEPS   [(tool, path), ...] with paths relative to the manifest; tool is one of
          "sprites", "tileset", "koala", "song", "levels", "asm" or "hyperload"
          (hyperload goes after asm, with the .prg as its path)
optional:
  TITLE   name for the log (default: the folder name)

The asm step writes <stem>.prg next to its source (and VICE symbols with
--symbols). With --shot N it also runs the PRG headless for N frames in
tools/c64sim and saves a screenshot.

  python build_tool.py ../../game_dev/ironfront/build.py
  python build_tool.py ../../game_dev/ironfront/build.py --shot 300
"""
import argparse
import importlib.util
import os
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = {
    "sprites": ("sprites/sprite_tool.py", []),
    "tileset": ("charset/tileset_tool.py", []),
    "koala": ("bitmap/koala_tool.py", []),
    "song": ("sid/song_tool.py", ["--build"]),
    "levels": ("levels/level_tool.py", []),
    "hyperload": ("hyperload/hyperload_tool.py", []),
}


def load_manifest(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def kickass_jar():
    env = os.environ.get("KICKASS_JAR")
    if env and pathlib.Path(env).is_file():
        return pathlib.Path(env)
    jar = TOOLS / "kickassembler" / "KickAss.jar"
    if jar.is_file():
        return jar
    raise SystemExit("KickAssembler not found: set KICKASS_JAR or put KickAss.jar in tools/kickassembler/")


def run(cmd, cwd, tag):
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    for line in (res.stdout + res.stderr).splitlines():
        if line.strip() and not line.startswith("//"):
            print(f"  [{tag}] {line}")
    return res.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=pathlib.Path)
    ap.add_argument("--shot", type=int, help="after building, run the PRG headless this many frames and screenshot")
    ap.add_argument("--symbols", action="store_true", help="also write VICE symbols (.vs) for the PRG")
    args = ap.parse_args()
    manifest = args.manifest.resolve()
    here = manifest.parent
    m = load_manifest(manifest)
    title = getattr(m, "TITLE", here.name)
    print(f"building {title}: {len(m.STEPS)} steps")
    prg = None
    for tool, rel in m.STEPS:
        src = (here / rel).resolve()
        if not src.is_file():
            raise SystemExit(f"step {tool}: {rel} not found")
        if tool == "asm":
            prg = src.with_suffix(".prg")
            cmd = ["java", "-jar", str(kickass_jar()), src.name, "-o", prg.name]
            if args.symbols:
                cmd.append("-vicesymbols")
            ok = run(cmd, src.parent, "asm")
        elif tool in SCRIPTS:
            script, extra = SCRIPTS[tool]
            ok = run([sys.executable, str(TOOLS / script), str(src), *extra], src.parent, tool)
        else:
            raise SystemExit(f"unknown tool {tool!r} in {manifest.name}")
        if not ok:
            print(f"step {tool} ({rel}) failed")
            sys.exit(1)
    if prg is None:
        print("no asm step: nothing assembled")
        return
    print(f"wrote {prg.relative_to(here).as_posix()}: {prg.stat().st_size} bytes")
    if args.shot:
        ok = run([sys.executable, str(TOOLS / "c64sim" / "c64sim.py"), str(prg), "--frames", str(args.shot),
                  "--scale", "2"], prg.parent, "c64sim")
        shot = prg.with_name(f"{prg.stem}_f{args.shot - 1}.png")
        if ok and shot.is_file():
            print(f"wrote {shot.relative_to(here).as_posix()}")


if __name__ == "__main__":
    main()
