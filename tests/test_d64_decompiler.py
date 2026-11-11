"""
Unit tests for D64 disk image parser, TAP extractor, and MOS 6502 PRG decompiler.
"""

from pathlib import Path
import pytest

from c64u_bridge.d64 import (
    create_d64,
    read_d64,
    petscii_to_ascii,
    ascii_to_petscii,
    track_sector_to_offset,
    D64Disk,
)
from c64u_bridge.tap import (
    prg_to_tap,
    extract_prgs_from_tap,
    tap_to_prg,
)
from c64u_bridge.prg_decompiler import (
    detokenize_basic,
    decompile_prg,
    decompile_d64_file,
    decompile_tap_file,
)


def test_d64_track_sector_offset():
    """Verify standard 1541 sector offset calculations."""
    # Track 1, Sector 0: first sector on disk
    assert track_sector_to_offset(1, 0) == 0
    # Track 18, Sector 0: BAM sector (offset 0x16500 = 91392)
    assert track_sector_to_offset(18, 0) == 91392
    # Track 18, Sector 1: first directory sector
    assert track_sector_to_offset(18, 1) == 91392 + 256


def test_petscii_conversions():
    """Verify PETSCII to ASCII and ASCII to PETSCII transformations."""
    ascii_str = "PACMAN 1982"
    petscii_bytes = ascii_to_petscii(ascii_str, length=16, pad_byte=0xA0)
    assert len(petscii_bytes) == 16
    assert petscii_bytes.startswith(b"PACMAN 1982")
    assert petscii_bytes.endswith(b"\xa0" * 5)

    converted_back = petscii_to_ascii(petscii_bytes)
    assert converted_back == "PACMAN 1982"


def test_d64_create_and_extract_files():
    """Verify creating a synthetic D64 disk image, parsing directory, and extracting PRGs."""
    prg1 = bytes([0x01, 0x08, 0x00, 0x0C, 0x08, 0x0A, 0x00, 0x9E, 0x32, 0x30, 0x36, 0x34, 0x00, 0x00, 0x00, 0x60])
    prg2 = bytes([0x00, 0xC0, 0xA9, 0x01, 0x8D, 0x20, 0xD0, 0x60])

    d64_bytes = create_d64(
        disk_name="RETRO GAMES",
        disk_id="84",
        files=[
            ("GAME ONE", prg1),
            ("BORDER FLASHER", prg2),
        ],
    )

    assert len(d64_bytes) == 174848

    disk = read_d64(d64_bytes)
    assert disk.disk_name == "RETRO GAMES"
    assert disk.disk_id == "84"
    assert len(disk.entries) == 2

    e1 = disk.entries[0]
    assert e1.filename == "GAME ONE"
    assert e1.is_prg is True
    extracted1 = disk.extract_file(e1)
    assert extracted1 == prg1

    e2 = disk.entries[1]
    assert e2.filename == "BORDER FLASHER"
    assert e2.is_prg is True
    extracted2 = disk.extract_file(e2)
    assert extracted2 == prg2


def test_tap_prg_roundtrip():
    """Verify converting PRG to TAP and extracting it back preserves byte-exact fidelity."""
    # Load address $0801 + simple payload
    original_prg = bytes([0x01, 0x08, 0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x60])
    tap_bytes = prg_to_tap(
        original_prg,
        tape_name="TESTTAPE",
        header_leader_pulses=100,
        data_leader_pulses=100,
        gap_pulses=50,
    )

    extracted = extract_prgs_from_tap(tap_bytes)
    assert len(extracted) == 1
    name, extracted_prg = extracted[0]
    assert name == "TESTTAPE"
    assert extracted_prg == original_prg
    assert tap_to_prg(tap_bytes) == original_prg


