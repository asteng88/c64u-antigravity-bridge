// HELISCAPE - prisoners

// free squad slot -> Y, carry set when found
find_pow:
        ldy #MAX_POW - 1
!:      lda q_st,y
        beq !yes+
        dey
        bpl !-
        clc
        rts
!yes:   sec
        rts

update_pows:
        // opened camps release a squad every so often
        inc pow_spawn
        lda pow_spawn
        and #31
        bne !squads+
        ldx c_n
!camp:  dex
        bmi !squads+
        lda c_hp,x
        bne !camp-
        lda c_wait,x
        beq !camp-
        lda c_delay,x
        beq !+
        dec c_delay,x
        jmp !camp-
!:      jsr find_pow
        bcc !squads+
        // up to three figures
        lda c_wait,x
        cmp #3
        bcc !+
        lda #3
!:      sta q_n,y
        sta t0
        sec
        lda c_wait,x
        sbc t0
        sta c_wait,x
        lda #P_IDLE
        sta q_st,y
        lda #0
        sta q_t,y
        sta q_dir,y
        // out of the ruins, a little apart from the last squad
        lda c_col,x
        sta t0
        lda #0
        asl t0
        rol
        asl t0
        rol
        asl t0
        rol
        sta t1
        tya
        asl
        asl
        asl
        clc
        adc #8
        adc t0
        sta q_xl,y
        lda t1
        adc #0
        sta q_xh,y
!squads:
        ldx #MAX_POW - 1
!loop:  lda q_st,x
        beq !next+
        stx xsave_s
        jsr squad_step
        ldx xsave_s
!next:  dex
        bpl !loop-
        rts

squad_step:
        cmp #P_WALK
        bne !+
        jmp squad_walk
!:      lda q_xl,x
        sta a0
        lda q_xh,x
        sta a1
        jsr b_is_player
        jsr abs_dx
        sta t3
        lda #0
        rol
        sta t2                  // 1 = squad east of the chopper
        // does the gunship wait for them?
        lda p_state
        cmp #PS_LANDED
        bne !wave+
        lda p_at_base
        bne !wave+
        lda p_cargo
        cmp #MAX_CARGO
        bcs !wave+
        lda t3
        cmp #240
        bcs !wave+
        lda #P_RUN
        sta q_st,x
        // at the door?
        lda t3
        cmp #8
        bcc !board+
        lda t2
        beq !east+
        lda #1
        sta q_dir,x
        lda q_xl,x
        bne !+
        dec q_xh,x
!:      dec q_xl,x
        rts
!east:  lda #0
        sta q_dir,x
        inc q_xl,x
        bne !+
        inc q_xh,x
!:      rts
!wave:  lda #P_IDLE
        sta q_st,x
        rts
!board: lda q_t,x
        beq !+
        dec q_t,x
        rts
!:      lda #10
        sta q_t,x
        inc p_cargo
        dec q_n,x
        bne !+
        lda #P_FREE
        sta q_st,x
!:      lda hud_dirty
        ora #1
        sta hud_dirty
        lda #CH_BOARD + 1
        sta ch_req
        rts

squad_walk:
        lda #1
        sta q_dir,x
        lda q_xh,x
        bne !+
        lda q_xl,x
        cmp #DOOR_X
        bcs !+
        // inside: safe
        lda #P_FREE
        sta q_st,x
        inc pow_saved
        lda #1
        jsr add_score
        lda #CH_SAVED + 1
        sta ch_req
        rts
!:      lda q_xl,x
        bne !+
        dec q_xh,x
!:      dec q_xl,x
        rts

// a passenger steps off at base
unload_one:
        jsr find_pow
        bcs !+
        rts
!:      dec p_cargo
        lda #P_WALK
        sta q_st,y
        lda #1
        sta q_n,y
        sta q_dir,y
        sec
        lda p_xl
        sbc #12
        sta q_xl,y
        lda p_xh
        sbc #0
        sta q_xh,y
        lda hud_dirty
        ora #1
        sta hud_dirty
        rts

// ---------------------------------------------------------------- casualties. Y = squad; Y survives.
pow_kill_one:
        lda q_n,y
        sec
        sbc #1
        sta q_n,y
        bne !+
        lda #P_FREE
        sta q_st,y
!:      inc pow_lost
pow_lost_fx:
        lda hud_dirty
        ora #1
        sta hud_dirty
        lda #CH_LOST + 1
        sta ch_req
        rts

pow_kill_all:
        clc
        lda pow_lost
        adc q_n,y
        sta pow_lost
        lda #P_FREE
        sta q_st,y
        jmp pow_lost_fx

// the gunship came down on top of them
crush_pows:
        jsr a_is_player
        ldy #MAX_POW - 1
!loop:  lda q_st,y
        beq !next+
        lda q_xl,y
        sta b0
        lda q_xh,y
        sta b1
        jsr abs_dx
        cmp #14
        bcs !next+
        jsr pow_kill_all
!next:  dey
        bpl !loop-
        rts
