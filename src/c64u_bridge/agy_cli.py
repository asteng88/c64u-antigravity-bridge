"""
Antigravity CLI (`agy`) Auto-Detection, Setup Walkthrough & Prompt Orchestrator
for C64 Studio IDE.

Supports:
- Automatic discovery of `agy` / `agy.exe` across PATH and standard OS install roots.
- Guided & automated installation via official `https://antigravity.google/cli/` scripts.
- One-click `c64u-bridge` MCP server registration with `agy mcp add`.
- Multi-language C64 prompt orchestration (6502 KickAssembler, C/Oscar64/CC65, Python-to-6502)
  with live line streaming, multi-turn `--continue`, and fenced code block extraction.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple


INSTALL_URL_PS1 = "https://antigravity.google/cli/install.ps1"
INSTALL_URL_CMD = "https://antigravity.google/cli/install.cmd"
INSTALL_URL_SH = "https://antigravity.google/cli/install.sh"

INSTALL_CMD_WINDOWS_PS1 = f"irm {INSTALL_URL_PS1} | iex"
INSTALL_CMD_WINDOWS_CMD = (
    f"curl -fsSL {INSTALL_URL_CMD} -o install.cmd && install.cmd && del install.cmd"
)
INSTALL_CMD_UNIX = f"curl -fsSL {INSTALL_URL_SH} | bash"

DEFAULT_AGY_MODELS: List[Tuple[str, str]] = [
    ("", "Default CLI Model"),
    ("gemini-4-carbon-medium", "Gemini 4 Carbon (Medium)"),
    ("gemini-4-carbon-high", "Gemini 4 Carbon (High)"),
    ("gemini-4-argon-medium", "Gemini 4 Argon (Medium)"),
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash (High)"),
]

CODE_BLOCK_RE = re.compile(
    r"```([a-zA-Z0-9_+-]*)\s*\n(.*?)```",
    re.DOTALL,
)


@dataclass
class ExtractedCodeBlock:
    """A fenced code block extracted from an Antigravity CLI response."""

    language_tag: str
    studio_mode: str  # "asm", "c", or "py"
    code: str


@dataclass
class AgyStatus:
    """Snapshot of local Antigravity CLI (`agy`) installation and configuration state."""

    installed: bool
    binary_path: Optional[Path] = None
    version: Optional[str] = None
    mcp_configured: bool = False
    settings_exists: bool = False
    models: List[Tuple[str, str]] = field(default_factory=lambda: list(DEFAULT_AGY_MODELS))
    install_command: str = ""
    install_command_alt: str = ""
    status_message: str = ""
    error: Optional[str] = None


@dataclass
class AgyPromptResult:
    """Result of executing a prompt through the Antigravity CLI (`agy`)."""

    success: bool
    response_text: str
    stderr: str
    return_code: int
    command: List[str]
    code_blocks: List[ExtractedCodeBlock] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def primary_code_block(self) -> Optional[ExtractedCodeBlock]:
        """Return the most relevant C64 code block (preferring the largest valid block)."""
        if not self.code_blocks:
            return None
        return max(self.code_blocks, key=lambda b: len(b.code))


def classify_code_block(lang_tag: str, code: str, preferred_mode: str = "asm") -> str:
    """Map a markdown code fence tag or code heuristics to 'asm', 'c', or 'py'."""
    tag = (lang_tag or "").strip().lower()
    if tag in {"asm", "s", "6502", "6510", "kickass", "kickassembler", "acme", "ca65"}:
        return "asm"
    if tag in {"c", "cpp", "c++", "cc", "cxx", "h", "hpp", "oscar64", "cc65"}:
        return "c"
    if tag in {"py", "python", "python3"}:
        return "py"

    # Content-based fallback when fence has no language tag
    if "#include" in code or "int main(" in code or "void main(" in code:
        return "c"
    if "BasicUpstart2" in code or re.search(r"^\s*(lda|sta|ldx|ldy|jsr|jmp|sei)\b", code, re.IGNORECASE | re.MULTILINE):
        return "asm"
    if "def " in code or "while True:" in code or "border_color(" in code or "wait_raster(" in code:
        return "py"
    return preferred_mode


def extract_code_blocks(markdown_text: str, preferred_mode: str = "asm") -> List[ExtractedCodeBlock]:
    """Extract all fenced code blocks from an Antigravity CLI markdown response."""
    blocks: List[ExtractedCodeBlock] = []
    for match in CODE_BLOCK_RE.finditer(markdown_text or ""):
        raw_tag = match.group(1) or ""
        raw_code = match.group(2).strip("\r\n")
        if not raw_code.strip():
            continue
        # Skip tiny shell/install snippets if they are bash/sh/powershell/json
        if raw_tag.strip().lower() in {"bash", "sh", "zsh", "powershell", "ps1", "cmd", "bat", "json", "toml", "yaml"}:
            continue
        mode = classify_code_block(raw_tag, raw_code, preferred_mode=preferred_mode)
        blocks.append(
            ExtractedCodeBlock(
                language_tag=raw_tag.strip().lower() or mode,
                studio_mode=mode,
                code=raw_code + "\n",
            )
        )
    return blocks


def build_c64_prompt(
    user_prompt: str,
    language_mode: str = "asm",
    current_code: str = "",
    active_file: Optional[Path] = None,
    include_code_context: bool = True,
) -> str:
    """
    Wrap the user's prompt with concise C64 Studio target guidance so `agy` emits
    immediately compilable 6502 Assembly, C (Oscar64/CC65), or C64-Python code.
    """
    # Pass slash commands through verbatim
    stripped = user_prompt.strip()
    if stripped.startswith("/") or stripped.startswith("!"):
        return stripped

    if language_mode == "c":
        lang_guidance = (
            "Target Platform: Commodore 64 (MOS 6510 / VIC-II $D000 / SID $D400) in C (Oscar64 / CC65).\n"
            "Return complete, compilable C source code inside a single ```c fenced block.\n"
            "Prefer Oscar64 conventions (e.g. `<c64/vic.h>`, `<c64/sid.h>`, or direct volatile uint8_t* "
            "memory-mapped registers at 0x0400, 0xD800, 0xD020, 0xD021, 0xD400 so it compiles cleanly)."
        )
        fence_tag = "c"
    elif language_mode == "py":
        lang_guidance = (
            "Target Platform: C64 Studio Python-to-6502 AST Transpiler.\n"
            "Return complete Python code inside a single ```python fenced block using ONLY supported "
            "bare-metal C64 intrinsics: `poke(addr, val)`, `peek(addr)`, `border_color(c)`, "
            "`background_color(c)`, `wait_raster(line)`, `clear_screen()`, `print_str(col, row, text, color)`, "
            "`sid_tone(freq, waveform)`, `delay(loops)`, `asm(\"\"\"...\"\"\")`, integer variables, "
            "`while`/`for range(...)`/`if` statements, and `COLOR_*` constants."
        )
        fence_tag = "python"
    else:
        lang_guidance = (
            "Target Platform: Commodore 64 (MOS 6510 / VIC-II / SID) using KickAssembler v5.x syntax.\n"
            "Return complete, assemblable 6502 assembly inside a single ```asm fenced block starting with "
            "`BasicUpstart2(start)` and `* = $0810`, using `//` comments."
        )
        fence_tag = "asm"

    parts = [
        f"[C64 Studio IDE Context — Active Language: {language_mode.upper()}]",
        lang_guidance,
    ]
    if active_file is not None:
        parts.append(f"Active Workspace File: {active_file}")
    if include_code_context and current_code.strip():
        trimmed = current_code.strip()
        if len(trimmed) <= 6000:
            parts.append(f"Current Editor Buffer:\n```{fence_tag}\n{trimmed}\n```")

    parts.append(f"User Request:\n{stripped}")
    return "\n\n".join(parts)


class AgyCliConnector:
    """Manages Antigravity CLI (`agy`) discovery, setup, MCP linking, and prompt execution."""

    def __init__(self, agy_bin: Optional[str] = None, workspace_dir: Optional[Path] = None):
        self._explicit_bin = agy_bin or os.getenv("AGY_BIN")
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.last_status: Optional[AgyStatus] = None

    @staticmethod
    def candidate_binary_paths() -> List[Path]:
        """Return ordered platform-specific candidate paths where `agy` is installed."""
        candidates: List[Path] = []
        home = Path.home()
        if os.name == "nt":
            local_appdata = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
            candidates.extend(
                [
                    local_appdata / "agy" / "bin" / "agy.exe",
                    local_appdata / "Programs" / "agy" / "bin" / "agy.exe",
                    local_appdata / "Programs" / "Antigravity" / "bin" / "agy.exe",
                    local_appdata
                    / "Programs"
                    / "Antigravity IDE"
                    / "resources"
                    / "app"
                    / "extensions"
                    / "agy"
                    / "bin"
                    / "agy.exe",
                    home / ".agy" / "bin" / "agy.exe",
                    home / ".local" / "bin" / "agy.exe",
                ]
            )
        else:
            candidates.extend(
                [
                    home / ".agy" / "bin" / "agy",
                    home / ".local" / "bin" / "agy",
                    Path("/usr/local/bin/agy"),
                    Path("/opt/homebrew/bin/agy"),
                ]
            )
        return candidates

    def find_binary(self) -> Optional[Path]:
        """Auto-detect the `agy` CLI executable."""
        if self._explicit_bin:
            exp = Path(self._explicit_bin)
            if exp.is_file():
                return exp.resolve()
            found_exp = shutil.which(self._explicit_bin)
            if found_exp:
                return Path(found_exp).resolve()

        for cmd_name in ("agy.exe", "agy") if os.name == "nt" else ("agy",):
            which_hit = shutil.which(cmd_name)
            if which_hit:
                return Path(which_hit).resolve()

        for cand in self.candidate_binary_paths():
            if cand.is_file():
                return cand.resolve()

        return None

    def detect_cli(self, fetch_models: bool = False) -> AgyStatus:
        """Inspect `agy` installation, version, settings, and C64U MCP registration."""
        is_win = os.name == "nt"
        install_cmd = INSTALL_CMD_WINDOWS_PS1 if is_win else INSTALL_CMD_UNIX
        install_alt = INSTALL_CMD_WINDOWS_CMD if is_win else ""

        bin_path = self.find_binary()
        settings_file = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
        global_mcp_file = Path.home() / ".gemini" / "config" / "mcp_config.json"

        mcp_linked = False
        if global_mcp_file.is_file():
            try:
                mcp_txt = global_mcp_file.read_text(encoding="utf-8", errors="ignore")
                mcp_linked = "c64u-bridge" in mcp_txt or "c64u-mcp" in mcp_txt
            except Exception:
                pass

        if bin_path is None:
            status = AgyStatus(
                installed=False,
                binary_path=None,
                version=None,
                mcp_configured=mcp_linked,
                settings_exists=settings_file.is_file(),
                install_command=install_cmd,
                install_command_alt=install_alt,
                status_message="Antigravity CLI (agy) not detected on this system.",
            )
            self.last_status = status
            return status

        version_str: Optional[str] = None
        err_str: Optional[str] = None
        try:
            res = subprocess.run(
                [str(bin_path), "--version"],
                capture_output=True,
                text=True,
                timeout=6.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            m = re.search(r"(\d+\.\d+\.\d+[a-zA-Z0-9.-]*)", out)
            version_str = m.group(1) if m else (out.splitlines()[0].strip() if out else "detected")
        except Exception as exc:
            err_str = str(exc)

        if not mcp_linked:
            try:
                mcp_res = subprocess.run(
                    [str(bin_path), "mcp", "list"],
                    capture_output=True,
                    text=True,
                    timeout=6.0,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                combined_mcp = (mcp_res.stdout or "") + (mcp_res.stderr or "")
                if "c64u" in combined_mcp.lower():
                    mcp_linked = True
            except Exception:
                pass

        models = list(DEFAULT_AGY_MODELS)
        if fetch_models:
            try:
                mod_res = subprocess.run(
                    [str(bin_path), "models"],
                    capture_output=True,
                    text=True,
                    timeout=8.0,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                parsed_models: List[Tuple[str, str]] = [("", "Default CLI Model")]
                for line in (mod_res.stdout or "").splitlines():
                    if "\t" in line:
                        mid, mlabel = line.split("\t", 1)
                        if mid.strip():
                            parsed_models.append((mid.strip(), mlabel.strip()))
                if len(parsed_models) > 1:
                    models = parsed_models
            except Exception:
                pass

        ver_disp = f"v{version_str}" if version_str else "(unknown version)"
        status = AgyStatus(
            installed=True,
            binary_path=bin_path,
            version=version_str,
            mcp_configured=mcp_linked,
            settings_exists=settings_file.is_file(),
            models=models,
            install_command=install_cmd,
            install_command_alt=install_alt,
            status_message=f"Antigravity CLI {ver_disp} detected at {bin_path}",
            error=err_str,
        )
        self.last_status = status
        return status

    def install_cli(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """Download and install the official Google Antigravity CLI (`agy`)."""
        def _emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        if os.name == "nt":
            _emit(f"Running official Windows installer: {INSTALL_CMD_WINDOWS_PS1}")
            ps_exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
            cmd = [
                ps_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                INSTALL_CMD_WINDOWS_PS1,
            ]
        else:
            _emit(f"Running official Unix installer: {INSTALL_CMD_UNIX}")
            bash_exe = shutil.which("bash") or "/bin/bash"
            cmd = [bash_exe, "-c", INSTALL_CMD_UNIX]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if res.stdout:
                for ln in res.stdout.strip().splitlines()[-6:]:
                    _emit(ln)
            st = self.detect_cli()
            if st.installed and st.binary_path:
                # Ensure `agy install` configures user PATH hooks if needed
                try:
                    subprocess.run(
                        [str(st.binary_path), "install"],
                        capture_output=True,
                        text=True,
                        timeout=15.0,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except Exception:
                    pass
                return True, f"Installed Antigravity CLI v{st.version or ''} at {st.binary_path}"
            err_detail = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
            return False, f"Installer finished without detecting agy binary: {err_detail}"
        except Exception as exc:
            return False, f"Automatic Antigravity CLI installation failed: {exc}"

    def update_cli(self) -> Tuple[bool, str]:
        """Update an existing `agy` installation via `agy update`."""
        bin_path = self.find_binary()
        if not bin_path:
            return False, "Antigravity CLI (agy) is not installed yet."
        try:
            res = subprocess.run(
                [str(bin_path), "update"],
                capture_output=True,
                text=True,
                timeout=120.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            st = self.detect_cli()
            out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            if res.returncode == 0:
                return True, out or f"Antigravity CLI updated (v{st.version})."
            return False, out or f"Update exited with code {res.returncode}"
        except Exception as exc:
            return False, f"Failed to run `agy update`: {exc}"

    def register_c64u_mcp(self, host: str = "c64u.local", port: int = 80) -> Tuple[bool, str]:
        """Register the `c64u-bridge` MCP server with the Antigravity CLI."""
        bin_path = self.find_binary()
        if not bin_path:
            return False, "Install Antigravity CLI (agy) first before linking MCP."

        # Prefer virtualenv c64u-mcp executable if present, otherwise `python -m c64u_bridge mcp`
        venv_mcp = self.workspace_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
            "c64u-mcp.exe" if os.name == "nt" else "c64u-mcp"
        )
        # Remove any stale entry quietly first so `add` cleanly updates
        try:
            subprocess.run(
                [str(bin_path), "mcp", "remove", "c64u-bridge"],
                capture_output=True,
                text=True,
                timeout=8.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

        env_flags = [
            "--env",
            f"C64U_HOST={host}",
            "--env",
            f"C64U_PORT={port}",
        ]
        if venv_mcp.is_file():
            cmd = [str(bin_path), "mcp", "add", *env_flags, "c64u-bridge", str(venv_mcp)]
        else:
            py_exe = shutil.which("python") or "python"
            cmd = [
                str(bin_path),
                "mcp",
                "add",
                *env_flags,
                "c64u-bridge",
                "--",
                py_exe,
                "-m",
                "c64u_bridge",
                "mcp",
            ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15.0,
                cwd=self.workspace_dir,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            self.detect_cli()
            if res.returncode == 0:
                return True, out or "Linked `c64u-bridge` MCP server to Antigravity CLI."
            return False, out or f"`agy mcp add` exited with code {res.returncode}"
        except Exception as exc:
            return False, f"Failed to register MCP server with agy: {exc}"

    def launch_interactive_terminal(self, initial_args: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Open `agy` inside a visible OS terminal window (e.g. for first-time sign-in / auth)."""
        bin_path = self.find_binary()
        if not bin_path:
            return False, "Antigravity CLI (agy) is not installed."
        extra = initial_args or []
        try:
            if os.name == "nt":
                subprocess.Popen(
                    ["cmd.exe", "/c", "start", "Antigravity CLI (agy)", str(bin_path), *extra],
                    cwd=self.workspace_dir,
                )
            elif platform.system() == "Darwin":
                escaped = " ".join([f'"{bin_path}"', *[f'"{a}"' for a in extra]])
                subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{escaped}"'])
            else:
                for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
                    if shutil.which(term):
                        subprocess.Popen([term, "-e", str(bin_path), *extra], cwd=self.workspace_dir)
                        break
                else:
                    return False, f"Run `{bin_path}` in your terminal to complete authentication."
            return True, f"Launched interactive Antigravity CLI terminal ({bin_path.name})."
        except Exception as exc:
            return False, f"Could not open terminal window: {exc}"

    def run_prompt(
        self,
        prompt: str,
        *,
        language_mode: str = "asm",
        current_code: str = "",
        active_file: Optional[Path] = None,
        include_code_context: bool = True,
        continue_conversation: bool = False,
        exec_mode: str = "accept-edits",
        model: str = "",
        effort: str = "",
        on_line: Optional[Callable[[str], None]] = None,
    ) -> AgyPromptResult:
        """
        Execute a prompt via `agy --print` in the workspace directory, streaming output lines
        in real time via `on_line` and extracting any generated C64 code blocks.
        """
        bin_path = self.find_binary()
        if not bin_path:
            return AgyPromptResult(
                success=False,
                response_text="",
                stderr="",
                return_code=-1,
                command=[],
                error_message=(
                    "Antigravity CLI (`agy`) is not installed. Click 'AGY SETUP' to auto-install "
                    f"or run: {INSTALL_CMD_WINDOWS_PS1 if os.name == 'nt' else INSTALL_CMD_UNIX}"
                ),
            )

        full_prompt = build_c64_prompt(
            user_prompt=prompt,
            language_mode=language_mode,
            current_code=current_code,
            active_file=active_file,
            include_code_context=include_code_context,
        )

        cmd: List[str] = [str(bin_path)]
        if exec_mode in {"accept-edits", "plan", "auto"}:
            cmd.extend(["--mode", exec_mode])
        if continue_conversation:
            cmd.append("--continue")
        if model.strip():
            cmd.extend(["--model", model.strip()])
        if effort.strip():
            cmd.extend(["--effort", effort.strip()])
        cmd.extend(["-p", full_prompt])

        stdout_lines: List[str] = []
        stderr_text = ""

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=self.workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                clean_line = line.rstrip("\r\n")
                stdout_lines.append(clean_line)
                if on_line is not None:
                    on_line(clean_line)

            if proc.stderr is not None:
                stderr_text = proc.stderr.read() or ""
            rc = proc.wait()
            response_text = "\n".join(stdout_lines).strip()
            blocks = extract_code_blocks(response_text, preferred_mode=language_mode)

            err_msg: Optional[str] = None
            if rc != 0:
                err_msg = (stderr_text.strip() or response_text or f"agy exited with status {rc}")

            return AgyPromptResult(
                success=(rc == 0),
                response_text=response_text,
                stderr=stderr_text,
                return_code=rc,
                command=cmd,
                code_blocks=blocks,
                error_message=err_msg,
            )
        except Exception as exc:
            return AgyPromptResult(
                success=False,
                response_text="\n".join(stdout_lines),
                stderr=stderr_text,
                return_code=-1,
                command=cmd,
                error_message=f"Antigravity CLI execution error: {exc}",
            )
