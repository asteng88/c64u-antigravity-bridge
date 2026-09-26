# Python to MOS 6502 Transpiler Developer Reference

The `c64u-bridge` includes a dedicated AST transpiler (`c64u_bridge.transpiler`) that translates structured Python code into optimized KickAssembler / ACME 6502 assembly, with full BASIC bootstrap (`BasicUpstart2(start)`) and direct hardware memory access.

---

## 1. Supported Python Features & Syntax

### Variables & Constants
* **Constants**: Variables defined in ALL_CAPS assigned to literal integers become compile-time `.const` values (zero runtime RAM overhead).
* **Mutable Variables**: Lowercase variables are allocated as zero-initialized RAM bytes (`var_name: .byte $00`).
* **Hardware Constants**: All standard C64 constants are pre-loaded:
  * Colors: `COLOR_BLACK`, `COLOR_WHITE`, `COLOR_RED`, `COLOR_CYAN`, `COLOR_PURPLE`, `COLOR_GREEN`, `COLOR_BLUE`, `COLOR_YELLOW`, `COLOR_ORANGE`, `COLOR_BROWN`, `COLOR_LIGHT_RED`, `COLOR_DARK_GREY`, `COLOR_GREY`, `COLOR_LIGHT_GREEN`, `COLOR_LIGHT_BLUE`, `COLOR_LIGHT_GREY`
  * Memory: `SCREEN_RAM` (`$0400`), `COLOR_RAM` (`$D800`), `VIC_BORDER` (`$D020`), `VIC_BG` (`$D021`), `RASTER` (`$D012`)
  * SID: `SID_BASE` (`$D400`), `SID_VOLUME` (`$D418`), `SID_V1_FREQ_LO` (`$D400`), `SID_V1_FREQ_HI` (`$D401`), `SID_V1_CTRL` (`$D404`), `SID_V1_AD` (`$D405`), `SID_V1_SR` (`$D406`)
  * Kernal: `CHROUT` (`$FFD2`), `GETIN` (`$FFE4`), `PLOT` (`$FFF0`)

### Control Flow
* **Loops**:
  * `while condition:` and `while True:`
  * `for i in range(stop):`, `for i in range(start, stop):`, `for i in range(start, stop, step):`
  * `break` and `continue`
* **Conditionals**:
  * `if condition:`, `elif condition:`, `else:`
  * Operators: `==`, `!=`, `<`, `<=`, `>`, `>=`
* **Subroutines**:
  * `def my_routine(): ...` compiles directly to a named 6502 subroutine ending with `rts`.
  * Calling `my_routine()` compiles to `jsr my_routine`.

---

## 2. Hardware Intrinsics

| Python Intrinsic | Generated 6502 Code | Description |
| :--- | :--- | :--- |
| `poke(address, value)` | `lda #val / sta addr` | Write 8-bit value to memory address. |
| `peek(address)` | `lda addr` | Read 8-bit value from memory address. |
| `border_color(color)` | `lda #c / sta $D020` | Set VIC-II screen border color (0-15). |
| `background_color(color)` | `lda #c / sta $D021` | Set VIC-II background color 0 (0-15). |
| `wait_raster(line)` | `lda $D012 / cmp #line / bne ...` | Busy-wait loop for raster scanline. |
| `clear_screen(char, color)` | Unrolled loop clearing `$0400` & `$D800` | Clears all 1000 screen characters & colors. |
| `print_char(ch)` | `lda #ch / jsr $FFD2` | Output character via Kernal CHROUT. |
| `print_str("TEXT")` | Indexed string print loop via `$FFD2` | Embeds `.text "TEXT"` and prints to screen. |
| `delay(cycles)` | Double 8-bit decrement loop (`X/Y`) | Delays CPU execution. |
| `sid_tone(freq, wave, ad, sr)` | Configures SID `$D400-$D406` & `$D418` | Plays tone on SID Voice 1. |
| `asm("raw 6502 asm")` | Inlines raw 6502 instructions | Direct inline assembly inside Python! |

---

## 3. High-Performance Hybrid Example (Python + Inline ASM)

```python
# C64 Multi-Voice Sound & Colorful Graphics in Python
border_color(COLOR_BLACK)
background_color(COLOR_BLACK)
clear_screen(32, COLOR_WHITE)
print_str("ANTIGRAVITY PYTHON C64 SYNTH")

# Setup SID Voice 1 Lead tone
sid_tone(0x2258, 0x21, 0x09, 0xA0) # C-5 Sawtooth

# Inline assembly for cycle-exact raster color modulation:
asm("""
    ldx #0
raster_cycle:
    lda $d012
    sta $d020       // Border color mirrors raster beam
    inx
    cpx #250
    bne raster_cycle
""")

# Voice release
poke(0xD404, 0x20)
print_str("DONE!")
```

---

## 4. Architectural Decision: Python vs. Assembly

| Feature / Goal | Python Transpiled | Pure KickAssembler |
| :--- | :---: | :---: |
| **Rapid Prototyping** | **Best** (Immediate turnaround) | Good |
| **High-level Game Logic / State Machine** | **Best** (Readable Python syntax) | Good |
| **Math, Algorithms, Data Tables** | **Great** (Python loops and logic) | Excellent (`Math.*` in KickAss) |
| **0-Cycle Jitter Raster Interrupts** | Limited | **Essential** |
| **16+ Sprite Multiplexing Engine** | Limited | **Essential** |
| **Full 3-Voice Tracker Music / SFX Driver** | Limited | **Essential** |
| **Opening Borders / Side-border removal** | Not possible | **Essential** (Cycle-exact) |
