// ==============================================================================
// IRONFRONT - raster interrupts and the sprite multiplexer
//
// Hardware sprite 0 is the cursor. Sprites 1-7 are shared by up to 48 virtual
// sprites (units, helicopter shadows, explosions) per frame:
//   * the main loop collects virtual sprites, sorts them by Y (bucket pass on
//     Y/8, then an insertion pass) and assigns hardware slots round-robin into
//     the back display list. A sprite is dropped when its slot's previous user
//     is less than 24 lines above it.
//   * the frame IRQ (line 251) swaps in the new list, writes the cursor and the
//     first seven entries, plays music and sound, and starts the chain.
//   * each chained IRQ writes the next entries once their slot is free
//     (d_irq = max(y - 8, previous y in that slot + 22)).
// ==============================================================================

.label irq_end7 = $68

mux_init:
        lda #0
        sta mux_cur
        sta mux_end
        sta mux_ready
        sta back_count
        sta cur_spr_msb
        lda #MUXMAX
        sta mux_back
        lda #160
        sta cur_spr_x
        lda #140
        sta cur_spr_y
        lda #SPR_BASE + SPR_CURSOR
        sta cur_spr_ptr
        lda #1
        sta cur_spr_col
        rts

frame_irq:
        sta save_a
        stx save_x
        sty save_y
        lda #$ff
        sta $d019
        lda mux_ready           // a new display list is ready: swap it in
        beq !+
        lda mux_back
        ldx mux_cur
        sta mux_cur
        stx mux_back
        clc
        adc back_count
        sta mux_end
        lda #0
        sta mux_ready
!:      lda cur_spr_x
        sta $d000
        lda cur_spr_y
        sta $d001
        lda cur_spr_ptr
        sta SPRPTR
        lda cur_spr_col
        sta $d027
        lda cur_spr_msb
        sta $d010
        lda #0
        sta $d01c
        lda mux_end
        sec
        sbc mux_cur
        cmp #7
        bcc !+
        lda #7
!:      tax
        lda en_tab,x
        sta $d015
        clc
        txa
        adc mux_cur
        sta irq_end7
        ldx mux_cur
!:      cpx irq_end7
        beq !+
        jsr put_sprite
        jmp !-
!:      stx mux_idx
        cpx mux_end
        beq !+
        lda d_irq,x
        sta $d012
        lda #<mux_irq
        sta $fffe
        lda #>mux_irq
        sta $ffff
!:      inc frame
        bne !+
        inc frame_hi
!:      lda #1
        sta frame_flag
        lda opt_music
        beq !+
        jsr music_play
!:      jsr sfx_update
        ldy save_y
        ldx save_x
        lda save_a
        rti

mux_irq:
        sta save_a
        stx save_x
        sty save_y
        ldx mux_idx
mi_loop:
        jsr put_sprite
        cpx mux_end
        beq mi_last
        lda d_irq,x             // time to set another IRQ before this one is due?
        sec
        sbc #2
        cmp $d012
        bcs mi_sched
!:      lda $d012               // no: wait for its line, then write it now
        cmp d_irq,x
        bcc !-
        jmp mi_loop
mi_sched:
        lda d_irq,x
        sta $d012
        stx mux_idx
        lda #$ff
        sta $d019
        ldy save_y
        ldx save_x
        lda save_a
        rti
mi_last:
        lda #FRAME_LINE
        sta $d012
        lda #<frame_irq
        sta $fffe
        lda #>frame_irq
        sta $ffff
        lda #$ff
        sta $d019
        ldy save_y
        ldx save_x
        lda save_a
        rti

// Write display entry X to its hardware sprite; X += 1.
put_sprite:
        ldy d_slot2,x
        lda d_x,x
        sta $d000,y
        lda d_y,x
        sta $d001,y
        ldy d_slot,x
        lda d_ptr,x
        sta SPRPTR,y
        lda d_col,x
        sta $d027,y
        lda $d010
        and d_and,x
        ora d_msb,x
        sta $d010
        lda $d01c
        and d_and,x
        ora d_mcb,x
        sta $d01c
        inx
        rts

en_tab:  .byte %00000001, %00000011, %00000111, %00001111, %00011111, %00111111, %01111111, %11111111
bit_tab: .byte 1, 2, 4, 8, 16, 32, 64, 128

