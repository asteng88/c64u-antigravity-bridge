// ==============================================================================
// IRONFRONT - player interface: cursor, scrolling, selection and orders,
// structure placement, the sidebar (production, options, messages)
// ==============================================================================

.const SB_COL = 33              // sidebar text column (32 is the divider)

ui_update:
        jsr move_cursor
        jsr cursor_world
        lda frame               // hover test on alternate frames
        and #1
        bne !+
        jsr find_hover
!:        jsr handle_keys
        jsr handle_fire
        jsr set_cursor_sprite
        lda alert_t
        beq !+
        dec alert_t
!:      rts

// ---------------------------------------------------------------- cursor
move_cursor:
        lda joy
        and #$0f
        bne !+
        sta cur_hold
        rts
!:      lda cur_hold            // accelerate while held: 1..5 px per frame
        cmp #40
        bcs !+
        inc cur_hold
!:      lda cur_hold
        lsr
        lsr
        lsr
        clc
        adc #1
        sta t0
        lda joy
        and #4
        beq mc_right
        lda cur_xl
        sec
        sbc t0
        sta cur_xl
        lda cur_xh
        sbc #0
        sta cur_xh
        bpl mc_right
        lda #0
        sta cur_xl
        sta cur_xh
        jsr scroll_left
mc_right:
        lda joy
        and #8
        beq mc_up
        lda cur_xl
        clc
        adc t0
        sta cur_xl
        lda cur_xh
        adc #0
        sta cur_xh
        beq mc_up
        lda cur_xl
        cmp #<320
        bcc mc_up
        lda #<319
        sta cur_xl
        jsr scroll_right
mc_up:  lda joy
        and #1
        beq mc_down
        lda cur_y
        sec
        sbc t0
        sta cur_y
        bcs mc_down
        lda #0
        sta cur_y
        jsr scroll_up
mc_down:
        lda joy
        and #2
        beq mc_done
        lda cur_y
        clc
        adc t0
        sta cur_y
        cmp #200
        bcc mc_done
        lda #199
        sta cur_y
        jsr scroll_down
mc_done:
        rts

scroll_left:
        lda frame
        and #1
        bne !+
        lda cam_x
        beq !+
        dec cam_x
        inc view_dirty
!:      rts
scroll_right:
        lda frame
        and #1
        bne !+
        lda cam_x
        cmp #64-VIEW_W
        bcs !+
        inc cam_x
        inc view_dirty
!:      rts
scroll_up:
        lda frame
        and #1
        bne !+
        lda cam_y
        beq !+
        dec cam_y
        inc view_dirty
!:      rts
scroll_down:
        lda frame
        and #1
        bne !+
        lda cam_y
        cmp #64-VIEW_H
        bcs !+
        inc cam_y
        inc view_dirty
!:      rts

// world pixel and tile under the cursor (camera may move this frame)
cursor_world:
        jsr cam_pixels
        lda cam_px_l
        clc
        adc cur_xl
        sta wx_l
        lda cam_px_h
        adc cur_xh
        sta wx_h
        lda cam_py_l
        clc
        adc cur_y
        sta wy_l
        lda cam_py_h
        adc #0
        sta wy_h
        lda wx_h
        asl
        asl
        asl
        asl
        sta ctx
        lda wx_l
        lsr
        lsr
        lsr
        lsr
        ora ctx
        and #31
        sta ctx
        lda wy_h
        asl
        asl
        asl
        asl
        sta cty
        lda wy_l
        lsr
        lsr
        lsr
        lsr
        ora cty
        and #31
        sta cty
        rts

// hover_u = unit under the cursor, hover_b = structure under it
find_hover:
        lda #$ff
        sta hover_u
        sta hover_b
        lda cur_xh
        ora game_state
        beq !+
        rts
