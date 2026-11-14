#!/usr/bin/env python3
"""
Game check: run a C64 game headless (tools/c64sim) and look for engine bugs that
are easy to make and hard to spot, with the frame they first happen:

  MODE FIGHT   main code switches bitmap/text mode ($D011 bit 5) but a raster IRQ
               keeps writing the other mode back, frame after frame. Typical cause:
               the game's raster IRQ was left running when a title / briefing /
               game-over screen was shown (the screen turns into garbage).
  STUCK SOUND  a SID voice has its gate open with a sustain level and nothing
               touches it for STUCK_FRAMES frames. Typical cause: a sound effect
               whose timer only counts down in the game loop, followed by a banner
               or wait-for-fire loop that never stops it.
  SCROLL JUMP  while scrolling (the axis moved 1-3 px the frame before), the fine
               scroll wraps (jumps by 4 or more) while the screen
               neither flipped to another page ($D018) nor got rewritten (fewer
               than 200 screen writes in this and the previous frame). Typical
               cause: fine scroll applied before the coarse-shifted screen is
               ready, so the picture jumps back and forth by a character.

Input: an input script as for c64sim (--input, JSON list of {"frame", "joy",
"keys", "hold", "poke"}). Without one it presses fire at frames 60 and 120 (a
title screen and one briefing / menu), then steers in all eight directions, 40
frames each. Write a script when your game needs a different start sequence,
and add pokes to reach rare situations (game over, level complete).

  python game_check.py game.prg --frames 1500
  python game_check.py game.prg --input play.json

Writes <prg>_check.txt next to the PRG and prints a summary. Exit code 1 when
something was found. The simulator is instruction-level: confirm findings on
VICE or the real machine. See .agents/skills/c64-development/references/
game_engine_pitfalls.md for the fixes.
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "c64sim"))
import c64sim  # noqa: E402
from c64sim import C64, CYCLES_PER_LINE, LINES, load_prg, parse_input  # noqa: E402

STUCK_FRAMES = 100        # 2 seconds at 50 Hz
FIGHT_FRAMES = 25         # half a second of the IRQ undoing the main code's mode
SCREEN_WRITES = 200       # a coarse scroll rewrites (most of) the screen


def default_script(frames):
    J = c64sim.JOY_BITS
    out = [{"frame": f, "joy": "fire", "hold": 4} for f in (60, 120)]
    dirs = ["right", "down+right", "down", "down+left", "left", "up+left", "up", "up+right"]
    f, k = 180, 0
    while f < frames:
        out.append({"frame": f, "joy": dirs[k % 8], "hold": 40})
        f += 40
        k += 1
    return out


class Checked(C64):
    def __init__(self):
        super().__init__()
        self.render = False
        self.irq_depth = 0
        self.findings = []
        self.seen = set()
        # mode fight
        self.main_bmm = None          # bitmap bit last written by main code
        self.main_bmm_frame = 0
        self.irq_undo = 0             # consecutive frames the IRQ wrote the other mode
        self.irq_undo_frame = False
        # sound
        self.voice_write = [0, 0, 0]
        self.sid_regs = bytearray(0x20)
        # scroll
        self.screen_writes = 0
        self.prev_writes = 0
        self.prev_state = None

    # ---- interrupt context
    def irq(self):
        super().irq()
        self.irq_depth += 1

    def trap(self):
        pc = self.pc
        done = super().trap()
        if done and pc in (0xEA31, 0xEA81) and self.irq_depth:
            self.irq_depth -= 1
        return done

    def step(self):
        op = self.mem[self.pc]
        super().step()
        if op == 0x40 and self.irq_depth:       # RTI
            self.irq_depth -= 1

    # ---- writes
    def io_write(self, a, v):
        r = a & 0x3F
        if 0xD000 <= a < 0xD400 and r == 0x11:
            bmm = (v >> 5) & 1
            if self.irq_depth:
                if self.main_bmm is not None and bmm != self.main_bmm:
                    self.irq_undo_frame = True
            else:
                self.main_bmm = bmm
                self.main_bmm_frame = self.frame
                self.irq_undo = 0
        if 0xD400 <= a <= 0xD41F:
            self.sid_regs[a - 0xD400] = v
            if a <= 0xD414:
                self.voice_write[(a - 0xD400) // 7] = self.frame
        super().io_write(a, v)

    def wr(self, a, v):
        a &= 0xFFFF
        base = self.bank() + (self.vic[0x18] >> 4) * 0x400
        if base <= a < base + 1000:
            self.screen_writes += 1
        super().wr(a, v)

    def report(self, kind, text):
        if kind in self.seen:
            return
        self.seen.add(kind)
        self.findings.append(f"frame {self.frame}: {kind}: {text}")

    # ---- per-frame checks
    def end_of_frame(self, prev):
        # mode fight
        if self.irq_undo_frame:
            self.irq_undo += 1
        else:
            self.irq_undo = 0
        self.irq_undo_frame = False
        if self.irq_undo >= FIGHT_FRAMES:
            mode = "bitmap" if self.main_bmm else "text"
            self.report("MODE FIGHT", f"main code set {mode} mode (frame {self.main_bmm_frame}) but a raster "
                        f"IRQ has switched it back for {self.irq_undo} frames: switch the IRQ off "
                        "($D01A = 0) before showing this screen")
        # stuck sound
        for vce in range(3):
            ctrl = self.sid_regs[vce * 7 + 4]
            sustain = self.sid_regs[vce * 7 + 6] >> 4
            if ctrl & 1 and sustain and self.frame - self.voice_write[vce] >= STUCK_FRAMES:
                self.report(f"STUCK SOUND voice {vce + 1}", f"gate on (waveform ${ctrl:02X}, sustain {sustain}) "
                            f"and untouched for {self.frame - self.voice_write[vce]} frames: keep the sound "
                            "effect running or silence the SID before wait loops / banners")
        # scroll jump (text modes, while actually scrolling: the axis moved by
        # 1-3 px in the frame before, so jumps on respawns / screen changes don't count)
        cur = (self.vic[0x16] & 7, self.vic[0x11] & 7, self.vic[0x18], (self.vic[0x11] >> 5) & 1)
        older = self.prev_state
        self.prev_state = prev
        if prev is not None and older is not None and not cur[3] and not prev[3]:
            jump = 0
            for ax in (0, 1):
                step = abs(prev[ax] - older[ax])
                if 1 <= step <= 3 and abs(cur[ax] - prev[ax]) >= 4:
                    jump = max(jump, abs(cur[ax] - prev[ax]))
            if jump and cur[2] == prev[2] and self.screen_writes + self.prev_writes < SCREEN_WRITES:
                self.report("SCROLL JUMP", f"fine scroll jumped by {jump} px but the screen did not move "
                            "(no page flip, few screen writes): apply fine scroll together with the "
                            "coarse-shifted screen")
        self.prev_writes = self.screen_writes
        self.screen_writes = 0
        return cur


def run(prg, frames, events):
    m = Checked()
    start = load_prg(m, prg.read_bytes())
    m.pc, m.sp, m.i = start, 0xF6, 0
    m.mem[0x314], m.mem[0x315] = 0x31, 0xEA
    script = parse_input(events)
    prev = None
    for f in range(frames):
        m.joy, m.keys = 0, set()
        for at, hold, joy, keys, poke in script:
            if at <= f < at + hold:
                m.joy |= joy
                m.keys.update(keys)
            if f == at:
                m.key_queue += [c64sim.PETSCII[k] for k in keys if k in c64sim.PETSCII]
                if poke:
                    m.mem[poke[0]:poke[0] + len(poke[1])] = poke[1]
        try:
            m.run_frame()
        except RuntimeError as e:
            m.findings.append(f"frame {f}: CRASH: {e}")
            break
        prev = m.end_of_frame(prev)
    return m.findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prg", type=pathlib.Path)
    ap.add_argument("--frames", type=int, default=1500)
    ap.add_argument("--input", type=pathlib.Path, help="JSON input script (as for c64sim)")
    args = ap.parse_args()
    prg = args.prg.resolve()
    events = json.loads(args.input.read_text()) if args.input else default_script(args.frames)
    findings = run(prg, args.frames, events)
    out = prg.with_name(f"{prg.stem}_check.txt")
    lines = [f"Game check: {prg.name}, {args.frames} frames"]
    lines += findings or ["no problems found"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for line in lines:
        print(line)
    print(f"wrote {out.name}")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()
