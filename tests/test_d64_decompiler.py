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


