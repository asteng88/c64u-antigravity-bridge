# Commodore 64 Memory Architecture, Banking & Zero-Page Map

The MOS 6510 CPU features an on-chip 6-bit bidirectional I/O port located at memory addresses `$0000` (Data Direction Register) and `$0001` (Port Data Register). This port controls memory banking, allowing the C64 to map 64 KB of RAM, BASIC ROM, Kernal ROM, Character ROM, and Hardware I/O into the same 16-bit address space.

---

## 1. 6510 On-Chip Port Register `$0001` Banking Modes

The 3 low bits of address `$0001` control the active memory configuration:
* **Bit 0 (`LORAM`)**: 1 = BASIC ROM visible at `$A000-$BFFF`. 0 = RAM at `$A000-$BFFF`.
* **Bit 1 (`HIRAM`)**: 1 = Kernal ROM visible at `$E000-$FFFF`. 0 = RAM at `$E000-$FFFF`.
* **Bit 2 (`CHAREN`)**: 1 = I/O registers visible at `$D000-$DFFF`. 0 = Character ROM visible at `$D000-$DFFF`.

### Banking Modes Table

| `$0001` Value | Hex | `$A000-$BFFF` | `$D000-$DFFF` | `$E000-$FFFF` | Total Usable RAM | Best Used For |
| :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `%xxx10111` | **`$37`** | BASIC ROM | I/O Registers | Kernal ROM | ~38 KB | Default state. BASIC programs and simple SYS launchers. |
| `%xxx10110` | **`$36`** | **RAM** | I/O Registers | Kernal ROM | **~52 KB** | Machine language games needing Kernal routines (e.g., `CHROUT`, `GETIN`). |
| `%xxx10101` | **`$35`** | **RAM** | **I/O Registers** | **RAM** | **~60 KB** | Pure ML games and demos with custom IRQ handlers. (Highest recommended configuration). |
| `%xxx10100` | **`$34`** | **RAM** | **RAM** | **RAM** | **Full 64 KB**| Extreme demoscene demos, large graphics tables, or RAM under I/O. |
| `%xxx10011` | **`$33`** | BASIC ROM | Char ROM | Kernal ROM | ~38 KB | Character generation inspection. |

### Switching to 60 KB RAM Mode (`$35`):
```kickassembler
sei                 // Disable interrupts before swapping OS vectors!
lda #$35            // RAM under BASIC & Kernal, keep I/O accessible
sta $01
// Install custom hardware IRQ vector at $FFFE/$FFFF or maintain custom handler
cli
```

---

## 2. Zero Page Memory Map (`$0000 - $00FF`)

Zero Page allows ultra-fast, 1-byte addressing modes (e.g. `lda ($fb),y`). Every cycle counts!

| Address | Description | Safe for User Machine Code? |
| :--- | :--- | :--- |
| `$00` | 6510 Data Direction Register (Default `$2F`) | **NO** (Hardware config) |
| `$0001` | 6510 I/O Port / Bank switching (Default `$37`) | **Modify with care** |
| `$0002` | Unused by Kernal/BASIC | **YES** |
| `$0003 - $0068`| BASIC floating point & formula evaluators | **YES** (When BASIC is disabled) |
| `$0069 - $008F`| BASIC pointer and math scratchpad | **YES** (When BASIC is disabled) |
| `$0090` | Kernal I/O Status Byte (`ST`) | Safe if no IEC / serial I/O |
| `$00A0 - $00A2`| Jiffy Clock (Counts 1/60th seconds) | Overwritten if standard IRQ runs |
| `$00C5` | Current matrix key pressed | Overwritten by Kernal keyboard scan |
| `$00C6` | Number of characters in keyboard buffer | Overwritten by Kernal keyboard scan |
| `$00FB - $00FE`| **Free Kernal Zero Page Pointers** | **100% SAFE AT ALL TIMES** |

