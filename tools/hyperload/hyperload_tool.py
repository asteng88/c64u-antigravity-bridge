#!/usr/bin/env python3
"""
HYPERLOAD tape tool: turn a PRG into a .tap that loads quickly with border stripes.

Takes a PRG with a BASIC SYS line (or --entry for its start address). The tape holds a
KERNAL file that autostarts the loader in hyperload.asm, then the program as single pulses,
about five times faster than a standard tape. Load it as usual with LOAD or SHIFT+RUN/STOP.
A checksum failure stops the tape and turns the screen red.

The program must load between $0800 and $D000: the loader lives below that and the tape
format writes whole pages, so the last one may run up to 255 bytes past the end.

Output next to the PRG:
  <stem>.tap

  python hyperload_tool.py ../../game_dev/Heliscape/heliscape.prg
"""
import argparse
import pathlib
import re
import struct
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build"))
sys.path.insert(0, str(HERE.parent.parent / "src"))
from build_tool import kickass_jar  # noqa: E402
from c64u_bridge.tap import PULSE_SHORT, TYPE_MACHINE_CODE, create_header_payload, encode_block  # noqa: E402

# Pulse lengths in TAP units of 8 cycles. The threshold sits below the midpoint because the
# loader only restarts its timer some 20 cycles after each edge.
FAST_SHORT = 0x20
FAST_LONG = 0x38
THRESHOLD = (FAST_SHORT + FAST_LONG) * 4 - 16
SYNC = 0x5A
# BASIC stops the motor before the loader starts it again, so this has to outlast the restart
PILOT_BITS = 8000
BOOT_LEADER = 10000
BOOT_GAP = 1000
BLOCK_START = 0x02A7         # the data block: exit code, then the BASIC vectors
BLOCK_END = 0x0304
HEADER_CODE = 0x0351
HEADER_SIZE = 192
PAL_HZ = 985248


def sys_entry(prg):
    """The address in the BASIC stub's SYS line."""
    match = re.match(rb".{4}\x9e\s*(\d+)", prg[2:40], re.S)
    return int(match.group(1)) if match else None


def assemble(start, pages, entry):
    """Assemble loader.asm and return (the data block, the code for the header)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "hyperload.prg"
        cmd = ["java", "-jar", str(kickass_jar()), str(HERE / "hyperload.asm"), "-o", str(out), "-odir", tmp,
               ":start=%d" % start, ":pages=%d" % pages, ":entry=%d" % entry,
               ":threshold=%d" % THRESHOLD, ":sync=%d" % SYNC]
        res = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True)
        if res.returncode or not out.is_file():
            raise SystemExit(f"hyperload.asm did not assemble:\n{res.stdout}{res.stderr}")
        image = out.read_bytes()
    if (image[0] | image[1] << 8) != BLOCK_START:
        raise SystemExit("hyperload.asm should start at the data block")
    body = image[2:]
    return body[:BLOCK_END - BLOCK_START], body[HEADER_CODE - BLOCK_START:]


def fast_bits(value):
    return bytes(FAST_LONG if value >> i & 1 else FAST_SHORT for i in range(8))


def fast_stream(data):
    """The pulses of the fast part: data is padded to whole pages here."""
    out = bytearray([FAST_SHORT]) * PILOT_BITS
    out.append(FAST_LONG)
    out += fast_bits(SYNC)
    padded = data + bytes(-len(data) % 256)
    for p in range(0, len(padded), 256):
        block = padded[p:p + 256]
        check = 0
        for b in block:
            out += fast_bits(b)
            check ^= b
        out += fast_bits(check)
    out += bytes([FAST_SHORT]) * 32       # so the last bit has an edge after it
    return bytes(out)


def boot_stream(name, block, code):
    """The standard-speed KERNAL file: header with the loader in it, then the data block."""
    header = bytearray(create_header_payload(BLOCK_START, BLOCK_END, filename=name, file_type=TYPE_MACHINE_CODE))
    offset = HEADER_CODE - 0x033C
    if offset + len(code) > HEADER_SIZE:
        raise SystemExit("the loader does not fit the tape header")
    header[offset:offset + len(code)] = code
    gap = bytes([PULSE_SHORT]) * BOOT_GAP
    return (bytes([PULSE_SHORT]) * BOOT_LEADER
            + encode_block(bytes(header)) + gap + encode_block(bytes(header), is_backup_copy=True)
            + gap * 4
            + encode_block(block) + gap + encode_block(block, is_backup_copy=True)
            + gap)


def build_tape(prg, name, entry=None):
    """Return (.tap bytes, pulses in the standard-speed part, data block, header code, seconds to load)."""
    if len(prg) < 3:
        raise SystemExit("not a PRG")
    start = prg[0] | prg[1] << 8
    data = prg[2:]
    entry = entry if entry is not None else sys_entry(prg)
    if entry is None:
        raise SystemExit("no SYS line in the PRG: give its start address with --entry")
    pages = (len(data) + 255) // 256
    if start < 0x0800 or start + pages * 256 > 0xD000:
        raise SystemExit(f"the program must load between $0800 and $D000: "
                         f"${start:04X} + {pages} pages reaches ${start + pages * 256:04X}")
    if not 0 < pages < 256:
        raise SystemExit("the program has no data")
    block, code = assemble(start, pages, entry)
    boot = boot_stream(name, block, code)
    pulses = boot + fast_stream(data)
    tap = b"C64-TAPE-RAW" + bytes([1, 0, 0, 0]) + struct.pack("<I", len(pulses)) + pulses
    seconds = sum(pulses) * 8 / PAL_HZ
    return tap, len(boot), block, code, seconds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg", type=pathlib.Path)
    ap.add_argument("-o", "--output", type=pathlib.Path)
    ap.add_argument("--name", help="name LOAD shows, up to 16 characters (default: the file's stem)")
    ap.add_argument("--entry", type=lambda s: int(s, 0), help="start address, if the PRG has no SYS line")
    args = ap.parse_args()
    path = args.prg.resolve()
    out = args.output or path.with_suffix(".tap")
    tap, _, _, code, seconds = build_tape(path.read_bytes(), args.name or path.stem, args.entry)
    out.write_bytes(tap)
    print(f"loader: {len(code)} of {HEADER_SIZE - (HEADER_CODE - 0x033C)} bytes in the tape header")
    print(f"load time: {int(seconds) // 60}m {int(seconds) % 60:02d}s")
    print(f"wrote {out.name}: {len(tap)} bytes")


if __name__ == "__main__":
    main()
