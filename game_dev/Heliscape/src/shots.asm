// HELISCAPE - projectiles and explosions

// ---------------------------------------------------------------- explosions: A = kind, a0/a1 = x, ey = centre line
// X survives; Y does not.
spawn_ex:
        sta t0
        ldy #MAX_EX - 1
!:      lda e_kind,y
        beq !free+
        dey
        bpl !-
        rts
!free:  lda t0
        clc
        adc #1
        sta e_kind,y
        lda a0
        sta e_xl,y
        lda a1
        sta e_xh,y
        lda ey
        sta e_y,y
        lda #0
        sta e_age,y
        rts

update_ex:
        ldx #MAX_EX - 1
!loop:  lda e_kind,x
        beq !next+
        inc e_age,x
        tay
        dey
        lda e_age,x
        cmp ex_len,y
        bcc !next+
        lda #0
        sta e_kind,x
!next:  dex
        bpl !loop-
        rts

request_fx:
        cmp fx_req
        bcc !+
        sta fx_req
!:      rts

// ---------------------------------------------------------------- all shots, one pass
update_shots:
        ldx #MAX_SHOT - 1
!loop:  lda s_type,x
        beq !next+
        stx xsave_s
        jsr shot_step
        ldx xsave_s
!next:  dex
        bpl !loop-
        rts

shot_kill:
        lda #0
        sta s_type,x
        rts

shot_step:
        // integrate
        clc
        lda s_xf,x
        adc s_vxl,x
        sta s_xf,x
        lda s_xl,x
        adc s_vxh,x
        sta s_xl,x
        lda s_vxh,x
        bmi !neg+
        lda s_xh,x
        adc #0
        jmp !+
!neg:   lda s_xh,x
        adc #$ff
!:      sta s_xh,x
        clc
        lda s_yf,x
        adc s_vyl,x
        sta s_yf,x
        lda s_yl,x
        adc s_vyh,x
        sta s_yl,x
        // gravity on bombs
        lda s_type,x
        cmp #S_BOMB
        beq !grav+
        cmp #S_EBOMB
        bne !+
!grav:  clc
        lda s_vyl,x
        adc #$0E
        sta s_vyl,x
        bcc !+
        inc s_vyh,x
!:      inc s_age,x
        // leaving the world or the sky
        lda s_xh,x
        cmp #>WORLD_PX
        bcs shot_kill
        lda s_yl,x
        cmp #40
        bcc shot_kill
        lda s_xl,x
        sta a0
        lda s_xh,x
        sta a1
        cpx #P_SHOTS
        bcc player_shot
        jmp enemy_shot

// ---------------------------------------------------------------- player shots
player_shot:
        lda s_type,x
        cmp #S_BOMB
        bne !+
        jmp bomb_step
!:      lda s_age,x
        cmp #38
        bcc !+
        jmp shot_kill
!:      lda s_yl,x
        cmp #GROUND_LINE
        bcc !alive+
        lda #GROUND_LINE - 4
        jsr shot_spark
        ldx xsave_s
        jmp shot_kill
!alive: jsr bullet_vs_air
        bcs !hit+
        jsr bullet_vs_ground
        bcs !hit+
        jsr bullet_vs_camps
        bcs !hit+
        jsr bullet_vs_pows
        bcs !hit+
        rts
!hit:   ldx xsave_s
        jmp shot_kill

// A = line; a small blast at the shot's position
shot_spark:
        sta ey
        lda #EX_SMALL
        jsr spawn_ex
        lda #FX_SMALL
        jmp request_fx

// ---- carry set when the bullet was used up
bullet_vs_air:
        ldy #MAX_AIR - 1
!loop:  lda a_kind,y
        beq !next+
        lda a_xl,y
        sta b0
        lda a_xh,y
        sta b1
        jsr abs_dx
        cmp #14
        bcs !next+
        lda a_y,y
        clc
        adc #11
        sec
        sbc s_yl,x
        bcs !+
        eor #$ff
        adc #1
!:      cmp #10
        bcs !next+
        lda #1
        jsr air_damage
        sec
        rts
