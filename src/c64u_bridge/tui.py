"""
Textual TUI for Commodore 64 Python-to-Assembly Transpiler, SID decompiler & Bridge.
Provides an interactive retro-styled IDE for writing 6502-targeted Python code,
transpiling to assembly, compiling to .prg, and DMA-deploying directly to the C64U.
"""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path
from typing import Iterable, Optional

from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)
from textual.widgets.option_list import Option

from .client import C64UClient, C64UClientError
from .compiler import CrossCompiler
from .screen import format_screen
from .sid_compiler import SidCompileError, compile_sid_source
from .sid_decompiler import SidDecompileError, decompile_sid_file
from .transpiler import PRESETS, PythonTo6502Transpiler, TranspileOptions, TranspileResult


C64_CSS = """
Screen {
    background: #0d1117;
    color: #e6edf3;
}

Header {
    background: #1f244a;
    color: #70a4b2;
    dock: top;
    text-style: bold;
}

Footer {
    background: #161b22;
    color: #8b949e;
}

#menu-bar {
    height: 1;
    background: #161b36;
    padding: 0 1;
    border-bottom: solid #352879;
}

.menu-bar-btn {
    height: 1;
    min-width: 8;
    border: none;
    background: #161b36;
    color: #e6edf3;
    padding: 0 1;
    margin-right: 1;
}

.menu-bar-btn:hover {
    background: #352879;
    color: #ffffff;
    text-style: bold;
}

.menu-bar-btn:focus {
    background: #4b3ba6;
    color: #ffffff;
}

.quick-run-btn {
    height: 1;
    min-width: 10;
    border: none;
    background: #238636;
    color: #ffffff;
    text-style: bold;
    padding: 0 1;
    margin-right: 1;
}

.quick-run-btn:hover {
    background: #2ea043;
}

.quick-reset-btn {
    height: 1;
    min-width: 10;
    border: none;
    background: #d97706;
    color: #ffffff;
    text-style: bold;
    padding: 0 1;
    margin-right: 1;
}

.quick-reset-btn:hover {
    background: #f59e0b;
}

#bridge-status {
    width: 28;
    content-align: right middle;
    text-style: bold;
    color: #8b949e;
    margin-left: 1;
}

/* Tiered Menu Dropdown Overlay */
MenuDropdownModal {
    background: rgba(0, 0, 0, 0.25);
    align: left top;
}

#menu-dropdown-box {
    width: 44;
    height: auto;
    background: #161b36;
    border: heavy #70a4b2;
    padding: 0;
}

#menu-dropdown-title {
    background: #1f244a;
    color: #b8c76f;
    text-style: bold;
    padding: 0 1;
    height: 1;
    text-align: center;
}

#menu-dropdown-options {
    height: auto;
    max-height: 14;
    background: #161b36;
    border: none;
    padding: 0;
}

#main-container {
    height: 1fr;
}

#left-column {
    width: 50%;
    border-right: solid #352879;
    padding: 0 1;
}

#right-column {
    width: 50%;
    padding: 0 1;
}

.pane-title {
    text-style: bold;
    color: #70a4b2;
    padding: 0 1;
    background: #161b36;
    height: 1;
}

#python-editor {
    height: 1fr;
    border: solid #21262d;
}

#asm-viewer {
    height: 1fr;
    border: solid #21262d;
}

#build-log {
    height: 1fr;
    background: #0d1117;
    border: solid #21262d;
}

#ast-tree {
    height: 1fr;
    background: #0d1117;
    border: solid #21262d;
}

.hardware-card {
    background: #161b36;
    border: solid #352879;
    padding: 1;
    margin-bottom: 1;
}

.hardware-card Label {
    color: #70a4b2;
    text-style: bold;
    margin-bottom: 1;
}

.hw-row {
    height: 3;
    align: left middle;
    margin-bottom: 1;
}

.hw-row Button {
    margin-right: 1;
}

/* Modals */
PresetModal, HelpModal, OpenFileModal {
    align: center middle;
}

#dialog {
    width: 80;
    height: 32;
    background: #161b36;
    border: heavy #70a4b2;
    padding: 1 2;
}

#open-dialog {
    width: 86;
    height: 32;
    background: #161b36;
    border: heavy #70a4b2;
    padding: 1 2;
}

#quick-jump-bar {
    height: 3;
    margin-bottom: 1;
    align: center middle;
}

.btn-jump {
    margin-right: 1;
    background: #21262d;
    color: #70a4b2;
    min-width: 16;
    height: 1;
    border: none;
}

.btn-jump:hover {
    background: #352879;
    color: #ffffff;
}

#file-tree {
    height: 16;
    background: #0d1117;
    border: solid #21262d;
    margin-bottom: 1;
}

#lbl-file-preview {
    height: 2;
    color: #8b949e;
    text-align: center;
    margin-bottom: 1;
}

#dialog-buttons {
    height: 3;
    align: right middle;
}

#dialog-buttons Button {
    margin-left: 1;
}

#dialog-title {
    text-style: bold;
    color: #b8c76f;
    text-align: center;
    margin-bottom: 1;
}

#preset-list {
    height: 18;
    background: #0d1117;
    margin-bottom: 1;
}

#dialog-close {
    width: 100%;
}
"""


class PresetModal(ModalScreen[Optional[str]]):
    """Modal dialog allowing selection of ready-to-run C64 demo programs."""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(" Commodore 64 Python Examples & Demos ", id="dialog-title")
            options = [
                Option(f"{name} - {data['description'][:50]}...", id=name)
                for name, data in PRESETS.items()
            ]
            yield OptionList(*options, id="preset-list")
            with Horizontal():
                yield Button("Load Selected", variant="success", id="btn-load-preset")
                yield Button("Cancel", variant="error", id="btn-cancel-preset")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-load-preset":
            opt_list = self.query_one(OptionList)
            if opt_list.highlighted is not None:
                selected_opt = opt_list.get_option_at_index(opt_list.highlighted)
                preset_key = str(selected_opt.id)
                self.dismiss(PRESETS.get(preset_key, {}).get("code"))
            else:
                self.dismiss(None)
        else:
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        preset_key = str(event.option.id)
        self.dismiss(PRESETS.get(preset_key, {}).get("code"))


