// ==============================================================================
// IRONFRONT - SID music driver
// Three-voice tracker driver: order lists -> patterns -> instruments with
// per-frame wavetables (drums, attack clicks), pulse-width sweeps, vibrato and
// a one-frame hard restart so every note attacks cleanly.
//
// Usage:   jsr music_init        once
//          jsr music_play        once per PAL frame (50 Hz), e.g. from a raster IRQ
// Uses zero page $FB/$FC. music_voice_off,x <> 0 leaves voice x to the caller. Song data comes from music_data.asm (gen_music.py).
// Target Assembler: KickAssembler v5.x
// ==============================================================================

.const SID       = $D400
.const SPEED     = 6            // frames per row: 6 -> 125 BPM in sixteenth notes
.const ZP        = $FB          // pattern / order list pointer
.const VIB_DELAY = 12           // frames before vibrato starts on a held note

music_init:     jmp init
music_play:     jmp play

// ---------------------------------------------------------------- init
init:
        lda #$00
        ldx #$18
!:      sta SID,x
        dex
        bpl !-
        sta tick
        ldx #2
!:      lda #$00
        sta op_pos,x
        sta transpose,x
        sta inst,x
        sta active,x
        lda #$01
        sta count,x
        sta dur,x
        lda #$fe
        sta gate,x
        jsr next_pattern
        dex
        bpl !-
        lda #FILTER_CUTOFF
        sta SID+$16
        lda #FILTER_ROUTING
        sta SID+$17
        lda #$1f                // low-pass on, volume 15
        sta SID+$18
        rts

// ---------------------------------------------------------------- play
play:
        lda tick
        bne no_fetch
        ldx #2
!:      dec count,x
        bne !+
        jsr fetch
!:      dex
        bpl !--
no_fetch:
        lda tick
        cmp #SPEED-1
        bne no_hr
        ldx #2
!:      lda count,x
        cmp #1
        bne !+
        jsr hard_restart
!:      dex
        bpl !--
no_hr:
        ldx #2
!:      jsr update_voice
        dex
        bpl !-
        inc tick
        lda tick
        cmp #SPEED
        bne !+
        lda #0
        sta tick
!:      rts

// ---------------------------------------------------------------- order list
// $00-$7F pattern number, $80-$BF transpose (value - $A0), $FF nn loop to nn
next_pattern:
        lda ol_lo,x
        sta ZP
        lda ol_hi,x
        sta ZP+1
np_loop:
        ldy op_pos,x
        lda (ZP),y
        cmp #$ff
        bne !+
        iny
        lda (ZP),y
        sta op_pos,x
        jmp np_loop
!:      cmp #$80
        bcc !+
        sec
        sbc #$a0
        sta transpose,x
        inc op_pos,x
        jmp np_loop
!:      tay
        lda pat_lo,y
        sta ptr_lo,x
        lda pat_hi,y
        sta ptr_hi,x
        inc op_pos,x
        rts

// ---------------------------------------------------------------- pattern events
// $00 rest, $01-$5F note, $80-$BF duration (n+1 rows), $C0-$DF instrument, $FF end
fetch:
        lda ptr_lo,x
        sta ZP
        lda ptr_hi,x
        sta ZP+1
f_loop:
        ldy #0
        lda (ZP),y
        inc ZP
        bne !+
        inc ZP+1
!:      cmp #$ff
        bne !+
        jsr next_pattern
        jmp fetch
!:      cmp #$c0
        bcc !+
        and #$1f
        sta inst,x
        jmp f_loop
!:      cmp #$80
        bcc !+
        and #$3f
        clc
        adc #1
        sta dur,x
        jmp f_loop
!:      pha
        lda ZP
        sta ptr_lo,x
        lda ZP+1
        sta ptr_hi,x
        lda dur,x
        sta count,x
        pla
        bne trigger
        lda #$fe                // rest: release the current note
        sta gate,x
        rts

trigger:
        clc
        adc transpose,x
        sta note,x
        ldy inst,x
        lda ins_wave,y
        sta wpos,x
        lda ins_pwlo,y
        sta pwlo,x
        lda ins_pwhi,y
        sta pwhi,x
        lda #0
        sta pwdir,x
        sta vibf,x
        sta vibph,x
        lda #$ff
        sta gate,x
        sta active,x
        lda music_voice_off,x
        bne !+
        lda ins_ad,y
        pha
        lda ins_sr,y
        ldy voff,x
        sta SID+6,y
        pla
        sta SID+5,y
!:      rts

// One frame before a new note: gate off with a zero envelope, so the next
// attack starts from silence (avoids the SID's ADSR delay bug).
// Skipped when the next event is a rest, so notes keep their release tail.
hard_restart:
        lda ptr_lo,x
        sta ZP
        lda ptr_hi,x
        sta ZP+1
        ldy #0
