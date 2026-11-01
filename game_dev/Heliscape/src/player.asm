// HELISCAPE - the gunship: flight model, landing, damage, weapons, camera

update_player:
        lda p_invul
        beq !+
        dec p_invul
!:      lda p_flash
        beq !+
        dec p_flash
!:      lda p_cool
        beq !+
        dec p_cool
!:      lda p_state
        cmp #PS_FLY
        bne !+
        jmp pl_fly
!:      cmp #PS_LANDED
        bne !+
        jmp pl_landed
!:      cmp #PS_FALL
        bne !+
        jmp pl_fall
!:      jmp pl_dead

// ---------------------------------------------------------------- flight
pl_fly:
        jsr pl_steer_x
        jsr pl_steer_y
        jsr pl_turn
        jsr pl_move
        jsr pl_contact
        lda p_state
        cmp #PS_FALL
        bcs !+
        jmp pl_fire
!:      rts

pl_steer_x:
        lda joy
        and #J_LEFT
        beq !no_left+
        lda #FACE_L
        sta p_want
        lda #ACC_X
        ldx p_vxh
        bmi !+
        asl                     // braking against our own speed
!:      sta t0
        sec
        lda p_vxl
        sbc t0
        sta p_vxl
        lda p_vxh
        sbc #0
        sta p_vxh
        bpl !ok+
        cmp #>(-MAX_VX)
        bcc !clamp+
        bne !ok+
        lda p_vxl
        cmp #<(-MAX_VX)
        bcs !ok+
!clamp: lda #<(-MAX_VX)
        sta p_vxl
        lda #>(-MAX_VX)
        sta p_vxh
!ok:    rts
!no_left:
        lda joy
        and #J_RIGHT
        beq !no_right+
        lda #FACE_R
        sta p_want
        lda #ACC_X
        ldx p_vxh
        bpl !+
        asl
!:      clc
        adc p_vxl
        sta p_vxl
        lda p_vxh
        adc #0
        sta p_vxh
        bmi !ok-
        cmp #>MAX_VX
        bcc !ok-
        bne !+
        lda p_vxl
        cmp #<MAX_VX
        bcc !ok-
!:      lda #<MAX_VX
        sta p_vxl
        lda #>MAX_VX
        sta p_vxh
        rts
!no_right:
        // drag toward zero
        lda p_vxh
        bmi !neg+
        ora p_vxl
        beq !ok-
        sec
        lda p_vxl
        sbc #8
        sta p_vxl
        lda p_vxh
        sbc #0
        sta p_vxh
        bpl !ok-
        jmp !zero+
!neg:   clc
        lda p_vxl
        adc #8
        sta p_vxl
        lda p_vxh
        adc #0
        sta p_vxh
        bmi !ok-
!zero:  lda #0
        sta p_vxl
        sta p_vxh
        rts

pl_steer_y:
        lda joy
        and #J_UP
        beq !no_up+
        sec
        lda p_vyl
        sbc #ACC_Y
        sta p_vyl
        lda p_vyh
        sbc #0
        sta p_vyh
        bpl !ok+
        cmp #>(-MAX_VY)
        bcc !clamp+
        bne !ok+
        lda p_vyl
        cmp #<(-MAX_VY)
        bcs !ok+
!clamp: lda #<(-MAX_VY)
        sta p_vyl
        lda #>(-MAX_VY)
        sta p_vyh
!ok:    rts
!no_up: lda joy
        and #J_DOWN
        beq !no_down+
        clc
        lda p_vyl
        adc #ACC_Y
        sta p_vyl
        lda p_vyh
        adc #0
        sta p_vyh
        bmi !ok-
        cmp #>MAX_VY
        bcc !ok-
        bne !+
        lda p_vyl
        cmp #<MAX_VY
        bcc !ok-
!:      lda #<MAX_VY
        sta p_vyl
        lda #>MAX_VY
        sta p_vyh
        rts
!no_down:
        // rotor hover: bleed vertical speed
        lda p_vyh
        bmi !neg+
        ora p_vyl
        beq !ok-
        sec
        lda p_vyl
        sbc #$10
        sta p_vyl
        lda p_vyh
        sbc #0
        sta p_vyh
        bpl !ok-
        jmp !zero+
!neg:   clc
        lda p_vyl
        adc #$10
        sta p_vyl
        lda p_vyh
        adc #0
        sta p_vyh
        bmi !ok-
