// ==============================================================================
// IRONFRONT - sound effects on SID voice 3
//
// An effect borrows voice 3 from the music (music_voice_off+2) and hands it
// back a short release later. Higher priority effects cut off lower ones.
// Effect data: attack/decay, sustain/release, then (control, frequency high)
// pairs, one per frame, ended by 0.
// ==============================================================================

// A = SFX_*
sfx_play:
        tay
        lda sfx_prio,y
        cmp sfx_pri
        bcc !+
        sei
        sta sfx_pri
        lda sfx_lo,y
        sta sfx_ptr
        lda sfx_hi,y
        sta sfx_ptr+1
        lda #1
        sta music_voice_off+2
        lda #0
        sta $d412               // gate off: the next frame retriggers
        sta $d410
        lda #8
        sta $d411               // 50% pulse for the beeps
        ldy #0
        lda (sfx_ptr),y
        sta $d413
        iny
        lda (sfx_ptr),y
        sta $d414
        lda #2
        sta sfx_pos
        cli
!:      rts

// once per frame, from the frame IRQ
sfx_update:
        lda sfx_pri
        beq su_release
        ldy sfx_pos
        lda (sfx_ptr),y
        beq su_end
        sta $d412
        sta sfx_last
        iny
        lda (sfx_ptr),y
        sta $d40f
        iny
        sty sfx_pos
        rts
su_end: lda sfx_last
        and #$fe
        sta $d412
        lda #0
        sta sfx_pri
        lda #10
        sta sfx_rel
        rts
su_release:
        lda sfx_rel
        beq !+
        dec sfx_rel
        bne !+
        lda opt_music           // give voice 3 back to the music
        beq !+
        lda #0
        sta music_voice_off+2
!:      rts

sfx_last: .byte 0

sfx_prio: .byte 1, 2, 4, 3, 4, 3
sfx_lo:   .byte <fx_shot, <fx_cannon, <fx_boom, <fx_click, <fx_ready, <fx_error
sfx_hi:   .byte >fx_shot, >fx_cannon, >fx_boom, >fx_click, >fx_ready, >fx_error

fx_shot:   .byte $06, $00, $81, $40, $81, $30, $81, $22, 0
fx_cannon: .byte $09, $00, $81, $18, $81, $12, $81, $0e, $81, $0b, $81, $09, $81, $07, 0
fx_boom:   .byte $0b, $00, $81, $10, $81, $0e, $81, $0c, $81, $0a, $81, $09, $81, $08, $81, $07
           .byte $81, $06, $81, $05, $81, $05, $81, $04, $81, $04, $81, $03, $81, $03, $81, $02, 0
fx_click:  .byte $00, $00, $11, $30, $11, $30, 0
fx_ready:  .byte $00, $a0, $41, $38, $41, $38, $41, $38, $41, $38, $40, $38, $40, $38
           .byte $41, $4b, $41, $4b, $41, $4b, $41, $4b, $41, $4b, 0
fx_error:  .byte $00, $a0, $21, $0c, $21, $0c, $21, $0c, $21, $0c, $21, $0b, $21, $0b, 0