> **Best Practice**: Use `$FB, $FC` and `$FD, $FE` as your primary 16-bit indirect pointers (`($FB),Y`). When banking to `$35` (Kernal disabled), addresses `$02` through `$7F` are entirely yours!

---

## 3. High Memory Allocation & Recommended Layout

```text
$0000 +-----------------------------------+
      | Zero Page ($00-$FF)               |
$0100 +-----------------------------------+
      | 6510 Hardware Stack ($100-$1FF)   |
$0200 +-----------------------------------+
      | Kernal Vectors & Buffers          |
$0314 | - IRQ Vector ($0314/$0315)        |
$0318 | - NMI Vector ($0318/$0319)        |
$0400 +-----------------------------------+
      | Default Screen RAM (1000 bytes)   |
$07F8 | - Sprite 0-7 Pointers             |
$0801 +-----------------------------------+
      | BASIC SYS Bootstrap ($0801-$080F) |
$0810 | Machine Code / Engine Code        |
      | Game Logic, Math, Sound Drivers   |
      | ...                               |
$2000 +-----------------------------------+
      | Custom Character Set or Bitmaps   |
$4000 +-----------------------------------+
      | VIC Bank 1 / Graphics Buffers     |
$C000 +-----------------------------------+
      | Free RAM Area ($C000-$CFFF) 4 KB  |
      | Perfect for SID Tunes & SFX Engine|
$D000 +-----------------------------------+
      | VIC-II Registers ($D000-$D02E)    |
$D400 | SID Registers    ($D400-$D41C)    |
$D800 | Color RAM        ($D800-$DBE7)    |
$DC00 | CIA 1 (Joy 1/2, Keyboard, Timer)  |
$DD00 | CIA 2 (VIC Banking, Serial Bus)   |
$E000 +-----------------------------------+
      | Kernal ROM (or RAM in $35 mode)   |
$FFFF +-----------------------------------+
```

---

## 4. Hardware I/O Registers Map

### CIA 1 (`$DC00 - $DC0F`) — Input Devices & Timers
* **`$DC00` (Data Port A)**:
  * Read: Joystick Port 2 direction bits (`Bit 0=Up, Bit 1=Down, Bit 2=Left, Bit 3=Right, Bit 4=Fire`, Active LOW `0`).
  * Write: Select Keyboard matrix rows for scanning.
* **`$DC01` (Data Port B)**:
  * Read: Joystick Port 1 or Keyboard matrix columns.
* **`$DC0D` (Interrupt Control Register)**:
  * Reading acknowledges pending CIA interrupts.
  * Writing `$7F` disables all CIA interrupts (crucial when taking over the IRQ vector for custom raster routines).

### CIA 2 (`$DD00 - $DD0F`) — VIC Banking & Serial IEC
* **`$DD00` (Data Port A)**:
  * Bits 0-1: VIC-II 16 KB Bank selection (Inverted: `3`=Bank 0, `2`=Bank 1, `1`=Bank 2, `0`=Bank 3).

---

## 5. Kernal Standard API Routines (When `$37` or `$36` active)

| Address | Routine | Description | Input / Output |
| :---: | :--- | :--- | :--- |
| **`$FFD2`** | `CHROUT` | Outputs ASCII/PETSCII character to active device / screen. | `A` = Character code |
| **`$FFE4`** | `GETIN` | Reads one character from keyboard buffer without waiting. | `A` = Character (0 if buffer empty) |
| **`$FF9F`** | `SCNKEY` | Scans keyboard matrix. | Call once per frame if polling keyboard |
| **`$FFF0`** | `PLOT` | Set or get cursor position. | `Carry=0`: Set cursor (`X`=Row 0-24, `Y`=Col 0-39). `Carry=1`: Read cursor |
| **`$FF81`** | `CINT` | Initialize VIC-II screen editor and clear screen. | None |
| **`$FFE1`** | `STOP` | Checks if RUN/STOP key is pressed. | Zero flag set if pressed |
