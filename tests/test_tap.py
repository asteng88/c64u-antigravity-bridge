"""
Unit tests for C64 TAP (C64-TAPE-RAW) generation and handling.
"""

import struct
from pathlib import Path
import pytest

from c64u_bridge.tap import (
    PULSE_SHORT,
    PULSE_MEDIUM,
    PULSE_LONG,
    MARKER_BYTE,
    MARKER_EOD,
    BIT_0,
    BIT_1,
    encode_byte,
    encode_block,
    create_header_payload,
    prg_to_tap,
    save_prg_to_tap,
    read_tap_info,
)
from c64u_bridge.compiler import CompilationResult, CrossCompiler


def test_pulse_constants():
    """Verify standard C64 pulse timing constants."""
    assert PULSE_SHORT == 0x30
    assert PULSE_MEDIUM == 0x42
    assert PULSE_LONG == 0x56
    assert MARKER_BYTE == bytes([0x56, 0x42])
    assert MARKER_EOD == bytes([0x56, 0x30])
    assert BIT_0 == bytes([0x30, 0x42])
    assert BIT_1 == bytes([0x42, 0x30])


def test_encode_byte_odd_parity():
    """Verify byte encoding with byte marker, 8 data bits (LSB first), and odd parity."""
    # 0x00 has zero 1-bits (even) -> parity bit must be 1 (BIT_1: [0x42, 0x30])
    encoded_0 = encode_byte(0x00)
    # Length: 2 (marker) + 8*2 (8 bits) + 2 (parity) = 20 pulses
    assert len(encoded_0) == 20
    assert encoded_0[:2] == MARKER_BYTE
    # All 8 bits are 0 (BIT_0: [0x30, 0x42])
    for i in range(8):
        assert encoded_0[2 + i * 2 : 4 + i * 2] == BIT_0
    # Parity bit should be 1
    assert encoded_0[18:20] == BIT_1

    # 0x01 has one 1-bit (odd) -> parity bit must be 0 (BIT_0: [0x30, 0x42])
    encoded_1 = encode_byte(0x01)
    assert len(encoded_1) == 20
    assert encoded_1[:2] == MARKER_BYTE
    assert encoded_1[2:4] == BIT_1  # bit 0 is 1
    assert encoded_1[4:6] == BIT_0  # bit 1 is 0
    assert encoded_1[18:20] == BIT_0  # parity is 0


def test_create_header_payload():
    """Verify 192-byte standard Commodore tape header block payload structure."""
    payload = create_header_payload(
        start_address=0x0801,
        end_address=0x0850,
        filename="CHOPLIFTER",
        file_type=0x01,
    )
    assert len(payload) == 192
    assert payload[0] == 0x01  # relocatable BASIC file type
    assert payload[1] == 0x01  # start address low
    assert payload[2] == 0x08  # start address high
    assert payload[3] == 0x50  # end address low
    assert payload[4] == 0x08  # end address high
    assert payload[5:15] == b"CHOPLIFTER"
    assert payload[15:21] == b" " * 6  # padded with spaces to 16 bytes
    assert payload[21:192] == b" " * 171  # 171 bytes of spaces


def test_encode_block():
    """Verify block encoding produces countdown, payload, checksum, and EOD marker."""
    data = bytes([0xAA, 0x55])
    block_primary = encode_block(data, is_backup_copy=False)
    # 9 countdown bytes + 2 payload bytes + 1 checksum byte = 12 bytes @ 20 pulses = 240 pulses + 2 (EOD) = 242
    assert len(block_primary) == 12 * 20 + 2
    assert block_primary[-2:] == MARKER_EOD

    block_backup = encode_block(data, is_backup_copy=True)
    assert len(block_backup) == 12 * 20 + 2
    assert block_backup[-2:] == MARKER_EOD


def test_prg_to_tap_structure(tmp_path):
    """Verify converting PRG to TAP creates valid C64-TAPE-RAW v1 image."""
    # Dummy PRG: load address $0801 + 4 bytes of program
    prg_bytes = bytes([0x01, 0x08, 0x00, 0xA9, 0x00, 0x60])
    tap_bytes = prg_to_tap(
        prg_bytes,
        tape_name="TESTGAME",
        header_leader_pulses=500,
        data_leader_pulses=200,
        gap_pulses=50,
    )

    info = read_tap_info(tap_bytes)
    assert info["valid"] is True
    assert info["signature"] == "C64-TAPE-RAW"
    assert info["version"] == 1
    assert info["platform"] == "C64"
    assert info["video"] == "PAL"
    assert info["has_correct_size"] is True

    # Test file write and save_prg_to_tap
    prg_file = tmp_path / "test.prg"
    prg_file.write_bytes(prg_bytes)
    tap_file = save_prg_to_tap(prg_file)
    assert tap_file.exists()
    assert tap_file.suffix == ".tap"
    assert tap_file.stat().st_size > 20

    saved_info = read_tap_info(tap_file.read_bytes())
    assert saved_info["valid"] is True


def test_prg_to_tap_invalid():
    """Verify error on invalid PRG data (< 2 bytes)."""
    with pytest.raises(ValueError, match="at least 2 bytes"):
        prg_to_tap(b"\x01")


def test_compilation_result_to_tap(tmp_path):
    """Verify CompilationResult.to_tap helper method."""
    prg_file = tmp_path / "hello.prg"
    prg_file.write_bytes(bytes([0x01, 0x08, 0x00, 0x60]))

    res = CompilationResult(
        success=True,
        output_prg=prg_file,
        stdout="OK",
        stderr="",
    )
    tap_out = res.to_tap()
    assert tap_out is not None
    assert tap_out.exists()
    assert res.output_tap == tap_out
    assert read_tap_info(tap_out.read_bytes())["valid"] is True