!:      ldx #MAXU-1
fh_loop:
        lda u_type,x
        beq fh_next
        lda u_state,x
        cmp #S_DYING
        beq fh_next
        lda u_xl,x              // |unit x - cursor x| < 8
        sec
        sbc wx_l
        sta t0
        lda u_xh,x
        sbc wx_h
        sta t1
        lda t0
        clc
        adc #8
        sta t0
        lda t1
        adc #0
        bne fh_next
        lda t0
        cmp #16
        bcs fh_next
        ldy #9                  // helicopters are drawn 12 px up
        lda u_type,x
        cmp #UT_HELI
        bne !+
        ldy #$fd
!:      sty t2
        lda u_yl,x
        sec
        sbc wy_l
        sta t0
        lda u_yh,x
        sbc wy_h
        sta t1
        lda t2
        bpl !+
        dec t1
!:      lda t0
        clc
        adc t2
        sta t0
        lda t1
        adc #0
        bne fh_next
        lda t0
        cmp #18
        bcs fh_next
        stx hover_u
        rts
fh_next:
        dex
        bpl fh_loop
        lda ctx
        ldy cty
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp #$40
        bcc fh_rts
        cmp #$ff
        beq fh_rts
        and #$3f
        sta hover_b
fh_rts: rts

handle_keys:
        lda keys_new
        and #KEY_F1 | KEY_O
        beq !+
        jsr toggle_options
!:      lda game_state
        bne hk_rts
        lda keys_new
        and #KEY_SPACE
        beq !++
        lda plc_on
        beq !+
        lda #0                  // SPACE cancels placement first
        sta plc_on
        beq !++
!:      jsr deselect_all
!:      lda keys_new
        and #KEY_A
        beq hk_rts
        jmp select_army
hk_rts: rts

handle_fire:
        lda joy_prev
        and #$10
        sta t1
        lda joy
        and #$10
        sta t0
        beq hf_up
        lda t1
        bne hf_held
        // pressed this frame
        lda game_state
        cmp #GS_WON
        bcc !+
        lda #1                  // after the battle: fire returns to the title
        sta quit_flag
        rts
!:      lda cur_xh
        beq !+
        jmp sidebar_click
!:      lda game_state
        bne hf_rts
        lda plc_on
        beq !+
        jmp try_place
!:      lda #1
        sta press
        lda #0
        sta drag
        lda cur_xl
        sta anc_xl
        lda cur_xh
        sta anc_xh
        lda cur_y
        sta anc_y
hf_rts: rts
hf_held:
        lda press
        beq hf_rts
        lda drag
        bne hf_rts
        lda cur_xl              // moved more than 6 px: box select
        sec
        sbc anc_xl
        bcs !+
        eor #$ff
        adc #1
!:      cmp #7
        bcs hf_drag
        lda cur_y
        sec
        sbc anc_y
        bcs !+
        eor #$ff
        adc #1
!:      cmp #7
        bcc hf_rts
hf_drag:
        lda #1
        sta drag
        rts
hf_up:  lda t1
        beq hf_rts
        lda press
        beq hf_rts
        lda #0
        sta press
        lda drag
        beq playfield_click
        lda #0
        sta drag
        jmp box_select

playfield_click:
        lda hover_u
        cmp #$ff
        beq pc_nounit
        cmp #16
        bcs pc_enemy
        jsr deselect_all        // own unit: select just this one
        ldx hover_u
        lda #1
        sta u_sel,x
        lda #SFX_CLICK
        jmp sfx_play
pc_enemy:
        sta tgt
        jmp order_attack
pc_nounit:
        lda hover_b
        cmp #$ff
        beq pc_ground
        tax
        lda b_owner,x
        beq pc_ground
        txa
        ora #$40
        sta tgt
        jmp order_attack
pc_ground:
        jmp order_move

deselect_all:
        lda #0
        ldx #15
!:      sta u_sel,x
        dex
        bpl !-
        rts

// A: every player combat unit
select_army:
        jsr deselect_all
        ldx #15
!:      lda u_type,x
        beq !+
        cmp #UT_HARV
        beq !+
        lda u_state,x
        cmp #S_DYING
        beq !+
        lda #1
        sta u_sel,x