class HelpModal(ModalScreen[None]):
    """Modal dialog with 6502 Python dialect documentation and keyboard shortcuts."""

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(" C64 Python-to-Assembly Reference & Guide ", id="dialog-title")
            with VerticalScroll():
                help_text = (
                    "[bold cyan]Supported Python Dialect & Intrinsics:[/]\n"
                    "• [yellow]poke(addr, val)[/]: Store byte directly to memory address\n"
                    "• [yellow]peek(addr)[/]: Read byte from memory address\n"
                    "• [yellow]border_color(c)[/]: Set VIC-II border ($D020)\n"
                    "• [yellow]background_color(c)[/]: Set VIC-II background ($D021)\n"
                    "• [yellow]wait_raster(line)[/]: Synchronize with raster beam ($D012)\n"
                    "• [yellow]clear_screen(char, color)[/]: Clear screen ($0400) and color ($D800) RAM\n"
                    "• [yellow]print_str(\"text\")[/]: Print string via KERNAL CHROUT ($FFD2)\n"
                    "• [yellow]print_char(c)[/]: Print single PETSCII character\n"
                    "• [yellow]sid_tone(freq, wave, ad, sr)[/]: Configure SID Voice 1\n"
                    "• [yellow]delay(cycles)[/]: Delay loop using X/Y registers\n"
                    "• [yellow]asm(\"...\")[/]: Verbatim inline 6502 assembly\n\n"
                    "[bold cyan]SID Reverse Decompiler:[/]\n"
                    "• Open a [yellow].sid[/] file or press [bold white]Ctrl+D[/] to import PSID/RSID music.\n"
                    "• Reachable init/play code becomes annotated 6502 assembly.\n"
                    "• Tables and uncertain bytes remain exact .byte data.\n"
                    "• Sidecars are written as *_decompiled.asm and *_decompiled.py.\n\n"
                    "[bold cyan]C64U SID Playback:[/]\n"
                    "• Press [bold white]Ctrl+P[/] or use Play SID to upload the selected tune.\n"
                    "• Playback uses the Ultimate firmware's built-in SID player.\n\n"
                    "[bold cyan]SID Compiler:[/]\n"
                    "• Press [bold white]Ctrl+B[/] to rebuild the loaded decompiled source as SID.\n"
                    "• Original PSID/RSID metadata and embedded load-address form are preserved.\n\n"
                    "[bold cyan]Control Flow & Statements:[/]\n"
                    "• [green]while cond:[/], [green]while True:[/], [green]break[/], [green]continue[/]\n"
                    "• [green]for i in range(stop):[/] or [green]for i in range(start, stop, step):[/]\n"
                    "• [green]if cond:[/], [green]elif cond:[/], [green]else:[/]\n"
                    "• Functions: [green]def my_sub():[/] compiled to subroutine with [green]rts[/]\n\n"
                    "[bold cyan]Tiered Menu Bar & Navigation:[/]\n"
                    "• [bold white]F10[/] or click any top-level menu ([yellow]File ▾[/], [yellow]Build ▾[/], [yellow]C64 Device ▾[/], [yellow]SID Audio ▾[/], [yellow]Help ▾[/])\n"
                    "• [bold white]Alt+F[/]: File Menu | [bold white]Alt+B[/]: Build Menu | [bold white]Alt+C[/]: Device Menu\n"
                    "• [bold white]Alt+S[/]: SID Menu  | [bold white]Alt+H[/]: Help Menu\n"
                    "• [bold white]Left / Right Arrow[/]: Glide between adjacent top-level menus\n"
                    "• [bold white]Escape[/]: Dismiss open menu dropdown\n\n"
                    "[bold cyan]Function Key Shortcuts (F1 - F8):[/]\n"
                    "• [bold white]F1[/]: Open this Reference Guide & Help\n"
                    "• [bold white]F2[/]: Open Preset 6502 Demos\n"
                    "• [bold white]F3[/]: Open File Browser (game_dev/, examples/)\n"
                    "• [bold white]F4[/]: Refresh C64U Connection Reachability\n"
                    "• [bold white]F5[/]: Run on C64U (Transpile/Assemble + DMA Run)\n"
                    "• [bold white]F6[/]: Transpile Python to 6502 Assembly\n"
                    "• [bold white]F7[/]: Assemble to C64 PRG binary\n"
                    "• [bold white]F8[/]: Soft Reset C64U Machine\n\n"
                    "[bold cyan]Shift Key & Ctrl Key Commands:[/]\n"
                    "• [bold white]↑F1 (Shift+F1) / Ctrl+S[/]: Save Current Assembly\n"
                    "• [bold white]↑F2 (Shift+F2) / Ctrl+T[/]: Export to TAP Cassette Tape Image (.tap)\n"
                    "• [bold white]↑F3 (Shift+F3)[/]: DMA Load PRG into RAM (without running)\n"
                    "• [bold white]↑F4 (Shift+F4)[/]: Pause 6510 CPU via DMA\n"
                    "• [bold white]↑F5 (Shift+F5)[/]: Resume 6510 CPU via DMA\n"
                    "• [bold white]↑F6 (Shift+F6)[/]: Dump C64 Screen Memory ($0400-$07E7)\n"
                    "• [bold white]↑F7 (Shift+F7)[/]: Hard Reboot C64U (with cartridge re-init)\n"
                    "• [bold white]↑F8 (Shift+F8) / Ctrl+Q[/]: Exit Application\n\n"
                    "[bold cyan]Cassette Tape (.TAP) & Ultimate 64 Support:[/]\n"
                    "• Standard C64-TAPE-RAW v1 format with PAL timing, 192-byte header, and checksums.\n"
                    "• Fully compatible with Ultimate 64 Tape Player, emulators (VICE), and real Datassettes.\n"
                    "• On Ultimate 64: Place .tap on USB/SD and select Play Tape from the U64 menu.\n"
                )
                yield Static(help_text)
            yield Button("Close", variant="primary", id="dialog-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class FilteredDirectoryTree(DirectoryTree):
    """Directory tree filtered for Commodore 64 source code and binary assets."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
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
        supported = {".py", ".asm", ".s", ".sid", ".prg", ".tap", ".c", ".h", ".sym", ".bin"}
        filtered = []
        for p in paths:
            if p.name in ignored or p.name.startswith("."):
                continue
            if p.is_dir() or p.suffix.lower() in supported:
                filtered.append(p)
        return filtered


class OpenFileModal(ModalScreen[Optional[Path]]):
    """Modal dialog allowing selection and browsing of project files (.py, .asm, .prg)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, initial_path: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        self.current_root = initial_path or Path.cwd()
        self.selected_file: Optional[Path] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="open-dialog"):
            yield Label(" Commodore 64 Project File Browser ", id="dialog-title")
            with Horizontal(id="quick-jump-bar"):
                yield Button("📂 game_dev/", id="jump-game-dev", classes="btn-jump")
                yield Button("📂 examples/", id="jump-examples", classes="btn-jump")
                yield Button("📂 Workspace Root", id="jump-root", classes="btn-jump")

            tree = FilteredDirectoryTree(str(self.current_root), id="file-tree")
            yield tree
            yield Label("Select source, SID music, or a C64 binary to open/import", id="lbl-file-preview")
            with Horizontal(id="dialog-buttons"):
                yield Button("Open / Run Selected", variant="success", id="btn-open-file")
                yield Button("Cancel", variant="error", id="btn-cancel-open")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        tree = self.query_one("#file-tree", FilteredDirectoryTree)
        preview = self.query_one("#lbl-file-preview", Label)

        if btn_id == "jump-game-dev":
            gd = Path.cwd() / "game_dev"
            if gd.exists():
                tree.path = gd
                preview.update("Browsing: game_dev/")
        elif btn_id == "jump-examples":
            ex = Path.cwd() / "examples"
            if ex.exists():
                tree.path = ex
                preview.update("Browsing: examples/")
        elif btn_id == "jump-root":
            tree.path = Path.cwd()
            preview.update("Browsing workspace root")
        elif btn_id == "btn-open-file":
            selected = self.selected_file
            if not selected and tree.cursor_node and tree.cursor_node.data:
                node_path = getattr(tree.cursor_node.data, "path", None)
                if node_path and isinstance(node_path, Path) and node_path.is_file():
                    selected = node_path
            if selected and selected.is_file():
                self.dismiss(selected)
            else:
                self.notify("Please select a file to open", severity="warning")
        elif btn_id == "btn-cancel-open":
            self.dismiss(None)

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        self.selected_file = event.path
        self.dismiss(event.path)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.node and event.node.data:
            path = getattr(event.node.data, "path", None)
            if path and isinstance(path, Path) and path.is_file():
                self.selected_file = path
                size = path.stat().st_size
                ext = path.suffix.lower()
                desc = (
                    "Python Dialect Script"
                    if ext == ".py"
                    else (
                        "6502 Assembly Source"
                        if ext in [".asm", ".s"]
                        else (
                            "PSID/RSID Music (reverse decompile)"
                            if ext == ".sid"
                            else (
                                "C64 Executable Binary (PRG)"
                                if ext == ".prg"
                                else ("C64 Cassette Tape Image (TAP)" if ext == ".tap" else "File")
                            )
                        )
                    )
                )
                self.query_one("#lbl-file-preview", Label).update(
                    f"[bold green]Selected:[/] {path.name} ({size} bytes) - [cyan]{desc}[/]"
                )


MENU_DEFINITIONS: dict[str, dict[str, object]] = {
    "file": {
        "title": "📁 File (cursor keys navigate)",
        "offset": 1,
        "items": [
            ("📂 Open File...", "open_file", "F3"),
            ("💾 Save ASM Source", "save_assembly", "⇧+F1"),
            ("📼 Export Cassette Tape Image", "export_tap", "⇧+F2"),
            ("────────────────────────────────────", "", None),
            ("🚪 Quit Studio", "quit", "⇧+F8"),
        ],
    },
    "build": {
        "title": "⚙  Build & Run",
        "offset": 12,
        "items": [
            ("⚡ DMA Run (Assemble & Exec)", "run_c64u", "F5"),
            ("⚙  Transpile Python → 6502", "transpile_code", "F6"),
            ("🔨 Assemble to PRG (KickAss)", "assemble_prg", "F7"),
            ("📥 DMA Load to RAM (No Exec)", "load_prg_only", "⇧+F3"),
        ],
    },
    "device": {
        "title": "🕹  C64 Device",
        "offset": 24,
        "items": [
            ("🔄 Refresh / Ping Connection", "refresh_connection", "F4"),
            ("🔁 Soft Reset C64", "reset_c64u", "F8"),
            ("⏸  Pause CPU", "pause_cpu", "⇧+F4"),
            (" ▶ Resume CPU", "resume_cpu", "⇧+F5"),
            ("📺 Inspect Screen Dump", "dump_screen", "⇧+F6"),
            ("────────────────────────────────────", "", None),
            ("💥 Cold Reboot Hardware", "reboot_c64u", "⇧+F7"),
        ],
    },
    "sid": {
        "title": "🎵 SID Audio",
        "offset": 43,
        "items": [
            ("🎵 SID → ASM + Python", "decompile_sid", "^D"),
            ("🎵 ASM → SID Compile", "compile_sid", "^B"),
            ("🎵 Play SID on Hardware", "play_sid", "^P"),
        ],
    },
    "help": {
        "title": "❓ Help",
        "offset": 58,
        "items": [
            ("📚 Preset Examples & Demos", "open_presets", "F2"),
            ("❓ Reference Guide & Help", "show_help", "F1"),
        ],
    },
}


