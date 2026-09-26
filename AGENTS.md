# Antigravity Workspace Guide: C64U Antigravity Bridge

Welcome to the **Commodore 64 Ultimate (C64U) Antigravity Bridge** repository. This project connects Google Antigravity agents directly to physical Commodore 64 Ultimate hardware via DMA over the local network, allowing seamless compilation, execution, debugging, screen inspection, and interactive hardware development.

---

## 1. Core Hardware Target
* **CPU**: MOS 6510 @ 0.985 MHz (PAL) / 1.023 MHz (NTSC). Full 6502 instruction set.
* **Video**: MOS 6569/6567 VIC-II (320x200 resolution, 16 colors, 8 hardware sprites, raster interrupts, hardware scrolling).
* **Audio**: MOS 6581/8580 SID (3 independent hardware voices, 4 waveforms, 12-bit pulse width modulation, 11-bit multi-mode resonant filter).
* **Hardware Bridge**: Ultimate-II+ / C64U REST API (`C64U_HOST:80`). Programs are transferred directly into C64 RAM via high-speed DMA.

---

## 2. Dedicated Agent Skill & Documentation
A comprehensive expert skill is installed in this workspace at:
* **Master Skill**: [`.agents/skills/c64-development/SKILL.md`](.agents/skills/c64-development/SKILL.md)
* **Specialized Reference Manuals**:
  * [VIC-II Graphics & Sprites](.agents/skills/c64-development/references/vic2_graphics.md)
  * [SID Audio & Music Synthesizer](.agents/skills/c64-development/references/sid_audio.md)
  * [Memory Architecture, Banking & Zero Page](.agents/skills/c64-development/references/c64_memory_and_banking.md)
  * [KickAssembler v5.x Guide & Directives](.agents/skills/c64-development/references/kickassembler_guide.md)
  * [Python-to-6502 Transpiler Developer Reference](.agents/skills/c64-development/references/python_transpiler_guide.md)
* **Production Templates**:
  * [Full 3-Voice SID Music & Tracker Engine](.agents/skills/c64-development/examples/sid_tracker_engine.asm)
  * [0-Cycle Jitter Stable Double-IRQ Template](.agents/skills/c64-development/examples/stable_double_irq.asm)

---

## 3. Language Strategies
1. **KickAssembler Assembly (`.asm`) — PREFERRED**:
   * Always preferred for maximum visual fidelity, demoscene effects (raster bars, plasma, FLI), cycle-exact raster splits, sprite multiplexing, and rich 3-voice SID music/sound engines.
   * Standard header: `BasicUpstart2(entry_point)` and `* = $0810`.
2. **Python (`.py`)**:
   * Parsed and translated by `c64u_bridge.transpiler` to 6502 assembly.
   * Ideal for rapid game prototypes, text engines, math routines, and quick screen tests.
   * Supports inline assembly via `asm(""" ... """)` for hardware synchronization.

---

## 4. MCP Tools & Verification Workflow
When interacting with the physical C64 hardware through Antigravity MCP:
* **`c64_build_and_run(source_path)`**: Assembles source code (.asm or .py) and DMA-pushes the binary to the C64U.
* **`c64_inspect_screen()`**: Reads current 40x25 screen matrix and color RAM, rendering ANSI text in the agent's context. Always inspect the screen after running to verify program behavior.
* **`c64_read_memory(address, length)`**: Non-invasively reads memory blocks to verify variables, flags, or buffer contents.
* **`c64_send_keys(keys)`**: Injects keystrokes into the C64 keyboard buffer for testing menus and interactive prompts.