// ---------------------------------------------------------------- build
build_sprites:
!:      lda mux_ready           // the IRQ hasn't taken the last list yet
        bne !-
        lda #0
        sta vs_count
        jsr collect_units
        jsr collect_effects
        lda drag
        beq !+
        lda anc_xl              // box-select anchor
        clc
        adc #12
        sta t2
        lda anc_xh
        adc #0
        sta t3
        lda anc_y
        clc
        adc #40
        sta t4
        lda #SPR_CURSOR + 6
        sta t5
        lda #1
        sta t6
        lda #0
        sta t7
        jsr add_vs
!:      jsr sort_vs
        jmp assign_slots

// t2/t3 = sprite X, t4 = sprite Y, t5 = bank index, t6 = colour, t7 = multicolor
add_vs:
        ldy vs_count
        cpy #VMAX
        bcs !+
        lda t2
        sta v_x,y
        lda t3
        sta v_xh,y
        lda t4
        sta v_y,y
        lda t5
        clc
        adc #SPR_BASE
        sta v_ptr,y
        lda t6
        sta v_col,y
        lda t7
        sta v_mc,y
        inc vs_count
!:      rts

// Screen position of world point (A/Y = x lo/hi in t0/t1 order is set by the
// caller); in: t0/t1 = x, t8/t9 = y. Out: C=1 if off screen, else t2/t3/t4 set
// for a 24x21 sprite centred on the point.
to_screen:
        lda t0
        sec
        sbc cam_px_l
        sta t2
        lda t1
        sbc cam_px_h
        bne !off+
        lda t8
        sec
        sbc cam_py_l
        sta t4
        lda t9
        sbc cam_py_h
        bne !off+
        lda t4
        cmp #200
        bcs !off+
        adc #40
        sta t4
        lda t2
        clc
        adc #12
        sta t2
        lda #0
        adc #0
        sta t3
        clc
        rts
!off:   sec
        rts

collect_units:
        ldx #MAXU-1
cu_loop:
        lda u_type,x
        bne !+
        jmp cu_next
!:      lda u_xl,x
        sta t0
        lda u_xh,x
        sta t1
        lda u_yl,x
        sta t8
        lda u_yh,x
        sta t9
        jsr to_screen
        bcc !+
        jmp cu_next
!:      jsr unit_frame          // t5 = bank index
        ldy t5
        lda sprite_multicolor,y
        sta t7
        txa                     // owner colour
        and #16
        beq !+
        lda #ENEMY_COL
        bne !++
!:      lda #PLAYER_COL
!:      sta t6
        lda u_sel,x
        beq !+
        lda frame
        and #8
        beq !+
        lda #1                  // selected: blink white
        sta t6
!:      lda u_flash,x
        beq !+
        lda #2                  // hit: red flash
        sta t6
!:      lda u_type,x
        cmp #UT_HELI
        bne cu_add
        lda t4                  // helicopter: drawn 12 lines up, shadow on the ground
        pha
        sec
        sbc #12
        sta t4
        jsr add_vs
        pla
        sta t4
        lda opt_shadow
        beq cu_next
        lda t2
        clc
        adc #6
        sta t2
        lda t3
        adc #0
        sta t3
        lda u_dir,x
        clc
        adc #SPR_SHADOW
        sta t5
        lda #0
        sta t6
        sta t7
cu_add: jsr add_vs
cu_next:
        dex
        bmi !+
        jmp cu_loop
!:      rts

// t5 = sprite bank index for unit X
unit_frame:
        ldy u_type,x
        cpy #UT_SQUAD
        beq uf_squad
        cpy #UT_HELI
        beq uf_heli
        lda u_anim,x            // vehicles: base + dir*2 + tread frame
        lsr
        lsr
        and #1
        sta t5
        lda u_dir,x
        asl
        ora t5
        clc
        adc spr_base_tab,y
        sta t5
        rts
uf_heli:
        lda frame
        lsr
        lsr
        and #1
        sta t5
        lda u_dir,x
        asl
        ora t5
        clc
        adc #SPR_HELI
        sta t5
        rts
uf_squad:
        lda #SPR_SQUAD1         // fewer soldiers as the squad takes damage
        ldy u_hp,x
        cpy #21
        bcc !+
        lda #SPR_SQUAD2
        cpy #41
        bcc !+
        lda #SPR_SQUAD3
!:      sta t5
        lda u_state,x
        cmp #S_DYING
        bne !+
        lda u_timer,x           // 24..1 -> die frames 0..2
        eor #$ff
        clc
        adc #25
        lsr
        lsr
        lsr
        cmp #3
        bcc uf_die
        lda #2
