import pytest
from c64u_bridge.transpiler import PythonTo6502Transpiler, TranspileOptions, PRESETS


def test_transpile_simple_assignment():
    code = """
x = 42
y = x + 10
border_color(y)
"""
    transpiler = PythonTo6502Transpiler()
    result = transpiler.transpile(code)
    assert result.success is True
    assert "sta var_x" in result.assembly
    assert "sta var_y" in result.assembly
    assert "sta $D020" in result.assembly
    assert "BasicUpstart2(start)" in result.assembly


def test_transpile_while_loop():
    code = """
while True:
    wait_raster(50)
    border_color(COLOR_RED)
"""
    transpiler = PythonTo6502Transpiler()
    result = transpiler.transpile(code)
    assert result.success is True
    assert "lda $D012" in result.assembly
    assert "jmp while_start" in result.assembly


def test_transpile_for_loop():
    code = """
for i in range(10):
    poke(0x0400 + i, 81)
"""
    transpiler = PythonTo6502Transpiler()
    result = transpiler.transpile(code)
    assert result.success is True
    assert "inc var_i" in result.assembly
    assert "cmp #$0A" in result.assembly


def test_transpile_if_else():
    code = """
x = 5
if x == 5:
    border_color(COLOR_WHITE)
else:
    border_color(COLOR_BLACK)
"""
    transpiler = PythonTo6502Transpiler()
    result = transpiler.transpile(code)
    assert result.success is True
    assert "bne else_" in result.assembly
    assert "jmp endif_" in result.assembly


def test_transpile_acme_assembler():
    code = "border_color(1)"
    opts = TranspileOptions(assembler="acme")
    transpiler = PythonTo6502Transpiler(opts)
    result = transpiler.transpile(code)
    assert result.success is True
    assert '!to "program.prg", cbm' in result.assembly


def test_transpile_presets():
    transpiler = PythonTo6502Transpiler()
    for name, preset in PRESETS.items():
        res = transpiler.transpile(preset["code"])
        assert res.success is True, f"Preset '{name}' failed: {res.errors}"
        assert len(res.assembly) > 0
