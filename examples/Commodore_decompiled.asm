// Reverse-decompiled by C64U Antigravity Bridge
// Format: PSID v2 | Title: Commodore
// Author: Kjell Nordbø | Released: 1994 SHAPE/Blues Muz'
// Songs: 1 | Default: 1 | Timing: 1:VBI
// Clock: PAL | SID model: 8580
// Static control-flow analysis is conservative. Unreachable and unknown bytes
// are emitted as data so lookup tables and undocumented opcodes remain exact.

.const SID_LOAD = $4cb0
.const SID_INIT = $4cb0
.const SID_PLAY = $4cb3
.const SID_SONGS = 1
.const SID_DEFAULT_SONG = 1

* = SID_LOAD "Commodore"

sid_init:
    jmp  loc_510e

sid_play:
    jsr  loc_50b4
    dec  $033d
    bpl  loc_4cc1
    lda  $033a
    sta  $033d

loc_4cc1:
    ldx  #$02

loc_4cc3:
    jsr  loc_4cc9
    dex
    bne  loc_4cc3

loc_4cc9:
    lda  $033d
    cmp  $033a
    beq  loc_4cd4

loc_4cd1:
    jmp  loc_4e6f

loc_4cd4:
    dec  $0347,x
    bpl  loc_4cd1
    lda  $0334,x
    sta  $fc
    lda  $0337,x
    sta  $fd

loc_4ce3:
    ldy  $033e,x
    lda  ($fc),y
    bpl  loc_4d32
    cmp  #$ff
    bne  loc_4d03
    iny
    lda  ($fc),y
    sta  $033e,x
    lda  #$0f
    sta  $50cb
    lda  #$00
    sta  $033c
    sta  $034a,x
    beq  loc_4ce3

loc_4d03:
    cmp  #$fd
    bne  loc_4d12
    lda  $033b
    sta  $033c

loc_4d0d:
    inc  $033e,x
    bne  loc_4ce3

loc_4d12:
    bcc  loc_4d15
    rts

loc_4d15:
    cmp  #$c0
    bcc  loc_4d27
    clc
    adc  #$20
    sta  $034a,x
    inc  $033e,x
    iny
    lda  ($fc),y
    bpl  loc_4d32

loc_4d27:
    and  #$3f
    sta  $0341,x
    inc  $033e,x
    iny
    lda  ($fc),y

loc_4d32:
    tay
    lda  $52d4,y
    sta  $fe
    lda  $52db,y
    sta  $ff

loc_4d3d:
    ldy  $0350,x
    inc  $0350,x
    lda  ($fe),y
    bpl  loc_4d7e
    cmp  #$f0
    bcs  loc_4dc0
    cmp  #$e0
    bcs  loc_4d8d
    cmp  #$c0
    beq  loc_4dab
    bcs  loc_4dcd
    and  #$3f
    sta  $0344,x
    sta  $0347,x
    bpl  loc_4d3d

loc_4d5f:
    iny
    inc  $0350,x
    lda  ($fe),y
    and  #$3f
    sta  $0344,x
    sta  $0347,x
    rts

loc_4d6e:
    lda  #$00
    sta  $0350,x
    lda  $0341,x
    beq  loc_4d0d
    dec  $0341,x
    jmp  loc_4ce3

loc_4d7e:
    cmp  #$7e
    beq  loc_4da5
    bcs  loc_4d6e
    cmp  #$5f
    beq  loc_4d5f
    bcs  loc_4e00
    jmp  loc_4e39

loc_4d8d:
    and  #$8f
    sta  $037d,x
    tay
    lda  $5235,y
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    sta  $0383,x
    lda  $5235,y
    and  #$1f
    bpl  loc_4e07

loc_4da5:
    dec  $0353,x
    jsr  loc_4e43

loc_4dab:
    ldy  $0350,x
    inc  $0350,x
    lda  ($fe),y
    clc
    adc  $034d,x
    sta  $0359,x
    jsr  loc_50a6
    jmp  loc_4e68

loc_4dc0:
    and  #$0f
    sta  $035f,x
    lda  #$01
    sta  $0377,x
    jmp  loc_4e68

loc_4dcd:
    and  #$1f
    pha
    asl  a
    asl  a
    asl  a
    asl  a
    asl  a
    sta  $0368,x
    pla
    lsr  a
    lsr  a
    lsr  a
    sta  $036b,x
    iny
    inc  $0350,x
    lda  ($fe),y
    clc
    adc  $034d,x
    sta  $035c,x
    cmp  $0359,x
    bcs  $4df4
    lda  #$ff
    bit  $01a9
    sta  $036e,x
    lda  $0344,x
    sta  $0347,x
    rts