def test_detokenize_basic():
    """Verify C64 BASIC line parser extracts line numbers, tokens, and SYS address."""
    # 10 SYS 2064
    # Pointer: $080C (dummy) -> 0x0C, 0x08
    # Line 10: 0x0A, 0x00
    # Token SYS: 0x9E
    # ASCII ' 2064': 0x20, 0x32, 0x30, 0x36, 0x34
    # End of line: 0x00
    # End of program: 0x00, 0x00
    payload = bytes([
        0x0C, 0x08,
        0x0A, 0x00,
        0x9E, ord('2'), ord('0'), ord('6'), ord('4'), 0x00,
        0x00, 0x00,
    ])

    lines, sys_addr, consumed = detokenize_basic(payload, base_address=0x0801)
    assert len(lines) == 1
    assert lines[0][0] == 10
    assert "SYS 2064" in lines[0][1]
    assert sys_addr == 2064
    assert consumed == len(payload)


def test_decompile_prg_with_basic_and_vic():
    """Verify decompilation of PRG with BASIC stub and VIC-II register writes."""
    # Start at $0801
    # BASIC: 10 SYS 2064 ($0810)
    # Machine Code at $0810:
    #   SEI            ($78)
    #   LDA #$01       ($A9, $01)
    #   STA $D020      ($8D, $20, $D0)
    #   STA $D021      ($8D, $21, $D0)
    #   RTS            ($60)
    basic_stub = bytes([
        0x0C, 0x08,
        0x0A, 0x00,
        0x9E, ord('2'), ord('0'), ord('6'), ord('4'), 0x00,
        0x00, 0x00,
    ])
    padding = bytes([0xEA] * (0x0810 - 0x0801 - len(basic_stub)))
    ml_code = bytes([
        0x78,             # SEI
        0xA9, 0x01,       # LDA #$01
        0x8D, 0x20, 0xD0, # STA $D020
        0x8D, 0x21, 0xD0, # STA $D021
        0x60,             # RTS
    ])
    full_prg = bytes([0x01, 0x08]) + basic_stub + padding + ml_code

    result = decompile_prg(full_prg, name="BORDER_TEST")
    assert result.load_address == 0x0801
    assert result.has_basic_sys is True
    assert result.sys_address == 2064
    assert result.instruction_count >= 5

    # Verify caution prompt embedded in assembly and python
    assert "ETHICAL USE & COPYRIGHT CAUTION" in result.assembly
    assert "Learn from it, but don't be a thief!" in result.assembly
    assert "ETHICAL USE & COPYRIGHT CAUTION" in result.python

    # Verify KickAssembler header
    assert ":BasicUpstart2(" in result.assembly
    assert "VIC_BORDER_COLOR" in result.assembly
    assert "VIC_BG_COLOR0" in result.assembly


def test_decompile_d64_file(tmp_path):
    """Verify decompile_d64_file loads and decompiles files from a D64 disk image."""
    code = bytes([0x00, 0xC0, 0xA9, 0x05, 0x8D, 0x20, 0xD0, 0x60])
    d64_bytes = create_d64(
        disk_name="TEST DISK",
        disk_id="99",
        files=[("AUTORUN", code)],
    )
    d64_path = tmp_path / "test.d64"
    d64_path.write_bytes(d64_bytes)

    res = decompile_d64_file(d64_path)
    assert res.filename == "AUTORUN"
    assert res.load_address == 0xC000
    assert "VIC_BORDER_COLOR" in res.assembly
    assert "sei" not in res.assembly or "rts" in res.assembly


def test_decompile_tap_file(tmp_path):
    """Verify decompile_tap_file loads and decompiles files from a TAP cassette image."""
    code = bytes([0x00, 0xC0, 0xA9, 0x02, 0x8D, 0x21, 0xD0, 0x60])
    tap_bytes = prg_to_tap(
        code,
        tape_name="TAPECODE",
        header_leader_pulses=100,
        data_leader_pulses=100,
        gap_pulses=50,
    )
    tap_path = tmp_path / "test.tap"
    tap_path.write_bytes(tap_bytes)

    res = decompile_tap_file(tap_path)
    assert res.filename == "TAPECODE"
    assert res.load_address == 0xC000
    assert "VIC_BG_COLOR0" in res.assembly


