#!/usr/bin/env python3
"""
Game build tool: rebuild a whole game from its `build.py` manifest or custom `build.py` script.

Supports two `build.py` styles seamlessly:
1. Declarative `STEPS` manifest:
   Defines `STEPS = [(tool, path), ...]` (and optional `TITLE`) with paths relative to `build.py`.
   Supported step tools: `"sprites"`, `"tileset"`, `"koala"`, `"song"`, `"levels"`, `"asm"`, `"c"`,
   `"py"`, and `"hyperload"`.
2. Custom executable `build.py` script:
   Any Python build script without top-level `STEPS` (or with its own `if __name__ == "__main__":`
   entrypoint). Runs directly via `python build.py` in the game folder and automatically reports
   the compiled `.prg` / `.sid` / `.tap` / `.d64` artifacts back to C64 Studio.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

TOOLS = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = TOOLS.parent
SCRIPTS = {
    "sprites": ("sprites/sprite_tool.py", []),
    "tileset": ("charset/tileset_tool.py", []),
    "koala": ("bitmap/koala_tool.py", []),
    "song": ("sid/song_tool.py", ["--build"]),
    "levels": ("levels/level_tool.py", []),
    "hyperload": ("hyperload/hyperload_tool.py", []),
}

WROTE_RE = re.compile(r"^wrote (\S+?):?(?=\s|$)", re.MULTILINE)
IGNORED_DIRS = {"__pycache__", ".git", ".venv", ".pytest_cache", "node_modules"}


def _is_declarative_steps_manifest(path: pathlib.Path) -> bool:
    """Return True if `path` defines top-level `STEPS` and does not define a `__main__` script guard."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return False

    has_steps = False
    has_main_guard = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "STEPS" for t in node.targets):
                has_steps = True
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "STEPS":
                has_steps = True
        elif isinstance(node, ast.If):
            try:
                cond_src = ast.unparse(node.test)
                if "__name__" in cond_src and "__main__" in cond_src:
                    has_main_guard = True
            except Exception:
                pass
    return has_steps and not has_main_guard


