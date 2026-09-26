# Commodore 64 Development Rules for Google Antigravity Agents

When generating software for the Commodore 64 (MOS 6510 CPU / VIC-II / SID) on the **Commodore 64 Ultimate (C64U)**, follow these strict architectural and coding rules:

---

## 1. CPU & Instruction Set (MOS 6510 / 6502)
* **Architecture**: MOS 6510 (100% binary instruction compatible with MOS 6502).
* **Clock Speeds**:
  * **PAL**: 0.985248 MHz (63 cycles per raster scanline, 312 lines, 50.0 Hz).
  * **NTSC**: 1.022727 MHz (65 cycles per raster scanline, 263 lines, 59.8 Hz).
* **Cycle Rules**: Every clock cycle matters.
  * Branch instructions (`bne`, `beq`, `bcc`, `bcs`, etc.) take **2 cycles** if not taken, **3 cycles** if taken on the same page, and **4 cycles** if crossing a page boundary. Time-critical raster loops must be aligned with `.align $100` to prevent page-crossing cycle penalties.
  * Self-modifying code is standard demoscene practice on 6502 to avoid indexed addressing cycle overhead.
* **Basic Bootstrap Launcher**:
  * Always include `BasicUpstart2(entry_point)` and target `* = $0810` for KickAssembler unless creating a dedicated Cartridge image (`.crt`) or relocatable driver.

---

## 2. Memory Organization & Banking
* **6510 On-Chip Port Register (`$0001`)**:
  * `$37` (`%00110111`): BASIC ROM + Kernal ROM + I/O enabled (Default, ~38 KB RAM).
  * `$36` (`%00110110`): BASIC disabled (RAM mapped), Kernal + I/O enabled (~52 KB RAM).
  * `$35` (`%00110101`): All ROMs disabled (RAM mapped), I/O enabled at `$D000-$DFFF` (~60 KB RAM). **Recommended for full-scale ML games and demoscene productions.**
  * `$34` (`%00110100`): Full 64 KB pure RAM (ROMs and I/O replaced by RAM).
* **Zero Page (`$0000 - $00FF`)**:
  * `$00` / `$01`: 6510 CPU Direction & Port registers.
  * `$FB - $FE`: The two standard 16-bit indirect zero-page pointer pairs (`($FB),Y` and `($FD),Y`). **100% safe to use at all times**, even with Kernal active.
  * `$02 - $7F`: Completely free for application zero-page pointers and counters when BASIC is bypassed or banked out.
* **Stack**: `$0100 - $01FF`.
* **Kernal Vectors**: IRQ (`$0314/$0315`), BRK (`$0316/$0317`), NMI (`$0318/$0319`).
* **Default Screen RAM**: `$0400 - $07E7` (40 columns x 25 rows = 1000 bytes).
* **Color RAM**: `$D800 - $DBE7` (Nibbles only: lower 4 bits define color 0-15).
* **CIA 1 (`$DC00 - $DC0F`)**: Joystick 2 / Keyboard rows (`$DC00`), Joystick 1 / Keyboard columns (`$DC01`), ICR (`$DC0D`).
* **CIA 2 (`$DD00 - $DD0F`)**: VIC-II 16 KB Bank selection (`$DD00` bits 0-1: `3`=Bank 0, `2`=Bank 1, `1`=Bank 2, `0`=Bank 3). Always mask bits 2-7 when altering bank!

---

## 3. Hardware Video (VIC-II MOS 6569/6567)
* **Display Coordinates**: Visible screen area is 320x200 pixels.
* **Screen Colors (0-15)**:
  `0`=Black, `1`=White, `2`=Red, `3`=Cyan, `4`=Purple, `5`=Green, `6`=Blue, `7`=Yellow, `8`=Orange, `9`=Brown, `10`=Light Red, `11`=Dark Grey, `12`=Grey, `13`=Light Green, `14`=Light Blue, `15`=Light Grey.
* **Border Color**: `$D020`. **Background Color 0**: `$D021`.
* **Raster Register**: `$D012` (Low 8 bits) and `$D011` bit 7 (High 9th bit).
* **Bad Lines**:
  * In character display mode, every 8th raster line between `$30` and `$F7` (where `$D012 & 7 == $D011 & 7`) causes the VIC-II to halt the CPU for 40-43 cycles to fetch character pointers.
  * Never place cycle-sensitive code on Bad Lines without cycle compensation.
* **Interrupt Acknowledgment**: Always acknowledge VIC-II IRQ by writing to `$D019` (`asl $d019` or `sta $d019`).
* **Hardware Sprites (0-7)**:
  * 24x21 pixels per sprite (64 bytes each, 63 bytes data + 1 byte padding).
  * Sprite pointers are located at the end of active Screen RAM: `$07F8` through `$07FF` (Pointer value = `Address / 64`).
  * Multicolor Sprites (`$D01C`): Shared Color 0 (`$D025`), Shared Color 1 (`$D026`), Individual Color (`$D027-$D02E`).

---

## 4. Hardware Audio (MOS 6581/8580 SID)
* **3 Hardware Voices**: Voice 1 (`$D400-$D406`), Voice 2 (`$D407-$D40D`), Voice 3 (`$D40E-$D414`).
* **Master Volume**: `$D418` (Bits 0-3: 0 to 15 level).
* **Waveforms (`$D404 / $D40B / $D412`)**:
  * `$11` = Triangle + Gate ON (Mellow bass, flutes).
  * `$21` = Sawtooth + Gate ON (Aggressive brass, lead synths, strings).
  * `$41` = Pulse/Square + Gate ON (8-bit classic tones, hollow reeds).
  * `$81` = White Noise + Gate ON (Percussion, snares, explosions, wind).
* **12-Bit Pulse Width Modulation**:
  * Duty Cycle = `(PW / 4095) * 100%`. Modulate PW registers at 50Hz for rich analog chorus/flanging.
* **11-Bit Multi-Mode Resonant Filter**:
  * Cutoff: `$D415` (bits 0-2) and `$D416` (bits 3-10).
  * Resonance & Voice Routing: `$D417` (Bits 4-7: Resonance 0-15; Bits 0-3: Voice 1-3 routing).
  * Filter Mode: `$D418` (Bit 4: Low-Pass, Bit 5: Band-Pass, Bit 6: High-Pass, Bit 7: 3-Off).

---

## 5. Development Cycle & Tooling
* **Language Selection**:
  * **KickAssembler Assembly (`.asm`)**: **Preferred**. Essential for cycle-exact raster splits, multicolor graphics, full SID music, and sprite multiplexing.
  * **Python (`.py`)**: Supported via `c64u_bridge.transpiler`. Use for rapid gameplay prototyping, text logic, and hybrid scripts with `asm(""" ... """)`.
* **KickAssembler Syntax Rules**:
  * Constants used in immediate instructions (e.g. `cpx #seq_len`) must be defined **before** their appearance in the code.
* **Non-Invasive Verification**:
  * Use `c64_inspect_screen` to verify text output and UI layouts without looking at the physical monitor.
  * Use `c64_read_memory` to check internal variable states and memory buffers.