def test_save_prg_to_d64(tmp_path):
    """Verify packaging PRG into D64 disk image."""
    from c64u_bridge.d64 import save_prg_to_d64, read_d64_file

    prg_bytes = bytes([0x01, 0x08, 0xA9, 0x07, 0x8D, 0x20, 0xD0, 0x60])
    prg_file = tmp_path / "game.prg"
    prg_file.write_bytes(prg_bytes)

    d64_path = save_prg_to_d64(prg_file, disk_name="GAME DISK")
    assert d64_path.exists()
    assert d64_path.suffix == ".d64"
    assert d64_path.stat().st_size == 174848

    disk = read_d64_file(d64_path)
    assert disk.disk_name == "GAME DISK"
    assert len(disk.entries) == 1
    assert disk.entries[0].filename == "GAME"
    extracted = disk.extract_file(disk.entries[0])
    assert extracted == prg_bytes


def test_compilation_result_to_d64(tmp_path):
    """Verify CompilationResult.to_d64 helper method."""
    from c64u_bridge.compiler import CompilationResult
    from c64u_bridge.d64 import read_d64_file

    prg_file = tmp_path / "app.prg"
    prg_bytes = bytes([0x01, 0x08, 0x00, 0x60])
    prg_file.write_bytes(prg_bytes)

    res = CompilationResult(
        success=True,
        output_prg=prg_file,
        stdout="OK",
        stderr="",
    )
    d64_out = res.to_d64(disk_name="APP DISK")
    assert d64_out is not None
    assert d64_out.exists()
    assert res.output_d64 == d64_out

    disk = read_d64_file(d64_out)
    assert disk.disk_name == "APP DISK"
    assert disk.extract_file(disk.entries[0]) == prg_bytes


def test_decompile_explanatory_comments_and_hardware_decoding():
    """Verify rich educational comments for C64 colors, banking ($01), VIC-II, SID, and subroutine callers."""
    # Load at $C000:
    # $C000: SEI                  ($78)
    # $C001: LDA #$35             ($A9, $35)
    # $C003: STA $01              ($85, $01) -> Bank out BASIC & KERNAL ROMs
    # $C005: LDA #$01             ($A9, $01)
    # $C007: STA $D020            ($8D, $20, $D0) -> White border
    # $C00A: LDA #$0F             ($A9, $0F)
    # $C00C: STA $D418            ($8D, $18, $D4) -> Master Volume = 15/15
    # $C00F: JSR $C013            ($20, $13, $C0) -> Call subroutine
    # $C012: RTS                  ($60)
    # $C013: LDA #$93             ($A9, $93)
    # $C015: JSR $FFD2            ($20, $D2, $FF) -> Clear Screen (CLR)
    # $C018: RTS                  ($60)
    prg = bytes([
        0x00, 0xC0,
        0x78,
        0xA9, 0x35,
        0x85, 0x01,
        0xA9, 0x01,
        0x8D, 0x20, 0xD0,
        0xA9, 0x0F,
        0x8D, 0x18, 0xD4,
        0x20, 0x13, 0xC0,
        0x60,
        0xA9, 0x93,
        0x20, 0xD2, 0xFF,
        0x60,
    ])
    res = decompile_prg(prg, name="COMMENT_TEST")
    asm = res.assembly

    assert "PROGRAM ARCHITECTURE & HARDWARE ANALYSIS" in asm
    assert "Disable maskable IRQ interrupts" in asm
    assert "Bank out BASIC & KERNAL ROMs" in asm
    assert "Set color to White" in asm
    assert "Master Volume = 15/15" in asm
    assert "Clear Screen (CLR)" in asm
    assert "sub_c013:" in asm
    assert "Called from: $C00F" in asm


