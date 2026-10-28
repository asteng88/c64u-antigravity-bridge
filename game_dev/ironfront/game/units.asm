// ==============================================================================
// IRONFRONT - unit behaviour: movement, combat, harvesting; turrets
//
// Ground units move tile to tile (16 px steps) and reserve the next tile in
// OCC before they enter it. Steering is greedy towards the goal, trying the
// two neighbouring headings and then the two after that when blocked.
// Helicopters use the same steps but ignore OCC.
// ==============================================================================

units_update:
        ldx #MAXU-1
!:      lda u_type,x
        beq !+
        stx cu
        jsr unit_think
        ldx cu
!:      dex
        bpl !--
        rts

unit_think:
        lda u_reload,x
        beq !+
        dec u_reload,x
!:      lda u_flash,x
        beq !+
        dec u_flash,x
!:      lda u_fire,x
        beq !+
        dec u_fire,x
!:      lda u_state,x
        cmp #S_DYING
        bne !+
        dec u_timer,x           // dying: remove when the timer runs out
        bne ut_rts
        lda #0
        sta u_type,x
ut_rts: rts
!:      lda u_step,x            // finish the current step before deciding
        beq !+
        jmp move_tick
!:      ldy u_state,x
        lda st_hi,y
        pha
        lda st_lo,y
        pha
        rts

st_lo:  .byte <st_idle-1, <st_move-1, <st_attack-1, <st_hseek-1, <st_hmove-1, <st_harvest-1, <st_hreturn-1, <st_hunload-1
st_hi:  .byte >st_idle-1, >st_move-1, >st_attack-1, >st_hseek-1, >st_hmove-1, >st_harvest-1, >st_hreturn-1, >st_hunload-1

// C=1 on this unit's scan frame (every 16 frames, staggered)
scan_due:
        txa
        clc
        adc frame
        and #15
        cmp #1
        rts                     // C=0 only when the result is 0

st_idle:
        lda u_type,x
        cmp #UT_HARV
        bne !+
        inc u_timer,x           // an idle harvester goes back to work
        lda u_timer,x
        cmp #150
        bcc si_rts
        lda #S_HSEEK
        sta u_state,x
si_rts: rts
!:      jsr scan_due
        bcs si_rts
        jsr find_target
        bcs si_rts
        sta u_target,x
        lda #1
        sta u_auto,x
        lda #S_ATTACK
        sta u_state,x
        rts

st_move:
        lda u_auto,x            // attack-move: engage anything in sight
        cmp #2
        bne !+
        jsr scan_due
        bcs !+
        jsr find_target
        bcs !+
        sta u_target,x
        lda #S_ATTACK
        sta u_state,x
        rts
!:      jsr nav_step
        bcc !+
        lda #S_IDLE
        sta u_state,x
        lda #0
        sta u_timer,x
        sta u_auto,x
!:      rts

st_attack:
        jsr target_valid
        bcs sa_drop
        jsr target_dist
        sta t0
        ldy u_type,x
        lda range_tab,y
        cmp t0
        bcs sa_fire
        lda u_auto,x            // guard targets are dropped when they get away
        cmp #1
        bne !+
        lda range_tab,y
        clc
        adc #4
        cmp t0
        bcc sa_drop
!:      lda tx_b
        sta u_gx,x
        lda ty_b
        sta u_gy,x
        jsr nav_step
        rts
sa_fire:
        jsr dir_to_b
        bmi !+
        sta u_dir,x
!:      lda u_reload,x
        bne !+
        jmp fire
!:      rts
sa_drop:
        lda #$ff
        sta u_target,x
        lda u_auto,x
        cmp #2
        bne !+
        lda u_ax,x              // attack-move resumes towards its destination
        sta u_gx,x
        lda u_ay,x
        sta u_gy,x
        lda #S_MOVE
        sta u_state,x
        rts
!:      lda #0
        sta u_auto,x
        sta u_timer,x
        lda #S_IDLE
        sta u_state,x
        rts

