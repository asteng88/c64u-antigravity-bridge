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
.const SID_V2_PW_HI     = $d40a
.const SID_V2_CTRL      = $d40b
.const SID_V2_AD        = $d40c
.const SID_V2_SR        = $d40d

.const SID_V3_FREQ_LO   = $d40e
.const SID_V3_FREQ_HI   = $d40f
.const SID_V3_PW_LO     = $d410
.const SID_V3_PW_HI     = $d411
.const SID_V3_CTRL      = $d412
.const SID_V3_AD        = $d413
.const SID_V3_SR        = $d414

.const SID_FLT_LO       = $d415
.const SID_FLT_HI       = $d416
.const SID_FLT_RES      = $d417
.const SID_VOLUME       = $d418

.const SCREEN_RAM       = $0400
.const COLOR_RAM        = $d800
.const SPRITE_PTRS      = $07f8
.const CHARSET_RAM      = $3000

// Custom tile screen codes ($C0-$CB in RAM charset at $3000)
.const CHAR_LED_BASE    = $c0       // $C0..$C8 = 0/8 to 8/8 segmented LED bars
.const CHAR_STAR_TILE   = $c9       // Animated top/bottom shimmer tile
.const CHAR_PILLAR_TILE = $ca       // Animated side plasma pillar tile
.const CHAR_DIVIDER     = $cb       // Crisp horizontal separator line

// Zero-Page State ($02-$2F)
.const zp_frame         = $02
.const zp_frame_ready   = $03
.const zp_scroll_x      = $04
.const zp_need_shift    = $05
.const zp_scroll_ptr    = $06       // 16-bit pointer ($06-$07)
.const zp_spr_phase_x   = $08
.const zp_spr_phase_y   = $09
.const zp_spr_anim      = $0a
.const zp_color_phase   = $0b

// SID Engine Zero-Page State
.const zp_tick          = $10
.const zp_step          = $11
.const zp_chord_idx     = $12
.const zp_v1_note       = $13
.const zp_v1_arp_on     = $14
.const zp_arp_tick      = $15
.const zp_vib_phase     = $16
.const zp_pwm_phase     = $17
.const zp_flt_phase     = $18
.const zp_drum_type     = $19
.const zp_drum_frame    = $1a
.const zp_drum_flash    = $1b

// Shadow Registers for Live HUD & Spectrum Analyzer
.const sh_v1_lo         = $1c
.const sh_v1_hi         = $1d
.const sh_v2_lo         = $1e
.const sh_v2_hi         = $1f
.const sh_flt_hi        = $20
.const sh_pw_hi         = $21
.const zp_v1_energy     = $22
.const zp_v2_energy     = $23
.const zp_v3_energy     = $24
.const zp_temp          = $25
.const zp_temp2         = $26

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

    // Install custom LED bar & animated background tiles at $3000 + $C0*8 ($3600)
    ldx #$00
install_tiles_loop:
    lda custom_tiles, x
    sta CHARSET_RAM + (CHAR_LED_BASE * 8), x
    inx
    cpx #(12 * 8)
    bne install_tiles_loop

    // Clear Zero-Page variables ($02-$2F)
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

    // Build static screen layout, analyzer color gradient, sprites, and SID
    jsr init_screen
    jsr init_sprites
    jsr init_sid

    // Set safe NMI vector (prevents RESTORE key crash when KERNAL is banked out)
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

    jsr update_spectrum_bars    // Compute & render 16-band 64px LED analyzer
    jsr animate_custom_tiles    // Morph RAM charset background tiles
    jsr update_color_wash       // Cycle rainbow colors on header & scroller
    jsr update_hud_telemetry    // Print live SID frequencies, filter & PW in hex

    jmp main_loop

nmi_rti:
    rti

// ==============================================================================
// RASTER IRQ CHAIN (5-Stage Split — 100% PAL & NTSC Compatible)
//   Stage 1 ($2A): Reset 40-col header, update 8 Lissajous sprites
//   Stage 2 ($5B): Top metallic cyan copper beam (Row 5) + 50Hz/60Hz SID Synth
//   Stage 3 ($BB): Beat-reactive warm copper beam (Row 17)
//   Stage 4 ($D9): Apply $D016 smooth hardware fine scroll (Row 21)
//   Stage 5 ($E3): Restore static footer & shift scroller characters safely
// ==============================================================================
irq_top:
    pha
    txa
    pha
    tya
    pha

    lda #$c8
    sta VIC_CTRL2               // Lock 40-col static header & visualizer

    inc zp_frame
    lda #$01
    sta zp_frame_ready

    jsr update_sprites          // Update 8 sprites before top of display

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

