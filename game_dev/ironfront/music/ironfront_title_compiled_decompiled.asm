// Reverse-decompiled by C64U Antigravity Bridge
// C64U_SID_METADATA: {"magic":"PSID","version":2,"data_offset":124,"load_address":4096,"init_address":4096,"play_address":4099,"songs":1,"start_song":1,"speed":0,"name":"IRONFRONT Title March","author":"Andrew Thomas","released":"2026 IRONFRONT","flags":52,"start_page":0,"page_length":0,"second_sid":0,"third_sid":0,"embedded_load_address":true,"container_header":"505349440002007c000010001003000100010000000049524f4e46524f4e54205469746c65204d617263680000000000000000000000416e647265772054686f6d617300000000000000000000000000000000000000323032362049524f4e46524f4e54000000000000000000000000000000000000003400000000"}
// Format: PSID v2 | Title: IRONFRONT Title March
// Author: Andrew Thomas | Released: 2026 IRONFRONT
// Songs: 1 | Default: 1 | Timing: 1:VBI
// Clock: PAL | SID model: 6581/8580
// Static control-flow analysis is conservative. Unreachable and unknown bytes
// are emitted as data so lookup tables and undocumented opcodes remain exact.

.const SID_LOAD = $1000
.const SID_INIT = $1000
.const SID_PLAY = $1003
.const SID_SONGS = 1
.const SID_DEFAULT_SONG = 1
.const SID_SPEED = $00000000
.const SID_FLAGS = $0034

* = SID_LOAD "IRONFRONT Title March"

sid_init:
    jmp  loc_1006

sid_play:
    jmp  loc_1046

loc_1006:
    lda  #$00
    ldx  #$18

loc_100a:
    sta  $d400,x  // SID V1_FREQ_LO
    dex
    bpl  loc_100a
    sta  $1371
    ldx  #$02

loc_1015:
    lda  #$00
    sta  $137b,x
    sta  $1384,x
    sta  $138d,x
    sta  $1396,x
    lda  #$01
    sta  $138a,x
    sta  $1387,x
    lda  #$fe
    sta  $1393,x
    jsr  loc_1086
    dex
    bpl  loc_1015
    lda  #$50
    sta  $d416  // SID FILTER_CUTOFF_HI
    lda  #$61
    sta  $d417  // SID FILTER_RESONANCE_ROUTING
    lda  #$1f
    sta  $d418  // SID FILTER_MODE_VOLUME
    rts

loc_1046:
    lda  $1371
    bne  loc_1058
    ldx  #$02

loc_104d:
    dec  $138a,x
    bne  loc_1055
    jsr  loc_10c3

loc_1055:
    dex
    bpl  loc_104d

loc_1058:
    lda  $1371
    cmp  #$05
    bne  loc_106e
    ldx  #$02

loc_1061:
    lda  $138a,x
    cmp  #$01
    bne  loc_106b
    jsr  loc_115c

loc_106b:
    dex
    bpl  loc_1061

loc_106e:
    ldx  #$02

loc_1070:
    jsr  loc_118d
    dex
    bpl  loc_1070
    inc  $1371
    lda  $1371
    cmp  #$06
    bne  loc_1085
    lda  #$00
    sta  $1371

loc_1085:
    rts

loc_1086:
    lda  $13ab,x
    sta  $fb
    lda  $13ae,x
    sta  $fc

loc_1090:
    ldy  $137b,x
    lda  ($fb),y
    cmp  #$ff
    bne  loc_10a2
    iny
    lda  ($fb),y
    sta  $137b,x
    jmp  loc_1090

loc_10a2:
    cmp  #$80
    bcc  loc_10b2
    sec
    sbc  #$a0
    sta  $1384,x
    inc  $137b,x
    jmp  loc_1090

loc_10b2:
    tay
    lda  $13ef,y
    sta  $137e,x
    lda  $13fa,y
    sta  $1381,x
    inc  $137b,x
    rts

loc_10c3:
    lda  $137e,x
    sta  $fb
    lda  $1381,x
    sta  $fc

loc_10cd:
    ldy  #$00
    lda  ($fb),y
    inc  $fb
    bne  loc_10d7
    inc  $fc

loc_10d7:
    cmp  #$ff
    bne  loc_10e1
    jsr  loc_1086
    jmp  loc_10c3

loc_10e1:
    cmp  #$c0
    bcc  loc_10ed
    and  #$1f
    sta  $138d,x
    jmp  loc_10cd

loc_10ed:
    cmp  #$80
    bcc  loc_10fc
    and  #$3f
    clc
    adc  #$01
    sta  $1387,x
    jmp  loc_10cd

loc_10fc:
    pha
    lda  $fb
    sta  $137e,x
    lda  $fc
    sta  $1381,x
    lda  $1387,x
    sta  $138a,x
    pla
    bne  loc_1116
    lda  #$fe
    sta  $1393,x
    rts

