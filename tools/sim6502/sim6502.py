#!/usr/bin/env python3
"""
Minimal NMOS 6502 emulator (official opcodes) for profiling music drivers.

Loads a PRG or a PSID file, calls the init address once, then calls the play
address once per frame and records the 25 SID registers after each call, plus
the cycles each call took. Stops with an error on an illegal opcode or a
runaway call. For a .sid file, init and play come from its header.

  python sim6502.py music.prg --frames 1800 --out sid_log.json
  python sim6502.py tune.sid
"""
import argparse
import json
import pathlib


class CPU:
    def __init__(self):
        self.mem = bytearray(0x10000)
        self.a = self.x = self.y = 0
        self.sp = 0xFD
        self.pc = 0
        self.c = self.z = self.i = self.d = self.v = self.n = 0
        self.cycles = 0
        self.sid = [0] * 25
        self.ops = self._build()

    # ---- memory
    def rd(self, a):
        return self.mem[a & 0xFFFF]

    def wr(self, a, v):
        a &= 0xFFFF
        v &= 0xFF
        if 0xD400 <= a <= 0xD418:
            self.sid[a - 0xD400] = v
        self.mem[a] = v

    def rd16(self, a):
        return self.rd(a) | (self.rd(a + 1) << 8)

    def push(self, v):
        self.wr(0x100 + self.sp, v)
        self.sp = (self.sp - 1) & 0xFF

    def pull(self):
        self.sp = (self.sp + 1) & 0xFF
        return self.rd(0x100 + self.sp)

    def nz(self, v):
        v &= 0xFF
        self.z = int(v == 0)
        self.n = v >> 7
        return v

    def flags(self):
        return self.c | self.z << 1 | self.i << 2 | self.d << 3 | 0x30 | self.v << 6 | self.n << 7

    def set_flags(self, p):
        self.c, self.z, self.i, self.d = p & 1, p >> 1 & 1, p >> 2 & 1, p >> 3 & 1
        self.v, self.n = p >> 6 & 1, p >> 7 & 1

    # ---- addressing: return effective address (or None for implied/acc)
    def addr(self, mode):
        pc = self.pc
        if mode == "imm":
            self.pc += 1
            return pc
        if mode == "zp":
            self.pc += 1
            return self.rd(pc)
        if mode == "zpx":
            self.pc += 1
            return (self.rd(pc) + self.x) & 0xFF
        if mode == "zpy":
            self.pc += 1
            return (self.rd(pc) + self.y) & 0xFF
        if mode == "abs":
            self.pc += 2
            return self.rd16(pc)
        if mode == "abx":
            self.pc += 2
            return (self.rd16(pc) + self.x) & 0xFFFF
        if mode == "aby":
            self.pc += 2
            return (self.rd16(pc) + self.y) & 0xFFFF
        if mode == "inx":
            self.pc += 1
            z = (self.rd(pc) + self.x) & 0xFF
            return self.rd(z) | self.rd((z + 1) & 0xFF) << 8
        if mode == "iny":
            self.pc += 1
            z = self.rd(pc)
            return ((self.rd(z) | self.rd((z + 1) & 0xFF) << 8) + self.y) & 0xFFFF
        if mode == "ind":
            self.pc += 2
            p = self.rd16(pc)
            return self.rd(p) | self.rd((p & 0xFF00) | ((p + 1) & 0xFF)) << 8
        if mode == "rel":
            self.pc += 1
            off = self.rd(pc)
            return (self.pc + (off - 256 if off & 0x80 else off)) & 0xFFFF
        return None

    def _build(self):
        ops = {}

        def op(code, name, mode, cyc):
            ops[code] = (name, mode, cyc)

        table = {
            "LDA": {"imm": (0xA9, 2), "zp": (0xA5, 3), "zpx": (0xB5, 4), "abs": (0xAD, 4), "abx": (0xBD, 4), "aby": (0xB9, 4), "inx": (0xA1, 6), "iny": (0xB1, 5)},
            "LDX": {"imm": (0xA2, 2), "zp": (0xA6, 3), "zpy": (0xB6, 4), "abs": (0xAE, 4), "aby": (0xBE, 4)},
            "LDY": {"imm": (0xA0, 2), "zp": (0xA4, 3), "zpx": (0xB4, 4), "abs": (0xAC, 4), "abx": (0xBC, 4)},
            "STA": {"zp": (0x85, 3), "zpx": (0x95, 4), "abs": (0x8D, 4), "abx": (0x9D, 5), "aby": (0x99, 5), "inx": (0x81, 6), "iny": (0x91, 6)},
            "STX": {"zp": (0x86, 3), "zpy": (0x96, 4), "abs": (0x8E, 4)},
            "STY": {"zp": (0x84, 3), "zpx": (0x94, 4), "abs": (0x8C, 4)},
            "ADC": {"imm": (0x69, 2), "zp": (0x65, 3), "zpx": (0x75, 4), "abs": (0x6D, 4), "abx": (0x7D, 4), "aby": (0x79, 4), "inx": (0x61, 6), "iny": (0x71, 5)},
            "SBC": {"imm": (0xE9, 2), "zp": (0xE5, 3), "zpx": (0xF5, 4), "abs": (0xED, 4), "abx": (0xFD, 4), "aby": (0xF9, 4), "inx": (0xE1, 6), "iny": (0xF1, 5)},
            "AND": {"imm": (0x29, 2), "zp": (0x25, 3), "zpx": (0x35, 4), "abs": (0x2D, 4), "abx": (0x3D, 4), "aby": (0x39, 4), "inx": (0x21, 6), "iny": (0x31, 5)},
            "ORA": {"imm": (0x09, 2), "zp": (0x05, 3), "zpx": (0x15, 4), "abs": (0x0D, 4), "abx": (0x1D, 4), "aby": (0x19, 4), "inx": (0x01, 6), "iny": (0x11, 5)},
            "EOR": {"imm": (0x49, 2), "zp": (0x45, 3), "zpx": (0x55, 4), "abs": (0x4D, 4), "abx": (0x5D, 4), "aby": (0x59, 4), "inx": (0x41, 6), "iny": (0x51, 5)},
            "CMP": {"imm": (0xC9, 2), "zp": (0xC5, 3), "zpx": (0xD5, 4), "abs": (0xCD, 4), "abx": (0xDD, 4), "aby": (0xD9, 4), "inx": (0xC1, 6), "iny": (0xD1, 5)},
            "CPX": {"imm": (0xE0, 2), "zp": (0xE4, 3), "abs": (0xEC, 4)},
            "CPY": {"imm": (0xC0, 2), "zp": (0xC4, 3), "abs": (0xCC, 4)},
            "BIT": {"zp": (0x24, 3), "abs": (0x2C, 4)},
            "INC": {"zp": (0xE6, 5), "zpx": (0xF6, 6), "abs": (0xEE, 6), "abx": (0xFE, 7)},
            "DEC": {"zp": (0xC6, 5), "zpx": (0xD6, 6), "abs": (0xCE, 6), "abx": (0xDE, 7)},
            "ASL": {"acc": (0x0A, 2), "zp": (0x06, 5), "zpx": (0x16, 6), "abs": (0x0E, 6), "abx": (0x1E, 7)},
            "LSR": {"acc": (0x4A, 2), "zp": (0x46, 5), "zpx": (0x56, 6), "abs": (0x4E, 6), "abx": (0x5E, 7)},
            "ROL": {"acc": (0x2A, 2), "zp": (0x26, 5), "zpx": (0x36, 6), "abs": (0x2E, 6), "abx": (0x3E, 7)},
            "ROR": {"acc": (0x6A, 2), "zp": (0x66, 5), "zpx": (0x76, 6), "abs": (0x6E, 6), "abx": (0x7E, 7)},
            "JMP": {"abs": (0x4C, 3), "ind": (0x6C, 5)},
            "JSR": {"abs": (0x20, 6)},
        }
        for name, modes in table.items():
            for mode, (code, cyc) in modes.items():
                op(code, name, mode, cyc)
        for name, code in {"BPL": 0x10, "BMI": 0x30, "BVC": 0x50, "BVS": 0x70, "BCC": 0x90, "BCS": 0xB0, "BNE": 0xD0, "BEQ": 0xF0}.items():
            op(code, name, "rel", 2)
        implied = {"RTS": (0x60, 6), "RTI": (0x40, 6), "BRK": (0x00, 7), "NOP": (0xEA, 2), "PHA": (0x48, 3), "PLA": (0x68, 4),
                   "PHP": (0x08, 3), "PLP": (0x28, 4), "TAX": (0xAA, 2), "TAY": (0xA8, 2), "TXA": (0x8A, 2), "TYA": (0x98, 2),
                   "TSX": (0xBA, 2), "TXS": (0x9A, 2), "INX": (0xE8, 2), "INY": (0xC8, 2), "DEX": (0xCA, 2), "DEY": (0x88, 2),
                   "CLC": (0x18, 2), "SEC": (0x38, 2), "CLI": (0x58, 2), "SEI": (0x78, 2), "CLD": (0xD8, 2), "SED": (0xF8, 2), "CLV": (0xB8, 2)}
        for name, (code, cyc) in implied.items():
            op(code, name, "imp", cyc)
        return ops

    def adc(self, v):
        assert not self.d, "decimal mode not supported"
        r = self.a + v + self.c
        self.v = int(((self.a ^ r) & (v ^ r) & 0x80) != 0)
        self.c = int(r > 0xFF)
        self.a = self.nz(r)

    def cmp(self, reg, v):
        r = reg - v
        self.c = int(reg >= v)
        self.nz(r)

    def step(self):
        code = self.rd(self.pc)
        if code not in self.ops:
            raise RuntimeError(f"illegal opcode ${code:02X} at ${self.pc:04X}")
        name, mode, cyc = self.ops[code]
        self.pc = (self.pc + 1) & 0xFFFF
        ea = self.addr(mode) if mode not in ("imp", "acc") else None
        self.cycles += cyc
        if name == "LDA": self.a = self.nz(self.rd(ea))
        elif name == "LDX": self.x = self.nz(self.rd(ea))
        elif name == "LDY": self.y = self.nz(self.rd(ea))
        elif name == "STA": self.wr(ea, self.a)
        elif name == "STX": self.wr(ea, self.x)
        elif name == "STY": self.wr(ea, self.y)
        elif name == "ADC": self.adc(self.rd(ea))
        elif name == "SBC": self.adc(self.rd(ea) ^ 0xFF)
        elif name == "AND": self.a = self.nz(self.a & self.rd(ea))
        elif name == "ORA": self.a = self.nz(self.a | self.rd(ea))
        elif name == "EOR": self.a = self.nz(self.a ^ self.rd(ea))
        elif name == "CMP": self.cmp(self.a, self.rd(ea))
        elif name == "CPX": self.cmp(self.x, self.rd(ea))
        elif name == "CPY": self.cmp(self.y, self.rd(ea))
        elif name == "BIT":
            v = self.rd(ea)
            self.z, self.n, self.v = int((self.a & v) == 0), v >> 7, v >> 6 & 1
        elif name in ("INC", "DEC"):
            self.wr(ea, self.nz(self.rd(ea) + (1 if name == "INC" else -1)))
        elif name in ("ASL", "LSR", "ROL", "ROR"):
            v = self.a if ea is None else self.rd(ea)
            if name == "ASL": self.c, v = v >> 7, v << 1
            elif name == "LSR": self.c, v = v & 1, v >> 1
            elif name == "ROL": self.c, v = v >> 7, (v << 1) | self.c
            else: self.c, v = v & 1, (v >> 1) | (self.c << 7)
            v = self.nz(v)
            if ea is None: self.a = v
            else: self.wr(ea, v)
        elif name == "JMP": self.pc = ea
        elif name == "JSR":
            ret = (self.pc - 1) & 0xFFFF
            self.push(ret >> 8)
            self.push(ret & 0xFF)
            self.pc = ea
        elif name == "RTS":
            self.pc = ((self.pull() | self.pull() << 8) + 1) & 0xFFFF
        elif name == "RTI":
            self.set_flags(self.pull())
            self.pc = self.pull() | self.pull() << 8
        elif name == "BRK": raise RuntimeError(f"BRK at ${(self.pc - 1) & 0xFFFF:04X}")
        elif mode == "rel":
            cond = {"BPL": not self.n, "BMI": self.n, "BVC": not self.v, "BVS": self.v,
                    "BCC": not self.c, "BCS": self.c, "BNE": not self.z, "BEQ": self.z}[name]
            if cond:
                self.cycles += 1
                self.pc = ea
        elif name == "PHA": self.push(self.a)
        elif name == "PLA": self.a = self.nz(self.pull())
        elif name == "PHP": self.push(self.flags())
        elif name == "PLP": self.set_flags(self.pull())
        elif name == "TAX": self.x = self.nz(self.a)
        elif name == "TAY": self.y = self.nz(self.a)
        elif name == "TXA": self.a = self.nz(self.x)
        elif name == "TYA": self.a = self.nz(self.y)
        elif name == "TSX": self.x = self.nz(self.sp)
        elif name == "TXS": self.sp = self.x
        elif name == "INX": self.x = self.nz(self.x + 1)
        elif name == "INY": self.y = self.nz(self.y + 1)
        elif name == "DEX": self.x = self.nz(self.x - 1)
        elif name == "DEY": self.y = self.nz(self.y - 1)
        elif name == "CLC": self.c = 0
        elif name == "SEC": self.c = 1
        elif name == "CLI": self.i = 0
        elif name == "SEI": self.i = 1
        elif name == "CLD": self.d = 0
        elif name == "SED": self.d = 1
        elif name == "CLV": self.v = 0

    def call(self, addr, limit=200000):
        """JSR addr and run until it returns; returns cycles used."""
        start = self.cycles
        self.push(0xFF)          # return to $FFFF+1 = $0000 sentinel
        self.push(0xFF)
        self.pc = addr
        steps = 0
        while self.pc != 0x0000:
            self.step()
            steps += 1
            if steps > limit:
                raise RuntimeError(f"call to ${addr:04X} did not return")
        return self.cycles - start