// ------------------------------------------------------------------------------
// Stage 2 ($5B): Top Copper Beam across lines $5C..$62 + SID Engine Step
// ------------------------------------------------------------------------------
irq_bar1:
    pha
    txa
    pha
    tya
    pha

    ldx #$00
    ldy #$5c                    // Bad-line-free window ($5C..$62) inside Row 5
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

    // Run 3-Voice SID Synthesizer & Sequencer at steady once-per-frame timing
    jsr sid_play

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

// ------------------------------------------------------------------------------
// Stage 3 ($BB): Beat-Reactive Copper Beam across lines $BC..$C2 (Row 17)
// ------------------------------------------------------------------------------
irq_bar2:
    pha
    txa
    pha
    tya
    pha

    ldx #$00
    ldy #$bc                    // Bad-line-free window ($BC..$C2) inside Row 17
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

// ------------------------------------------------------------------------------
// Stage 4 ($D9): Smooth 38-Column Hardware Fine Scroller on Row 21 ($DA..$E2)
// ------------------------------------------------------------------------------
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
    and #$07                    // Bits 0..2 = fine X scroll, bit 3 = 0 (38-col mode)
    ora #$c0
    sta VIC_CTRL2

    // Advance smooth scroll by 1 pixel per frame
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

// ------------------------------------------------------------------------------
// Stage 5 ($E3): Restore 40-Column Footer & Shift Scroller Text After Raster Pass
// ------------------------------------------------------------------------------
irq_bottom:
    pha
    txa
    pha
    tya
    pha

    lda #$c8                    // 40-col mode ($08), standard text, scroll = 0
    sta VIC_CTRL2

    lda zp_need_shift
    beq skip_char_shift
    lda #$00
    sta zp_need_shift

    // Shift Row 21 ($0400 + 21*40 = $0748) left by 1 character
    ldx #$00
shift_row21:
    lda SCREEN_RAM + 21 * 40 + 1, x
    sta SCREEN_RAM + 21 * 40, x
    inx
    cpx #39
    bne shift_row21

    // Fetch next character from scroll_message
    ldy #$00
    lda (zp_scroll_ptr), y
    bne got_scroll_char

    // Wrap around to start of scroll_message on $00 terminator
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
// 3-VOICE SID SYNTHESIZER & SEQUENCER ENGINE
//   Voice 1: Melodic Lead with Vibrato + 50Hz Chord Triad Arpeggiator (Saw/Pulse)
//   Voice 2: Octave-Bouncing Analog Bass with Sine PWM Chorus (Pulse, Filtered)
//   Voice 3: 5-Frame Wavetable Percussion (Kick / Snare / Closed & Open Hi-Hats)
//   Filter : 11-Bit Resonant Low-Pass Sine Sweep + Bass Envelope Accent
// ==============================================================================
init_sid:
    ldx #$18
    lda #$00
clear_sid:
    sta SID_BASE, x
    dex
    bpl clear_sid

    // Voice 1 ADSR: Crisp attack, singing sustain, smooth release
    lda #$09
    sta SID_V1_AD
    lda #$b4
    sta SID_V1_SR
    lda #$06
    sta SID_V1_PW_HI

    // Voice 2 ADSR: Punchy analog bass pluck
    lda #$08
    sta SID_V2_AD
    lda #$93
    sta SID_V2_SR
    lda #$08
    sta SID_V2_PW_HI

    // Filter routing: Route Voice 2 (Bass) + Voice 1 (Lead) with high resonance
    lda #$93                    // Resonance = 9 ($90), Filter V1 + V2 ($03)
    sta SID_FLT_RES
    lda #$1f                    // Low-Pass mode ($10) + Master Volume 15 ($0F)
    sta SID_VOLUME

    // Start immediately on step 0 when first frame runs
    lda #$05
    sta zp_tick
    lda #$3f
    sta zp_step
    rts

sid_play:
    // Decay visual voice energy meters smoothly each frame
    lda zp_v1_energy
    beq !+
    sec
    sbc #$02
    bcs !store1+
    lda #$00
!store1:
    sta zp_v1_energy
!:
    lda zp_v2_energy
    beq !+
    sec
    sbc #$03
    bcs !store2+
    lda #$00
!store2:
    sta zp_v2_energy
!:
    lda zp_v3_energy
    beq !+
    sec
    sbc #$04
    bcs !store3+
    lda #$00
!store3:
    sta zp_v3_energy
