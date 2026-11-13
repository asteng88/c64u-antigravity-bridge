BasicUpstart2(start)

* = $0810 "SID Synth & Animated Graphics Demo"

// ==============================================================================
// HARDWARE CONSTANTS
// ==============================================================================
.const VIC_SPR0_X       = $d000
.const VIC_SPR0_Y       = $d001
.const VIC_SPR_MSB      = $d010
.const VIC_CTRL1        = $d011
.const VIC_RASTER       = $d012
.const VIC_SPR_ENA      = $d015
.const VIC_CTRL2        = $d016
.const VIC_MEM_PTR      = $d018
.const VIC_IRQ_STATUS   = $d019
.const VIC_IRQ_CTRL     = $d01a
.const VIC_SPR_PRIO     = $d01b
.const VIC_SPR_MC       = $d01c
.const VIC_BORDER       = $d020
.const VIC_BG           = $d021
.const VIC_SPR_MC0      = $d025
.const VIC_SPR_MC1      = $d026
.const VIC_SPR0_COL     = $d027

.const SID_BASE         = $d400
.const SID_FLT_LO       = $d415
.const SID_FLT_HI       = $d416
.const SID_FLT_RES      = $d417
.const SID_VOLUME       = $d418

.const SCREEN_RAM       = $0400
.const COLOR_RAM        = $d800
.const SPRITE_PTRS      = $07f8
.const CHARSET_RAM      = $3000

// Custom tile screen codes ($C0-$CD in RAM charset at $3000)
.const CHAR_LED_BASE    = $c0       // $C0..$C8 = 0/8 to 8/8 segmented LED bars
.const CHAR_PEAK_LO     = $c9       // Peak-hold marker, lower LED segment
.const CHAR_PEAK_HI     = $ca       // Peak-hold marker, upper LED segment
.const CHAR_STAR_TILE   = $cb       // Animated top/bottom shimmer tile
.const CHAR_PILLAR_TILE = $cc       // Animated side plasma pillar tile
.const CHAR_DIVIDER     = $cd       // Crisp horizontal separator line
.const NUM_TILES        = 14

// Zero-Page: Visual State
.const zp_frame         = $02
.const zp_frame_ready   = $03
.const zp_scroll_x      = $04
.const zp_need_shift    = $05
.const zp_scroll_ptr    = $06       // 16-bit pointer ($06-$07)
.const zp_spr_phase_x   = $08
.const zp_spr_phase_y   = $09
.const zp_spr_anim      = $0a
.const zp_color_phase   = $0b

// Zero-Page: Music Engine (IRQ-only)
.const zp_tick          = $10
.const zp_step          = $11       // Global row counter (HUD)
.const zp_row           = $12       // Row inside current 16-row pattern
.const zp_mptr          = $13       // 16-bit pointer ($13-$14)
.const zp_mt0           = $15
.const zp_mt2           = $17
.const zp_mt3           = $18
.const zp_mt4           = $19
.const zp_flt           = $1a       // Current filter cutoff (bits 10..3)
.const zp_drum_flash    = $1b
.const sh_flt_hi        = $20

// Zero-Page: Sprites (IRQ)
.const zp_temp          = $25
.const zp_temp2         = $26

// Zero-Page: Spectrum Analyzer (main loop only)
.const zp_alvl          = $27
.const zp_aband         = $28
.const zp_ashape        = $29
.const zp_adist         = $2a
.const zp_aamt          = $2b
.const zp_atmp          = $2c
.const zp_apcell        = $2d
.const zp_apchar        = $2e
.const zp_achar         = $2f

// Music engine constants
.const SPEED            = 6         // Frames per row (16th note @ 125 BPM PAL)

// Instrument indices (must be defined before the player code references them)
.const I_LEAD           = 0
.const I_BASS           = 1
.const I_ARPMIN         = 2
.const I_ARPMAJ         = 3
.const I_KICK           = 4
.const I_SNARE          = 5
.const I_HATC           = 6
.const I_HATO           = 7
.const I_BASSDK         = 8

// ==============================================================================
// ENTRY POINT & SYSTEM INITIALIZATION
// ==============================================================================
start:
    sei

    // Disable CIA 1 & CIA 2 interrupts and clear pending flags
    lda #$7f
    sta $dc0d
    sta $dd0d
    lda $dc0d
    lda $dd0d

    // Copy 2KB Character ROM ($D000-$D7FF) into RAM at $3000-$37FF
    lda #$33                    // CHAREN=0: expose Character ROM to CPU
    sta $01
    ldx #$00
copy_charset_loop:
    .for (var p = 0; p < 8; p++) {
        lda $d000 + p * $100, x
        sta CHARSET_RAM + p * $100, x
    }
    inx
    bne copy_charset_loop

    // Bank out BASIC & KERNAL ROMs, keep I/O active at $D000-$DFFF
    lda #$35
    sta $01

    // Install custom LED bar, peak & animated tiles at $3000 + $C0*8 ($3600)
    ldx #$00
install_tiles_loop:
    lda custom_tiles, x
    sta CHARSET_RAM + (CHAR_LED_BASE * 8), x
    inx
    cpx #(NUM_TILES * 8)
    bne install_tiles_loop

    // Clear Zero-Page variables ($02-$30)
    lda #$00
    ldx #$2e
clear_zp_loop:
    sta $02, x
    dex
    bpl clear_zp_loop

    // Initialize scroller pointer & fine offset
    lda #$07
    sta zp_scroll_x
    lda #<scroll_message
    sta zp_scroll_ptr
    lda #>scroll_message
    sta zp_scroll_ptr + 1

    // Configure VIC-II Bank 0 ($0000-$3FFF), Screen $0400, Charset $3000
    lda $dd00
    and #$fc
    ora #$03
    sta $dd00

    lda #$1b                    // Standard text mode, 25 rows, screen on
    sta VIC_CTRL1
    lda #$c8                    // 40 columns, fine scroll = 0
    sta VIC_CTRL2
    lda #$1c                    // Screen = $0400 ($10), Charset = $3000 ($0C)
    sta VIC_MEM_PTR

    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    jsr init_screen
    jsr init_sprites
    jsr init_sid

    // Safe NMI vector (prevents RESTORE key crash when KERNAL is banked out)
    lda #<nmi_rti
    sta $fffa
    lda #>nmi_rti
    sta $fffb

    // Configure first Raster IRQ at scanline $2A (top border)
    lda #<irq_top
    sta $fffe
    lda #>irq_top
    sta $ffff

    lda #$2a
    sta VIC_RASTER
    lda #$01
    sta VIC_IRQ_CTRL
    asl VIC_IRQ_STATUS

    cli

// ==============================================================================
// MAIN LOOP (Frame-Synchronized Non-Blocking Visual Updates)
// ==============================================================================
main_loop:
    lda zp_frame_ready
    beq main_loop
    lda #$00
    sta zp_frame_ready

    jsr update_spectrum_bars    // Real per-voice 16-band analyzer with peak hold
    jsr animate_custom_tiles
    jsr update_color_wash
    jsr update_hud_telemetry

    jmp main_loop

nmi_rti:
    rti

