# Commodore 64 Development Rules for Google Antigravity Agents

When generating software for the Commodore 64 (MOS 6510 CPU / VIC-II / SID) on the **Commodore 64 Ultimate (C64U)**, follow these strict architectural and coding rules:

## 1. CPU & Instruction Set
* **Target Architecture**: MOS 6510 (100% compatible with MOS 6502).
* **Clock Speed**: ~0.985 MHz (PAL) / ~1.023 MHz (NTSC).
* **Cycles Matter**: Every cycle counts during raster splits or time-critical loops. Branch instructions take 2 cycles not taken, 3 cycles if taken on same page, 4 cycles if crossing page boundaries.
* **Basic Bootstrap**: Always include standard BASIC SYS launcher stub (e.g. `10 SYS 2064` / `$0810`) unless creating a dedicated Cartridge image (`.crt`).

## 2. Memory Organization & Zero Page
* **Zero Page ($0000 - $00FF)**: 
  * `$00` / `$01`: 6510 On-Chip I/O Port & Direction register (Bank switching: `$37` = BASIC + Kernal + I/O enabled; `$35` = All RAM except I/O; `$34` = All 64K RAM).
  * `$02 - $7F`: Free for user zero-page pointers when Kernal/BASIC are not actively utilized.
  * `$FB - $FE`: Safest general-purpose zero page pointers when Kernal is running.
* **Stack**: `$0100 - $01FF`.
* **Screen RAM**: Default at `$0400 - $07E7` (1000 bytes, 40 columns x 25 rows).
* **BASIC Program Area**: `$0801 - $9FFF`.
* **VIC-II Registers**: `$D000 - $D02E`.
* **SID Registers**: `$D400 - $D41C`.
* **Color RAM**: `$D800 - $DBE7` (Nibbles 0-15 only).
* **CIA 1 (Keyboard/Joysticks/Timer)**: `$DC00 - $DC0F`.
* **CIA 2 (Serial/VIC Banking/NMI)**: `$DD00 - $DD0F`.

## 3. Hardware Video (VIC-II)
* **Screen Coordinates**: Visible area is 320x200 pixels.
* **Border Color**: `$D020` (Values: 0=Black, 1=White, 2=Red, 3=Cyan, 4=Purple, 5=Green, 6=Blue, 7=Yellow, 8=Orange, 9=Brown, 10=Light Red, 11=Dark Grey, 12=Grey, 13=Light Green, 14=Light Blue, 15=Light Grey).
* **Background Color**: `$D021`.
* **Raster Line Register**: `$D012` (Low 8 bits) and `$D011` bit 7 (High 9th bit).
* **Raster Interrupts**: Always acknowledge IRQ by writing to `$D019` (`asl $d019` or `sta $d019`).

## 4. Hardware Audio (SID MOS 6581/8580)
* **Master Volume**: `$D418` (Bits 0-3: 0 to 15 volume level).
* **Voice 1**: Freq Low (`$D400`), Freq High (`$D401`), Pulse Width (`$D402-$D403`), Control/Waveform (`$D404`), Attack/Decay (`$D405`), Sustain/Release (`$D406`).
* **Waveforms**: `$11` = Triangle + Gate, `$21` = Sawtooth + Gate, `$41` = Pulse + Gate, `$81` = Noise + Gate.

## 5. Development Cycle with Antigravity
1. **Write Code**: Save file to project workspace as `.asm` (KickAssembler format preferred).
2. **Build and Deploy**: Call `c64_build_and_run` to assemble and push the binary to physical C64U via DMA.
3. **Inspect Output**: Call `c64_inspect_screen` or `c64_read_memory` to verify program behavior, check memory variables, or diagnose bugs without touching the physical hardware.
