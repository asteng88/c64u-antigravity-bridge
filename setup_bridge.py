#!/usr/bin/env python3
"""
C64U Antigravity Bridge - Interactive Setup & Configuration Wizard
Guides users through configuring the C64 Ultimate bridge, setting up the CLI,
installing KickAssembler, and connecting to Google Antigravity.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# Terminal ANSI styling
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    DIM = "\033[2m"

    @classmethod
    def enable_windows_ansi(cls):
        """Enable ANSI VT100 sequences on Windows console."""
        if platform.system() == "Windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            except Exception:
                pass


Style.enable_windows_ansi()


def print_banner():
    print(f"""
{Style.CYAN}{Style.BOLD}========================================================================
             C64U ANTIGRAVITY BRIDGE - SETUP WIZARD             
========================================================================{Style.RESET}
  {Style.MAGENTA}Bridge Google Antigravity & Commodore 64 Ultimate (C64U){Style.RESET}
  * Cross-compile 6502 assembly with KickAssembler
  * Sub-second DMA deployment via C64U REST API
  * Real-time hardware telemetry and memory inspection
{Style.CYAN}------------------------------------------------------------------------{Style.RESET}
""")


def prompt_user(prompt_text: str, default: Optional[str] = None, allow_empty: bool = True) -> str:
    """Prompt user for text input with a default option."""
    if default:
        formatted_prompt = f"{Style.BOLD}{prompt_text}{Style.RESET} [{Style.GREEN}{default}{Style.RESET}]: "
    else:
        formatted_prompt = f"{Style.BOLD}{prompt_text}{Style.RESET}: "

    try:
        val = input(formatted_prompt).strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Style.YELLOW}Setup cancelled by user.{Style.RESET}")
        sys.exit(0)

    if not val:
        if default is not None:
            return default
        if not allow_empty:
            return prompt_user(prompt_text, default, allow_empty)
        return ""
    return val


def prompt_yes_no(prompt_text: str, default_yes: bool = True) -> bool:
    """Prompt user for a yes/no confirmation."""
    choices = "[Y/n]" if default_yes else "[y/N]"
    formatted_prompt = f"{Style.BOLD}{prompt_text}{Style.RESET} {choices}: "

    try:
        val = input(formatted_prompt).strip().lower()
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Style.YELLOW}Setup cancelled by user.{Style.RESET}")
        sys.exit(0)

    if not val:
        return default_yes
    return val in ["y", "yes", "true", "1"]


def find_uv_executable() -> Optional[str]:
    """Find uv on system path or user home local bin."""
    candidate = shutil.which("uv")
    if candidate:
        return candidate

    home = Path.home()
    for local_path in [
        home / ".local" / "bin" / "uv.exe",
        home / ".local" / "bin" / "uv",
        home / ".cargo" / "bin" / "uv.exe",
        home / ".cargo" / "bin" / "uv",
    ]:
        if local_path.exists():
            return str(local_path)
    return None


def read_existing_env(env_path: Path) -> Dict[str, str]:
    """Parse existing .env if it exists."""
    data = {}
    if not env_path.exists():
        return data
    try:
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k:
                    data[k] = v
    except Exception:
        pass
    return data


KICKASS_URL = "http://theweb.dk/KickAssembler/KickAssembler.zip"
ADOPTIUM_JRE17_WIN64_URL = (
    "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jre/hotspot/normal/eclipse"
)
OSCAR64_RELEASES_API = "https://api.github.com/repos/drmortalwombat/oscar64/releases/latest"
C64_STUDIO_GITHUB_REPO = os.getenv("C64_STUDIO_GITHUB_REPO", "asteng88/c64u-antigravity-bridge")
VERSION_STAMP_FILE = ".c64_studio_version"
APP_VERSION = "0.1.0"


def _parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a tag like 'v0.2.1' or '0.2.1' into a comparable integer tuple."""
    import re

    cleaned = version_str.strip().lstrip("vV")
    nums = [int(n) for n in re.findall(r"\d+", cleaned)]
    return tuple(nums)


def is_newer_version(latest: str, current: str) -> bool:
    """Return True if `latest` is strictly greater than `current`."""
    l_parts = _parse_version(latest)
    c_parts = _parse_version(current)
    if l_parts and c_parts:
        width = max(len(l_parts), len(c_parts))
        l_padded = l_parts + (0,) * (width - len(l_parts))
        c_padded = c_parts + (0,) * (width - len(c_parts))
        return l_padded > c_padded
    return bool(latest.strip() and latest.strip() != current.strip())


def get_installed_version(project_root: Path) -> str:
    """Return the installed version from .c64_studio_version, or built-in APP_VERSION."""
    stamp_file = project_root / VERSION_STAMP_FILE
    if stamp_file.is_file():
        recorded = stamp_file.read_text(encoding="utf-8").strip()
        if recorded:
            return recorded
    pyproject = project_root / "pyproject.toml"
    if pyproject.is_file():
        import re

        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.M)
        if m:
            return m.group(1)
    return APP_VERSION


def is_frozen() -> bool:
    """Return True when running from a PyInstaller frozen executable."""
    return bool(getattr(sys, "frozen", False))


