import shutil
import time
import tkinter as tk
import pytest
from pathlib import Path
from c64u_bridge.tui import (
    C64PythonToAsmApp,
    FilteredDirectoryTree,
    OpenFileModal,
    CopyrightCautionModal,
    DiskSelectModal,
    DecompileScopeModal,
    KickAssUpdateModal,
)
from c64u_bridge.themes import (
    THEMES,
    FONT_CREDITS_TEXT,
    register_embedded_fonts,
    get_asset_path,
)
from c64u_bridge.d64 import create_d64, read_d64
from c64u_bridge.project import create_definition


@pytest.fixture(scope="module")
def shared_root():
    """Provide a single withdrawn Tkinter root for the test session."""
    existing = getattr(tk, "_default_root", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.withdraw()
                return existing
        except tk.TclError:
            pass
    root = tk.Tk()
    root.withdraw()
    register_embedded_fonts()
    return root


@pytest.fixture
def tk_app(shared_root):
    """Create a fresh C64PythonToAsmApp instance inside the shared Tkinter root."""
    app = C64PythonToAsmApp(root=shared_root, skip_boot=True, start_maximized=False)
    shared_root.update_idletasks()
    return app


def test_font_registration_and_credits():
    """Verify embedded retro fonts exist, register cleanly, and credits attribute creators."""
    loaded = register_embedded_fonts()
    assert isinstance(loaded, bool)
    assert get_asset_path("fonts", "PetMe64.ttf").is_file()
    assert get_asset_path("fonts", "LICENSE-Kreative-FreeUse-1.2f.txt").is_file()
    assert get_asset_path("8bitC64.png").is_file()
    assert get_asset_path("8bitCassette.png").is_file()

    assert "Commodore 64" in THEMES
    assert "C64 Phosphor" not in THEMES
    assert "ZX Spectrum" not in THEMES
    assert THEMES["Commodore 64"]["border_idle"] == "#70A4B2"
    assert THEMES["Commodore 64"]["paper"] == "#352879"
    assert "PetMe64.ttf" in FONT_CREDITS_TEXT
    assert "Kreative Korporation" in FONT_CREDITS_TEXT
    assert "Faerie" in FONT_CREDITS_TEXT
    assert "BackMeUpScotty" in FONT_CREDITS_TEXT


def test_c64_splash_screen_fade_and_immediate_ide(shared_root):
    """Verify startup goes straight into the IDE with a fade-in/fade-out 'C64 Studio by Station 88 Retro' splash."""
    app = C64PythonToAsmApp(root=shared_root, skip_boot=False, start_maximized=False)
    shared_root.update_idletasks()

    # IDE loads immediately without any blocking BASIC V2 loading sequence
    assert app._boot_active is False
    assert app.studio_frame.winfo_manager() == "pack"

    # Splash overlay appears with expected Station 88 Retro branding and fades in then out
    assert app._splash_win is not None and app._splash_win.winfo_exists()
    assert app._splash_title_lbl.cget("text") == "C64 STUDIO"
    assert app._splash_subtitle_lbl.cget("text") == "BY STATION 88 RETRO"
    assert app._splash_phase == "fade_in"
    assert app._splash_alpha == 0.0

    # Fade in to full opacity (1.0)
    for step in range(1, 16):
        app._step_splash_fade("fade_in", step)
    assert app._splash_alpha == 1.0
    assert app._splash_phase == "hold"

    # Fade out to 0.0 and close cleanly
    for step in range(1, 16):
        app._step_splash_fade("fade_out", step)
    assert app._splash_phase == "done"
    assert app._splash_win is None
    assert app._splash_alpha == 0.0


def test_tui_app_mount_and_fullscreen_toggle(tk_app):
    """Verify main studio widgets mount properly and F11 fullscreen toggles cleanly."""
    app = tk_app
    assert app.py_text is not None
    assert app.asm_text is not None
    assert bool(app.py_text.cget("blockcursor")) is True
    assert bool(app.asm_text.cget("blockcursor")) is True

    assert app.log_text is not None
    assert app.ast_listbox is not None
    assert app.label_listbox is not None

    # Verify menu and quick buttons exist
    assert "menu-btn-file" in app.menu_buttons
    assert "quick-btn-run" in app.menu_buttons

    # Test F11 fullscreen toggle
    initial_fs = app.is_fullscreen
    app.action_toggle_fullscreen()
    assert app.is_fullscreen is not initial_fs
    app.action_toggle_fullscreen()
    assert app.is_fullscreen is initial_fs


def test_filtered_directory_tree():
    fdt = FilteredDirectoryTree(".")
    test_paths = [
        Path(".git"),
        Path(".venv"),
        Path("__pycache__"),
        Path("game_dev"),
        Path("game_dev/choplifter.asm"),
        Path("game_dev/choplifter.prg"),
        Path("music/test.sid"),
        Path("random.xyz"),
    ]
    filtered = fdt.filter_paths(test_paths)
    names = [p.name for p in filtered]
    assert ".git" not in names
    assert ".venv" not in names
    assert "__pycache__" not in names
    assert "random.xyz" not in names
    assert "game_dev" in names
    assert "choplifter.asm" in names
    assert "choplifter.prg" in names
    assert "test.sid" in names


def test_load_assembly_file_and_asm_editor_features(tk_app):
    """Verify loading .asm files, syntax highlighting, label outline, comment toggle, and ASM focus mode."""
    app = tk_app
    asm_path = Path("game_dev/choplifter.asm")
    if asm_path.exists():
        app.load_project_file(asm_path)
        assert app.file_mode == "asm"
        assert app.loaded_file == asm_path
        assert "CHOPLIFTER" in app.asm_text.get("1.0", "end-1c")
        assert app._active_tab == "tab-asm"
        assert app.py_text.get("1.0", "end-1c") == ""

    rainbow_asm = Path("examples/rainbow_border.asm")
    if rainbow_asm.exists():
        app.load_project_file(rainbow_asm)
        assert app.file_mode == "asm"
        assert "border_color" in app.py_text.get("1.0", "end-1c")

    # Test ASM label/subroutine outline population
    sample_asm = (
        ":BasicUpstart2(main)\n"
        ".const VIC_BORDER = $D020\n"
        "* = $0810 \"Main\"\n"
        "main:\n"
        "    sei\n"
        "    lda #$00\n"
        "    sta $D020 // border black\n"
        "loop:\n"
        "    inc $D020\n"
        "    jmp loop\n"
    )
    app._set_asm_text(sample_asm)
    assert len(app._label_line_map) >= 3  # VIC_BORDER, * = $0810, main:, loop:

    # Test syntax highlighting tags applied on asm_text
    opcode_ranges = app.asm_text.tag_ranges("opcode")
    assert len(opcode_ranges) > 0
    comment_ranges = app.asm_text.tag_ranges("comment")
    assert len(comment_ranges) > 0

    # Test Ctrl+/ comment toggle on line 5 ("    sei")
    app.asm_text.mark_set("insert", "5.0")
    app.action_toggle_asm_comment()
    line5 = app.asm_text.get("5.0", "5.end")
    assert line5.strip().startswith("//")
    app.action_toggle_asm_comment()
    line5_restored = app.asm_text.get("5.0", "5.end")
    assert not line5_restored.strip().startswith("//")

    # Test Find / Goto line feature
    app.find_var.set("8")
    app._on_find_or_goto()
    assert app.asm_text.index("insert").startswith("8.")
    app.find_var.set("loop")
    app._on_find_or_goto()
    assert len(app.asm_text.tag_ranges("find_match")) > 0

    # Test Full ASM IDE Focus mode toggle (Ctrl+E)
    assert app.asm_focus_mode is False
    app.action_toggle_asm_focus()
    assert app.asm_focus_mode is True
    app.action_toggle_asm_focus()
    assert app.asm_focus_mode is False

    # Test New 6502 .asm Template (Ctrl+N)
    app.action_new_asm_template()
    assert app.file_mode == "asm"
    assert "BasicUpstart2(start)" in app.asm_text.get("1.0", "end-1c")


def test_load_python_file(tk_app):
    app = tk_app
    py_path = Path("examples/rainbow_border.py")
    if py_path.exists():
        app.load_project_file(py_path)
        assert app.file_mode == "py"
        assert app.loaded_file == py_path
        py_content = app.py_text.get("1.0", "end-1c")
        assert "border_color" in py_content or len(py_content) > 0


def test_open_file_modal_composition(tk_app):
    app = tk_app
    modal = OpenFileModal(initial_path=Path.cwd())
    dlg = modal.show_tk(app, lambda _p: None)
    app.root.update_idletasks()
    assert dlg.winfo_exists()
    dlg.destroy()


def test_refresh_connection_and_reset_actions(tk_app):
    app = tk_app
    btn_reset = app.menu_buttons.get("quick-btn-reset")
    assert btn_reset is not None
    assert any(b.key == "f8" and b.action == "reset_c64u" for b in app.BINDINGS)

    app.action_refresh_connection()
    app.action_reset_c64u()


def test_export_tap_and_compile_d64_bindings(tk_app):
    app = tk_app
    assert any(b.key == "shift+f2" and b.action == "export_tap" for b in app.BINDINGS)
    assert any(b.key == "shift+f9" and b.action == "compile_d64" for b in app.BINDINGS)
    assert any(b.key == "f12" and b.action == "export_hyperload" for b in app.BINDINGS)
    assert app.root.bind("<F12>")
    assert "btn-export-d64" in app.menu_buttons


def test_tiered_menu_bar_and_bindings(tk_app):
    app = tk_app
    assert app.menu_bar is not None
    for col_id in ("col-file", "col-build", "col-device", "col-gamedev", "col-help"):
        assert col_id in app.col_frames

    for hdr_id in ("menu-btn-file", "menu-btn-build", "menu-btn-device", "menu-btn-gamedev", "menu-btn-help"):
        assert hdr_id in app.col_headers

    for btn_id in ("btn-gd-game", "btn-gd-build", "btn-gd-sprites", "btn-gd-tileset", "btn-gd-koala", "btn-gd-song",
                   "btn-gd-levels", "btn-gd-c64sim", "btn-gd-sim"):
        assert btn_id in app.menu_columns["gamedev"], f"Missing game dev button {btn_id}"

    for btn_id in (
        "btn-open",
        "btn-new-asm",
        "btn-save",
        "btn-export-tap",
        "btn-export-hyperload",
        "btn-export-d64",
        "btn-quit",
        "quick-btn-run",
        "btn-build",
        "btn-load-prg",
        "btn-refresh",
        "quick-btn-reset",
        "btn-pause-cpu",
        "btn-resume-cpu",
        "btn-screen-dump",
        "btn-c64u-reboot",
        "btn-play-sid",
        "btn-presets",
        "btn-help",
    ):
        assert btn_id in app.menu_buttons, f"Missing button {btn_id}"

    # Test focus navigation
    app.action_focus_menu()
    assert app.focused_button_id == "btn-open"

    app.action_focus_submenu("build")
    assert app.focused_button_id == "quick-btn-run"

    app.action_focus_submenu("device")
    assert app.focused_button_id == "btn-refresh"

    app.action_focus_submenu("help")
    assert app.focused_button_id == "btn-presets"

    app.navigate_menu_key("down")
    assert app.focused_button_id == "btn-help"

    # Game Dev column sits between Device and Help
    app.action_focus_submenu("gamedev")
    assert app.focused_button_id == "btn-gd-game"
    app.navigate_menu_key("right")
    assert app.focused_button_id == "btn-presets"
    app.action_focus_submenu("gamedev")
    app.navigate_menu_key("left")
    assert app.focused_button_id == "btn-refresh"

    # F9 is free: loading a file is how anything gets decompiled
    f_keys = [f"f{i}" for i in range(1, 13) if i != 9]
    shift_f_keys = [f"shift+f{i}" for i in range(1, 10)]
    bound_keys = [b.key for b in app.BINDINGS]

    for fk in f_keys:
        assert fk in bound_keys, f"Missing binding for {fk}"
    for sfk in shift_f_keys:
        assert sfk in bound_keys, f"Missing binding for {sfk}"


def test_copyright_caution_modal(tk_app):
    """Verify CopyrightCautionModal displays mandated warning text and responds to proceed/cancel."""
    app = tk_app
    result_holder = []

    modal = CopyrightCautionModal(filename="GAME.D64")
    assert "subject to copyright" in modal.message
    assert "technique review" in modal.message
    assert "self-improvement" in modal.message
    assert "Do not copy someone else's hard work" in modal.message
    assert "Learn from it, but don't be a thief!" in modal.message

    dlg = modal.show_tk(app, lambda val: result_holder.append(val))
    app.root.update_idletasks()
    modal.proceed_btn.invoke()
    app.root.update_idletasks()
    assert result_holder == [True]


def test_disk_select_modal(tk_app):
    """Verify DiskSelectModal displays files on D64 disk image and allows selection."""
    dummy_prg1 = bytes([0x01, 0x08, 0x00, 0x60])
    dummy_prg2 = bytes([0x00, 0xC0, 0x60])
    d64_bytes = create_d64(
        disk_name="TEST DISK",
        disk_id="2A",
        files=[("GAME A", dummy_prg1), ("GAME B", dummy_prg2)],
    )
    disk = read_d64(d64_bytes)

    app = tk_app
    result_holder = []
    modal = DiskSelectModal(disk)
    assert len(modal.prg_entries) == 2

    dlg = modal.show_tk(app, lambda entry: result_holder.append(entry))
    app.root.update_idletasks()
    modal.select_btn.invoke()
    app.root.update_idletasks()

    assert len(result_holder) == 1
    assert result_holder[0].filename == "GAME A"


def test_decompile_d64_action_flow(tk_app, tmp_path):
    """Verify _decompile_file_flow loads, decompiles D64 and updates UI state."""
    code = bytes([0x00, 0xC0, 0x78, 0xA9, 0x01, 0x8D, 0x20, 0xD0, 0x60])
    d64_bytes = create_d64(
        disk_name="DEMO DISK",
        disk_id="84",
        files=[("COLOR TEST", code)],
    )
    d64_file = tmp_path / "demo.d64"
    d64_file.write_bytes(d64_bytes)

    app = tk_app
    app._decompile_file_flow(d64_file)
    app.root.update_idletasks()

    asm_content = app.asm_text.get("1.0", "end-1c")
    py_content = app.py_text.get("1.0", "end-1c")
    assert app._active_tab == "tab-asm"
    assert "VIC_BORDER_COLOR" in asm_content
    assert "ETHICAL USE & COPYRIGHT CAUTION" in asm_content
    assert "Learn from it, but don't be a thief!" in asm_content
    assert "COLOR TEST" in asm_content
    assert "asm(" in py_content


def test_decompile_scope_modal_and_tap_flow(tk_app, tmp_path):
    """Verify DecompileScopeModal asks Loader / Main Game / Both and decompiles TAP into commented assembly."""
    app = tk_app
    tap_path = Path("example_games/Burger Time.tap")
    if not tap_path.exists():
        pytest.skip("Burger Time.tap not found")

    # Trigger _decompile_file_flow on multi-stage TAP -> opens DecompileScopeModal
    app._decompile_file_flow(tap_path)
    app.root.update_idletasks()

    modal = getattr(app, "_last_scope_modal", None)
    assert modal is not None
    assert modal.has_loader is True
    assert modal.has_main is True

    # Choose 'main' via the modal button
    modal.main_btn.invoke()
    app.root.update_idletasks()

    asm_main = app.asm_text.get("1.0", "end-1c")
    assert "+BUR1" in asm_main
    assert "PROGRAM ARCHITECTURE & HARDWARE ANALYSIS" in asm_main
    assert len(asm_main.splitlines()) > 1000

    # Also test choosing 'loader'
    app._decompile_file_flow(tap_path)
    app.root.update_idletasks()
    app._last_scope_modal.loader_btn.invoke()
    app.root.update_idletasks()
    asm_loader = app.asm_text.get("1.0", "end-1c")
    assert "BURGERTIME (TAPE LOADER)" in asm_loader

    # Also test choosing 'both'
    app._decompile_file_flow(tap_path)
    app.root.update_idletasks()
    app._last_scope_modal.both_btn.invoke()
    app.root.update_idletasks()
    asm_both = app.asm_text.get("1.0", "end-1c")
    assert "MULTI-STAGE DECOMPILATION" in asm_both
    assert "BURGERTIME (TAPE LOADER)" in asm_both
    assert "+BUR1 (MAIN GAME PART 1)" in asm_both


def test_kickass_update_modal_ui(tk_app):
    """Verify KickAssUpdateModal renders version status and handles user response."""
    from c64u_bridge.compiler import KickAssVersionStatus

    app = tk_app
    status = KickAssVersionStatus(
        installed_version="5.24",
        latest_version="5.25",
        update_available=True,
        jar_path=Path("tools/kickassembler/KickAss.jar"),
        status_message="KickAssembler update available: installed v5.24 -> latest v5.25!",
    )
    modal = KickAssUpdateModal(status)
    outcomes = []
    dlg = modal.show_tk(app, callback=lambda updated: outcomes.append(updated))
    app.root.update_idletasks()

    assert dlg.winfo_exists()
    assert "5.24" in modal.info_lbl.cget("text")
    assert "5.25" in modal.info_lbl.cget("text")
    assert "macro assembler" in modal.info_lbl.cget("text")

    modal.close_btn.invoke()
    app.root.update_idletasks()
    assert outcomes == [False]


# ---------------------------------------------------------------- the sequence


def _pump(app, done):
    """Let a background build finish and its result reach the window."""
    deadline = time.time() + 120

    def check():
        if done() or time.time() > deadline:
            app.root.quit()
        else:
            app.root.after(30, check)

    # background threads can only reach the window while its main loop runs
    app.root.after(30, check)
    app.root.mainloop()
    assert done(), "the build did not finish"
    app.root.update()


def _log(app):
    return app.log_text.get("1.0", "end-1c")


def test_starts_blank_with_nothing_to_build(tk_app):
    app = tk_app
    assert app.py_text.get("1.0", "end-1c") == ""
    assert app.asm_text.get("1.0", "end-1c") == ""
    assert app.loaded_file is None
    assert "NOTHING LOADED" in app.mode_badge_lbl.cget("text")
    app.action_build()
    app.action_run_c64u()
    assert app.last_prg_path is None


def test_loading_a_prg_shows_it_and_does_not_run_it(tk_app, tmp_path, monkeypatch):
    app = tk_app
    ran = []
    monkeypatch.setattr(app.client, "run_prg", lambda p: ran.append(p))
    prg = tmp_path / "game.prg"
    prg.write_bytes(bytes([0x00, 0xC0, 0xA9, 0x01, 0x8D, 0x20, 0xD0, 0x60]))

    app.load_project_file(prg)
    app._last_caution_modal.proceed_btn.invoke()
    app.root.update()

    assert ran == []
    assert "BasicUpstart" in app.asm_text.get("1.0", "end-1c") or "$C000" in app.asm_text.get("1.0", "end-1c")
    assert app.binary_source == prg
    # F5 runs the original, not a reassembly
    app.action_run_c64u()
    _pump(app, lambda: ran)
    assert ran == [prg]
    # and saving a disassembly never touches the binary
    before = prg.read_bytes()
    app.loaded_file = None if app.loaded_file == prg else app.loaded_file
    app._save_loaded_file()
    assert prg.read_bytes() == before


def test_loading_a_definition_shows_it_without_transpiling(tk_app, tmp_path):
    app = tk_app
    bank = tmp_path / "bank.py"
    create_definition("sprites", bank)
    app.load_project_file(bank)
    assert app.file_mode == "def"
    assert app.file_kind == "sprites"
    assert "GROUPS" in app.py_text.get("1.0", "end-1c")
    assert app.asm_text.get("1.0", "end-1c") == ""
    assert "SPRITE BANK" in app.left_title_lbl.cget("text")
    assert "Error" not in _log(app)


def test_f7_saves_the_edit_and_runs_the_right_tool(tk_app, tmp_path, monkeypatch):
    from c64u_bridge.tui import UnsavedChangesModal

    app = tk_app
    monkeypatch.setattr("c64u_bridge.tui.webbrowser.open", lambda *_: True)
    level = tmp_path / "lv.py"
    create_definition("levels", level)
    app.load_project_file(level)
    app.py_text.insert("end", "\n# edited\n")
    app.root.update_idletasks()
    app.action_build()
    assert isinstance(app._last_unsaved_modal, UnsavedChangesModal)
    app._last_unsaved_modal.save_btn.invoke()
    _pump(app, lambda: app.stage >= 2)
    assert "# edited" in level.read_text(encoding="utf-8")
    assert (tmp_path / "lv_levels.asm").is_file()


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_new_game_builds_and_runs_from_its_build_py(tk_app, tmp_path, monkeypatch):
    app = tk_app
    monkeypatch.setattr("c64u_bridge.tui.default_target_dir", lambda: tmp_path)
    ran = []
    monkeypatch.setattr(app.client, "run_prg", lambda p: ran.append(p))

    app._create_game("Space Race")
    manifest = tmp_path / "space_race" / "build.py"
    assert app.loaded_file == manifest
    assert "STEPS" in app.py_text.get("1.0", "end-1c")

    app.action_run_c64u()
    _pump(app, lambda: ran)
    assert ran == [tmp_path / "space_race" / "space_race.prg"]

    # a program file in the game builds the game, and F12 still makes a tape from it
    app.load_project_file(tmp_path / "space_race" / "space_race.asm")
    assert app.file_mode == "asm"
    app.stage = 1
    app.action_export_hyperload()
    _pump(app, lambda: (tmp_path / "space_race" / "space_race.tap").is_file())
    assert (tmp_path / "space_race" / "space_race.tap").read_bytes()[:12] == b"C64-TAPE-RAW"


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_new_definition_joins_the_game_it_is_created_in(tk_app, tmp_path, monkeypatch):
    app = tk_app
    monkeypatch.setattr("c64u_bridge.tui.default_target_dir", lambda: tmp_path)
    monkeypatch.setattr("c64u_bridge.tui.webbrowser.open", lambda *_: True)
    app._create_game("Pad")
    folder = tmp_path / "pad"
    app._create_definition("sprites", folder / "sprites" / "bank.py")
    assert app.loaded_file == folder / "sprites" / "bank.py"
    steps = (folder / "build.py").read_text(encoding="utf-8")
    assert steps.index('("sprites", "sprites/bank.py")') < steps.index('("asm", "pad.asm")')

    # F7 on the sprites builds the sprites; asking for a program builds the game
    app.action_build()
    _pump(app, lambda: (folder / "sprites" / "sprites.asm").is_file() and app.stage >= 2)
    got = []
    app._build_program(got.append)
    _pump(app, lambda: got)
    assert got == [folder / "pad.prg"]


def test_build_file_written_for_a_folder_then_loaded(tk_app, tmp_path):
    app = tk_app
    create_definition("levels", tmp_path / "lv.py")
    (tmp_path / "main.asm").write_text("BasicUpstart2(s)\ns: rts\n", encoding="utf-8")
    app._create_build_file(tmp_path)
    assert app.loaded_file == tmp_path / "build.py"
    assert app.file_kind == "build"
    text = app.py_text.get("1.0", "end-1c")
    assert '("levels", "lv.py")' in text and '("asm", "main.asm")' in text


def test_save_writes_what_is_loaded_and_asks_when_untitled(tk_app, tmp_path, monkeypatch):
    app = tk_app
    src = tmp_path / "tune.py"
    create_definition("song", src)
    app.load_project_file(src)
    app.py_text.insert("end", "# mine\n")
    app.action_save_file()
    assert "# mine" in src.read_text(encoding="utf-8")

    app.action_new_asm_template()
    named = tmp_path / "fresh.asm"
    monkeypatch.setattr("c64u_bridge.tui.filedialog.asksaveasfilename", lambda **_: str(named))
    app.action_save_file()
    assert app.loaded_file == named and "BasicUpstart2" in named.read_text(encoding="utf-8")


def test_a_failed_dma_run_reports_its_error(tk_app, tmp_path, monkeypatch):
    app = tk_app

    def refuse(_p):
        raise RuntimeError("no route to c64u")

    monkeypatch.setattr(app.client, "run_prg", refuse)
    prg = tmp_path / "x.prg"
    prg.write_bytes(b"\x01\x08\x00")
    app._dma_run(prg)
    _pump(app, lambda: "no route to c64u" in _log(app))


# ---------------------------------------------------------------- C64 Studio & Antigravity CLI


def test_hub_launcher_and_sprite_studio_integration(tk_app, monkeypatch):
    """Verify C64 Studio acts as the default platform hub and launches Sprite Studio & Validation Reports."""
    from unittest.mock import patch
    from c64u_bridge import cli

    app = tk_app
    assert "btn-sprite-studio" in app.menu_buttons
    assert "btn-validation-rep" in app.menu_buttons

    opened = []
    monkeypatch.setattr("c64u_bridge.tui.webbrowser.open", lambda url, *_: opened.append(url))
    app.action_open_sprite_studio()
    assert len(opened) == 1
    assert "sprite_studio.html" in opened[0]

    with patch("c64u_bridge.c64_studio.main") as mock_studio_main:
        cli.main([])
        mock_studio_main.assert_called_once_with([])

    for alias in ("c64-studio", "studio", "tui"):
        with patch("c64u_bridge.c64_studio.main") as mock_alias_main:
            cli.main([alias, "--no-boot"])
            mock_alias_main.assert_called_once_with(["--no-boot"])

    with patch("c64u_bridge.server.run_stdio_server") as mock_mcp:
        cli.main(["mcp"])
        mock_mcp.assert_called_once()


def test_c64_studio_rename_and_multi_language_ide_modes(tk_app, tmp_path, monkeypatch):
    """Verify C64 Studio rename, tui.py backwards compatibility, and ASM / C / Python IDE modes."""
    from c64u_bridge import c64_studio, tui

    assert c64_studio.C64StudioApp is tui.C64StudioApp
    assert tui.C64PythonToAsmApp is c64_studio.C64StudioApp

    app = tk_app
    assert "C64 STUDIO" in app.root.title()
    assert set(app.lang_buttons.keys()) == {"asm", "c", "py"}

    # 1. Switch to C / Oscar64 mode and generate C template
    app.action_select_language("c")
    app.root.update_idletasks()
    assert app.file_mode == "c"
    assert app.agy_lang_var.get() == "c"
    assert "C / C++ SOURCE" in app.left_title_lbl.cget("text")
    assert "int main(void)" in app.py_text.get("1.0", "end-1c")

    # Verify C syntax highlighting tags (opcode, directive, hardware) apply cleanly
    assert len(app.py_text.tag_ranges("opcode")) > 0
    assert len(app.py_text.tag_ranges("directive")) > 0
    assert len(app.py_text.tag_ranges("hardware")) > 0

    # Save C source in tmp_path
    monkeypatch.chdir(tmp_path)
    app.loaded_file = None
    app.action_save_assembly()
    saved_c = tmp_path / "output.c"
    assert saved_c.is_file()
    assert "int main(void)" in saved_c.read_text(encoding="utf-8")

    # 2. Switch to 6502 Assembly mode and load ASM starter template
    app.action_new_asm_template()
    app.root.update_idletasks()
    assert app.file_mode == "asm"
    assert "BasicUpstart2(start)" in app.asm_text.get("1.0", "end-1c")

    # 3. Switch to Python mode and load Python 6502 starter template
    app.action_new_py_template()
    app.root.update_idletasks()
    assert app.file_mode == "py"
    assert "C64 STUDIO" in app.py_text.get("1.0", "end-1c")
    assert "sta $d020" in app.asm_text.get("1.0", "end-1c").lower()


def test_agy_cli_connector_detection_install_mcp_and_prompt(tmp_path):
    """Verify AgyCliConnector auto-detection, installer, MCP registration, and code block extraction."""
    import io
    from unittest.mock import MagicMock, patch
    from c64u_bridge.agy_cli import (
        AgyCliConnector,
        build_c64_prompt,
        classify_code_block,
        extract_code_blocks,
    )

    p_asm = build_c64_prompt("make raster bars", language_mode="asm", current_code="* = $0810")
    assert "KickAssembler" in p_asm
    assert "```asm" in p_asm

    p_c = build_c64_prompt("bounce a sprite", language_mode="c", current_code="int main(void) {}")
    assert "Oscar64" in p_c
    assert "```c" in p_c
    assert "Game Project Structure" not in p_asm
    assert "Game Project Structure" not in p_c

    p_game = build_c64_prompt("Build a helicopter rescue game", language_mode="asm")
    assert "Game Project Structure" in p_game
    assert "game_dev/<slug>/build.py" in p_game
    assert "game/<slug>.asm" in p_game

    p_py = build_c64_prompt("play sid tone", language_mode="py", current_code="border_color(0)")
    assert "Python-to-6502" in p_py
    assert "```python" in p_py

    assert build_c64_prompt("/doctor", language_mode="asm") == "/doctor"

    sample_md = (
        "Here is your C64 program:\n"
        "```bash\nirm https://antigravity.google/cli/install.ps1 | iex\n```\n"
        "```c\n#include <stdint.h>\nint main(void) { *((volatile uint8_t*)0xD020) = 2; return 0; }\n```\n"
    )
    blocks = extract_code_blocks(sample_md, preferred_mode="asm")
    assert len(blocks) == 1
    assert blocks[0].studio_mode == "c"
    assert "0xD020" in blocks[0].code
    assert classify_code_block("", "BasicUpstart2(start)\nstart: lda #$01", "py") == "asm"

    conn_missing = AgyCliConnector(agy_bin=str(tmp_path / "nonexistent_agy.exe"), workspace_dir=tmp_path)
    with patch("shutil.which", return_value=None), patch.object(
        AgyCliConnector, "candidate_binary_paths", return_value=[]
    ):
        st_missing = conn_missing.detect_cli()
        assert st_missing.installed is False
        assert "antigravity.google/cli/install" in st_missing.install_command

    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_text("fake", encoding="utf-8")
    conn_ok = AgyCliConnector(agy_bin=str(fake_agy), workspace_dir=tmp_path)

    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="1.5.2\n", stderr=""),
            MagicMock(returncode=0, stdout="c64u-bridge: connected\n", stderr=""),
        ]
        st_ok = conn_ok.detect_cli()
        assert st_ok.installed is True
        assert st_ok.version == "1.5.2"
        assert st_ok.mcp_configured is True

    with patch("subprocess.run") as mock_mcp_run:
        mock_mcp_run.return_value = MagicMock(returncode=0, stdout="Added stdio MCP server c64u-bridge", stderr="")
        ok, msg = conn_ok.register_c64u_mcp(host="192.168.1.64", port=80)
        assert ok is True
        assert "c64u-bridge" in msg

    fake_stdout = io.StringIO(
        "Generating KickAssembler routine...\n"
        "```asm\nBasicUpstart2(start)\n* = $0810\nstart:\n    inc $d020\n    jmp start\n```\n"
    )
    fake_stderr = io.StringIO("")
    fake_proc = MagicMock()
    fake_proc.stdout = fake_stdout
    fake_proc.stderr = fake_stderr
    fake_proc.wait.return_value = 0

    streamed: list[str] = []
    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        res = conn_ok.run_prompt(
            "flash the border",
            language_mode="asm",
            exec_mode="accept-edits",
            continue_conversation=True,
            on_line=streamed.append,
        )
        assert res.success is True
        assert res.primary_code_block is not None
        assert res.primary_code_block.studio_mode == "asm"
        assert "inc $d020" in res.primary_code_block.code
        assert any("Generating KickAssembler" in ln for ln in streamed)
        called_cmd = mock_popen.call_args[0][0]
        assert "--mode" in called_cmd
        assert "--continue" in called_cmd
        assert "-p" in called_cmd