loc_4e00:
    tay
    lda  #$00
    sta  $037d,x
    tya

loc_4e07:
    and  #$1f
    sta  $0356,x
    tay
    lda  $526c,y
    and  #$01
    eor  #$01
    beq  loc_4e19
    lda  $034a,x

loc_4e19:
    sta  $034d,x
    lda  $513c,x
    and  $50bf
    sta  $50bf
    lda  $5299,y
    beq  loc_4e36
    stx  $50b5
    lda  $5139,x
    ora  $50bf
    sta  $50bf

loc_4e36:
    jmp  loc_4d3d

loc_4e39:
    inc  $0353,x
    clc
    adc  $034d,x
    sta  $0359,x

loc_4e43:
    ldy  $0356,x
    lda  $5267,y
    sta  $035f,x
    lda  $526c,y
    and  #$fe
    sta  $0386,x
    lda  $5276,y
    sta  $0389,x
    lda  $527b,y
    sta  $0395,x
    lda  $5285,y
    and  #$0f
    sta  $0398,x

loc_4e68:
    lda  $0344,x
    sta  $0347,x
    rts

loc_4e6f:
    stx  $fc
    lda  $5136,x
    sta  $fd
    ldy  $0356,x
    lda  $0353,x
    beq  loc_4eb9
    bmi  loc_4e99
    cpx  $50b5
    bne  loc_4e99
    lda  $528a,y
    and  #$fe
    sta  $50e8
    lda  $528f,y
    sta  $50eb
    lda  $5294,y
    sta  $50d0

loc_4e99:
    lda  #$00
    sta  $0353,x
    sta  $036e,x
    sta  $037a,x
    sta  $0380,x
    sta  $0377,x
    sta  $038c,x
    sta  $038f,x
    sta  $0392,x
    sta  $039b,x
    sta  $039e,x

loc_4eb9:
    lda  $5267,y
    and  #$f0
    ora  $035f,x
    ldx  $fd
    sta  $d406,x  // SID V1_SUSTAIN_RELEASE
    nop
    nop
    lda  $5262,y
    sta  $d405,x  // SID V1_ATTACK_DECAY
    ldx  $fc
    ldy  $fd
    lda  $0386,x
    asl  a
    asl  a
    asl  a
    asl  a
    sta  $d402,y  // SID V1_PW_LO
    lda  $0386,x
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    sta  $d403,y  // SID V1_PW_HI
    ldy  $0356,x
    sec
    sbc  $038c,x
    lda  $5271,y
    bcs  loc_4ef6
    eor  #$ff
    adc  #$01

loc_4ef6:
    clc
    adc  $0386,x
    sta  $0386,x
    dec  $0389,x
    bne  loc_4f10
    lda  $5276,y
    sta  $0389,x
    lda  $038c,x
    eor  #$80
    sta  $038c,x

loc_4f10:
    lda  $0374,x
    bne  loc_4f40
    lda  $037a,x

loc_4f18:
    ldy  $0356,x
    clc
    adc  $525d,y
    tay
    lda  $529e,y
    cmp  #$7f
    bne  loc_4f2f
    lda  $52a9,y
    sta  $037a,x
    bpl  loc_4f18

loc_4f2f:
    cmp  #$7e
    beq  loc_4f5c
    inc  $037a,x
    cmp  #$7d
    bne  loc_4f46
    lda  $52a9,y
    sta  $0374,x

loc_4f40:
    dec  $0374,x
    jmp  loc_4f77

loc_4f46:
    sta  $0371,x
    asl  a
    bcc  loc_4f54
    lda  $52a9,y
    jsr  loc_50a6
    bne  loc_4f77

loc_4f54:
    lda  $52a9,y
    jsr  loc_50a2
    bne  loc_4f77

loc_4f5c:
    lda  $0377,x
    bne  loc_4f67
    lda  $52a9,y
    sta  $0377,x

loc_4f67:
    beq  loc_4f77
    cmp  #$01
    bne  loc_4f74
    lda  $0371,x
    and  #$fe
    bcs  loc_4f7a

loc_4f74:
    dec  $0377,x

loc_4f77:
    lda  $0371,x

loc_4f7a:
    ldy  $fd
    sta  $d404,y  // SID V1_CONTROL
    clc
    lda  $0362,x
    adc  $038f,x
    sta  $d400,y  // SID V1_FREQ_LO
    lda  $0365,x
    adc  $0392,x
    sta  $d401,y  // SID V1_FREQ_HI

