// HELISCAPE - four-band parallax
//
// Each band keeps a position in pixels; its screen rows are moved one column
// whenever position / 8 changes, and the fine scroll goes to the raster split.
// All moves run in the main loop right after the bottom IRQ, so the raster chain
// is never delayed and the rows are done before the beam reaches them. At most
// one band moves per frame (near first); a late band just holds its fine scroll
// for a frame, which nobody can see on the slow layers.

.macro SHIFT_LEFT(base, rows) {
        ldx #0
!loop:  .for (var r = 0; r < rows; r++) {
            lda base + r * 40 + 1,x
            sta base + r * 40,x
        }
        inx
        cpx #39
        beq !done+
        jmp !loop-
!done:
}

.macro SHIFT_RIGHT(base, rows) {
        ldx #38
!loop:  .for (var r = 0; r < rows; r++) {
            lda base + r * 40,x
            sta base + r * 40 + 1,x
        }
        dex
        bmi !done+
        jmp !loop-
!done:
}

// ---------------------------------------------------------------- column writers: X = screen column, Y = world column
draw_near_col:
        .for (var r = 0; r < NEAR_H; r++) {
            lda WCH + r * 256,y
            sta ROW(R_NEAR + r),x
            lda WCO + r * 256,y
            sta CROW(R_NEAR + r),x
        }
        rts

draw_far_col:
        tya
        and #FAR_W - 1
        tay
        .for (var r = 0; r < FAR_ROWS; r++) {
            lda (far_p + r * 2),y
            sta ROW(R_FAR + r),x
        }
        rts

draw_mid_col:
        tya
        and #MID_W - 1
        tay
        .for (var r = 0; r < MID_ROWS; r++) {
            lda (mid_p + r * 2),y
            sta ROW(R_MID + r),x
        }
        rts

draw_cld_col:
        tya
        and #CLOUD_W - 1
        tay
        .for (var r = 0; r < CLD_ROWS; r++) {
            lda (cld_p + r * 2),y
            sta ROW(R_CLOUD + r),x
        }
        rts

// ---------------------------------------------------------------- one column step per band
near_left:
        SHIFT_LEFT(ROW(R_NEAR), NEAR_H)
        SHIFT_LEFT(CROW(R_NEAR), NEAR_H)
        inc col_near
        lda col_near
        clc
        adc #39
        tay
        ldx #39
        jmp draw_near_col
near_right:
        SHIFT_RIGHT(ROW(R_NEAR), NEAR_H)
        SHIFT_RIGHT(CROW(R_NEAR), NEAR_H)
        dec col_near
        ldy col_near
        ldx #0
        jmp draw_near_col

far_left:
        SHIFT_LEFT(ROW(R_FAR), FAR_ROWS)
        inc col_far
        lda col_far
        clc
        adc #39
        tay
        ldx #39
        jmp draw_far_col
far_right:
        SHIFT_RIGHT(ROW(R_FAR), FAR_ROWS)
        dec col_far
        ldy col_far
        ldx #0
        jmp draw_far_col

mid_left:
        SHIFT_LEFT(ROW(R_MID), MID_ROWS)
        inc col_mid
        lda col_mid
        clc
        adc #39
        tay
        ldx #39
        jmp draw_mid_col
mid_right:
        SHIFT_RIGHT(ROW(R_MID), MID_ROWS)
        dec col_mid
        ldy col_mid
        ldx #0
        jmp draw_mid_col

cld_left:
        SHIFT_LEFT(ROW(R_CLOUD), CLD_ROWS)
        inc col_cld
        lda col_cld
        clc
        adc #39
        tay
        ldx #39
        jmp draw_cld_col

// ---------------------------------------------------------------- A = position lo, X = position hi -> A = column
pos_to_col:
        stx t0
        lsr t0
        ror
        lsr t0
        ror
        lsr t0
        ror
        rts

// A = position lo -> A = $D016 value with this band's fine scroll
fine_of:
        and #7
        eor #7
        ora #D016_STATIC
        rts

// ---------------------------------------------------------------- called once per frame in vblank
apply_scroll:
        // mid moves dx/2, far dx/4, as 16.8 pixels (arithmetic shifts keep the sign)
        ldx #0
        lda cam_dx
        bpl !+
        ldx #$ff
!:      stx t1                  // sign extension
        cmp #$80
        ror
        sta t3                  // whole pixels of dx/2
        lda #0
        ror
        sta t4                  // fraction of dx/2
        clc
        adc mid_f
        sta mid_f
        lda mid_l
        adc t3
        sta mid_l
        lda mid_h
        adc t1
        sta mid_h
        lda t3
        cmp #$80
        ror
        sta t3                  // whole pixels of dx/4
        lda t4
        ror
        clc
        adc far_f
        sta far_f
        lda far_l
        adc t3
        sta far_l
        lda far_h
        adc t1
        sta far_h
        lda #0
        sta cam_dx

        // near band first
        lda cam_l
        ldx cam_h
        jsr pos_to_col
        sec
        sbc col_near
        beq !near_ok+
        bmi !+
        jsr near_left
        jmp !near_moved+
!:      jsr near_right
!near_moved:
        lda #1
        sta t2
        jmp !near_fine+
!near_ok:
        lda #0
        sta t2
!near_fine:
        lda cam_l
        jsr fine_of
        sta d_near

        // mid band, if nothing has moved yet
        lda mid_l
        ldx mid_h
        jsr pos_to_col
        sec
        sbc col_mid
        beq !mid_ok+
        ldx t2
        bne !mid_done+          // no budget: hold for a frame
        inc t2
        cmp #0
        bmi !+
        jsr mid_left
        jmp !mid_ok+