def test_c64_studio_agy_setup_modal_and_prompt_workflow(tk_app, tmp_path):
    """Verify AgySetupModal walkthrough and live Antigravity CLI prompting inside C64 Studio."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock
    from c64u_bridge.c64_studio import AgySetupModal

    app = tk_app

    missing_status = AgyStatus(
        installed=False,
        install_command="irm https://antigravity.google/cli/install.ps1 | iex",
        status_message="Antigravity CLI (agy) not detected on this system.",
    )
    with patch.object(app.agy, "detect_cli", return_value=missing_status):
        app.agy_prompt_var.set("Write a C64 raster bar demo")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

        assert app._last_agy_modal is not None
        modal_text = app._last_agy_modal.info_lbl.cget("text")
        assert "STEP 1" in modal_text
        assert "install.ps1" in modal_text
        assert "AUTO-INSTALL AGY CLI" in app._last_agy_modal.install_btn.cget("text")

        app._last_agy_modal.copy_btn.invoke()
        assert "install.ps1" in app.root.clipboard_get()

        app._last_agy_modal.close_btn.invoke()
        app.root.update_idletasks()

    installed_status = AgyStatus(
        installed=True,
        binary_path=Path("C:/Users/test/AppData/Local/agy/bin/agy.exe"),
        version="1.5.2",
        mcp_configured=True,
        install_command="irm https://antigravity.google/cli/install.ps1 | iex",
        status_message="Antigravity CLI v1.5.2 detected",
    )
    c_code = (
        "#include <stdint.h>\n"
        "int main(void) {\n"
        "    *((volatile uint8_t*)0xD020) = 6;\n"
        "    for (;;) {}\n"
        "}\n"
    )
    mock_result = AgyPromptResult(
        success=True,
        response_text=f"Here is your Oscar64 C program:\n```c\n{c_code}```",
        stderr="",
        return_code=0,
        command=["agy", "-p", "..."],
        code_blocks=[ExtractedCodeBlock(language_tag="c", studio_mode="c", code=c_code)],
    )

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", return_value=mock_result
    ) as mock_run_prompt:
        app.action_select_language("c")
        app.agy_auto_apply_var.set(True)
        app.agy_prompt_var.set("Set the VIC-II border to blue in Oscar64 C")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

        mock_run_prompt.assert_called_once()
        assert app.file_mode == "c"
        assert "0xD020" in app.py_text.get("1.0", "end-1c")
        assert "Extracted C code block" in app.agy_chat_text.get("1.0", "end-1c")
        assert "v1.5.2" in app.btn_agy_status.cget("text")

    # Verify touched_files + code_blocks does NOT create a duplicate unnamed tab
    disk_asm = tmp_path / "disk_game.asm"
    disk_asm.write_text('BasicUpstart2(start)\n* = $0810\nstart:\n    rts\n', encoding="utf-8")
    app.open_tabs.clear()
    app.active_file_tab_id = None
    app.loaded_file = None
    app.py_text.delete("1.0", "end")
    app.asm_text.delete("1.0", "end")
    touched_result = AgyPromptResult(
        success=True,
        response_text="Updated disk_game.asm:\n```asm\n; snippet\n```",
        stderr="",
        return_code=0,
        command=["agy", "-p", "..."],
        code_blocks=[ExtractedCodeBlock(language_tag="asm", studio_mode="asm", code="; snippet\n")],
        touched_files=[disk_asm],
    )
    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", return_value=touched_result
    ):
        app.agy_auto_apply_var.set(True)
        app.agy_prompt_var.set("Create disk_game.asm")
        app.action_send_agy_prompt()
        app.root.update_idletasks()
        assert len(app.open_tabs) == 1
        assert app.open_tabs[0].loaded_file == disk_asm.resolve()
        assert "BasicUpstart2(start)" in app.asm_text.get("1.0", "end-1c")

    modal_ok = AgySetupModal(app.agy, installed_status)
    dlg_ok = modal_ok.show_tk(app)
    app.root.update_idletasks()
    assert dlg_ok.winfo_exists()
    assert "UPDATE AGY CLI" in modal_ok.install_btn.cget("text")
    modal_ok.close_btn.invoke()
    app.root.update_idletasks()


def test_agy_cli_stream_json_and_headless_permission_detection(tmp_path):
    """Verify NDJSON stream-json token/tool callbacks, file-write fallback, and silent headless error detection."""
    import io
    import json
    from unittest.mock import MagicMock, patch
    from c64u_bridge.agy_cli import (
        AgyCliConnector,
        build_c64_prompt,
        extract_streaming_code_preview,
        infer_prompt_language,
    )

    # 1. Partial streaming code preview & language inference
    partial_md = "Sure! Streaming your raster routine:\n```asm\nBasicUpstart2(start)\n* = $0810\nstart:\n    inc $d020"
    preview = extract_streaming_code_preview(partial_md, preferred_mode="py")
    assert preview is not None
    assert preview.studio_mode == "asm"
    assert "inc $d020" in preview.code
    assert extract_streaming_code_preview("```bash\necho hi", preferred_mode="asm") is None

    assert infer_prompt_language("Write a raster split in KickAssembler", fallback_mode="py") == "asm"
    assert infer_prompt_language("Build a SID player in Oscar64", fallback_mode="asm") == "c"
    assert infer_prompt_language("Add a bassline", fallback_mode="def") == "def"

    def_prompt = build_c64_prompt("Add an arpeggio pattern", language_mode="def")
    assert "PATTERNS" in def_prompt
    assert "Do NOT invoke `run_command`" in def_prompt

    # 2. Stream-JSON NDJSON parsing + callbacks
    fake_agy = tmp_path / "agy.exe"
    fake_agy.write_text("fake", encoding="utf-8")
    conn = AgyCliConnector(agy_bin=str(fake_agy), workspace_dir=tmp_path)

    written_asm = tmp_path / "generated_demo.asm"
    written_asm.write_text("BasicUpstart2(start)\n* = $0810\nstart:\n    dec $d020\n    jmp start\n", encoding="utf-8")

    ndjson_events = [
        {"event": "init", "conversation_id": "conv-12345678-abcd"},
        {"event": "step_update", "step_update": {"step_type": "user_input", "state": "DONE"}},
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "ACTIVE",
                "tool_name": "write_file",
                "tool_info": {"name": "write_file", "parameters": {"Path": str(written_asm)}},
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "step_type": "tool",
                "state": "DONE",
                "tool_name": "write_file",
                "tool_info": {"name": "write_file", "parameters": {"Path": str(written_asm)}},
            },
        },
        {
            "event": "step_update",
            "step_update": {
                "step_type": "agent_response",
                "state": "ACTIVE",
                "text_delta": "Wrote `generated_demo.asm` for you!",
            },
        },
        {
            "event": "result",
            "result": {
                "status": "SUCCESS",
                "conversation_id": "conv-12345678-abcd",
                "response": "Wrote `generated_demo.asm` for you!",
            },
        },
    ]
    fake_proc = MagicMock()
    fake_proc.stdout = io.StringIO("\n".join(json.dumps(e) for e in ndjson_events) + "\n")
    fake_proc.stderr = io.StringIO("")
    fake_proc.wait.return_value = 0

    deltas: list[str] = []
    statuses: list[str] = []
    file_writes: list[Path] = []
    with patch("subprocess.Popen", return_value=fake_proc) as mock_popen:
        res = conn.run_prompt(
            "create generated_demo.asm",
            language_mode="asm",
            effort="low",
            on_delta=deltas.append,
            on_status=statuses.append,
            on_file_write=lambda p, _txt: file_writes.append(p),
        )
        called_cmd = mock_popen.call_args[0][0]
        assert "--output-format" in called_cmd
        assert "stream-json" in called_cmd
        assert "--effort" in called_cmd
        assert "low" in called_cmd

    assert res.success is True
    assert res.conversation_id == "conv-12345678-abcd"
    assert written_asm.resolve() in res.touched_files
    assert file_writes == [written_asm.resolve()]
    assert any("AGY CONNECTED" in s for s in statuses)
    assert any("write_file" in s for s in statuses)
    assert "generated_demo.asm" in "".join(deltas)
    # Fallback extracted the written .asm file even though response_text had no fenced block
    assert res.primary_code_block is not None
    assert res.primary_code_block.studio_mode == "asm"
    assert "dec $d020" in res.primary_code_block.code

    # 3. Silent headless permission failure (rc == 0, empty stdout, permission error on stderr)
    silent_fail_proc = MagicMock()
    silent_fail_proc.stdout = io.StringIO(
        json.dumps({"event": "result", "result": {"status": "SUCCESS", "response": ""}}) + "\n"
    )
    silent_fail_proc.stderr = io.StringIO(
        "jetski: no output produced — a tool required the 'command' permission that headless mode cannot prompt for, so it was auto-denied.\n"
    )
    silent_fail_proc.wait.return_value = 0

    with patch("subprocess.Popen", return_value=silent_fail_proc):
        fail_res = conn.run_prompt("run a shell command", language_mode="asm")
    assert fail_res.success is False
    assert fail_res.error_message is not None
    assert "headless mode" in fail_res.error_message
    assert "auto" in fail_res.error_message


def test_c64_studio_live_streaming_and_external_cli_sync(tk_app, tmp_path, monkeypatch):
    """Verify live editor preview during token streaming and external CLI file/MCP sync into C64 Studio."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock
    from c64u_bridge.server import emit_studio_bridge_event

    app = tk_app
    installed_status = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        status_message="Antigravity CLI v1.5.6 detected",
    )

    asm_code = "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$05\n    sta $d020\n    jmp start\n"
    streamed_snapshots: list[str] = []

    def _fake_streaming_run_prompt(prompt, **kwargs):
        on_status = kwargs.get("on_status")
        on_delta = kwargs.get("on_delta")
        if on_status:
            on_status("AGY CONNECTED (1234abcd) — READING C64 CONTEXT...")
            on_status("AGY THINKING...")
        if on_delta:
            on_delta("Streaming ASM:\n```asm\nBasicUpstart2(start)\n* = $0810\nstart:\n    lda #$05\n")
            streamed_snapshots.append(app.asm_text.get("1.0", "end-1c"))
            on_delta("    sta $d020\n    jmp start\n```\n")
        return AgyPromptResult(
            success=True,
            response_text=f"Streaming ASM:\n```asm\n{asm_code}```",
            stderr="",
            return_code=0,
            command=["agy"],
            code_blocks=[ExtractedCodeBlock(language_tag="asm", studio_mode="asm", code=asm_code)],
        )

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", side_effect=_fake_streaming_run_prompt
    ):
        app.agy_auto_apply_var.set(True)
        app.agy_prompt_var.set("Set the border color to green in KickAssembler")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

    # Verified mid-stream live preview populated asm_text BEFORE run_prompt even finished
    assert streamed_snapshots and "lda #$05" in streamed_snapshots[0]
    assert app.file_mode == "asm"
    assert app._active_tab == "tab-asm"
    assert "sta $d020" in app.asm_text.get("1.0", "end-1c")
    assert "AGY CONNECTED" in app.agy_chat_text.get("1.0", "end-1c")

    # Test external CLI workspace file sync + MCP bridge event journal tailing
    events_file = tmp_path / "studio_events.jsonl"
    monkeypatch.setenv("C64U_STUDIO_EVENTS_FILE", str(events_file))
    old_ws = app.agy.workspace_dir
    try:
        app.agy.workspace_dir = tmp_path
        app.agy_watch_cli_var.set(True)
        app._init_external_cli_watch_state()

        ext_asm = tmp_path / "cli_created.asm"
        ext_asm.write_text(
            "BasicUpstart2(main)\n* = $0810\nmain:\n    lda #$02\n    sta $d020\n    rts\n",
            encoding="utf-8",
        )
        app._poll_external_cli_activity()
        app.root.update_idletasks()

        assert app.loaded_file == ext_asm.resolve()
        assert app.file_mode == "asm"
        assert app.agy_lang_var.get() == "asm"
        assert "lda #$02" in app.asm_text.get("1.0", "end-1c")
        assert "Live-synced `cli_created.asm`" in app.agy_chat_text.get("1.0", "end-1c")

        # Unsaved manual edits in editor must NOT be overwritten by external disk changes
        app.asm_text.insert("end-1c", "\n    // manual unsaved edit\n")
        assert app._is_editor_dirty() is True
        ext_asm.write_text(
            "BasicUpstart2(main)\n* = $0810\nmain:\n    lda #$07\n    sta $d020\n    rts\n",
            encoding="utf-8",
        )
        app._poll_external_cli_activity()
        assert "manual unsaved edit" in app.asm_text.get("1.0", "end-1c")
        assert "unsaved editor edits preserved" in app.agy_chat_text.get("1.0", "end-1c")

        # Reset clean state and verify MCP bridge journal events show up live in C64 Studio
        app._mark_editor_synced()
        fake_prg = tmp_path / "cli_created.prg"
        fake_prg.write_bytes(b"\x01\x08\x00")
        emit_studio_bridge_event(
            "start",
            "c64_build_and_run",
            summary="Building & DMA-running cli_created.asm (kickass)",
            source_path=ext_asm,
        )
        emit_studio_bridge_event(
            "done",
            "c64_build_and_run",
            ok=True,
            summary="Built cli_created.asm -> cli_created.prg (3 bytes) & DMA launched on C64U",
            source_path=ext_asm,
            prg_path=fake_prg,
        )
        app._poll_external_cli_activity()
        chat_dump = app.agy_chat_text.get("1.0", "end-1c")
        assert "[CLI → MCP] Building & DMA-running cli_created.asm" in chat_dump
        assert "[CLI → MCP] Built cli_created.asm -> cli_created.prg" in chat_dump
        assert app.last_prg_path == fake_prg.resolve()
    finally:
        app.agy.workspace_dir = old_ws