// ---------------------------------------------------------------- harvester
st_hseek:
        jsr find_ore
        bcs !+
        lda tx_b
        sta u_gx,x
        lda ty_b
        sta u_gy,x
        lda #S_HMOVE
        sta u_state,x
        rts
!:      lda u_cargo,x           // no ore left anywhere: deliver what we have
        beq !+
        lda #S_HRETURN
        sta u_state,x
        rts
!:      lda #0
        sta u_timer,x
        lda #S_IDLE
        sta u_state,x
        rts

st_hmove:
        jsr nav_step
        bcc !++
        lda u_tx,x
        cmp u_gx,x
        bne !+
        lda u_ty,x
        cmp u_gy,x
        bne !+
        lda #0
        sta u_timer,x
        lda #S_HARVEST
        sta u_state,x
        rts
!:      lda #S_HSEEK
        sta u_state,x
!:      rts

st_harvest:
        inc u_anim,x            // scoop spins
        inc u_timer,x
        lda u_timer,x
        cmp #10
        bcc sh_rts
        lda #0
        sta u_timer,x
        lda u_tx,x
        sta tx_a
        ldy u_ty,x
        sty ty_a
        jsr set_gp
        ldy #0
        lda (gpo),y
        beq sh_empty
        sec
        sbc #1
        sta (gpo),y
        jsr ore_tile
        inc u_cargo,x
        lda u_cargo,x
        cmp #HARV_CAP
        bcc sh_rts
        lda #S_HRETURN
        sta u_state,x
sh_rts: rts
sh_empty:
        lda #S_HSEEK
        sta u_state,x
        rts

// A = ore left at tx_a/ty_a (gpt points at the tile): swap the tile picture
// when the ore level drops. Keeps X.
ore_tile:
        ldy #T_SAND4
        cmp #0
        beq !+
        ldy #T_ORE1
        cmp #9
        bcc !+
        ldy #T_ORE2
        cmp #17
        bcc !+
        ldy #T_ORE3
!:      tya
        ldy #0
        cmp (gpt),y
        beq !+
        jmp set_tile
!:      rts

st_hreturn:
        jsr find_refinery
        bcs sr_idle
        lda tx_b
        sta u_gx,x
        lda ty_b
        sta u_gy,x
        jsr goal_dist
        cmp #2
        bcc sr_unload
        jsr nav_step
        bcc sr_rts
        jsr goal_dist
        cmp #2
        bcc sr_unload
sr_rts: rts
sr_unload:
        lda #0
        sta u_timer,x
        lda #S_HUNLOAD
        sta u_state,x
        rts
sr_idle:
        lda #0
        sta u_timer,x
        lda #S_IDLE
        sta u_state,x
        rts

st_hunload:
        inc u_timer,x
        lda u_timer,x
        and #3
        bne hu_rts
        lda u_cargo,x
        beq hu_done
        dec u_cargo,x
        cpx #16
        bcs !+
        lda credits_l
        clc
        adc #ORE_VALUE
        sta credits_l
        bcc hu_rts
        inc credits_h
        rts
!:      lda ai_cr_l
        clc
        adc #ORE_VALUE
        sta ai_cr_l
        bcc hu_rts
        inc ai_cr_h
hu_rts: rts
hu_done:
        lda #S_HSEEK
        sta u_state,x
        rts

// Owner's refinery -> tx_b/ty_b = its unloading tile. C=1 if none.
find_refinery:
        txa
        and #16
        beq !+
        lda #1
!:      sta t0
        ldy #MAXB-1
!:      lda b_type,y
        cmp #B_REFINERY
        bne !+
        lda b_owner,y
        cmp t0
        bne !+
        lda b_tx,y
        sta tx_b
        lda b_ty,y
        clc
        adc #2
        sta ty_b
        clc
        rts
!:      dey
        bpl !--
        sec
        rts

// Nearest ore tile that is free (or our own) -> tx_b/ty_b. C=1 if none.
find_ore:
        lda #$ff
        sta t6
        txa
        clc
        adc #1
        sta t7
        lda #0
        sta t5
