"""
Commodore 64 TAP (C64-TAPE-RAW) Tape Image Generator & Converter

Converts C64 binaries (.prg) and 6502 assembly files into authentic, standard-compliant
Commodore 64 .tap cassette tape images compatible with:
- Ultimate 64 / C64U Tape Player and Virtual Cassette
- Real Commodore 64 / 128 hardware via Datasette / Tapecart / TapeMate
- VICE, CCS64, HOFS, and other C64 emulators
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .compiler import CrossCompiler

# Standard C64 pulse timing representations in units of 8 PAL clock cycles
# Short (~352 µs, 48 * 8 cycles)
PULSE_SHORT = 0x30
# Medium (~512 µs, 66 * 8 cycles)
PULSE_MEDIUM = 0x42
# Long (~672 µs, 86 * 8 cycles)
PULSE_LONG = 0x56

# Markers (2-pulse combinations)
# Byte Marker: Long then Medium
MARKER_BYTE = bytes([PULSE_LONG, PULSE_MEDIUM])
# End-of-Data Marker (EOD): Long then Short
MARKER_EOD = bytes([PULSE_LONG, PULSE_SHORT])

# Bit encodings (2-pulse combinations)
# Bit 0: Short then Medium
BIT_0 = bytes([PULSE_SHORT, PULSE_MEDIUM])
# Bit 1: Medium then Short
BIT_1 = bytes([PULSE_MEDIUM, PULSE_SHORT])

# Standard sync countdown sequences
SYNC_COUNTDOWN_PRIMARY = bytes([0x89, 0x88, 0x87, 0x86, 0x85, 0x84, 0x83, 0x82, 0x81])
SYNC_COUNTDOWN_BACKUP = bytes([0x09, 0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01])

# Header sizes and file types
HEADER_PAYLOAD_SIZE = 192
TYPE_BASIC_RELOCATABLE = 0x01
TYPE_MACHINE_CODE = 0x03


def encode_byte(val: int) -> bytes:
    """
    Encode a single byte into Datassette pulses.
    Sequence: Byte Marker (L/M) + 8 data bits (LSB first) + odd parity bit.
    """
    buf = bytearray(MARKER_BYTE)
    ones_count = 0

    for bit_idx in range(8):
        if (val >> bit_idx) & 1:
            buf.extend(BIT_1)
            ones_count += 1
        else:
            buf.extend(BIT_0)

    # Odd parity: parity bit ensures the total number of 1s (including parity) is odd
    parity_bit = 1 if (ones_count % 2 == 0) else 0
    buf.extend(BIT_1 if parity_bit == 1 else BIT_0)

    return bytes(buf)


def encode_block(payload: bytes, is_backup_copy: bool = False) -> bytes:
    """
    Encode a data block with sync countdown, payload bytes, XOR checksum, and EOD marker.
    
    Args:
        payload: The raw bytes of the block payload (e.g. 192 bytes for header, or PRG data).
        is_backup_copy: False for primary copy ($89..$81), True for backup copy ($09..$01).
    """
    buf = bytearray()

    # 1. Sync Countdown sequence
    countdown = SYNC_COUNTDOWN_BACKUP if is_backup_copy else SYNC_COUNTDOWN_PRIMARY
    for b in countdown:
        buf.extend(encode_byte(b))

    # 2. Payload bytes & Checksum computation
    checksum = 0
    for b in payload:
        checksum ^= b
        buf.extend(encode_byte(b))

    # 3. Checksum byte
    buf.extend(encode_byte(checksum))

    # 4. End-of-Data Marker
    buf.extend(MARKER_EOD)

    return bytes(buf)


def create_header_payload(
    start_address: int,
    end_address: int,
    filename: str = "PROGRAM",
    file_type: int = TYPE_MACHINE_CODE,
) -> bytes:
    """
    Construct the 192-byte standard Commodore tape header payload.
    
    Layout:
      Byte 0: File type (0x01 relocatable, 0x03 non-relocatable)
      Bytes 1-2: 16-bit start address (little-endian)
      Bytes 3-4: 16-bit end address (little-endian)
      Bytes 5-20: 16-character filename (ASCII/PETSCII uppercase padded with spaces 0x20)
      Bytes 21-191: Reserved / padding (171 bytes of spaces 0x20)
    """
    buf = bytearray(HEADER_PAYLOAD_SIZE)
    buf[0] = file_type & 0xFF
    buf[1] = start_address & 0xFF
    buf[2] = (start_address >> 8) & 0xFF
    buf[3] = end_address & 0xFF
    buf[4] = (end_address >> 8) & 0xFF

    # Sanitize filename (clean up path extensions, uppercase, max 16 chars)
    clean_name = Path(filename).stem if ("." in filename or "/" in filename or "\\" in filename) else filename
    ascii_name = clean_name.upper().encode("ascii", errors="replace")[:16]
    ascii_name = ascii_name.ljust(16, b" ")

    buf[5:21] = ascii_name
    buf[21:192] = b" " * 171

    return bytes(buf)


def prg_to_tap(
    prg_data: bytes,
    tape_name: str = "PROGRAM",
    file_type: Optional[int] = None,
    header_leader_pulses: int = 10000,
    data_leader_pulses: int = 4000,
    gap_pulses: int = 1000,
) -> bytes:
    """
    Convert raw Commodore PRG bytes into a full C64-TAPE-RAW v1 .tap file image.
    
    Args:
        prg_data: Raw PRG content (minimum 2 bytes load address + payload).
        tape_name: Tape filename label shown on screen when loading.
        file_type: Optional header type (0x01 for BASIC, 0x03 for ML). Auto-detects if None.
        header_leader_pulses: Number of initial short pulses before header (default: 10,000).
        data_leader_pulses: Number of short pulses before data block (default: 4,000).
        gap_pulses: Number of short pulses in inter-block gaps (default: 1,000).
    
    Returns:
        Complete bytes of the .tap file.
    """
    if len(prg_data) < 2:
        raise ValueError("Invalid PRG: Must be at least 2 bytes long for the 16-bit load address.")

    start_address = prg_data[0] | (prg_data[1] << 8)
    data_payload = prg_data[2:]
    end_address = start_address + len(data_payload)

    if file_type is None:
        file_type = TYPE_BASIC_RELOCATABLE if start_address == 0x0801 else TYPE_MACHINE_CODE

    # 1. Build Header Block
    header_payload = create_header_payload(
        start_address=start_address,
        end_address=end_address,
        filename=tape_name,
        file_type=file_type,
    )

    pulses = bytearray()

    # --- Header Block ---
    # Initial Leader
    pulses.extend(bytes([PULSE_SHORT]) * header_leader_pulses)
    # Primary copy ($89..$81)
    pulses.extend(encode_block(header_payload, is_backup_copy=False))
    # Inter-record gap
    pulses.extend(bytes([PULSE_SHORT]) * gap_pulses)
    # Backup copy ($09..$01)
    pulses.extend(encode_block(header_payload, is_backup_copy=True))

    # --- Data Block ---
    # Leader before data
    pulses.extend(bytes([PULSE_SHORT]) * data_leader_pulses)
    # Primary copy ($89..$81)
    pulses.extend(encode_block(data_payload, is_backup_copy=False))
    # Inter-record gap
    pulses.extend(bytes([PULSE_SHORT]) * gap_pulses)
    # Backup copy ($09..$01)
    pulses.extend(encode_block(data_payload, is_backup_copy=True))

    # Lead-out trailer gap
    pulses.extend(bytes([PULSE_SHORT]) * gap_pulses)

    # --- TAP File 20-byte Header ---
    # Bytes 0-11: Signature "C64-TAPE-RAW"
    # Byte 12: Version (0x01)
    # Byte 13: Platform (0x00 = C64)
    # Byte 14: Video Standard (0x00 = PAL)
    # Byte 15: Reserved (0x00)
    # Bytes 16-19: 32-bit unsigned little-endian pulse data length
    tap_header = bytearray(b"C64-TAPE-RAW")
    tap_header.append(1)  # Version 1
    tap_header.append(0)  # Platform C64
    tap_header.append(0)  # Video PAL
    tap_header.append(0)  # Reserved
    tap_header.extend(struct.pack("<I", len(pulses)))

    return bytes(tap_header + pulses)


def save_prg_to_tap(
    prg_path: Union[str, Path],
    tap_path: Optional[Union[str, Path]] = None,
    tape_name: Optional[str] = None,
    file_type: Optional[int] = None,
) -> Path:
    """
    Convert an existing .prg file to a .tap cassette image.
    
    Args:
        prg_path: Path to existing .prg file.
        tap_path: Optional target .tap path (defaults to <prg_stem>.tap in same folder).
        tape_name: Optional tape name (defaults to file stem uppercase).
        file_type: Optional tape header type.
        
    Returns:
        Path to the saved .tap file.
    """
    src_prg = Path(prg_path).resolve()
    if not src_prg.exists():
        raise FileNotFoundError(f"PRG file not found: {src_prg}")

    prg_data = src_prg.read_bytes()
    name = tape_name or src_prg.stem

    out_tap = Path(tap_path).resolve() if tap_path else src_prg.with_suffix(".tap")
    tap_bytes = prg_to_tap(prg_data, tape_name=name, file_type=file_type)

    out_tap.write_bytes(tap_bytes)
    return out_tap


def asm_to_tap(
    asm_path: Union[str, Path],
    tap_path: Optional[Union[str, Path]] = None,
    compiler: Optional[CrossCompiler] = None,
    tape_name: Optional[str] = None,
    assembler: str = "auto",
) -> Path:
    """
    Assemble a 6502 assembly source file (.asm or .s) into PRG, then export to .tap.
    
    Args:
        asm_path: Path to .asm source file.
        tap_path: Optional target .tap path.
        compiler: Optional CrossCompiler instance.
        tape_name: Optional tape name.
        assembler: Assembler backend ('auto', 'kickass', 'acme', etc.).
        
    Returns:
        Path to the saved .tap file.
    """
    src_asm = Path(asm_path).resolve()
    if not src_asm.exists():
        raise FileNotFoundError(f"Assembly file not found: {src_asm}")

    comp = compiler or CrossCompiler()
    temp_prg = src_asm.with_suffix(".prg")

    comp_res = comp.compile(src_asm, output_prg=temp_prg, assembler=assembler)
    if not comp_res.success or not temp_prg.exists():
        err = comp_res.error_message or comp_res.stderr or comp_res.stdout
        raise RuntimeError(f"Assembly failed for {src_asm.name}: {err}")

    name = tape_name or src_asm.stem
    out_tap = Path(tap_path).resolve() if tap_path else src_asm.with_suffix(".tap")

    return save_prg_to_tap(temp_prg, tap_path=out_tap, tape_name=name)


def read_tap_info(tap_data: bytes) -> Dict[str, Any]:
    """
    Inspect and validate a C64 .tap file image.
    
    Returns:
        Dictionary containing signature, version, pulse count, and basic metadata.
    """
    if len(tap_data) < 20:
        raise ValueError("TAP file too small: must be at least 20 bytes.")

    signature = tap_data[:12]
    if signature != b"C64-TAPE-RAW":
        raise ValueError(f"Invalid TAP signature: {signature!r} (expected b'C64-TAPE-RAW')")

    version = tap_data[12]
    platform = tap_data[13]
    video = tap_data[14]
    data_length = struct.unpack("<I", tap_data[16:20])[0]

    actual_pulse_data_len = len(tap_data) - 20

    return {
        "valid": True,
        "signature": signature.decode("ascii", errors="replace"),
        "version": version,
        "platform": "C64" if platform == 0 else f"Platform {platform}",
        "video": "PAL" if video == 0 else ("NTSC" if video == 1 else f"Standard {video}"),
        "declared_length": data_length,
        "actual_length": actual_pulse_data_len,
        "has_correct_size": data_length == actual_pulse_data_len,
    }