def test_single_screen_editor_and_asm_toggle_workflow(tk_app, tmp_path):
    """Verify the unified single-screen editor, Show ASM toggle, PY->ASM promotion, and single-editor agy_cli focus."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock

    app = tk_app

    # 1. Single-screen workspace: only one unified pane in workspace_frame (no side-by-side split)
    assert len(app.workspace_frame.winfo_children()) == 1
    assert app.workspace_frame.winfo_children()[0] is app.right_pane

    # 2. Python mode displays ONLY source_view_frame (py_text), hiding asm_view_frame
    app.action_select_language("py")
    app._set_python_text('print("HELLO SINGLE SCREEN")\n')
    assert app.file_mode == "py"
    assert app.asm_focus_mode is False
    assert app.source_view_frame.winfo_manager() == "pack"
    assert app.asm_view_frame.winfo_manager() == ""
    assert "SHOW ASM" in app.btn_show_asm.cget("text")

    # 3. Toggling btn_show_asm auto-transpiles Python -> 6502 ASM and swaps to asm_view_frame
    app.btn_show_asm.invoke()
    assert app.asm_focus_mode is True
    assert app.asm_view_frame.winfo_manager() == "pack"
    assert app.source_view_frame.winfo_manager() == ""
    assert "HIDE ASM" in app.btn_show_asm.cget("text")
    assert app.btn_back_to_source.winfo_manager() == "pack"
    assert app.btn_promote_asm.winfo_manager() == "pack"
    assert "HELLO SINGLE SCREEN" in app.asm_text.get("1.0", "end-1c").upper() or "$FFD2" in app.asm_text.get(
        "1.0", "end-1c"
    ).upper()

    # 4. Clicking '⬅ BACK TO PYTHON (^E)' hides ASM and restores the single Python editor
    app.btn_back_to_source.invoke()
    assert app.asm_focus_mode is False
    assert app.source_view_frame.winfo_manager() == "pack"
    assert app.asm_view_frame.winfo_manager() == ""

    # 5. Source comment toggle handles '#' in Python mode and '//' in C mode
    app.py_text.mark_set("insert", "1.0")
    app.action_toggle_source_comment()
    assert app.py_text.get("1.0", "1.end").startswith("# ")
    app.action_toggle_source_comment()
    assert app.py_text.get("1.0", "1.end").startswith("print(")

    # 6. Clicking '⚡ PY → ASM' converts and opens ASM view; '✎ EDIT AS .ASM' promotes to native ASM mode
    app.btn_py_to_asm.invoke()
    assert app.asm_focus_mode is True
    assert app.asm_view_frame.winfo_manager() == "pack"

    app.btn_promote_asm.invoke()
    assert app.file_mode == "asm"
    assert app.asm_focus_mode is False
    assert app.asm_view_frame.winfo_manager() == "pack"
    assert app.source_view_frame.winfo_manager() == ""
    assert app.btn_back_to_source.winfo_manager() == ""
    assert app.btn_promote_asm.winfo_manager() == ""

    # 7. agy_cli with AUTO-APPLY stays focused on the single main editor while streaming Python code
    app.action_select_language("py")
    installed_status = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        status_message="Antigravity CLI v1.5.6 detected",
    )
    py_code = 'BORDER_COLOR = 0xD020\npoke(BORDER_COLOR, 6)\nprint("STREAMED IN MAIN EDITOR")\n'
    active_tabs_during_stream: list[str] = []
    source_packed_during_stream: list[str] = []

    def _fake_py_stream(_prompt, **kwargs):
        on_delta = kwargs.get("on_delta")
        if on_delta:
            on_delta(f"```python\n{py_code}```\n")
            active_tabs_during_stream.append(app._active_tab)
            source_packed_during_stream.append(app.source_view_frame.winfo_manager())
        return AgyPromptResult(
            success=True,
            response_text=f"```python\n{py_code}```",
            stderr="",
            return_code=0,
            command=["agy"],
            code_blocks=[ExtractedCodeBlock(language_tag="python", studio_mode="py", code=py_code)],
        )

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", side_effect=_fake_py_stream
    ):
        app.agy_auto_apply_var.set(True)
        app.agy_lang_var.set("py")
        app.agy_prompt_var.set("Write a Python C64 border color test")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

    assert active_tabs_during_stream == ["tab-asm"]
    assert source_packed_during_stream == ["pack"]
    assert app._active_tab == "tab-asm"
    assert app.file_mode == "py"
    assert app.source_view_frame.winfo_manager() == "pack"
    assert app.asm_view_frame.winfo_manager() == ""
    assert "STREAMED IN MAIN EDITOR" in app.py_text.get("1.0", "end-1c")

    # Pure Q&A response (no code blocks) switches to 5:AI CONSOLE so the user can read the answer
    def _fake_qa_stream(_prompt, **_kwargs):
        return AgyPromptResult(
            success=True,
            response_text="The VIC-II border color register is at $D020 (53280).",
            stderr="",
            return_code=0,
            command=["agy"],
            code_blocks=[],
        )

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", side_effect=_fake_qa_stream
    ):
        app.agy_prompt_var.set("What address is the border color register?")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

    assert app._active_tab == "tab-agy"


def test_collapsible_menu_drawer_labels_toggle_and_clean_badges(tk_app, tmp_path):
    """Verify the collapsible menu drawer, 1-click ribbon, ASM labels toggle, and clean AGY status pill."""
    from c64u_bridge.agy_cli import AgyStatus

    app = tk_app

    # Ensure clean default state even if earlier tests opened the menu
    app.close_menu_drawer()
    assert app._open_menu_category is None
    assert app.menu_bar.winfo_manager() == ""

    # Opening a single category shows only that submenu in a compact grid
    app.toggle_menu_category("gamedev")
    assert app._open_menu_category == "gamedev"
    assert app.menu_bar.winfo_manager() == "pack"
    assert app.col_frames["col-gamedev"].winfo_manager() == "grid"
    assert app.col_frames["col-file"].winfo_manager() == ""

    # Invoking any menu item automatically tucks the menu drawer away
    app.menu_buttons["btn-new-asm"].invoke()
    assert app._open_menu_category is None
    assert app.menu_bar.winfo_manager() == ""
    assert app.file_mode == "asm"

    # F10 (action_focus_menu) toggles ALL MENUS open and closed
    app.action_focus_menu()
    assert app._open_menu_category == "all"
    assert app.menu_bar.winfo_manager() == "pack"
    for cid in ("col-file", "col-build", "col-device", "col-gamedev", "col-help"):
        assert app.col_frames[cid].winfo_manager() == "grid"
    app.action_focus_menu()
    assert app._open_menu_category is None
    assert app.menu_bar.winfo_manager() == ""

    # Collapsible 6502 ASM labels sidebar toggle
    assert app._show_asm_labels is True
    assert app.label_nav_frame.winfo_manager() == "pack"
    app.action_toggle_asm_labels()
    assert app._show_asm_labels is False
    assert app.label_nav_frame.winfo_manager() == ""
    assert "OFF" in app.btn_toggle_labels.cget("text")
    app.action_toggle_asm_labels()
    assert app._show_asm_labels is True
    assert app.label_nav_frame.winfo_manager() == "pack"
    assert "ON" in app.btn_toggle_labels.cget("text")

    # AGY status badge never displays 'vdetected'
    app._refresh_agy_badge(
        AgyStatus(installed=True, binary_path=tmp_path / "agy.exe", version="detected")
    )
    assert "vdetected" not in app.btn_agy_status.cget("text")
    assert app.btn_agy_status.cget("text") == "● AGY READY"

    app._refresh_agy_badge(
        AgyStatus(installed=True, binary_path=tmp_path / "agy.exe", version="1.5.6")
    )
    assert app.btn_agy_status.cget("text") == "● AGY v1.5.6"

    app._refresh_agy_badge(AgyStatus(installed=False, binary_path=None, version=None))
    assert app.btn_agy_status.cget("text") == "! AGY SETUP"


def test_new_file_and_load_file_type_filters_flow(tk_app, tmp_path):
    """Verify NewFileModal (C, Py, ASM, SID) and OpenFileModal type filters load files into the IDE code window."""
    from c64u_bridge.tui import NEW_SID_TEMPLATE, NewFileModal, OpenFileModal

    app = tk_app

    # 1. NewFileModal creates C, Py, ASM, and SID files directly in the IDE editor
    for choice, expected_mode, expected_kind, expected_tab in (
        ("c", "c", "c", "1:EDITOR [C]"),
        ("py", "py", "python", "1:EDITOR [PY]"),
        ("asm", "asm", "asm", "1:EDITOR [ASM]"),
        ("sid", "asm", "sid", "1:EDITOR [SID]"),
    ):
        app.action_new_file_dialog()
        app.root.update_idletasks()
        assert isinstance(app._last_new_file_modal, NewFileModal)
        assert app._last_new_file_modal.dlg is not None
        getattr(app._last_new_file_modal, f"btn_{choice}").invoke()
        app.root.update_idletasks()
        assert app.file_mode == expected_mode
        assert app.file_kind == expected_kind
        assert app._active_tab == "tab-asm"
        assert app.tab_buttons["tab-asm"].cget("text") == expected_tab

    assert "C64U_SID_METADATA:" in app.asm_text.get("1.0", "end-1c")

    # 2. OpenFileModal filters by C, Py, ASM, and SID and loads into the IDE code window
    (tmp_path / "demo.c").write_text("int main(void) { return 0; }\n", encoding="utf-8")
    (tmp_path / "demo.py").write_text("border_color(2)\n", encoding="utf-8")
    (tmp_path / "demo.asm").write_text("BasicUpstart2(s)\ns: rts\n", encoding="utf-8")
    (tmp_path / "tune_sid.asm").write_text(NEW_SID_TEMPLATE, encoding="utf-8")

    modal = OpenFileModal(initial_path=tmp_path)
    picked: list[Path | None] = []
    dlg = modal.show_tk(app, picked.append)
    app.root.update_idletasks()

    modal.set_type_filter("c")
    items_c = "\n".join(modal.listbox.get(0, "end"))
    assert "demo.c" in items_c
    assert "demo.py" not in items_c
    assert "demo.asm" not in items_c

    modal.set_type_filter("py")
    items_py = "\n".join(modal.listbox.get(0, "end"))
    assert "demo.py" in items_py
    assert "demo.c" not in items_py

    modal.set_type_filter("asm")
    items_asm = "\n".join(modal.listbox.get(0, "end"))
    assert "demo.asm" in items_asm
    assert "demo.c" not in items_asm

    dlg.destroy()

    # Loading a saved SID driver .asm auto-detects SID source mode in the IDE editor
    app.load_project_file(tmp_path / "tune_sid.asm")
    assert app.file_mode == "asm"
    assert app.file_kind == "sid"
    assert app._active_tab == "tab-asm"
    assert "SID_INIT" in app.asm_text.get("1.0", "end-1c")


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_compile_test_first_autofix_modal_and_send_to_c64u(tk_app, tmp_path, monkeypatch):
    """Verify compile-test-first flow for ASM/Py/SID, CompileErrorFixModal (Yes->AGY / No->IDE), and Send to C64U."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock
    from c64u_bridge.tui import CompileErrorFixModal

    app = tk_app
    monkeypatch.chdir(tmp_path)

    dma_runs: list[Path] = []
    sid_plays: list[Path] = []
    monkeypatch.setattr(app.client, "run_prg", lambda p: dma_runs.append(p))
    monkeypatch.setattr(app.client, "play_sid", lambda p: sid_plays.append(p))

    # 1. Valid SID starter compiles cleanly on F7 without uploading, and SEND TO C64U uploads/plays it
    app.action_new_sid_template()
    app.action_build()
    assert app._last_compile_error is None
    assert app.last_sid_path is not None and app.last_sid_path.is_file()
    assert app.last_sid_path.read_bytes()[:4] == b"PSID"
    assert sid_plays == []

    app.action_send_to_c64u()
    assert sid_plays == [app.last_sid_path]

    # 2. Broken SID edits fail compile test, block SEND TO C64U, and pop CompileErrorFixModal
    sid_plays.clear()
    app._set_asm_text(app.asm_text.get("1.0", "end-1c") + "\n    sta unknown_sid_register\n")
    app.action_send_to_c64u()
    assert app._last_unsaved_modal is not None
    app._last_unsaved_modal.compile_unsaved_btn.invoke()
    app.root.update_idletasks()
    assert sid_plays == []
    assert isinstance(app._last_compile_error_modal, CompileErrorFixModal)
    assert "SID MUSIC COMPILE" in app._last_compile_error_modal.stage_title

    # Choosing 'NO — FIX MYSELF IN IDE' closes modal, stays on 1:EDITOR, and highlights offending line
    app._last_compile_error_modal.fix_in_ide_btn.invoke()
    app.root.update_idletasks()
    assert app._active_tab == "tab-asm"
    assert len(app.asm_text.tag_ranges("find_match")) > 0

    # 3. Broken ASM fails compile test -> Choosing 'YES — AUTO-FIX WITH ANTIGRAVITY' fixes code in IDE!
    broken_asm = "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$02\n    sta typo_border_reg\n    rts\n"
    fixed_asm = "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$02\n    sta $d020\n    rts\n"
    app.action_new_asm_template()
    app._set_asm_text(broken_asm)

    app.action_send_to_c64u()
    assert app._last_unsaved_modal is not None
    app._last_unsaved_modal.compile_unsaved_btn.invoke()
    app.root.update_idletasks()
    assert dma_runs == []
    assert app._last_compile_error_modal is not None
    assert "typo_border_reg" in app._last_compile_error_modal.error_detail

    installed_status = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        status_message="Antigravity CLI v1.5.6 detected",
    )
    mock_fix_res = AgyPromptResult(
        success=True,
        response_text=f"Fixed the symbol typo:\n```asm\n{fixed_asm}```",
        stderr="",
        return_code=0,
        command=["agy"],
        code_blocks=[ExtractedCodeBlock(language_tag="asm", studio_mode="asm", code=fixed_asm)],
    )
    sent_prompts: list[str] = []

    def _capture_autofix(prompt, **_kw):
        sent_prompts.append(prompt)
        return mock_fix_res

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", side_effect=_capture_autofix
    ):
        app._last_compile_error_modal.autofix_btn.invoke()
        app.root.update_idletasks()

    assert len(sent_prompts) == 1
    assert "typo_border_reg" in sent_prompts[0]
    assert "sta $d020" in app.asm_text.get("1.0", "end-1c")
    assert app._active_tab == "tab-asm"

    # Now SEND TO C64U prompts to save unsaved AGY edits, compiles cleanly, and DMA-runs on C64U
    app.action_send_to_c64u()
    assert app._last_unsaved_modal is not None
    app._last_unsaved_modal.compile_unsaved_btn.invoke()
    _pump(app, lambda: dma_runs)
    assert len(dma_runs) == 1 and dma_runs[0].is_file()


