# Commodore 64 Fast Reference Memory Map

| Address Range | Size | Description | Typical Use |
| :--- | :--- | :--- | :--- |
| `$0000 - $00FF` | 256 B | Zero Page | Fast 1-byte addressed variables and pointers |
| `$0100 - $01FF` | 256 B | Hardware Stack | 6510 CPU Stack (pointed to by S register) |
| `$0200 - $03FF` | 512 B | OS / Kernal Vectors & Buffers | Keyboard buffer, IRQ vectors (`$0314/$0315`), NMI (`$0318`) |
| `$0400 - $07E7` | 1000 B | Screen Matrix RAM (Default) | 40 columns x 25 rows of screen character codes |
| `$07F8 - $07FF` | 8 B | Sprite Data Pointers | Pointers (val x 64) for Sprites 0 through 7 |
| `$0801 - $9FFF` | ~38 KB | BASIC Program Area | Free RAM for programs launched via BASIC SYS |
| `$A000 - $BFFF` | 8 KB | BASIC ROM | Mapped to RAM when 6510 port `$01` is banked |
| `$C000 - $CFFF` | 4 KB | Free RAM Area | Common for custom ML routines, music players, and data |
| `$D000 - $D3FF` | 1 KB | VIC-II Graphics Chip | Video registers (Sprites, Colors, Raster, Control) |
| `$D400 - $D7FF` | 1 KB | SID Sound Chip | 3 Voices, Filter, Envelope, Volume |
| `$D800 - $DBE7` | 1000 B | Color RAM | Nybbles (0-15) defining foreground color per screen cell |
| `$DC00 - $DCFF` | 256 B | CIA 1 | Keyboard matrix, Joysticks Port 1 & 2, Timers A/B |
| `$DD00 - $DDFF` | 256 B | CIA 2 | Serial IEC bus, RS-232, VIC-II 16KB Bank selection |
| `$E000 - $FFFF` | 8 KB | Kernal ROM | Standard Commodore OS Routines & Hardware Vectors |