!:      lda (ZP),y
        beq hr_done             // rest follows: let the note release naturally
        cmp #$ff
        beq !+                  // pattern ends: next pattern starts with a note
        cmp #$80
        bcc !+                  // a note
        iny
        bne !-
!:      lda #$fe
        sta gate,x
        lda music_voice_off,x
        bne hr_done
        ldy voff,x
        lda #0
        sta SID+5,y
        sta SID+6,y
hr_done:
        rts

// ---------------------------------------------------------------- per frame
update_voice:
        lda active,x
        bne !+
        rts
!:
w_loop: ldy wpos,x
        lda wt_wave,y
        cmp #$ff
        bne !+
        lda wt_arp,y            // loop marker: jump within the wavetable
        sta wpos,x
        jmp w_loop
!:      sta curwave
        inc wpos,x
        lda wt_arp,y
        bmi !+
        clc
        adc note,x              // relative: semitones above the played note
        jmp got_note
!:      and #$7f                // absolute note (drums)
got_note:
        tay
        lda freq_lo,y
        sta flo
        lda freq_hi,y
        sta fhi

        // vibrato: after VIB_DELAY frames, wobble by depth * (freq >> 8)
        ldy inst,x
        lda ins_vib,y
        beq no_vib
        sta vdepth
        lda vibf,x
        cmp #VIB_DELAY
        bcs !+
        inc vibf,x
        jmp no_vib
!:      inc vibph,x
        lda vibph,x
        and #7
        tay
        lda vib_shape,y
        beq no_vib
        bmi vib_down
        tay                     // y = steps (1 or 2)
vu_steps:
        lda vdepth
        sta vcount
!:      lda flo
        clc
        adc fhi
        sta flo
        bcc !+
        inc fhi
!:      dec vcount
        bne !--
        dey
        bne vu_steps
        jmp no_vib
vib_down:
        eor #$ff
        clc
        adc #1
        tay
vd_steps:
        lda vdepth
        sta vcount
!:      lda flo
        sec
        sbc fhi
        sta flo
        bcs !+
        dec fhi
!:      dec vcount
        bne !--
        dey
        bne vd_steps
no_vib:
        // pulse width sweep between $0200 and $0E00
        ldy inst,x
        lda ins_pws,y
        beq pw_done
        sta pwstep
        lda pwdir,x
        bne pw_down
        lda pwlo,x
        clc
        adc pwstep
        sta pwlo,x
        bcc !+
        inc pwhi,x
!:      lda pwhi,x
        cmp #$0e
        bcc pw_done
        lda #1
        sta pwdir,x
        jmp pw_done
pw_down:
        lda pwlo,x
        sec
        sbc pwstep
        sta pwlo,x
        bcs !+
        dec pwhi,x
!:      lda pwhi,x
        cmp #$02
        bcs pw_done
        lda #0
        sta pwdir,x
pw_done:
        lda music_voice_off,x
        bne !+
        ldy voff,x
        lda flo
        sta SID+0,y
        lda fhi
        sta SID+1,y
        lda pwlo,x
        sta SID+2,y
        lda pwhi,x
        sta SID+3,y
        lda curwave
        and gate,x
        sta SID+4,y
!:      rts

// ---------------------------------------------------------------- tables
voff:       .byte 0, 7, 14
vib_shape:  .byte 0, 1, 2, 1, 0, -1, -2, -1

// PAL note frequencies, C0 = note 0 (clock 985248 Hz)
freq_lo:    .fill 96, <round(440 * pow(2, (i - 57) / 12) * 16777216 / 985248)
freq_hi:    .fill 96, >round(440 * pow(2, (i - 57) / 12) * 16777216 / 985248)

// ---------------------------------------------------------------- state
tick:       .byte 0
// set an entry non-zero to keep the driver off that voice (sound effects own it)
music_voice_off: .fill 3, 0
curwave:    .byte 0
flo:        .byte 0
fhi:        .byte 0
vdepth:     .byte 0
vcount:     .byte 0
pwstep:     .byte 0
op_pos:     .fill 3, 0
ptr_lo:     .fill 3, 0
ptr_hi:     .fill 3, 0
transpose:  .fill 3, 0
dur:        .fill 3, 0
count:      .fill 3, 0
inst:       .fill 3, 0
note:       .fill 3, 0
gate:       .fill 3, 0
active:     .fill 3, 0
wpos:       .fill 3, 0
vibf:       .fill 3, 0
vibph:      .fill 3, 0
pwlo:       .fill 3, 0
pwhi:       .fill 3, 0
pwdir:      .fill 3, 0
