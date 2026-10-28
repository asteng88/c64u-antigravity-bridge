#!/usr/bin/env python3
"""
Headless C64: runs a PRG for a number of PAL frames and saves screenshots.

Built on tools/sim6502 (CPU) with enough of the rest of the machine to test
games without an emulator or the real hardware:

  * VIC-II rendered line by line (text, multicolor text, hires and multicolor
    bitmap, 8 sprites with multicolor, expansion, MSB and background priority,
    border, fine scroll, VIC banks via $DD00), so raster splits and sprite
    multiplexers show up as they would on screen.
  * Raster interrupts ($D012/$D019/$D01A), bad-line CPU stalls.
  * CIA 1 keyboard matrix and joystick port 2, driven by an input script.
  * Memory banking through $01. ROMs are not emulated: programs that bank the
    KERNAL out (and use $FFFE) run as-is; programs that stay on the KERNAL get
    its IRQ entry ($0314), exit ($EA31/$EA81) and GETIN ($FFE4) as traps.

  python c64sim.py game.prg --frames 600 --shot 100,300,599 --scale 2
  python c64sim.py game.prg --frames 900 --input script.json --shot 899 --dump c000:40

Input script (JSON list): {"frame": 120, "joy": "fire", "hold": 4} or
{"frame": 200, "keys": "space", "hold": 3}; joy tokens up/down/left/right/fire
joined with "+", e.g. "up+fire". {"frame": 90, "poke": "0020:40,00"} writes bytes
(hex) into RAM at the start of that frame, e.g. to place a cursor for a test. Screenshots are 384x272 PNGs (the visible PAL
area) written next to the PRG as <name>_f<frame>.png.
"""
import argparse
import json
import pathlib
import struct
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "sim6502"))
from sim6502 import CPU  # noqa: E402

PALETTE = [
    (0x00, 0x00, 0x00), (0xFF, 0xFF, 0xFF), (0x68, 0x37, 0x2B), (0x70, 0xA4, 0xB2),
    (0x6F, 0x3D, 0x86), (0x58, 0x8D, 0x43), (0x35, 0x28, 0x79), (0xB8, 0xC7, 0x6F),
    (0x6F, 0x4F, 0x25), (0x43, 0x39, 0x00), (0x9A, 0x67, 0x59), (0x44, 0x44, 0x44),
    (0x6C, 0x6C, 0x6C), (0x9A, 0xD2, 0x84), (0x6C, 0x5E, 0xB5), (0x95, 0x95, 0x95),
]
CYCLES_PER_LINE = 63
LINES = 312
FIRST_LINE = 15            # first raster line in the screenshot (36 px of top border)
IMG_W, IMG_H = 384, 272
SPRITE_X0 = 24 - 32        # sprite X that lands on screenshot column 0

# keyboard matrix: name -> (column written to $DC00, row bit read from $DC01)
KEYS = {
    "del": (0, 0), "return": (0, 1), "right": (0, 2), "f7": (0, 3), "f1": (0, 4), "f3": (0, 5), "f5": (0, 6), "down": (0, 7),
    "3": (1, 0), "w": (1, 1), "a": (1, 2), "4": (1, 3), "z": (1, 4), "s": (1, 5), "e": (1, 6), "lshift": (1, 7),
    "5": (2, 0), "r": (2, 1), "d": (2, 2), "6": (2, 3), "c": (2, 4), "f": (2, 5), "t": (2, 6), "x": (2, 7),
    "7": (3, 0), "y": (3, 1), "g": (3, 2), "8": (3, 3), "b": (3, 4), "h": (3, 5), "u": (3, 6), "v": (3, 7),
    "9": (4, 0), "i": (4, 1), "j": (4, 2), "0": (4, 3), "m": (4, 4), "k": (4, 5), "o": (4, 6), "n": (4, 7),
    "+": (5, 0), "p": (5, 1), "l": (5, 2), "-": (5, 3), ".": (5, 4), ":": (5, 5), "@": (5, 6), ",": (5, 7),
    "£": (6, 0), "*": (6, 1), ";": (6, 2), "home": (6, 3), "rshift": (6, 4), "=": (6, 5), "^": (6, 6), "/": (6, 7),
    "1": (7, 0), "<-": (7, 1), "ctrl": (7, 2), "2": (7, 3), "space": (7, 4), "c=": (7, 5), "q": (7, 6), "stop": (7, 7),
}
JOY_BITS = {"up": 1, "down": 2, "left": 4, "right": 8, "fire": 16}
PETSCII = {"space": 0x20, "return": 0x0D, "f1": 0x85}