fo_row: lda u_ty,x              // t4 = row distance
        sec
        sbc t5
        bcs !+
        eor #$ff
        adc #1
!:      sta t4
        cmp t6
        bcs fo_next
        lda #0
        ldy t5
        jsr set_gp
        ldy #MAP_W-1
fo_col: lda (gpo),y
        beq fo_skip
        lda (gp),y
        beq !+
        cmp t7
        bne fo_skip
!:      tya
        sec
        sbc u_tx,x
        bcs !+
        eor #$ff
        adc #1
!:      clc
        adc t4
        cmp t6
        bcs fo_skip
        sta t6
        sty tx_b
        lda t5
        sta ty_b
fo_skip:
        dey
        bpl fo_col
fo_next:
        inc t5
        lda t5
        cmp #MAP_H
        bne fo_row
        lda t6
        cmp #$ff
        rts                     // C=1 when nothing was found

// ---------------------------------------------------------------- movement
// At a tile centre: step towards u_gx/u_gy. C=1 when there (or given up).
nav_step:
        lda u_tx,x
        cmp u_gx,x
        bne ns_go
        lda u_ty,x
        cmp u_gy,x
        bne ns_go
        lda #0
        sta u_stuck,x
        sec
        rts
ns_go:  lda u_gx,x
        sta tx_b
        lda u_gy,x
        sta ty_b
        jsr dir_to_b
        sta t3
        jsr try_dir
        bcc ns_ok
        lda #1                  // alternate which side is tried first
        sta t2
        txa
        eor frame_hi
        and #1
        beq !+
        lda #$ff
        sta t2
!:      lda t3
        clc
        adc t2
        and #7
        jsr try_dir
        bcc ns_ok
        lda t3
        sec
        sbc t2
        and #7
        jsr try_dir
        bcc ns_ok
        asl t2
        lda t3
        clc
        adc t2
        and #7
        jsr try_dir
        bcc ns_ok
        lda t3
        sec
        sbc t2
        and #7
        jsr try_dir
        bcc ns_ok
        inc u_stuck,x           // blocked all round: wait, then settle for close
        lda u_stuck,x
        cmp #30
        bcc ns_wait
        jsr goal_dist
        cmp #2
        bcc ns_give
        lda u_stuck,x
        cmp #150
        bcs ns_give
ns_wait:
        clc
        rts
ns_give:
        lda #0
        sta u_stuck,x
        sec
        rts
ns_ok:  lda #0
        sta u_stuck,x
        clc
        rts

// A = heading: start a step if the next tile is free. C=1 if blocked.
try_dir:
        sta t7
        tay
        lda u_tx,x
        clc
        adc dxt,y
        cmp #MAP_W
        bcs td_fail
        sta t4
        lda u_ty,x
        clc
        adc dyt,y
        cmp #MAP_H
        bcs td_fail
        sta t5
        lda u_type,x
        cmp #UT_HELI
        beq td_go
        lda t7                  // diagonal: don't squeeze between rocks/buildings
        and #1
        beq !+
        lda u_tx,x
        ldy t5
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp #$40
        bcs td_fail
        lda t4
        ldy u_ty,x
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp #$40
        bcs td_fail
!:      lda t4
        ldy t5
        jsr set_gp
        ldy #0
        lda (gp),y
        bne td_fail
        txa
        clc
        adc #1
        sta (gp),y
td_go:  lda t4
        sta u_nx,x
        lda t5
        sta u_ny,x
        lda #16
        sta u_step,x
        lda t7
        sta u_dir,x
        clc
        rts
td_fail:
        sec
        rts

// One frame of movement along the current step.
move_tick:
        ldy u_type,x
        lda u_sub,x
        clc
        adc speed_tab,y
        sta u_sub,x
        bcc mt_rts
        ldy u_dir,x
        lda dxt,y
        beq mt_y
        bmi !+
        inc u_xl,x
        bne mt_y
        inc u_xh,x
        jmp mt_y
!:      lda u_xl,x
        bne !+
        dec u_xh,x