def test_decompile_d64_loader_main_both_scopes(tmp_path):
    """Verify decompiling a multi-PRG D64 disk with scope='loader', 'main', and 'both'."""
    from c64u_bridge.prg_decompiler import inspect_media_stages

    # Small boot loader at $0801
    loader_prg = bytes([0x01, 0x08, 0x78, 0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x60])
    # Larger main game at $0800 with 1 padding byte + BASIC `10 SYS (2064)` + code at $0810
    basic_sys_parens = bytes([
        0xEA,              # $0800 padding byte
        0x0E, 0x08,        # next line ptr $080E
        0x0A, 0x00,        # line 10
        0x9E, ord("("), ord("2"), ord("0"), ord("6"), ord("4"), ord(")"), 0x00,
        0x00, 0x00,        # end of BASIC ($080E..$080F)
    ])
    main_code = bytes([
        0x78,              # $0810: SEI
        0xA9, 0x06,        # LDA #$06
        0x8D, 0x21, 0xD0,  # STA $D021
        0xA9, 0x1B,        # LDA #$1B
        0x8D, 0x11, 0xD0,  # STA $D011
        0x60,              # RTS
    ]) + bytes([0xEA] * 64)
    main_prg = bytes([0x00, 0x08]) + basic_sys_parens + main_code

    d64_path = tmp_path / "multigame.d64"
    d64_path.write_bytes(
        create_d64(
            disk_name="MULTI GAME",
            disk_id="2A",
            files=[("BOOTLOADER", loader_prg), ("MAINGAME", main_prg)],
        )
    )

    stages = inspect_media_stages(d64_path)
    assert len(stages) == 2
    assert stages[0].role == "loader"
    assert stages[1].role == "main"

    res_loader = decompile_d64_file(d64_path, scope="loader")
    assert res_loader.stages_decompiled == ["BOOTLOADER"]
    assert res_loader.instruction_count >= 3

    res_main = decompile_d64_file(d64_path, scope="main")
    assert res_main.stages_decompiled == ["MAINGAME"]
    assert res_main.has_basic_sys is True
    assert res_main.sys_address == 2064
    assert res_main.instruction_count >= 5

    res_both = decompile_d64_file(d64_path, scope="both")
    assert res_both.stages_decompiled == ["BOOTLOADER", "MAINGAME"]
    assert "MULTI-STAGE DECOMPILATION" in res_both.assembly
    assert res_both.instruction_count == res_loader.instruction_count + res_main.instruction_count


def test_decompile_real_tap_games_loader_main_both():
    """Verify real-world .tap games (Bruce Lee, Burger Time, Donkey Kong) decompile into 6502 assembly."""
    example_dir = Path("example_games")
    if not example_dir.exists():
        pytest.skip("example_games directory not present")

    expected_mins = {
        "Bruce Lee.tap": (100, 4000),
        "Burger Time.tap": (10, 3000),
        "Donkey Kong.tap": (40, 4000),
    }
    for tap_name, (min_loader_ins, min_main_ins) in expected_mins.items():
        tap_path = example_dir / tap_name
        if not tap_path.exists():
            continue
        res_loader = decompile_tap_file(tap_path, scope="loader")
        res_main = decompile_tap_file(tap_path, scope="main")
        res_both = decompile_tap_file(tap_path, scope="both")

        assert res_loader.instruction_count >= min_loader_ins, f"{tap_name} loader had {res_loader.instruction_count} insns"
        assert res_main.instruction_count >= min_main_ins, f"{tap_name} main had {res_main.instruction_count} insns"
        assert res_both.instruction_count == res_loader.instruction_count + res_main.instruction_count
        assert "PROGRAM ARCHITECTURE & HARDWARE ANALYSIS" in res_main.assembly


