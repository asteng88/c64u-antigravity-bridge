# KickAssembler v5.x Practical Reference & Idioms

KickAssembler is the premier cross-assembler for the Commodore 64, combining an ultra-fast 6502/6510 core with a rich Java-based scripting language.

---

## 1. Essential Directives & Setup

### BASIC Bootstrap Launcher
Instead of typing raw SYS line bytecodes manually, use the built-in macro:
```kickassembler
BasicUpstart2(entry_point)

* = $0810 "Main Application"
entry_point:
    sei
    // Program begins here
```

### Memory Segments & Addresses
* `* = $C000 "Music Driver"`: Sets the program counter to `$C000`.
* `.pseudopc $00FB { ... }`: Assembles code as if it runs at address `$FB` (e.g. Zero Page relocatable code), but packs it at the current binary location.

---

## 2. Data Directives

```kickassembler
.const BORDER_COLOR = $D020
.var frame_counter = 0

// Literal Bytes & Words
my_bytes:   .byte $01, $02, $03, $ff
my_words:   .word $0400, $d000, $d800

// Strings and Text
.encoding "screencode_upper"       // Screen code characters ($01=A, $02=B...)
screen_text: .text "COMMODORE 64 ULTIMATE"
             .byte 0                // Null terminator

.encoding "petscii_upper"          // PETSCII encoding ($41=A, $42=B...)
petscii_msg: .text "COMMODORE 64"

// Memory Blocks & Fill
zero_fill:  .fill 256, 0           // Fill 256 bytes with 0
gradient:   .fill 16, i            // Fill 16 bytes with values 0, 1, 2... 15
```

---

## 3. Mathematical Tables Generation in Assembly

You can compute sine tables, raster bounce curves, and circle paths directly at compile time using KickAssembler's built-in `Math` functions:

```kickassembler
// Generate a 256-byte sine table centered at 100 with amplitude 60:
sine_table:
    .for (var i = 0; i < 256; i++) {
        .var angle = i * 2 * Math.PI / 256
        .byte Math.round(100 + 60 * Math.sin(angle))
    }
```

---

## 4. Reusable Macros

```kickassembler
// 16-bit Pointer Assignment Macro
.macro SetPointer(source, dest) {
    lda #<source
    sta dest
    lda #>source
    sta dest + 1
}

// Border Flash Macro
.macro FlashBorder(color) {
    lda #color
    sta $d020
}

// Usage in code:
:SetPointer(my_data, $fb)
:FlashBorder(1)
```

---

## 5. Importing External Assets

### 1. PSID Music Files (`.sid`)
KickAssembler can parse High Voltage SID Collection (`.sid`) files directly and extract their load address, init address, and play address:
```kickassembler
.var music = LoadSid("music.sid")

* = music.location "Music"
.fill music.size, music.getData(i)

* = $0810 "Player"
BasicUpstart2(start)

start:
    lda #$00            // Default tune number 0
    jsr music.init      // Call SID initialization routine

irq:
    asl $d019
    jsr music.play      // Call SID 50Hz play routine on raster IRQ
    jmp $ea81
```

### 2. Koala Multicolor Bitmaps (`.prg` / `.koa`)
Koala format consists of:
* 2 bytes load address (usually `$6000`)
* 8000 bytes bitmap data
* 1000 bytes screen RAM colors
* 1000 bytes color RAM nibbles
* 1 byte background color
```kickassembler
* = $6000 "Koala Picture"
koala_pic:
    .import binary "mypic.koa"
```

---

## 6. Zero-Cycle Raster Loops & Optimization Rules

* **Branches across page boundaries**: Add 1 penalty cycle (4 cycles instead of 3). Ensure time-critical loops do not cross page boundaries (`.align $100`).
* **Self-Modifying Code**: For maximum rendering speed on 6502, patch operand addresses directly in memory:
```kickassembler
draw_tile:
    lda source_tile
tile_patch:
    sta $0400       // Modified at runtime: inc tile_patch+1 to advance address
```
