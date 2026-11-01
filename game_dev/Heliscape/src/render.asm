// HELISCAPE - builds the back display list once per frame

// a0/a1 = world X of the sprite's left edge -> spr_x0/x1, carry set when on screen
world_x:
        sec
        lda a0
        sbc cam_l
        sta spr_x0
        lda a1
        sbc cam_h
        sta spr_x1
        clc
        lda spr_x0
        adc #31
        sta spr_x0
        lda spr_x1
        adc #0
        sta spr_x1
        beq !yes+
        cmp #1
        bne !no+
        lda spr_x0
        cmp #88
        bcs !no+
!yes:   sec
        rts
!no:    clc
        rts

// X = logical slot; uses spr_x0/x1, spr_y, spr_f. X survives.
put_slot:
        stx xsave
        txa
        clc
        adc bk
        tax
        lda spr_x0
        sta s_x,x
        lda spr_x1
        sta s_m,x
        lda spr_y
        sta s_y,x
        ldy spr_f
        tya
        clc
        adc #SPRPTR0
        sta s_p,x
        lda sprite_colours,y
        sta s_c,x
        ldx xsave
        rts

emit_air:
        ldx air_n
        cpx #8
        bcs !+
        jsr put_slot
        inc air_n
!:      rts

emit_gnd:
        ldx gnd_n
        cpx #12
        bcs !+
        jsr put_slot
        inc gnd_n
!:      rts

render:
        lda #12
        sec
        sbc front
        sta bk
        // hide everything
        tax
        ldy #12
        lda #Y_OFF
!:      sta s_y,x
        inx
        dey
        bne !-
        lda #4
        sta air_n
        lda #8
        sta gnd_n
        jsr render_player
        jsr render_shots
        jsr render_explosions
        jsr render_air
        jsr render_ground
        jsr render_pows
        jsr render_shadow
        // $D010 values
        ldx bk
        ldy #0
        sty t0
        sty t1
!:      lda s_m,x
        lsr
        ror t0
        inx
        iny
        cpy #8
        bne !-
!:      lda s_m,x
        lsr
        ror t1
        inx
        iny
        cpy #12
        bne !-
        ldx bk
        lda t0
        sta s_msb_top,x
        lda t1
        sta s_msb_gnd,x
        lda #1
        sta back_ready
        rts

// ---------------------------------------------------------------- the gunship, slots 0 and 1
chop_base:
        .byte SPR_CHOP_R, SPR_CHOP_F, SPR_CHOP_L
tilt_base:
        .byte SPR_TILT_R, SPR_CHOP_F, SPR_TILT_L
gear_base:
        .byte SPR_GEAR_R, SPR_GEAR_F, SPR_GEAR_L
phase_x2:
        .byte 0, 2, 4, 0

render_player:
        lda p_state
        cmp #PS_DEAD
        bne !+
        rts
!:      lda p_invul
        and #4
        beq !+
        rts
!:      sec
        lda p_xl
        sbc #24
        sta a0
        lda p_xh
        sbc #0
        sta a1
        jsr world_x
        lda p_y
        sta spr_y
        // rotor phase: spinning fast in flight, slower on the ground
        lda frame
        ldx p_state
        cpx #PS_LANDED
        bne !+
        lsr
!:      and #3
        cmp #3
        bne !+
        lda #1
!:      tax
        lda phase_x2,x
        sta t0
        ldx p_face
        lda p_tilt
        beq !+
        lda tilt_base,x
        bne !set+
!:      lda p_y                 // wheels come down near the ground
        cmp #GEAR_Y
        bcc !+
        lda gear_base,x
        bne !set+
!:      lda chop_base,x
!set:   clc
        adc t0
        sta spr_f
        ldx #0
        jsr put_slot
        inc spr_f
        clc
        lda spr_x0
        adc #24
        sta spr_x0
        bcc !+
        inc spr_x1
!:      ldx #1
        jsr put_slot
        lda p_flash
        beq !+
        lda #1
        ldx bk
        sta s_c,x
        sta s_c + 1,x
!:      rts

// ---------------------------------------------------------------- shots share one sprite per side, 25 Hz flicker
render_shots:
        lda #0
        sta t3                  // offset into the shot pool
        ldx #2
        jsr shot_side
        lda #P_SHOTS
        sta t3
        ldx #3
shot_side:
        stx t2
        // start at a different shot each frame
        lda frame
        and #3
        cmp #3
        bne !+
        lda #0
!:      sta t0
        lda #P_SHOTS
        sta t1
!try:   lda t0
        clc
        adc t3
        tax
        lda s_type,x
        bne !found+
        inc t0
        lda t0
        cmp #P_SHOTS
        bcc !+
        lda #0
        sta t0
!:      dec t1
        bne !try-
        rts
!found: sec
        lda s_xl,x
        sbc #12
        sta a0
        lda s_xh,x
        sbc #0
        sta a1
        lda s_yl,x
        sec
        sbc #11
        sta spr_y
        ldy s_type,x
        lda shot_frame,y
        sta spr_f
        cpy #S_MISSILE
        bne !+
        lda s_vxh,x
        bmi !+
        inc spr_f               // heading right
!:      cpy #S_FLAK
        bne !+
        lda frame
        lsr
        and #1
        clc
        adc spr_f
        sta spr_f
!:      jsr world_x
        bcc !+
        ldx t2
        jsr put_slot
!:      rts

shot_frame:
        .byte 0, SPR_BULLET, SPR_BOMB, SPR_SHOT, SPR_SHOT + 2, SPR_SHOT + 4