!zero:  lda #0
        sta p_vyl
        sta p_vyh
        rts

// facing: a change of heading swings through the head-on pose. Let go during the
// swing and the gunship stays head-on; keep holding and it carries on round.
pl_turn:
        lda joy
        and #J_LEFT | J_RIGHT
        bne !held+
        lda p_face
        cmp #FACE_F
        bne !tilt+
        sta p_want
        lda #TURN_T
        sta p_turn
        jmp !tilt+
!held:  lda p_face
        cmp p_want
        beq !tilt+
        cmp #FACE_F
        beq !front+
        lda #FACE_F
        sta p_face
        lda #TURN_T
        sta p_turn
        jmp !tilt+
!front: dec p_turn
        bne !tilt+
        lda p_want
        sta p_face
!tilt:  // nose-down pose when moving fast the way we face
        lda #0
        sta p_tilt
        lda p_face
        cmp #FACE_R
        bne !+
        lda p_vxh
        bmi !done+
        beq !done+
        inc p_tilt
        rts
!:      cmp #FACE_L
        bne !done+
        lda p_vxh
        bpl !done+
        cmp #$ff
        beq !done+
        inc p_tilt
!done:  rts

pl_move:
        clc
        lda p_xf
        adc p_vxl
        sta p_xf
        lda p_xl
        adc p_vxh
        sta p_xl
        lda p_vxh
        bmi !neg+
        lda p_xh
        adc #0
        jmp !+
!neg:   lda p_xh
        adc #$ff
!:      sta p_xh
        // world edges
        bmi !left+
        beq !lowpage+
        cmp #>(WORLD_PX - 24)
        bcc !y+
        lda p_xl
        cmp #<(WORLD_PX - 24)
        bcc !y+
        lda #<(WORLD_PX - 24)
        sta p_xl
        lda #>(WORLD_PX - 24)
        sta p_xh
        jmp !stopx+
!lowpage:
        lda p_xl
        cmp #24
        bcs !y+
!left:  lda #24
        sta p_xl
        lda #0
        sta p_xh
!stopx: lda #0
        sta p_vxl
        sta p_vxh
!y:     clc
        lda p_yf
        adc p_vyl
        sta p_yf
        lda p_y
        adc p_vyh
        sta p_y
        cmp #CHOP_CEIL
        bcs !+
        lda #CHOP_CEIL
        sta p_y
        lda #0
        sta p_vyl
        sta p_vyh
!:      rts

// world column of a0/a1 in A
col_of:
        lda a1
        sta t0
        lda a0
        lsr t0
        ror
        lsr t0
        ror
        lsr t0
        ror
        rts

// lowest Y allowed under the rotor span -> A
floor_under:
        lda #CHOP_GROUND
        sta t1
        sec
        lda p_xl
        sbc #20
        sta a0
        lda p_xh
        sbc #0
        sta a1
        jsr col_of
        tax
        lda WH,x
        cmp t1
        bcs !+
        sta t1
!:      jsr a_is_player
        jsr col_of
        tax
        lda WH,x
        cmp t1
        bcs !+
        sta t1
!:      clc
        lda p_xl
        adc #20
        sta a0
        lda p_xh
        adc #0
        sta a1
        jsr col_of
        tax
        lda WH,x
        cmp t1
        bcs !+
        sta t1
!:      lda t1
        rts

pl_contact:
        jsr floor_under
        cmp p_y
        beq !touch+
        bcc !touch+
        rts
!touch: cmp #CHOP_GROUND
        beq !ground+
        // into a building: bounce off it
        dec p_y
        dec p_y
        lda p_invul
        bne !+
        lda #1
        jsr hurt
!:      lda #<-$0100
        sta p_vyl
        lda #>-$0100
        sta p_vyh
        jmp reverse_vx

!ground:
        lda #CHOP_GROUND
        sta p_y
        // gentle enough?
        lda p_vyh
        bmi !air+
        cmp #>SAFE_VY
        bcc !softy+
        bne !hard+
        lda p_vyl
        cmp #<SAFE_VY
        bcs !hard+
!softy: lda p_vxh
        bpl !+
        // negate for the speed test
        lda p_vxl
        eor #$ff
        clc
        adc #1
        sta t0
        lda p_vxh
        eor #$ff
        adc #0
        jmp !cmp+
!:      ldy p_vxl
        sty t0