def test_game_generation_menu_and_modal(tk_app, tmp_path, monkeypatch):
    """Verify GAME GEN menu tools and GameAssetGenModal (Sprite Studio + AI Sprite/SID/Game generation)."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock
    from c64u_bridge.tui import GameAssetGenModal

    app = tk_app
    assert "btn-gd-ai-gen" in app.menu_buttons
    assert "btn-gd-ai-gen" in app.menu_columns["gamedev"]

    opened_urls: list[str] = []
    monkeypatch.setattr("c64u_bridge.tui.webbrowser.open", lambda url, *_: opened_urls.append(url))

    app.action_open_game_generator_dialog("sprites")
    app.root.update_idletasks()
    modal = app._last_game_gen_modal
    assert isinstance(modal, GameAssetGenModal)
    assert modal.dlg is not None and modal.dlg.winfo_exists()

    modal.sprite_studio_btn.invoke()
    assert len(opened_urls) == 1 and "sprite_studio.html" in opened_urls[0]

    # Re-open generator modal, select playable arcade game preset in Python format, and generate into IDE
    app.action_open_game_generator_dialog("sprites")
    app.root.update_idletasks()
    modal = app._last_game_gen_modal
    assert isinstance(modal, GameAssetGenModal)
    modal.select_kind("full_game")
    modal.target_fmt_var.set("py")
    modal.desc_var.set("Galaga-style starfighter wave shooter")

    installed_status = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        status_message="Antigravity CLI v1.5.6 detected",
    )
    generated_py = 'border_color(0)\nbackground_color(0)\nprint("STARFIGHTER READY")\n'
    mock_game_res = AgyPromptResult(
        success=True,
        response_text=f"```python\n{generated_py}```",
        stderr="",
        return_code=0,
        command=["agy"],
        code_blocks=[ExtractedCodeBlock(language_tag="python", studio_mode="py", code=generated_py)],
    )

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", return_value=mock_game_res
    ) as mock_run:
        modal.generate_btn.invoke()
        app.root.update_idletasks()

    mock_run.assert_called_once()
    assert app.file_mode == "py"
    assert app._active_tab == "tab-asm"
    assert "STARFIGHTER READY" in app.py_text.get("1.0", "end-1c")


def test_c64_studio_bat_launcher_is_portable_crlf():
    """Ensure C64-Studio.bat uses pure ASCII + CRLF for cmd.exe and sets PYTHONPATH=%~dp0src."""
    bat = Path(__file__).resolve().parent.parent / "C64-Studio.bat"
    assert bat.is_file()
    raw = bat.read_bytes()
    assert raw.isascii(), "Windows .bat files with if-blocks must stay pure ASCII so cmd.exe byte offsets match"
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), "C64-Studio.bat must use CRLF line endings"
    text = raw.decode("ascii")
    assert "PYTHONPATH=%~dp0src" in text
    assert "-m c64u_bridge" in text


def test_custom_and_manifest_build_py_directs_game_compilation(tk_app, tmp_path, monkeypatch):
    """Verify loading any build.py (custom Python script or STEPS manifest) runs build.py to direct compilation."""
    from c64u_bridge.project import classify_file
    from c64u_bridge.tui import CompileErrorFixModal, OpenFileModal

    app = tk_app
    ran: list[Path] = []
    monkeypatch.setattr(app.client, "run_prg", lambda p: ran.append(p))

    # Create a custom standalone Python build.py (no STEPS list — runs Python code to build the game .prg)
    game_dir = tmp_path / "star_raider"
    game_dir.mkdir()
    build_py = game_dir / "build.py"
    build_py.write_text(
        'import pathlib\n'
        'def main():\n'
        '    here = pathlib.Path(__file__).resolve().parent\n'
        '    # Emit a valid C64 PRG ($C000: LDA #$01, STA $D020, RTS)\n'
        '    prg = here / "star_raider.prg"\n'
        '    prg.write_bytes(bytes([0x00, 0xC0, 0xA9, 0x01, 0x8D, 0x20, 0xD0, 0x60]))\n'
        '    print("Custom build.py compiled star_raider.prg!")\n'
        'if __name__ == "__main__":\n'
        '    main()\n',
        encoding="utf-8",
    )

    assert classify_file(build_py) == "build"

    # Verify OpenFileModal BUILD.PY filter surfaces build.py clearly
    modal = OpenFileModal(initial_path=game_dir)
    dlg = modal.show_tk(app, lambda _p: None)
    modal.set_type_filter("build")
    listing = "\n".join(modal.listbox.get(0, "end"))
    assert "build.py" in listing and "BUILD" in listing
    dlg.destroy()

    # Load build.py into IDE: must NOT transpile as 6502 Python; shows in 1:EDITOR [BUILD.PY]
    app.load_project_file(build_py)
    assert app.loaded_file == build_py
    assert app.file_kind == "build"
    assert app.file_mode == "def"
    assert app.tab_buttons["tab-asm"].cget("text") == "1:EDITOR [BUILD.PY]"
    assert "RUN BUILD.PY" in app.btn_py_to_asm.cget("text")

    # Even if user clicks PY mode button while build.py is loaded, F7 / F5 still runs build.py
    app.file_mode = "py"
    app.action_build()
    expected_prg = game_dir / "star_raider.prg"
    _pump(app, lambda: app.last_prg_path == expected_prg)
    assert expected_prg.is_file()
    assert "Custom build.py compiled star_raider.prg!" in _log(app)
    assert ran == []

    # SEND TO C64U [F5] runs build.py and DMA-uploads star_raider.prg
    app.action_send_to_c64u()
    _pump(app, lambda: ran)
    assert ran == [expected_prg]

    # Failing build.py pops UnsavedChangesModal first, then CompileErrorFixModal instead of uploading stale PRG
    ran.clear()
    app._set_python_text('import sys\nprint("Asset packer failed on level 3!")\nsys.exit(1)\n')
    app.action_send_to_c64u()
    assert app._last_unsaved_modal is not None
    app._last_unsaved_modal.save_btn.invoke()
    _pump(app, lambda: app._last_compile_error is not None)
    assert ran == []
    assert isinstance(app._last_compile_error_modal, CompileErrorFixModal)
    assert "Asset packer failed on level 3!" in app._last_compile_error_modal.error_detail
    app._last_compile_error_modal.fix_in_ide_btn.invoke()


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_build_options_tap_hypertap_and_d64(tk_app, tmp_path):
    """Verify building .tap, Hyper.tap (.hyper.tap), .d64, and ALL from ribbon, BuildOutputModal, menu, and build.py."""
    from c64u_bridge.tui import BuildOutputModal

    app = tk_app
    for bid in ("btn-build-options", "btn-build-tap", "btn-build-hypertap", "btn-build-d64", "btn-build-all"):
        assert bid in app.menu_buttons
        assert bid in app.menu_columns["build"]

    # Default ribbon state is .PRG
    assert app.build_format_var.get() == "prg"
    assert app.btn_build_format.cget("text") == "OUT: .PRG"

    # Right-click / cycle_build_format cycles cleanly across all 5 targets
    assert app.cycle_build_format() == "tap"
    assert app.btn_build_format.cget("text") == "OUT: .TAP"
    assert app.cycle_build_format() == "hypertap"
    assert app.btn_build_format.cget("text") == "OUT: HYPER.TAP"
    assert app.cycle_build_format() == "d64"
    assert app.btn_build_format.cget("text") == "OUT: .D64"
    assert app.cycle_build_format() == "all"
    assert app.btn_build_format.cget("text") == "OUT: ALL"
    assert app.cycle_build_format() == "prg"
    assert app.btn_build_format.cget("text") == "OUT: .PRG"

    # Prepare a single-file ASM game and verify modal + 1-click builds for .tap, Hyper.tap, and .d64
    asm_file = tmp_path / "orbit.asm"
    asm_file.write_text(
        "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$06\n    sta $d020\n    rts\n",
        encoding="utf-8",
    )
    app.load_project_file(asm_file)

    # Open BuildOutputModal, choose Hyper.tap, and click BUILD NOW
    app.action_open_build_options()
    app.root.update_idletasks()
    modal = app._last_build_output_modal
    assert isinstance(modal, BuildOutputModal)
    assert modal.dlg is not None and modal.dlg.winfo_exists()
    modal.select_format("hypertap")
    modal.build_now_btn.invoke()
    app.root.update_idletasks()

    assert app.btn_build_format.cget("text") == "OUT: HYPER.TAP"
    assert (tmp_path / "orbit.prg").is_file()
    hyper_tap = tmp_path / "orbit.hyper.tap"
    assert hyper_tap.is_file()
    assert hyper_tap.read_bytes()[:12] == b"C64-TAPE-RAW"
    assert app.last_hyper_tap_path == hyper_tap

    # Build .tap via action_build_with_format("tap")
    app.action_build_with_format("tap")
    std_tap = tmp_path / "orbit.tap"
    assert std_tap.is_file()
    assert std_tap.read_bytes()[:12] == b"C64-TAPE-RAW"
    assert app.last_tap_path == std_tap

    # Build .d64 via action_build_with_format("d64")
    app.action_build_with_format("d64")
    d64_img = tmp_path / "orbit.d64"
    assert d64_img.is_file()
    assert d64_img.stat().st_size == 174848
    assert app.last_d64_path == d64_img

    # Custom build.py game with ALL selected produces .prg + .tap + .hyper.tap + .d64 in one build!
    game_dir = tmp_path / "nebula_run"
    game_dir.mkdir()
    build_py = game_dir / "build.py"
    build_py.write_text(
        'import pathlib\n'
        'here = pathlib.Path(__file__).resolve().parent\n'
        '# Raw $C000 machine-code PRG (tests automatic --entry detection for Hyper.tap too!)\n'
        '(here / "nebula_run.prg").write_bytes(bytes([0x00, 0xC0, 0xA9, 0x05, 0x8D, 0x20, 0xD0, 0x60]))\n',
        encoding="utf-8",
    )
    app.load_project_file(build_py)
    app.set_build_format("all")
    app.action_build()
    _pump(
        app,
        lambda: (game_dir / "nebula_run.d64").is_file()
        and (game_dir / "nebula_run.hyper.tap").is_file()
        and (game_dir / "nebula_run.tap").is_file(),
    )
    assert (game_dir / "nebula_run.prg").is_file()
    assert (game_dir / "nebula_run.tap").read_bytes()[:12] == b"C64-TAPE-RAW"
    assert (game_dir / "nebula_run.hyper.tap").read_bytes()[:12] == b"C64-TAPE-RAW"
    assert (game_dir / "nebula_run.d64").stat().st_size == 174848

    # Reset back to default .prg for subsequent tests
    app.set_build_format("prg")


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_build_tool_cli_tap_hypertap_d64_flags(tmp_path):
    """Verify tools/build/build_tool.py CLI --tap, --hypertap, and --d64 flags."""
    import subprocess
    import sys

    game_dir = tmp_path / "cli_racer"
    game_dir.mkdir()
    (game_dir / "cli_racer.asm").write_text(
        "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$01\n    sta $d020\n    rts\n",
        encoding="utf-8",
    )
    manifest = game_dir / "build.py"
    manifest.write_text('TITLE = "CLI Racer"\nSTEPS = [("asm", "cli_racer.asm")]\n', encoding="utf-8")

    build_tool = Path(__file__).resolve().parent.parent / "tools" / "build" / "build_tool.py"
    res = subprocess.run(
        [sys.executable, str(build_tool), str(manifest), "--tap", "--hypertap", "--d64"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    assert (game_dir / "cli_racer.prg").is_file()
    assert (game_dir / "cli_racer.tap").is_file()
    assert (game_dir / "cli_racer.hyper.tap").is_file()
    assert (game_dir / "cli_racer.d64").stat().st_size == 174848


@pytest.mark.skipif(shutil.which("java") is None, reason="KickAssembler needs Java")
def test_multi_file_tabs_agy_edits_star_indicator_and_save_prompt_before_compile(tk_app, tmp_path):
    """Verify multi-file tabs, preserving AGY edits across file loads/tab switches, '*' dirty badge, and pre-compile save prompt."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus, ExtractedCodeBlock
    from c64u_bridge.tui import UnsavedChangesModal

    app = tk_app
    game_dir = tmp_path / "tab_quest"
    game_dir.mkdir()

    orig_asm = (
        "BasicUpstart2(start)\n"
        "* = $0810\n"
        "start:\n"
        "    lda #$00\n"
        "    sta $d020\n"
        "    rts\n"
    )
    agy_updated_asm = (
        "BasicUpstart2(start)\n"
        "* = $0810\n"
        "start:\n"
        "    lda #$07  // AGY yellow border\n"
        "    sta $d020\n"
        "    rts\n"
    )
    agy_bg_asm = (
        "BasicUpstart2(start)\n"
        "* = $0810\n"
        "start:\n"
        "    lda #$05  // AGY green border while user viewed build.py\n"
        "    sta $d020\n"
        "    rts\n"
    )

    hero_asm = game_dir / "hero.asm"
    hero_asm.write_text(orig_asm, encoding="utf-8")

    build_py = game_dir / "build.py"
    build_py.write_text(
        "import pathlib, sys\n"
        "here = pathlib.Path(__file__).resolve().parent\n"
        "src = (here / 'hero.asm').read_text(encoding='utf-8')\n"
        "if 'AGY green border' not in src:\n"
        "    print('hero.asm was NOT saved before build.py ran!')\n"
        "    sys.exit(1)\n"
        "(here / 'tab_quest.prg').write_bytes(bytes([0x00, 0xC0, 0xA9, 0x05, 0x8D, 0x20, 0xD0, 0x60]))\n"
        "print('Built tab_quest.prg with saved AGY edits!')\n",
        encoding="utf-8",
    )

    # 1. Load hero.asm -> opens clean tab without '*'
    app.load_project_file(hero_asm)
    assert [t.display_name() for t in app.open_tabs] == ["hero.asm"]
    hero_tab = app.open_tabs[0]
    assert not hero_tab.is_dirty

    installed_status = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        status_message="Antigravity CLI v1.5.6 detected",
    )
    mock_res_1 = AgyPromptResult(
        success=True,
        response_text=f"Updated border color:\n```asm\n{agy_updated_asm}```",
        stderr="",
        return_code=0,
        command=["agy"],
        code_blocks=[ExtractedCodeBlock(language_tag="asm", studio_mode="asm", code=agy_updated_asm)],
    )

    # 2. AGY edits hero.asm in IDE -> marks tab dirty with '*' so loading another file won't lose it!
    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", return_value=mock_res_1
    ):
        app.agy_prompt_var.set("Make border yellow")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

    assert hero_tab.is_dirty
    assert hero_tab.display_name() == "hero.asm *"
    assert "HERO.ASM *" in app.left_title_lbl.cget("text")
    assert "hero.asm *" in app.file_tab_buttons[hero_tab.tab_id].cget("text")
    assert app.btn_save_all_tabs.cget("text") == "SAVE *"
    assert hero_asm.read_text(encoding="utf-8") == orig_asm  # Disk untouched until user saves

    # 3. Load build.py -> BOTH tabs remain open, hero.asm * keeps AGY's unsaved changes!
    app.load_project_file(build_py)
    assert [t.display_name() for t in app.open_tabs] == ["hero.asm *", "build.py"]
    build_tab = app.open_tabs[1]
    assert app.active_file_tab_id == build_tab.tab_id
    assert "tab_quest.prg" in app.py_text.get("1.0", "end-1c")

    # Click back to hero.asm * tab -> AGY's code is 100% preserved!
    app.file_tab_buttons[hero_tab.tab_id].invoke()
    app.root.update_idletasks()
    assert app.active_file_tab_id == hero_tab.tab_id
    assert "AGY yellow border" in app.asm_text.get("1.0", "end-1c")

    # 4. Start another AGY prompt on hero.asm *, then switch to build.py mid-flight ->
    #    AGY writes into origin_tab_id (hero.asm *) without clobbering build.py!
    mock_res_2 = AgyPromptResult(
        success=True,
        response_text=f"Switched to green border:\n```asm\n{agy_bg_asm}```",
        stderr="",
        return_code=0,
        command=["agy"],
        code_blocks=[ExtractedCodeBlock(language_tag="asm", studio_mode="asm", code=agy_bg_asm)],
    )

    def _run_while_user_switches_tabs(prompt, **_kw):
        app.switch_file_tab(build_tab.tab_id)
        return mock_res_2

    with patch.object(app.agy, "detect_cli", return_value=installed_status), patch.object(
        app.agy, "run_prompt", side_effect=_run_while_user_switches_tabs
    ):
        app.agy_prompt_var.set("Make border green")
        app.action_send_agy_prompt()
        app.root.update_idletasks()

    assert app.active_file_tab_id == build_tab.tab_id
    assert "tab_quest.prg" in app.py_text.get("1.0", "end-1c")  # build.py NOT clobbered!
    assert "AGY green border" in hero_tab.asm_content
    assert hero_tab.is_dirty

    # 5. Compiling from build.py while hero.asm * is unsaved prompts UnsavedChangesModal!
    app.action_build()
    modal = app._last_unsaved_modal
    assert isinstance(modal, UnsavedChangesModal)
    assert modal.mode == "compile"
    assert [t.display_name() for t in modal.dirty_tabs] == ["hero.asm *"]

    # Cancel aborts compile and keeps hero.asm * dirty
    modal.cancel_btn.invoke()
    app.root.update_idletasks()
    assert hero_tab.is_dirty
    assert not (game_dir / "tab_quest.prg").exists()

    # Compile again -> click 'SAVE & COMPILE' -> saves hero.asm, clears '*', and build.py succeeds!
    app.action_build()
    modal = app._last_unsaved_modal
    assert isinstance(modal, UnsavedChangesModal)
    modal.save_btn.invoke()
    _pump(app, lambda: (game_dir / "tab_quest.prg").is_file())

    assert not hero_tab.is_dirty
    assert [t.display_name() for t in app.open_tabs] == ["hero.asm", "build.py"]
    assert "AGY green border" in hero_asm.read_text(encoding="utf-8")

    # 6. Open a standalone .asm file, make an in-memory edit, and test 'COMPILE WITHOUT SAVING' + close prompt
    standalone_asm = tmp_path / "standalone.asm"
    standalone_asm.write_text(orig_asm, encoding="utf-8")
    app.load_project_file(standalone_asm)
    standalone_tab = app._get_active_file_tab()
    assert standalone_tab is not None
    app._set_asm_text(agy_bg_asm.replace("lda #$05", "lda #$02"))
    assert standalone_tab.display_name() == "standalone.asm *"

    app.action_build()
    assert isinstance(app._last_unsaved_modal, UnsavedChangesModal)
    app._last_unsaved_modal.compile_unsaved_btn.invoke()
    app.root.update_idletasks()
    assert standalone_tab.is_dirty  # Still dirty on disk!
    assert "lda #$00" in standalone_asm.read_text(encoding="utf-8")  # Disk file NOT overwritten!
    assert (tmp_path / "standalone.prg").is_file()

    # Closing dirty standalone.asm * prompts UnsavedChangesModal(mode="close")
    app.close_file_tab(standalone_tab.tab_id)
    close_modal = app._last_unsaved_modal
    assert isinstance(close_modal, UnsavedChangesModal)
    assert close_modal.mode == "close"
    close_modal.discard_btn.invoke()
    app.root.update_idletasks()
    assert [t.display_name() for t in app.open_tabs] == ["hero.asm", "build.py"]


