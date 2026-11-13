// HELISCAPE - top five table and arcade-style initials entry
//
// An entry is 6 bytes: three screen codes, then the score as BCD, low byte first.
// The table lives in RAM, so it lasts until the machine is reset.

.const HS_COUNT = 5
.const HS_SIZE  = HS_COUNT * 6
.const NAME_ROW = 3
.const NAME_COL = 18            // letters sit on every other column

hs_defaults:
        .text "ACE"
        .byte $00, $00, $01     // 10000
        .text "CPT"
        .byte $00, $75, $00     // 7500
        .text "LTN"
        .byte $00, $50, $00     // 5000
        .text "SGT"
        .byte $00, $25, $00     // 2500
        .text "CPL"
        .byte $00, $10, $00     // 1000

name_chars:
        .text "ABCDEFGHIJKLMNOPQRSTUVWXYZ ."
.const NAME_CHARS = 28

t_new:  .text "NEW HIGH SCORE"
        .byte 0
t_rank: .text "RANK 0 OF 5"
        .byte 0
t_pick: .text "UP/DOWN PICK  FIRE NEXT"
        .byte 0
t_top:  .text "TOP PILOTS"
        .byte 0

init_scores:
        ldx #HS_SIZE - 1
!:      lda hs_defaults,x
        sta hs,x
        dex
        bpl !-
        rts

// the HUD's HI shows the best score
hs_to_hi:
        lda hs + 3
        sta hi0
        lda hs + 4
        sta hi1
        lda hs + 5
        sta hi2
        rts

// -> rank = where the score belongs, HS_COUNT when it misses the table. A tie stays below.
find_rank:
        ldx #0
        stx rank
!loop:  lda score2
        cmp hs + 5,x
        bcc !below+
        bne !done+
        lda score1
        cmp hs + 4,x
        bcc !below+
        bne !done+
        lda score0
        cmp hs + 3,x
        bcc !below+
        bne !done+
!below: txa
        clc
        adc #6
        tax
        inc rank
        lda rank
        cmp #HS_COUNT
        bne !loop-
!done:  rts

// rank * 6 in A (and X)
rank_offset:
        lda rank
        asl
        adc rank
        asl
        tax
        rts

// open the entry at rank: everything below moves down, the last one drops off
insert_score:
        jsr rank_offset
        stx t0
        ldy #HS_SIZE - 7
!:      cpy t0
        bcc !open+
        lda hs,y
        sta hs + 6,y
        dey
        cpy #$ff
        bne !-
!open:  ldx t0
        lda name_chars
        sta hs,x
        sta hs + 1,x
        sta hs + 2,x
        lda score0
        sta hs + 3,x
        lda score1
        sta hs + 4,x
        lda score2
        sta hs + 5,x
        rts

// ---------------------------------------------------------------- after any game
after_game:
        jsr find_rank
        lda rank
        cmp #HS_COUNT
        bcc !+
        lda #0
        sta title_page
        jmp enter_title
!:      jsr insert_score
        lda #ST_NAME
        sta game_state
        lda #0
        sta name_pos
        sta name_rep
        sta name_idx
        sta name_idx + 1
        sta name_idx + 2
        jsr clear_sky_top
        // the frozen scene stays behind the entry; row 3 still says PRESS FIRE
        ldx #39
        lda #32
!:      sta ROW(NAME_ROW),x
        dex
        bpl !-
        PRINT(t_new, 0, 13, 1)
        PRINT(t_rank, 1, 14, 7)
        lda rank
        clc
        adc #49
        sta ROW(1) + 19
        PRINT(t_pick, 5, 3, 3)
        rts

name_frame:
        jsr read_input
        // ---- show the letters, the current one flashing
        ldy #0
!:      ldx name_idx,y
        lda name_chars,x
        ldx name_screen,y
        sta ROW(NAME_ROW),x
        lda #1
        cpy name_pos
        bne !col+
        lda frame
        and #8
        beq !on+
        lda #7
        bne !col+
!on:    lda #2
!col:   sta CROW(NAME_ROW),x
        iny
        cpy #3
        bne !-
        // ---- fire: next letter, and after the third, done
        lda joy
        and #J_FIRE
        beq !nofire+
        lda joy_prev
        and #J_FIRE
        bne !nofire+
        jmp name_next