loc_4f92:
    ldy  $037d,x
    bpl  loc_4fca
    lda  $5236,y
    clc
    adc  $0380,x
    tay
    lda  $52b4,y
    cmp  #$7e
    beq  loc_4fca
    cmp  #$7f
    bne  loc_4fb1
    lda  #$00
    sta  $0380,x
    beq  loc_4f92

loc_4fb1:
    jsr  loc_50a2
    dec  $0383,x
    bpl  loc_4fca
    ldy  $037d,x
    lda  $5235,y
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    sta  $0383,x
    inc  $0380,x

loc_4fca:
    lda  $036e,x
    beq  loc_501e
    bmi  loc_4fe8
    clc
    lda  $0362,x
    adc  $0368,x
    sta  $0362,x
    lda  $0365,x
    adc  $036b,x
    sta  $0365,x
    lda  #$b0
    bne  loc_4ffd

loc_4fe8:
    sec
    lda  $0362,x
    sbc  $0368,x
    sta  $0362,x
    lda  $0365,x
    sbc  $036b,x
    sta  $0365,x
    lda  #$90

loc_4ffd:
    sta  $5010
    ldy  $035c,x
    sec
    lda  $51fe,y
    cmp  $0362,x
    lda  $519e,y
    sbc  $0365,x
    bcs  loc_501e
    lda  #$00
    sta  $036e,x
    tya
    sta  $0359,x
    jsr  loc_50a7

loc_501e:
    ldy  $0356,x
    lda  $5285,y
    beq  loc_502e
    lda  $0395,x
    beq  loc_502f
    dec  $0395,x

loc_502e:
    rts

loc_502f:
    lda  $0398,x
    bne  loc_505f
    lda  $039b,x
    eor  #$01
    sta  $039b,x
    lda  $5285,y
    and  #$0f
    asl  a
    sta  $0398,x
    lda  $5280,y
    bmi  loc_505f
    lda  $5285,y
    lsr  a
    lsr  a
    lsr  a
    lsr  a
    adc  $039e,x
    cmp  $5280,y
    bcc  loc_505c
    lda  $5280,y

loc_505c:
    sta  $039e,x

loc_505f:
    dec  $0398,x
    lda  $5280,y
    bpl  loc_506c
    and  #$7f
    sta  $039e,x

loc_506c:
    lda  $0359,x
    lsr  a
    clc
    adc  $039e,x
    tay
    lda  $039b,x
    beq  loc_508e
    clc
    lda  $038f,x
    adc  $519f,y
    sta  $038f,x
    lda  $0392,x
    adc  $513f,y
    sta  $0392,x
    rts

loc_508e:
    sec
    lda  $038f,x
    sbc  $519f,y
    sta  $038f,x
    lda  $0392,x
    sbc  $513f,y
    sta  $0392,x
    rts

loc_50a2:
    clc
    adc  $0359,x

loc_50a6:
    tay

loc_50a7:
    lda  $51fe,y
    sta  $0362,x
    lda  $519e,y
    sta  $0365,x
    rts

loc_50b4:
    ldx  #$00
    ldy  $0356,x
    lda  $5299,y
    and  #$f0
    ora  #$00
    sta  $d417  // SID FILTER_RESONANCE_ROUTING
    lda  $5299,y
    asl  a
    asl  a
    asl  a
    asl  a
    ora  #$0f
    sta  $d418  // SID FILTER_MODE_VOLUME
    lda  #$00
    bne  loc_50e7
    lda  $528a,y
    and  #$01
    bne  loc_50f5
    sec
    sbc  $50eb
    sta  $50eb
    lda  $5294,y
    sta  $50d0

loc_50e7:
    lda  #$00
    clc
    adc  #$00
    sta  $50e8
    sta  $d416  // SID FILTER_CUTOFF_HI
    dec  $50d0

loc_50f5:
    lda  $033c
    beq  loc_510d
    lda  $50cb
    beq  loc_510d
    dec  $03a1
    bpl  loc_510d
    lda  $033c
    sta  $03a1
    dec  $50cb

loc_510d:
    rts

loc_510e:
    ldx  #$16

loc_5110:
    lda  #$08
    sta  $d400,x  // SID V1_FREQ_LO
    lda  #$00
    sta  $d400,x  // SID V1_FREQ_LO
    dex
    bpl  loc_5110
    ldx  #$66

loc_511f:
    sta  $033b,x
    dex
    bne  loc_511f
    ldx  #$07