// ==============================================================================
// RASTER IRQ CHAIN (5-Stage Split)
//   Stage 1 ($2A): Reset 40-col header, update 8 Lissajous sprites
//   Stage 2 ($5B): Top cyan copper beam (Row 5) + SID music player
//   Stage 3 ($BB): Beat-reactive warm copper beam (Row 17)
//   Stage 4 ($D9): Apply $D016 smooth hardware fine scroll (Row 21)
//   Stage 5 ($E3): Restore static footer & shift scroller characters
// ==============================================================================
irq_top:
    pha
    txa
    pha
    tya
    pha

    lda #$c8
    sta VIC_CTRL2

    inc zp_frame
    lda #$01
    sta zp_frame_ready

    jsr update_sprites

    lda #<irq_bar1
    sta $fffe
    lda #>irq_bar1
    sta $ffff
    lda #$5b
    sta VIC_RASTER
    asl VIC_IRQ_STATUS

    pla
    tay
    pla
    tax
    pla
    rti

irq_bar1:
    pha
    txa
    pha
    tya
    pha

    ldx #$00
    ldy #$5c
bar1_loop:
    lda copper_cyan, x
!wait:
    cpy VIC_RASTER
    bne !wait-
    sta VIC_BORDER
    sta VIC_BG
    iny
    inx
    cpx #$07
    bne bar1_loop

!wait_end:
    cpy VIC_RASTER
    bne !wait_end-
    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    jsr sid_play                // Music player: once per frame

    lda #<irq_bar2
    sta $fffe
    lda #>irq_bar2
    sta $ffff
    lda #$bb
    sta VIC_RASTER
    asl VIC_IRQ_STATUS

    pla
    tay
    pla
    tax
    pla
    rti

irq_bar2:
    pha
    txa
    pha
    tya
    pha

    ldx #$00
    ldy #$bc
    lda zp_drum_flash
    beq bar2_normal

bar2_flash_loop:
    lda copper_flash, x
!wait_f:
    cpy VIC_RASTER
    bne !wait_f-
    sta VIC_BORDER
    sta VIC_BG
    iny
    inx
    cpx #$07
    bne bar2_flash_loop
    dec zp_drum_flash
    jmp bar2_done

bar2_normal:
    lda copper_warm, x
!wait_n:
    cpy VIC_RASTER
    bne !wait_n-
    sta VIC_BORDER
    sta VIC_BG
    iny
    inx
    cpx #$07
    bne bar2_normal

bar2_done:
!wait_end2:
    cpy VIC_RASTER
    bne !wait_end2-
    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    lda #<irq_scroll
    sta $fffe
    lda #>irq_scroll
    sta $ffff
    lda #$d9
    sta VIC_RASTER
    asl VIC_IRQ_STATUS

    pla
    tay
    pla
    tax
    pla
    rti

irq_scroll:
    pha
    txa
    pha
    tya
    pha

    lda #$da
!wait_sc:
    cmp VIC_RASTER
    bne !wait_sc-

    lda zp_scroll_x
    and #$07
    ora #$c0
    sta VIC_CTRL2

    dec zp_scroll_x
    bpl scroll_no_wrap
    lda #$07
    sta zp_scroll_x
    lda #$01
    sta zp_need_shift
scroll_no_wrap:

    lda #<irq_bottom
    sta $fffe
    lda #>irq_bottom
    sta $ffff
    lda #$e3
    sta VIC_RASTER
    asl VIC_IRQ_STATUS

    pla
    tay
    pla
    tax
    pla
    rti

irq_bottom:
    pha
    txa
    pha
    tya
    pha

    lda #$c8
    sta VIC_CTRL2

    lda zp_need_shift
    beq skip_char_shift
    lda #$00
    sta zp_need_shift

    ldx #$00
shift_row21:
    lda SCREEN_RAM + 21 * 40 + 1, x
    sta SCREEN_RAM + 21 * 40, x
    inx
    cpx #39
    bne shift_row21

    ldy #$00
    lda (zp_scroll_ptr), y
    bne got_scroll_char

    lda #<scroll_message
    sta zp_scroll_ptr
    lda #>scroll_message
    sta zp_scroll_ptr + 1
    lda (zp_scroll_ptr), y

got_scroll_char:
    sta SCREEN_RAM + 21 * 40 + 39
    inc zp_scroll_ptr
    bne skip_char_shift
    inc zp_scroll_ptr + 1

skip_char_shift:
    lda #<irq_top
    sta $fffe
    lda #>irq_top
    sta $ffff
    lda #$2a
    sta VIC_RASTER
    asl VIC_IRQ_STATUS

    pla
    tay
    pla
    tax
    pla
    rti

// ==============================================================================
// SID MUSIC ENGINE
//   - Per-voice order lists (pattern index / transpose / loop)
//   - 16-row patterns: note, legato-slide note, drum, note-off
//   - Instruments: ADSR, wavetable (wave + relative/absolute pitch, loops),
//     pulse-width sweep, delayed vibrato, filter envelope, analyzer profile
//   - 2-frame hard restart before every new note (consistent attacks)
//
// Pattern byte format:
//   $00        = continue
//   $01..$5F   = new note (+ voice transpose), pattern instrument
//   $61..$BF   = legato slide to note (byte - $60), no retrigger
//   $E0..$EF   = trigger instrument (byte & $1F) as drum (absolute pitches)
//   $FE        = gate off (release)
// ==============================================================================
init_sid:
    ldx #$18
    lda #$00
clear_sid:
    sta SID_BASE, x
    dex
    bpl clear_sid

    ldx #$00
    lda #$00
clear_vstate:
    sta vstate_start, x
    inx
    cpx #(vstate_end - vstate_start)
    bne clear_vstate

    ldx #$00
init_voices:
    lda #$fe
    sta v_gate, x
    jsr fetch_next              // Prefetch first pattern...
    jsr switch_pattern          // ...make it current, prefetch the second
    inx
    cpx #$03
    bne init_voices

    lda #$00
    sta SID_FLT_LO
    lda #$c2                    // Resonance $C, filter Voice 2 (bass) only
    sta SID_FLT_RES
    lda #$1f                    // Low-pass + volume 15
    sta SID_VOLUME

    lda #$28
    sta zp_flt
    sta flt_floor
    lda #$00
    sta flt_dec
    sta zp_tick
    sta zp_row
    sta zp_step
    rts

// ------------------------------------------------------------------------------
sid_play:
    lda zp_tick
    bne sp_no_row
    jsr process_row
sp_no_row:
    lda zp_tick
    cmp #(SPEED - 2)
    bne sp_no_hr
    jsr hard_restart
sp_no_hr:
    ldx #$00
    jsr voice_frame
    ldx #$01
    jsr voice_frame
    ldx #$02
    jsr voice_frame
    jsr filter_frame

    inc zp_tick
    lda zp_tick
    cmp #SPEED
    bcc sp_done
    lda #$00
    sta zp_tick
    inc zp_step
    inc zp_row
    lda zp_row
    cmp #16
    bcc sp_done
    lda #$00
    sta zp_row
    ldx #$00
    jsr switch_pattern
    ldx #$01
    jsr switch_pattern
    ldx #$02
    jsr switch_pattern
sp_done:
    rts

// ------------------------------------------------------------------------------
// Order list: read next pattern for voice X into v_nlo/v_nhi (+ transpose)
// ------------------------------------------------------------------------------
fetch_next:
    lda ord_lo, x
    sta zp_mptr
    lda ord_hi, x
    sta zp_mptr + 1
fn_read:
    ldy v_ord, x
    lda (zp_mptr), y
    cmp #$ff
    bne fn_not_jump
    iny
    lda (zp_mptr), y
    sta v_ord, x
    jmp fn_read