!next:  dey
        bpl !loop-
        clc
        rts

bullet_vs_ground:
        lda s_yl,x
        cmp #200
        bcc !miss+
        ldy #MAX_TANK - 1
!loop:  lda g_kind,y
        beq !next+
        lda g_xl,y
        sta b0
        lda g_xh,y
        sta b1
        jsr abs_dx
        cmp #12
        bcs !next+
        lda #1
        jsr ground_damage
        sec
        rts
!next:  dey
        bpl !loop-
!miss:  clc
        rts

// over a standing camp and below its roof line?
bullet_vs_camps:
        lda s_yl,x
        cmp #HIT_LINE
        bcc !miss+
        lda a1
        sta b1
        lda a0
        sta b0
        jsr col_of
        sta t3
        ldy c_n
!loop:  dey
        bmi !miss+
        lda c_hp,y
        beq !loop-
        lda t3
        sec
        sbc c_col,y
        cmp #8
        bcs !loop-
        // chipped
        sty xsave
        lda s_yl,x
        sta ey
        lda #EX_SMALL
        jsr spawn_ex
        lda #FX_SMALL
        jsr request_fx
        ldy xsave
        lda #1
        jsr camp_damage
        sec
        rts
!miss:  clc
        rts

// friendly fire
bullet_vs_pows:
        lda s_yl,x
        cmp #204
        bcc !miss+
        ldy #MAX_POW - 1
!loop:  lda q_st,y
        beq !next+
        lda q_xl,y
        sta b0
        lda q_xh,y
        sta b1
        jsr abs_dx
        cmp #8
        bcs !next+
        jsr pow_kill_one
        sec
        rts
!next:  dey
        bpl !loop-
!miss:  clc
        rts

// ---------------------------------------------------------------- bombs
bomb_step:
        lda s_yl,x
        cmp #GROUND_LINE
        bcs !boom+
        cmp #HIT_LINE
        bcc !done+
        // on a camp roof?
        jsr col_of
        sta t3
        ldy c_n
!loop:  dey
        bmi !done+
        lda c_hp,y
        beq !loop-
        lda t3
        sec
        sbc c_col,y
        cmp #8
        bcs !loop-
!boom:  lda s_xl,x
        sta a0
        lda s_xh,x
        sta a1
        jsr bomb_blast
        ldx xsave_s
        jmp shot_kill
!done:  rts

// world X of the middle of camp Y -> b0/b1
camp_mid_x:
        lda c_col,y
        sta b0
        lda #0
        asl b0
        rol
        asl b0
        rol
        asl b0
        rol
        sta b1
        clc
        lda b0
        adc #32
        sta b0
        bcc !+
        inc b1
!:      rts

// a0/a1 = impact point
bomb_blast:
        lda #203
        sta ey
        lda #EX_BIG
        jsr spawn_ex
        lda #3
        sta flash
        lda #FX_BIG
        jsr request_fx
        // tanks and turrets
        ldy #MAX_TANK - 1
!loop:  lda g_kind,y
        beq !next+
        lda g_xl,y
        sta b0
        lda g_xh,y
        sta b1
        jsr abs_dx
        cmp #26
        bcs !next+
        // ground_damage changes a0/a1: keep the impact point
        lda a0
        pha
        lda a1
        pha
        sty t3
        lda #3
        jsr ground_damage
        ldy t3
        pla
        sta a1
        pla
        sta a0
!next:  dey
        bpl !loop-
        // POWs caught in it
        ldy #MAX_POW - 1
!loop:  lda q_st,y
        beq !next+
        lda q_xl,y
        sta b0
        lda q_xh,y
        sta b1
        jsr abs_dx
        cmp #18
        bcs !next+
        jsr pow_kill_all
!next:  dey
        bpl !loop-
        // camps within reach of the blast
        ldy c_n