!:      dec u_xl,x
mt_y:   lda dyt,y
        beq mt_step
        bmi !+
        inc u_yl,x
        bne mt_step
        inc u_yh,x
        jmp mt_step
!:      lda u_yl,x
        bne !+
        dec u_yh,x
!:      dec u_yl,x
mt_step:
        inc u_anim,x
        dec u_step,x
        bne mt_rts
        lda u_type,x            // arrived: let go of the tile behind
        cmp #UT_HELI
        beq !+
        txa
        clc
        adc #1
        sta t0
        lda u_tx,x
        ldy u_ty,x
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp t0
        bne !+
        tya
        sta (gp),y
!:      lda u_nx,x
        sta u_tx,x
        lda u_ny,x
        sta u_ty,x
mt_rts: rts

// heading from the unit's tile to tx_b/ty_b, $FF if the same tile
dir_to_b:
        ldy #3
        lda tx_b
        sec
        sbc u_tx,x
        beq !++
        bpl !+
        ldy #0
        beq !++
!:      ldy #6
!:      sty t8
        ldy #1
        lda ty_b
        sec
        sbc u_ty,x
        beq !++
        bpl !+
        ldy #0
        beq !++
!:      ldy #2
!:      tya
        clc
        adc t8
        tay
        lda dir_tab,y
        rts

// Chebyshev distance unit X -> tx_b/ty_b
target_dist:
        lda u_tx,x
        sec
        sbc tx_b
        bcs !+
        eor #$ff
        adc #1
!:      sta t8
        lda u_ty,x
        sec
        sbc ty_b
        bcs !+
        eor #$ff
        adc #1
!:      cmp t8
        bcs !+
        lda t8
!:      rts

goal_dist:
        lda u_gx,x
        sta tx_b
        lda u_gy,x
        sta ty_b
        jmp target_dist

// ---------------------------------------------------------------- combat
// u_target,x still worth shooting? Sets tgt and tx_b/ty_b. C=1 if not.
target_valid:
        lda u_target,x
        sta tgt
        cmp #$ff
        beq tv_bad
        and #$40
        bne tv_bld
        ldy tgt
        lda u_type,y
        beq tv_bad
        cmp #UT_HELI
        bne !+
        lda u_type,x            // can we hit aircraft?
        tay
        lda air_tab,y
        beq tv_bad
        ldy tgt
!:      lda u_state,y
        cmp #S_DYING
        beq tv_bad
        lda u_tx,y
        sta tx_b
        lda u_ty,y
        sta ty_b
        clc
        rts
tv_bld: lda tgt
        and #$3f
        tay
        lda b_type,y
        bmi tv_bad
        lda u_tx,x
        sta tx_a
        lda u_ty,x
        sta ty_a
        jsr clamp_bld
        lda t0
        sta tx_b
        lda t1
        sta ty_b
        clc
        rts
tv_bad: sec
        rts

// Y = structure: t0/t1 = its tile nearest to tx_a/ty_a
clamp_bld:
        lda b_tx,y
        cmp tx_a
        bcs !+
        adc #1
        cmp tx_a
        bcc !+
        lda tx_a
!:      sta t0
        lda b_ty,y
        cmp ty_a
        bcs !+
        adc #1
        cmp ty_a
        bcc !+
        lda ty_a
!:      sta t1
        rts

// Unit X: nearest enemy in sight -> A (unit, or $40+structure). C=1 if none.
find_target:
        lda u_tx,x
        sta tx_a
        lda u_ty,x
        sta ty_a
        ldy u_type,x
        lda range_tab,y
        clc
        adc #3                  // sight = range + 2
        sta t6
        lda air_tab,y
        sta t5
        txa
        lsr
        lsr
        lsr
        lsr
        and #1
        sta t3
        lda #1
        sta t2
        jsr scan_enemies
        lda t7
        cmp #$ff
        rts

// From tx_a/ty_a: nearest enemy of owner t3 closer than t6 tiles. t5 = can
// hit aircraft, t2 = include structures. -> t7 (or $FF), tx_b/ty_b. Keeps X.
scan_enemies:
        lda #$ff
        sta t7
        ldy #16
        lda t3
        beq !+
        ldy #0