def test_kickassembler_version_check_and_updater(tmp_path):
    """Verify CrossCompiler checks KickAssembler version and updates KickAss.jar from zip archive."""
    import io
    import zipfile
    from c64u_bridge.compiler import CrossCompiler

    compiler = CrossCompiler()
    inst_ver = compiler.get_installed_kickass_version()
    assert inst_ver is not None
    assert inst_ver.startswith("5.")

    status = compiler.check_kickass_version(timeout=1.5)
    assert status.installed_version == inst_ver
    assert status.has_decompiler is False
    assert "KickAssembler" in status.status_message

    # Test update_kickassembler using a local file:// zip archive
    fake_zip_path = tmp_path / "KickAssembler.zip"
    real_jar_bytes = Path(compiler.kickass_jar).read_bytes()
    with zipfile.ZipFile(fake_zip_path, "w") as zf:
        zf.writestr("KickAss.jar", real_jar_bytes)
        zf.writestr("KickAss.cfg", b"-showmem\n")

    target_jar = tmp_path / "tools" / "KickAss.jar"
    temp_compiler = CrossCompiler(kickass_jar=str(target_jar))
    ok, msg = temp_compiler.update_kickassembler(download_url=fake_zip_path.as_uri())
    assert ok is True
    assert target_jar.exists()
    assert "5." in msg


def test_automated_deployment_validation_report_and_diff(tmp_path):
    """
    Verify DeploymentValidator records compilation size, C64U firmware details,
    load/exec status, Screen RAM snapshot, hardware register values, and diffs
    between consecutive deployments.
    """
    from c64u_bridge.validation_report import DeploymentValidator

    class _MockC64UClient:
        host = "192.168.1.64"
        port = 80

        def __init__(self, border_col: int, screen_text: bytes):
            self.border_col = border_col
            self.screen_text = screen_text

        def get_info(self):
            return {"version": "3.11a", "product": "Ultimate-64", "fpga": "1.22"}

        def read_memory(self, address: int, length: int) -> bytes:
            if address == 0x0400:
                buf = bytearray([0x20] * 1000)
                buf[: len(self.screen_text)] = self.screen_text
                return bytes(buf)
            if address == 0xD800:
                return bytes([0x01] * 1000)
            if address == 0x0000:
                return bytes([0x2F, 0x37])  # DDR=$2F, PORT=$37
            if address == 0x0314:
                return bytes([0x31, 0xEA, 0x66, 0xFE, 0x47, 0xFE])  # IRQ=$EA31
            if address == 0xD011:
                vic = bytearray(0x1E)
                vic[0x00] = 0x1B  # $D011 Screen ON, Text
                vic[0x04] = 0x03  # $D015 Sprites 0, 1 ON
                vic[0x07] = 0x14  # $D018
                vic[0x0F] = self.border_col  # $D020
                vic[0x10] = 0x06  # $D021 Blue
                return bytes(vic)
            if address == 0xD400:
                sid = bytearray(25)
                sid[24] = 0x0F  # Volume 15
                return bytes(sid)
            if address == 0xDD00:
                return bytes([0x03])  # Bank 0 ($0000-$3FFF)
            return bytes(length)

    state_file = tmp_path / "last_deploy.json"
    validator = DeploymentValidator(state_file=state_file)

    # Deployment #1: 10-byte PRG, Border = 14 (Light Blue), Screen Row 0 = "HELLO C64"
    prg1 = tmp_path / "demo_v1.prg"
    prg1.write_bytes(bytes([0x01, 0x08, 0xA9, 0x0E, 0x8D, 0x20, 0xD0, 0x60]))
    # Screen codes for "HELLO": H=8, E=5, L=12, L=12, O=15
    client1 = _MockC64UClient(border_col=0x0E, screen_text=bytes([8, 5, 12, 12, 15]))

    rep1 = validator.validate_deployment(
        client=client1,
        source_name="demo_v1.asm",
        prg_path=prg1,
        execution_mode="DMA_RUN",
        load_and_exec_success=True,
        runner_response="OK",
        settle_delay_sec=0.0,
    )
    txt1 = rep1.format_report()
    assert rep1.compilation_success is True
    assert rep1.prg_size_bytes == 8
    assert rep1.load_address == 0x0801
    assert rep1.c64u_connected is True
    assert rep1.firmware_version == "3.11a"
    assert rep1.load_and_exec_success is True
    assert rep1.screen_captured is True
    assert rep1.non_blank_chars == 5
    assert "Light Blue" in rep1.registers["$D020/$D021 Colors"]
    assert rep1.diff.has_previous is False
    assert "Baseline deployment recorded" in txt1

    # Deployment #2: 12-byte PRG (+4 bytes), Border = 0 (Black), Screen Row 0 = "READY"
    prg2 = tmp_path / "demo_v2.prg"
    prg2.write_bytes(bytes([0x01, 0x08, 0x78, 0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x8D, 0x21, 0xD0, 0x60]))
    # Screen codes for "READY": R=18, E=5, A=1, D=4, Y=25
    client2 = _MockC64UClient(border_col=0x00, screen_text=bytes([18, 5, 1, 4, 25]))

    rep2 = validator.validate_deployment(
        client=client2,
        source_name="demo_v2.asm",
        prg_path=prg2,
        execution_mode="DMA_RUN",
        load_and_exec_success=True,
        runner_response="OK",
        settle_delay_sec=0.0,
    )
    txt2 = rep2.format_report()
    assert rep2.diff.has_previous is True
    assert rep2.diff.prg_size_delta == 4
    assert rep2.diff.prg_hash_changed is True
    assert any("Light Blue" in rc and "Black" in rc for rc in rep2.diff.register_changes)
    assert rep2.diff.screen_Wait_cells_changed == 4  # H, L, L, O changed (E at index 1 stayed 5)
    assert "Row 00: \"HELLO\" -> \"READY\"" in txt2