fn_not_jump:
    inc v_ord, x
    cmp #$80
    bcc fn_pattern
    sec
    sbc #$a0                    // $A0 = no transpose
    sta v_ntrans, x
    jmp fn_read
fn_pattern:
    tay
    lda pat_lo, y
    sta v_nlo, x
    lda pat_hi, y
    sta v_nhi, x
    rts

switch_pattern:
    lda v_nlo, x
    sta v_plo, x
    sta zp_mptr
    lda v_nhi, x
    sta v_phi, x
    sta zp_mptr + 1
    lda v_ntrans, x
    sta v_trans, x
    ldy #$00
    lda (zp_mptr), y            // Pattern header = instrument
    sta v_pinst, x
    jmp fetch_next

// ------------------------------------------------------------------------------
// Row processing (tick 0)
// ------------------------------------------------------------------------------
process_row:
    ldx #$00
pr_voice:
    lda v_plo, x
    sta zp_mptr
    lda v_phi, x
    sta zp_mptr + 1
    ldy zp_row
    iny                         // Skip header byte
    lda (zp_mptr), y
    bne pr_has_event
    jmp pr_next
pr_has_event:
    cmp #$fe
    bne pr_not_off
    sta v_gate, x               // $FE = gate mask off
    jmp pr_next
pr_not_off:
    cmp #$e0
    bcc pr_not_drum
    and #$1f
    sta v_inst, x
    lda #$00
    sta v_note, x
    jsr trigger_note
    jmp pr_next
pr_not_drum:
    cmp #$60
    bcc pr_new_note
    // Legato slide: change pitch only, restart delayed vibrato
    sbc #$60                    // Carry set from cmp
    clc
    adc v_trans, x
    sta v_note, x
    lda #$01
    sta v_glide, x
    ldy v_inst, x
    lda inst_vibdel, y
    sta v_vibdel, x
    lda inst_vibspd, y
    lsr
    sta v_vibcnt, x
    lda #$00
    sta v_vibdir, x
    sta v_viboffl, x
    sta v_viboffh, x
    jmp pr_next
pr_new_note:
    clc
    adc v_trans, x
    sta v_note, x
    lda v_pinst, x
    sta v_inst, x
    jsr trigger_note
pr_next:
    inx
    cpx #$03
    beq pr_done
    jmp pr_voice
pr_done:
    rts

// ------------------------------------------------------------------------------
// Note trigger for voice X with instrument v_inst,x (preserves X)
// ------------------------------------------------------------------------------
trigger_note:
    ldy v_inst, x
    sty zp_mt0
    lda inst_wt, y
    sta v_wtptr, x
    lda inst_pw, y
    sta v_pwhi, x
    lda inst_vibdel, y
    sta v_vibdel, x
    lda inst_vibspd, y
    lsr
    sta v_vibcnt, x
    lda inst_vpeak, y
    sta v_level, x
    lda #$00
    sta v_pwlo, x
    sta v_pwdir, x
    sta v_glide, x
    sta v_vibdir, x
    sta v_viboffl, x
    sta v_viboffh, x
    lda #$ff
    sta v_gate, x

    lda inst_ad, y
    ldy voff, x
    sta SID_BASE + 5, y
    ldy zp_mt0
    lda inst_sr, y
    ldy voff, x
    sta SID_BASE + 6, y

    ldy zp_mt0
    lda inst_flt, y
    beq tn_no_filter
    sta zp_flt
    lda inst_fltdec, y
    sta flt_dec
    lda inst_fltmin, y
    sta flt_floor
tn_no_filter:
    cpy #I_KICK
    beq tn_flash
    cpy #I_SNARE
    bne tn_done
tn_flash:
    lda #$03
    sta zp_drum_flash
tn_done:
    rts

// ------------------------------------------------------------------------------
// Hard restart (tick SPEED-2): gate off + ADSR $0000 if next row has a new note
// ------------------------------------------------------------------------------
hard_restart:
    ldx #$00
hr_voice:
    lda zp_row
    cmp #15
    bne hr_current
    lda v_nlo, x
    sta zp_mptr
    lda v_nhi, x
    sta zp_mptr + 1
    ldy #$01                    // Row 0 of next pattern
    jmp hr_read
hr_current:
    lda v_plo, x
    sta zp_mptr
    lda v_phi, x
    sta zp_mptr + 1
    ldy zp_row
    iny
    iny                         // Header + next row
hr_read:
    lda (zp_mptr), y
    beq hr_next
    cmp #$fe
    beq hr_next
    cmp #$e0
    bcs hr_do
    cmp #$60
    bcs hr_next                 // Legato: keep gate
hr_do:
    lda #$fe
    sta v_gate, x
    ldy voff, x
    lda #$00
    sta SID_BASE + 5, y
    sta SID_BASE + 6, y
hr_next:
    inx
    cpx #$03
    bne hr_voice
    rts

// ------------------------------------------------------------------------------
// Per-frame voice update (X = voice)
// ------------------------------------------------------------------------------
voice_frame:
    // 1. Wavetable: waveform + relative/absolute pitch
    ldy v_wtptr, x
    lda wt_wave, y
    cmp #$ff
    bne vf_wt_exec
    lda wt_note, y              // Jump: target index
    tay
    lda wt_wave, y
vf_wt_exec:
    cmp #$00
    beq vf_wt_keep
    sta v_wave, x
vf_wt_keep:
    lda wt_note, y
    bmi vf_wt_abs
    clc
    adc v_note, x
    jmp vf_wt_note
vf_wt_abs:
    and #$7f
vf_wt_note:
    cmp #95
    bcc vf_wt_inrange
    lda #94
vf_wt_inrange:
    sta v_curnote, x
    iny
    tya
    sta v_wtptr, x

    // 2. Target frequency + exponential portamento
    ldy v_curnote, x
    lda sid_freq_lo, y
    sta zp_mt2
    lda sid_freq_hi, y
    sta zp_mt3
    lda v_glide, x
    beq vf_snap
    sec
    lda zp_mt2
    sbc v_freqlo, x
    sta zp_mt4
    lda zp_mt3
    sbc v_freqhi, x
    cmp #$80                    // Signed 16-bit >> 2
    ror
    ror zp_mt4
    cmp #$80
    ror
    ror zp_mt4
    sta zp_mt0
    ora zp_mt4
    beq vf_snap
    clc
    lda v_freqlo, x
    adc zp_mt4
    sta v_freqlo, x
    lda v_freqhi, x
    adc zp_mt0
    sta v_freqhi, x
    jmp vf_vibrato
vf_snap:
    lda zp_mt2
    sta v_freqlo, x
    lda zp_mt3
    sta v_freqhi, x

    // 3. Delayed pitch-scaled triangle vibrato
vf_vibrato:
    ldy v_inst, x
    lda inst_vibspd, y
    beq vf_out
    lda v_vibdel, x
    beq vf_vib_run
    dec v_vibdel, x
    jmp vf_out
vf_vib_run:
    ldy v_curnote, x
    sec
    lda sid_freq_lo + 1, y
    sbc sid_freq_lo, y
    sta zp_mt4
    lda sid_freq_hi + 1, y
    sbc sid_freq_hi, y
    sta zp_mt0
    ldy v_inst, x
    lda inst_vibdep, y
    tay
