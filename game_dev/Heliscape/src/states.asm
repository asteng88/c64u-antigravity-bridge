// HELISCAPE - title, level flow

palette_names_lo: .byte <pn1, <pn2, <pn3, <pn4, <pn5, <pn6
palette_names_hi: .byte >pn1, >pn2, >pn3, >pn4, >pn5, >pn6
pn1:    .text "OPERATION DUSK"
        .byte 0
pn2:    .text "NIGHT RAID"
        .byte 0
pn3:    .text "FIRST LIGHT"
        .byte 0
pn4:    .text "HIGH NOON"
        .byte 0
pn5:    .text "STORM FRONT"
        .byte 0
pn6:    .text "BLOOD MOON"
        .byte 0
t_level: .text "LEVEL"
        .byte 0
t_need: .text "POWS 00  MUST SAVE 00"
        .byte 0
t_sub:  .text "RESCUE PROTOCOL"
        .byte 0
t_fire: .text "PRESS FIRE TO FLY"
        .byte 0
t_help: .text "JOY OR WASD+SPACE  DOWN+FIRE: BOMB"
        .byte 0
t_done: .text "LEVEL COMPLETE"
        .byte 0
t_win:  .text "ALL LEVELS FLOWN - WELL DONE"
        .byte 0
t_over: .text "MISSION FAILED"
        .byte 0
t_lost: .text "TOO MANY LOST"
        .byte 0
t_cont: .text "PRESS FIRE"
        .byte 0
t_tap:  .text "TAP BACK: FACE AHEAD"
        .byte 0
t_hi:   .text "HI"
        .byte 0

// ---------------------------------------------------------------- build a whole scene with the screen off
setup_scene:
        lda #$0b
        sta $d011
        lda #0
        sta pow_total
        sta pow_saved
        sta pow_lost
        sta cam_l
        sta cam_h
        sta cam_dx
        sta flash
        sta paused
        // the world's look repeats every PALETTES levels
        lda mission
!:      cmp #PALETTES
        bcc !+
        sbc #PALETTES
        bcs !-
!:      sta palette
        jsr load_palette
        jsr build_world
        jsr init_enemies
        jsr draw_sky
        jsr load_row_colours
        jsr redraw_near
        jsr redraw_back
        jsr redraw_clouds
        lda #1
        sta clouds_on
        rts

show_screen:
        lda #0
        sta vflag
!:      lda vflag               // switch on during the bottom border
        beq !-
        lda #0
        sta vflag
        lda #$1b
        sta $d011
        rts

clear_sky_top:
        lda #0
        sta clouds_on
        lda #D016_STATIC
        sta d_cloud
        ldx #79
        lda #32
!:      sta ROW(0),x
        dex
        bpl !-
        rts

// ptr = tune block: copy it to where the driver runs. Music must be off.
load_tune:
        lda #0
        sta ptr2
        lda #>music_init
        sta ptr2+1
        ldx #>TUNE_SIZE
        ldy #0
!:      lda (ptr),y
        sta (ptr2),y
        iny
        bne !-
        inc ptr+1
        inc ptr2+1
        dex
        bne !-
        rts

// mission + 1 as three screen codes in level_d
level_digits:
        lda mission
        clc
        adc #1
        ldx #48
!:      cmp #100
        bcc !+
        sbc #100
        inx
        bne !-
!:      stx level_d
        ldx #48
!:      cmp #10
        bcc !+
        sbc #10
        inx
        bne !-
!:      stx level_d + 1
        ora #48
        sta level_d + 2
        rts

// ---------------------------------------------------------------- title
enter_title:
        lda #ST_TITLE
        sta game_state
        lda #0
        sta sfx_on
        sta music_on
        sta mission
        sta p_flash
        sta p_invul
        sta title_t
        jsr sid_silence
        jsr hs_to_hi
        jsr setup_scene
        jsr clear_hud
        PRINT(t_tap, 22, 3, 3)
        PRINT(t_hi, 22, 27, 3)
        lda #<(ROW(22) + 30)
        sta ptr
        lda #>(ROW(22) + 30)
        sta ptr+1
        lda hi2
        jsr put_bcd
        lda hi1
        jsr put_bcd
        lda hi0
        jsr put_bcd
        ldx #5
        lda #1
