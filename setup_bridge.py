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


def download_and_extract_kickass(target_dir: Path) -> Optional[Path]:
    """Download KickAssembler.zip from the official site and extract KickAss.jar."""
    target_dir.mkdir(parents=True, exist_ok=True)
    jar_path = target_dir / "KickAss.jar"
    if jar_path.exists():
        print(f"  {Style.GREEN}* KickAss.jar already exists at: {jar_path}{Style.RESET}")
        return jar_path

    url = "http://theweb.dk/KickAssembler/KickAssembler.zip"
    print(f"  {Style.CYAN}-> Downloading Kick Assembler from {url}...{Style.RESET}")

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "C64U-Antigravity-Bridge-Setup/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
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


def check_java_runtime() -> Tuple[bool, str]:
    """Check if Java runtime is available."""
    java_cmd = shutil.which("java")
    if not java_cmd:
        return False, "Java executable not found in PATH"

    try:
        res = subprocess.run(
            [java_cmd, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ver_output = res.stderr or res.stdout
        first_line = ver_output.splitlines()[0] if ver_output else "Java detected"
        return True, first_line.strip()
    except Exception as e:
        return False, str(e)


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
):
    """Write .env file and update antigravity/antigravity.json."""
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
        # Store resolved absolute path
        lines.append(f"KICKASS_JAR={kickass_jar.resolve()}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  {Style.GREEN}* Saved environment file: {env_file}{Style.RESET}")

    # Update antigravity/antigravity.json
    antigravity_dir = project_root / "antigravity"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    mcp_config_path = antigravity_dir / "antigravity.json"

    kickass_str = str(kickass_jar.resolve()) if kickass_jar and kickass_jar.exists() else ""
    mcp_data = {
        "mcpServers": {
            "c64u-bridge": {
                "command": "uv",
                "args": ["run", "--no-sync", "--directory", str(project_root.resolve()), "c64u-bridge", "mcp"],
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


def main():
    parser = argparse.ArgumentParser(
        description="Interactive Setup Wizard for C64U Antigravity Bridge",
    )
    parser.add_argument("--host", help="C64U IP address or hostname")
    parser.add_argument("--port", type=int, default=80, help="C64U REST API port (default: 80)")
    parser.add_argument("--password", help="C64U network password")
    parser.add_argument("--kickass-dir", help="Directory where KickAss.jar is or will be installed")
    parser.add_argument("--skip-kickass", action="store_true", help="Skip KickAssembler download")
    parser.add_argument("--skip-cli", action="store_true", help="Skip CLI and virtualenv setup")
    parser.add_argument("--skip-test", action="store_true", help="Skip C64U connectivity test")
    parser.add_argument("-y", "--yes", "--non-interactive", dest="non_interactive", action="store_true",
                        help="Run non-interactively with defaults or provided options")

    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    existing_env = read_existing_env(env_file)

    print_banner()

    interactive = not args.non_interactive

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

    # --- 5. Java Runtime Check ---
    java_ok, java_info = check_java_runtime()
    if java_ok:
        print(f"  {Style.GREEN}* Java Runtime detected:{Style.RESET} {java_info}")
    else:
        print(f"  {Style.YELLOW}! Java check:{Style.RESET} {java_info}")
        offer_java_installation(interactive)

    # --- 6. CLI & Virtualenv Setup ---
    if not args.skip_cli:
        setup_cli = True
        if interactive:
            setup_cli = prompt_yes_no(
                "\nSet up C64U Bridge CLI and install python dependencies in editable mode?",
                default_yes=True,
            )
        if setup_cli:
            setup_cli_and_virtualenv(project_root)

    # --- 7. Save Configuration ---
    print(f"\n{Style.BOLD}Step 3: Saving Configuration{Style.RESET}")
    save_configuration(
        project_root=project_root,
        host=host,
        port=port,
        password=password if password else None,
        kickass_jar=kickass_jar,
    )

    # --- 8. Test C64U Connection ---
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
