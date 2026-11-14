// ==============================================================================
// TORNADO - levels: 25 missions, survivors placed on different islands, cyclones
// that grow stronger every level, day and night missions, the mission briefing.
// Assembled in the free gap after the music ($1508-$17FF).
// ==============================================================================

// Per-level settings (index level - 1)
//   people  survivors to rescue
//   gale    cyclone wind radius in tiles (16 px)
//   pull    low nibble: pull every (mask + 1) frames, high nibble: px per pull
//   speed   cyclones move every (mask + 1) frames
//   home    the hunting cyclone re-aims at the heli every (mask + 1) frames
lv_people: .byte 5, 5, 6, 6, 7, 7, 7, 8, 8, 8, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12
lv_gale:   .byte 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 9
lv_pull:   .byte $13, $13, $13, $13, $11, $11, $11, $11, $11, $11, $11, $11
           .byte $10, $10, $10, $10, $10, $10, $10, $20, $20, $20, $20, $20, $20
lv_speed:  .byte 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
lv_home:   .byte $3F, $3F, $3F, $3F, $3F, $3F, $3F, $1F, $1F, $1F, $1F, $1F, $1F, $1F, $1F
           .byte $0F, $0F, $0F, $0F, $0F, $0F, $0F, $0F, $0F, $0F

// Day / night palettes: $D021 sea, $D022 sand, $D023 outlines
pal_d021: .byte BG0, $00
pal_d022: .byte BG1, $09
pal_d023: .byte BG2, $00

// Set up everything for mission `level` (1..25): settings, survivors, cyclones
setup_level:
        ldx level
        dex
        lda lv_people, x
        sta n_people
        lda lv_gale, x
        sta gale_r
        lda lv_pull, x
        and #$0F
        sta pull_mask
        lda lv_pull, x
        lsr
        lsr
        lsr
        lsr
        sta pull_px
        lda lv_speed, x
        sta spd_mask
        lda lv_home, x
        sta home_mask
        lda level               // even missions are flown at night
        and #$01
        eor #$01
        sta night
        lda #$00
        sta crates_got
        sta aboard
        sta run_state
        sta run_delay
        jsr place_people
        ldx #(NUM_TORNS - 1)    // cyclones back to their start
!init_t:
        lda torn_init_x_lo, x
        sta torn_wx_lo, x
        lda torn_init_x_hi, x
        sta torn_wx_hi, x
        lda torn_init_y_lo, x
        sta torn_wy_lo, x
        lda torn_init_y_hi, x
        sta torn_wy_hi, x
        lda torn_init_vx, x
        sta torn_vx, x
        lda torn_init_vy, x
        sta torn_vy, x
        dex
        bpl !init_t-
        rts

// Survivors on different islands: start on a random island, then every
// SPOT_STEP-th island (the generator picks a step sharing no factor with
// SPOT_ISLANDS, so no island repeats), on a random one of its spots.
place_people:
        ldx #(MAX_PEOPLE - 1)
        lda #$00
!clr:   sta crate_active, x
        dex
        bpl !clr-
        jsr rnd
        ldy #SPOT_ISLANDS
        jsr mod_y
        sta lv_isl
        ldx #$00
!lp:    cpx n_people
        bcs !done+
        stx lv_k
        jsr rnd
        ldy lv_isl
        pha
        lda isl_count, y
        tay
        pla
        jsr mod_y               // spot within the island
        ldy lv_isl
        clc
        adc isl_first, y
        tay
        ldx lv_k
        lda spot_x_lo, y
        sta crate_wx_lo, x
        lda spot_x_hi, y
        sta crate_wx_hi, x
        lda spot_y_lo, y
        sta crate_wy_lo, x
        lda spot_y_hi, y
        sta crate_wy_hi, x
        lda #$01
        sta crate_active, x
        lda lv_isl              // next island: SPOT_STEP further round
        clc
        adc #SPOT_STEP
        ldy #SPOT_ISLANDS
        jsr mod_y
        sta lv_isl
        inx
        jmp !lp-
!done:  rts

// A crash: everyone on board is lost; each is replaced by a new survivor
lose_aboard:
        lda aboard
        beq !d+
        jsr spawn_person
        dec aboard
        jmp lose_aboard
!d:     rts

// A new survivor in a free slot, at a random spot nobody stands on
spawn_person:
        ldx #(MAX_PEOPLE - 1)
!f:     lda crate_active, x
        beq !got+
        dex
        bpl !f-
        rts
