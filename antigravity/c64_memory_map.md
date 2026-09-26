# Commodore 64 Fast Reference Memory Map & Architecture

| Address Range | Size | Description | Typical Use / Contents |
| :--- | :--- | :--- | :--- |
| `$0000 - $0001` | 2 B | 6510 On-Chip I/O Port | `$00`: DDR, `$01`: Memory banking control (`$37`, `$36`, `$35`, `$34`) |
| `$0002 - $00FF` | 254 B | Zero Page | Fast 1-byte variables. `$FB-$FE` safe pointers. `$02-$7F` free when Kernal disabled |
| `$0100 - $01FF` | 256 B | Hardware Stack | 6510 CPU Stack (indexed by S register) |
| `$0200 - $02FF` | 256 B | Kernal Buffers | Keyboard queue, cassette buffer, RS-232, screen editor lines |
| `$0300 - $03FF` | 256 B | OS Vectors & Storage | IRQ (`$0314/$0315`), BRK (`$0316/$0317`), NMI (`$0318/$0319`) |
| `$0400 - $07E7` | 1000 B | Screen Matrix RAM (Default) | 40 columns x 25 rows of screen character codes |
| `$07F8 - $07FF` | 8 B | Sprite Data Pointers | Pointers (Block Address = value x 64) for Sprites 0 through 7 |
| `$0801 - $9FFF` | ~38 KB | BASIC Program Area | Free RAM for programs launched via BASIC SYS (`$0801` launcher stub) |
| `$A000 - $BFFF` | 8 KB | BASIC ROM | Mapped to RAM when 6510 port `$01` bit 0 is cleared (`$36` / `$35`) |
| `$C000 - $CFFF` | 4 KB | Free RAM Area | Common for custom ML routines, SID music drivers, SFX engines, buffers |
| `$D000 - $D02E` | 47 B | VIC-II Video Chip | Sprites, raster interrupts, colors, scroll, display modes |
| `$D02F - $D3FF` | 977 B | VIC-II Mirror Space | Mirrors of VIC-II registers |
| `$D400 - $D41C` | 29 B | SID Sound Synthesizer | 3 Voices, Waveforms, ADSR, Filter, Master Volume |
| `$D41D - $D7FF` | 995 B | SID Mirror Space | Mirrors of SID registers |
| `$D800 - $DBE7` | 1000 B | Color RAM | Lower nibbles (0-15) define foreground color per screen character |
| `$DC00 - $DC0F` | 16 B | CIA 1 | Joystick 2 / Keyboard matrix rows (`$DC00`), Joystick 1 / Cols (`$DC01`), Timers |
| `$DD00 - $DD0F` | 16 B | CIA 2 | Serial IEC bus, RS-232, VIC-II 16 KB Bank selection (`$DD00` bits 0-1) |
| `$E000 - $FFFF` | 8 KB | Kernal ROM | Standard Commodore OS Routines & Hardware Vectors (RAM when `$35`/`$34`) |

---

## VIC-II 16 KB Memory Banks (`$DD00` Bits 0-1)

| Bits | Bank | Memory Range | Characteristics |
| :---: | :---: | :---: | :--- |
| `%11` | Bank 0 | `$0000 - $3FFF` | Default bank. Char ROM shadowed at `$1000-$1FFF` |
| `%10` | Bank 1 | `$4000 - $7FFF` | Pure RAM bank. Highly recommended for custom graphics & double buffering |
| `%01` | Bank 2 | `$8000 - $BFFF` | Char ROM shadowed at `$9000-$9FFF` |
| `%00` | Bank 3 | `$C000 - $FFFF` | Pure RAM bank (Kernal ROM overhead only visible to CPU, not VIC-II) |

---

## 6510 CPU Memory Configurations (`$0001` Port Register)

| Value | BASIC ($A000-$BFFF) | I/O ($D000-$DFFF) | Kernal ($E000-$FFFF) | Available RAM |
| :---: | :---: | :---: | :---: | :---: |
| `$37` | ROM | I/O | ROM | 38 KB (Default) |
| `$36` | **RAM** | I/O | ROM | 52 KB |
| `$35` | **RAM** | **I/O** | **RAM** | **60 KB (Recommended for ML)** |
| `$34` | **RAM** | **RAM** | **RAM** | **64 KB (Pure RAM)** |
