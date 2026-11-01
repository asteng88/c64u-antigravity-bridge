// HELISCAPE - building the world for a mission, palettes, stamping blocks

.macro STAMP_X(block, wrow, w, h, colour) {
        lda #w
        sta t0
        lda #h
        sta t1
        lda #colour
        sta t2
        lda #block
        ldy #wrow
        jsr stamp_block
}

.macro STAMP_CAMP(block) {
        lda #8
        sta t0
        lda #3
        sta t1
        lda #RED8
        sta t2
        lda #block
        ldy #1
        jsr stamp_block
}

// palettes: one row per split, top / r3 / r5 / r7 / far / mid / near / ground / hud
//                     top r3 r5 r7 far mid nr gnd hud
pal_src_21:
        .byte 6, 4, 2, 8,10, 4, 9, 8, 0         // dusk
        .byte 0, 6, 6, 4, 4, 0, 6,11, 0         // night
        .byte 6,14,14, 3,15, 6, 5, 9, 0         // dawn
        .byte 14,14,3, 3,15, 2, 8, 7, 0         // noon
        .byte 11,11,12,12,15, 6,11,12, 0        // storm
        .byte 0, 2, 2, 8,10, 0, 2, 8, 0         // blood moon
pal_src_22:
        .byte 4, 2, 8,10, 8, 9, 0, 9,11
        .byte 6, 6, 4, 4, 6, 6, 0, 0,11
        .byte 14,14,3,15,14, 5, 0, 0,11
        .byte 14,3, 3,15,10, 8, 0, 8,11
        .byte 11,12,12,15,11,11, 0,11,11
        .byte 2, 2, 8,10, 7, 2, 0, 2,11
pal_src_23:
        .byte 8, 7, 7, 7, 2, 8,12,10,12
        .byte 11,15,15,15,11,14,11,12,12
        .byte 3, 7, 7, 7, 6,13,12, 8,12
        .byte 3, 7, 7, 7, 8, 7,15, 1,12
        .byte 12,15,15,15, 0,12,15,15,12
        .byte 9, 7, 7, 7, 2, 8,11,10,12

// char colours per palette (multicolor bit added)
mis_cloud:  .byte 4, 6, 1, 1, 0, 2
mis_sun:    .byte 1, 1, 7, 7, 1, 7
mis_far:    .byte 4, 0, 6, 2, 6, 0
mis_mid:    .byte 2, 0, 0, 2, 0, 0
mis_plain:  .byte 2, 0, 0, 2, 0, 0
mis_ground: .byte 7, 1, 7, 2, 0, 0
mis_palm:   .byte 5, 5, 0, 5, 5, 0

load_palette:
        lda palette
        asl
        asl
        asl
        adc palette             // palette * 9
        tax
        ldy #0
!:      lda pal_src_21,x
        sta pal_21,y
        lda pal_src_22,x
        sta pal_22,y
        lda pal_src_23,x
        sta pal_23,y
        inx
        iny
        cpy #SPLITS
        bne !-
        rts

load_row_colours:
        ldx palette
        lda mis_cloud,x
        ora #8
        sta t0
        lda mis_sun,x
        ora #8
        sta t1
        lda mis_far,x
        ora #8
        sta t2
        lda mis_mid,x
        ora #8
        sta t3
        jmp draw_row_colours

// ---------------------------------------------------------------- stamp a block into the world
// A = block, X = column, Y = world row, t0 = width, t1 = height, t2 = colour RAM value
stamp_block:
        stx t3
        sty t4
        tax
        lda block_lo,x
        sta ptr
        lda block_hi,x
        sta ptr+1
!row:   // ptr2 -> world chars at (t4, t3)
        lda t3
        sta ptr2
        clc
        lda t4
        adc #>WCH
        sta ptr2+1
        ldy #0
!col:   lda (ptr),y
        sta (ptr2),y
        iny
        cpy t0
        bne !col-
        // same cells in the colour map
        clc
        lda ptr2+1
        adc #>(WCO - WCH)
        sta ptr2+1
        ldy #0
        lda t2
!col2:  sta (ptr2),y
        iny
        cpy t0
        bne !col2-
        // next row
        clc
        lda ptr
        adc t0
        sta ptr
        bcc !+
        inc ptr+1
!:      inc t4
        dec t1
        bne !row-
        rts

.macro STAMP(block, col, wrow, w, h, colour) {
        lda #w
        sta t0
        lda #h
        sta t1
        lda #colour
        sta t2
        lda #block
        ldx #col
        ldy #wrow
        jsr stamp_block
}

// A = limit, X = first column, Y = count: set the column height table
set_heights:
        sty t0
!:      sta WH,x
        inx
        dec t0
        bne !-
        rts

