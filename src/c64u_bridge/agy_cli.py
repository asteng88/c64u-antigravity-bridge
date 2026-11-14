"""
AI CLI (`agy` & `claude`) Auto-Detection, Setup Walkthrough & Prompt Orchestrator
for C64 Studio IDE.

Supports:
- Automatic discovery of Antigravity CLI (`agy`) and Claude Code CLI (`claude`)
  across PATH and standard OS install roots.
- Guided & automated installation via official install scripts.
- One-click `c64u-bridge` MCP server registration with `agy mcp add` or `claude mcp add`.
- Multi-language C64 prompt orchestration (6502 KickAssembler, C/Oscar64/CC65, Python-to-6502)
  with live line streaming, multi-turn `--continue`, and fenced code block extraction.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


INSTALL_URL_PS1 = "https://antigravity.google/cli/install.ps1"
INSTALL_URL_CMD = "https://antigravity.google/cli/install.cmd"
INSTALL_URL_SH = "https://antigravity.google/cli/install.sh"

INSTALL_CMD_WINDOWS_PS1 = f"irm {INSTALL_URL_PS1} | iex"
INSTALL_CMD_WINDOWS_CMD = (
    f"curl -fsSL {INSTALL_URL_CMD} -o install.cmd && install.cmd && del install.cmd"
)
INSTALL_CMD_UNIX = f"curl -fsSL {INSTALL_URL_SH} | bash"

CLAUDE_INSTALL_URL_PS1 = "https://claude.ai/install.ps1"
CLAUDE_INSTALL_URL_CMD = "https://claude.ai/install.cmd"
CLAUDE_INSTALL_URL_SH = "https://claude.ai/install.sh"

CLAUDE_INSTALL_CMD_WINDOWS_PS1 = f"irm {CLAUDE_INSTALL_URL_PS1} | iex"
CLAUDE_INSTALL_CMD_WINDOWS_CMD = (
    f"curl -fsSL {CLAUDE_INSTALL_URL_CMD} -o install.cmd && install.cmd && del install.cmd"
)
CLAUDE_INSTALL_CMD_UNIX = f"curl -fsSL {CLAUDE_INSTALL_URL_SH} | bash"

AI_PROVIDERS: Tuple[Tuple[str, str], ...] = (
    ("agy", "Antigravity (agy)"),
    ("claude", "Claude Code (claude)"),
)

DEFAULT_AGY_MODELS: List[Tuple[str, str]] = [
    ("", "Default CLI Model"),
    ("gemini-4-hydrogen-medium", "Gemini 4 Hydrogen (Medium)"),
    ("gemini-4-hydrogen-high", "Gemini 4 Hydrogen (High)"),
    ("gemini-4-carbon-medium", "Gemini 4 Carbon (Medium)"),
    ("gemini-4-carbon-high", "Gemini 4 Carbon (High)"),
    ("gemini-4-argon-medium", "Gemini 4 Argon (Medium)"),
    ("gemini-3.8-flash-high", "Gemini 3.8 Flash (High)"),
]

DEFAULT_CLAUDE_MODELS: List[Tuple[str, str]] = [
    ("", "Default CLI Model"),
    ("sonnet", "Claude Sonnet (Latest)"),
    ("opus", "Claude Opus (Latest)"),
    ("haiku", "Claude Haiku (Latest)"),
]

AGY_EFFORT_LEVELS: Tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")


def normalize_provider(provider: Optional[str]) -> str:
    """Normalize an AI CLI provider identifier to 'agy' or 'claude'."""
    val = (provider or "").strip().lower()
    if val in ("claude", "claude-code", "claude_code", "claude.exe"):
        return "claude"
    return "agy"


def provider_display_name(provider: str) -> str:
    """Human-readable display name for an AI CLI provider."""
    return "Claude Code CLI" if normalize_provider(provider) == "claude" else "Antigravity CLI"


def provider_short_tag(provider: str) -> str:
    """Short uppercase badge/log tag for an AI CLI provider."""
    return "CLAUDE" if normalize_provider(provider) == "claude" else "AGY"


def default_models_for_provider(provider: str) -> List[Tuple[str, str]]:
    """Return default model choices for the specified AI CLI provider."""
    if normalize_provider(provider) == "claude":
        return list(DEFAULT_CLAUDE_MODELS)
    return list(DEFAULT_AGY_MODELS)


def install_commands_for_provider(provider: str) -> Tuple[str, str]:
    """Return (primary_install_cmd, alt_install_cmd) for the current OS and provider."""
    is_win = os.name == "nt"
    if normalize_provider(provider) == "claude":
        return (
            CLAUDE_INSTALL_CMD_WINDOWS_PS1 if is_win else CLAUDE_INSTALL_CMD_UNIX,
            CLAUDE_INSTALL_CMD_WINDOWS_CMD if is_win else "",
        )
    return (
        INSTALL_CMD_WINDOWS_PS1 if is_win else INSTALL_CMD_UNIX,
        INSTALL_CMD_WINDOWS_CMD if is_win else "",
    )


CODE_BLOCK_RE = re.compile(
    r"```([a-zA-Z0-9_+-]*)\s*\n(.*?)```",
    re.DOTALL,
)


@dataclass
class ExtractedCodeBlock:
    """A fenced code block extracted from an AI CLI response."""

    language_tag: str
    studio_mode: str  # "asm", "c", or "py"
    code: str


@dataclass
class AgyStatus:
    """Snapshot of local AI CLI (`agy` or `claude`) installation and configuration state."""

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
    provider: str = "agy"


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
    touched_files: List[Path] = field(default_factory=list)
    conversation_id: Optional[str] = None

    @property
    def primary_code_block(self) -> Optional[ExtractedCodeBlock]:
        """Return the most relevant C64 code block (preferring the largest valid block)."""
        if not self.code_blocks:
            return None
        return max(self.code_blocks, key=lambda b: len(b.code))


_SKIPPED_FENCE_TAGS = {
    "bash",
    "sh",
    "zsh",
    "powershell",
    "ps1",
    "cmd",
    "bat",
    "json",
    "toml",
    "yaml",
    "markdown",
    "md",
    "text",
    "txt",
}


def classify_code_block(lang_tag: str, code: str, preferred_mode: str = "asm") -> str:
    """Map a markdown code fence tag or code heuristics to 'asm', 'c', 'py', or 'def'."""
    tag = (lang_tag or "").strip().lower()
    if tag in {"asm", "s", "6502", "6510", "kickass", "kickassembler", "acme", "ca65"}:
        return "asm"
    if tag in {"c", "cpp", "c++", "cc", "cxx", "h", "hpp", "oscar64", "cc65"}:
        return "c"
    if tag in {"py", "python", "python3"}:
        return "def" if preferred_mode == "def" else "py"

    # Content-based fallback when fence has no language tag
    if "#include" in code or "int main(" in code or "void main(" in code:
        return "c"
    if "BasicUpstart2" in code or re.search(
        r"^\s*(lda|sta|ldx|ldy|jsr|jmp|sei)\b", code, re.IGNORECASE | re.MULTILINE
    ):
        return "asm"
    if preferred_mode == "def" and (
        "PATTERNS" in code or "SPRITES" in code or "STEPS" in code or "TILES" in code or "LEVELS" in code
    ):
        return "def"
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
        # Skip tiny shell/install/config snippets
        if raw_tag.strip().lower() in _SKIPPED_FENCE_TAGS:
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


def extract_streaming_code_preview(
    markdown_text: str,
    preferred_mode: str = "asm",
) -> Optional[ExtractedCodeBlock]:
    """
    Extract an in-progress (unclosed) or completed fenced code block from partial
    streaming markdown so C64 Studio can live-render generated code in the editor.
    """
    if not markdown_text:
        return None
    # Check if there is a trailing unclosed ```<tag>\n<code> block actively streaming
    remainder = CODE_BLOCK_RE.sub("", markdown_text)
    open_match = re.search(r"```([a-zA-Z0-9_+-]*)[ \t]*\r?\n(.*)$", remainder, re.DOTALL)
    if open_match:
        raw_tag = open_match.group(1) or ""
        raw_code = open_match.group(2).lstrip("\r\n")
        if raw_code.strip() and raw_tag.strip().lower() not in _SKIPPED_FENCE_TAGS:
            mode = classify_code_block(raw_tag, raw_code, preferred_mode=preferred_mode)
            return ExtractedCodeBlock(
                language_tag=raw_tag.strip().lower() or mode,
                studio_mode=mode,
                code=raw_code,
            )

    completed = extract_code_blocks(markdown_text, preferred_mode=preferred_mode)
    if completed:
        return max(completed, key=lambda b: len(b.code))
    return None


def infer_prompt_language(user_prompt: str, fallback_mode: str = "asm") -> str:
    """Detect when a prompt explicitly asks for Assembly, C/Oscar64, or Python."""
    low = (user_prompt or "").lower()
    if re.search(r"\b(kickassembler|kickass|6502\s+asm|6502\s+assembly|in\s+assembly|in\s+asm|\.asm)\b", low):
        return "asm"
    if re.search(r"\b(oscar64|cc65|in\s+c\+\+|in\s+c99|in\s+c\b|\.c\b)", low):
        return "c"
    if re.search(r"\b(in\s+python|python-to-6502|\.py\b)", low) and fallback_mode != "def":
        return "py"
    return fallback_mode


GAME_PROJECT_STRUCTURE_GUIDANCE = (
    "Game Project Structure (REQUIRED for multi-asset C64 games under `game_dev/<slug>/`):\n"
    "Always organize games using the standard `tools/build/build_tool.py` layout:\n"
    "- `game_dev/<slug>/build.py`: Declarative manifest (`TITLE = \"...\"` and `STEPS = [...]`) with steps:\n"
    "  `(\"sprites\", \"sprites/<slug>_sprites.py\")`, `(\"tileset\", \"map/<slug>_map.py\")`, "
    "`(\"song\", \"music/<slug>_theme.py\")`, `(\"koala\", \"loading/loading_scene.py\")`, "
    "and `(\"asm\", \"game/<slug>.asm\")` (plus `(\"levels\", ...)` if needed).\n"
    "- `game_dev/<slug>/sprites/<slug>_sprites.py`: Sprite bank definition for `tools/sprites/sprite_tool.py`.\n"
    "- `game_dev/<slug>/map/<slug>_map.py`: Charset/tileset/map definition for `tools/charset/tileset_tool.py`.\n"
    "- `game_dev/<slug>/music/<slug>_theme.py`: Song definition for `tools/sid/song_tool.py` "
    "(`ASM = \"music.asm\"`, `INSTRUMENTS`, `PATTERNS`, `ORDERS`, `FILTER_CUTOFF`, `FILTER_ROUTING`).\n"
    "- `game_dev/<slug>/loading/loading_scene.py`: Koala title screen for `tools/bitmap/koala_tool.py` (`OUTPUT = \"loading\"`).\n"
    "- `game_dev/<slug>/game/<slug>.asm`: Main KickAssembler source (`BasicUpstart2(boot)`) importing generated "
    "assets/constants BEFORE code references them, built via `python tools/build/build_tool.py game_dev/<slug>/build.py`.\n"
    "- **CRITICAL 6510 Boot/IRQ Safety**: When banking out KERNAL (`$01 = #$35`), ALWAYS disable CIA1/CIA2 IRQs "
    "(`lda #$7F; sta $DC0D; sta $DD0D; lda $DC0D; lda $DD0D`) and install `$FFFE/$FFFF` + `$FFFA/$FFFB` vectors "
    "(e.g., an `rti` stub or raster IRQ) BEFORE `cli`, and set `$DD02 |= 3` before selecting VIC bank via `$DD00`.\n"
    "- Isometric terrain: `(\"isotiles\", \"map/<slug>_iso.py\")` step; full-resolution title art: `FULL_RES = True`.\n"
    "Game engine checklist (each item was a real bug; details and fixes in references/game_engine_pitfalls.md):\n"
    "1. Scrolling: publish fine scroll, screen page ($D018) and sprite positions as ONE frame state and let the\n"
    "   raster IRQ apply them together; never apply fine scroll before the coarse-shifted screen is ready.\n"
    "2. Coarse scroll by shifting the double-buffered screen and drawing only the new edge; rebuild colour RAM\n"
    "   from a colour map in the IRQ right after the page flip; measure the latest raster line the main loop\n"
    "   publishes on its heaviest frame and keep ~10 lines of margin.\n"
    "3. Raster splits: write $D011 first in the handler, at a line that is never a bad line for any fine-scroll\n"
    "   value, and keep the VIC idle between the playfield and a HUD so no partial row shifts the HUD.\n"
    "4. Switching screens (title, briefing, map, game over): switch the game's raster IRQ off ($D01A = 0) first,\n"
    "   on every path; re-install it when play starts.\n"
    "5. Double buffering: banners, HUD rows and sprite pointers go to BOTH screen pages.\n"
    "6. Sound: before any wait-for-fire loop or banner, finish or silence sound effects; play music only on the\n"
    "   screens meant for it and silence the SID when leaving them.\n"
    "7. Spawn/target points: validate at build time that the player can reach them (movement clamps + pickup\n"
    "   tolerance + margin), that nothing hides them, and spread them with a stride coprime to the area count.\n"
    "8. Verify with tools/gamecheck/game_check.py (studio GAME CHECK, build_tool --check N), then on VICE/hardware.\n"
)


def _is_game_project_prompt(
    user_prompt: str,
    language_mode: str = "asm",
    active_file: Optional[Path] = None,
) -> bool:
    """Return True only when the request or active file is for a multi-asset C64 game project."""
    if language_mode == "def":
        return True
    if active_file is not None:
        parts_low = {p.lower() for p in active_file.parts}
        if "game_dev" in parts_low or active_file.name.lower() == "build.py":
            return True
    low = (user_prompt or "").lower()
    return bool(
        re.search(
            r"\b(game_dev|build\.py|full\s+game|new\s+game|build\s+(?:a|an|the|this)\s+[\w\s-]*game|"
            r"create\s+(?:a|an|the)\s+[\w\s-]*game|make\s+(?:a|an|the)\s+[\w\s-]*game|"
            r"arcade\s+game|platformer|shooter|shmup)\b",
            low,
        )
    )


def build_c64_prompt(
    user_prompt: str,
    language_mode: str = "asm",
    current_code: str = "",
    active_file: Optional[Path] = None,
    include_code_context: bool = True,
) -> str:
    """
    Wrap the user's prompt with concise C64 Studio target guidance so `agy` streams
    immediately compilable 6502 Assembly, C (Oscar64/CC65), C64-Python, or Game Dev asset code.
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
    elif language_mode == "def":
        lang_guidance = (
            "Target Platform: C64 Studio Game Dev Python Asset / Build Definition.\n"
            "Return the complete updated Python definition file inside a single ```python fenced block, "
            "preserving the file's top-level schema constants (such as `INSTRUMENTS`/`PATTERNS`/`ORDERS`, "
            "`SPRITES`, `TILES`/`MAP`, `STEPS`, or `LEVELS`) so F7 builds it cleanly."
        )
        fence_tag = "python"
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

    ide_fast_path = (
        "IDE Execution Note: You are streaming live inside the C64 Studio IDE editor window. "
        "Generate and stream the complete requested code directly in your reply inside the fenced code block "
        "right away. Do NOT invoke `run_command` / shell commands or spend turns scanning unrelated directories "
        "unless explicitly asked — C64 Studio automatically loads your fenced code block into the live editor "
        "and handles compilation and DMA execution."
    )

    parts = [
        f"[C64 Studio IDE Context — Active Language: {language_mode.upper()}]",
        lang_guidance,
        ide_fast_path,
    ]
    if _is_game_project_prompt(stripped, language_mode=language_mode, active_file=active_file):
        parts.append(GAME_PROJECT_STRUCTURE_GUIDANCE)
    if active_file is not None:
        parts.append(f"Active Workspace File: {active_file}")
    if include_code_context and current_code.strip():
        trimmed = current_code.strip()
        if len(trimmed) <= 6000:
            parts.append(f"Current Editor Buffer:\n```{fence_tag}\n{trimmed}\n```")

    parts.append(f"User Request:\n{stripped}")
    return "\n\n".join(parts)


