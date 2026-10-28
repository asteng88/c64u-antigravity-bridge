#!/usr/bin/env python3
"""
Wrap a music PRG in a PSID v2 file for SID players (including the C64U's).

  python make_psid.py music.prg -o tune.sid --name "Title" --author "Me" \
      --released "2026 Studio" --init 0x1000 --play 0x1003
"""
import argparse
import pathlib
import struct


def text32(s):
    return s.encode("latin-1", "replace")[:32].ljust(32, b"\x00")


def make_psid(prg, init, play, name, author, released, flags=0x0034):
    """flags $0034 = PAL, plays on 6581 or 8580."""
    header = b"PSID" + struct.pack(">HHHHHHHI", 2, 0x7C, 0x0000, init, play, 1, 1, 0)
    header += text32(name) + text32(author) + text32(released)
    header += struct.pack(">HBBBB", flags, 0, 0, 0, 0)
    assert len(header) == 0x7C
    return header + prg  # load address 0: the PRG's own first two bytes are used


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg", type=pathlib.Path)
    ap.add_argument("-o", "--out", type=pathlib.Path, help="default: the PRG name with .sid")
    ap.add_argument("--init", type=lambda s: int(s, 0), default=0x1000)
    ap.add_argument("--play", type=lambda s: int(s, 0), default=0x1003)
    ap.add_argument("--name", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--released", default="")
    args = ap.parse_args()
    prg = args.prg.read_bytes()
    out = args.out or args.prg.with_suffix(".sid")
    out.write_bytes(make_psid(prg, args.init, args.play, args.name, args.author, args.released))
    print(f"{out.name}: {len(prg) - 2} bytes of music at ${prg[0] | prg[1] << 8:04X}")


if __name__ == "__main__":
    main()