vf_vib_shift:
    lsr zp_mt0
    ror zp_mt4
    dey
    bne vf_vib_shift
    lda v_vibdir, x
    bne vf_vib_down
    clc
    lda v_viboffl, x
    adc zp_mt4
    sta v_viboffl, x
    lda v_viboffh, x
    adc zp_mt0
    sta v_viboffh, x
    jmp vf_vib_count
vf_vib_down:
    sec
    lda v_viboffl, x
    sbc zp_mt4
    sta v_viboffl, x
    lda v_viboffh, x
    sbc zp_mt0
    sta v_viboffh, x
vf_vib_count:
    dec v_vibcnt, x
    bne vf_out
    ldy v_inst, x
    lda inst_vibspd, y
    sta v_vibcnt, x
    lda v_vibdir, x
    eor #$01
    sta v_vibdir, x

    // 4. Write frequency
vf_out:
    ldy voff, x
    clc
    lda v_freqlo, x
    adc v_viboffl, x
    sta SID_BASE + 0, y
    sta sh_flo, x
    lda v_freqhi, x
    adc v_viboffh, x
    sta SID_BASE + 1, y
    sta sh_fhi, x

    // 5. Pulse-width ping-pong sweep ($0200..$0E00)
    ldy v_inst, x
    lda inst_pwspd, y
    beq vf_pw_write
    sta zp_mt4
    lda v_pwdir, x
    bne vf_pw_down
    clc
    lda v_pwlo, x
    adc zp_mt4
    sta v_pwlo, x
    lda v_pwhi, x
    adc #$00
    sta v_pwhi, x
    cmp #$0e
    bcc vf_pw_write
    lda #$01
    sta v_pwdir, x
    jmp vf_pw_write
vf_pw_down:
    sec
    lda v_pwlo, x
    sbc zp_mt4
    sta v_pwlo, x
    lda v_pwhi, x
    sbc #$00
    sta v_pwhi, x
    cmp #$02
    bcs vf_pw_write
    lda #$00
    sta v_pwdir, x
vf_pw_write:
    ldy voff, x
    lda v_pwlo, x
    sta SID_BASE + 2, y
    lda v_pwhi, x
    sta SID_BASE + 3, y

    // 6. Waveform + gate
    lda v_wave, x
    and v_gate, x
    sta SID_BASE + 4, y

    // 7. Analyzer envelope model (decay to sustain floor while gated)
    ldy v_inst, x
    lda v_level, x
    sec
    sbc inst_vdecay, y
    bcs vf_lv_dec
    lda #$00
vf_lv_dec:
    sta zp_mt4
    lda v_gate, x
    cmp #$ff
    bne vf_lv_store
    lda inst_vfloor, y
    cmp zp_mt4
    bcc vf_lv_store
    sta zp_mt4
vf_lv_store:
    lda zp_mt4
    sta v_level, x
    lda inst_band, y
    bpl vf_band_set
    ldy v_curnote, x
    lda note_band, y
vf_band_set:
    sta v_band, x
    rts

// ------------------------------------------------------------------------------
// Filter envelope (bass instruments retrigger it, it decays to a floor)
// ------------------------------------------------------------------------------
filter_frame:
    lda zp_flt
    sec
    sbc flt_dec
    bcc ff_floor
    cmp flt_floor
    bcs ff_store
ff_floor:
    lda flt_floor
ff_store:
    sta zp_flt
    sta SID_FLT_HI
    sta sh_flt_hi
    rts

// ==============================================================================
// SPRITE ENGINE: 8 Spinning Multicolor Hardware Sprites in 3D Lissajous Orbit
// ==============================================================================
init_sprites:
    lda #$06
    sta VIC_SPR_MC0
    lda #$01
    sta VIC_SPR_MC1
    lda #$ff
    sta VIC_SPR_MC
    lda #$aa
    sta VIC_SPR_PRIO

    ldx #$07
init_spr_cols:
    lda sprite_colors, x
    sta VIC_SPR0_COL, x
    lda #$80
    sta SPRITE_PTRS, x
    dex
    bpl init_spr_cols

    lda #$ff
    sta VIC_SPR_ENA
    rts

update_sprites:
    lda zp_spr_phase_x
    clc
    adc #$02
    sta zp_spr_phase_x

    lda zp_spr_phase_y
    clc
    adc #$03
    sta zp_spr_phase_y

    lda zp_frame
    lsr
    lsr
    sta zp_spr_anim

    lda #$00
    sta zp_temp

    ldx #$00
spr_loop:
    txa
    asl
    asl
    asl
    asl
    clc
    adc zp_spr_phase_x
    tay

    txa
    asl
    sta zp_temp2

    lda spr_sin_x_lo, y
    ldy zp_temp2
    sta VIC_SPR0_X, y

    txa
    asl
    asl
    asl
    asl
    clc
    adc zp_spr_phase_x
    tay
    lda spr_sin_x_hi, y
    beq spr_no_msb
    lda zp_temp
    ora bit_masks, x
    sta zp_temp
spr_no_msb:

    txa
    asl
    asl
    asl
    clc
    adc zp_spr_phase_y
    tay
    lda spr_sin_y, y
    ldy zp_temp2
    sta VIC_SPR0_Y, y

    txa
    clc
    adc zp_spr_anim
    and #$03
    ora #$80
    sta SPRITE_PTRS, x

    inx
    cpx #$08
    bne spr_loop

    lda zp_temp
    sta VIC_SPR_MSB
    rts

// ==============================================================================
// 16-BAND SPECTRUM ANALYZER (Rows 8..15, Cols 4..35)
//   Each voice deposits its modeled envelope level into the band of the pitch
//   it is actually playing (drums use fixed bands), spread to neighbours by a
//   per-instrument shape. The sum is passed through a soft-saturation curve so
//   bars only approach the top on genuinely loud, stacked moments.
// ==============================================================================
update_spectrum_bars:
    ldx #15
    lda #$00
an_clear:
    sta an_tgt, x
    dex
    bpl an_clear

    ldx #$02
an_voice:
    lda v_level, x
    bne an_voice_on
    jmp an_voice_next
an_voice_on:
    sta zp_alvl
    lda v_band, x
    sta zp_aband
    ldy v_inst, x
    lda inst_shape, y
    asl
    asl
    sta zp_ashape
    lda #$00
    sta zp_adist
an_dist_loop:
    lda zp_ashape
    clc
    adc zp_adist
    tay
    lda shape_shift, y
    cmp #$08
    bcs an_voice_next           // End of spread for this voice
    tay
    lda zp_alvl
an_shift:
    cpy #$00
    beq an_shift_done
    lsr
    dey
    jmp an_shift
an_shift_done:
    sta zp_aamt
    lda zp_aband
    clc
    adc zp_adist
    cmp #16
    bcs an_skip_up
    tay
    jsr an_add
an_skip_up:
    lda zp_adist
    beq an_skip_down
    lda zp_aband
    sec
    sbc zp_adist
    bcc an_skip_down
    tay
    jsr an_add
an_skip_down:
    inc zp_adist
    lda zp_adist
    cmp #$04
    bcc an_dist_loop
an_voice_next:
    dex
    bpl an_voice

    // Smooth bars: fast attack, gravity fall, peak hold
    ldx #15
an_smooth:
    ldy an_tgt, x
    lda an_comp, y
    sta zp_atmp
    cmp bar_heights, x
    bcc an_fall
    sec
    sbc bar_heights, x
    lsr
    adc bar_heights, x
    sta bar_heights, x
    jmp an_peak
