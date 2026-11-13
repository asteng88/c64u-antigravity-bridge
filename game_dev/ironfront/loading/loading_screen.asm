// ==============================================================================
// IRONFRONT - loading screen
// Shows loading.kla (multicolor bitmap, made by gen_loading.py), overlays crisp
// high-res sprite text ("Game by Station88Retro") in the bottom right corner,
// plays the title march (../music) from a 50 Hz raster interrupt, and waits for
// fire on joystick port 2 or SPACE. Stage 3 will jump into the game from `done`.
// Target Assembler: KickAssembler v5.x
// ==============================================================================

.var pic = LoadBinary("loading.kla", BF_KOALA)

#import "../music/music_config.asm"

.const SCREEN_RAM   = $0400
.const SPRITE_PTRS  = $07F8
.const COLOR_RAM    = $D800
.const CHAR_ROM     = $D800     // Lowercase/uppercase glyphs in Character ROM ($D000 + $0800)
.const BITMAP       = $2000
.const SPRITE_BASE  = $0340     // 3 x 64-byte sprites ($0340-$03FF, pointers $0D, $0E, $0F)

.const VIC_SP0_X    = $D000
.const VIC_SP0_Y    = $D001
.const VIC_SP_MSB   = $D010
.const VIC_CTRL1    = $D011
.const VIC_RASTER   = $D012
.const VIC_SP_EN    = $D015
.const VIC_CTRL2    = $D016
.const VIC_SP_EXPY  = $D017
.const VIC_MEMORY   = $D018
.const VIC_IRQ_FLAG = $D019
.const VIC_IRQ_MASK = $D01A
.const VIC_SP_PRIO  = $D01B
.const VIC_SP_MC    = $D01C
.const VIC_SP_EXPX  = $D01D
.const BORDER       = $D020
.const BACKGROUND   = $D021
.const VIC_SP0_COL  = $D027

.const CIA1_PRA     = $DC00
.const CIA1_ICR     = $DC0D
.const GETIN        = $FFE4
.const IRQ_VECTOR   = $0314
.const KERNAL_IRQ   = $EA31
.const IRQ_LINE     = 250       // in the lower border, clear of the picture

.const ZP_SRC       = $FB       // temporary ZP pointers (used before music_init)
.const ZP_DST       = $FD

// Bottom-right placement for 3 adjacent 24px sprites (22 chars = 176px wide; 3 sprites = 72px? Wait: 22 chars * 8px = 176px -> 8 sprites!)
// Let's use 8 hires sprites (8 * 24px = 192px) across the bottom-right corner!
.const CREDIT_SPRITES = 8
.const SPRITE_RAM   = $3F40     //Wait: $2000 + 8000 = $3F40..$3FFF? No, 8 sprites = 512 bytes -> place at $3E00? Wait: $2000..$3F3F is bitmap!

BasicUpstart2(start)

* = $0810 "Loader"
start:
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

        // Render "Game by Station88Retro" into 8 high-res hardware sprites
        // so it overlays cleanly at full 320px sharpness without altering Koala cell colors
        jsr build_credit_sprites
        jsr setup_credit_sprites

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
        sta VIC_SP_EN           // turn off credit overlay sprites
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

// ------------------------------------------------------------------------------
// Build 8 hires sprites at $1E00-$1FFF (VIC Bank 0 pointers $78..$7F)
// from Character ROM ($D800 mixed-case font) for "  Game by Station88Retro"
// (24 characters = 8 sprites x 3 characters per sprite).
// ------------------------------------------------------------------------------
.const CREDIT_SPR_MEM = $1E00
.const CREDIT_SPR_PTR = CREDIT_SPR_MEM / 64

build_credit_sprites:
        // Clear 512 bytes ($1E00-$1FFF)
        lda #$00
        tax
!:      sta CREDIT_SPR_MEM,x
        sta CREDIT_SPR_MEM+$100,x
        inx
        bne !-

        // Bank in Character ROM at $D000-$DFFF while interrupts are disabled
        sei
        lda $01
        pha
        and #%11111011          // CHAREN = 0 -> Character ROM visible at $D000
        sta $01

        ldx #$00                // character index 0..23