def test_oscar64_compiler_detection_and_invocation(tmp_path):
    """Verify Oscar64 C/C++ compiler detection and command-line orchestration."""
    from unittest.mock import patch
    from c64u_bridge.compiler import CrossCompiler

    compiler = CrossCompiler(oscar64_bin="oscar64")

    # 1. C++ files and C files with <c64/vic.h> or #pragma compile auto-select oscar64
    c_oscar = tmp_path / "game_oscar.c"
    c_oscar.write_text('#include <c64/vic.h>\nint main(void) { vic.color_border = VCOL_BLACK; return 0; }\n', encoding="utf-8")
    assert compiler.detect_assembler(c_oscar) == "oscar64"

    cpp_oscar = tmp_path / "engine.cpp"
    cpp_oscar.write_text('int main() { return 0; }\n', encoding="utf-8")
    assert compiler.detect_assembler(cpp_oscar) == "oscar64"

    # 2. C files with <conio.h> / <cbm.h> auto-select cc65
    c_cc65 = tmp_path / "legacy_cc65.c"
    c_cc65.write_text('#include <conio.h>\nint main(void) { cputs("HI"); return 0; }\n', encoding="utf-8")
    assert compiler.detect_assembler(c_cc65) == "cc65"

    # 3. Mock subprocess.run for Oscar64 compilation to PRG
    out_prg = tmp_path / "game_oscar.prg"

    def _fake_oscar64_run(cmd, **kwargs):
        assert "oscar64" in cmd[0]
        assert "-tf=prg" in cmd
        assert any(arg.startswith("-o=") for arg in cmd)
        out_prg.write_bytes(bytes([0x01, 0x08, 0xA9, 0x00, 0x8D, 0x20, 0xD0, 0x60]))

        class _Res:
            returncode = 0
            stdout = "Oscar64 C/C++ Compiler v1.30 - Compiled successfully"
            stderr = ""

        return _Res()

    with patch("c64u_bridge.compiler.subprocess.run", side_effect=_fake_oscar64_run):
        res = compiler.compile(c_oscar, output_prg=out_prg, assembler="auto")
        assert res.success is True
        assert res.output_prg == out_prg
        assert out_prg.exists()




