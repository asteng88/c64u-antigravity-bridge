// HELISCAPE - tanks, flak turrets, jets and enemy helicopters

init_enemies:
        // everything off
        lda #0
        ldx #MAX_TANK - 1
!:      sta g_kind,x
        dex
        bpl !-
        ldx #MAX_AIR - 1
!:      sta a_kind,x
        dex
        bpl !-
        ldx #MAX_SHOT - 1
!:      sta s_type,x
        dex
        bpl !-
        ldx #MAX_EX - 1
!:      sta e_kind,x
        dex
        bpl !-
        ldx #MAX_POW - 1
!:      sta q_st,x
        dex
        bpl !-
        sta g_n
        // tanks and turrets from the level's layout record, after the camps
        ldy lvy
        lda (lvp),y
        sta t1
        iny
        sty lvy
!loop:  lda t1
        beq !done+
        ldy lvy
        lda (lvp),y
        sta t0                  // column
        iny
        lda (lvp),y
        sta t2                  // 0 turret, 1 tank, 2 fast tank
        iny
        sty lvy
        ldx mission
        ldy g_n
        lda t2
        sta g_speed,y
        bne !tank+
        lda #T_TURRET
        sta g_kind,y
        lda lv_turret_hp,x
        jmp !common+
!tank:  lda #T_TANK
        sta g_kind,y
        lda lv_tank_hp,x
!common:
        sta g_hp,y
        lda #0
        asl t0
        rol
        asl t0
        rol
        asl t0
        rol
        sta g_xh,y
        lda t0
        sta g_xl,y
        lda #2
        sta g_aim,y
        tya
        asl
        asl
        asl
        asl
        clc
        adc #40
        sta g_reload,y
        inc g_n
        dec t1
        jmp !loop-
!done:  ldx mission
        lda lv_jet_delay,x
        sta jet_timer
        lda lv_heli_delay,x
        sta heli_timer
        rts

// ---------------------------------------------------------------- ground units
update_ground:
        ldx #MAX_TANK - 1
!loop:  lda g_kind,x
        beq !next+
        stx xsave_s
        jsr ground_step
        ldx xsave_s
!next:  dex
        bpl !loop-
        rts

ground_step:
        lda g_xl,x
        sta a0
        lda g_xh,x
        sta a1
        jsr b_is_player
        jsr abs_dx              // carry set: unit right of player
        sta t3                  // |dx|
        php
        cmp #255
        bne !+
        plp
        rts                     // too far away to matter
!:      plp
        // barrel angle
        bcs !rt+
        // player to the right
        lda t3
        ldy #2
        cmp #16
        bcc !aim+
        ldy #3
        cmp #70
        bcc !aim+
        ldy #4
        bne !aim+
!rt:    lda t3
        ldy #2
        cmp #16
        bcc !aim+
        ldy #1
        cmp #70
        bcc !aim+
        ldy #0
!aim:   tya
        sta g_aim,x
        // drive toward the gunship, but keep a stand-off
        lda g_speed,x
        beq !fire+
        lda t3
        cmp #50
        bcc !fire+
        lda g_speed,x
        cmp #2
        bcs !go+
        lda frame
        and #1
        bne !fire+
!go:    lda g_aim,x
        cmp #2
        beq !fire+
        bcs !east+
        // west, but stay out of the home base
        lda g_xh,x
        cmp #>280
        bcc !fire+
        bne !+
        lda g_xl,x
        cmp #<280
        bcc !fire+
!:      lda g_xl,x
        bne !+
        dec g_xh,x
!:      dec g_xl,x
        jmp !fire+
!east:  inc g_xl,x
        bne !fire+
        inc g_xh,x
!fire:  jsr tank_runs_over_pows
        ldx xsave_s
        dec g_reload,x
        beq !+
        rts
!:      // reload, then shoot if it makes sense
        ldy mission
        lda g_kind,x
        cmp #T_TANK
        bne !+
        lda lv_reload_tank,y
        jmp !set+