next_char:
        // Source address = CHAR_ROM ($D800) + screencode * 8
        lda credit_text,x
        sta ZP_SRC
        lda #$00
        asl ZP_SRC
        rol
        asl ZP_SRC
        rol
        asl ZP_SRC
        rol
        clc
        adc #>CHAR_ROM
        sta ZP_SRC+1

        // Destination address = sprite base + (char / 3) * 64 + (char % 3) + 18 (row 6 offset)
        lda char_spr_lo,x
        sta ZP_DST
        lda char_spr_hi,x
        sta ZP_DST+1

        // Copy 8 scanlines of glyph into sprite rows (stride 3 bytes per sprite row)
        ldy #$00
        lda (ZP_SRC),y
        sta (ZP_DST),y          // line 0 (offset 0)
        iny
        lda (ZP_SRC),y
        ldy #3
        sta (ZP_DST),y          // line 1 (offset 3)
        ldy #2
        lda (ZP_SRC),y
        ldy #6
        sta (ZP_DST),y          // line 2 (offset 6)
        ldy #3
        lda (ZP_SRC),y
        ldy #9
        sta (ZP_DST),y          // line 3 (offset 9)
        ldy #4
        lda (ZP_SRC),y
        ldy #12
        sta (ZP_DST),y          // line 4 (offset 12)
        ldy #5
        lda (ZP_SRC),y
        ldy #15
        sta (ZP_DST),y          // line 5 (offset 15)
        ldy #6
        lda (ZP_SRC),y
        ldy #18
        sta (ZP_DST),y          // line 6 (offset 18)
        ldy #7
        lda (ZP_SRC),y
        ldy #21
        sta (ZP_DST),y          // line 7 (offset 21)

        inx
        cpx #24
        bne next_char

        pla
        sta $01                 // restore I/O at $D000-$DFFF
        cli
        rts

// ------------------------------------------------------------------------------
// Position and enable all 8 sprites along the bottom-right corner
// Visible X range: 24..343. Right-aligned 22 chars (with 2 leading spaces = 24 chars):
// Sprite 0..7 X = 148, 172, 196, 220, 244, 268, 292, 316 (ends at X=340, 4px from right border)
// Glyph rows placed at sprite Y+6..Y+13 -> Sprite Y = 234 puts text at Y = 240..247 (bottom row)
// ------------------------------------------------------------------------------
setup_credit_sprites:
        lda #$00
        sta VIC_SP_MC           // all high-resolution sprites
        sta VIC_SP_EXPX         // normal width
        sta VIC_SP_EXPY         // normal height
        sta VIC_SP_PRIO         // in front of bitmap

        ldx #$00
!:      txa
        clc
        adc #CREDIT_SPR_PTR
        sta SPRITE_PTRS,x       // sprite data pointers at $07F8..$07FF
        lda #$0f                // light grey crisp text (readable over dark/colored art)
        sta VIC_SP0_COL,x

        txa
        asl
        tay
        lda spr_x_lo,x
        sta VIC_SP0_X,y
        lda #234                // Y position (text sits on raster lines 240..247)
        sta VIC_SP0_Y,y

        inx
        cpx #8
        bne !-

        lda #%11100000          // sprites 5, 6, 7 have X >= 256
        sta VIC_SP_MSB
        lda #$ff                // enable all 8 sprites
        sta VIC_SP_EN
        rts

.encoding "screencode_mixed"
credit_text:
        .text "  Game by Station88Retro"

// Lookup tables mapping each of the 24 character slots into $1E00 + (i/3)*64 + 18 + (i%3)
char_spr_lo:
        .fill 24, <(CREDIT_SPR_MEM + floor(i / 3) * 64 + 18 + mod(i, 3))
char_spr_hi:
        .fill 24, >(CREDIT_SPR_MEM + floor(i / 3) * 64 + 18 + mod(i, 3))

// Sprite X low bytes: 148 + i * 24 (wrapped mod 256)
spr_x_lo:
        .fill 8, <(148 + i * 24)

#import "../../../tools/sid/sid_player.asm"
#import "../music/music_data.asm"

// Ensure code + music before $1E00 do not collide with sprite buffer at $1E00-$1FFF
.if (* > CREDIT_SPR_MEM) {
        .error "Code/music exceeds $1E00 sprite buffer!"
}

* = BITMAP "Bitmap"
        .fill pic.getBitmapSize(), pic.getBitmap(i)
screen_data:
        .fill pic.getScreenRamSize(), pic.getScreenRam(i)
color_data:
        .fill pic.getColorRamSize(), pic.getColorRam(i)