!:      dex
        bpl !--
        lda #SFX_CLICK
        jmp sfx_play

box_select:
        lda anc_xh              // box in screen pixels, clipped to the playfield
        beq !+
        lda #255
        sta anc_xl
!:      lda cur_xh
        beq !+
        lda #255
        .byte $2c
!:      lda cur_xl
        cmp anc_xl              // t0..t1 = x range, t2..t3 = y range
        bcc !+
        sta t1
        lda anc_xl
        sta t0
        jmp !++
!:      sta t0
        lda anc_xl
        sta t1
!:      lda cur_y
        cmp anc_y
        bcc !+
        sta t3
        lda anc_y
        sta t2
        jmp !++
!:      sta t2
        lda anc_y
        sta t3
!:      jsr deselect_all
        lda #0
        sta t6
        ldx #15
bs_loop:
        lda u_type,x
        beq bs_next
        lda u_state,x
        cmp #S_DYING
        beq bs_next
        lda u_xl,x
        sec
        sbc cam_px_l
        sta t4
        lda u_xh,x
        sbc cam_px_h
        bne bs_next
        lda u_yl,x
        sec
        sbc cam_py_l
        sta t5
        lda u_yh,x
        sbc cam_py_h
        bne bs_next
        lda t4
        cmp t0
        bcc bs_next
        lda t1
        cmp t4
        bcc bs_next
        lda t5
        cmp t2
        bcc bs_next
        lda t3
        cmp t5
        bcc bs_next
        lda #1
        sta u_sel,x
        sta t6
bs_next:
        dex
        bpl bs_loop
        lda t6
        beq !+
        lda #SFX_CLICK
        jmp sfx_play
!:      rts

// selected units attack tgt
order_attack:
        lda #0
        sta t6
        ldx #15
oa_loop:
        lda u_sel,x
        beq oa_next
        ldy u_type,x
        lda range_tab,y
        beq oa_next
        lda tgt
        and #$40
        bne !+
        ldy tgt
        lda u_type,y
        cmp #UT_HELI
        bne !+
        ldy u_type,x
        lda air_tab,y
        beq oa_next
!:      lda tgt
        sta u_target,x
        lda #0
        sta u_auto,x
        lda #S_ATTACK
        sta u_state,x
        inc t6
oa_next:
        dex
        bpl oa_loop
        lda t6
        beq !+
        lda #SFX_CLICK
        jmp sfx_play
!:      rts

// selected units move to the cursor tile, spread around it
order_move:
        lda #0
        sta t6
        ldx #0
om_loop:
        lda u_sel,x
        beq om_next
        ldy t6
        lda ctx
        clc
        adc ring_dx,y
        cmp #MAP_W
        bcc !+
        lda ctx
!:      sta u_gx,x
        lda cty
        clc
        adc ring_dy,y
        cmp #MAP_H
        bcc !+
        lda cty
!:      sta u_gy,x
        inc t6
        lda #$ff
        sta u_target,x
        lda #0
        sta u_auto,x
        sta u_stuck,x
        lda #S_MOVE
        ldy u_type,x
        cpy #UT_HARV
        bne !+
        lda ctx                 // a harvester sent onto ore starts mining there
        ldy cty
        jsr set_gp
        ldy #0
        lda (gpo),y
        beq !+
        lda ctx
        sta u_gx,x
        lda cty
        sta u_gy,x
        lda #S_HMOVE
        .byte $2c
!:      lda #S_MOVE
        sta u_state,x
om_next:
        inx
        cpx #16
        bne om_loop
        lda t6
        beq !+
        lda #SFX_CLICK
        jmp sfx_play
!:      rts

set_cursor_sprite:
        lda #0                  // t0 = cursor frame
        sta t0
        lda cur_xh
        ora game_state
        ora plc_on
        ora drag
        bne cs_set
        lda hover_u
        cmp #16
        bcs !+
        lda #6                  // over own unit: select bracket
        sta t0
        bne cs_set