def load_manifest(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_kickass_jar() -> Optional[pathlib.Path]:
    env = os.environ.get("KICKASS_JAR")
    if env and pathlib.Path(env).is_file():
        return pathlib.Path(env).resolve()
    jar = TOOLS / "kickassembler" / "KickAss.jar"
    if jar.is_file():
        return jar.resolve()
    alt = TOOLS / "KickAss.jar"
    if alt.is_file():
        return alt.resolve()
    return None


def kickass_jar() -> pathlib.Path:
    jar = find_kickass_jar()
    if jar is not None:
        return jar
    raise SystemExit("KickAssembler not found: set KICKASS_JAR or put KickAss.jar in tools/kickassembler/")


def _py_cmd(script: pathlib.Path, *extra_args: str) -> List[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--run-script", str(script), *extra_args]
    return [sys.executable, str(script), *extra_args]


def _java_cmd() -> str:
    env_java = os.environ.get("JAVA_BIN")
    if env_java and pathlib.Path(env_java).is_file():
        return env_java
    for cand in (TOOLS / "java" / "bin" / "java.exe", TOOLS / "java" / "bin" / "java"):
        if cand.is_file():
            return str(cand)
    return "java"


def _build_subprocess_env() -> Dict[str, str]:
    env = os.environ.copy()
    jar = find_kickass_jar()
    if jar is not None:
        env["KICKASS_JAR"] = str(jar)
    bin_dirs: List[str] = []
    for d in (TOOLS / "java" / "bin", TOOLS / "oscar64" / "bin"):
        if d.is_dir():
            bin_dirs.append(str(d))
    if bin_dirs:
        cur_path = env.get("PATH", "")
        env["PATH"] = os.pathsep.join(bin_dirs + ([cur_path] if cur_path else []))
    extra_py_paths = [str(REPO_ROOT / "src"), str(TOOLS)]
    existing = env.get("PYTHONPATH", "")
    joined = os.pathsep.join(extra_py_paths + ([existing] if existing else []))
    env["PYTHONPATH"] = joined
    return env


def run(cmd: List[str], cwd: pathlib.Path, tag: str, env: Optional[Dict[str, str]] = None) -> bool:
    res = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    for line in (res.stdout + res.stderr).splitlines():
        if line.strip() and not line.startswith("//"):
            print(f"  [{tag}] {line}")
    return res.returncode == 0


def _snapshot_artifacts(root: pathlib.Path) -> Dict[pathlib.Path, Tuple[int, int]]:
    snap: Dict[pathlib.Path, Tuple[int, int]] = {}
    for p in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in {".prg", ".sid", ".tap", ".d64"}:
            try:
                st = p.stat()
                snap[p.resolve()] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
    return snap


def _rank_prg_candidate(prg: pathlib.Path, root: pathlib.Path) -> Tuple[int, int]:
    """Higher tuple wins: prefer `<folder>.prg` in root, then root `.prg`, deprioritize sub-module music/loader PRGs."""
    try:
        rel_parts = prg.relative_to(root).parts
    except ValueError:
        rel_parts = (prg.name,)
    stem_l = prg.stem.lower()
    folder_l = root.name.lower()
    in_root = len(rel_parts) == 1
    is_aux = any(part.lower() in {"music", "loading", "loader", "sfx", "tests"} for part in rel_parts[:-1]) or stem_l in {
        "music",
        "loading_screen",
        "loader",
    }
    score = 0
    if not is_aux:
        score += 100
    if stem_l == folder_l:
        score += 50
    if in_root:
        score += 25
    try:
        mtime = prg.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (score, mtime)


def _select_best_artifact(
    before: Dict[pathlib.Path, Tuple[int, int]],
    after: Dict[pathlib.Path, Tuple[int, int]],
    root: pathlib.Path,
    suffix: str,
) -> Optional[pathlib.Path]:
    changed = [
        p
        for p, meta in after.items()
        if p.suffix.lower() == suffix and before.get(p) != meta
    ]
    pool = changed or [p for p in after if p.suffix.lower() == suffix]
    if not pool:
        return None
    if suffix == ".prg":
        return max(pool, key=lambda p: _rank_prg_candidate(p, root))
    return max(pool, key=lambda p: after[p][0])


def _rel_display(path: pathlib.Path, root: pathlib.Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _package_extra_media(
    prg: pathlib.Path,
    here: pathlib.Path,
    *,
    make_tap: bool,
    make_hypertap: bool,
    make_d64: bool,
    env: Dict[str, str],
) -> None:
    if not (make_tap or make_hypertap or make_d64):
        return
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from c64u_bridge.d64 import save_prg_to_d64
    from c64u_bridge.tap import save_prg_to_tap

    if make_tap:
        out_tap = prg.with_suffix(".tap")
        save_prg_to_tap(prg, tap_path=out_tap, tape_name=prg.stem)
        print(f"wrote {_rel_display(out_tap, here)}: {out_tap.stat().st_size} bytes")

    if make_hypertap:
        out_hyper = prg.with_suffix(".hyper.tap")
        raw = prg.read_bytes()
        extra_entry: List[str] = []
        if len(raw) >= 3 and not re.match(rb".{4}\x9e\s*(\d+)", raw[2:40], re.S):
            load_addr = raw[0] | (raw[1] << 8)
            if load_addr >= 0x0800 and load_addr != 0x0801:
                extra_entry = ["--entry", f"0x{load_addr:04X}"]
        ok = run(
            _py_cmd(
                TOOLS / "hyperload" / "hyperload_tool.py",
                str(prg),
                "-o",
                str(out_hyper),
                "--name",
                prg.stem,
                *extra_entry,
            ),
            prg.parent,
            "hyperload",
            env=env,
        )
        if not ok or not out_hyper.is_file():
            print(f"hyperload packaging failed for {prg.name}")
            sys.exit(1)
        print(f"wrote {_rel_display(out_hyper, here)}: {out_hyper.stat().st_size} bytes")

    if make_d64:
        out_d64 = prg.with_suffix(".d64")
        save_prg_to_d64(prg, d64_path=out_d64, disk_name=prg.stem.upper()[:16])
        print(f"wrote {_rel_display(out_d64, here)}: {out_d64.stat().st_size} bytes")


def _run_custom_build_script(
    manifest: pathlib.Path,
    shot_frames: Optional[int],
    env: Dict[str, str],
    *,
    make_tap: bool = False,
    make_hypertap: bool = False,
    make_d64: bool = False,
) -> None:
    here = manifest.parent
    print(f"running custom game build script: {manifest.name} (in {here})")
    before = _snapshot_artifacts(here)
    res = subprocess.run(_py_cmd(manifest), cwd=here, env=env, capture_output=True, text=True)
    combined = (res.stdout or "") + ("\n" + res.stderr if res.stderr else "")
    for line in combined.splitlines():
        if line.strip():
            print(f"  [build.py] {line}")
    if res.returncode != 0:
        print(f"custom build script {manifest.name} failed (exit code {res.returncode})")
        sys.exit(res.returncode)

    already_wrote = set(WROTE_RE.findall(res.stdout or ""))
    after = _snapshot_artifacts(here)
    prg = _select_best_artifact(before, after, here, ".prg")
    sid = _select_best_artifact(before, after, here, ".sid")
    tap = _select_best_artifact(before, after, here, ".tap")
    d64 = _select_best_artifact(before, after, here, ".d64")

    for art in (sid, tap, d64):
        if art is not None and before.get(art) != after.get(art):
            rel = _rel_display(art, here)
            if rel not in already_wrote and art.name not in already_wrote:
                print(f"wrote {rel}: {art.stat().st_size} bytes")

    if prg is not None:
        rel_prg = _rel_display(prg, here)
        if rel_prg not in already_wrote and prg.name not in already_wrote:
            print(f"wrote {rel_prg}: {prg.stat().st_size} bytes")
        _package_extra_media(
            prg,
            here,
            make_tap=make_tap,
            make_hypertap=make_hypertap,
            make_d64=make_d64,
            env=env,
        )
        if shot_frames:
            ok = run(
                _py_cmd(TOOLS / "c64sim" / "c64sim.py", str(prg), "--frames", str(shot_frames), "--scale", "2"),
                prg.parent,
                "c64sim",
                env=env,
            )
            shot = prg.with_name(f"{prg.stem}_f{shot_frames - 1}.png")
            if ok and shot.is_file():
                print(f"wrote {_rel_display(shot, here)}")
    elif sid is None:
        print("build.py finished (no .prg or .sid output detected)")


def _compile_c_or_py_step(tool: str, src: pathlib.Path, env: Dict[str, str]) -> Optional[pathlib.Path]:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from c64u_bridge.compiler import CrossCompiler
    from c64u_bridge.transpiler import PythonTo6502Transpiler

    compiler = CrossCompiler()
    out_prg = src.with_suffix(".prg")
    if tool == "py":
        tr = PythonTo6502Transpiler().transpile(src.read_text(encoding="utf-8"))
        if not tr.success:
            for err in tr.errors:
                print(f"  [py] {err}")
            return None
        asm_out = src.with_suffix(".asm")
        asm_out.write_text(tr.assembly, encoding="utf-8")
        comp = compiler.compile(asm_out, output_prg=out_prg, assembler="kickass")
    else:
        comp = compiler.compile(src, output_prg=out_prg, assembler="auto")

    for line in ((comp.stdout or "") + "\n" + (comp.stderr or "")).splitlines():
        if line.strip():
            print(f"  [{tool}] {line}")
    if not comp.success or not out_prg.is_file():
        if comp.error_message:
            print(f"  [{tool}] {comp.error_message}")
        return None
    return out_prg


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=pathlib.Path)
    ap.add_argument("--shot", type=int, help="after building, run the PRG headless this many frames and screenshot")
    ap.add_argument("--symbols", action="store_true", help="also write VICE symbols (.vs) for the PRG")
    ap.add_argument("--tap", action="store_true", help="also package a standard C64 cassette image (<stem>.tap)")
    ap.add_argument(
        "--hypertap",
        action="store_true",
        help="also package a HYPERLOAD fast-loader turbo cassette (<stem>.hyper.tap)",
    )
    ap.add_argument("--d64", action="store_true", help="also package a 35-track 1541 floppy disk image (<stem>.d64)")
    args = ap.parse_args()
    manifest = args.manifest.resolve()
    if not manifest.is_file():
        raise SystemExit(f"manifest not found: {manifest}")

    env = _build_subprocess_env()
    if not _is_declarative_steps_manifest(manifest):
        _run_custom_build_script(
            manifest,
            args.shot,
            env,
            make_tap=args.tap,
            make_hypertap=args.hypertap,
            make_d64=args.d64,
        )
        return

    here = manifest.parent
    m = load_manifest(manifest)
    title = getattr(m, "TITLE", here.name)
    print(f"building {title}: {len(m.STEPS)} steps")
    prg: Optional[pathlib.Path] = None
    for tool, rel in m.STEPS:
        src = (here / rel).resolve()
        if not src.is_file():
            raise SystemExit(f"step {tool}: {rel} not found")
        if tool == "asm":
            prg = src.with_suffix(".prg")
            cmd = [_java_cmd(), "-jar", str(kickass_jar()), src.name, "-o", prg.name]
            if args.symbols:
                cmd.append("-vicesymbols")
            ok = run(cmd, src.parent, "asm", env=env)
        elif tool in ("c", "py"):
            built = _compile_c_or_py_step(tool, src, env)
            ok = built is not None
            if built is not None:
                prg = built
        elif tool in SCRIPTS:
            script, extra = SCRIPTS[tool]
            ok = run(_py_cmd(TOOLS / script, str(src), *extra), src.parent, tool, env=env)
        else:
            raise SystemExit(f"unknown tool {tool!r} in {manifest.name}")
        if not ok:
            print(f"step {tool} ({rel}) failed")
            sys.exit(1)
    if prg is None:
        print("no asm/c/py step: nothing assembled")
        return
    print(f"wrote {_rel_display(prg, here)}: {prg.stat().st_size} bytes")
    _package_extra_media(
        prg,
        here,
        make_tap=args.tap,
        make_hypertap=args.hypertap,
        make_d64=args.d64,
        env=env,
    )
    if args.shot:
        ok = run(
            _py_cmd(TOOLS / "c64sim" / "c64sim.py", str(prg), "--frames", str(args.shot), "--scale", "2"),
            prg.parent,
            "c64sim",
            env=env,
        )
        shot = prg.with_name(f"{prg.stem}_f{args.shot - 1}.png")
        if ok and shot.is_file():
            print(f"wrote {_rel_display(shot, here)}")


if __name__ == "__main__":
    main()
