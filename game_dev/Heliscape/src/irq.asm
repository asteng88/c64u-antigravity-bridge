// HELISCAPE - the raster chain
//
//   30   top       sprites 0-7 (air band), first palette, cloud scroll
//   66   row 2     sky stops scrolling
//   74   row 3     sky band          90  row 5       106  row 7
//  122   row 9     mesas: palette + 1/4 scroll
//  154   row 13    dunes: palette + 1/2 scroll
//  178   row 16    plain: palette + full scroll
//  184   zone      sprites 4-7 reloaded for the ground band
//  210   row 20    ground palette
//  226   row 22    HUD: black, 40 columns, no scroll
//  251   bottom    frame tick, buffer swap, sound
//
// Sprites steal CPU time around the end of a line and a row's first line belongs to the
// VIC (a bad line), so a store cannot be promised a place between two rows. With enough
// sprites it slips, and the old colour shows as a stray line. So nothing here depends on
// timing to the cycle: each change happens behind pixels it does not affect.
//
//   * The line before a row shows no $D021: the last two lines of a sky dither are all
//     $D022, which is the next band's $D021 (the palette tables must keep that true), and
//     mesas and dunes are solid. $D021, $D023 and $D016 can change at any moment of it.
//   * $D022 is in use on that line, so it changes once the row has begun. A row's first
//     line only has pixels where old and new look the same.
//   * ROW_BEGUN leaves the value ready in X, so the store follows at once: at the start of
//     the first line, or just after the VIC lets go, and before the second line is drawn
//     even with sprites taking more time.
//   * The ground works the other way round, because the plain above it shows $D021 on its
//     bottom line: $D022 and $D023 change on that line (it has no pixels in them), and the
//     top two lines of the ground are all $D022, so $D021 changes behind those.
//   * No sprite reaches the HUD, so nothing delays that store: it lands before the VIC
//     takes the line, and the top line of the text is already in 40 columns with no scroll.

// wait until the raster is past the line before this row: >= so a stolen line cannot be
// missed, and 7 cycles a turn so the store after it beats the bad line of an unstolen row
.macro ROW_BEGUN(row) {
        lda #SPLITLINE(row)
!:      cmp $d012
        bcs !-
}

.macro SPLIT(i, d016src, isVar, row, nextLine, nextIrq) {
        sta sa
        stx sx
        ldx pal_22 + i
        lda pal_21 + i
        sta $d021
        lda pal_23 + i
        sta $d023
        .if (isVar) {
            lda d016src
        } else {
            lda #d016src
        }
        sta $d016
        ROW_BEGUN(row)
        stx $d022
        lda #nextLine
        sta $d012
        lda #<nextIrq
        sta $fffe
        lda #>nextIrq
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        rti
}

.const D016_STATIC = $10        // multicolor, 38 columns, no scroll
.const D016_HUD    = $18        // multicolor, 40 columns

// ---- palette indexes
.const PI_TOP = 0
.const PI_R3  = 1
.const PI_R5  = 2
.const PI_R7  = 3
.const PI_FAR = 4
.const PI_MID = 5
.const PI_NEAR = 6
.const PI_GND = 7
.const PI_HUD = 8

irq_top:
        sta sa
        stx sx
        sty sy
        lda pal_21 + PI_TOP
        sta $d021
        lda pal_22 + PI_TOP
        sta $d022
        lda pal_23 + PI_TOP
        sta $d023
        lda d_cloud
        sta $d016
        ldy front
        .for (var s = 0; s < 8; s++) {
            lda s_x + s,y
            sta $d000 + s * 2
            lda s_y + s,y
            sta $d001 + s * 2
            lda s_p + s,y
            sta SPRPTR + s
            lda s_c + s,y
            sta $d027 + s
        }
        lda s_msb_top,y
        sta $d010
        lda #SPLITLINE(2)
        sta $d012
        lda #<irq_r2
        sta $fffe
        lda #>irq_r2
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        ldy sy
        rti

irq_r2:
        sta sa
        stx sx
        ldx #D016_STATIC
        ROW_BEGUN(2)
        stx $d016
        lda #SPLITLINE(3)
        sta $d012
        lda #<irq_r3
        sta $fffe
        lda #>irq_r3
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        rti

irq_r3:  SPLIT(PI_R3,  D016_STATIC, false, 3, SPLITLINE(5),  irq_r5)
irq_r5:  SPLIT(PI_R5,  D016_STATIC, false, 5, SPLITLINE(7),  irq_r7)
irq_r7:  SPLIT(PI_R7,  D016_STATIC, false, 7, SPLITLINE(R_FAR), irq_far)
irq_far: SPLIT(PI_FAR, d_far,  true,  R_FAR, SPLITLINE(R_MID), irq_mid)
irq_mid: SPLIT(PI_MID, d_mid,  true,  R_MID, SPLITLINE(R_NEAR), irq_near)
irq_near: SPLIT(PI_NEAR, d_near, true, R_NEAR, LINE_ZONE, irq_zone)

irq_zone:
        sta sa
        stx sx
        sty sy
        ldy front
        lda s_msb_top,y
        and #$0f
        ora s_msb_gnd,y
        sta $d010
        .for (var s = 0; s < 4; s++) {
            lda s_x + 8 + s,y
            sta $d000 + (4 + s) * 2
            lda s_y + 8 + s,y
            sta $d001 + (4 + s) * 2
            lda s_p + 8 + s,y
            sta SPRPTR + 4 + s
            lda s_c + 8 + s,y
            sta $d027 + 4 + s
        }
        lda #SPLITLINE(R_GROUND)
        sta $d012
        lda #<irq_gnd
        sta $fffe
        lda #>irq_gnd
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        ldy sy
        rti

irq_gnd:
        sta sa
        stx sx
        ldx pal_21 + PI_GND
        lda pal_22 + PI_GND
        sta $d022
        lda pal_23 + PI_GND
        sta $d023
        ROW_BEGUN(R_GROUND)
        stx $d021
        lda #SPLITLINE(R_HUD)
        sta $d012
        lda #<irq_hud
        sta $fffe
        lda #>irq_hud
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        rti

irq_hud:
        sta sa
        stx sx
        lda pal_21 + PI_HUD
        sta $d021
        ldx #D016_HUD
        ROW_BEGUN(R_HUD)
        stx $d016
        lda pal_22 + PI_HUD
        sta $d022
        lda pal_23 + PI_HUD
        sta $d023
        lda #LINE_BOTTOM
        sta $d012
        lda #<irq_bottom
        sta $fffe
        lda #>irq_bottom
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        rti

irq_bottom:
        sta sa
        stx sx
        sty sy
        cld
        inc frame
        lda #1
        sta vflag
        lda back_ready
        beq !+
        lda bk
        sta front
        lda #0
        sta back_ready
!:      lda music_on
        beq !+
        jsr music_play
!:      lda sfx_on
        beq !+
        jsr sfx_tick
!:      lda #LINE_TOP
        sta $d012
        lda #<irq_top
        sta $fffe
        lda #>irq_top
        sta $ffff
        lda #1
        sta $d019
        lda sa
        ldx sx
        ldy sy
        rti