an_fall:
    lda bar_heights, x
    sec
    sbc #$02
    bcs an_fall_ok
    lda #$00
an_fall_ok:
    cmp zp_atmp
    bcs an_fall_store
    lda zp_atmp
an_fall_store:
    sta bar_heights, x
an_peak:
    lda bar_heights, x
    cmp peak_h, x
    bcc an_peak_decay
    sta peak_h, x
    lda #20
    sta peak_t, x
    jmp an_smooth_next
an_peak_decay:
    lda peak_t, x
    beq an_peak_drop
    dec peak_t, x
    jmp an_smooth_next
an_peak_drop:
    lda peak_h, x
    beq an_smooth_next
    dec peak_h, x
an_smooth_next:
    dex
    bpl an_smooth

    // Draw 16 bars x 8 cells (2 columns per bar)
    ldx #$00
an_draw:
    txa
    asl
    tay
    lda peak_h, x
    beq an_no_peak
    sec
    sbc #$01
    lsr
    lsr                         // LED segment 0..15
    lsr                         // Cell 0..7, carry = upper segment
    sta zp_apcell
    lda #CHAR_PEAK_LO
    adc #$00
    sta zp_apchar
    jmp an_have_peak
an_no_peak:
    lda #$ff
    sta zp_apcell
an_have_peak:
    lda bar_heights, x
    sta zp_atmp

    .for (var c = 0; c < 8; c++) {
        lda zp_atmp
        beq !empty+
        cmp #$08
        bcc !partial+
        sbc #$08
        sta zp_atmp
        lda #(CHAR_LED_BASE + 8)
        jmp !plot+
    !partial:
        ora #CHAR_LED_BASE
        sta zp_achar
        lda #$00
        sta zp_atmp
        lda zp_achar
        jmp !plot+
    !empty:
        lda zp_apcell
        cmp #c
        bne !blank+
        lda zp_apchar
        jmp !plot+
    !blank:
        lda #CHAR_LED_BASE
    !plot:
        sta SCREEN_RAM + (15 - c) * 40 + 4, y
        sta SCREEN_RAM + (15 - c) * 40 + 5, y
    }

    inx
    cpx #16
    beq an_draw_done
    jmp an_draw
an_draw_done:
    rts

// Add zp_aamt into band Y, saturating at 127
an_add:
    lda an_tgt, y
    clc
    adc zp_aamt
    bpl an_add_ok
    lda #$7f
an_add_ok:
    sta an_tgt, y
    rts

// ==============================================================================
// ANIMATED RAM CHARSET TILES, COLOR WASH & LIVE SID TELEMETRY HUD
// ==============================================================================
animate_custom_tiles:
    lda zp_frame
    and #$01
    bne anim_tiles_rts

    ldy CHARSET_RAM + (CHAR_PILLAR_TILE * 8) + 7
    ldx #$06
scroll_pillar:
    lda CHARSET_RAM + (CHAR_PILLAR_TILE * 8), x
    sta CHARSET_RAM + (CHAR_PILLAR_TILE * 8) + 1, x
    dex
    bpl scroll_pillar
    sty CHARSET_RAM + (CHAR_PILLAR_TILE * 8)

    ldx #$07
rot_star:
    lda CHARSET_RAM + (CHAR_STAR_TILE * 8), x
    asl
    adc #$00
    sta CHARSET_RAM + (CHAR_STAR_TILE * 8), x
    dex
    bpl rot_star
anim_tiles_rts:
    rts

update_color_wash:
    inc zp_color_phase
    ldx #$27
color_wash_loop:
    txa
    clc
    adc zp_color_phase
    lsr
    and #$0f
    tay
    lda rainbow_palette, y
    sta COLOR_RAM + 1 * 40, x
    sta COLOR_RAM + 21 * 40, x
    dex
    bpl color_wash_loop
    rts

update_hud_telemetry:
    lda zp_step
    ldx #(3 * 40 + 6)
    jsr print_hex_byte

    lda sh_fhi + 0
    ldx #(3 * 40 + 13)
    jsr print_hex_byte
    lda sh_flo + 0
    ldx #(3 * 40 + 15)
    jsr print_hex_byte

    lda sh_fhi + 1
    ldx #(3 * 40 + 22)
    jsr print_hex_byte
    lda sh_flo + 1
    ldx #(3 * 40 + 24)
    jsr print_hex_byte

    lda sh_flt_hi
    ldx #(3 * 40 + 32)
    jsr print_hex_byte

    lda v_pwhi + 0
    ldx #(3 * 40 + 38)
    jsr print_hex_byte
    rts

print_hex_byte:
    pha
    lsr
    lsr
    lsr
    lsr
    tay
    lda hex_chars, y
    sta SCREEN_RAM, x
    pla
    and #$0f
    tay
    lda hex_chars, y
    sta SCREEN_RAM + 1, x
    rts

// ==============================================================================
// INITIAL SCREEN LAYOUT & STUDIO LED COLOR GRADIENT
// ==============================================================================
init_screen:
    ldx #$00
clear_scr:
    lda #$20
    sta SCREEN_RAM + $000, x
    sta SCREEN_RAM + $100, x
    sta SCREEN_RAM + $200, x
    sta SCREEN_RAM + $2e8, x
    lda #$0e
    sta COLOR_RAM + $000, x
    sta COLOR_RAM + $100, x
    sta COLOR_RAM + $200, x
    sta COLOR_RAM + $2e8, x
    inx
    bne clear_scr

    ldx #39
row0_loop:
    lda #CHAR_STAR_TILE
    sta SCREEN_RAM + 0 * 40, x
    lda #$06
    sta COLOR_RAM + 0 * 40, x

    lda txt_title, x
    sta SCREEN_RAM + 1 * 40, x

    lda txt_subtitle, x
    sta SCREEN_RAM + 2 * 40, x
    lda #$03
    sta COLOR_RAM + 2 * 40, x

    lda txt_hud, x
    sta SCREEN_RAM + 3 * 40, x
    lda #$07
    sta COLOR_RAM + 3 * 40, x

    lda txt_bands, x
    sta SCREEN_RAM + 7 * 40, x
    lda #$01
    sta COLOR_RAM + 7 * 40, x

    lda #CHAR_DIVIDER
    sta SCREEN_RAM + 20 * 40, x
    sta SCREEN_RAM + 23 * 40, x
    lda #$06
    sta COLOR_RAM + 20 * 40, x
    sta COLOR_RAM + 23 * 40, x

    lda txt_footer, x
    sta SCREEN_RAM + 24 * 40, x
    lda #$03
    sta COLOR_RAM + 24 * 40, x

    dex
    bpl row0_loop

    ldx #31
floor_loop:
    lda #CHAR_DIVIDER
    sta SCREEN_RAM + 16 * 40 + 4, x
    lda #$0b
    sta COLOR_RAM + 16 * 40 + 4, x
    dex
    bpl floor_loop

    .for (var r = 8; r <= 15; r++) {
        .var led_col = $03
        .if (r == 8)  .eval led_col = $01
        .if (r == 9)  .eval led_col = $02
        .if (r == 10) .eval led_col = $0a
        .if (r == 11) .eval led_col = $08
        .if (r == 12) .eval led_col = $07
        .if (r == 13) .eval led_col = $0d
        .if (r == 14) .eval led_col = $05
        .if (r == 15) .eval led_col = $03

        ldx #31
    !grad_loop:
        lda #led_col
        sta COLOR_RAM + r * 40 + 4, x
        lda #CHAR_LED_BASE
        sta SCREEN_RAM + r * 40 + 4, x
        dex
        bpl !grad_loop-

        lda #CHAR_PILLAR_TILE
        sta SCREEN_RAM + r * 40 + 1
        sta SCREEN_RAM + r * 40 + 38
        lda #$04
        sta COLOR_RAM + r * 40 + 1
        sta COLOR_RAM + r * 40 + 38
    }
    rts