def resolve_project_root() -> Path:
    """Return the workspace/app root (exe directory when frozen, else script directory)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _extract_zip_flattened(content: bytes, target_dir: Path) -> None:
    """Extract a ZIP archive into target_dir, flattening a single top-level folder if present."""
    import tempfile

    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(tmp_path)
        entries = list(tmp_path.iterdir())
        src_root = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp_path
        for item in src_root.iterdir():
            dest = target_dir / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))


def download_and_extract_kickass(target_dir: Path) -> Optional[Path]:
    """Download KickAssembler.zip from the official site and extract KickAss.jar."""
    target_dir.mkdir(parents=True, exist_ok=True)
    jar_path = target_dir / "KickAss.jar"
    if jar_path.exists():
        print(f"  {Style.GREEN}* KickAss.jar already exists at: {jar_path}{Style.RESET}")
        return jar_path

    url = KICKASS_URL
    print(f"  {Style.CYAN}-> Downloading Kick Assembler from {url}...{Style.RESET}")

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "C64U-Antigravity-Bridge-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            content = resp.read()

        print(f"  {Style.CYAN}-> Extracting archive ({len(content) // 1024} KB)...{Style.RESET}")
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            zf.extractall(target_dir)

        # Look for KickAss.jar
        found = list(target_dir.rglob("KickAss.jar"))
        if found:
            actual_jar = found[0]
            if actual_jar != jar_path:
                shutil.copy2(actual_jar, jar_path)
            print(f"  {Style.GREEN}[OK] KickAssembler successfully installed to: {jar_path}{Style.RESET}")
            return jar_path
        else:
            print(f"  {Style.YELLOW}! Extracted files, but KickAss.jar not found in archive.{Style.RESET}")
            return None
    except Exception as e:
        print(f"  {Style.RED}! Failed to download Kick Assembler: {e}{Style.RESET}")
        print(f"    You can download it manually from: {url}")
        print(f"    and place KickAss.jar inside: {target_dir}")
        return None


def find_local_java_bin(project_root: Path) -> Optional[Path]:
    """Return local portable java binary path if installed under tools/java."""
    exe_name = "java.exe" if platform.system() == "Windows" else "java"
    cand = project_root / "tools" / "java" / "bin" / exe_name
    if cand.is_file():
        return cand.resolve()
    return None


def download_and_extract_portable_java(target_dir: Path) -> Optional[Path]:
    """Download and extract portable Eclipse Temurin JRE 17 into target_dir."""
    exe_name = "java.exe" if platform.system() == "Windows" else "java"
    existing = target_dir / "bin" / exe_name
    if existing.is_file():
        print(f"  {Style.GREEN}* Portable Java JRE already exists at: {existing}{Style.RESET}")
        return existing.resolve()

    if platform.system() != "Windows":
        print(f"  {Style.YELLOW}! Automatic portable JRE download is currently configured for Windows x64.{Style.RESET}")
        return None

    print(f"  {Style.CYAN}-> Downloading portable Eclipse Temurin JRE 17 from Adoptium...{Style.RESET}")
    try:
        req = urllib.request.Request(
            ADOPTIUM_JRE17_WIN64_URL,
            headers={"User-Agent": "C64-Studio-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            content = resp.read()
        print(f"  {Style.CYAN}-> Extracting Java JRE ({len(content) // (1024 * 1024)} MB)...{Style.RESET}")
        _extract_zip_flattened(content, target_dir)
        if existing.is_file():
            print(f"  {Style.GREEN}[OK] Portable Java JRE installed to: {existing}{Style.RESET}")
            return existing.resolve()
        found = list(target_dir.rglob(exe_name))
        if found:
            print(f"  {Style.GREEN}[OK] Portable Java JRE installed to: {found[0]}{Style.RESET}")
            return found[0].resolve()
        print(f"  {Style.YELLOW}! Extracted JRE archive, but {exe_name} was not found.{Style.RESET}")
        return None
    except Exception as e:
        print(f"  {Style.RED}! Failed to download portable Java JRE: {e}{Style.RESET}")
        print("    You can install Java 17 manually from https://adoptium.net/")
        return None


def find_local_oscar64_bin(project_root: Path) -> Optional[Path]:
    """Return local oscar64 binary path if installed under tools/oscar64."""
    exe_name = "oscar64.exe" if platform.system() == "Windows" else "oscar64"
    oscar_dir = project_root / "tools" / "oscar64"
    for cand in (oscar_dir / "bin" / exe_name, oscar_dir / exe_name):
        if cand.is_file():
            return cand.resolve()
    if oscar_dir.is_dir():
        found = list(oscar_dir.rglob(exe_name))
        if found:
            return found[0].resolve()
    return None


def download_and_extract_oscar64(target_dir: Path) -> Optional[Path]:
    """Download the latest Oscar64 Windows release from GitHub and extract to target_dir."""
    exe_name = "oscar64.exe" if platform.system() == "Windows" else "oscar64"
    for cand in (target_dir / "bin" / exe_name, target_dir / exe_name):
        if cand.is_file():
            print(f"  {Style.GREEN}* Oscar64 already exists at: {cand}{Style.RESET}")
            return cand.resolve()

    if platform.system() != "Windows":
        print(f"  {Style.YELLOW}! Automatic Oscar64 binary download is currently configured for Windows.{Style.RESET}")
        return None

    print(f"  {Style.CYAN}-> Checking latest Oscar64 release on GitHub...{Style.RESET}")
    try:
        req = urllib.request.Request(
            OSCAR64_RELEASES_API,
            headers={
                "User-Agent": "C64-Studio-Setup/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            release = json.loads(resp.read().decode("utf-8"))

        assets = release.get("assets", [])
        chosen = None
        for tag in ("win64", "win"):
            for asset in assets:
                name = str(asset.get("name", "")).lower()
                if name.endswith(".zip") and tag in name:
                    chosen = asset
                    break
            if chosen:
                break
        if chosen is None:
            for asset in assets:
                name = str(asset.get("name", "")).lower()
                if name == "oscar64.zip" or (
                    name.endswith(".zip")
                    and not any(bad in name for bad in ("linux", "mac", "darwin", "src", "source"))
                ):
                    chosen = asset
                    break

        if not chosen or not chosen.get("browser_download_url"):
            print(f"  {Style.YELLOW}! No Windows ZIP asset found in latest Oscar64 release.{Style.RESET}")
            return None

        dl_url = chosen["browser_download_url"]
        print(f"  {Style.CYAN}-> Downloading {chosen['name']}...{Style.RESET}")
        dl_req = urllib.request.Request(dl_url, headers={"User-Agent": "C64-Studio-Setup/1.0"})
        with urllib.request.urlopen(dl_req, timeout=180) as resp:
            content = resp.read()

        print(f"  {Style.CYAN}-> Extracting Oscar64 ({len(content) // 1024} KB)...{Style.RESET}")
        _extract_zip_flattened(content, target_dir)

        for cand in (target_dir / "bin" / exe_name, target_dir / exe_name):
            if cand.is_file():
                print(f"  {Style.GREEN}[OK] Oscar64 installed to: {cand}{Style.RESET}")
                return cand.resolve()
        found = list(target_dir.rglob(exe_name))
        if found:
            print(f"  {Style.GREEN}[OK] Oscar64 installed to: {found[0]}{Style.RESET}")
            return found[0].resolve()
        print(f"  {Style.YELLOW}! Extracted Oscar64 archive, but {exe_name} was not found.{Style.RESET}")
        return None
    except Exception as e:
        print(f"  {Style.RED}! Failed to download Oscar64: {e}{Style.RESET}")
        print("    You can download it manually from https://github.com/drmortalwombat/oscar64/releases")
        return None


def check_java_runtime(project_root: Optional[Path] = None) -> Tuple[bool, str, Optional[Path]]:
    """Check if Java runtime is available (local portable JRE first, then PATH)."""
    java_path: Optional[Path] = None
    if project_root is not None:
        java_path = find_local_java_bin(project_root)
    if java_path is None:
        env_java = os.environ.get("JAVA_BIN")
        if env_java and Path(env_java).is_file():
            java_path = Path(env_java).resolve()
    if java_path is None:
        which_java = shutil.which("java")
        if which_java:
            java_path = Path(which_java).resolve()

    if java_path is None:
        return False, "Java executable not found in tools/java or PATH", None

    try:
        res = subprocess.run(
            [str(java_path), "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ver_output = res.stderr or res.stdout
        first_line = ver_output.splitlines()[0] if ver_output else "Java detected"
        return True, first_line.strip(), java_path
    except Exception as e:
        return False, str(e), None


def offer_java_installation(interactive: bool):
    """Offer to install Java via winget on Windows if Java is missing."""
    print(f"\n{Style.YELLOW}------------------------------------------------------------------------{Style.RESET}")
    print(f"{Style.YELLOW}! KickAssembler requires Java (JRE 8 or later) to execute.{Style.RESET}")
    
    if platform.system() == "Windows":
        winget = shutil.which("winget")
        if winget and interactive:
            install_now = prompt_yes_no("Would you like to install Eclipse Temurin JRE 17 via winget now?", default_yes=True)
            if install_now:
                print(f"  {Style.CYAN}-> Running: winget install EclipseAdoptium.Temurin.17.JRE...{Style.RESET}")
                try:
                    subprocess.run(
                        [winget, "install", "EclipseAdoptium.Temurin.17.JRE", "-e", "--accept-package-agreements", "--accept-source-agreements"],
                        check=False,
                    )
                    print(f"  {Style.GREEN}* Winget installation finished. Note: you may need to restart your terminal for Java to appear on PATH.{Style.RESET}")
                    return
                except Exception as e:
                    print(f"  {Style.RED}! Winget installation encountered an issue: {e}{Style.RESET}")
    print(f"  Please download and install Java manually if not installed: https://adoptium.net/")
    print(f"{Style.YELLOW}------------------------------------------------------------------------{Style.RESET}\n")


def setup_cli_and_virtualenv(project_root: Path) -> bool:
    """Set up the Python virtual environment and install the c64u-bridge package."""
    print(f"\n{Style.CYAN}------------------------------------------------------------------------{Style.RESET}")
    print(f"{Style.BOLD}Setting up C64U Bridge CLI & Python Environment{Style.RESET}")
    print(f"{Style.CYAN}------------------------------------------------------------------------{Style.RESET}")

    uv_path = find_uv_executable()
    venv_dir = project_root / ".venv"

    if uv_path:
        print(f"  * Using uv package manager: {uv_path}")
        if not venv_dir.exists():
            print(f"  -> Creating virtual environment with uv...")
            subprocess.run([uv_path, "venv", str(venv_dir)], check=True, cwd=project_root)
        print(f"  -> Installing c64u-bridge in editable mode...")
        res = subprocess.run([uv_path, "pip", "install", "-e", "."], cwd=project_root)
        if res.returncode != 0:
            print(f"  {Style.RED}! Failed to install package with uv.{Style.RESET}")
            return False
        # Also install into uv tool environment for global CLI PATH availability
        try:
            print(f"  -> Installing c64u-bridge as global tool into PATH...")
            subprocess.run([uv_path, "tool", "install", "--editable", "."], cwd=project_root, capture_output=True)
        except Exception:
            pass
    else:
        print(f"  * uv not found, falling back to standard python...")
        if not venv_dir.exists():
            print(f"  -> Creating virtual environment...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, cwd=project_root)

        pip_exe = venv_dir / "Scripts" / "pip.exe" if platform.system() == "Windows" else venv_dir / "bin" / "pip"
        print(f"  -> Installing c64u-bridge in editable mode with pip...")
        res = subprocess.run([str(pip_exe), "install", "-e", "."], cwd=project_root)
        if res.returncode != 0:
            print(f"  {Style.RED}! Failed to install package with pip.{Style.RESET}")
            return False

    # Create root launcher wrappers for easy CLI access
    create_cli_launchers(project_root)
    print(f"  {Style.GREEN}[OK] CLI installed successfully!{Style.RESET}")
    return True


def create_cli_launchers(project_root: Path):
    """Generate root directory launcher scripts (c64u-bridge.ps1, c64u-bridge.cmd)."""
    # Windows CMD
    cmd_launcher = project_root / "c64u-bridge.cmd"
    cmd_launcher.write_text(
        '@echo off\r\n"%~dp0.venv\\Scripts\\c64u-bridge.exe" %*\r\n',
        encoding="utf-8",
    )

    # Windows PowerShell
    ps_launcher = project_root / "c64u-bridge.ps1"
    ps_launcher.write_text(
        '$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path\r\n'
        '& "$PSScriptRoot\\.venv\\Scripts\\c64u-bridge.exe" @args\r\n',
        encoding="utf-8",
    )

    # Unix / Git Bash shell script
    sh_launcher = project_root / "c64u-bridge"
    sh_content = '#!/usr/bin/env bash\nDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\nexec "$DIR/.venv/bin/c64u-bridge" "$@"\n'
    sh_launcher.write_text(sh_content, encoding="utf-8")
    try:
        sh_launcher.chmod(0o755)
    except Exception:
        pass


def test_c64u_connection(host: str, port: int, password: Optional[str] = None) -> bool:
    """Test HTTP connectivity to the C64U REST API."""
    print(f"\n{Style.CYAN}-> Testing connection to C64U at http://{host}:{port}...{Style.RESET}")
    url = f"http://host:{port}/v1/info".replace("host", host)
    headers = {"User-Agent": "C64U-Bridge-Setup/1.0"}
    if password:
        headers["X-Password"] = password

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                raw = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(raw)
                print(f"  {Style.GREEN}[SUCCESS] Connected to Commodore 64 Ultimate!{Style.RESET}")
                for k, v in data.items():
                    print(f"    * {k}: {v}")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            print(f"  {Style.YELLOW}! Authentication required. Please check your C64U_PASSWORD.{Style.RESET}")
            return False
        # Try fallback /v1/about endpoint
        try:
            fallback_url = f"http://{host}:{port}/v1/about"
            with urllib.request.urlopen(urllib.request.Request(fallback_url, headers=headers), timeout=5) as resp:
                print(f"  {Style.GREEN}[SUCCESS] Connected to C64U (/v1/about)!{Style.RESET}")
                return True
        except Exception:
            pass
    except Exception as e:
        print(f"  {Style.YELLOW}! Could not connect to C64U ({e}).{Style.RESET}")
        print(f"    Troubleshooting checklist:")
        print(f"    1. Verify C64U is powered ON and Ethernet/Wi-Fi is connected.")
        print(f"    2. On C64U, press 'Commodore + RESTORE' -> 'F1' -> 'Network Settings' to confirm IP.")
        print(f"    3. Confirm 'Web Remote Control' service is enabled in settings.")

    return False


def save_configuration(
    project_root: Path,
    host: str,
    port: int,
    password: Optional[str],
    kickass_jar: Optional[Path],
    java_bin: Optional[Path] = None,
    oscar64_bin: Optional[Path] = None,
):
    """Write .env file and (when in repo mode) update antigravity/antigravity.json."""
    env_file = project_root / ".env"
    lines = [
        "# ====================================================================",
        "# C64U Antigravity Bridge Configuration",
        "# ====================================================================",
        f"C64U_HOST={host}",
        f"C64U_PORT={port}",
    ]
    if password:
        lines.append(f"C64U_PASSWORD={password}")
    else:
        lines.append("# C64U_PASSWORD=")

    if kickass_jar and kickass_jar.exists():
        lines.append(f"KICKASS_JAR={kickass_jar.resolve()}")
    if java_bin and java_bin.exists():
        lines.append(f"JAVA_BIN={java_bin.resolve()}")
    if oscar64_bin and oscar64_bin.exists():
        lines.append(f"OSCAR64_BIN={oscar64_bin.resolve()}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {Style.GREEN}* Saved environment file: {env_file}{Style.RESET}")

    if is_frozen() and not (project_root / "pyproject.toml").is_file():
        return

    # Update antigravity/antigravity.json
    antigravity_dir = project_root / "antigravity"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    mcp_config_path = antigravity_dir / "antigravity.json"

    kickass_str = str(kickass_jar.resolve()) if kickass_jar and kickass_jar.exists() else ""
    mcp_data = {
        "mcpServers": {
            "c64u-bridge": {
                "command": "uv",
                "args": ["run", "--no-sync", "--directory", str(project_root.resolve()), "c64u-mcp"],
                "env": {
                    "C64U_HOST": host,
                    "C64U_PORT": str(port),
                    "KICKASS_JAR": kickass_str,
                },
            }
        }
    }
    if password:
        mcp_data["mcpServers"]["c64u-bridge"]["env"]["C64U_PASSWORD"] = password

    mcp_config_path.write_text(json.dumps(mcp_data, indent=2) + "\n", encoding="utf-8")
    print(f"  {Style.GREEN}* Updated Antigravity MCP config: {mcp_config_path}{Style.RESET}")

    # Also sync to global ~/.gemini/config/mcp_config.json and ~/.gemini/antigravity-ide/mcp_config.json
    home = Path.home()
    for global_mcp_path in [
        home / ".gemini" / "config" / "mcp_config.json",
        home / ".gemini" / "antigravity-ide" / "mcp_config.json",
    ]:
        try:
            if global_mcp_path.parent.exists():
                existing = {}
                if global_mcp_path.exists() and global_mcp_path.stat().st_size > 0:
                    try:
                        existing = json.loads(global_mcp_path.read_text(encoding="utf-8"))
                    except Exception:
                        existing = {}
                if "mcpServers" not in existing:
                    existing["mcpServers"] = {}
                existing["mcpServers"]["c64u-bridge"] = mcp_data["mcpServers"]["c64u-bridge"]
                global_mcp_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
                print(f"  {Style.GREEN}* Updated Antigravity environment config: {global_mcp_path}{Style.RESET}")
        except Exception:
            pass

    # Install rules to .agents/rules/c64-bridge.md if antigravity/rules.md exists
    rules_src = antigravity_dir / "rules.md"
    if rules_src.exists():
        workspace_rules_dir = project_root / ".agents" / "rules"
        workspace_rules_dir.mkdir(parents=True, exist_ok=True)
        rules_dest = workspace_rules_dir / "c64-bridge.md"
        shutil.copy2(rules_src, rules_dest)
        print(f"  {Style.GREEN}* Installed agent rules into workspace: {rules_dest}{Style.RESET}")


def fetch_latest_c64_studio_release(repo: str = C64_STUDIO_GITHUB_REPO) -> Optional[Dict[str, Any]]:
    """Fetch the latest GitHub release metadata for C64 Studio."""
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    print(f"  {Style.CYAN}-> Checking GitHub ({repo}) for latest C64 Studio release...{Style.RESET}")
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "C64-Studio-Setup/1.0",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  {Style.YELLOW}! No published GitHub releases found yet for {repo}.{Style.RESET}")
            return None
        print(f"  {Style.YELLOW}! GitHub release check failed (HTTP {e.code}): {e.reason}{Style.RESET}")
        return None
    except Exception as e:
        print(f"  {Style.YELLOW}! Could not check GitHub for updates: {e}{Style.RESET}")
        return None


def _select_release_assets(assets: list[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Identify C64-Studio bundle ZIP, C64-Studio.exe, and C64-Studio-Setup.exe assets."""
    studio_zip: Optional[Dict[str, Any]] = None
    studio_exe: Optional[Dict[str, Any]] = None
    setup_exe: Optional[Dict[str, Any]] = None

    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if not asset.get("browser_download_url"):
            continue
        if name.endswith(".zip") and ("c64-studio" in name or "c64_studio" in name or "studio" in name):
            if studio_zip is None or "win" in name:
                studio_zip = asset
        elif name.endswith(".exe") and "setup" in name and ("c64" in name or "studio" in name):
            setup_exe = asset
        elif name in ("c64-studio.exe", "c64_studio.exe") or (
            name.endswith(".exe") and "studio" in name and "setup" not in name
        ):
            studio_exe = asset

    return {"studio_zip": studio_zip, "studio_exe": studio_exe, "setup_exe": setup_exe}


