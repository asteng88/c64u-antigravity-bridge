import pytest
from c64u_bridge.tui import C64PythonToAsmApp
from textual.widgets import TextArea, RichLog, Tree


@pytest.mark.anyio
async def test_tui_app_mount():
    app = C64PythonToAsmApp()
    async with app.run_test() as pilot:
        editor = app.query_one("#python-editor", TextArea)
        assert editor is not None
        assert "while True:" in editor.text

        asm_viewer = app.query_one("#asm-viewer", TextArea)
        assert asm_viewer is not None

        log = app.query_one("#build-log", RichLog)
        assert log is not None

        tree = app.query_one("#ast-tree", Tree)
        assert tree is not None
