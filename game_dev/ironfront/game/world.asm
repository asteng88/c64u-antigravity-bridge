// ==============================================================================
// IRONFRONT - the battlefield: tile grids, char map, view drawing, spawning
// structures, units and explosions
// ==============================================================================

init_world:
        lda #0                  // clear the unit and structure tables
        tax
!:      sta $4400,x
        sta $4500,x
        sta $4600,x
        sta $4700,x
        inx
        bne !-
        ldx #MAXB-1
        lda #$ff
!:      sta b_type,x
        dex
        bpl !-
        ldx #MAXF-1
        lda #0
!:      sta f_kind,x
        dex
        bpl !-
        ldx #2
!:      lda #$ff
        sta q_item,x
        lda #0
        sta q_prog,x
        sta q_tick,x
        sta q_ready,x
        dex
        bpl !-

        // tile map -> TMAP, rocks -> OCC, ore levels -> ORE_AMT
        lda #<map_tiles
        sta ptr
        lda #>map_tiles
        sta ptr+1
        lda #0
        sta gp
        sta gpt
        sta gpo
        lda #>OCC
        sta gp+1
        lda #>TMAP
        sta gpt+1
        lda #>ORE_AMT
        sta gpo+1
        lda #4
        sta t0
        ldy #0
iw_copy:
        lda (ptr),y
        sta (gpt),y
        tax
        lda tile_flags,x
        pha
        and #TF_BLOCKED
        beq !+
        lda #$ff
!:      sta (gp),y
        pla
        lsr                     // ore level (bits 4-5) x 8
        and #$18
        sta (gpo),y
        iny
        bne iw_copy
        inc ptr+1
        inc gp+1
        inc gpt+1
        inc gpo+1
        dec t0
        bne iw_copy

        lda #0                  // expand every tile into the char map
        sta ty_a
!:      lda #0
        sta tx_a
!:      jsr draw_tile
        inc tx_a
        lda tx_a
        cmp #MAP_W
        bne !-
        inc ty_a
        lda ty_a
        cmp #MAP_H
        bne !--

        lda #<map_objects       // starting structures and units
        sta ptr3
        lda #>map_objects
        sta ptr3+1
iw_obj: ldy #0
        lda (ptr3),y
        cmp #$ff
        beq iw_done
        sta t9
        iny
        lda (ptr3),y
        sta sp_owner
        iny
        lda (ptr3),y
        sta tx_a
        iny
        lda (ptr3),y
        sta ty_a
        lda ptr3                // the spawn routines use ptr..ptr4
        pha
        lda ptr3+1
        pha
        lda t9
        cmp #K_TANK
        bcs !+
        sta sp_type             // structure: kind = block id
        jsr place_building
        jmp !++
!:      sec
        sbc #K_TANK-UT_TANK
        sta sp_type
        jsr spawn_unit
!:      pla
        sta ptr3+1
        pla
        clc
        adc #4
        sta ptr3
        bcc iw_obj
        inc ptr3+1
        jmp iw_obj
iw_done:
        lda #<3000
        sta credits_l
        lda #>3000
        sta credits_h
        lda #<2500
        sta ai_cr_l
        lda #>2500
        sta ai_cr_h
        lda #<WAVE_FIRST
        sta ai_wave_l
        lda #>WAVE_FIRST
        sta ai_wave_h
        lda #3
        sta ai_wave_size
        lda #0
        sta cam_x
        sta game_state
        sta quit_flag
        sta drag
        sta press
        sta plc_on
        sta msg_timer
        sta alert_t
        sta cur_xh
        sta sfx_pri
        sta sfx_rel
        sta view_dirty
        lda #64-VIEW_H          // start at the bottom-left: the player's base
        sta cam_y
        lda #$ff
        sta plc_ox
        sta hover_u
        sta hover_b
        sta hover_item
        sta shown_cr_l
        lda #128
        sta cur_xl
        lda #100
        sta cur_y
        jmp cam_pixels

// ---------------------------------------------------------------- grids
// A = tile x, Y = tile y -> gp/gpt/gpo point at that cell of OCC/TMAP/ORE_AMT
set_gp:
        clc
        adc tyoff_lo,y
        sta gp
        sta gpt
        sta gpo
        lda tyoff_hi,y
        ora #>OCC
        sta gp+1
        eor #(>OCC) ^ (>TMAP)
        sta gpt+1
        eor #(>TMAP) ^ (>ORE_AMT)
        sta gpo+1
        rts