!:

    // Advance tick (6 frames per 16th-note step)
    inc zp_tick
    lda zp_tick
    cmp #$05
    bne check_new_step

    // Tick 5: Gate-Off Articulation (0->1 transition guarantees crisp ADSR attack!)
    lda #$40                    // Clear Gate on Voice 2 Bass before next 16th note
    sta SID_V2_CTRL

    // Check if next step on Voice 1 triggers a new note (not $00 sustain)
    lda zp_step
    clc
    adc #$01
    and #$3f
    tax
    lda lead_pattern, x
    beq v1_keep_sustain         // $00 = hold tie/sustain across step boundary
    lda #$20                    // Clear Gate on Voice 1 for crisp re-attack
    sta SID_V1_CTRL
v1_keep_sustain:
    jmp sid_modulations

check_new_step:
    cmp #$06
    bcs do_new_step
    jmp sid_modulations

do_new_step:
    // Tick 6 -> Wrap to Tick 0 and advance 64-step pattern!
    lda #$00
    sta zp_tick

    lda zp_step
    clc
    adc #$01
    and #$3f
    sta zp_step
    tax

    // Current chord index = step / 8 (0..7 across 64 steps)
    lsr
    lsr
    lsr
    sta zp_chord_idx

    // --- 1. Trigger Voice 2 PWM Bass Note ---
    ldy bass_pattern, x
    lda sid_freq_lo, y
    sta SID_V2_FREQ_LO
    sta sh_v2_lo
    lda sid_freq_hi, y
    sta SID_V2_FREQ_HI
    sta sh_v2_hi
    lda #$41                    // Pulse waveform + Gate ON
    sta SID_V2_CTRL
    lda #$3c
    sta zp_v2_energy

    // --- 2. Trigger Voice 1 Lead / Arpeggio Note ---
    lda lead_pattern, x
    beq v1_step_done            // $00 = sustain previous note
    cmp #$ff
    bne v1_trigger_note
    lda #$20                    // $FF = note rest (Gate OFF)
    sta SID_V1_CTRL
    lda #$00
    sta zp_v1_arp_on
    jmp v1_step_done

v1_trigger_note:
    tay
    and #$80                    // Bit 7 = enable 50Hz chord arpeggiator on this step
    sta zp_v1_arp_on
    tya
    and #$7f
    sta zp_v1_note
    tay
    lda sid_freq_lo, y
    sta SID_V1_FREQ_LO
    sta sh_v1_lo
    lda sid_freq_hi, y
    sta SID_V1_FREQ_HI
    sta sh_v1_hi
    lda #$00
    sta zp_arp_tick
    lda #$21                    // Sawtooth waveform + Gate ON
    sta SID_V1_CTRL
    lda #$3e
    sta zp_v1_energy
v1_step_done:

    // --- 3. Trigger Voice 3 Wavetable Drum ---
    lda drum_pattern, x
    beq sid_modulations
    sta zp_drum_type
    lda #$00
    sta zp_drum_frame
    lda #$3f
    sta zp_v3_energy

    // Trigger copper bar beat flash on Kick (1) and Snare (2)
    lda zp_drum_type
    cmp #$03
    bcs sid_modulations
    lda #$03
    sta zp_drum_flash

// ------------------------------------------------------------------------------
// Per-Frame 50Hz/60Hz Continuous Synth Modulations
// ------------------------------------------------------------------------------
sid_modulations:
    // --- A. Voice 1 Arpeggio OR Singing Vibrato ---
    lda zp_v1_arp_on
    beq v1_do_vibrato

    // Fast 3-note chord triad arpeggiator (0, +3rd, +5th)
    ldx zp_arp_tick
    inx
    cpx #$03
    bcc !+
    ldx #$00
!:
    stx zp_arp_tick

    ldy zp_chord_idx
    cpx #$00
    beq arp_offset_zero
    cpx #$01
    beq arp_offset_third
    lda chord_fifth, y
    jmp arp_apply_note
arp_offset_third:
    lda chord_third, y
    jmp arp_apply_note
arp_offset_zero:
    lda #$00

arp_apply_note:
    clc
    adc zp_v1_note
    tay
    lda sid_freq_lo, y
    sta SID_V1_FREQ_LO
    sta sh_v1_lo
    lda sid_freq_hi, y
    sta SID_V1_FREQ_HI
    sta sh_v1_hi
    jmp mod_pwm

v1_do_vibrato:
    // Smooth sine vibrato on sustained melody notes (after tick 1)
    lda zp_v1_note
    beq mod_pwm
    lda zp_vib_phase
    clc
    adc #$14
    sta zp_vib_phase
    tax
    ldy zp_v1_note
    lda sid_freq_lo, y
    clc
    adc vib_sine, x
    sta SID_V1_FREQ_LO
    sta sh_v1_lo
    lda sid_freq_hi, y
    ldx zp_vib_phase
    ldy vib_sine, x
    bpl vib_pos
    sbc #$00
    jmp vib_hi_done
