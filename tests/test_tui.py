import pytest
from pathlib import Path
from c64u_bridge.tui import C64PythonToAsmApp, FilteredDirectoryTree, OpenFileModal
from textual.widgets import Button, TabbedContent, TextArea, RichLog, Tree


@pytest.mark.anyio
async def test_tui_app_mount():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        editor = app.query_one("#python-editor", TextArea)
        assert editor is not None
        assert "while True:" in editor.text

        asm_viewer = app.query_one("#asm-viewer", TextArea)
        assert asm_viewer is not None
        assert not asm_viewer.read_only

        log = app.query_one("#build-log", RichLog)
        assert log is not None

        tree = app.query_one("#ast-tree", Tree)
        assert tree is not None

        # Verify Open File (F3) button exists in toolbar
        btn_open = app.query_one("#btn-open", Button)
        assert btn_open is not None


@pytest.mark.anyio
async def test_filtered_directory_tree():
    fdt = FilteredDirectoryTree(".")
    test_paths = [
        Path(".git"),
        Path(".venv"),
        Path("__pycache__"),
        Path("game_dev"),
        Path("game_dev/choplifter.asm"),
        Path("game_dev/choplifter.prg"),
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


@pytest.mark.anyio
async def test_load_assembly_file():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        asm_path = Path("game_dev/choplifter.asm")
        if asm_path.exists():
            app.load_project_file(asm_path)
            assert app.file_mode == "asm"
            assert app.loaded_file == asm_path

            asm_viewer = app.query_one("#asm-viewer", TextArea)
            assert "CHOPLIFTER" in asm_viewer.text
            tabs = app.query_one("#tabs", TabbedContent)
            assert tabs.active == "tab-asm"

            # Verify LHS editor is blank since choplifter has no Python conversion
            editor = app.query_one("#python-editor", TextArea)
            assert editor.text == ""

        # Test loading an ASM file that has an available Python conversion
        rainbow_asm = Path("examples/rainbow_border.asm")
        if rainbow_asm.exists():
            app.load_project_file(rainbow_asm)
            assert app.file_mode == "asm"
            editor = app.query_one("#python-editor", TextArea)
            assert "border_color" in editor.text


@pytest.mark.anyio
async def test_load_python_file():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        py_path = Path("examples/rainbow_border.py")
        if py_path.exists():
            app.load_project_file(py_path)
            assert app.file_mode == "py"
            assert app.loaded_file == py_path

            editor = app.query_one("#python-editor", TextArea)
            assert "border_color" in editor.text or len(editor.text) > 0


@pytest.mark.anyio
async def test_open_file_modal_composition():
    modal = OpenFileModal()
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        app.push_screen(modal)
        await pilot.pause()
        assert modal.query_one("#jump-game-dev", Button) is not None
        assert modal.query_one("#jump-examples", Button) is not None
        assert modal.query_one("#jump-root", Button) is not None
        assert modal.query_one("#file-tree", FilteredDirectoryTree) is not None
        modal.dismiss(None)


@pytest.mark.anyio
async def test_refresh_connection_button_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        btn_refresh = app.query_one("#btn-refresh", Button)
        assert btn_refresh is not None

        # Trigger F4 action directly
        app.action_refresh_connection()
        await pilot.pause()

        # Trigger via button click
        btn_refresh.press()
        await pilot.pause()


@pytest.mark.anyio
async def test_reset_c64u_button_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        btn_reset = app.query_one("#btn-c64u-reset", Button)
        assert btn_reset is not None

        # Verify F8 binding is registered
        assert any(b.key == "f8" and b.action == "reset_c64u" for b in app.BINDINGS)

        # Trigger action directly
        app.action_reset_c64u()
        await pilot.pause()

        # Trigger via button press
        btn_reset.press()
        await pilot.pause()


@pytest.mark.anyio
async def test_export_tap_button_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        btn_tap = app.query_one("#btn-export-tap", Button)
        assert btn_tap is not None

        # Verify Ctrl+T binding is registered
        assert any(b.key == "ctrl+t" and b.action == "export_tap" for b in app.BINDINGS)

        # Trigger action directly
        app.action_export_tap()
        await pilot.pause()

        # Trigger via button press
        btn_tap.press()
        await pilot.pause()


@pytest.mark.anyio
async def test_two_row_toolbar_menu_and_bindings():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        # Check Row 1 has 8 buttons (F1-F8 in order)
        row1 = app.query_one("#toolbar-row-1")
        assert row1 is not None
        row1_buttons = row1.query(Button)
        assert len(row1_buttons) == 8
        row1_ids = [b.id for b in row1_buttons]
        assert row1_ids == [
            "btn-help",
            "btn-presets",
            "btn-open",
            "btn-refresh",
            "btn-run",
            "btn-transpile",
            "btn-assemble",
            "btn-c64u-reset",
        ]

        # Check Row 2 has 8 buttons (Shift+F1 to Shift+F8)
        row2 = app.query_one("#toolbar-row-2")
        assert row2 is not None
        row2_buttons = row2.query(Button)
        assert len(row2_buttons) == 8
        row2_ids = [b.id for b in row2_buttons]
        assert row2_ids == [
            "btn-save",
            "btn-export-tap",
            "btn-load-prg",
            "btn-pause-cpu",
            "btn-resume-cpu",
            "btn-screen-dump",
            "btn-c64u-reboot",
            "btn-quit",
        ]

        # Check F1-F8 and Shift+F1-Shift+F8 key bindings
        f_keys = [f"f{i}" for i in range(1, 9)]
        shift_f_keys = [f"shift+f{i}" for i in range(1, 9)]
        bound_keys = [b.key for b in app.BINDINGS]

        for fk in f_keys:
            assert fk in bound_keys, f"Missing binding for {fk}"
        for sfk in shift_f_keys:
            assert sfk in bound_keys, f"Missing binding for {sfk}"