// tx_a/ty_a -> ptr/ptr2 = char/colour map address of the tile's top-left char
cell_ptr:
        lda ty_a
        lsr
        pha
        lda #0
        ror
        sta ptr
        lda tx_a
        asl
        ora ptr
        sta ptr
        sta ptr2
        pla
        clc
        adc #>CHARMAP
        sta ptr+1
        clc
        adc #(>COLMAP) - (>CHARMAP)
        sta ptr2+1
        rts

// A = char row -> ptr/ptr2 = char/colour map row start
map_row:
        pha
        and #3
        tay
        lda mul64,y
        sta ptr
        sta ptr2
        pla
        lsr
        lsr
        clc
        adc #>CHARMAP
        sta ptr+1
        clc
        adc #(>COLMAP) - (>CHARMAP)
        sta ptr2+1
        rts

// Draw the tile at tx_a/ty_a into the char map. Keeps X.
draw_tile:
        lda tx_a
        ldy ty_a
        jsr set_gp
        jsr cell_ptr
        txa
        pha
        ldy #0
        lda (gpt),y
        tax
        lda tile_c0,x
        sta (ptr),y
        lda tile_col,x
        sta (ptr2),y
        iny
        lda tile_c1,x
        sta (ptr),y
        lda tile_col,x
        sta (ptr2),y
        ldy #64
        lda tile_c2,x
        sta (ptr),y
        lda tile_col,x
        sta (ptr2),y
        iny
        lda tile_c3,x
        sta (ptr),y
        lda tile_col,x
        sta (ptr2),y
        pla
        tax
        rts

// Change the tile at tx_a/ty_a to A and show it. Keeps X.
set_tile:
        pha
        lda tx_a
        ldy ty_a
        jsr set_gp
        pla
        ldy #0
        sta (gpt),y
        jsr draw_tile
        lda tx_a
        asl
        sta t0
        lda ty_a
        asl
        sta t1
        lda #2
        sta t2
        sta t3
        jmp refresh_rect

// Building X: draw its 4x4 chars into the char map in the owner's colour.
draw_block:
        lda b_tx,x
        sta tx_a
        lda b_ty,x
        sta ty_a
        jsr cell_ptr
        ldy b_type,x
        lda block_lo,y
        sta ptr3
        lda block_hi,y
        sta ptr3+1
        lda #PLAYER_COL | 8
        ldy b_owner,x
        beq !+
        lda #ENEMY_COL | 8
!:      sta t0
        lda #4
        sta t1
db_row: ldy #3
!:      lda (ptr3),y
        sta (ptr),y
        lda t0
        sta (ptr2),y
        dey
        bpl !-
        lda ptr3
        clc
        adc #4
        sta ptr3
        bcc !+
        inc ptr3+1
!:      lda ptr
        clc
        adc #64
        sta ptr
        sta ptr2
        bcc !+
        inc ptr+1
        inc ptr2+1
!:      dec t1
        bne db_row
        rts

// Building X: A -> its four OCC cells
mark_building:
        sta t0
        lda b_tx,x
        ldy b_ty,x
        jsr set_gp
        lda t0
        ldy #0
        sta (gp),y
        iny
        sta (gp),y
        ldy #32
        sta (gp),y
        iny
        sta (gp),y
        rts

refresh_building:
        lda b_tx,x
        asl
        sta t0
        lda b_ty,x
        asl
        sta t1
        lda #4
        sta t2
        sta t3
        jmp refresh_rect

// ---------------------------------------------------------------- view
draw_view:
        lda #0
        sta view_dirty
        lda cam_y
        jsr map_row
        lda ptr
        clc
        adc cam_x
        sta ptr
        sta ptr2
        lda #<SCREEN
        sta ptr3
        sta ptr4
        lda #>SCREEN
        sta ptr3+1
        lda #>COLRAM
        sta ptr4+1
        ldx #VIEW_H
dv_row: ldy #VIEW_W-1
!:      lda (ptr),y
        sta (ptr3),y
        lda (ptr2),y
        sta (ptr4),y
        dey
        bpl !-
        lda ptr
        clc
        adc #64
        sta ptr
        sta ptr2
        bcc !+
        inc ptr+1
        inc ptr2+1
