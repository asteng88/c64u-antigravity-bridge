// HELISCAPE - machine setup and the frame loop

boot:
        sei
        cld
        ldx #$ff
        txs
        lda #$2f
        sta $00
        lda #$35                // RAM everywhere except I/O
        sta $01
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #$ff
        sta $dc02               // port A out (keyboard columns)
        lda #0
        sta $dc03
        sta $d01a
        lda #<nmi
        sta $fffa
        lda #>nmi
        sta $fffb
        // clear zero page variables and RAM
        ldx #$02
        lda #0
!:      sta $00,x
        inx
        cpx #$fb
        bne !-
        lda #<ram_start
        sta ptr
        lda #>ram_start
        sta ptr+1
!loop:  ldy #0
        lda #0
        sta (ptr),y
        inc ptr
        bne !+
        inc ptr+1
!:      lda ptr
        cmp #<ram_end
        bne !loop-
        lda ptr+1
        cmp #>ram_end
        bne !loop-
        // VIC: bank 1, screen $4800, charset $4000
        lda $dd02
        ora #3
        sta $dd02
        lda $dd00
        and #$fc
        ora #2
        sta $dd00
        lda #$20
        sta $d018
        lda #0
        sta $d020
        sta $d021
        sta $d017
        sta $d01b
        sta $d01d
        lda #$ff
        sta $d01c               // all sprites multicolor
        sta $d015
        lda #0
        sta $d025
        lda #1
        sta $d026
        lda #$0b                // blank while the first screen is drawn
        sta $d011
        lda #$a7
        sta rnd
        jsr init_art_pointers
        jsr init_scores
        // raster chain
        lda #<irq_bottom
        sta $fffe
        lda #>irq_bottom
        sta $ffff
        lda #LINE_BOTTOM
        sta $d012
        lda #1
        sta $d01a
        sta $d019
        cli
        jsr enter_title

main_loop:
!:      lda vflag
        beq !-
        lda #0
        sta vflag
        lda game_state
        cmp #ST_PLAY
        bne !+
        jsr play_frame
        jmp main_loop
!:      cmp #ST_TITLE
        bne !+
        jsr title_frame
        jmp main_loop
!:      cmp #ST_BRIEF
        bne !+
        jsr brief_frame
        jmp main_loop
!:      cmp #ST_NAME
        bne !+
        jsr name_frame
        jmp main_loop
!:      jsr end_frame
        jmp main_loop

nmi:    rti

// ---------------------------------------------------------------- joystick + keyboard -> joy
read_input:
        lda joy
        sta joy_prev
        lda #$ff
        sta $dc00
        lda $dc00
        and $dc01               // both joystick ports
        eor #$ff
        and #$1f
        sta joy
        // joystick 1 shares $DC01 with the keyboard rows: while it is in use, a scan
        // would read its lines as phantom keys (down = W, left = A and D, ...)
        lda $dc01
        cmp #$ff
        beq !+
        rts
!:      // keyboard: W A S (column 1)
        lda #$fd
        sta $dc00
        lda $dc01
        sta t0
        and #$02
        bne !+
        lda #J_UP
        jsr joy_or
!:      lda t0
        and #$04
        bne !+
        lda #J_LEFT
        jsr joy_or
!:      lda t0
        and #$20
        bne !+
        lda #J_DOWN
        jsr joy_or
!:      lda t0
        sta t1                  // bit 7: left shift
        // D (column 2)
        lda #$fb
        sta $dc00
        lda $dc01
        and #$04
        bne !+
        lda #J_RIGHT
        jsr joy_or
!:      // SPACE (column 7)
        lda #$7f
        sta $dc00
        lda $dc01
        and #$10
        bne !+
        lda #J_FIRE
        jsr joy_or
!:      // right shift (column 6)
        lda #$bf
        sta $dc00
        lda $dc01
        and #$10
        bne !+
        lda t1
        and #$7f
        sta t1
!:      // RETURN and cursors (column 0)
        lda #$fe
        sta $dc00
        lda $dc01
        sta t0
        and #$02
        bne !+
        lda #J_FIRE
        jsr joy_or
!:      lda t0
        and #$80
        bne !no_ud+
        lda t1
        bmi !down+
        lda #J_UP
        bne !set+
!down:  lda #J_DOWN
!set:   jsr joy_or
!no_ud: lda t0
        and #$04
        bne !no_lr+
        lda t1
        bmi !right+
        lda #J_LEFT
        bne !set+
!right: lda #J_RIGHT
!set:   jsr joy_or
!no_lr: lda #$ff
        sta $dc00
        rts
joy_or: ora joy
        sta joy
        rts

// P key: edge-detected pause toggle. Returns with paused set.
check_pause:
        ldx #0
        lda #$ff
        sta $dc00
        lda $dc01
        cmp #$ff
        bne !up+                // joystick 1 in use: its "down" would read as P
        lda #$df
        sta $dc00
        lda $dc01
        and #$02
        eor #$02                // 2 when P is down
        tax
!up:
        lda #$ff
        sta $dc00
        txa
        cmp key_prev
        beq !done+
        sta key_prev
        cmp #0
        beq !done+
        lda paused
        eor #1
        sta paused
!done:  rts

// ---------------------------------------------------------------- helpers
random:
        lda rnd
        asl
        bcc !+
        eor #$1d
!:      sta rnd
        eor frame
        rts

// A = |a - b| clamped to 255, carry set when a >= b. X and Y survive.
abs_dx:
        sec
        lda a0
        sbc b0
        sta t5
        lda a1
        sbc b1
        bcs !pos+
        // negative: negate, carry is clear here
        eor #$ff
        sta t4
        lda t5
        eor #$ff
        adc #1
        sta t5
        lda t4
        adc #0
        bne !big+
        lda t5
        clc
        rts
!big:   lda #255
        clc
        rts
!pos:   beq !+
        lda #255
        sec
        rts
!:      lda t5
        sec
        rts

// a = chopper position
a_is_player:
        lda p_xl
        sta a0
        lda p_xh
        sta a1
        rts
b_is_player:
        lda p_xl
        sta b0
        lda p_xh
        sta b1
        rts

// A = BCD hundreds to add to the score
add_score:
        sed
        clc
        adc score1
        sta score1
        lda score2
        adc #0
        sta score2
        cld
        bcc !+
        lda #$99                // the counter stops at 999999
        sta score0
        sta score1
        sta score2
!:      lda hud_dirty
        ora #1
        sta hud_dirty
        rts

// print a zero-terminated string: ptr = text, ptr2 = screen, A = colour
print:
        sta t0
        lda ptr2
        sta t2
        lda ptr2+1
        clc
        adc #>(COLRAM - SCREEN)
        sta t3
        ldy #0
!:      lda (ptr),y
        beq !done+
        sta (ptr2),y
        lda t0
        sta (t2),y
        iny
        bne !-
!done:  rts

.macro PRINT(text, row, col, colour) {
        lda #<text
        sta ptr
        lda #>text
        sta ptr+1
        lda #<(SCREEN + row * 40 + col)
        sta ptr2
        lda #>(SCREEN + row * 40 + col)
        sta ptr2+1
        lda #colour
        jsr print
}