!cmp:   cmp #>SAFE_VX
        bcc !land+
        bne !hard+
        lda t0
        cmp #<SAFE_VX
        bcc !land+
!hard:  lda #2
        jsr hurt
        lda p_state
        cmp #PS_FLY
        bne !air+
        dec p_y
        dec p_y
        lda #<-$0100
        sta p_vyl
        lda #>-$0100
        sta p_vyh
!air:   rts

!land:  lda #PS_LANDED
        sta p_state
        lda #0
        sta p_vxl
        sta p_vxh
        sta p_vyl
        sta p_vyh
        sta p_yf
        sta p_tilt
        lda #FX_SMALL
        jsr request_fx
        // home base?
        lda #0
        sta p_at_base
        lda p_xh
        bne !field+
        lda p_xl
        cmp #BASE_MAX_X
        bcs !field+
        lda #1
        sta p_at_base
        rts
!field: jmp crush_pows

reverse_vx:
        sec
        lda #0
        sbc p_vxl
        sta p_vxl
        lda #0
        sbc p_vxh
        sta p_vxh
        rts

// ---------------------------------------------------------------- on the ground
pl_landed:
        lda joy
        and #J_LEFT
        beq !+
        lda #FACE_L
        sta p_want
!:      lda joy
        and #J_RIGHT
        beq !+
        lda #FACE_R
        sta p_want
!:      jsr pl_turn
        lda #0
        sta p_tilt
        lda joy
        and #J_UP
        beq !stay+
        lda #PS_FLY
        sta p_state
        lda #0
        sta p_at_base
        lda #<-$00C0
        sta p_vyl
        lda #>-$00C0
        sta p_vyh
        dec p_y
        rts
!stay:  jsr pl_fire
        lda p_at_base
        beq !done+
        // repairs, slower on the later levels
        ldx mission
        lda frame
        and lv_repair,x
        bne !+
        lda p_armor
        cmp #MAX_ARMOR
        bcs !+
        inc p_armor
        lda hud_dirty
        ora #1
        sta hud_dirty
!:      // passengers walk out one at a time
        lda p_cargo
        beq !done+
        lda frame
        and #15
        bne !done+
        jmp unload_one
!done:  rts

// ---------------------------------------------------------------- shot down
pl_fall:
        jsr pl_move
        clc
        lda p_vyl
        adc #$18
        sta p_vyl
        bcc !+
        inc p_vyh
!:      lda frame
        and #3
        bne !+
        jsr a_is_player
        lda p_y
        clc
        adc #10
        sta ey
        lda #EX_SMOKE
        jsr spawn_ex
!:      lda p_y
        cmp #CHOP_GROUND
        bcc !done+
        // impact
        jsr a_is_player
        lda #205
        sta ey
        lda #EX_BIG
        jsr spawn_ex
        lda #6
        sta flash
        lda #FX_BIG
        jsr request_fx
        lda #PS_DEAD
        sta p_state
        lda #100
        sta p_timer
        // everyone aboard is lost with the ship
        clc
        lda pow_lost
        adc p_cargo
        sta pow_lost
        lda #0
        sta p_cargo
        dec lives
        lda hud_dirty
        ora #1
        sta hud_dirty
!done:  rts

pl_dead:
        dec p_timer
        beq !+
        rts
!:      lda lives
        bne respawn
        jmp lose_game

respawn:
        jsr place_player
        lda #150
        sta p_invul
        // jump the camera home with the screen off for a moment
        lda #$0b
        sta $d011
        lda #0
        sta cam_l
        sta cam_h
        sta cam_dx
        jsr redraw_near
        lda #$1b
        sta $d011
        lda #$ff
        sta hud_dirty
        rts

place_player:
        lda #<START_X
        sta p_xl
        lda #>START_X
        sta p_xh
        lda #CHOP_GROUND
        sta p_y
        lda #0
        sta p_xf
        sta p_yf
        sta p_vxl
        sta p_vxh
        sta p_vyl
        sta p_vyh
        sta p_tilt
        sta p_flash
        lda #FACE_R
        sta p_face
        sta p_want
        lda #TURN_T
        sta p_turn
        lda #PS_LANDED
        sta p_state
        lda #1
        sta p_at_base
        lda #MAX_ARMOR
        sta p_armor
        rts

// ---------------------------------------------------------------- A = damage
hurt:
        ldx p_invul
        bne !done+
        ldx p_state
        cpx #PS_FALL
        bcs !done+
        sta t0
        lda p_armor
        sec
        sbc t0
        bcs !+
        lda #0