def _is_windows_process_running(image_name: str) -> bool:
    """Return True if a Windows process with the given image name is currently running."""
    if platform.system() != "Windows":
        return False
    try:
        res = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {image_name}", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return image_name.lower() in (res.stdout or "").lower()
    except Exception:
        return False


def _download_bytes(url: str, label: str) -> bytes:
    print(f"  {Style.CYAN}-> Downloading {label}...{Style.RESET}")
    req = urllib.request.Request(url, headers={"User-Agent": "C64-Studio-Setup/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def stage_c64_studio_update(project_root: Path, release: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Download latest release artifacts into a staging directory for post-exit overwrite."""
    tag = str(release.get("tag_name") or release.get("name") or "latest")
    selected = _select_release_assets(release.get("assets", []))
    studio_zip = selected["studio_zip"]
    studio_exe = selected["studio_exe"]
    setup_exe = selected["setup_exe"]

    if not any((studio_zip, studio_exe, setup_exe)):
        print(f"  {Style.YELLOW}! Release {tag} has no C64-Studio Windows .zip or .exe assets.{Style.RESET}")
        return None

    staging_dir = project_root / ".update_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir, ignore_errors=True)
    staging_dir.mkdir(parents=True, exist_ok=True)

    staged_studio_dir: Optional[Path] = None
    staged_studio_exe: Optional[Path] = None
    staged_setup_exe: Optional[Path] = None

    try:
        if studio_zip is not None:
            content = _download_bytes(studio_zip["browser_download_url"], studio_zip["name"])
            staged_studio_dir = staging_dir / "studio"
            _extract_zip_flattened(content, staged_studio_dir)
            # Never overwrite user's .env from a release archive
            for env_cand in (staged_studio_dir / ".env",):
                if env_cand.exists():
                    env_cand.unlink()
            # If the ZIP already contains C64-Studio-Setup.exe, stage it separately for self-replace
            zipped_setup = staged_studio_dir / "C64-Studio-Setup.exe"
            if zipped_setup.is_file():
                staged_setup_exe = staging_dir / "C64-Studio-Setup.exe"
                shutil.move(str(zipped_setup), str(staged_setup_exe))

        if studio_exe is not None:
            content = _download_bytes(studio_exe["browser_download_url"], studio_exe["name"])
            staged_studio_exe = staging_dir / "C64-Studio.exe"
            staged_studio_exe.write_bytes(content)

        if setup_exe is not None:
            content = _download_bytes(setup_exe["browser_download_url"], setup_exe["name"])
            staged_setup_exe = staging_dir / "C64-Studio-Setup.exe"
            staged_setup_exe.write_bytes(content)

        print(f"  {Style.GREEN}[OK] Release {tag} staged for installation.{Style.RESET}")
        return {
            "tag": tag,
            "staging_dir": staging_dir,
            "studio_dir": staged_studio_dir,
            "studio_exe": staged_studio_exe,
            "setup_exe": staged_setup_exe,
        }
    except Exception as e:
        print(f"  {Style.RED}! Failed to download release {tag}: {e}{Style.RESET}")
        shutil.rmtree(staging_dir, ignore_errors=True)
        return None


def build_windows_updater_script(
    project_root: Path,
    staged: Dict[str, Any],
    wait_pid: int,
    temp_dir: Optional[Path] = None,
) -> Path:
    """Generate a temporary .bat script that waits for setup & IDE to exit, then overwrites them."""
    import tempfile

    out_dir = temp_dir or Path(tempfile.gettempdir())
    bat_path = out_dir / f"c64_studio_apply_update_{wait_pid}.bat"
    root_str = str(project_root.resolve())
    staging_str = str(Path(staged["staging_dir"]).resolve())
    tag = str(staged.get("tag") or "latest")

    lines = [
        "@echo off",
        "setlocal enabledelayedexpansion",
        "echo Applying C64 Studio update (" + tag + ")...",
        f":wait_setup_{wait_pid}",
        f'tasklist /FI "PID eq {wait_pid}" /NH 2>nul | find "{wait_pid}" >nul',
        "if not errorlevel 1 (",
        "    timeout /t 1 /nobreak >nul",
        f"    goto wait_setup_{wait_pid}",
        ")",
        ":wait_studio",
        'tasklist /FI "IMAGENAME eq C64-Studio.exe" /NH 2>nul | find /I "C64-Studio.exe" >nul',
        "if not errorlevel 1 (",
        "    echo Waiting for C64-Studio.exe to close before overwriting...",
        "    timeout /t 1 /nobreak >nul",
        "    goto wait_studio",
        ")",
    ]

    if staged.get("studio_dir"):
        src_dir = str(Path(staged["studio_dir"]).resolve())
        lines.append(f'xcopy /E /Y /I /Q "{src_dir}\\*" "{root_str}\\" >nul')

    if staged.get("studio_exe"):
        src_exe = str(Path(staged["studio_exe"]).resolve())
        lines.append(f'copy /Y "{src_exe}" "{root_str}\\C64-Studio.exe" >nul')

    if staged.get("setup_exe"):
        src_setup = str(Path(staged["setup_exe"]).resolve())
        lines.append(f'move /Y "{src_setup}" "{root_str}\\C64-Studio-Setup.exe" >nul')

    lines.extend(
        [
            f'echo {tag}> "{root_str}\\{VERSION_STAMP_FILE}"',
            f'if exist "{staging_str}" rmdir /S /Q "{staging_str}"',
            "echo Update applied successfully!",
            "timeout /t 2 /nobreak >nul",
            '(goto) 2>nul & del "%~f0"',
        ]
    )

    bat_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return bat_path


def launch_windows_self_updater_and_exit(project_root: Path, staged: Dict[str, Any]) -> None:
    """Launch the detached post-exit updater script and exit this process immediately."""
    bat_path = build_windows_updater_script(project_root, staged, os.getpid())
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        ["cmd.exe", "/c", str(bat_path)],
        cwd=str(project_root),
        creationflags=flags,
        close_fds=True,
    )
    print(f"\n  {Style.GREEN}-> Setup is closing to overwrite C64-Studio.exe and C64-Studio-Setup.exe...{Style.RESET}")
    raise SystemExit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Setup Wizard for C64 Studio & C64U Antigravity Bridge",
    )
    parser.add_argument("--host", help="C64U IP address or hostname")
    parser.add_argument("--port", type=int, default=80, help="C64U REST API port (default: 80)")
    parser.add_argument("--password", help="C64U network password")
    parser.add_argument("--kickass-dir", help="Directory where KickAss.jar is or will be installed")
    parser.add_argument("--skip-kickass", action="store_true", help="Skip KickAssembler download")
    parser.add_argument("--skip-java", action="store_true", help="Skip portable Java JRE download")
    parser.add_argument("--skip-oscar64", action="store_true", help="Skip Oscar64 C/C++ compiler download")
    parser.add_argument("--skip-update", action="store_true", help="Skip checking GitHub for C64 Studio updates")
    parser.add_argument("--force-update", action="store_true", help="Re-download latest GitHub release even if tag matches")
    parser.add_argument("--repo", default=C64_STUDIO_GITHUB_REPO, help="GitHub owner/repo for release updates")
    parser.add_argument("--skip-cli", action="store_true", help="Skip CLI and virtualenv setup")
    parser.add_argument("--skip-test", action="store_true", help="Skip C64U connectivity test")
    parser.add_argument("-y", "--yes", "--non-interactive", dest="non_interactive", action="store_true",
                        help="Run non-interactively with defaults or provided options")

    args = parser.parse_args()

    project_root = resolve_project_root()
    env_file = project_root / ".env"
    existing_env = read_existing_env(env_file)

    print_banner()

    interactive = not args.non_interactive

    # --- 0. Check GitHub for Latest C64 Studio & Setup Release ---
    staged_update: Optional[Dict[str, Any]] = None
    if not args.skip_update:
        print(f"{Style.BOLD}Step 0: C64 Studio Self-Update (GitHub Releases){Style.RESET}")
        release = fetch_latest_c64_studio_release(args.repo)
        if release is not None:
            latest_tag = str(release.get("tag_name") or release.get("name") or "").strip()
            current_version = get_installed_version(project_root)
            if latest_tag and not is_newer_version(latest_tag, current_version) and not args.force_update:
                print(
                    f"  {Style.GREEN}* C64 Studio is up to date "
                    f"(installed: {current_version}, latest: {latest_tag}).{Style.RESET}"
                )
            else:
                do_update = True
                if interactive:
                    do_update = prompt_yes_no(
                        f"New release {latest_tag or 'latest'} found on GitHub (installed: {current_version}). Download and update C64-Studio.exe & C64-Studio-Setup.exe?",
                        default_yes=True,
                    )
                if do_update:
                    if _is_windows_process_running("C64-Studio.exe") and interactive:
                        print(f"  {Style.YELLOW}! C64-Studio.exe is currently running. Please close it so the update can overwrite it after Setup exits.{Style.RESET}")
                    staged_update = stage_c64_studio_update(project_root, release)
        print()

    # --- 1. C64U Host ---
    default_host = args.host or existing_env.get("C64U_HOST", "192.168.1.64")
    if interactive and not args.host:
        print(f"{Style.BOLD}Step 1: Commodore 64 Ultimate (C64U) Network Address{Style.RESET}")
        print(f"  (Find this on your C64U under: Commodore + RESTORE -> F1 -> Network Settings)")
        host = prompt_user("Enter C64U IP address or hostname", default=default_host, allow_empty=False)
    else:
        host = default_host

    # --- 2. C64U Port ---
    default_port = args.port or int(existing_env.get("C64U_PORT", "80"))
    if interactive and not args.port:
        port_str = prompt_user("Enter C64U REST API port", default=str(default_port))
        try:
            port = int(port_str)
        except ValueError:
            port = 80
    else:
        port = default_port

    # --- 3. C64U Password ---
    default_pwd = args.password or existing_env.get("C64U_PASSWORD", "")
    if interactive and args.password is None:
        password = prompt_user("Enter C64U Password (press enter if none configured)", default=default_pwd)
    else:
        password = default_pwd or ""

    # --- 4. KickAssembler Installation ---
    print(f"\n{Style.BOLD}Step 2: 6502 Assembler Toolchain (KickAssembler){Style.RESET}")
    kickass_dir = Path(args.kickass_dir).resolve() if args.kickass_dir else (project_root / "tools" / "kickassembler")
    
    # Check if KickAss already exists
    existing_jar = None
    if existing_env.get("KICKASS_JAR") and Path(existing_env["KICKASS_JAR"]).exists():
        existing_jar = Path(existing_env["KICKASS_JAR"]).resolve()
    elif (kickass_dir / "KickAss.jar").exists():
        existing_jar = kickass_dir / "KickAss.jar"
    elif (project_root / "tools" / "KickAss.jar").exists():
        existing_jar = project_root / "tools" / "KickAss.jar"

    kickass_jar: Optional[Path] = existing_jar

    if existing_jar:
        print(f"  {Style.GREEN}* KickAssembler is already installed at:{Style.RESET} {existing_jar}")
    elif not args.skip_kickass:
        install_kick = True
        if interactive:
            install_kick = prompt_yes_no(
                f"KickAssembler is not installed. Download and install automatically to {kickass_dir}?",
                default_yes=True,
            )
        if install_kick:
            kickass_jar = download_and_extract_kickass(kickass_dir)
        else:
            custom_path = prompt_user("Enter custom path to KickAss.jar (or leave empty to skip)", default="")
            if custom_path and Path(custom_path).exists():
                kickass_jar = Path(custom_path).resolve()

    # --- 5. Java Runtime Check / Portable JRE 17 ---
    print(f"\n{Style.BOLD}Step 3: Java Runtime (for KickAssembler){Style.RESET}")
    java_ok, java_info, java_bin = check_java_runtime(project_root)
    java_dir = project_root / "tools" / "java"
    if java_ok:
        print(f"  {Style.GREEN}* Java Runtime detected:{Style.RESET} {java_info} ({java_bin})")
    else:
        print(f"  {Style.YELLOW}! Java check:{Style.RESET} {java_info}")
        if not args.skip_java:
            install_java = True
            if interactive:
                install_java = prompt_yes_no(
                    f"Download portable Eclipse Temurin JRE 17 into {java_dir}?",
                    default_yes=True,
                )
            if install_java:
                downloaded_java = download_and_extract_portable_java(java_dir)
                if downloaded_java is not None:
                    java_bin = downloaded_java
            else:
                offer_java_installation(interactive)

    # --- 6. Oscar64 C/C++ Compiler ---
    print(f"\n{Style.BOLD}Step 4: C/C++ Compiler Toolchain (Oscar64){Style.RESET}")
    oscar_dir = project_root / "tools" / "oscar64"
    oscar64_bin: Optional[Path] = None
    if existing_env.get("OSCAR64_BIN") and Path(existing_env["OSCAR64_BIN"]).is_file():
        oscar64_bin = Path(existing_env["OSCAR64_BIN"]).resolve()
    elif find_local_oscar64_bin(project_root) is not None:
        oscar64_bin = find_local_oscar64_bin(project_root)
    else:
        which_oscar = shutil.which("oscar64")
        if which_oscar:
            oscar64_bin = Path(which_oscar).resolve()

    if oscar64_bin:
        print(f"  {Style.GREEN}* Oscar64 is already installed at:{Style.RESET} {oscar64_bin}")
    elif not args.skip_oscar64:
        install_oscar = True
        if interactive:
            install_oscar = prompt_yes_no(
                f"Oscar64 is not installed. Download and install automatically to {oscar_dir}?",
                default_yes=True,
            )
        if install_oscar:
            oscar64_bin = download_and_extract_oscar64(oscar_dir)

    # --- 7. CLI & Virtualenv Setup ---
    if not args.skip_cli and not is_frozen():
        setup_cli = True
        if interactive:
            setup_cli = prompt_yes_no(
                "\nSet up C64U Bridge CLI and install python dependencies in editable mode?",
                default_yes=True,
            )
        if setup_cli:
            setup_cli_and_virtualenv(project_root)

    # --- 8. Save Configuration ---
    print(f"\n{Style.BOLD}Step 5: Saving Configuration{Style.RESET}")
    save_configuration(
        project_root=project_root,
        host=host,
        port=port,
        password=password if password else None,
        kickass_jar=kickass_jar,
        java_bin=java_bin,
        oscar64_bin=oscar64_bin,
    )

    # --- 9. Test C64U Connection ---
    if not args.skip_test:
        do_test = True
        if interactive:
            do_test = prompt_yes_no(
                f"\nWould you like to test connecting to your C64U at {host}:{port} now?",
                default_yes=True,
            )
        if do_test:
            test_c64u_connection(host, port, password if password else None)

    # --- Summary ---
    if is_frozen():
        print(f"""
{Style.GREEN}{Style.BOLD}========================================================================
                      SETUP COMPLETED SUCCESSFULLY
========================================================================{Style.RESET}

{Style.BOLD}Installed Toolchains & Config:{Style.RESET}
  * Configuration: {Style.CYAN}{env_file}{Style.RESET}
  * KickAssembler: {Style.CYAN}{kickass_jar or 'Not installed'}{Style.RESET}
  * Java Runtime:  {Style.CYAN}{java_bin or 'Not installed'}{Style.RESET}
  * Oscar64:       {Style.CYAN}{oscar64_bin or 'Not installed'}{Style.RESET}

{Style.BOLD}Next Step:{Style.RESET}
  Launch {Style.CYAN}C64-Studio.exe{Style.RESET} in {Style.CYAN}{project_root}{Style.RESET}!
""")
        if staged_update is not None and platform.system() == "Windows":
            launch_windows_self_updater_and_exit(project_root, staged_update)
        if interactive and platform.system() == "Windows":
            try:
                input("Press Enter to exit...")
            except EOFError:
                pass
    else:
        print(f"""
{Style.GREEN}{Style.BOLD}========================================================================
                      SETUP COMPLETED SUCCESSFULLY                      
========================================================================{Style.RESET}

{Style.BOLD}Quick Start Usage:{Style.RESET}
  * Check C64U Status:
      {Style.CYAN}.\\c64u-bridge status{Style.RESET}
  * Inspect Live Screen Memory ($0400-$07E7):
      {Style.CYAN}.\\c64u-bridge screen --color{Style.RESET}
  * Compile & DMA Run 6502 Assembly:
      {Style.CYAN}.\\c64u-bridge run examples/hello_world.asm{Style.RESET}

{Style.BOLD}Google Antigravity Integration:{Style.RESET}
  * Configuration generated in: {Style.CYAN}antigravity/antigravity.json{Style.RESET}
  * C64 Hardware Rules installed in: {Style.CYAN}.agents/rules/c64-bridge.md{Style.RESET}
  * Launch MCP Server:
      {Style.CYAN}.\\c64u-bridge mcp{Style.RESET}
""")


if __name__ == "__main__":
    main()