!:      tya
        clc
        adc #16
        sta t9
se_unit:
        lda u_type,y
        beq se_unext
        cmp #UT_HELI
        bne !+
        lda t5
        beq se_unext
!:      lda u_state,y
        cmp #S_DYING
        beq se_unext
        lda u_tx,y
        sec
        sbc tx_a
        bcs !+
        eor #$ff
        adc #1
!:      sta t8
        lda u_ty,y
        sec
        sbc ty_a
        bcs !+
        eor #$ff
        adc #1
!:      cmp t8
        bcs !+
        lda t8
!:      cmp t6
        bcs se_unext
        sta t6
        sty t7
        lda u_tx,y
        sta tx_b
        lda u_ty,y
        sta ty_b
se_unext:
        iny
        cpy t9
        bne se_unit
        lda t2
        beq se_done
        ldy #MAXB-1
se_bld: lda b_type,y
        bmi se_bnext
        lda b_owner,y
        cmp t3
        beq se_bnext
        jsr clamp_bld
        lda t0
        sec
        sbc tx_a
        bcs !+
        eor #$ff
        adc #1
!:      sta t8
        lda t1
        sec
        sbc ty_a
        bcs !+
        eor #$ff
        adc #1
!:      cmp t8
        bcs !+
        lda t8
!:      cmp t6
        bcs se_bnext
        sta t6
        tya
        ora #$40
        sta t7
        lda t0
        sta tx_b
        lda t1
        sta ty_b
se_bnext:
        dey
        bpl se_bld
se_done:
        rts

// tgt -> Y = armour class: 0 infantry, 1 vehicle, 2 structure
target_class:
        ldy #2
        lda tgt
        and #$40
        bne !+
        ldy tgt
        lda u_type,y
        ldy #0
        cmp #UT_SQUAD
        beq !+
        iny
!:      rts

// Unit X fires at tgt (tx_b/ty_b = its tile).
fire:
        ldy u_type,x
        lda reload_tab,y
        sta u_reload,x
        lda #12
        sta u_fire,x
        jsr target_class
        sty t0
        lda u_type,x
        asl
        clc
        adc u_type,x
        adc t0
        tay
        lda dmg_tab,y
        sta t1
        stx t2
        lda u_type,x
        cmp #UT_TANK
        beq !+
        cmp #UT_HELI
        beq !+
        lda #SFX_SHOT
        .byte $2c               // bit abs: skip the next lda
!:      lda #SFX_CANNON
        sta t3
        jmp shoot

// Common to units and turrets: tgt is hit for t1 damage by t2 (unit, or
// $40+structure); t3 = sound. Keeps X.
shoot:
        txa
        pha
        lda t1
        pha
        lda t2
        pha
        jsr tile_visible
        bcs !+
        lda t3
        jsr sfx_play
!:      jsr hit_fx
        pla
        sta t2
        pla
        sta t1
        jsr apply_damage
        pla
        tax
        rts

// Small explosion on tgt, slightly off-centre.
hit_fx:
        lda tgt
        and #$40
        beq !+
        lda tgt
        and #$3f
        tax
        jsr bld_centre
        jmp !++
!:      ldx tgt
        lda u_xl,x
        sta t0
        lda u_xh,x
        sta t1
        lda u_yl,x
        sta t8
        lda u_yh,x
        sta t9
        lda u_type,x
        cmp #UT_HELI
        bne !+
        lda t8                  // helicopters fly 12 px up
        sec
        sbc #12
        sta t8
        bcs !+
        dec t9
!:      jsr rand
        and #7
        sec
        sbc #4
        clc
        adc t0
        sta t0
        jsr rand
        and #7
        sec
        sbc #4
        clc
        adc t8
        sta t8
        lda #FX_PUFF
        jmp spawn_fx