// ---------------------------------------------------------------- explosions, in the band they are in
ex_len:     .byte 6 * 3, 3 * 3, 3 * 6
ex_base:    .byte SPR_EXPLOSION, SPR_SPARK, SPR_SMOKE
ex_rate:    .byte 3, 3, 6

render_explosions:
        ldx #MAX_EX - 1
!loop:  lda e_kind,x
        bne !+
        jmp !next+
!:      stx t3
        sec
        lda e_xl,x
        sbc #12
        sta a0
        lda e_xh,x
        sbc #0
        sta a1
        jsr world_x
        bcs !+
        jmp !nx2+
!:      ldx t3
        lda e_age,x
        ldy e_kind,x
        dey
        ldx #0
!div:   cmp ex_rate,y
        bcc !dv+
        sbc ex_rate,y
        inx
        jmp !div-
!dv:    txa
        clc
        adc ex_base,y
        sta spr_f
        ldx t3
        lda e_y,x
        sec
        sbc #11
        cmp #176
        bcs !ground+
        cmp #AIR_Y_MAX
        bcc !+
        lda #AIR_Y_MAX
!:      sta spr_y
        jsr emit_air
        jmp !nx2+
!ground:
        cmp #GND_Y_MIN
        bcs !+
        lda #GND_Y_MIN
!:      sta spr_y
        jsr emit_gnd
!nx2:   ldx t3
!next:  dex
        bmi !+
        jmp !loop-
!:      rts

// ---------------------------------------------------------------- aircraft
render_air:
        ldx #MAX_AIR - 1
!loop:  lda a_kind,x
        beq !next+
        stx t3
        sec
        lda a_xl,x
        sbc #12
        sta a0
        lda a_xh,x
        sbc #0
        sta a1
        jsr world_x
        ldx t3
        bcc !next+
        lda a_y,x
        sta spr_y
        lda a_kind,x
        cmp #A_JET
        bne !heli+
        lda frame
        and #1
        ldy a_dir,x
        beq !+
        clc
        adc #2
!:      clc
        adc #SPR_JET
        bne !emit+
!heli: lda frame
        and #1
        clc
        ldy a_dir,x
        beq !+
        clc
        adc #2
!:      clc
        adc #SPR_HELI
!emit:  sta spr_f
        jsr emit_air
        ldx t3
!next:  dex
        bpl !loop-
        rts

// ---------------------------------------------------------------- tanks and turrets
render_ground:
        ldx #MAX_TANK - 1
!loop:  lda g_kind,x
        beq !next+
        stx t3
        sec
        lda g_xl,x
        sbc #12
        sta a0
        lda g_xh,x
        sbc #0
        sta a1
        jsr world_x
        ldx t3
        bcc !next+
        lda #TANK_Y
        sta spr_y
        lda g_kind,x
        cmp #T_TANK
        bne !turret+
        lda g_aim,x
        asl
        sta t0
        lda g_xl,x
        lsr
        and #1
        clc
        adc t0
        adc #SPR_TANK
        bne !emit+
!turret:
        lda g_aim,x
        clc
        adc #SPR_TURRET
!emit:  sta spr_f
        jsr emit_gnd
        ldx t3
!next:  dex
        bpl !loop-
        rts

// ---------------------------------------------------------------- POW squads
// When more squads are on screen than slots remain, the start rotates: flicker
// instead of people vanishing.
render_pows:
        lda frame
        and #MAX_POW - 1
        sta t3
        lda #MAX_POW
        sta t2
!loop:  ldx t3
        lda q_st,x
        beq !next+
        sec
        lda q_xl,x
        sbc #12
        sta a0
        lda q_xh,x
        sbc #0
        sta a1
        jsr world_x
        bcc !next+
        ldx t3
        lda #POW_Y
        sta spr_y
        // frame = (count - 1) * 6 + pose
        lda q_n,x
        sec
        sbc #1
        sta t0
        asl
        adc t0
        asl
        sta t0
        lda q_st,x
        cmp #P_IDLE
        bne !run+
        lda frame
        lsr
        lsr
        lsr
        and #1
        ora #4
        bne !pose+
!run:   lda q_xl,x
        lsr
        lsr
        and #1
        ldy q_dir,x
        beq !pose+
        ora #2
!pose:  clc
        adc t0
        adc #SPR_POW
        sta spr_f
        jsr emit_gnd
!next:  inc t3
        lda t3
        and #MAX_POW - 1
        sta t3
        dec t2
        bne !loop-
        rts

// ---------------------------------------------------------------- shadow / rotor dust, if a slot is free
render_shadow:
        lda p_state
        cmp #PS_DEAD
        beq !done+
        sec
        lda p_xl
        sbc #12
        sta a0
        lda p_xh
        sbc #0
        sta a1
        jsr world_x
        bcc !done+
        lda #SHADOW_Y
        sta spr_y
        lda #CHOP_GROUND
        sec
        sbc p_y
        cmp #18
        bcs !shadow+
        cmp #1
        bcc !shadow+
        lda frame
        lsr
        and #1
        clc
        adc #SPR_DUST
        bne !emit+
!shadow:
        cmp #40
        bcc !wide+
        cmp #90
        bcc !mid+
        lda #SPR_SHADOW + 2
        bne !emit+
!wide:  lda #SPR_SHADOW
        bne !emit+
!mid:   lda #SPR_SHADOW + 1
!emit:  sta spr_f
        jsr emit_gnd
!done:  rts
