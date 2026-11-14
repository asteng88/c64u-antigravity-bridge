"""
C64 Studio — Commodore 64 Multi-Language IDE, Game Studio & Antigravity AI Hub (Tkinter).

Provides an authentic Commodore 64 BASIC V2 screen experience with:
- Splash screen
- Bundled 'Pet Me 64' (`PetMe64.ttf`) bitmap font
  by Kreative Korporation / Kreative Software (Free Use License 1.2f)
- Full-featured 6502 KickAssembler (`.asm`) editor with syntax highlighting,
  line numbers, label navigator, find/goto, and one-touch DMA execution
- Python-to-6502 AST transpiler, D64/TAP/PRG/SID reverse decompiler,
  1541 D64 disk & TAP cassette mastering, and live C64U hardware inspection.
"""

from __future__ import annotations

import ast
import ctypes
import json
import os
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, simpledialog
from typing import Callable, Iterable, Optional

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from .agy_cli import (
    AGY_EFFORT_LEVELS,
    AI_PROVIDERS,
    DEFAULT_AGY_MODELS,
    DEFAULT_CLAUDE_MODELS,
    INSTALL_CMD_UNIX,
    INSTALL_CMD_WINDOWS_PS1,
    AgyCliConnector,
    AgyPromptResult,
    AgyStatus,
    ExtractedCodeBlock,
    default_models_for_provider,
    extract_streaming_code_preview,
    infer_prompt_language,
    install_commands_for_provider,
    normalize_provider,
    provider_display_name,
    provider_short_tag,
)
from .client import C64UClient
from .env import load_studio_settings, save_studio_settings
from .server import get_studio_event_journal_path
from .validation_report import DeploymentValidationReport, DeploymentValidator


def _tui_attr(name: str, default):
    tui_mod = sys.modules.get("c64u_bridge.tui")
    if tui_mod is not None and hasattr(tui_mod, name):
        return getattr(tui_mod, name)
    return default
from .compiler import CrossCompiler, KickAssVersionStatus
from .d64 import D64Disk, D64Entry, save_prg_to_d64
from .gamedev import GAME_TOOLS, default_target_dir, run_tool
from .project import (
    DEFINITION_KINDS,
    KIND_FILES,
    KIND_FOLDERS,
    KIND_LABELS,
    NEW_ASM_TEMPLATE,
    add_step,
    classify_file,
    create_definition,
    create_game,
    create_manifest,
    find_manifest,
)
from .prg_decompiler import (
    MediaStageInfo,
    PrgDecompileResult,
    decompile_d64_file,
    decompile_prg,
    decompile_tap_file,
    inspect_media_stages,
)
from .screen import format_screen
from .sid_compiler import compile_sid_source
from .sid_decompiler import SidDecompileError, decompile_sid_file
from .tap import save_prg_to_tap
from .themes import (
    FONT_CREDITS_TEXT,
    THEMES,
    get_asset_path,
    register_embedded_fonts,
)
from .transpiler import PRESETS, PythonTo6502Transpiler, TranspileResult


# ---------------------------------------------------------------------------
# 6502 Assembly Starter Template & Presets
# ---------------------------------------------------------------------------

ASM_OPCODES_PATTERN = re.compile(
    r"\b("
    r"lda|ldx|ldy|sta|stx|sty|jsr|jmp|rts|rti|sei|cli|pha|pla|php|plp|"
    r"inx|iny|dex|dey|inc|dec|adc|sbc|cmp|cpx|cpy|and|ora|eor|asl|lsr|"
    r"rol|ror|bit|bcc|bcs|beq|bne|bmi|bpl|bvc|bvs|clc|sec|cld|sed|clv|"
    r"tax|tay|txa|tya|tsx|txs|nop|brk"
    r")\b",
    re.IGNORECASE,
)

ASM_DIRECTIVES_PATTERN = re.compile(
    r"(BasicUpstart2|\.[a-zA-Z_][a-zA-Z0-9_]*|#import|#define|\*\s*=)"
)

ASM_HEX_PATTERN = re.compile(r"(#?\$[0-9A-Fa-f]+|#?%[01]+|\b0x[0-9A-Fa-f]+\b)")
ASM_HW_PATTERN = re.compile(
    r"\b(VIC_[A-Z0-9_]+|SID_[A-Z0-9_]+|CIA[12]_[A-Z0-9_]+|SCREEN_RAM|COLOR_RAM|KERNAL_[A-Z0-9_]+)\b"
)
ASM_LABEL_PATTERN = re.compile(r"^(\s*[!a-zA-Z_][a-zA-Z0-9_]*:)", re.MULTILINE)
ASM_COMMENT_PATTERN = re.compile(r"(//[^\n]*|;[^\n]*)", re.MULTILINE)
STRING_PATTERN = re.compile(r'("[^"\n]*"|\'[^\'\n]*\')')

PY_KEYWORDS_PATTERN = re.compile(
    r"\b(def|while|for|in|range|if|elif|else|break|continue|return|True|False|None|and|or|not|import|from)\b"
)
PY_INTRINSICS_PATTERN = re.compile(
    r"\b(poke|peek|border_color|background_color|wait_raster|clear_screen|print_str|print_char|sid_tone|delay|asm|COLOR_[A-Z_]+)\b"
)
PY_COMMENT_PATTERN = re.compile(r"(#[^\n]*)", re.MULTILINE)

C_KEYWORDS_PATTERN = re.compile(
    r"\b("
    r"auto|break|case|char|const|continue|default|do|double|else|enum|extern|"
    r"float|for|goto|if|inline|int|long|register|restrict|return|short|signed|"
    r"sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while|"
    r"uint8_t|uint16_t|uint32_t|int8_t|int16_t|int32_t|bool|true|false|"
    r"__asm|__interrupt|__export|__zeropage"
    r")\b"
)
C_PREPROC_PATTERN = re.compile(r"^\s*#\s*[a-zA-Z_]+[^\n]*", re.MULTILINE)
C_HW_PATTERN = re.compile(
    r"\b(VIC_[A-Z0-9_]+|SID_[A-Z0-9_]+|CIA[12]_[A-Z0-9_]+|SCREEN_RAM|COLOR_RAM|vic|sid|cia1|cia2)\b"
)
C_COMMENT_PATTERN = re.compile(r"(//[^\n]*|/\*[\s\S]*?\*/)", re.MULTILINE)

NEW_C_TEMPLATE = """// ============================================================================
// C64 STUDIO — C99 / C++ SOURCE FOR OSCAR64 OR CC65 (.C)
// Press F7 to Compile & Disassemble 6502, or F5 to Compile & DMA Run on C64U
// ============================================================================
#include <stdint.h>

#define VIC_RASTER   (*(volatile uint8_t*)0xD012)
#define VIC_BORDER   (*(volatile uint8_t*)0xD020)
#define VIC_BG0      (*(volatile uint8_t*)0xD021)
#define SCREEN_RAM   ((volatile uint8_t*)0x0400)
#define COLOR_RAM    ((volatile uint8_t*)0xD800)

int main(void) {
    VIC_BORDER = 14;  // Light Blue
    VIC_BG0    = 6;   // Dark Blue

    const uint8_t msg[] = {3, 54, 52, 32, 19, 20, 21, 4, 9, 15, 32, 3};
    for (uint8_t i = 0; i < sizeof(msg); ++i) {
        SCREEN_RAM[i] = msg[i];
        COLOR_RAM[i]  = 1;  // White
    }

    for (;;) {
        while (VIC_RASTER != 250) {}
        VIC_BORDER = 1;
        VIC_BORDER = 14;
    }
    return 0;
}
"""

NEW_PY_TEMPLATE = """# ============================================================================
# C64 STUDIO — PYTHON-TO-6502 BARE-METAL SOURCE (.PY)
# Press F6 to Transpile -> 6502 ASM, F7 to Compile, or F5 to Send to C64U
# ============================================================================

clear_screen()
border_color(COLOR_LIGHT_BLUE)
background_color(COLOR_BLUE)
print_str(10, 12, "HELLO FROM C64 STUDIO!", COLOR_WHITE)

while True:
    wait_raster(250)
    border_color(COLOR_YELLOW)
    border_color(COLOR_LIGHT_BLUE)
"""

NEW_SID_TEMPLATE = """// ============================================================================
// C64 STUDIO — MOS 6581 / 8580 PSID V2 MUSIC DRIVER (.SID)
// Press F7 to Compile & Test .SID, or F5 to Compile & Send to C64U SID Player
// ============================================================================
// C64U_SID_METADATA: {"magic": "PSID", "version": 2, "data_offset": 124, "load_address": 4096, "init_address": 4096, "play_address": 4099, "songs": 1, "start_song": 1, "speed": 0, "name": "C64 STUDIO SID", "author": "C64U BRIDGE", "released": "2026", "flags": 20, "embedded_load_address": true}

.const SID_LOAD         = $1000
.const SID_INIT         = $1000
.const SID_PLAY         = $1003
.const SID_SONGS        = 1
.const SID_DEFAULT_SONG = 1

.const SID_V1_FREQ_LO   = $D400
.const SID_V1_FREQ_HI   = $D401
.const SID_V1_PW_LO     = $D402
.const SID_V1_PW_HI     = $D403
.const SID_V1_CTRL      = $D404
.const SID_V1_AD        = $D405
.const SID_V1_SR        = $D406
.const SID_MODE_VOL     = $D418

* = SID_LOAD "SID Music Driver"

    jmp sid_init        // $1000: PSID Init entry point
    jmp sid_play        // $1003: PSID Play (50/60 Hz IRQ) entry point

sid_init:
    ldx #$18
    lda #$00
!clear_sid:
    sta $D400,x
    dex
    bpl !clear_sid-

    lda #$0f            // Master volume = 15
    sta SID_MODE_VOL
    lda #$00
    sta SID_V1_PW_LO
    lda #$08            // 50% pulse width ($0800)
    sta SID_V1_PW_HI
    lda #$09            // Crisp attack/decay
    sta SID_V1_AD
    lda #$a8            // Rich sustain/release
    sta SID_V1_SR
    lda #$00
    sta tick_cnt
    sta note_idx
    rts

sid_play:
    inc tick_cnt
    lda tick_cnt
    and #$07            // Step arpeggio every 8 frames
    bne !done+

    ldx note_idx
    lda note_lo,x
    sta SID_V1_FREQ_LO
    lda note_hi,x
    sta SID_V1_FREQ_HI
    lda #$41            // Pulse waveform + Gate ON
    sta SID_V1_CTRL

    inx
    txa
    and #$03
    sta note_idx
!done:
    rts

tick_cnt: .byte $00
note_idx: .byte $00
note_lo:  .byte $25, $af, $4b, $af   // C-4, E-4, G-4, E-4
note_hi:  .byte $11, $15, $1a, $15
"""


# ---------------------------------------------------------------------------
# Key Binding Metadata & Directory Filtering Helper
# ---------------------------------------------------------------------------

@dataclass
class KeyBindingDef:
    key: str
    action: str
    description: str
    show: bool = True


class FilteredDirectoryTree:
    """Directory helper filtered for Commodore 64 source code, disk, tape, and binary assets."""

    def __init__(self, path: str | Path = "."):
        self.path = Path(path)

    def filter_paths(self, paths: Iterable[Path]) -> list[Path]:
        ignored = {
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            ".agents",
            "build",
            "dist",
            ".idea",
            ".vscode",
        }
        supported = {".py", ".asm", ".s", ".sid", ".prg", ".tap", ".d64", ".c", ".cpp", ".cc", ".cxx", ".h", ".sym", ".bin"}
        filtered: list[Path] = []
        for p in paths:
            if p.name in ignored or p.name.startswith("."):
                continue
            if p.is_dir() or p.suffix.lower() in supported:
                filtered.append(p)
        return filtered


def center_popup(window: tk.Toplevel) -> None:
    """Center a popup window on the active display."""
    window.update_idletasks()
    width = max(window.winfo_width(), window.winfo_reqwidth())
    height = max(window.winfo_height(), window.winfo_reqheight())
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


# ---------------------------------------------------------------------------
# Retro C64 Modal Dialogs (Open File, Presets, Caution, Disk Select, Help/Credits)
# ---------------------------------------------------------------------------

class CopyrightCautionModal:
    """Ethical use and copyright caution prompt before reverse-decompiling D64/TAP/PRG media."""

    CAUTION_TEXT = (
        "ETHICAL USE & COPYRIGHT CAUTION\n"
        "────────────────────────────────────────────────────────────\n"
        "• Notice: This code could be subject to copyright, so the user\n"
        "  should only use it for technique review and self-improvement.\n\n"
        "• Ethical Principle: Do not copy someone else's hard work.\n"
        "  Learn from it, but don't be a thief!\n"
        "────────────────────────────────────────────────────────────\n"
        "Proceed with decompilation for technique evaluation?"
    )

    def __init__(self, filename: Optional[str] = None):
        self.target_name = filename or "selected media"
        self.message = f"Target: {self.target_name}\n\n{self.CAUTION_TEXT}"

    def show_tk(self, parent: "C64PythonToAsmApp", callback: Callable[[bool], None]) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("COPYRIGHT & ETHICAL USE CAUTION")
        dlg.geometry("760x380")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["warning"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ ! ETHICAL USE & COPYRIGHT CAUTION ! ]",
            font=(font_fam, 11, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["warning"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        msg_lbl = tk.Label(
            dlg,
            text=self.message,
            font=(font_fam, 9, "bold"),
            bg=str(t["paper"]),
            fg=str(t["accent_bright"]),
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=8,
        )
        msg_lbl.pack(fill=tk.BOTH, expand=True, padx=14)

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=18, pady=14)

        def proceed(_event=None):
            if dlg.winfo_exists():
                dlg.destroy()
            callback(True)

        def cancel(_event=None):
            if dlg.winfo_exists():
                dlg.destroy()
            callback(False)

        btn_ok = tk.Button(
            btn_row,
            text="✔ ACKNOWLEDGE & PROCEED (ENTER)",
            command=proceed,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        btn_ok.pack(side=tk.RIGHT, padx=(8, 0))
        self.proceed_btn = btn_ok
        self.proceed = proceed

        btn_cancel = tk.Button(
            btn_row,
            text="✖ CANCEL (ESC)",
            command=cancel,
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        btn_cancel.pack(side=tk.RIGHT)
        self.cancel_btn = btn_cancel
        self.cancel = cancel

        dlg.bind("<Return>", proceed)
        dlg.bind("<Escape>", cancel)
        center_popup(dlg)
        try:
            dlg.grab_set()
            btn_ok.focus_set()
        except tk.TclError:
            pass
        return dlg


class DiskSelectModal:
    """Modal listing all PRG files inside a 1541 .D64 disk image for selection."""

    def __init__(self, disk: D64Disk):
        self.disk = disk
        self.prg_entries = [e for e in disk.entries if e.is_prg]

    def show_tk(self, parent: "C64PythonToAsmApp", callback: Callable[[Optional[D64Entry]], None]) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title(f'1541 DIRECTORY // 0 "{self.disk.disk_name}" {self.disk.disk_id}')
        dlg.geometry("760x440")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text=f'0 "{self.disk.disk_name:<16}" {self.disk.disk_id} 2A  [SELECT PRG TO DECOMPILE]',
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        list_frame = tk.Frame(dlg, bg=str(t["paper"]))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        lb = tk.Listbox(
            list_frame,
            font=(font_fam, 10, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=str(t["accent"]),
            activestyle="none",
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(list_frame, command=lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=sb.set)

        for entry in self.prg_entries:
            lb.insert(
                tk.END,
                f'{entry.blocks:<4d} "{entry.filename}"{" " * max(1, 17 - len(entry.filename))}PRG   (T:{entry.track:02d} S:{entry.sector:02d})',
            )
        if self.prg_entries:
            lb.selection_set(0)

        def select_current(_event=None):
            sel = lb.curselection()
            idx = sel[0] if sel else 0
            chosen = self.prg_entries[idx] if 0 <= idx < len(self.prg_entries) else None
            if dlg.winfo_exists():
                dlg.destroy()
            callback(chosen)

        def cancel(_event=None):
            if dlg.winfo_exists():
                dlg.destroy()
            callback(None)

        lb.bind("<Double-Button-1>", select_current)
        lb.bind("<Return>", select_current)
        dlg.bind("<Escape>", cancel)

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=12)

        btn_sel = tk.Button(
            btn_row,
            text="LOAD & DECOMPILE SELECTED",
            command=select_current,
            font=(font_fam, 9, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        btn_sel.pack(side=tk.RIGHT, padx=(8, 0))
        self.select_btn = btn_sel
        self.listbox = lb
        self.select_current = select_current

        tk.Button(
            btn_row,
            text="CANCEL",
            command=cancel,
            font=(font_fam, 9, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["panel_fg"]),
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        center_popup(dlg)
        try:
            dlg.grab_set()
            lb.focus_set()
        except tk.TclError:
            pass
        return dlg


class DecompileScopeModal:
    """
    Modal asking the user whether to decompile the Loader, the Main Game, or Both
    when reverse-decompiling a .TAP cassette image or .D64 disk image into 6502 assembly.
    """

    def __init__(self, media_path: Path, stages: list[MediaStageInfo]):
        self.media_path = media_path
        self.stages = stages
        self.has_loader = any(s.role == "loader" for s in stages)
        self.has_main = any(s.role == "main" for s in stages)

    def show_tk(
        self,
        parent: "C64PythonToAsmApp",
        callback: Callable[[Optional[str], Optional[int]], None],
    ) -> tk.Toplevel:
        """
        Display the scope selection modal.
        Calls `callback(scope, stage_index)` where `scope` is `"main"`, `"loader"`, `"both"`,
        `"stage"` (with `stage_index`), or `None` if cancelled.
        """
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title(f'DECOMPILE TARGET // "{self.media_path.name.upper()}"')
        dlg.geometry("860x500")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text=f'[ SELECT 6502 DECOMPILATION SCOPE FOR "{self.media_path.name.upper()}" ]',
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 6))

        tk.Label(
            dlg,
            text=(
                "CHOOSE WHETHER TO DECOMPILE THE LOADER, THE MAIN GAME, OR BOTH INTO COMMENTED\n"
                "KICKASSEMBLER (.ASM) SOURCE (OR DOUBLE-CLICK ANY INDIVIDUAL STAGE BELOW):"
            ),
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["ink"]),
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=14, pady=(0, 6))

        list_frame = tk.Frame(dlg, bg=str(t["paper"]))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        lb = tk.Listbox(
            list_frame,
            font=(font_fam, 9, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=str(t["accent"]),
            activestyle="none",
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb = tk.Scrollbar(list_frame, command=lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=sb.set)

        for st in self.stages:
            role_tag = "[LOADER]" if st.role == "loader" else "[MAIN]  "
            lb.insert(
                tk.END,
                f"#{st.index + 1:<2d} {role_tag} {st.name:<28} ${st.load_address:04X}-${st.end_address:04X} ({st.size:,} BYTES)",
            )
        if self.stages:
            lb.selection_set(len(self.stages) - 1 if self.has_main else 0)

        def select_scope(scope: Optional[str], stage_idx: Optional[int] = None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            callback(scope, stage_idx)

        def select_highlighted_stage(_event=None) -> None:
            sel = lb.curselection()
            idx = sel[0] if sel else 0
            if 0 <= idx < len(self.stages):
                select_scope("stage", self.stages[idx].index)

        self.select_scope = select_scope
        self.listbox = lb

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(10, 14))

        self.both_btn = tk.Button(
            btn_row,
            text="[3] BOTH (LOADER + MAIN)",
            command=lambda: select_scope("both"),
            font=(font_fam, 8, "bold"),
            bg=str(t["accent"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        self.both_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.main_btn = tk.Button(
            btn_row,
            text="[1] MAIN GAME ONLY",
            command=lambda: select_scope("main"),
            font=(font_fam, 8, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        self.main_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.loader_btn = tk.Button(
            btn_row,
            text="[2] LOADER ONLY",
            command=lambda: select_scope("loader"),
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        self.loader_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.stage_btn = tk.Button(
            btn_row,
            text="[4] SELECTED STAGE",
            command=select_highlighted_stage,
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["panel_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        self.stage_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.cancel_btn = tk.Button(
            btn_row,
            text="✖ CANCEL",
            command=lambda: select_scope(None),
            font=(font_fam, 8, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        lb.bind("<Double-Button-1>", select_highlighted_stage)
        dlg.bind("1", lambda _e: select_scope("main"))
        dlg.bind("2", lambda _e: select_scope("loader"))
        dlg.bind("3", lambda _e: select_scope("both"))
        dlg.bind("<Return>", lambda _e: select_scope("both"))
        dlg.bind("<Escape>", lambda _e: select_scope(None))

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.both_btn.focus_set()
        except tk.TclError:
            pass
        return dlg


class KickAssUpdateModal:
    """
    Interactive C64 modal displaying KickAssembler version status, explaining decompilation
    architecture, and prompting the user to update KickAss.jar when a newer version is available.
    """

    def __init__(self, status: KickAssVersionStatus):
        self.status = status

    def show_tk(self, parent: "C64PythonToAsmApp", callback: Optional[Callable[[bool], None]] = None) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("KICKASSEMBLER VERSION & UPDATE MANAGER")
        dlg.geometry("800x430")
        border_col = str(t["warning"]) if self.status.update_available else str(t["border_idle"])
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=border_col)
        dlg.transient(parent.root)

        hdr_text = (
            "[ ! KICKASSEMBLER UPDATE AVAILABLE ! ]"
            if self.status.update_available
            else "[ KICKASSEMBLER VERSION & DECOMPILER STATUS ]"
        )
        tk.Label(
            dlg,
            text=hdr_text,
            font=(font_fam, 11, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["warning"]) if self.status.update_available else str(t["accent_bright"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        inst_v = f"v{self.status.installed_version}" if self.status.installed_version else "NOT INSTALLED"
        lat_v = f"v{self.status.latest_version}" if self.status.latest_version else "UNKNOWN (OFFLINE)"
        prompt_line = (
            f"A newer version of KickAssembler ({lat_v}) is available! Would you like to update now?"
            if self.status.update_available
            else f"Your KickAssembler installation ({inst_v}) is up to date with upstream ({lat_v}).\n"
                 "You can still re-download/reinstall the latest KickAss.jar below if desired."
        )

        body_text = (
            f"• Installed Version : {inst_v}\n"
            f"• Latest Upstream   : {lat_v} (http://theweb.dk/KickAssembler)\n"
            f"• Local JAR Path    : {self.status.jar_path}\n"
            "────────────────────────────────────────────────────────────────────\n"
            "• Decompiler Note   : KickAssembler (KickAss.jar) is a 6502 macro assembler\n"
            "  only and does not include a built-in disassembler/decompiler class.\n"
            "  C64-BRIDGE uses its built-in multi-pass 6502 Reverse Decompiler to emit\n"
            "  100% compatible KickAssembler v5.x syntax with educational hardware comments.\n"
            "────────────────────────────────────────────────────────────────────\n"
            f"{prompt_line}"
        )

        info_lbl = tk.Label(
            dlg,
            text=body_text,
            font=(font_fam, 9, "bold"),
            bg=str(t["paper"]),
            fg=str(t["ink"]),
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=8,
        )
        info_lbl.pack(fill=tk.BOTH, expand=True, padx=14)
        self.info_lbl = info_lbl

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=18, pady=14)

        def do_update(_event=None):
            if dlg.winfo_exists():
                dlg.destroy()
            parent._perform_kickass_update(callback=callback)

        def do_close(_event=None):
            if dlg.winfo_exists():
                dlg.destroy()
            if callback:
                callback(False)

        upd_label = (
            f"⬇ UPDATE TO V{self.status.latest_version or 'LATEST'} NOW (ENTER)"
            if self.status.update_available
            else "↻ RE-DOWNLOAD / UPDATE KICKASS.JAR"
        )
        btn_upd = tk.Button(
            btn_row,
            text=upd_label,
            command=do_update,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        btn_upd.pack(side=tk.RIGHT, padx=(8, 0))
        self.update_btn = btn_upd
        self.do_update = do_update

        btn_close = tk.Button(
            btn_row,
            text="✖ CLOSE / SKIP (ESC)",
            command=do_close,
            font=(font_fam, 9, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["panel_fg"]),
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        btn_close.pack(side=tk.RIGHT)
        self.close_btn = btn_close
        self.do_close = do_close

        if self.status.update_available:
            dlg.bind("<Return>", do_update)
        else:
            dlg.bind("<Return>", do_close)
        dlg.bind("<Escape>", do_close)

        center_popup(dlg)
        try:
            dlg.grab_set()
            btn_upd.focus_set() if self.status.update_available else btn_close.focus_set()
        except tk.TclError:
            pass
        return dlg



class AgySetupModal:
    """
    Interactive C64 Studio Setup & Walkthrough Modal for AI CLIs (`agy` & `claude`).
    Auto-detects both `agy` and `claude`, lets the user choose their active AI CLI,
    provides copyable install commands OR 1-click auto-download/install,
    assists with first-run authentication, and links the `c64u-bridge` MCP server.
    """

    def __init__(
        self,
        connector: AgyCliConnector,
        status: Optional[AgyStatus] = None,
        provider: Optional[str] = None,
        all_statuses: Optional[dict[str, AgyStatus]] = None,
    ):
        self.connector = connector
        inferred_prov = provider or (getattr(status, "provider", None) if status is not None else None) or connector.provider
        self.provider = normalize_provider(inferred_prov)
        self.status = status or connector.detect_cli(provider=self.provider)
        self.all_statuses: dict[str, AgyStatus] = dict(all_statuses or {})
        self.all_statuses[self.provider] = self.status

    def _build_walkthrough_text(self) -> str:
        s = self.status
        prov = self.provider
        disp = provider_display_name(prov)
        disp_upper = disp.upper()
        step1_state = (
            f"✓ DETECTED: {prov} v{s.version or 'installed'} ({s.binary_path})"
            if s.installed
            else "✗ NOT DETECTED ON PATH OR STANDARD INSTALL FOLDERS"
        )
        step3_state = (
            "✓ LINKED (`c64u-bridge` MCP active for hardware DMA & screen inspection)"
            if s.mcp_configured
            else "○ NOT YET LINKED (Click 'LINK C64U MCP' below for 1-click setup)"
        )
        tag = provider_short_tag(prov)
        if prov == "claude":
            auth_guide = (
                "  Guide   : On first run, `claude` opens an Anthropic sign-in prompt to authenticate.\n"
                "            Click '🔑 AUTH TERMINAL' if you haven't signed in to `claude` yet."
            )
        else:
            auth_guide = (
                "  Guide   : On first run, `agy` opens a browser sign-in prompt to authenticate.\n"
                "            Click '🔑 AUTH TERMINAL' if you haven't signed in to `agy` yet."
            )
        lines = [
            f"STEP 1 — {disp_upper} (`{prov}`) AUTO-DETECTION & INSTALLATION",
            f"  Status  : {step1_state}",
            f"  Command : {s.install_command}",
        ]
        if not s.installed:
            lines.append(
                f"  Action  : Click '⬇ AUTO-INSTALL {tag} CLI' to download & install automatically,\n"
                "            or click '📋 COPY INSTALL CMD' to run it in your own terminal."
            )
        lines.extend(
            [
                "────────────────────────────────────────────────────────────────────────────",
                "STEP 2 — SIGN IN / AUTHENTICATE (FIRST RUN ONLY)",
                auth_guide,
                "────────────────────────────────────────────────────────────────────────────",
                "STEP 3 — CONNECT C64U HARDWARE BRIDGE MCP SERVER",
                f"  Status  : {step3_state}",
                f"  Guide   : Linking `c64u-bridge` lets {disp} compile ASM/C/Python, push",
                "            via DMA to your C64U, and inspect Screen RAM automatically!",
            ]
        )
        return "\n".join(lines)

    def _format_provider_summary(self) -> str:
        parts = []
        for pid, _plabel in AI_PROVIDERS:
            st = self.all_statuses.get(pid)
            if st is None:
                parts.append(f"{pid}: ?")
            elif st.installed:
                ver = f"v{st.version}" if st.version else "ready"
                parts.append(f"{pid}: ✓ {ver}")
            else:
                parts.append(f"{pid}: ✗ not found")
        return "  |  ".join(parts)

    def show_tk(self, parent: "C64StudioApp", callback: Optional[Callable[[AgyStatus], None]] = None) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("C64 STUDIO // AI CLI SETUP & PROVIDER SELECTOR (AGY & CLAUDE)")
        dlg.geometry("940x650")
        border_col = str(t["success"]) if self.status.installed else str(t["warning"])
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=border_col)
        dlg.transient(parent.root)

        def _header_text() -> str:
            disp_upper = provider_display_name(self.provider).upper()
            if self.status.installed:
                return f"[ ✓ {disp_upper} (`{self.provider}`) CONNECTED — SETUP & MCP WIZARD ]"
            return f"[ ! {disp_upper} (`{self.provider}`) SETUP WALKTHROUGH ! ]"

        hdr_lbl = tk.Label(
            dlg,
            text=_header_text(),
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["success"]) if self.status.installed else str(t["warning"]),
            pady=8,
        )
        hdr_lbl.pack(fill=tk.X, padx=14, pady=(12, 6))
        self.hdr_lbl = hdr_lbl

        # Provider Selector Card (Antigravity `agy` vs Claude Code `claude`)
        prov_card = tk.Frame(
            dlg,
            bg=str(t["panel_bg"]),
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
            padx=12,
            pady=6,
        )
        prov_card.pack(fill=tk.X, padx=14, pady=(0, 6))

        tk.Label(
            prov_card,
            text="ACTIVE AI CLI:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
        ).pack(side=tk.LEFT, padx=(0, 8))

        modal_provider_var = tk.StringVar(master=dlg, value=self.provider)
        self.modal_provider_var = modal_provider_var
        provider_btns: dict[str, tk.Radiobutton] = {}

        provider_summary_lbl = tk.Label(
            prov_card,
            text=self._format_provider_summary(),
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["cyan"]),
            anchor="e",
        )
        provider_summary_lbl.pack(side=tk.RIGHT)
        self.provider_summary_lbl = provider_summary_lbl

        info_lbl = tk.Label(
            dlg,
            text=self._build_walkthrough_text(),
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["accent_bright"]),
            justify=tk.LEFT,
            anchor="w",
            padx=12,
            pady=8,
        )
        info_lbl.pack(fill=tk.BOTH, expand=True, padx=14)
        self.info_lbl = info_lbl

        status_bar = tk.Label(
            dlg,
            text=self.status.status_message,
            font=(font_fam, 8, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["cyan"]),
            anchor="w",
            padx=10,
            pady=6,
        )
        status_bar.pack(fill=tk.X, padx=14, pady=(0, 8))
        self.status_bar = status_bar

        # Persistent CLI Model & Reasoning Effort Options
        opts_card = tk.Frame(
            dlg,
            bg=str(t["panel_bg"]),
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
            padx=12,
            pady=8,
        )
        opts_card.pack(fill=tk.X, padx=14, pady=(0, 10))
        tk.Label(
            opts_card,
            text="CLI MODEL & EFFORT (SAVED AUTOMATICALLY FOR EVERY LAUNCH):",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))

        opts_row = tk.Frame(opts_card, bg=str(t["panel_bg"]))
        opts_row.pack(fill=tk.X)

        tk.Label(
            opts_row,
            text="MODEL:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
        ).pack(side=tk.LEFT, padx=(0, 6))

        models_list = list(self.status.models or default_models_for_provider(self.provider))
        cur_model = parent.agy_model_var.get().strip()
        if cur_model and all(mid != cur_model for mid, _ in models_list):
            models_list.append((cur_model, cur_model))
        model_display = {mid: (f"{lbl} [{mid}]" if mid else lbl) for mid, lbl in models_list}
        modal_model_var = tk.StringVar(
            master=dlg,
            value=model_display.get(cur_model, cur_model or "Default CLI Model"),
        )

        def _on_modal_model_pick(selected_label: str) -> None:
            chosen_id = ""
            for mid, disp in model_display.items():
                if disp == selected_label:
                    chosen_id = mid
                    break
            parent.agy_model_var.set(chosen_id)
            parent._refresh_agy_model_menu(models_list)
            status_bar.configure(
                text=f"✓ Saved CLI model: {chosen_id or 'Default CLI Model'} (effort: {parent.agy_effort_var.get()})"
            )

        model_menu = tk.OptionMenu(
            opts_row,
            modal_model_var,
            *[model_display[mid] for mid, _ in models_list],
            command=_on_modal_model_pick,
        )
        model_menu.config(
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
            relief=tk.FLAT,
            padx=6,
            pady=3,
        )
        model_menu.pack(side=tk.LEFT, padx=(0, 14))
        self.model_menu = model_menu
        self.modal_model_var = modal_model_var

        def _rebuild_modal_models(new_models: list[tuple[str, str]]) -> None:
            nonlocal models_list, model_display
            models_list = list(new_models or default_models_for_provider(self.provider))
            c_mod = parent.agy_model_var.get().strip()
            if c_mod and all(mid != c_mod for mid, _ in models_list):
                models_list.append((c_mod, c_mod))
            model_display = {mid: (f"{lbl} [{mid}]" if mid else lbl) for mid, lbl in models_list}
            m_menu = model_menu["menu"]
            m_menu.delete(0, tk.END)
            for mid, _ in models_list:
                disp = model_display[mid]
                m_menu.add_command(
                    label=disp,
                    command=lambda d=disp: (
                        modal_model_var.set(d),
                        _on_modal_model_pick(d),
                    ),
                )
            modal_model_var.set(model_display.get(c_mod, c_mod or "Default CLI Model"))

        tk.Label(
            opts_row,
            text="EFFORT:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
        ).pack(side=tk.LEFT, padx=(0, 6))

        def _on_modal_effort_pick(val: str) -> None:
            parent.agy_effort_var.set(val)
            status_bar.configure(
                text=f"✓ Saved CLI effort: {val} (model: {parent.agy_model_var.get() or 'Default CLI Model'})"
            )

        effort_menu = tk.OptionMenu(
            opts_row,
            parent.agy_effort_var,
            *AGY_EFFORT_LEVELS,
            command=_on_modal_effort_pick,
        )
        effort_menu.config(
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
            relief=tk.FLAT,
            padx=6,
            pady=3,
        )
        effort_menu.pack(side=tk.LEFT)
        self.effort_menu = effort_menu

        def _refresh_ui(msg: Optional[str] = None, detect_all: bool = False) -> None:
            if detect_all:
                self.all_statuses = self.connector.detect_all_clis()
                self.status = self.all_statuses[self.provider]
            else:
                self.status = self.connector.detect_cli(provider=self.provider)
                self.all_statuses[self.provider] = self.status
            if hasattr(parent, "cli_statuses"):
                parent.cli_statuses.update(self.all_statuses)
            parent._refresh_agy_badge(self.status)
            if not dlg.winfo_exists():
                return
            tag = provider_short_tag(self.provider)
            dlg.configure(
                highlightbackground=str(t["success"]) if self.status.installed else str(t["warning"])
            )
            hdr_lbl.configure(
                text=_header_text(),
                fg=str(t["success"]) if self.status.installed else str(t["warning"]),
            )
            provider_summary_lbl.configure(text=self._format_provider_summary())
            info_lbl.configure(text=self._build_walkthrough_text())
            status_bar.configure(text=msg or self.status.status_message)
            btn_install.configure(
                text=f"↻ UPDATE {tag} CLI" if self.status.installed else f"⬇ AUTO-INSTALL {tag} CLI"
            )
            _rebuild_modal_models(self.status.models)

        def _on_provider_select() -> None:
            chosen_prov = normalize_provider(modal_provider_var.get())
            self.provider = chosen_prov
            if hasattr(parent, "set_ai_provider"):
                parent.set_ai_provider(chosen_prov, detect=False)
            else:
                self.connector.provider = chosen_prov
            if chosen_prov in self.all_statuses:
                self.status = self.all_statuses[chosen_prov]
            else:
                self.status = self.connector.detect_cli(provider=chosen_prov)
                self.all_statuses[chosen_prov] = self.status
            _refresh_ui(detect_all=False)
            parent.notify(f"ACTIVE AI CLI: {provider_display_name(chosen_prov).upper()}")

        for pid, plabel in AI_PROVIDERS:
            rb = tk.Radiobutton(
                prov_card,
                text=plabel,
                variable=modal_provider_var,
                value=pid,
                command=_on_provider_select,
                font=(font_fam, 8, "bold"),
                bg=str(t["panel_bg"]),
                fg=str(t["accent_bright"]),
                selectcolor=str(t["editor_bg"]),
                activebackground=str(t["panel_bg"]),
                activeforeground=str(t["cyan"]),
                indicatoron=True,
                cursor="hand2",
            )
            rb.pack(side=tk.LEFT, padx=(0, 12))
            provider_btns[pid] = rb
        self.provider_buttons = provider_btns

        def do_redetect() -> None:
            _refresh_ui(detect_all=True)
            tag = provider_short_tag(self.provider)
            parent.notify(
                f"{tag} CLI {'DETECTED v' + (self.status.version or '') if self.status.installed else 'NOT FOUND'}"
            )

        def do_copy_cmd() -> None:
            dlg.clipboard_clear()
            dlg.clipboard_append(self.status.install_command)
            status_bar.configure(text=f"✓ Copied install command to clipboard: {self.status.install_command}")
            parent.notify(f"COPIED {provider_short_tag(self.provider)} INSTALL COMMAND TO CLIPBOARD")

        def do_install_or_update() -> None:
            btn_install.configure(state=tk.DISABLED, text="⏳ WORKING...")
            disp = provider_display_name(self.provider)
            status_bar.configure(text=f"Running official {disp} installer/updater... please wait.")

            def _worker() -> None:
                if self.status.installed:
                    ok, msg = self.connector.update_cli(provider=self.provider)
                else:
                    ok, msg = self.connector.install_cli(
                        progress_callback=lambda m: parent.root.after(
                            0, lambda line=m: status_bar.configure(text=line) if dlg.winfo_exists() else None
                        ),
                        provider=self.provider,
                    )

                def _done() -> None:
                    parent._write_log(f"{'✓' if ok else '✗'} {disp}: {msg}")
                    parent.notify(msg[:56].upper(), severity="information" if ok else "error")
                    if dlg.winfo_exists():
                        btn_install.configure(state=tk.NORMAL)
                        _refresh_ui(msg)

                if getattr(parent, "_in_mainloop", False):
                    parent.root.after(0, _done)
                else:
                    _done()

            if getattr(parent, "_in_mainloop", False):
                threading.Thread(target=_worker, daemon=True).start()
            else:
                _worker()

        def do_auth_terminal() -> None:
            ok, msg = self.connector.launch_interactive_terminal(provider=self.provider)
            status_bar.configure(text=msg)
            parent._write_log(f"{'✓' if ok else 'ℹ'} {msg}")

        def do_link_mcp() -> None:
            ok, msg = self.connector.register_c64u_mcp(
                host=parent.client.host,
                port=parent.client.port,
                provider=self.provider,
            )
            parent._write_log(f"{'✓' if ok else '✗'} {msg}")
            _refresh_ui(msg)

        def do_close(_event=None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            if callback:
                callback(self.status)

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(2, 12))

        init_tag = provider_short_tag(self.provider)
        btn_install = tk.Button(
            btn_row,
            text=f"↻ UPDATE {init_tag} CLI" if self.status.installed else f"⬇ AUTO-INSTALL {init_tag} CLI",
            command=do_install_or_update,
            font=(font_fam, 8, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        btn_install.pack(side=tk.LEFT, padx=(0, 6))
        self.install_btn = btn_install

        btn_copy = tk.Button(
            btn_row,
            text="📋 COPY INSTALL CMD",
            command=do_copy_cmd,
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        btn_copy.pack(side=tk.LEFT, padx=(0, 6))
        self.copy_btn = btn_copy

        btn_auth = tk.Button(
            btn_row,
            text="🔑 AUTH TERMINAL",
            command=do_auth_terminal,
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        btn_auth.pack(side=tk.LEFT, padx=(0, 6))
        self.auth_btn = btn_auth

        btn_mcp = tk.Button(
            btn_row,
            text="🔗 LINK C64U MCP",
            command=do_link_mcp,
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        btn_mcp.pack(side=tk.LEFT, padx=(0, 6))
        self.mcp_btn = btn_mcp

        btn_detect = tk.Button(
            btn_row,
            text="🔍 RE-DETECT",
            command=do_redetect,
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["panel_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor="hand2",
        )
        btn_detect.pack(side=tk.LEFT)
        self.redetect_btn = btn_detect

        btn_close = tk.Button(
            btn_row,
            text="✖ CLOSE (ESC)",
            command=do_close,
            font=(font_fam, 8, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=12,
            pady=6,
            cursor="hand2",
        )
        btn_close.pack(side=tk.RIGHT)
        self.close_btn = btn_close

        dlg.bind("<Escape>", do_close)
        center_popup(dlg)
        try:
            dlg.grab_set()
            btn_install.focus_set()
        except tk.TclError:
            pass
        return dlg


class OpenFileModal:
    """Retro C64 Project File Browser Modal supporting C, Python, 6502 ASM, SID, and Disk/Tape media."""

    TYPE_FILTERS: dict[str, Optional[set[str]]] = {
        "all": None,
        "build": {".py"},
        "asm": {".asm", ".s"},
        "c": {".c", ".cpp", ".cc", ".cxx", ".h"},
        "py": {".py"},
        "sid": {".sid"},
        "media": {".prg", ".tap", ".d64", ".bin"},
    }

    def __init__(self, initial_path: Optional[Path] = None, initial_filter: str = "all"):
        self.current_root = initial_path or Path.cwd()
        self.selected_file: Optional[Path] = None
        self.active_type_filter: str = initial_filter if initial_filter in self.TYPE_FILTERS else "all"
        self.tree_helper = FilteredDirectoryTree(self.current_root)
        self.filter_buttons: dict[str, tk.Button] = {}

    def show_tk(self, parent: "C64PythonToAsmApp", callback: Callable[[Optional[Path]], None]) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title('LOAD "$",8 // C64 STUDIO FILE LOADER (C, PY, ASM, SID)')
        dlg.geometry("920x590")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ LOAD FILE INTO IDE CODE WINDOW — C / PY / ASM / SID ]",
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(12, 6))

        jump_bar = tk.Frame(dlg, bg=str(t["paper"]))
        jump_bar.pack(fill=tk.X, padx=14, pady=3)

        filter_bar = tk.Frame(dlg, bg=str(t["panel_bg"]), padx=8, pady=4, highlightthickness=1, highlightbackground=str(t["accent"]))
        filter_bar.pack(fill=tk.X, padx=14, pady=3)

        tk.Label(
            filter_bar,
            text="FILE TYPE:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
        ).pack(side=tk.LEFT, padx=(0, 8))

        entries_map: list[Path] = []

        lbl_dir = tk.Label(
            dlg,
            text=f"DIR: {self.current_root}",
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["accent_bright"]),
            anchor="w",
        )
        lbl_dir.pack(fill=tk.X, padx=14, pady=(2, 4))

        list_frame = tk.Frame(dlg, bg=str(t["paper"]))
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        lb = tk.Listbox(
            list_frame,
            font=(font_fam, 9, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=str(t["accent"]),
            activestyle="none",
        )
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox = lb

        sb = tk.Scrollbar(list_frame, command=lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=sb.set)

        lbl_preview = tk.Label(
            dlg,
            text="CHOOSE A .C, .PY, .ASM, OR .SID FILE TO LOAD INTO THE IDE EDITOR",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["success"]),
            pady=5,
        )
        lbl_preview.pack(fill=tk.X, padx=14, pady=4)

        def _sync_filter_styles() -> None:
            for fkey, fbtn in self.filter_buttons.items():
                is_act = fkey == self.active_type_filter
                fbtn.configure(
                    bg=str(t["button_active_bg"]) if is_act else str(t["button_bg"]),
                    fg=str(t["button_active_fg"]) if is_act else str(t["button_fg"]),
                )

        def populate(folder: Path):
            if not folder.exists() or not folder.is_dir():
                return
            self.current_root = folder.resolve()
            lbl_dir.configure(text=f'DRIVE 8 PATH: "{self.current_root}"')
            lb.delete(0, tk.END)
            entries_map.clear()

            if self.current_root.parent != self.current_root:
                entries_map.append(self.current_root.parent)
                lb.insert(tk.END, "[DIR] .. (PARENT DIRECTORY)")

            allowed_exts = self.TYPE_FILTERS.get(self.active_type_filter)
            try:
                raw_children = sorted(
                    self.current_root.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
                filtered = self.tree_helper.filter_paths(raw_children)
                for p in filtered:
                    if p.is_file() and allowed_exts is not None:
                        suf = p.suffix.lower()
                        if self.active_type_filter == "build":
                            if p.name.lower() != "build.py":
                                continue
                        elif self.active_type_filter == "sid" and suf in (".asm", ".py"):
                            try:
                                head_chunk = p.read_text(encoding="utf-8", errors="ignore")[:512]
                            except OSError:
                                head_chunk = ""
                            if "C64U_SID_METADATA:" not in head_chunk:
                                continue
                        elif suf not in allowed_exts:
                            continue
                    entries_map.append(p)
                    if p.is_dir():
                        lb.insert(tk.END, f"[DIR] {p.name.upper()}/")
                    else:
                        sz = p.stat().st_size
                        blocks = max(1, (sz + 253) // 254)
                        ext_tag = "BUILD" if p.name.lower() == "build.py" else (p.suffix.upper().lstrip(".") or "FILE")
                        lb.insert(tk.END, f'{blocks:<4d} "{p.name:<28}" {ext_tag:<5} ({sz} BYTES)')
            except OSError:
                pass

        def set_type_filter(ftype: str) -> None:
            if ftype not in self.TYPE_FILTERS:
                return
            self.active_type_filter = ftype
            _sync_filter_styles()
            populate(self.current_root)

        self.set_type_filter = set_type_filter

        for fkey, flbl in (
            ("all", "ALL"),
            ("build", "BUILD.PY"),
            ("c", "C (.C)"),
            ("py", "PYTHON (.PY)"),
            ("asm", "6502 (.ASM)"),
            ("sid", "SID (.SID)"),
            ("media", "PRG / D64 / TAP"),
        ):
            fb = tk.Button(
                filter_bar,
                text=flbl,
                command=lambda k=fkey: set_type_filter(k),
                font=(font_fam, 8, "bold"),
                relief=tk.FLAT,
                padx=8,
                pady=3,
                cursor="hand2",
            )
            fb.pack(side=tk.LEFT, padx=(0, 4))
            self.filter_buttons[fkey] = fb
        _sync_filter_styles()

        def on_select(_event=None):
            sel = lb.curselection()
            if not sel:
                return
            p = entries_map[sel[0]]
            if p.is_file():
                self.selected_file = p
                if p.name.lower() == "build.py":
                    lbl_preview.configure(
                        text=f"SELECTED: {p.name} ({p.stat().st_size} BYTES) — DIRECTS FULL GAME COMPILATION [F7 / F5]"
                    )
                else:
                    lbl_preview.configure(text=f"SELECTED: {p.name} ({p.stat().st_size} BYTES) — ENTER TO DISPLAY IN IDE")
            else:
                lbl_preview.configure(text=f"FOLDER: {p.name}/ (DOUBLE-CLICK OR ENTER TO OPEN)")

        def on_activate(_event=None):
            sel = lb.curselection()
            if not sel:
                return
            p = entries_map[sel[0]]
            if p.is_dir():
                populate(p)
            elif p.is_file():
                self.selected_file = p
                if dlg.winfo_exists():
                    dlg.destroy()
                callback(p)

        def browse_os_dialog():
            chosen = filedialog.askopenfilename(
                parent=dlg,
                initialdir=str(self.current_root),
                title="Select Commodore 64 Source (C, Py, ASM, SID) or Media File",
                filetypes=[
                    ("All C64 Studio Files", "*.c *.cpp *.h *.py *.asm *.s *.sid *.prg *.tap *.d64 *.bin"),
                    ("C / Oscar64 (.c, .cpp, .h)", "*.c *.cpp *.cc *.cxx *.h"),
                    ("Python 6502 Dialect (.py)", "*.py"),
                    ("6502 Assembly (.asm, .s)", "*.asm *.s"),
                    ("SID Music (.sid)", "*.sid"),
                    ("C64 Disk / Tape / PRG (.d64, .tap, .prg)", "*.d64 *.tap *.prg"),
                    ("All Files", "*.*"),
                ],
            )
            if chosen:
                if dlg.winfo_exists():
                    dlg.destroy()
                callback(Path(chosen))

        for label, target in (
            ("> GAME_DEV/", Path.cwd() / "game_dev"),
            ("> EXAMPLE_GAMES/", Path.cwd() / "example_games"),
            ("> EXAMPLES/", Path.cwd() / "examples"),
            ("> WORKSPACE", Path.cwd()),
        ):
            tk.Button(
                jump_bar,
                text=label,
                command=lambda p=target: populate(p if p.exists() else Path.cwd()),
                font=(font_fam, 8, "bold"),
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                relief=tk.FLAT,
                padx=10,
                pady=4,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(
            jump_bar,
            text="OS FILE DIALOG...",
            command=browse_os_dialog,
            font=(font_fam, 8, "bold"),
            bg=str(t["accent"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        lb.bind("<<ListboxSelect>>", on_select)
        lb.bind("<Double-Button-1>", on_activate)
        lb.bind("<Return>", on_activate)
        dlg.bind("<Escape>", lambda _e: (dlg.destroy(), callback(None)))

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=10)

        self.load_btn = tk.Button(
            btn_row,
            text="LOAD INTO IDE [ENTER]",
            command=on_activate,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.load_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.cancel_btn = tk.Button(
            btn_row,
            text="CANCEL [ESC]",
            command=lambda: (dlg.destroy(), callback(None)),
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        populate(self.current_root if self.current_root.exists() else Path.cwd())
        center_popup(dlg)
        try:
            dlg.grab_set()
            lb.focus_set()
        except tk.TclError:
            pass
        return dlg


class NewFileModal:
    """Modal allowing the user to create a New File of type C, Python, 6502 ASM, or SID in the IDE."""

    def show_tk(
        self,
        parent: "C64StudioApp",
        callback: Optional[Callable[[Optional[str]], None]] = None,
    ) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("NEW C64 STUDIO FILE // CHOOSE LANGUAGE OR SID")
        dlg.geometry("760x430")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ CREATE NEW FILE IN IDE — CHOOSE TYPE ]",
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 6))

        tk.Label(
            dlg,
            text=(
                "SELECT THE SOURCE TYPE TO OPEN IN THE C64 STUDIO CODE EDITOR.\n"
                "PRESS F7 TO TEST COMPILE, OR F5 TO COMPILE & SEND DIRECTLY TO C64U:"
            ),
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["ink"]),
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, padx=16, pady=(0, 8))

        cards = tk.Frame(dlg, bg=str(t["paper"]))
        cards.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)

        def _pick(choice: Optional[str]) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            if choice == "c":
                parent.action_new_c_template()
            elif choice == "py":
                parent.action_new_py_template()
            elif choice == "asm":
                parent.action_new_asm_template()
            elif choice == "sid":
                parent.action_new_sid_template()
            if callback:
                callback(choice)

        self.pick = _pick
        specs = [
            ("c", "btn_c", "[1] C SOURCE (.C)          — OSCAR64 / CC65 OPTIMIZING COMPILER"),
            ("py", "btn_py", "[2] PYTHON (.PY)           — MOS 6502 BARE-METAL TRANSPILER"),
            ("asm", "btn_asm", "[3] 6502 ASSEMBLY (.ASM)   — KICKASSEMBLER V5.X NATIVE"),
            ("sid", "btn_sid", "[4] SID MUSIC (.SID)       — MOS 6581/8580 PSID V2 DRIVER"),
        ]
        for code, attr_name, label_txt in specs:
            b = tk.Button(
                cards,
                text=label_txt,
                command=lambda k=code: _pick(k),
                font=(font_fam, 9, "bold"),
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                activebackground=str(t["button_active_bg"]),
                activeforeground=str(t["button_active_fg"]),
                relief=tk.FLAT,
                anchor="w",
                padx=14,
                pady=9,
                cursor="hand2",
            )
            b.pack(fill=tk.X, pady=4)
            setattr(self, attr_name, b)

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=16, pady=(6, 14))

        self.cancel_btn = tk.Button(
            btn_row,
            text="CANCEL [ESC]",
            command=lambda: _pick(None),
            font=(font_fam, 8, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        dlg.bind("1", lambda _e: _pick("c"))
        dlg.bind("2", lambda _e: _pick("py"))
        dlg.bind("3", lambda _e: _pick("asm"))
        dlg.bind("4", lambda _e: _pick("sid"))
        dlg.bind("<Escape>", lambda _e: _pick(None))

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.btn_asm.focus_set()
        except tk.TclError:
            pass
        return dlg


class CompileErrorFixModal:
    """
    Modal shown whenever a SID, ASM, C, Python, or Game build fails its compile test.
    Asks the user whether to send the issue to Antigravity CLI (`agy`) for auto-fix
    or jump directly into the IDE code editor to fix it manually.
    """

    def __init__(self, stage_title: str, error_detail: str, lang_mode: str):
        self.stage_title = stage_title
        self.error_detail = error_detail.strip() or "Unknown compiler/assembler error."
        self.lang_mode = lang_mode
        self.dlg: Optional[tk.Toplevel] = None

    def show_tk(
        self,
        parent: "C64StudioApp",
        callback: Optional[Callable[[bool], None]] = None,
    ) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title(f"COMPILE TEST FAILED // {self.stage_title}")
        dlg.geometry("860x470")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["danger"]))
        dlg.transient(parent.root)

        self.hdr_lbl = tk.Label(
            dlg,
            text=f"[ ! COMPILE TEST FAILED — {self.stage_title} ! ]",
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["warning"]),
            pady=8,
        )
        self.hdr_lbl.pack(fill=tk.X, padx=14, pady=(14, 6))

        prov = parent._active_provider() if hasattr(parent, "_active_provider") else "agy"
        disp_upper = provider_display_name(prov).upper()
        prov_brand = "CLAUDE" if prov == "claude" else "ANTIGRAVITY"

        self.prompt_lbl = tk.Label(
            dlg,
            text=(
                "COMPILATION DID NOT SUCCEED.\n"
                f"WOULD YOU LIKE TO SEND THIS ISSUE TO {disp_upper} (`{prov}`) TO BE AUTO-FIXED,\n"
                "OR RETURN TO THE IDE CODE EDITOR TO FIX IT YOURSELF?"
            ),
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["accent_bright"]),
            justify=tk.LEFT,
            anchor="w",
        )
        self.prompt_lbl.pack(fill=tk.X, padx=14, pady=(0, 6))

        err_wrap = tk.Frame(dlg, bg=str(t["editor_bg"]), highlightthickness=1, highlightbackground=str(t["accent"]))
        err_wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        sb = tk.Scrollbar(err_wrap)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        err_box = tk.Text(
            err_wrap,
            font=(font_fam, 8, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            wrap="word",
            bd=0,
            padx=10,
            pady=8,
            yscrollcommand=sb.set,
        )
        err_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=err_box.yview)
        err_box.insert("1.0", self.error_detail)
        err_box.configure(state="disabled")
        self.error_box = err_box

        def choose_autofix(_event=None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            parent.action_autofix_compile_error(self.stage_title, self.error_detail, self.lang_mode)
            if callback:
                callback(True)

        def choose_manual(_event=None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            parent._focus_ide_at_compile_error(self.error_detail, self.lang_mode)
            if callback:
                callback(False)

        self.choose_autofix = choose_autofix
        self.choose_manual = choose_manual

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(8, 14))

        self.autofix_btn = tk.Button(
            btn_row,
            text=f"▶ YES — AUTO-FIX WITH {prov_brand} [ENTER]",
            command=choose_autofix,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.autofix_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.fix_in_ide_btn = tk.Button(
            btn_row,
            text="NO — FIX MYSELF IN IDE [ESC]",
            command=choose_manual,
            font=(font_fam, 9, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.fix_in_ide_btn.pack(side=tk.RIGHT)

        dlg.bind("<Return>", choose_autofix)
        dlg.bind("<Escape>", choose_manual)

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.autofix_btn.focus_set()
        except tk.TclError:
            pass
        return dlg


class GameAssetGenModal:
    """
    Game Generation Studio Modal providing AI-assisted VIC-II Sprite, SID SFX/Music,
    Tileset/Screen, and Playable Mini-Game generation plus direct access to Sprite Studio.
    """

    PRESETS: dict[str, tuple[str, str, str]] = {
        "sprites": (
            "VIC-II SPRITES (24x21 / MULTICOLOR)",
            "asm",
            "Animated player spaceship + thruster frame + alien enemy sprite at $2000",
        ),
        "sfx_sid": (
            "SID SOUND EFFECTS / GAME MUSIC (.SID)",
            "sid",
            "Upbeat C64 arcade chiptune loop with pulse lead and bassline",
        ),
        "tiles_screen": (
            "CHARSET TILES + GAME LEVEL SCREEN",
            "asm",
            "Starfield + sci-fi platformer HUD and custom 8x8 tile characters",
        ),
        "full_game": (
            "PLAYABLE C64 ARCADE GAME",
            "asm",
            "Playable joystick-port-2 space shooter with hardware sprites and SID laser SFX",
        ),
    }

    def __init__(self, initial_kind: str = "sprites"):
        self.initial_kind = initial_kind if initial_kind in self.PRESETS else "sprites"
        self.kind_buttons: dict[str, tk.Button] = {}

    def show_tk(self, parent: "C64StudioApp") -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("C64 GAME GENERATION STUDIO // SPRITES, SID SFX & GAME BUILDER")
        dlg.geometry("900x520")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ C64 GAME GENERATION TOOLS — SPRITES, TILES, SID & MINI-GAMES ]",
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        kind_frame = tk.Frame(dlg, bg=str(t["panel_bg"]), padx=10, pady=8, highlightthickness=1, highlightbackground=str(t["accent"]))
        kind_frame.pack(fill=tk.X, padx=14, pady=(0, 8))

        tk.Label(
            kind_frame,
            text="1. CHOOSE WHAT TO GENERATE:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 6))

        self.kind_var = tk.StringVar(value=self.initial_kind)
        _, init_fmt, init_desc = self.PRESETS[self.initial_kind]
        self.target_fmt_var = tk.StringVar(value=init_fmt)
        self.desc_var = tk.StringVar(value=init_desc)

        kind_grid = tk.Frame(kind_frame, bg=str(t["panel_bg"]))
        kind_grid.pack(fill=tk.X)
        kind_grid.columnconfigure(0, weight=1)
        kind_grid.columnconfigure(1, weight=1)

        def _sync_kind_btns() -> None:
            cur = self.kind_var.get()
            for k, btn in self.kind_buttons.items():
                is_sel = k == cur
                btn.configure(
                    bg=str(t["button_active_bg"]) if is_sel else str(t["editor_bg"]),
                    fg=str(t["button_active_fg"]) if is_sel else str(t["ink"]),
                )

        def select_kind(k: str) -> None:
            if k not in self.PRESETS:
                return
            self.kind_var.set(k)
            _, def_fmt, def_desc = self.PRESETS[k]
            self.target_fmt_var.set(def_fmt)
            self.desc_var.set(def_desc)
            _sync_kind_btns()

        self.select_kind = select_kind

        for idx, (k, (title_txt, _, _)) in enumerate(self.PRESETS.items()):
            kb = tk.Button(
                kind_grid,
                text=title_txt,
                command=lambda key=k: select_kind(key),
                font=(font_fam, 8, "bold"),
                relief=tk.FLAT,
                anchor="w",
                padx=10,
                pady=6,
                cursor="hand2",
            )
            kb.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=3, pady=3)
            self.kind_buttons[k] = kb
        _sync_kind_btns()

        spec_card = tk.Frame(dlg, bg=str(t["panel_bg"]), padx=10, pady=8, highlightthickness=1, highlightbackground=str(t["accent"]))
        spec_card.pack(fill=tk.X, padx=14, pady=(0, 8))

        fmt_row = tk.Frame(spec_card, bg=str(t["panel_bg"]))
        fmt_row.pack(fill=tk.X, pady=(0, 6))
        tk.Label(
            fmt_row,
            text="2. OUTPUT TARGET:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
        ).pack(side=tk.LEFT, padx=(0, 8))

        fmt_menu = tk.OptionMenu(fmt_row, self.target_fmt_var, "asm", "py", "c", "sid", "def")
        fmt_menu.config(
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
            padx=8,
            pady=2,
        )
        fmt_menu.pack(side=tk.LEFT)

        tk.Label(
            spec_card,
            text="3. DESCRIBE SPRITES / GAME MECHANICS / SOUND TO GENERATE:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 4))

        self.desc_entry = tk.Entry(
            spec_card,
            textvariable=self.desc_var,
            font=(font_fam, 9, "bold"),
            bg=str(t["input_bg"]),
            fg=str(t["input_fg"]),
            insertbackground=str(t["input_fg"]),
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
        )
        self.desc_entry.pack(fill=tk.X, ipady=5)

        tools_card = tk.Frame(dlg, bg=str(t["panel_bg"]), padx=10, pady=8, highlightthickness=1, highlightbackground=str(t["accent"]))
        tools_card.pack(fill=tk.X, padx=14, pady=(0, 8))

        tk.Label(
            tools_card,
            text="VISUAL PIXEL & PROJECT TOOLS:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
        ).pack(side=tk.LEFT, padx=(0, 10))

        def open_pixel_editor() -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            parent.action_open_sprite_studio()

        self.sprite_studio_btn = tk.Button(
            tools_card,
            text="OPEN PIXEL SPRITE STUDIO [HTML5]",
            command=open_pixel_editor,
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.sprite_studio_btn.pack(side=tk.LEFT, padx=(0, 8))

        def open_new_game_proj() -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            parent.action_new_game()

        self.new_game_btn = tk.Button(
            tools_card,
            text="CREATE MULTI-FILE GAME PROJECT",
            command=open_new_game_proj,
            font=(font_fam, 8, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.new_game_btn.pack(side=tk.LEFT)

        def do_generate(_event=None) -> None:
            chosen_kind = self.kind_var.get()
            chosen_fmt = self.target_fmt_var.get().strip().lower()
            brief = self.desc_var.get().strip() or self.PRESETS[chosen_kind][2]
            if dlg.winfo_exists():
                dlg.destroy()
            parent._run_ai_game_generation(chosen_kind, chosen_fmt, brief)

        def do_cancel(_event=None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()

        self.do_generate = do_generate

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(4, 14))

        prov = parent._active_provider() if hasattr(parent, "_active_provider") else "agy"
        prov_brand = "CLAUDE" if prov == "claude" else "ANTIGRAVITY"

        self.generate_btn = tk.Button(
            btn_row,
            text=f"▶ GENERATE IN IDE WITH {prov_brand} [ENTER]",
            command=do_generate,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.generate_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.cancel_btn = tk.Button(
            btn_row,
            text="CANCEL [ESC]",
            command=do_cancel,
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        self.desc_entry.bind("<Return>", do_generate)
        dlg.bind("<Escape>", do_cancel)

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.desc_entry.focus_set()
        except tk.TclError:
            pass
        return dlg


BUILD_OUTPUT_OPTIONS: tuple[tuple[str, str, str, str], ...] = (
    (
        "prg",
        ".PRG",
        "PRG BINARY ONLY (.prg)",
        "Standard C64 executable binary ready for direct DMA upload to C64U.",
    ),
    (
        "tap",
        ".TAP",
        "STANDARD CASSETTE (.tap)",
        "Builds .prg + standard-speed C64 Datasette cassette image (<stem>.tap).",
    ),
    (
        "hypertap",
        "HYPER.TAP",
        "HYPERLOAD TURBO TAPE (Hyper.tap)",
        "Builds .prg + 5x fast-loading HYPERLOAD cassette with VIC-II border stripes (<stem>.hyper.tap).",
    ),
    (
        "d64",
        ".D64",
        "1541 FLOPPY DISK (.d64)",
        "Builds .prg + formatted 35-track Commodore 1541 disk image (<stem>.d64).",
    ),
    (
        "all",
        "ALL",
        "ALL MEDIA (.tap + Hyper.tap + .d64)",
        "Builds .prg plus .tap, .hyper.tap, and .d64 images in one pass.",
    ),
)


class BuildOutputModal:
    """
    Build Output Packaging Modal allowing 1-click selection of `.prg`, `.tap`,
    `Hyper.tap` (`.hyper.tap`), `.d64`, or `ALL` media outputs when compiling.
    """

    def __init__(self, initial_format: str = "prg"):
        valid = {opt[0] for opt in BUILD_OUTPUT_OPTIONS}
        self.initial_format = initial_format if initial_format in valid else "prg"
        self.option_buttons: dict[str, tk.Button] = {}
        self.dlg: Optional[tk.Toplevel] = None

    def show_tk(self, parent: "C64StudioApp") -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)
        dlg.title("C64 BUILD OUTPUT OPTIONS // .PRG, .TAP, HYPER.TAP & .D64")
        dlg.geometry("860x500")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ BUILD OUTPUT TARGET — CHOOSE .PRG, .TAP, HYPER.TAP OR .D64 ]",
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        card = tk.Frame(
            dlg,
            bg=str(t["panel_bg"]),
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
        )
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        tk.Label(
            card,
            text="SELECT PACKAGING FORMAT FOR COMPILE [F7] / BUILD.PY / SEND TO C64U [F5]:",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))

        self.format_var = tk.StringVar(master=dlg, value=self.initial_format)
        self.desc_lbl = tk.Label(
            card,
            text="",
            font=(font_fam, 8, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            anchor="w",
            padx=10,
            pady=7,
        )

        def _sync_choices() -> None:
            cur = self.format_var.get()
            cur_desc = ""
            for code, _short, _title, desc in BUILD_OUTPUT_OPTIONS:
                is_sel = code == cur
                if is_sel:
                    cur_desc = desc
                btn = self.option_buttons.get(code)
                if btn is not None:
                    btn.configure(
                        bg=str(t["button_active_bg"]) if is_sel else str(t["editor_bg"]),
                        fg=str(t["button_active_fg"]) if is_sel else str(t["ink"]),
                    )
            self.desc_lbl.configure(text=f"INFO: {cur_desc}")

        def select_format(fmt_code: str) -> None:
            valid_codes = {opt[0] for opt in BUILD_OUTPUT_OPTIONS}
            if fmt_code not in valid_codes:
                return
            self.format_var.set(fmt_code)
            _sync_choices()

        self.select_format = select_format

        for code, short_lbl, title_txt, _desc in BUILD_OUTPUT_OPTIONS:
            b = tk.Button(
                card,
                text=f"[{short_lbl:<9}]  {title_txt}",
                command=lambda fc=code: select_format(fc),
                font=(font_fam, 9, "bold"),
                relief=tk.FLAT,
                anchor="w",
                padx=12,
                pady=7,
                cursor="hand2",
            )
            b.pack(fill=tk.X, pady=3)
            self.option_buttons[code] = b

        self.desc_lbl.pack(fill=tk.X, pady=(8, 2))
        _sync_choices()

        def do_build_now(_event=None) -> None:
            chosen = self.format_var.get()
            if dlg.winfo_exists():
                dlg.destroy()
            parent.action_build_with_format(chosen)

        def do_save_only(_event=None) -> None:
            chosen = self.format_var.get()
            if dlg.winfo_exists():
                dlg.destroy()
            parent.set_build_format(chosen, notify_user=True)

        def do_cancel(_event=None) -> None:
            if dlg.winfo_exists():
                dlg.destroy()

        self.do_build_now = do_build_now
        self.do_save_only = do_save_only

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(4, 14))

        self.build_now_btn = tk.Button(
            btn_row,
            text="▶ BUILD NOW [ENTER]",
            command=do_build_now,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.build_now_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.save_only_btn = tk.Button(
            btn_row,
            text="SET TARGET ONLY",
            command=do_save_only,
            font=(font_fam, 9, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
        )
        self.save_only_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.cancel_btn = tk.Button(
            btn_row,
            text="CANCEL [ESC]",
            command=do_cancel,
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        dlg.bind("<Return>", do_build_now)
        dlg.bind("<Escape>", do_cancel)

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.build_now_btn.focus_set()
        except tk.TclError:
            pass
        return dlg


@dataclass
class EditorTabState:
    """In-memory state for each open file/buffer tab in C64 Studio."""

    tab_id: str
    title_hint: str = "untitled"
    loaded_file: Optional[Path] = None
    file_mode: str = "py"          # "py", "c", "asm", or "def"
    file_kind: str = ""
    py_content: str = ""
    asm_content: str = ""
    baseline_text: str = ""
    needs_disk_save: bool = False
    asm_focus_mode: bool = False
    binary_source: Optional[Path] = None
    last_asm: str = ""
    last_prg_path: Optional[Path] = None
    last_sid_path: Optional[Path] = None
    stage: int = 1
    py_cursor: str = "1.0"
    asm_cursor: str = "1.0"

    def primary_text(self) -> str:
        return self.asm_content if self.file_mode == "asm" else self.py_content

    @property
    def is_dirty(self) -> bool:
        cur = self.primary_text()
        if self.loaded_file is None and not cur.strip() and not self.needs_disk_save:
            return False
        return bool(self.needs_disk_save or (cur != self.baseline_text))

    def base_name(self) -> str:
        if self.loaded_file is not None:
            return self.loaded_file.name
        if "." in self.title_hint:
            return self.title_hint
        if self.file_kind == "sid":
            return f"{self.title_hint}.sid.asm"
        ext_map = {"asm": ".asm", "c": ".c", "py": ".py", "def": ".py"}
        return f"{self.title_hint}{ext_map.get(self.file_mode, '.asm')}"

    def display_name(self) -> str:
        base = self.base_name()
        return f"{base} *" if self.is_dirty else base


class UnsavedChangesModal:
    """
    Prompt shown before compiling (or before closing a dirty tab) when one or more
    open tabs have unsaved changes (`*`).
    """

    def __init__(self, dirty_tabs: list[EditorTabState], mode: str = "compile"):
        self.dirty_tabs = list(dirty_tabs)
        self.mode = mode if mode in ("compile", "close") else "compile"
        self.dlg: Optional[tk.Toplevel] = None

    def show_tk(self, parent: "C64StudioApp", callback: Callable[[str], None]) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        self.dlg = dlg
        parent._apply_application_icon(dlg)

        is_compile = self.mode == "compile"
        dlg.title(
            "UNSAVED CHANGES (*) — SAVE BEFORE COMPILING?"
            if is_compile
            else "UNSAVED CHANGES (*) — SAVE BEFORE CLOSING TAB?"
        )
        dlg.geometry("840x380")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["warning"]))
        dlg.transient(parent.root)

        hdr_txt = (
            "[ UNSAVED FILE CHANGES (*) — SAVE BEFORE COMPILING? ]"
            if is_compile
            else "[ UNSAVED FILE CHANGES (*) — SAVE BEFORE CLOSING TAB? ]"
        )
        tk.Label(
            dlg,
            text=hdr_txt,
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["warning"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(14, 8))

        card = tk.Frame(
            dlg,
            bg=str(t["panel_bg"]),
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=str(t["accent"]),
        )
        card.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 8))

        explain = (
            "THE FOLLOWING OPEN TAB(S) HAVE UNSAVED CHANGES (*).\n"
            "SAVE THEM TO DISK NOW SO YOUR BUILD USES THE LATEST CODE?"
            if is_compile
            else "THIS TAB HAS UNSAVED CHANGES (*). SAVE BEFORE CLOSING?"
        )
        tk.Label(
            card,
            text=explain,
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["ink"]),
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 8))

        list_box = tk.Frame(card, bg=str(t["editor_bg"]), padx=10, pady=8)
        list_box.pack(fill=tk.BOTH, expand=True)
        for tab in self.dirty_tabs[:6]:
            loc = str(tab.loaded_file) if tab.loaded_file is not None else "(unsaved new buffer)"
            tk.Label(
                list_box,
                text=f"• {tab.display_name()}   [{loc}]",
                font=(font_fam, 8, "bold"),
                bg=str(t["editor_bg"]),
                fg=str(t["warning"]),
                anchor="w",
            ).pack(fill=tk.X, pady=2)

        def _finish(choice: str) -> None:
            if dlg.winfo_exists():
                dlg.destroy()
            callback(choice)

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=(4, 14))

        self.save_btn = tk.Button(
            btn_row,
            text="▶ SAVE & COMPILE [ENTER]" if is_compile else "▶ SAVE & CLOSE [ENTER]",
            command=lambda: _finish("save"),
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(8, 0))

        alt_btn = tk.Button(
            btn_row,
            text="COMPILE WITHOUT SAVING" if is_compile else "DISCARD CHANGES",
            command=lambda: _finish("skip"),
            font=(font_fam, 9, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
        )
        alt_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.compile_unsaved_btn = alt_btn
        self.discard_btn = alt_btn

        self.cancel_btn = tk.Button(
            btn_row,
            text="CANCEL [ESC]",
            command=lambda: _finish("cancel"),
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        dlg.bind("<Return>", lambda _e: _finish("save"))
        dlg.bind("<Escape>", lambda _e: _finish("cancel"))

        center_popup(dlg)
        try:
            dlg.grab_set()
            self.save_btn.focus_set()
        except tk.TclError:
            pass
        return dlg


# ---------------------------------------------------------------------------
# Main Tkinter C64 Lookalike Studio Application
# ---------------------------------------------------------------------------

class C64StudioApp:
    """
    C64 Studio — Authentic Commodore 64 Multi-Language IDE (6502 ASM, Oscar64 C, Python),
    Game Studio, and Google Antigravity CLI (`agy`) AI Hub in Tkinter.
    """

    BINDINGS: list[KeyBindingDef] = [
        KeyBindingDef("f1", "show_help", "Help & Credits"),
        KeyBindingDef("f2", "open_presets", "Presets"),
        KeyBindingDef("f3", "open_file", "Load File"),
        KeyBindingDef("f4", "refresh_connection", "Ping C64U"),
        KeyBindingDef("f5", "run_c64u", "Build + Run"),
        KeyBindingDef("f6", "transpile_code", "Transpile"),
        KeyBindingDef("f7", "build", "Build"),
        KeyBindingDef("f8", "reset_c64u", "Reset C64U"),
        KeyBindingDef("f10", "focus_menu", "Menu Bar"),
        KeyBindingDef("f11", "toggle_fullscreen", "Fullscreen"),
        KeyBindingDef("f12", "export_hyperload", "Hyperload TAP"),
        KeyBindingDef("shift+f1", "save_file", "Save File"),
        KeyBindingDef("shift+f2", "export_tap", "Export TAP"),
        KeyBindingDef("shift+f3", "load_prg_only", "DMA Load"),
        KeyBindingDef("shift+f4", "pause_cpu", "Pause CPU"),
        KeyBindingDef("shift+f5", "resume_cpu", "Resume CPU"),
        KeyBindingDef("shift+f6", "dump_screen", "Screen Dump"),
        KeyBindingDef("shift+f7", "reboot_c64u", "Reboot C64U"),
        KeyBindingDef("shift+f8", "quit", "Quit"),
        KeyBindingDef("shift+f9", "compile_d64", "Compile D64"),
        KeyBindingDef("shift+f10", "open_sprite_studio", "Sprite Studio"),
        KeyBindingDef("shift+f11", "validation_report", "Validation Report"),
        KeyBindingDef("shift+f12", "focus_agy_prompt", "Antigravity AI"),
        KeyBindingDef("ctrl+s", "save_file", "Save File"),
        KeyBindingDef("ctrl+p", "play_sid", "Play SID"),
        KeyBindingDef("ctrl+e", "toggle_asm_focus", "ASM IDE Focus"),
        KeyBindingDef("ctrl+n", "new_asm_template", "New ASM"),
        KeyBindingDef("ctrl+f", "focus_find", "Find / Goto"),
        KeyBindingDef("ctrl+k", "open_agy_setup", "AGY CLI Setup"),
        KeyBindingDef("ctrl+q", "quit", "Quit"),
        KeyBindingDef("alt+a", "focus_agy_prompt", "AGY Prompt"),
        KeyBindingDef("alt+f", "focus_submenu('file')", "File"),
        KeyBindingDef("alt+b", "focus_submenu('build')", "Build"),
        KeyBindingDef("alt+c", "focus_submenu('device')", "Device"),
        KeyBindingDef("alt+h", "focus_submenu('help')", "Help"),
        KeyBindingDef("alt+g", "focus_submenu('gamedev')", "Game Dev"),
    ]

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        skip_boot: bool = False,
        start_maximized: bool = True,
        **kwargs,
    ):
        register_embedded_fonts()
        self._owns_root = root is None
        if root is None:
            if os.name == "nt":
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    pass
            existing_root = getattr(tk, "_default_root", None)
            if existing_root is not None:
                try:
                    if existing_root.winfo_exists():
                        for child in list(existing_root.winfo_children()):
                            child.destroy()
                        self.root = existing_root
                    else:
                        self.root = tk.Tk()
                except tk.TclError:
                    self.root = tk.Tk()
            else:
                self.root = tk.Tk()
        else:
            for child in list(root.winfo_children()):
                try:
                    child.destroy()
                except tk.TclError:
                    pass
            self.root = root

        self.transpiler = PythonTo6502Transpiler()
        self.compiler = CrossCompiler()
        self.client = C64UClient(
            host=kwargs.get("host"),
            port=int(kwargs.get("port", 80)),
            password=kwargs.get("password"),
        )
        self._studio_settings = load_studio_settings()
        self._loading_studio_settings = True
        explicit_provider = kwargs.get("ai_provider") or self._studio_settings.get("ai_provider")
        self._provider_explicitly_chosen = bool(explicit_provider)
        initial_provider = normalize_provider(explicit_provider)
        init_install_cmd, init_install_alt = install_commands_for_provider(initial_provider)

        self.validator = DeploymentValidator()
        self.agy = AgyCliConnector(
            agy_bin=kwargs.get("agy_bin"),
            claude_bin=kwargs.get("claude_bin"),
            workspace_dir=Path.cwd(),
            provider=initial_provider,
        )
        self.agy_status: AgyStatus = AgyStatus(
            installed=False,
            models=default_models_for_provider(initial_provider),
            install_command=init_install_cmd,
            install_command_alt=init_install_alt,
            status_message=f"Checking {provider_display_name(initial_provider)}...",
            provider=initial_provider,
        )
        self.cli_statuses: dict[str, AgyStatus] = {}
        self.last_validation_report: Optional[DeploymentValidationReport] = None
        self.last_agy_result: Optional[AgyPromptResult] = None
        self.last_agy_code_block: Optional[ExtractedCodeBlock] = None
        self._last_agy_modal: Optional[AgySetupModal] = None
        self._last_new_file_modal: Optional[NewFileModal] = None
        self._last_compile_error_modal: Optional[CompileErrorFixModal] = None
        self._last_game_gen_modal: Optional[GameAssetGenModal] = None
        self._last_build_output_modal: Optional[BuildOutputModal] = None
        self._last_unsaved_modal: Optional[UnsavedChangesModal] = None
        self._last_compile_error: Optional[tuple[str, str, str]] = None
        self._agy_busy: bool = False
        self._last_synced_editor_text: str = ""
        self._workspace_watch_mtimes: dict[Path, tuple[int, int]] = {}
        self._self_written_mtimes: dict[Path, int] = {}
        self._studio_journal_offset: int = 0
        self._ext_poll_counter: int = 0

        # Multi-file Open Tabs state
        self.open_tabs: list[EditorTabState] = []
        self.active_file_tab_id: Optional[str] = None
        self._next_tab_seq: int = 1
        self._restoring_tab: bool = False
        self.file_tab_buttons: dict[str, tk.Button] = {}
        self.file_tab_close_buttons: dict[str, tk.Button] = {}

        self.current_theme = "Commodore 64"
        self.build_format_var = tk.StringVar(master=self.root, value="prg")
        self._suppress_auto_package: bool = False
        self.last_asm: str = ""
        self.last_prg_path: Optional[Path] = None
        self.last_tap_path: Optional[Path] = None
        self.last_hyper_tap_path: Optional[Path] = None
        self.last_d64_path: Optional[Path] = None
        self.last_sid_path: Optional[Path] = None
        self.loaded_file: Optional[Path] = None
        self.file_mode: str = "py"  # "py", "c", "asm", or "def" for a build.py or game definition
        self.file_kind: str = ""    # see project.classify_file; "" until something is loaded
        self.binary_source: Optional[Path] = None   # the .prg behind a disassembly
        self.stage: int = 0         # how far along the sequence: 1 loaded, 2 built, 3 running
        self.asm_focus_mode: bool = False
        self.is_fullscreen: bool = False
        self._open_menu_category: Optional[str] = None
        self._show_asm_labels: bool = True

        # Animation & Splash state
        self._anim_tick: int = 0
        self._border_busy: bool = False
        self._busy_phase: str = "READY // DMA LINK IDLE"
        self._busy_progress: float = 1.0
        self._boot_active: bool = False
        self._splash_win: Optional[tk.Toplevel] = None
        self._splash_alpha: float = 0.0
        self._splash_phase: str = "idle"
        self._splash_after_id: Optional[str] = None
        self._window_icon_handles: list[int] = []
        self._native_icon_window_ids: set[int] = set()
        self._c64_badge_img: Optional[ImageTk.PhotoImage] = None
        self._cassette_badge_img: Optional[ImageTk.PhotoImage] = None
        self._deck_c64_badge_img: Optional[ImageTk.PhotoImage] = None
        self._deck_cas_badge_img: Optional[ImageTk.PhotoImage] = None
        self._active_tab: str = "tab-asm"
        self.focused_button_id: Optional[str] = None

        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "RetroSoft.C64UBridge.LookalikeStudio.1"
                )
            except Exception:
                pass

        self.root.title('C64 STUDIO // **** COMMODORE 64 BASIC V2 **** 6502 ASM, C (OSCAR64) & PYTHON IDE')
        self.root.geometry("1440x920")
        self.root.minsize(1024, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.action_quit)

        self._build_ui()
        self.apply_theme(self.current_theme)
        self._bind_shortcuts()

        self._update_mode_badge()

        if start_maximized:
            try:
                self.root.state("zoomed")
            except tk.TclError:
                pass

        self._finish_boot_sequence()
        if not skip_boot:
            self._show_splash_screen()

        self._tick_animation()

    # -----------------------------------------------------------------------
    # UI Construction (Clean Single-Screen Retro C64 Studio Layout)
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Outer VIC-II Border Canvas (Light Blue #70A4B2 in idle, Raster Bars during load/DMA)
        self.border_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.border_canvas.pack(fill=tk.BOTH, expand=True)

        # Inner CRT Screen Frame (Dark Blue #352879)
        self.screen_frame = tk.Frame(self.border_canvas, bd=0, highlightthickness=2)
        self.screen_window_id = self.border_canvas.create_window(
            18, 18, anchor="nw", window=self.screen_frame
        )
        self.border_canvas.bind("<Configure>", self._on_border_resize)

        # Main Studio Container inside screen_frame
        self.studio_frame = tk.Frame(self.screen_frame, bd=0)
        self.studio_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Clean Top Header Bar: C64 Badge + Studio Title + Language Selector + Live Status + Themes
        self.top_bar = tk.Frame(self.studio_frame)
        self.top_bar.pack(fill=tk.X, padx=14, pady=(10, 4))

        self.c64_logo_lbl = tk.Label(self.top_bar, bd=0)
        self.c64_logo_lbl.pack(side=tk.LEFT, padx=(0, 10))

        self.header_right = tk.Frame(self.top_bar)
        self.header_right.pack(side=tk.RIGHT)

        self.banner_label = tk.Label(self.top_bar, text="", justify=tk.LEFT, anchor="w")
        self.banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lang_buttons: dict[str, tk.Button] = {}
        for lang_code, lang_lbl in (
            ("asm", "ASM"),
            ("c", "C"),
            ("py", "PY"),
        ):
            lb = tk.Button(
                self.header_right,
                text=lang_lbl,
                command=lambda lc=lang_code: self.action_select_language(lc),
                relief=tk.FLAT,
                padx=7,
                pady=4,
                cursor="hand2",
            )
            lb.pack(side=tk.LEFT, padx=2)
            self.lang_buttons[lang_code] = lb

        self.btn_lang_sid = tk.Button(
            self.header_right,
            text="SID",
            command=lambda: self.action_select_language("sid"),
            relief=tk.FLAT,
            padx=7,
            pady=4,
            cursor="hand2",
        )
        self.btn_lang_sid.pack(side=tk.LEFT, padx=2)

        self.bridge_status_lbl = tk.Button(
            self.header_right,
            text="● C64U: CHECK",
            command=self.action_refresh_connection,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        self.bridge_status_lbl.pack(side=tk.LEFT, padx=(8, 2))

        self.btn_agy_status = tk.Button(
            self.header_right,
            text="● AGY: CHECK",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        self.btn_agy_status.pack(side=tk.LEFT, padx=2)

        # Kept constructed for backwards compatibility (primary ASM toggle sits on the workspace bar)
        self.btn_asm_focus = tk.Button(
            self.header_right,
            text="SHOW ASM (^E)",
            command=self.action_toggle_asm_focus,
            relief=tk.FLAT,
            padx=6,
            pady=4,
            cursor="hand2",
        )

        self.btn_fullscreen = tk.Button(
            self.header_right,
            text="[F11]",
            command=self.action_toggle_fullscreen,
            relief=tk.FLAT,
            padx=6,
            pady=4,
            cursor="hand2",
        )
        self.btn_fullscreen.pack(side=tk.LEFT, padx=(6, 0))

        # 2. Crisp C64 Rainbow Color Divider Strip
        self.divider_canvas = tk.Canvas(self.studio_frame, height=5, highlightthickness=0, bd=0)
        self.divider_canvas.pack(fill=tk.X, padx=14, pady=(2, 6))

        # 3. Sleek Single-Row Menu & Quick-Action Ribbon + Collapsible Menu Drawer
        self.command_ribbon = tk.Frame(self.studio_frame, padx=6, pady=4, highlightthickness=1)
        self.command_ribbon.pack(fill=tk.X, padx=14, pady=(0, 6))

        # Pack right-side 1-click actions FIRST so they never clip at high DPI
        self.ribbon_right = tk.Frame(self.command_ribbon)
        self.ribbon_right.pack(side=tk.RIGHT)

        self.ribbon_left = tk.Frame(self.command_ribbon)
        self.ribbon_left.pack(side=tk.LEFT)

        # Collapsible Menu Drawer (hidden by default so the code editor stays spacious!)
        self.menu_bar = tk.Frame(self.studio_frame, padx=8, pady=6, highlightthickness=1)

        self.menu_drawer_hdr = tk.Frame(self.menu_bar)
        self.menu_drawer_title = tk.Label(self.menu_drawer_hdr, text="", anchor="w")
        self.menu_drawer_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_close_menu = tk.Button(
            self.menu_drawer_hdr,
            text="X CLOSE [ESC]",
            command=self.close_menu_drawer,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_close_menu.pack(side=tk.RIGHT)

        self.menu_cols_wrap = tk.Frame(self.menu_bar)
        self.menu_cols_wrap.pack(fill=tk.X, expand=True)

        self.menu_buttons: dict[str, tk.Button] = {}
        self.menu_columns: dict[str, list[str]] = {
            "file": [],
            "build": [],
            "device": [],
            "gamedev": [],
            "help": [],
        }

        self._menu_cat_titles: dict[str, str] = {
            "file": "10 FILE: NEW & LOAD",
            "build": "20 COMPILE & TEST",
            "device": "30 SEND TO C64U",
            "gamedev": "40 GAME GENERATION",
            "help": "50 HELP & AI",
        }

        menu_spec = [
            (
                0,
                "file",
                "col-file",
                "menu-btn-file",
                "FILE",
                [
                    ("btn-open", "LOAD FILE     [F3]", self.action_open_file),
                    ("btn-new-file", "NEW FILE...       ", self.action_new_file_dialog),
                    ("btn-new-c", "NEW .C (OSCAR64)  ", self.action_new_c_template),
                    ("btn-new-py", "NEW .PY (6502)    ", self.action_new_py_template),
                    ("btn-new-asm", "NEW .ASM      [^N]", self.action_new_asm_template),
                    ("btn-new-sid", "NEW .SID (MUSIC)  ", self.action_new_sid_template),
                    ("btn-save", "SAVE FILE    [⇧F1]", self.action_save_file),
                    ("btn-save-all", "SAVE ALL TABS[^⇧S]", self.action_save_all_files),
                    ("btn-close-tab", "CLOSE TAB     [^W]", self.action_close_active_tab),
                    ("btn-export-tap", "EXPORT .TAP  [⇧F2]", self.action_export_tap),
                    ("btn-export-hyperload", "HYPERLOAD    [F12]", self.action_export_hyperload),
                    ("btn-export-d64", "EXPORT .D64  [⇧F9]", self.action_compile_d64),
                ],
            ),
            (
                1,
                "build",
                "col-build",
                "menu-btn-build",
                "BUILD",
                [
                    ("quick-btn-run", "▶ SEND TO C64U [F5]", self.action_send_to_c64u),
                    ("btn-build", "COMPILE & TEST [F7]", self.action_build),
                    ("btn-build-options", "BUILD TARGET...    ", self.action_open_build_options),
                    ("btn-build-tap", "BUILD .TAP    [⇧F2]", lambda: self.action_build_with_format("tap")),
                    ("btn-build-hypertap", "BUILD HYPER.TAP[F12]", lambda: self.action_build_with_format("hypertap")),
                    ("btn-build-d64", "BUILD .D64    [⇧F9]", lambda: self.action_build_with_format("d64")),
                    ("btn-build-all", "BUILD ALL MEDIA    ", lambda: self.action_build_with_format("all")),
                    ("btn-compile-sid", "COMPILE .SID   [F7]", self.action_compile_sid),
                    ("btn-py-to-asm-menu", "TRANSPILE → ASM[F6]", self.action_transpile_code),
                    ("btn-load-prg", "DMA LOAD RAM  [⇧F3]", self.action_load_prg_only),
                    ("btn-validation-rep", "VALID REPORT [⇧F11]", self.action_validation_report),
                ],
            ),
            (
                2,
                "device",
                "col-device",
                "menu-btn-device",
                "C64U",
                [
                    ("btn-refresh", "PING C64U     [F4]", self.action_refresh_connection),
                    ("btn-send-c64u", "▶ SEND TO C64U [F5]", self.action_send_to_c64u),
                    ("btn-play-sid", "SEND/PLAY SID [^P]", self.action_play_sid),
                    ("quick-btn-reset", "SOFT RESET    [F8]", self.action_reset_c64u),
                    ("btn-pause-cpu", "PAUSE 6510   [⇧F4]", self.action_pause_cpu),
                    ("btn-resume-cpu", "RESUME 6510  [⇧F5]", self.action_resume_cpu),
                    ("btn-screen-dump", "SCREEN DUMP  [⇧F6]", self.action_dump_screen),
                    ("btn-c64u-reboot", "COLD REBOOT  [⇧F7]", self.action_reboot_c64u),
                ],
            ),
            (
                3,
                "gamedev",
                "col-gamedev",
                "menu-btn-gamedev",
                "GAMES",
                [
                    ("btn-gd-game", "NEW GAME PROJECT  ", self.action_new_game),
                    ("btn-gd-ai-gen", "AI SPRITE/GAME GEN", self.action_open_game_generator_dialog),
                    ("btn-sprite-studio", "SPRITE STUDIO[⇧F10]", self.action_open_sprite_studio),
                    ("btn-gd-sprites", "GEN SPRITE BANK   ", lambda: self.action_new_definition("sprites")),
                    ("btn-gd-tileset", "GEN TILES + MAP   ", lambda: self.action_new_definition("tileset")),
                    ("btn-gd-isotiles", "GEN ISO TERRAIN   ", lambda: self.action_new_definition("isotiles")),
                    ("btn-gd-koala", "GEN TITLE SCREEN  ", lambda: self.action_new_definition("koala")),
                    ("btn-gd-song", "GEN SID SONG      ", lambda: self.action_new_definition("song")),
                    ("btn-gd-levels", "GEN LEVEL TABLES  ", lambda: self.action_new_definition("levels")),
                    ("btn-gd-build", "GEN BUILD.PY      ", self.action_new_build_file),
                    ("btn-gd-c64sim", "C64 SCREEN   [SIM]", self.action_gamedev_c64sim),
                    ("btn-gd-check", "GAME CHECK   [SIM]", self.action_gamedev_check),
                    ("btn-gd-sim", "SID PROFILE  [SIM]", self.action_gamedev_sim),
                ],
            ),
            (
                4,
                "help",
                "col-help",
                "menu-btn-help",
                "HELP",
                [
                    ("btn-presets", "PRESET DEMOS  [F2]", self.action_open_presets),
                    ("btn-help", "GUIDE/CREDITS [F1]", self.action_show_help),
                    ("btn-agy-setup", "AGY CLI SETUP [^K]", self.action_open_agy_setup),
                    ("btn-agy-prompt", "PROMPT AGY  [⇧F12]", self.action_focus_agy_prompt),
                    ("btn-kickass-ver", "KICKASS VER  [UPD]", self.action_check_kickass_version),
                    ("btn-quit", "QUIT STUDIO  [⇧F8]", self.action_quit),
                ],
            ),
        ]

        self.col_frames: dict[str, tk.Frame] = {}
        self.col_headers: dict[str, tk.Button] = {}
        self._col_hdr_base_labels: dict[str, str] = {}
        self._col_cat_by_hdr: dict[str, str] = {}
        self._col_id_by_cat: dict[str, str] = {}
        self._col_hdr_inside: dict[str, tk.Label] = {}

        for _col_idx, cat_key, col_id, hdr_id, hdr_title, items in menu_spec:
            self._col_hdr_base_labels[hdr_id] = hdr_title
            self._col_cat_by_hdr[hdr_id] = cat_key
            self._col_id_by_cat[cat_key] = col_id

            # Sleek top-ribbon menu category trigger
            hdr_btn = tk.Button(
                self.ribbon_left,
                text=f"{hdr_title}+",
                command=lambda ck=cat_key: self.toggle_menu_category(ck),
                relief=tk.FLAT,
                padx=4,
                pady=3,
                cursor="hand2",
            )
            hdr_btn.pack(side=tk.LEFT, padx=(0, 2))
            self.col_headers[hdr_id] = hdr_btn
            self.menu_buttons[hdr_id] = hdr_btn

            # Drawer column frame
            col_f = tk.Frame(self.menu_cols_wrap, padx=4, pady=4, highlightthickness=1)
            self.col_frames[col_id] = col_f

            col_lbl = tk.Label(col_f, text=self._menu_cat_titles[cat_key], anchor="w", padx=4, pady=2)
            self._col_hdr_inside[col_id] = col_lbl

            for item_id, item_text, item_cmd in items:
                b = tk.Button(
                    col_f,
                    text=item_text,
                    command=lambda cid=item_id, fn=item_cmd: self._invoke_menu_btn(cid, fn),
                    relief=tk.FLAT,
                    anchor="w",
                    padx=8,
                    pady=3,
                    cursor="hand2",
                )
                b.bind("<FocusIn>", lambda _e, cid=item_id: self._on_btn_focus(cid))
                self.menu_buttons[item_id] = b
                self.menu_columns[cat_key].append(item_id)

        self.btn_toggle_deck = tk.Button(
            self.ribbon_left,
            text="F10",
            command=lambda: self.toggle_menu_category("all"),
            relief=tk.FLAT,
            padx=4,
            pady=3,
            cursor="hand2",
        )
        self.btn_toggle_deck.pack(side=tk.LEFT, padx=(2, 0))

        # Everyday 1-Click IDE Flow Actions on Right of Ribbon (New -> Load -> Output -> Compile -> Send to C64U)
        self.quick_ribbon_buttons: list[tk.Button] = []
        for q_id, q_txt, q_cmd, is_run in (
            ("new", "NEW", self.action_new_file_dialog, False),
            ("load", "LOAD", self.action_open_file, False),
            ("save", "SAVE", self.action_save_file, False),
            ("format", "OUT: .PRG", self.action_open_build_options, False),
            ("compile", "BUILD [F7]", self.action_build, False),
            ("send", "▶ SEND C64U [F5]", self.action_send_to_c64u, True),
        ):
            qb = tk.Button(
                self.ribbon_right,
                text=q_txt,
                command=q_cmd,
                relief=tk.FLAT,
                padx=5,
                pady=3,
                cursor="hand2",
            )
            qb.pack(side=tk.LEFT, padx=(2, 0))
            if q_id == "new":
                self.btn_quick_new = qb
            if q_id == "format":
                self.btn_build_format = qb
                qb.bind("<Button-3>", lambda _e: self.cycle_build_format())
            elif is_run:
                self.btn_quick_run = qb
            else:
                self.quick_ribbon_buttons.append(qb)

        # 4. Unified Single-Screen Workspace (Spacious, Border-Clean Layout)
        self.workspace_frame = tk.Frame(self.studio_frame)
        self.workspace_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))
        self.workspace_frame.columnconfigure(0, weight=1)
        self.workspace_frame.rowconfigure(0, weight=1)

        self.right_pane = tk.Frame(self.workspace_frame, highlightthickness=0, padx=0, pady=0)
        self.right_pane.grid(row=0, column=0, sticky="nsew")
        self.left_pane = self.right_pane  # Backwards-compatible alias for single-pane workspace

        # Tab Selector Strip + Single-Screen ASM Toggle
        self.tab_bar = tk.Frame(self.right_pane)
        self.tab_bar.pack(fill=tk.X, pady=(0, 4))

        self.tab_buttons: dict[str, tk.Button] = {}
        for tab_id, tab_title in (
            ("tab-asm", "1:EDITOR"),
            ("tab-log", "2:LOG"),
            ("tab-ast", "3:AST"),
            ("tab-hw", "4:C64U"),
            ("tab-agy", "5:AGY AI"),
        ):
            tb = tk.Button(
                self.tab_bar,
                text=tab_title,
                command=lambda tid=tab_id: self.switch_tab(tid),
                relief=tk.FLAT,
                padx=10,
                pady=4,
                cursor="hand2",
            )
            tb.pack(side=tk.LEFT, padx=(0, 4))
            self.tab_buttons[tab_id] = tb

        self.btn_show_asm = tk.Button(
            self.tab_bar,
            text="SHOW ASM [^E]",
            command=self.action_toggle_asm_focus,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.btn_show_asm.pack(side=tk.RIGHT, padx=(8, 0))

        self.mode_badge_lbl = tk.Label(
            self.tab_bar,
            text="NOTHING LOADED",
            anchor="e",
        )
        self.mode_badge_lbl.pack(side=tk.RIGHT, padx=6)

        # Tab Stack Container
        self.tab_stack = tk.Frame(self.right_pane)
        self.tab_stack.pack(fill=tk.BOTH, expand=True)

        # --- TAB 1: UNIFIED SINGLE-SCREEN CODE EDITOR (PYTHON / C / DEF + TOGGLEABLE 6502 ASM) ---
        self.pane_asm = tk.Frame(self.tab_stack)

        # Live Antigravity CLI Activity Strip (visible only while AGY is actively generating)
        self.agy_live_bar = tk.Frame(self.pane_asm, padx=10, pady=4, highlightthickness=1)
        self.agy_live_lbl = tk.Label(
            self.agy_live_bar,
            text="▶ ANTIGRAVITY AI READY",
            anchor="w",
        )
        self.agy_live_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_agy_live_log = tk.Button(
            self.agy_live_bar,
            text="5:AI CONSOLE",
            command=lambda: self.switch_tab("tab-agy"),
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_agy_live_log.pack(side=tk.RIGHT, padx=(8, 0))

        # Open File Tabs Strip (keeps multiple files open simultaneously with `*` unsaved indicator)
        self.file_tab_bar = tk.Frame(self.pane_asm, padx=6, pady=3, highlightthickness=1)
        self.file_tabs_right = tk.Frame(self.file_tab_bar)
        self.file_tabs_right.pack(side=tk.RIGHT)
        self.btn_save_all_tabs = tk.Button(
            self.file_tabs_right,
            text="SAVE ALL *",
            command=self.action_save_all_files,
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
        )
        self.btn_tab_open = tk.Button(
            self.file_tabs_right,
            text="+ LOAD [F3]",
            command=self.action_open_file,
            relief=tk.FLAT,
            padx=7,
            pady=2,
            cursor="hand2",
        )
        self.btn_tab_open.pack(side=tk.RIGHT, padx=(4, 0))
        self.file_tabs_inner = tk.Frame(self.file_tab_bar)
        self.file_tabs_inner.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Unified Active Editor Context Header Bar
        self.left_hdr_bar = tk.Frame(self.pane_asm, padx=8, pady=4, highlightthickness=1)
        self.left_hdr_bar.pack(fill=tk.X, pady=(0, 0))

        self.btn_py_to_asm = tk.Button(
            self.left_hdr_bar,
            text="PY → ASM [F6]",
            command=self._on_left_build_clicked,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_py_to_asm.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_new_sid_hdr = tk.Button(
            self.left_hdr_bar,
            text="+ .SID",
            command=self.action_new_sid_template,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_new_sid_hdr.pack(side=tk.RIGHT, padx=2)

        self.btn_new_asm_hdr = tk.Button(
            self.left_hdr_bar,
            text="+ .ASM",
            command=self.action_new_asm_template,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_new_asm_hdr.pack(side=tk.RIGHT, padx=2)

        self.btn_new_py = tk.Button(
            self.left_hdr_bar,
            text="+ .PY",
            command=self.action_new_py_template,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_new_py.pack(side=tk.RIGHT, padx=2)

        self.btn_new_c = tk.Button(
            self.left_hdr_bar,
            text="+ .C",
            command=self.action_new_c_template,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_new_c.pack(side=tk.RIGHT, padx=2)

        self.left_title_lbl = tk.Label(
            self.left_hdr_bar,
            text="PYTHON SOURCE (MOS 6502 DIALECT)",
            anchor="w",
        )
        self.left_title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Mutually-Exclusive Editor Stack (shows ONE comfortable editor at 100% width)
        self.editor_stack = tk.Frame(self.pane_asm)
        self.editor_stack.pack(fill=tk.BOTH, expand=True)

        self.find_var = tk.StringVar()

        # --- VIEW A: Full-Screen Source Editor (Python / C / Game Dev Definitions) ---
        self.source_view_frame = tk.Frame(self.editor_stack, highlightthickness=1)

        self.py_toolbar = tk.Frame(self.source_view_frame, padx=8, pady=4)
        self.py_toolbar.pack(fill=tk.X)

        self.py_cursor_lbl = tk.Label(
            self.py_toolbar,
            text="LN 1/1, COL 1",
            anchor="e",
        )
        self.py_cursor_lbl.pack(side=tk.RIGHT, padx=4)

        self.btn_py_comment = tk.Button(
            self.py_toolbar,
            text="# CMT [^/]",
            command=self.action_toggle_source_comment,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_py_comment.pack(side=tk.LEFT, padx=(0, 10))

        self.py_find_lbl = tk.Label(self.py_toolbar, text="FIND:")
        self.py_find_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.py_find_entry = tk.Entry(
            self.py_toolbar,
            textvariable=self.find_var,
            width=14,
            relief=tk.FLAT,
            highlightthickness=1,
        )
        self.py_find_entry.pack(side=tk.LEFT, padx=(0, 4), ipady=2)
        self.py_find_entry.bind("<Return>", self._on_find_or_goto)

        self.btn_py_find_go = tk.Button(
            self.py_toolbar,
            text="GO",
            command=self._on_find_or_goto,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_py_find_go.pack(side=tk.LEFT, padx=(0, 6))

        self.py_editor_container = tk.Frame(self.source_view_frame, highlightthickness=0)
        self.py_editor_container.pack(fill=tk.BOTH, expand=True)

        self.py_gutter = tk.Text(
            self.py_editor_container,
            width=5,
            padx=6,
            pady=8,
            spacing1=2,
            spacing3=2,
            takefocus=0,
            bd=0,
            highlightthickness=0,
            state="disabled",
            wrap="none",
        )
        self.py_gutter.pack(side=tk.LEFT, fill=tk.Y)

        self.py_scroll = tk.Scrollbar(self.py_editor_container)
        self.py_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.py_text = tk.Text(
            self.py_editor_container,
            wrap="none",
            undo=True,
            maxundo=50,
            bd=0,
            padx=12,
            pady=8,
            spacing1=2,
            spacing3=2,
            highlightthickness=0,
            blockcursor=True,
            insertontime=530,
            insertofftime=530,
        )
        self.py_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.py_text.config(yscrollcommand=self._on_py_scroll)
        self.py_scroll.config(command=self._yview_py_both)
        self.py_text.bind("<KeyRelease>", self._on_py_changed)
        self.py_text.bind("<<Modified>>", self._on_py_modified_event)
        self.py_text.bind("<ButtonRelease-1>", self._on_py_cursor_move)
        self.py_text.bind("<Control-slash>", lambda _e: self.action_toggle_source_comment())

        # --- VIEW B: Full-Screen 6502 Assembly Editor & Toggled ASM Inspector ---
        self.asm_view_frame = tk.Frame(self.editor_stack, highlightthickness=1)

        self.asm_toolbar = tk.Frame(self.asm_view_frame, padx=8, pady=4)
        self.asm_toolbar.pack(fill=tk.X)

        self.btn_toggle_labels = tk.Button(
            self.asm_toolbar,
            text="LABELS: ON",
            command=self.action_toggle_asm_labels,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_toggle_labels.pack(side=tk.RIGHT, padx=(8, 0))

        self.asm_cursor_lbl = tk.Label(
            self.asm_toolbar,
            text="LN 1/1, COL 1",
            anchor="e",
        )
        self.asm_cursor_lbl.pack(side=tk.RIGHT, padx=4)

        self.btn_back_to_source = tk.Button(
            self.asm_toolbar,
            text="← EDITOR [^E]",
            command=self.action_toggle_asm_focus,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )

        self.btn_promote_asm = tk.Button(
            self.asm_toolbar,
            text="USE AS .ASM",
            command=self.action_promote_to_asm,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )

        self.btn_asm_comment = tk.Button(
            self.asm_toolbar,
            text="// CMT [^/]",
            command=self.action_toggle_asm_comment,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_asm_comment.pack(side=tk.LEFT, padx=(0, 10))

        self.find_lbl = tk.Label(self.asm_toolbar, text="FIND:")
        self.find_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self.find_entry = tk.Entry(
            self.asm_toolbar,
            textvariable=self.find_var,
            width=14,
            relief=tk.FLAT,
            highlightthickness=1,
        )
        self.find_entry.pack(side=tk.LEFT, padx=(0, 4), ipady=2)
        self.find_entry.bind("<Return>", self._on_find_or_goto)

        self.btn_find_go = tk.Button(
            self.asm_toolbar,
            text="GO",
            command=self._on_find_or_goto,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_find_go.pack(side=tk.LEFT, padx=(0, 6))

        self.asm_body_frame = tk.Frame(self.asm_view_frame)
        self.asm_body_frame.pack(fill=tk.BOTH, expand=True)

        # Collapsible 6502 Label & Subroutine Jump Sidebar inside the ASM View
        self.label_nav_frame = tk.Frame(self.asm_body_frame, highlightthickness=1)
        self.label_nav_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.label_nav_hdr = tk.Label(
            self.label_nav_frame,
            text="6502 LABELS (JUMP):",
            anchor="w",
        )
        self.label_nav_hdr.pack(fill=tk.X)

        self.nav_list_wrap = tk.Frame(self.label_nav_frame)
        self.nav_list_wrap.pack(fill=tk.BOTH, expand=True)

        self.label_listbox = tk.Listbox(
            self.nav_list_wrap,
            width=21,
            height=18,
            relief=tk.FLAT,
            highlightthickness=0,
            activestyle="none",
        )
        self.label_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)
        self.label_listbox.bind("<<ListboxSelect>>", self._on_label_nav_selected)

        self.label_scroll = tk.Scrollbar(self.nav_list_wrap, command=self.label_listbox.yview)
        self.label_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_listbox.config(yscrollcommand=self.label_scroll.set)
        self._label_line_map: list[int] = []

        # Full-Height 6502 ASM Editor with Line Number Gutter
        self.asm_editor_container = tk.Frame(self.asm_body_frame, highlightthickness=0)
        self.asm_editor_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.asm_gutter = tk.Text(
            self.asm_editor_container,
            width=5,
            padx=6,
            pady=8,
            spacing1=2,
            spacing3=2,
            takefocus=0,
            bd=0,
            highlightthickness=0,
            state="disabled",
            wrap="none",
        )
        self.asm_gutter.pack(side=tk.LEFT, fill=tk.Y)

        self.asm_scroll = tk.Scrollbar(self.asm_editor_container)
        self.asm_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.asm_text = tk.Text(
            self.asm_editor_container,
            wrap="none",
            undo=True,
            maxundo=50,
            bd=0,
            padx=12,
            pady=8,
            spacing1=2,
            spacing3=2,
            highlightthickness=0,
            blockcursor=True,
            insertontime=530,
            insertofftime=530,
        )
        self.asm_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.asm_text.config(yscrollcommand=self._on_asm_scroll)
        self.asm_scroll.config(command=self._yview_asm_both)
        self.asm_text.bind("<KeyRelease>", self._on_asm_changed)
        self.asm_text.bind("<<Modified>>", self._on_asm_modified_event)
        self.asm_text.bind("<ButtonRelease-1>", self._on_asm_cursor_move)
        self.asm_text.bind("<Control-slash>", lambda _e: self.action_toggle_asm_comment())
        self.asm_text.bind("<Return>", self._on_asm_return_autoindent)

        # --- TAB 2: BUILD & DMA LOG ---
        self.pane_log = tk.Frame(self.tab_stack)
        self.log_bar = tk.Frame(self.pane_log, padx=8, pady=4, highlightthickness=1)
        self.log_bar.pack(fill=tk.X)

        self.log_title_lbl = tk.Label(self.log_bar, text="COMPILER, TRANSPILER & DMA TELEMETRY LOG", anchor="w")
        self.log_title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_clear_log = tk.Button(
            self.log_bar,
            text="CLEAR LOG",
            command=self._clear_build_log,
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        self.btn_clear_log.pack(side=tk.RIGHT)

        log_wrap = tk.Frame(self.pane_log, highlightthickness=1)
        log_wrap.pack(fill=tk.BOTH, expand=True)
        self.log_wrap = log_wrap

        self.log_scroll = tk.Scrollbar(log_wrap)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            spacing1=2,
            spacing3=2,
            highlightthickness=0,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_scroll.config(command=self.log_text.yview)

        # --- TAB 3: AST & SYMBOLS ---
        self.pane_ast = tk.Frame(self.tab_stack)
        ast_wrap = tk.Frame(self.pane_ast, highlightthickness=1)
        ast_wrap.pack(fill=tk.BOTH, expand=True)
        self.ast_wrap = ast_wrap

        self.ast_scroll = tk.Scrollbar(ast_wrap)
        self.ast_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.ast_listbox = tk.Listbox(
            ast_wrap,
            bd=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.ast_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=6)
        self.ast_listbox.config(yscrollcommand=self.ast_scroll.set)
        self.ast_scroll.config(command=self.ast_listbox.yview)

        # --- TAB 4: C64U HARDWARE & MEMORY CONSOLE ---
        self.pane_hw = tk.Frame(self.tab_stack, padx=2, pady=4)

        self.hw_card_actions = tk.Frame(self.pane_hw, padx=14, pady=10, highlightthickness=1)
        self.hw_card_actions.pack(fill=tk.X, pady=(0, 10))

        self.hw_lbl_title = tk.Label(
            self.hw_card_actions,
            text="ULTIMATE 64 / C64U DMA & 6510 CPU CONTROLS",
            anchor="w",
        )
        self.hw_lbl_title.pack(fill=tk.X, pady=(0, 8))

        self.hw_btn_row1 = tk.Frame(self.hw_card_actions)
        self.hw_btn_row1.pack(fill=tk.X, pady=2)
        self.hw_buttons: dict[str, tk.Button] = {}
        for bid, btxt, bcmd in (
            ("hw-run-prg", "▶ DMA RUN PRG", self.action_run_c64u),
            ("hw-load-prg", "DMA LOAD PRG", self.action_load_prg_only),
            ("hw-reset", "SOFT RESET [F8]", self.action_reset_c64u),
            ("hw-reboot", "COLD REBOOT", self.action_reboot_c64u),
            ("hw-pause", "PAUSE 6510", self.action_pause_cpu),
            ("hw-resume", "▶ RESUME 6510", self.action_resume_cpu),
        ):
            b = tk.Button(
                self.hw_btn_row1,
                text=btxt,
                command=bcmd,
                relief=tk.FLAT,
                padx=10,
                pady=5,
                cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=(0, 8))
            self.hw_buttons[bid] = b

        self.hw_card_mem = tk.Frame(self.pane_hw, padx=14, pady=10, highlightthickness=1)
        self.hw_card_mem.pack(fill=tk.X, pady=(0, 10))

        self.hw_lbl_mem = tk.Label(
            self.hw_card_mem,
            text="DIRECT MEMORY PEEK / POKE & LIVE HARDWARE TELEMETRY",
            anchor="w",
        )
        self.hw_lbl_mem.pack(fill=tk.X, pady=(0, 8))

        self.poke_row = tk.Frame(self.hw_card_mem)
        self.poke_row.pack(fill=tk.X, pady=(2, 6))

        self.lbl_addr = tk.Label(self.poke_row, text="ADDR:")
        self.lbl_addr.pack(side=tk.LEFT, padx=(0, 6))
        self.inp_addr_var = tk.StringVar(value="$D020")
        self.inp_addr_entry = tk.Entry(
            self.poke_row, textvariable=self.inp_addr_var, width=10, relief=tk.FLAT, highlightthickness=1
        )
        self.inp_addr_entry.pack(side=tk.LEFT, padx=(0, 14), ipady=4)

        self.lbl_val = tk.Label(self.poke_row, text="VAL:")
        self.lbl_val.pack(side=tk.LEFT, padx=(0, 6))
        self.inp_val_var = tk.StringVar(value="$01")
        self.inp_val_entry = tk.Entry(
            self.poke_row, textvariable=self.inp_val_var, width=8, relief=tk.FLAT, highlightthickness=1
        )
        self.inp_val_entry.pack(side=tk.LEFT, padx=(0, 14), ipady=4)

        for bid, btxt, bcmd in (
            ("hw-poke", "POKE MEMORY", self._handle_hw_poke),
            ("hw-peek", "PEEK MEMORY", self._handle_hw_peek),
        ):
            b = tk.Button(self.poke_row, text=btxt, command=bcmd, relief=tk.FLAT, padx=10, pady=4, cursor="hand2")
            b.pack(side=tk.LEFT, padx=(0, 8))
            self.hw_buttons[bid] = b

        self.hw_diag_row = tk.Frame(self.hw_card_mem)
        self.hw_diag_row.pack(fill=tk.X, pady=(4, 2))
        for bid, btxt, bcmd in (
            ("hw-dump", "INSPECT SCREEN ($0400) [⇧F6]", self.action_dump_screen),
            ("hw-validate", "VALIDATION REPORT [⇧F11]", self.action_validation_report),
            ("hw-ping", "PING C64U BRIDGE [F4]", self.action_refresh_connection),
        ):
            b = tk.Button(self.hw_diag_row, text=btxt, command=bcmd, relief=tk.FLAT, padx=10, pady=4, cursor="hand2")
            b.pack(side=tk.LEFT, padx=(0, 8))
            self.hw_buttons[bid] = b

        self.hw_card_keys = tk.Frame(self.pane_hw, padx=14, pady=10, highlightthickness=1)
        self.hw_card_keys.pack(fill=tk.X)

        self.hw_lbl_keys_hdr = tk.Label(
            self.hw_card_keys,
            text="KERNAL KEYBOARD BUFFER INJECTION",
            anchor="w",
        )
        self.hw_lbl_keys_hdr.pack(fill=tk.X, pady=(0, 8))

        self.key_row = tk.Frame(self.hw_card_keys)
        self.key_row.pack(fill=tk.X, pady=2)
        self.lbl_keys = tk.Label(self.key_row, text="SEND KEYS:")
        self.lbl_keys.pack(side=tk.LEFT, padx=(0, 8))
        self.inp_keys_var = tk.StringVar(value='PRINT "HELLO C64U"\r')
        self.inp_keys_entry = tk.Entry(
            self.key_row, textvariable=self.inp_keys_var, width=34, relief=tk.FLAT, highlightthickness=1
        )
        self.inp_keys_entry.pack(side=tk.LEFT, padx=(0, 10), ipady=4)
        b_send = tk.Button(
            self.key_row,
            text="▶ INJECT KEYS TO C64",
            command=self._handle_send_keys,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        b_send.pack(side=tk.LEFT)
        self.hw_buttons["hw-send-keys"] = b_send

        # --- TAB 5: ANTIGRAVITY AI CLI CONSOLE ---
        self.pane_agy = tk.Frame(self.tab_stack)

        # Two-Row AI Header Card (eliminates horizontal clipping at any window width)
        self.agy_top_bar = tk.Frame(self.pane_agy, padx=10, pady=6, highlightthickness=1)
        self.agy_top_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 4))

        self.agy_top_row1 = tk.Frame(self.agy_top_bar)
        self.agy_top_row1.pack(fill=tk.X, pady=(0, 4))

        self.agy_lbl_provider = tk.Label(self.agy_top_row1, text="CLI:")
        self.agy_lbl_provider.pack(side=tk.LEFT, padx=(0, 4))

        self.agy_provider_var = tk.StringVar(master=self.root, value=self.agy.provider)
        self.agy_provider_display_var = tk.StringVar(
            master=self.root,
            value=dict(AI_PROVIDERS).get(self.agy.provider, "Antigravity (agy)"),
        )
        self.agy_provider_menu = tk.OptionMenu(
            self.agy_top_row1,
            self.agy_provider_display_var,
            *[plabel for _, plabel in AI_PROVIDERS],
            command=lambda chosen_label: self._on_provider_menu_pick(chosen_label),
        )
        self.agy_provider_menu.config(relief=tk.FLAT, highlightthickness=1, padx=6, pady=2)
        self.agy_provider_menu.pack(side=tk.LEFT, padx=(0, 10))

        self.agy_lbl_lang = tk.Label(self.agy_top_row1, text="TARGET:")
        self.agy_lbl_lang.pack(side=tk.LEFT, padx=(0, 4))

        self.agy_lang_var = tk.StringVar(value="py")
        self.agy_lang_menu = tk.OptionMenu(
            self.agy_top_row1, self.agy_lang_var, "asm", "c", "py", "def"
        )
        self.agy_lang_menu.config(relief=tk.FLAT, highlightthickness=1, padx=6, pady=2)
        self.agy_lang_menu.pack(side=tk.LEFT, padx=(0, 12))

        self.agy_lbl_mode = tk.Label(self.agy_top_row1, text="MODE:")
        self.agy_lbl_mode.pack(side=tk.LEFT, padx=(0, 4))

        self.agy_mode_var = tk.StringVar(value="accept-edits")
        self.agy_mode_menu = tk.OptionMenu(
            self.agy_top_row1, self.agy_mode_var, "accept-edits", "plan", "auto"
        )
        self.agy_mode_menu.config(relief=tk.FLAT, highlightthickness=1, padx=6, pady=2)
        self.agy_mode_menu.pack(side=tk.LEFT, padx=(0, 12))

        self.agy_lbl_effort = tk.Label(self.agy_top_row1, text="EFFORT:")
        self.agy_lbl_effort.pack(side=tk.LEFT, padx=(0, 4))

        saved_effort = str(self._studio_settings.get("agy_effort", "medium")).strip().lower()
        if saved_effort not in AGY_EFFORT_LEVELS:
            saved_effort = "medium"
        self.agy_effort_var = tk.StringVar(master=self.root, value=saved_effort)
        self.agy_effort_menu = tk.OptionMenu(
            self.agy_top_row1, self.agy_effort_var, *AGY_EFFORT_LEVELS
        )
        self.agy_effort_menu.config(relief=tk.FLAT, highlightthickness=1, padx=6, pady=2)
        self.agy_effort_menu.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_agy_setup_tab = tk.Button(
            self.agy_top_row1,
            text="CLI SETUP",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_setup_tab.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_agy_term = tk.Button(
            self.agy_top_row1,
            text="▶ CLI TERM",
            command=self.action_launch_agy_terminal,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_term.pack(side=tk.RIGHT, padx=4)

        self.btn_agy_clear = tk.Button(
            self.agy_top_row1,
            text="CLEAR",
            command=self._clear_agy_chat,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_clear.pack(side=tk.RIGHT, padx=4)

        self.agy_top_row2 = tk.Frame(self.agy_top_bar)
        self.agy_top_row2.pack(fill=tk.X)

        self.agy_lbl_model = tk.Label(self.agy_top_row2, text="MODEL:")
        self.agy_lbl_model.pack(side=tk.LEFT, padx=(0, 4))

        model_key = "claude_model" if self.agy.provider == "claude" else "agy_model"
        saved_model = str(self._studio_settings.get(model_key, self._studio_settings.get("agy_model", ""))).strip()
        self.agy_model_var = tk.StringVar(master=self.root, value=saved_model)
        self.agy_model_display_var = tk.StringVar(master=self.root, value="")
        self._agy_model_choices: list[tuple[str, str]] = default_models_for_provider(self.agy.provider)
        if saved_model and all(mid != saved_model for mid, _ in self._agy_model_choices):
            self._agy_model_choices.append((saved_model, saved_model))
        self.agy_model_menu = tk.OptionMenu(
            self.agy_top_row2,
            self.agy_model_display_var,
            *[lbl for _, lbl in self._agy_model_choices],
        )
        self.agy_model_menu.config(relief=tk.FLAT, highlightthickness=1, padx=6, pady=2)
        self.agy_model_menu.pack(side=tk.LEFT, padx=(0, 12))
        self._refresh_agy_model_menu(self._agy_model_choices)
        self._loading_studio_settings = False
        self.agy_model_var.trace_add("write", self._on_agy_cli_option_changed)
        self.agy_effort_var.trace_add("write", self._on_agy_cli_option_changed)

        self.agy_include_ctx_var = tk.BooleanVar(value=True)
        self.agy_chk_ctx = tk.Checkbutton(
            self.agy_top_row2,
            text="EDITOR CTX",
            variable=self.agy_include_ctx_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_ctx.pack(side=tk.LEFT, padx=(0, 10))

        self.agy_continue_var = tk.BooleanVar(value=False)
        self.agy_chk_cont = tk.Checkbutton(
            self.agy_top_row2,
            text="CONTINUE (-c)",
            variable=self.agy_continue_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_cont.pack(side=tk.LEFT, padx=(0, 10))

        self.agy_auto_apply_var = tk.BooleanVar(value=True)
        self.agy_chk_apply = tk.Checkbutton(
            self.agy_top_row2,
            text="AUTO-APPLY",
            variable=self.agy_auto_apply_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_apply.pack(side=tk.LEFT, padx=(0, 10))

        self.agy_watch_cli_var = tk.BooleanVar(value=True)
        self.agy_chk_watch = tk.Checkbutton(
            self.agy_top_row2,
            text="LIVE CLI SYNC",
            variable=self.agy_watch_cli_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_watch.pack(side=tk.LEFT, padx=(0, 8))

        # Dock bottom action bar BEFORE expanding chat frame so buttons never clip
        self.agy_action_bar = tk.Frame(self.pane_agy, pady=4)
        self.agy_action_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.btn_agy_apply = tk.Button(
            self.agy_action_bar,
            text="APPLY LAST CODE TO EDITOR",
            command=self.action_apply_last_agy_code,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.btn_agy_apply.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_agy_apply_run = tk.Button(
            self.agy_action_bar,
            text="▶ APPLY & DMA RUN [F5]",
            command=self.action_apply_and_run_agy_code,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        self.btn_agy_apply_run.pack(side=tk.LEFT, padx=(0, 8))

        agy_chat_wrap = tk.Frame(self.pane_agy, highlightthickness=1)
        agy_chat_wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 4))
        self.agy_chat_wrap = agy_chat_wrap

        self.agy_chat_scroll = tk.Scrollbar(agy_chat_wrap)
        self.agy_chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.agy_chat_text = tk.Text(
            agy_chat_wrap,
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            spacing1=2,
            spacing3=2,
            highlightthickness=0,
        )
        self.agy_chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.agy_chat_text.config(yscrollcommand=self.agy_chat_scroll.set)
        self.agy_chat_scroll.config(command=self.agy_chat_text.yview)

        # 5. Always-Accessible Antigravity CLI Prompt Bar (across bottom of C64 Studio)
        self.agy_quick_bar = tk.Frame(self.studio_frame, padx=10, pady=5, highlightthickness=1)
        self.agy_quick_bar.pack(fill=tk.X, padx=14, pady=(2, 2))

        self.lbl_agy_prompt = tk.Label(
            self.agy_quick_bar,
            text="AI PROMPT [⇧F12]:",
            anchor="w",
        )
        self.lbl_agy_prompt.pack(side=tk.LEFT, padx=(0, 8))

        self.agy_prompt_var = tk.StringVar()
        self.agy_prompt_entry = tk.Entry(
            self.agy_quick_bar,
            textvariable=self.agy_prompt_var,
            relief=tk.FLAT,
            highlightthickness=1,
        )
        self.agy_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=4)
        self.agy_prompt_entry.bind("<Return>", lambda _e: self.action_send_agy_prompt())

        self.btn_agy_send = tk.Button(
            self.agy_quick_bar,
            text="▶ ASK AGY",
            command=self.action_send_agy_prompt,
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="hand2",
        )
        self.btn_agy_send.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_agy_quick_setup = tk.Button(
            self.agy_quick_bar,
            text="CLI SETUP",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="hand2",
        )
        self.btn_agy_quick_setup.pack(side=tk.LEFT)

        # 6. Slim Bottom Retro DMA & Tape Telemetry Footer
        self.deck_frame = tk.Frame(self.studio_frame, padx=8, pady=4, highlightthickness=1)
        self.deck_frame.pack(fill=tk.X, padx=14, pady=(2, 8))

        self.deck_canvas = tk.Canvas(self.deck_frame, height=30, highlightthickness=0, bd=0)
        self.deck_canvas.pack(fill=tk.X)
        self.deck_canvas.bind("<Configure>", lambda _e: self.root.after_idle(self._draw_bottom_deck))

        self.status_row = tk.Frame(self.deck_frame)
        self.status_row.pack(fill=tk.X, pady=(3, 0))

        self.credits_hint_lbl = tk.Label(
            self.status_row,
            text="F3:LOAD  F7:COMPILE  F5:SEND C64U  F10:MENUS",
            anchor="e",
        )
        self.credits_hint_lbl.pack(side=tk.RIGHT, padx=(12, 0))

        self.prompt_lbl = tk.Label(self.status_row, text="READY. █", anchor="w")
        self.prompt_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Dock bottom bars with side=BOTTOM BEFORE workspace_frame expands so they never clip at high DPI
        self.workspace_frame.pack_forget()
        self.agy_quick_bar.pack_forget()
        self.deck_frame.pack_forget()
        self.deck_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(2, 8))
        self.agy_quick_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(2, 2))
        self.workspace_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 4))

        self.switch_tab("tab-asm")

    # -----------------------------------------------------------------------
    # Startup Splash Screen ("C64 Studio by Station88 Retro" Fade In / Out)
    # -----------------------------------------------------------------------

    def _set_splash_alpha(self, alpha: float) -> None:
        self._splash_alpha = max(0.0, min(1.0, float(alpha)))
        win = self._splash_win
        if win is not None and win.winfo_exists():
            try:
                win.wm_attributes("-alpha", self._splash_alpha)
            except tk.TclError:
                pass

    def _show_splash_screen(self) -> None:
        """Display the fade-in / fade-out Station 88 Retro splash screen over the ready IDE."""
        if not self.root.winfo_exists():
            return
        self._close_splash_screen()

        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])

        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        try:
            win.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        win.configure(bg=str(t["border_idle"]))
        self._splash_win = win

        outer = tk.Frame(
            win,
            bg=str(t["paper"]),
            highlightthickness=2,
            highlightbackground=str(t["accent_bright"]),
            padx=28,
            pady=22,
        )
        outer.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if self._c64_badge_img is not None:
            tk.Label(outer, image=self._c64_badge_img, bg=str(t["paper"]), bd=0).pack(pady=(0, 10))

        self._splash_title_lbl = tk.Label(
            outer,
            text="C64 STUDIO",
            font=(font_fam, 20, "bold"),
            bg=str(t["paper"]),
            fg=str(t["accent_bright"]),
        )
        self._splash_title_lbl.pack(pady=(0, 6))

        self._splash_subtitle_lbl = tk.Label(
            outer,
            text="BY STATION88 RETRO",
            font=(font_fam, 11, "bold"),
            bg=str(t["paper"]),
            fg=str(t["warning"]),
        )
        self._splash_subtitle_lbl.pack(pady=(0, 14))

        rainbow_bar = tk.Canvas(outer, height=5, width=360, highlightthickness=0, bd=0, bg=str(t["paper"]))
        rainbow_bar.pack(pady=(0, 12))
        rainbow_cols = list(t["rainbow"])
        seg_w = 360 / max(1, len(rainbow_cols))
        for idx, col in enumerate(rainbow_cols):
            rainbow_bar.create_rectangle(idx * seg_w, 0, (idx + 1) * seg_w + 1, 5, fill=str(col), outline="")

        tk.Label(
            outer,
            text="6502 ASM  •  C (OSCAR64)  •  PYTHON  •  SID",
            font=(font_fam, 8, "bold"),
            bg=str(t["paper"]),
            fg=str(t["cyan"]),
        ).pack()

        win.update_idletasks()
        sw = max(460, win.winfo_reqwidth())
        sh = max(210, win.winfo_reqheight())
        try:
            self.root.update_idletasks()
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            if rw <= 1 or rh <= 1:
                rw = win.winfo_screenwidth()
                rh = win.winfo_screenheight()
                rx, ry = 0, 0
            x = rx + max(0, (rw - sw) // 2)
            y = ry + max(0, (rh - sh) // 2)
        except tk.TclError:
            x, y = 200, 160
        win.geometry(f"{sw}x{sh}+{x}+{y}")

        win.bind("<Button-1>", lambda _e: self._dismiss_splash_screen())
        win.bind("<Key>", lambda _e: self._dismiss_splash_screen())

        self._splash_phase = "fade_in"
        self._set_splash_alpha(0.0)
        try:
            win.deiconify()
            win.lift()
        except tk.TclError:
            pass
        self._splash_after_id = self.root.after(120, lambda: self._step_splash_fade("fade_in", 1))

    def _center_splash_over_root(self) -> None:
        win = self._splash_win
        if win is None or not win.winfo_exists():
            return
        try:
            self.root.update_idletasks()
            win.update_idletasks()
            sw = max(460, win.winfo_reqwidth())
            sh = max(210, win.winfo_reqheight())
            rx = self.root.winfo_rootx()
            ry = self.root.winfo_rooty()
            rw = self.root.winfo_width()
            rh = self.root.winfo_height()
            if rw <= 10 or rh <= 10:
                rw = win.winfo_screenwidth()
                rh = win.winfo_screenheight()
                rx, ry = 0, 0
            x = rx + max(0, (rw - sw) // 2)
            y = ry + max(0, (rh - sh) // 2)
            win.geometry(f"{sw}x{sh}+{x}+{y}")
            win.lift()
        except tk.TclError:
            pass

    def _step_splash_fade(self, phase: str, step: int) -> None:
        win = self._splash_win
        if win is None or not win.winfo_exists() or not self.root.winfo_exists():
            self._splash_phase = "done"
            self._splash_after_id = None
            return

        self._splash_phase = phase
        if phase == "fade_in":
            if step == 1:
                self._center_splash_over_root()
            total_in = 15
            alpha = min(1.0, step / total_in)
            self._set_splash_alpha(alpha)
            if step < total_in:
                self._splash_after_id = self.root.after(30, lambda s=step + 1: self._step_splash_fade("fade_in", s))
            else:
                self._splash_phase = "hold"
                self._splash_after_id = self.root.after(1600, lambda: self._step_splash_fade("fade_out", 1))
            return

        if phase == "fade_out":
            total_out = 15
            alpha = max(0.0, 1.0 - (step / total_out))
            self._set_splash_alpha(alpha)
            if step < total_out:
                self._splash_after_id = self.root.after(30, lambda s=step + 1: self._step_splash_fade("fade_out", s))
            else:
                self._close_splash_screen()
            return

    def _dismiss_splash_screen(self) -> None:
        if self._splash_after_id is not None:
            try:
                self.root.after_cancel(self._splash_after_id)
            except tk.TclError:
                pass
            self._splash_after_id = None
        if self._splash_win is not None and self._splash_win.winfo_exists() and self._splash_phase != "fade_out":
            self._step_splash_fade("fade_out", 2)
        else:
            self._close_splash_screen()

    def _close_splash_screen(self) -> None:
        if self._splash_after_id is not None:
            try:
                self.root.after_cancel(self._splash_after_id)
            except tk.TclError:
                pass
            self._splash_after_id = None
        win = self._splash_win
        self._splash_win = None
        self._splash_alpha = 0.0
        self._splash_phase = "done"
        if win is not None:
            try:
                if win.winfo_exists():
                    win.destroy()
            except tk.TclError:
                pass

    def _finish_boot_sequence(self) -> None:
        """Show the ready-to-use C64 Studio IDE immediately."""
        if self.studio_frame.winfo_ismapped():
            return
        self._boot_active = False
        self._border_busy = False
        self.studio_frame.pack(fill=tk.BOTH, expand=True)
        self._draw_border_and_divider()
        self._draw_bottom_deck()
        self._write_log('**** COMMODORE 64 BASIC V2 ****  //  LOAD "C64-BRIDGE",8,1  //  READY.')
        self._write_log(f"Bridge Target: http://{self.client.host}:{self.client.port}")
        self._write_log("Font Credit: 'Pet Me 64' by Kreative Korporation / Kreative Software (Free Use License 1.2f).")
        self._write_log("F3 loads a file, 40 GAME DEV starts something new. Then F7 builds it and F5 runs it.")
        if not self.agy_chat_text.get("1.0", "end-1c").strip():
            self._write_agy_chat(
                "*** C64 STUDIO // GOOGLE ANTIGRAVITY CLI (`agy`) AI ASSISTANT ***\n"
                "• Select target language (ASM 6502, C / Oscar64, Python, or Game Def) and type a prompt below!\n"
                "• Live Streaming: Tokens, tool steps, and generated code stream into the IDE in real time.\n"
                "• External CLI Sync: Run `agy` in any terminal (or click '▶ CLI TERM') — workspace edits & MCP runs sync live!\n"
                "• Press Shift+F12 (Alt+A) to jump to the prompt box, or Ctrl+K for guided CLI setup.\n"
                "────────────────────────────────────────────────────────────────────────"
            )
        self._init_external_cli_watch_state()
        self.check_agy_cli_startup()
        if getattr(self, "_in_mainloop", False):
            self.check_bridge_status()
            self.check_kickass_version_startup()

    # -----------------------------------------------------------------------
    # Theme Application, Icons & Retro Visuals
    # -----------------------------------------------------------------------

    def _apply_application_icon(self, window: tk.Tk | tk.Toplevel) -> None:
        ico_file = get_asset_path("app_icon.ico")
        master_png = get_asset_path("app_icon_master.png")
        if os.name == "nt" and ico_file.is_file():
            try:
                window.iconbitmap(default=str(ico_file))
                return
            except tk.TclError:
                pass
        if Image is not None and ImageTk is not None and not hasattr(self, "_tk_icon_64") and master_png.is_file():
            try:
                with Image.open(master_png) as img:
                    pil_master = img.convert("RGBA")
                    self._tk_icon_64 = ImageTk.PhotoImage(pil_master.resize((64, 64), Image.Resampling.LANCZOS), master=self.root)
                    self._tk_icon_32 = ImageTk.PhotoImage(pil_master.resize((32, 32), Image.Resampling.LANCZOS), master=self.root)
                window.iconphoto(True, self._tk_icon_64, self._tk_icon_32)
            except Exception:
                pass

    def _load_badge_images(self) -> None:
        if Image is None or ImageTk is None:
            return
        if self._c64_badge_img is None:
            c64_path = get_asset_path("8bitC64.png")
            if c64_path.is_file():
                try:
                    with Image.open(c64_path) as img:
                        rgba = img.convert("RGBA")
                        bbox = rgba.getchannel("A").getbbox()
                        if bbox:
                            rgba = rgba.crop(bbox)
                        top_rgba = rgba.copy()
                        top_rgba.thumbnail((52, 32), Image.Resampling.NEAREST)
                        self._c64_badge_img = ImageTk.PhotoImage(top_rgba, master=self.root)
                        deck_rgba = rgba.copy()
                        deck_rgba.thumbnail((38, 24), Image.Resampling.NEAREST)
                        self._deck_c64_badge_img = ImageTk.PhotoImage(deck_rgba, master=self.root)
                except Exception:
                    pass
        if self._cassette_badge_img is None:
            cas_path = get_asset_path("8bitCassette.png")
            if cas_path.is_file():
                try:
                    with Image.open(cas_path) as img:
                        rgba = img.convert("RGBA")
                        bbox = rgba.getchannel("A").getbbox()
                        if bbox:
                            rgba = rgba.crop(bbox)
                        top_cas = rgba.copy()
                        top_cas.thumbnail((48, 34), Image.Resampling.NEAREST)
                        self._cassette_badge_img = ImageTk.PhotoImage(top_cas, master=self.root)
                        deck_cas = rgba.copy()
                        deck_cas.thumbnail((36, 24), Image.Resampling.NEAREST)
                        self._deck_cas_badge_img = ImageTk.PhotoImage(deck_cas, master=self.root)
                except Exception:
                    pass

    def apply_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            theme_name = "Commodore 64"
        self.current_theme = theme_name
        t = THEMES[theme_name]
        font_fam = str(t["font_family"])

        f_banner = (font_fam, 10, "bold")
        f_hdr = (font_fam, 9, "bold")
        f_btn = (font_fam, 8, "bold")
        f_code = (font_fam, 10, "bold")
        f_small = (font_fam, 8, "bold")

        self._apply_application_icon(self.root)
        self._load_badge_images()

        if self._c64_badge_img is not None:
            self.c64_logo_lbl.configure(image=self._c64_badge_img, bg=str(t["paper"]))

        # Outer paper containers
        for frame in (
            self.screen_frame,
            self.studio_frame,
            self.top_bar,
            self.header_right,
            self.workspace_frame,
            self.right_pane,
            self.tab_bar,
            self.tab_stack,
            self.pane_asm,
            self.editor_stack,
            self.asm_body_frame,
            self.pane_log,
            self.pane_ast,
            self.pane_hw,
            self.pane_agy,
            self.agy_action_bar,
        ):
            frame.configure(bg=str(t["paper"]))

        # Bordered cards & bars (panel_bg + accent border)
        for panel_card in (
            self.command_ribbon,
            self.menu_bar,
            self.file_tab_bar,
            self.left_hdr_bar,
            self.log_bar,
            self.hw_card_actions,
            self.hw_card_mem,
            self.hw_card_keys,
            self.agy_top_bar,
            self.agy_quick_bar,
            self.deck_frame,
        ):
            panel_card.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))

        # Inner borderless panel rows (prevents raw #F0F0F0 Tk stripes)
        for inner_row in (
            self.ribbon_left,
            self.ribbon_right,
            self.menu_drawer_hdr,
            self.menu_cols_wrap,
            self.file_tabs_inner,
            self.file_tabs_right,
            self.hw_btn_row1,
            self.poke_row,
            self.hw_diag_row,
            self.key_row,
            self.agy_top_row1,
            self.agy_top_row2,
            self.nav_list_wrap,
            self.status_row,
        ):
            inner_row.configure(bg=str(t["panel_bg"]))

        # Seamless dark editor utility bars
        for util_bar in (self.py_toolbar, self.asm_toolbar):
            util_bar.configure(bg=str(t["gutter_bg"]))

        # Bordered editor & console containers
        for code_wrap in (
            self.source_view_frame,
            self.asm_view_frame,
            self.log_wrap,
            self.ast_wrap,
            self.agy_chat_wrap,
        ):
            code_wrap.configure(bg=str(t["editor_bg"]), highlightbackground=str(t["accent"]))

        self.screen_frame.configure(
            highlightbackground=str(t["accent"]),
            highlightcolor=str(t["accent"]),
        )
        self.agy_live_bar.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent_bright"]))
        self.agy_live_lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent_bright"]))
        self.btn_agy_live_log.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        self.banner_label.configure(
            text="C64 STUDIO",
            font=f_banner,
            bg=str(t["paper"]),
            fg=str(t["ink"]),
        )
        self._update_language_button_styles()
        self._refresh_agy_badge(self.agy_status)

        self.btn_fullscreen.configure(
            font=f_btn,
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
        )

        # Style Command Ribbon & Collapsible Menu Drawer
        self.menu_drawer_title.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=4, pady=2)
        self.btn_close_menu.configure(
            font=f_btn,
            bg=str(t["panel_bg"]),
            fg=str(t["warning"]),
            activebackground=str(t["button_bg"]),
            activeforeground=str(t["button_fg"]),
        )
        for qb in self.quick_ribbon_buttons:
            qb.configure(
                font=f_btn,
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                activebackground=str(t["button_active_bg"]),
                activeforeground=str(t["button_active_fg"]),
            )
        self.btn_quick_run.configure(
            font=f_btn,
            bg=str(t["success"]),
            fg="#000000",
            activebackground=str(t["accent_bright"]),
            activeforeground="#000000",
        )
        self._sync_build_format_button()

        for col_f in self.col_frames.values():
            col_f.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["paper"]))
        for col_lbl in self._col_hdr_inside.values():
            col_lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]))

        for bid, b in self.menu_buttons.items():
            if bid in self.col_headers:
                continue
            fg_col = str(t["panel_fg"])
            if bid in ("quick-btn-run", "btn-send-c64u", "btn-gd-ai-gen"):
                fg_col = str(t["success"])
            elif bid in ("quick-btn-reset", "btn-decompile-disk"):
                fg_col = str(t["warning"])
            elif bid in ("btn-quit", "btn-c64u-reboot"):
                fg_col = str(t["danger"])
            b.configure(
                font=f_btn,
                bg=str(t["editor_bg"]),
                fg=fg_col,
                activebackground=str(t["button_bg"]),
                activeforeground=str(t["button_fg"]),
            )

        self._sync_menu_drawer()

        self.bridge_status_lbl.configure(
            font=f_btn,
            bg=str(t["editor_bg"]),
            fg=str(t["accent"]),
        )

        self.btn_tab_open.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))
        self.btn_save_all_tabs.configure(font=f_btn, bg=str(t["warning"]), fg="#000000")
        self._render_file_tab_bar()

        # Style Unified Single-Screen Editor Header & Source View
        self.left_title_lbl.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=4, pady=2)
        for lbtn in (
            self.btn_py_to_asm,
            self.btn_new_sid_hdr,
            self.btn_new_asm_hdr,
            self.btn_new_c,
            self.btn_new_py,
        ):
            lbtn.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        for pbtn in (self.btn_py_comment, self.btn_py_find_go):
            pbtn.configure(font=f_btn, bg=str(t["panel_bg"]), fg=str(t["accent_bright"]))
        self.py_find_lbl.configure(font=f_small, bg=str(t["gutter_bg"]), fg=str(t["ink"]))
        self.py_find_entry.configure(
            font=f_small,
            bg=str(t["input_bg"]),
            fg=str(t["input_fg"]),
            insertbackground=str(t["input_fg"]),
            highlightbackground=str(t["accent"]),
        )
        self.py_cursor_lbl.configure(font=f_small, bg=str(t["gutter_bg"]), fg=str(t["accent_bright"]), padx=4, pady=2)

        self.py_editor_container.configure(bg=str(t["editor_bg"]))
        self.py_gutter.configure(font=f_code, bg=str(t["gutter_bg"]), fg=str(t["gutter_fg"]))
        self.py_text.configure(
            font=f_code,
            bg=str(t["editor_bg"]),
            fg=str(t["editor_fg"]),
            insertbackground=str(t["accent_bright"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
        )

        self.label_nav_frame.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))
        self.label_nav_hdr.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=6, pady=4)
        self.label_listbox.configure(
            font=f_small,
            bg=str(t["editor_bg"]),
            fg=str(t["cyan"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
        )

        # Style ASM View & Tabs
        self.mode_badge_lbl.configure(font=f_small, bg=str(t["paper"]), fg=str(t["accent"]))
        self.btn_back_to_source.configure(font=f_btn, bg=str(t["accent"]), fg="#000000")
        self.btn_promote_asm.configure(font=f_btn, bg=str(t["success"]), fg="#000000")
        for btn in (self.btn_asm_comment, self.btn_find_go, self.btn_toggle_labels):
            btn.configure(font=f_btn, bg=str(t["panel_bg"]), fg=str(t["accent_bright"]))

        self.log_title_lbl.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=4, pady=2)
        self.btn_clear_log.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        self.find_lbl.configure(font=f_small, bg=str(t["gutter_bg"]), fg=str(t["ink"]))
        self.find_entry.configure(
            font=f_small,
            bg=str(t["input_bg"]),
            fg=str(t["input_fg"]),
            insertbackground=str(t["input_fg"]),
            highlightbackground=str(t["accent"]),
        )
        self.asm_cursor_lbl.configure(font=f_small, bg=str(t["gutter_bg"]), fg=str(t["accent_bright"]), padx=4, pady=2)

        self.asm_editor_container.configure(bg=str(t["editor_bg"]))
        self.asm_gutter.configure(font=f_code, bg=str(t["gutter_bg"]), fg=str(t["gutter_fg"]))
        self.asm_text.configure(
            font=f_code,
            bg=str(t["editor_bg"]),
            fg=str(t["editor_fg"]),
            insertbackground=str(t["accent_bright"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
        )

        self.log_text.configure(
            font=f_code,
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            insertbackground=str(t["accent_bright"]),
        )
        self.ast_listbox.configure(
            font=f_code,
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
        )

        # Style Hardware Tab (3 Structured Cards)
        for lbl in (
            self.hw_lbl_title,
            self.hw_lbl_mem,
            self.hw_lbl_keys_hdr,
            self.lbl_addr,
            self.lbl_val,
            self.lbl_keys,
        ):
            lbl.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]))
        for entry in (self.inp_addr_entry, self.inp_val_entry, self.inp_keys_entry):
            entry.configure(
                font=f_code,
                bg=str(t["input_bg"]),
                fg=str(t["input_fg"]),
                insertbackground=str(t["input_fg"]),
                highlightbackground=str(t["accent"]),
            )
        for bid, b in self.hw_buttons.items():
            if bid in ("hw-run-prg", "hw-send-keys"):
                b.configure(font=f_btn, bg=str(t["success"]), fg="#000000")
            elif bid == "hw-reboot":
                b.configure(font=f_btn, bg=str(t["danger"]), fg="#FFFFFF")
            else:
                b.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        # Style AI Console & Quick Prompt Bar
        for lbl in (
            self.agy_lbl_provider,
            self.agy_lbl_lang,
            self.agy_lbl_mode,
            self.agy_lbl_effort,
            self.agy_lbl_model,
        ):
            lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]))
        for om in (
            self.agy_provider_menu,
            self.agy_lang_menu,
            self.agy_mode_menu,
            self.agy_effort_menu,
            self.agy_model_menu,
        ):
            om.configure(
                font=f_small,
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                highlightbackground=str(t["accent"]),
            )
        for chk in (self.agy_chk_ctx, self.agy_chk_cont, self.agy_chk_apply, self.agy_chk_watch):
            chk.configure(
                font=f_small,
                bg=str(t["panel_bg"]),
                fg=str(t["ink"]),
                selectcolor=str(t["editor_bg"]),
                activebackground=str(t["panel_bg"]),
                activeforeground=str(t["accent_bright"]),
            )
        self.agy_chat_text.configure(
            font=f_code,
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            insertbackground=str(t["accent_bright"]),
        )
        for abtn in (
            self.btn_agy_setup_tab,
            self.btn_agy_term,
            self.btn_agy_clear,
            self.btn_agy_apply,
            self.btn_agy_quick_setup,
        ):
            abtn.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))
        for green_btn in (self.btn_agy_apply_run, self.btn_agy_send):
            green_btn.configure(font=f_btn, bg=str(t["success"]), fg="#000000")

        self.lbl_agy_prompt.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent_bright"]))
        self.agy_prompt_entry.configure(
            font=f_code,
            bg=str(t["input_bg"]),
            fg=str(t["input_fg"]),
            insertbackground=str(t["input_fg"]),
            highlightbackground=str(t["accent"]),
        )

        # Configure Syntax Highlighting Tags
        self._configure_syntax_tags()
        self._highlight_asm_editor()
        self._highlight_py_editor()

        # Bottom Status & Deck
        self.deck_canvas.configure(bg=str(t["panel_bg"]))
        self.prompt_lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["ink"]))
        self.credits_hint_lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]))

        self._sync_editor_display()
        self._update_tab_button_styles()
        self._draw_border_and_divider()
        self._draw_bottom_deck()

    def toggle_menu_category(self, category: str) -> None:
        """Toggle a single compact submenu drawer (or 'all' for the 5-column command deck)."""
        if self._open_menu_category == category:
            self.close_menu_drawer()
        else:
            self._open_menu_category = category
            self._sync_menu_drawer()

    def close_menu_drawer(self) -> None:
        """Collapse the menu drawer so the editor reclaims maximum vertical space."""
        self._open_menu_category = None
        self._sync_menu_drawer()

    def _sync_menu_drawer(self) -> None:
        """Render the top ribbon button states and show/hide the collapsible menu drawer."""
        if not self.root.winfo_exists():
            return
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        f_btn = (font_fam, 8, "bold")
        open_cat = self._open_menu_category

        for hdr_id, hdr_btn in self.col_headers.items():
            base_lbl = self._col_hdr_base_labels[hdr_id]
            cat_key = self._col_cat_by_hdr[hdr_id]
            is_open = open_cat == cat_key or open_cat == "all"
            glyph = "-" if open_cat == cat_key else "+"
            hdr_btn.configure(
                text=f"{base_lbl}{glyph}",
                font=f_btn,
                bg=str(t["button_active_bg"]) if is_open else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_open else str(t["accent_bright"]),
                activebackground=str(t["button_active_bg"]),
                activeforeground=str(t["button_active_fg"]),
            )

        all_open = open_cat == "all"
        self.btn_toggle_deck.configure(
            text="F10-" if all_open else "F10",
            font=f_btn,
            bg=str(t["button_active_bg"]) if all_open else str(t["panel_bg"]),
            fg=str(t["button_active_fg"]) if all_open else str(t["panel_fg"]),
            activebackground=str(t["button_active_bg"]),
            activeforeground=str(t["button_active_fg"]),
        )

        if open_cat is None:
            self.menu_bar.pack_forget()
            return

        # Clear existing grid placements before re-laying out
        for col_f in self.col_frames.values():
            col_f.grid_forget()

        cats_ordered = ["file", "build", "device", "gamedev", "help"]
        if open_cat == "all":
            self.menu_drawer_title.configure(
                text="ALL STUDIO MENUS & SHORTCUTS  //  CLICK COMMAND OR PRESS ESC"
            )
            for c_idx, ck in enumerate(cats_ordered):
                cid = self._col_id_by_cat[ck]
                col_f = self.col_frames[cid]
                self.menu_cols_wrap.columnconfigure(c_idx, weight=1, uniform="menu_col")
                col_f.columnconfigure(0, weight=1, uniform="")
                col_f.columnconfigure(1, weight=0, uniform="")
                col_f.columnconfigure(2, weight=0, uniform="")
                self._col_hdr_inside[cid].grid(row=0, column=0, sticky="ew", pady=(0, 4))
                for r_idx, btn_id in enumerate(self.menu_columns[ck], start=1):
                    self.menu_buttons[btn_id].grid(row=r_idx, column=0, sticky="ew", padx=1, pady=1)
                col_f.grid(row=0, column=c_idx, sticky="nsew", padx=2, pady=1)
        elif open_cat in self._col_id_by_cat:
            self.menu_drawer_title.configure(
                text=f"{self._menu_cat_titles[open_cat]}  //  SELECT ACTION OR PRESS ESC"
            )
            for c_idx in range(5):
                self.menu_cols_wrap.columnconfigure(c_idx, weight=1 if c_idx == 0 else 0, uniform="")
            cid = self._col_id_by_cat[open_cat]
            col_f = self.col_frames[cid]
            self._col_hdr_inside[cid].grid_forget()
            for gcol in range(3):
                col_f.columnconfigure(gcol, weight=1, uniform="cat_col")
            for idx, btn_id in enumerate(self.menu_columns[open_cat]):
                self.menu_buttons[btn_id].grid(
                    row=idx // 3,
                    column=idx % 3,
                    sticky="ew",
                    padx=3,
                    pady=2,
                )
            col_f.grid(row=0, column=0, sticky="ew", padx=2, pady=1)

        if self.menu_drawer_hdr.winfo_manager() != "pack":
            self.menu_drawer_hdr.pack(fill=tk.X, pady=(0, 6), before=self.menu_cols_wrap)
        if self.menu_bar.winfo_manager() != "pack":
            self.menu_bar.pack(fill=tk.X, padx=14, pady=(0, 6), after=self.command_ribbon)

    def action_toggle_asm_labels(self) -> None:
        """Toggle the 6502 label/subroutine sidebar inside the ASM editor."""
        self._show_asm_labels = not self._show_asm_labels
        if self._show_asm_labels:
            self.label_nav_frame.pack(side=tk.RIGHT, fill=tk.Y, before=self.asm_editor_container)
            self.btn_toggle_labels.configure(text="LABELS: ON")
        else:
            self.label_nav_frame.pack_forget()
            self.btn_toggle_labels.configure(text="LABELS: OFF")

    def _is_asm_view_active(self) -> bool:
        """Return True when the single-screen editor should display 6502 Assembly (`asm_view_frame`)."""
        return self.file_mode == "asm" or bool(self.asm_focus_mode)

    def _sync_editor_display(self) -> None:
        """Ensure the single-screen workspace displays ONLY the active editor (or toggled ASM view)."""
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        f_btn = (font_fam, 8, "bold")
        showing_asm = self._is_asm_view_active()

        if showing_asm:
            self.source_view_frame.pack_forget()
            if self.asm_view_frame.winfo_manager() != "pack":
                self.asm_view_frame.pack(fill=tk.BOTH, expand=True)
            if self.file_mode != "asm":
                back_lang = "C" if self.file_mode == "c" else ("DEF" if self.file_mode == "def" else "PYTHON")
                self.btn_back_to_source.configure(text=f"← {back_lang} [^E]")
                self.btn_back_to_source.pack_forget()
                self.btn_promote_asm.pack_forget()
                self.btn_back_to_source.pack(side=tk.LEFT, padx=(0, 6), before=self.btn_asm_comment)
                self.btn_promote_asm.pack(side=tk.LEFT, padx=(0, 8), before=self.btn_asm_comment)
            else:
                self.btn_back_to_source.pack_forget()
                self.btn_promote_asm.pack_forget()
        else:
            self.asm_view_frame.pack_forget()
            if self.source_view_frame.winfo_manager() != "pack":
                self.source_view_frame.pack(fill=tk.BOTH, expand=True)

        # Sync the Show/Hide ASM toggle buttons in both the workspace bar and top header
        if self.file_mode == "asm":
            show_lbl = "* 6502 ASM ACTIVE"
            top_lbl = "* 6502 ASM (^E)"
            is_toggled = True
        elif self.asm_focus_mode:
            back_lang = "C" if self.file_mode == "c" else ("DEF" if self.file_mode == "def" else "PYTHON")
            show_lbl = f"HIDE ASM → {back_lang} [^E]"
            top_lbl = "HIDE ASM (^E)"
            is_toggled = True
        else:
            show_lbl = "SHOW ASM [^E]"
            top_lbl = "SHOW ASM (^E)"
            is_toggled = False

        for toggle_btn, txt_val in ((self.btn_show_asm, show_lbl), (self.btn_asm_focus, top_lbl)):
            toggle_btn.configure(
                text=txt_val,
                font=f_btn,
                bg=str(t["accent"]) if is_toggled else str(t["panel_bg"]),
                fg="#000000" if is_toggled else str(t["accent_bright"]),
            )

        # Keep Tab 1 title crystal-clear about which single editor is active
        if "tab-asm" in self.tab_buttons:
            if self.file_kind == "sid" and self.file_mode == "asm":
                tab1_lbl = "1:EDITOR [SID]"
            elif self.file_mode == "asm":
                tab1_lbl = "1:EDITOR [ASM]"
            elif self.asm_focus_mode:
                tab1_lbl = "1:ASM VIEW"
            elif self.file_mode == "c":
                tab1_lbl = "1:EDITOR [C]"
            elif self.file_kind == "build":
                tab1_lbl = "1:EDITOR [BUILD.PY]"
            elif self.file_mode == "def":
                tab1_lbl = "1:EDITOR [DEF]"
            else:
                tab1_lbl = "1:EDITOR [PY]"
            self.tab_buttons["tab-asm"].configure(text=tab1_lbl)

    def _set_agy_live_banner(self, visible: bool, message: str = "") -> None:
        """Show or hide the live Antigravity CLI status strip above the single editor."""
        if not self.root.winfo_exists():
            return
        if visible:
            if message:
                self.agy_live_lbl.configure(text=message)
            if self.agy_live_bar.winfo_manager() != "pack":
                anchor = self.file_tab_bar if self.file_tab_bar.winfo_manager() == "pack" else self.left_hdr_bar
                self.agy_live_bar.pack(fill=tk.X, pady=(0, 4), before=anchor)
        else:
            self.agy_live_bar.pack_forget()

    def _update_tab_button_styles(self) -> None:
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        for tid, tb in self.tab_buttons.items():
            is_act = tid == self._active_tab
            tb.configure(
                font=(font_fam, 8, "bold"),
                bg=str(t["button_active_bg"]) if is_act else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_act else str(t["panel_fg"]),
            )

    def switch_tab(self, tab_id: str) -> None:
        if tab_id == "tab-editor":
            tab_id = "tab-asm"
        self._active_tab = tab_id
        for pane in (self.pane_asm, self.pane_log, self.pane_ast, self.pane_hw, self.pane_agy):
            pane.pack_forget()
        if tab_id == "tab-asm":
            self._sync_editor_display()
            self.pane_asm.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-log":
            self.pane_log.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-ast":
            self.pane_ast.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-hw":
            self.pane_hw.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-agy":
            self.pane_agy.pack(fill=tk.BOTH, expand=True)
        self._update_tab_button_styles()

    # -----------------------------------------------------------------------
    # Syntax Highlighting, Line Numbers & 6502 ASM Editor Power Features
    # -----------------------------------------------------------------------

    def _configure_syntax_tags(self) -> None:
        t = THEMES[self.current_theme]
        for widget in (self.asm_text, self.py_text):
            widget.tag_configure("opcode", foreground=str(t["syn_opcode"]))
            widget.tag_configure("directive", foreground=str(t["syn_directive"]))
            widget.tag_configure("number", foreground=str(t["syn_number"]))
            widget.tag_configure("label", foreground=str(t["syn_label"]))
            widget.tag_configure("hardware", foreground=str(t["syn_hardware"]))
            widget.tag_configure("string", foreground=str(t["syn_string"]))
            widget.tag_configure("comment", foreground=str(t["syn_comment"]))
            widget.tag_configure("find_match", background=str(t["accent"]), foreground="#000000")
            widget.tag_configure("agy_edit_line", background="#2A5866", foreground=str(t["accent_bright"]))

    def _highlight_asm_editor(self) -> None:
        import bisect

        text = self.asm_text.get("1.0", "end-1c")
        for tag in ("opcode", "directive", "number", "label", "hardware", "string", "comment"):
            self.asm_text.tag_remove(tag, "1.0", tk.END)

        if not text:
            self._update_asm_gutter_and_labels(text)
            return

        # Precompute line start offsets so converting char offset -> "line.col" is O(log L) instead of O(N) in Tk
        line_starts = [0]
        for idx, ch in enumerate(text):
            if ch == "\n":
                line_starts.append(idx + 1)

        def _pos_to_index(pos: int) -> str:
            ln = bisect.bisect_right(line_starts, pos)
            col = pos - line_starts[ln - 1]
            return f"{ln}.{col}"

        for pattern, tag in (
            (ASM_OPCODES_PATTERN, "opcode"),
            (ASM_DIRECTIVES_PATTERN, "directive"),
            (ASM_HEX_PATTERN, "number"),
            (ASM_HW_PATTERN, "hardware"),
            (ASM_LABEL_PATTERN, "label"),
            (STRING_PATTERN, "string"),
            (ASM_COMMENT_PATTERN, "comment"),
        ):
            spans: list[str] = []
            for m in pattern.finditer(text):
                spans.append(_pos_to_index(m.start()))
                spans.append(_pos_to_index(m.end()))
            if spans:
                # Batch tag_add in chunks of 2000 indices for instant Tk rendering on 10,000+ line files
                for i in range(0, len(spans), 2000):
                    self.asm_text.tag_add(tag, *spans[i : i + 2000])

        self._update_asm_gutter_and_labels(text)

    def _update_asm_gutter_and_labels(self, text: str) -> None:
        lines = text.split("\n")
        line_count = max(1, len(lines))
        gutter_str = "\n".join(f"{i:4d}" for i in range(1, line_count + 1))
        self.asm_gutter.configure(state="normal")
        self.asm_gutter.delete("1.0", tk.END)
        self.asm_gutter.insert("1.0", gutter_str)
        self.asm_gutter.configure(state="disabled")
        self.asm_gutter.yview_moveto(self.asm_text.yview()[0])

        # Refresh 6502 Label & Subroutine Navigator
        self.label_listbox.delete(0, tk.END)
        self._label_line_map.clear()
        for line_no, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith(";"):
                continue
            lbl_match = re.match(r"^([!a-zA-Z_][a-zA-Z0-9_]*):", stripped)
            if lbl_match:
                self.label_listbox.insert(tk.END, f"L{line_no:<4d} {lbl_match.group(1)}:")
                self._label_line_map.append(line_no)
            elif stripped.startswith("* =") or stripped.startswith("*="):
                self.label_listbox.insert(tk.END, f"L{line_no:<4d} {stripped[:28]}")
                self._label_line_map.append(line_no)
            elif stripped.startswith(".const ") or stripped.startswith(".label "):
                self.label_listbox.insert(tk.END, f"L{line_no:<4d} {stripped[:28]}")
                self._label_line_map.append(line_no)

    def _highlight_py_editor(self) -> None:
        import bisect

        text = self.py_text.get("1.0", "end-1c")
        for tag in ("opcode", "directive", "number", "hardware", "string", "comment"):
            self.py_text.tag_remove(tag, "1.0", tk.END)

        if text:
            line_starts = [0]
            for idx, ch in enumerate(text):
                if ch == "\n":
                    line_starts.append(idx + 1)

            def _pos_to_index(pos: int) -> str:
                ln = bisect.bisect_right(line_starts, pos)
                col = pos - line_starts[ln - 1]
                return f"{ln}.{col}"

            syntax_rules = (
                (
                    (C_KEYWORDS_PATTERN, "opcode"),
                    (C_PREPROC_PATTERN, "directive"),
                    (ASM_HEX_PATTERN, "number"),
                    (C_HW_PATTERN, "hardware"),
                    (STRING_PATTERN, "string"),
                    (C_COMMENT_PATTERN, "comment"),
                )
                if self.file_mode == "c"
                else (
                    (PY_KEYWORDS_PATTERN, "opcode"),
                    (PY_INTRINSICS_PATTERN, "directive"),
                    (ASM_HEX_PATTERN, "number"),
                    (STRING_PATTERN, "string"),
                    (PY_COMMENT_PATTERN, "comment"),
                )
            )
            for pattern, tag in syntax_rules:
                spans: list[str] = []
                for m in pattern.finditer(text):
                    spans.append(_pos_to_index(m.start()))
                    spans.append(_pos_to_index(m.end()))
                if spans:
                    for i in range(0, len(spans), 2000):
                        self.py_text.tag_add(tag, *spans[i : i + 2000])

        line_count = max(1, text.count("\n") + 1)
        gutter_str = "\n".join(f"{i:4d}" for i in range(1, line_count + 1))
        self.py_gutter.configure(state="normal")
        self.py_gutter.delete("1.0", tk.END)
        self.py_gutter.insert("1.0", gutter_str)
        self.py_gutter.configure(state="disabled")
        self.py_gutter.yview_moveto(self.py_text.yview()[0])

    def _on_asm_scroll(self, *args) -> None:
        self.asm_scroll.set(*args)
        self.asm_gutter.yview_moveto(args[0])

    def _yview_asm_both(self, *args) -> None:
        self.asm_text.yview(*args)
        self.asm_gutter.yview(*args)

    def _on_py_scroll(self, *args) -> None:
        self.py_scroll.set(*args)
        self.py_gutter.yview_moveto(args[0])

    def _yview_py_both(self, *args) -> None:
        self.py_text.yview(*args)
        self.py_gutter.yview(*args)

    def _on_asm_changed(self, _event=None) -> None:
        self._highlight_asm_editor()
        self._on_asm_cursor_move()

    def _on_asm_cursor_move(self, _event=None) -> None:
        try:
            idx = self.asm_text.index(tk.INSERT)
            ln, col = idx.split(".")
            total_lines = int(self.asm_text.index("end-1c").split(".")[0])
            self.asm_cursor_lbl.configure(text=f"LN {ln}/{total_lines}, COL {int(col) + 1}")
        except Exception:
            pass

    def _on_py_changed(self, _event=None) -> None:
        self._highlight_py_editor()
        self._on_py_cursor_move()

    def _on_py_cursor_move(self, _event=None) -> None:
        try:
            idx = self.py_text.index(tk.INSERT)
            ln, col = idx.split(".")
            total_lines = int(self.py_text.index("end-1c").split(".")[0])
            self.py_cursor_lbl.configure(text=f"LN {ln}/{total_lines}, COL {int(col) + 1}")
        except Exception:
            pass

    def _on_asm_return_autoindent(self, _event=None) -> str:
        """Smart 6502 assembly auto-indent on Enter."""
        line_start = self.asm_text.index("insert linestart")
        line_end = self.asm_text.index("insert")
        cur_line = self.asm_text.get(line_start, line_end)
        indent_match = re.match(r"^(\s*)", cur_line)
        indent = indent_match.group(1) if indent_match else ""
        if cur_line.strip().endswith(":"):
            indent = "    "
        self.asm_text.insert(tk.INSERT, "\n" + indent)
        self.asm_text.see(tk.INSERT)
        self._on_asm_changed()
        return "break"

    def _on_label_nav_selected(self, _event=None) -> None:
        sel = self.label_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._label_line_map):
            line_no = self._label_line_map[idx]
            if self.file_mode != "asm":
                self.asm_focus_mode = True
            self.switch_tab("tab-asm")
            target = f"{line_no}.0"
            self.asm_text.mark_set(tk.INSERT, target)
            self.asm_text.see(target)
            self.asm_text.focus_set()
            self._on_asm_cursor_move()

    def _on_find_or_goto(self, _event=None) -> None:
        query = self.find_var.get().strip()
        if not query:
            return
        self.switch_tab("tab-asm")
        in_asm = self._is_asm_view_active()
        widget = self.asm_text if in_asm else self.py_text
        cursor_cb = self._on_asm_cursor_move if in_asm else self._on_py_cursor_move
        widget.tag_remove("find_match", "1.0", tk.END)

        # If numeric, jump to line number
        if query.isdigit():
            line_no = max(1, int(query))
            target = f"{line_no}.0"
            widget.mark_set(tk.INSERT, target)
            widget.see(target)
            widget.tag_add("find_match", target, f"{line_no}.end")
            widget.focus_set()
            cursor_cb()
            return

        # Otherwise search text from current cursor position (wrapping around)
        start_pos = widget.index(f"{tk.INSERT}+1c")
        pos = widget.search(query, start_pos, stopindex=tk.END, nocase=True)
        if not pos:
            pos = widget.search(query, "1.0", stopindex=tk.END, nocase=True)
        if pos:
            end_pos = f"{pos}+{len(query)}c"
            widget.tag_add("find_match", pos, end_pos)
            widget.mark_set(tk.INSERT, pos)
            widget.see(pos)
            widget.focus_set()
            cursor_cb()
        else:
            self.notify(f'"{query}" NOT FOUND IN EDITOR', severity="warning")

    def action_toggle_source_comment(self) -> str:
        """Toggle `# ` (Python) or `// ` (C) comment prefix on selected lines in the source editor."""
        prefix = "//" if self.file_mode == "c" else "#"
        try:
            start_ln = int(self.py_text.index("sel.first").split(".")[0])
            end_ln = int(self.py_text.index("sel.last").split(".")[0])
        except tk.TclError:
            start_ln = int(self.py_text.index(tk.INSERT).split(".")[0])
            end_ln = start_ln

        for ln in range(start_ln, end_ln + 1):
            line_txt = self.py_text.get(f"{ln}.0", f"{ln}.end")
            stripped = line_txt.lstrip()
            leading = line_txt[: len(line_txt) - len(stripped)]
            if stripped.startswith(f"{prefix} "):
                new_line = leading + stripped[len(prefix) + 1 :]
            elif stripped.startswith(prefix):
                new_line = leading + stripped[len(prefix) :]
            else:
                new_line = f"{leading}{prefix} {stripped}"
            self.py_text.delete(f"{ln}.0", f"{ln}.end")
            self.py_text.insert(f"{ln}.0", new_line)

        self._highlight_py_editor()
        return "break"

    def action_toggle_asm_comment(self) -> str:
        """Toggle `// ` comment prefix on the current line or selected lines in the 6502 ASM editor."""
        try:
            start_ln = int(self.asm_text.index("sel.first").split(".")[0])
            end_ln = int(self.asm_text.index("sel.last").split(".")[0])
        except tk.TclError:
            start_ln = int(self.asm_text.index(tk.INSERT).split(".")[0])
            end_ln = start_ln

        for ln in range(start_ln, end_ln + 1):
            line_txt = self.asm_text.get(f"{ln}.0", f"{ln}.end")
            stripped = line_txt.lstrip()
            leading = line_txt[: len(line_txt) - len(stripped)]
            if stripped.startswith("// "):
                new_line = leading + stripped[3:]
            elif stripped.startswith("//"):
                new_line = leading + stripped[2:]
            else:
                new_line = leading + "// " + stripped
            self.asm_text.delete(f"{ln}.0", f"{ln}.end")
            self.asm_text.insert(f"{ln}.0", new_line)

        self._highlight_asm_editor()
        return "break"

    def action_new_asm_template(self) -> None:
        """Load a clean KickAssembler 6502 starter template into a new or clean untitled tab."""
        tab = self._open_or_reuse_untitled_tab("untitled.asm")
        self._begin_load("asm", None)
        self.file_mode = "asm"
        self.asm_focus_mode = False
        self.agy_lang_var.set("asm")
        self.last_asm = NEW_ASM_TEMPLATE
        self._set_asm_text(NEW_ASM_TEMPLATE)
        self._set_python_text("")
        tab.title_hint = "untitled.asm"
        self._mark_editor_synced()
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new 6502 KickAssembler template in editor.")
        self.notify("NEW 6502 .ASM TEMPLATE READY")

    def action_new_c_template(self) -> None:
        """Switch to C/C++ (Oscar64 / CC65) mode and load a clean C64 starter template in a tab."""
        tab = self._open_or_reuse_untitled_tab("untitled.c")
        self._begin_load("c", None)
        self.file_mode = "c"
        self.asm_focus_mode = False
        self.agy_lang_var.set("c")
        self._set_python_text(NEW_C_TEMPLATE)
        self._set_asm_text("")
        self.last_asm = ""
        tab.title_hint = "untitled.c"
        self._mark_editor_synced()
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new C64 C99 (Oscar64 / CC65) template in editor.")
        self.notify("NEW C64 .C (OSCAR64) TEMPLATE READY")

    def action_new_py_template(self) -> None:
        """Switch to Python-to-6502 mode and load a clean bare-metal Python template in a tab."""
        tab = self._open_or_reuse_untitled_tab("untitled.py")
        self._begin_load("python", None)
        self.file_mode = "py"
        self.asm_focus_mode = False
        self.agy_lang_var.set("py")
        self._set_python_text(NEW_PY_TEMPLATE)
        tab.title_hint = "untitled.py"
        self._mark_editor_synced()
        self.action_transpile_code(silent=True)
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new Python-to-6502 template in editor.")
        self.notify("NEW C64 .PY TEMPLATE READY")

    def action_new_sid_template(self) -> None:
        """Switch to SID Music mode and load a compilable MOS 6581/8580 PSID v2 driver into a tab."""
        tab = self._open_or_reuse_untitled_tab("untitled_sid.asm")
        self._begin_load("sid", None)
        self.file_mode = "asm"
        self.asm_focus_mode = False
        self.agy_lang_var.set("asm")
        self.last_asm = NEW_SID_TEMPLATE
        self._set_asm_text(NEW_SID_TEMPLATE)
        self._set_python_text("")
        tab.title_hint = "untitled_sid.asm"
        self._mark_editor_synced()
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new MOS 6581/8580 PSID v2 (.SID) music driver template in editor.")
        self.notify("NEW C64 .SID MUSIC TEMPLATE READY")

    def action_new_file_dialog(self) -> None:
        """Open the New File modal so the user can choose C, Python, 6502 ASM, or SID."""
        modal = NewFileModal()
        self._last_new_file_modal = modal
        modal.show_tk(self)

    def action_open_game_generator_dialog(self, preset_kind: str = "sprites") -> None:
        """Open the C64 Game Generation Studio modal (Sprites, SID SFX, Tiles, Full Games)."""
        modal = GameAssetGenModal(initial_kind=preset_kind)
        self._last_game_gen_modal = modal
        modal.show_tk(self)

    def _run_ai_game_generation(self, kind: str, target_fmt: str, brief: str) -> None:
        """Generate C64 sprites, SID sound/music, tiles, or a playable game via Antigravity CLI into the IDE."""
        self.agy_auto_apply_var.set(True)
        self.agy_include_ctx_var.set(True)

        if target_fmt == "sid" or kind == "sfx_sid" and target_fmt == "sid":
            self._begin_load("sid", self.loaded_file if self.file_kind == "sid" else None)
            self.file_mode = "asm"
            self.asm_focus_mode = False
            self.agy_lang_var.set("asm")
            prompt = (
                f"Generate a complete, KickAssembler v5.x compilable Commodore 64 PSID v2 music/SFX driver for: {brief}.\n"
                "CRITICAL: Include a valid `// C64U_SID_METADATA: {\"magic\": \"PSID\", \"version\": 2, \"data_offset\": 124, "
                "\"load_address\": 4096, \"init_address\": 4096, \"play_address\": 4099, \"songs\": 1, \"start_song\": 1, "
                "\"speed\": 0, \"name\": \"GENERATED SID\", \"author\": \"C64 STUDIO\", \"released\": \"2026\", "
                "\"flags\": 20, \"embedded_load_address\": true}` comment header, `* = $1000`, `jmp sid_init` at `$1000`, "
                "and `jmp sid_play` at `$1003` so C64 Studio can compile it straight to `.sid` and play it on C64U."
            )
            self.action_send_agy_prompt(prompt_override=prompt, force_language="asm")
            return

        studio_lang = target_fmt if target_fmt in ("asm", "py", "c", "def") else "asm"
        if studio_lang == "def" and kind == "sprites":
            self._begin_load("sprites", None)
            self.file_mode = "def"
        self.agy_lang_var.set(studio_lang)

        kind_instructions = {
            "sprites": (
                f"Generate Commodore 64 VIC-II hardware sprite data and animation demo code ({studio_lang.upper()}) for: {brief}. "
                "Include clean 64-byte aligned sprite blocks (e.g. `$2000`), sprite pointers at `$07F8+`, multicolor/hi-res register setup "
                "(`$D015`, `$D01C`, `$D025`..`$D02E`), and smooth raster-timed movement so it compiles and runs immediately on C64U."
            ),
            "sfx_sid": (
                f"Generate Commodore 64 MOS 6581/8580 SID sound effects / chiptune routine ({studio_lang.upper()}) for: {brief}. "
                "Program `$D400..$D418` voices, ADSR envelopes, and waveforms so it compiles cleanly and plays on C64U."
            ),
            "tiles_screen": (
                f"Generate Commodore 64 custom character set / tile screen and color RAM layout ({studio_lang.upper()}) for: {brief}. "
                "Populate `$0400` Screen RAM and `$D800` Color RAM so it compiles cleanly and runs on C64U."
            ),
            "full_game": (
                f"Generate a complete, self-contained playable Commodore 64 arcade game ({studio_lang.upper()}) for: {brief}. "
                "Include Joystick Port 2 (`$DC00`) controls, VIC-II sprites/graphics, score HUD, and SID sound effects so it compiles cleanly."
            ),
        }
        prompt = kind_instructions.get(kind, f"Generate Commodore 64 ({studio_lang.upper()}) game asset/code for: {brief}")
        self.action_send_agy_prompt(prompt_override=prompt, force_language=studio_lang)

    def action_promote_to_asm(self) -> None:
        """Convert the currently generated 6502 Assembly into a primary editable .ASM tab."""
        if self.file_mode == "py" and not self.asm_text.get("1.0", "end-1c").strip():
            self.action_transpile_code(silent=True)
        asm_code = self.asm_text.get("1.0", "end-1c")
        if not asm_code.strip():
            self.notify("NO 6502 ASM GENERATED YET — BUILD OR TRANSPILE FIRST", severity="warning")
            return
        stem = self.loaded_file.stem if self.loaded_file else "promoted"
        tab = self._open_or_reuse_untitled_tab(f"{stem}_promoted.asm")
        self._begin_load("asm", None)
        self.file_mode = "asm"
        self.asm_focus_mode = False
        self.agy_lang_var.set("asm")
        self.last_asm = asm_code
        self._set_asm_text(asm_code)
        self._set_python_text("")
        tab.title_hint = f"{stem}_promoted.asm"
        self._sync_active_tab_from_widgets()
        tab.baseline_text = ""
        tab.needs_disk_save = True
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self.asm_text.focus_set()
        self._write_log("✓ Promoted generated 6502 Assembly to primary editable .ASM buffer.")
        self.notify("EDITING CONVERTED 6502 .ASM DIRECTLY")

    def action_select_language(self, lang: str) -> None:
        """Switch active C64 Studio single-screen editor language between 'asm', 'c', 'py', and 'sid'."""
        norm = lang.lower().strip()
        if norm not in {"asm", "c", "py", "sid"}:
            return
        if norm == "sid":
            curr_asm = self.asm_text.get("1.0", "end-1c")
            if "C64U_SID_METADATA:" not in curr_asm and not self.last_sid_path:
                tab = self._open_or_reuse_untitled_tab("untitled_sid.asm")
                self._begin_load("sid", None)
                self.file_mode = "asm"
                self.file_kind = "sid"
                self.asm_focus_mode = False
                self.agy_lang_var.set("asm")
                self.last_asm = NEW_SID_TEMPLATE
                self._set_asm_text(NEW_SID_TEMPLATE)
                self._set_python_text("")
                tab.title_hint = "untitled_sid.asm"
                self._mark_editor_synced()
            else:
                self.file_mode = "asm"
                self.file_kind = "sid"
                self.asm_focus_mode = False
                self.agy_lang_var.set("asm")
                self._sync_active_tab_from_widgets()
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self.asm_text.focus_set()
            self.notify("C64 STUDIO LANGUAGE MODE: SID (.SID)")
            return

        prev_mode = self.file_mode
        if norm == "asm":
            if prev_mode == "py" and self.py_text.get("1.0", "end-1c").strip():
                self.action_transpile_code(silent=True)
            was_sid = self.file_kind == "sid"
            curr_asm = self.asm_text.get("1.0", "end-1c").strip()
            if not curr_asm or (was_sid and curr_asm == NEW_SID_TEMPLATE.strip()):
                tab = self._open_or_reuse_untitled_tab("untitled.asm")
                self._begin_load("asm", None)
                self.file_mode = "asm"
                self.asm_focus_mode = False
                self.agy_lang_var.set("asm")
                self.last_asm = NEW_ASM_TEMPLATE
                self._set_asm_text(NEW_ASM_TEMPLATE)
                self._set_python_text("")
                tab.title_hint = "untitled.asm"
                self._mark_editor_synced()
            else:
                self.file_mode = "asm"
                self.file_kind = "asm"
                self.asm_focus_mode = False
                self.agy_lang_var.set("asm")
                self._sync_active_tab_from_widgets()
            self.switch_tab("tab-asm")
            self.asm_text.focus_set()
        else:
            curr_lhs = self.py_text.get("1.0", "end-1c").strip()
            if norm == "c":
                if not curr_lhs or "border_color(" in curr_lhs or "while True:" in curr_lhs:
                    tab = self._open_or_reuse_untitled_tab("untitled.c")
                    self._begin_load("c", None)
                    self.file_mode = "c"
                    self.asm_focus_mode = False
                    self.agy_lang_var.set("c")
                    self._set_python_text(NEW_C_TEMPLATE)
                    self._set_asm_text("")
                    self.last_asm = ""
                    tab.title_hint = "untitled.c"
                    self._mark_editor_synced()
                else:
                    self.file_mode = "c"
                    self.file_kind = "c"
                    self.asm_focus_mode = False
                    self.agy_lang_var.set("c")
                    self._highlight_py_editor()
                    self._sync_active_tab_from_widgets()
            else:
                if not curr_lhs or "#include" in curr_lhs:
                    tab = self._open_or_reuse_untitled_tab("untitled.py")
                    self._begin_load("python", None)
                    self.file_mode = "py"
                    self.asm_focus_mode = False
                    self.agy_lang_var.set("py")
                    self._set_python_text(NEW_PY_TEMPLATE)
                    tab.title_hint = "untitled.py"
                    self._mark_editor_synced()
                    self.action_transpile_code(silent=True)
                else:
                    self.file_mode = "py"
                    self.file_kind = "python"
                    self.asm_focus_mode = False
                    self.agy_lang_var.set("py")
                    self._highlight_py_editor()
                    self._sync_active_tab_from_widgets()
            self.switch_tab("tab-asm")
            self.py_text.focus_set()

        self._update_mode_badge()
        self.notify(f"C64 STUDIO LANGUAGE MODE: {norm.upper()}")

    def _on_left_build_clicked(self) -> None:
        """Convert Python/C to 6502 ASM (or run build.py / test-compile SID) and toggle ASM view when applicable."""
        if self.file_kind == "sid":
            self.action_compile_sid()
            return
        if self.file_mode == "def" or (self.loaded_file and self.loaded_file.name.lower() == "build.py"):
            self.action_build()
            return
        if self.file_mode == "c":
            self.action_build()
            if self.asm_text.get("1.0", "end-1c").strip() and self._last_compile_error is None:
                self.asm_focus_mode = True
                self.switch_tab("tab-asm")
                self._update_mode_badge()
        elif self.file_mode == "py":
            source = self.py_text.get("1.0", "end-1c")
            if not source.strip():
                self.notify("PYTHON EDITOR IS EMPTY", severity="warning")
                return
            res = self.transpiler.transpile(source)
            if res.success:
                self.last_asm = res.assembly
                self._set_asm_text(res.assembly)
                self._update_ast_tree(res)
                self.asm_focus_mode = True
                self.switch_tab("tab-asm")
                self._update_mode_badge()
                self.notify(f"TRANSPILED ({len(res.assembly.splitlines())} LINES 6502 ASM)")
            else:
                err_txt = "\n".join(res.errors)
                self._handle_compile_failure("PYTHON → 6502 TRANSPILE", err_txt, "py")

    def _update_language_button_styles(self) -> None:
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        is_sid = self.file_kind in ("sid", "song")
        for lc, btn in self.lang_buttons.items():
            is_act = (lc == self.file_mode) and not (is_sid and lc == "asm")
            btn.configure(
                font=(font_fam, 8, "bold"),
                bg=str(t["button_active_bg"]) if is_act else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_act else str(t["panel_fg"]),
            )
        if hasattr(self, "btn_lang_sid"):
            self.btn_lang_sid.configure(
                font=(font_fam, 8, "bold"),
                bg=str(t["button_active_bg"]) if is_sid else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_sid else str(t["panel_fg"]),
            )

    def action_toggle_asm_focus(self) -> None:
        """Toggle between the primary coding editor (Python/C/Def) and the 6502 ASM view."""
        self.asm_focus_mode = not self.asm_focus_mode
        if self.file_mode == "asm":
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self.asm_text.focus_set()
            self.notify("6502 ASM EDITOR ACTIVE (SELECT PYTHON OR C/OSCAR TO SWITCH LANGUAGE)")
            return

        if self.asm_focus_mode:
            if self.file_mode == "py" and self.py_text.get("1.0", "end-1c").strip():
                self.action_transpile_code(silent=True)
            elif (
                self.file_mode == "c"
                and not self.asm_text.get("1.0", "end-1c").strip()
                and self.py_text.get("1.0", "end-1c").strip()
            ):
                self._set_asm_text(
                    "// Press F7 (BUILD) or click 'C → ASM [F7]' to compile with Oscar64/CC65\n"
                    "// and inspect the disassembled 6502 machine instructions here.\n"
                )
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self.asm_text.focus_set()
            self.notify("SHOWING 6502 ASM VIEW (CLICK 'HIDE ASM' OR CTRL+E TO RETURN)")
        else:
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self.py_text.focus_set()
            self.notify(f"RETURNED TO {self.file_mode.upper()} EDITOR")

    def action_toggle_fullscreen(self) -> None:
        """Toggle F11 borderless fullscreen C64 monitor mode."""
        self.is_fullscreen = not self.is_fullscreen
        try:
            self.root.attributes("-fullscreen", self.is_fullscreen)
            if not self.is_fullscreen:
                self.root.state("zoomed")
        except tk.TclError:
            pass

    def action_focus_find(self) -> None:
        self.switch_tab("tab-asm")
        entry = self.find_entry if self._is_asm_view_active() else self.py_find_entry
        entry.focus_set()
        entry.selection_range(0, tk.END)

    def _update_mode_badge(self) -> None:
        """Show the active file, language header, ASM toggle state, `*` unsaved mark, and stage."""
        active_tab = self._get_active_file_tab()
        dirty_suffix = " *" if (active_tab is not None and active_tab.is_dirty) else ""
        if self.loaded_file:
            fname = f"{self.loaded_file.name}{dirty_suffix}"
        elif self._has_source():
            if self.file_kind == "sid":
                fname = f"UNTITLED.SID{dirty_suffix}"
            elif self.file_mode == "asm":
                fname = f"UNTITLED.ASM{dirty_suffix}"
            elif self.file_mode == "c":
                fname = f"UNTITLED.C{dirty_suffix}"
            else:
                fname = f"UNTITLED.PY{dirty_suffix}"
        else:
            fname = "NOTHING LOADED"
        steps = ("LOAD", "COMPILE", "SEND C64U")
        marks = " > ".join(f"*{step}*" if i < self.stage else step for i, step in enumerate(steps))
        badge_txt = f"NOTHING LOADED  |  {marks}" if fname == "NOTHING LOADED" else marks
        self.mode_badge_lbl.configure(text=badge_txt)

        if self.file_kind == "sid" and self.file_mode == "asm":
            hdr_txt = f"SID MUSIC SOURCE (MOS 6581/8580 PSID)  //  {fname.upper()}"
        elif self.file_mode == "asm":
            hdr_txt = f"6502 ASSEMBLY (KICKASSEMBLER V5.X)  //  {fname.upper()}"
        elif self.asm_focus_mode:
            src_name = "C / OSCAR64" if self.file_mode == "c" else "PYTHON"
            hdr_txt = f"GENERATED 6502 ASSEMBLY ({src_name})  //  {fname.upper()}"
        elif self.file_mode == "def":
            title = KIND_LABELS.get(self.file_kind, KIND_LABELS["python"])
            hdr_txt = f"{title}  //  {fname.upper()}"
        else:
            default_kind = "c" if self.file_mode == "c" else "python"
            title = KIND_LABELS.get(self.file_kind, KIND_LABELS[default_kind])
            hdr_txt = f"{title}  //  {fname.upper()}" if fname != "NOTHING LOADED" else title
        self.left_title_lbl.configure(text=hdr_txt)

        if self.file_kind == "sid":
            conv_lbl = "TEST .SID [F7]"
            conv_state = tk.NORMAL
        elif self.file_kind == "build" or (self.loaded_file and self.loaded_file.name.lower() == "build.py"):
            conv_lbl = "▶ RUN BUILD.PY [F7]"
            conv_state = tk.NORMAL
        elif self.file_mode == "def":
            conv_lbl = "BUILD ASSET [F7]"
            conv_state = tk.NORMAL
        elif self.file_mode == "c":
            conv_lbl = "C → ASM [F7]"
            conv_state = tk.NORMAL
        elif self.file_mode == "py":
            conv_lbl = "PY → ASM [F6]"
            conv_state = tk.NORMAL
        else:
            conv_lbl = "PY → ASM [F6]"
            conv_state = tk.DISABLED
        self.btn_py_to_asm.configure(text=conv_lbl, state=conv_state)

        if hasattr(self, "agy_lang_var") and self.file_mode in ("asm", "c", "py", "def"):
            self.agy_lang_var.set(self.file_mode)
        if hasattr(self, "lang_buttons"):
            self._update_language_button_styles()
        if hasattr(self, "btn_show_asm"):
            self._sync_editor_display()
        if hasattr(self, "file_tab_bar"):
            self._render_file_tab_bar()

    def _set_stage(self, stage: int) -> None:
        self.stage = stage
        self._update_mode_badge()

    # -----------------------------------------------------------------------
    # Outer VIC-II Border, Rainbow Strip & Bottom DMA Deck Drawing
    # -----------------------------------------------------------------------

    def _on_border_resize(self, event) -> None:
        pad = 18
        w = max(320, event.width - pad * 2)
        h = max(240, event.height - pad * 2)
        self.border_canvas.coords(self.screen_window_id, pad, pad)
        self.border_canvas.itemconfigure(self.screen_window_id, width=w, height=h)
        self._draw_border_and_divider()

    def _draw_border_and_divider(self) -> None:
        t = THEMES[self.current_theme]
        self.border_canvas.delete("border_stripes")
        w = max(self.border_canvas.winfo_width(), 1024)
        h = max(self.border_canvas.winfo_height(), 768)

        if self._border_busy:
            palette = list(t["border_active_1"]) if (self._anim_tick % 2 == 0) else list(t["border_active_2"])
            stripe_h = 8
            for y in range(0, h, stripe_h):
                color = palette[(self._anim_tick + (y // stripe_h)) % len(palette)]
                self.border_canvas.create_rectangle(
                    0, y, w, y + stripe_h, fill=color, outline="", tags="border_stripes"
                )
            self.border_canvas.tag_lower("border_stripes")
        else:
            self.border_canvas.configure(bg=str(t["border_idle"]))

        self.divider_canvas.delete("all")
        dw = max(self.divider_canvas.winfo_width(), 960)
        rainbow = list(t["rainbow"])
        seg_w = dw / len(rainbow)
        for i, col in enumerate(rainbow):
            self.divider_canvas.create_rectangle(
                i * seg_w, 0, (i + 1) * seg_w, 5, fill=col, outline=""
            )

    def _draw_bottom_deck(self) -> None:
        t = THEMES[self.current_theme]
        c = self.deck_canvas
        c.delete("all")
        w = max(c.winfo_width(), 900)
        h = 30
        font_fam = str(t["font_family"])

        cas_img = self._deck_cas_badge_img or self._cassette_badge_img
        c64_img = self._deck_c64_badge_img or self._c64_badge_img
        if cas_img is not None:
            c.create_image(26, h // 2, image=cas_img)
        if c64_img is not None:
            c.create_image(w - 30, h // 2, image=c64_img)

        bar_x1 = 60
        bar_x2 = w - 66
        bar_y1 = 4
        bar_y2 = 26
        bar_w = max(40, bar_x2 - bar_x1)

        c.create_rectangle(
            bar_x1, bar_y1, bar_x2, bar_y2,
            outline=str(t["accent_bright"]), width=1, fill=str(t["bar_bg"])
        )

        num_blocks = 28
        gap = 3
        block_w = (bar_w - 8 - (num_blocks - 1) * gap) / num_blocks
        filled = int(round(self._busy_progress * num_blocks))

        for b in range(num_blocks):
            bx1 = bar_x1 + 4 + b * (block_w + gap)
            bx2 = bx1 + block_w
            if b < filled:
                if self._border_busy and (b + self._anim_tick) % 6 == 0:
                    col = str(t["accent_bright"])
                else:
                    col = str(t["bar_fg"]) if (b % 2 == 0) else str(t["bar_alt"])
                c.create_rectangle(bx1, bar_y1 + 3, bx2, bar_y2 - 3, fill=col, outline="")
            else:
                c.create_rectangle(bx1, bar_y1 + 3, bx2, bar_y2 - 3, fill="#0D0826", outline="")

        badge_txt = f" {self._busy_phase} "
        tid = c.create_text(
            (bar_x1 + bar_x2) / 2,
            (bar_y1 + bar_y2) / 2,
            text=badge_txt,
            font=(font_fam, 8, "bold"),
            fill=str(t["accent_bright"]),
        )
        bbox = c.bbox(tid)
        if bbox:
            bg_id = c.create_rectangle(
                bbox[0] - 8, bar_y1 + 2, bbox[2] + 8, bar_y2 - 2,
                fill="#000000", outline=str(t["accent"])
            )
            c.tag_lower(bg_id, tid)

    def _pulse_raster_border(self, phase_label: str, duration_ms: int = 420) -> None:
        """Flash authentic C64 VIC-II raster bars on the outer border during build/DMA actions."""
        self._border_busy = True
        self._busy_phase = phase_label
        self._busy_progress = 1.0
        self._draw_border_and_divider()
        self._draw_bottom_deck()

        def _stop_busy():
            if not self.root.winfo_exists() or self._agy_busy:
                return
            self._border_busy = False
            self._busy_phase = "READY // DMA LINK IDLE"
            self._draw_border_and_divider()
            self._draw_bottom_deck()

        self.root.after(duration_ms, _stop_busy)

    def _tick_animation(self) -> None:
        if not self.root.winfo_exists():
            return
        self._anim_tick = (self._anim_tick + 1) % 10000
        t = THEMES[self.current_theme]

        if self._agy_busy:
            elapsed_s = max(0, int(time.monotonic() - getattr(self, "_agy_started_at", time.monotonic())))
            base_phase = getattr(self, "_agy_status_base", "ANTIGRAVITY CLI GENERATING")
            self._busy_phase = f"{base_phase} [{elapsed_s}S]"[:46]
            if self._anim_tick % 6 == 0:
                short_btn = base_phase.replace("AGY ", "")[:14]
                self.btn_agy_send.configure(text=f"... {short_btn} ({elapsed_s}s)")
                self._set_agy_live_banner(
                    True,
                    f"▶ {base_phase} [{elapsed_s}s] — Live-editing active editor buffer",
                )
        if self._border_busy:
            self._draw_border_and_divider()
            self._draw_bottom_deck()
        cursor_char = "█" if (self._anim_tick // 5) % 2 == 0 else " "
        base_text = getattr(self, "_last_status_message", str(t["ready_prompt"]))
        display_status = base_text if len(base_text) <= 54 else f"{base_text[:51]}..."
        self.prompt_lbl.configure(text=f"{display_status} {cursor_char}")
        if getattr(self, "_in_mainloop", False) and (self._anim_tick % 10 == 0):
            self._poll_external_cli_activity()

        self.root.after(80, self._tick_animation)

    def notify(self, message: str, severity: str = "information", title: str = "") -> None:
        """Display status notification in the C64 READY prompt bar and bottom deck."""
        prefix = "READY."
        if severity == "error":
            prefix = "?SYNTAX/BUILD ERROR:"
        elif severity == "warning":
            prefix = "CAUTION:"
        self._last_status_message = f"{prefix} {message}"
        self._busy_phase = message.upper()[:46]
        if self.root.winfo_exists():
            display_status = (
                self._last_status_message
                if len(self._last_status_message) <= 54
                else f"{self._last_status_message[:51]}..."
            )
            self.prompt_lbl.configure(text=f"{display_status} █")
            self._draw_bottom_deck()

    def _write_log(self, line: str) -> None:
        clean = re.sub(r"\[/?[a-zA-Z0-9_ ]+\]", "", line)
        if self.root.winfo_exists():
            self.log_text.insert(tk.END, clean + "\n")
            self.log_text.see(tk.END)

    def _clear_build_log(self) -> None:
        self.log_text.delete("1.0", tk.END)

    def _set_python_text(self, code: str) -> None:
        self.py_text.delete("1.0", tk.END)
        self.py_text.insert("1.0", code)
        self._highlight_py_editor()
        self._on_py_cursor_move()
        if not getattr(self, "_restoring_tab", False) and getattr(self, "open_tabs", None):
            self.py_text.edit_modified(False)
            self._sync_active_tab_from_widgets()
            self._update_mode_badge()

    def _set_asm_text(self, asm_code: str) -> None:
        self.asm_text.delete("1.0", tk.END)
        self.asm_text.insert("1.0", asm_code)
        self._highlight_asm_editor()
        self._on_asm_cursor_move()
        if not getattr(self, "_restoring_tab", False) and getattr(self, "open_tabs", None):
            self.asm_text.edit_modified(False)
            self._sync_active_tab_from_widgets()
            self._update_mode_badge()

    # -----------------------------------------------------------------------
    # Keyboard Shortcuts & On-Screen Menu Bar Navigation
    # -----------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        self.root.bind("<F1>", lambda _e: self.action_show_help())
        self.root.bind("<F2>", lambda _e: self.action_open_presets())
        self.root.bind("<F3>", lambda _e: self.action_open_file())
        self.root.bind("<F4>", lambda _e: self.action_refresh_connection())
        self.root.bind("<F5>", lambda _e: self.action_run_c64u())
        self.root.bind("<F6>", lambda _e: self.action_transpile_code())
        self.root.bind("<F7>", lambda _e: self.action_build())
        self.root.bind("<F8>", lambda _e: self.action_reset_c64u())
        self.root.bind("<F10>", lambda _e: self.action_focus_menu())
        self.root.bind("<F11>", lambda _e: self.action_toggle_fullscreen())
        self.root.bind("<F12>", lambda _e: self.action_export_hyperload())

        self.root.bind("<Shift-F1>", lambda _e: self.action_save_file())
        self.root.bind("<Shift-F2>", lambda _e: self.action_export_tap())
        self.root.bind("<Shift-F3>", lambda _e: self.action_load_prg_only())
        self.root.bind("<Shift-F4>", lambda _e: self.action_pause_cpu())
        self.root.bind("<Shift-F5>", lambda _e: self.action_resume_cpu())
        self.root.bind("<Shift-F6>", lambda _e: self.action_dump_screen())
        self.root.bind("<Shift-F7>", lambda _e: self.action_reboot_c64u())
        self.root.bind("<Shift-F8>", lambda _e: self.action_quit())
        self.root.bind("<Shift-F9>", lambda _e: self.action_compile_d64())
        self.root.bind("<Shift-F10>", lambda _e: self.action_open_sprite_studio())
        self.root.bind("<Shift-F11>", lambda _e: self.action_validation_report())
        self.root.bind("<Shift-F12>", lambda _e: self.action_focus_agy_prompt())

        self.root.bind("<Control-s>", lambda _e: self.action_save_file())
        self.root.bind("<Control-S>", lambda _e: self.action_save_all_files())
        self.root.bind("<Control-w>", lambda _e: self.action_close_active_tab())
        self.root.bind("<Control-Tab>", lambda _e: self.action_next_file_tab())
        self.root.bind("<Control-k>", lambda _e: self.action_open_agy_setup())
        self.root.bind("<Alt-a>", lambda _e: self.action_focus_agy_prompt())
        self.root.bind("<Control-p>", lambda _e: self.action_play_sid())
        self.root.bind("<Control-e>", lambda _e: self.action_toggle_asm_focus())
        self.root.bind("<Control-n>", lambda _e: self.action_new_asm_template())
        self.root.bind("<Control-f>", lambda _e: self.action_focus_find())
        self.root.bind("<Control-q>", lambda _e: self.action_quit())

        self.root.bind("<Alt-f>", lambda _e: self.action_focus_submenu("file"))
        self.root.bind("<Alt-b>", lambda _e: self.action_focus_submenu("build"))
        self.root.bind("<Alt-c>", lambda _e: self.action_focus_submenu("device"))
        self.root.bind("<Alt-h>", lambda _e: self.action_focus_submenu("help"))
        self.root.bind("<Alt-g>", lambda _e: self.action_focus_submenu("gamedev"))

        self.root.bind("<Key>", self._on_global_key)

    def _on_global_key(self, event) -> None:
        if self._splash_win is not None and self._splash_win.winfo_exists():
            self._dismiss_splash_screen()
            return
        if event.keysym == "Escape" and self._open_menu_category is not None:
            self.close_menu_drawer()
            self.focused_button_id = None
            return
        if self.focused_button_id and event.keysym in ("Up", "Down", "Left", "Right", "Escape"):
            self.navigate_menu_key(event.keysym.lower())

    def _on_btn_focus(self, btn_id: str) -> None:
        self.focused_button_id = btn_id

    def _invoke_menu_btn(self, btn_id: str, fn: Callable[[], None]) -> None:
        self.focused_button_id = btn_id
        self.close_menu_drawer()
        fn()

    def action_focus_menu(self) -> None:
        """Toggle the full 5-column menu drawer (F10) and focus the File column."""
        if self._open_menu_category == "all":
            self.close_menu_drawer()
            self.focused_button_id = None
            return
        self._open_menu_category = "all"
        self._sync_menu_drawer()
        self.focused_button_id = "btn-open"
        btn = self.menu_buttons.get("btn-open")
        if btn:
            try:
                btn.focus_set()
            except tk.TclError:
                pass

    def action_focus_submenu(self, category: str) -> None:
        target_map = {
            "file": "btn-open",
            "build": "quick-btn-run",
            "device": "btn-refresh",
            "gamedev": "btn-gd-game",
            "help": "btn-presets",
        }
        if self._open_menu_category != "all":
            self._open_menu_category = category if category in target_map else "file"
            self._sync_menu_drawer()
        btn_id = target_map.get(category, "btn-open")
        self.focused_button_id = btn_id
        btn = self.menu_buttons.get(btn_id)
        if btn:
            try:
                btn.focus_set()
            except tk.TclError:
                pass

    def navigate_menu_key(self, key: str) -> None:
        """Navigate across the C64 menu categories and buttons using arrow keys."""
        if not self.focused_button_id:
            return
        cats = ["file", "build", "device", "gamedev", "help"]
        cur_col = -1
        cur_row = -1
        for c_idx, cat in enumerate(cats):
            col_items = self.menu_columns[cat]
            if self.focused_button_id in col_items:
                cur_col = c_idx
                cur_row = col_items.index(self.focused_button_id)
                break
        if cur_col == -1:
            return

        if key == "up" and cur_row > 0:
            next_id = self.menu_columns[cats[cur_col]][cur_row - 1]
        elif key == "down" and cur_row < len(self.menu_columns[cats[cur_col]]) - 1:
            next_id = self.menu_columns[cats[cur_col]][cur_row + 1]
        elif key == "left":
            nc = (cur_col - 1) % len(cats)
            if self._open_menu_category not in (None, "all"):
                self._open_menu_category = cats[nc]
                self._sync_menu_drawer()
            nr = min(cur_row, len(self.menu_columns[cats[nc]]) - 1)
            next_id = self.menu_columns[cats[nc]][nr]
        elif key == "right":
            nc = (cur_col + 1) % len(cats)
            if self._open_menu_category not in (None, "all"):
                self._open_menu_category = cats[nc]
                self._sync_menu_drawer()
            nr = min(cur_row, len(self.menu_columns[cats[nc]]) - 1)
            next_id = self.menu_columns[cats[nc]][nr]
        elif key == "escape":
            self.close_menu_drawer()
            self.focused_button_id = None
            target_editor = self.asm_text if self._is_asm_view_active() else self.py_text
            target_editor.focus_set()
            return
        else:
            return

        self.focused_button_id = next_id
        btn = self.menu_buttons.get(next_id)
        if btn:
            try:
                btn.focus_set()
            except tk.TclError:
                pass

    # -----------------------------------------------------------------------
    # Core Actions: Transpile, Assemble, DMA Run, Decompile, D64/TAP/SID
    # -----------------------------------------------------------------------

    def check_bridge_status(self, notify_user: bool = False) -> None:
        """Poll C64U bridge hardware reachability in a background thread."""
        t = THEMES[self.current_theme]
        if self.root.winfo_exists():
            self.bridge_status_lbl.configure(
                text=f"● C64U: PING ({self.client.host})...",
                fg=str(t["warning"]),
            )

        def _worker():
            try:
                quick = C64UClient(
                    host=self.client.host,
                    port=self.client.port,
                    password=self.client.password,
                    timeout=1.2,
                )
                info = quick.get_info()
                ver = info.get("version", "ONLINE")

                def _ok():
                    if not self.root.winfo_exists():
                        return
                    self.bridge_status_lbl.configure(
                        text=f"● C64U: ONLINE ({ver})",
                        fg=str(THEMES[self.current_theme]["success"]),
                    )
                    if notify_user:
                        self._write_log(f"✓ C64U ONLINE: Version {ver} (http://{self.client.host}:{self.client.port})")
                        self.notify(f"C64U ONLINE ({ver})")

                try:
                    self.root.after(0, _ok)
                except (tk.TclError, RuntimeError):
                    pass
            except Exception as exc:
                def _err(exc=exc):     # Python deletes `exc` when this except block ends
                    if not self.root.winfo_exists():
                        return
                    self.bridge_status_lbl.configure(
                        text=f"○ C64U: OFFLINE ({self.client.host})",
                        fg=str(THEMES[self.current_theme]["danger"]),
                    )
                    if notify_user:
                        self._write_log(f"✗ C64U OFFLINE at http://{self.client.host}:{self.client.port} ({exc})")
                        self.notify(f"C64U OFFLINE ({self.client.host})", severity="warning")

                try:
                    self.root.after(0, _err)
                except (tk.TclError, RuntimeError):
                    pass

        if getattr(self, "_in_mainloop", False):
            threading.Thread(target=_worker, daemon=True).start()
        elif notify_user:
            self.bridge_status_lbl.configure(
                text=f"● C64U: PING ({self.client.host})...",
                fg=str(t["warning"]),
            )
            self._write_log(f"Ping C64U at http://{self.client.host}:{self.client.port}...")

    def action_transpile_code(self, silent: bool = False) -> bool:
        """Transpile Python (MOS 6502 Dialect) source into 6502 Assembly."""
        if self.file_mode == "c":
            self._assemble_current(package_extra=False)
            return self._last_compile_error is None
        if self.file_mode == "def":
            if not silent:
                self.notify("THIS FILE IS BUILT WITH F7, NOT TRANSPILED", severity="warning")
            return False
        source = self.py_text.get("1.0", "end-1c")
        if not source.strip():
            if not silent:
                self._write_log("No Python source code in LHS editor to transpile.")
                self.notify("PYTHON EDITOR IS EMPTY", severity="warning")
            return False

        if not silent:
            self._pulse_raster_border("TRANSPILING PYTHON → 6502 ASM", 350)
            self._write_log("Transpiling Python source to 6502 assembly...")

        result = self.transpiler.transpile(source)
        if result.success:
            self.last_asm = result.assembly
            self._set_asm_text(result.assembly)
            self._update_ast_tree(result)
            line_cnt = len(result.assembly.splitlines())
            if not silent:
                self._write_log(f"✓ Transpiled successfully ({line_cnt} lines of 6502 assembly).")
                self.notify(f"TRANSPILED ({line_cnt} LINES 6502 ASM)")
            return True
        else:
            for err in result.errors:
                self._write_log(f"Error: {err}")
            if not silent:
                self.notify("TRANSPILATION FAILED", severity="error")
            return False

    def _update_ast_tree(self, result: TranspileResult) -> None:
        self.ast_listbox.delete(0, tk.END)
        self.ast_listbox.insert(tk.END, "=== SYMBOLS & ZERO-PAGE VARIABLES ===")
        for sym_name, sym_val in sorted(result.symbols.items()):
            self.ast_listbox.insert(tk.END, f"  {sym_name:<20} = {sym_val}")
        self.ast_listbox.insert(tk.END, "")
        self.ast_listbox.insert(tk.END, "=== PYTHON AST HIERARCHY ===")
        if result.ast_tree:
            for stmt in getattr(result.ast_tree, "body", []):
                stmt_desc = f"  {type(stmt).__name__}: {ast.unparse(stmt)[:54]}"
                self.ast_listbox.insert(tk.END, stmt_desc)

    def _has_source(self) -> bool:
        return bool(self.py_text.get("1.0", "end-1c").strip() or self.asm_text.get("1.0", "end-1c").strip())

    def _editor_text(self) -> str:
        """The text of the loaded file: assembly in ASM mode, the left pane otherwise."""
        widget = self.asm_text if self.file_mode == "asm" else self.py_text
        return widget.get("1.0", "end-1c")

    def _asm_unchanged(self) -> bool:
        return self.asm_text.get("1.0", "end-1c").strip() == self.last_asm.strip()

    def _binary_unchanged(self) -> bool:
        """A loaded .prg whose disassembly has not been edited runs as it is."""
        return bool(self.binary_source and self.binary_source.is_file() and self._asm_unchanged())

    # -----------------------------------------------------------------------
    # Multi-File Open Tabs, Dirty `*` Tracking & Pre-Compile Save Prompt
    # -----------------------------------------------------------------------

    def _new_tab_id(self) -> str:
        self._next_tab_seq += 1
        return f"ftab-{self._next_tab_seq}"

    def _get_tab_by_id(self, tab_id: Optional[str]) -> Optional[EditorTabState]:
        if not tab_id:
            return None
        for tab in self.open_tabs:
            if tab.tab_id == tab_id:
                return tab
        return None

    def _get_active_file_tab(self) -> Optional[EditorTabState]:
        return self._get_tab_by_id(self.active_file_tab_id)

    def _ensure_active_file_tab(self, title_hint: str = "untitled") -> EditorTabState:
        existing = self._get_active_file_tab()
        if existing is not None:
            return existing
        hint = self.loaded_file.name if self.loaded_file is not None else title_hint
        tab = EditorTabState(
            tab_id=self._new_tab_id(),
            title_hint=hint,
            loaded_file=self.loaded_file,
            file_mode=self.file_mode,
            file_kind=self.file_kind,
            py_content=self.py_text.get("1.0", "end-1c"),
            asm_content=self.asm_text.get("1.0", "end-1c"),
            baseline_text=self._last_synced_editor_text,
            needs_disk_save=False,
            asm_focus_mode=self.asm_focus_mode,
            binary_source=self.binary_source,
            last_asm=self.last_asm,
            last_prg_path=self.last_prg_path,
            last_sid_path=self.last_sid_path,
            stage=self.stage,
        )
        self.open_tabs.append(tab)
        self.active_file_tab_id = tab.tab_id
        return tab

    def _sync_active_tab_from_widgets(self) -> Optional[EditorTabState]:
        tab = self._get_active_file_tab()
        if tab is None:
            if not self._has_source() and self.loaded_file is None:
                return None
            tab = self._ensure_active_file_tab()
        tab.loaded_file = self.loaded_file
        tab.file_mode = self.file_mode
        tab.file_kind = self.file_kind
        tab.py_content = self.py_text.get("1.0", "end-1c")
        tab.asm_content = self.asm_text.get("1.0", "end-1c")
        tab.asm_focus_mode = self.asm_focus_mode
        tab.binary_source = self.binary_source
        tab.last_asm = self.last_asm
        tab.last_prg_path = self.last_prg_path
        tab.last_sid_path = self.last_sid_path
        tab.stage = self.stage
        try:
            tab.py_cursor = self.py_text.index(tk.INSERT)
            tab.asm_cursor = self.asm_text.index(tk.INSERT)
        except tk.TclError:
            pass
        return tab

    def _apply_tab_to_widgets(self, tab: EditorTabState) -> None:
        self._restoring_tab = True
        try:
            self.loaded_file = tab.loaded_file
            self.file_mode = tab.file_mode
            self.file_kind = tab.file_kind
            self.asm_focus_mode = tab.asm_focus_mode
            self.binary_source = tab.binary_source
            self.last_asm = tab.last_asm
            self.last_prg_path = tab.last_prg_path
            self.last_sid_path = tab.last_sid_path
            self.stage = tab.stage
            self._set_python_text(tab.py_content)
            self._set_asm_text(tab.asm_content)
            try:
                self.py_text.mark_set(tk.INSERT, tab.py_cursor)
                self.asm_text.mark_set(tk.INSERT, tab.asm_cursor)
            except tk.TclError:
                pass
            try:
                self.py_text.edit_modified(False)
                self.asm_text.edit_modified(False)
            except tk.TclError:
                pass
            self._last_synced_editor_text = tab.baseline_text
        finally:
            self._restoring_tab = False
        self._update_mode_badge()

    def _find_open_tab_for_path(self, path: Path) -> Optional[EditorTabState]:
        try:
            target_res = path.resolve()
        except OSError:
            target_res = path
        for tab in self.open_tabs:
            for candidate in (tab.loaded_file, tab.binary_source, tab.last_sid_path):
                if candidate is not None:
                    try:
                        if candidate.resolve() == target_res:
                            return tab
                    except OSError:
                        if candidate == path:
                            return tab
        return None

    def _activate_or_open_tab_for_path(self, path: Path) -> tuple[EditorTabState, bool]:
        """
        Switch to an already-open tab for `path` (preserving unsaved `*` edits if dirty),
        or open a dedicated new tab so existing open files are never overwritten.
        Returns `(tab, preserved_dirty_in_memory)`.
        """
        self._sync_active_tab_from_widgets()
        existing = self._find_open_tab_for_path(path)
        if existing is not None:
            self.active_file_tab_id = existing.tab_id
            if existing.is_dirty:
                self._apply_tab_to_widgets(existing)
                return existing, True
            return existing, False

        cur = self._get_active_file_tab()
        if (
            cur is not None
            and cur.loaded_file is None
            and cur.binary_source is None
            and cur.last_sid_path is None
            and not cur.is_dirty
            and not cur.py_content.strip()
            and not cur.asm_content.strip()
        ):
            cur.title_hint = path.name
            cur.loaded_file = path
            return cur, False

        new_tab = EditorTabState(
            tab_id=self._new_tab_id(),
            title_hint=path.name,
            loaded_file=path,
        )
        self.open_tabs.append(new_tab)
        self.active_file_tab_id = new_tab.tab_id
        return new_tab, False

    def _open_or_reuse_untitled_tab(self, title_hint: str = "untitled") -> EditorTabState:
        """Reuse an untouched untitled tab, or open a new untitled tab so loaded/dirty files stay open."""
        self._sync_active_tab_from_widgets()
        cur = self._get_active_file_tab()
        if (
            cur is not None
            and cur.loaded_file is None
            and cur.binary_source is None
            and cur.last_sid_path is None
            and not cur.is_dirty
        ):
            cur.title_hint = title_hint
            return cur

        new_tab = EditorTabState(
            tab_id=self._new_tab_id(),
            title_hint=title_hint,
        )
        self.open_tabs.append(new_tab)
        self.active_file_tab_id = new_tab.tab_id
        return new_tab

    def _on_py_modified_event(self, _event=None) -> None:
        try:
            if not self.py_text.edit_modified():
                return
            self.py_text.edit_modified(False)
        except tk.TclError:
            return
        if self._restoring_tab:
            return
        if self.open_tabs or self.py_text.get("1.0", "end-1c").strip():
            self._sync_active_tab_from_widgets()
            self._update_mode_badge()

    def _on_asm_modified_event(self, _event=None) -> None:
        try:
            if not self.asm_text.edit_modified():
                return
            self.asm_text.edit_modified(False)
        except tk.TclError:
            return
        if self._restoring_tab:
            return
        if self.open_tabs or self.asm_text.get("1.0", "end-1c").strip():
            self._sync_active_tab_from_widgets()
            self._update_mode_badge()

    def _render_file_tab_bar(self) -> None:
        """Render the horizontal open-file tab strip (`hero.asm *`, `build.py`, etc.)."""
        if not hasattr(self, "file_tab_bar") or not self.root.winfo_exists():
            return
        for child in list(self.file_tabs_inner.winfo_children()):
            child.destroy()
        self.file_tab_buttons.clear()
        self.file_tab_close_buttons.clear()

        if not self.open_tabs:
            self.btn_save_all_tabs.pack_forget()
            self.file_tab_bar.pack_forget()
            return

        if self.file_tab_bar.winfo_manager() != "pack":
            self.file_tab_bar.pack(fill=tk.X, pady=(0, 3), before=self.left_hdr_bar)

        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        f_tab = (font_fam, 8, "bold")
        f_close = (font_fam, 7, "bold")

        dirty_cnt = sum(1 for tab in self.open_tabs if tab.is_dirty)
        if dirty_cnt > 0:
            self.btn_save_all_tabs.configure(
                text=f"SAVE ALL ({dirty_cnt}) *" if dirty_cnt > 1 else "SAVE *"
            )
            if self.btn_save_all_tabs.winfo_manager() != "pack":
                self.btn_save_all_tabs.pack(side=tk.RIGHT, padx=(4, 0))
        else:
            self.btn_save_all_tabs.pack_forget()

        for tab in self.open_tabs:
            is_act = tab.tab_id == self.active_file_tab_id
            is_dirty = tab.is_dirty
            if is_act and is_dirty:
                chip_bg = str(t["warning"])
                chip_fg = "#000000"
                border_col = str(t["accent_bright"])
            elif is_act:
                chip_bg = str(t["button_active_bg"])
                chip_fg = str(t["button_active_fg"])
                border_col = str(t["accent_bright"])
            elif is_dirty:
                chip_bg = str(t["editor_bg"])
                chip_fg = str(t["warning"])
                border_col = str(t["warning"])
            else:
                chip_bg = str(t["editor_bg"])
                chip_fg = str(t["ink"])
                border_col = str(t["button_bg"])

            chip = tk.Frame(
                self.file_tabs_inner,
                bg=chip_bg,
                highlightthickness=1,
                highlightbackground=border_col,
            )
            chip.pack(side=tk.LEFT, padx=(0, 4), pady=1)

            btn_lbl = tk.Button(
                chip,
                text=tab.display_name(),
                command=lambda tid=tab.tab_id: self.switch_file_tab(tid),
                font=f_tab,
                bg=chip_bg,
                fg=chip_fg,
                activebackground=str(t["button_active_bg"]),
                activeforeground=str(t["warning"]) if is_dirty else str(t["button_active_fg"]),
                relief=tk.FLAT,
                bd=0,
                padx=7,
                pady=2,
                cursor="hand2",
            )
            btn_lbl.pack(side=tk.LEFT)
            btn_lbl.bind("<Button-2>", lambda _e, tid=tab.tab_id: self.close_file_tab(tid))

            btn_x = tk.Button(
                chip,
                text="x",
                command=lambda tid=tab.tab_id: self.close_file_tab(tid),
                font=f_close,
                bg=chip_bg,
                fg=str(t["panel_fg"]) if not is_act else str(t["button_active_fg"]),
                activebackground=str(t["danger"]),
                activeforeground="#FFFFFF",
                relief=tk.FLAT,
                bd=0,
                padx=4,
                pady=2,
                cursor="hand2",
            )
            btn_x.pack(side=tk.LEFT)

            self.file_tab_buttons[tab.tab_id] = btn_lbl
            self.file_tab_close_buttons[tab.tab_id] = btn_x

    def switch_file_tab(self, tab_id: str) -> bool:
        """Switch the active IDE editor view to `tab_id`, preserving edits in all open tabs."""
        self._sync_active_tab_from_widgets()
        target = self._get_tab_by_id(tab_id)
        if target is None:
            return False
        self.active_file_tab_id = target.tab_id
        self._apply_tab_to_widgets(target)
        self.switch_tab("tab-asm")
        return True

    def action_next_file_tab(self) -> str:
        """Cycle through open file tabs (`Ctrl+Tab`)."""
        if len(self.open_tabs) >= 2:
            self._sync_active_tab_from_widgets()
            ids = [t.tab_id for t in self.open_tabs]
            cur_idx = ids.index(self.active_file_tab_id) if self.active_file_tab_id in ids else 0
            nxt_id = ids[(cur_idx + 1) % len(ids)]
            self.switch_file_tab(nxt_id)
        return "break"

    def action_close_active_tab(self) -> None:
        """Close the currently active file tab (`Ctrl+W`), prompting if it has unsaved `*` changes."""
        if self.active_file_tab_id is not None:
            self.close_file_tab(self.active_file_tab_id)

    def close_file_tab(self, tab_id: str, *, force: bool = False) -> None:
        """Close `tab_id`, asking to save first if the tab has unsaved `*` changes."""
        self._sync_active_tab_from_widgets()
        tab = self._get_tab_by_id(tab_id)
        if tab is None:
            return
        if tab.is_dirty and not force:
            prev = getattr(self, "_last_unsaved_modal", None)
            if prev is not None and getattr(prev, "dlg", None) is not None:
                try:
                    if prev.dlg.winfo_exists():
                        prev.dlg.destroy()
                except tk.TclError:
                    pass
            modal = UnsavedChangesModal([tab], mode="close")
            self._last_unsaved_modal = modal

            def _on_close_choice(choice: str) -> None:
                if choice == "save":
                    if self._save_tab(tab):
                        self.close_file_tab(tab_id, force=True)
                elif choice == "skip":
                    self.close_file_tab(tab_id, force=True)

            modal.show_tk(self, _on_close_choice)
            return

        idx = next((i for i, t in enumerate(self.open_tabs) if t.tab_id == tab_id), -1)
        if idx == -1:
            return
        was_active = tab_id == self.active_file_tab_id
        self.open_tabs.pop(idx)

        if self.open_tabs:
            if was_active:
                next_tab = self.open_tabs[min(idx, len(self.open_tabs) - 1)]
                self.active_file_tab_id = next_tab.tab_id
                self._apply_tab_to_widgets(next_tab)
            else:
                self._render_file_tab_bar()
        else:
            self.active_file_tab_id = None
            self._restoring_tab = True
            try:
                self.loaded_file = None
                self.file_kind = ""
                self.file_mode = "py"
                self.asm_focus_mode = False
                self.binary_source = None
                self.last_asm = ""
                self.last_prg_path = None
                self.last_sid_path = None
                self.stage = 1
                self._set_python_text("")
                self._set_asm_text("")
                self._last_synced_editor_text = ""
                try:
                    self.py_text.edit_modified(False)
                    self.asm_text.edit_modified(False)
                except tk.TclError:
                    pass
            finally:
                self._restoring_tab = False
            self._update_mode_badge()

    def _get_dirty_tabs(self) -> list[EditorTabState]:
        """Sync active widgets and return every open tab that currently needs saving (`*`)."""
        self._sync_active_tab_from_widgets()
        return [tab for tab in self.open_tabs if tab.is_dirty]

    def _save_tab(self, tab: EditorTabState) -> bool:
        """Write `tab` to disk (prompting for filename if untitled) and clear its `*` indicator."""
        if tab.tab_id == self.active_file_tab_id:
            self._sync_active_tab_from_widgets()
        text = tab.primary_text()
        if tab.loaded_file is None:
            fd_mod = _tui_attr("filedialog", filedialog)
            target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
            ext = ".asm" if tab.file_mode == "asm" else (".c" if tab.file_mode == "c" else ".py")
            init_name = tab.base_name()
            if not Path(init_name).suffix:
                init_name = f"{init_name}{ext}"
            chosen = fd_mod.asksaveasfilename(
                title=f"SAVE {init_name.upper()}",
                initialdir=target_dir_fn(),
                initialfile=init_name,
                defaultextension=ext,
            )
            if not chosen:
                return False
            tab.loaded_file = Path(chosen)
            tab.title_hint = tab.loaded_file.name
        elif tab.loaded_file.suffix.lower() in (".prg", ".bin", ".d64", ".tap", ".sid"):
            # Never overwrite binary media images with disassembled text
            tab.loaded_file = tab.loaded_file.with_name(f"{tab.loaded_file.stem}_decompiled.asm")

        tab.loaded_file.write_text(text, encoding="utf-8")
        self._record_self_saved_file(tab.loaded_file)
        tab.baseline_text = text
        tab.needs_disk_save = False
        if tab.file_mode == "asm":
            tab.last_asm = text

        if tab.tab_id == self.active_file_tab_id:
            self.loaded_file = tab.loaded_file
            if self.file_mode == "asm":
                self.last_asm = text
            self._last_synced_editor_text = text

        self._write_log(f"✓ Saved {tab.loaded_file}")
        self._update_mode_badge()
        return True

    def action_save_all_files(self) -> bool:
        """Save all dirty `*` open tabs (or the active tab if none are marked dirty)."""
        dirty = self._get_dirty_tabs()
        targets = dirty if dirty else ([self._get_active_file_tab()] if self._get_active_file_tab() else [])
        targets = [t for t in targets if t is not None]
        if not targets:
            self.notify("NOTHING TO SAVE", severity="warning")
            return False
        saved_names: list[str] = []
        for tab in targets:
            if not self._save_tab(tab):
                return False
            if tab.loaded_file is not None:
                saved_names.append(tab.loaded_file.name)
        if saved_names:
            summary = ", ".join(saved_names[:3])
            if len(saved_names) > 3:
                summary += f" (+{len(saved_names) - 3})"
            self.notify(f"SAVED {summary.upper()}")
        return True

    def _confirm_save_before_compile(self, on_proceed: Callable[[bool], None]) -> None:
        """
        If any open tab has unsaved `*` changes, prompt the user to Save & Compile,
        Compile Without Saving, or Cancel. Calls `on_proceed(allow_unsaved)` when continuing.
        """
        dirty = self._get_dirty_tabs()
        if not dirty:
            on_proceed(False)
            return

        prev = getattr(self, "_last_unsaved_modal", None)
        if prev is not None and getattr(prev, "dlg", None) is not None:
            try:
                if prev.dlg.winfo_exists():
                    prev.dlg.destroy()
            except tk.TclError:
                pass

        modal = UnsavedChangesModal(dirty, mode="compile")
        self._last_unsaved_modal = modal

        def _on_choice(choice: str) -> None:
            if choice == "save":
                for tab in list(dirty):
                    if not self._save_tab(tab):
                        self.notify("SAVE CANCELLED — COMPILE ABORTED", severity="warning")
                        return
                on_proceed(False)
            elif choice == "skip":
                on_proceed(True)
            else:
                self.notify("COMPILE CANCELLED — UNSAVED CHANGES PRESERVED")

        modal.show_tk(self, _on_choice)

    def _mark_editor_synced(self) -> None:
        """Mark the active editor buffer as cleanly synced with its current baseline."""
        txt = self._editor_text()
        self._last_synced_editor_text = txt
        tab = self._sync_active_tab_from_widgets()
        if tab is not None:
            tab.baseline_text = tab.primary_text()
            tab.needs_disk_save = False
        try:
            self.py_text.edit_modified(False)
            self.asm_text.edit_modified(False)
        except tk.TclError:
            pass
        if hasattr(self, "file_tab_bar"):
            self._render_file_tab_bar()

    def _is_editor_dirty(self) -> bool:
        """Return True when the active tab has unsaved edits (`*`)."""
        tab = self._sync_active_tab_from_widgets()
        if tab is not None:
            return tab.is_dirty
        cur = self._editor_text()
        if not cur.strip():
            return False
        if cur in (NEW_ASM_TEMPLATE, NEW_C_TEMPLATE, NEW_PY_TEMPLATE, NEW_SID_TEMPLATE):
            return False
        return cur != self._last_synced_editor_text

    def _record_self_saved_file(self, path: Path) -> None:
        """Record mtime of a file written by C64 Studio itself so the watcher ignores self-writes."""
        try:
            resolved = path.resolve()
            st = resolved.stat()
            self._self_written_mtimes[resolved] = st.st_mtime_ns
            self._workspace_watch_mtimes[resolved] = (st.st_mtime_ns, st.st_size)
        except OSError:
            pass

    def _save_loaded_file(self) -> None:
        """Save the active loaded source file if it has a valid non-binary path."""
        if not self.loaded_file or self.loaded_file.suffix.lower() in (".prg", ".bin", ".d64", ".tap", ".sid"):
            return
        tab = self._ensure_active_file_tab()
        self._save_tab(tab)

    def _project_manifest(self) -> Optional[Path]:
        """The game's build.py. A disassembly or SID source sits beside a game without being part of it."""
        if not self.loaded_file or self.file_kind in ("sid", "prg", "bin", "tap", "d64"):
            return None
        return find_manifest(self.loaded_file)

    def _extract_compile_error_line(self, error_detail: str) -> Optional[int]:
        """Extract a 1-based source line number from KickAssembler, Oscar64, CC65, or Python diagnostics."""
        for pat in (
            r"(?:at line\s+|line\s+)(\d+)",
            r"\((\d+)(?:[:,]\s*\d+)?\)",
            r":(\d+):\d*:",
            r":(\d+):",
        ):
            m = re.search(pat, error_detail, re.IGNORECASE)
            if m:
                try:
                    line_no = int(m.group(1))
                    if line_no >= 1:
                        return line_no
                except ValueError:
                    pass
        return None

    def _highlight_compile_error_line(self, error_detail: str, lang_mode: str) -> None:
        """Jump cursor and highlight the offending line in the IDE editor if present."""
        in_asm = lang_mode == "asm" or (self._is_asm_view_active() and lang_mode not in ("py", "c", "def"))
        widget = self.asm_text if in_asm else self.py_text
        cursor_cb = self._on_asm_cursor_move if in_asm else self._on_py_cursor_move
        widget.tag_remove("find_match", "1.0", tk.END)
        line_no = self._extract_compile_error_line(error_detail)
        if line_no is not None:
            total_lines = max(1, int(widget.index("end-1c").split(".")[0]))
            clamped = min(line_no, total_lines)
            target = f"{clamped}.0"
            widget.mark_set(tk.INSERT, target)
            widget.see(target)
            widget.tag_add("find_match", target, f"{clamped}.end")
            cursor_cb()

    def _focus_ide_at_compile_error(self, error_detail: str, lang_mode: str) -> None:
        """Keep the user in the IDE code editor at the error location so they can fix it themselves."""
        if lang_mode in ("py", "c", "def"):
            self.asm_focus_mode = False
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._highlight_compile_error_line(error_detail, lang_mode)
        target_widget = self.asm_text if self._is_asm_view_active() else self.py_text
        target_widget.focus_set()
        self.notify("FIX IN IDE — PRESS F7 TO RE-COMPILE")

    def _handle_compile_failure(self, stage_title: str, error_detail: str, lang_mode: str) -> None:
        """Log compile diagnostics, highlight the IDE line, and ask whether to auto-fix via Antigravity CLI."""
        detail = (error_detail or "Unknown compilation failure.").strip()
        self._last_compile_error = (stage_title, detail, lang_mode)
        self._write_log(f"✗ {stage_title} Failed:\n{detail}")
        if lang_mode in ("py", "c", "def"):
            self.asm_focus_mode = False
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._highlight_compile_error_line(detail, lang_mode)
        self.notify(f"{stage_title} FAILED — SEND TO AGY OR FIX IN IDE", severity="error")

        prev_modal = getattr(self, "_last_compile_error_modal", None)
        if prev_modal is not None and getattr(prev_modal, "dlg", None) is not None:
            try:
                if prev_modal.dlg.winfo_exists():
                    prev_modal.dlg.destroy()
            except tk.TclError:
                pass

        modal = CompileErrorFixModal(stage_title, detail, lang_mode)
        self._last_compile_error_modal = modal
        modal.show_tk(self)

    def action_autofix_compile_error(self, stage_title: str, error_detail: str, lang_mode: str) -> None:
        """Send the compiler error and active source code to Antigravity CLI (`agy`) for automatic fixing."""
        norm_lang = lang_mode if lang_mode in ("asm", "c", "py", "def") else "asm"
        self.agy_auto_apply_var.set(True)
        self.agy_include_ctx_var.set(True)
        self.agy_lang_var.set(norm_lang)

        extra_req = ""
        if self.file_kind == "sid":
            extra_req = (
                "\nCRITICAL SID REQUIREMENT: Preserve the `// C64U_SID_METADATA: {...}` header comment "
                "(or `SID_LOAD` / `SID_INIT` / `SID_PLAY` constants) and valid `$1000` init / `$1003` play entry points "
                "so C64 Studio can compile this directly to a `.sid` file."
            )
        elif self.file_kind == "build" or (self.loaded_file and self.loaded_file.name.lower() == "build.py"):
            game_dir = self.loaded_file.parent if self.loaded_file else Path.cwd()
            extra_req = (
                f"\nGAME BUILD.PY CONTEXT: `{self.loaded_file}` directs full game compilation in `{game_dir}`. "
                "If the build failure is in `build.py` itself, return the complete corrected `build.py` in a ```python block. "
                "If the failure is inside one of the game's `.asm`, `.c`, or asset `.py` files referenced by `build.py`, "
                "inspect and fix that file on disk so re-running `build.py` succeeds."
            )

        prompt = (
            f"Auto-fix this Commodore 64 {stage_title} compilation failure in the active {norm_lang.upper()} file.\n"
            f"Compiler diagnostics:\n```\n{error_detail.strip()}\n```\n"
            "Return the complete corrected source code in a single fenced code block so C64 Studio can apply "
            f"and compile it cleanly without errors.{extra_req}"
        )
        self.action_send_agy_prompt(prompt_override=prompt, force_language=norm_lang)

    def _sync_build_format_button(self) -> None:
        """Update the top-ribbon `OUT:` build target button label and active highlight."""
        if not hasattr(self, "btn_build_format"):
            return
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        f_btn = (font_fam, 8, "bold")
        cur = self.build_format_var.get()
        short_map = {code: short for code, short, _title, _desc in BUILD_OUTPUT_OPTIONS}
        short_lbl = short_map.get(cur, ".PRG")
        is_extra = cur != "prg"
        self.btn_build_format.configure(
            text=f"OUT: {short_lbl}",
            font=f_btn,
            bg=str(t["button_active_bg"]) if is_extra else str(t["button_bg"]),
            fg=str(t["button_active_fg"]) if is_extra else str(t["accent_bright"]),
            activebackground=str(t["button_active_bg"]),
            activeforeground=str(t["button_active_fg"]),
        )

    def set_build_format(self, fmt_code: str, notify_user: bool = False) -> None:
        """Select the build output packaging target (`prg`, `tap`, `hypertap`, `d64`, or `all`)."""
        valid_map = {code: title for code, _short, title, _desc in BUILD_OUTPUT_OPTIONS}
        if fmt_code not in valid_map:
            return
        self.build_format_var.set(fmt_code)
        self._sync_build_format_button()
        if notify_user:
            self._write_log(f"✓ Build output target set to: {valid_map[fmt_code]}")
            self.notify(f"BUILD TARGET: {valid_map[fmt_code]}")

    def cycle_build_format(self) -> str:
        """Cycle through `.PRG` -> `.TAP` -> `HYPER.TAP` -> `.D64` -> `ALL`."""
        codes = [opt[0] for opt in BUILD_OUTPUT_OPTIONS]
        cur = self.build_format_var.get()
        nxt = codes[(codes.index(cur) + 1) % len(codes)] if cur in codes else "prg"
        self.set_build_format(nxt, notify_user=True)
        return nxt

    def action_open_build_options(self) -> None:
        """Open the Build Output Packaging Modal (`.prg`, `.tap`, `Hyper.tap`, `.d64`, `all`)."""
        prev = getattr(self, "_last_build_output_modal", None)
        if prev is not None and getattr(prev, "dlg", None) is not None:
            try:
                if prev.dlg.winfo_exists():
                    prev.dlg.destroy()
            except tk.TclError:
                pass
        modal = BuildOutputModal(initial_format=self.build_format_var.get())
        self._last_build_output_modal = modal
        modal.show_tk(self)

    def action_build_with_format(self, fmt_code: str, on_done: Optional[Callable[[Optional[Path]], None]] = None) -> None:
        """Set the build output format (`prg`, `tap`, `hypertap`, `d64`, or `all`) and run `action_build`."""
        self.set_build_format(fmt_code, notify_user=False)
        self.action_build(on_done=on_done)

    @staticmethod
    def _hyperload_extra_args(prg: Path) -> tuple[str, ...]:
        """Supply `--entry` automatically when a raw machine-code PRG has no BASIC `SYS` stub."""
        try:
            raw = prg.read_bytes()
        except OSError:
            return ()
        if len(raw) >= 3 and not re.match(rb".{4}\x9e\s*(\d+)", raw[2:40], re.S):
            load_addr = raw[0] | (raw[1] << 8)
            if load_addr >= 0x0800 and load_addr != 0x0801:
                return ("--entry", f"0x{load_addr:04X}")
        return ()

    def _package_built_prg(self, prg: Path, fmt: Optional[str] = None) -> list[Path]:
        """Package a newly compiled `.prg` into `.tap`, `Hyper.tap` (`.hyper.tap`), and/or `.d64` if selected."""
        if self._suppress_auto_package or not prg.is_file():
            return []
        mode = (fmt or self.build_format_var.get() or "prg").strip().lower()
        if mode == "prg":
            return []

        created: list[Path] = []
        if mode in ("tap", "all"):
            self._pulse_raster_border("MASTERING .TAP CASSETTE IMAGE", 480)
            out_tap = prg.with_suffix(".tap")
            try:
                save_prg_to_tap(prg, tap_path=out_tap, tape_name=prg.stem)
                self.last_tap_path = out_tap
                created.append(out_tap)
                sz = out_tap.stat().st_size
                self._write_log(f"✓ TAP Cassette Image Generated: {out_tap} ({sz} bytes)")
            except Exception as exc:
                self._write_log(f"TAP Packaging Error: {exc}")
                self.notify(f"TAP EXPORT ERROR: {exc}", severity="error")

        if mode in ("hypertap", "all"):
            self._pulse_raster_border("MASTERING HYPER.TAP TURBO CASSETTE", 480)
            out_hyper = prg.with_suffix(".hyper.tap")
            extra_args = self._hyperload_extra_args(prg)
            res = run_tool("hyperload", prg, args=("-o", str(out_hyper), "--name", prg.stem, *extra_args))
            if res.ok and out_hyper.is_file():
                self.last_hyper_tap_path = out_hyper
                created.append(out_hyper)
                sz = out_hyper.stat().st_size
                self._write_log(f"✓ HYPER.TAP Turbo Cassette Generated: {out_hyper} ({sz} bytes)")
                for line in res.output.splitlines():
                    if line.strip():
                        self._write_log(f"  {line}")
            else:
                self._write_log(f"HYPER.TAP Packaging Error: {res.output}")
                err_tail = res.output.splitlines()[-1] if res.output else "see log"
                self.notify(f"HYPER.TAP ERROR: {err_tail}", severity="error")

        if mode in ("d64", "all"):
            self._pulse_raster_border("FORMATTING & WRITING 1541 .D64 DISK", 500)
            out_d64 = prg.with_suffix(".d64")
            try:
                save_prg_to_d64(prg, d64_path=out_d64, disk_name=prg.stem.upper()[:16])
                self.last_d64_path = out_d64
                created.append(out_d64)
                sz = out_d64.stat().st_size
                self._write_log(f"✓ 1541 D64 Disk Image Generated: {out_d64} ({sz} bytes)")
            except Exception as exc:
                self._write_log(f"D64 Packaging Error: {exc}")
                self.notify(f"D64 EXPORT ERROR: {exc}", severity="error")

        if created:
            names = ", ".join(p.name for p in created)
            self.notify(f"BUILT {prg.name} + {names}")
        return created

    def action_build(
        self,
        on_done: Optional[Callable[[Optional[Path]], None]] = None,
        *,
        package_extra: bool = True,
        _skip_save_prompt: bool = False,
    ) -> None:
        """Compile and test whatever is loaded before any hardware upload. Prompts to save if `*` dirty."""
        if not self._has_source():
            self.notify("NOTHING TO BUILD: F3 LOADS A FILE", severity="warning")
            return
        self._last_compile_error = None
        if self._binary_unchanged() and self.binary_source is not None and not self._get_dirty_tabs():
            self.last_prg_path = self.binary_source
            if package_extra:
                self._package_built_prg(self.binary_source)
            self._set_stage(max(self.stage, 2))
            if on_done:
                on_done(self.binary_source)
            return
        if not _skip_save_prompt and self._get_dirty_tabs():
            self._confirm_save_before_compile(
                lambda _allow_unsaved: self.action_build(
                    on_done=on_done,
                    package_extra=package_extra,
                    _skip_save_prompt=True,
                )
            )
            return

        if self.loaded_file and self.loaded_file.name.lower() == "build.py":
            self.file_kind = "build"
            self.file_mode = "def"
            self._sync_active_tab_from_widgets()
            self._write_log(f"Running {self.loaded_file} to direct full game compilation...")
            target_build = self.loaded_file
            cleanup_tmp: Optional[Path] = None
            if self._is_editor_dirty():
                cleanup_tmp = self.loaded_file.parent / f".{self.loaded_file.stem}_unsaved_preview.py"
                cleanup_tmp.write_text(self._editor_text(), encoding="utf-8")
                target_build = cleanup_tmp
            self._run_game_tool(
                "build",
                target_build,
                on_done,
                package_extra=package_extra,
                cleanup_path=cleanup_tmp,
            )
            return

        manifest = self._project_manifest()
        if self.file_mode == "def" and self.loaded_file:
            target_def = self.loaded_file
            cleanup_def: Optional[Path] = None
            if self._is_editor_dirty():
                cleanup_def = self.loaded_file.parent / f".{self.loaded_file.stem}_unsaved_preview.py"
                cleanup_def.write_text(self._editor_text(), encoding="utf-8")
                target_def = cleanup_def
            self._run_game_tool(
                self.file_kind,
                target_def,
                on_done,
                package_extra=package_extra,
                cleanup_path=cleanup_def,
            )
        elif self.file_mode in ("asm", "c", "py") and manifest and self.file_kind != "sid":
            self._write_log(f"Part of the project in {manifest}: running build.py to compile the whole game")
            self._run_game_tool("build", manifest, on_done, package_extra=package_extra)
        elif self.file_kind == "sid":
            self.action_compile_sid(on_done=on_done, _skip_save_prompt=True)
        else:
            self._assemble_current(on_done, package_extra=package_extra)

    def _assemble_current(
        self,
        on_done: Optional[Callable[[Optional[Path]], None]] = None,
        *,
        package_extra: bool = True,
    ) -> None:
        """Assemble or compile the loaded program (Oscar64/CC65 for C, KickAssembler for ASM/Python)."""
        self._last_compile_error = None
        active_dirty = self._is_editor_dirty()
        if self.file_mode == "c":
            self._pulse_raster_border("COMPILING C/C++ → PRG BINARY", 450)
            c_source = self.py_text.get("1.0", "end-1c").strip()
            if not c_source:
                self.notify("NO C/C++ SOURCE TO COMPILE", severity="warning")
                return
            out_prg = self.loaded_file.with_suffix(".prg").resolve() if self.loaded_file else Path("./output.prg").resolve()
            temp_c = None
            if self.loaded_file and self.loaded_file.is_file() and not active_dirty:
                target_c = self.loaded_file
            else:
                tmp_dir = str(self.loaded_file.parent) if (self.loaded_file and self.loaded_file.parent.is_dir()) else None
                c_suffix = (
                    self.loaded_file.suffix
                    if (self.loaded_file and self.loaded_file.suffix.lower() in (".c", ".cpp", ".cc", ".cxx"))
                    else ".c"
                )
                with tempfile.NamedTemporaryFile(suffix=c_suffix, dir=tmp_dir, delete=False) as tmp:
                    tmp.write(c_source.encode("utf-8"))
                    target_c = temp_c = Path(tmp.name)
            detected_cc = self.compiler.detect_assembler(target_c)
            self._write_log(f"Compiling C/C++ source {target_c.name} → {out_prg.name} with {detected_cc.upper()}...")
            comp_res = self.compiler.compile(target_c, output_prg=out_prg, assembler="auto")
            if temp_c:
                temp_c.unlink(missing_ok=True)
            if comp_res.success and out_prg.exists():
                self.last_prg_path = out_prg
                sz = out_prg.stat().st_size
                self._write_log(f"✓ Compiled {out_prg.name} ({sz} bytes) via {detected_cc.upper()}")
                asm_loaded = False
                if comp_res.asm_file and comp_res.asm_file.is_file():
                    try:
                        asm_listing = comp_res.asm_file.read_text(encoding="utf-8", errors="ignore")
                        if asm_listing.strip():
                            self.last_asm = asm_listing
                            self._set_asm_text(asm_listing)
                            asm_loaded = True
                            self._write_log(
                                f"  ↳ Loaded {detected_cc.upper()} 6502 assembly listing ({len(asm_listing.splitlines()):,} lines) into ASM view."
                            )
                    except Exception:
                        pass
                if not asm_loaded:
                    try:
                        dec = decompile_prg(out_prg.read_bytes(), name=out_prg.stem)
                        self.last_asm = dec.assembly
                        self._set_asm_text(dec.assembly)
                        self._write_log(f"  ↳ Disassembled {dec.instruction_count:,} optimized 6502 instructions into ASM view.")
                    except Exception:
                        pass
                self.notify(f"COMPILE TEST OK: {out_prg.name} ({sz} BYTES // {detected_cc.upper()})")
                if package_extra:
                    self._package_built_prg(out_prg)
                self._set_stage(2)
                if on_done:
                    on_done(out_prg)
            else:
                err = comp_res.error_message or comp_res.stderr or comp_res.stdout
                self._handle_compile_failure(f"C / {detected_cc.upper()} COMPILE", err, "c")
            return

        self._pulse_raster_border("ASSEMBLING 6502 → PRG BINARY", 450)
        if self.file_mode == "py":
            py_source = self.py_text.get("1.0", "end-1c")
            if not py_source.strip():
                self.notify("NO PYTHON SOURCE TO COMPILE", severity="warning")
                return
            res = self.transpiler.transpile(py_source)
            if not res.success:
                err_txt = "\n".join(res.errors)
                self._handle_compile_failure("PYTHON → 6502 TRANSPILE", err_txt, "py")
                return
            self.last_asm = res.assembly
            self._set_asm_text(res.assembly)
            self._update_ast_tree(res)

        asm_text = self.asm_text.get("1.0", "end-1c").strip()
        if not asm_text:
            self.notify("NO 6502 ASSEMBLY TO COMPILE", severity="warning")
            return

        out_prg = self.loaded_file.with_suffix(".prg").resolve() if self.loaded_file else Path("./output.prg").resolve()
        temp_asm = None
        if self.file_mode == "asm" and self.loaded_file and self.loaded_file.is_file() and not active_dirty:
            target_asm = self.loaded_file
        else:
            tmp_dir = str(self.loaded_file.parent) if (self.loaded_file and self.loaded_file.parent.is_dir()) else None
            with tempfile.NamedTemporaryFile(suffix=".asm", dir=tmp_dir, delete=False) as tmp:
                tmp.write(asm_text.encode("utf-8"))
                target_asm = temp_asm = Path(tmp.name)

        self._write_log(f"Assembling {target_asm.name} → {out_prg.name} with KickAssembler...")
        comp_res = self.compiler.compile(target_asm, output_prg=out_prg, assembler="auto")
        if temp_asm:
            temp_asm.unlink(missing_ok=True)

        if comp_res.success and out_prg.exists():
            self.last_prg_path = out_prg
            sz = out_prg.stat().st_size
            self._write_log(f"✓ Assembled {out_prg.name} ({sz} bytes)")
            self.notify(f"COMPILE TEST OK: {out_prg.name} ({sz} BYTES)")
            if package_extra:
                self._package_built_prg(out_prg)
            self._set_stage(2)
            if on_done:
                on_done(out_prg)
        else:
            err = comp_res.error_message or comp_res.stderr or comp_res.stdout
            stage_lbl = "6502 ASM COMPILE" if self.file_mode == "asm" else "PYTHON → 6502 ASM COMPILE"
            target_mode = "asm" if self.file_mode == "asm" else "py"
            self._handle_compile_failure(stage_lbl, err, target_mode)

    def _build_program(
        self,
        use_prg: Callable[[Path], None],
        *,
        package_extra: bool = True,
        _skip_save_prompt: bool = False,
    ) -> None:
        """Get a .prg for what is loaded, prompting to save unsaved `*` tabs first if needed."""
        if self._binary_unchanged() and self.binary_source is not None and not self._get_dirty_tabs():
            if package_extra:
                self._package_built_prg(self.binary_source)
            use_prg(self.binary_source)
            return

        if not _skip_save_prompt and self._get_dirty_tabs():
            self._confirm_save_before_compile(
                lambda _allow_unsaved: self._build_program(
                    use_prg,
                    package_extra=package_extra,
                    _skip_save_prompt=True,
                )
            )
            return

        def _got(prg: Optional[Path]) -> None:
            if prg:
                use_prg(prg)
            elif self.file_kind == "build" and self.last_sid_path and self.last_sid_path.is_file() and use_prg == self._dma_run:
                self._play_sid_worker(self.last_sid_path)
            elif self.file_kind == "build":
                self.notify("BUILD.PY FINISHED WITHOUT PRODUCING A .PRG BINARY", severity="warning")
            else:
                self.notify("THIS FILE MAKES NO PROGRAM: IT NEEDS A BUILD.PY", severity="warning")

        manifest = self._project_manifest()
        if self.file_mode == "def" and self.file_kind != "build" and manifest:
            self._run_game_tool("build", manifest, _got, package_extra=package_extra)
        else:
            self.action_build(_got, package_extra=package_extra, _skip_save_prompt=True)

    def action_send_to_c64u(self) -> None:
        """Test-compile what is loaded (prompting to save if `*` dirty) and send/run on C64U."""
        if self.file_kind == "song":
            self.action_build(lambda _prg: self.action_play_sid())
        elif self.file_kind == "sid":
            if self._asm_unchanged() and not self._get_dirty_tabs() and self.last_sid_path and self.last_sid_path.is_file():
                self.action_play_sid()
            else:
                self.action_compile_sid(on_done=lambda sid_path: self._play_sid_worker(sid_path))
        else:
            self._build_program(self._dma_run)

    def action_run_c64u(self) -> None:
        """Backwards-compatible alias for `action_send_to_c64u` (F5)."""
        self.action_send_to_c64u()

    def _dma_run(self, prg_path: Path) -> None:
        self._pulse_raster_border("DMA UPLOADING & EXECUTING ON C64U", 600)
        sz = prg_path.stat().st_size
        src_name = self.loaded_file.name if self.loaded_file else prg_path.name
        self._write_log(f"DMA Uploading {prg_path.name} ({sz} bytes) to C64U at {self.client.base_url}...")

        def _dma_worker():
            try:
                dma_res = self.client.run_prg(prg_path)
                report = self.validator.validate_deployment(
                    client=self.client,
                    source_name=src_name,
                    prg_path=prg_path,
                    execution_mode="DMA_RUN",
                    load_and_exec_success=True,
                    runner_response=str(dma_res),
                )
                self.last_validation_report = report
                self.root.after(0, lambda: (
                    self._write_log(f"✓ DMA RUN Executed Successfully! Response: {dma_res}"),
                    self._write_log(report.format_report(include_full_screen=True)),
                    self.notify(f"RUNNING ON C64U ({sz} BYTES)"),
                    self._set_stage(3),
                ))
            except Exception as exc:
                report = self.validator.validate_deployment(
                    client=self.client,
                    source_name=src_name,
                    prg_path=prg_path,
                    execution_mode="DMA_RUN",
                    load_and_exec_success=False,
                    execution_error=str(exc),
                )
                self.last_validation_report = report
                self.root.after(0, lambda err=exc: (
                    self._write_log(f"C64U DMA Run Error: {err}"),
                    self._write_log(report.format_report(include_full_screen=False)),
                    self.notify("DMA UPLOAD FAILED (C64U OFFLINE)", severity="warning"),
                ))

        threading.Thread(target=_dma_worker, daemon=True).start()

    def action_open_file(self) -> None:
        target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
        modal = OpenFileModal(initial_path=self.loaded_file.parent if self.loaded_file else target_dir_fn())
        self._last_open_file_modal = modal
        modal.show_tk(self, lambda path: self.load_project_file(path) if path else None)

    def _begin_load(self, kind: str, path: Optional[Path]) -> None:
        """Whatever was built from the last file no longer applies."""
        self.file_kind = kind
        self.loaded_file = path
        self.binary_source = None
        self.last_prg_path = None
        self.last_tap_path = None
        self.last_hyper_tap_path = None
        self.last_d64_path = None
        self.last_sid_path = None
        self.stage = 1

    def load_project_file(self, path: Path) -> None:
        """Open `path` in its own IDE file tab (or switch to its existing tab), preserving unsaved `*` tabs."""
        if not path.exists():
            self.notify(f"FILE NOT FOUND: {path.name}", severity="error")
            return

        self._pulse_raster_border(f'LOADING "{path.name.upper()}",8,1', 420)
        kind = classify_file(path)

        if kind not in ("build", *DEFINITION_KINDS, "c", "python", "asm", "sid", "d64", "tap", "prg", "bin"):
            self.notify(f"CANNOT LOAD {path.suffix.upper()} FILES", severity="warning")
            return

        if kind in ("d64", "tap", "prg", "bin"):
            existing_bin = self._find_open_tab_for_path(path)
            if existing_bin is not None and existing_bin.is_dirty:
                self.switch_file_tab(existing_bin.tab_id)
                self.notify(f'SWITCHED TO "{existing_bin.display_name().upper()}" (UNSAVED EDITS PRESERVED)')
                return

            def _shown() -> None:
                self._activate_or_open_tab_for_path(path)
                self._begin_load(kind, None)     # likewise for the image
                self.agy_lang_var.set("asm")
                if kind in ("prg", "bin"):
                    self.binary_source = path
                    self.last_prg_path = path

            self.action_decompile_media(path, before=_shown)
            return

        tab, preserved_dirty = self._activate_or_open_tab_for_path(path)
        if preserved_dirty:
            self.switch_tab("tab-asm")
            self._write_log(f"ℹ Switched to open tab {tab.display_name()} — unsaved edits preserved.")
            self.notify(f'SWITCHED TO "{tab.display_name().upper()}"')
            return

        if kind in ("build", *DEFINITION_KINDS):
            self._begin_load(kind, path)
            self.file_mode = "def"
            self.asm_focus_mode = False
            self.agy_lang_var.set("def")
            self._set_python_text(path.read_text(encoding="utf-8"))
            self._set_asm_text("")
            self.last_asm = ""
            self._mark_editor_synced()
            self.switch_tab("tab-asm")
            if kind == "build":
                self._write_log(
                    f"✓ Loaded {KIND_LABELS[kind]}: {path} — F7 runs build.py to compile the entire game; F5 builds & sends to C64U."
                )
                self.notify(f'LOADED "{path.name.upper()}" — F7 RUNS BUILD.PY')
            else:
                self._write_log(f"✓ Loaded {KIND_LABELS[kind]}: {path.name}. F7 builds it.")
                self.notify(f'LOADED "{path.name.upper()}"')

        elif kind == "c":
            self._begin_load(kind, path)
            self.file_mode = "c"
            self.asm_focus_mode = False
            self.agy_lang_var.set("c")
            self._set_python_text(path.read_text(encoding="utf-8"))
            self._set_asm_text("")
            self.last_asm = ""
            self._mark_editor_synced()
            self.switch_tab("tab-asm")
            self._write_log(f"✓ Loaded C/C++ source (Oscar64/CC65): {path.name} ({path.stat().st_size} bytes)")
            self.notify(f'LOADED "{path.name.upper()}" (C/OSCAR64 MODE)')

        elif kind == "python":
            py_content = path.read_text(encoding="utf-8")
            resolved_kind = "sid" if "C64U_SID_METADATA:" in py_content else kind
            self._begin_load(resolved_kind, path)
            self.file_mode = "py"
            self.asm_focus_mode = False
            self.agy_lang_var.set("py")
            self._set_python_text(py_content)
            self.action_transpile_code(silent=True)
            self._mark_editor_synced()
            self.switch_tab("tab-asm")
            self._write_log(f"✓ Loaded Python source: {path.name} ({path.stat().st_size} bytes)")
            self.notify(f'LOADED "{path.name.upper()}"')

        elif kind == "asm":
            asm_content = path.read_text(encoding="utf-8")
            resolved_kind = "sid" if "C64U_SID_METADATA:" in asm_content else kind
            self._begin_load(resolved_kind, path)
            self.file_mode = "asm"
            self.asm_focus_mode = False
            self.agy_lang_var.set("asm")
            self.last_asm = asm_content
            self._set_asm_text(asm_content)
            sidecar = path.with_suffix(".py")
            has_sidecar = sidecar.is_file() and classify_file(sidecar) == "python"
            self._set_python_text(sidecar.read_text(encoding="utf-8") if has_sidecar else "")
            self._mark_editor_synced()
            self.switch_tab("tab-asm")
            mode_tag = "SID SOURCE MODE" if resolved_kind == "sid" else "6502 ASM MODE"
            self._write_log(
                f"✓ Loaded {mode_tag}: {path.name} ({path.stat().st_size} bytes, {len(asm_content.splitlines())} lines)"
            )
            self.notify(f'LOADED "{path.name.upper()}" ({mode_tag})')
            if has_sidecar:
                self._write_log(f"ℹ Matching Python source {sidecar.name} is ready (click PYTHON to edit)")

        elif kind == "sid":
            self._begin_load(kind, None)     # the source gets its own file: never save over the .sid
            self.agy_lang_var.set("asm")
            self._load_sid_file(path)
            self._mark_editor_synced()

        self._update_mode_badge()

    # -----------------------------------------------------------------------
    # KickAssembler Version Check & Interactive Updater
    # -----------------------------------------------------------------------

    def check_kickass_version_startup(self) -> None:
        """
        Check in a background thread whether KickAssembler (KickAss.jar) is the latest
        upstream version. If a newer version is available, prompt the user via KickAssUpdateModal.
        """
        def _worker():
            status = self.compiler.check_kickass_version(timeout=3.5)

            def _on_main():
                if not self.root.winfo_exists():
                    return
                self._write_log(f"ℹ {status.status_message}")
                self._write_log(
                    "ℹ Decompiler Engine: KickAss.jar is an assembler only; using C64U Multi-Pass 6502 Decompiler (KickAss v5.x syntax)."
                )
                if status.update_available:
                    self.notify(
                        f"KICKASSEMBLER V{status.latest_version} UPDATE AVAILABLE!",
                        severity="warning",
                    )
                    modal = KickAssUpdateModal(status)
                    self._last_kickass_modal = modal
                    modal.show_tk(self)

            try:
                self.root.after(0, _on_main)
            except (tk.TclError, RuntimeError):
                pass

        if getattr(self, "_in_mainloop", False):
            threading.Thread(target=_worker, daemon=True).start()

    def action_check_kickass_version(self) -> None:
        """Check KickAssembler version interactively and open KickAssUpdateModal."""
        self._pulse_raster_border("CHECKING KICKASSEMBLER VERSION", 350)
        status = self.compiler.check_kickass_version(timeout=4.0)
        self._write_log(f"✓ {status.status_message}")
        modal = KickAssUpdateModal(status)
        self._last_kickass_modal = modal
        modal.show_tk(self)

    def _perform_kickass_update(self, callback: Optional[Callable[[bool], None]] = None) -> None:
        """Download and install the latest KickAss.jar from the official KickAssembler repository."""
        self._pulse_raster_border("DOWNLOADING & UPDATING KICKASSEMBLER", 700)
        self._write_log("Downloading latest KickAssembler release from http://theweb.dk/KickAssembler/...")

        def _do_sync():
            ok, msg = self.compiler.update_kickassembler(
                progress_callback=lambda m: self._write_log(f"  {m}")
            )
            if ok:
                self._write_log(f"✓ {msg}")
                self.notify(msg.upper())
            else:
                self._write_log(f"✗ {msg}")
                self.notify(msg.upper(), severity="error")
            if callback:
                callback(ok)

        if getattr(self, "_in_mainloop", False):
            def _bg():
                ok, msg = self.compiler.update_kickassembler()
                self.root.after(
                    0,
                    lambda: (
                        self._write_log(f"{'✓' if ok else '✗'} {msg}"),
                        self.notify(msg.upper(), severity="information" if ok else "error"),
                        callback(ok) if callback else None,
                    ),
                )

            threading.Thread(target=_bg, daemon=True).start()
        else:
            _do_sync()

    # -----------------------------------------------------------------------
    # Reverse Decompilation (D64 / TAP / PRG / SID) with Copyright Caution
    # -----------------------------------------------------------------------

    def action_decompile_media(self, target_path: Path, before: Optional[Callable[[], None]] = None) -> None:
        """Show mandatory copyright & ethical use caution, then reverse-decompile D64/TAP/PRG."""
        def _on_answer(proceed: bool) -> None:
            if not proceed:
                self.notify("DECOMPILATION CANCELLED")
                return
            if before:
                before()
            self._decompile_file_flow(target_path)

        caution = CopyrightCautionModal(filename=target_path.name)
        self._last_caution_modal = caution
        caution.show_tk(self, _on_answer)

    def _decompile_file_flow(self, path: Path, scope: Optional[str] = None) -> None:
        self._pulse_raster_border(f"REVERSE-DECOMPILING {path.name.upper()}", 500)
        ext = path.suffix.lower()

        if ext == ".d64":
            try:
                stages = inspect_media_stages(path)
                if not stages:
                    self.notify(f"NO PRG FILES ON DISK: {path.name}", severity="error")
                    return
                if scope is not None:
                    res = decompile_d64_file(path, scope=scope)
                    self._apply_decompile_result(res, f"{path.name} [{scope.upper()}]", source_path=path)
                    return
                if len(stages) == 1:
                    res = decompile_d64_file(path, file_name_or_index=0)
                    self._apply_decompile_result(res, f"{path.name} / {stages[0].name}", source_path=path)
                else:
                    modal = DecompileScopeModal(path, stages)
                    self._last_scope_modal = modal

                    def _on_d64_scope(chosen_scope: Optional[str], stage_idx: Optional[int]) -> None:
                        if chosen_scope is None:
                            self.notify("DECOMPILATION CANCELLED")
                            return
                        try:
                            if chosen_scope == "stage" and stage_idx is not None:
                                res = decompile_d64_file(path, file_name_or_index=stage_idx)
                                label = f"{path.name} / {res.filename}"
                            else:
                                res = decompile_d64_file(path, scope=chosen_scope)
                                label = f"{path.name} [{chosen_scope.upper()}]"
                            self._apply_decompile_result(res, label, source_path=path)
                        except Exception as exc:
                            self.notify(f"D64 ERROR: {exc}", severity="error")

                    modal.show_tk(self, _on_d64_scope)
            except Exception as exc:
                self.notify(f"D64 ERROR: {exc}", severity="error")

        elif ext == ".tap":
            try:
                stages = inspect_media_stages(path)
                if not stages:
                    self.notify(f"NO PRG BLOCKS IN TAP: {path.name}", severity="error")
                    return
                if scope is not None:
                    res = decompile_tap_file(path, scope=scope)
                    self._apply_decompile_result(res, f"{path.name} [{scope.upper()}]", source_path=path)
                    return
                if len(stages) == 1:
                    res = decompile_tap_file(path, file_index=0)
                    self._apply_decompile_result(res, f"{path.name} ({stages[0].name})", source_path=path)
                else:
                    modal = DecompileScopeModal(path, stages)
                    self._last_scope_modal = modal

                    def _on_tap_scope(chosen_scope: Optional[str], stage_idx: Optional[int]) -> None:
                        if chosen_scope is None:
                            self.notify("DECOMPILATION CANCELLED")
                            return
                        try:
                            if chosen_scope == "stage" and stage_idx is not None:
                                res = decompile_tap_file(path, file_index=stage_idx)
                                label = f"{path.name} ({res.filename})"
                            else:
                                res = decompile_tap_file(path, scope=chosen_scope)
                                label = f"{path.name} [{chosen_scope.upper()}]"
                            self._apply_decompile_result(res, label, source_path=path)
                        except Exception as exc:
                            self.notify(f"TAP ERROR: {exc}", severity="error")

                    modal.show_tk(self, _on_tap_scope)
            except Exception as exc:
                self.notify(f"TAP ERROR: {exc}", severity="error")

        elif ext in (".prg", ".bin"):
            try:
                self._apply_decompiled_prg(path.stem, path.read_bytes(), path.name, source_path=path)
            except Exception as exc:
                self.notify(f"PRG ERROR: {exc}", severity="error")
        else:
            self.notify(f"UNSUPPORTED DECOMPILE FORMAT: {ext}", severity="warning")

    def _apply_decompiled_prg(
        self,
        name: str,
        prg_bytes: bytes,
        source_label: str,
        source_path: Optional[Path] = None,
    ) -> None:
        try:
            res = decompile_prg(prg_bytes, name=name)
            self._apply_decompile_result(res, source_label, source_path=source_path)
        except Exception as exc:
            self._write_log(f"Decompilation failed: {exc}")
            self.notify(f"DECOMPILE ERROR: {exc}", severity="error")

    def _apply_decompile_result(
        self,
        res: PrgDecompileResult,
        source_label: str,
        source_path: Optional[Path] = None,
    ) -> None:
        self._ensure_active_file_tab(source_path.name if source_path is not None else source_label)
        self.last_asm = res.assembly
        self.file_mode = "asm"
        self.stage = 1
        if source_path is not None:
            self.loaded_file = source_path.with_name(f"{source_path.stem}_decompiled.asm")
        self._set_asm_text(res.assembly)
        self._set_python_text(res.python)
        self._mark_editor_synced()
        self.switch_tab("tab-asm")
        self._update_mode_badge()

        self._write_log(f"✓ Successfully decompiled {source_label} into commented KickAssembler (.asm)!")
        self._write_log(f"  Memory Range : ${res.load_address:04X}..${res.end_address:04X} ({res.payload_size:,} bytes)")
        if res.stages_decompiled and len(res.stages_decompiled) > 1:
            self._write_log(f"  Stages ({len(res.stages_decompiled)}) : {', '.join(res.stages_decompiled)}")
        if res.has_basic_sys:
            self._write_log(f"  BASIC Stub   : SYS {res.sys_address} (${res.sys_address:04X})")
        self._write_log(
            f"  Disassembled : {res.instruction_count:,} 6502 instructions; preserved {res.data_byte_count:,} data bytes."
        )
        self._write_log("  ⚠️ Notice: Code decompiled with explanatory comments for technique review & self-improvement.")
        self.notify(f"DECOMPILED {res.filename} ({res.instruction_count:,} INSTRS)")

    # -----------------------------------------------------------------------
    # SID Decompile / Compile / Playback
    # -----------------------------------------------------------------------

    def _load_sid_file(self, path: Path) -> None:
        try:
            self._pulse_raster_border(f"DECOMPILING SID: {path.name.upper()}", 480)
            result = decompile_sid_file(path)
            asm_path = path.with_name(f"{path.stem}_decompiled.asm")
            py_path = path.with_name(f"{path.stem}_decompiled.py")
            asm_path.write_text(result.assembly, encoding="utf-8")
            py_path.write_text(result.python, encoding="utf-8")
            self._record_self_saved_file(asm_path)
            self._record_self_saved_file(py_path)

            self.file_mode = "asm"
            self.file_kind = "sid"
            self.last_sid_path = path
            self.loaded_file = asm_path
            self.last_asm = result.assembly
            self._set_asm_text(result.assembly)
            self._set_python_text(result.python)
            self._mark_editor_synced()
            self.switch_tab("tab-asm")
            self._update_mode_badge()

            h = result.sid.header
            self._write_log(f"✓ Reverse-decompiled {h.magic} v{h.version}: {path.name}")
            self._write_log(f"  Title: {h.name or '(untitled)'} by {h.author or '(unknown)'}")
            self._write_log(f"  Load ${h.load_address:04X} | Init ${h.init_address:04X} | Play ${h.play_address:04X}")
            self.notify(f"SID DECOMPILED: {asm_path.name}")
        except (OSError, SidDecompileError) as exc:
            self._write_log(f"SID decompile failed: {exc}")
            self.notify(f"SID DECOMPILE ERROR: {exc}", severity="error")

    def action_compile_sid(
        self,
        on_done: Optional[Callable[[Path], None]] = None,
        *,
        _skip_save_prompt: bool = False,
    ) -> bool:
        """Test-compile the active SID driver source into a PSID/RSID `.sid` container."""
        self._last_compile_error = None
        source_text = (
            self.asm_text.get("1.0", "end-1c")
            if self.file_mode == "asm"
            else self.py_text.get("1.0", "end-1c")
        )
        if not source_text.strip():
            self.notify("NO SID SOURCE TO COMPILE", severity="warning")
            return False

        if not _skip_save_prompt and self._get_dirty_tabs():
            self._confirm_save_before_compile(
                lambda _allow_unsaved: self.action_compile_sid(
                    on_done=on_done,
                    _skip_save_prompt=True,
                )
            )
            return False

        lang_mode = "py" if self.file_mode == "py" else "asm"
        if "C64U_SID_METADATA:" not in source_text and not self.last_sid_path:
            self._handle_compile_failure(
                "SID MUSIC COMPILE (.SID)",
                "Missing SID metadata header (`// C64U_SID_METADATA: {...}`). "
                "Add a PSID metadata header or create a new SID starter template via NEW -> SID.",
                lang_mode,
            )
            return False

        active_dirty = self._is_editor_dirty()
        temp_src: Optional[Path] = None
        out_sid: Optional[Path] = None
        try:
            self._pulse_raster_border("COMPILING ASM → SID CONTAINER", 450)
            if (
                self.loaded_file is not None
                and self.loaded_file.suffix.lower() in {".asm", ".s", ".py"}
                and self.loaded_file.is_file()
                and not active_dirty
            ):
                target_src = self.loaded_file
            else:
                suffix = ".py" if self.file_mode == "py" else ".asm"
                tmp_dir = str(self.loaded_file.parent) if (self.loaded_file and self.loaded_file.parent.is_dir()) else None
                with tempfile.NamedTemporaryFile(suffix=suffix, dir=tmp_dir, delete=False) as tmp:
                    tmp.write(source_text.encode("utf-8"))
                    target_src = temp_src = Path(tmp.name)
                out_sid = (
                    self.loaded_file.with_suffix(".sid").resolve()
                    if self.loaded_file is not None
                    else Path("./output.sid").resolve()
                )

            res = compile_sid_source(
                target_src,
                output_sid=out_sid,
                template_sid=self.last_sid_path,
                compiler=self.compiler,
                source_text=source_text,
            )
            self.last_sid_path = res.output_sid
            if self.file_mode == "asm":
                self.last_asm = source_text
            self._write_log(f"✓ SID compiled: {res.output_sid} ({res.payload_size} bytes)")
            self.notify(f"COMPILE TEST OK: {res.output_sid.name} ({res.payload_size} BYTES)")
            self._set_stage(2)
            if on_done:
                on_done(res.output_sid)
            return True
        except Exception as exc:
            self._handle_compile_failure("SID MUSIC COMPILE (.SID)", str(exc), lang_mode)
            return False
        finally:
            if temp_src is not None:
                temp_src.unlink(missing_ok=True)

    def action_play_sid(self) -> None:
        if self.last_sid_path and self.last_sid_path.is_file():
            self._play_sid_worker(self.last_sid_path)
        else:
            self.notify("NO SID YET: LOAD A .SID OR BUILD A SONG", severity="warning")

    def _play_sid_worker(self, path: Path) -> None:
        self._pulse_raster_border(f"UPLOADING SID: {path.name.upper()}", 480)
        try:
            res = self.client.play_sid(path)
            self._write_log(f"✓ Playing {path.name} on C64U SID Player: {res}")
            self.notify(f"PLAYING {path.name.upper()} ON C64U")
            self._set_stage(3)
        except Exception as exc:
            self._write_log(f"C64U SID playback failed: {exc}")
            self.notify(f"SID PLAYBACK FAILED: {exc}", severity="error")

    # -----------------------------------------------------------------------
    # Game Dev: start something new, then it follows the same sequence
    # -----------------------------------------------------------------------

    def action_new_game(self) -> None:
        name = simpledialog.askstring("NEW GAME PROJECT", "NAME OF THE GAME:", parent=self.root)
        if name:
            self._create_game(name)

    def _create_game(self, name: str) -> None:
        target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
        try:
            manifest = create_game(name, target_dir_fn())
        except (OSError, ValueError) as exc:
            self._write_log(f"Could not start the game: {exc}")
            self.notify(f"NEW GAME FAILED: {exc}", severity="error")
            return
        self._write_log(f"✓ Started {manifest.parent}")
        self.load_project_file(manifest)

    def action_new_build_file(self) -> None:
        """Load the project's build.py, first writing one from the folder's files if it has none."""
        folder = self.loaded_file.parent if self.loaded_file else None
        if folder is None:
            fd_mod = _tui_attr("filedialog", filedialog)
            target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
            chosen = fd_mod.askdirectory(title="FOLDER OF THE GAME", initialdir=target_dir_fn())
            if not chosen:
                return
            folder = Path(chosen)
        self._create_build_file(folder)

    def _create_build_file(self, folder: Path) -> None:
        manifest = find_manifest(folder / "build.py") or create_manifest(folder)
        self.load_project_file(manifest)

    def action_new_definition(self, kind: str) -> None:
        fd_mod = _tui_attr("filedialog", filedialog)
        target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
        manifest = self._project_manifest()
        folder = (manifest.parent / KIND_FOLDERS[kind]) if manifest else target_dir_fn()
        folder.mkdir(parents=True, exist_ok=True)
        chosen = fd_mod.asksaveasfilename(
            title=f"NEW {KIND_LABELS[kind]}",
            initialdir=folder,
            initialfile=KIND_FILES[kind],
            defaultextension=".py",
            filetypes=[("Python definition", "*.py")],
        )
        if chosen:
            self._create_definition(kind, Path(chosen))

    def _create_definition(self, kind: str, path: Path) -> None:
        try:
            create_definition(kind, path)
            manifest = find_manifest(path)
            if manifest and add_step(manifest, kind, path):
                self._write_log(f"✓ Added it to {manifest.name}")
        except (OSError, ValueError) as exc:
            self._write_log(f"Could not create {path.name}: {exc}")
            self.notify(f"NEW FILE FAILED: {exc}", severity="error")
            return
        self.load_project_file(path)

    def action_gamedev_c64sim(self) -> None:
        self._build_program(lambda prg: self._run_game_tool("c64sim", prg))

    def action_gamedev_check(self) -> None:
        """Build, then run the game headless and report engine bugs (tools/gamecheck)."""
        self._build_program(lambda prg: self._run_game_tool("gamecheck", prg))

    def action_gamedev_sim(self) -> None:
        if self.last_sid_path and self.last_sid_path.is_file():
            self._run_game_tool("sim", self.last_sid_path)
        else:
            self._build_program(lambda prg: self._run_game_tool("sim", prg))

    def _run_game_tool(
        self,
        key: str,
        target: Path,
        on_done: Optional[Callable[[Optional[Path]], None]] = None,
        *,
        package_extra: bool = True,
        cleanup_path: Optional[Path] = None,
    ) -> None:
        tool = GAME_TOOLS[key]
        self._pulse_raster_border(f"{tool.label}: {target.name.upper()}", 600)
        self._write_log(f"▶ {tool.label}: {target}")

        def _worker():
            try:
                result = run_tool(key, target)
            finally:
                if cleanup_path is not None:
                    cleanup_path.unlink(missing_ok=True)

            def _done():
                if not self.root.winfo_exists():
                    return
                for line in result.output.splitlines():
                    self._write_log(f"  {line}")
                if not result.ok:
                    if key in ("build", *DEFINITION_KINDS):
                        err_lang = "asm" if self.file_mode == "asm" else "def"
                        self._handle_compile_failure(f"{tool.label} COMPILE", result.output, err_lang)
                    else:
                        self.switch_tab("tab-log")
                        self._write_log(f"✗ {tool.label} failed")
                        self.notify(f"{tool.label} FAILED", severity="error")
                    return
                self._write_log(f"✓ {tool.label} done")
                self.notify(f"{tool.label} DONE: {target.name.upper()}")
                sid = result.first(".sid")
                if sid:
                    self.last_sid_path = sid
                    self._write_log(f"  PLAY SID [^P] now plays {sid.name} on the C64U")
                prg = result.first(".prg")
                if prg:
                    self.last_prg_path = prg
                    if key == "build" and prg.is_file():
                        try:
                            dec = decompile_prg(prg.read_bytes(), name=prg.stem)
                            self.last_asm = dec.assembly
                            self._set_asm_text(dec.assembly)
                        except Exception:
                            pass
                        if package_extra:
                            self._package_built_prg(prg)
                page = result.first(".html") or result.first(".png")
                if page:
                    self._open_review_page(page)
                self._set_stage(max(self.stage, 2))
                if on_done:
                    on_done(prg)

            try:
                self.root.after(0, _done)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _open_review_page(self, page: Path) -> None:
        wb_mod = _tui_attr("webbrowser", webbrowser)
        try:
            wb_mod.open(page.resolve().as_uri())
            self._write_log(f"  Opened review page {page.name}")
        except Exception as exc:
            self._write_log(f"Could not open {page}: {exc}")

    # -----------------------------------------------------------------------
    # Save ASM, Export TAP, Compile D64, Hardware Controls & Modals
    # -----------------------------------------------------------------------

    def action_save_file(self) -> bool:
        """Save the active open tab, asking for a filename if untitled, and clear its `*` indicator."""
        if not self._has_source() and self.loaded_file is None:
            self.notify("NOTHING TO SAVE", severity="warning")
            return False
        tab = self._ensure_active_file_tab()
        if not self._save_tab(tab):
            return False
        if tab.loaded_file is not None:
            self.notify(f'SAVED "{tab.loaded_file.name.upper()}"')
        return True

    def action_save_assembly(self) -> None:
        """Direct non-modal save helper for C / ASM / Python editor buffers."""
        if self.file_mode == "c":
            c_text = self.py_text.get("1.0", "end-1c")
            if not c_text.strip():
                self.notify("NO C SOURCE TO SAVE", severity="warning")
                return
            out_c = (
                self.loaded_file
                if (self.loaded_file and self.loaded_file.suffix.lower() in (".c", ".cpp", ".cc", ".cxx", ".h"))
                else Path("./output.c").resolve()
            )
            out_c.write_text(c_text, encoding="utf-8")
            self.loaded_file = out_c
            self._record_self_saved_file(out_c)
            self._mark_editor_synced()
            self._write_log(f"✓ Saved C/C++ source to {out_c}")
            self.notify(f'SAVED "{out_c.name.upper()}"')
            self._update_mode_badge()
            return

        current_text = self.asm_text.get("1.0", "end-1c") or self.last_asm
        if not current_text.strip():
            self.notify("NO 6502 ASSEMBLY TO SAVE", severity="warning")
            return
        out_file = self.loaded_file if (self.file_mode == "asm" and self.loaded_file) else Path("./output.asm").resolve()
        out_file.write_text(current_text, encoding="utf-8")
        if self.file_mode == "asm":
            self.loaded_file = out_file
        self._record_self_saved_file(out_file)
        self.last_asm = current_text
        self._mark_editor_synced()
        self._write_log(f"✓ Saved 6502 assembly to {out_file}")
        self.notify(f'SAVED "{out_file.name.upper()}"')
        self._update_mode_badge()

    def action_export_hyperload(self) -> None:
        """Build, then write a .tap with the HYPERLOAD fast loader and border stripes."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("MASTERING HYPERLOAD CASSETTE IMAGE", 480)
            out_tap = prg.with_suffix(".tap")
            extra_args = self._hyperload_extra_args(prg)
            res = run_tool("hyperload", prg, args=("-o", str(out_tap), "--name", prg.stem, *extra_args))
            if res.ok and out_tap.is_file():
                self.last_hyper_tap_path = out_tap
                sz = out_tap.stat().st_size
                self._write_log(f"✓ HYPERLOAD Cassette Image Generated: {out_tap} ({sz} bytes)")
                self._write_log(res.output)
                self.notify(f"EXPORTED {out_tap.name.upper()} WITH HYPERLOAD ({sz} BYTES)")
            else:
                self._write_log(f"HYPERLOAD Export Error: {res.output}")
                self.notify(f"HYPERLOAD EXPORT ERROR: {res.output.splitlines()[-1] if res.output else 'see log'}",
                            severity="error")

        self._build_program(_export, package_extra=False)

    def action_export_tap(self) -> None:
        """Build, then write a standard-speed .tap cassette image."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("MASTERING .TAP CASSETTE IMAGE", 480)
            out_tap = prg.with_suffix(".tap")
            try:
                save_prg_to_tap(prg, tap_path=out_tap, tape_name=prg.stem)
                self.last_tap_path = out_tap
                sz = out_tap.stat().st_size
                self._write_log(f"✓ TAP Cassette Image Generated: {out_tap} ({sz} bytes)")
                self.notify(f"EXPORTED {out_tap.name.upper()} ({sz} BYTES)")
            except Exception as exc:
                self._write_log(f"TAP Export Error: {exc}")
                self.notify(f"TAP EXPORT ERROR: {exc}", severity="error")

        self._build_program(_export, package_extra=False)

    def action_compile_d64(self) -> None:
        """Build, then package into a standard 35-track 1541 .d64 disk image."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("FORMATTING & WRITING 1541 .D64 DISK", 500)
            out_d64 = prg.with_suffix(".d64")
            try:
                save_prg_to_d64(prg, d64_path=out_d64, disk_name=prg.stem.upper()[:16])
                self.last_d64_path = out_d64
                sz = out_d64.stat().st_size
                self._write_log(f"✓ 1541 D64 Disk Image Generated: {out_d64} ({sz} bytes)")
                self.notify(f"COMPILED {out_d64.name.upper()} ({sz} BYTES)")
            except Exception as exc:
                self._write_log(f"D64 Packaging Error: {exc}")
                self.notify(f"D64 EXPORT ERROR: {exc}", severity="error")

        self._build_program(_export, package_extra=False)

    def action_load_prg_only(self) -> None:
        """Build, then put the program in C64 RAM without starting it."""
        def _load(prg: Path) -> None:
            try:
                res = self.client.load_prg(prg)
                self._write_log(f"✓ PRG Loaded into C64 RAM: {res}")
                self.notify("PRG LOADED INTO C64 RAM")
            except Exception as exc:
                self._write_log(f"DMA Load Error: {exc}")
                self.notify(f"DMA LOAD FAILED: {exc}", severity="error")

        self._build_program(_load)

    def action_refresh_connection(self) -> None:
        self._write_log(f"Checking connection to C64U at http://{self.client.host}:{self.client.port}...")
        self.check_bridge_status(notify_user=True)

    def action_reset_c64u(self) -> None:
        self._write_log(f"⚡ Sending Soft Reset to C64U at http://{self.client.host}:{self.client.port}...")
        try:
            res = self.client.reset(reboot=False)
            self._write_log(f"✓ C64U Reset Successful: {res}")
            self.notify("C64U SOFT RESET SENT")
        except Exception as exc:
            self._write_log(f"✗ C64U Reset Failed: {exc}")
            self.notify(f"RESET FAILED: {exc}", severity="error")

    def action_reboot_c64u(self) -> None:
        self._write_log("⚡ Sending Cold Reboot to C64U...")
        try:
            res = self.client.reset(reboot=True)
            self._write_log(f"✓ C64U Cold Reboot Sent: {res}")
            self.notify("C64U COLD REBOOT SENT")
        except Exception as exc:
            self._write_log(f"✗ C64U Reboot Failed: {exc}")
            self.notify(f"REBOOT FAILED: {exc}", severity="error")

    def action_pause_cpu(self) -> None:
        try:
            self.client.pause()
            self._write_log("✓ 6510 CPU Paused")
            self.notify("6510 CPU PAUSED")
        except Exception as exc:
            self._write_log(f"Pause CPU Error: {exc}")
            self.notify(f"PAUSE FAILED: {exc}", severity="error")

    def action_resume_cpu(self) -> None:
        try:
            self.client.resume()
            self._write_log("✓ 6510 CPU Resumed")
            self.notify("6510 CPU RESUMED")
        except Exception as exc:
            self._write_log(f"Resume CPU Error: {exc}")
            self.notify(f"RESUME FAILED: {exc}", severity="error")

    def action_dump_screen(self) -> None:
        self._write_log("Reading screen memory from C64U ($0400-$07E7)...")
        try:
            screen_mem = self.client.read_memory(0x0400, 1000)
            color_mem = None
            try:
                color_mem = self.client.read_memory(0xD800, 1000)
            except Exception:
                pass
            dump = format_screen(screen_mem, color_mem, use_ansi=False)
            self.switch_tab("tab-log")
            self._write_log("=== C64 SCREEN MEMORY DUMP ($0400-$07E7) ===")
            self._write_log(dump)
            self.notify("SCREEN MEMORY DUMPED TO BUILD LOG")
        except Exception as exc:
            self._write_log(f"Screen Dump Error: {exc}")
            self.notify(f"SCREEN DUMP FAILED: {exc}", severity="error")

    def _handle_hw_poke(self) -> None:
        try:
            addr = int(self.inp_addr_var.get().strip().replace("$", "0x"), 16)
            val = int(self.inp_val_var.get().strip().replace("$", "0x"), 16)
            self.client.write_memory(addr, [val])
            self._write_log(f"✓ POKED ${addr:04X} = ${val:02X}")
            self.notify(f"POKE ${addr:04X},${val}")
        except Exception as exc:
            self._write_log(f"Poke Error: {exc}")
            self.notify(f"POKE ERROR: {exc}", severity="error")

    def _handle_hw_peek(self) -> None:
        try:
            addr = int(self.inp_addr_var.get().strip().replace("$", "0x"), 16)
            raw = self.client.read_memory(addr, 1)
            val = raw[0] if raw else 0
            self.inp_val_var.set(f"${val:02X}")
            self._write_log(f"✓ PEEKED ${addr:04X} -> ${val:02X} ({val})")
            self.notify(f"PEEK(${addr:04X}) = ${val:02X} ({val})")
        except Exception as exc:
            self._write_log(f"Peek Error: {exc}")
            self.notify(f"PEEK ERROR: {exc}", severity="error")

    def _handle_send_keys(self) -> None:
        txt = self.inp_keys_var.get()
        try:
            res = self.client.send_keys(txt)
            self._write_log(f"✓ Sent keys to C64 keyboard buffer: {res}")
            self.notify("KEYS INJECTED INTO C64 BUFFER")
        except Exception as exc:
            self._write_log(f"Send Keys Error: {exc}")
            self.notify(f"SEND KEYS ERROR: {exc}", severity="error")

    def action_open_presets(self) -> None:
        """Open Retro C64 Preset Selector Modal."""
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(self.root)
        self._apply_application_icon(dlg)
        dlg.title("COMMODORE 64 PRESET DEMOS & EXAMPLES")
        dlg.geometry("780x440")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(self.root)

        tk.Label(
            dlg,
            text="[ COMMODORE 64 PYTHON & 6502 PRESET DEMOS ]",
            font=(font_fam, 11, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(12, 8))

        lb = tk.Listbox(
            dlg,
            font=(font_fam, 9, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
            relief=tk.FLAT,
            highlightthickness=2,
            highlightbackground=str(t["accent"]),
            activestyle="none",
        )
        lb.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        keys = list(PRESETS.keys())
        for k in keys:
            desc = PRESETS[k].get("description", "")
            lb.insert(tk.END, f"{k:<26} — {desc[:48]}")
        if keys:
            lb.selection_set(0)

        def load_sel(_event=None):
            sel = lb.curselection()
            idx = sel[0] if sel else 0
            if 0 <= idx < len(keys):
                code = PRESETS[keys[idx]].get("code", "")
                preset_slug = re.sub(r"[^a-z0-9]+", "_", keys[idx].lower()).strip("_") or "preset"
                tab = self._open_or_reuse_untitled_tab(f"{preset_slug}.py")
                self._begin_load("python", None)
                self.file_mode = "py"
                self.asm_focus_mode = False
                self._set_python_text(str(code))
                tab.title_hint = f"{preset_slug}.py"
                self.action_transpile_code()
                self._mark_editor_synced()
                self.switch_tab("tab-asm")
                self._update_mode_badge()
                self.notify(f"LOADED PRESET: {keys[idx].upper()}")
            if dlg.winfo_exists():
                dlg.destroy()

        lb.bind("<Double-Button-1>", load_sel)
        lb.bind("<Return>", load_sel)
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        btn_row = tk.Frame(dlg, bg=str(t["paper"]))
        btn_row.pack(fill=tk.X, padx=14, pady=12)

        tk.Button(
            btn_row,
            text="LOAD SELECTED PRESET (ENTER)",
            command=load_sel,
            font=(font_fam, 9, "bold"),
            bg=str(t["success"]),
            fg="#000000",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(8, 0))

        tk.Button(
            btn_row,
            text="CANCEL",
            command=dlg.destroy,
            font=(font_fam, 9, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["panel_fg"]),
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        center_popup(dlg)
        try:
            dlg.grab_set()
            lb.focus_set()
        except tk.TclError:
            pass

    def action_show_help(self) -> None:
        """Open C64 Reference Guide, ASM Editor Shortcuts & Full Font Credits Modal."""
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(self.root)
        self._apply_application_icon(dlg)
        dlg.title("C64-BRIDGE STUDIO // REFERENCE GUIDE & FONT CREDITS")
        dlg.geometry("920x640")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(self.root)

        tk.Label(
            dlg,
            text="[ C64-BRIDGE 6502 ASM STUDIO — REFERENCE GUIDE & CREDITS ]",
            font=(font_fam, 11, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(12, 8))

        txt_wrap = tk.Frame(dlg, bg=str(t["paper"]))
        txt_wrap.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        sb = tk.Scrollbar(txt_wrap)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        help_box = tk.Text(
            txt_wrap,
            font=(font_fam, 9, "bold"),
            bg=str(t["editor_bg"]),
            fg=str(t["ink"]),
            wrap="word",
            padx=12,
            pady=10,
            bd=0,
            yscrollcommand=sb.set,
        )
        help_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=help_box.yview)

        guide_content = (
            f"{FONT_CREDITS_TEXT}\n\n"
            "SINGLE-SCREEN EDITOR & 6502 ASM TOGGLE TOOLS\n"
            "============================================================\n"
            "• ASM / C / PY  : Pick your active coding language in one focused full-screen editor\n"
            "• SHOW ASM (^E) : Toggle between your Python/C editor and its generated 6502 Assembly\n"
            "• F6 / C→ASM    : Convert Python or C to 6502 Assembly and inspect the ASM output\n"
            "• Ctrl+N        : Create New 6502 KickAssembler (.asm) Starter Template\n"
            "• Ctrl+S / ⇧F1  : Save the Loaded File\n"
            "• Ctrl+/        : Comment / Uncomment Selected Lines (# in Python, // in C & ASM)\n"
            "• Ctrl+F        : Find Text, Label, or Jump to Line Number\n"
            "• Label Outline : Click any label/subroutine in the ASM outline rail to jump instantly\n\n"
            "THE SEQUENCE\n"
            "============================================================\n"
            "1. LOAD (F3)  : Any file goes on screen. Nothing runs yet.\n"
            "2. BUILD (F7) : Saves the file and builds it the way its kind needs.\n"
            "3. RUN (F5)   : Builds if needed and runs it. A song plays.\n"
            "   EXPORT     : Shift+F2 .TAP, F12 HYPERLOAD .TAP, Shift+F9 .D64.\n\n"
            "WHAT F7 DOES FOR EACH FILE\n"
            "============================================================\n"
            "• .asm            : Assembles it, or its whole game if it has a build.py\n"
            "• .py game code   : Transpiles to 6502, then assembles\n"
            "• build.py        : Runs every step of the game's build\n"
            "• Sprites, tiles, screen, song, levels : Runs that file's tool\n"
            "• .prg .tap .d64 .sid : Load shows the disassembly; a .prg or .sid runs as is\n\n"
            "GAME DEV: START SOMETHING NEW (ALT+G)\n"
            "============================================================\n"
            "• GAME PROJECT : A new folder with a build.py and a program that runs\n"
            "• BUILD.PY     : The folder's build.py, written from its files if it has none\n"
            "• SPRITE BANK, TILES + MAP, TITLE SCREEN, SID SONG, LEVELS : A starter file\n"
            "  that builds as it stands, added to the game's build.py\n"
            "• C64 SCREEN   : Runs the program in the simulator and shows a screenshot\n"
            "• SID PROFILE  : CPU time the music takes per frame\n\n"
            "OTHER KEYS\n"
            "============================================================\n"
            "• F1 Guide   F2 Preset Demos   F4 Ping C64U   F6 Python to ASM   F8 Soft Reset\n"
            "• F10 / Alt+Key : On-Screen Menu (Arrow Keys)   F11 Fullscreen\n"
            "• Shift+F3 DMA Load   Shift+F4/F5 Pause/Resume   Shift+F6 Screen Dump\n"
            "• Shift+F7 Cold Reboot   Ctrl+P Play SID   Shift+F8 / Ctrl+Q Quit\n"
        )
        help_box.insert("1.0", guide_content)
        help_box.configure(state="disabled")

        tk.Button(
            dlg,
            text="CLOSE GUIDE (ESC / ENTER)",
            command=dlg.destroy,
            font=(font_fam, 9, "bold"),
            bg=str(t["button_bg"]),
            fg=str(t["button_fg"]),
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
        ).pack(pady=10)

        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        dlg.bind("<Return>", lambda _e: dlg.destroy())
        center_popup(dlg)


    def action_validation_report(self) -> None:
        """Capture and log an on-demand C64U Hardware & Deployment Validation Report."""
        prg_path = self.last_prg_path if (self.last_prg_path and self.last_prg_path.exists()) else None
        src_name = self.loaded_file.name if self.loaded_file else (prg_path.name if prg_path else "LIVE_INSPECTION")
        report = self.validator.validate_deployment(
            client=self.client,
            source_name=src_name,
            prg_path=prg_path,
            execution_mode="LIVE_SNAPSHOT",
            load_and_exec_success=True,
        )
        self.last_validation_report = report
        self.switch_tab("tab-log")
        self._write_log(report.format_report(include_full_screen=True))
        self.notify("VALIDATION REPORT LOGGED TO BUILD LOG")

    def action_open_sprite_studio(self) -> None:
        """Launch the interactive C64 Retro Sprite Studio (HTML5 Canvas) from the Studio hub."""
        wb_mod = _tui_attr("webbrowser", webbrowser)
        html_path = Path(__file__).parent / "web" / "sprite_studio.html"
        if not html_path.is_file():
            self.notify(f"SPRITE STUDIO NOT FOUND: {html_path.name}", severity="error")
            return
        self._pulse_raster_border("LAUNCHING VIC-II SPRITE STUDIO", 380)
        wb_mod.open(html_path.resolve().as_uri())
        self._write_log(f"✓ Opened C64 Retro Sprite Studio in browser: {html_path.resolve()}")
        self.notify("OPENED VIC-II SPRITE STUDIO IN BROWSER")

    # -----------------------------------------------------------------------
    # AI CLI (`agy` & `claude`) Auto-Detection, Setup & Prompting
    # -----------------------------------------------------------------------

    def _active_provider(self) -> str:
        if hasattr(self, "agy_provider_var"):
            return normalize_provider(self.agy_provider_var.get())
        return normalize_provider(getattr(self.agy, "provider", "agy"))

    def _on_provider_menu_pick(self, chosen_label: str) -> None:
        chosen_id = "agy"
        for pid, plabel in AI_PROVIDERS:
            if plabel == chosen_label:
                chosen_id = pid
                break
        self.set_ai_provider(chosen_id, detect=True)

    def set_ai_provider(
        self,
        provider: str,
        *,
        detect: bool = True,
        persist: bool = True,
    ) -> None:
        """Switch active AI CLI provider between 'agy' (Antigravity) and 'claude' (Claude Code)."""
        prov = normalize_provider(provider)
        self.agy.provider = prov
        if hasattr(self, "agy_provider_var") and self.agy_provider_var.get() != prov:
            self.agy_provider_var.set(prov)
        if hasattr(self, "agy_provider_display_var"):
            self.agy_provider_display_var.set(dict(AI_PROVIDERS).get(prov, "Antigravity (agy)"))
        if persist:
            self._provider_explicitly_chosen = True
            save_studio_settings({"ai_provider": prov})

        # Load per-provider saved model if available
        if hasattr(self, "agy_model_var"):
            model_key = "claude_model" if prov == "claude" else "agy_model"
            saved_m = str(self._studio_settings.get(model_key, "")).strip()
            self._loading_studio_settings = True
            try:
                self.agy_model_var.set(saved_m)
            finally:
                self._loading_studio_settings = False

        if detect:
            st = self.agy.detect_cli(provider=prov)
            self.cli_statuses[prov] = st
        else:
            st = self.cli_statuses.get(prov) or AgyStatus(
                installed=False,
                models=default_models_for_provider(prov),
                install_command=install_commands_for_provider(prov)[0],
                install_command_alt=install_commands_for_provider(prov)[1],
                status_message=f"{provider_display_name(prov)} ({prov}) status pending.",
                provider=prov,
            )
        self._refresh_agy_badge(st)
        self._refresh_agy_model_menu(st.models or default_models_for_provider(prov))

    def _refresh_agy_badge(self, status: Optional[AgyStatus] = None) -> None:
        """Update the top-bar AI CLI status indicator pill and send button label."""
        if status is not None:
            self.agy_status = status
        if not self.root.winfo_exists():
            return
        prov = normalize_provider(getattr(self.agy_status, "provider", None) or self._active_provider())
        tag = provider_short_tag(prov)
        t = THEMES[self.current_theme]
        f_btn = (str(t["font_family"]), 8, "bold")
        if self.agy_status.installed:
            raw_ver = (self.agy_status.version or "").strip()
            if raw_ver and raw_ver[0].isdigit():
                ver_tag = f"v{raw_ver}"
            else:
                ver_tag = "READY"
            self.btn_agy_status.configure(
                text=f"● {tag} {ver_tag}",
                font=f_btn,
                bg=str(t["success"]),
                fg="#000000",
            )
        else:
            self.btn_agy_status.configure(
                text=f"! {tag} SETUP",
                font=f_btn,
                bg=str(t["warning"]),
                fg="#000000",
            )
        if not getattr(self, "_agy_busy", False) and hasattr(self, "btn_agy_send"):
            self.btn_agy_send.configure(text=f"▶ ASK {tag}")
        if hasattr(self, "btn_agy_setup_tab"):
            self.btn_agy_setup_tab.configure(text=f"{tag} SETUP")
        if hasattr(self, "btn_agy_term"):
            self.btn_agy_term.configure(text=f"▶ {tag} TERM")
        if hasattr(self, "menu_buttons"):
            if "btn-agy-setup" in self.menu_buttons:
                self.menu_buttons["btn-agy-setup"].configure(text=f"{tag} CLI SETUP [^K]")
            if "btn-agy-prompt" in self.menu_buttons:
                prompt_pad = " " if tag == "CLAUDE" else "  "
                self.menu_buttons["btn-agy-prompt"].configure(text=f"PROMPT {tag}{prompt_pad}[⇧F12]")
        if hasattr(self, "tab_buttons") and "tab-agy" in self.tab_buttons:
            self.tab_buttons["tab-agy"].configure(text=f"5:{tag} AI")

    def _on_agy_cli_option_changed(self, *_args) -> None:
        if getattr(self, "_loading_studio_settings", False):
            return
        prov = self._active_provider()
        model_id = self.agy_model_var.get().strip() if hasattr(self, "agy_model_var") else ""
        effort = self.agy_effort_var.get().strip() if hasattr(self, "agy_effort_var") else "medium"
        model_key = "claude_model" if prov == "claude" else "agy_model"
        self._studio_settings[model_key] = model_id
        self._studio_settings["agy_effort"] = effort
        save_studio_settings({model_key: model_id, "agy_effort": effort, "ai_provider": prov})

    def _refresh_agy_model_menu(self, models: Optional[list[tuple[str, str]]] = None) -> None:
        if not hasattr(self, "agy_model_menu"):
            return
        prov = self._active_provider()
        choices = list(models or getattr(self, "_agy_model_choices", None) or default_models_for_provider(prov))
        cur_id = self.agy_model_var.get().strip()
        if cur_id and all(mid != cur_id for mid, _ in choices):
            choices.append((cur_id, cur_id))
        self._agy_model_choices = choices

        menu = self.agy_model_menu["menu"]
        menu.delete(0, tk.END)
        cur_label = "Default CLI Model"
        for mid, lbl in choices:
            short_lbl = lbl if len(lbl) <= 28 else lbl[:25] + "..."
            if mid == cur_id:
                cur_label = short_lbl
            menu.add_command(
                label=short_lbl,
                command=lambda m_id=mid, disp=short_lbl: (
                    self.agy_model_var.set(m_id),
                    self.agy_model_display_var.set(disp),
                ),
            )
        self.agy_model_display_var.set(cur_label)

    def check_agy_cli_startup(self, full: bool = False) -> None:
        """Auto-detect both `agy` and `claude` CLI installations on C64 Studio startup."""
        if getattr(self, "_in_mainloop", False):
            def _bg() -> None:
                all_sts = self.agy.detect_all_clis(fetch_models=True)

                def _apply() -> None:
                    if not self.root.winfo_exists():
                        return
                    self.cli_statuses.update(all_sts)
                    active_prov = self._active_provider()
                    if (
                        not getattr(self, "_provider_explicitly_chosen", False)
                        and not all_sts[active_prov].installed
                    ):
                        for alt_prov, alt_st in all_sts.items():
                            if alt_st.installed:
                                active_prov = alt_prov
                                self.set_ai_provider(alt_prov, detect=False, persist=False)
                                break

                    st = all_sts[active_prov]
                    self._refresh_agy_badge(st)
                    if st.models:
                        self._refresh_agy_model_menu(st.models)

                    installed_list = [s for s in all_sts.values() if s.installed]
                    if installed_list:
                        for s in installed_list:
                            self._write_log(f"✓ {s.status_message}")
                        if len(installed_list) > 1:
                            self._write_log(
                                f"ℹ Multiple AI CLIs detected (active: {provider_display_name(active_prov)}). Switch anytime in 5:AI or CLI SETUP (^K)."
                            )
                    else:
                        self._write_log(
                            f"ℹ Neither Antigravity (`agy`) nor Claude Code (`claude`) CLI detected. Click '! {provider_short_tag(active_prov)} SETUP' (Ctrl+K) to install."
                        )

                try:
                    self.root.after(0, _apply)
                except (tk.TclError, RuntimeError):
                    pass

            threading.Thread(target=_bg, daemon=True).start()
            return

        active_prov = self._active_provider()
        if full:
            st = self.agy.detect_cli(provider=active_prov)
            other_prov = "claude" if active_prov == "agy" else "agy"
            other_st = self.agy.detect_cli(provider=other_prov)
            self.cli_statuses[active_prov] = st
            self.cli_statuses[other_prov] = other_st
        else:
            def _quick_status(prov_id: str) -> AgyStatus:
                b_path = self.agy.find_binary() if prov_id == "agy" else self.agy.find_binary(provider=prov_id)
                cmd_1, cmd_2 = install_commands_for_provider(prov_id)
                d_name = provider_display_name(prov_id)
                return AgyStatus(
                    installed=b_path is not None,
                    binary_path=b_path,
                    version="detected" if b_path is not None else None,
                    models=default_models_for_provider(prov_id),
                    install_command=cmd_1,
                    install_command_alt=cmd_2,
                    status_message=(
                        f"{d_name} detected at {b_path}"
                        if b_path
                        else f"{d_name} ({prov_id}) not detected on this system."
                    ),
                    provider=prov_id,
                )

            st = _quick_status(active_prov)
            other_prov = "claude" if active_prov == "agy" else "agy"
            other_st = _quick_status(other_prov)
            self.cli_statuses[active_prov] = st
            self.cli_statuses[other_prov] = other_st
            if not getattr(self, "_provider_explicitly_chosen", False) and not st.installed and other_st.installed:
                self.set_ai_provider(other_prov, detect=False, persist=False)
                st = other_st

        self._refresh_agy_badge(st)

    def action_open_agy_setup(self) -> None:
        """Open the guided AI CLI (`agy` & `claude`) setup, provider selector, and MCP linking modal."""
        active_prov = self._active_provider()
        fetch = getattr(self, "_in_mainloop", False)
        st = self.agy.detect_cli(fetch_models=fetch, provider=active_prov)
        other_prov = "claude" if active_prov == "agy" else "agy"
        other_st = self.agy.detect_cli(fetch_models=False, provider=other_prov)
        self.cli_statuses[active_prov] = st
        self.cli_statuses[other_prov] = other_st

        self._refresh_agy_badge(st)
        if st.models:
            self._refresh_agy_model_menu(st.models)
        modal = AgySetupModal(
            self.agy,
            st,
            provider=active_prov,
            all_statuses=self.cli_statuses,
        )
        self._last_agy_modal = modal
        modal.show_tk(self, callback=lambda updated: self._refresh_agy_badge(updated))

    def action_launch_agy_terminal(self) -> None:
        """Open an interactive AI CLI terminal window rooted in the workspace with live C64 Studio sync."""
        prov = self._active_provider()
        tag = provider_short_tag(prov)
        ok, msg = self.agy.launch_interactive_terminal(
            model=self.agy_model_var.get().strip(),
            effort=self.agy_effort_var.get().strip(),
            provider=prov,
        )
        self._write_log(f"{'✓' if ok else 'ℹ'} {msg}")
        self._write_agy_chat(
            f"\n[CLI TERMINAL] {msg}\n"
            "  • Any .asm / .c / .py / .sid files generated or MCP builds run in that CLI terminal "
            "automatically appear live in C64 Studio while 'LIVE CLI SYNC' is checked."
        )
        self.notify(f"LAUNCHED INTERACTIVE {tag} CLI TERMINAL" if ok else msg[:48].upper())

    def action_focus_agy_prompt(self) -> None:
        """Keep the main editor visible and focus the bottom Antigravity CLI prompt bar (`Shift+F12`)."""
        if self.file_mode in ("asm", "c", "py", "def"):
            self.agy_lang_var.set(self.file_mode)
        if self._active_tab not in ("tab-asm", "tab-agy"):
            self.switch_tab("tab-asm")
        try:
            self.agy_prompt_entry.focus_set()
            self.agy_prompt_entry.selection_range(0, tk.END)
        except tk.TclError:
            pass

    def _write_agy_chat(self, text: str) -> None:
        if not self.root.winfo_exists():
            return
        self.agy_chat_text.insert(tk.END, f"{text}\n")
        self.agy_chat_text.see(tk.END)

    def _append_agy_delta(self, chunk: str) -> None:
        """Append a live streaming text delta to the Antigravity CRT console without artificial newlines."""
        if not chunk or not self.root.winfo_exists():
            return
        self.agy_chat_text.insert(tk.END, chunk)
        self.agy_chat_text.see(tk.END)

    def _clear_agy_chat(self) -> None:
        self.agy_chat_text.delete("1.0", tk.END)

    def _preview_streaming_code_block(
        self,
        block: ExtractedCodeBlock,
        target_tab_id: Optional[str] = None,
    ) -> None:
        """Live-render an in-progress streamed code block into its target tab without clobbering other tabs."""
        if not self.root.winfo_exists() or not self.agy_auto_apply_var.get():
            return
        mode = block.studio_mode if block.studio_mode in ("asm", "c", "py", "def") else "asm"

        if (
            target_tab_id is not None
            and self.active_file_tab_id is not None
            and target_tab_id != self.active_file_tab_id
        ):
            bg_tab = self._get_tab_by_id(target_tab_id)
            if bg_tab is not None:
                bg_tab.file_mode = mode
                bg_tab.asm_focus_mode = False
                if mode == "asm":
                    bg_tab.asm_content = block.code
                    bg_tab.last_asm = block.code
                else:
                    bg_tab.py_content = block.code
                bg_tab.needs_disk_save = True
                self._render_file_tab_bar()
            return

        tab = self._ensure_active_file_tab()
        if mode == "asm":
            self.file_mode = "asm"
            self.asm_focus_mode = False
            self._sync_editor_display()
            self._set_asm_text(block.code)
            self.asm_text.see(tk.END)
        else:
            if self.file_mode != mode:
                self.file_mode = mode
            self.asm_focus_mode = False
            self._sync_editor_display()
            self._set_python_text(block.code)
            self.py_text.see(tk.END)
        self._sync_active_tab_from_widgets()
        tab.needs_disk_save = True
        self._update_mode_badge()

    def action_send_agy_prompt(
        self,
        prompt_override: Optional[str] = None,
        force_language: Optional[str] = None,
    ) -> None:
        """Send a prompt from C64 Studio to the active AI CLI (`agy` or `claude`) with live tab-safe streaming."""
        prov = self._active_provider()
        disp_name = provider_display_name(prov)
        tag = provider_short_tag(prov)

        if self._agy_busy:
            self.notify(f"{disp_name.upper()} IS CURRENTLY GENERATING...", severity="warning")
            return

        user_prompt = (
            prompt_override if prompt_override is not None else self.agy_prompt_var.get()
        ).strip()
        if not user_prompt:
            self.action_focus_agy_prompt()
            self.notify(f"ENTER A PROMPT FOR {disp_name.upper()} [⇧F12]")
            return

        st = self.agy.detect_cli(provider=prov)
        self._refresh_agy_badge(st)
        if not st.installed:
            self.switch_tab("tab-agy")
            self._write_agy_chat(
                f"⚠ {disp_name} (`{prov}`) was not detected on this machine.\n"
                f"  • Install Command : {st.install_command}\n"
                "  • Opening the C64 Studio AI CLI Setup Wizard so you can auto-install or switch CLIs in 1 click!"
            )
            self.notify(f"{tag} CLI NOT FOUND — OPENING SETUP WIZARD", severity="warning")
            self.action_open_agy_setup()
            return

        if prompt_override is None:
            self.agy_prompt_var.set("")

        if force_language and force_language in ("asm", "c", "py", "def"):
            target_lang = force_language
        else:
            base_lang = (self.agy_lang_var.get() or self.file_mode or "asm").strip().lower()
            if base_lang not in ("asm", "c", "py", "def"):
                base_lang = "asm"
            target_lang = infer_prompt_language(user_prompt, fallback_mode=base_lang)
        self.agy_lang_var.set(target_lang)

        current_code = (
            self.asm_text.get("1.0", "end-1c")
            if self.file_mode == "asm"
            else self.py_text.get("1.0", "end-1c")
        )
        include_ctx = bool(self.agy_include_ctx_var.get())
        continue_conv = bool(self.agy_continue_var.get())
        exec_mode = self.agy_mode_var.get().strip() or "accept-edits"
        effort_level = self.agy_effort_var.get().strip()

        origin_tab = self._ensure_active_file_tab()
        origin_tab_id = origin_tab.tab_id
        origin_loaded_file = origin_tab.loaded_file

        # Keep the single main editor focused so the user watches `agy` generate/edit right in place
        if self.agy_auto_apply_var.get():
            # If an existing file tab has a different language extension than target_lang, open a fresh tab
            if origin_loaded_file is not None:
                suf = origin_loaded_file.suffix.lower()
                mismatch = (
                    (target_lang == "asm" and suf not in (".asm", ".s"))
                    or (target_lang == "c" and suf not in (".c", ".cpp", ".cc", ".cxx", ".h"))
                    or (target_lang in ("py", "def") and suf != ".py")
                )
                if mismatch:
                    ext_map = {"asm": ".asm", "c": ".c", "py": ".py", "def": ".py"}
                    origin_tab = self._open_or_reuse_untitled_tab(
                        f"agy_generated{ext_map.get(target_lang, '.asm')}"
                    )
                    origin_tab_id = origin_tab.tab_id
                    origin_loaded_file = None
                    self._begin_load("python" if target_lang == "py" else target_lang, None)

            if target_lang == "asm":
                self.file_mode = "asm"
                self.asm_focus_mode = False
            else:
                if self.file_mode != target_lang:
                    self.file_mode = target_lang
                self.asm_focus_mode = False
            self._sync_active_tab_from_widgets()
            self.switch_tab("tab-asm")
            self._update_mode_badge()
        else:
            self.switch_tab("tab-agy")

        self._agy_busy = True
        self._agy_started_at = time.monotonic()
        self._agy_status_base = f"{tag} CONNECTING ({target_lang.upper()})"
        self._border_busy = True
        self._busy_phase = f"{self._agy_status_base} [0S]"
        self.btn_agy_send.configure(state=tk.DISABLED, text="... CONNECTING (0s)")
        self._set_agy_live_banner(
            True,
            f"▶ {self._agy_status_base} [0s] — Generating directly into {target_lang.upper()} editor...",
        )
        self._draw_border_and_divider()
        self._draw_bottom_deck()

        self._write_agy_chat(f"\n>>> YOU [{target_lang.upper()} -> {tag}]: {user_prompt}")
        self._write_agy_chat(f"─── {disp_name.upper()} LIVE STREAM ────────────────────────────────────────")

        stream_accum: list[str] = []
        saw_delta = False
        last_preview_ts = 0.0
        last_logged_status = ""

        def _handle_status(status_msg: str) -> None:
            nonlocal last_logged_status
            if not self.root.winfo_exists():
                return
            self._agy_status_base = status_msg[:36]
            elapsed_s = max(0, int(time.monotonic() - self._agy_started_at))
            self._busy_phase = f"{self._agy_status_base} [{elapsed_s}S]"[:46]
            short_btn = status_msg.replace(f"{tag} ", "").replace("AGY ", "")[:14]
            self.btn_agy_send.configure(text=f"... {short_btn} ({elapsed_s}s)")
            self._set_agy_live_banner(
                True,
                f"▶ {self._agy_status_base} [{elapsed_s}s] — Live-editing {target_lang.upper()} editor",
            )
            self._draw_bottom_deck()
            if (
                status_msg != last_logged_status
                and (
                    "CONNECTED" in status_msg
                    or "THINKING" in status_msg
                    or "TOOL:" in status_msg
                    or "TOOL BLOCKED" in status_msg
                )
            ):
                last_logged_status = status_msg
                tail_char = self.agy_chat_text.get("end-2c", "end-1c")
                prefix = "\n" if tail_char and tail_char != "\n" else ""
                self._append_agy_delta(f"{prefix}  • {status_msg}\n")

        def _handle_delta(chunk: str) -> None:
            nonlocal saw_delta, last_preview_ts
            saw_delta = True
            stream_accum.append(chunk)
            self._append_agy_delta(chunk)
            now = time.monotonic()
            if self.agy_auto_apply_var.get() and (now - last_preview_ts >= 0.12 or "\n" in chunk):
                last_preview_ts = now
                preview = extract_streaming_code_preview("".join(stream_accum), preferred_mode=target_lang)
                if preview is not None:
                    self._preview_streaming_code_block(preview, target_tab_id=origin_tab_id)

        def _handle_file_edit_start(fpath: Path) -> None:
            self._focus_file_for_cli_edit(fpath, source_tag=f"{tag} EDIT")

        def _handle_file_write(fpath: Path, _content: Optional[str]) -> None:
            self._record_self_saved_file(fpath)
            self._write_log(f"✓ {disp_name} updated file on disk: {fpath}")
            if self.agy_auto_apply_var.get() and fpath.is_file():
                self._sync_external_file(fpath, source_tag=f"{tag} WRITE", allow_reload_tab_id=origin_tab_id)

        def _finish(res: AgyPromptResult) -> None:
            self._agy_busy = False
            self._border_busy = False
            self._busy_phase = "READY // DMA LINK IDLE"
            self.last_agy_result = res
            if self.root.winfo_exists():
                self._set_agy_live_banner(False)
                self.btn_agy_send.configure(state=tk.NORMAL, text=f"▶ ASK {tag}")
                self._draw_border_and_divider()
                self._draw_bottom_deck()

            if not saw_delta and res.response_text.strip():
                self._write_agy_chat(res.response_text)
            elif saw_delta:
                tail_char = self.agy_chat_text.get("end-2c", "end-1c")
                if tail_char and tail_char != "\n":
                    self._append_agy_delta("\n")

            if not res.success and res.error_message:
                self.switch_tab("tab-agy")
                self._write_agy_chat(f"✗ Error: {res.error_message}")
                self._write_log(f"✗ {disp_name} Error: {res.error_message}")
                self.notify(f"{tag} CLI ERROR (SEE AI CONSOLE)", severity="error")
                return

            block = res.primary_code_block
            if res.touched_files:
                if block is not None:
                    self.last_agy_code_block = block
                latest_file = res.touched_files[-1]
                if self.agy_auto_apply_var.get() and latest_file.is_file():
                    self._sync_external_file(
                        latest_file,
                        source_tag=f"{tag} CLI",
                        allow_reload_tab_id=origin_tab_id,
                    )
                else:
                    self.notify(f"{tag} UPDATED {latest_file.name.upper()}")
            elif block is not None:
                self.last_agy_code_block = block
                line_cnt = len(block.code.splitlines())
                self._write_agy_chat(
                    f"✓ Extracted {block.studio_mode.upper()} code block ({line_cnt} lines)."
                )
                self._write_log(
                    f"✓ {disp_name} generated {block.studio_mode.upper()} code ({line_cnt} lines)."
                )
                if self.agy_auto_apply_var.get():
                    self._apply_extracted_code_block(block, target_tab_id=origin_tab_id)
                else:
                    self.switch_tab("tab-agy")
                    self.notify(f"{tag} {block.studio_mode.upper()} CODE READY — CLICK APPLY")
            else:
                self.switch_tab("tab-agy")
                self.notify(f"{tag} RESPONSE RECEIVED")

        model_id = self.agy_model_var.get().strip() if hasattr(self, "agy_model_var") else ""

        if getattr(self, "_in_mainloop", False):
            def _worker() -> None:
                res = self.agy.run_prompt(
                    user_prompt,
                    language_mode=target_lang,
                    current_code=current_code,
                    active_file=origin_loaded_file,
                    include_code_context=include_ctx,
                    continue_conversation=continue_conv,
                    exec_mode=exec_mode,
                    model=model_id,
                    effort=effort_level,
                    provider=prov,
                    on_delta=lambda d: self.root.after(0, lambda chunk=d: _handle_delta(chunk)),
                    on_status=lambda s: self.root.after(0, lambda st_msg=s: _handle_status(st_msg)),
                    on_file_write=lambda p, c: self.root.after(
                        0, lambda fp=p, txt=c: _handle_file_write(fp, txt)
                    ),
                    on_file_edit_start=lambda p: self.root.after(
                        0, lambda fp=p: _handle_file_edit_start(fp)
                    ),
                )
                try:
                    self.root.after(0, lambda: _finish(res))
                except (tk.TclError, RuntimeError):
                    self._agy_busy = False
                    self._border_busy = False

            threading.Thread(target=_worker, daemon=True).start()
        else:
            res = self.agy.run_prompt(
                user_prompt,
                language_mode=target_lang,
                current_code=current_code,
                active_file=origin_loaded_file,
                include_code_context=include_ctx,
                continue_conversation=continue_conv,
                exec_mode=exec_mode,
                model=model_id,
                effort=effort_level,
                provider=prov,
                on_delta=_handle_delta,
                on_status=_handle_status,
                on_file_write=_handle_file_write,
                on_file_edit_start=_handle_file_edit_start,
            )
            _finish(res)

    def _apply_extracted_code_block(
        self,
        block: ExtractedCodeBlock,
        target_tab_id: Optional[str] = None,
    ) -> None:
        """
        Apply an extracted Antigravity code block (`asm`, `c`, `py`, or `def`) to `target_tab_id`
        (or the active tab) and mark it `*` dirty if unsaved on disk so tab switches never lose AGY edits.
        """
        mode = block.studio_mode if block.studio_mode in ("asm", "c", "py", "def") else "asm"

        # Resolve target tab; if user switched to another tab (e.g. build.py) while AGY was running,
        # apply AGY's edits cleanly into `bg_tab` without clobbering the currently viewed tab!
        bg_tab = (
            self._get_tab_by_id(target_tab_id)
            if (target_tab_id is not None and target_tab_id != self.active_file_tab_id)
            else None
        )
        if bg_tab is not None:
            target_loaded = bg_tab.loaded_file
            if target_loaded is not None:
                suf = target_loaded.suffix.lower()
                if (
                    (mode == "asm" and suf not in (".asm", ".s"))
                    or (mode == "c" and suf not in (".c", ".cpp", ".cc", ".cxx", ".h"))
                    or (mode in ("py", "def") and suf != ".py")
                ):
                    ext_map = {"asm": ".asm", "c": ".c", "py": ".py", "def": ".py"}
                    bg_tab = EditorTabState(
                        tab_id=self._new_tab_id(),
                        title_hint=f"agy_generated{ext_map.get(mode, '.asm')}",
                    )
                    self.open_tabs.append(bg_tab)
                    target_loaded = None

            disk_matches = False
            if target_loaded is not None and target_loaded.is_file():
                try:
                    disk_matches = target_loaded.read_text(encoding="utf-8") == block.code
                except OSError:
                    disk_matches = False

            bg_tab.file_mode = mode
            bg_tab.asm_focus_mode = False
            bg_tab.stage = 1
            if mode == "def":
                bg_tab.file_kind = bg_tab.file_kind if bg_tab.file_kind in ("build", *DEFINITION_KINDS) else "build"
                bg_tab.py_content = block.code
            elif mode == "asm":
                bg_tab.file_kind = "sid" if ("C64U_SID_METADATA:" in block.code or bg_tab.file_kind == "sid") else "asm"
                bg_tab.asm_content = block.code
                bg_tab.last_asm = block.code
            else:
                bg_tab.file_kind = "sid" if (mode == "py" and "C64U_SID_METADATA:" in block.code) else ("python" if mode == "py" else mode)
                bg_tab.py_content = block.code
            if disk_matches:
                bg_tab.baseline_text = block.code
                bg_tab.needs_disk_save = False
            else:
                bg_tab.needs_disk_save = True
            self._render_file_tab_bar()
            self._write_log(
                f"✓ Applied Antigravity {mode.upper()} changes into open tab `{bg_tab.display_name()}` ({len(block.code.splitlines())} lines)"
            )
            self.notify(f"AGY UPDATED TAB: {bg_tab.display_name().upper()}")
            return

        # Applying into the currently active tab: if loaded_file has a different language extension,
        # open a dedicated new tab instead of overwriting the loaded file's tab!
        active_tab = self._ensure_active_file_tab()
        target_loaded = self.loaded_file
        if target_loaded is not None:
            suf = target_loaded.suffix.lower()
            mismatch = (
                (mode == "asm" and suf not in (".asm", ".s"))
                or (mode == "c" and suf not in (".c", ".cpp", ".cc", ".cxx", ".h"))
                or (mode in ("py", "def") and suf != ".py")
            )
            if mismatch:
                ext_map = {"asm": ".asm", "c": ".c", "py": ".py", "def": ".py"}
                active_tab = self._open_or_reuse_untitled_tab(
                    f"agy_generated{ext_map.get(mode, '.asm')}"
                )
                target_loaded = None

        disk_matches = False
        if target_loaded is not None and target_loaded.is_file():
            try:
                disk_matches = target_loaded.read_text(encoding="utf-8") == block.code
            except OSError:
                disk_matches = False

        if mode == "def":
            preserved_kind = self.file_kind if self.file_kind in ("build", *DEFINITION_KINDS) else "build"
            self._begin_load(preserved_kind, target_loaded)
            self.file_mode = "def"
            self.asm_focus_mode = False
            self.agy_lang_var.set("def")
            self._set_python_text(block.code)
            self._sync_active_tab_from_widgets()
            if disk_matches:
                self._mark_editor_synced()
            else:
                active_tab.needs_disk_save = True
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self._write_log(
                f"✓ Applied Antigravity Game Dev definition into editor ({len(block.code.splitlines())} lines)"
            )
            self.notify("APPLIED AGY GAME DEFINITION — CTRL+S TO SAVE OR F7 TO BUILD")
            return

        if mode == "asm" and ("C64U_SID_METADATA:" in block.code or self.file_kind == "sid"):
            kind = "sid"
        elif mode == "py" and "C64U_SID_METADATA:" in block.code:
            kind = "sid"
        else:
            kind = "python" if mode == "py" else mode

        self._begin_load(kind, target_loaded)
        self.file_mode = mode
        self.asm_focus_mode = False
        self.agy_lang_var.set(mode)

        if mode == "asm":
            self.last_asm = block.code
            self._set_asm_text(block.code)
            self._sync_active_tab_from_widgets()
            if disk_matches:
                self._mark_editor_synced()
            else:
                active_tab.needs_disk_save = True
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self._write_log(
                f"✓ Applied Antigravity 6502 Assembly into editor ({len(block.code.splitlines())} lines)"
            )
            self.notify("APPLIED AGY 6502 ASM (*) — CTRL+S TO SAVE OR F5 TO RUN")
        else:
            self._set_python_text(block.code)
            if mode == "py":
                self.action_transpile_code(silent=True)
            self._sync_active_tab_from_widgets()
            if disk_matches:
                self._mark_editor_synced()
            else:
                active_tab.needs_disk_save = True
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            if mode == "py":
                self._write_log(
                    f"✓ Applied Antigravity Python code & transpiled to 6502 ASM ({len(block.code.splitlines())} lines)"
                )
                self.notify("APPLIED AGY PYTHON (*) — CTRL+S TO SAVE OR F5 TO RUN")
            else:
                self._write_log(
                    f"✓ Applied Antigravity C (Oscar64/CC65) code into editor ({len(block.code.splitlines())} lines)"
                )
                self.notify("APPLIED AGY C SOURCE (*) — CTRL+S TO SAVE OR F5 TO RUN")

    # -----------------------------------------------------------------------
    # External CLI & MCP Live Workspace Sync
    # -----------------------------------------------------------------------

    def _iter_watched_workspace_files(self) -> list[Path]:
        """Return candidate source files across the workspace for external CLI live sync."""
        watched_exts = {".asm", ".s", ".c", ".cpp", ".cc", ".cxx", ".py", ".sid"}
        ignored_dirs = {
            ".git",
            ".venv",
            ".pytest_cache",
            "__pycache__",
            ".agents",
            "src",
            "tests",
            "tools",
            "curated_core_docs",
            "screenshots",
            "build",
            "dist",
        }
        root_dir = self.agy.workspace_dir
        results: list[Path] = []
        if self.loaded_file and self.loaded_file.is_file():
            results.append(self.loaded_file.resolve())

        try:
            for entry in root_dir.iterdir():
                if entry.name.startswith(".") or entry.name in ignored_dirs:
                    continue
                if entry.is_file() and entry.suffix.lower() in watched_exts:
                    results.append(entry.resolve())
                elif entry.is_dir():
                    for sub in entry.rglob("*"):
                        if any(part.startswith(".") or part in ignored_dirs for part in sub.parts):
                            continue
                        if sub.is_file() and sub.suffix.lower() in watched_exts:
                            results.append(sub.resolve())
        except OSError:
            pass
        return results

    def _init_external_cli_watch_state(self) -> None:
        """Snapshot workspace file mtimes and seek to the end of the MCP event journal at startup."""
        self._workspace_watch_mtimes.clear()
        for fpath in self._iter_watched_workspace_files():
            try:
                st = fpath.stat()
                self._workspace_watch_mtimes[fpath] = (st.st_mtime_ns, st.st_size)
            except OSError:
                pass
        journal = get_studio_event_journal_path()
        try:
            self._studio_journal_offset = journal.stat().st_size if journal.is_file() else 0
        except OSError:
            self._studio_journal_offset = 0

    def _focus_file_for_cli_edit(self, path: Path, source_tag: str = "AGY EDIT") -> None:
        """Open/focus the file currently being edited by the CLI so the user can follow along in the IDE."""
        if not self.root.winfo_exists():
            return
        resolved = path.resolve()
        self._sync_active_tab_from_widgets()
        existing_tab = self._find_open_tab_for_path(resolved)
        if existing_tab is not None:
            if existing_tab.tab_id != self.active_file_tab_id:
                self.switch_file_tab(existing_tab.tab_id)
        elif resolved.is_file():
            self.load_project_file(resolved)
        if self.agy_auto_apply_var.get():
            self.switch_tab("tab-asm")
        self._set_agy_live_banner(True, f"▶ {source_tag}: EDITING {resolved.name.upper()}...")

    def _highlight_cli_edited_lines(self, prev_text: str, new_text: str) -> None:
        """Scroll the active editor to the first changed line and briefly highlight the edited lines."""
        import difflib

        widget = self.asm_text if self._is_asm_view_active() else self.py_text
        widget.tag_remove("agy_edit_line", "1.0", tk.END)
        old_lines = prev_text.splitlines()
        new_lines = new_text.splitlines()
        if not new_lines:
            return
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        first_line: Optional[int] = None
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag in ("replace", "insert") and j2 > j1:
                if first_line is None:
                    first_line = j1 + 1
                for ln in range(j1 + 1, j2 + 1):
                    widget.tag_add("agy_edit_line", f"{ln}.0", f"{ln}.end+1c")
        if first_line is not None:
            pos = f"{first_line}.0"
            widget.mark_set(tk.INSERT, pos)
            widget.see(pos)
            if self._is_asm_view_active():
                self._on_asm_cursor_move()
            else:
                self._on_py_cursor_move()
            if getattr(self, "_in_mainloop", False):
                self.root.after(
                    2600,
                    lambda w=widget: w.tag_remove("agy_edit_line", "1.0", tk.END)
                    if self.root.winfo_exists()
                    else None,
                )

    def _sync_external_file(
        self,
        path: Path,
        source_tag: str = "EXTERNAL CLI",
        allow_reload_tab_id: Optional[str] = None,
    ) -> None:
        """Load or refresh a source file created/modified by an external CLI into its own tab."""
        if not path.is_file():
            return
        resolved = path.resolve()
        try:
            st = resolved.stat()
            self._workspace_watch_mtimes[resolved] = (st.st_mtime_ns, st.st_size)
        except OSError:
            return

        self._sync_active_tab_from_widgets()
        existing_tab = self._find_open_tab_for_path(resolved)
        prev_text = existing_tab.primary_text() if existing_tab is not None else ""
        try:
            disk_text = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            disk_text = ""

        if existing_tab is not None and not existing_tab.is_dirty and prev_text == disk_text:
            if existing_tab.tab_id != self.active_file_tab_id:
                self.switch_file_tab(existing_tab.tab_id)
            if self.agy_auto_apply_var.get():
                self.switch_tab("tab-asm")
            return

        if existing_tab is not None and existing_tab.is_dirty:
            if allow_reload_tab_id is not None and existing_tab.tab_id == allow_reload_tab_id:
                existing_tab.needs_disk_save = False
                existing_tab.baseline_text = existing_tab.primary_text()
            else:
                msg = (
                    f"ℹ [{source_tag}] {resolved.name} changed on disk — "
                    "unsaved editor edits preserved (press F3 to reload)."
                )
                self._write_log(msg)
                self._write_agy_chat(msg)
                return

        self.load_project_file(resolved)
        if self.agy_auto_apply_var.get():
            self.switch_tab("tab-asm")
            new_tab = self._find_open_tab_for_path(resolved)
            new_text = new_tab.primary_text() if new_tab is not None else ""
            if new_text and new_text != prev_text:
                self._highlight_cli_edited_lines(prev_text, new_text)
        try:
            rel_disp = str(resolved.relative_to(self.agy.workspace_dir))
        except ValueError:
            rel_disp = resolved.name
        notice = f"📥 [{source_tag}] Live-synced `{rel_disp}` into C64 Studio."
        self._write_agy_chat(notice)
        self._write_log(notice)
        self.notify(f"{source_tag}: SYNCED {resolved.name.upper()}")

    def _poll_external_cli_activity(self) -> None:
        """Poll MCP bridge events and external CLI workspace file writes (~800ms cadence)."""
        if not self.agy_watch_cli_var.get():
            return

        # 1. Tail MCP server event journal (fires when external `agy` runs c64_build_and_run, etc.)
        journal = get_studio_event_journal_path()
        if journal.is_file():
            try:
                sz = journal.stat().st_size
                if sz < self._studio_journal_offset:
                    self._studio_journal_offset = 0
                if sz > self._studio_journal_offset:
                    with journal.open("r", encoding="utf-8", errors="replace") as fh:
                        fh.seek(self._studio_journal_offset)
                        new_chunk = fh.read()
                        self._studio_journal_offset = fh.tell()
                    for raw_ln in new_chunk.splitlines():
                        raw_ln = raw_ln.strip()
                        if not raw_ln:
                            continue
                        try:
                            evt = json.loads(raw_ln)
                        except Exception:
                            continue
                        phase = evt.get("phase", "")
                        tool_name = evt.get("tool", "mcp")
                        summary = evt.get("summary") or f"{tool_name} ({phase})"
                        ok = bool(evt.get("ok", True))
                        src_str = evt.get("source_path")
                        prg_str = evt.get("prg_path")
                        sid_str = evt.get("sid_path")

                        if phase == "start":
                            self._pulse_raster_border(f"CLI MCP: {tool_name.upper()}", 900)
                            self._write_agy_chat(f"\n⚡ [CLI → MCP] {summary}")
                            self._write_log(f"⚡ [CLI → MCP] {summary}")
                            if src_str and Path(src_str).is_file() and not self._agy_busy:
                                self._sync_external_file(Path(src_str), source_tag="CLI MCP")
                        elif phase == "done":
                            icon = "✓" if ok else "✗"
                            self._write_agy_chat(f"{icon} [CLI → MCP] {summary}")
                            self._write_log(f"{icon} [CLI → MCP] {summary}")
                            if prg_str and Path(prg_str).is_file():
                                self.last_prg_path = Path(prg_str)
                            if sid_str and Path(sid_str).is_file():
                                self.last_sid_path = Path(sid_str)
                            self.notify(
                                summary[:46].upper(),
                                severity="information" if ok else "error",
                            )
            except OSError:
                pass

        # 2. Check watched workspace files for external CLI creations/modifications
        if self._agy_busy:
            return

        changed_files: list[tuple[int, Path]] = []
        for fpath in self._iter_watched_workspace_files():
            try:
                st = fpath.stat()
            except OSError:
                continue
            sig = (st.st_mtime_ns, st.st_size)
            prev_sig = self._workspace_watch_mtimes.get(fpath)
            if prev_sig == sig:
                continue
            self._workspace_watch_mtimes[fpath] = sig
            if self._self_written_mtimes.get(fpath) == st.st_mtime_ns:
                continue
            if st.st_size > 0:
                changed_files.append((st.st_mtime_ns, fpath))

        if changed_files:
            changed_files.sort(key=lambda item: item[0])
            newest_path = changed_files[-1][1]
            self._sync_external_file(newest_path, source_tag="EXTERNAL CLI")

    def action_apply_last_agy_code(self) -> None:
        """Apply the most recent code block generated by Antigravity CLI into the editor."""
        if self.last_agy_code_block is None:
            self.notify("NO ANTIGRAVITY CODE BLOCK TO APPLY YET", severity="warning")
            return
        self._apply_extracted_code_block(self.last_agy_code_block)
        if self.last_agy_code_block.studio_mode == "asm":
            self.switch_tab("tab-asm")

    def action_apply_and_run_agy_code(self) -> None:
        """Apply the most recent Antigravity CLI code block and immediately compile & DMA run on C64U."""
        if self.last_agy_code_block is not None:
            self._apply_extracted_code_block(self.last_agy_code_block)
        self.action_run_c64u()

    def action_quit(self) -> None:
        if self.root.winfo_exists():
            self.root.quit()
            self.root.destroy()

    def query_one(self, selector: str, _expected_type: object = None):
        """Compatibility helper for querying editor text or buttons by ID."""
        clean = selector.lstrip("#")
        if clean == "asm-viewer":
            return _TextWidgetAdapter(self.asm_text)
        if clean == "python-editor":
            return _TextWidgetAdapter(self.py_text)
        if clean == "agy-chat":
            return _TextWidgetAdapter(self.agy_chat_text)
        if clean in self.menu_buttons:
            return self.menu_buttons[clean]
        if clean in self.col_frames:
            return self.col_frames[clean]
        if clean == "menu-bar":
            return self.menu_bar
        raise KeyError(f"Unknown widget selector: {selector}")

    def run_test(self):
        """Async context manager for headless automated tests."""
        app = self

        class _TestContext:
            async def __aenter__(self):
                try:
                    app.root.withdraw()
                    app._finish_boot_sequence()
                    app.root.update_idletasks()
                except tk.TclError:
                    pass
                return app

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                try:
                    for child in list(app.root.winfo_children()):
                        child.destroy()
                    app.root.withdraw()
                except tk.TclError:
                    pass

        return _TestContext()

    def run(self) -> None:
        """Start the Tkinter main event loop."""
        self._in_mainloop = True
        self.check_bridge_status()
        self.root.mainloop()


# Backwards-compatible class alias for callers importing C64PythonToAsmApp
C64PythonToAsmApp = C64StudioApp


class _TextWidgetAdapter:
    """Thin adapter exposing `.text` and `.read_only` on a `tk.Text` widget."""

    def __init__(self, widget: tk.Text):
        self._widget = widget

    @property
    def text(self) -> str:
        return self._widget.get("1.0", "end-1c")

    @property
    def read_only(self) -> bool:
        return str(self._widget.cget("state")) == "disabled"


def _dispatch_run_script(raw_args: list[str]) -> Optional[int]:
    """Execute an external Python script inside the frozen/bundled runtime."""
    import os
    import runpy
    from .env import get_app_root, load_env, prepend_local_tool_paths

    if len(raw_args) < 2:
        sys.stderr.write("Usage: C64-Studio.exe --run-script <script.py> [args...]\n")
        return 2

    script_path = Path(raw_args[1]).resolve()
    if not script_path.is_file():
        sys.stderr.write(f"Script not found: {script_path}\n")
        return 2

    load_env()
    prepend_local_tool_paths(os.environ)

    app_root = get_app_root()
    for extra in (app_root / "tools", app_root / "src", script_path.parent):
        extra_str = str(extra)
        if extra.is_dir() and extra_str not in sys.path:
            sys.path.insert(0, extra_str)

    sys.argv = [str(script_path), *raw_args[2:]]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        sys.stderr.write(f"{code}\n")
        return 1


def main(argv: Optional[list[str]] = None) -> None:
    """Primary hub entry point for C64 Studio (`c64-studio`, `c64u-studio`, `c64u`, `c64u-bridge`)."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "--run-script":
        raise SystemExit(_dispatch_run_script(raw_args))

    import argparse

    parser = argparse.ArgumentParser(
        prog="c64-studio",
        description="C64 Studio — Commodore 64 Multi-Language IDE (6502 ASM, C/Oscar64, Python) + Antigravity CLI",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Optional .asm, .py, .c, .cpp, .sid, .prg, .tap, or .d64 file to open on startup",
    )
    parser.add_argument(
        "--no-boot",
        action="store_true",
        help="Skip the startup Station 88 Retro splash screen",
    )
    parser.add_argument("--host", help="C64U IP address or hostname (default: env C64U_HOST or c64u.local)")
    parser.add_argument("--port", type=int, default=80, help="C64U REST API port (default: 80)")
    parser.add_argument("--password", help="Optional C64U network password")
    parser.add_argument("--agy-bin", help="Optional explicit path to the Antigravity CLI (`agy`) binary")
    parser.add_argument("--claude-bin", help="Optional explicit path to the Claude Code CLI (`claude`) binary")
    parser.add_argument(
        "--ai-provider",
        choices=("agy", "claude"),
        help="Active AI CLI provider ('agy' or 'claude')",
    )
    args = parser.parse_args(argv)

    app = C64StudioApp(
        skip_boot=args.no_boot,
        start_maximized=True,
        host=args.host,
        port=args.port,
        password=args.password,
        agy_bin=args.agy_bin,
        claude_bin=args.claude_bin,
        ai_provider=args.ai_provider,
    )
    if args.file:
        p = Path(args.file)
        if p.exists():
            app.root.after(150, lambda target=p: app.load_project_file(target))
    app.run()


if __name__ == "__main__":
    main()