def from_psid(data):
    """PSID/RSID -> (prg bytes with load address, init, play)."""
    offset, load, init, play = (int.from_bytes(data[i:i + 2], "big") for i in (6, 8, 10, 12))
    body = data[offset:]
    if load == 0:  # load address is the first two bytes of the data
        load, body = body[0] | body[1] << 8, body[2:]
    if play == 0:
        raise SystemExit("this SID installs its own interrupt (play address 0); it cannot be profiled per frame")
    return bytes([load & 0xFF, load >> 8]) + body, init or load, play


def run(prg, init, play, frames):
    cpu = CPU()
    load = prg[0] | prg[1] << 8
    cpu.mem[load:load + len(prg) - 2] = prg[2:]
    cpu.call(init)
    regs, cyc = [], []
    for _ in range(frames):
        cyc.append(cpu.call(play))
        regs.append(list(cpu.sid))
    return regs, cyc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg", type=pathlib.Path, help=".prg (load address first) or .sid file")
    ap.add_argument("--init", type=lambda s: int(s, 0), default=0x1000, help="PRG only (default $1000)")
    ap.add_argument("--play", type=lambda s: int(s, 0), default=0x1003, help="PRG only (default $1003)")
    ap.add_argument("--frames", type=int, default=1800)
    ap.add_argument("--out", type=pathlib.Path)
    args = ap.parse_args()
    data = args.prg.read_bytes()
    if data[:4] in (b"PSID", b"RSID"):
        prg, init, play = from_psid(data)
    else:
        prg, init, play = data, args.init, args.play
    regs, cyc = run(prg, init, play, args.frames)
    print(f"{len(regs)} frames ok; play routine {min(cyc)}-{max(cyc)} cycles "
          f"(max {max(cyc) / 63:.1f} PAL raster lines)")
    if args.out:
        args.out.write_text(json.dumps({"frames": len(regs), "maxCycles": max(cyc),
                                        "regs": ["".join(f"{v:02x}" for v in r) for r in regs]}))


if __name__ == "__main__":
    main()