class MenuDropdownModal(ModalScreen[Optional[str]]):
    """Dropdown overlay for tiered top-level menus."""

    BINDINGS = [
        Binding("escape", "dismiss_menu", "Close", show=False),
        Binding("left", "menu_prev", "Previous Menu", show=False),
        Binding("right", "menu_next", "Next Menu", show=False),
    ]

    def __init__(self, category: str = "file", **kwargs) -> None:
        super().__init__(**kwargs)
        self.category = category if category in MENU_DEFINITIONS else "file"

    def compose(self) -> ComposeResult:
        menu = MENU_DEFINITIONS[self.category]
        with Vertical(id="menu-dropdown-box"):
            yield Static(menu["title"], id="menu-dropdown-title")
            options = self._build_options(self.category)
            yield OptionList(*options, id="menu-dropdown-options")

    def _build_options(self, category: str) -> list[Option]:
        menu = MENU_DEFINITIONS[category]
        options: list[Option] = []
        for idx, (label, action_id, shortcut) in enumerate(menu["items"]):
            if not action_id:
                options.append(Option(label, id=f"sep_{idx}", disabled=True))
            else:
                pad = 34 - len(label) - (len(shortcut) if shortcut else 0)
                if pad < 2:
                    pad = 2
                text = f"{label}{' ' * pad}[cyan]{shortcut}[/]" if shortcut else label
                options.append(Option(text, id=action_id))
        return options

    def on_mount(self) -> None:
        self._position_menu(self.category)

    def _position_menu(self, category: str) -> None:
        menu = MENU_DEFINITIONS[category]
        box = self.query_one("#menu-dropdown-box")
        max_offset = max(1, self.app.size.width - 46)
        actual_offset = min(menu["offset"], max_offset)
        box.styles.margin = (2, 0, 0, actual_offset)

    def switch_to_category(self, new_category: str) -> None:
        if new_category not in MENU_DEFINITIONS or new_category == self.category:
            return
        self.category = new_category
        menu = MENU_DEFINITIONS[self.category]
        self.query_one("#menu-dropdown-title", Static).update(menu["title"])
        self._position_menu(self.category)

        opt_list = self.query_one("#menu-dropdown-options", OptionList)
        opt_list.clear_options()
        for opt in self._build_options(self.category):
            opt_list.add_option(opt)
        opt_list.highlighted = 0

    def action_menu_prev(self) -> None:
        cats = list(MENU_DEFINITIONS.keys())
        idx = cats.index(self.category)
        new_cat = cats[(idx - 1) % len(cats)]
        self.switch_to_category(new_cat)

    def action_menu_next(self) -> None:
        cats = list(MENU_DEFINITIONS.keys())
        idx = cats.index(self.category)
        new_cat = cats[(idx + 1) % len(cats)]
        self.switch_to_category(new_cat)

    def action_dismiss_menu(self) -> None:
        self.dismiss(None)

    def on_click(self, event: events.Click) -> None:
        if event.screen_y == 1:
            x = event.screen_x
            if 0 <= x < 11:
                self.switch_to_category("file")
                return
            elif 11 <= x < 23:
                self.switch_to_category("build")
                return
            elif 23 <= x < 40:
                self.switch_to_category("device")
                return
            elif 40 <= x < 55:
                self.switch_to_category("sid")
                return
            elif 55 <= x < 70:
                self.switch_to_category("help")
                return

        box = self.query_one("#menu-dropdown-box")
        if not box.region.contains(event.screen_x, event.screen_y):
            self.dismiss(None)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        action_id = str(event.option.id)
        if not action_id.startswith("sep_"):
            self.dismiss(action_id)


