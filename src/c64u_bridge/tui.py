"""
Commodore 64 Lookalike Studio & 6502 Assembly / Python IDE (Tkinter).

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
import time
import tkinter as tk
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Iterable, Optional

try:
    from PIL import Image, ImageTk
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageTk = None  # type: ignore

from .client import C64UClient, C64UClientError
from .compiler import CrossCompiler, KickAssVersionStatus
from .d64 import D64Disk, D64Entry, read_d64_file, save_prg_to_d64
from .gamedev import GAME_TOOLS, default_target_dir, run_tool
from .prg_decompiler import (
    MediaStageInfo,
    PrgDecompileResult,
    decompile_d64_file,
    decompile_prg,
    decompile_tap_file,
    inspect_media_stages,
)
from .screen import format_screen
from .sid_compiler import SidCompileError, compile_sid_source
from .sid_decompiler import SidDecompileError, decompile_sid_file
from .tap import extract_prgs_from_tap, read_tap_info, save_prg_to_tap
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

NEW_ASM_TEMPLATE = """// ============================================================================
// COMMODORE 64 — MOS 6502 / 6510 KICKASSEMBLER SOURCE
// Press F5 to Assemble & DMA Run on C64U, or F7 to Assemble to .PRG
// ============================================================================

BasicUpstart2(start)

.const VIC_BORDER_COLOR = $D020
.const VIC_BG_COLOR0    = $D021
.const VIC_RASTER_LINE  = $D012
.const SCREEN_RAM       = $0400
.const COLOR_RAM        = $D800
.const KERNAL_CHROUT    = $FFD2

* = $0810 "Main Program"

start:
    sei
    lda #$0e            // Light Blue border
    sta VIC_BORDER_COLOR
    lda #$06            // Dark Blue background
    sta VIC_BG_COLOR0
    cli

main_loop:
    lda #$fb            // Wait for raster line 251
!wait:
    cmp VIC_RASTER_LINE
    bne !wait-

    inc VIC_BORDER_COLOR
    nop
    nop
    nop
    dec VIC_BORDER_COLOR
    jmp main_loop
