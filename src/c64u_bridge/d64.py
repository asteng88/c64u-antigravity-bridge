"""
Commodore 64 D64 Disk Image Parser & Extractor

Supports standard 1541 35-track (and 40-track) D64 disk images.
Provides:
- BAM parsing (disk label, disk ID, DOS version)
- Directory parsing (filenames, file types, sector counts)
- Sector chain traversal and PRG/file extraction
- PETSCII / ASCII name conversions
- Synthetic D64 generation for testing and bridge transfers
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union


# Standard 1541 track sector allocation (1-based track index)
SECTORS_PER_TRACK = [
    0,   # dummy index 0
    # Tracks 1 - 17: 21 sectors each (0..20)
    21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 21,
    # Tracks 18 - 24: 19 sectors each (0..18)
    19, 19, 19, 19, 19, 19, 19,
    # Tracks 25 - 30: 18 sectors each (0..17)
    18, 18, 18, 18, 18, 18,
    # Tracks 31 - 35: 17 sectors each (0..16)
    17, 17, 17, 17, 17,
    # Optional Tracks 36 - 40: 17 sectors each (40-track D64)
    17, 17, 17, 17, 17,
]

# File type bitmask constants
FILE_TYPE_DEL = 0x00
FILE_TYPE_SEQ = 0x01
FILE_TYPE_PRG = 0x02
FILE_TYPE_USR = 0x03
FILE_TYPE_REL = 0x04

FILE_TYPE_NAMES = {
    FILE_TYPE_DEL: "DEL",
    FILE_TYPE_SEQ: "SEQ",
    FILE_TYPE_PRG: "PRG",
    FILE_TYPE_USR: "USR",
    FILE_TYPE_REL: "REL",
}


def petscii_to_ascii(b: bytes) -> str:
    """Convert CBM PETSCII string bytes to readable ASCII string, stripping 0xA0 padding."""
    chars = []
    for byte in b:
        if byte == 0xA0 or byte == 0x00:
            continue
        elif 0x20 <= byte <= 0x7E:
            chars.append(chr(byte))
        elif 0xC1 <= byte <= 0xDA:
            chars.append(chr(byte - 0x80))
        elif 0x41 <= byte <= 0x5A:
            chars.append(chr(byte))
        else:
            chars.append("?")
    return "".join(chars).strip()


def ascii_to_petscii(s: str, length: int = 16, pad_byte: int = 0xA0) -> bytes:
    """Convert an ASCII string to fixed-length PETSCII padded bytes."""
    buf = bytearray()
    for char in s[:length].upper():
        code = ord(char)
        if 0x20 <= code <= 0x7E:
            buf.append(code)
        else:
            buf.append(0x3F)  # '?'
    while len(buf) < length:
        buf.append(pad_byte)
    return bytes(buf)


def track_sector_to_offset(track: int, sector: int) -> int:
    """
    Calculate the byte offset of a given track (1-based) and sector (0-based) in a D64 image.
    """
    if track < 1 or track >= len(SECTORS_PER_TRACK):
        raise ValueError(f"Invalid D64 track number: {track} (valid range 1..40)")
    max_sectors = SECTORS_PER_TRACK[track]
    if sector < 0 or sector >= max_sectors:
        raise ValueError(f"Invalid sector {sector} for track {track} (valid range 0..{max_sectors - 1})")

    sector_index = sum(SECTORS_PER_TRACK[1:track]) + sector
    return sector_index * 256


@dataclass(frozen=True)
class D64Entry:
    filename: str
    file_type: str
    file_type_id: int
    track: int
    sector: int
    blocks: int
    is_closed: bool
    is_locked: bool
    raw_bytes: bytes = b""

    @property
    def is_prg(self) -> bool:
        return self.file_type_id == FILE_TYPE_PRG


@dataclass
class D64Disk:
    disk_name: str
    disk_id: str
    dos_type: str
    entries: List[D64Entry]
    raw_data: bytes

    def read_sector(self, track: int, sector: int) -> bytes:
        """Read a 256-byte sector from the D64 image."""
        offset = track_sector_to_offset(track, sector)
        if offset + 256 > len(self.raw_data):
            raise ValueError(f"Sector T:{track} S:{sector} at offset {offset} extends beyond D64 image size ({len(self.raw_data)} bytes)")
        return self.raw_data[offset : offset + 256]

    def extract_file(self, entry: D64Entry) -> bytes:
        """
        Traverse the sector chain of a file entry and return the assembled file bytes.
        For PRG files, the first 2 bytes are the 16-bit load address.
        """
        if entry.track == 0:
            return b""

        payload = bytearray()
        track = entry.track
        sector = entry.sector
        visited = set()

        while track != 0:
            pos = (track, sector)
            if pos in visited:
                break  # avoid infinite loop on circular chains
            visited.add(pos)

            sector_data = self.read_sector(track, sector)
            next_track = sector_data[0]
            next_sector = sector_data[1]

            if next_track == 0:
                # Final sector: next_sector is index of the last valid byte + 1
                last_byte_idx = next_sector
                if last_byte_idx > 1:
                    payload.extend(sector_data[2 : last_byte_idx + 1])
                elif last_byte_idx == 0:
                    payload.extend(sector_data[2:256])
                break
            else:
                # Intermediate sector: 254 bytes of data
                payload.extend(sector_data[2:256])
                track = next_track
                sector = next_sector

        return bytes(payload)

    def extract_all_prgs(self) -> List[Tuple[str, bytes]]:
        """Extract all PRG files from the disk image as (filename, prg_bytes) pairs."""
        results = []
        for entry in self.entries:
            if entry.is_prg:
                prg_bytes = self.extract_file(entry)
                if prg_bytes:
                    results.append((entry.filename, prg_bytes))
        return results

    def find_entry(self, filename: str) -> Optional[D64Entry]:
        """Case-insensitive search for a directory entry by filename."""
        upper_target = filename.strip().upper()
        for entry in self.entries:
            if entry.filename.upper() == upper_target:
                return entry
        return None


def read_d64(data: bytes) -> D64Disk:
    """
    Parse a D64 disk image from raw bytes.
    Supports standard 35-track (174,848 or 175,531 with errors) and 40-track images.
    """
    if len(data) < 174848:
        raise ValueError(f"File is too small to be a valid D64 disk image ({len(data)} bytes, minimum 174,848)")

    # Read BAM sector: Track 18, Sector 0
    bam_offset = track_sector_to_offset(18, 0)
    bam_sector = data[bam_offset : bam_offset + 256]

    first_dir_track = bam_sector[0]
    first_dir_sector = bam_sector[1]
    disk_name = petscii_to_ascii(bam_sector[144:160])
    disk_id = petscii_to_ascii(bam_sector[162:164])
    dos_type = petscii_to_ascii(bam_sector[165:167])

    entries: List[D64Entry] = []
    dir_track = first_dir_track if first_dir_track > 0 else 18
    dir_sector = first_dir_sector if first_dir_track > 0 else 1
    visited_dir_sectors = set()

    disk_obj = D64Disk(
        disk_name=disk_name or "UNTITLED",
        disk_id=disk_id or "2A",
        dos_type=dos_type or "2A",
        entries=[],
        raw_data=data,
    )

    # Traverse directory sectors
    while dir_track != 0:
        if (dir_track, dir_sector) in visited_dir_sectors:
            break
        visited_dir_sectors.add((dir_track, dir_sector))

        sector_bytes = disk_obj.read_sector(dir_track, dir_sector)
        next_dir_track = sector_bytes[0]
        next_dir_sector = sector_bytes[1]

        # Each directory sector contains up to 8 entries of 32 bytes
        for entry_idx in range(8):
            offset = entry_idx * 32
            entry_bytes = sector_bytes[offset : offset + 32]
            file_type_raw = entry_bytes[2]
            if file_type_raw == 0:
                continue  # Scratched / deleted slot

            file_type_id = file_type_raw & 0x07
            is_closed = bool(file_type_raw & 0x80)
            is_locked = bool(file_type_raw & 0x40)
            type_name = FILE_TYPE_NAMES.get(file_type_id, f"?{file_type_id}")

            first_track = entry_bytes[3]
            first_sector = entry_bytes[4]
            filename = petscii_to_ascii(entry_bytes[5:21])
            blocks = entry_bytes[30] | (entry_bytes[31] << 8)

            entry = D64Entry(
                filename=filename or f"FILE_{len(entries)+1}",
                file_type=type_name,
                file_type_id=file_type_id,
                track=first_track,
                sector=first_sector,
                blocks=blocks,
                is_closed=is_closed,
                is_locked=is_locked,
                raw_bytes=entry_bytes,
            )
            entries.append(entry)

        if next_dir_track == 0 or (next_dir_track == 18 and next_dir_sector == 0xFF):
            break
        dir_track = next_dir_track
        dir_sector = next_dir_sector

    disk_obj.entries = entries
    return disk_obj


def read_d64_file(path: Union[str, Path]) -> D64Disk:
    """Read and parse a D64 disk image from disk."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"D64 disk image not found: {p}")
    return read_d64(p.read_bytes())