!nofire:
        // ---- directions: step at once, then repeat while held
        lda joy
        and #J_UP | J_DOWN | J_LEFT | J_RIGHT
        bne !+
        sta name_rep
        rts
!:      sta t1
        lda name_rep
        beq !act+
        dec name_rep
        beq !repeat+
        rts
!act:   lda #16                 // first repeat comes after a moment
        bne !go+
!repeat:
        lda #6
!go:    sta name_rep
        lda t1
        and #J_UP
        bne name_up
        lda t1
        and #J_DOWN
        bne name_down
        lda t1
        and #J_RIGHT
        bne name_next
        // left: back a letter
        lda name_pos
        beq !+
        dec name_pos
!:      rts

name_screen:
        .byte NAME_COL, NAME_COL + 2, NAME_COL + 4

name_up:
        ldx name_pos
        ldy name_idx,x
        iny
        cpy #NAME_CHARS
        bcc !+
        ldy #0
!:      tya
        sta name_idx,x
        rts

name_down:
        ldx name_pos
        ldy name_idx,x
        dey
        bpl !+
        ldy #NAME_CHARS - 1
!:      tya
        sta name_idx,x
        rts

name_next:
        inc name_pos
        lda name_pos
        cmp #3
        bcs !commit+
        rts
!commit:
        jsr rank_offset
        ldy #0
!:      sty t0
        ldx name_idx,y
        lda name_chars,x
        pha
        jsr rank_offset
        txa
        clc
        adc t0
        tax
        pla
        sta hs,x
        ldy t0
        iny
        cpy #3
        bne !-
        lda #1
        sta title_page          // straight to the table, to see the name on it
        jmp enter_title

// ---------------------------------------------------------------- the table on the title screen
draw_score_page:
        jsr draw_sky
        jsr load_row_colours
        jsr clear_sky_top
        PRINT(t_top, 1, 9, 7)
        lda #<(ROW(3) + 7)
        sta ptr2
        lda #>(ROW(3) + 7)
        sta ptr2+1
        ldx #0
        stx t4
!entry: ldy #0
        lda t4
        clc
        adc #49
        sta (ptr2),y            // rank
        iny
        lda #46
        sta (ptr2),y
        lda #32                 // the sky's dither must not show between the columns
        ldy #2
        sta (ptr2),y
        ldy #6
        sta (ptr2),y
        ldy #3
        lda hs,x
        sta (ptr2),y
        iny
        lda hs + 1,x
        sta (ptr2),y
        iny
        lda hs + 2,x
        sta (ptr2),y
        // digits
        lda ptr2
        clc
        adc #7
        sta ptr
        lda ptr2+1
        adc #0
        sta ptr+1
        stx xsave
        lda hs + 5,x
        jsr put_bcd
        ldx xsave
        lda hs + 4,x
        jsr put_bcd
        ldx xsave
        lda hs + 3,x
        jsr put_bcd
        // colour RAM for the row: the winner in yellow
        lda ptr2
        sta t2
        lda ptr2+1
        clc
        adc #>(COLRAM - SCREEN)
        sta t3
        lda #1
        ldx t4
        bne !+
        lda #7
!:      ldy #12
!:      sta (t2),y
        dey
        bpl !-
        // next
        clc
        lda ptr2
        adc #40
        sta ptr2
        bcc !+
        inc ptr2+1
!:      ldx xsave
        txa
        clc
        adc #6
        tax
        inc t4
        lda t4
        cmp #HS_COUNT
        beq !+
        jmp !entry-
!:      rts

draw_logo_page:
        jsr draw_sky
        jsr load_row_colours
        jsr clear_sky_top
        jsr draw_logo
        PRINT(t_sub, 5, 8, 1)
        PRINT(t_by, 7, 7, 7)
        rts

// every ten seconds or so the title swaps logo and table
title_pages:
        lda frame
        bne !done+
        inc title_t
        lda title_t
        and #1
        bne !done+
        lda title_page
        eor #1
        sta title_page
        beq !+
        jmp draw_score_page
!:      jmp draw_logo_page
!done:  rts
