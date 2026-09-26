// ==============================================================================
// 3-VOICE SID SYNTHESIS & MUSIC ENGINE
// Target Assembler: KickAssembler v5.x
// Architecture: MOS 6510 CPU / MOS 6581/8580 SID
// Features: 
//   - Voice 1: Arpeggiated Melodic Lead (Sawtooth wave + fast 50Hz arpeggio)
//   - Voice 2: Deep Analog Bassline (Pulse wave with real-time Pulse Width Modulation)
//   - Voice 3: Percussive Hi-Hat / Snare (White Noise with instant attack/decay)
//   - Master 11-bit Filter Sweep: Low-pass sweep on bass/lead
// ==============================================================================

BasicUpstart2(entry_point)

* = $0810 "SID Symphony Engine"

// Hardware Constants
.const SID_BASE         = $d400
.const SID_V1_FREQ_LO   = $d400
.const SID_V1_FREQ_HI   = $d401
.const SID_V1_PW_LO     = $d402
.const SID_V1_PW_HI     = $d403
.const SID_V1_CTRL      = $d404
.const SID_V1_AD        = $d405
.const SID_V1_SR        = $d406

.const SID_V2_FREQ_LO   = $d407
.const SID_V2_FREQ_HI   = $d408
.const SID_V2_PW_LO     = $d409
.const SID_V2_PW_HI     = $d40A
.const SID_V2_CTRL      = $d40B
.const SID_V2_AD        = $d40C
.const SID_V2_SR        = $d40D

.const SID_V3_FREQ_LO   = $d40E
.const SID_V3_FREQ_HI   = $d40F
.const SID_V3_CTRL      = $d412
.const SID_V3_AD        = $d413
.const SID_V3_SR        = $d414

.const SID_FLT_LO       = $d415
.const SID_FLT_HI       = $d416
.const SID_FLT_RES      = $d417
.const SID_VOLUME       = $d418

.const VIC_BORDER       = $d020
.const VIC_BG           = $d021
.const VIC_RASTER       = $d012
.const VIC_CTRL1        = $d011
.const VIC_IRQ_STATUS   = $d019
.const VIC_IRQ_CTRL     = $d01a

entry_point:
    sei

    // Set screen styling
    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    // Clear SID registers
    ldx #$18
    lda #$00
clear_sid_loop:
    sta SID_BASE,x
    dex
    bpl clear_sid_loop

    // Set Master Volume to Maximum (15) and enable Low-Pass Filter
    lda #$1f            // Low-pass mode ($10) + Volume 15 ($0F)
    sta SID_VOLUME

    // Route Voice 1 & Voice 2 through Filter, with Medium Resonance
    lda #$73            // Resonance 7 ($70) + Filter V1 and V2 ($03)
    sta SID_FLT_RES

    // Initialize Voice 1 (Lead Synth)
    lda #$09            // Attack: 0, Decay: 9
    sta SID_V1_AD
    lda #$a4            // Sustain: 10, Release: 4
    sta SID_V1_SR

    // Initialize Voice 2 (Deep Bassline)
    lda #$18            // Attack: 1, Decay: 8
    sta SID_V2_AD
    lda #$f2            // Sustain: 15, Release: 2
    sta SID_V2_SR
    lda #$08            // Default 50% pulse width ($0800)
    sta SID_V2_PW_HI
    lda #$00
    sta SID_V2_PW_LO

    // Initialize Voice 3 (Hi-Hat / Snare Noise)
    lda #$00            // Attack: 0, Decay: 0 (Ultra sharp)
    sta SID_V3_AD
    lda #$00            // Sustain: 0, Release: 0
    sta SID_V3_SR

    // Hook custom Raster Interrupt (50 Hz / PAL Line 0)
    lda #$7f
    sta $dc0d           // Disable CIA1 timer interrupts
    lda $dc0d           // Acknowledge any pending interrupt

    lda #$01
    sta VIC_IRQ_CTRL    // Enable Raster IRQ
    lda #$00
    sta VIC_RASTER      // Trigger at scanline 0
    lda VIC_CTRL1
    and #$7f            // 9th bit = 0
    sta VIC_CTRL1

    lda #<irq_handler
    sta $0314
    lda #>irq_handler
    sta $0315

    cli