class C64(CPU):
    def __init__(self):
        super().__init__()
        self.port = 0x37
        self.vic = bytearray(0x40)
        self.color = bytearray(0x400)
        self.cia1 = bytearray(16)
        self.cia2 = bytearray(16)
        self.cia2[0] = 0x03
        self.cia1[0] = self.cia1[1] = 0xFF
        self.raster = 0
        self.frame = 0
        self.line_start = 0
        self.joy = 0                 # active-high bits, port 2
        self.keys = set()
        self.key_queue = []
        self.render = False
        self.image = None
        self.vic[0x11] = 0x1B
        self.vic[0x16] = 0xC8

    # ---- banking
    def io_visible(self):
        return (self.port & 3) != 0 and (self.port & 4) != 0

    def kernal_visible(self):
        return (self.port & 2) != 0

    def rd(self, a):
        a &= 0xFFFF
        if 0xD000 <= a <= 0xDFFF and self.io_visible():
            return self.io_read(a)
        if a == 1:
            return self.port
        return self.mem[a]

    def wr(self, a, v):
        a &= 0xFFFF
        v &= 0xFF
        if 0xD000 <= a <= 0xDFFF and self.io_visible():
            self.io_write(a, v)
            return
        if a == 1:
            self.port = v
            return
        self.mem[a] = v

    # ---- I/O
    def io_read(self, a):
        if a < 0xD400:
            r = a & 0x3F
            if r == 0x11:
                return (self.vic[0x11] & 0x7F) | ((self.raster & 0x100) >> 1)
            if r == 0x12:
                return self.raster & 0xFF
            if r == 0x19:
                return self.vic[0x19] | (0x80 if self.vic[0x19] & self.vic[0x1A] & 0x0F else 0) | 0x70
            if r >= 0x2F:
                return 0xFF
            return self.vic[r]
        if a < 0xD800:
            return 0
        if a < 0xDC00:
            return self.color[a & 0x3FF] | 0xF0
        if a < 0xDD00:
            r = a & 0x0F
            if r == 0:   # port A: keyboard columns out, joystick 2 in
                return self.cia1[0] & ~self.joy & 0xFF
            if r == 1:   # port B: keyboard rows
                cols = ~self.cia1[0] & 0xFF
                rows = 0xFF
                for k in self.keys:
                    col, row = KEYS[k]
                    if cols >> col & 1:
                        rows &= ~(1 << row)
                return rows & 0xFF
            if r == 0x0D:
                return 0
            return self.cia1[r]
        if a < 0xDE00:
            return self.cia2[a & 0x0F]
        return 0

    def io_write(self, a, v):
        if a < 0xD400:
            r = a & 0x3F
            if r == 0x19:
                self.vic[0x19] &= ~v & 0x0F
            elif r < 0x2F:
                self.vic[r] = v
        elif a < 0xD800:
            if 0xD400 <= a <= 0xD418:
                self.sid[a - 0xD400] = v
        elif a < 0xDC00:
            self.color[a & 0x3FF] = v & 0x0F
        elif a < 0xDD00:
            self.cia1[a & 0x0F] = v
        elif a < 0xDE00:
            self.cia2[a & 0x0F] = v

    def raster_compare(self):
        return self.vic[0x12] | ((self.vic[0x11] & 0x80) << 1)

    # ---- KERNAL traps (only while the KERNAL is banked in)
    def trap(self):
        pc = self.pc
        if pc in (0xEA31, 0xEA81):
            self.y, self.x, self.a = self.pull(), self.pull(), self.pull()
            self.set_flags(self.pull())
            self.pc = self.pull() | self.pull() << 8
            return True
        if pc == 0xFFE4:     # GETIN
            self.a = self.nz(self.key_queue.pop(0) if self.key_queue else 0)
            self.c = 0
        elif not (0xFF81 <= pc <= 0xFFF3):
            return False
        self.pc = ((self.pull() | self.pull() << 8) + 1) & 0xFFFF     # other KERNAL calls: plain RTS
        return True

    def irq(self):
        self.push(self.pc >> 8)
        self.push(self.pc & 0xFF)
        self.push(self.flags() & ~0x10)
        self.i = 1
        self.cycles += 7
        if self.kernal_visible():
            self.push(self.a)
            self.push(self.x)
            self.push(self.y)
            self.pc = self.mem[0x314] | self.mem[0x315] << 8
        else:
            self.pc = self.mem[0xFFFE] | self.mem[0xFFFF] << 8

    # ---- timing
    def run_frame(self):
        end = (self.frame + 1) * CYCLES_PER_LINE * LINES
        while self.cycles < end:
            if self.vic[0x19] & self.vic[0x1A] & 0x0F and not self.i:
                self.irq()
            if self.pc >= 0xE000 and self.kernal_visible() and self.trap():
                pass
            else:
                self.step()
            line = (self.cycles // CYCLES_PER_LINE) % LINES
            while line != self.raster:
                self.end_line()
                self.raster = (self.raster + 1) % LINES
                if self.raster == self.raster_compare():
                    self.vic[0x19] |= 1
                if self.badline():
                    self.cycles += 40
                line = (self.cycles // CYCLES_PER_LINE) % LINES
        self.frame += 1

    def badline(self):
        r = self.raster
        return 0x30 <= r <= 0xF7 and (r & 7) == (self.vic[0x11] & 7) and self.vic[0x11] & 0x10

    # ---- rendering
    def bank(self):
        return (3 - (self.cia2[0] & 3)) * 0x4000

    def vram(self, off):
        b = self.bank()
        if b in (0, 0x8000) and 0x1000 <= off < 0x2000:
            return 0                    # character ROM: not emulated
        return self.mem[b + off]

    def end_line(self):
        if not self.render:
            return
        y = self.raster - FIRST_LINE
        if not 0 <= y < IMG_H:
            return
        v = self.vic
        border = v[0x20] & 15
        row = [border] * IMG_W
        fg = [False] * IMG_W
        d011, d016, d018 = v[0x11], v[0x16], v[0x18]
        rsel, csel = d011 & 8, d016 & 8
        top, bottom = (51, 251) if rsel else (55, 247)
        left, right = (32, 352) if csel else (39, 343)
        in_window = top <= self.raster < bottom and d011 & 0x10
        if in_window:
            self.draw_background(row, fg, d011, d016, d018)
            self.draw_sprites(row, fg)
            for x in range(0, left):
                row[x] = border
            for x in range(right, IMG_W):
                row[x] = border
        self.image[y] = row

    def draw_background(self, row, fg, d011, d016, d018):
        v = self.vic
        bg = [v[0x21] & 15, v[0x22] & 15, v[0x23] & 15]
        for x in range(32, 352):
            row[x] = bg[0]
        dy = self.raster - 48 - (d011 & 7)
        if not 0 <= dy < 200:
            return
        crow, py = dy // 8, dy % 8
        screen = (d018 >> 4) * 0x400
        xs = d016 & 7
        bmm, mcm, ecm = d011 & 0x20, d016 & 0x10, d011 & 0x40
        chars = (d018 & 0x0E) * 0x400
        bitmap = (d018 & 0x08) * 0x400
        for col in range(40):
            cell = crow * 40 + col
            sc = self.vram(screen + cell)
            cc = self.color[cell]
            x0 = 32 + col * 8 + xs
            if bmm:
                bits = self.vram(bitmap + cell * 8 + py)
                if mcm:
                    cols = (bg[0], sc >> 4, sc & 15, cc)
                    for p in range(4):
                        c = bits >> (6 - 2 * p) & 3
                        for q in (0, 1):
                            self._px(row, fg, x0 + 2 * p + q, cols[c], c >= 2)
                else:
                    for p in range(8):
                        on = bits >> (7 - p) & 1
                        self._px(row, fg, x0 + p, (sc >> 4) if on else (sc & 15), on)
                continue
            if ecm:
                bits = self.vram(chars + (sc & 0x3F) * 8 + py)
                back = (v[0x21 + (sc >> 6)]) & 15
                for p in range(8):
                    on = bits >> (7 - p) & 1
                    self._px(row, fg, x0 + p, cc if on else back, on)
                continue
            bits = self.vram(chars + sc * 8 + py)
            if mcm and cc & 8:
                cols = (bg[0], bg[1], bg[2], cc & 7)
                for p in range(4):
                    c = bits >> (6 - 2 * p) & 3
                    for q in (0, 1):
                        self._px(row, fg, x0 + 2 * p + q, cols[c], c >= 2)
            else:
                for p in range(8):
                    on = bits >> (7 - p) & 1
                    self._px(row, fg, x0 + p, cc if on else bg[0], on)

    @staticmethod
    def _px(row, fg, x, c, on):
        if x < IMG_W:
            row[x] = c
            fg[x] = bool(on)

    def draw_sprites(self, row, fg):
        v = self.vic
        screen = (v[0x18] >> 4) * 0x400
        for s in range(7, -1, -1):
            if not v[0x15] >> s & 1:
                continue
            sy = v[1 + 2 * s]
            yexp = v[0x17] >> s & 1
            line = self.raster - sy - 1
            if line < 0:
                line += LINES
            if not 0 <= line < (42 if yexp else 21):
                continue
            if yexp:
                line //= 2
            sx = v[2 * s] | ((v[0x10] >> s & 1) << 8)
            ptr = self.vram(screen + 0x3F8 + s)
            data = [self.vram(ptr * 64 + line * 3 + i) for i in range(3)]
            bits = data[0] << 16 | data[1] << 8 | data[2]
            xexp = v[0x1D] >> s & 1
            behind = v[0x1B] >> s & 1
            col = v[0x27 + s] & 15
            mc = v[0x1C] >> s & 1
            w = 2 if xexp else 1
            x = sx - SPRITE_X0
            if mc:
                cols = (None, v[0x25] & 15, col, v[0x26] & 15)
                for p in range(12):
                    c = cols[bits >> (22 - 2 * p) & 3]
                    if c is not None:
                        for q in range(2 * w):
                            self._spx(row, fg, x + p * 2 * w + q, c, behind)
            else:
                for p in range(24):
                    if bits >> (23 - p) & 1:
                        for q in range(w):
                            self._spx(row, fg, x + p * w + q, col, behind)

    @staticmethod
    def _spx(row, fg, x, c, behind):
        if 0 <= x < IMG_W and not (behind and fg[x]):
            row[x] = c


def write_png(path, rows, scale=1):
    rows = [[c for c in r for _ in range(scale)] for r in rows for _ in range(scale)]
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    plte = b"".join(bytes(rgb) for rgb in PALETTE)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", len(rows[0]), len(rows), 8, 3, 0, 0, 0))
    png += chunk(b"PLTE", plte) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def load_prg(m, data):
    load = data[0] | data[1] << 8
    m.mem[load:load + len(data) - 2] = data[2:]
    if load == 0x0801:   # BASIC stub: find the SYS number
        text = bytes(data[2:60])
        i = text.find(b"\x9e")
        if i >= 0:
            digits = b""
            for ch in text[i + 1:]:
                if 0x30 <= ch <= 0x39:
                    digits += bytes([ch])
                elif digits:
                    break
            return int(digits)
    return load


def parse_input(events):
    out = []
    for ev in events:
        joy = 0
        for tok in filter(None, ev.get("joy", "").split("+")):
            joy |= JOY_BITS[tok]
        keys = [k for k in ev.get("keys", "").split("+") if k]
        poke = None
        if "poke" in ev:
            addr, data = ev["poke"].split(":")
            poke = (int(addr, 16), bytes(int(b, 16) for b in data.split(",")))
        out.append((ev["frame"], ev.get("hold", 2), joy, keys, poke))
    return out


def run(prg_path, frames, shots, events, entry=None):
    m = C64()
    start = load_prg(m, prg_path.read_bytes())
    m.pc = entry if entry is not None else start
    m.sp = 0xF6
    m.mem[0x314], m.mem[0x315] = 0x31, 0xEA
    m.i = 0
    script = parse_input(events)
    out = {}
    for f in range(frames):
        m.joy = 0
        m.keys = set()
        for at, hold, joy, keys, poke in script:
            if at <= f < at + hold:
                m.joy |= joy
                m.keys.update(keys)
            if f == at:
                m.key_queue += [PETSCII[k] for k in keys if k in PETSCII]
                if poke:
                    m.mem[poke[0]:poke[0] + len(poke[1])] = poke[1]
        m.render = f in shots
        if m.render:
            m.image = [[0] * IMG_W for _ in range(IMG_H)]
        try:
            m.run_frame()
        except RuntimeError as e:
            raise RuntimeError(f"frame {f}: {e}") from None
        if m.render:
            out[f] = m.image
    return m, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg", type=pathlib.Path)
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--shot", default="", help="comma-separated frame numbers to screenshot (default: last frame)")
    ap.add_argument("--input", type=pathlib.Path, help="JSON input script")
    ap.add_argument("--entry", type=lambda s: int(s, 16), help="start address in hex (default: SYS address)")
    ap.add_argument("--scale", type=int, default=1, help="enlarge screenshots by this factor")
    ap.add_argument("--dump", action="append", default=[], help="hexdump addr:len (hex) after the run")
    args = ap.parse_args()
    shots = {int(s) for s in args.shot.split(",") if s} or {args.frames - 1}
    events = json.loads(args.input.read_text()) if args.input else []
    m, images = run(args.prg, args.frames, shots, events, args.entry)
    print(f"ran {args.frames} frames, PC=${m.pc:04X}")
    for f, img in sorted(images.items()):
        path = args.prg.with_name(f"{args.prg.stem}_f{f}.png")
        write_png(path, img, args.scale)
        print(f"wrote {path.name}")
    for d in args.dump:
        a, n = (int(p, 16) for p in d.split(":"))
        for i in range(0, n, 16):
            print(f"{a + i:04X}: " + " ".join(f"{m.mem[a + i + j]:02X}" for j in range(min(16, n - i))))


if __name__ == "__main__":
    main()
