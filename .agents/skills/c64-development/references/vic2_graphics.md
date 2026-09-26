# The Definitive MOS 6567 / 6569 VIC-II Graphics Programming Guide

The VIC-II (MOS 6569 PAL / 6567 NTSC) is the video display processor of the Commodore 64. It manages the 40x25 character matrix, high-resolution and multicolor bitmaps, 8 hardware sprites, raster beam synchronization, and hardware scrolling.

---

## 1. Video Memory Organization & Banks

The VIC-II can directly address 16 KB of memory at any time. It determines its 16 KB active bank from **CIA 2 Port A (`$DD00`) bits 0 and 1**:

| `$DD00` Bits 1-0 | VIC-II Bank | Memory Range | Notes |
| :---: | :---: | :---: | :--- |
| **`%11` (`3`)** | Bank 0 | `$0000 - $3FFF` | Default bank. Character ROM shadowed at `$1000-$1FFF` (VIC sees ROM, CPU sees RAM unless mapped). |
| **`%10` (`2`)** | Bank 1 | `$4000 - $7FFF` | Pure RAM bank. Very popular for demoscene demos and games. |
| **`%01` (`1`)** | Bank 2 | `$8000 - $BFFF` | Character ROM shadowed at `$9000-$9FFF`. |
| **`%00` (`0`)** | Bank 3 | `$C000 - $FFFF` | Pure RAM bank (Kernal ROM overhead only affects CPU, not VIC-II). |

> **Crucial CIA2 Rule**: When writing to `$DD00`, preserve bits 2-7 (`ora #$03` / `and #...`) to avoid breaking serial bus communication!

### VIC-II Memory Setup Register (`$D018`)

Register `$D018` configures the relative offsets of **Screen RAM** and **Character/Bitmap RAM** within the active 16 KB bank:

$$\text{Screen RAM Address} = \text{VIC\_Bank\_Base} + (D018[7:4] \times 1024)$$
$$\text{Character/Bitmap Address} = \text{VIC\_Bank\_Base} + (D018[3:1] \times 2048)$$

* **Screen RAM Offsets** (bits 4-7):
  * `%0001` (`$1x`): `$0400` (Default)
  * `%0010` (`$2x`): `$0800`
  * `%0100` (`$4x`): `$1000`
  * `%1000` (`$8x`): `$2000`
  * `%1100` (`$Cx`): `$3000`
  * `%1101` (`$Dx`): `$3400`
* **Character ROM / Font Offsets** (bits 1-3):
  * `%0010` (`$x4`): `$1000` (Uppercase/graphics in Bank 0)
  * `%0011` (`$x6`): `$1800` (Lowercase in Bank 0)
  * `%1000` (`$x8`): `$2000` (Custom RAM character set)
* **Bitmap Mode Offset** (bit 3):
  * `0`: Bitmap at offset `$0000`
  * `1`: Bitmap at offset `$2000`

---

## 2. Display Modes & Registers

| Mode | `$D011` Bit 5 (BMM) | `$D011` Bit 6 (ECM) | `$D016` Bit 4 (MCM) | Resolution | Color Capabilities |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Standard Text** | 0 | 0 | 0 | 320x200 (40x25 chars) | 1 background color (`$D021`) + 1 foreground color per 8x8 cell (Color RAM `$D800`). |
| **Multicolor Text**| 0 | 0 | 1 | 160x200 (40x25 chars) | 4 colors per 4x8 cell: BG0 (`$D021`), BG1 (`$D022`), BG2 (`$D023`), Color RAM (bits 0-2). Color bit 3 selects multicolor vs hires character. |
| **Extended Color (ECM)**| 0 | 1 | 0 | 320x200 (40x25 chars) | 64 characters only. Bits 6-7 of char select 1 of 4 background colors (`$D021-$D024`) per char cell. |
| **Standard Hires Bitmap**| 1 | 0 | 0 | 320x200 pixels | 8000 bytes bitmap data. Screen RAM holds 2 colors per 8x8 block (high nibble foreground, low nibble background). |
| **Multicolor Bitmap** | 1 | 0 | 1 | 160x200 (wide pixels) | 8000 bytes bitmap. 4 colors per 4x8 block: BG0 (`$D021`), Screen RAM high nibble, Screen RAM low nibble, Color RAM `$D800` low nibble. (Standard Koala format). |

---

## 3. Hardware Sprites (Movable Objects)