vib_pos:
    adc #$00
vib_hi_done:
    sta SID_V1_FREQ_HI
    sta sh_v1_hi

    // --- B. Voice 2 Lush Sine Pulse Width Modulation ($0280..$0D80) ---
mod_pwm:
    lda zp_pwm_phase
    clc
    adc #$03
    sta zp_pwm_phase
    tax
    lda pwm_sine_lo, x
    sta SID_V2_PW_LO
    lda pwm_sine_hi, x
    sta SID_V2_PW_HI
    sta sh_pw_hi

    // --- C. 11-Bit Resonant Low-Pass Filter Sweep + Bass Accent ---
    lda zp_flt_phase
    clc
    adc #$02
    sta zp_flt_phase
    tax
    lda zp_v2_energy
    lsr
    lsr                         // Add punchy bass envelope boost to filter cutoff!
    clc
    adc filter_sine, x
    bcc !+
    lda #$f8
!:
    sta SID_FLT_HI
    sta sh_flt_hi
    lda #$04
    sta SID_FLT_LO

    // --- D. Voice 3 Multi-Frame Wavetable Percussion State Machine ---
    lda zp_drum_type
    bne !active_drum+
    rts
!active_drum:
    ldx zp_drum_frame
    cpx #$05
    bcc !run_drum+
    lda #$00
    sta zp_drum_type
    rts
!run_drum:
    cmp #$01
    beq play_kick
    cmp #$02
    beq play_snare
    cmp #$03
    beq play_hat_closed

    // Type 4: Open Hi-Hat
    lda #$09
    sta SID_V3_AD
    lda #$54
    sta SID_V3_SR
    lda ohat_freq, x
    sta SID_V3_FREQ_HI
    lda ohat_wave, x
    sta SID_V3_CTRL
    inc zp_drum_frame
    rts

play_kick:
    lda #$08
    sta SID_V3_AD
    lda #$a0
    sta SID_V3_SR
    lda #$08
    sta SID_V3_PW_HI
    lda kick_freq_lo, x
    sta SID_V3_FREQ_LO
    lda kick_freq_hi, x
    sta SID_V3_FREQ_HI
    lda kick_wave, x
    sta SID_V3_CTRL
    inc zp_drum_frame
    rts

play_snare:
    lda #$0a
    sta SID_V3_AD
    lda #$42
    sta SID_V3_SR
    lda #$08
    sta SID_V3_PW_HI
    lda snare_freq_hi, x
    sta SID_V3_FREQ_HI
    lda snare_wave, x
    sta SID_V3_CTRL
    inc zp_drum_frame
    rts

play_hat_closed:
    lda #$04
    sta SID_V3_AD
    lda #$00
    sta SID_V3_SR
    lda chat_freq, x
    sta SID_V3_FREQ_HI
    lda chat_wave, x
    sta SID_V3_CTRL
    inc zp_drum_frame
    rts

// ==============================================================================
// SPRITE ENGINE: 8 Spinning Multicolor Hardware Sprites in 3D Lissajous Orbit
// ==============================================================================
init_sprites:
    lda #$06                    // Shared Multicolor 0: Deep Blue
    sta VIC_SPR_MC0
    lda #$01                    // Shared Multicolor 1: Bright White
    sta VIC_SPR_MC1
    lda #$ff                    // All 8 sprites in Multicolor Mode
    sta VIC_SPR_MC
    lda #$aa                    // Odd sprites weave BEHIND LED bars, even IN FRONT!
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
    // Advance Lissajous X/Y phases (2:3 harmonic ratio)
    lda zp_spr_phase_x
    clc
    adc #$02
    sta zp_spr_phase_x

    lda zp_spr_phase_y
    clc
    adc #$03
    sta zp_spr_phase_y

    // Cycle sprite animation frames ($80..$83 at $2000..$20FF) every 4 frames
    lda zp_frame
    lsr
    lsr
    sta zp_spr_anim

    lda #$00
    sta zp_temp                 // Accumulates $D010 9th-bit X MSBs

    ldx #$00
spr_loop:
    // Compute Sprite X (9-bit coordinate across full 320px width)
    txa
    asl
    asl
    asl
    asl                         // Phase spacing = sprite * 16
    clc
    adc zp_spr_phase_x
    tay

    txa
    asl                         // Register offset = sprite * 2
    sta zp_temp2

    lda spr_sin_x_lo, y
    ldy zp_temp2
    sta VIC_SPR0_X, y

    // Check X MSB from high-byte table
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

    // Compute Sprite Y
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

    // Stagger spinning animation frame per sprite ($80..$83)
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
// 16-BAND 64-PIXEL SEGMENTED LED SPECTRUM ANALYZER (Rows 8..15, Cols 4..35)
// ==============================================================================
update_spectrum_bars:
    ldx #$00
