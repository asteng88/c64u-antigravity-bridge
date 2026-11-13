"""
Environment & Configuration Loader for C64U Bridge
Loads .env variables and discovers local toolchain binaries automatically.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, MutableMapping, Optional


def is_frozen() -> bool:
    """Return True when running from a PyInstaller frozen executable."""
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    """Return the application root directory (exe folder when frozen, else repo root)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_studio_settings_path() -> Path:
    """Return the persistent user settings JSON path for C64 Studio."""
    override = os.getenv("C64U_STUDIO_SETTINGS")
    if override and override.strip():
        return Path(override.strip()).expanduser()
    return Path.home() / ".config" / "c64u-bridge" / "studio_settings.json"


def load_studio_settings(settings_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load persisted C64 Studio preferences (e.g., AGY model and reasoning effort)."""
    target = settings_path or get_studio_settings_path()
    if not target.is_file():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_studio_settings(updates: Dict[str, Any], settings_path: Optional[Path] = None) -> Path:
    """Persist C64 Studio preferences to disk, merging with any existing settings."""
    target = settings_path or get_studio_settings_path()
    data = load_studio_settings(target)
    data.update(updates)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return target


def find_project_root(start: Optional[Path] = None) -> Path:
    """Find repository or application root by walking up towards pyproject.toml, .git, or tools/."""
    if is_frozen() and start is None:
        return Path(sys.executable).resolve().parent
    curr = (start or Path.cwd()).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return curr


def load_env(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Load environment variables from a .env file into os.environ if not already present.
    Returns the dictionary of loaded key-value pairs.
    """
    if env_path is None:
        roots = [get_app_root(), find_project_root(), Path.cwd()]
        for root in roots:
            candidate = root / ".env"
            if candidate.exists():
                env_path = candidate
                break

    loaded: Dict[str, str] = {}
    if not env_path or not env_path.exists():
        return loaded

    try:
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Remove enclosing quotes if present
                if len(val) >= 2 and (
                    (val.startswith('"') and val.endswith('"'))
                    or (val.startswith("'") and val.endswith("'"))
                ):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
                    loaded[key] = val
    except Exception:
        pass

    return loaded


def find_default_kickass_jar() -> Optional[Path]:
    """Locate KickAss.jar in tools directory or environment."""
    # 1. Environment variable (only if the file actually exists)
    env_jar = os.getenv("KICKASS_JAR")
    if env_jar and Path(env_jar).is_file():
        return Path(env_jar).resolve()

    # 2. Application / project tools directory
    roots = [get_app_root(), find_project_root(), find_project_root(Path(__file__)), Path.cwd()]
    for root in roots:
        candidate = root / "tools" / "kickassembler" / "KickAss.jar"
        if candidate.is_file():
            return candidate.resolve()
        alt_candidate = root / "tools" / "KickAss.jar"
        if alt_candidate.is_file():
            return alt_candidate.resolve()

    return None


def find_default_java_bin() -> Optional[str]:
    """Locate java executable from JAVA_BIN, local portable tools/java, or system PATH."""
    env_java = os.getenv("JAVA_BIN")
    if env_java and Path(env_java).is_file():
        return str(Path(env_java).resolve())

    exe_name = "java.exe" if os.name == "nt" else "java"
    for root in (get_app_root(), find_project_root(), Path.cwd()):
        for rel in (
            Path("tools") / "java" / "bin" / exe_name,
            Path("tools") / "jre" / "bin" / exe_name,
        ):
            cand = root / rel
            if cand.is_file():
                return str(cand.resolve())
        # Also handle nested jdk/jre folder inside tools/java/<subdir>/bin/java.exe
        java_dir = root / "tools" / "java"
        if java_dir.is_dir():
            for match in java_dir.glob(f"*/bin/{exe_name}"):
                if match.is_file():
                    return str(match.resolve())

    return shutil.which("java")


def find_default_oscar64_bin() -> Optional[str]:
    """Locate oscar64 executable from OSCAR64_BIN, local tools/oscar64, or system PATH."""
    env_osc = os.getenv("OSCAR64_BIN")
    if env_osc and Path(env_osc).is_file():
        return str(Path(env_osc).resolve())

    exe_name = "oscar64.exe" if os.name == "nt" else "oscar64"
    for root in (get_app_root(), find_project_root(), Path.cwd()):
        for rel in (
            Path("tools") / "oscar64" / "bin" / exe_name,
            Path("tools") / "oscar64" / exe_name,
        ):
            cand = root / rel
            if cand.is_file():
                return str(cand.resolve())
        osc_dir = root / "tools" / "oscar64"
        if osc_dir.is_dir():
            for match in osc_dir.rglob(exe_name):
                if match.is_file():
                    return str(match.resolve())

    return shutil.which("oscar64")


def prepend_local_tool_paths(
    target_env: Optional[MutableMapping[str, str]] = None,
    root: Optional[Path] = None,
) -> MutableMapping[str, str]:
    """Ensure local portable Java and Oscar64 bin directories are on PATH for child scripts."""
    env_map: MutableMapping[str, str] = os.environ if target_env is None else target_env
    extra_dirs: list[str] = []
    if root is not None:
        for rel in (Path("tools") / "java" / "bin", Path("tools") / "oscar64" / "bin"):
            cand_dir = root / rel
            if cand_dir.is_dir():
                extra_dirs.append(str(cand_dir.resolve()))
    for bin_path in (find_default_java_bin(), find_default_oscar64_bin()):
        if bin_path:
            p = Path(bin_path)
            if p.is_file():
                parent = str(p.parent.resolve())
                if parent not in extra_dirs:
                    extra_dirs.append(parent)
    if extra_dirs:
        cur = env_map.get("PATH", "")
        cur_parts = cur.split(os.pathsep) if cur else []
        to_add = [d for d in extra_dirs if d not in cur_parts]
        if to_add:
            env_map["PATH"] = os.pathsep.join(to_add + cur_parts)
    return env_map


# Automatically load .env and register local toolchains on module import
load_env()
prepend_local_tool_paths()