!:      ldx #15                 // anything selected?
!:      lda u_sel,x
        bne cs_order
        dex
        bpl !-
        bmi cs_set
cs_order:
        lda frame
        lsr
        lsr
        lsr
        and #1
        sta t1
        lda hover_u
        cmp #$ff
        bne cs_attack
        lda hover_b
        cmp #$ff
        beq cs_ground
        tax
        lda b_owner,x
        beq cs_ground
cs_attack:
        lda #3
        ora t1
        sta t0
        bne cs_set
cs_ground:
        lda ctx
        ldy cty
        jsr set_gp
        ldy #0
        lda (gp),y
        cmp #$ff
        bne !+
        lda #5                  // rock: can't go there
        sta t0
        bne cs_set
!:      lda #1
        ora t1
        sta t0
cs_set: ldy t0
        lda sprite_colours+SPR_CURSOR,y
        sta cur_spr_col
        tya
        clc
        adc #SPR_BASE + SPR_CURSOR
        sta cur_spr_ptr
        lda #24                 // pointer: tip at the cursor; others centred
        ldx #50
        cpy #0
        beq !+
        lda #12
        ldx #40
!:      stx t1
        clc
        adc cur_xl
        sta cur_spr_x
        lda cur_xh
        adc #0
        sta cur_spr_msb
        lda cur_y
        clc
        adc t1
        sta cur_spr_y
        rts

// ---------------------------------------------------------------- placement
// C=0 if a 2x2 structure fits with its top-left at ctx/cty
placement_valid:
        lda ctx
        cmp #MAP_W-1
        bcs pv_bad
        lda cty
        cmp #MAP_H-1
        bcs pv_bad
        lda ctx
        ldy cty
        jsr set_gp
        ldy #0
        jsr pv_cell
        bcs pv_bad
        ldy #1
        jsr pv_cell
        bcs pv_bad
        ldy #32
        jsr pv_cell
        bcs pv_bad
        ldy #33
        jsr pv_cell
        bcs pv_bad
        ldx #MAXB-1             // must be near one of our structures
!:      lda b_type,x
        bmi pv_next
        lda b_owner,x
        bne pv_next
        lda b_tx,x
        sec
        sbc ctx
        clc
        adc #4
        cmp #9
        bcs pv_next
        lda b_ty,x
        sec
        sbc cty
        clc
        adc #4
        cmp #9
        bcs pv_next
        clc
        rts
pv_next:
        dex
        bpl !-
pv_bad: sec
        rts
pv_cell:
        lda (gp),y
        bne !+
        lda (gpt),y
        tax
        lda tile_flags,x
        and #TF_BLOCKED | TF_NOBUILD
        beq !++
!:      sec
        rts
!:      clc
        rts

// Draw (or clear) the placement grid under the cursor.
place_overlay:
        lda plc_on
        beq po_clear
        lda cur_xh
        bne po_clear
        jsr placement_valid
        lda #0
        rol
        sta plc_ok              // 1 = blocked
        lda ctx
        cmp plc_ox
        bne !+
        lda cty
        cmp plc_oy
        bne !+
        lda plc_ok
        cmp plc_okd
        beq po_rts
!:      jsr po_restore
        lda ctx
        sta plc_ox
        asl
        sta t0
        lda cty
        sta plc_oy
        asl
        sta t1
        lda plc_ok
        sta plc_okd
        lda #4
        sta t2
        sta t3
        lda #5                  // green: fits, red: blocked
        ldx plc_ok
        beq !+
        lda #2
!:      sta t9
        jmp fill_rect
po_clear:
        jsr po_restore
        lda #$ff
        sta plc_ox
po_rts: rts
po_restore:
        lda plc_ox
        cmp #$ff
        beq po_rts
        asl
        sta t0
        lda plc_oy
        asl
        sta t1
        lda #4
        sta t2
        sta t3
        jmp refresh_rect

try_place:
        jsr placement_valid
        bcc !+
        lda #MSG_LOCKED
        jsr show_msg
        lda #SFX_ERROR
        jmp sfx_play