uf_die: clc
        adc #12
        jmp uf_add
!:      lda u_fire,x
        beq uf_walk
        lsr
        lsr
        and #1
        ldy u_dir,x             // fire east for dir 0-3, west for 4-7
        cpy #4
        bcc !+
        ora #2
!:      ora #8
        jmp uf_add
uf_walk:
        ldy u_dir,x
        lda dir4_tab,y
        asl
        sta t6
        lda u_anim,x
        lsr
        lsr
        and #1
        ora t6
uf_add: clc
        adc t5
        sta t5
        rts

collect_effects:
        ldx #MAXF-1
!loop:  lda f_kind,x
        beq !next+
        lda f_xl,x
        sta t0
        lda f_xh,x
        sta t1
        lda f_yl,x
        sta t8
        lda f_yh,x
        sta t9
        jsr to_screen
        bcs !next+
        lda f_fr,x
        clc
        adc #SPR_EXPLOSION
        sta t5
        tay
        lda sprite_colours,y
        sta t6
        lda sprite_multicolor,y
        sta t7
        jsr add_vs
!next:  dex
        bpl !loop-
        rts

// Bucket the virtual sprites by Y/16, then one insertion pass.
sort_vs:
        ldx #15
        lda #$ff
!:      sta v_head,x
        dex
        bpl !-
        ldx vs_count
        dex
        bmi sv_done
!:      lda v_y,x
        lsr
        lsr
        lsr
        lsr
        tay
        lda v_head,y
        sta v_next,x
        txa
        sta v_head,y
        dex
        bpl !-
        lda #0
        sta t0
        tay
sv_bucket:
        ldx t0
        lda v_head,x
sv_chain:
        cmp #$ff
        beq !+
        sta v_order,y
        iny
        tax
        lda v_next,x
        jmp sv_chain
!:      inc t0
        lda t0
        cmp #32
        bne sv_bucket
        ldx #1
sv_ins: cpx vs_count
        bcs sv_done
        stx t3
        lda v_order,x
        sta t1
        tay
        lda v_y,y
        sta t2
        ldy t3
!:      cpy #0
        beq !+
        ldx v_order-1,y
        lda v_y,x
        cmp t2
        bcc !+
        beq !+
        txa
        sta v_order,y
        dey
        jmp !-
!:      lda t1
        sta v_order,y
        ldx t3
        inx
        jmp sv_ins
sv_done:
        rts

assign_slots:
        lda #0
        ldx #7
!:      sta slot_y,x
        dex
        bpl !-
        sta t2                  // t2 = sorted position
        lda #1
        sta t0                  // t0 = next hardware slot (1-7)
        lda mux_back
        sta t1                  // t1 = output entry
as_loop:
        ldx t2
        cpx vs_count
        bcc !+
        jmp as_done
!:      lda v_order,x
        tax
        ldy t0
        lda slot_y,y            // slot free 24 lines above?
        clc
        adc #24
        bcs as_skip
        cmp v_y,x
        beq !+
        bcc !+
as_skip:
        jmp as_drop
!:      lda v_y,x               // irq line = max(y - 8, slot y + 22)
        sec
        sbc #8
        sta t3
        lda slot_y,y
        clc
        adc #22
        cmp t3
        bcc !+
        sta t3
!:      lda v_y,x
        sta slot_y,y
        sty t4
        lda bit_tab,y
        sta t5
        eor #$ff
        sta t6
        lda v_xh,x
        beq !+
        lda t5
!:      sta t7
        lda v_mc,x
        beq !+
        lda t5
!:      sta t8
        ldy t1
        lda t3
        sta d_irq,y
        lda v_y,x
        sta d_y,y
        lda v_x,x
        sta d_x,y
        lda v_ptr,x
        sta d_ptr,y
        lda v_col,x
        sta d_col,y
        lda t6
        sta d_and,y
        lda t7
        sta d_msb,y
        lda t8
        sta d_mcb,y
        lda t4
        sta d_slot,y
        asl
        sta d_slot2,y
        inc t1
        ldy t4
        iny
        cpy #8
        bne !+
        ldy #1
!:      sty t0
as_drop:
        inc t2
        jmp as_loop
as_done:
        lda t1
        sec
        sbc mux_back
        sta back_count
        lda #1
        sta mux_ready
        rts
