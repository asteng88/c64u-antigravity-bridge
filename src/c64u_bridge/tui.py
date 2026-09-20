"""
Textual TUI for Commodore 64 Python-to-Assembly Transpiler & Bridge.
Provides an interactive retro-styled IDE for writing 6502-targeted Python code,
transpiling to assembly, compiling to .prg, and DMA-deploying directly to the C64U.
"""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
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

#toolbar {
    height: 3;
    background: #161b36;
    padding: 0 1;
    align: left middle;
    border-bottom: solid #352879;
}

#toolbar Button {
    margin-right: 1;
    min-width: 14;
    height: 1;
    border: none;
}

#btn-run {
    background: #238636;
    color: #ffffff;
    text-style: bold;
}

#btn-run:hover {
    background: #2ea043;
}

#btn-transpile {
    background: #352879;
    color: #ffffff;
}

#btn-transpile:hover {
    background: #4b3ba6;
}

#btn-assemble {
    background: #1f6feb;
    color: #ffffff;
}

#btn-presets {
    background: #6e40c9;
    color: #ffffff;
}

#bridge-status {
    width: 32;
    content-align: right middle;
    text-style: bold;
    color: #8b949e;
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
PresetModal, HelpModal {
    align: center middle;
}

#dialog {
    width: 80;
    height: 32;
    background: #161b36;
    border: heavy #70a4b2;
    padding: 1 2;
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
                    "[bold cyan]Control Flow & Statements:[/]\n"
                    "• [green]while cond:[/], [green]while True:[/], [green]break[/], [green]continue[/]\n"
                    "• [green]for i in range(stop):[/] or [green]for i in range(start, stop, step):[/]\n"
                    "• [green]if cond:[/], [green]elif cond:[/], [green]else:[/]\n"
                    "• Functions: [green]def my_sub():[/] compiled to subroutine with [green]rts[/]\n\n"
                    "[bold cyan]Keyboard Shortcuts:[/]\n"
                    "• [bold white]F5[/]: Transpile + Assemble + DMA Run on C64U\n"
                    "• [bold white]F6[/]: Transpile Python to 6502 Assembly\n"
                    "• [bold white]F7[/]: Assemble to C64 PRG binary\n"
                    "• [bold white]F2[/]: Open Preset Demos\n"
                    "• [bold white]F1[/]: Open this Reference Guide\n"
                    "• [bold white]Ctrl+Q[/]: Exit Application\n"
                )
                yield Static(help_text)
            yield Button("Close", variant="primary", id="dialog-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class C64PythonToAsmApp(App):
    """Textual TUI for Commodore 64 Python development and C64U execution."""

    CSS = C64_CSS
    TITLE = "C64U Python-to-Assembly Studio"
    SUB_TITLE = "6502 Cross-Transpiler & DMA Hardware Bridge"

    BINDINGS = [
        Binding("f5", "run_c64u", "Run C64U", show=True),
        Binding("f6", "transpile_code", "Transpile", show=True),
        Binding("f7", "assemble_prg", "Assemble", show=True),
        Binding("f2", "open_presets", "Presets", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("ctrl+s", "save_assembly", "Save ASM", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.transpiler = PythonTo6502Transpiler()
        self.compiler = CrossCompiler()
        self.client = C64UClient()
        self.last_asm: str = ""
        self.last_prg_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Button("⚡ Run C64U (F5)", id="btn-run")
            yield Button("⚙ Transpile (F6)", id="btn-transpile")
            yield Button("🔨 Assemble (F7)", id="btn-assemble")
            yield Button("📚 Presets (F2)", id="btn-presets")
            yield Button("💾 Save ASM", id="btn-save")
            yield Button("❓ Help (F1)", id="btn-help")
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
                        yield TextArea("", language="asm", theme="monokai", read_only=True, id="asm-viewer")

                    with TabPane("Build Log", id="tab-log"):
                        yield RichLog(id="build-log", highlight=True, markup=True)

                    with TabPane("AST & Symbols", id="tab-ast"):
                        yield Tree("Program AST", id="ast-tree")

                    with TabPane("C64U Hardware", id="tab-hw"):
                        with VerticalScroll():
                            with Vertical(classes="hardware-card"):
                                yield Label("Ultimate 64 Hardware Actions")
                                with Horizontal(classes="hw-row"):
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
    def check_bridge_status(self) -> None:
        """Poll the C64U bridge to check hardware reachability."""
        status_widget = self.query_one("#bridge-status", Static)
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
            self.call_from_thread(status_widget.update, f"[green]● C64U: Connected ({ver})[/]")
        except Exception:
            self.call_from_thread(status_widget.update, f"[red]○ C64U: Offline ({self.client.host})[/]")

    @work(thread=True, exclusive=True)
    def do_compile_and_run(self) -> None:
        """Transpile, assemble, and send binary to C64U via DMA."""
        log = self.query_one("#build-log", RichLog)
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

    def action_open_presets(self) -> None:
        """Display preset selector modal dialog."""
        def on_preset_selected(code: Optional[str]) -> None:
            if code:
                editor = self.query_one("#python-editor", TextArea)
                editor.text = code
                self.notify("Loaded preset example", severity="information")
                self.action_transpile_code()

        self.push_screen(PresetModal(), on_preset_selected)

    def action_show_help(self) -> None:
        """Display help documentation modal dialog."""
        self.push_screen(HelpModal())

    def action_save_assembly(self) -> None:
        """Save the generated 6502 assembly to a local file."""
        if not self.last_asm:
            self.notify("No assembly to save. Transpile first.", severity="warning")
            return
        out_file = Path("./output.asm").resolve()
        out_file.write_text(self.last_asm, encoding="utf-8")
        log = self.query_one("#build-log", RichLog)
        log.write(f"[green]✓ Saved assembly to {out_file}[/]")
        self.notify(f"Saved to {out_file.name}", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn-run":
            self.action_run_c64u()
        elif btn_id == "btn-transpile":
            self.action_transpile_code()
        elif btn_id == "btn-assemble":
            self.action_assemble_prg()
        elif btn_id == "btn-presets":
            self.action_open_presets()
        elif btn_id == "btn-save":
            self.action_save_assembly()
        elif btn_id == "btn-help":
            self.action_show_help()
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
            try:
                self.client.reset(reboot=False)
                self.notify("C64 Reset sent", severity="warning")
            except Exception as e:
                self.notify(f"Reset failed: {e}", severity="error")
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