class C64PythonToAsmApp(App):
    """Textual TUI for Commodore 64 Python development and C64U execution."""

    CSS = C64_CSS
    TITLE = "C64U Python-to-Assembly Studio"
    SUB_TITLE = "6502 Cross-Transpiler & DMA Hardware Bridge"

    BINDINGS = [
        Binding("f1", "show_help", "Help", show=True),
        Binding("f2", "open_presets", "Presets", show=False),
        Binding("f3", "open_file", "Open", show=True),
        Binding("f4", "refresh_connection", "Refresh", show=False),
        Binding("f5", "run_c64u", "Run C64U", show=True),
        Binding("f6", "transpile_code", "Transpile", show=False),
        Binding("f7", "assemble_prg", "Assemble", show=False),
        Binding("f8", "reset_c64u", "Reset C64U", show=True),
        Binding("f10", "open_menu_category('file')", "Menu Bar", show=True),
        Binding("shift+f1", "save_assembly", "Save ASM", show=False),
        Binding("shift+f2", "export_tap", "Export TAP", show=False),
        Binding("shift+f3", "load_prg_only", "Load PRG", show=False),
        Binding("shift+f4", "pause_cpu", "Pause CPU", show=False),
        Binding("shift+f5", "resume_cpu", "Resume CPU", show=False),
        Binding("shift+f6", "dump_screen", "Screen Dump", show=False),
        Binding("shift+f7", "reboot_c64u", "Reboot C64U", show=False),
        Binding("shift+f8", "quit", "Quit", show=False),
        Binding("ctrl+s", "save_assembly", "Save ASM", show=False),
        Binding("ctrl+t", "export_tap", "Export TAP", show=False),
        Binding("ctrl+r", "reset_c64u", "Reset C64U", show=False),
        Binding("ctrl+d", "decompile_sid", "Decompile SID", show=False),
        Binding("ctrl+b", "compile_sid", "Compile SID", show=False),
        Binding("ctrl+p", "play_sid", "Play SID", show=False),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("alt+f", "open_menu_category('file')", "File", show=False),
        Binding("alt+b", "open_menu_category('build')", "Build", show=False),
        Binding("alt+c", "open_menu_category('device')", "Device", show=False),
        Binding("alt+s", "open_menu_category('sid')", "SID", show=False),
        Binding("alt+h", "open_menu_category('help')", "Help", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transpiler = PythonTo6502Transpiler()
        self.compiler = CrossCompiler()
        self.client = C64UClient()
        self.last_asm: str = ""
        self.last_prg_path: Optional[Path] = None
        self.last_sid_path: Optional[Path] = None
        self.loaded_file: Optional[Path] = None
        self.file_mode: str = "py"  # "py" or "asm"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="menu-bar"):
            yield Button("📁 File ▾", id="menu-btn-file", classes="menu-bar-btn")
            yield Button("⚙ Build ▾", id="menu-btn-build", classes="menu-bar-btn")
            yield Button("🕹 C64 Device ▾", id="menu-btn-device", classes="menu-bar-btn")
            yield Button("🎵 SID Audio ▾", id="menu-btn-sid", classes="menu-bar-btn")
            yield Button("❓ Help ▾", id="menu-btn-help", classes="menu-bar-btn")
            yield Button("⚡ Run (F5)", id="quick-btn-run", classes="quick-run-btn")
            yield Button("🔁 Reset (F8)", id="quick-btn-reset", classes="quick-reset-btn")
            yield Static("● C64U: Checking...", id="bridge-status")

        with Horizontal(id="main-container"):
            # Left Column: Python Source Editor
            with Vertical(id="left-column"):
                yield Static(" Python Source (MOS 6502 Dialect)", classes="pane-title")
                initial_code = PRESETS["Rainbow Raster Bars"]["code"]
                yield TextArea(initial_code, language="python", theme="monokai", id="python-editor")

            # Right Column: Assembly Output, Logs, AST, and Hardware Console
            with Vertical(id="right-column"):
                with TabbedContent(id="tabs"):
                    with TabPane("6502 Assembly", id="tab-asm"):
                        yield TextArea("", language="asm", theme="monokai", read_only=False, id="asm-viewer")

                    with TabPane("Build Log", id="tab-log"):
                        yield RichLog(id="build-log", highlight=True, markup=True)

                    with TabPane("AST & Symbols", id="tab-ast"):
                        yield Tree("Program AST", id="ast-tree")

                    with TabPane("C64U Hardware", id="tab-hw"):
                        with VerticalScroll():
                            with Vertical(classes="hardware-card"):
                                with Horizontal(classes="hw-row"):
                                    yield Label("Ultimate 64 Hardware Actions")
                                    yield Static("● C64U: Checking...", id="bridge-status")
                                chip_hw_row = Horizontal(classes="hw-row")
                                with chip_hw_row:
                                    yield Button("DMA Run PRG", variant="success", id="hw-run-prg")
                                    yield Button("DMA Load PRG", variant="primary", id="hw-load-prg")
                                    yield Button("Reset C64", variant="warning", id="hw-reset")
                                    yield Button("Reboot C64", variant="error", id="hw-reboot")
                                with Horizontal(classes="hw-row"):
                                    yield Button("Pause CPU", variant="warning", id="hw-pause")
                                    yield Button("Resume CPU", variant="success", id="hw-resume")

                            with Vertical(classes="hardware-card"):
                                yield Label("Direct Memory Peek / Poke Tool")
                                with Horizontal(classes="hw-row"):
                                    yield Input(placeholder="Hex Address ($D020)", id="inp-addr", value="$D020")
                                    yield Input(placeholder="Hex Value ($01)", id="inp-val", value="$01")
                                    yield Button("Poke", variant="primary", id="hw-poke")
                                    yield Button("Peek", id="hw-peek")

        yield Footer()

    def on_mount(self) -> None:
        """Called when application UI is ready."""
        log = self.query_one("#build-log", RichLog)
        log.write("[bold cyan]C64U Python-to-6502 Transpiler Initialized.[/]")
        log.write(f"[dim]Bridge Target: http://{self.client.host}:{self.client.port}[/]")
        self.check_bridge_status()
        self.action_transpile_code()

    # -------------------------------------------------------------------------
    # Background Workers
    # -------------------------------------------------------------------------

    @work(thread=True, exclusive=True)
    def check_bridge_status(self, notify_user: bool = False) -> None:
        """Poll the C64U bridge to check hardware reachability."""
        status_widget = self.query_one("#bridge-status", Static)
        self.call_from_thread(status_widget.update, f"[yellow]● C64U: Checking ({self.client.host})...[/]")
        log = self.query_one("#build-log", RichLog)

        try:
            # Use quick timeout for background ping
            quick_client = C64UClient(
                host=self.client.host,
                port=self.client.port,
                password=self.client.password,
                timeout=1.5,
            )
            info = quick_client.get_info()
            ver = info.get("version", "Online")
            self.sub_title = f"● C64U: Online ({self.client.host}) | 6502 Studio"
            self.call_from_thread(status_widget.update, f"[green]● C64U: Connected ({ver})[/]")
            if notify_user:
                self.call_from_thread(
                    log.write,
                    f"\n[bold green]✓ C64U is ONLINE: Version {ver} (http://{self.client.host}:{self.client.port})[/]",
                )
                self.notify(f"C64U Online ({ver})", title="Bridge Status", severity="information")
        except Exception as exc:
            self.sub_title = f"○ C64U: Offline ({self.client.host}) | 6502 Studio"
            self.call_from_thread(status_widget.update, f"[red]○ C64U: Offline ({self.client.host})[/]")
            if notify_user:
                self.call_from_thread(
                    log.write,
                    f"\n[bold red]✗ C64U is OFFLINE: Unable to reach http://{self.client.host}:{self.client.port}[/]\n[dim]{exc}[/]",
                )
                self.notify(f"C64U Offline at {self.client.host}", title="Bridge Status", severity="warning")

    @work(thread=True, exclusive=True)
    def do_compile_and_run(self) -> None:
        """Transpile/assemble and send binary to C64U via DMA."""
        log = self.query_one("#build-log", RichLog)

        # Handle direct Assembly execution (e.g. from game_dev/choplifter.asm)
        if self.file_mode == "asm":
            asm_viewer = self.query_one("#asm-viewer", TextArea)
            asm_text = asm_viewer.text
            src_file = self.loaded_file

            self.call_from_thread(log.write, "\n[bold yellow]=== [F5] Starting Pipeline: Assemble ASM -> DMA Run ===[/]")

            # If user has an existing .asm file loaded and unchanged in viewer, compile directly
            if src_file and src_file.suffix.lower() in [".asm", ".s"] and src_file.exists() and asm_text == self.last_asm:
                target_asm = src_file
                out_prg = src_file.with_suffix(".prg")
            else:
                with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
                    asm_tmp.write(asm_text.encode("utf-8"))
                    target_asm = Path(asm_tmp.name)
                out_prg = target_asm.with_suffix(".prg")

            self.call_from_thread(log.write, f"[cyan]Compiling {target_asm.name} with KickAssembler...[/]")
            comp_res = self.compiler.compile(target_asm, output_prg=out_prg, assembler="auto")

            if not comp_res.success or not out_prg.exists():
                err_msg = comp_res.error_message or comp_res.stderr or comp_res.stdout
                self.call_from_thread(log.write, f"[bold red]Assembler Error:[/] {err_msg}")
                self.notify("Assembly compilation failed!", severity="error")
                return

            self.last_prg_path = out_prg
            prg_size = out_prg.stat().st_size
            self.call_from_thread(log.write, f"[green]✓ Binary assembled:[/] {out_prg.name} ({prg_size} bytes)")

            # DMA Run on C64U
            self.call_from_thread(log.write, f"[yellow]DMA Uploading {prg_size} bytes to C64U at {self.client.base_url}...[/]")
            try:
                dma_res = self.client.run_prg(out_prg)
                self.call_from_thread(log.write, f"[bold green]✓ DMA RUN Executed Successfully![/] Response: {dma_res}")
                self.notify(f"Running on C64U! ({prg_size} bytes)", severity="information")
            except C64UClientError as ce:
                self.call_from_thread(log.write, f"[bold red]C64U DMA Run Error:[/] {ce}")
                self.notify("Could not send to C64U hardware. Check connection.", severity="warning")
            return

        # Python-to-Assembly pipeline
        editor = self.query_one("#python-editor", TextArea)
        source = editor.text

        self.call_from_thread(log.write, "\n[bold yellow]=== [F5] Starting Pipeline: Transpile -> Assemble -> DMA Run ===[/]")

        # Step 1: Transpile
        trans_res = self.transpiler.transpile(source)
        if not trans_res.success:
            for err in trans_res.errors:
                self.call_from_thread(log.write, f"[bold red]Transpile Error:[/] {err}")
            self.notify("Transpilation failed! Check Build Log.", severity="error")
            return

        self.last_asm = trans_res.assembly
        asm_viewer = self.query_one("#asm-viewer", TextArea)
        self.call_from_thread(setattr, asm_viewer, "text", trans_res.assembly)
        self.call_from_thread(self._update_ast_tree, trans_res)
        self.call_from_thread(log.write, "[green]✓ Transpilation successful[/]")

        # Step 2: Assemble via KickAssembler
        with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
            asm_tmp.write(trans_res.assembly.encode("utf-8"))
            asm_path = Path(asm_tmp.name)

        out_prg = asm_path.with_suffix(".prg")
        self.call_from_thread(log.write, f"[cyan]Invoking KickAssembler on {asm_path.name}...[/]")
        comp_res = self.compiler.compile(asm_path, output_prg=out_prg, assembler="kickass")

        if not comp_res.success or not out_prg.exists():
            err_msg = comp_res.error_message or comp_res.stderr or comp_res.stdout
            self.call_from_thread(log.write, f"[bold red]KickAssembler Error:[/] {err_msg}")
            self.notify("Assembly compilation failed!", severity="error")
            try:
                asm_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        self.last_prg_path = out_prg
        prg_size = out_prg.stat().st_size
        self.call_from_thread(log.write, f"[green]✓ Binary assembled:[/] {out_prg.name} ({prg_size} bytes)")

        # Step 3: DMA Run on C64U
        self.call_from_thread(log.write, f"[yellow]DMA Uploading {prg_size} bytes to C64U at {self.client.base_url}...[/]")
        try:
            dma_res = self.client.run_prg(out_prg)
            self.call_from_thread(log.write, f"[bold green]✓ DMA RUN Executed Successfully![/] Response: {dma_res}")
            self.notify(f"Running on C64U! ({prg_size} bytes)", severity="information")
        except C64UClientError as ce:
            self.call_from_thread(log.write, f"[bold red]C64U DMA Run Error:[/] {ce}")
            self.notify("Could not send to C64U hardware. Check connection.", severity="warning")

    @work(thread=True, exclusive=True)
    def play_sid_on_c64u(self, path: Path) -> None:
        """Upload a SID file and start the Ultimate firmware SID player."""
        log = self.query_one("#build-log", RichLog)
        try:
            size = path.stat().st_size
            self.call_from_thread(
                log.write,
                f"\n[bold yellow]Uploading {path.name} ({size} bytes) to the C64U SID player...[/]",
            )
            result = self.client.play_sid(path)
            self.call_from_thread(
                log.write,
                f"[bold green]✓ SID playback started successfully![/] Response: {result}",
            )
            self.notify(
                f"Playing {path.name} on C64U",
                title="C64U SID Player",
                severity="information",
            )
        except (OSError, C64UClientError, ValueError) as exc:
            self.call_from_thread(log.write, f"[bold red]C64U SID playback failed:[/] {exc}")
            self.notify(str(exc), title="C64U SID Player Error", severity="error")

    @work(thread=True, exclusive=True)
    def compile_loaded_sid(self, source_path: Path, source_text: str) -> None:
        """Assemble the current decompiled source and rebuild its SID container."""
        log = self.query_one("#build-log", RichLog)
        try:
            self.call_from_thread(
                log.write,
                f"\n[bold yellow]Compiling {source_path.name} back into SID...[/]",
            )
            result = compile_sid_source(
                source_path,
                template_sid=self.last_sid_path,
                compiler=self.compiler,
                source_text=source_text,
            )
            self.last_sid_path = result.output_sid
            h = result.sid.header
            self.call_from_thread(
                log.write,
                f"[bold green]✓ SID compiled:[/] {result.output_sid} "
                f"({result.payload_size} bytes, load ${h.load_address:04X}, "
                f"init ${h.init_address:04X}, play ${h.play_address:04X})",
            )
            self.notify(
                f"Compiled {result.output_sid.name}",
                title="SID Compiler",
                severity="information",
            )
        except (OSError, SidCompileError) as exc:
            self.call_from_thread(log.write, f"[bold red]SID compilation failed:[/] {exc}")
            self.notify(str(exc), title="SID Compiler Error", severity="error")

    # -------------------------------------------------------------------------
    # Actions & Handlers
    # -------------------------------------------------------------------------

    def action_run_c64u(self) -> None:
        """Trigger compile and DMA run."""
        self.do_compile_and_run()

    def action_transpile_code(self) -> None:
        """Transpile Python code and display assembly output."""
        log = self.query_one("#build-log", RichLog)
        editor = self.query_one("#python-editor", TextArea)
        asm_viewer = self.query_one("#asm-viewer", TextArea)
        source = editor.text

        if not source.strip():
            log.write("[yellow]No Python source code in LHS pane to transpile.[/]")
            self.notify("LHS editor is empty.", severity="warning")
            return

        log.write("[bold cyan]Transpiling Python source...[/]")
        result = self.transpiler.transpile(source)

        if result.success:
            self.last_asm = result.assembly
            asm_viewer.text = result.assembly
            self._update_ast_tree(result)
            log.write(f"[green]✓ Transpiled successfully ({len(result.assembly.splitlines())} lines of 6502 assembly).[/]")
            self.notify("Transpilation successful!", severity="information")
        else:
            for err in result.errors:
                log.write(f"[bold red]Error:[/] {err}")
            self.notify("Transpilation failed.", severity="error")

    def action_assemble_prg(self) -> None:
        """Assemble current assembly to PRG binary."""
        log = self.query_one("#build-log", RichLog)

        # Direct Assembly mode
        if self.file_mode == "asm":
            asm_viewer = self.query_one("#asm-viewer", TextArea)
            asm_text = asm_viewer.text
            src_file = self.loaded_file

            if src_file and src_file.suffix.lower() in [".asm", ".s"] and src_file.exists() and asm_text == self.last_asm:
                target_asm = src_file
                out_prg = src_file.with_suffix(".prg")
            else:
                with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
                    asm_tmp.write(asm_text.encode("utf-8"))
                    target_asm = Path(asm_tmp.name)
                out_prg = Path("./output.prg").resolve()

            log.write(f"[cyan]Assembling {target_asm.name} to {out_prg.name}...[/]")
            comp_res = self.compiler.compile(target_asm, output_prg=out_prg, assembler="auto")

            if comp_res.success and out_prg.exists():
                self.last_prg_path = out_prg
                size = out_prg.stat().st_size
                log.write(f"[bold green]✓ Assembled {out_prg.name} ({size} bytes)[/]")
                self.notify(f"Generated {out_prg.name} ({size} bytes)", severity="information")
            else:
                err = comp_res.error_message or comp_res.stderr or comp_res.stdout
                log.write(f"[bold red]Assembly Failed:[/] {err}")
                self.notify("Assembly failed!", severity="error")
            return

        # Python-to-Assembly mode
        if not self.last_asm:
            self.action_transpile_code()
            if not self.last_asm:
                return

        with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
            asm_tmp.write(self.last_asm.encode("utf-8"))
            asm_path = Path(asm_tmp.name)

        out_prg = Path("./output.prg").resolve()
        log.write(f"[cyan]Assembling to {out_prg}...[/]")
        comp_res = self.compiler.compile(asm_path, output_prg=out_prg, assembler="kickass")

        if comp_res.success and out_prg.exists():
            self.last_prg_path = out_prg
            size = out_prg.stat().st_size
            log.write(f"[bold green]✓ Assembled output.prg ({size} bytes)[/]")
            self.notify(f"Generated output.prg ({size} bytes)", severity="information")
        else:
            err = comp_res.error_message or comp_res.stderr or comp_res.stdout
            log.write(f"[bold red]Assembly Failed:[/] {err}")
            self.notify("Assembly failed!", severity="error")

        try:
            asm_path.unlink(missing_ok=True)
        except Exception:
            pass

    def action_open_file(self) -> None:
        """Display project file selector dialog."""
        def on_file_selected(file_path: Optional[Path]) -> None:
            if file_path:
                self.load_project_file(file_path)

        # Default to game_dev if it exists, otherwise workspace root
        initial_dir = Path.cwd() / "game_dev" if (Path.cwd() / "game_dev").exists() else Path.cwd()
        self.push_screen(OpenFileModal(initial_path=initial_dir), on_file_selected)

    def load_project_file(self, path: Path) -> None:
        """Load a file (.py, .asm, .s, or .prg) into the studio workspace."""
        if not path.exists():
            self.notify(f"File not found: {path.name}", severity="error")
            return

        ext = path.suffix.lower()
        log = self.query_one("#build-log", RichLog)

        if ext == ".py":
            self.file_mode = "py"
            self.loaded_file = path
            editor = self.query_one("#python-editor", TextArea)
            try:
                code = path.read_text(encoding="utf-8")
                editor.text = code
                log.write(f"\n[bold green]✓ Loaded Python source: {path.name}[/] ({path.stat().st_size} bytes)")
                self.notify(f"Loaded {path.name}", severity="information")
                self.action_transpile_code()
            except Exception as e:
                log.write(f"[bold red]Failed to read {path.name}:[/] {e}")
                self.notify(f"Error loading file: {e}", severity="error")

        elif ext in [".asm", ".s"]:
            self.file_mode = "asm"
            self.loaded_file = path
            asm_viewer = self.query_one("#asm-viewer", TextArea)
            editor = self.query_one("#python-editor", TextArea)
            try:
                asm_content = path.read_text(encoding="utf-8")
                self.last_asm = asm_content
                asm_viewer.text = asm_content
                tabs = self.query_one("#tabs", TabbedContent)
                tabs.active = "tab-asm"
                log.write(f"\n[bold green]✓ Loaded 6502 Assembly: {path.name}[/] ({path.stat().st_size} bytes, {len(asm_content.splitlines())} lines)")
                self.notify(f"Loaded {path.name} (Assembly Mode)", severity="information")

                # Show Python Source (MOS 6502 Dialect) conversion if available; otherwise leave blank
                py_source = self._find_python_source_for_asm(path, asm_content)
                if py_source:
                    editor.text = py_source
                    log.write(f"[cyan]ℹ Associated Python source loaded in LHS pane ({len(py_source.splitlines())} lines)[/]")
                else:
                    editor.text = ""
                    log.write("[dim]ℹ No associated Python source available for this assembly file (LHS pane cleared)[/]")
            except Exception as e:
                log.write(f"[bold red]Failed to read {path.name}:[/] {e}")
                self.notify(f"Error loading file: {e}", severity="error")

        elif ext == ".sid":
            self._load_sid_file(path)

        elif ext == ".prg":
            self.last_prg_path = path
            size = path.stat().st_size
            log.write(f"\n[bold cyan]Selected PRG binary:[/] {path.name} ({size} bytes)")
            log.write(f"[yellow]Launching {path.name} to C64U via DMA Run...[/]")
            try:
                dma_res = self.client.run_prg(path)
                log.write(f"[bold green]✓ DMA RUN Executed Successfully![/] Response: {dma_res}")
                self.notify(f"Running {path.name} on C64U! ({size} bytes)", severity="information")
            except C64UClientError as ce:
                log.write(f"[bold red]C64U DMA Run Error:[/] {ce}")
                self.notify("Could not send PRG to C64U hardware.", severity="warning")
            except Exception as e:
                log.write(f"[bold red]DMA Run Error:[/] {e}")
                self.notify(f"Error: {e}", severity="error")

        elif ext == ".tap":
            from .tap import read_tap_info
            size = path.stat().st_size
            log.write(f"\n[bold cyan]Selected TAP Tape Image:[/] {path.name} ({size} bytes)")
            try:
                tap_info = read_tap_info(path.read_bytes())
                log.write(f"[green]✓ Valid TAP File:[/] {tap_info['signature']} v{tap_info['version']} ({tap_info['platform']} {tap_info['video']})")
                log.write(f"[cyan]Pulses recorded:[/] {tap_info['actual_length']}")
                log.write(f"[yellow]ℹ Ultimate 64 / C64U:[/] Mount {path.name} using the U64 File Manager / Tape Player to run directly on hardware.")
                self.notify(f"Selected TAP image: {path.name}", severity="information")
            except Exception as e:
                log.write(f"[bold red]TAP Validation Error:[/] {e}")
                self.notify(f"Invalid TAP: {e}", severity="error")

    def _find_python_source_for_asm(self, path: Path, asm_content: str) -> Optional[str]:
        """Locate associated Python source (MOS 6502 Dialect) conversion for an assembly file."""
        # 1. Direct sidecar file with .py extension in same directory
        py_sidecar = path.with_suffix(".py")
        if py_sidecar.is_file():
            try:
                return py_sidecar.read_text(encoding="utf-8")
            except Exception:
                pass

        # 2. Check standard project directories (examples/, game_dev/, workspace root)
        alt_candidates = [
            Path.cwd() / "examples" / f"{path.stem}.py",
            Path.cwd() / "game_dev" / f"{path.stem}.py",
            Path.cwd() / f"{path.stem}.py",
        ]
        for cand in alt_candidates:
            if cand.resolve() != py_sidecar.resolve() and cand.is_file():
                try:
                    return cand.read_text(encoding="utf-8")
                except Exception:
                    pass

        # 3. Check if stem matches a known preset
        stem_norm = path.stem.lower().replace("_", "").replace("-", "").replace(" ", "")
        for preset_name, preset_data in PRESETS.items():
            preset_norm = preset_name.lower().replace("_", "").replace("-", "").replace(" ", "")
            if stem_norm == preset_norm or (len(stem_norm) >= 4 and (stem_norm in preset_norm or preset_norm in stem_norm)):
                code = preset_data.get("code")
                if code:
                    return code

        # 4. Check for embedded Python source block within assembly comments
        if "// [PYTHON_SOURCE_START]" in asm_content and "// [PYTHON_SOURCE_END]" in asm_content:
            try:
                start_marker = "// [PYTHON_SOURCE_START]"
                end_marker = "// [PYTHON_SOURCE_END]"
                start_pos = asm_content.find(start_marker) + len(start_marker)
                end_pos = asm_content.find(end_marker)
                raw_block = asm_content[start_pos:end_pos]
                extracted_lines = []
                for line in raw_block.splitlines():
                    sline = line.strip()
                    if sline.startswith("//"):
                        sline = sline[2:].lstrip()
                    extracted_lines.append(sline)
                clean_py = "\n".join(extracted_lines).strip()
                if clean_py:
                    return clean_py
            except Exception:
                pass

        return None

    def _load_sid_file(self, path: Path) -> None:
        """Reverse-decompile a PSID/RSID file and load both generated sources."""
        log = self.query_one("#build-log", RichLog)
        try:
            result = decompile_sid_file(path)
            asm_path = path.with_name(f"{path.stem}_decompiled.asm")
            py_path = path.with_name(f"{path.stem}_decompiled.py")
            asm_path.write_text(result.assembly, encoding="utf-8")
            py_path.write_text(result.python, encoding="utf-8")

            self.file_mode = "asm"
            self.last_sid_path = path
            self.loaded_file = asm_path
            self.last_asm = result.assembly
            self.last_prg_path = None
            self.query_one("#asm-viewer", TextArea).text = result.assembly
            self.query_one("#python-editor", TextArea).text = result.python
            self.query_one("#tabs", TabbedContent).active = "tab-asm"

            h = result.sid.header
            log.write(
                f"\n[bold green]✓ Reverse-decompiled {h.magic} v{h.version}: {path.name}[/]"
            )
            log.write(
                f"[cyan]{h.name or '(untitled)'}[/] by {h.author or '(unknown)'} | "
                f"load ${h.load_address:04X}, init ${h.init_address:04X}, "
                f"play ${h.play_address:04X}, {h.songs} song(s)"
            )
            log.write(
                f"[green]Recovered {result.instruction_count} instructions; "
                f"preserved {result.data_byte_count} bytes as data.[/]"
            )
            log.write(f"[bold]ASM:[/] {asm_path}")
            log.write(f"[bold]Python:[/] {py_path}")
            for warning in result.warnings:
                log.write(f"[yellow]Warning:[/] {warning}")
            self.notify(
                f"SID decompiled to {asm_path.name} and {py_path.name}",
                title="SID Reverse Decompiler",
                severity="information",
            )
        except (OSError, SidDecompileError) as exc:
            log.write(f"[bold red]SID decompile failed:[/] {exc}")
            self.notify(str(exc), title="SID Decompile Error", severity="error")

    def action_decompile_sid(self) -> None:
        """Choose a SID file and reverse-decompile it to ASM and Python sidecars."""
        def on_file_selected(file_path: Optional[Path]) -> None:
            if not file_path:
                return
            if file_path.suffix.lower() != ".sid":
                self.notify("Select a .sid (PSID/RSID) file", severity="warning")
                return
            self._load_sid_file(file_path)

        self.push_screen(OpenFileModal(initial_path=Path.cwd()), on_file_selected)

    def action_play_sid(self) -> None:
        """Play the last imported SID, or prompt for one when none is selected."""
        if self.last_sid_path and self.last_sid_path.is_file():
            self.play_sid_on_c64u(self.last_sid_path)
            return

        def on_file_selected(file_path: Optional[Path]) -> None:
            if not file_path:
                return
            if file_path.suffix.lower() != ".sid":
                self.notify("Select a .sid (PSID/RSID) file", severity="warning")
                return
            self.last_sid_path = file_path
            self.play_sid_on_c64u(file_path)

        self.push_screen(OpenFileModal(initial_path=Path.cwd()), on_file_selected)

    def action_compile_sid(self) -> None:
        """Compile the currently loaded decompiled source back into a SID file."""
        if not self.loaded_file or self.loaded_file.suffix.lower() not in {".asm", ".s", ".py"}:
            self.notify("Load a decompiled SID source first", severity="warning")
            return
        if self.file_mode == "asm":
            source_text = self.query_one("#asm-viewer", TextArea).text
        else:
            source_text = self.query_one("#python-editor", TextArea).text
        if "C64U_SID_METADATA:" not in source_text and not self.last_sid_path:
            self.notify("Loaded source has no SID metadata or template", severity="warning")
            return
        self.compile_loaded_sid(self.loaded_file, source_text)

    def action_open_presets(self) -> None:
        """Display preset selector modal dialog."""
        def on_preset_selected(code: Optional[str]) -> None:
            if code:
                self.file_mode = "py"
                self.loaded_file = None
                editor = self.query_one("#python-editor", TextArea)
                editor.text = code
                self.notify("Loaded preset example", severity="information")
                self.action_transpile_code()

        self.push_screen(PresetModal(), on_preset_selected)

    def action_show_help(self) -> None:
        """Display help documentation modal dialog."""
        self.push_screen(HelpModal())

    def action_save_assembly(self) -> None:
        """Save the 6502 assembly to a local file."""
        asm_viewer = self.query_one("#asm-viewer", TextArea)
        current_text = asm_viewer.text or self.last_asm
        if not current_text:
            self.notify("No assembly to save.", severity="warning")
            return

        out_file = self.loaded_file if (self.file_mode == "asm" and self.loaded_file) else Path("./output.asm").resolve()
        out_file.write_text(current_text, encoding="utf-8")
        self.last_asm = current_text
        log = self.query_one("#build-log", RichLog)
        log.write(f"[green]✓ Saved assembly to {out_file}[/]")
        self.notify(f"Saved to {out_file.name}", severity="information")

    def action_refresh_connection(self) -> None:
        """Refresh and re-check C64U connection reachability."""
        log = self.query_one("#build-log", RichLog)
        log.write(f"\n[cyan]Checking connection to C64U at http://{self.client.host}:{self.client.port}...[/]")
        self.check_bridge_status(notify_user=True)

    def action_reset_c64u(self) -> None:
        """Send hardware reset command to the C64U machine."""
        log = self.query_one("#build-log", RichLog)
        log.write(f"\n[bold yellow]⚡ Sending Hardware Reset to C64U at http://{self.client.host}:{self.client.port}...[/]")
        try:
            res = self.client.reset(reboot=False)
            log.write(f"[bold green]✓ C64U Reset Successful:[/] {res}")
            self.notify("C64U Reset Command Sent", severity="warning", title="C64U Hardware")
        except Exception as e:
            log.write(f"[bold red]✗ C64U Reset Failed:[/] {e}")
            self.notify(f"Reset failed: {e}", severity="error", title="C64U Hardware")

    def action_export_tap(self) -> None:
        """Export current assembly or project to a standard Commodore 64 .tap cassette image."""
        from .tap import save_prg_to_tap
        log = self.query_one("#build-log", RichLog)

        # Direct Assembly mode
        if self.file_mode == "asm":
            asm_viewer = self.query_one("#asm-viewer", TextArea)
            asm_text = asm_viewer.text
            src_file = self.loaded_file

            if src_file and src_file.suffix.lower() in [".asm", ".s"] and src_file.exists() and asm_text == self.last_asm:
                target_asm = src_file
                out_prg = src_file.with_suffix(".prg")
                out_tap = src_file.with_suffix(".tap")
                tape_name = src_file.stem
            elif src_file:
                src_file.write_text(asm_text, encoding="utf-8")
                self.last_asm = asm_text
                target_asm = src_file
                out_prg = src_file.with_suffix(".prg")
                out_tap = src_file.with_suffix(".tap")
                tape_name = src_file.stem
            else:
                with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
                    asm_tmp.write(asm_text.encode("utf-8"))
                    target_asm = Path(asm_tmp.name)
                out_prg = Path("./output.prg").resolve()
                out_tap = Path("./output.tap").resolve()
                tape_name = "OUTPUT"

            log.write(f"\n[bold cyan]📼 Exporting to TAP Tape Image...[/]")
            log.write(f"[cyan]Compiling {target_asm.name} with KickAssembler to PRG...[/]")
            comp_res = self.compiler.compile(target_asm, output_prg=out_prg, assembler="auto")

            if not comp_res.success or not out_prg.exists():
                err = comp_res.error_message or comp_res.stderr or comp_res.stdout
                log.write(f"[bold red]Assembly Failed:[/] {err}")
                self.notify("Assembly failed before TAP export!", severity="error")
                return

            self.last_prg_path = out_prg
            prg_size = out_prg.stat().st_size
            log.write(f"[green]✓ Binary assembled:[/] {out_prg.name} ({prg_size} bytes)")

            try:
                save_prg_to_tap(out_prg, tap_path=out_tap, tape_name=tape_name)
                tap_size = out_tap.stat().st_size
                log.write(f"[bold green]✓ TAP Image Generated:[/] {out_tap.name} ({tap_size} bytes)")
                log.write(f"[cyan]ℹ Format:[/] C64-TAPE-RAW v1 (PAL, 100% CBM KERNAL Tape compatible)")
                log.write(f"[cyan]ℹ Path:[/] {out_tap}")
                log.write(f"[yellow]ℹ Ultimate 64 / C64U:[/] Mount {out_tap.name} via U64 File Manager / Tape Player to run directly on hardware.")
                self.notify(f"Exported {out_tap.name} ({tap_size} bytes)", severity="information", title="TAP Tape Export")
            except Exception as e:
                log.write(f"[bold red]TAP Export Error:[/] {e}")
                self.notify(f"TAP export error: {e}", severity="error")
            return

        # Python-to-Assembly mode
        if not self.last_asm:
            self.action_transpile_code()
            if not self.last_asm:
                return

        with tempfile.NamedTemporaryFile(suffix=".asm", delete=False) as asm_tmp:
            asm_tmp.write(self.last_asm.encode("utf-8"))
            asm_path = Path(asm_tmp.name)

        out_prg = Path("./output.prg").resolve()
        out_tap = Path("./output.tap").resolve()
        log.write(f"\n[bold cyan]📼 Exporting to TAP Tape Image...[/]")
        log.write(f"[cyan]Assembling to {out_prg.name}...[/]")
        comp_res = self.compiler.compile(asm_path, output_prg=out_prg, assembler="kickass")

        if not comp_res.success or not out_prg.exists():
            err = comp_res.error_message or comp_res.stderr or comp_res.stdout
            log.write(f"[bold red]Assembly Failed:[/] {err}")
            self.notify("Assembly failed before TAP export!", severity="error")
            try:
                asm_path.unlink(missing_ok=True)
            except Exception:
                pass
            return

        self.last_prg_path = out_prg
        prg_size = out_prg.stat().st_size
        log.write(f"[green]✓ Binary assembled:[/] {out_prg.name} ({prg_size} bytes)")

        try:
            save_prg_to_tap(out_prg, tap_path=out_tap, tape_name="OUTPUT")
            tap_size = out_tap.stat().st_size
            log.write(f"[bold green]✓ TAP Image Generated:[/] {out_tap.name} ({tap_size} bytes)")
            log.write(f"[cyan]ℹ Format:[/] C64-TAPE-RAW v1 (PAL, 100% CBM KERNAL Tape compatible)")
            log.write(f"[cyan]ℹ Path:[/] {out_tap}")
            log.write(f"[yellow]ℹ Ultimate 64 / C64U:[/] Mount {out_tap.name} via U64 File Manager / Tape Player to run directly on hardware.")
            self.notify(f"Exported {out_tap.name} ({tap_size} bytes)", severity="information", title="TAP Tape Export")
        except Exception as e:
            log.write(f"[bold red]TAP Export Error:[/] {e}")
            self.notify(f"TAP export error: {e}", severity="error")

        try:
            asm_path.unlink(missing_ok=True)
        except Exception:
            pass

    def action_load_prg_only(self) -> None:
        """DMA load PRG into C64 memory without starting execution."""
        log = self.query_one("#build-log", RichLog)
        if self.last_prg_path and self.last_prg_path.exists():
            target_prg = self.last_prg_path
        else:
            self.action_assemble_prg()
            target_prg = self.last_prg_path

        if not target_prg or not target_prg.exists():
            self.notify("Assemble PRG first before DMA Load", severity="warning")
            return

        prg_size = target_prg.stat().st_size
        log.write(f"\n[cyan]DMA Loading {target_prg.name} ({prg_size} bytes) to C64 RAM...[/]")
        try:
            res = self.client.load_prg(target_prg)
            log.write(f"[bold green]✓ PRG Loaded into RAM successfully:[/] {res}")
            self.notify(f"PRG loaded into C64 RAM ({prg_size} bytes)", severity="information")
        except Exception as e:
            log.write(f"[bold red]DMA Load Error:[/] {e}")
            self.notify(f"DMA Load failed: {e}", severity="error")

    def action_pause_cpu(self) -> None:
        """Pause 6510 CPU execution on C64U."""
        log = self.query_one("#build-log", RichLog)
        log.write("\n[yellow]Pausing 6510 CPU...[/]")
        try:
            self.client.pause()
            log.write("[green]✓ 6510 CPU Paused[/]")
            self.notify("C64 CPU Paused", severity="warning")
        except Exception as e:
            log.write(f"[bold red]Pause CPU Error:[/] {e}")
            self.notify(f"Pause failed: {e}", severity="error")

    def action_resume_cpu(self) -> None:
        """Resume 6510 CPU execution on C64U."""
        log = self.query_one("#build-log", RichLog)
        log.write("\n[green]Resuming 6510 CPU...[/]")
        try:
            self.client.resume()
            log.write("[green]✓ 6510 CPU Resumed[/]")
            self.notify("C64 CPU Resumed", severity="information")
        except Exception as e:
            log.write(f"[bold red]Resume CPU Error:[/] {e}")
            self.notify(f"Resume failed: {e}", severity="error")

    def action_dump_screen(self) -> None:
        """Read and display current C64 screen RAM ($0400-$07E7) in Build Log."""
        log = self.query_one("#build-log", RichLog)
        log.write("\n[cyan]Reading screen memory from C64U ($0400-$07E7)...[/]")
        try:
            screen_mem = self.client.read_memory(0x0400, 1000)
            color_mem = None
            try:
                color_mem = self.client.read_memory(0xD800, 1000)
            except Exception:
                color_mem = None
            dump = format_screen(screen_mem, color_mem, use_ansi=False)
            tabs = self.query_one("#tabs", TabbedContent)
            tabs.active = "tab-log"
            log.write("[bold green]=== C64 Screen Memory Dump ===[/]")
            log.write(dump)
            self.notify("Screen memory dumped to Build Log", severity="information")
        except Exception as e:
            log.write(f"[bold red]Screen Dump Error:[/] {e}")
            self.notify(f"Screen Dump failed: {e}", severity="error")

    def action_reboot_c64u(self) -> None:
        """Hard reboot the C64 machine with cartridge reinitialization."""
        log = self.query_one("#build-log", RichLog)
        log.write(f"\n[bold red]⚡ Sending Hardware Reboot (Hard Reset) to C64U...[/]")
        try:
            res = self.client.reset(reboot=True)
            log.write(f"[bold green]✓ C64U Reboot Command Sent:[/] {res}")
            self.notify("C64 Reboot Command Sent", severity="error", title="C64U Hardware")
        except Exception as e:
            log.write(f"[bold red]✗ C64U Reboot Failed:[/] {e}")
            self.notify(f"Reboot failed: {e}", severity="error", title="C64U Hardware")

    def open_menu(self, category: str = "file") -> None:
        """Display tiered menu dropdown overlay."""
        def on_action(action_id: Optional[str]) -> None:
            if action_id:
                self.dispatch_menu_action(action_id)

        self.push_screen(MenuDropdownModal(category), on_action)

    def action_open_menu_category(self, category: str) -> None:
        """Action handler to open specific menu category via hotkey."""
        self.open_menu(category)

    def dispatch_menu_action(self, action_id: str) -> None:
        """Dispatch action from dropdown menu selection."""
        method_name = f"action_{action_id}"
        handler = getattr(self, method_name, None)
        if callable(handler):
            handler()
        else:
            self.notify(f"Unknown action: {action_id}", severity="warning")

    def action_quit(self) -> None:
        """Exit the C64 studio application."""
        self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        # Tiered menu bar buttons
        if btn_id == "menu-btn-file":
            self.open_menu("file")
        elif btn_id == "menu-btn-build":
            self.open_menu("build")
        elif btn_id == "menu-btn-device":
            self.open_menu("device")
        elif btn_id == "menu-btn-sid":
            self.open_menu("sid")
        elif btn_id == "menu-btn-help":
            self.open_menu("help")
        elif btn_id in ["btn-run", "quick-btn-run"]:
            self.action_run_c64u()
        elif btn_id in ["btn-c64u-reset", "quick-btn-reset"]:
            self.action_reset_c64u()
        # Row 1 - Function keys F1-F8 fallbacks
        elif btn_id == "btn-help":
            self.action_show_help()
        elif btn_id == "btn-presets":
            self.action_open_presets()
        elif btn_id == "btn-open":
            self.action_open_file()
        elif btn_id == "btn-refresh":
            self.action_refresh_connection()
        elif btn_id == "btn-transpile":
            self.action_transpile_code()
        elif btn_id == "btn-assemble":
            self.action_assemble_prg()
        # Row 2 - Shift commands
        elif btn_id == "btn-save":
            self.action_save_assembly()
        elif btn_id == "btn-export-tap":
            self.action_export_tap()
        elif btn_id == "btn-load-prg":
            self.action_load_prg_only()
        elif btn_id == "btn-pause-cpu":
            self.action_pause_cpu()
        elif btn_id == "btn-resume-cpu":
            self.action_resume_cpu()
        elif btn_id == "btn-screen-dump":
            self.action_dump_screen()
        elif btn_id == "btn-c64u-reboot":
            self.action_reboot_c64u()
        elif btn_id == "btn-quit":
            self.action_quit()
        elif btn_id == "btn-decompile-sid":
            self.action_decompile_sid()
        elif btn_id == "btn-compile-sid":
            self.action_compile_sid()
        elif btn_id == "btn-play-sid":
            self.action_play_sid()
        elif btn_id == "hw-run-prg":
            if self.last_prg_path and self.last_prg_path.exists():
                self.client.run_prg(self.last_prg_path)
                self.notify("PRG launched on C64U", severity="information")
            else:
                self.action_run_c64u()
        elif btn_id == "hw-load-prg":
            if self.last_prg_path and self.last_prg_path.exists():
                self.client.load_prg(self.last_prg_path)
                self.notify("PRG loaded into C64 RAM", severity="information")
            else:
                self.notify("Assemble PRG first!", severity="warning")
        elif btn_id == "hw-reset":
            self.action_reset_c64u()
        elif btn_id == "hw-reboot":
            try:
                self.client.reset(reboot=True)
                self.notify("C64 Reboot sent", severity="error")
            except Exception as e:
                self.notify(f"Reboot failed: {e}", severity="error")
        elif btn_id == "hw-pause":
            try:
                self.client.pause()
                self.notify("C64 CPU Paused", severity="warning")
            except Exception as e:
                self.notify(f"Pause failed: {e}", severity="error")
        elif btn_id == "hw-resume":
            try:
                self.client.resume()
                self.notify("C64 CPU Resumed", severity="information")
            except Exception as e:
                self.notify(f"Resume failed: {e}", severity="error")
        elif btn_id == "hw-poke":
            self._handle_hw_poke()
        elif btn_id == "hw-peek":
            self._handle_hw_peek()

    def _handle_hw_poke(self) -> None:
        addr_str = self.query_one("#inp-addr", Input).value.strip()
        val_str = self.query_one("#inp-val", Input).value.strip()
        log = self.query_one("#build-log", RichLog)
        try:
            addr = int(addr_str.replace("$", "0x"), 16)
            val = int(val_str.replace("$", "0x"), 16)
            self.client.write_memory(addr, [val])
            log.write(f"[green]✓ POKED ${addr:04X} = ${val:02X}[/]")
            self.notify(f"POKE ${addr:04X} = ${val:02X}", severity="information")
        except Exception as e:
            log.write(f"[red]Poke Error:[/] {e}")
            self.notify(f"Poke Error: {e}", severity="error")

    def _handle_hw_peek(self) -> None:
        addr_str = self.query_one("#inp-addr", Input).value.strip()
        log = self.query_one("#build-log", RichLog)
        try:
            addr = int(addr_str.replace("$", "0x"), 16)
            raw = self.client.read_memory(addr, 1)
            val = raw[0] if raw else 0
            self.query_one("#inp-val", Input).value = f"${val:02X}"
            log.write(f"[green]✓ PEEKED ${addr:04X} -> ${val:02X} ({val})[/]")
            self.notify(f"PEEK ${addr:04X} -> ${val:02X}", severity="information")
        except Exception as e:
            log.write(f"[red]Peek Error:[/] {e}")
            self.notify(f"Peek Error: {e}", severity="error")

    def _update_ast_tree(self, result: TranspileResult) -> None:
        """Populate the AST and Symbol tree viewer."""
        tree = self.query_one("#ast-tree", Tree)
        tree.clear()
        root = tree.root
        root.expand()

        # Symbols Branch
        symbols_node = root.add("Symbols & Variables", expand=True)
        for sym_name, sym_val in sorted(result.symbols.items()):
            symbols_node.add_leaf(f"{sym_name}: {sym_val}")

        # AST Branch
        if result.ast_tree:
            ast_node = root.add("Python AST Hierarchy", expand=True)
            for stmt in getattr(result.ast_tree, "body", []):
                stmt_desc = f"{type(stmt).__name__}: {ast.unparse(stmt)[:40]}"
                ast_node.add_leaf(stmt_desc)


def main() -> None:
    """Entry point for standalone execution."""
    app = C64PythonToAsmApp()
    app.run()


if __name__ == "__main__":
    main()