!:      sta p_armor
        lda #4
        sta p_flash
        lda #40
        sta p_invul
        lda hud_dirty
        ora #1
        sta hud_dirty
        lda #FX_HIT
        jsr request_fx
        lda p_armor
        bne !done+
        // going down
        lda #PS_FALL
        sta p_state
        lda #0
        sta p_invul
        sta p_at_base
        jsr a_is_player
        lda p_y
        clc
        adc #12
        sta ey
        lda #EX_BIG
        jsr spawn_ex
        lda #FX_BIG
        jsr request_fx
!done:  rts

// ---------------------------------------------------------------- weapons
pl_fire:
        lda joy
        and #J_FIRE
        beq !done+
        lda p_cool
        bne !done+
        // free player shot?
        ldx #P_SHOTS - 1
!:      lda s_type,x
        beq !free+
        dex
        bpl !-
!done:  rts
!free:  lda p_state
        cmp #PS_FLY
        bne !gun+
        lda joy
        and #J_DOWN
        bne !bomb+
        lda p_face
        cmp #FACE_F
        bne !gun+
        jmp !bomb+
!gun:   lda p_face
        cmp #FACE_F
        beq !done-              // landed and head-on: nothing to fire along
        lda #S_BULLET
        sta s_type,x
        lda #0
        sta s_age,x
        sta s_xf,x
        sta s_yf,x
        sta s_vxl,x
        sta s_vyh,x
        lda p_tilt
        beq !+
        lda #$50                // nose down: tracers sink a little
!:      sta s_vyl,x
        lda p_y
        clc
        adc #14
        sta s_yl,x
        lda p_face
        cmp #FACE_R
        bne !gun_l+
        clc
        lda p_xl
        adc #26
        sta s_xl,x
        lda p_xh
        adc #0
        sta s_xh,x
        lda p_vxh
        clc
        adc #6
        sta s_vxh,x
        jmp !fx+
!gun_l: sec
        lda p_xl
        sbc #26
        sta s_xl,x
        lda p_xh
        sbc #0
        sta s_xh,x
        lda p_vxh
        sec
        sbc #6
        sta s_vxh,x
!fx:    lda #7
        sta p_cool
        lda #FX_GUN
        jmp request_fx

!bomb:  lda #S_BOMB
        sta s_type,x
        lda #0
        sta s_age,x
        sta s_xf,x
        sta s_yf,x
        sta s_vyh,x
        lda #$80
        sta s_vyl,x
        lda p_vxl
        sta s_vxl,x
        lda p_vxh
        sta s_vxh,x
        lda p_xl
        sta s_xl,x
        lda p_xh
        sta s_xh,x
        lda p_y
        clc
        adc #19
        sta s_yl,x
        lda #26
        sta p_cool
        lda #FX_DROP
        jmp request_fx

// ---------------------------------------------------------------- camera leads the way we face
cam_lead_lo: .byte <(152 - 64), <152, <(152 + 64)
cam_lead_hi: .byte >(152 - 64), >152, >(152 + 64)

update_camera:
        lda p_state
        cmp #PS_DEAD
        beq !done+
        // target = x - lead, clamped to the world
        ldx p_face
        sec
        lda p_xl
        sbc cam_lead_lo,x
        sta a0
        lda p_xh
        sbc cam_lead_hi,x
        sta a1
        bpl !+
        lda #0
        sta a0
        sta a1
!:      lda a1
        cmp #>CAM_MAX
        bcc !+
        bne !max+
        lda a0
        cmp #<CAM_MAX
        bcc !+
!max:   lda #<CAM_MAX
        sta a0
        lda #>CAM_MAX
        sta a1
!:      lda cam_l
        sta b0
        lda cam_h
        sta b1
        jsr abs_dx
        php
        cmp #2
        bcc !still+
        lsr
        lsr
        lsr
        lsr
        clc
        adc #1
        cmp #4
        bcc !+
        lda #4
!:      sta t0
        plp
        bcc !back+
        lda t0
        sta cam_dx
        clc
        adc cam_l
        sta cam_l
        bcc !done+
        inc cam_h
!done:  rts
!back:  sec
        lda #0
        sbc t0
        sta cam_dx
        sec
        lda cam_l
        sbc t0
        sta cam_l
        bcs !done-
        dec cam_h
        rts
!still: plp
        rts
