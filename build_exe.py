#!/usr/bin/env python3
"""
Build standalone Windows executables for C64 Studio:
  - dist/C64-Studio/C64-Studio.exe       (one-folder IDE distribution)
  - dist/C64-Studio/C64-Studio-Setup.exe (one-file setup & toolchain downloader)
  - dist/C64-Studio/tools/               (game dev & build tools)
  - dist/C64-Studio/examples/            (sample C64 projects)
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DIST_ROOT = REPO_ROOT / "dist"
APP_DIST_DIR = DIST_ROOT / "C64-Studio"
WORK_ROOT = REPO_ROOT / "build" / "pyinstaller"
ASSETS_DIR = REPO_ROOT / "src" / "c64u_bridge" / "assets"
ICONS_DIR = REPO_ROOT / "icons"
STUDIO_ICON_PATH = ICONS_DIR / "c64_studio.ico" if (ICONS_DIR / "c64_studio.ico").is_file() else ASSETS_DIR / "app_icon.ico"
SETUP_ICON_PATH = ICONS_DIR / "c64_studio_setup.ico" if (ICONS_DIR / "c64_studio_setup.ico").is_file() else STUDIO_ICON_PATH

HIDDEN_IMPORTS = [
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "httpx",
    "pydantic",
    "runpy",
    "http.server",
    "socketserver",
    "webbrowser",
    "wave",
    "xml.etree.ElementTree",
    "urllib.request",
    "urllib.error",
    "zipfile",
]


def _copy_tree_filtered(src: Path, dst: Path) -> None:
    if not src.is_dir():
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache"),
    )


def _run(cmd: list[str]) -> None:
    print(f"> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)


def build_studio(py_exe: str) -> None:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    entry = WORK_ROOT / "c64_studio_entry.py"
    entry.write_text(
        "from c64u_bridge.c64_studio import main\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )

    sep = ";" if os.name == "nt" else ":"
    cmd = [
        py_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        "C64-Studio",
        "--contents-directory",
        "_internal",
        "--distpath",
        str(DIST_ROOT),
        "--workpath",
        str(WORK_ROOT / "studio_work"),
        "--specpath",
        str(WORK_ROOT),
        "--paths",
        str(REPO_ROOT / "src"),
        "--collect-submodules",
        "c64u_bridge",
        "--add-data",
        f"{ASSETS_DIR}{sep}c64u_bridge/assets",
    ]
    if STUDIO_ICON_PATH.is_file():
        cmd.extend(["--icon", str(STUDIO_ICON_PATH)])
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])
    cmd.append(str(entry))

    _run(cmd)


def build_setup(py_exe: str) -> None:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    cmd = [
        py_exe,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name",
        "C64-Studio-Setup",
        "--distpath",
        str(APP_DIST_DIR),
        "--workpath",
        str(WORK_ROOT / "setup_work"),
        "--specpath",
        str(WORK_ROOT),
    ]
    if SETUP_ICON_PATH.is_file():
        cmd.extend(["--icon", str(SETUP_ICON_PATH)])
    cmd.append(str(REPO_ROOT / "setup_bridge.py"))

    _run(cmd)


def copy_runtime_folders() -> None:
    print(f"> Copying tools/, examples/, and icons/ into {APP_DIST_DIR}...")
    _copy_tree_filtered(REPO_ROOT / "tools", APP_DIST_DIR / "tools")
    _copy_tree_filtered(REPO_ROOT / "examples", APP_DIST_DIR / "examples")
    _copy_tree_filtered(ICONS_DIR, APP_DIST_DIR / "icons")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build C64 Studio and Setup executables")
    ap.add_argument("--skip-studio", action="store_true", help="Skip building C64-Studio.exe")
    ap.add_argument("--skip-setup", action="store_true", help="Skip building C64-Studio-Setup.exe")
    args = ap.parse_args()

    py_exe = sys.executable
    if not args.skip_studio:
        build_studio(py_exe)
    if not args.skip_setup:
        build_setup(py_exe)
    copy_runtime_folders()

    print("\nBuild complete:")
    print(f"  IDE:   {APP_DIST_DIR / 'C64-Studio.exe'}")
    print(f"  Setup: {APP_DIST_DIR / 'C64-Studio-Setup.exe'}")


if __name__ == "__main__":
    main()
