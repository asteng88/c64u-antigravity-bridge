"""
Commodore 64 TAP (C64-TAPE-RAW) Tape Image Generator & Converter

Converts C64 binaries (.prg) and 6502 assembly files into authentic, standard-compliant
Commodore 64 .tap cassette tape images compatible with:
- Ultimate 64 / C64U Tape Player and Virtual Cassette
- Real Commodore 64 / 128 hardware via Datasette / Tapecart / TapeMate
- VICE, CCS64, HOFS, and other C64 emulators
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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


@dataclass
class TapStage:
    """Represents a logical stage (Loader or Main Game) decoded from a C64 .tap image."""

    name: str
    role: str  # "loader" or "main"
    prg_data: bytes  # 2-byte little-endian load address + payload
    description: str = ""
    entry_points: List[int] = field(default_factory=list)

    @property
    def load_address(self) -> int:
        if len(self.prg_data) >= 2:
            return self.prg_data[0] | (self.prg_data[1] << 8)
        return 0

    @property
    def payload_size(self) -> int:
        return max(0, len(self.prg_data) - 2)


def _looks_like_basic_at_0801(payload: bytes) -> bool:
    """Return True if payload starts with a valid C64 BASIC V2 line link at $0801."""
    if len(payload) < 7:
        return False
    next_ptr = payload[0] | (payload[1] << 8)
    # Standard BASIC line link from $0801 points into $0805..$0860
    return 0x0805 <= next_ptr <= 0x0880


def _header_has_machine_code(header_blk: bytes) -> bool:
    """
    Check if a 192-byte C64 tape header ($033C..$03FB) contains custom 6502
    fast-loader machine code in bytes 21..191 ($0351..$03FB).
    """
    if len(header_blk) < 192:
        return False
    tail = header_blk[21:192]
    # Standard unused header tail is filled with spaces (0x20) or zeros (0x00)
    non_pad = [b for b in tail if b not in (0x20, 0x00, 0xA0)]
    if len(non_pad) < 16:
        return False
    # Check for typical 6502 opcodes in the tape buffer routine (SEI, PHA, LDA, STA, JSR, JMP, RTI, RTS)
    common_opcodes = {0x78, 0x48, 0x68, 0xA9, 0x8D, 0xAD, 0x85, 0xA5, 0x20, 0x4C, 0x40, 0x60}
    hits = sum(1 for b in tail if b in common_opcodes)
    return hits >= 5


def _decode_bleepload_turbo(pulses_raw: bytes) -> Optional[Tuple[Dict[int, bytes], List[int]]]:
    """
    Decode Bleepload turbo-tape 256-byte page blocks (used by Bruce Lee and classic US Gold/Datasoft tapes).
    Returns (dict_of_page_hi_to_256_bytes, entry_points) or None if not found.
    """
    n = len(pulses_raw)
    if n < 2000:
        return None

    first_turbo = None
    for i in range(0, n - 200, 50):
        if sum(1 for x in pulses_raw[i : i + 200] if 20 <= x <= 42) > 120:
            first_turbo = i
            break
    if first_turbo is None:
        return None

    bits = [0 if p < 60 else 1 for p in pulses_raw[first_turbo:] if p != 0]
    nb = len(bits)

    def read_byte(p: int) -> Tuple[Optional[int], int]:
        if p + 8 > nb:
            return None, p
        v = 0
        for k in range(8):
            v = (v >> 1) | (bits[p + k] << 7)
        return v, p + 8

    state = 0x02
    patch_3a2 = 0x3F
    aa = 0x55
    a6 = 0
    reg = 0x55
    pos = 0
    pages: Dict[int, bytes] = {}
    cur_page = bytearray()

    while pos < nb:
        if state == 0x02:
            bit_out = reg & 1
            reg = (reg >> 1) | (bits[pos] << 7)
            pos += 1
            if bit_out == 0 and reg == 0x80:
                state = 0x0A
        else:
            b, pos = read_byte(pos)
            if b is None:
                break
            if state == 0x0A:
                if b == 0xAA:
                    state = 0x37
                else:
                    state = 0x02
                    reg = 0x7F
            elif state == 0x37:
                if b == aa:
                    state = patch_3a2
                else:
                    state = 0x02
                    reg = 0x7F
            elif state == 0x3F:
                patch_3a2 = 0x4B
                aa = b
                a6 = b
                cur_page = bytearray()
                state = 0x22
            elif state == 0x4B:
                if b == 0:
                    state = 0x02
                    reg = 0x7F
                else:
                    aa = b
                    a6 = b
                    cur_page = bytearray()
                    state = 0x22
            elif state == 0x22:
                cur_page.append(b)
                aa = (aa + b) & 0xFF
                if len(cur_page) == 256:
                    pages[a6] = bytes(cur_page)
                    state = 0x37

    if len(pages) < 8:
        return None

    entries: List[int] = []
    if 0xFF in pages and len(pages[0xFF]) == 256:
        p_ff = pages[0xFF]
        nmi_vec = p_ff[0xFA] | (p_ff[0xFB] << 8)
        rst_vec = p_ff[0xFC] | (p_ff[0xFD] << 8)
        irq_vec = p_ff[0xFE] | (p_ff[0xFF] << 8)
        for v in (rst_vec, irq_vec, nmi_vec):
            if 0x0800 <= v <= 0xFFF0 and v not in entries:
                entries.append(v)

    return pages, entries


def _decode_freeload_turbo(pulses_raw: bytes) -> Optional[Tuple[Dict[int, bytes], List[int]]]:
    """
    Decode Freeload / Pavloda turbo-tape 256-byte page blocks (used by Donkey Kong, Ocean/Atarisoft tapes).
    Pilot is >= 255 zero-bits (<60) followed by a one-bit (>=60), then [flag_byte, page_hi, 256 data bytes].
    """
    n = len(pulses_raw)
    if n < 2000:
        return None

    first_turbo = None
    for i in range(0, n - 200, 50):
        if sum(1 for x in pulses_raw[i : i + 200] if 20 <= x <= 42) > 120:
            first_turbo = i
            break
    if first_turbo is None:
        return None

    zero_run = 0
    start_bit_idx = None
    for i in range(first_turbo, n):
        p = pulses_raw[i]
        if p == 0:
            continue
        bit = 0 if p < 60 else 1
        if bit == 0:
            zero_run += 1
        else:
            if zero_run >= 255:
                start_bit_idx = i + 1
                break
            zero_run = 0

    if start_bit_idx is None:
        return None

    def read_byte(pos: int) -> Tuple[Optional[int], int]:
        val = 0
        for _ in range(8):
            while pos < n and pulses_raw[pos] == 0:
                pos += 1
            if pos >= n:
                return None, pos
            bit = 0 if pulses_raw[pos] < 60 else 1
            pos += 1
            val = (val >> 1) | (bit << 7)
        return val, pos

    pos = start_bit_idx
    pages: Dict[int, bytes] = {}
    while pos < n:
        flag_byte, pos = read_byte(pos)
        page_hi, pos = read_byte(pos)
        if flag_byte is None or page_hi is None or page_hi == 0:
            break
        page_data = bytearray()
        for _ in range(256):
            b, pos = read_byte(pos)
            if b is None:
                break
            page_data.append(b)
        if len(page_data) == 256:
            pages[page_hi] = bytes(page_data)

    if len(pages) < 8:
        return None

    entries: List[int] = []
    # Check if Page $01 has a patched JMP at $0195 (standard Freeload post-load jump)
    if 0x01 in pages and pages[0x01][0x95] == 0x4C:
        jmp_target = pages[0x01][0x96] | (pages[0x01][0x97] << 8)
        if jmp_target > 0:
            entries.append(jmp_target)
    if 0xFF in pages:
        p_ff = pages[0xFF]
        for off in (0xFC, 0xFE, 0xFA):
            v = p_ff[off] | (p_ff[off + 1] << 8)
            if 0x0400 <= v <= 0xFFF0 and v not in entries:
                entries.append(v)

    return pages, entries


def _pages_to_contiguous_prg(pages: Dict[int, bytes]) -> Tuple[bytes, List[int]]:
    """
    Combine decoded 256-byte turbo pages into the primary contiguous main-game PRG
    (preferring the largest contiguous RAM block starting at >= $0400 or $0800).
    """
    sorted_p = sorted(pages.keys())
    runs: List[List[int]] = []
    for p in sorted_p:
        if p < 0x04:  # Keep $0100-$03FF stack/vector pages separate from main RAM run
            continue
        if not runs or p != runs[-1][-1] + 1:
            runs.append([p])
        else:
            runs[-1].append(p)

    if not runs:
        runs = [sorted_p]

    best_run = max(runs, key=len)
    start_page = best_run[0]
    start_addr = start_page << 8
    payload = b"".join(pages[p] for p in best_run)
    prg = bytes([start_addr & 0xFF, (start_addr >> 8) & 0xFF]) + payload
    return prg, best_run


def extract_tap_stages(tap_data: bytes) -> List[TapStage]:
    """
    Decode a C64 .tap image into structured Loader and Main Game stages.
    Supports:
    - Standard KERNAL single-file and multi-file tapes (e.g. Burger Time)
    - Tape-header fastloaders at $033C..$03FB (e.g. Bruce Lee)
    - Autostart vector loaders at $02A7..$033C (e.g. Donkey Kong, Burger Time)
    - Bleepload & Freeload/Pavloda TurboTape main game streams
    """
    info = read_tap_info(tap_data)
    if not info["valid"]:
        raise ValueError("Invalid TAP data")

    version = info["version"]
    pulses_raw = tap_data[20:]
    pulses: List[int] = []
    idx = 0
    end = len(pulses_raw)

    while idx < end:
        b = pulses_raw[idx]
        idx += 1
        if b == 0:
            if version >= 1 and idx + 3 <= end:
                dur = pulses_raw[idx] | (pulses_raw[idx + 1] << 8) | (pulses_raw[idx + 2] << 16)
                idx += 3
                pulses.append(dur)
            else:
                pulses.append(256)
        else:
            pulses.append(b)

    classified = ["S" if p <= 57 else ("M" if p <= 76 else "L") for p in pulses]
    p_len = len(classified)
    p_idx = 0
    decoded_items: List[Tuple[str, Any]] = []

    while p_idx < p_len - 1:
        c1 = classified[p_idx]
        c2 = classified[p_idx + 1]
        if c1 == "L" and c2 == "M":
            p_idx += 2
            if p_idx + 18 > p_len:
                break
            val = 0
            valid_byte = True
            for bit_i in range(8):
                b1 = classified[p_idx]
                b2 = classified[p_idx + 1]
                p_idx += 2
                if b1 == "S" and b2 == "M":
                    pass
                elif b1 == "M" and b2 == "S":
                    val |= 1 << bit_i
                else:
                    valid_byte = False
                    break
            p_idx += 2
            if valid_byte:
                decoded_items.append(("BYTE", val))
            continue
        elif c1 == "L" and c2 == "S":
            p_idx += 2
            decoded_items.append(("EOD", None))
            continue
        else:
            p_idx += 1

    primary_sync = [0x89, 0x88, 0x87, 0x86, 0x85, 0x84, 0x83, 0x82, 0x81]
    backup_sync = [0x09, 0x08, 0x07, 0x06, 0x05, 0x04, 0x03, 0x02, 0x01]

    blocks: List[bytes] = []
    item_idx = 0
    total_items = len(decoded_items)

    while item_idx < total_items:
        is_sync = False
        if item_idx + 9 <= total_items:
            window = [val for kind, val in decoded_items[item_idx : item_idx + 9] if kind == "BYTE"]
            if window == primary_sync or window == backup_sync:
                is_sync = True
                item_idx += 9

        if is_sync:
            block_bytes = bytearray()
            while item_idx < total_items:
                kind, val = decoded_items[item_idx]
                if kind == "EOD":
                    item_idx += 1
                    break
                elif kind == "BYTE":
                    block_bytes.append(val)
                    item_idx += 1
            if len(block_bytes) > 1:
                blocks.append(bytes(block_bytes[:-1]))
        else:
            item_idx += 1

    kernal_files: List[Tuple[str, int, bytes, bytes]] = []  # (fname, file_type, header_blk, prg_bytes)
    cur_header: Optional[Tuple[str, int, int, int, bytes]] = None

    for blk in blocks:
        if len(blk) == 192:
            file_type = blk[0]
            start_addr = blk[1] | (blk[2] << 8)
            end_addr = blk[3] | (blk[4] << 8)
            fname_raw = blk[5:21]
            fname = "".join(chr(c) for c in fname_raw if 0x20 <= c <= 0x7E).strip() or "PROGRAM"
            cur_header = (fname, file_type, start_addr, end_addr, blk)
        elif cur_header is not None:
            fname, file_type, start_addr, end_addr, hdr_blk = cur_header
            expected_size = end_addr - start_addr
            if expected_size <= 0 or expected_size > len(blk):
                expected_size = len(blk)
            data_payload = blk[:expected_size]

            # Type 1 is Relocatable BASIC ($0801); also check if payload starts with a $0801 BASIC line link
            if file_type == TYPE_BASIC_RELOCATABLE or _looks_like_basic_at_0801(data_payload):
                start_addr = 0x0801

            prg = bytes([start_addr & 0xFF, (start_addr >> 8) & 0xFF]) + data_payload
            kernal_files.append((fname, file_type, hdr_blk, prg))
            cur_header = None

    stages: List[TapStage] = []

    # Check if there is a Bleepload or Freeload TurboTape stream after the KERNAL loader
    turbo_decoded = _decode_bleepload_turbo(pulses_raw)
    turbo_kind = "Bleepload TurboTape"
    if turbo_decoded is None:
        turbo_decoded = _decode_freeload_turbo(pulses_raw)
        turbo_kind = "Freeload/Pavloda TurboTape"

    if len(kernal_files) == 1 and turbo_decoded is not None:
        # Case 1: KERNAL Loader + TurboTape Main Game (e.g. Bruce Lee.tap, Donkey Kong.tap)
        fname, _ftype, hdr_blk, loader_prg = kernal_files[0]
        load_addr = loader_prg[0] | (loader_prg[1] << 8)
        stages.append(
            TapStage(
                name=f"{fname} (LOADER)",
                role="loader",
                prg_data=loader_prg,
                description=f"KERNAL Bootstrap Loader at ${load_addr:04X} ({len(loader_prg) - 2} bytes)",
            )
        )
        # If the 192-byte tape header ($033C..$03FB) contains the 6502 turbo IRQ routine, include it in loader!
        if _header_has_machine_code(hdr_blk):
            hdr_prg = bytes([0x3C, 0x03]) + hdr_blk
            stages.append(
                TapStage(
                    name=f"{fname} (TAPE BUFFER IRQ $033C)",
                    role="loader",
                    prg_data=hdr_prg,
                    description="Cassette Buffer ($033C-$03FB) 6502 Turbo IRQ Routine (entry $0351 / $03E5)",
                    entry_points=[0x0351, 0x03E5],
                )
            )
        pages, turbo_entries = turbo_decoded
        # Check if Page $E0 is a stage-2 turbo loader (like Bruce Lee's $E000 loader)
        if 0xE0 in pages and 0xDF not in pages and pages[0xE0][0] == 0x4C:
            e0_run = [p for p in range(0xE0, 0xE6) if p in pages]
            e0_payload = b"".join(pages[p] for p in e0_run)
            stages.append(
                TapStage(
                    name=f"{fname} (STAGE-2 LOADER $E000)",
                    role="loader",
                    prg_data=bytes([0x00, 0xE0]) + e0_payload,
                    description=f"Stage-2 Turbo Screen & Decruncher Routine at $E000 ({len(e0_payload)} bytes)",
                    entry_points=[0xE000],
                )
            )
        main_prg, main_run = _pages_to_contiguous_prg(pages)
        m_load = main_prg[0] | (main_prg[1] << 8)
        m_len = len(main_prg) - 2
        stages.append(
            TapStage(
                name=f"{fname} (MAIN GAME)",
                role="main",
                prg_data=main_prg,
                description=f"Decoded {turbo_kind} Main Game at ${m_load:04X}-${m_load + m_len:04X} ({m_len} bytes)",
                entry_points=turbo_entries,
            )
        )
    elif len(kernal_files) > 1:
        # Case 2: Multi-file KERNAL tape (e.g. Burger Time.tap: 'BURGERTIME' loader + '+BUR1', '+BUR2' main game)
        for idx_f, (fname, _ftype, hdr_blk, prg) in enumerate(kernal_files):
            load_addr = prg[0] | (prg[1] << 8)
            plen = len(prg) - 2
            is_loader = idx_f == 0 and (plen < 2048 or load_addr < 0x0400)
            role = "loader" if is_loader else "main"
            role_label = "TAPE LOADER" if is_loader else f"MAIN GAME PART {idx_f}"
            stages.append(
                TapStage(
                    name=f"{fname} ({role_label})",
                    role=role,
                    prg_data=prg,
                    description=f"{role_label}: {fname} at ${load_addr:04X}-${load_addr + plen:04X} ({plen} bytes)",
                )
            )
    elif len(kernal_files) == 1:
        # Case 3: Single KERNAL PRG file on tape (e.g. heliscape.tap, SID_Radio_Star.tap)
        fname, _ftype, hdr_blk, prg = kernal_files[0]
        load_addr = prg[0] | (prg[1] << 8)
        payload = prg[2:]
        # If it starts at $0801 with a BASIC stub + ML code, expose the BASIC/bootstrap stub as loader and ML as main
        if load_addr == 0x0801 and _looks_like_basic_at_0801(payload) and len(payload) > 32:
            # Find end of BASIC (0x00, 0x00)
            basic_end = 0
            for i in range(len(payload) - 1):
                if payload[i] == 0 and payload[i + 1] == 0:
                    basic_end = i + 2
                    break
            if 0 < basic_end < len(payload):
                loader_slice = bytes([0x01, 0x08]) + payload[: min(len(payload), basic_end + 32)]
                stages.append(
                    TapStage(
                        name=f"{fname} (BASIC LOADER STUB)",
                        role="loader",
                        prg_data=loader_slice,
                        description=f"BASIC Bootstrap & Entry Stub at $0801 ({len(loader_slice) - 2} bytes)",
                    )
                )
        stages.append(
            TapStage(
                name=fname,
                role="main",
                prg_data=prg,
                description=f"Main Program {fname} at ${load_addr:04X}-${load_addr + len(payload):04X} ({len(payload)} bytes)",
            )
        )

    return stages


def extract_prgs_from_tap(tap_data: bytes) -> List[Tuple[str, bytes]]:
    """
    Decode Datassette pulses from a C64 .tap image and extract PRG files.
    
    Returns:
        List of (filename, prg_bytes) tuples extracted from the tape.
    """
    stages = extract_tap_stages(tap_data)
    if not stages:
        return []
    # Preserve clean (name, prg_data) pairs; if only 1 KERNAL file produced a synthetic BASIC stub + main,
    # return the full PRG as first element for backward compatibility with single-PRG roundtrip tests.
    if len(stages) == 2 and stages[0].name.endswith("(BASIC LOADER STUB)") and stages[1].role == "main":
        return [(stages[1].name, stages[1].prg_data)]
    return [(s.name, s.prg_data) for s in stages]


def tap_to_prg(tap_data: bytes) -> bytes:
    """
    Extract the first PRG binary from a TAP file.
    
    Raises:
        ValueError: If no valid PRG blocks could be extracted from the tape.
    """
    prgs = extract_prgs_from_tap(tap_data)
    if not prgs:
        raise ValueError("No valid PRG blocks detected in TAP image.")
    return prgs[0][1]


