// ==============================================================================
// IRONFRONT - loading screen
// Shows loading.kla (multicolor bitmap, made by gen_loading.py), plays the title
// march (../music) from a 50 Hz raster interrupt, and waits for fire on
// joystick port 2 or SPACE. Stage 3 will jump into the game from `done`.
// Target Assembler: KickAssembler v5.x
// ==============================================================================

.var pic = LoadBinary("loading.kla", BF_KOALA)

#import "../music/music_config.asm"

.const SCREEN_RAM   = $0400
.const COLOR_RAM    = $D800
.const BITMAP       = $2000
.const VIC_CTRL1    = $D011
.const VIC_CTRL2    = $D016
.const VIC_MEMORY   = $D018
.const BORDER       = $D020
.const BACKGROUND   = $D021
.const CIA1_PRA     = $DC00
.const GETIN        = $FFE4
.const VIC_RASTER   = $D012
.const VIC_IRQ_FLAG = $D019
.const VIC_IRQ_MASK = $D01A
.const CIA1_ICR     = $DC0D
.const IRQ_VECTOR   = $0314
.const KERNAL_IRQ   = $EA31
.const IRQ_LINE     = 250       // in the lower border, clear of the picture

BasicUpstart2(entry_point)

* = $0810 "Loader"
entry_point:
        lda #$00
        sta BORDER
        lda #pic.getBackgroundColor()
        sta BACKGROUND

        // copy screen RAM (colours 01/10) and colour RAM (colour 11): 1000 bytes each
        ldx #$00
copy:   lda screen_data,x
        sta SCREEN_RAM,x
        lda screen_data+$100,x
        sta SCREEN_RAM+$100,x
        lda screen_data+$200,x
        sta SCREEN_RAM+$200,x
        lda screen_data+$2e8,x
        sta SCREEN_RAM+$2e8,x
        lda color_data,x
        sta COLOR_RAM,x
        lda color_data+$100,x
        sta COLOR_RAM+$100,x
        lda color_data+$200,x
        sta COLOR_RAM+$200,x
        lda color_data+$2e8,x
        sta COLOR_RAM+$2e8,x
        inx
        bne copy

        lda #$3b                // bitmap mode, screen on, 25 rows
        sta VIC_CTRL1
        lda #$18                // multicolor, 40 columns
        sta VIC_CTRL2
        lda #$18                // screen at $0400, bitmap at $2000
        sta VIC_MEMORY

        jsr music_init
        sei
        lda #$7f                // CIA timer IRQ off: the raster IRQ drives the music
        sta CIA1_ICR            // and the KERNAL keyboard scan, once per frame
        lda CIA1_ICR
        lda #<irq
        sta IRQ_VECTOR
        lda #>irq
        sta IRQ_VECTOR+1
        lda #IRQ_LINE
        sta VIC_RASTER
        lda VIC_CTRL1
        and #$7f                // raster line bit 8 = 0
        sta VIC_CTRL1
        lda #$01
        sta VIC_IRQ_MASK
        cli

wait:   lda CIA1_PRA            // joystick port 2: fire is bit 4, active low
        and #%00010000
        beq done
        jsr GETIN
        cmp #$20
        beq done
        jmp wait

done:   sei                     // stop the music and restore the KERNAL interrupt
        lda #$00
        sta VIC_IRQ_MASK
        sta $d418               // SID volume off
        lda #$ff
        sta VIC_IRQ_FLAG
        lda #<KERNAL_IRQ
        sta IRQ_VECTOR
        lda #>KERNAL_IRQ
        sta IRQ_VECTOR+1
        lda #$81
        sta CIA1_ICR
        cli
        lda #$1b                // back to the standard text screen for now
        sta VIC_CTRL1
        lda #$c8
        sta VIC_CTRL2
        lda #$15
        sta VIC_MEMORY
        lda #14
        sta BORDER
        lda #6
        sta BACKGROUND
        jmp $e544               // KERNAL: clear screen, then return to BASIC

irq:    lda #$ff
        sta VIC_IRQ_FLAG        // acknowledge the raster interrupt
        jsr music_play
        jmp KERNAL_IRQ          // keyboard scan, then return from the interrupt

#import "../../../tools/sid/sid_player.asm"
#import "../music/music_data.asm"

* = BITMAP "Bitmap"
        .fill pic.getBitmapSize(), pic.getBitmap(i)
screen_data:
        .fill pic.getScreenRamSize(), pic.getScreenRam(i)
color_data:
        .fill pic.getColorRamSize(), pic.getColorRam(i)