main_loop:
    jmp main_loop

// ==============================================================================
// 50Hz Frame Interrupt (Music Player Step)
// ==============================================================================
irq_handler:
    asl VIC_IRQ_STATUS  // Acknowledge VIC-II IRQ

    // 1. Advance Frame Counter
    inc frame_counter
    lda frame_counter
    and #$07
    bne update_modulation

    // Every 8 frames, step the music sequence
    jsr step_sequencer

update_modulation:
    // 2. Update Voice 1 Arpeggio (Steps every single frame at 50Hz)
    jsr update_arpeggio

    // 3. Update Voice 2 Pulse Width Modulation (Smooth analog chorusing)
    jsr update_pwm

    // 4. Update Filter Cutoff Sweep
    jsr update_filter

    jmp $ea81           // Return to standard Kernal routine

.const seq_length = 8

// ------------------------------------------------------------------------------
// Sequencer: Advance Notes
// ------------------------------------------------------------------------------
step_sequencer:
    ldx seq_index
    inx
    cpx #seq_length
    bne seq_ok
    ldx #$00
seq_ok:
    stx seq_index

    // Play Voice 2 Bass Note
    lda bass_notes,x
    sta SID_V2_FREQ_LO
    lda bass_notes_hi,x
    sta SID_V2_FREQ_HI
    lda #$41            // Pulse waveform + Gate ON
    sta SID_V2_CTRL

    // Trigger Voice 3 Drum (every even step: hi-hat, every 4th step: snare)
    txa
    and #$01
    bne drum_done
    lda #$18            // Drum pitch
    sta SID_V3_FREQ_HI
    lda #$81            // Noise waveform + Gate ON
    sta SID_V3_CTRL
drum_done:
    rts

// ------------------------------------------------------------------------------
// Voice 1 50Hz Fast Arpeggiator (Triad chord cycling)
// ------------------------------------------------------------------------------
update_arpeggio:
    ldx arp_step
    inx
    cpx #$03
    bne arp_ok
    ldx #$00
arp_ok:
    stx arp_step

    lda lead_notes_lo,x
    sta SID_V1_FREQ_LO
    lda lead_notes_hi,x
    sta SID_V1_FREQ_HI
    lda #$21            // Sawtooth + Gate ON
    sta SID_V1_CTRL
    rts

// ------------------------------------------------------------------------------
// Voice 2 Dynamic Pulse Width Modulation (Lush analog chorus)
// ------------------------------------------------------------------------------
update_pwm:
    lda pwm_counter
    clc
    adc #$10
    sta pwm_counter
    sta SID_V2_PW_LO
    lda #$08
    adc #$00
    sta SID_V2_PW_HI
    rts

// ------------------------------------------------------------------------------
// Master Filter Sweep
// ------------------------------------------------------------------------------
update_filter:
    lda filter_val
    clc
    adc #$02
    sta filter_val
    sta SID_FLT_HI
    rts

// ==============================================================================
// Data Tables
// ==============================================================================
frame_counter:  .byte $00
seq_index:      .byte $00
arp_step:       .byte $00
pwm_counter:    .byte $00
filter_val:     .byte $40

// Bass Sequence Notes (C-2, G-2, A#2, F-2...)
bass_notes:     .byte $5d, $5d, $8b, $8b, $75, $75, $68, $68
bass_notes_hi:  .byte $04, $04, $04, $04, $04, $04, $04, $04

// Lead Arpeggio Frequencies (C Major Triad: C-4, E-4, G-4)
lead_notes_lo:  .byte $74, $d5, $2d
lead_notes_hi:  .byte $11, $11, $12
