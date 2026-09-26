---
name: c64-development
description: >-
  Authoritative engineering guide for developing high-performance Commodore 64 (MOS 6510/VIC-II/SID) software on the Commodore 64 Ultimate (C64U). Use whenever writing, optimizing, or debugging C64 code in KickAssembler assembly (preferred) or Python (via transpiler), creating colorful VIC-II graphics, programming SID chip multi-voice audio, sound effects, tracker music, or deploying binaries via DMA.
---

# Commodore 64 & C64U Development Mastery Skill

This skill equips Antigravity with complete architectural, graphics, audio, and toolchain knowledge to build state-of-the-art Commodore 64 software for physical hardware via the Commodore 64 Ultimate (C64U) REST API bridge.

---

## 1. Quick Navigation & References

Before writing code, consult the specialized reference manuals depending on the subsystem:

* **[VIC-II Graphics & Sprites Manual](./references/vic2_graphics.md)**: Display modes (Hires & Multicolor Bitmap, Multicolor Text, ECM), 8 hardware sprites, sprite multiplexing, cycle-exact raster IRQs, 0-cycle jitter Double-IRQ, Bad Lines calculations, border removal (opening top/bottom and side borders), and hardware fine scrolling.
* **[SID Audio & Music Synthesizer Manual](./references/sid_audio.md)**: 3-voice synthesis, chromatic frequency tables (C-0 to B-7), waveforms (Triangle, Sawtooth, Pulse, Noise), 12-bit Pulse Width Modulation (PWM), ADSR envelopes, 11-bit multi-mode resonant analog filter (LP, BP, HP, Notch), sound effects engines (SFX state machines), 50Hz frame-based tracker music architecture, and PSID file integration.
* **[Memory Map, Banking & Zero-Page Architecture](./references/c64_memory_and_banking.md)**: Complete Zero-Page map, 6510 Port `$0001` banking (`$37`, `$36`, `$35`, `$34`), CIA 1 & CIA 2 registers, Kernal vectors, safe scratchpad pointers (`$FB-$FE`).
* **[KickAssembler v5.x Practical Guide](./references/kickassembler_guide.md)**: Directives, `BasicUpstart2`, macros, pseudo-commands, compile-time trigonometric table scripting (`Math.sin()`), memory segments, and asset imports (`.import c64`, `.import binary`).
* **[Python-to-6502 Transpiler Guide](./references/python_transpiler_guide.md)**: Supported Python subset, intrinsics (`poke`, `peek`, `border_color`, `background_color`, `wait_raster`, `clear_screen`, `print_str`, `sid_tone`, `asm`), and hybrid Python + ASM techniques.

---

## 2. Choosing Language: Assembly vs. Python

* **KickAssembler Assembly (Preferred)**:
  * Mandatory for cycle-exact raster splits, raster bars, demoscene effects.
  * Mandatory for multi-voice SID tracker music, arpeggios, vibrato, and dynamic filter sweeps.
  * Mandatory for hardware sprite multiplexers and opening borders.
* **Python (via `c64u_bridge.transpiler`)**:
  * Excellent for rapid game logic prototyping, text adventure engines, math solvers, and simple screen animations.
  * Supports seamless inline assembly (`asm(""" ... """)`) for performance-critical bottlenecks.

---

## 3. Development Workflow with Antigravity Tools

### Step 1: Write Source Code
Create either a `.asm` (KickAssembler) or `.py` file in the workspace (e.g. `src/`, `examples/`, or `game_dev/`).
* Always start assembly programs with `BasicUpstart2(entry_point)` and `* = $0810` unless producing a cartridge or relocatable driver.
* Always acknowledge raster interrupts with `asl $d019` or `sta $d019`.

### Step 2: Build & Deploy via DMA
Use the MCP tool or CLI to compile and push the program directly into C64 RAM over the network:
* **MCP Tool**: Call `c64_build_and_run(source_path="path/to/source.asm")`.
* **CLI (PowerShell/Bash)**: `uv run --no-sync c64u-bridge run path/to/source.asm`

### Step 3: Inspect Screen & Diagnose
Verify output directly without disturbing the physical C64 display:
* Call `c64_inspect_screen()` to read the current 40x25 screen matrix and color RAM formatted in ANSI text.
* Call `c64_read_memory(address=0x0400, length=1000)` to examine raw screen or variable bytes.
* Call `c64_send_keys(keys="...")` to simulate keyboard input for interactive applications.