The VIC-II provides 8 independent hardware sprites (numbered 0 through 7).

### Sprite Dimensions and Layout
* **Dimensions**: 24 pixels wide by 21 pixels high.
* **Size in Bytes**: 63 bytes of pixel data + 1 byte padding = 64 bytes total per sprite.
* **Sprite Data Pointers**: Located at the end of the active Screen RAM:
  * Default location: `$07F8` (Sprite 0) through `$07FF` (Sprite 7).
  * **Pointer Formula**: $\text{Sprite Data Address} = \text{VIC\_Bank\_Base} + (\text{Pointer} \times 64)$.
  * Example: Pointer value `$80` (128) in Bank 0 $\rightarrow 128 \times 64 = \$2000$.

### Sprite Control Registers

| Register | Name | Description |
| :--- | :--- | :--- |
| `$D000 + 2*n` | `SPn_X` | Sprite $n$ X-coordinate low 8 bits (0-255). |
| `$D001 + 2*n` | `SPn_Y` | Sprite $n$ Y-coordinate (0-255). |
| `$D010` | `MSB_X` | 9th X-coordinate bit for sprites 0-7 (permits X coordinates from 256 to 511). |
| `$D015` | `SP_ENABLE` | Bits 0-7: Enable/disable sprites 0-7. |
| `$D017` | `SP_EXP_Y` | Bits 0-7: Vertical expansion (2x height = 42 lines). |
| `$D01D` | `SP_EXP_X` | Bits 0-7: Horizontal expansion (2x width = 48 pixels). |
| `$D01C` | `SP_MULTICOLOR`| Bits 0-7: High-resolution (1-color) vs Multicolor (3-color). |
| `$D01B` | `SP_PRIORITY` | Bits 0-7: 0 = Sprite in front of background, 1 = Sprite behind background. |
| `$D01E` | `SP_SP_COLL` | Sprite-to-Sprite collision flags (Read to clear). |
| `$D01F` | `SP_BG_COLL` | Sprite-to-Background collision flags (Read to clear). |
| `$D025` | `SP_MC_COLOR0` | Multicolor Sprite Shared Color 0. |
| `$D026` | `SP_MC_COLOR1` | Multicolor Sprite Shared Color 1. |
| `$D027 + n` | `SPn_COLOR` | Sprite $n$ Individual Color. |

### Multicolor Sprites (4 Simultaneous Colors within One Boundary)
By setting the sprite's corresponding bit in `$D01C` (Sprite Multicolor Register), a single sprite can display **up to 4 colors** (transparent background + 3 solid colors) within the same 24x21 VIC-II boundary.

In Multicolor mode, pixels are double-width (12 double-wide pixels across the 24-pixel span, 21 rows high), with each pixel defined by **2 bits**:

| Bit Pair | Meaning | VIC-II Hardware Register | Typical Usage |
| :---: | :--- | :--- | :--- |
| **`%00`** | **Transparent** | Background Color (`$D021`) | Allows background graphics / sky to show through |
| **`%01`** | **Extra Color 1** | Sprite Extra Color 1 (`$D025`) | Weapon pods, engines, danger stripes, shadows |
| **`%10`** | **Sprite Color** | Sprite $n$ Individual Color (`$D027 + n`)| Main fuselage, armor, skin tone (unique per sprite) |
| **`%11`** | **Extra Color 2** | Sprite Extra Color 2 (`$D026`) | Tinted canopy, searchlight flare, secondary trim |

```kickassembler
// Example: Configuring Sprite 0 as a 4-Color Helicopter
lda #$01 : sta $d027 // Sprite 0 Individual Color (White)
lda #$02 : sta $d025 // Shared Extra Color 1 (Red)
lda #$07 : sta $d026 // Shared Extra Color 2 (Yellow)
lda $d01c : ora #%00000001 : sta $d01c // Enable Multicolor on Sprite 0
```

### Sprite Overlaying Technique (5 Simultaneous Colors with Hires Sharpness)
To combine the sharp 1-pixel resolution of High-Resolution mode with the vibrant color variety of Multicolor mode:
1. Assign **Sprite 0** to High-Resolution mode (`$D01C` bit 0 = 0) with a dark outline color (Black or Dark Grey).
2. Assign **Sprite 1** to Multicolor mode (`$D01C` bit 1 = 1) containing internal fills (White body, Red pods, Yellow windshield).
3. Position both sprites at the **exact same $(X, Y)$ coordinate**:
   ```kickassembler
   lda #160 : sta $d000 : sta $d002 // X0 = X1 = 160
   lda #130 : sta $d001 : sta $d003 // Y0 = Y1 = 130
   ```
