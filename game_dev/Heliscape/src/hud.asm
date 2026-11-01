// HELISCAPE - instrument panel, rows 22-24
//
//   SCORE 000000  HI 000000  M1  LIVES xxx
//   [      radar, 32 cells = 256 columns    ]
//   ARM ........  CARGO 0/8  SAVED 00  LOST 00

.const HUD_SCORE  = ROW(22) + 6
.const HUD_HI     = ROW(22) + 17
.const HUD_MIS    = ROW(22) + 25
.const HUD_LIVES  = ROW(22) + 35
.const RADAR      = ROW(23) + 4
.const CRADAR     = CROW(23) + 4
.const RADAR_W    = 32
.const HUD_ARMOR  = ROW(24) + 4
.const CHUD_ARMOR = CROW(24) + 4
.const HUD_CARGO  = ROW(24) + 20
.const HUD_SAVED  = ROW(24) + 30
.const HUD_LOST   = ROW(24) + 38

hud_t1: .text "SCORE 000000  HI 000000 L001 LIVES"
        .byte 0
hud_t3: .text "ARM          CARGO 0/8  SAVED 00 LOST 00"
        .byte 0
hud_ra: .text "RDR"
        .byte 0

clear_hud:
        ldx #119
        lda #32
!:      sta ROW(22),x
        dex
        bpl !-
        rts

hud_frame:
        jsr clear_hud
        PRINT(hud_t1, 22, 0, 3)
        PRINT(hud_ra, 23, 0, 3)
        PRINT(hud_t3, 24, 0, 3)
        // digit colours: bright numbers on the grey labels
        lda #1
        ldx #5
!:      sta CROW(22) + 6,x
        dex
        bpl !-
        lda #1
        ldx #5
!:      sta CROW(22) + 17,x
        dex
        bpl !-
        lda #7
        sta CROW(22) + 25
        sta CROW(22) + 26
        sta CROW(22) + 27
        sta CROW(24) + 19
        sta CROW(24) + 20
        lda #5
        sta CROW(24) + 30
        sta CROW(24) + 31
        lda #2
        sta CROW(24) + 38
        sta CROW(24) + 39
        lda #$ff
        sta hud_dirty
        rts

// ---------------------------------------------------------------- A = BCD pair, X = screen offset from ptr
put_bcd:
        pha
        lsr
        lsr
        lsr
        lsr
        ora #48
        ldy #0
        sta (ptr),y
        pla
        and #15
        ora #48
        iny
        sta (ptr),y
        clc
        lda ptr
        adc #2
        sta ptr
        bcc !+
        inc ptr+1
!:      rts

// binary 0-99 in A -> BCD in A
to_bcd:
        ldx #0
!:      cmp #10
        bcc !+
        sbc #10
        inx
        jmp !-
!:      sta t0
        txa
        asl
        asl
        asl
        asl
        ora t0
        rts

update_hud:
        lda hud_dirty
        bne !+
        jmp draw_radar_tick
!:      lda #0
        sta hud_dirty
        lda #<HUD_SCORE
        sta ptr
        lda #>HUD_SCORE
        sta ptr+1
        lda score2
        jsr put_bcd
        lda score1
        jsr put_bcd
        lda score0
        jsr put_bcd
        lda #<HUD_HI
        sta ptr
        lda #>HUD_HI
        sta ptr+1
        lda hi2
        jsr put_bcd
        lda hi1
        jsr put_bcd
        lda hi0
        jsr put_bcd
        jsr level_digits
        lda level_d
        sta HUD_MIS
        lda level_d + 1
        sta HUD_MIS + 1
        lda level_d + 2
        sta HUD_MIS + 2
        // lives icons
        ldx #0
!:      lda #32
        cpx lives
        bcs !+
        lda #H_LIFE
!:      sta HUD_LIVES,x
        lda #7
        sta CROW(22) + 35,x
        inx
        cpx #MAX_LIVES
        bne !--
        // armor bar
        ldx #0
!:      lda #H_BAR_OFF
        ldy #6
        cpx p_armor
        bcs !+
        lda #H_BAR
        ldy #5
        pha
        lda p_armor
        cmp #3
        pla
        bcs !+
        ldy #2
!:      sta HUD_ARMOR,x
        tya
        sta CHUD_ARMOR,x
        inx
        cpx #MAX_ARMOR
        bne !--
        lda p_cargo
        clc
        adc #48
        sta HUD_CARGO - 1
        lda #<HUD_SAVED
        sta ptr
        lda #>HUD_SAVED
        sta ptr+1
        lda pow_saved
        jsr to_bcd
        jsr put_bcd
        lda #<HUD_LOST
        sta ptr
        lda #>HUD_LOST
        sta ptr+1
        lda pow_lost
        jsr to_bcd
        jsr put_bcd
draw_radar_tick:
        lda frame
        and #7
        beq draw_radar
        rts

// ---------------------------------------------------------------- 8 pixels per... 64 world pixels per radar cell
draw_radar:
        ldx #RADAR_W - 1
!:      lda #H_R_DOT
        sta RADAR,x
        lda #6
        sta CRADAR,x
        dex
        bpl !-
        // base
        lda #H_R_BASE
        sta RADAR
        lda #5
        sta CRADAR
        // camps: red while standing with prisoners, yellow once open and people wait
        ldx c_n
        beq !camps_done+
!:      dex
        bmi !camps_done+
        lda c_col,x
        lsr
        lsr
        lsr
        tay
        lda #H_R_CAMP
        sta RADAR,y
        lda c_hp,x
        beq !open+
        lda #2
        bne !set+
!open:  lda c_wait,x
        beq !empty+
        lda #7
        bne !set+
!empty: lda #6
!set:   sta CRADAR,y
        jmp !-
!camps_done:
        // POW squads
        ldx #MAX_POW - 1
!loop:  lda q_st,x
        beq !next+
        jsr radar_cell_q
        lda #H_R_BLIP
        sta RADAR,y
        lda #7
        sta CRADAR,y
!next:  dex
        bpl !loop-
        // tanks and turrets
        ldx #MAX_TANK - 1
!loop:  lda g_kind,x
        beq !next+
        lda g_xl,x
        sta t0
        lda g_xh,x
        jsr radar_cell
        lda #H_R_BLIP
        sta RADAR,y
        lda #2
        sta CRADAR,y
!next:  dex
        bpl !loop-
        // aircraft
        ldx #MAX_AIR - 1
!loop:  lda a_kind,x
        beq !next+
        lda a_xl,x
        sta t0
        lda a_xh,x
        jsr radar_cell
        lda #H_R_BLIP
        sta RADAR,y
        lda #4
        sta CRADAR,y
!next:  dex
        bpl !loop-
        // the chopper, on top
        lda p_xl
        sta t0
        lda p_xh
        jsr radar_cell
        lda #H_R_CHOP
        sta RADAR,y
        lda #1
        sta CRADAR,y
        rts

radar_cell_q:
        lda q_xl,x
        sta t0
        lda q_xh,x
// A = world X hi, t0 = lo -> Y = radar cell (64 px per cell)
radar_cell:
        asl t0
        rol
        asl t0
        rol
        and #RADAR_W - 1
        tay
        rts
