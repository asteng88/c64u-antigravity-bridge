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
    assert "ZX Spectrum" not in THEMES
    assert THEMES["Commodore 64"]["border_idle"] == "#70A4B2"
    assert THEMES["Commodore 64"]["paper"] == "#352879"
    assert "PetMe64.ttf" in FONT_CREDITS_TEXT
    assert "Kreative Korporation" in FONT_CREDITS_TEXT
    assert "Faerie" in FONT_CREDITS_TEXT
    assert "BackMeUpScotty" in FONT_CREDITS_TEXT


def test_c64_boot_sequence_simulation(shared_root):
    """Verify C64 startup screen pretends to LOAD \"C64-BRIDGE\",8,1 with brief loading lines."""
    app = C64PythonToAsmApp(root=shared_root, skip_boot=False, start_maximized=False)
    shared_root.update_idletasks()

    assert app._boot_active is True
    assert app.boot_canvas is not None

    # Step through typing LOAD "C64-BRIDGE",8,1 (steps 1..6)
    for _ in range(6):
        app._advance_boot_sequence()
    assert 'LOAD "C64-BRIDGE",8,1' in app._boot_lines

    # Step 7: SEARCHING FOR C64-BRIDGE / LOADING
    app._advance_boot_sequence()
    assert "SEARCHING FOR C64-BRIDGE" in app._boot_lines
    assert "LOADING" in app._boot_lines
    assert app._border_busy is True

    # Steps 8..11: Brief loading lines
    for _ in range(4):
        app._advance_boot_sequence()
    joined = "\n".join(app._boot_lines)
    assert "6502 ASSEMBLER" in joined
    assert "PYTHON TRANSPILER" in joined
    assert "D64/TAP/SID ENGINE" in joined
    assert "C64U HARDWARE BRIDGE" in joined

    # Step 12: READY. / RUN
    app._advance_boot_sequence()
    assert "READY." in app._boot_lines
    assert "RUN" in app._boot_lines

    # Finish boot sequence
    app._finish_boot_sequence()
    assert app._boot_active is False


def test_tui_app_mount_and_fullscreen_toggle(tk_app):
    """Verify main studio widgets mount properly and F11 fullscreen toggles cleanly."""
    app = tk_app
    assert app.py_text is not None
    assert app.asm_text is not None

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
    app = tk_app
    monkeypatch.setattr("c64u_bridge.tui.webbrowser.open", lambda *_: True)
    level = tmp_path / "lv.py"
    create_definition("levels", level)
    app.load_project_file(level)
    app.py_text.insert("end", "\n# edited\n")
    app.action_build()
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