loc_1116:
    clc
    adc  $1384,x
    sta  $1390,x
    ldy  $138d,x
    lda  $151f,y
    sta  $1399,x
    lda  $1513,y
    sta  $13a2,x
    lda  $1519,y
    sta  $13a5,x
    lda  #$00
    sta  $13a8,x
    sta  $139c,x
    sta  $139f,x
    lda  #$ff
    sta  $1393,x
    sta  $1396,x
    lda  $1372,x
    bne  loc_115b
    lda  $14fb,y
    pha
    lda  $1501,y
    ldy  $12a6,x
    sta  $d406,y  // SID V1_SUSTAIN_RELEASE
    pla
    sta  $d405,y  // SID V1_ATTACK_DECAY

loc_115b:
    rts

loc_115c:
    lda  $137e,x
    sta  $fb
    lda  $1381,x
    sta  $fc
    ldy  #$00

loc_1168:
    lda  ($fb),y
    beq  loc_118c
    cmp  #$ff
    beq  loc_1177
    cmp  #$80
    bcc  loc_1177
    iny
    bne  loc_1168

loc_1177:
    lda  #$fe
    sta  $1393,x
    lda  $1372,x
    bne  loc_118c
    ldy  $12a6,x
    lda  #$00
    sta  $d405,y  // SID V1_ATTACK_DECAY
    sta  $d406,y  // SID V1_SUSTAIN_RELEASE

loc_118c:
    rts

loc_118d:
    lda  $1396,x
    bne  loc_1193
    rts

loc_1193:
    ldy  $1399,x
    lda  $1525,y
    cmp  #$ff
    bne  loc_11a6
    lda  $153f,y
    sta  $1399,x
    jmp  loc_1193

loc_11a6:
    sta  $1375
    inc  $1399,x
    lda  $153f,y
    bmi  loc_11b8
    clc
    adc  $1390,x
    jmp  loc_11ba

loc_11b8:
    and  #$7f

loc_11ba:
    tay
    lda  $12b1,y
    sta  $1376
    lda  $1311,y
    sta  $1377
    ldy  $138d,x
    lda  $150d,y
    beq  loc_1233
    sta  $1378
    lda  $139c,x
    cmp  #$0c
    bcs  loc_11df
    inc  $139c,x
    jmp  loc_1233

loc_11df:
    inc  $139f,x
    lda  $139f,x
    and  #$07
    tay
    lda  $12a9,y
    beq  loc_1233
    bmi  loc_1210
    tay

loc_11f0:
    lda  $1378
    sta  $1379

loc_11f6:
    lda  $1376
    clc
    adc  $1377
    sta  $1376
    bcc  loc_1205
    inc  $1377

loc_1205:
    dec  $1379
    bne  loc_11f6
    dey
    bne  loc_11f0
    jmp  loc_1233

loc_1210:
    eor  #$ff
    clc
    adc  #$01
    tay

loc_1216:
    lda  $1378
    sta  $1379

loc_121c:
    lda  $1376
    sec
    sbc  $1377
    sta  $1376
    bcs  loc_122b
    dec  $1377

loc_122b:
    dec  $1379
    bne  loc_121c
    dey
    bne  loc_1216

loc_1233:
    ldy  $138d,x
    lda  $1507,y
    beq  loc_127c
    sta  $137a
    lda  $13a8,x
    bne  loc_1261
    lda  $13a2,x
    clc
    adc  $137a
    sta  $13a2,x
    bcc  loc_1252
    inc  $13a5,x

loc_1252:
    lda  $13a5,x
    cmp  #$0e
    bcc  loc_127c
    lda  #$01
    sta  $13a8,x
    jmp  loc_127c

loc_1261:
    lda  $13a2,x
    sec
    sbc  $137a
    sta  $13a2,x
    bcs  loc_1270
    dec  $13a5,x

loc_1270:
    lda  $13a5,x
    cmp  #$02
    bcs  loc_127c
    lda  #$00
    sta  $13a8,x

loc_127c:
    lda  $1372,x
    bne  loc_12a5
    ldy  $12a6,x
    lda  $1376
    sta  $d400,y  // SID V1_FREQ_LO
    lda  $1377
    sta  $d401,y  // SID V1_FREQ_HI
    lda  $13a2,x
    sta  $d402,y  // SID V1_PW_LO
    lda  $13a5,x
    sta  $d403,y  // SID V1_PW_HI
    lda  $1375
    and  $1393,x
    sta  $d404,y  // SID V1_CONTROL