def test_agy_cli_model_effort_persistence_and_live_file_follow(shared_root, tmp_path, monkeypatch):
    """Verify persistent CLI model & effort options across restarts and live IDE file-following when CLI edits a file."""
    from unittest.mock import patch
    from c64u_bridge.agy_cli import AgyPromptResult, AgyStatus
    from c64u_bridge.tui import AgySetupModal, C64StudioApp

    settings_file = tmp_path / "studio_settings.json"
    monkeypatch.setenv("C64U_STUDIO_SETTINGS", str(settings_file))

    app1 = C64StudioApp(root=shared_root, skip_boot=True, start_maximized=False)
    shared_root.update_idletasks()

    # 1. Open CLI options modal (AgySetupModal), pick model & effort -> persists to studio_settings.json
    st = AgyStatus(
        installed=True,
        binary_path=tmp_path / "agy.exe",
        version="1.5.6",
        mcp_configured=True,
        models=[
            ("", "Default CLI Model"),
            ("gemini-4-hydrogen-medium", "Gemini 4 Hydrogen (Medium)"),
            ("claude-opus-5-5-high", "Claude Opus 5.5 (High)"),
        ],
        status_message="Antigravity CLI v1.5.6 detected",
    )
    with patch.object(app1.agy, "detect_cli", return_value=st):
        app1.action_open_agy_setup()
    modal = app1._last_agy_modal
    assert isinstance(modal, AgySetupModal)
    assert hasattr(modal, "model_menu") and hasattr(modal, "effort_menu")

    app1.agy_model_var.set("gemini-4-hydrogen-medium")
    app1.agy_effort_var.set("xhigh")
    shared_root.update_idletasks()
    modal.dlg.destroy()

    assert settings_file.is_file()
    saved_txt = settings_file.read_text(encoding="utf-8")
    assert "gemini-4-hydrogen-medium" in saved_txt
    assert "xhigh" in saved_txt

    # 2. Restart IDE -> saved model & effort are automatically restored and passed to CLI calls!
    for child in list(shared_root.winfo_children()):
        child.destroy()
    app2 = C64StudioApp(root=shared_root, skip_boot=True, start_maximized=False)
    shared_root.update_idletasks()
    assert app2.agy_model_var.get() == "gemini-4-hydrogen-medium"
    assert app2.agy_effort_var.get() == "xhigh"

    # 3. When CLI edits a file on disk (even while user is on 5:AGY AI tab), IDE opens & shows the file + edited line!
    target_asm = tmp_path / "scroller.asm"
    target_asm.write_text(
        "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$00\n    sta $d020\n    rts\n",
        encoding="utf-8",
    )
    app2.switch_tab("tab-agy")
    assert app2._active_tab == "tab-agy"

    captured_calls: list[dict] = []

    def _fake_run_prompt(prompt, **kw):
        captured_calls.append({"prompt": prompt, **kw})
        # Simulate CLI tool starting edit, then writing updated file on disk
        if kw.get("on_file_edit_start"):
            kw["on_file_edit_start"](target_asm)
        updated = "BasicUpstart2(start)\n* = $0810\nstart:\n    lda #$0e  // CLI light blue\n    sta $d020\n    rts\n"
        target_asm.write_text(updated, encoding="utf-8")
        if kw.get("on_file_write"):
            kw["on_file_write"](target_asm, updated)
        return AgyPromptResult(
            success=True,
            response_text="Updated border color in scroller.asm.",
            stderr="",
            return_code=0,
            command=["agy"],
            touched_files=[target_asm],
        )

    with patch.object(app2.agy, "detect_cli", return_value=st), patch.object(
        app2.agy, "run_prompt", side_effect=_fake_run_prompt
    ):
        app2.agy_prompt_var.set("Change border to light blue")
        app2.action_send_agy_prompt()
        shared_root.update_idletasks()

    assert len(captured_calls) == 1
    assert captured_calls[0]["model"] == "gemini-4-hydrogen-medium"
    assert captured_calls[0]["effort"] == "xhigh"
    assert app2.loaded_file == target_asm.resolve()
    assert app2._active_tab == "tab-asm"
    assert "CLI light blue" in app2.asm_text.get("1.0", "end-1c")
    assert len(app2.asm_text.tag_ranges("agy_edit_line")) > 0