!:      lda ptr3
        clc
        adc #40
        sta ptr3
        sta ptr4
        bcc !+
        inc ptr3+1
        inc ptr4+1
!:      dex
        bne dv_row
        jmp cam_pixels

// Copy map chars to the screen for the char rectangle t0,t1 (x,y), t2 x t3,
// clipped to the view. With t9 <> 0 it fills the visible part with the
// placement grid char in colour t9 instead. Keeps X.
refresh_rect:
        lda #0
        sta t9
fill_rect:
        lda t1
        sta t4
rr_row: lda t4
        sec
        sbc cam_y
        cmp #VIEW_H
        bcs rr_next
        tay
        lda scr_lo,y
        sta ptr3
        sta ptr4
        lda scr_hi,y
        sta ptr3+1
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta ptr4+1
        lda t4
        jsr map_row
        lda t0
        sta t6
        lda t2
        sta t7
rr_col: lda t6
        sec
        sbc cam_x
        cmp #VIEW_W
        bcs rr_cn
        sta t8
        lda t9
        bne rr_fill
        ldy t6
        lda (ptr),y
        ldy t8
        sta (ptr3),y
        ldy t6
        lda (ptr2),y
        ldy t8
        sta (ptr4),y
        jmp rr_cn
rr_fill:
        ldy t8
        lda #H_PLACE
        sta (ptr3),y
        lda t9
        sta (ptr4),y
rr_cn:  inc t6
        dec t7
        bne rr_col
rr_next:
        inc t4
        dec t3
        bne rr_row
        rts

cam_pixels:
        lda #0
        sta cam_px_h
        sta cam_py_h
        lda cam_x
        asl
        asl
        rol cam_px_h
        asl
        rol cam_px_h
        sta cam_px_l
        lda cam_y
        asl
        asl
        rol cam_py_h
        asl
        rol cam_py_h
        sta cam_py_l
        rts

// C=0 if tile tx_b/ty_b is on screen
tile_visible:
        lda cam_x
        lsr
        sta t8
        lda tx_b
        sec
        sbc t8
        cmp #VIEW_W/2
        bcs !+
        lda cam_y
        lsr
        sta t8
        lda ty_b
        sec
        sbc t8
        cmp #VIEW_H/2 + 1
!:      rts

// ---------------------------------------------------------------- spawning
// First free tile at or around tx_a/ty_a (7x7 spiral). C=1 if none. Keeps X.
find_free_near:
        lda #0
        sta t7
ff_loop:
        ldy t7
        cpy #49
        bcs ff_fail
        lda tx_a
        clc
        adc ring_dx,y
        cmp #MAP_W
        bcs ff_next
        sta t5
        lda ty_a
        clc
        adc ring_dy,y
        cmp #MAP_H
        bcs ff_next
        sta t6
        lda t5
        ldy t6
        jsr set_gp
        ldy #0
        lda (gp),y
        bne ff_next
        lda t5
        sta tx_a
        lda t6
        sta ty_a
        clc
        rts
ff_next:
        inc t7
        jmp ff_loop
ff_fail:
        sec
        rts

// sp_type (UT_*), sp_owner, tx_a/ty_a -> X = new unit. C=1 if no room.
spawn_unit:
        ldx #15
        lda sp_owner
        beq !+
        ldx #31
!:      lda #16
        sta t0
!:      lda u_type,x
        beq su_slot
        dex
        dec t0
        bne !-
        sec
        rts
su_slot:
        lda sp_type
        cmp #UT_HELI
        beq !+
        jsr find_free_near
        bcc !+
        rts
!:      lda #0
        sta u_step,x
        sta u_sub,x
        sta u_stuck,x
        sta u_auto,x
        sta u_anim,x
        sta u_fire,x
        sta u_sel,x
        sta u_flash,x
        sta u_cargo,x
        sta u_reload,x
        sta u_timer,x
        lda #$ff
        sta u_target,x
        lda #4                  // facing south
        sta u_dir,x
        lda sp_type
        sta u_type,x
        tay
        lda hp_tab,y
        sta u_hp,x
        lda #S_IDLE
        cpy #UT_HARV
        bne !+
        lda #S_HSEEK