def create_d64(
    disk_name: str = "EMPTY DISK",
    disk_id: str = "2A",
    files: Optional[List[Tuple[str, bytes]]] = None,
) -> bytes:
    """
    Create a clean, valid 35-track D64 disk image with BAM, directory, and optional files.
    Files list should contain (filename, prg_bytes) pairs.
    """
    # 35 tracks total 683 sectors * 256 bytes = 174,848 bytes
    total_bytes = sum(SECTORS_PER_TRACK[1:36]) * 256
    disk = bytearray(total_bytes)

    # 1. Format BAM Sector: Track 18, Sector 0
    bam_offset = track_sector_to_offset(18, 0)
    # Link to first directory sector: Track 18, Sector 1
    disk[bam_offset + 0] = 18
    disk[bam_offset + 1] = 1
    disk[bam_offset + 2] = 0x41  # DOS version 'A'
    disk[bam_offset + 3] = 0x00

    # Initialize BAM entries for tracks 1..35
    for t in range(1, 36):
        entry_off = bam_offset + 4 + (t - 1) * 4
        num_sectors = SECTORS_PER_TRACK[t]
        if t == 18:
            # Track 18 is BAM and directory
            disk[entry_off + 0] = 0  # No free sectors for files
            disk[entry_off + 1] = 0x00
            disk[entry_off + 2] = 0x00
            disk[entry_off + 3] = 0x00
        else:
            disk[entry_off + 0] = num_sectors
            # Set bits for available sectors
            mask = (1 << num_sectors) - 1
            disk[entry_off + 1] = mask & 0xFF
            disk[entry_off + 2] = (mask >> 8) & 0xFF
            disk[entry_off + 3] = (mask >> 16) & 0xFF

    # Disk name, ID, and DOS type
    name_bytes = ascii_to_petscii(disk_name, 16, 0xA0)
    id_bytes = ascii_to_petscii(disk_id, 2, 0xA0)
    disk[bam_offset + 144 : bam_offset + 160] = name_bytes
    disk[bam_offset + 160 : bam_offset + 162] = b"\xa0\xa0"
    disk[bam_offset + 162 : bam_offset + 164] = id_bytes
    disk[bam_offset + 164] = 0xA0
    disk[bam_offset + 165 : bam_offset + 167] = b"2A"
    disk[bam_offset + 167 : bam_offset + 171] = b"\xa0\xa0\xa0\xa0"

    # 2. Initialize First Directory Sector: Track 18, Sector 1
    dir_offset = track_sector_to_offset(18, 1)
    disk[dir_offset + 0] = 0x00  # Track 0 = last directory block
    disk[dir_offset + 1] = 0xFF  # Next sector = 0xFF

    # 3. Write files if provided
    if files:
        # Simple allocator: use tracks 1..17
        alloc_track = 1
        alloc_sector = 0
        dir_entry_idx = 0

        for fname, fbytes in files:
            if dir_entry_idx >= 8:
                # For simplicity in test generator, supports up to 8 files per initial dir sector
                break

            file_start_track = alloc_track
            file_start_sector = alloc_sector

            # Calculate blocks
            remaining_bytes = fbytes
            blocks_for_file = 0

            while remaining_bytes:
                cur_t = alloc_track
                cur_s = alloc_sector
                sec_off = track_sector_to_offset(cur_t, cur_s)
                blocks_for_file += 1

                # Advance allocation
                alloc_sector += 1
                if alloc_sector >= SECTORS_PER_TRACK[alloc_track]:
                    alloc_sector = 0
                    alloc_track += 1
                    if alloc_track == 18:
                        alloc_track = 19  # skip directory track

                if len(remaining_bytes) <= 254:
                    # Final sector
                    disk[sec_off + 0] = 0x00  # Next track 0
                    disk[sec_off + 1] = len(remaining_bytes) + 1  # Last byte offset
                    disk[sec_off + 2 : sec_off + 2 + len(remaining_bytes)] = remaining_bytes
                    remaining_bytes = b""
                else:
                    chunk = remaining_bytes[:254]
                    remaining_bytes = remaining_bytes[254:]
                    disk[sec_off + 0] = alloc_track
                    disk[sec_off + 1] = alloc_sector
                    disk[sec_off + 2 : sec_off + 256] = chunk

            # Directory entry (32 bytes)
            d_off = dir_offset + dir_entry_idx * 32
            # Byte 2: File type: PRG (0x02) | Closed (0x80) = 0x82
            disk[d_off + 2] = 0x82
            disk[d_off + 3] = file_start_track
            disk[d_off + 4] = file_start_sector
            disk[d_off + 5 : d_off + 21] = ascii_to_petscii(fname, 16, 0xA0)
            disk[d_off + 30] = blocks_for_file & 0xFF
            disk[d_off + 31] = (blocks_for_file >> 8) & 0xFF

            dir_entry_idx += 1

    return bytes(disk)