!:      sta CROW(22) + 30,x
        dex
        bpl !-
        PRINT(t_fire, 23, 11, 7)
        PRINT(t_help, 24, 3, 3)
        lda title_page
        beq !+
        jsr draw_score_page
        jmp !page+
!:      jsr draw_logo_page
!page:  // the gunship flies the attract loop
        lda #PS_FLY
        sta p_state
        lda #FACE_R
        sta p_face
        sta p_want
        lda #1
        sta p_tilt
        lda #118
        sta p_y
        lda #<theme_tune
        sta ptr
        lda #>theme_tune
        sta ptr+1
        jsr load_tune
        jsr music_init
        lda #1
        sta music_on
        jsr render
        jmp show_screen

logo_blocks:
        .byte B_L_H, B_L_E, B_L_L, B_L_I, B_L_S, B_L_C, B_L_A, B_L_P, B_L_E

draw_logo:
        lda #2                  // screen column
        sta t0
        ldx #0
!letter:
        stx t1
        ldy logo_blocks,x
        lda block_lo,y
        sta ptr
        lda block_hi,y
        sta ptr+1
        ldy #0
        ldx t0
        .for (var r = 0; r < 3; r++) {
!:          lda (ptr),y
            sta ROW(1 + r),x
            lda #(r == 0 ? 1 | 8 : 7 | 8)
            sta CROW(1 + r),x
            iny
            inx
            txa
            sec
            sbc t0
            cmp #4
            bne !-
            ldx t0
        }
        clc
        lda t0
        adc #4
        sta t0
        ldx t1
        inx
        cpx #9
        bne !letter-
        rts

title_frame:
        jsr apply_scroll
        // scenery rolls past forever; the world wraps at 2048 pixels
        lda #1
        sta cam_dx
        inc cam_l
        bne !+
        inc cam_h
        lda cam_h
        cmp #>WORLD_PX
        bne !+
        lda #0
        sta cam_h
!:      // the gunship keeps station in the middle
        clc
        lda cam_l
        adc #152
        sta p_xl
        lda cam_h
        adc #0
        sta p_xh
        // bob gently
        lda frame
        lsr
        lsr
        lsr
        and #15
        tax
        lda bob_table,x
        sta p_y
        jsr render
        jsr title_pages
        // flash the prompt
        lda frame
        and #16
        beq !+
        lda #7
        bne !set+
!:      lda #1
!set:   ldx #16
!:      sta CROW(23) + 11,x
        dex
        bpl !-
        jsr read_input
        lda joy
        and #J_FIRE
        beq !done+
        lda joy_prev
        and #J_FIRE
        bne !done+
        jmp start_game
!done:  rts

bob_table:
        .byte 118, 119, 120, 122, 123, 124, 125, 125, 125, 124, 123, 122, 120, 119, 118, 118

// ---------------------------------------------------------------- game flow
start_game:
        lda #0
        sta music_on
        sta mission
        sta score0
        sta score1
        sta score2
        sta title_page
        lda #START_LIVES
        sta lives
start_mission:
        lda #ST_BRIEF
        sta game_state
        jsr sfx_start
        jsr setup_scene
        jsr hud_frame
        jsr place_player
        lda #0
        sta p_cargo
        sta p_invul
        sta p_cool
        jsr render
        // briefing in place of the clouds
        jsr clear_sky_top
        PRINT(t_level, 0, 3, 1)
        jsr level_digits
        ldx #2
!:      lda level_d,x
        sta ROW(0) + 9,x
        lda #1
        sta CROW(0) + 9,x
        dex
        bpl !-
        ldx palette
        lda palette_names_lo,x
        sta ptr
        lda palette_names_hi,x
        sta ptr+1
        lda #<(ROW(0) + 14)
        sta ptr2
        lda #>(ROW(0) + 14)
        sta ptr2+1
        lda #1
        jsr print
        PRINT(t_need, 1, 3, 7)
        lda pow_total
        jsr to_bcd
        ldx #<(ROW(1) + 8)
        ldy #>(ROW(1) + 8)
        jsr put_bcd_at
        ldx mission
        lda lv_need,x
        jsr to_bcd
        ldx #<(ROW(1) + 22)
        ldy #>(ROW(1) + 22)
        jsr put_bcd_at
        jsr update_hud
        jsr draw_radar
        lda #200
        sta state_t
        jmp show_screen