!got:   stx lv_k
        lda #8
        sta sp_try
!try:   jsr rnd
        ldy #SPOT_COUNT
        jsr mod_y
        tay
        ldx #(MAX_PEOPLE - 1)
!c:     lda crate_active, x
        beq !n+
        lda crate_wx_lo, x
        cmp spot_x_lo, y
        bne !n+
        lda crate_wy_lo, x
        cmp spot_y_lo, y
        bne !n+
        dec sp_try              // taken: try another spot
        bne !try-
!n:     dex
        bpl !c-
        ldx lv_k
        lda spot_x_lo, y
        sta crate_wx_lo, x
        lda spot_x_hi, y
        sta crate_wx_hi, x
        lda spot_y_lo, y
        sta crate_wy_lo, x
        lda spot_y_hi, y
        sta crate_wy_hi, x
        lda #$01
        sta crate_active, x
        rts

// A = A mod Y (Y > 0)
mod_y:  sty lv_m
!m:     cmp lv_m
        bcc !r+
        sbc lv_m
        jmp !m-
!r:     rts

// 8-bit Galois LFSR (never 0)
rnd:    lda rng
        asl
        bcc !nx+
        eor #$1D
!nx:    sta rng
        rts

// Shared colours for day or night
set_palette:
        ldx night
        lda pal_d021, x
        sta $D021
        lda pal_d022, x
        sta $D022
        lda pal_d023, x
        sta $D023
        rts

// ------------------------------------------------------------------------------
// Mission briefing: MISSION nn OF 25, DAY PATROL / NIGHT RESCUE, SURVIVORS nn
// ------------------------------------------------------------------------------
level_intro:
        sei
        lda #$00
        sta $D01A               // raster IRQ off while the briefing is up
        sta $D015
        lda #$01
        sta $D019
        cli
        lda #$1B
        sta $D011
        lda #$08                // hires text
        sta $D016
        lda #$02
        sta $D018
        lda #$00
        sta $D020
        sta $D021
        ldx #$00
!cl:    lda #$20
        sta SCREEN + $000, x
        sta SCREEN + $100, x
        sta SCREEN + $200, x
        sta SCREEN + $2E8, x
        lda #$01
        sta COLRAM + $000, x
        sta COLRAM + $100, x
        sta COLRAM + $200, x
        sta COLRAM + $2E8, x
        inx
        bne !cl-
        ldx #15
!t1:    lda txt_mission, x
        sta SCREEN + 8 * 40 + 12, x
        lda #$07
        sta COLRAM + 8 * 40 + 12, x
        dex
        bpl !t1-
        lda level
        jsr byte_to_2dec
        stx SCREEN + 8 * 40 + 20
        sta SCREEN + 8 * 40 + 21
        lda night
        beq !day+
        ldx #11
!t2:    lda txt_night, x
        sta SCREEN + 11 * 40 + 14, x
        lda #$0E
        sta COLRAM + 11 * 40 + 14, x
        dex
        bpl !t2-
        jmp !surv+
!day:   ldx #11
!t3:    lda txt_day, x
        sta SCREEN + 11 * 40 + 14, x
        lda #$03
        sta COLRAM + 11 * 40 + 14, x
        dex
        bpl !t3-
!surv:  ldx #11
!t4:    lda txt_surv, x
        sta SCREEN + 14 * 40 + 14, x
        lda #$0A
        sta COLRAM + 14 * 40 + 14, x
        dex
        bpl !t4-
        lda n_people
        jsr byte_to_2dec
        stx SCREEN + 14 * 40 + 24
        sta SCREEN + 14 * 40 + 25
        ldx #9
!t5:    lda txt_fire, x
        sta SCREEN + 18 * 40 + 15, x
        dex
        bpl !t5-
!wf:    jsr wait_vbl            // fire to start (after any held fire is let go)
        jsr read_input
        lda joy_bits
        and #$10
        bne !wf-
!wp:    jsr wait_vbl
        jsr read_input
        lda joy_bits
        and #$10
        beq !wp-
!wr:    jsr wait_vbl
        jsr read_input
        lda joy_bits
        and #$10
        bne !wr-
        rts

txt_mission: .text "MISSION 00 OF 25"
txt_day:     .text " DAY PATROL "
txt_night:   .text "NIGHT RESCUE"
txt_surv:    .text "SURVIVORS 00"
txt_fire:    .text "PRESS FIRE"
