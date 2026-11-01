// HELISCAPE - in-game sound (called from the bottom IRQ)
//   voice 1  rotor thump     voice 2  chimes and alarm     voice 3  effects

sid_silence:
        ldx #$18
        lda #0
!:      sta $d400,x
        dex
        bpl !-
        sta fx_id
        sta fx_t
        sta fx_req
        sta ch_req
        sta ch_t
        lda #$0f
        sta $d418
        rts

sfx_start:
        lda #0
        sta sfx_on
        jsr sid_silence
        lda #$03
        sta $d405               // rotor: instant hit, quick decay
        lda #$00
        sta $d406
        lda #$05
        sta $d401
        lda #$08
        sta $d40a
        lda #$09
        sta $d40c
        lda #$00
        sta $d40d
        lda #1
        sta rotor_t
        sta sfx_on
        rts

// wave, start pitch, pitch step, frames, AD, SR
fx_table:
        .byte 0, 0, 0, 0, 0, 0
        .byte $81, $50, $f0, 4, $02, $00        // gun
        .byte $11, $38, $ff, 22, $0a, $00       // bomb away
        .byte $81, $18, $ff, 10, $06, $00       // flak
        .byte $81, $14, $ff, 14, $07, $00       // small blast
        .byte $21, $10, $fe, 7, $07, $00        // hit
        .byte $81, $16, $ff, 21, $0b, $00       // big blast

sfx_tick:
        // ---- rotor
        lda game_state
        cmp #ST_PLAY
        bne !rotor_off+
        lda p_state
        cmp #PS_FALL
        bcs !rotor_off+
        dec rotor_t
        bne !rotor_off+
        ldx #4                  // beat interval
        lda p_state
        cmp #PS_LANDED
        bne !+
        ldx #6
        jmp !beat+
!:      lda p_vyh
        bpl !beat+
        ldx #3                  // climbing: working harder
!beat:  stx rotor_t
        lda #$81
        sta $d404
        jmp !voice2+
!rotor_off:
        lda #$80
        sta $d404
!voice2:
        // ---- chimes: a new request wins
        lda ch_req
        beq !+
        tax
        lda #0
        sta ch_req
        lda ch_index - 1,x
        sta ch_pos
        lda #1
        sta ch_t
!:      lda ch_t
        beq !alarm+
        dec ch_t
        bne !voice3+
        ldx ch_pos
        lda ch_notes,x
        beq !chend+
        sta $d408
        lda #$40
        sta $d40b
        lda #$41
        sta $d40b
        inc ch_pos
        lda #4
        sta ch_t
        jmp !voice3+
!chend: lda #$40
        sta $d40b
        jmp !voice3+
!alarm: // low armour klaxon
        lda game_state
        cmp #ST_PLAY
        bne !voice3+
        lda p_state
        cmp #PS_FLY
        bne !voice3+
        lda p_armor
        cmp #3
        bcs !voice3+
        lda frame
        and #63
        bne !voice3+
        lda #CH_ALARM + 1
        sta ch_req
!voice3:
        // ---- effects
        lda fx_req
        beq !run+
        cmp fx_id
        bcs !new+
        ldx fx_t
        bne !clr+
        lda fx_req
!new:   sta fx_id
        asl
        adc fx_id
        asl
        tax
        lda fx_table,x
        sta fx_w
        lda fx_table + 1,x
        sta fx_f
        lda fx_table + 2,x
        sta fx_d
        lda fx_table + 3,x
        sta fx_t
        lda fx_table + 4,x
        sta $d413
        lda fx_table + 5,x
        sta $d414
        lda #$80
        sta $d412
        lda fx_w
        sta $d412
!clr:   lda #0
        sta fx_req
!run:   lda fx_t
        beq !done+
        lda fx_f
        sta $d40f
        clc
        adc fx_d
        sta fx_f
        dec fx_t
        bne !done+
        lda fx_w
        and #$fe
        sta $d412
        lda #0
        sta fx_id
!done:  rts

ch_index:
        .byte ch_board - ch_notes, ch_saved - ch_notes, ch_alarm - ch_notes
        .byte ch_lost - ch_notes, ch_win - ch_notes
ch_notes:
ch_board: .byte $22, $2d, 0
ch_saved: .byte $2d, $39, $44, 0
ch_alarm: .byte $14, $10, $14, $10, 0
ch_lost:  .byte $18, $14, $10, $0c, 0
ch_win:   .byte $22, $2d, $39, $44, $39, $44, $5a, 0