// A = BCD, X/Y = screen address
put_bcd_at:
        stx ptr
        sty ptr+1
        jmp put_bcd

brief_frame:
        jsr render
        jsr read_input
        lda joy
        and #J_FIRE
        beq !+
        lda joy_prev
        and #J_FIRE
        beq !go+
!:      dec state_t
        beq !go+
        rts
!go:    // clouds back
        jsr load_row_colours
        jsr redraw_clouds
        lda #1
        sta clouds_on
        lda #ST_PLAY
        sta game_state
        rts

play_frame:
        jsr apply_scroll
        jsr check_pause
        lda paused
        beq !+
        rts
!:      jsr read_input
        jsr update_player
        lda game_state
        cmp #ST_PLAY
        bne !out+
        jsr update_camera
        jsr update_shots
        jsr update_air
        jsr update_ground
        jsr update_pows
        jsr update_ex
        jsr update_flash
        jsr check_hiscore
        jsr update_hud
        jsr render
        jsr check_mission
!out:   lda $d012
        sta dbg_line
        lda vflag
        beq !+
        inc dbg_over
!:      rts

check_hiscore:
        lda score2
        cmp hi2
        bcc !done+
        bne !new+
        lda score1
        cmp hi1
        bcc !done+
        bne !new+
        lda score0
        cmp hi0
        bcc !done+
        beq !done+
!new:   lda score0
        sta hi0
        lda score1
        sta hi1
        lda score2
        sta hi2
        lda hud_dirty
        ora #1
        sta hud_dirty
!done:  rts

// everyone accounted for?
check_mission:
        lda p_state
        cmp #PS_FALL
        bcs !no+
        lda p_cargo
        bne !no+
        clc
        lda pow_saved
        adc pow_lost
        cmp pow_total
        bcs !+
!no:    rts
!:      // enough of them home?
        ldx mission
        lda pow_saved
        cmp lv_need,x
        bcs !+
        jmp lose_lost
!:      lda #CH_WIN + 1
        sta ch_req
        lda #ST_DONE
        sta game_state
        // clearing a level pays by its number, and every fifth gives a gunship
        ldx mission
        inx
        txa
        cmp #100
        bcc !+
        lda #99
!:      jsr to_bcd
        jsr add_score
        jsr check_hiscore
        lda mission
        clc
        adc #1
!:      cmp #5
        bcc !+
        sbc #5
        bcs !-
!:      cmp #0
        bne !+
        lda lives
        cmp #MAX_LIVES
        bcs !+
        inc lives
!:      lda #$ff
        sta hud_dirty
        jsr update_hud
        jsr clear_sky_top
        PRINT(t_done, 0, 13, 1)
        PRINT(t_cont, 3, 15, 7)
        lda mission
        cmp #LEVEL_COUNT - 1
        bcc !+
        PRINT(t_win, 1, 6, 7)
!:      lda #60
        sta state_t
        rts

lose_lost:
        jsr lose_game
        PRINT(t_lost, 1, 13, 7)
        rts

lose_game:
        lda #ST_OVER
        sta game_state
        // the rotor falls silent and the march begins
        lda #0
        sta sfx_on
        sta music_on
        lda #<march_tune
        sta ptr
        lda #>march_tune
        sta ptr+1
        jsr load_tune
        jsr music_init
        lda #1
        sta music_on
        jsr clear_sky_top
        PRINT(t_over, 0, 13, 1)
        PRINT(t_cont, 3, 15, 7)
        lda #60
        sta state_t
        rts

// tally screens: wait for a fresh press
end_frame:
        lda state_t
        beq !+
        dec state_t
        rts
!:      jsr read_input
        lda joy
        and #J_FIRE
        beq !done+
        lda joy_prev
        and #J_FIRE
        bne !done+
        lda game_state
        cmp #ST_DONE
        bne !end+
        inc mission
        lda mission
        cmp #LEVEL_COUNT
        bcs !end+
        jmp start_mission
!end:   jmp after_game
!done:  rts