!:      ldy q_item
        lda item_kind,y
        sta sp_type
        lda #0
        sta sp_owner
        lda ctx
        sta tx_a
        lda cty
        sta ty_a
        jsr place_building
        lda #$ff
        sta q_item
        sta plc_ox              // the structure has replaced the grid
        lda #0
        sta q_ready
        sta plc_on
        lda #MSG_PLACED
        jsr show_msg
        lda #SFX_READY
        jmp sfx_play

// ---------------------------------------------------------------- production
production_update:
        ldx #0
        jsr queue_tick
        ldx #1
queue_tick:
        lda q_item,x
        bmi qt_rts
        lda q_ready,x
        bne qt_ready
        inc q_tick,x
        ldy q_item,x
        lda q_tick,x
        cmp item_time,y
        bcc qt_rts
        lda #0
        sta q_tick,x
        inc q_prog,x
        lda q_prog,x
        cmp #PROG_MAX
        bcc qt_rts
        lda #1
        sta q_ready,x
        cpx #0
        bne qt_rts
        lda #MSG_READY          // structure finished: waiting to be placed
        jsr show_msg
        lda #SFX_READY
        jmp sfx_play
qt_ready:
        cpx #1
        bne qt_rts
        lda #0
        sta sp_owner
        lda q_item+1
        jsr deliver_unit
        bcs !+
        lda #$ff
        sta q_item+1
        lda #0
        sta q_ready+1
        lda #MSG_UNIT
        jsr show_msg
        lda #SFX_READY
        jmp sfx_play
!:      lda frame               // no room or no factory: keep trying
        and #127
        bne qt_rts
        lda #MSG_FULL
        jmp show_msg
qt_rts: rts

// A = unit item, sp_owner = owner: roll it out of the right structure.
// C=1 if there is no such structure or no room.
deliver_unit:
        tay
        lda item_kind,y
        sta sp_type
        lda item_req,y
        sta t0
        ldx #MAXB-1
!:      lda b_type,x
        cmp t0
        bne !+
        lda b_owner,x
        cmp sp_owner
        beq du_found
!:      dex
        bpl !--
        sec
        rts
du_found:
        lda b_tx,x
        sta tx_a
        lda b_ty,x
        sta ty_a
        lda sp_type
        cmp #UT_HELI
        beq !+
        inc ty_a                // ground units roll out of the front
        inc ty_a
!:      jmp spawn_unit

// ---------------------------------------------------------------- sidebar
// A = screen row -> ptr3/ptr4 = screen/colour address of the sidebar text
sb_row:
        tay
        lda scr_lo,y
        clc
        adc #SB_COL
        sta ptr3
        sta ptr4
        lda scr_hi,y
        adc #0
        sta ptr3+1
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta ptr4+1
        rts

// 7 chars from ptr to ptr3 in colour t0
print7:
        ldy #6
!:      lda (ptr),y
        sta (ptr3),y
        lda t0
        sta (ptr4),y
        dey
        bpl !-
        rts

// A = row: blank it (black)
clear_row:
        jsr sb_row
        ldy #6
!:      lda #32
        sta (ptr3),y
        lda #0
        sta (ptr4),y
        dey
        bpl !-
        rts

// A = row, X = text offset in sb_text, Y = colour
print_at:
        sty t0
        stx t1
        jsr sb_row
        lda t1
        clc
        adc #<sb_text
        sta ptr
        lda #>sb_text
        adc #0
        sta ptr+1
        jmp print7

sidebar_init:
        ldx #24
!:      txa                     // divider down column 32, rest blank
        pha
        tay
        lda scr_lo,y
        sta ptr3
        sta ptr4
        lda scr_hi,y
        sta ptr3+1
        clc
        adc #(>COLRAM) - (>SCREEN)
        sta ptr4+1
        ldy #32
        lda #H_VLINE
        sta (ptr3),y
        lda #0
        sta (ptr4),y
        ldy #39