// ==============================================================================
// RUNTIME VARIABLES
// ==============================================================================
vstate_start:
v_plo:      .fill 3, 0      // Current pattern pointer
v_phi:      .fill 3, 0
v_nlo:      .fill 3, 0      // Prefetched next pattern pointer
v_nhi:      .fill 3, 0
v_trans:    .fill 3, 0
v_ntrans:   .fill 3, 0
v_ord:      .fill 3, 0
v_pinst:    .fill 3, 0
v_inst:     .fill 3, 0
v_note:     .fill 3, 0
v_curnote:  .fill 3, 0
v_wtptr:    .fill 3, 0
v_wave:     .fill 3, 0
v_gate:     .fill 3, 0
v_freqlo:   .fill 3, 0
v_freqhi:   .fill 3, 0
v_glide:    .fill 3, 0
v_pwlo:     .fill 3, 0
v_pwhi:     .fill 3, 0
v_pwdir:    .fill 3, 0
v_vibdel:   .fill 3, 0
v_vibcnt:   .fill 3, 0
v_vibdir:   .fill 3, 0
v_viboffl:  .fill 3, 0
v_viboffh:  .fill 3, 0
v_level:    .fill 3, 0
v_band:     .fill 3, 0
sh_flo:     .fill 3, 0
sh_fhi:     .fill 3, 0
flt_dec:    .byte 0
flt_floor:  .byte 0
vstate_end:

an_tgt:      .fill 16, 0
bar_heights: .fill 16, 0
peak_h:      .fill 16, 0
peak_t:      .fill 16, 0

// ==============================================================================
// VISUAL PALETTES, CUSTOM TILES & TEXT STRINGS
// ==============================================================================
bit_masks:
    .byte $01, $02, $04, $08, $10, $20, $40, $80

sprite_colors:
    .byte $03, $07, $0a, $0d, $04, $0e, $07, $03

copper_cyan:
    .byte $06, $0e, $03, $01, $03, $0e, $06
copper_warm:
    .byte $09, $02, $08, $07, $08, $02, $09
copper_flash:
    .byte $02, $0a, $07, $01, $07, $0a, $02

rainbow_palette:
    .byte $06, $04, $0e, $03, $0d, $01, $07, $08
    .byte $0a, $04, $0e, $03, $0d, $01, $07, $0e

// Analyzer spread shapes: right-shift per distance 0..3 ($08 = stop)
shape_shift:
    .byte 0, 1, 3, 8        // 0: tonal (narrow)
    .byte 0, 0, 1, 2        // 1: noise (wide)
    .byte 0, 1, 8, 8        // 2: focused drum

// 14 Custom 8x8 Characters ($C0..$CD)
// LED cell = two 3-pixel segments (rows 1-3 and 5-7), gaps on rows 0 and 4
.const S = %01111110
custom_tiles:
    .byte 0, 0, 0, 0, 0, 0, 0, %00011000    // $C0 empty (grid dot)
    .byte 0, 0, 0, 0, 0, 0, 0, S            // $C1
    .byte 0, 0, 0, 0, 0, 0, S, S            // $C2
    .byte 0, 0, 0, 0, 0, S, S, S            // $C3
    .byte 0, 0, 0, 0, 0, S, S, S            // $C4
    .byte 0, 0, 0, S, 0, S, S, S            // $C5
    .byte 0, 0, S, S, 0, S, S, S            // $C6
    .byte 0, S, S, S, 0, S, S, S            // $C7
    .byte 0, S, S, S, 0, S, S, S            // $C8 full
    .byte 0, 0, 0, 0, 0, S, 0, 0            // $C9 peak (lower segment)
    .byte 0, S, 0, 0, 0, 0, 0, 0            // $CA peak (upper segment)
    // $CB Animated Shimmer Tile
    .byte %00000000, %10001000, %01010000, %00100010, %01010000, %10001000, %00000000, %00000000
    // $CC Animated Vertical Plasma Pillar
    .byte %00111100, %01100110, %01011010, %00111100, %00011000, %00100100, %01000010, %00111100
    // $CD Horizontal Frame Divider
    .byte %00000000, %00000000, %00000000, %11111111, %11111111, %00000000, %00000000, %00000000

.encoding "screencode_upper"

hex_chars:
    .text "0123456789ABCDEF"

txt_title:
    .text "  * C64 SID SYNTHESIZER & VISUALIZER *  "
txt_subtitle:
    .text "  3-VOICE ANALOG FILTER + 8 HW SPRITES  "
txt_hud:
    .text " STEP:00  V1:0000  V2:0000  FLT:00 PW:00"
txt_bands:
    .text "    "
    .text "  BASS  "
    .text "LOW-MID "
    .text "  MID   "
    .text "  HIGH  "
    .text "    "
txt_footer:
    .text " V1:LEAD/ARP "
    .text " V2:ACID BASS "
    .text " V3:DRUMS    "

scroll_message:
    .text "   *** WELCOME TO THE COMMODORE 64 SID SYNTHESIZER & ANIMATED GRAPHICS DEMO! ***   "
    .text "NEW MUSIC ENGINE: ORDER LISTS WITH TRANSPOSE, WAVETABLE INSTRUMENTS AND 2-FRAME HARD RESTART FOR CRISP ATTACKS... "
    .text "VOICE 1 PULSE LEAD WITH PWM SWEEP, DELAYED VIBRATO AND PORTAMENTO SLIDES, PLUS 50HZ CHORD ARPEGGIOS... "
    .text "VOICE 2 ACID BASS THROUGH THE RESONANT LOW-PASS FILTER WITH A PER-NOTE CUTOFF ENVELOPE... "
    .text "VOICE 3 WAVETABLE KICK, SNARE AND HI-HATS... "
    .text "THE 16-BAND ANALYZER NOW TRACKS THE REAL PITCH AND ENVELOPE OF EVERY VOICE, WITH PEAK HOLD!   "
    .byte $00

// ==============================================================================
// MULTICOLOR HARDWARE SPRITE FRAMES ($2000-$20FF -> Pointers $80..$83)
// ==============================================================================
* = $2000 "Spinning Synth Orb Sprites"

// Frame 0 ($80)
    .byte %00000000, %01010100, %00000000
    .byte %00000101, %10101001, %01000000
    .byte %00010110, %10111010, %01010000
    .byte %00011010, %10111010, %10010000
    .byte %01011010, %11111110, %10010100
    .byte %01101010, %11111110, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %10111010, %10100100
    .byte %01101010, %11111110, %10100100
    .byte %01011010, %11111110, %10010100
    .byte %00011010, %10111010, %10010000
    .byte %00010110, %10111010, %01010000
    .byte %00000101, %10101001, %01000000
    .byte %00000000, %01010100, %00000000
    .byte %00000000, %00000000, %00000000
    .byte $00