!:      jsr mid_right
!mid_ok:
        lda mid_l
        jsr fine_of
        sta d_mid
!mid_done:

        // far band
        lda far_l
        ldx far_h
        jsr pos_to_col
        sec
        sbc col_far
        beq !far_ok+
        ldx t2
        bne !far_done+
        inc t2
        cmp #0
        bmi !+
        jsr far_left
        jmp !far_ok+
!:      jsr far_right
!far_ok:
        lda far_l
        jsr fine_of
        sta d_far
!far_done:

        // clouds drift on their own, one way only
        lda clouds_on
        beq !done+
        clc
        lda cld_f
        adc #$28
        sta cld_f
        lda cld_l
        adc #0
        sta cld_l
        lda cld_h
        adc #0
        sta cld_h
        lda cld_l
        ldx cld_h
        jsr pos_to_col
        cmp col_cld
        beq !cld_ok+
        ldx t2
        bne !done+
        jsr cld_left
!cld_ok:
        lda cld_l
        jsr fine_of
        sta d_cloud
!done:  rts

// ---------------------------------------------------------------- full redraws (screen blanked)
redraw_near:
        lda cam_l
        ldx cam_h
        jsr pos_to_col
        sta col_near
        lda cam_l
        jsr fine_of
        sta d_near
        ldx #39
!:      txa
        clc
        adc col_near
        tay
        jsr draw_near_col
        dex
        bpl !-
        rts

redraw_back:
        lda far_l
        ldx far_h
        jsr pos_to_col
        sta col_far
        lda mid_l
        ldx mid_h
        jsr pos_to_col
        sta col_mid
        lda far_l
        jsr fine_of
        sta d_far
        lda mid_l
        jsr fine_of
        sta d_mid
        ldx #39
!:      txa
        clc
        adc col_far
        tay
        jsr draw_far_col
        txa
        clc
        adc col_mid
        tay
        jsr draw_mid_col
        dex
        bpl !-
        rts

redraw_clouds:
        lda cld_l
        ldx cld_h
        jsr pos_to_col
        sta col_cld
        lda cld_l
        jsr fine_of
        sta d_cloud
        ldx #39
!:      txa
        clc
        adc col_cld
        tay
        jsr draw_cld_col
        dex
        bpl !-
        rts

// the static sky: dither rows between gradient bands, then the sun
draw_sky:
        ldx #39
!loop:  lda #32
        .for (var r = 0; r < R_FAR; r++) {
            sta ROW(r),x
        }
        txa
        and #1
        tay
        lda dither_codes,y
        sta ROW(2),x
        sta ROW(4),x
        sta ROW(6),x
        sta ROW(8),x
        dex
        bpl !loop-
        // sun, 6x5 chars
        lda block_lo + B_SUN
        sta ptr
        lda block_hi + B_SUN
        sta ptr+1
        ldy #0
        .for (var r = 0; r < 5; r++) {
            ldx #0
!:          lda (ptr),y
            sta ROW(R_SUN + r) + SUN_COL,x
            iny
            inx
            cpx #6
            bne !-
        }
        rts

dither_codes:
        .byte 0, 0              // patched at boot from the block table

// fill colour RAM by row: sky and parallax rows never change colour
// t0 = cloud, t1 = sun, t2 = far, t3 = mid (values have the multicolor bit set)
draw_row_colours:
        ldx #39
!:      lda t0
        .for (var r = 0; r < 4; r++) {
            sta CROW(r),x
        }
        lda t1
        .for (var r = 4; r < R_FAR; r++) {
            sta CROW(r),x
        }
        lda t2
        .for (var r = R_FAR; r < R_MID; r++) {
            sta CROW(r),x
        }
        lda t3
        .for (var r = R_MID; r < R_NEAR; r++) {
            sta CROW(r),x
        }
        dex
        bpl !-
        rts

// ---------------------------------------------------------------- art pointers
init_art_pointers:
        lda block_lo + B_FAR
        sta t0
        lda block_hi + B_FAR
        sta t1
        ldx #0
!:      lda t0
        sta far_p,x
        lda t1
        sta far_p + 1,x
        clc
        lda t0
        adc #FAR_W
        sta t0
        bcc !+
        inc t1
!:      inx
        inx
        cpx #2 * FAR_ROWS
        bne !--
        lda block_lo + B_MID
        sta t0
        lda block_hi + B_MID
        sta t1
        ldx #0
!:      lda t0
        sta mid_p,x
        lda t1
        sta mid_p + 1,x
        clc
        lda t0
        adc #MID_W
        sta t0
        bcc !+
        inc t1
!:      inx
        inx
        cpx #2 * MID_ROWS
        bne !--
        lda block_lo + B_CLOUDS
        sta t0
        lda block_hi + B_CLOUDS
        sta t1
        ldx #0
!:      lda t0
        sta cld_p,x
        lda t1
        sta cld_p + 1,x
        clc
        lda t0
        adc #CLOUD_W
        sta t0
        bcc !+
        inc t1
!:      inx
        inx
        cpx #2 * CLD_ROWS
        bne !--
        // the dither chars are 1x1 blocks: their code is the first block_chars byte
        lda block_lo + B_DITHER_A
        sta ptr
        lda block_hi + B_DITHER_A
        sta ptr+1
        ldy #0
        lda (ptr),y
        sta dither_codes
        lda block_lo + B_DITHER_B
        sta ptr
        lda block_hi + B_DITHER_B
        sta ptr+1
        lda (ptr),y
        sta dither_codes + 1
        rts