spec_calc_loop:
    // Smooth gravity decay on current bar height (0..64)
    lda bar_heights, x
    sec
    sbc #$03
    bcs !+
    lda #$00
!:
    sta bar_heights, x

    // Compute target height per frequency group (0..3 Drums, 4..7 Bass, 8..11 Filter, 12..15 Arp)
    txa
    lsr
    lsr
    cmp #$00
    beq band_drums
    cmp #$01
    beq band_bass
    cmp #$02
    beq band_filter

    // Group 3 (Bars 12..15): Voice 1 Arp/Lead energy + harmonic wave
    lda zp_frame
    asl
    asl
    clc
    adc bar_wave_offsets, x
    tay
    lda spec_wave, y
    clc
    adc zp_v1_energy
    jmp apply_bar_target

band_drums:
    // Group 0 (Bars 0..3): Voice 3 Percussion energy + sub bounce
    lda zp_frame
    asl
    clc
    adc bar_wave_offsets, x
    tay
    lda spec_wave, y
    clc
    adc zp_v3_energy
    jmp apply_bar_target

band_bass:
    // Group 1 (Bars 4..7): Voice 2 PWM Bass energy + pitch modulation
    lda sh_v2_lo
    and #$0f
    clc
    adc zp_v2_energy
    jmp apply_bar_target

band_filter:
    // Group 2 (Bars 8..11): 11-Bit Filter Cutoff + Resonance ripple
    lda sh_flt_hi
    lsr
    lsr
    clc
    adc #$06
    clc
    adc bar_flt_spread, x

apply_bar_target:
    cmp #64
    bcc !+
    lda #64
!:
    cmp bar_heights, x
    bcc draw_this_bar
    sta bar_heights, x

draw_this_bar:
    // Render 8 vertical character cells (Row 15 bottom -> Row 8 top)
    // Each bar is 2 columns wide at column offset Y = 4 + X*2
    txa
    asl
    tay
    lda bar_heights, x
    sta zp_temp                 // Remaining pixel height (0..64)

    .for (var row = 15; row >= 8; row--) {
        lda zp_temp
        beq !empty+
        cmp #$08
        bcc !partial+
        sec
        sbc #$08
        sta zp_temp
        lda #(CHAR_LED_BASE + 8)
        jmp !plot+
    !partial:
        clc
        adc #CHAR_LED_BASE
        pha
        lda #$00
        sta zp_temp
        pla
        jmp !plot+
    !empty:
        lda #CHAR_LED_BASE
    !plot:
        sta SCREEN_RAM + row * 40 + 4, y
        sta SCREEN_RAM + row * 40 + 5, y
    }

    inx
    cpx #16
    beq spec_done
    jmp spec_calc_loop
spec_done:
    rts

// ==============================================================================
// ANIMATED RAM CHARSET TILES, COLOR WASH & LIVE SID TELEMETRY HUD
// ==============================================================================
animate_custom_tiles:
    lda zp_frame
    and #$01
    bne anim_tiles_rts

    // Scroll side plasma pillar tile ($CA) vertically downward
    ldy CHARSET_RAM + (CHAR_PILLAR_TILE * 8) + 7
    ldx #$06
scroll_pillar:
    lda CHARSET_RAM + (CHAR_PILLAR_TILE * 8), x
    sta CHARSET_RAM + (CHAR_PILLAR_TILE * 8) + 1, x
    dex
    bpl scroll_pillar
    sty CHARSET_RAM + (CHAR_PILLAR_TILE * 8)

    // Barrel-rotate top/bottom star shimmer tile ($C9) horizontally
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
    sta COLOR_RAM + 1 * 40, x   // Row 1: Title rainbow wave
    sta COLOR_RAM + 21 * 40, x  // Row 21: Fine scroller rainbow wave
    dex
    bpl color_wash_loop
    rts

update_hud_telemetry:
    // STEP:XX at Row 3, Col 6
    lda zp_step
    ldx #(3 * 40 + 6)
    jsr print_hex_byte

    // V1:XXXX at Row 3, Col 13
    lda sh_v1_hi
    ldx #(3 * 40 + 13)
    jsr print_hex_byte
    lda sh_v1_lo
    ldx #(3 * 40 + 15)
    jsr print_hex_byte

    // V2:XXXX at Row 3, Col 22
    lda sh_v2_hi
    ldx #(3 * 40 + 22)
    jsr print_hex_byte
    lda sh_v2_lo
    ldx #(3 * 40 + 24)
    jsr print_hex_byte

    // FLT:XX at Row 3, Col 32
    lda sh_flt_hi
    ldx #(3 * 40 + 32)
    jsr print_hex_byte

    // PW:XX at Row 3, Col 38
    lda sh_pw_hi
    ldx #(3 * 40 + 38)
    jsr print_hex_byte
    rts