// Frame 1 ($81)
    .byte %00000000, %01010100, %00000000
    .byte %00000101, %10101001, %01000000
    .byte %00010110, %10101011, %01010000
    .byte %00011010, %01011011, %10010000
    .byte %01011001, %00001110, %10010100
    .byte %01100100, %00111001, %10100100
    .byte %01100100, %00110001, %10100100
    .byte %01100000, %01110000, %10100100
    .byte %01100000, %11111000, %10100100
    .byte %01100000, %11001100, %10100100
    .byte %01100000, %11111000, %10100100
    .byte %01100000, %01110000, %10100100
    .byte %01100100, %01100001, %10100100
    .byte %01100100, %11100001, %10100100
    .byte %01011011, %10000001, %10010100
    .byte %01011110, %01010110, %10010100
    .byte %00011110, %10101010, %10010000
    .byte %00010110, %10101010, %01010000
    .byte %00000101, %10101001, %01000000
    .byte %00000000, %01010100, %00000000
    .byte %00000000, %00000000, %00000000
    .byte $00

// Frame 2 ($82)
    .byte %00000000, %01010100, %00000000
    .byte %00000101, %10101001, %01000000
    .byte %00010110, %10101010, %01010000
    .byte %00011010, %01010101, %10010000
    .byte %01011001, %00000000, %01010100
    .byte %01101000, %00000000, %00100100
    .byte %01101000, %00101000, %00100100
    .byte %01101001, %10111010, %01100100
    .byte %01111111, %11111111, %11110100
    .byte %01111111, %11011111, %11110100
    .byte %01111111, %11111111, %11110100
    .byte %01101001, %10111010, %01100100
    .byte %01101000, %00101000, %00100100
    .byte %01101000, %00000000, %00100100
    .byte %01011001, %00000000, %01010100
    .byte %00011010, %01010101, %10010000
    .byte %00010110, %10101010, %01010000
    .byte %00000101, %10101001, %01000000
    .byte %00000000, %01010100, %00000000
    .byte %00000000, %00000000, %00000000
    .byte %00000000, %00000000, %00000000
    .byte $00

// Frame 3 ($83)
    .byte %00000000, %01010100, %00000000
    .byte %00000101, %10101001, %01000000
    .byte %00010111, %10101010, %01010000
    .byte %00011011, %10010101, %10010000
    .byte %01011010, %11000001, %10010100
    .byte %01101001, %11100000, %01100100
    .byte %01101000, %01100000, %01100100
    .byte %01100000, %00111000, %00100100
    .byte %01100000, %11111000, %00100100
    .byte %01100000, %11001100, %00100100
    .byte %01100000, %11111000, %00100100
    .byte %01100000, %00111000, %00100100
    .byte %01100100, %00011000, %10100100
    .byte %01100100, %00011101, %10100100
    .byte %01011001, %00001110, %10010100
    .byte %01011010, %01010111, %10010100
    .byte %00011010, %10101011, %10010000
    .byte %00010110, %10101010, %01010000
    .byte %00000101, %10101001, %01000000
    .byte %00000000, %01010100, %00000000
    .byte %00000000, %00000000, %00000000
    .byte $00

// ==============================================================================
// TABLES & MUSIC DATA ($2100-$2FFF, below the RAM charset at $3000)
// ==============================================================================
* = $2100 "Tables & Music"

.const PAL_CLOCK = 985248.0
.function sidPitch(n) {
    .var p = round(440.0 * pow(2.0, (n - 57.0) / 12.0) * 16777216.0 / PAL_CLOCK)
    .return p > 65535 ? 65535 : p
}

// 97 entries (0..96) so vibrato can safely read note+1 up to note 95
sid_freq_lo:
    .fill 97, <sidPitch(i)
sid_freq_hi:
    .fill 97, >sidPitch(i)

// Note -> analyzer band (log-spaced, 5 semitones per band)
.function noteBand(n) {
    .var b = floor((n - 14) / 5)
    .if (b < 0) .eval b = 0
    .if (b > 15) .eval b = 15
    .return b
}
note_band:
    .fill 97, noteBand(i)

// Soft-saturation curve: raw band energy 0..127 -> bar height 0..~61
an_comp:
    .fill 128, round(63.0 * (1.0 - exp(-i / 34.0)))

voff:
    .byte 0, 7, 14

// Sprite tables
spr_sin_x_lo:
    .fill 256, <round(172.0 + 130.0 * sin(toRadians(i * 360.0 / 256.0)))
spr_sin_x_hi:
    .fill 256, >round(172.0 + 130.0 * sin(toRadians(i * 360.0 / 256.0)))
spr_sin_y:
    .fill 256, round(136.0 + 34.0 * sin(toRadians(i * 360.0 / 256.0)))

// ------------------------------------------------------------------------------
// INSTRUMENTS  (instrument index constants I_* are defined in the header)
// ------------------------------------------------------------------------------
//               LEAD  BASS  ARPm  ARPM  KICK  SNR   HATC  HATO  BSDK
inst_ad:    .byte $28,  $09,  $08,  $08,  $07,  $08,  $03,  $07,  $0a
inst_sr:    .byte $a8,  $a9,  $88,  $88,  $00,  $00,  $00,  $00,  $c9
inst_wt:    .byte 0,    2,    5,    9,    13,   21,   28,   30,   2
inst_pw:    .byte $04,  $08,  $03,  $03,  $08,  $08,  $08,  $08,  $06
inst_pwspd: .byte $18,  $28,  $0c,  $0c,  $00,  $00,  $00,  $00,  $10
inst_vibdel:.byte 10,   0,    0,    0,    0,    0,    0,    0,    0
inst_vibspd:.byte 4,    0,    0,    0,    0,    0,    0,    0,    0
inst_vibdep:.byte 3,    1,    1,    1,    1,    1,    1,    1,    1
inst_flt:   .byte $00,  $a8,  $00,  $00,  $00,  $00,  $00,  $00,  $58
inst_fltdec:.byte $00,  $05,  $00,  $00,  $00,  $00,  $00,  $00,  $01
inst_fltmin:.byte $00,  $28,  $00,  $00,  $00,  $00,  $00,  $00,  $20
// Analyzer model: peak level, decay/frame, sustain floor, band ($FF=pitch), shape
inst_vpeak: .byte 46,   42,   36,   36,   54,   44,   30,   32,   32
inst_vdecay:.byte 1,    3,    1,    1,    4,    3,    5,    2,    2
inst_vfloor:.byte 32,   18,   26,   26,   0,    0,    0,    0,    14
inst_band:  .byte $ff,  $ff,  $ff,  $ff,  1,    7,    14,   13,   $ff
inst_shape: .byte 0,    0,    0,    0,    2,    1,    2,    1,    0

// ------------------------------------------------------------------------------
// WAVETABLE: wave ($FF = jump to index in note column)
//            note ($00-$7F relative semitones, $80|n = absolute note n)
// ------------------------------------------------------------------------------
.const AB = $80
wt_wave:
    .byte $41, $ff                          //  0: Lead pulse (hold)
    .byte $81, $41, $ff                     //  2: Bass: noise click -> pulse
    .byte $41, $41, $41, $ff                //  5: Minor arp 0-3-7
    .byte $41, $41, $41, $ff                //  9: Major arp 0-4-7
    .byte $81, $41, $41, $41, $11, $11, $11, $ff   // 13: Kick
    .byte $81, $41, $41, $81, $81, $81, $ff        // 21: Snare
    .byte $81, $ff                          // 28: Closed hat
    .byte $81, $81, $ff                     // 30: Open hat (sizzle)