"""

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
        supported = {".py", ".asm", ".s", ".sid", ".prg", ".tap", ".d64", ".c", ".h", ".sym", ".bin"}
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

class C64PythonToAsmApp:
    """
    Authentic Commodore 64 Lookalike Screen & 6502 Assembly / Python IDE in Tkinter.
    Replaces the legacy terminal TUI with a full-screen C64 CRT studio modeled after
    the BackMeUpScotty project.
    """

    BINDINGS: list[KeyBindingDef] = [
        KeyBindingDef("f1", "show_help", "Help & Credits"),
        KeyBindingDef("f2", "open_presets", "Presets"),
        KeyBindingDef("f3", "open_file", "Open File"),
        KeyBindingDef("f4", "refresh_connection", "Ping C64U"),
        KeyBindingDef("f5", "run_c64u", "DMA Run"),
        KeyBindingDef("f6", "transpile_code", "Transpile"),
        KeyBindingDef("f7", "assemble_prg", "Assemble"),
        KeyBindingDef("f8", "reset_c64u", "Reset C64U"),
        KeyBindingDef("f9", "decompile_media", "Decompile"),
        KeyBindingDef("f10", "focus_menu", "Menu Bar"),
        KeyBindingDef("f11", "toggle_fullscreen", "Fullscreen"),
        KeyBindingDef("shift+f1", "save_assembly", "Save ASM"),
        KeyBindingDef("shift+f2", "export_tap", "Export TAP"),
        KeyBindingDef("shift+f3", "load_prg_only", "DMA Load"),
        KeyBindingDef("shift+f4", "pause_cpu", "Pause CPU"),
        KeyBindingDef("shift+f5", "resume_cpu", "Resume CPU"),
        KeyBindingDef("shift+f6", "dump_screen", "Screen Dump"),
        KeyBindingDef("shift+f7", "reboot_c64u", "Reboot C64U"),
        KeyBindingDef("shift+f8", "quit", "Quit"),
        KeyBindingDef("shift+f9", "compile_d64", "Compile D64"),
        KeyBindingDef("ctrl+s", "save_assembly", "Save ASM"),
        KeyBindingDef("ctrl+t", "export_tap", "Export TAP"),
        KeyBindingDef("ctrl+m", "compile_d64", "Compile D64"),
        KeyBindingDef("ctrl+r", "reset_c64u", "Reset C64U"),
        KeyBindingDef("ctrl+d", "decompile_sid", "Decompile SID"),
        KeyBindingDef("ctrl+b", "compile_sid", "Compile SID"),
        KeyBindingDef("ctrl+p", "play_sid", "Play SID"),
        KeyBindingDef("ctrl+e", "toggle_asm_focus", "ASM IDE Focus"),
        KeyBindingDef("ctrl+n", "new_asm_template", "New ASM"),
        KeyBindingDef("ctrl+f", "focus_find", "Find / Goto"),
        KeyBindingDef("ctrl+q", "quit", "Quit"),
        KeyBindingDef("alt+f", "focus_submenu('file')", "File"),
        KeyBindingDef("alt+b", "focus_submenu('build')", "Build"),
        KeyBindingDef("alt+c", "focus_submenu('device')", "Device"),
        KeyBindingDef("alt+s", "focus_submenu('sid')", "SID"),
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
        self.client = C64UClient()

        self.current_theme = "Commodore 64"
        self.last_asm: str = ""
        self.last_prg_path: Optional[Path] = None
        self.last_sid_path: Optional[Path] = None
        self.loaded_file: Optional[Path] = None
        self.file_mode: str = "py"  # "py" or "asm"
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

        self.root.title('C64-BRIDGE // **** COMMODORE 64 BASIC V2 **** 6502 ASM & PYTHON STUDIO')
        self.root.geometry("1440x920")
        self.root.minsize(1024, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.action_quit)

        self._build_ui()
        self.apply_theme(self.current_theme)
        self._bind_shortcuts()

        # Populate initial Rainbow Raster Bars code & transpile into 6502 ASM editor
        initial_code = PRESETS["Rainbow Raster Bars"]["code"]
        self._set_python_text(initial_code)
        self.action_transpile_code(silent=True)

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
        self.c64_logo_lbl.pack(side=tk.LEFT, padx=(0, 10))

        self.banner_label = tk.Label(self.top_bar, text="", justify=tk.LEFT, anchor="w")
        self.banner_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.header_right = tk.Frame(self.top_bar)
        self.header_right.pack(side=tk.RIGHT)

        self.btn_asm_focus = tk.Button(
            self.header_right,
            text="★ 6502 ASM IDE (^E)",
            command=self.action_toggle_asm_focus,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_asm_focus.pack(side=tk.LEFT, padx=3)

        self.btn_fullscreen = tk.Button(
            self.header_right,
            text="⛶ FULLSCREEN (F11)",
            command=self.action_toggle_fullscreen,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_fullscreen.pack(side=tk.LEFT, padx=3)

        self.theme_buttons: dict[str, tk.Button] = {}
        for t_name in ("Commodore 64", "C64 Phosphor"):
            btn = tk.Button(
                self.header_right,
                text=t_name.upper(),
                command=lambda n=t_name: self.apply_theme(n),
                relief=tk.FLAT,
                padx=6,
                pady=3,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=2)
            self.theme_buttons[t_name] = btn

        # 2. C64 Rainbow Color Divider Strip
        self.divider_canvas = tk.Canvas(self.studio_frame, height=7, highlightthickness=0, bd=0)
        self.divider_canvas.pack(fill=tk.X, padx=12, pady=(0, 6))

        # 3. 6-Column On-Screen C64 Menu & Command Deck
        self.menu_bar = tk.Frame(self.studio_frame, highlightthickness=1)
        self.menu_bar.pack(fill=tk.X, padx=12, pady=(0, 6))
        for col_i in range(6):
            self.menu_bar.columnconfigure(col_i, weight=1, uniform="menu_col")

        self.menu_buttons: dict[str, tk.Button] = {}
        self.menu_columns: dict[str, list[str]] = {
            "file": [],
            "build": [],
            "device": [],
            "sid": [],
            "gamedev": [],
            "help": [],
        }
        # last target file per game dev tool, so a rebuild is one click away
        self.gamedev_targets: dict[str, Path] = {}

        menu_spec = [
            (
                0,
                "file",
                "col-file",
                "menu-btn-file",
                "10 FILE & DISK",
                self.action_open_file,
                [
                    ("btn-open", "OPEN FILE     [F3]", self.action_open_file),
                    ("btn-new-asm", "NEW .ASM      [^N]", self.action_new_asm_template),
                    ("btn-save", "SAVE .ASM    [⇧F1]", self.action_save_assembly),
                    ("btn-decompile-disk", "DECOMP MEDIA  [F9]", self.action_decompile_media),
                    ("btn-export-tap", "EXPORT .TAP  [⇧F2]", self.action_export_tap),
                    ("btn-export-d64", "BUILD .D64   [⇧F9]", self.action_compile_d64),
                ],
            ),
            (
                1,
                "build",
                "col-build",
                "menu-btn-build",
                "20 BUILD & DMA",
                self.action_run_c64u,
                [
                    ("quick-btn-run", "▶ DMA RUN     [F5]", self.action_run_c64u),
                    ("btn-transpile", "PY → 6502     [F6]", self.action_transpile_code),
                    ("btn-assemble", "ASSEMBLE PRG  [F7]", self.action_assemble_prg),
                    ("btn-load-prg", "DMA LOAD RAM [⇧F3]", self.action_load_prg_only),
                    ("btn-focus-asm", "ASM IDE MODE  [^E]", self.action_toggle_asm_focus),
                    ("btn-find-bar", "FIND / GOTO   [^F]", self.action_focus_find),
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
                ],
            ),
            (
                3,
                "sid",
                "col-sid",
                "menu-btn-sid",
                "40 SID SYNTH",
                self.action_decompile_sid,
                [
                    ("btn-decompile-sid", "SID → ASM     [^D]", self.action_decompile_sid),
                    ("btn-compile-sid", "ASM → SID     [^B]", self.action_compile_sid),
                    ("btn-play-sid", "PLAY SID      [^P]", self.action_play_sid),
                ],
            ),
            (
                4,
                "gamedev",
                "col-gamedev",
                "menu-btn-gamedev",
                "50 GAME DEV",
                self.action_gamedev_sprites,
                [
                    ("btn-gd-sprites", "SPRITE BANK  [GEN]", self.action_gamedev_sprites),
                    ("btn-gd-tileset", "TILES + MAP  [GEN]", self.action_gamedev_tileset),
                    ("btn-gd-koala", "KOALA SCREEN [GEN]", self.action_gamedev_koala),
                    ("btn-gd-song", "SONG → SID   [GEN]", self.action_gamedev_song),
                    ("btn-gd-build", "BUILD GAME   [RUN]", self.action_gamedev_build),
                    ("btn-gd-c64sim", "C64 SCREEN   [SIM]", self.action_gamedev_c64sim),
                    ("btn-gd-sim", "SID PROFILE  [SIM]", self.action_gamedev_sim),
                    ("btn-gd-review", "OPEN REVIEW  [WEB]", self.action_gamedev_open_review),
                ],
            ),
            (
                5,
                "help",
                "col-help",
                "menu-btn-help",
                "60 HELP & INFO",
                self.action_show_help,
                [
                    ("btn-presets", "PRESET DEMOS  [F2]", self.action_open_presets),
                    ("btn-help", "GUIDE/CREDITS [F1]", self.action_show_help),
                    ("btn-kickass-ver", "KICKASS VER  [UPD]", self.action_check_kickass_version),
                    ("btn-replay-boot", "REPLAY BOOT  [C64]", self.action_replay_boot),
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

        self.left_title_lbl = tk.Label(
            self.left_hdr_bar,
            text="PYTHON SOURCE (MOS 6502 DIALECT)",
            anchor="w",
        )
        self.left_title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_py_to_asm = tk.Button(
            self.left_hdr_bar,
            text="TRANSPILE → ASM (F6)",
            command=self.action_transpile_code,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_py_to_asm.pack(side=tk.RIGHT)

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
            ("tab-asm", "1: 6502 ASSEMBLY (.ASM)"),
            ("tab-log", "2: BUILD & DMA LOG"),
            ("tab-ast", "3: AST & SYMBOLS"),
            ("tab-hw", "4: C64U HARDWARE"),
        ):
            tb = tk.Button(
                self.tab_bar,
                text=tab_title,
                command=lambda tid=tab_id: self.switch_tab(tid),
                relief=tk.FLAT,
                padx=8,
                pady=3,
                cursor="hand2",
            )
            tb.pack(side=tk.LEFT, padx=(0, 4))
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

        self.btn_asm_new = tk.Button(
            self.asm_toolbar,
            text="+ NEW .ASM",
            command=self.action_new_asm_template,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_asm_new.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_asm_save = tk.Button(
            self.asm_toolbar,
            text="💾 SAVE .ASM",
            command=self.action_save_assembly,
            relief=tk.FLAT,
            padx=6,
            pady=2,
            cursor="hand2",
        )
        self.btn_asm_save.pack(side=tk.LEFT, padx=(0, 4))

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

        # 5. Bottom Retro DMA & Tape Transfer Deck (Modeled on BackMeUpScotty)
        self.deck_frame = tk.Frame(self.studio_frame, padx=8, pady=4, highlightthickness=1)
        self.deck_frame.pack(fill=tk.X, padx=12, pady=(4, 8))

        self.deck_canvas = tk.Canvas(self.deck_frame, height=54, highlightthickness=0, bd=0)
        self.deck_canvas.pack(fill=tk.X)
        self.deck_canvas.bind("<Configure>", lambda _e: self.root.after_idle(self._draw_bottom_deck))

        self.status_row = tk.Frame(self.deck_frame)
        self.status_row.pack(fill=tk.X, pady=(2, 0))

        self.prompt_lbl = tk.Label(self.status_row, text="READY. █", anchor="w")
        self.prompt_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.credits_hint_lbl = tk.Label(
            self.status_row,
            text="[F1: GUIDE & CREDITS | F5: DMA RUN]",
            anchor="e",
        )
        self.credits_hint_lbl.pack(side=tk.RIGHT)

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
        if getattr(self, "_in_mainloop", False):
            self.check_bridge_status()
            self.check_kickass_version_startup()

    def action_replay_boot(self) -> None:
        """Replay the authentic C64 LOAD \"C64-BRIDGE\",8,1 boot animation."""
        self._start_boot_sequence()

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
        self.deck_frame.configure(highlightbackground=str(t["accent"]))

        self.banner_label.configure(
            text=str(t["boot_banner"]),
            font=f_banner,
            bg=str(t["paper"]),
            fg=str(t["ink"]),
        )

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

        # Style 6-Column Menu Deck
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
        self.btn_py_to_asm.configure(font=f_btn, bg=str(t["button_bg"]), fg=str(t["button_fg"]))

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
        for btn in (self.btn_asm_new, self.btn_asm_save, self.btn_asm_comment, self.btn_find_go, self.btn_clear_log):
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
        for pane in (self.pane_asm, self.pane_log, self.pane_ast, self.pane_hw):
            pane.pack_forget()
        if tab_id == "tab-asm":
            self.pane_asm.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-log":
            self.pane_log.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-ast":
            self.pane_ast.pack(fill=tk.BOTH, expand=True)
        elif tab_id == "tab-hw":
            self.pane_hw.pack(fill=tk.BOTH, expand=True)
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

            for pattern, tag in (
                (PY_KEYWORDS_PATTERN, "opcode"),
                (PY_INTRINSICS_PATTERN, "directive"),
                (ASM_HEX_PATTERN, "number"),
                (STRING_PATTERN, "string"),
                (PY_COMMENT_PATTERN, "comment"),
            ):
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
        self.file_mode = "asm"
        self.loaded_file = None
        self.last_asm = NEW_ASM_TEMPLATE
        self._set_asm_text(NEW_ASM_TEMPLATE)
        self.switch_tab("tab-asm")
        self._update_mode_badge()
        self._write_log("✓ Created new 6502 KickAssembler template in ASM Editor.")
        self.notify("NEW 6502 .ASM TEMPLATE READY")

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
        fname = self.loaded_file.name if self.loaded_file else ("UNTITLED.ASM" if self.file_mode == "asm" else "UNTITLED.PY")
        mode_str = "6502 ASM DIRECT" if self.file_mode == "asm" else "PYTHON → 6502"
        self.mode_badge_lbl.configure(text=f"[{mode_str} // {fname}]")

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
        self.root.bind("<F7>", lambda _e: self.action_assemble_prg())
        self.root.bind("<F8>", lambda _e: self.action_reset_c64u())
        self.root.bind("<F9>", lambda _e: self.action_decompile_media())
        self.root.bind("<F10>", lambda _e: self.action_focus_menu())
        self.root.bind("<F11>", lambda _e: self.action_toggle_fullscreen())

        self.root.bind("<Shift-F1>", lambda _e: self.action_save_assembly())
        self.root.bind("<Shift-F2>", lambda _e: self.action_export_tap())
        self.root.bind("<Shift-F3>", lambda _e: self.action_load_prg_only())
        self.root.bind("<Shift-F4>", lambda _e: self.action_pause_cpu())
        self.root.bind("<Shift-F5>", lambda _e: self.action_resume_cpu())
        self.root.bind("<Shift-F6>", lambda _e: self.action_dump_screen())
        self.root.bind("<Shift-F7>", lambda _e: self.action_reboot_c64u())
        self.root.bind("<Shift-F8>", lambda _e: self.action_quit())
        self.root.bind("<Shift-F9>", lambda _e: self.action_compile_d64())

        self.root.bind("<Control-s>", lambda _e: self.action_save_assembly())
        self.root.bind("<Control-t>", lambda _e: self.action_export_tap())
        self.root.bind("<Control-m>", lambda _e: self.action_compile_d64())
        self.root.bind("<Control-r>", lambda _e: self.action_reset_c64u())
        self.root.bind("<Control-d>", lambda _e: self.action_decompile_sid())
        self.root.bind("<Control-b>", lambda _e: self.action_compile_sid())
        self.root.bind("<Control-p>", lambda _e: self.action_play_sid())
        self.root.bind("<Control-e>", lambda _e: self.action_toggle_asm_focus())
        self.root.bind("<Control-n>", lambda _e: self.action_new_asm_template())
        self.root.bind("<Control-f>", lambda _e: self.action_focus_find())
        self.root.bind("<Control-g>", lambda _e: self.action_focus_find())
        self.root.bind("<Control-q>", lambda _e: self.action_quit())

        self.root.bind("<Alt-f>", lambda _e: self.action_focus_submenu("file"))
        self.root.bind("<Alt-b>", lambda _e: self.action_focus_submenu("build"))
        self.root.bind("<Alt-c>", lambda _e: self.action_focus_submenu("device"))
        self.root.bind("<Alt-s>", lambda _e: self.action_focus_submenu("sid"))
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
            "sid": "btn-decompile-sid",
            "gamedev": "btn-gd-sprites",
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
        """Navigate across the 6 displayed C64 menu columns using arrow keys."""
        if not self.focused_button_id:
            return
        cats = ["file", "build", "device", "sid", "gamedev", "help"]
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
                def _err():
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

    def action_transpile_code(self, silent: bool = False) -> None:
        """Transpile Python (MOS 6502 Dialect) source into 6502 Assembly."""
        source = self.py_text.get("1.0", "end-1c")
        if not source.strip():
            if not silent:
                self._write_log("No Python source code in LHS editor to transpile.")
                self.notify("PYTHON EDITOR IS EMPTY", severity="warning")
            return

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
        else:
            for err in result.errors:
                self._write_log(f"Error: {err}")
            if not silent:
                self.notify("TRANSPILATION FAILED", severity="error")

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

    def action_assemble_prg(self) -> None:
        """Assemble current 6502 assembly to a C64 .prg binary."""
        self._pulse_raster_border("ASSEMBLING 6502 → PRG BINARY", 450)
        asm_text = self.asm_text.get("1.0", "end-1c").strip()

        if self.file_mode == "py" and not asm_text:
            self.action_transpile_code()
            asm_text = self.asm_text.get("1.0", "end-1c").strip()

        if not asm_text:
            self.notify("NO 6502 ASSEMBLY TO COMPILE", severity="warning")
            return

        src_file = self.loaded_file
        if self.file_mode == "asm" and src_file and src_file.suffix.lower() in (".asm", ".s") and src_file.exists() and asm_text == self.last_asm.strip():
            target_asm = src_file
            out_prg = src_file.with_suffix(".prg")
            cleanup = False
        else:
            with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as tmp:
                tmp.write(asm_text.encode("utf-8"))
                target_asm = Path(tmp.name)
            out_prg = Path("./output.prg").resolve()
            cleanup = True

        self._write_log(f"Assembling {target_asm.name} → {out_prg.name} with KickAssembler...")
        comp_res = self.compiler.compile(target_asm, output_prg=out_prg, assembler="auto")

        if cleanup:
            try:
                target_asm.unlink(missing_ok=True)
            except Exception:
                pass

        if comp_res.success and out_prg.exists():
            self.last_prg_path = out_prg
            sz = out_prg.stat().st_size
            self._write_log(f"✓ Assembled {out_prg.name} ({sz} bytes)")
            self.notify(f"ASSEMBLED {out_prg.name} ({sz} BYTES)")
        else:
            err = comp_res.error_message or comp_res.stderr or comp_res.stdout
            self._write_log(f"Assembly Failed: {err}")
            self.notify("ASSEMBLY FAILED! CHECK LOG", severity="error")

    def action_run_c64u(self) -> None:
        """Assemble and DMA-execute on C64U hardware."""
        self._pulse_raster_border("DMA UPLOADING & EXECUTING ON C64U", 600)
        if self.file_mode == "py":
            self.action_transpile_code(silent=True)

        self.action_assemble_prg()
        if not self.last_prg_path or not self.last_prg_path.exists():
            return

        prg_path = self.last_prg_path
        sz = prg_path.stat().st_size
        self._write_log(f"DMA Uploading {prg_path.name} ({sz} bytes) to C64U at {self.client.base_url}...")

        def _dma_worker():
            try:
                dma_res = self.client.run_prg(prg_path)
                self.root.after(0, lambda: (
                    self._write_log(f"✓ DMA RUN Executed Successfully! Response: {dma_res}"),
                    self.notify(f"RUNNING ON C64U ({sz} BYTES)"),
                ))
            except Exception as exc:
                self.root.after(0, lambda: (
                    self._write_log(f"C64U DMA Run Error: {exc}"),
                    self.notify("DMA UPLOAD FAILED (C64U OFFLINE)", severity="warning"),
                ))

        threading.Thread(target=_dma_worker, daemon=True).start()

    def action_open_file(self) -> None:
        initial_dir = Path.cwd() / "game_dev" if (Path.cwd() / "game_dev").exists() else Path.cwd()
        modal = OpenFileModal(initial_path=initial_dir)
        modal.show_tk(self, lambda path: self.load_project_file(path) if path else None)

    def load_project_file(self, path: Path) -> None:
        """Load `.py`, `.asm`, `.s`, `.sid`, `.prg`, `.tap`, or `.d64` into the C64 studio."""
        if not path.exists():
            self.notify(f"FILE NOT FOUND: {path.name}", severity="error")
            return

        self._pulse_raster_border(f'LOADING "{path.name.upper()}",8,1', 420)
        ext = path.suffix.lower()

        if ext == ".py":
            self.file_mode = "py"
            self.loaded_file = path
            code = path.read_text(encoding="utf-8")
            self._set_python_text(code)
            self._update_mode_badge()
            self._write_log(f"✓ Loaded Python source: {path.name} ({path.stat().st_size} bytes)")
            self.notify(f'LOADED "{path.name.upper()}"')
            self.action_transpile_code(silent=True)

        elif ext in (".asm", ".s"):
            self.file_mode = "asm"
            self.loaded_file = path
            asm_content = path.read_text(encoding="utf-8")
            self.last_asm = asm_content
            self._set_asm_text(asm_content)
            self.switch_tab("tab-asm")
            self._update_mode_badge()
            self._write_log(
                f"✓ Loaded 6502 Assembly: {path.name} ({path.stat().st_size} bytes, {len(asm_content.splitlines())} lines)"
            )
            self.notify(f'LOADED "{path.name.upper()}" (6502 ASM MODE)')

            py_source = self._find_python_source_for_asm(path, asm_content)
            if py_source:
                self._set_python_text(py_source)
                self._write_log(f"ℹ Associated Python source loaded in LHS pane ({len(py_source.splitlines())} lines)")
            else:
                self._set_python_text("")
                self._write_log("ℹ Pure 6502 Assembly file loaded (LHS Python pane cleared; use Ctrl+E for Full ASM IDE)")

        elif ext == ".sid":
            self._load_sid_file(path)

        elif ext == ".d64":
            self.action_decompile_media(target_path=path)

        elif ext == ".prg":
            self.last_prg_path = path
            sz = path.stat().st_size
            self._write_log(f"Selected PRG binary: {path.name} ({sz} bytes)")
            try:
                res = self.client.run_prg(path)
                self._write_log(f"✓ DMA RUN Executed: {res}")
                self.notify(f"RUNNING {path.name.upper()} ON C64U")
            except Exception as exc:
                self._write_log(f"DMA Run Error: {exc} -- Opening PRG in 6502 Decompiler...")
                self.action_decompile_media(target_path=path)

        elif ext == ".tap":
            sz = path.stat().st_size
            self._write_log(f"Selected TAP Tape Image: {path.name} ({sz} bytes)")
            try:
                tap_info = read_tap_info(path.read_bytes())
                self._write_log(
                    f"✓ Valid TAP: {tap_info['signature']} v{tap_info['version']} ({tap_info['platform']} {tap_info['video']})"
                )
            except Exception as exc:
                self._write_log(f"TAP Header Warning: {exc}")
            self.action_decompile_media(target_path=path)

    def _find_python_source_for_asm(self, path: Path, asm_content: str) -> Optional[str]:
        py_sidecar = path.with_suffix(".py")
        if py_sidecar.is_file():
            try:
                return py_sidecar.read_text(encoding="utf-8")
            except Exception:
                pass

        for cand in (
            Path.cwd() / "examples" / f"{path.stem}.py",
            Path.cwd() / "game_dev" / f"{path.stem}.py",
            Path.cwd() / f"{path.stem}.py",
        ):
            if cand.resolve() != py_sidecar.resolve() and cand.is_file():
                try:
                    return cand.read_text(encoding="utf-8")
                except Exception:
                    pass

        stem_norm = path.stem.lower().replace("_", "").replace("-", "").replace(" ", "")
        for preset_name, preset_data in PRESETS.items():
            preset_norm = preset_name.lower().replace("_", "").replace("-", "").replace(" ", "")
            if stem_norm == preset_norm or (len(stem_norm) >= 4 and (stem_norm in preset_norm or preset_norm in stem_norm)):
                code = preset_data.get("code")
                if code:
                    return str(code)
        return None

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

    def action_decompile_media(self, target_path: Optional[Path] = None) -> None:
        """Show mandatory copyright & ethical use caution, then reverse-decompile D64/TAP/PRG."""
        if target_path is not None:
            caution = CopyrightCautionModal(filename=target_path.name)
            self._last_caution_modal = caution
            caution.show_tk(self, lambda ok: self._decompile_file_flow(target_path) if ok else self.notify("DECOMPILATION CANCELLED"))
            return

        caution = CopyrightCautionModal()
        self._last_caution_modal = caution

        def on_caution_ack(proceed: bool) -> None:
            if not proceed:
                self.notify("DECOMPILATION CANCELLED")
                return
            picker = OpenFileModal(initial_path=Path.cwd())
            self._last_open_modal = picker
            picker.show_tk(self, lambda p: self._decompile_file_flow(p) if (p and p.is_file()) else None)

        caution.show_tk(self, on_caution_ack)

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

    def action_decompile_sid(self) -> None:
        picker = OpenFileModal(initial_path=Path.cwd())
        picker.show_tk(
            self,
            lambda p: self._load_sid_file(p)
            if (p and p.suffix.lower() == ".sid")
            else (self.notify("SELECT A .SID FILE", severity="warning") if p else None),
        )

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
        except Exception as exc:
            self._write_log(f"SID compilation failed: {exc}")
            self.notify(f"SID COMPILE FAILED: {exc}", severity="error")

    def action_play_sid(self) -> None:
        if self.last_sid_path and self.last_sid_path.is_file():
            self._play_sid_worker(self.last_sid_path)
            return
        picker = OpenFileModal(initial_path=Path.cwd())

        def on_picked(p: Optional[Path]):
            if p and p.suffix.lower() == ".sid":
                self.last_sid_path = p
                self._play_sid_worker(p)
            elif p:
                self.notify("SELECT A .SID FILE", severity="warning")

        picker.show_tk(self, on_picked)

    def _play_sid_worker(self, path: Path) -> None:
        self._pulse_raster_border(f"UPLOADING SID: {path.name.upper()}", 480)
        try:
            res = self.client.play_sid(path)
            self._write_log(f"✓ Playing {path.name} on C64U SID Player: {res}")
            self.notify(f"PLAYING {path.name.upper()} ON C64U")
        except Exception as exc:
            self._write_log(f"C64U SID playback failed: {exc}")
            self.notify(f"SID PLAYBACK FAILED: {exc}", severity="error")

    # -----------------------------------------------------------------------
    # Game Dev: sprite banks, tilesets, Koala screens, SID songs, game builds,
    # headless C64 screenshots, 6502 profiling
    # -----------------------------------------------------------------------

    def action_gamedev_sprites(self) -> None:
        self._pick_and_run_game_tool("sprites")

    def action_gamedev_tileset(self) -> None:
        self._pick_and_run_game_tool("tileset")

    def action_gamedev_koala(self) -> None:
        self._pick_and_run_game_tool("koala")

    def action_gamedev_build(self) -> None:
        self._pick_and_run_game_tool("build")

    def action_gamedev_c64sim(self) -> None:
        self._pick_and_run_game_tool("c64sim")

    def action_gamedev_song(self) -> None:
        self._pick_and_run_game_tool("song")

    def action_gamedev_sim(self) -> None:
        self._pick_and_run_game_tool("sim")

    def action_gamedev_open_review(self) -> None:
        picker = OpenFileModal(initial_path=default_target_dir())

        def on_picked(p: Optional[Path]):
            if p and p.suffix.lower() in {".html", ".htm"}:
                self._open_review_page(p)
            elif p:
                self.notify("SELECT A REVIEW .HTML PAGE", severity="warning")

        picker.show_tk(self, on_picked)

    def _pick_and_run_game_tool(self, key: str) -> None:
        """Ask for the tool's target file (starting from the last one used), then run the tool."""
        tool = GAME_TOOLS[key]
        last = self.gamedev_targets.get(key)
        picker = OpenFileModal(initial_path=last.parent if last else default_target_dir())

        def on_picked(p: Optional[Path]):
            if not p:
                return
            if p.suffix.lower() not in tool.suffixes:
                self.notify(f"{tool.label}: SELECT A {' / '.join(s.upper() for s in tool.suffixes)} FILE",
                            severity="warning")
                return
            self.gamedev_targets[key] = p
            self._run_game_tool(key, p)

        picker.show_tk(self, on_picked)

    def _run_game_tool(self, key: str, target: Path) -> None:
        tool = GAME_TOOLS[key]
        self._pulse_raster_border(f"{tool.label}: {target.name.upper()}", 600)
        self._write_log(f"▶ {tool.label}: {target}")

        def _worker():
            result = run_tool(key, target)
            prg = result.first(".prg") if result.ok and tool.run_result else None
            run_note = ""
            if prg:
                try:
                    self.client.run_prg(prg)
                    run_note = f"✓ Running {prg.name} on the C64U"
                except Exception as exc:
                    run_note = f"ℹ Built {prg.name}; C64U not reachable ({exc})"

            def _done():
                if not self.root.winfo_exists():
                    return
                for line in result.output.splitlines():
                    self._write_log(f"  {line}")
                if not result.ok:
                    self._write_log(f"✗ {tool.label} failed")
                    self.notify(f"{tool.label} FAILED", severity="error")
                    return
                self._write_log(f"✓ {tool.label} done")
                self.notify(f"{tool.label} DONE: {target.name.upper()}")
                sid = result.first(".sid")
                if sid:
                    self.last_sid_path = sid
                    self._write_log(f"  PLAY SID [^P] now plays {sid.name} on the C64U")
                if prg:
                    self.last_prg_path = prg
                    self._write_log(f"  {run_note}")
                page = result.first(".html") or result.first(".png")
                if page:
                    self._open_review_page(page)

            try:
                self.root.after(0, _done)
            except (tk.TclError, RuntimeError):
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _open_review_page(self, page: Path) -> None:
        try:
            webbrowser.open(page.resolve().as_uri())
            self._write_log(f"  Opened review page {page.name}")
        except Exception as exc:
            self._write_log(f"Could not open {page}: {exc}")

    # -----------------------------------------------------------------------
    # Save ASM, Export TAP, Compile D64, Hardware Controls & Modals
    # -----------------------------------------------------------------------

    def action_save_assembly(self) -> None:
        current_text = self.asm_text.get("1.0", "end-1c") or self.last_asm
        if not current_text.strip():
            self.notify("NO 6502 ASSEMBLY TO SAVE", severity="warning")
            return
        out_file = self.loaded_file if (self.file_mode == "asm" and self.loaded_file) else Path("./output.asm").resolve()
        out_file.write_text(current_text, encoding="utf-8")
        self.last_asm = current_text
        self._write_log(f"✓ Saved 6502 assembly to {out_file}")
        self.notify(f'SAVED "{out_file.name.upper()}"')

    def action_export_tap(self) -> None:
        """Assemble and export to a C64-TAPE-RAW v1 .tap cassette image."""
        self._pulse_raster_border("MASTERING .TAP CASSETTE IMAGE", 480)
        self.action_assemble_prg()
        if not self.last_prg_path or not self.last_prg_path.exists():
            return
        out_tap = (
            self.loaded_file.with_suffix(".tap")
            if (self.file_mode == "asm" and self.loaded_file)
            else Path("./output.tap").resolve()
        )
        tape_name = self.loaded_file.stem if self.loaded_file else "OUTPUT"
        try:
            save_prg_to_tap(self.last_prg_path, tap_path=out_tap, tape_name=tape_name)
            sz = out_tap.stat().st_size
            self._write_log(f"✓ TAP Cassette Image Generated: {out_tap} ({sz} bytes)")
            self.notify(f"EXPORTED {out_tap.name.upper()} ({sz} BYTES)")
        except Exception as exc:
            self._write_log(f"TAP Export Error: {exc}")
            self.notify(f"TAP EXPORT ERROR: {exc}", severity="error")

    def action_compile_d64(self) -> None:
        """Assemble and package into a standard 35-track 1541 .d64 disk image."""
        self._pulse_raster_border("FORMATTING & WRITING 1541 .D64 DISK", 500)
        self.action_assemble_prg()
        if not self.last_prg_path or not self.last_prg_path.exists():
            return
        out_d64 = (
            self.loaded_file.with_suffix(".d64")
            if (self.file_mode == "asm" and self.loaded_file)
            else Path("./output.d64").resolve()
        )
        disk_name = (self.loaded_file.stem if self.loaded_file else "OUTPUT").upper()[:16]
        try:
            save_prg_to_d64(self.last_prg_path, d64_path=out_d64, disk_name=disk_name)
            sz = out_d64.stat().st_size
            self._write_log(f"✓ 1541 D64 Disk Image Generated: {out_d64} ({sz} bytes)")
            self.notify(f"COMPILED {out_d64.name.upper()} ({sz} BYTES)")
        except Exception as exc:
            self._write_log(f"D64 Packaging Error: {exc}")
            self.notify(f"D64 EXPORT ERROR: {exc}", severity="error")

    def action_load_prg_only(self) -> None:
        if not self.last_prg_path or not self.last_prg_path.exists():
            self.action_assemble_prg()
        if not self.last_prg_path or not self.last_prg_path.exists():
            return
        try:
            res = self.client.load_prg(self.last_prg_path)
            self._write_log(f"✓ PRG Loaded into C64 RAM: {res}")
            self.notify("PRG LOADED INTO C64 RAM")
        except Exception as exc:
            self._write_log(f"DMA Load Error: {exc}")
            self.notify(f"DMA LOAD FAILED: {exc}", severity="error")

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
                self.file_mode = "py"
                self.loaded_file = None
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
            "• Ctrl+S / ⇧F1  : Save Current 6502 Assembly Source\n"
            "• Ctrl+/        : Comment / Uncomment Selected 6502 Assembly Lines\n"
            "• Ctrl+F / ^G   : Find Text, Label, or Jump to Line Number\n"
            "• Label Outline : Click any label/subroutine in the left outline to jump instantly\n\n"
            "FUNCTION KEY & STUDIO SHORTCUTS\n"
            "============================================================\n"
            "• F1            : Open Reference Guide & Credits\n"
            "• F2            : Load Built-in C64 Preset Demos\n"
            "• F3            : Open Project File Browser (.asm, .py, .d64, .tap, .prg, .sid)\n"
            "• F4            : Refresh / Ping C64U Network Connection\n"
            "• F5            : Assemble & DMA Run Immediately on C64U Hardware\n"
            "• F6            : Transpile Python (6502 Dialect) to 6502 Assembly\n"
            "• F7            : Assemble to C64 .PRG Binary (KickAssembler / ACME)\n"
            "• F8            : Soft Reset C64U Machine\n"
            "• F9            : Reverse-Decompile .D64 / .TAP / .PRG (with Copyright Notice)\n"
            "• F10 / Alt+Key : Focus On-Screen Menu Bar (Navigate with Arrow Keys)\n"
            "• F11           : Toggle Fullscreen C64 Monitor Mode\n"
            "• Shift+F2 / ^T : Master & Export .TAP Cassette Tape Image\n"
            "• Shift+F9 / ^M : Compile & Package 1541 .D64 Floppy Disk Image\n"
            "• Ctrl+D/B/P    : Decompile SID (^D), Compile SID (^B), Play SID on C64U (^P)\n"
            "• Alt+G         : Game Dev menu (tools from the repository's tools/ folder)\n"
            + "".join(f"    {t.label:<16}: {t.describe}\n" for t in GAME_TOOLS.values())
            + "    OPEN REVIEW     : Open a generated review page in your web browser\n"
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


def main() -> None:
    """Entry point for `c64u-bridge tui`, `c64u-py2asm`, and standalone execution."""
    skip_boot = "--no-boot" in sys.argv
    app = C64PythonToAsmApp(skip_boot=skip_boot, start_maximized=True)
    app.run()


if __name__ == "__main__":
    main()