// ---------------------------------------------------------------- A -> world (with the mission's colours)
build_world:
        // plain rows 0-3 and ground rows 4-5 repeat every 128 columns
        ldx palette
        lda mis_plain,x
        ora #8
        sta t2
        lda mis_ground,x
        ora #8
        sta t3
        lda block_lo + B_PLAIN
        sta ptr
        lda block_hi + B_PLAIN
        sta ptr+1
        lda #>WCH
        sta ptr2+1
        lda #0
        sta ptr2
        lda #PLAIN_H
        sta t0
        lda t2
        sta t1
!bandrow:
        jsr fill_world_row
        clc
        lda ptr
        adc #PLAIN_W
        sta ptr
        bcc !+
        inc ptr+1
!:      inc ptr2+1
        dec t0
        bne !bandrow-
        lda block_lo + B_GROUND
        sta ptr
        lda block_hi + B_GROUND
        sta ptr+1
        lda #GROUND_H
        sta t0
        lda t3
        sta t1
!bandrow:
        jsr fill_world_row
        clc
        lda ptr
        adc #GROUND_W
        sta ptr
        bcc !+
        inc ptr+1
!:      inc ptr2+1
        dec t0
        bne !bandrow-
        // open ground everywhere
        ldx #0
        lda #CHOP_GROUND
!:      sta WH,x
        inx
        bne !-

        // home base
        STAMP(B_HANGAR, HANGAR_COL, 0, 12, 4, CYAN8)
        STAMP(B_TOWER, TOWER_COL, 0, 3, 4, CYAN8)
        STAMP(B_PAD, PAD_COL, 4, 10, 1, WHITE8)
        lda #HANGAR_Y
        ldx #HANGAR_COL
        ldy #12
        jsr set_heights
        lda #HANGAR_Y
        ldx #TOWER_COL
        ldy #3
        jsr set_heights

        // scenery for this palette, from the object table
        ldx #0
        stx t5
!next:  ldx t5
        lda map_objects,x
        bpl !+
        jmp place_camps
!:      sta xsave
        ldy palette
        lda palette_bit,y
        and map_objects + 2,x
        bne !use+
!skip:  lda t5
        clc
        adc #4
        sta t5
        jmp !next-
!use:   lda map_objects + 1,x
        tax
        lda xsave
        cmp #K_PALM
        bne !+
        lda #3
        sta t0
        sta t1
        ldy palette
        lda mis_palm,y          // fronds must show against this palette's plain
        ora #8
        sta t2
        lda #B_PALM
        ldy #1
        jsr stamp_block
        jmp !skip-
!:      cmp #K_ROCK
        bne !+
        STAMP_X(B_ROCK, 3, 3, 1, RED8)
        jmp !skip-
!:      STAMP_X(B_WRECK, 3, 2, 1, RED8)
        jmp !skip-

palette_bit:
        .byte 1, 2, 4, 8, 16, 32

// the camps from this level's layout record; init_enemies reads on from lvy
place_camps:
        ldx mission
        lda lv_layout_lo,x
        sta lvp
        lda lv_layout_hi,x
        sta lvp+1
        ldy #0
        sty c_n
        lda (lvp),y
        sta t5
        iny
        sty lvy
!:      ldy lvy
        lda (lvp),y
        pha
        iny
        lda (lvp),y
        iny
        sty lvy
        ldx c_n
        sta c_wait,x
        clc
        adc pow_total
        sta pow_total
        ldy mission
        lda lv_camp_hp,y
        sta c_hp,x
        lda #3
        sta c_delay,x
        pla
        sta c_col,x
        inc c_n
        pha
        tax
        STAMP_CAMP(B_COMPOUND)
        pla
        tax
        lda #COMPOUND_Y
        ldy #8
        jsr set_heights
        dec t5
        bne !-
        rts

// copies a looping art row to one 256-column world row
// ptr = art row, ptr2 = chars page, t1 = colour
fill_world_row:
        ldy #0
!:      tya
        pha
        and #127
        tay
        lda (ptr),y
        sta t4
        pla
        tay
        lda t4
        sta (ptr2),y
        iny
        bne !-
        // colours live WCO - WCH further on
        lda ptr2+1
        pha
        clc
        adc #>(WCO - WCH)
        sta ptr2+1
        lda t1
!:      sta (ptr2),y
        iny
        bne !-
        pla
        sta ptr2+1
        rts

// X = camp index: replace it with rubble, in the world and on screen
destroy_compound:
        lda c_col,x
        pha
        tax
        STAMP_CAMP(B_RUBBLE)
        pla
        tax
        lda #CHOP_GROUND
        ldy #8
        jsr set_heights
        // redraw whatever part of the near band is visible
        ldx #39
!:      txa
        clc
        adc col_near
        tay
        jsr draw_near_col
        dex
        bpl !-
        rts

// ---------------------------------------------------------------- flash the sky for one frame
update_flash:
        lda flash
        beq !+
        dec flash
        beq !restore+
        lda #1
        sta pal_21 + PI_TOP
        sta pal_21 + PI_R3
        lda #7
        sta pal_21 + PI_R5
        sta pal_21 + PI_R7
!:      rts
!restore:
        jmp load_palette