loc_5127:
    lda  $52b7,x
    sta  $0334,x
    dex
    bpl  loc_5127
    lda  #$0f
    sta  $50cb
    rts
    .byte $00,$07,$0e,$01,$02,$04,$fe,$fd,$fb,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$01,$01,$01,$01,$01,$01,$01,$01,$01
    .byte $01,$01,$01,$02,$02,$02,$02,$02,$02,$02,$03,$03,$03,$03,$03,$04
    .byte $04,$04,$04,$05,$05,$05,$06,$06,$06,$07,$07,$08,$08,$09,$09,$0a
    .byte $0a,$0b,$0c,$0d,$0d,$0e,$0f,$10,$11,$12,$13,$14,$15,$17,$18,$1a
    .byte $1b,$1d,$1f,$20,$22,$24,$27,$29,$2b,$2e,$31,$34,$37,$3a,$3e,$41
    .byte $45,$49,$4e,$52,$57,$5c,$62,$68,$6e,$75,$7c,$83,$8b,$93,$9c,$a5
    .byte $af,$b9,$c4,$d0,$dd,$ea,$f8,$06,$16,$27,$38,$4b,$5e,$73,$89,$a1
    .byte $ba,$d4,$f0,$0d,$2c,$4e,$71,$96,$bd,$e7,$13,$42,$74,$a8,$e0,$1b
    .byte $59,$9c,$e2,$2c,$7b,$ce,$27,$84,$e8,$51,$c0,$36,$b3,$38,$c4,$59
    .byte $f6,$9d,$4e,$09,$d0,$a2,$81,$6d,$67,$70,$88,$b2,$ed,$3a,$9c,$13
    .byte $a0,$44,$02,$da,$ce,$e0,$11,$64,$da,$75,$38,$26,$40,$89,$04,$b4
    .byte $9c,$c0,$22,$c8,$b4,$eb,$71,$4c,$80,$12,$08,$68,$38,$80,$45,$90
    .byte $68,$d6,$e3,$98,$00,$24,$10,$00,$01,$03,$05,$08,$00,$00,$00,$00
    .byte $00,$00,$f0,$40,$80,$f0,$00,$00,$50,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$7e,$11,$7e,$41,$7e,$01,$21,$7e
    .byte $11,$11,$7e,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$7e,$00
    .byte $00,$bf,$c6,$cd,$52,$52,$52,$05,$00,$01,$01,$01,$06,$06,$ff,$01
    .byte $00,$02,$02,$04,$04,$ff,$01,$00,$03,$03,$05,$05,$ff,$01,$e2,$e8
    .byte $1b,$5e,$90,$a2,$c1,$52,$52,$53,$53,$53,$53,$53,$bf,$5f,$af,$60
    .byte $00,$7f,$81,$64,$1c,$f1,$28,$f1,$28,$f1,$17,$f1,$28,$f1,$28,$f1
    .byte $1c,$f1,$28,$f1,$28,$f1,$17,$f1,$19,$f1,$1b,$f1,$1c,$f1,$28,$f1
    .byte $28,$f1,$17,$f1,$28,$f1,$28,$f1,$1c,$f1,$28,$f1,$28,$f1,$17,$f1
    .byte $1e,$f1,$1b,$f1,$7f,$82,$62,$2f,$80,$f1,$81,$20,$21,$85,$22,$80
    .byte $23,$84,$f1,$82,$62,$32,$80,$f1,$86,$31,$80,$f1,$81,$2e,$2f,$82
    .byte $30,$80,$f1,$82,$31,$80,$f1,$82,$36,$80,$f1,$87,$38,$80,$34,$82
    .byte $f1,$37,$80,$f1,$86,$31,$80,$f1,$81,$34,$33,$32,$31,$2f,$2e,$2f
    .byte $32,$2e,$31,$32,$80,$38,$fb,$7f,$82,$63,$2c,$80,$f1,$81,$28,$2a
    .byte $85,$2b,$80,$2c,$84,$f1,$81,$61,$3e,$3f,$40,$3e,$3d,$3b,$87,$3a
    .byte $83,$3b,$42,$40,$44,$3b,$37,$42,$38,$40,$3e,$81,$3b,$3a,$84,$3b
    .byte $80,$f1,$81,$3b,$80,$39,$3a,$3b,$f1,$7f,$81,$61,$28,$34,$28,$34
    .byte $1c,$28,$23,$2f,$28,$34,$28,$34,$83,$24,$23,$7f,$80,$61,$2f,$34
    .byte $37,$38,$3b,$3e,$40,$3b,$37,$38,$37,$38,$39,$3a,$39,$3a,$83,$3b
    .byte $3a,$80,$3c,$30,$3c,$30,$3b,$2f,$3b,$2f,$7f,$81,$64,$1c,$f1,$28
    .byte $f1,$28,$f1,$17,$f1,$28,$f1,$28,$f1,$34,$f1,$33,$f1,$7f