class AgyCliConnector:
    """Manages AI CLI (`agy` & `claude`) discovery, setup, MCP linking, and prompt execution."""

    def __init__(
        self,
        agy_bin: Optional[str] = None,
        workspace_dir: Optional[Path] = None,
        claude_bin: Optional[str] = None,
        provider: str = "agy",
    ):
        self._explicit_bin = agy_bin or os.getenv("AGY_BIN")
        self._explicit_claude_bin = claude_bin or os.getenv("CLAUDE_BIN")
        self.provider = normalize_provider(provider)
        self.workspace_dir = (workspace_dir or Path.cwd()).resolve()
        self.last_status: Optional[AgyStatus] = None
        self.last_statuses: Dict[str, AgyStatus] = {}

    @staticmethod
    def candidate_binary_paths(provider: str = "agy") -> List[Path]:
        """Return ordered platform-specific candidate paths where the CLI binary is installed."""
        prov = normalize_provider(provider)
        candidates: List[Path] = []
        home = Path.home()
        if prov == "claude":
            if os.name == "nt":
                local_appdata = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
                appdata = Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming")))
                candidates.extend(
                    [
                        home / ".local" / "bin" / "claude.exe",
                        home / ".claude" / "local" / "claude.exe",
                        local_appdata / "Claude" / "claude.exe",
                        local_appdata / "Programs" / "claude" / "claude.exe",
                        appdata / "npm" / "claude.cmd",
                    ]
                )
            else:
                candidates.extend(
                    [
                        home / ".local" / "bin" / "claude",
                        home / ".claude" / "local" / "claude",
                        Path("/usr/local/bin/claude"),
                        Path("/opt/homebrew/bin/claude"),
                        home / ".npm-global" / "bin" / "claude",
                    ]
                )
            return candidates

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

    def find_binary(self, provider: Optional[str] = None) -> Optional[Path]:
        """Auto-detect the CLI executable for `provider` ('agy' or 'claude')."""
        prov = normalize_provider(provider or self.provider)
        explicit = self._explicit_claude_bin if prov == "claude" else self._explicit_bin
        if explicit:
            exp = Path(explicit)
            if exp.is_file():
                return exp.resolve()
            found_exp = shutil.which(explicit)
            if found_exp:
                return Path(found_exp).resolve()

        if prov == "claude":
            cmd_names = ("claude.exe", "claude.cmd", "claude") if os.name == "nt" else ("claude",)
        else:
            cmd_names = ("agy.exe", "agy") if os.name == "nt" else ("agy",)

        for cmd_name in cmd_names:
            which_hit = shutil.which(cmd_name)
            if which_hit:
                return Path(which_hit).resolve()

        cands = (
            self.candidate_binary_paths()
            if prov == "agy"
            else self.candidate_binary_paths("claude")
        )
        for cand in cands:
            if cand.is_file():
                return cand.resolve()

        return None

    def detect_cli(
        self,
        fetch_models: bool = False,
        provider: Optional[str] = None,
    ) -> AgyStatus:
        """Inspect CLI installation, version, settings, and C64U MCP registration."""
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        install_cmd, install_alt = install_commands_for_provider(prov)

        bin_path = self.find_binary(provider=prov)
        if prov == "claude":
            settings_file = Path.home() / ".claude" / "settings.json"
            global_mcp_file = Path.home() / ".claude.json"
        else:
            settings_file = Path.home() / ".gemini" / "antigravity-cli" / "settings.json"
            global_mcp_file = Path.home() / ".gemini" / "config" / "mcp_config.json"

        mcp_linked = False
        if global_mcp_file.is_file():
            try:
                mcp_txt = global_mcp_file.read_text(encoding="utf-8", errors="ignore")
                mcp_linked = "c64u-bridge" in mcp_txt or "c64u-mcp" in mcp_txt
            except Exception:
                pass

        default_models = default_models_for_provider(prov)
        if bin_path is None:
            status = AgyStatus(
                installed=False,
                binary_path=None,
                version=None,
                mcp_configured=mcp_linked,
                settings_exists=settings_file.is_file(),
                models=default_models,
                install_command=install_cmd,
                install_command_alt=install_alt,
                status_message=f"{disp_name} ({prov}) not detected on this system.",
                provider=prov,
            )
            self.last_statuses[prov] = status
            if prov == self.provider:
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

        models = list(default_models)
        if fetch_models and prov == "agy":
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
            status_message=f"{disp_name} {ver_disp} detected at {bin_path}",
            error=err_str,
            provider=prov,
        )
        self.last_statuses[prov] = status
        if prov == self.provider:
            self.last_status = status
        return status

    def detect_all_clis(self, fetch_models: bool = False) -> Dict[str, AgyStatus]:
        """Detect both Antigravity (`agy`) and Claude Code (`claude`) CLIs."""
        return {
            prov_id: self.detect_cli(fetch_models=fetch_models, provider=prov_id)
            for prov_id, _ in AI_PROVIDERS
        }

    def install_cli(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        provider: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Download and install the official CLI (`agy` or `claude`)."""
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        install_ps1, _ = install_commands_for_provider(prov)
        install_unix = CLAUDE_INSTALL_CMD_UNIX if prov == "claude" else INSTALL_CMD_UNIX

        def _emit(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        if os.name == "nt":
            _emit(f"Running official Windows installer: {install_ps1}")
            ps_exe = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
            cmd = [
                ps_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                install_ps1,
            ]
        else:
            _emit(f"Running official Unix installer: {install_unix}")
            bash_exe = shutil.which("bash") or "/bin/bash"
            cmd = [bash_exe, "-c", install_unix]

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
            st = self.detect_cli(provider=prov)
            if st.installed and st.binary_path:
                if prov == "agy":
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
                return True, f"Installed {disp_name} v{st.version or ''} at {st.binary_path}"
            err_detail = (res.stderr or res.stdout or f"exit code {res.returncode}").strip()
            return False, f"Installer finished without detecting {prov} binary: {err_detail}"
        except Exception as exc:
            return False, f"Automatic {disp_name} installation failed: {exc}"

    def update_cli(self, provider: Optional[str] = None) -> Tuple[bool, str]:
        """Update an existing `agy` or `claude` installation."""
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        bin_path = self.find_binary(provider=prov)
        if not bin_path:
            return False, f"{disp_name} ({prov}) is not installed yet."
        try:
            res = subprocess.run(
                [str(bin_path), "update"],
                capture_output=True,
                text=True,
                timeout=120.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            st = self.detect_cli(provider=prov)
            out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            if res.returncode == 0:
                return True, out or f"{disp_name} updated (v{st.version})."
            return False, out or f"Update exited with code {res.returncode}"
        except Exception as exc:
            return False, f"Failed to run `{prov} update`: {exc}"

    def register_c64u_mcp(
        self,
        host: str = "c64u.local",
        port: int = 80,
        provider: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Register the `c64u-bridge` MCP server with the selected CLI (`agy` or `claude`)."""
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        bin_path = self.find_binary(provider=prov)
        if not bin_path:
            return False, f"Install {disp_name} ({prov}) first before linking MCP."

        venv_mcp = self.workspace_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
            "c64u-mcp.exe" if os.name == "nt" else "c64u-mcp"
        )
        # Remove any stale entry quietly first so `add` cleanly updates
        rm_cmds = (
            [[str(bin_path), "mcp", "remove", "-s", "user", "c64u-bridge"], [str(bin_path), "mcp", "remove", "c64u-bridge"]]
            if prov == "claude"
            else [[str(bin_path), "mcp", "remove", "c64u-bridge"]]
        )
        for rm_cmd in rm_cmds:
            try:
                subprocess.run(
                    rm_cmd,
                    capture_output=True,
                    text=True,
                    timeout=8.0,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass

        env_flag = "-e" if prov == "claude" else "--env"
        env_flags = [
            env_flag,
            f"C64U_HOST={host}",
            env_flag,
            f"C64U_PORT={port}",
            env_flag,
            f"PYTHONPATH={self.workspace_dir / 'src'}",
        ]
        scope_flags = ["-s", "user"] if prov == "claude" else []
        venv_py = self.workspace_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
            "python.exe" if os.name == "nt" else "python"
        )
        if venv_py.is_file():
            cmd = [
                str(bin_path),
                "mcp",
                "add",
                *scope_flags,
                *env_flags,
                "c64u-bridge",
                "--",
                str(venv_py),
                "-m",
                "c64u_bridge",
                "mcp",
            ]
        elif venv_mcp.is_file():
            cmd = [str(bin_path), "mcp", "add", *scope_flags, *env_flags, "c64u-bridge", "--", str(venv_mcp)]
        else:
            py_exe = shutil.which("python") or "python"
            cmd = [
                str(bin_path),
                "mcp",
                "add",
                *scope_flags,
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
            self.detect_cli(provider=prov)
            if res.returncode == 0:
                return True, out or f"Linked `c64u-bridge` MCP server to {disp_name}."
            return False, out or f"`{prov} mcp add` exited with code {res.returncode}"
        except Exception as exc:
            return False, f"Failed to register MCP server with {prov}: {exc}"

    def launch_interactive_terminal(
        self,
        initial_args: Optional[List[str]] = None,
        model: str = "",
        effort: str = "",
        provider: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Open `agy` or `claude` inside a visible OS terminal window rooted in the workspace."""
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        bin_path = self.find_binary(provider=prov)
        if not bin_path:
            return False, f"{disp_name} ({prov}) is not installed."
        extra: List[str] = []
        if model.strip():
            extra.extend(["--model", model.strip()])
        if effort.strip():
            extra.extend(["--effort", effort.strip()])
        if initial_args:
            extra.extend(initial_args)
        try:
            if os.name == "nt":
                subprocess.Popen(
                    [
                        "cmd.exe",
                        "/c",
                        "start",
                        f"{disp_name} ({prov}) — C64 Studio Live Sync",
                        "cmd.exe",
                        "/k",
                        str(bin_path),
                        *extra,
                    ],
                    cwd=self.workspace_dir,
                )
            elif platform.system() == "Darwin":
                escaped = " ".join(
                    [f'cd "{self.workspace_dir}" && "{bin_path}"', *[f'"{a}"' for a in extra]]
                )
                subprocess.Popen(["osascript", "-e", f'tell app "Terminal" to do script "{escaped}"'])
            else:
                for term in ("x-terminal-emulator", "gnome-terminal", "konsole", "xterm"):
                    if shutil.which(term):
                        subprocess.Popen([term, "-e", str(bin_path), *extra], cwd=self.workspace_dir)
                        break
                else:
                    return False, f"Run `{bin_path}` in your terminal to complete authentication."
            return True, f"Launched interactive {disp_name} terminal ({bin_path.name})."
        except Exception as exc:
            return False, f"Could not open terminal window: {exc}"

    @staticmethod
    def _summarize_tool_target(params: dict) -> str:
        """Format a short target hint for live CLI tool status display."""
        for key in ("Path", "TargetFile", "file_path", "path", "source_path", "prg_path", "sid_path", "output_path"):
            val = params.get(key)
            if isinstance(val, str) and val.strip():
                return Path(val.strip()).name
        for key in ("CommandLine", "command", "query", "action"):
            val = params.get(key)
            if isinstance(val, str) and val.strip():
                clean = " ".join(val.strip().split())
                return clean[:38] + ("..." if len(clean) > 38 else "")
        return ""

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
        provider: Optional[str] = None,
        on_line: Optional[Callable[[str], None]] = None,
        on_delta: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None,
        on_file_write: Optional[Callable[[Path, Optional[str]], None]] = None,
        on_file_edit_start: Optional[Callable[[Path], None]] = None,
    ) -> AgyPromptResult:
        """
        Execute a prompt via `agy` or `claude` (`--output-format stream-json -p`) in the workspace,
        streaming live tokens (`on_delta`), lines (`on_line`), tool/thinking status (`on_status`),
        and direct file writes (`on_file_write`) in real time.
        """
        prov = normalize_provider(provider or self.provider)
        disp_name = provider_display_name(prov)
        tag = provider_short_tag(prov)
        install_cmd, _ = install_commands_for_provider(prov)

        bin_path = self.find_binary(provider=prov)
        if not bin_path:
            return AgyPromptResult(
                success=False,
                response_text="",
                stderr="",
                return_code=-1,
                command=[],
                error_message=(
                    f"{disp_name} (`{prov}`) is not installed. Click 'CLI SETUP' to auto-install "
                    f"or run: {install_cmd}"
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
        if prov == "claude":
            claude_mode_map = {
                "accept-edits": "acceptEdits",
                "plan": "plan",
                "auto": "auto",
            }
            if exec_mode in claude_mode_map:
                cmd.extend(["--permission-mode", claude_mode_map[exec_mode]])
            if continue_conversation:
                cmd.append("--continue")
            if model.strip():
                cmd.extend(["--model", model.strip()])
            if effort.strip():
                cmd.extend(["--effort", effort.strip()])
            cmd.extend(["--output-format", "stream-json", "--verbose", "--include-partial-messages", "-p", full_prompt])
        else:
            if exec_mode in {"accept-edits", "plan", "auto"}:
                cmd.extend(["--mode", exec_mode])
            if continue_conversation:
                cmd.append("--continue")
            if model.strip():
                cmd.extend(["--model", model.strip()])
            if effort.strip():
                cmd.extend(["--effort", effort.strip()])
            cmd.extend(["--output-format", "stream-json", "-p", full_prompt])

        text_chunks: List[str] = []
        line_buffer = ""
        stderr_chunks: List[str] = []
        touched_files: List[Path] = []
        conv_id: Optional[str] = None
        result_error: Optional[str] = None
        saw_stream_deltas = False
        file_write_tools = {
            "write_file",
            "edit_file",
            "create_file",
            "replace_file_content",
            "multi_replace_file_content",
            "Write",
            "Edit",
            "MultiEdit",
            "write",
            "edit",
        }

        def _emit_delta(delta: str) -> None:
            nonlocal line_buffer
            if not delta:
                return
            text_chunks.append(delta)
            if on_delta is not None:
                on_delta(delta)
            if on_line is not None:
                line_buffer += delta
                while "\n" in line_buffer:
                    ln, line_buffer = line_buffer.split("\n", 1)
                    on_line(ln.rstrip("\r"))

        def _emit_status(msg: str) -> None:
            if on_status is not None and msg:
                on_status(msg)

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=self.workspace_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert proc.stdout is not None

            def _drain_stderr() -> None:
                if proc.stderr is not None:
                    try:
                        data = proc.stderr.read()
                        if data:
                            stderr_chunks.append(data)
                    except Exception:
                        pass

            stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
            stderr_thread.start()

            for raw_line in proc.stdout:
                clean_line = raw_line.rstrip("\r\n")
                if not clean_line:
                    continue

                parsed_evt = None
                stripped_ln = clean_line.lstrip()
                if stripped_ln.startswith("{"):
                    try:
                        cand = json.loads(stripped_ln)
                        if isinstance(cand, dict) and ("event" in cand or "type" in cand):
                            parsed_evt = cand
                    except Exception:
                        parsed_evt = None

                if parsed_evt is None:
                    # Plain-text stdout fallback (compatible with mocks or non-JSON CLI output)
                    _emit_delta(clean_line + "\n")
                    continue

                def _resolve_tool_path(params: dict) -> Optional[Path]:
                    raw_p = (
                        params.get("Path")
                        or params.get("TargetFile")
                        or params.get("file_path")
                        or params.get("path")
                    )
                    if isinstance(raw_p, str) and raw_p.strip():
                        p_obj = Path(raw_p.strip())
                        return (
                            p_obj if p_obj.is_absolute() else (self.workspace_dir / p_obj)
                        ).resolve()
                    return None

                def _record_file_write(resolved: Path, fallback_content: Optional[str] = None) -> None:
                    if resolved not in touched_files:
                        touched_files.append(resolved)
                    disk_txt: Optional[str] = None
                    if resolved.is_file():
                        try:
                            disk_txt = resolved.read_text(encoding="utf-8")
                        except Exception:
                            disk_txt = fallback_content
                    elif isinstance(fallback_content, str):
                        disk_txt = fallback_content
                    if on_file_write is not None:
                        on_file_write(resolved, disk_txt)

                if isinstance(parsed_evt.get("event"), str):
                    evt_type = parsed_evt.get("event")
                    if evt_type == "init":
                        conv_id = parsed_evt.get("conversation_id") or conv_id
                        short_id = conv_id[:8] if isinstance(conv_id, str) and conv_id else "ready"
                        _emit_status(f"{tag} CONNECTED ({short_id}) — READING C64 CONTEXT...")

                    elif evt_type == "step_update":
                        su = parsed_evt.get("step_update") or {}
                        step_type = su.get("step_type", "")
                        state = su.get("state", "")

                        if step_type == "user_input" and state == "DONE":
                            _emit_status(f"{tag} THINKING...")
                        elif su.get("thinking_delta"):
                            _emit_status(f"{tag} REASONING...")
                        elif step_type == "agent_response":
                            td = su.get("text_delta") or ""
                            if td:
                                saw_stream_deltas = True
                                _emit_delta(td)
                                _emit_status(f"{tag} STREAMING CODE...")
                            elif state == "DONE":
                                _emit_status(f"{tag} PREPARING NEXT STEP...")
                        elif step_type == "tool":
                            t_info = su.get("tool_info") or {}
                            t_name = su.get("tool_name") or t_info.get("name") or "tool"
                            params = t_info.get("parameters") or {}
                            target_hint = self._summarize_tool_target(params) if isinstance(params, dict) else ""
                            label = f"{t_name} ({target_hint})" if target_hint else t_name

                            if state == "ACTIVE":
                                _emit_status(f"{tag} TOOL: {label}")
                                if t_name in file_write_tools and isinstance(params, dict) and on_file_edit_start is not None:
                                    resolved = _resolve_tool_path(params)
                                    if resolved is not None:
                                        on_file_edit_start(resolved)
                            elif state == "DONE":
                                if t_name in file_write_tools and isinstance(params, dict):
                                    resolved = _resolve_tool_path(params)
                                    if resolved is not None:
                                        _record_file_write(resolved, params.get("Content") or params.get("content"))
                            elif state == "ERROR":
                                _emit_status(f"{tag} TOOL BLOCKED: {label}")

                    elif evt_type == "result":
                        res_obj = parsed_evt.get("result") or {}
                        conv_id = res_obj.get("conversation_id") or conv_id
                        final_resp = res_obj.get("response") or ""
                        if final_resp and not "".join(text_chunks).strip():
                            _emit_delta(final_resp)
                        status_val = res_obj.get("status")
                        if status_val not in (None, "SUCCESS"):
                            result_error = res_obj.get("error") or f"{disp_name} returned status: {status_val}"

                    elif evt_type == "error":
                        err_obj = parsed_evt.get("error")
                        result_error = str(err_obj) if err_obj else f"{disp_name} reported an error event."

                else:
                    # Claude Code CLI (`--output-format stream-json`) event schema
                    msg_type = parsed_evt.get("type")
                    if msg_type == "system":
                        conv_id = parsed_evt.get("session_id") or conv_id
                        if parsed_evt.get("subtype") == "init":
                            short_id = conv_id[:8] if isinstance(conv_id, str) and conv_id else "ready"
                            _emit_status(f"{tag} CONNECTED ({short_id}) — READING C64 CONTEXT...")

                    elif msg_type == "stream_event":
                        ev = parsed_evt.get("event") or {}
                        ev_t = ev.get("type")
                        if ev_t == "message_start":
                            _emit_status(f"{tag} THINKING...")
                        elif ev_t == "content_block_start":
                            cb = ev.get("content_block") or {}
                            if cb.get("type") == "tool_use":
                                t_name = cb.get("name") or "tool"
                                _emit_status(f"{tag} TOOL: {t_name}")
                            elif cb.get("type") == "thinking":
                                _emit_status(f"{tag} REASONING...")
                        elif ev_t == "content_block_delta":
                            delta_obj = ev.get("delta") or {}
                            d_type = delta_obj.get("type")
                            if d_type == "text_delta":
                                td = delta_obj.get("text") or ""
                                if td:
                                    saw_stream_deltas = True
                                    _emit_delta(td)
                                    _emit_status(f"{tag} STREAMING CODE...")
                            elif d_type == "thinking_delta":
                                _emit_status(f"{tag} REASONING...")

                    elif msg_type == "assistant":
                        msg_obj = parsed_evt.get("message") or {}
                        for block in msg_obj.get("content") or []:
                            if not isinstance(block, dict):
                                continue
                            b_type = block.get("type")
                            if b_type == "text" and not saw_stream_deltas:
                                txt = block.get("text") or ""
                                if txt:
                                    _emit_delta(txt)
                            elif b_type == "tool_use":
                                t_name = block.get("name") or "tool"
                                params = block.get("input") or {}
                                target_hint = self._summarize_tool_target(params) if isinstance(params, dict) else ""
                                label = f"{t_name} ({target_hint})" if target_hint else t_name
                                _emit_status(f"{tag} TOOL: {label}")
                                if t_name in file_write_tools and isinstance(params, dict):
                                    resolved = _resolve_tool_path(params)
                                    if resolved is not None:
                                        if on_file_edit_start is not None:
                                            on_file_edit_start(resolved)
                                        _record_file_write(resolved, params.get("content") or params.get("Content"))

                    elif msg_type == "user":
                        # Tool results returned to Claude
                        msg_obj = parsed_evt.get("message") or {}
                        for block in msg_obj.get("content") or []:
                            if isinstance(block, dict) and block.get("type") == "tool_result":
                                if block.get("is_error"):
                                    _emit_status(f"{tag} TOOL BLOCKED")
                                elif touched_files and on_file_write is not None:
                                    # Re-sync latest touched file once tool_result confirms disk write
                                    _record_file_write(touched_files[-1])

                    elif msg_type == "result":
                        conv_id = parsed_evt.get("session_id") or conv_id
                        final_resp = parsed_evt.get("result") or ""
                        if isinstance(final_resp, str) and final_resp and not "".join(text_chunks).strip():
                            _emit_delta(final_resp)
                        if parsed_evt.get("is_error"):
                            errs = parsed_evt.get("errors")
                            if isinstance(errs, list) and errs:
                                result_error = "; ".join(str(e) for e in errs)
                            else:
                                result_error = (final_resp if isinstance(final_resp, str) and final_resp else None) or f"{disp_name} returned an error."

                    elif msg_type == "error":
                        err_obj = parsed_evt.get("error")
                        result_error = str(err_obj) if err_obj else f"{disp_name} reported an error event."

            if line_buffer and on_line is not None:
                on_line(line_buffer.rstrip("\r"))
                line_buffer = ""

            rc = proc.wait()
            stderr_thread.join(timeout=2.0)
            stderr_text = "".join(stderr_chunks)
            response_text = "".join(text_chunks).strip()
            blocks = extract_code_blocks(response_text, preferred_mode=language_mode)

            # Fallback: if `agy` wrote code directly to a workspace file via write_file/edit_file
            # without repeating a fenced markdown block in chat, extract code from the written file.
            if not blocks and touched_files:
                for tf in reversed(touched_files):
                    if tf.is_file() and tf.suffix.lower() in {".asm", ".s", ".c", ".cpp", ".cc", ".cxx", ".py"}:
                        try:
                            file_code = tf.read_text(encoding="utf-8")
                            if file_code.strip():
                                ext_tag = tf.suffix.lstrip(".").lower()
                                f_mode = classify_code_block(ext_tag, file_code, preferred_mode=language_mode)
                                blocks.append(
                                    ExtractedCodeBlock(
                                        language_tag=ext_tag,
                                        studio_mode=f_mode,
                                        code=file_code if file_code.endswith("\n") else file_code + "\n",
                                    )
                                )
                                break
                        except Exception:
                            pass

            err_msg: Optional[str] = None
            has_silent_headless_failure = (
                not response_text and not blocks and not touched_files and bool(stderr_text.strip())
            )
            if rc != 0 or result_error or has_silent_headless_failure:
                err_msg = (
                    result_error
                    or stderr_text.strip()
                    or response_text
                    or f"{prov} exited with status {rc}"
                )
                if "permission" in err_msg.lower() and "headless" in err_msg.lower():
                    err_msg += (
                        "\n💡 Tip: Switch MODE from 'accept-edits' to 'auto' in the 5:AI HUB toolbar "
                        f"when you want {disp_name} to execute shell or hardware commands autonomously."
                    )

            return AgyPromptResult(
                success=(err_msg is None),
                response_text=response_text,
                stderr=stderr_text,
                return_code=rc,
                command=cmd,
                code_blocks=blocks,
                error_message=err_msg,
                touched_files=touched_files,
                conversation_id=conv_id,
            )
        except Exception as exc:
            return AgyPromptResult(
                success=False,
                response_text="".join(text_chunks),
                stderr="".join(stderr_chunks),
                return_code=-1,
                command=cmd,
                error_message=f"{disp_name} execution error: {exc}",
                touched_files=touched_files,
                conversation_id=conv_id,
            )