// Prints byte in A as 2 hex digits at SCREEN_RAM + 0,X (Row 3 is within first 256 bytes!)
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
    // Clear all 1000 screen chars to space ($20) and colors to Light Blue ($0E)
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

    // Row 0: Animated top shimmer border
    ldx #39
row0_loop:
    lda #CHAR_STAR_TILE
    sta SCREEN_RAM + 0 * 40, x
    lda #$06
    sta COLOR_RAM + 0 * 40, x

    // Row 1: Title
    lda txt_title, x
    sta SCREEN_RAM + 1 * 40, x

    // Row 2: Subtitle
    lda txt_subtitle, x
    sta SCREEN_RAM + 2 * 40, x
    lda #$03
    sta COLOR_RAM + 2 * 40, x

    // Row 3: Live HUD Telemetry
    lda txt_hud, x
    sta SCREEN_RAM + 3 * 40, x
    lda #$07
    sta COLOR_RAM + 3 * 40, x

    // Row 7: Analyzer Band Group Labels
    lda txt_bands, x
    sta SCREEN_RAM + 7 * 40, x
    lda #$01
    sta COLOR_RAM + 7 * 40, x

    // Rows 20 & 23: Crisp Scroller Frame Dividers
    lda #CHAR_DIVIDER
    sta SCREEN_RAM + 20 * 40, x
    sta SCREEN_RAM + 23 * 40, x
    lda #$06
    sta COLOR_RAM + 20 * 40, x
    sta COLOR_RAM + 23 * 40, x

    // Row 24: Footer Synth Legend
    lda txt_footer, x
    sta SCREEN_RAM + 24 * 40, x
    lda #$03
    sta COLOR_RAM + 24 * 40, x

    dex
    bpl row0_loop

    // Row 16: Analyzer Base Floor Line (Cols 4..35)
    ldx #31
floor_loop:
    lda #CHAR_DIVIDER
    sta SCREEN_RAM + 16 * 40 + 4, x
    lda #$0b
    sta COLOR_RAM + 16 * 40 + 4, x
    dex
    bpl floor_loop

    // Paint Studio LED Color Gradient across Analyzer Rows 8..15 & Side Pillars
    .for (var r = 8; r <= 15; r++) {
        .var led_col = $03
        .if (r == 8)  .eval led_col = $01   // Peak: Bright White
        .if (r == 9)  .eval led_col = $02   // Clip: Red
        .if (r == 10) .eval led_col = $0a   // High: Light Red
        .if (r == 11) .eval led_col = $08   // Upper-Mid: Orange
        .if (r == 12) .eval led_col = $07   // Mid: Yellow
        .if (r == 13) .eval led_col = $0d   // Lower-Mid: Light Green
        .if (r == 14) .eval led_col = $05   // Low: Green
        .if (r == 15) .eval led_col = $03   // Sub: Cyan

        ldx #31
    !grad_loop:
        lda #led_col
        sta COLOR_RAM + r * 40 + 4, x
        dex
        bpl !grad_loop-

        // Animated cyber-pillars on Columns 1 & 38
        lda #CHAR_PILLAR_TILE
        sta SCREEN_RAM + r * 40 + 1
        sta SCREEN_RAM + r * 40 + 38
        lda #$04
        sta COLOR_RAM + r * 40 + 1
        sta COLOR_RAM + r * 40 + 38
    }
    rts

// ==============================================================================
// COMPILE-TIME MATHEMATICAL & CHROMATIC PITCH TABLES
// ==============================================================================
.const PAL_CLOCK = 985248.0
.function sidPitch(n) {
    .var p = round(440.0 * pow(2.0, (n - 57.0) / 12.0) * 16777216.0 / PAL_CLOCK)
    .return p > 65535 ? 65535 : p
}

sid_freq_lo:
    .fill 84, <sidPitch(i)
sid_freq_hi:
    .fill 84, >sidPitch(i)

// 9-bit Sprite X Sine Table (Center = 172, Amplitude = 130 -> X = 42..302)
spr_sin_x_lo:
    .fill 256, <round(172.0 + 130.0 * sin(toRadians(i * 360.0 / 256.0)))
spr_sin_x_hi:
    .fill 256, >round(172.0 + 130.0 * sin(toRadians(i * 360.0 / 256.0)))

// Sprite Y Sine Table (Center = 136, Amplitude = 34 -> Y = 102..170 over Analyzer)
spr_sin_y:
    .fill 256, round(136.0 + 34.0 * sin(toRadians(i * 360.0 / 256.0)))