!:      lda #32
        sta (ptr3),y
        lda #0
        sta (ptr4),y
        dey
        cpy #32
        bne !-
        pla
        tax
        dex
        bpl !--
        lda #1
        jsr hline_row
        lda #22
        jsr hline_row
        lda #0
        ldx #SBT_CREDIT
        ldy #0
        jsr print_at
        lda #24
        ldx #SBT_OPTIONS
        ldy #0
        jsr print_at
        lda #0                  // price digits for every item
        sta sb_next
        sta t3
!:      ldy t3
        lda item_cost_l,y
        sta t0
        lda item_cost_h,y
        sta t1
        jsr to_decimal
        lda t3
        asl
        asl
        clc
        adc t3
        tay
        ldx #0
!:      lda num_buf,x
        sta price_buf,y
        iny
        inx
        cpx #5
        bne !-
        inc t3
        lda t3
        cmp #ITEM_COUNT
        bne !--
        lda #$ff
        sta shown_cr_l
        jmp sidebar_draw_page

hline_row:
        jsr sb_row
        ldy #6
!:      lda #H_HLINE
        sta (ptr3),y
        lda #0
        sta (ptr4),y
        dey
        bpl !-
        rts

sidebar_update:
        lda #$ff                // item under the cursor
        sta hover_item
        lda cur_xh
        beq !+
        lda cur_y
        lsr
        lsr
        lsr
        sec
        sbc #2
        cmp #ITEM_COUNT*2
        bcs !+
        lsr
        sta hover_item
!:      lda credits_l
        cmp shown_cr_l
        bne !+
        lda credits_h
        cmp shown_cr_h
        beq !++
!:      jsr draw_credits
!:      lda msg_timer
        beq !+
        dec msg_timer
        bne !+
        lda #23
        jsr clear_row
!:      lda game_state
        bne !+
        jmp draw_items_step
!:      rts

draw_credits:
        lda credits_l
        sta shown_cr_l
        sta t0
        lda credits_h
        sta shown_cr_h
        sta t1
        jsr to_decimal
        lda #0
        jsr sb_row
        ldy #6
        ldx #4
!:      lda num_buf,x
        sta (ptr3),y
        lda #0
        sta (ptr4),y
        dey
        dex
        bpl !-
        rts

// t0/t1 -> num_buf: 5 screen-code digits, leading zeros as spaces
to_decimal:
        ldx #0
td_digit:
        ldy #0
!:      lda t0
        sec
        sbc pow10_lo,x
        sta t2
        lda t1
        sbc pow10_hi,x
        bcc !+
        sta t1
        lda t2
        sta t0
        iny
        bne !-
!:      tya
        ora #$30
        sta num_buf,x
        inx
        cpx #5
        bne td_digit
        ldx #0
!:      lda num_buf,x
        cmp #$30
        bne !+
        lda #32
        sta num_buf,x
        inx
        cpx #4
        bne !-
!:      rts

draw_page_rows:
        ldx #2
!:      txa
        pha
        jsr clear_row
        pla
        tax
        inx
        cpx #22
        bne !-
        rts

// production list, options or the end-of-battle page
sidebar_draw_page:
        jsr draw_page_rows
        lda game_state
        bne !+
        jmp draw_items
!:      cmp #GS_OPTIONS
        beq draw_options
        lda #6
        ldx #SBT_MISSION
        ldy #1
        jsr print_at
        lda game_state
        cmp #GS_WON
        bne !+
        lda #7
        ldx #SBT_SUCCESS
        ldy #5
        jsr print_at
        jmp !++
!:      lda #7
        ldx #SBT_FAILED
        ldy #2
        jsr print_at
!:      lda #11
        ldx #SBT_PRESS
        ldy #1
        jsr print_at
        lda #12
        ldx #SBT_FIRE
        ldy #1
        jmp print_at