!:      lda lv_reload_turret,y
!set:   sta g_reload,x
        lda p_state
        cmp #PS_FALL
        bcs !no+
        lda p_at_base
        bne !no+
        lda t3
        cmp #170
        bcs !no+
        // aim, from the top of the unit
        lda g_xl,x
        sta a0
        lda g_xh,x
        sta a1
        lda #199
        sta ey
        ldy mission
        lda lv_shot_speed,y
        jsr aim_at_player
        jsr find_eshot
        bcc !no+
        lda #S_FLAK
        jsr launch_eshot
        lda #FX_FLAK
        jsr request_fx
!no:    rts

// squads under the tracks: one figure every so often
tank_runs_over_pows:
        lda frame
        and #63
        bne !done+
        lda g_xl,x
        sta a0
        lda g_xh,x
        sta a1
        ldy #MAX_POW - 1
!loop:  lda q_st,y
        beq !next+
        lda q_xl,y
        sta b0
        lda q_xh,y
        sta b1
        jsr abs_dx
        cmp #10
        bcs !next+
        jmp pow_kill_one
!next:  dey
        bpl !loop-
!done:  rts

// ---------------------------------------------------------------- aircraft
update_air:
        jsr maybe_spawn
        ldx #MAX_AIR - 1
!loop:  lda a_kind,x
        beq !next+
        stx xsave_s
        cmp #A_JET
        bne !+
        jsr jet_step
        jmp !c+
!:      jsr heli_step
!c:     ldx xsave_s
        lda a_kind,x
        beq !next+
        jsr air_vs_player
        ldx xsave_s
!next:  dex
        bpl !loop-
        rts

maybe_spawn:
        lda frame
        and #3
        beq !+
!no:    rts
!:      lda p_state
        cmp #PS_FLY
        bne !no-
        // nothing attacks over the home base
        lda p_xh
        cmp #>300
        bcc !no-
        bne !+
        lda p_xl
        cmp #<300
        bcc !no-
!:      lda jet_timer
        beq !tryd+
        dec jet_timer
        bne !tryd+
        jsr spawn_jet
        ldx mission
        lda lv_jet_delay,x
        sta jet_timer
!tryd:  lda heli_timer
        beq !no-
        dec heli_timer
        bne !no-
        jsr spawn_heli
        ldx mission
        lda lv_heli_delay,x
        sta heli_timer
        rts

// free aircraft slot -> X, carry set when found
find_air:
        ldx #MAX_AIR - 1
!:      lda a_kind,x
        beq !yes+
        dex
        bpl !-
        clc
        rts
!yes:   sec
        rts

// A = distance: position slot X ahead of the player, or behind if there is no
// room; a_dir points it at the player.
air_entry:
        sta t0
        lda p_face
        cmp #FACE_L
        beq !from_left+
        // try from the east
        clc
        lda p_xl
        adc t0
        sta a_xl,x
        lda p_xh
        adc #0
        sta a_xh,x
        cmp #>(WORLD_PX - 64)
        bcs !from_left+
        lda #0
        sta a_dir,x
        rts
!from_left:
        sec
        lda p_xl
        sbc t0
        sta a_xl,x
        lda p_xh
        sbc #0
        sta a_xh,x
        lda #1
        sta a_dir,x
        rts

spawn_jet:
        jsr find_air
        bcc !done+
        lda #A_JET
        sta a_kind,x
        ldy mission
        lda lv_air_hp,y
        sta a_hp,x
        lda #0
        sta a_t,x
        lda #240
        jsr air_entry
        // at the gunship's height, more or less
        jsr random
        and #15
        sec
        sbc #8
        clc
        adc p_y
        cmp #52
        bcs !+
        lda #52
!:      cmp #AIR_Y_MAX - 12
        bcc !+
        lda #AIR_Y_MAX - 12
!:      sta a_y,x
!done:  rts

spawn_heli:
        jsr find_air
        bcc !done+
        lda #A_HELI
        sta a_kind,x
        ldy mission
        lda lv_air_hp,y
        clc
        adc #1
        sta a_hp,x
        lda #30
        sta a_t,x
        lda #220
        jsr air_entry
        jsr random
        and #63
        clc
        adc #54
        sta a_y,x
