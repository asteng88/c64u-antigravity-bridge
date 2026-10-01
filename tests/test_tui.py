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

        # Verify Tiered Menu Bar and Quick Run button exist
        btn_file = app.query_one("#menu-btn-file", Button)
        assert btn_file is not None
        btn_quick_run = app.query_one("#quick-btn-run", Button)
        assert btn_quick_run is not None


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
async def test_refresh_connection_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        # Trigger F4 action directly
        app.action_refresh_connection()
        await pilot.pause()


@pytest.mark.anyio
async def test_reset_c64u_button_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        btn_reset = app.query_one("#quick-btn-reset", Button)
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
async def test_export_tap_and_action():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        # Verify Ctrl+T and Shift+F2 bindings are registered
        assert any(b.key == "ctrl+t" and b.action == "export_tap" for b in app.BINDINGS)
        assert any(b.key == "shift+f2" and b.action == "export_tap" for b in app.BINDINGS)

        # Trigger action directly
        app.action_export_tap()
        await pilot.pause()


@pytest.mark.anyio
async def test_tiered_menu_bar_and_bindings():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        # Check Menu Bar has the 5 tiered category buttons + quick action buttons
        menu_bar = app.query_one("#menu-bar")
        assert menu_bar is not None
        menu_buttons = menu_bar.query(Button)
        assert len(menu_buttons) == 7
        button_ids = [b.id for b in menu_buttons]
        assert button_ids == [
            "menu-btn-file",
            "menu-btn-build",
            "menu-btn-device",
            "menu-btn-sid",
            "menu-btn-help",
            "quick-btn-run",
            "quick-btn-reset",
        ]

        # Test opening the File menu dropdown
        btn_file = app.query_one("#menu-btn-file", Button)
        btn_file.press()
        await pilot.pause()

        # Check that MenuDropdownModal opened
        from c64u_bridge.tui import MenuDropdownModal
        modal = app.screen
        assert isinstance(modal, MenuDropdownModal)
        assert modal.category == "file"

        # Check options in the dropdown
        opts = modal.query_one("#menu-dropdown-options")
        assert opts is not None
        assert opts.option_count >= 4

        # Test switching categories via Left/Right navigation
        modal.action_menu_next()
        assert modal.category == "build"
        modal.action_menu_next()
        assert modal.category == "device"
        modal.action_menu_prev()
        assert modal.category == "build"

        # Test closing menu via escape
        modal.action_dismiss_menu()
        await pilot.pause()
        assert not isinstance(app.screen, MenuDropdownModal)

        # Check F1-F8 and Shift+F1-Shift+F8 key bindings
        f_keys = [f"f{i}" for i in range(1, 9)]
        shift_f_keys = [f"shift+f{i}" for i in range(1, 9)]
        bound_keys = [b.key for b in app.BINDINGS]

        for fk in f_keys:
            assert fk in bound_keys, f"Missing binding for {fk}"
        for sfk in shift_f_keys:
            assert sfk in bound_keys, f"Missing binding for {sfk}"

        assert "ctrl+d" in bound_keys
        assert "ctrl+b" in bound_keys
        assert "ctrl+p" in bound_keys
        assert "f10" in bound_keys
        assert "alt+f" in bound_keys
        assert "alt+b" in bound_keys
        assert "alt+c" in bound_keys
        assert "alt+s" in bound_keys
        assert "alt+h" in bound_keys