// Voice 1 Signed Vibrato Table (-12..+12 frequency units)
vib_sine:
    .fill 256, <round(12.0 * sin(toRadians(i * 360.0 / 256.0)))

// Voice 2 12-bit PWM Sine Sweep ($0280..$0D80)
pwm_sine_lo:
    .fill 256, <round($0800 + $0580 * sin(toRadians(i * 360.0 / 256.0)))
pwm_sine_hi:
    .fill 256, >round($0800 + $0580 * sin(toRadians(i * 360.0 / 256.0)))

// 11-bit Filter Cutoff Sine Sweep ($24..$AC)
filter_sine:
    .fill 256, round($68 + $44 * sin(toRadians(i * 360.0 / 256.0)))

// Spectrum Harmonic Ripple Wave (0..18)
spec_wave:
    .fill 256, round(9.0 + 9.0 * sin(toRadians(i * 360.0 / 256.0)))

// ==============================================================================
// 64-STEP CHIPTUNE SEQUENCER DATA (Am -> C -> F -> G -> Am -> Em -> F -> E7)
// Note Reference: C2=24, E2=28, F2=29, G2=31, A2=33, B2=35, C3=36, D3=38, E3=40
//                 A4=57, B4=59, C5=60, D5=62, E5=64, F5=65, G5=67, G#4=56, A5=69
// ==============================================================================
// Chord Triad Intervals per 8-step half-bar: Am, C, F, G, Am, Em, F, E7
chord_third:
    .byte 3, 4, 4, 4, 3, 3, 4, 4
chord_fifth:
    .byte 7, 7, 7, 7, 7, 7, 7, 7

// Voice 2: Driving Octave-Jumping 16th-Note Analog Bass
bass_pattern:
    // Bar 1: Am (A1=21, A2=33) | C (C2=24, C3=36)
    .byte 21, 33, 21, 33, 24, 21, 28, 33,  24, 36, 24, 36, 28, 24, 31, 36
    // Bar 2: F (F1=17, F2=29)  | G (G1=19, G2=31)
    .byte 17, 29, 17, 29, 21, 17, 24, 29,  19, 31, 19, 31, 23, 19, 26, 31
    // Bar 3: Am (A1=21, A2=33) | Em (E1=16, E2=28)
    .byte 21, 33, 21, 33, 36, 33, 28, 24,  16, 28, 16, 28, 19, 16, 23, 28
    // Bar 4: F (F1=17, F2=29)  | E7 Turnaround (E1=16, E2=28, G#2=32, B2=35)
    .byte 17, 29, 17, 29, 24, 29, 33, 29,  16, 28, 20, 28, 23, 28, 32, 35

// Voice 1: Lead Melody + Chord Arpeggios ($80 bit = 50Hz triad arpeggio!)
// $00 = sustain/tie previous note, $FF = rest
lead_pattern:
    // Bar 1: Am -> C
    .byte 57, $00, 60, 64,  57|$80, $00, 62, 60,   64, $00, 67, 64,  48|$80, $00, 60, 62
    // Bar 2: F -> G
    .byte 65, $00, 64, 60,  53|$80, $00, 57, 60,   62, $00, 64, 67,  55|$80, $00, 62, 59
    // Bar 3: Am -> Em
    .byte 69, $00, 67, 64,  57|$80, $00, 60, 64,   67, $00, 64, 59,  52|$80, $00, 55, 59
    // Bar 4: F -> E7 Dramatic Turnaround
    .byte 65, $00, 64, 62,  60, $00, 57, 60,       64, $00, 52|$80, $00, 68, 64, 59, 56

// Voice 3: Percussion Pattern (1=Kick, 2=Snare, 3=Closed Hat, 4=Open Hat)
drum_pattern:
    .byte 1, 3, 4, 3,  2, 3, 1, 4,   1, 3, 4, 1,  2, 3, 4, 3
    .byte 1, 3, 4, 3,  2, 3, 1, 4,   1, 1, 4, 3,  2, 3, 2, 4
    .byte 1, 3, 4, 3,  2, 3, 1, 4,   1, 3, 4, 1,  2, 3, 4, 3
    .byte 1, 3, 4, 3,  2, 3, 1, 4,   1, 2, 1, 2,  1, 2, 4, 2

// Wavetable Drum Tables (5 frames per hit)
kick_freq_lo:   .byte $00, $40, $e0, $20, $90
kick_freq_hi:   .byte $16, $05, $02, $02, $01
kick_wave:      .byte $81, $51, $11, $11, $10

snare_freq_hi:  .byte $2c, $07, $3c, $26, $1c
snare_wave:     .byte $81, $51, $81, $81, $80