!:      sta u_state,x
        lda tx_a
        sta u_tx,x
        sta u_nx,x
        sta u_gx,x
        sta u_ax,x
        lsr
        lsr
        lsr
        lsr
        sta u_xh,x
        lda tx_a
        asl
        asl
        asl
        asl
        ora #8
        sta u_xl,x
        lda ty_a
        sta u_ty,x
        sta u_ny,x
        sta u_gy,x
        sta u_ay,x
        lsr
        lsr
        lsr
        lsr
        sta u_yh,x
        lda ty_a
        asl
        asl
        asl
        asl
        ora #8
        sta u_yl,x
        cpy #UT_HELI
        beq !+
        lda tx_a
        ldy ty_a
        jsr set_gp
        txa
        clc
        adc #1
        ldy #0
        sta (gp),y
!:      clc
        rts

// sp_type (B_*), sp_owner, tx_a/ty_a -> X = new structure. C=1 if no room.
place_building:
        ldx #MAXB-1
!:      lda b_type,x
        bmi pb_slot
        dex
        bpl !-
        sec
        rts
pb_slot:
        lda sp_type
        sta b_type,x
        tay
        lda bhp_tab,y
        sta b_hp,x
        lda sp_owner
        sta b_owner,x
        lda tx_a
        sta b_tx,x
        lda ty_a
        sta b_ty,x
        lda #0
        sta b_reload,x
        txa
        ora #$40
        jsr mark_building
        jsr draw_block
        jsr refresh_building
        clc
        rts

// Structure X is destroyed: rubble, explosions, free its cells.
destroy_building:
        lda #0
        jsr mark_building
        lda b_tx,x
        sta tx_a
        lda b_ty,x
        sta ty_a
        lda #T_RUBBLE
        jsr set_tile
        inc tx_a
        lda #T_RUBBLE
        jsr set_tile
        inc ty_a
        lda #T_RUBBLE
        jsr set_tile
        dec tx_a
        lda #T_RUBBLE
        jsr set_tile
        jsr bld_centre
        lda #FX_BLAST
        jsr spawn_fx
        lda t0
        sec
        sbc #10
        sta t0
        lda t8
        sec
        sbc #8
        sta t8
        lda #FX_BLAST
        jsr spawn_fx
        lda t0
        clc
        adc #18
        sta t0
        lda #FX_BLAST
        jsr spawn_fx
        lda #$ff
        sta b_type,x
        lda b_tx,x
        sta tx_b
        lda b_ty,x
        sta ty_b
        jsr tile_visible
        bcs !+
        lda #SFX_BOOM
        jmp sfx_play
!:      rts

// Building X -> t0/t1, t8/t9 = world pixel centre
bld_centre:
        lda b_ty,x
        jsr tile_px
        clc
        adc #8
        sta t8
        lda t1
        adc #0
        sta t9
        lda b_tx,x
        jsr tile_px
        clc
        adc #8
        sta t0
        lda t1
        adc #0
        sta t1
        rts

// A = tile -> A = low byte of tile*16+8, t1 = high byte
tile_px:
        pha
        lsr
        lsr
        lsr
        lsr
        sta t1
        pla
        asl
        asl
        asl
        asl
        ora #8
        rts

// ---------------------------------------------------------------- explosions
// A = FX_*, t0/t1 = x, t8/t9 = y. Keeps X.
spawn_fx:
        ldy #MAXF-1
!:      pha
        lda f_kind,y
        beq !+
        pla
        dey
        bpl !-
        rts
!:      pla
        sta f_kind,y
        lda #0
        sta f_fr,y
        lda #3
        sta f_t,y
        lda t0
        sta f_xl,y
        lda t1
        sta f_xh,y
        lda t8
        sta f_yl,y
        lda t9
        sta f_yh,y
        rts

effects_update:
        ldx #MAXF-1
!loop:  lda f_kind,x
        beq !next+
        dec f_t,x
        bne !next+
        ldy f_kind,x
        lda fx_ticks,y
        sta f_t,x
        inc f_fr,x
        lda f_fr,x
        cmp fx_frames,y
        bcc !next+
        lda #0
        sta f_kind,x
!next:  dex
        bpl !loop-
        rts

fx_ticks:  .byte 0, 3, 5
fx_frames: .byte 0, 2, 6