draw_options:
        lda #3
        ldx #SBT_OPTIONS
        ldy #1
        jsr print_at
        lda #6
        ldx #SBT_SHADOWS
        ldy #0
        jsr print_at
        ldx #SBT_ON
        lda opt_shadow
        bne !+
        ldx #SBT_OFF
!:      lda #7
        ldy #1
        jsr print_at
        lda #10
        ldx #SBT_MUSIC
        ldy #0
        jsr print_at
        ldx #SBT_ON
        lda opt_music
        bne !+
        ldx #SBT_OFF
!:      lda #11
        ldy #1
        jsr print_at
        lda #14
        ldx #SBT_RESUME
        ldy #0
        jsr print_at
        lda #17
        ldx #SBT_QUIT
        ldy #0
        jmp print_at

// t3 = item: C=0 if its structure exists (player). Uses have_bld.
item_available:
        ldy t3
        ldx item_req,y
        lda have_bld,x
        eor #1
        cmp #1                  // C=1 when missing
        rts

// have_bld[B_*] = 1 for each structure type the player owns
scan_have:
        ldx #5
        lda #0
!:      sta have_bld,x
        dex
        bpl !-
        ldx #MAXB-1
!:      ldy b_type,x
        bmi !+
        lda b_owner,x
        bne !+
        lda #1
        sta have_bld,y
!:      dex
        bpl !--
        rts

// whole list (after a click or page change)
draw_items:
        jsr scan_have
        lda #0
        sta t3
!:      jsr draw_item
        inc t3
        lda t3
        cmp #ITEM_COUNT
        bne !-
        rts

// two items per frame, so the list never costs a whole frame
draw_items_step:
        lda sb_next
        bne !+
        jsr scan_have
!:      lda sb_next
        asl
        sta t3
        jsr draw_item
        inc t3
        jsr draw_item
        inc sb_next
        lda sb_next
        cmp #ITEM_COUNT/2
        bcc !+
        lda #0
        sta sb_next
!:      rts

// t3 = item
draw_item:
        lda t3                  // name row
        asl
        clc
        adc #2
        sta t5
        lda #0                  // t0 = colour: black, red if locked, white if busy
        sta t0
        jsr item_available
        bcc !+
        lda #2
        sta t0
!:      ldx #0
        lda t3
        cmp #5
        bcc !+
        inx
!:      stx t6                  // queue for this item
        lda q_item,x
        cmp t3
        bne !+
        lda #1
        sta t0
!:      lda t3
        cmp hover_item
        bne !+
        lda #1
        sta t0
!:      lda t5
        jsr sb_row
        lda t3
        asl
        asl
        asl
        sec
        sbc t3                  // x7
        clc
        adc #<item_names
        sta ptr
        lda #>item_names
        adc #0
        sta ptr+1
        jsr print7
        inc t5                  // second row: progress, READY or price
        lda t5
        jsr sb_row
        ldx t6
        lda q_item,x
        cmp t3
        bne di_price
        lda q_ready,x
        beq di_bar
        lda frame
        and #16
        beq !+
        lda #1
!:      sta t0
        lda #<(sb_text+SBT_READY)
        sta ptr
        lda #>(sb_text+SBT_READY)
        sta ptr+1
        jsr print7
        jmp di_next
di_bar: lda q_prog,x
        sta t7
        ldy #0
!:      lda t7                  // full blocks, one partial, then blanks
        cmp #8
        bcc !+
        sbc #8
        sta t7
        lda #H_BAR8
        sta (ptr3),y
        lda #5
        sta (ptr4),y
        iny
        bne !-
!:      tax
        lda bar_chars,x
        sta (ptr3),y
        lda #5
        sta (ptr4),y
        iny
!:      cpy #7
        bcs di_next
        lda #32
        sta (ptr3),y
        iny
        bne !-
di_price:
        ldy t3
        lda credits_l           // red when we can't afford it
        cmp item_cost_l,y
        lda credits_h
        sbc item_cost_h,y
        lda #0
        bcs !+
        lda #2
!:      sta t7
        lda t3                  // price digits were worked out once, at start
        asl
        asl
        clc
        adc t3
        tax
        ldy #2