// tgt loses t1 hit points; t2 = attacker. Keeps X.
apply_damage:
        lda tgt
        and #$40
        bne ad_bld
        ldy tgt
        lda u_hp,y
        sec
        sbc t1
        bcc ad_kill
        beq ad_kill
        sta u_hp,y
        lda #6
        sta u_flash,y
        lda u_state,y           // an idle unit shoots back
        cmp #S_IDLE
        bne ad_rts
        lda u_type,y
        cmp #UT_HARV
        beq ad_rts
        lda t2
        and #$40
        bne !+
        stx t3
        ldx t2
        lda u_type,x
        ldx t3
        cmp #UT_HELI
        bne !+
        lda u_type,y
        tay
        lda air_tab,y
        beq ad_rts
        ldy tgt
!:      lda t2
        sta u_target,y
        lda #1
        sta u_auto,y
        lda #S_ATTACK
        sta u_state,y
ad_rts: rts
ad_kill:
        txa
        pha
        ldx tgt
        jsr kill_unit
        pla
        tax
        rts
ad_bld: lda tgt
        and #$3f
        tay
        lda b_hp,y
        sec
        sbc t1
        bcc ad_bkill
        beq ad_bkill
        sta b_hp,y
        lda b_owner,y
        bne ad_rts
        lda alert_t             // warn the player, at most every 5 s
        bne ad_rts
        lda #250
        sta alert_t
        lda #MSG_ALERT
        jmp show_msg
ad_bkill:
        txa
        pha
        tya
        tax
        jsr destroy_building
        pla
        tax
        rts

kill_unit:
        jsr free_occ
        lda #0
        sta u_step,x
        sta u_sel,x
        lda #S_DYING
        sta u_state,x
        lda u_type,x
        cmp #UT_SQUAD
        bne !+
        lda #24                 // three-frame fall
        sta u_timer,x
        rts
!:      lda #1
        sta u_timer,x
        lda u_xl,x
        sta t0
        lda u_xh,x
        sta t1
        lda u_yl,x
        sta t8
        lda u_yh,x
        sta t9
        lda #FX_BLAST
        jsr spawn_fx
        lda u_tx,x
        sta tx_b
        sta tx_a
        lda u_ty,x
        sta ty_b
        sta ty_a
        jsr tile_visible
        bcs !+
        lda #SFX_BOOM
        jsr sfx_play
!:      lda u_type,x            // scorch the sand under a wrecked vehicle
        cmp #UT_HELI
        beq !+
        lda tx_a
        ldy ty_a
        jsr set_gp
        ldy #0
        lda (gpt),y
        cmp #T_DIRT1
        bcs !+
        lda #T_CRATER
        jmp set_tile
!:      rts

// Release the unit's OCC cells.
free_occ:
        lda u_type,x
        cmp #UT_HELI
        beq fo_rts
        txa
        clc
        adc #1
        sta t0
        lda u_tx,x
        ldy u_ty,x
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp t0
        bne !+
        tya
        sta (gp),y
!:      lda u_nx,x
        ldy u_ny,x
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp t0
        bne fo_rts
        tya
        sta (gp),y
fo_rts: rts

// ---------------------------------------------------------------- turrets
buildings_update:
        ldx #MAXB-1
bu_loop:
        lda b_type,x
        cmp #B_TURRET
        bne bu_next
        lda b_reload,x
        beq !+
        dec b_reload,x
        jmp bu_next
!:      txa
        clc
        adc frame
        and #7
        bne bu_next
        lda b_tx,x
        sta tx_a
        lda b_ty,x
        sta ty_a
        lda #6                  // range 5
        sta t6
        lda #1
        sta t5
        lda b_owner,x
        sta t3
        lda #0
        sta t2
        jsr scan_enemies
        lda t7
        cmp #$ff
        beq bu_next
        sta tgt
        lda #45
        sta b_reload,x
        jsr target_class
        lda dmg_tab+UT_TURRET*3,y
        sta t1
        txa
        ora #$40
        sta t2
        lda #SFX_CANNON
        sta t3
        jsr shoot
bu_next:
        dex
        bpl bu_loop
        rts

rand:
        lda rnd
        asl
        rol rnd2
        bcc !+
        eor #$39
!:      sta rnd
        eor rnd2
        eor frame
        rts