!done:  rts

jet_step:
        lda a_dir,x
        bne !east+
        sec
        lda a_xl,x
        sbc #4
        sta a_xl,x
        bcs !moved+
        dec a_xh,x
        jmp !moved+
!east:  clc
        lda a_xl,x
        adc #4
        sta a_xl,x
        bcc !moved+
        inc a_xh,x
!moved: // off the map?
        lda a_xh,x
        cmp #>WORLD_PX
        bcs !gone+
        lda a_xl,x
        sta a0
        lda a_xh,x
        sta a1
        jsr b_is_player
        jsr abs_dx
        sta t3
        // carry = jet east of player; flying the same way means it has passed
        lda #0
        rol
        cmp a_dir,x
        bne !closing+
        lda t3
        cmp #255
        bne !done+
!gone:  lda #A_NONE
        sta a_kind,x
!done:  rts
!closing:
        // one missile on the way in
        lda a_t,x
        bne !done-
        lda t3
        cmp #150
        bcs !done-
        lda #1
        sta a_t,x
        lda a_y,x
        clc
        adc #11
        sta ey
        lda #0
        sta aim_vxl
        sta aim_vyl
        sta aim_vyh
        lda a_dir,x
        beq !w+
        lda #5
        bne !+
!w:     lda #-5
!:      sta aim_vxh
        jsr find_eshot
        bcc !done-
        lda #S_MISSILE
        jsr launch_eshot
        lda #FX_FLAK
        jmp request_fx

heli_step:
        // creep toward the gunship
        lda a_xl,x
        sta a0
        lda a_xh,x
        sta a1
        jsr b_is_player
        jsr abs_dx
        sta t3
        lda #0
        rol
        sta t2                  // 1 = helicopter east of player
        eor #1
        sta a_dir,x             // nose toward the gunship
        lda frame
        and #1
        bne !skipx+
        lda t2
        beq !east+
        lda a_xl,x
        bne !+
        dec a_xh,x
!:      dec a_xl,x
        jmp !skipx+
!east:  inc a_xl,x
        bne !skipx+
        inc a_xh,x
!skipx: // and to its height, leaving room for the air band
        lda frame
        and #3
        bne !+
        lda a_y,x
        cmp p_y
        beq !+
        bcs !up+
        cmp #AIR_Y_MAX - 14
        bcs !+
        inc a_y,x
        jmp !+
!up:    dec a_y,x
!:      // shoot on the way in, bomb when overhead
        lda a_t,x
        beq !+
        dec a_t,x
        rts
!:      lda t3
        cmp #16
        bcc !bomb+
        cmp #130
        bcs !done+
        lda p_at_base
        bne !done+
        lda #70
        sta a_t,x
        lda a_y,x
        clc
        adc #11
        sta ey
        ldy mission
        lda lv_shot_speed,y
        jsr aim_at_player       // keeps a0/a1 = this helicopter
        ldx xsave_s
        jsr find_eshot
        bcc !done+
        lda #S_FLAK
        jsr launch_eshot
        lda #FX_FLAK
        jmp request_fx
!bomb:  lda #64
        sta a_t,x
        lda a_y,x
        clc
        adc #18
        sta ey
        lda #0
        sta aim_vxl
        sta aim_vxh
        sta aim_vyh
        lda #$80
        sta aim_vyl
        lda a_xl,x
        sta a0
        lda a_xh,x
        sta a1
        jsr find_eshot
        bcc !done+
        lda #S_EBOMB
        jsr launch_eshot
!done:  rts

// collision with the gunship
air_vs_player:
        lda p_state
        cmp #PS_FALL
        bcs !done+
        lda p_invul
        bne !done+
        lda a_xl,x
        sta a0
        lda a_xh,x
        sta a1
        jsr b_is_player
        jsr abs_dx
        cmp #28
        bcs !done+
        lda a_y,x
        sec
        sbc p_y
        bcs !+
        eor #$ff
        adc #1
!:      cmp #16
        bcs !done+
        // both hurt
        txa
        tay
        jsr air_destroy
        lda #3
        jmp hurt
!done:  rts