def save_prg_to_d64(
    prg_path: Union[str, Path],
    d64_path: Optional[Union[str, Path]] = None,
    disk_name: Optional[str] = None,
    file_name: Optional[str] = None,
    disk_id: str = "2A",
) -> Path:
    """
    Package an existing .prg file into a standard 1541 .d64 disk image.
    
    Args:
        prg_path: Path to existing .prg file.
        d64_path: Optional target .d64 path (defaults to <prg_stem>.d64 in same folder).
        disk_name: Optional disk header label (defaults to uppercase filename).
        file_name: Optional file directory name (defaults to uppercase filename).
        disk_id: 2-character disk ID.
        
    Returns:
        Path to the saved .d64 file.
    """
    src_prg = Path(prg_path).resolve()
    if not src_prg.exists():
        raise FileNotFoundError(f"PRG file not found: {src_prg}")

    prg_data = src_prg.read_bytes()
    d_name = disk_name or src_prg.stem.upper()[:16]
    f_name = file_name or src_prg.stem.upper()[:16]
    out_d64 = Path(d64_path).resolve() if d64_path else src_prg.with_suffix(".d64")

    d64_bytes = create_d64(
        disk_name=d_name,
        disk_id=disk_id,
        files=[(f_name, prg_data)],
    )

    out_d64.write_bytes(d64_bytes)
    return out_d64


def asm_to_d64(
    asm_path: Union[str, Path],
    d64_path: Optional[Union[str, Path]] = None,
    compiler: Optional[object] = None,
    disk_name: Optional[str] = None,
    disk_id: str = "2A",
    assembler: str = "auto",
) -> Path:
    """
    Assemble a 6502 assembly source file into PRG, then package into a .d64 disk image.
    """
    from .compiler import CrossCompiler

    src_asm = Path(asm_path).resolve()
    if not src_asm.exists():
        raise FileNotFoundError(f"Assembly file not found: {src_asm}")

    comp = compiler or CrossCompiler()
    temp_prg = src_asm.with_suffix(".prg")

    comp_res = comp.compile(src_asm, output_prg=temp_prg, assembler=assembler)
    if not comp_res.success or not temp_prg.exists():
        err = comp_res.error_message or comp_res.stderr or comp_res.stdout
        raise RuntimeError(f"Assembly failed for {src_asm.name}: {err}")

    name = disk_name or src_asm.stem.upper()[:16]
    out_d64 = Path(d64_path).resolve() if d64_path else src_asm.with_suffix(".d64")

    return save_prg_to_d64(temp_prg, d64_path=out_d64, disk_name=name, disk_id=disk_id)