!loop:  dey
        bmi !done+
        lda c_hp,y
        beq !loop-
        jsr camp_mid_x
        jsr abs_dx
        cmp #44
        bcs !loop-
        lda a0
        pha
        lda a1
        pha
        sty t3
        lda #4
        jsr camp_damage
        ldy t3
        pla
        sta a1
        pla
        sta a0
        jmp !loop-
!done:  rts

// ---------------------------------------------------------------- damage. Y = index, A = amount.
camp_damage:
        sta t0
        lda c_hp,y
        sec
        sbc t0
        bcs !+
        lda #0
!:      sta c_hp,y
        bne !done+
        // down: rubble, big bang, prisoners start coming out
        tya
        pha
        tax
        jsr destroy_compound
        pla
        tay
        jsr camp_mid_x
        lda b0
        sta a0
        lda b1
        sta a1
        lda #200
        sta ey
        lda #EX_BIG
        jsr spawn_ex
        lda #5
        sta flash
        lda #FX_BIG
        jsr request_fx
        lda #1
        jsr add_score
!done:  rts

ground_damage:
        sta t0
        lda g_xl,y
        sta a0
        lda g_xh,y
        sta a1
        lda #206
        sta ey
        lda g_hp,y
        sec
        sbc t0
        bcs !+
        lda #0
!:      sta g_hp,y
        bne !spark+
        lda #T_NONE
        sta g_kind,y
        lda #EX_BIG
        jsr spawn_ex
        lda #FX_BIG
        jsr request_fx
        lda #$02
        jmp add_score
!spark: lda #EX_SMALL
        jsr spawn_ex
        lda #FX_SMALL
        jmp request_fx

air_damage:
        sta t0
        lda a_hp,y
        sec
        sbc t0
        bcs !+
        lda #0
!:      sta a_hp,y
        bne !spark+
air_destroy:
        lda a_kind,y
        sta t1
        lda #A_NONE
        sta a_kind,y
        lda a_xl,y
        sta a0
        lda a_xh,y
        sta a1
        lda a_y,y
        clc
        adc #11
        sta ey
        lda t1
        pha
        lda #EX_BIG
        jsr spawn_ex
        lda #FX_BIG
        jsr request_fx
        pla
        cmp #A_JET
        bne !heli+
        lda #$03
        jmp add_score
!heli: lda #$02
        jmp add_score
!spark: lda a_xl,y
        sta a0
        lda a_xh,y
        sta a1
        lda a_y,y
        clc
        adc #11
        sta ey
        lda #EX_SMALL
        jsr spawn_ex
        lda #FX_SMALL
        jmp request_fx

// ---------------------------------------------------------------- enemy shots
shot_damage:
        .byte 0, 0, 0, 1, 2, 2

enemy_shot:
        lda s_age,x
        cmp #90
        bcc !+
        // burns out in a puff
        lda s_yl,x
        sta ey
        lda #EX_SMALL
        jsr spawn_ex
        ldx xsave_s
        jmp shot_kill
!:      lda s_yl,x
        cmp #GROUND_LINE
        bcc !+
        lda #GROUND_LINE - 4
        jsr shot_spark
        ldx xsave_s
        jmp shot_kill
!:      // hit the gunship?
        lda p_state
        cmp #PS_FALL
        bcs !done+
        lda p_at_base
        bne !done+
        lda p_invul
        bne !done+
        jsr b_is_player
        jsr abs_dx
        cmp #20
        bcs !done+
        lda p_y
        clc
        adc #CHOP_CY
        sec
        sbc s_yl,x
        bcs !+
        eor #$ff
        adc #1
!:      cmp #10
        bcs !done+
        ldy s_type,x
        lda shot_damage,y
        ldy mission
        clc
        adc lv_dmg,y
        pha
        lda s_yl,x
        sta ey
        lda #EX_SMALL
        jsr spawn_ex
        pla
        jsr hurt
        ldx xsave_s
        jmp shot_kill
!done:  rts