4. This yields **5 colors simultaneously** with needle-sharp outlines!

### Sprite Multiplexing Technique
Because sprite registers can be updated at any scanline:
1. Sort sprite display list by ascending Y coordinates.
2. After the raster beam passes Sprite 0's scanlines ($Y + 21$), trigger a raster IRQ.
3. Repoint Sprite 0's pointer and update its X/Y coordinates to a position further down the screen.
4. Using this method, a game can easily display **16, 24, 32, or more sprites** on a single screen!

---

## 4. VIC-II Timing, Bad Lines, and Cycle Counting

### PAL vs NTSC Architecture:
* **PAL (MOS 6569)**: 312 total raster lines (lines 0 to 311).
  * 63 CPU cycles per raster line.
  * Frame rate: 50.0 Hz.
  * Visible frame: Raster lines ~51 through ~250.
* **NTSC (MOS 6567R8)**: 263 total raster lines.
  * 65 CPU cycles per raster line.
  * Frame rate: 59.8 Hz.

### Bad Lines Theory:
During character display mode, the VIC-II needs to fetch 40 character pointer bytes and 40 color bytes for every character row (every 8 scanlines).
* A **Bad Line** occurs on any scanline where:
  $$\$30 \le \text{Raster Line} \le \$F7 \quad \text{AND} \quad (\text{Raster Line} \ \& \ 7) == (\$D011 \ \& \ 7)$$
* **What happens**: The VIC-II pulls the 6510 CPU `RDY` line low (halts the CPU) for **40 to 43 clock cycles** to steal memory bus access.
* **Critical Rule for Timing Code**: Never place cycle-exact raster splits on a Bad Line unless cycle calculations account for CPU suspension.

---

## 5. Stable Double-IRQ (0-Cycle Jitter Stabilization)

When the 6510 receives an interrupt, it may be executing an instruction that takes between 2 and 7 cycles to finish. This introduces 1 to 3 cycles of **interrupt jitter** (visual waving/flickering on raster splits).

The demoscene solves this with the **Double IRQ** technique:
1. First IRQ triggers at raster line $L$.
2. It sets the next IRQ to trigger at raster line $L+1$.
3. It acknowledges the first IRQ and executes a chain of `NOP`s or `CLI / HLT`.
4. Because the CPU is executing known 2-cycle instructions when line $L+1$ fires, jitter is completely eliminated!

```kickassembler
irq_stage1:
    // Acknowledge VIC-II IRQ
    asl $d019
    
    // Set IRQ vector to stage 2
    lda #<irq_stage2
    sta $0314
    lda #>irq_stage2
    sta $0315
    
    // Set interrupt to fire on the very next scanline
    inc $d012
    
    // Save stack pointer and wait
    tsx
    cli
    nop; nop; nop; nop; nop
    nop; nop; nop; nop; nop
    rts

irq_stage2:
    txs             // Restore stack
    ldx #$08
wait_cycles:
    dex
    bne wait_cycles
    
    // Compare raster counter to align exact cycle
    lda $d012
    cmp $d012       // 5 cycles: 0-jitter lock
    beq jitter_lock
jitter_lock:
    // EXACT CYCLE ALIGNMENT REACHED HERE
    // Perform ultra-sharp border color split:
    lda #$01
    sta $d020
```

---

## 6. Border Removal (Opening Borders)

### Top & Bottom Border Opening:
The VIC-II displays borders by checking raster line 247/251 (bottom) and line 51/55 (top).
* Register `$D011` bit 3 selects 24-row mode (`0`) or 25-row mode (`1`).
* **The Trick**: Keep the screen in 24-row mode. When the raster beam reaches line 249, switch to 25-row mode. The VIC-II misses its bottom border trigger, keeping the border open!
* Result: 200 pixel display expands to **full 256 pixel vertical display**!

### Side Border Opening:
* Register `$D016` bit 3 selects 38-column mode (`0`) or 40-column mode (`1`).
* **The Trick**: At raster line cycle 56/57, switch from 40 to 38 columns and back. The VIC-II side border flip-flop is tricked, rendering graphics across the entire horizontal border (320 $\rightarrow$ **384 pixels wide**)!