chat_freq:      .byte $6c, $78, $78, $00, $00
chat_wave:      .byte $81, $80, $00, $00, $00

ohat_freq:      .byte $66, $70, $74, $70, $68
ohat_wave:      .byte $81, $81, $81, $81, $80

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

bar_heights:
    .fill 16, 0
bar_wave_offsets:
    .fill 16, i * 19
bar_flt_spread:
    .byte 0, 0, 0, 0,  0, 0, 0, 0,  2, 8, 12, 5,  0, 0, 0, 0

// 12 Custom 8x8 Characters ($C0..$CB):
//   $C0..$C8: 0/8 through 8/8 Segmented Studio LED Analyzer Bars
//   $C9     : Animated Top/Bottom Shimmer Border Tile
//   $CA     : Animated Vertical Plasma Pillar Tile
//   $CB     : Crisp Horizontal Frame Divider
custom_tiles:
    // $C0 (0/8 LED: faint grid dot at bottom)
    .byte %00000000, %00000000, %00000000, %00000000, %00000000, %00000000, %00000000, %00011000
    // $C1 (1/8 LED)
    .byte %00000000, %00000000, %00000000, %00000000, %00000000, %00000000, %00000000, %01111110
    // $C2 (2/8 LED)
    .byte %00000000, %00000000, %00000000, %00000000, %00000000, %00000000, %01111110, %01111110
    // $C3 (3/8 LED)
    .byte %00000000, %00000000, %00000000, %00000000, %00000000, %01111110, %00000000, %01111110
    // $C4 (4/8 LED)
    .byte %00000000, %00000000, %00000000, %00000000, %01111110, %01111110, %00000000, %01111110
    // $C5 (5/8 LED)
    .byte %00000000, %00000000, %00000000, %01111110, %00000000, %01111110, %00000000, %01111110
    // $C6 (6/8 LED)
    .byte %00000000, %00000000, %01111110, %01111110, %00000000, %01111110, %00000000, %01111110
    // $C7 (7/8 LED)
    .byte %00000000, %01111110, %00000000, %01111110, %00000000, %01111110, %00000000, %01111110
    // $C8 (8/8 Full Segmented LED Block)
    .byte %01111110, %01111110, %00000000, %01111110, %01111110, %00000000, %01111110, %01111110
    // $C9 (Animated Shimmer Tile)
    .byte %00000000, %10001000, %01010000, %00100010, %01010000, %10001000, %00000000, %00000000
    // $CA (Animated Vertical Plasma Pillar)
    .byte %00111100, %01100110, %01011010, %00111100, %00011000, %00100100, %01000010, %00111100
    // $CB (Horizontal Frame Divider)
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
    .text "     DRUMS  PWM BASS FILTER ARP LEAD    "
txt_footer:
    .text " V1:SAW/ARP  V2:PULSE/PWM  V3:WAVEDRUMS "

scroll_message:
    .text "   *** WELCOME TO THE COMMODORE 64 SID SYNTHESIZER & ANIMATED GRAPHICS DEMO! ***   "
    .text "FEATURING REAL-TIME 3-VOICE MOS 6581/8580 SYNTHESIS: VOICE 1 SAWTOOTH MELODY WITH VIBRATO & 50HZ CHORD ARPEGGIOS... "
    .text "VOICE 2 OCTAVE BASSLINE WITH LUSH 12-BIT SINE PULSE-WIDTH MODULATION ROUTED THROUGH THE 11-BIT RESONANT LOW-PASS FILTER... "
    .text "VOICE 3 5-FRAME WAVETABLE KICK, SNARE & HI-HAT PERCUSSION... "
    .text "ACCOMPANIED BY 8 SPINNING MULTICOLOR HARDWARE SPRITES IN 3D LISSAJOUS ORBITS, BEAT-REACTIVE COPPER BARS, AND A 16-BAND LED SPECTRUM ANALYZER!   "
    .byte $00

// ==============================================================================
// MULTICOLOR HARDWARE SPRITE FRAMES ($2000-$20FF -> Pointers $80..$83)
// Pixel Encoding: 00 = Transparent, 01 = MC0 (Blue), 10 = Sprite Color, 11 = MC1 (White)
// ==============================================================================
* = $2000 "Spinning Synth Orb Sprites"

// Frame 0 ($80): Glowing Synth Orb (Vertical Specular Core)
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

// Frame 1 ($81): Spinning Ring (Diagonal Highlight A)
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

// Frame 2 ($82): Glowing Synth Orb (Horizontal Equator Pulse)
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

// Frame 3 ($83): Spinning Ring (Diagonal Highlight B)
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
