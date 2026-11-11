"""
C64 Studio — Commodore 64 Multi-Language IDE, Game Studio & Antigravity AI Hub (Tkinter).

Provides an authentic Commodore 64 BASIC V2 screen experience with:
- Authentic C64 boot sequence (`LOAD "C64-BRIDGE",8,1`, VIC-II raster bars, `RUN`)
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
import os
import re
import sys
import tempfile
import threading
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
    INSTALL_CMD_UNIX,
    INSTALL_CMD_WINDOWS_PS1,
    AgyCliConnector,
    AgyPromptResult,
    AgyStatus,
    ExtractedCodeBlock,
)
from .client import C64UClient
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
# Press F6 to Transpile -> 6502 ASM, F7 to Build, or F5 to Build & DMA Run
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
    Interactive C64 Studio Setup & Walkthrough Modal for Google Antigravity CLI (`agy`).
    Auto-detects `agy`, provides copyable install commands OR 1-click auto-download/install,
    assists with first-run authentication, and links the `c64u-bridge` MCP server.
    """

    def __init__(self, connector: AgyCliConnector, status: Optional[AgyStatus] = None):
        self.connector = connector
        self.status = status or connector.detect_cli()

    def _build_walkthrough_text(self) -> str:
        s = self.status
        step1_state = (
            f"✓ DETECTED: agy v{s.version or 'installed'} ({s.binary_path})"
            if s.installed
            else "✗ NOT DETECTED ON PATH OR STANDARD INSTALL FOLDERS"
        )
        step3_state = (
            "✓ LINKED (`c64u-bridge` MCP active for hardware DMA & screen inspection)"
            if s.mcp_configured
            else "○ NOT YET LINKED (Click 'LINK C64U MCP' below for 1-click setup)"
        )
        lines = [
            "STEP 1 — ANTIGRAVITY CLI (`agy`) AUTO-DETECTION & INSTALLATION",
            f"  Status  : {step1_state}",
            f"  Command : {s.install_command}",
        ]
        if not s.installed:
            lines.append(
                "  Action  : Click '⬇ AUTO-INSTALL AGY CLI' to download & install automatically,\n"
                "            or click '📋 COPY INSTALL CMD' to run it in your own terminal."
            )
        lines.extend(
            [
                "────────────────────────────────────────────────────────────────────────────",
                "STEP 2 — SIGN IN / AUTHENTICATE (FIRST RUN ONLY)",
                "  Guide   : On first run, `agy` opens a browser sign-in prompt to authenticate.",
                "            Click '🔑 AUTH TERMINAL' if you haven't signed in to `agy` yet.",
                "────────────────────────────────────────────────────────────────────────────",
                "STEP 3 — CONNECT C64U HARDWARE BRIDGE MCP SERVER",
                f"  Status  : {step3_state}",
                "  Guide   : Linking `c64u-bridge` lets Antigravity compile ASM/C/Python, push",
                "            via DMA to your C64U, and inspect Screen RAM automatically!",
            ]
        )
        return "\n".join(lines)

    def show_tk(self, parent: "C64StudioApp", callback: Optional[Callable[[AgyStatus], None]] = None) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        parent._apply_application_icon(dlg)
        dlg.title("C64 STUDIO // ANTIGRAVITY CLI (AGY) SETUP WALKTHROUGH")
        dlg.geometry("900x520")
        border_col = str(t["success"]) if self.status.installed else str(t["warning"])
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=border_col)
        dlg.transient(parent.root)

        hdr_lbl = tk.Label(
            dlg,
            text=(
                "[ ✓ GOOGLE ANTIGRAVITY CLI (`agy`) CONNECTED — SETUP & MCP WIZARD ]"
                if self.status.installed
                else "[ ! GOOGLE ANTIGRAVITY CLI (`agy`) SETUP WALKTHROUGH ! ]"
            ),
            font=(font_fam, 10, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["success"]) if self.status.installed else str(t["warning"]),
            pady=8,
        )
        hdr_lbl.pack(fill=tk.X, padx=14, pady=(12, 6))
        self.hdr_lbl = hdr_lbl

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

        def _refresh_ui(msg: Optional[str] = None) -> None:
            self.status = self.connector.detect_cli()
            parent._refresh_agy_badge(self.status)
            if not dlg.winfo_exists():
                return
            dlg.configure(
                highlightbackground=str(t["success"]) if self.status.installed else str(t["warning"])
            )
            hdr_lbl.configure(
                text=(
                    "[ ✓ GOOGLE ANTIGRAVITY CLI (`agy`) CONNECTED — SETUP & MCP WIZARD ]"
                    if self.status.installed
                    else "[ ! GOOGLE ANTIGRAVITY CLI (`agy`) SETUP WALKTHROUGH ! ]"
                ),
                fg=str(t["success"]) if self.status.installed else str(t["warning"]),
            )
            info_lbl.configure(text=self._build_walkthrough_text())
            status_bar.configure(text=msg or self.status.status_message)
            btn_install.configure(
                text="↻ UPDATE AGY CLI" if self.status.installed else "⬇ AUTO-INSTALL AGY CLI"
            )

        def do_redetect() -> None:
            _refresh_ui()
            parent.notify(
                f"AGY CLI {'DETECTED v' + (self.status.version or '') if self.status.installed else 'NOT FOUND'}"
            )

        def do_copy_cmd() -> None:
            dlg.clipboard_clear()
            dlg.clipboard_append(self.status.install_command)
            status_bar.configure(text=f"✓ Copied install command to clipboard: {self.status.install_command}")
            parent.notify("COPIED AGY INSTALL COMMAND TO CLIPBOARD")

        def do_install_or_update() -> None:
            btn_install.configure(state=tk.DISABLED, text="⏳ WORKING...")
            status_bar.configure(text="Running official Antigravity CLI installer/updater... please wait.")

            def _worker() -> None:
                if self.status.installed:
                    ok, msg = self.connector.update_cli()
                else:
                    ok, msg = self.connector.install_cli(
                        progress_callback=lambda m: parent.root.after(
                            0, lambda line=m: status_bar.configure(text=line) if dlg.winfo_exists() else None
                        )
                    )

                def _done() -> None:
                    parent._write_log(f"{'✓' if ok else '✗'} Antigravity CLI: {msg}")
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
            ok, msg = self.connector.launch_interactive_terminal()
            status_bar.configure(text=msg)
            parent._write_log(f"{'✓' if ok else 'ℹ'} {msg}")

        def do_link_mcp() -> None:
            ok, msg = self.connector.register_c64u_mcp(
                host=parent.client.host,
                port=parent.client.port,
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

        btn_install = tk.Button(
            btn_row,
            text="↻ UPDATE AGY CLI" if self.status.installed else "⬇ AUTO-INSTALL AGY CLI",
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
    """Retro C64 Project File Browser Modal supporting game_dev/, examples/, and workspace files."""

    def __init__(self, initial_path: Optional[Path] = None):
        self.current_root = initial_path or Path.cwd()
        self.selected_file: Optional[Path] = None
        self.tree_helper = FilteredDirectoryTree(self.current_root)

    def show_tk(self, parent: "C64PythonToAsmApp", callback: Callable[[Optional[Path]], None]) -> tk.Toplevel:
        t = THEMES[parent.current_theme]
        font_fam = str(t["font_family"])
        dlg = tk.Toplevel(parent.root)
        parent._apply_application_icon(dlg)
        dlg.title('LOAD "$",8 // C64 PROJECT FILE BROWSER')
        dlg.geometry("880x560")
        dlg.configure(bg=str(t["paper"]), highlightthickness=6, highlightbackground=str(t["border_idle"]))
        dlg.transient(parent.root)

        tk.Label(
            dlg,
            text="[ COMMODORE 64 PROJECT FILE & DISK BROWSER ]",
            font=(font_fam, 11, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["accent"]),
            pady=8,
        ).pack(fill=tk.X, padx=14, pady=(12, 6))

        jump_bar = tk.Frame(dlg, bg=str(t["paper"]))
        jump_bar.pack(fill=tk.X, padx=14, pady=4)

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

        sb = tk.Scrollbar(list_frame, command=lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb.config(yscrollcommand=sb.set)

        lbl_preview = tk.Label(
            dlg,
            text="SELECT .ASM, .PY, .SID, .PRG, .TAP, OR .D64 FILE TO OPEN",
            font=(font_fam, 8, "bold"),
            bg=str(t["panel_bg"]),
            fg=str(t["success"]),
            pady=5,
        )
        lbl_preview.pack(fill=tk.X, padx=14, pady=4)

        def populate(folder: Path):
            if not folder.exists() or not folder.is_dir():
                return
            self.current_root = folder.resolve()
            lbl_dir.configure(text=f'DRIVE 8 PATH: "{self.current_root}"')
            lb.delete(0, tk.END)
            entries_map.clear()

            if self.current_root.parent != self.current_root:
                entries_map.append(self.current_root.parent)
                lb.insert(tk.END, "📁 [..] (PARENT DIRECTORY)")

            try:
                raw_children = sorted(
                    self.current_root.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
                filtered = self.tree_helper.filter_paths(raw_children)
                for p in filtered:
                    entries_map.append(p)
                    if p.is_dir():
                        lb.insert(tk.END, f"📁 [{p.name.upper()}/]")
                    else:
                        sz = p.stat().st_size
                        blocks = max(1, (sz + 253) // 254)
                        ext_tag = p.suffix.upper().lstrip(".") or "FILE"
                        lb.insert(tk.END, f'{blocks:<4d} "{p.name:<28}" {ext_tag:<5} ({sz} BYTES)')
            except OSError:
                pass

        def on_select(_event=None):
            sel = lb.curselection()
            if not sel:
                return
            p = entries_map[sel[0]]
            if p.is_file():
                self.selected_file = p
                lbl_preview.configure(text=f"SELECTED: {p.name} ({p.stat().st_size} BYTES)")
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
                title="Select Commodore 64 Source, SID, Disk, Tape, or PRG File",
                filetypes=[
                    ("All C64 Studio Files", "*.asm *.s *.py *.sid *.prg *.tap *.d64 *.bin"),
                    ("6502 Assembly (.asm, .s)", "*.asm *.s"),
                    ("Python 6502 Dialect (.py)", "*.py"),
                    ("C64 Disk / Tape / PRG (.d64, .tap, .prg)", "*.d64 *.tap *.prg"),
                    ("SID Music (.sid)", "*.sid"),
                    ("All Files", "*.*"),
                ],
            )
            if chosen:
                if dlg.winfo_exists():
                    dlg.destroy()
                callback(Path(chosen))

        for label, target in (
            ("📂 GAME_DEV/", Path.cwd() / "game_dev"),
            ("📂 EXAMPLE_GAMES/", Path.cwd() / "example_games"),
            ("📂 EXAMPLES/", Path.cwd() / "examples"),
            ("📂 WORKSPACE ROOT", Path.cwd()),
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
            text="🖥 OS FILE DIALOG...",
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

        tk.Button(
            btn_row,
            text="LOAD SELECTED (ENTER)",
            command=on_activate,
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
            text="CANCEL (ESC)",
            command=lambda: (dlg.destroy(), callback(None)),
            font=(font_fam, 9, "bold"),
            bg=str(t["danger"]),
            fg="#FFFFFF",
            relief=tk.FLAT,
            padx=14,
            pady=6,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

        populate(self.current_root if self.current_root.exists() else Path.cwd())
        center_popup(dlg)
        try:
            dlg.grab_set()
            lb.focus_set()
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
        self.validator = DeploymentValidator()
        self.agy = AgyCliConnector(agy_bin=kwargs.get("agy_bin"), workspace_dir=Path.cwd())
        self.agy_status: AgyStatus = AgyStatus(
            installed=False,
            install_command=INSTALL_CMD_WINDOWS_PS1 if os.name == "nt" else INSTALL_CMD_UNIX,
            status_message="Checking Antigravity CLI...",
        )
        self.last_validation_report: Optional[DeploymentValidationReport] = None
        self.last_agy_result: Optional[AgyPromptResult] = None
        self.last_agy_code_block: Optional[ExtractedCodeBlock] = None
        self._last_agy_modal: Optional[AgySetupModal] = None
        self._agy_busy: bool = False

        self.current_theme = "Commodore 64"
        self.last_asm: str = ""
        self.last_prg_path: Optional[Path] = None
        self.last_sid_path: Optional[Path] = None
        self.loaded_file: Optional[Path] = None
        self.file_mode: str = "py"  # "py", "c", "asm", or "def" for a build.py or game definition
        self.file_kind: str = ""    # see project.classify_file; "" until something is loaded
        self.binary_source: Optional[Path] = None   # the .prg behind a disassembly
        self.stage: int = 0         # how far along the sequence: 1 loaded, 2 built, 3 running
        self.asm_focus_mode: bool = False
        self.is_fullscreen: bool = False

        # Animation & Boot state
        self._anim_tick: int = 0
        self._border_busy: bool = False
        self._busy_phase: str = "READY"
        self._busy_progress: float = 1.0
        self._boot_active: bool = not skip_boot
        self._boot_step: int = 0
        self._boot_lines: list[str] = []
        self._window_icon_handles: list[int] = []
        self._native_icon_window_ids: set[int] = set()
        self._c64_badge_img: Optional[ImageTk.PhotoImage] = None
        self._cassette_badge_img: Optional[ImageTk.PhotoImage] = None
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

        if self._boot_active:
            self._start_boot_sequence()
        else:
            self._finish_boot_sequence()

        self._tick_animation()

    # -----------------------------------------------------------------------
    # UI Construction (Modeled on BackMeUpScotty C64 CRT & Border Canvas)
    # -----------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Outer VIC-II Border Canvas (Light Blue #70A4B2 in idle, Raster Bars during load/DMA)
        self.border_canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.border_canvas.pack(fill=tk.BOTH, expand=True)

        # Inner CRT Screen Frame (Dark Blue #352879)
        self.screen_frame = tk.Frame(self.border_canvas, bd=0, highlightthickness=2)
        self.screen_window_id = self.border_canvas.create_window(
            26, 26, anchor="nw", window=self.screen_frame
        )
        self.border_canvas.bind("<Configure>", self._on_border_resize)

        # Boot Overlay Canvas (covers screen_frame during authentic C64 startup sequence)
        self.boot_canvas = tk.Canvas(self.screen_frame, highlightthickness=0, bd=0)
        self.boot_canvas.bind("<Button-1>", lambda _e: self._finish_boot_sequence())

        # Main Studio Container inside screen_frame
        self.studio_frame = tk.Frame(self.screen_frame, bd=0)
        self.studio_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Top Header Bar: C64 Badge + Boot Banner + View Mode + Theme Switcher
        self.top_bar = tk.Frame(self.studio_frame)
        self.top_bar.pack(fill=tk.X, padx=12, pady=(8, 4))

        self.c64_logo_lbl = tk.Label(self.top_bar, bd=0)
        self.c64_logo_lbl.pack(side=tk.LEFT, padx=(0, 8))

        self.header_right = tk.Frame(self.top_bar)
        self.header_right.pack(side=tk.RIGHT)

        self.banner_label = tk.Label(self.top_bar, text="", justify=tk.LEFT, anchor="w")
        self.banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.lang_buttons: dict[str, tk.Button] = {}
        for lang_code, lang_lbl in (
            ("asm", "ASM"),
            ("c", "C/OSCAR"),
            ("py", "PYTHON"),
        ):
            lb = tk.Button(
                self.header_right,
                text=lang_lbl,
                command=lambda lc=lang_code: self.action_select_language(lc),
                relief=tk.FLAT,
                padx=5,
                pady=3,
                cursor="hand2",
            )
            lb.pack(side=tk.LEFT, padx=2)
            self.lang_buttons[lang_code] = lb

        self.btn_agy_status = tk.Button(
            self.header_right,
            text="● AGY: CHECK",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=6,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_status.pack(side=tk.LEFT, padx=2)

        self.btn_asm_focus = tk.Button(
            self.header_right,
            text="★ 6502 (^E)",
            command=self.action_toggle_asm_focus,
            relief=tk.FLAT,
            padx=5,
            pady=3,
            cursor="hand2",
        )
        self.btn_asm_focus.pack(side=tk.LEFT, padx=2)

        self.btn_fullscreen = tk.Button(
            self.header_right,
            text="⛶ F11",
            command=self.action_toggle_fullscreen,
            relief=tk.FLAT,
            padx=5,
            pady=3,
            cursor="hand2",
        )
        self.btn_fullscreen.pack(side=tk.LEFT, padx=2)

        self.theme_buttons: dict[str, tk.Button] = {}
        for t_name, t_short in (("Commodore 64", "C64 BLUE"), ("C64 Phosphor", "PHOSPHOR")):
            btn = tk.Button(
                self.header_right,
                text=t_short,
                command=lambda n=t_name: self.apply_theme(n),
                relief=tk.FLAT,
                padx=5,
                pady=3,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.theme_buttons[t_name] = btn

        # 2. C64 Rainbow Color Divider Strip
        self.divider_canvas = tk.Canvas(self.studio_frame, height=7, highlightthickness=0, bd=0)
        self.divider_canvas.pack(fill=tk.X, padx=12, pady=(0, 6))

        # 3. 5-Column On-Screen C64 Menu & Command Deck
        self.menu_bar = tk.Frame(self.studio_frame, highlightthickness=1)
        self.menu_bar.pack(fill=tk.X, padx=12, pady=(0, 6))
        for col_i in range(5):
            self.menu_bar.columnconfigure(col_i, weight=1, uniform="menu_col")

        self.menu_buttons: dict[str, tk.Button] = {}
        self.menu_columns: dict[str, list[str]] = {
            "file": [],
            "build": [],
            "device": [],
            "gamedev": [],
            "help": [],
        }

        menu_spec = [
            (
                0,
                "file",
                "col-file",
                "menu-btn-file",
                "10 FILE & TAPE",
                self.action_open_file,
                [
                    ("btn-open", "LOAD FILE     [F3]", self.action_open_file),
                    ("btn-new-asm", "NEW .ASM      [^N]", self.action_new_asm_template),
                    ("btn-save", "SAVE FILE    [⇧F1]", self.action_save_file),
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
                "20 BUILD & RUN",
                self.action_run_c64u,
                [
                    ("quick-btn-run", "▶ BUILD + RUN [F5]", self.action_run_c64u),
                    ("btn-build", "BUILD         [F7]", self.action_build),
                    ("btn-load-prg", "DMA LOAD RAM [⇧F3]", self.action_load_prg_only),
                    ("btn-sprite-studio", "SPRITE EDIT [⇧F10]", self.action_open_sprite_studio),
                    ("btn-validation-rep", "VALID REPRT [⇧F11]", self.action_validation_report),
                ],
            ),
            (
                2,
                "device",
                "col-device",
                "menu-btn-device",
                "30 C64U DEVICE",
                self.action_refresh_connection,
                [
                    ("btn-refresh", "PING C64U     [F4]", self.action_refresh_connection),
                    ("quick-btn-reset", "SOFT RESET    [F8]", self.action_reset_c64u),
                    ("btn-pause-cpu", "PAUSE 6510   [⇧F4]", self.action_pause_cpu),
                    ("btn-resume-cpu", "RESUME 6510  [⇧F5]", self.action_resume_cpu),
                    ("btn-screen-dump", "SCREEN DUMP  [⇧F6]", self.action_dump_screen),
                    ("btn-c64u-reboot", "COLD REBOOT  [⇧F7]", self.action_reboot_c64u),
                    ("btn-play-sid", "PLAY SID      [^P]", self.action_play_sid),
                ],
            ),
            (
                3,
                "gamedev",
                "col-gamedev",
                "menu-btn-gamedev",
                "40 GAME DEV",
                self.action_new_game,
                [
                    ("btn-gd-game", "GAME PROJECT [NEW]", self.action_new_game),
                    ("btn-gd-build", "BUILD.PY     [NEW]", self.action_new_build_file),
                    ("btn-gd-sprites", "SPRITE BANK  [NEW]", lambda: self.action_new_definition("sprites")),
                    ("btn-gd-tileset", "TILES + MAP  [NEW]", lambda: self.action_new_definition("tileset")),
                    ("btn-gd-koala", "TITLE SCREEN [NEW]", lambda: self.action_new_definition("koala")),
                    ("btn-gd-song", "SID SONG     [NEW]", lambda: self.action_new_definition("song")),
                    ("btn-gd-levels", "LEVELS       [NEW]", lambda: self.action_new_definition("levels")),
                    ("btn-gd-c64sim", "C64 SCREEN   [SIM]", self.action_gamedev_c64sim),
                    ("btn-gd-sim", "SID PROFILE  [SIM]", self.action_gamedev_sim),
                ],
            ),
            (
                4,
                "help",
                "col-help",
                "menu-btn-help",
                "50 HELP & INFO",
                self.action_show_help,
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

        for col_idx, cat_key, col_id, hdr_id, hdr_title, hdr_cmd, items in menu_spec:
            col_f = tk.Frame(self.menu_bar, padx=2, pady=2, highlightthickness=1)
            col_f.grid(row=0, column=col_idx, sticky="nsew")
            self.col_frames[col_id] = col_f

            hdr_btn = tk.Button(
                col_f,
                text=hdr_title,
                command=hdr_cmd,
                relief=tk.FLAT,
                pady=2,
                cursor="hand2",
            )
            hdr_btn.pack(fill=tk.X, pady=(0, 2))
            self.col_headers[hdr_id] = hdr_btn
            self.menu_buttons[hdr_id] = hdr_btn

            for item_id, item_text, item_cmd in items:
                b = tk.Button(
                    col_f,
                    text=item_text,
                    command=lambda cid=item_id, fn=item_cmd: self._invoke_menu_btn(cid, fn),
                    relief=tk.FLAT,
                    anchor="w",
                    padx=6,
                    pady=1,
                    cursor="hand2",
                )
                b.pack(fill=tk.X, pady=1)
                b.bind("<FocusIn>", lambda _e, cid=item_id: self._on_btn_focus(cid))
                self.menu_buttons[item_id] = b
                self.menu_columns[cat_key].append(item_id)

            if cat_key == "help":
                self.bridge_status_lbl = tk.Label(
                    col_f,
                    text="● C64U: CHECKING...",
                    anchor="center",
                    pady=3,
                )
                self.bridge_status_lbl.pack(fill=tk.X, side=tk.BOTTOM, pady=(2, 0))

        # 4. Main Workspace Split Area (Left Column: Python + ASM Label Navigator | Right Column: 6502 ASM IDE & Tabs)
        self.workspace_frame = tk.Frame(self.studio_frame)
        self.workspace_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)
        self.workspace_frame.columnconfigure(0, weight=5)
        self.workspace_frame.columnconfigure(1, weight=7)
        self.workspace_frame.rowconfigure(0, weight=1)

        # --- LEFT COLUMN: Python 6502 Dialect Editor + ASM Label Outline ---
        self.left_pane = tk.Frame(self.workspace_frame, highlightthickness=1, padx=6, pady=6)
        self.left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.left_hdr_bar = tk.Frame(self.left_pane)
        self.left_hdr_bar.pack(fill=tk.X, pady=(0, 4))

        self.btn_py_to_asm = tk.Button(
            self.left_hdr_bar,
            text="PY → ASM (F6)",
            command=self._on_left_build_clicked,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_py_to_asm.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_new_py = tk.Button(
            self.left_hdr_bar,
            text="+ .PY",
            command=self.action_new_py_template,
            relief=tk.FLAT,
            padx=5,
            pady=2,
            cursor="hand2",
        )
        self.btn_new_py.pack(side=tk.RIGHT, padx=2)

        self.btn_new_c = tk.Button(
            self.left_hdr_bar,
            text="+ .C",
            command=self.action_new_c_template,
            relief=tk.FLAT,
            padx=5,
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

        # Python Editor with Line Number Gutter
        self.py_editor_container = tk.Frame(self.left_pane, highlightthickness=1)
        self.py_editor_container.pack(fill=tk.BOTH, expand=True)

        self.py_gutter = tk.Text(
            self.py_editor_container,
            width=4,
            padx=4,
            pady=6,
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
            padx=8,
            pady=6,
            highlightthickness=0,
            insertwidth=8,
        )
        self.py_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.py_text.config(yscrollcommand=self._on_py_scroll)
        self.py_scroll.config(command=self._yview_py_both)
        self.py_text.bind("<KeyRelease>", self._on_py_changed)
        self.py_text.bind("<ButtonRelease-1>", self._on_py_changed)

        # Quick 6502 Label & Subroutine Outline Box at bottom of Left Pane
        self.label_nav_frame = tk.Frame(self.left_pane, highlightthickness=1)
        self.label_nav_frame.pack(fill=tk.X, pady=(6, 0))

        self.label_nav_hdr = tk.Label(
            self.label_nav_frame,
            text="6502 ASM LABELS & SUBROUTINES (CLICK TO JUMP):",
            anchor="w",
        )
        self.label_nav_hdr.pack(fill=tk.X)

        nav_list_wrap = tk.Frame(self.label_nav_frame)
        nav_list_wrap.pack(fill=tk.BOTH, expand=True)

        self.label_listbox = tk.Listbox(
            nav_list_wrap,
            height=5,
            relief=tk.FLAT,
            highlightthickness=0,
            activestyle="none",
        )
        self.label_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.label_listbox.bind("<<ListboxSelect>>", self._on_label_nav_selected)

        self.label_scroll = tk.Scrollbar(nav_list_wrap, command=self.label_listbox.yview)
        self.label_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.label_listbox.config(yscrollcommand=self.label_scroll.set)
        self._label_line_map: list[int] = []

        # --- RIGHT COLUMN: Primary 6502 Assembly Editor, Build Log, AST, Hardware ---
        self.right_pane = tk.Frame(self.workspace_frame, highlightthickness=1, padx=6, pady=6)
        self.right_pane.grid(row=0, column=1, sticky="nsew")

        # Tab Selector Strip + ASM Toolbar
        self.tab_bar = tk.Frame(self.right_pane)
        self.tab_bar.pack(fill=tk.X, pady=(0, 4))

        self.tab_buttons: dict[str, tk.Button] = {}
        for tab_id, tab_title in (
            ("tab-asm", "1:ASM"),
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
                padx=6,
                pady=3,
                cursor="hand2",
            )
            tb.pack(side=tk.LEFT, padx=(0, 3))
            self.tab_buttons[tab_id] = tb

        self.mode_badge_lbl = tk.Label(
            self.tab_bar,
            text="[MODE: PYTHON → 6502]",
            anchor="e",
        )
        self.mode_badge_lbl.pack(side=tk.RIGHT, padx=4)

        # Tab Stack Container
        self.tab_stack = tk.Frame(self.right_pane)
        self.tab_stack.pack(fill=tk.BOTH, expand=True)

        # --- TAB 1: 6502 ASSEMBLY EDITOR (.ASM) ---
        self.pane_asm = tk.Frame(self.tab_stack)

        # ASM Editor Power Toolbar (New ASM, Save, Comment, Find/Goto, Cursor Line/Col)
        self.asm_toolbar = tk.Frame(self.pane_asm, pady=2)
        self.asm_toolbar.pack(fill=tk.X, pady=(0, 4))

        self.btn_asm_comment = tk.Button(
            self.asm_toolbar,
            text="// COMMENT (^/)",
            command=self.action_toggle_asm_comment,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_asm_comment.pack(side=tk.LEFT, padx=(0, 8))

        self.find_lbl = tk.Label(self.asm_toolbar, text="FIND/LINE:")
        self.find_lbl.pack(side=tk.LEFT, padx=(0, 4))

        self.find_var = tk.StringVar()
        self.find_entry = tk.Entry(
            self.asm_toolbar,
            textvariable=self.find_var,
            width=16,
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
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_find_go.pack(side=tk.LEFT, padx=(0, 6))

        self.asm_cursor_lbl = tk.Label(
            self.asm_toolbar,
            text="LN 1, COL 1",
            anchor="e",
        )
        self.asm_cursor_lbl.pack(side=tk.RIGHT, padx=4)

        # ASM Editor with Line Number Gutter
        self.asm_editor_container = tk.Frame(self.pane_asm, highlightthickness=1)
        self.asm_editor_container.pack(fill=tk.BOTH, expand=True)

        self.asm_gutter = tk.Text(
            self.asm_editor_container,
            width=5,
            padx=4,
            pady=6,
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
            padx=8,
            pady=6,
            highlightthickness=0,
            insertwidth=8,
        )
        self.asm_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.asm_text.config(yscrollcommand=self._on_asm_scroll)
        self.asm_scroll.config(command=self._yview_asm_both)
        self.asm_text.bind("<KeyRelease>", self._on_asm_changed)
        self.asm_text.bind("<ButtonRelease-1>", self._on_asm_cursor_move)
        self.asm_text.bind("<Control-slash>", lambda _e: self.action_toggle_asm_comment())
        self.asm_text.bind("<Return>", self._on_asm_return_autoindent)

        # --- TAB 2: BUILD & DMA LOG ---
        self.pane_log = tk.Frame(self.tab_stack)
        log_bar = tk.Frame(self.pane_log)
        log_bar.pack(fill=tk.X, pady=(0, 4))

        self.btn_clear_log = tk.Button(
            log_bar,
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

        self.log_scroll = tk.Scrollbar(log_wrap)
        self.log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_text = tk.Text(
            log_wrap,
            wrap="word",
            bd=0,
            padx=8,
            pady=6,
            highlightthickness=0,
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text.config(yscrollcommand=self.log_scroll.set)
        self.log_scroll.config(command=self.log_text.yview)

        # --- TAB 3: AST & SYMBOLS ---
        self.pane_ast = tk.Frame(self.tab_stack)
        ast_wrap = tk.Frame(self.pane_ast, highlightthickness=1)
        ast_wrap.pack(fill=tk.BOTH, expand=True)

        self.ast_scroll = tk.Scrollbar(ast_wrap)
        self.ast_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.ast_listbox = tk.Listbox(
            ast_wrap,
            bd=0,
            highlightthickness=0,
            activestyle="none",
        )
        self.ast_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.ast_listbox.config(yscrollcommand=self.ast_scroll.set)
        self.ast_scroll.config(command=self.ast_listbox.yview)

        # --- TAB 4: C64U HARDWARE & MEMORY CONSOLE ---
        self.pane_hw = tk.Frame(self.tab_stack, padx=8, pady=8)

        self.hw_card_actions = tk.Frame(self.pane_hw, padx=10, pady=8, highlightthickness=1)
        self.hw_card_actions.pack(fill=tk.X, pady=(0, 8))

        self.hw_lbl_title = tk.Label(
            self.hw_card_actions,
            text="ULTIMATE 64 / C64U DMA HARDWARE CONTROLS",
            anchor="w",
        )
        self.hw_lbl_title.pack(fill=tk.X, pady=(0, 6))

        hw_btn_row1 = tk.Frame(self.hw_card_actions)
        hw_btn_row1.pack(fill=tk.X, pady=3)
        self.hw_buttons: dict[str, tk.Button] = {}
        for bid, btxt, bcmd in (
            ("hw-run-prg", "▶ DMA RUN PRG", self.action_run_c64u),
            ("hw-load-prg", "📥 DMA LOAD PRG", self.action_load_prg_only),
            ("hw-reset", "🔁 SOFT RESET", self.action_reset_c64u),
            ("hw-reboot", "💥 COLD REBOOT", self.action_reboot_c64u),
            ("hw-pause", "⏸ PAUSE 6510", self.action_pause_cpu),
            ("hw-resume", "▶ RESUME 6510", self.action_resume_cpu),
        ):
            b = tk.Button(
                hw_btn_row1,
                text=btxt,
                command=bcmd,
                relief=tk.FLAT,
                padx=8,
                pady=4,
                cursor="hand2",
            )
            b.pack(side=tk.LEFT, padx=(0, 6))
            self.hw_buttons[bid] = b

        self.hw_card_mem = tk.Frame(self.pane_hw, padx=10, pady=8, highlightthickness=1)
        self.hw_card_mem.pack(fill=tk.X, pady=(0, 8))

        self.hw_lbl_mem = tk.Label(
            self.hw_card_mem,
            text="DIRECT MEMORY PEEK / POKE & KEYSTROKE INJECTION",
            anchor="w",
        )
        self.hw_lbl_mem.pack(fill=tk.X, pady=(0, 6))

        poke_row = tk.Frame(self.hw_card_mem)
        poke_row.pack(fill=tk.X, pady=3)

        self.lbl_addr = tk.Label(poke_row, text="ADDR:")
        self.lbl_addr.pack(side=tk.LEFT, padx=(0, 4))
        self.inp_addr_var = tk.StringVar(value="$D020")
        self.inp_addr_entry = tk.Entry(poke_row, textvariable=self.inp_addr_var, width=10, relief=tk.FLAT, highlightthickness=1)
        self.inp_addr_entry.pack(side=tk.LEFT, padx=(0, 10), ipady=3)

        self.lbl_val = tk.Label(poke_row, text="VAL:")
        self.lbl_val.pack(side=tk.LEFT, padx=(0, 4))
        self.inp_val_var = tk.StringVar(value="$01")
        self.inp_val_entry = tk.Entry(poke_row, textvariable=self.inp_val_var, width=8, relief=tk.FLAT, highlightthickness=1)
        self.inp_val_entry.pack(side=tk.LEFT, padx=(0, 10), ipady=3)

        for bid, btxt, bcmd in (
            ("hw-poke", "POKE MEMORY", self._handle_hw_poke),
            ("hw-peek", "PEEK MEMORY", self._handle_hw_peek),
            ("hw-dump", "INSPECT SCREEN ($0400)", self.action_dump_screen),
            ("hw-validate", "📋 VALIDATION REPORT", self.action_validation_report),
        ):
            b = tk.Button(poke_row, text=btxt, command=bcmd, relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
            b.pack(side=tk.LEFT, padx=(0, 6))
            self.hw_buttons[bid] = b

        key_row = tk.Frame(self.hw_card_mem)
        key_row.pack(fill=tk.X, pady=(8, 3))
        self.lbl_keys = tk.Label(key_row, text="SEND KEYS:")
        self.lbl_keys.pack(side=tk.LEFT, padx=(0, 4))
        self.inp_keys_var = tk.StringVar(value='PRINT "HELLO C64U"\r')
        self.inp_keys_entry = tk.Entry(key_row, textvariable=self.inp_keys_var, width=32, relief=tk.FLAT, highlightthickness=1)
        self.inp_keys_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=3)
        b_send = tk.Button(key_row, text="INJECT KEYS TO C64", command=self._handle_send_keys, relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
        b_send.pack(side=tk.LEFT)
        self.hw_buttons["hw-send-keys"] = b_send

        # --- TAB 5: ANTIGRAVITY AI CLI CONSOLE ---
        self.pane_agy = tk.Frame(self.tab_stack, padx=4, pady=4)

        self.agy_top_bar = tk.Frame(self.pane_agy, padx=6, pady=4, highlightthickness=1)
        self.agy_top_bar.pack(fill=tk.X, pady=(0, 4))

        self.agy_lbl_lang = tk.Label(self.agy_top_bar, text="TARGET:")
        self.agy_lbl_lang.pack(side=tk.LEFT, padx=(0, 4))

        self.agy_lang_var = tk.StringVar(value="py")
        self.agy_lang_menu = tk.OptionMenu(self.agy_top_bar, self.agy_lang_var, "asm", "c", "py")
        self.agy_lang_menu.config(relief=tk.FLAT, highlightthickness=1, padx=4, pady=1)
        self.agy_lang_menu.pack(side=tk.LEFT, padx=(0, 8))

        self.agy_lbl_mode = tk.Label(self.agy_top_bar, text="MODE:")
        self.agy_lbl_mode.pack(side=tk.LEFT, padx=(0, 4))

        self.agy_mode_var = tk.StringVar(value="accept-edits")
        self.agy_mode_menu = tk.OptionMenu(
            self.agy_top_bar, self.agy_mode_var, "accept-edits", "plan", "auto"
        )
        self.agy_mode_menu.config(relief=tk.FLAT, highlightthickness=1, padx=4, pady=1)
        self.agy_mode_menu.pack(side=tk.LEFT, padx=(0, 8))

        self.agy_include_ctx_var = tk.BooleanVar(value=True)
        self.agy_chk_ctx = tk.Checkbutton(
            self.agy_top_bar,
            text="CTX",
            variable=self.agy_include_ctx_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_ctx.pack(side=tk.LEFT, padx=2)

        self.agy_continue_var = tk.BooleanVar(value=False)
        self.agy_chk_cont = tk.Checkbutton(
            self.agy_top_bar,
            text="CONT (-c)",
            variable=self.agy_continue_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_cont.pack(side=tk.LEFT, padx=(2, 6))

        self.agy_auto_apply_var = tk.BooleanVar(value=True)
        self.agy_chk_apply = tk.Checkbutton(
            self.agy_top_bar,
            text="AUTO-APPLY",
            variable=self.agy_auto_apply_var,
            relief=tk.FLAT,
            highlightthickness=0,
        )
        self.agy_chk_apply.pack(side=tk.LEFT, padx=2)

        self.btn_agy_setup_tab = tk.Button(
            self.agy_top_bar,
            text="⚙ AGY SETUP",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_agy_setup_tab.pack(side=tk.RIGHT, padx=2)

        self.btn_agy_clear = tk.Button(
            self.agy_top_bar,
            text="CLEAR",
            command=self._clear_agy_chat,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_agy_clear.pack(side=tk.RIGHT, padx=2)

        agy_chat_wrap = tk.Frame(self.pane_agy, highlightthickness=1)
        agy_chat_wrap.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.agy_chat_wrap = agy_chat_wrap

        self.agy_chat_scroll = tk.Scrollbar(agy_chat_wrap)
        self.agy_chat_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.agy_chat_text = tk.Text(
            agy_chat_wrap,
            wrap="word",
            bd=0,
            padx=8,
            pady=6,
            highlightthickness=0,
        )
        self.agy_chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.agy_chat_text.config(yscrollcommand=self.agy_chat_scroll.set)
        self.agy_chat_scroll.config(command=self.agy_chat_text.yview)

        self.agy_action_bar = tk.Frame(self.pane_agy)
        self.agy_action_bar.pack(fill=tk.X)

        self.btn_agy_apply = tk.Button(
            self.agy_action_bar,
            text="📥 APPLY LAST CODE TO IDE",
            command=self.action_apply_last_agy_code,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_apply.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_agy_apply_run = tk.Button(
            self.agy_action_bar,
            text="⚡ APPLY & DMA RUN [F5]",
            command=self.action_apply_and_run_agy_code,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_apply_run.pack(side=tk.LEFT, padx=(0, 6))

        # 5. Always-Accessible Antigravity CLI Prompt Bar (across bottom of C64 Studio)
        self.agy_quick_bar = tk.Frame(self.studio_frame, padx=8, pady=4, highlightthickness=1)
        self.agy_quick_bar.pack(fill=tk.X, padx=12, pady=(2, 2))

        self.lbl_agy_prompt = tk.Label(
            self.agy_quick_bar,
            text="AGY AI PROMPT [⇧F12]:",
            anchor="w",
        )
        self.lbl_agy_prompt.pack(side=tk.LEFT, padx=(0, 6))

        self.agy_prompt_var = tk.StringVar()
        self.agy_prompt_entry = tk.Entry(
            self.agy_quick_bar,
            textvariable=self.agy_prompt_var,
            relief=tk.FLAT,
            highlightthickness=1,
        )
        self.agy_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=3)
        self.agy_prompt_entry.bind("<Return>", lambda _e: self.action_send_agy_prompt())

        self.btn_agy_send = tk.Button(
            self.agy_quick_bar,
            text="▶ ASK ANTIGRAVITY",
            command=self.action_send_agy_prompt,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_send.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_agy_quick_setup = tk.Button(
            self.agy_quick_bar,
            text="⚙ CLI SETUP",
            command=self.action_open_agy_setup,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_agy_quick_setup.pack(side=tk.LEFT)

        # 6. Bottom Retro DMA & Tape Transfer Deck (Modeled on BackMeUpScotty)
        self.deck_frame = tk.Frame(self.studio_frame, padx=8, pady=4, highlightthickness=1)
        self.deck_frame.pack(fill=tk.X, padx=12, pady=(2, 8))

        self.deck_canvas = tk.Canvas(self.deck_frame, height=54, highlightthickness=0, bd=0)
        self.deck_canvas.pack(fill=tk.X)
        self.deck_canvas.bind("<Configure>", lambda _e: self.root.after_idle(self._draw_bottom_deck))

        self.status_row = tk.Frame(self.deck_frame)
        self.status_row.pack(fill=tk.X, pady=(2, 0))

        self.prompt_lbl = tk.Label(self.status_row, text="READY. █", anchor="w")
        self.prompt_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.credits_hint_lbl = tk.Label(
            self.status_row,
            text="[F3: LOAD | F7: BUILD | F5: RUN | F12: HYPERLOAD | ⇧F12: AGY AI]",
            anchor="e",
        )
        self.credits_hint_lbl.pack(side=tk.RIGHT)

        # Dock bottom bars with side=BOTTOM BEFORE workspace_frame expands so they never clip at high DPI
        self.workspace_frame.pack_forget()
        self.agy_quick_bar.pack_forget()
        self.deck_frame.pack_forget()
        self.deck_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(2, 6))
        self.agy_quick_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(2, 2))
        self.workspace_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=2)

        self.switch_tab("tab-asm")

    # -----------------------------------------------------------------------
    # Authentic C64 Boot & LOAD "C64-BRIDGE",8,1 Sequence
    # -----------------------------------------------------------------------

    def _start_boot_sequence(self) -> None:
        """Run the authentic C64 BASIC V2 startup and LOAD \"C64-BRIDGE\",8,1 sequence."""
        self._boot_active = True
        self._boot_waiting_for_key = False
        self._boot_step = 0
        self._border_busy = False
        self.studio_frame.pack_forget()
        self.boot_canvas.pack(fill=tk.BOTH, expand=True)
        self._render_boot_screen()
        self.root.after(700, self._advance_boot_sequence)

    def _advance_boot_sequence(self) -> None:
        if not self._boot_active or not self.root.winfo_exists():
            return
        self._boot_step += 1

        # Step 1..6: Typing LOAD "C64-BRIDGE",8,1
        cmd = 'LOAD "C64-BRIDGE",8,1'
        if self._boot_step <= 6:
            typed_len = min(len(cmd), self._boot_step * 4)
            self._boot_lines = [
                "    **** COMMODORE 64 BASIC V2 ****",
                "",
                " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
                "",
                "READY.",
                cmd[:typed_len],
            ]
            self._render_boot_screen()
            self.root.after(260, self._advance_boot_sequence)
            return

        # Step 7: SEARCHING FOR C64-BRIDGE / LOADING
        if self._boot_step == 7:
            self._boot_lines = [
                "    **** COMMODORE 64 BASIC V2 ****",
                "",
                " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
                "",
                "READY.",
                'LOAD "C64-BRIDGE",8,1',
                "",
                "SEARCHING FOR C64-BRIDGE",
                "LOADING",
            ]
            self._border_busy = True
            self._render_boot_screen()
            self._draw_border_and_divider()
            self.root.after(900, self._advance_boot_sequence)
            return

        # Steps 8..11: Loading lines + VIC-II fast-loader raster border
        loading_stages = [
            "LOADING FROM DRIVE 8 (ULTIMATE-II+ DMA): $0801-$1F40 6502 ASSEMBLER",
            "LOADING FROM DRIVE 8 (ULTIMATE-II+ DMA): $2000-$3FFF PYTHON TRANSPILER",
            "LOADING FROM DRIVE 8 (ULTIMATE-II+ DMA): $4000-$5FFF D64/TAP/SID ENGINE",
            "LOADING FROM DRIVE 8 (ULTIMATE-II+ DMA): $C000-$DFFF C64U HARDWARE BRIDGE",
        ]
        if 8 <= self._boot_step <= 11:
            stage_idx = self._boot_step - 8
            self._boot_lines = [
                "    **** COMMODORE 64 BASIC V2 ****",
                "",
                " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
                "",
                "READY.",
                'LOAD "C64-BRIDGE",8,1',
                "",
                "SEARCHING FOR C64-BRIDGE",
                "LOADING",
            ] + loading_stages[: stage_idx + 1]
            self._border_busy = True
            self._render_boot_screen()
            self._draw_border_and_divider()
            self.root.after(700, self._advance_boot_sequence)
            return

        # Step 12: READY. / RUN
        if self._boot_step == 12:
            self._border_busy = False
            self._boot_lines = [
                "    **** COMMODORE 64 BASIC V2 ****",
                "",
                " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
                "",
                "READY.",
                'LOAD "C64-BRIDGE",8,1',
                "",
                "SEARCHING FOR C64-BRIDGE",
                "LOADING",
                *loading_stages,
                "READY.",
                "RUN",
            ]
            self._render_boot_screen()
            self._draw_border_and_divider()

            # =================================================================
            # TEMPORARY PAUSE AT END OF LOADING SCREEN ("PRESS ANY KEY")
            # REM out the two lines below (`self._boot_waiting_for_key = True`
            # and `return`) and uncomment `self.root.after(...)` when you want
            # the studio to auto-start without waiting for a keypress.
            # =================================================================
            self._boot_waiting_for_key = True
            return
            # self.root.after(600, self._finish_boot_sequence)
            # return

        self._finish_boot_sequence()

    def _render_boot_screen(self) -> None:
        if not self._boot_active:
            return
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        self.boot_canvas.configure(bg=str(t["paper"]))
        self.boot_canvas.delete("all")

        lines = self._boot_lines or [
            "    **** COMMODORE 64 BASIC V2 ****",
            "",
            " 64K RAM SYSTEM  38911 BASIC BYTES FREE",
            "",
            "READY.",
            "",
        ]
        y = 38
        for idx, line in enumerate(lines):
            is_last = idx == len(lines) - 1
            cursor = "█" if (is_last and ((self._anim_tick // 4) % 2 == 0)) else ""
            color = str(t["accent"]) if line.startswith("LOADING FROM") else str(t["ink"])
            self.boot_canvas.create_text(
                42,
                y,
                anchor="nw",
                text=f"{line}{cursor}",
                font=(font_fam, 14, "bold"),
                fill=color,
            )
            y += 30

        if getattr(self, "_boot_waiting_for_key", False):
            prompt_text = ">>> LOADING COMPLETE -- PRESS ANY KEY (OR CLICK) TO START STUDIO <<<"
            prompt_col = str(t["accent_bright"]) if ((self._anim_tick // 4) % 2 == 0) else str(t["success"])
        else:
            prompt_text = "[PRESS ANY KEY OR CLICK TO SKIP BOOT SEQUENCE]"
            prompt_col = str(t["accent"])

        self.boot_canvas.create_text(
            42,
            y + 32,
            anchor="nw",
            text=prompt_text,
            font=(font_fam, 10, "bold"),
            fill=prompt_col,
        )

    def _finish_boot_sequence(self) -> None:
        """Complete boot sequence and show the ready-to-use C64-BRIDGE Studio."""
        if not self._boot_active and self.studio_frame.winfo_ismapped():
            return
        self._boot_active = False
        self._boot_waiting_for_key = False
        self._border_busy = False
        self.boot_canvas.pack_forget()
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
                "• Select target language (ASM 6502, C / Oscar64, or Python) and type a prompt below!\n"
                "• Example: \"Create a VIC-II raster bar demo with a 3-voice SID bassline\"\n"
                "• Press Shift+F12 (Alt+A) to jump to the prompt box, or Ctrl+K for guided CLI setup.\n"
                "────────────────────────────────────────────────────────────────────────"
            )
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
                        rgba.thumbnail((68, 44), Image.Resampling.NEAREST)
                        self._c64_badge_img = ImageTk.PhotoImage(rgba, master=self.root)
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
                        rgba.thumbnail((58, 44), Image.Resampling.NEAREST)
                        self._cassette_badge_img = ImageTk.PhotoImage(rgba, master=self.root)
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

        for frame in (
            self.screen_frame,
            self.studio_frame,
            self.top_bar,
            self.header_right,
            self.workspace_frame,
            self.left_pane,
            self.left_hdr_bar,
            self.right_pane,
            self.tab_bar,
            self.tab_stack,
            self.pane_asm,
            self.asm_toolbar,
            self.pane_log,
            self.pane_ast,
            self.pane_hw,
            self.pane_agy,
            self.agy_action_bar,
            self.deck_frame,
            self.status_row,
        ):
            frame.configure(bg=str(t["paper"]))

        self.screen_frame.configure(
            highlightbackground=str(t["accent"]),
            highlightcolor=str(t["accent"]),
        )
        self.left_pane.configure(highlightbackground=str(t["accent"]))
        self.right_pane.configure(highlightbackground=str(t["accent"]))
        self.agy_quick_bar.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))
        self.deck_frame.configure(highlightbackground=str(t["accent"]))

        self.banner_label.configure(
            text="**** COMMODORE 64 STUDIO IDE ****",
            font=f_banner,
            bg=str(t["paper"]),
            fg=str(t["ink"]),
        )
        self._update_language_button_styles()
        self._refresh_agy_badge(self.agy_status)

        self.btn_asm_focus.configure(
            font=f_btn,
            bg=str(t["accent"]) if self.asm_focus_mode else str(t["panel_bg"]),
            fg="#000000" if self.asm_focus_mode else str(t["accent"]),
        )
        self.btn_fullscreen.configure(
            font=f_btn,
            bg=str(t["panel_bg"]),
            fg=str(t["accent_bright"]),
        )

        for name, btn in self.theme_buttons.items():
            is_sel = name == theme_name
            btn.configure(
                font=f_btn,
                bg=str(t["button_active_bg"]) if is_sel else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_sel else str(t["panel_fg"]),
            )

        # Style 5-Column Menu Deck
        self.menu_bar.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))
        for col_f in self.col_frames.values():
            col_f.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["paper"]))

        for hdr_id, hdr_btn in self.col_headers.items():
            hdr_btn.configure(
                font=f_hdr,
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                activebackground=str(t["button_active_bg"]),
                activeforeground=str(t["button_active_fg"]),
            )

        for bid, b in self.menu_buttons.items():
            if bid in self.col_headers:
                continue
            fg_col = str(t["panel_fg"])
            if bid == "quick-btn-run":
                fg_col = str(t["success"])
            elif bid in ("quick-btn-reset", "btn-decompile-disk"):
                fg_col = str(t["warning"])
            elif bid in ("btn-quit", "btn-c64u-reboot"):
                fg_col = str(t["danger"])
            b.configure(
                font=f_btn,
                bg=str(t["panel_bg"]),
                fg=fg_col,
                activebackground=str(t["button_bg"]),
                activeforeground=str(t["button_fg"]),
            )

        self.bridge_status_lbl.configure(
            font=f_btn,
            bg=str(t["editor_bg"]),
            fg=str(t["accent"]),
        )

        # Style Left Pane (Python + ASM Labels)
        self.left_title_lbl.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=6, pady=2)
        for lbtn in (self.btn_py_to_asm, self.btn_new_c, self.btn_new_py):
            lbtn.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        self.py_editor_container.configure(bg=str(t["editor_bg"]), highlightbackground=str(t["accent"]))
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
        self.label_nav_hdr.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]), padx=4, pady=2)
        self.label_listbox.configure(
            font=f_small,
            bg=str(t["editor_bg"]),
            fg=str(t["cyan"]),
            selectbackground=str(t["button_bg"]),
            selectforeground=str(t["button_fg"]),
        )

        # Style Right Pane & ASM Editor
        self.mode_badge_lbl.configure(font=f_small, bg=str(t["paper"]), fg=str(t["accent"]))
        for btn in (self.btn_asm_comment, self.btn_find_go, self.btn_clear_log):
            btn.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        self.find_lbl.configure(font=f_small, bg=str(t["paper"]), fg=str(t["ink"]))
        self.find_entry.configure(
            font=f_small,
            bg=str(t["input_bg"]),
            fg=str(t["input_fg"]),
            insertbackground=str(t["input_fg"]),
            highlightbackground=str(t["accent"]),
        )
        self.asm_cursor_lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent_bright"]), padx=6, pady=2)

        self.asm_editor_container.configure(bg=str(t["editor_bg"]), highlightbackground=str(t["accent"]))
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

        # Style Hardware Tab
        for card in (self.hw_card_actions, self.hw_card_mem):
            card.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))
        for lbl in (self.hw_lbl_title, self.hw_lbl_mem, self.lbl_addr, self.lbl_val, self.lbl_keys):
            lbl.configure(font=f_hdr, bg=str(t["panel_bg"]), fg=str(t["accent"]))
        for entry in (self.inp_addr_entry, self.inp_val_entry, self.inp_keys_entry):
            entry.configure(
                font=f_code,
                bg=str(t["input_bg"]),
                fg=str(t["input_fg"]),
                insertbackground=str(t["input_fg"]),
                highlightbackground=str(t["accent"]),
            )
        for b in self.hw_buttons.values():
            b.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

        # Style Antigravity AI Console & Quick Prompt Bar
        self.agy_top_bar.configure(bg=str(t["panel_bg"]), highlightbackground=str(t["accent"]))
        self.agy_chat_wrap.configure(bg=str(t["editor_bg"]), highlightbackground=str(t["accent"]))
        for lbl in (self.agy_lbl_lang, self.agy_lbl_mode):
            lbl.configure(font=f_small, bg=str(t["panel_bg"]), fg=str(t["accent"]))
        for om in (self.agy_lang_menu, self.agy_mode_menu):
            om.configure(
                font=f_small,
                bg=str(t["button_bg"]),
                fg=str(t["button_fg"]),
                highlightbackground=str(t["accent"]),
            )
        for chk in (self.agy_chk_ctx, self.agy_chk_cont, self.agy_chk_apply):
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
        self.prompt_lbl.configure(font=f_hdr, bg=str(t["paper"]), fg=str(t["ink"]))
        self.credits_hint_lbl.configure(font=f_small, bg=str(t["paper"]), fg=str(t["accent"]))

        self._update_tab_button_styles()
        self._draw_border_and_divider()
        self._draw_bottom_deck()

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
        self._active_tab = tab_id
        for pane in (self.pane_asm, self.pane_log, self.pane_ast, self.pane_hw, self.pane_agy):
            pane.pack_forget()
        if tab_id == "tab-asm":
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
        gutter_str = "\n".join(f"{i:3d}" for i in range(1, line_count + 1))
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
        self.asm_text.tag_remove("find_match", "1.0", tk.END)

        # If numeric, jump to line number
        if query.isdigit():
            line_no = max(1, int(query))
            target = f"{line_no}.0"
            self.asm_text.mark_set(tk.INSERT, target)
            self.asm_text.see(target)
            self.asm_text.tag_add("find_match", target, f"{line_no}.end")
            self.asm_text.focus_set()
            self._on_asm_cursor_move()
            return

        # Otherwise search text from current cursor position (wrapping around)
        start_pos = self.asm_text.index(f"{tk.INSERT}+1c")
        pos = self.asm_text.search(query, start_pos, stopindex=tk.END, nocase=True)
        if not pos:
            pos = self.asm_text.search(query, "1.0", stopindex=tk.END, nocase=True)
        if pos:
            end_pos = f"{pos}+{len(query)}c"
            self.asm_text.tag_add("find_match", pos, end_pos)
            self.asm_text.mark_set(tk.INSERT, pos)
            self.asm_text.see(pos)
            self.asm_text.focus_set()
            self._on_asm_cursor_move()
        else:
            self.notify(f'"{query}" NOT FOUND IN ASM', severity="warning")

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
        """Load a clean KickAssembler 6502 starter template into the ASM editor."""
        self._begin_load("asm", None)
        self.file_mode = "asm"
        self.last_asm = NEW_ASM_TEMPLATE
        self._set_asm_text(NEW_ASM_TEMPLATE)
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new 6502 KickAssembler template in ASM Editor.")
        self.notify("NEW 6502 .ASM TEMPLATE READY")

    def action_new_c_template(self) -> None:
        """Switch to C/C++ (Oscar64 / CC65) mode and load a clean C64 starter template."""
        if self.asm_focus_mode:
            self.action_toggle_asm_focus()
        self._begin_load("c", None)
        self.file_mode = "c"
        self._set_python_text(NEW_C_TEMPLATE)
        self._update_mode_badge()
        self._write_log("✓ Created new C64 C99 (Oscar64 / CC65) template in LHS Editor.")
        self.notify("NEW C64 .C (OSCAR64) TEMPLATE READY")

    def action_new_py_template(self) -> None:
        """Switch to Python-to-6502 mode and load a clean bare-metal Python template."""
        if self.asm_focus_mode:
            self.action_toggle_asm_focus()
        self._begin_load("python", None)
        self.file_mode = "py"
        self._set_python_text(NEW_PY_TEMPLATE)
        self.action_transpile_code(silent=True)
        self._update_mode_badge()
        self._write_log("✓ Created new Python-to-6502 template in LHS Editor.")
        self.notify("NEW C64 .PY TEMPLATE READY")

    def action_select_language(self, lang: str) -> None:
        """Switch active C64 Studio IDE language between 'asm', 'c', and 'py'."""
        norm = lang.lower().strip()
        if norm not in {"asm", "c", "py"}:
            return
        self.file_mode = norm
        self.agy_lang_var.set(norm)
        if norm == "asm":
            self.file_kind = "asm"
            self.switch_tab("tab-asm")
            if not self.asm_text.get("1.0", "end-1c").strip():
                self._begin_load("asm", None)
                self.file_mode = "asm"
                self.last_asm = NEW_ASM_TEMPLATE
                self._set_asm_text(NEW_ASM_TEMPLATE)
            self.asm_text.focus_set()
        else:
            if self.asm_focus_mode:
                self.action_toggle_asm_focus()
            curr_lhs = self.py_text.get("1.0", "end-1c").strip()
            if norm == "c":
                self.file_kind = "c"
                if not curr_lhs or "border_color(" in curr_lhs or "while True:" in curr_lhs:
                    self._begin_load("c", None)
                    self.file_mode = "c"
                    self._set_python_text(NEW_C_TEMPLATE)
                else:
                    self._highlight_py_editor()
            else:
                self.file_kind = "python"
                if not curr_lhs or "#include" in curr_lhs:
                    self._begin_load("python", None)
                    self.file_mode = "py"
                    self._set_python_text(NEW_PY_TEMPLATE)
                    self.action_transpile_code(silent=True)
                else:
                    self._highlight_py_editor()
            self.py_text.focus_set()

        self._update_mode_badge()
        self.notify(f"C64 STUDIO LANGUAGE MODE: {norm.upper()}")

    def _on_left_build_clicked(self) -> None:
        """Compile C/C++ (Oscar64/CC65) when in 'c' mode, or transpile Python -> 6502 in 'py' mode."""
        if self.file_mode == "c":
            self.action_build()
        else:
            self.action_transpile_code()

    def _update_language_button_styles(self) -> None:
        t = THEMES[self.current_theme]
        font_fam = str(t["font_family"])
        for lc, btn in self.lang_buttons.items():
            is_act = lc == self.file_mode
            btn.configure(
                font=(font_fam, 8, "bold"),
                bg=str(t["button_active_bg"]) if is_act else str(t["panel_bg"]),
                fg=str(t["button_active_fg"]) if is_act else str(t["panel_fg"]),
            )

    def action_toggle_asm_focus(self) -> None:
        """Toggle between Split View (Python + ASM) and Full 6502 ASM IDE Focus Mode."""
        self.asm_focus_mode = not self.asm_focus_mode
        if self.asm_focus_mode:
            self.py_editor_container.pack_forget()
            self.left_hdr_bar.pack_forget()
            self.label_nav_frame.pack_configure(fill=tk.BOTH, expand=True, pady=0)
            self.label_listbox.configure(height=24)
            self.workspace_frame.columnconfigure(0, weight=2)
            self.workspace_frame.columnconfigure(1, weight=9)
            self.switch_tab("tab-asm")
            self.notify("6502 ASM IDE FOCUS ENABLED (CTRL+E TO SPLIT)")
        else:
            self.label_nav_frame.pack_forget()
            self.left_hdr_bar.pack(fill=tk.X, pady=(0, 4))
            self.py_editor_container.pack(fill=tk.BOTH, expand=True)
            self.label_nav_frame.pack(fill=tk.X, pady=(6, 0))
            self.label_listbox.configure(height=5)
            self.workspace_frame.columnconfigure(0, weight=5)
            self.workspace_frame.columnconfigure(1, weight=7)
            self.notify("SPLIT VIEW (PYTHON + 6502 ASM) ENABLED")
        self.apply_theme(self.current_theme)

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
        self.find_entry.focus_set()
        self.find_entry.selection_range(0, tk.END)

    def _update_mode_badge(self) -> None:
        """Show the file and how far along LOAD > BUILD > RUN it has got."""
        if self.loaded_file:
            fname = self.loaded_file.name
        elif self._has_source():
            if self.file_mode == "asm":
                fname = "UNTITLED.ASM"
            elif self.file_mode == "c":
                fname = "UNTITLED.C"
            else:
                fname = "UNTITLED.PY"
        else:
            fname = "NOTHING LOADED"
        steps = ("LOAD [F3]", "BUILD [F7]", "RUN [F5]")
        marks = " > ".join(f"*{step}*" if i < self.stage else step for i, step in enumerate(steps))
        self.mode_badge_lbl.configure(text=f"[{fname.upper()} // {marks}]")
        default_kind = "c" if self.file_mode == "c" else "python"
        title = KIND_LABELS.get(self.file_kind, KIND_LABELS[default_kind])
        self.left_title_lbl.configure(text=f"{title} // {fname.upper()}" if self.file_mode == "def" else title)
        self.btn_py_to_asm.configure(
            text="COMPILE C (F7)" if self.file_mode == "c" else "PY → ASM (F6)",
            state=tk.DISABLED if self.file_mode == "def" else tk.NORMAL,
        )
        if hasattr(self, "agy_lang_var") and self.file_mode in ("asm", "c", "py"):
            self.agy_lang_var.set(self.file_mode)
        if hasattr(self, "lang_buttons"):
            self._update_language_button_styles()

    def _set_stage(self, stage: int) -> None:
        self.stage = stage
        self._update_mode_badge()

    # -----------------------------------------------------------------------
    # Outer VIC-II Border, Rainbow Strip & Bottom DMA Deck Drawing
    # -----------------------------------------------------------------------

    def _on_border_resize(self, event) -> None:
        pad = 24
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
                i * seg_w, 0, (i + 1) * seg_w, 7, fill=col, outline=""
            )

    def _draw_bottom_deck(self) -> None:
        t = THEMES[self.current_theme]
        c = self.deck_canvas
        c.delete("all")
        w = max(c.winfo_width(), 900)
        h = 54
        font_fam = str(t["font_family"])

        # Left Cassette Badge & Right C64 Badge
        if self._cassette_badge_img is not None:
            c.create_image(36, h // 2, image=self._cassette_badge_img)
        if self._c64_badge_img is not None:
            c.create_image(w - 42, h // 2, image=self._c64_badge_img)

        bar_x1 = 82
        bar_x2 = w - 92
        bar_y1 = 10
        bar_y2 = 44
        bar_w = max(40, bar_x2 - bar_x1)

        c.create_rectangle(
            bar_x1, bar_y1, bar_x2, bar_y2,
            outline=str(t["accent_bright"]), width=2, fill=str(t["bar_bg"])
        )

        num_blocks = 32
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
                c.create_rectangle(bx1, bar_y1 + 4, bx2, bar_y2 - 4, fill=col, outline="")
            else:
                c.create_rectangle(bx1, bar_y1 + 4, bx2, bar_y2 - 4, fill="#0D0826", outline="")

        badge_txt = f" {self._busy_phase} "
        tid = c.create_text(
            (bar_x1 + bar_x2) / 2,
            (bar_y1 + bar_y2) / 2,
            text=badge_txt,
            font=(font_fam, 9, "bold"),
            fill=str(t["accent_bright"]),
        )
        bbox = c.bbox(tid)
        if bbox:
            bg_id = c.create_rectangle(
                bbox[0] - 8, bar_y1 + 5, bbox[2] + 8, bar_y2 - 5,
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
            if not self.root.winfo_exists():
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

        if self._boot_active:
            self._render_boot_screen()
            if self._border_busy:
                self._draw_border_and_divider()
        else:
            if self._border_busy:
                self._draw_border_and_divider()
                self._draw_bottom_deck()
            cursor_char = "█" if (self._anim_tick // 5) % 2 == 0 else " "
            base_text = getattr(self, "_last_status_message", str(t["ready_prompt"]))
            self.prompt_lbl.configure(text=f"{base_text} {cursor_char}")

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
            self.prompt_lbl.configure(text=f"{self._last_status_message} █")
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

    def _set_asm_text(self, asm_code: str) -> None:
        self.asm_text.delete("1.0", tk.END)
        self.asm_text.insert("1.0", asm_code)
        self._highlight_asm_editor()
        self._on_asm_cursor_move()

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
        if self._boot_active:
            self._finish_boot_sequence()
            return
        if self.focused_button_id and event.keysym in ("Up", "Down", "Left", "Right", "Escape"):
            self.navigate_menu_key(event.keysym.lower())

    def _on_btn_focus(self, btn_id: str) -> None:
        self.focused_button_id = btn_id

    def _invoke_menu_btn(self, btn_id: str, fn: Callable[[], None]) -> None:
        self.focused_button_id = btn_id
        fn()

    def action_focus_menu(self) -> None:
        self.action_focus_submenu("file")

    def action_focus_submenu(self, category: str) -> None:
        target_map = {
            "file": "btn-open",
            "build": "quick-btn-run",
            "device": "btn-refresh",
            "gamedev": "btn-gd-game",
            "help": "btn-presets",
        }
        btn_id = target_map.get(category, "btn-open")
        self.focused_button_id = btn_id
        btn = self.menu_buttons.get(btn_id)
        if btn:
            try:
                btn.focus_set()
            except tk.TclError:
                pass

    def navigate_menu_key(self, key: str) -> None:
        """Navigate across the 5 displayed C64 menu columns using arrow keys."""
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
            nr = min(cur_row, len(self.menu_columns[cats[nc]]) - 1)
            next_id = self.menu_columns[cats[nc]][nr]
        elif key == "right":
            nc = (cur_col + 1) % len(cats)
            nr = min(cur_row, len(self.menu_columns[cats[nc]]) - 1)
            next_id = self.menu_columns[cats[nc]][nr]
        elif key == "escape":
            self.focused_button_id = None
            self.asm_text.focus_set()
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

    def _save_loaded_file(self) -> None:
        """Building uses what is on screen, so it goes to disk first."""
        if not self.loaded_file:
            return
        text = self._editor_text()
        if not self.loaded_file.is_file() or self.loaded_file.read_text(encoding="utf-8") != text:
            self.loaded_file.write_text(text, encoding="utf-8")
            self._write_log(f"✓ Saved {self.loaded_file}")

    def _project_manifest(self) -> Optional[Path]:
        """The game's build.py. A disassembly or SID source sits beside a game without being part of it."""
        if not self.loaded_file or self.file_kind in ("sid", "prg", "bin", "tap", "d64"):
            return None
        return find_manifest(self.loaded_file)

    def action_build(self, on_done: Optional[Callable[[Optional[Path]], None]] = None) -> None:
        """Build whatever is loaded. on_done gets the .prg, or None if this kind of file makes none."""
        if not self._has_source():
            self.notify("NOTHING TO BUILD: F3 LOADS A FILE", severity="warning")
            return
        self._save_loaded_file()
        manifest = self._project_manifest()
        if self.file_mode == "def" and self.loaded_file:
            self._run_game_tool(self.file_kind, self.loaded_file, on_done)
        elif self.file_mode == "asm" and manifest:
            self._write_log(f"Part of the project in {manifest}: building all of it")
            self._run_game_tool("build", manifest, on_done)
        elif self.file_kind == "sid":
            self.action_compile_sid()
        else:
            self._assemble_current(on_done)

    def _assemble_current(self, on_done: Optional[Callable[[Optional[Path]], None]] = None) -> None:
        """Assemble or compile the loaded program (Oscar64/CC65 for C, KickAssembler for ASM/Python)."""
        if self.file_mode == "c":
            self._pulse_raster_border("COMPILING C/C++ → PRG BINARY", 450)
            c_source = self.py_text.get("1.0", "end-1c").strip()
            if not c_source:
                self.notify("NO C/C++ SOURCE TO COMPILE", severity="warning")
                return
            out_prg = self.loaded_file.with_suffix(".prg").resolve() if self.loaded_file else Path("./output.prg").resolve()
            temp_c = None
            if self.loaded_file and self.loaded_file.is_file():
                target_c = self.loaded_file
            else:
                with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as tmp:
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
                try:
                    dec = decompile_prg(out_prg.read_bytes(), name=out_prg.stem)
                    self.last_asm = dec.assembly
                    self._set_asm_text(dec.assembly)
                    self._write_log(f"  ↳ Disassembled {dec.instruction_count:,} optimized 6502 instructions into ASM view.")
                except Exception:
                    pass
                self.notify(f"BUILT {out_prg.name} ({sz} BYTES // {detected_cc.upper()})")
                self._set_stage(2)
                if on_done:
                    on_done(out_prg)
            else:
                err = comp_res.error_message or comp_res.stderr or comp_res.stdout
                self.switch_tab("tab-log")
                self._write_log(f"C/C++ Compilation Failed ({detected_cc}): {err}")
                self.notify("C/C++ COMPILATION FAILED! CHECK LOG", severity="error")
            return

        self._pulse_raster_border("ASSEMBLING 6502 → PRG BINARY", 450)
        if self.file_mode == "py" and not self.action_transpile_code(silent=True):
            self.notify("TRANSPILATION FAILED! CHECK LOG", severity="error")
            return
        asm_text = self.asm_text.get("1.0", "end-1c").strip()
        if not asm_text:
            self.notify("NO 6502 ASSEMBLY TO COMPILE", severity="warning")
            return

        out_prg = self.loaded_file.with_suffix(".prg").resolve() if self.loaded_file else Path("./output.prg").resolve()
        temp_asm = None
        if self.file_mode == "asm" and self.loaded_file:
            target_asm = self.loaded_file
        else:
            with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as tmp:
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
            self.notify(f"BUILT {out_prg.name} ({sz} BYTES)")
            self._set_stage(2)
            if on_done:
                on_done(out_prg)
        else:
            err = comp_res.error_message or comp_res.stderr or comp_res.stdout
            self.switch_tab("tab-log")
            self._write_log(f"Assembly Failed: {err}")
            self.notify("ASSEMBLY FAILED! CHECK LOG", severity="error")

    def _build_program(self, use_prg: Callable[[Path], None]) -> None:
        """Get a .prg for what is loaded, then hand it on. A game's assets build the whole game."""
        if self._binary_unchanged():
            use_prg(self.binary_source)
            return

        def _got(prg: Optional[Path]) -> None:
            if prg:
                use_prg(prg)
            else:
                self.notify("THIS FILE MAKES NO PROGRAM: IT NEEDS A BUILD.PY", severity="warning")

        manifest = self._project_manifest()
        if self.file_mode == "def" and self.file_kind != "build" and manifest:
            self._save_loaded_file()
            self._run_game_tool("build", manifest, _got)
        else:
            self.action_build(_got)

    def action_run_c64u(self) -> None:
        """Build what is loaded and run it on the C64U: a song plays, anything else DMA-runs."""
        if self.file_kind == "song":
            self.action_build(lambda _prg: self.action_play_sid())
        elif self.file_kind == "sid":
            if not self._asm_unchanged():
                self.action_build()
            self.action_play_sid()
        else:
            self._build_program(self._dma_run)

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
        modal.show_tk(self, lambda path: self.load_project_file(path) if path else None)

    def _begin_load(self, kind: str, path: Optional[Path]) -> None:
        """Whatever was built from the last file no longer applies."""
        self.file_kind = kind
        self.loaded_file = path
        self.binary_source = None
        self.last_prg_path = None
        self.last_sid_path = None
        self.stage = 1

    def load_project_file(self, path: Path) -> None:
        """The start of every sequence: put a file on screen. Nothing runs from here."""
        if not path.exists():
            self.notify(f"FILE NOT FOUND: {path.name}", severity="error")
            return

        self._pulse_raster_border(f'LOADING "{path.name.upper()}",8,1', 420)
        kind = classify_file(path)

        if kind in ("build", *DEFINITION_KINDS):
            self._begin_load(kind, path)
            self.file_mode = "def"
            if self.asm_focus_mode:
                self.action_toggle_asm_focus()
            self._set_python_text(path.read_text(encoding="utf-8"))
            self._set_asm_text("")
            self.last_asm = ""
            self.switch_tab("tab-log")
            self._write_log(f"✓ Loaded {KIND_LABELS[kind]}: {path.name}. F7 builds it.")
            self.notify(f'LOADED "{path.name.upper()}"')

        elif kind == "c":
            self._begin_load(kind, path)
            self.file_mode = "c"
            if self.asm_focus_mode:
                self.action_toggle_asm_focus()
            self._set_python_text(path.read_text(encoding="utf-8"))
            self._write_log(f"✓ Loaded C/C++ source (Oscar64/CC65): {path.name} ({path.stat().st_size} bytes)")
            self.notify(f'LOADED "{path.name.upper()}" (C/OSCAR64 MODE)')

        elif kind == "python":
            self._begin_load(kind, path)
            self.file_mode = "py"
            self._set_python_text(path.read_text(encoding="utf-8"))
            self._write_log(f"✓ Loaded Python source: {path.name} ({path.stat().st_size} bytes)")
            self.notify(f'LOADED "{path.name.upper()}"')
            self.action_transpile_code(silent=True)

        elif kind == "asm":
            self._begin_load(kind, path)
            self.file_mode = "asm"
            asm_content = path.read_text(encoding="utf-8")
            self.last_asm = asm_content
            self._set_asm_text(asm_content)
            self.switch_tab("tab-asm")
            self._write_log(
                f"✓ Loaded 6502 Assembly: {path.name} ({path.stat().st_size} bytes, {len(asm_content.splitlines())} lines)"
            )
            self.notify(f'LOADED "{path.name.upper()}" (6502 ASM MODE)')

            sidecar = path.with_suffix(".py")
            has_sidecar = sidecar.is_file() and classify_file(sidecar) == "python"
            self._set_python_text(sidecar.read_text(encoding="utf-8") if has_sidecar else "")
            if has_sidecar:
                self._write_log(f"ℹ Its Python source {sidecar.name} is in the left pane")

        elif kind == "sid":
            self._begin_load(kind, None)     # the source gets its own file: never save over the .sid
            self._load_sid_file(path)

        elif kind in ("d64", "tap", "prg", "bin"):
            def _shown() -> None:
                self._begin_load(kind, None)     # likewise for the image
                if kind in ("prg", "bin"):
                    self.binary_source = path
                    self.last_prg_path = path

            self.action_decompile_media(path, before=_shown)

        else:
            self.notify(f"CANNOT LOAD {path.suffix.upper()} FILES", severity="warning")
            return

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
        self.last_asm = res.assembly
        self.file_mode = "asm"
        self.stage = 1
        if source_path is not None:
            self.loaded_file = source_path.with_name(f"{source_path.stem}_decompiled.asm")
        self._set_asm_text(res.assembly)
        self._set_python_text(res.python)
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

            self.file_mode = "asm"
            self.file_kind = "sid"
            self.last_sid_path = path
            self.loaded_file = asm_path
            self.last_asm = result.assembly
            self._set_asm_text(result.assembly)
            self._set_python_text(result.python)
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

    def action_compile_sid(self) -> None:
        if not self.loaded_file or self.loaded_file.suffix.lower() not in {".asm", ".s", ".py"}:
            self.notify("LOAD A DECOMPILED SID SOURCE FIRST", severity="warning")
            return
        source_text = self.asm_text.get("1.0", "end-1c") if self.file_mode == "asm" else self.py_text.get("1.0", "end-1c")
        if "C64U_SID_METADATA:" not in source_text and not self.last_sid_path:
            self.notify("SOURCE HAS NO SID METADATA", severity="warning")
            return
        try:
            self._pulse_raster_border("COMPILING ASM → SID CONTAINER", 450)
            res = compile_sid_source(
                self.loaded_file,
                template_sid=self.last_sid_path,
                compiler=self.compiler,
                source_text=source_text,
            )
            self.last_sid_path = res.output_sid
            self._write_log(f"✓ SID compiled: {res.output_sid} ({res.payload_size} bytes)")
            self.notify(f"COMPILED {res.output_sid.name}")
            self._set_stage(2)
        except Exception as exc:
            self._write_log(f"SID compilation failed: {exc}")
            self.notify(f"SID COMPILE FAILED: {exc}", severity="error")

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

    def action_gamedev_sim(self) -> None:
        if self.last_sid_path and self.last_sid_path.is_file():
            self._run_game_tool("sim", self.last_sid_path)
        else:
            self._build_program(lambda prg: self._run_game_tool("sim", prg))

    def _run_game_tool(
        self, key: str, target: Path, on_done: Optional[Callable[[Optional[Path]], None]] = None
    ) -> None:
        tool = GAME_TOOLS[key]
        self._pulse_raster_border(f"{tool.label}: {target.name.upper()}", 600)
        self._write_log(f"▶ {tool.label}: {target}")

        def _worker():
            result = run_tool(key, target)

            def _done():
                if not self.root.winfo_exists():
                    return
                for line in result.output.splitlines():
                    self._write_log(f"  {line}")
                if not result.ok:
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

    def action_save_file(self) -> None:
        """Save the loaded file, asking for a name if it does not have one yet."""
        if not self._has_source():
            self.notify("NOTHING TO SAVE", severity="warning")
            return
        if not self.loaded_file:
            fd_mod = _tui_attr("filedialog", filedialog)
            target_dir_fn = _tui_attr("default_target_dir", default_target_dir)
            ext = ".asm" if self.file_mode == "asm" else (".c" if self.file_mode == "c" else ".py")
            chosen = fd_mod.asksaveasfilename(
                title="SAVE FILE",
                initialdir=target_dir_fn(),
                initialfile=f"untitled{ext}",
                defaultextension=ext,
            )
            if not chosen:
                return
            self.loaded_file = Path(chosen)
        self.loaded_file.write_text(self._editor_text(), encoding="utf-8")
        if self.file_mode == "asm":
            self.last_asm = self._editor_text()
        self._write_log(f"✓ Saved {self.loaded_file}")
        self.notify(f'SAVED "{self.loaded_file.name.upper()}"')
        self._update_mode_badge()

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
        self.last_asm = current_text
        self._write_log(f"✓ Saved 6502 assembly to {out_file}")
        self.notify(f'SAVED "{out_file.name.upper()}"')

    def action_export_hyperload(self) -> None:
        """Build, then write a .tap with the HYPERLOAD fast loader and border stripes."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("MASTERING HYPERLOAD CASSETTE IMAGE", 480)
            out_tap = prg.with_suffix(".tap")
            res = run_tool("hyperload", prg, args=("-o", str(out_tap), "--name", prg.stem))
            if res.ok:
                sz = out_tap.stat().st_size
                self._write_log(f"✓ HYPERLOAD Cassette Image Generated: {out_tap} ({sz} bytes)")
                self._write_log(res.output)
                self.notify(f"EXPORTED {out_tap.name.upper()} WITH HYPERLOAD ({sz} BYTES)")
            else:
                self._write_log(f"HYPERLOAD Export Error: {res.output}")
                self.notify(f"HYPERLOAD EXPORT ERROR: {res.output.splitlines()[-1] if res.output else 'see log'}",
                            severity="error")

        self._build_program(_export)

    def action_export_tap(self) -> None:
        """Build, then write a standard-speed .tap cassette image."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("MASTERING .TAP CASSETTE IMAGE", 480)
            out_tap = prg.with_suffix(".tap")
            try:
                save_prg_to_tap(prg, tap_path=out_tap, tape_name=prg.stem)
                sz = out_tap.stat().st_size
                self._write_log(f"✓ TAP Cassette Image Generated: {out_tap} ({sz} bytes)")
                self.notify(f"EXPORTED {out_tap.name.upper()} ({sz} BYTES)")
            except Exception as exc:
                self._write_log(f"TAP Export Error: {exc}")
                self.notify(f"TAP EXPORT ERROR: {exc}", severity="error")

        self._build_program(_export)

    def action_compile_d64(self) -> None:
        """Build, then package into a standard 35-track 1541 .d64 disk image."""
        def _export(prg: Path) -> None:
            self._pulse_raster_border("FORMATTING & WRITING 1541 .D64 DISK", 500)
            out_d64 = prg.with_suffix(".d64")
            try:
                save_prg_to_d64(prg, d64_path=out_d64, disk_name=prg.stem.upper()[:16])
                sz = out_d64.stat().st_size
                self._write_log(f"✓ 1541 D64 Disk Image Generated: {out_d64} ({sz} bytes)")
                self.notify(f"COMPILED {out_d64.name.upper()} ({sz} BYTES)")
            except Exception as exc:
                self._write_log(f"D64 Packaging Error: {exc}")
                self.notify(f"D64 EXPORT ERROR: {exc}", severity="error")

        self._build_program(_export)

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
                self._begin_load("python", None)
                self.file_mode = "py"
                self._set_python_text(str(code))
                self._update_mode_badge()
                self.action_transpile_code()
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
            "6502 ASSEMBLY (.ASM) EDITOR POWER TOOLS\n"
            "============================================================\n"
            "• Ctrl+E        : Toggle Full 6502 ASM IDE Focus vs Split View (Python + ASM)\n"
            "• Ctrl+N        : Create New 6502 KickAssembler (.asm) Starter Template\n"
            "• Ctrl+S / ⇧F1  : Save the Loaded File\n"
            "• Ctrl+/        : Comment / Uncomment Selected 6502 Assembly Lines\n"
            "• Ctrl+F        : Find Text, Label, or Jump to Line Number\n"
            "• Label Outline : Click any label/subroutine in the left outline to jump instantly\n\n"
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
    # Google Antigravity CLI (`agy`) Auto-Detection, Setup & Prompting
    # -----------------------------------------------------------------------

    def _refresh_agy_badge(self, status: Optional[AgyStatus] = None) -> None:
        """Update the top-bar Antigravity CLI status indicator pill."""
        if status is not None:
            self.agy_status = status
        if not self.root.winfo_exists():
            return
        t = THEMES[self.current_theme]
        if self.agy_status.installed:
            ver_tag = f"v{self.agy_status.version}" if self.agy_status.version else "OK"
            self.btn_agy_status.configure(
                text=f"● AGY {ver_tag}",
                bg=str(t["success"]),
                fg="#000000",
            )
        else:
            self.btn_agy_status.configure(
                text="⚠ AGY SETUP",
                bg=str(t["warning"]),
                fg="#000000",
            )

    def check_agy_cli_startup(self, full: bool = False) -> None:
        """Auto-detect `agy` CLI installation on C64 Studio startup."""
        if getattr(self, "_in_mainloop", False):
            def _bg() -> None:
                st = self.agy.detect_cli()

                def _apply() -> None:
                    if not self.root.winfo_exists():
                        return
                    self._refresh_agy_badge(st)
                    if st.installed:
                        self._write_log(f"✓ {st.status_message}")
                    else:
                        self._write_log(
                            f"ℹ {st.status_message} Click '⚠ AGY SETUP' (Ctrl+K) to install or copy `{st.install_command}`."
                        )

                try:
                    self.root.after(0, _apply)
                except (tk.TclError, RuntimeError):
                    pass

            threading.Thread(target=_bg, daemon=True).start()
            return

        if full:
            st = self.agy.detect_cli()
        else:
            bin_path = self.agy.find_binary()
            is_win = os.name == "nt"
            st = AgyStatus(
                installed=bin_path is not None,
                binary_path=bin_path,
                version="detected" if bin_path is not None else None,
                install_command=INSTALL_CMD_WINDOWS_PS1 if is_win else INSTALL_CMD_UNIX,
                status_message=(
                    f"Antigravity CLI detected at {bin_path}"
                    if bin_path
                    else "Antigravity CLI (agy) not detected on this system."
                ),
            )
        self._refresh_agy_badge(st)

    def action_open_agy_setup(self) -> None:
        """Open the guided Antigravity CLI (`agy`) setup, installer, and MCP linking modal."""
        st = self.agy.detect_cli()
        self._refresh_agy_badge(st)
        modal = AgySetupModal(self.agy, st)
        self._last_agy_modal = modal
        modal.show_tk(self, callback=lambda updated: self._refresh_agy_badge(updated))

    def action_focus_agy_prompt(self) -> None:
        """Switch to the Antigravity AI Console tab and focus the prompt entry box (`Shift+F12`)."""
        if self.file_mode in ("asm", "c", "py"):
            self.agy_lang_var.set(self.file_mode)
        self.switch_tab("tab-agy")
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

    def _clear_agy_chat(self) -> None:
        self.agy_chat_text.delete("1.0", tk.END)

    def action_send_agy_prompt(self, prompt_override: Optional[str] = None) -> None:
        """Send a prompt from C64 Studio to the Antigravity CLI (`agy`) and stream/apply code."""
        if self._agy_busy:
            self.notify("ANTIGRAVITY CLI IS CURRENTLY GENERATING...", severity="warning")
            return

        user_prompt = (
            prompt_override if prompt_override is not None else self.agy_prompt_var.get()
        ).strip()
        if not user_prompt:
            self.action_focus_agy_prompt()
            self.notify("ENTER A PROMPT FOR ANTIGRAVITY CLI [⇧F12]")
            return

        st = self.agy.detect_cli()
        self._refresh_agy_badge(st)
        if not st.installed:
            self.switch_tab("tab-agy")
            self._write_agy_chat(
                "⚠ Google Antigravity CLI (`agy`) was not detected on this machine.\n"
                f"  • Install Command : {st.install_command}\n"
                "  • Opening the C64 Studio Antigravity Setup Wizard so you can auto-install in 1 click!"
            )
            self.notify("AGY CLI NOT FOUND — OPENING SETUP WIZARD", severity="warning")
            self.action_open_agy_setup()
            return

        if prompt_override is None:
            self.agy_prompt_var.set("")

        self.switch_tab("tab-agy")
        target_lang = (self.agy_lang_var.get() or self.file_mode or "asm").strip().lower()
        if target_lang not in ("asm", "c", "py"):
            target_lang = "asm"

        current_code = (
            self.asm_text.get("1.0", "end-1c")
            if target_lang == "asm"
            else self.py_text.get("1.0", "end-1c")
        )
        include_ctx = bool(self.agy_include_ctx_var.get())
        continue_conv = bool(self.agy_continue_var.get())
        exec_mode = self.agy_mode_var.get().strip() or "accept-edits"

        self._agy_busy = True
        self.btn_agy_send.configure(state=tk.DISABLED, text="⏳ AGY THINKING...")
        self._pulse_raster_border(f"ANTIGRAVITY CLI ({target_lang.upper()})", 900)
        self._write_agy_chat(f"\n>>> YOU [{target_lang.upper()}]: {user_prompt}")
        self._write_agy_chat("─── ANTIGRAVITY CLI RESPONSE ───────────────────────────────────────────")

        def _finish(res: AgyPromptResult) -> None:
            self._agy_busy = False
            self.last_agy_result = res
            if self.root.winfo_exists():
                self.btn_agy_send.configure(state=tk.NORMAL, text="▶ ASK ANTIGRAVITY")
            if not res.success and res.error_message:
                self._write_agy_chat(f"✗ Error: {res.error_message}")
                self._write_log(f"✗ Antigravity CLI Error: {res.error_message}")
                self.notify("ANTIGRAVITY CLI ERROR (SEE AI CONSOLE)", severity="error")
                return

            block = res.primary_code_block
            if block is not None:
                self.last_agy_code_block = block
                line_cnt = len(block.code.splitlines())
                self._write_agy_chat(
                    f"✓ Extracted {block.studio_mode.upper()} code block ({line_cnt} lines)."
                )
                self._write_log(
                    f"✓ Antigravity CLI generated {block.studio_mode.upper()} code ({line_cnt} lines)."
                )
                if self.agy_auto_apply_var.get():
                    self._apply_extracted_code_block(block)
                else:
                    self.notify(f"AGY {block.studio_mode.upper()} CODE READY — CLICK APPLY")
            else:
                self.notify("ANTIGRAVITY RESPONSE RECEIVED")

        if getattr(self, "_in_mainloop", False):
            def _worker() -> None:
                res = self.agy.run_prompt(
                    user_prompt,
                    language_mode=target_lang,
                    current_code=current_code,
                    active_file=self.loaded_file,
                    include_code_context=include_ctx,
                    continue_conversation=continue_conv,
                    exec_mode=exec_mode,
                    on_line=lambda ln: self.root.after(0, lambda line=ln: self._write_agy_chat(line)),
                )
                try:
                    self.root.after(0, lambda: _finish(res))
                except (tk.TclError, RuntimeError):
                    self._agy_busy = False

            threading.Thread(target=_worker, daemon=True).start()
        else:
            res = self.agy.run_prompt(
                user_prompt,
                language_mode=target_lang,
                current_code=current_code,
                active_file=self.loaded_file,
                include_code_context=include_ctx,
                continue_conversation=continue_conv,
                exec_mode=exec_mode,
                on_line=self._write_agy_chat,
            )
            _finish(res)

    def _apply_extracted_code_block(self, block: ExtractedCodeBlock) -> None:
        """Load an extracted Antigravity code block (`asm`, `c`, or `py`) into C64 Studio."""
        mode = block.studio_mode if block.studio_mode in ("asm", "c", "py") else "asm"
        kind = "python" if mode == "py" else mode
        self._begin_load(kind, self.loaded_file)
        self.file_mode = mode
        self.agy_lang_var.set(mode)

        if mode == "asm":
            self.last_asm = block.code
            self._set_asm_text(block.code)
            self._update_mode_badge()
            self._write_log(
                f"✓ Applied Antigravity 6502 Assembly into ASM IDE ({len(block.code.splitlines())} lines)"
            )
            self.notify("APPLIED AGY 6502 ASM TO EDITOR (F5 TO RUN)")
        else:
            if self.asm_focus_mode:
                self.action_toggle_asm_focus()
            self._set_python_text(block.code)
            self._update_mode_badge()
            if mode == "py":
                self.action_transpile_code(silent=True)
                self._write_log(
                    f"✓ Applied Antigravity Python code & transpiled to 6502 ASM ({len(block.code.splitlines())} lines)"
                )
                self.notify("APPLIED AGY PYTHON & TRANSPILED (F5 TO RUN)")
            else:
                self._write_log(
                    f"✓ Applied Antigravity C (Oscar64/CC65) code into editor ({len(block.code.splitlines())} lines)"
                )
                self.notify("APPLIED AGY C SOURCE TO EDITOR (F5 TO COMPILE & RUN)")

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


def main(argv: Optional[list[str]] = None) -> None:
    """Primary hub entry point for C64 Studio (`c64-studio`, `c64u-studio`, `c64u`, `c64u-bridge`)."""
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
        help="Skip the simulated C64 LOAD \"C64-BRIDGE\",8,1 startup sequence",
    )
    parser.add_argument("--host", help="C64U IP address or hostname (default: env C64U_HOST or c64u.local)")
    parser.add_argument("--port", type=int, default=80, help="C64U REST API port (default: 80)")
    parser.add_argument("--password", help="Optional C64U network password")
    parser.add_argument("--agy-bin", help="Optional explicit path to the Antigravity CLI (`agy`) binary")
    args = parser.parse_args(argv)

    app = C64StudioApp(
        skip_boot=args.no_boot,
        start_maximized=True,
        host=args.host,
        port=args.port,
        password=args.password,
        agy_bin=args.agy_bin,
    )
    if args.file:
        p = Path(args.file)
        if p.exists():
            app.root.after(150, lambda target=p: app.load_project_file(target))
    app.run()


if __name__ == "__main__":
    main()
