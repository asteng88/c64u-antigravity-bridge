"""
Environment & Configuration Loader for C64U Bridge
Loads .env variables and discovers local toolchain binaries automatically.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def find_project_root(start: Optional[Path] = None) -> Path:
    """Find repository or project root by walking up towards pyproject.toml or .git."""
    curr = (start or Path.cwd()).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return curr


def load_env(env_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Load environment variables from a .env file into os.environ if not already present.
    Returns the dictionary of loaded key-value pairs.
    """
    if env_path is None:
        root = find_project_root()
        candidate = root / ".env"
        if candidate.exists():
            env_path = candidate
        elif Path(".env").exists():
            env_path = Path(".env").resolve()

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
    # 1. Environment variable
    env_jar = os.getenv("KICKASS_JAR")
    if env_jar and Path(env_jar).exists():
        return Path(env_jar).resolve()

    # 2. Project tools directory
    root = find_project_root()
    candidate = root / "tools" / "kickassembler" / "KickAss.jar"
    if candidate.exists():
        return candidate.resolve()

    # 3. Direct tools directory
    alt_candidate = root / "tools" / "KickAss.jar"
    if alt_candidate.exists():
        return alt_candidate.resolve()

    return None


# Automatically load .env on module import
load_env()