wt_note:
    .byte 0, 0
    .byte 24, 0, 3
    .byte 0, 3, 7, 5
    .byte 0, 4, 7, 9
    .byte AB|72, AB|46, AB|38, AB|32, AB|28, AB|24, AB|21, 19
    .byte AB|80, AB|52, AB|47, AB|76, AB|74, AB|72, 26
    .byte AB|93, 28
    .byte AB|94, AB|90, 30

// ------------------------------------------------------------------------------
// PATTERNS (header = instrument, then 16 rows)
// Notes: C3=36 A3=45 C4=48 E4=52 A4=57 C5=60 E5=64 A5=69 C6=72
// ------------------------------------------------------------------------------
.const SL   = $60           // Legato slide prefix
.const GOFF = $fe           // Gate off
.const KK   = $e0 + I_KICK
.const SN   = $e0 + I_SNARE
.const HH   = $e0 + I_HATC
.const OH   = $e0 + I_HATO

pat_lo:
    .byte <pat_la1, <pat_la2, <pat_la3, <pat_la4, <pat_la4b
    .byte <pat_lb1, <pat_lb2, <pat_lb3, <pat_lb4
    .byte <pat_arpmin, <pat_arpmaj
    .byte <pat_bass_a, <pat_bass_b, <pat_bass_intro
    .byte <pat_dr_a, <pat_dr_fill, <pat_dr_intro, <pat_dr_half
pat_hi:
    .byte >pat_la1, >pat_la2, >pat_la3, >pat_la4, >pat_la4b
    .byte >pat_lb1, >pat_lb2, >pat_lb3, >pat_lb4
    .byte >pat_arpmin, >pat_arpmaj
    .byte >pat_bass_a, >pat_bass_b, >pat_bass_intro
    .byte >pat_dr_a, >pat_dr_fill, >pat_dr_intro, >pat_dr_half

// --- Lead, section A (Am | F | C | G) ---
pat_la1:    .byte I_LEAD
            .byte 64,0,0,0,      57,0,60,0,     64,0,62,60,    0,0,59,0
pat_la2:    .byte I_LEAD
            .byte 60,0,0,0,      0,0,57,0,      60,0,65,0,     64,0,60,0
pat_la3:    .byte I_LEAD
            .byte 64,0,67,0,     0,0,72,0,      SL+71,0,67,0,  64,0,0,0
pat_la4:    .byte I_LEAD
            .byte 62,0,59,0,     55,0,0,0,      59,0,62,0,     64,0,SL+67,0
pat_la4b:   .byte I_LEAD
            .byte 67,0,0,0,      65,0,64,0,     62,0,0,0,      0,0,GOFF,0

// --- Lead, section B (Dm | Am | F | E) ---
pat_lb1:    .byte I_LEAD
            .byte 69,0,0,0,      0,0,65,0,      69,0,72,0,     SL+74,0,0,0
pat_lb2:    .byte I_LEAD
            .byte 72,0,0,0,      69,0,0,0,      64,0,0,0,      69,0,72,0
pat_lb3:    .byte I_LEAD
            .byte 72,0,0,0,      0,0,69,0,      65,0,69,0,     72,0,SL+74,SL+72
pat_lb4:    .byte I_LEAD
            .byte 71,0,0,0,      SL+68,0,0,0,   64,0,68,0,     71,0,GOFF,0

// --- Chord arpeggios (root A4, transposed per chord) ---
pat_arpmin: .byte I_ARPMIN
            .byte 57,0,0,57,     0,0,57,0,      57,0,0,57,     0,0,57,0
pat_arpmaj: .byte I_ARPMAJ
            .byte 57,0,0,57,     0,0,57,0,      57,0,0,57,     0,0,57,0

// --- Bass (root A1, transposed per chord; roots/fifths/octaves only) ---
pat_bass_a: .byte I_BASS
            .byte 21,0,33,21,    SL+33,21,33,0, 21,0,33,21,    33,28,SL+40,33
pat_bass_b: .byte I_BASS
            .byte 21,21,33,21,   21,33,21,21,   33,21,21,33,   28,33,40,45
pat_bass_intro: .byte I_BASSDK
            .byte 21,0,0,0,      0,0,21,0,      0,0,33,0,      21,0,SL+33,0

// --- Drums ---
pat_dr_a:   .byte 0
            .byte KK,0,HH,0,     SN,0,HH,KK,    0,KK,HH,0,     SN,0,OH,HH
pat_dr_fill:.byte 0
            .byte KK,0,HH,0,     SN,0,HH,KK,    SN,0,SN,SN,    SN,SN,SN,SN
pat_dr_intro:.byte 0
            .byte HH,0,HH,0,     OH,0,HH,0,     HH,0,HH,0,     OH,0,HH,HH
pat_dr_half:.byte 0
            .byte KK,0,0,0,      HH,0,0,0,      SN,0,0,0,      HH,0,OH,0

// ------------------------------------------------------------------------------
// ORDER LISTS: pattern index | $A0+t = transpose t | $FF,n = loop to n
// Transposes from A: F=-4 ($9C), C=+3 ($A3), G=-2 ($9E), D=+5 ($A5), E=-5 ($9B)
// Song: Intro | A | A' | B | Breakdown | B | A'  -> loop to A
// ------------------------------------------------------------------------------
ord_lo:
    .byte <ord_v1, <ord_v2, <ord_v3
ord_hi:
    .byte >ord_v1, >ord_v2, >ord_v3

ord_v1:
    .byte $a0, 9, $9c, 10, $a3, 10, $9e, 10         // Intro arps: Am F C G
    .byte $a0, 0, 1, 2, 3                           // A   (loop point = 8)
    .byte 0, 1, 2, 4                                // A'
    .byte 5, 6, 7, 8                                // B
    .byte $a5, 9, $a0, 9, $9c, 10, $9b, 10          // Breakdown arps: Dm Am F E
    .byte $a0, 5, 6, 7, 8                           // B
    .byte 0, 1, 2, 4                                // A'
    .byte $ff, 8

ord_v2:
    .byte $a0, 13, $9c, 13, $a3, 13, $9e, 13        // Intro (dark bass)
    .byte $a0, 11, $9c, 11, $a3, 11, $9e, 11        // A   (loop point = 8)
    .byte $a0, 12, $9c, 12, $a3, 12, $9e, 12        // A'
    .byte $a5, 11, $a0, 11, $9c, 11, $9b, 11        // B
    .byte $a5, 12, $a0, 12, $9c, 12, $9b, 12        // Breakdown
    .byte $a5, 11, $a0, 11, $9c, 11, $9b, 11        // B
    .byte $a0, 12, $9c, 12, $a3, 12, $9e, 12        // A'
    .byte $ff, 8

ord_v3:
    .byte 16, 16, 16, 15                            // Intro hats + fill
    .byte 14, 14, 14, 15                            // A   (loop point = 4)
    .byte 14, 14, 14, 15                            // A'
    .byte 14, 14, 14, 15                            // B
    .byte 17, 17, 17, 15                            // Breakdown (half-time)
    .byte 14, 14, 14, 15                            // B
    .byte 14, 14, 14, 15                            // A'
    .byte $ff, 4
