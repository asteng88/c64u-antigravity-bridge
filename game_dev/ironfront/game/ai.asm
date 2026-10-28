// ==============================================================================
// IRONFRONT - the enemy commander
//
// Builds units from its own credits (harvesting plus a small trickle) using
// whichever of its structures still stand, keeps one harvester working, and
// every WAVE_GAP frames sends its idle army at a random player target once it
// has ai_wave_size units. Waves grow by one unit each time, up to ten.
// Idle enemy units defend on their own (they scan like the player's).
// ==============================================================================

ai_update:
        lda frame               // trickle income: 3 credits every 32 frames
        and #31
        bne !+
        lda ai_cr_l
        clc
        adc #3
        sta ai_cr_l
        bcc !+
        inc ai_cr_h
!:      lda q_item+2
        bmi ai_choose
        inc q_tick+2            // building something
        ldy q_item+2
        lda q_tick+2
        cmp item_time,y
        bcc ai_waves
        lda #0
        sta q_tick+2
        lda q_prog+2
        cmp #PROG_MAX
        bcs !+
        inc q_prog+2
        jmp ai_waves
!:      lda #1
        sta sp_owner
        lda q_item+2
        jsr deliver_unit
        bcs ai_waves
        lda #$ff
        sta q_item+2
        jmp ai_waves
ai_choose:
        lda frame
        and #63
        bne ai_waves
        jsr ai_harvesters
        bne !+
        lda #ITEM_HARV          // always keep a harvester running
        bne ai_try
!:      jsr rand
        and #7
        tay
        lda ai_pick,y
ai_try: sta t3
        jsr ai_has_req
        bcs ai_waves
        ldy t3
        lda ai_cr_l
        sec
        sbc item_cost_l,y
        sta t0
        lda ai_cr_h
        sbc item_cost_h,y
        bcc ai_waves
        sta ai_cr_h
        lda t0
        sta ai_cr_l
        lda t3
        sta q_item+2
        lda #0
        sta q_prog+2
        sta q_tick+2

ai_waves:
        lda frame
        and #63
        bne aw_rts
        lda ai_wave_l
        sec
        sbc #64
        sta ai_wave_l
        lda ai_wave_h
        sbc #0
        sta ai_wave_h
        bcs aw_rts
        lda #0                  // count the idle army
        sta t5
        ldx #31
!:      lda u_type,x
        beq !+
        cmp #UT_HARV
        beq !+
        lda u_state,x
        cmp #S_IDLE
        bne !+
        inc t5
!:      dex
        cpx #16
        bcs !--
        lda t5
        cmp ai_wave_size
        bcs aw_launch
        lda #<400               // not enough yet: look again in 8 s
        sta ai_wave_l
        lda #>400
        sta ai_wave_h
aw_rts: rts
aw_launch:
        jsr ai_pick_target
        bcs aw_rts
        lda #0
        sta t6
        ldx #16
aw_loop:
        lda u_type,x
        beq aw_next
        cmp #UT_HARV
        beq aw_next
        lda u_state,x
        cmp #S_IDLE
        bne aw_next
        ldy t6
        lda tx_b
        clc
        adc ring_dx,y
        cmp #MAP_W
        bcc !+
        lda tx_b
!:      sta u_ax,x
        sta u_gx,x
        lda ty_b
        clc
        adc ring_dy,y
        cmp #MAP_H
        bcc !+
        lda ty_b
!:      sta u_ay,x
        sta u_gy,x
        lda #2                  // attack-move
        sta u_auto,x
        lda #$ff
        sta u_target,x
        lda #0
        sta u_stuck,x
        lda #S_MOVE
        sta u_state,x
        inc t6
aw_next:
        inx
        cpx #32
        bne aw_loop
        lda ai_wave_size
        cmp #10
        bcs !+
        inc ai_wave_size
!:      lda #<WAVE_GAP
        sta ai_wave_l
        lda #>WAVE_GAP
        sta ai_wave_h
        rts

// A = enemy harvesters (Z set if none)
ai_harvesters:
        lda #0
        sta t0
        ldx #31
!:      lda u_type,x
        cmp #UT_HARV
        bne !+
        inc t0
!:      dex
        cpx #16
        bcs !--
        lda t0
        rts

// t3 = item: C=0 if the enemy owns the structure that makes it
ai_has_req:
        ldy t3
        lda item_req,y
        sta t4
        ldx #MAXB-1
!:      lda b_type,x
        cmp t4
        bne !+
        lda b_owner,x
        beq !+
        clc
        rts
!:      dex
        bpl !--
        sec
        rts

// A random player structure (or unit) -> tx_b/ty_b. C=1 if nothing is left.
ai_pick_target:
        jsr rand
        and #31
        sta t0
        lda #MAXB
        sta t1
!:      ldx t0
        cpx #MAXB
        bcc !+
        ldx #0
        stx t0
!:      lda b_type,x
        bmi !+
        lda b_owner,x
        bne !+
        lda b_tx,x
        sta tx_b
        lda b_ty,x
        sta ty_b
        clc
        rts
!:      inc t0
        dec t1
        bne !---
        ldx #15
!:      lda u_type,x
        beq !+
        lda u_tx,x
        sta tx_b
        lda u_ty,x
        sta ty_b
        clc
        rts
!:      dex
        bpl !--
        sec
        rts
