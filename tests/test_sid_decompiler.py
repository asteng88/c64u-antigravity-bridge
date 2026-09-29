from pathlib import Path

import pytest

from c64u_bridge.compiler import CompilationResult
from c64u_bridge.sid_compiler import build_sid, compile_sid_source
from c64u_bridge.sid_decompiler import SidDecompileError, decompile_sid, parse_sid
from c64u_bridge.tui import C64PythonToAsmApp
from textual.widgets import TextArea


def make_sid(*, embedded_load: bool = False) -> bytes:
    load = 0 if embedded_load else 0x1000
    payload = bytes(
        [
            0xA9, 0x00,              # lda #$00
            0x8D, 0x18, 0xD4,        # sta $d418
            0x60,                    # rts
            0xA9, 0x01,              # play: lda #$01
            0xD0, 0xFC,              # bne play
            0x60,                    # rts (unreachable but preserved)
            0x02, 0xFF,              # undocumented/data bytes
        ]
    )
    header = bytearray(0x7C)
    header[0:4] = b"PSID"
    header[4:6] = (2).to_bytes(2, "big")
    header[6:8] = (0x7C).to_bytes(2, "big")
    header[8:10] = load.to_bytes(2, "big")
    header[10:12] = (0x1000).to_bytes(2, "big")
    header[12:14] = (0x1006).to_bytes(2, "big")
    header[14:16] = (1).to_bytes(2, "big")
    header[16:18] = (1).to_bytes(2, "big")
    header[22:54] = b"TEST TUNE".ljust(32, b"\0")
    header[54:86] = b"CODEX".ljust(32, b"\0")
    header[86:118] = b"2026".ljust(32, b"\0")
    header[118:120] = (0x14).to_bytes(2, "big")  # PAL + 6581
    if embedded_load:
        payload = b"\x00\x10" + payload
    return bytes(header) + payload


def test_parse_sid_with_embedded_load_address():
    sid = parse_sid(make_sid(embedded_load=True))
    assert sid.header.load_address == 0x1000
    assert sid.header.init_address == 0x1000
    assert sid.header.clock == "PAL"
    assert sid.header.model == "6581"
    assert sid.payload.startswith(b"\xA9\x00")


def test_decompile_sid_recovers_code_and_preserves_data():
    result = decompile_sid(make_sid())
    assert "sid_init:" in result.assembly
    assert "sid_play:" in result.assembly
    assert "sta  $d418  // SID FILTER_MODE_VOLUME" in result.assembly
    assert "bne  sid_play" in result.assembly
    assert ".byte $02,$ff" in result.assembly
    assert "SID_LOAD = 0x1000" in result.python
    assert 'asm("""' in result.python
    assert "C64U_SID_METADATA:" in result.assembly
    assert "C64U_SID_METADATA:" in result.python
    assert result.instruction_count == 6
    assert result.data_byte_count == 2


def test_invalid_sid_is_rejected():
    with pytest.raises(SidDecompileError, match="PSID/RSID"):
        decompile_sid(b"not a sid file" + bytes(200))


@pytest.mark.parametrize("embedded_load", [False, True])
def test_build_sid_round_trips_original_container(embedded_load: bool):
    original = make_sid(embedded_load=embedded_load)
    sid = parse_sid(original)
    assert build_sid(sid, sid.payload) == original


def test_compile_decompiled_sid_with_preserved_metadata(tmp_path: Path):
    original = make_sid(embedded_load=True)
    result = decompile_sid(original)
    source_path = tmp_path / "music_decompiled.asm"
    source_path.write_text(result.assembly, encoding="utf-8")

    class FakeCompiler:
        def compile(self, source_path, output_prg, assembler):
            output = Path(output_prg)
            output.write_bytes((0x1000).to_bytes(2, "little") + result.sid.payload)
            return CompilationResult(True, output, "assembled", "")

    compiled = compile_sid_source(source_path, compiler=FakeCompiler())
    assert compiled.output_sid.name == "music_compiled.sid"
    assert compiled.output_sid.read_bytes() == original


def test_compile_decompiled_python_uses_embedded_metadata(tmp_path: Path):
    original = make_sid(embedded_load=True)
    result = decompile_sid(original)
    source_path = tmp_path / "standalone_decompiled.py"
    source_path.write_text(result.python, encoding="utf-8")

    class FakeCompiler:
        def compile(self, source_path, output_prg, assembler):
            output = Path(output_prg)
            output.write_bytes((0x1000).to_bytes(2, "little") + result.sid.payload)
            return CompilationResult(True, output, "assembled", "")

    compiled = compile_sid_source(source_path, compiler=FakeCompiler())
    assert compiled.output_sid.read_bytes() == original


@pytest.mark.anyio
async def test_tui_sid_import_writes_and_loads_sidecars(tmp_path: Path):
    sid_path = tmp_path / "music.sid"
    sid_path.write_bytes(make_sid())
    app = C64PythonToAsmApp()
    async with app.run_test():
        app.load_project_file(sid_path)
        asm_path = tmp_path / "music_decompiled.asm"
        py_path = tmp_path / "music_decompiled.py"
        assert asm_path.is_file()
        assert py_path.is_file()
        assert app.file_mode == "asm"
        assert app.loaded_file == asm_path
        assert app.last_sid_path == sid_path
        assert "sid_init:" in app.query_one("#asm-viewer", TextArea).text
        assert "SID_INIT = 0x1000" in app.query_one("#python-editor", TextArea).text