loc_12a5:
    rts
    .byte $00,$07,$0e,$00,$01,$02,$01,$00,$ff,$fe,$ff,$16,$27,$39,$4b,$5f
    .byte $74,$8a,$a1,$ba,$d4,$f0,$0e,$2d,$4e,$71,$96,$be,$e7,$14,$42,$74
    .byte $a9,$e0,$1b,$5a,$9c,$e2,$2d,$7b,$cf,$27,$85,$e8,$51,$c1,$37,$b4
    .byte $38,$c4,$59,$f7,$9d,$4e,$0a,$d0,$a2,$81,$6d,$67,$70,$89,$b2,$ed
    .byte $3b,$9c,$13,$a0,$45,$02,$da,$ce,$e0,$11,$64,$da,$76,$39,$26,$40
    .byte $89,$04,$b4,$9c,$c0,$23,$c8,$b4,$eb,$72,$4c,$80,$12,$08,$68,$39
    .byte $80,$45,$90,$68,$d6,$e3,$99,$00,$24,$10,$d0,$01,$01,$01,$01,$01
    .byte $01,$01,$01,$01,$01,$01,$02,$02,$02,$02,$02,$02,$02,$03,$03,$03
    .byte $03,$03,$04,$04,$04,$04,$05,$05,$05,$06,$06,$06,$07,$07,$08,$08
    .byte $09,$09,$0a,$0a,$0b,$0c,$0d,$0d,$0e,$0f,$10,$11,$12,$13,$14,$15
    .byte $17,$18,$1a,$1b,$1d,$1f,$20,$22,$24,$27,$29,$2b,$2e,$31,$34,$37
    .byte $3a,$3e,$41,$45,$49,$4e,$52,$57,$5c,$62,$68,$6e,$75,$7c,$83,$8b
    .byte $93,$9c,$a5,$af,$b9,$c4,$d0,$dd,$ea,$f8,$06,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$00,$00,$b1,$d5,$db,$13,$13,$13,$01,$01,$a0,$02,$a0
    .byte $02,$9c,$02,$9b,$02,$a0,$02,$99,$02,$9b,$02,$a0,$03,$9c,$02,$97
    .byte $02,$9e,$02,$9b,$02,$a0,$02,$99,$02,$9b,$02,$a0,$03,$ff,$02,$00
    .byte $00,$09,$0a,$ff,$02,$04,$05,$06,$07,$06,$07,$06,$07,$06,$08,$06
    .byte $07,$06,$07,$06,$07,$06,$08,$ff,$02,$05,$09,$0d,$18,$23,$27,$31
    .byte $4b,$65,$7d,$bf,$14,$14,$14,$14,$14,$14,$14,$14,$14,$14,$14,$c0
    .byte $8f,$00,$ff,$c1,$8f,$00,$ff,$c1,$81,$26,$00,$21,$00,$26,$00,$21
    .byte $00,$ff,$c1,$81,$26,$00,$21,$00,$26,$28,$29,$2d,$ff,$c5,$8f,$30
    .byte $ff,$c5,$87,$30,$c3,$81,$30,$30,$30,$30,$ff,$c2,$81,$30,$c4,$80
    .byte $30,$30,$c3,$81,$30,$c4,$30,$c2,$30,$c4,$80,$30,$30,$c3,$30,$c4
    .byte $30,$c5,$81,$30,$ff,$c2,$81,$30,$c4,$80,$30,$30,$c3,$81,$30,$c4
    .byte $80,$30,$30,$c2,$30,$30,$c4,$30,$30,$c3,$30,$30,$81,$30,$ff,$c3
    .byte $80,$30,$c4,$30,$c3,$30,$c4,$30,$c5,$83,$30,$c3,$80,$30,$30,$30
    .byte $30,$c5,$81,$30,$c3,$30,$ff,$c0,$82,$39,$80,$39,$83,$3e,$39,$35
    .byte $82,$3e,$80,$40,$83,$41,$81,$40,$3e,$83,$3d,$85,$3e,$81,$3c,$83
    .byte $3a,$39,$82,$37,$80,$39,$83,$3a,$87,$39,$82,$39,$80,$39,$83,$3e
    .byte $41,$45,$85,$46,$81,$45,$83,$43,$41,$82,$40,$80,$41,$83,$43,$81
    .byte $41,$40,$83,$3d,$8b,$3e,$83,$00,$ff,$c0,$82,$41,$80,$41,$83,$41
    .byte $3e,$3a,$82,$3c,$80,$3c,$83,$3c,$39,$35,$82,$40,$80,$40,$83,$43
    .byte $40,$3c,$3d,$40,$87,$45,$82,$45,$80,$43,$83,$41,$81,$40,$3e,$83
    .byte $39,$82,$3a,$80,$3c,$83,$3e,$43,$46,$85,$45,$81,$43,$41,$40,$83
    .byte $3d,$87,$3e,$00,$ff,$26,$06,$08,$07,$04,$04,$a9,$98,$00,$00,$00
    .byte $00,$28,$18,$00,$00,$00,$00,$01,$00,$00,$00,$00,$00,$00,$00,$00
    .byte $00,$00,$00,$06,$04,$08,$08,$08,$08,$00,$03,$06,$0d,$13,$16,$41
    .byte $41,$ff,$81,$41,$ff,$81,$41,$41,$41,$41,$40,$ff,$81,$41,$41,$81
    .byte $81,$ff,$81,$81,$ff,$81,$81,$80,$ff,$0c,$00,$01,$c8,$00,$04,$bc
    .byte $a8,$a2,$9d,$99,$96,$0b,$dc,$b4,$b1,$d8,$d6,$11,$da,$d6,$14,$dc
    .byte $d8,$d8,$16