!:      lda price_buf,x
        sta (ptr3),y
        lda t7
        sta (ptr4),y
        inx
        iny
        cpy #7
        bne !-
        lda #32
        ldy #0
        sta (ptr3),y
        iny
        sta (ptr3),y
di_next:
        rts

bar_chars: .byte 32, H_BAR1, H_BAR2, H_BAR3, H_BAR4, H_BAR5, H_BAR6, H_BAR7

sidebar_click:
        lda cur_y
        lsr
        lsr
        lsr
        cmp #24
        bne !+
        jmp toggle_options
!:      ldx game_state
        beq sc_items
        cpx #GS_OPTIONS
        bne sc_rts
        cmp #6                  // options page
        beq sc_shadow
        cmp #7
        beq sc_shadow
        cmp #10
        beq sc_music
        cmp #11
        beq sc_music
        cmp #14
        bne !+
        jmp toggle_options
!:      cmp #17
        bne sc_rts
        lda #1
        sta quit_flag
sc_rts: rts
sc_shadow:
        lda opt_shadow
        eor #1
        sta opt_shadow
        jmp sc_redraw
sc_music:
        lda opt_music
        eor #1
        sta opt_music
        jsr apply_music_option
sc_redraw:
        lda #SFX_CLICK
        jsr sfx_play
        jmp sidebar_draw_page
sc_items:
        lda hover_item
        cmp #$ff
        beq sc_rts
        sta t3
        ldx #0
        cmp #5
        bcc !+
        inx
!:      lda q_item,x
        cmp t3
        bne sc_new
        lda q_ready,x           // a finished structure: pick it up to place it
        beq sc_rts
        cpx #0
        bne sc_rts
        lda #1
        sta plc_on
        lda #$ff
        sta plc_ox
        lda #SFX_CLICK
        jmp sfx_play
sc_new: lda q_item,x
        cmp #$ff
        beq !+
        lda #MSG_BUSY
        jmp sc_error
!:      stx t6
        jsr item_available
        bcc !+
        lda #MSG_LOCKED
        jmp sc_error
!:      ldy t3
        lda credits_l
        sec
        sbc item_cost_l,y
        sta t0
        lda credits_h
        sbc item_cost_h,y
        bcs !+
        lda #MSG_CASH
        jmp sc_error
!:      sta credits_h
        lda t0
        sta credits_l
        ldx t6
        lda t3
        sta q_item,x
        lda #0
        sta q_prog,x
        sta q_tick,x
        sta q_ready,x
        lda #SFX_CLICK
        jsr sfx_play
        jmp draw_items
sc_error:
        jsr show_msg
        lda #SFX_ERROR
        jmp sfx_play

toggle_options:
        lda game_state
        cmp #GS_WON
        bcs !+
        eor #GS_OPTIONS
        sta game_state
        lda #0
        sta drag
        sta press
        lda #SFX_CLICK
        jsr sfx_play
        jmp sidebar_draw_page
!:      rts

apply_music_option:
        lda opt_music
        bne !+
        lda #1                  // off: the driver leaves all voices alone
        sta music_voice_off
        sta music_voice_off+1
        sta music_voice_off+2
        lda #0
        sta $d404
        sta $d40b
        lda sfx_pri
        bne amo_rts
        sta $d412
        rts
!:      lda #0
        sta music_voice_off
        sta music_voice_off+1
        lda sfx_pri
        ora sfx_rel
        bne amo_rts
        sta music_voice_off+2
amo_rts:
        rts

// A = MSG_*: show it on row 23 for 3 seconds
show_msg:
        sta t2                  // x7 = x8 - x1
        asl
        asl
        asl
        sec
        sbc t2
        clc
        adc #<msg_text
        sta ptr
        lda #>msg_text
        adc #0
        sta ptr+1
        lda #23
        jsr sb_row
        lda #1
        sta t0
        jsr print7
        lda #150
        sta msg_timer
        rts