// ---------------------------------------------------------------- aim at the gunship
// a0/a1 = source x, ey = source line, A = speed level -> aim_vxl/h, aim_vyl/h
// Speeds come from one table of (long axis, short axis) pairs for three angles.
aim_at_player:
        sta t3
        jsr b_is_player
        jsr abs_dx              // |dx|
        sta t1
        lda #0
        rol                     // bit 0 = source right of player or level
        sta t2
        lda p_y
        clc
        adc #CHOP_CY
        sec
        sbc ey                  // target - source
        bcs !+
        eor #$ff
        adc #1
        jmp !dy+
!:      pha
        lda t2
        ora #2                  // bit 1 = target below source
        sta t2
        pla
!dy:    // A = |dy|; sort into long and short axis
        ldy #0
        cmp t1
        bcc !xlong+
        ldy #1
        sta t4                  // long = dy
        lda t1
        sta t5                  // short = dx
        jmp !bins+
!xlong: sta t5
        lda t1
        sta t4
!bins:  sty t1                  // 1 when y is the long axis
        // angle bin: short < long/4 -> 0, short < long*5/8 -> 1, else 2
        lda t4
        lsr
        lsr
        sta t0
        lda t5
        ldx #0
        cmp t0
        bcc !bin+
        lda t4
        lsr
        sta t0
        lsr
        lsr
        clc
        adc t0
        sta t0
        lda t5
        ldx #1
        cmp t0
        bcc !bin+
        ldx #2
!bin:   stx t0
        lda t3
        asl
        clc
        adc t3
        adc t0
        tax                     // level * 3 + bin
        lda t1
        bne !ylong+
        lda aim_lg_lo,x
        sta aim_vxl
        lda aim_lg_hi,x
        sta aim_vxh
        lda aim_sm_lo,x
        sta aim_vyl
        lda aim_sm_hi,x
        sta aim_vyh
        jmp !signs+
!ylong: lda aim_lg_lo,x
        sta aim_vyl
        lda aim_lg_hi,x
        sta aim_vyh
        lda aim_sm_lo,x
        sta aim_vxl
        lda aim_sm_hi,x
        sta aim_vxh
!signs: lda t2
        and #1
        beq !+                  // player is to the right: keep +x
        sec
        lda #0
        sbc aim_vxl
        sta aim_vxl
        lda #0
        sbc aim_vxh
        sta aim_vxh
!:      lda t2
        and #2
        bne !+
        sec
        lda #0
        sbc aim_vyl
        sta aim_vyl
        lda #0
        sbc aim_vyh
        sta aim_vyh
!:      rts

.function aimWord(level, bin, longAxis) {
    .var s = 384 + level * 96
    .if (bin == 0) .return longAxis ? s : 0
    .if (bin == 1) .return round(longAxis ? s * 0.89 : s * 0.45)
    .return round(s * 0.71)
}
aim_lg_lo: .for (var l = 0; l < 5; l++) .for (var b = 0; b < 3; b++) .byte <aimWord(l, b, true)
aim_lg_hi: .for (var l = 0; l < 5; l++) .for (var b = 0; b < 3; b++) .byte >aimWord(l, b, true)
aim_sm_lo: .for (var l = 0; l < 5; l++) .for (var b = 0; b < 3; b++) .byte <aimWord(l, b, false)
aim_sm_hi: .for (var l = 0; l < 5; l++) .for (var b = 0; b < 3; b++) .byte >aimWord(l, b, false)

// free enemy shot slot -> X, carry set when found
find_eshot:
        ldx #MAX_SHOT - 1
!:      lda s_type,x
        beq !yes+
        dex
        cpx #P_SHOTS
        bcs !-
        clc
        rts
!yes:   sec
        rts

// X = slot, A = type, a0/a1 = x, ey = line, aim_v* = velocity
launch_eshot:
        sta s_type,x
        lda a0
        sta s_xl,x
        lda a1
        sta s_xh,x
        lda ey
        sta s_yl,x
        lda #0
        sta s_xf,x
        sta s_yf,x
        sta s_age,x
        lda aim_vxl
        sta s_vxl,x
        lda aim_vxh
        sta s_vxh,x
        lda aim_vyl
        sta s_vyl,x
        lda aim_vyh
        sta s_vyh,x
        rts
