// ==============================================================================
// VIDEO KILLED THE RADIO STAR - THE BUGGLES (1979)
// COMMODORE 64 ULTIMATE (C64U) FULL SID SYMPHONY & DEMO
// Target Assembler: KickAssembler v5.x
// Architecture: MOS 6510 CPU / MOS 6581/8580 Sound Interface Device (SID)
// ==============================================================================

BasicUpstart2(entry_point)

* = $0810 "Radio Star SID Symphony"

// Safe Zero Page Scratchpad Pointers
.const ZP_PTR_LO        = $fb
.const ZP_PTR_HI        = $fc

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
.const SID_V3_PW_LO     = $d410
.const SID_V3_PW_HI     = $d411
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

.const SCREEN_RAM       = $0400
.const COLOR_RAM        = $d800

.const TOTAL_STEPS      = 320
// Build for PAL by default. Set true and rebuild for NTSC.
.const NTSC = false
.const SID_CLOCK = NTSC ? 1022727 : 985248
.const FRAME_RATE = NTSC ? 59.826 : 50.125
.const BPM = 131
// 16-bit phase accumulator: four sixteenth-note steps per quarter note.
.const STEP_RATE = round(BPM * 4 * 65536 / (60 * FRAME_RATE))
.encoding "screencode_upper"

// ==============================================================================
// Initialization Entry Point
// ==============================================================================
entry_point:
    sei

    // Set screen styling: Black background, dark grey border
    lda #$00
    sta VIC_BG
    lda #$0b            // Dark grey border
    sta VIC_BORDER

    // Clear SID registers
    ldx #$18
    lda #$00
clear_sid:
    sta SID_BASE,x
    dex
    bpl clear_sid

    // Clear Screen RAM and Color RAM
    ldx #$00
clear_screen_loop:
    lda #$20            // Space
    sta SCREEN_RAM,x
    sta SCREEN_RAM+$100,x
    sta SCREEN_RAM+$200,x
    sta SCREEN_RAM+$2e8,x
    lda #$0e            // Light Blue text
    sta COLOR_RAM,x
    sta COLOR_RAM+$100,x
    sta COLOR_RAM+$200,x
    sta COLOR_RAM+$2e8,x
    inx
    bne clear_screen_loop

    // Draw the static UI / Title Screen
    jsr draw_title_screen

    // Set Master Volume to Maximum (15) and enable Low-Pass Filter
    lda #$1f            // Low-pass mode ($10) + Volume 15 ($0F)
    sta SID_VOLUME

    // Route Voice 2 ONLY through Filter (Chords), keep Voice 1 (Lead) and Voice 3 direct
    lda #$72            // Resonance 7 ($70) + Filter Voice 2 ONLY ($02)
    sta SID_FLT_RES

    // Initialize Voice 1 (Melodic Lead): Punchy attack, solid sustain
    lda #$08            // Attack: 0, Decay: 8
    sta SID_V1_AD
    lda #$d4            // Sustain: 13, Release: 4
    sta SID_V1_SR

    // Initialize Voice 2 (Chords & PWM): Fast attack, punchy decay
    lda #$06            // Attack: 0, Decay: 6
    sta SID_V2_AD
    lda #$52            // Quieter harmony, leaving room for the lead
    sta SID_V2_SR
    lda #$08            // Default 50% pulse width ($0800)
    sta SID_V2_PW_HI
    lda #$00
    sta SID_V2_PW_LO

    // Initialize Voice 3 (Rhythm & Bass): Sharp percussive envelopes
    lda #$05
    sta SID_V3_AD
    lda #$a2
    sta SID_V3_SR

    // Play step zero immediately, rather than skipping its chord and kick.
    jsr fetch_step_events

    // Hook custom Raster Interrupt (PAL / NTSC Line 0)
    lda #$7f
    sta $dc0d           // Disable CIA1 timer interrupts
    lda $dc0d           // Acknowledge any pending CIA interrupt

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

// Main idle loop (Wait for interrupts)
main_loop:
    jmp main_loop

// ==============================================================================
// 50Hz Frame Interrupt Handler
// ==============================================================================
irq_handler:
    asl VIC_IRQ_STATUS  // Acknowledge VIC-II IRQ

    // Check border flash timer (snare punch)
    lda border_flash
    beq flash_done
    dec border_flash
    bne flash_done
    lda #$0b            // Return border to dark grey
    sta VIC_BORDER
flash_done:

    // Advance old drum state BEFORE triggering a new hit. A one-frame hat
    // must survive until the next IRQ rather than disappearing immediately.
    jsr update_v3_drums
    clc
    lda tempo_lo
    adc #<STEP_RATE
    sta tempo_lo
    lda tempo_hi
    adc #>STEP_RATE
    sta tempo_hi
    bcc no_music_step
    jsr step_sequencer
    jmp modulation
no_music_step:
    // Predict next frame's overflow and release one frame before a note.
    clc
    lda tempo_lo
    adc #<STEP_RATE
    lda tempo_hi
    adc #>STEP_RATE
    bcc modulation
    jsr check_v1_gate_cut
    jsr check_v3_gate_cut
modulation:
    jsr update_v1_vibrato
    jsr update_v2_chords_pwm

    jsr update_filter

    // 3. 50Hz Demoscene Screen Telemetry & Animation
    jsr update_visualizer

    jmp $ea81           // Return to standard Kernal IRQ

// ==============================================================================
// Music Step Sequencer (131 BPM fractional-frame timing)
// ==============================================================================
step_sequencer:
    // Advance step pointer
    inc step_lo
    bne step_lo_ok
    inc step_hi
step_lo_ok:

    // Check if reached end of song
    lda step_hi
    cmp #>TOTAL_STEPS
    bne step_not_end
    lda step_lo
    cmp #<TOTAL_STEPS
    bne step_not_end
    // Loop back to step 0
    lda #$00
    sta step_lo
    sta step_hi
step_not_end:

    jsr fetch_step_events
    rts

// ------------------------------------------------------------------------------
// Fetch Events for the Current Step
// ------------------------------------------------------------------------------
fetch_step_events:
    lda step_hi
    beq fetch_low_page

    // Second page (step_hi == 1, steps 256..511)
    cmp #$01
    bne fetch_page_2
    ldx step_lo
    lda v1_seq+256,x
    sta cur_v1_note
    lda v2_seq+256,x
    sta cur_v2_chord
    lda v3_seq+256,x
    sta cur_v3_event
    lda bass_seq+256,x
    sta cur_bass_note
    jmp process_step_events

fetch_page_2:
    // Third page (step_hi == 2, steps 512+)
    ldx step_lo
    lda v1_seq+512,x
    sta cur_v1_note
    lda v2_seq+512,x
    sta cur_v2_chord
    lda v3_seq+512,x
    sta cur_v3_event
    lda bass_seq+512,x
    sta cur_bass_note
    jmp process_step_events

fetch_low_page:
    // First page (step_hi == 0, steps 0..255)
    ldx step_lo
    lda v1_seq,x
    sta cur_v1_note
    lda v2_seq,x
    sta cur_v2_chord
    lda v3_seq,x
    sta cur_v3_event
    lda bass_seq,x
    sta cur_bass_note

process_step_events:
    // --- 1. Process Voice 1 (Lead Note) ---
    lda cur_v1_note
    beq v1_no_change    // 0 = Rest / sustain
    cmp #$ff
    beq v1_gate_off     // 255 = Gate off

    // Note Trigger
    sta v1_note_idx
    tax
    lda sid_freq_lo,x
    sta v1_base_freq_lo
    sta SID_V1_FREQ_LO
    lda sid_freq_hi,x
    sta v1_base_freq_hi
    sta SID_V1_FREQ_HI

    // Gate has already been released for one frame by the lookahead.
    lda #$20
    sta SID_V1_CTRL
    // Sawtooth + Gate ON
    lda #$21
    sta SID_V1_CTRL
    lda #$00
    sta v1_vib_counter
    sta v1_vib_active
    sta v1_vib_phase

    // Set VU meter for Voice 1
    lda #16
    sta v1_vu_val
    jmp v1_no_change

v1_gate_off:
    lda #$20            // Gate OFF
    sta SID_V1_CTRL
    lda #$00
    sta v1_note_idx
v1_no_change:

    // --- 2. Process Voice 2 (Chord) ---
    lda cur_v2_chord
    beq v2_no_change
    sta v2_active_chord
    lda #$00
    sta v2_arp_phase
    lda #$41            // Pulse + Gate ON
    sta SID_V2_CTRL
    // Boost VU meter for Voice 2
    lda #16
    sta v2_vu_val
v2_no_change:

    // The bass score is independent of percussion, so a new bass pitch
    // is not delayed or lost when it falls on the kick/snare/hat step.
    lda cur_bass_note
    beq bass_root_ready
    sta v3_active_bass
bass_root_ready:

    lda cur_v3_event
    beq restore_bass
    cmp #1
    beq trigger_kick
    cmp #2
    beq trigger_snare
    cmp #3
    beq trigger_hat
    sta v3_active_bass
    lda #0
    sta v3_drum_timer
restore_bass:
    ldx v3_active_bass
    beq silence_bass
    lda sid_freq_lo,x
    sta SID_V3_FREQ_LO
    lda sid_freq_hi,x
    sta SID_V3_FREQ_HI
    lda #$04
    sta SID_V3_AD
    lda #$72
    sta SID_V3_SR
    lda #$41
    sta SID_V3_CTRL
    lda #0
    sta SID_V3_PW_LO
    lda #$06
    sta SID_V3_PW_HI
    lda #12
    sta v3_vu_val
    rts
silence_bass:
    lda #0
    sta SID_V3_CTRL
    rts
trigger_kick:
    lda #1
    sta v3_drum_type
    lda #3
    sta v3_drum_timer
    lda #$18
    sta SID_V3_FREQ_HI
    lda #$11
    jmp start_drum
trigger_snare:
    lda #2
    sta v3_drum_type
    lda #3
    sta v3_drum_timer
    lda #$24
    sta SID_V3_FREQ_HI
    lda #1
    sta VIC_BORDER
    lda #2
    sta border_flash
    lda #$81
    jmp start_drum
trigger_hat:
    lda #3
    sta v3_drum_type
    lda #1
    sta v3_drum_timer
    lda #$70
    sta SID_V3_FREQ_HI
    lda #$81
start_drum:
    pha
    lda #0
    sta SID_V3_FREQ_LO
    lda #$03
    sta SID_V3_AD
    lda #$a0
    sta SID_V3_SR
    pla
    sta SID_V3_CTRL
    lda #16
    sta v3_vu_val
    rts


// ==============================================================================
// 50Hz Voice 1 Vibrato (16-bit safe)
// ==============================================================================
update_v1_vibrato:
    lda v1_note_idx
    beq vib_done
    lda v1_vib_counter
    cmp #12
    bcs vibrato_ready
    inc v1_vib_counter
vibrato_ready:
    lda v1_vib_counter
    cmp #12             // Delayed vibrato leaves short vocal notes clear
    bcc vib_done
    lda #$01
    sta v1_vib_active

    // Advance vibrato sine phase
    inc v1_vib_phase
    lda v1_vib_phase
    and #$07
    tax
    lda v1_base_freq_lo
    clc
    adc vib_table_lo,x
    sta SID_V1_FREQ_LO
    lda v1_base_freq_hi
    adc vib_table_hi,x
    sta SID_V1_FREQ_HI
vib_done:
    rts

vib_table_lo:
    .byte $00, $01, $02, $01, $00, $ff, $fe, $ff
vib_table_hi:
    .byte $00, $00, $00, $00, $00, $ff, $ff, $ff

// ==============================================================================
// Check if next step triggers a new note; if so, clear gate for articulation
// ==============================================================================
check_v1_gate_cut:
    lda step_lo
    clc
    adc #$01
    sta temp_next_lo
    lda step_hi
    adc #$00
    sta temp_next_hi

    // If next step >= TOTAL_STEPS (320), wrap to 0
    cmp #>TOTAL_STEPS
    bne next_step_wrap_ok
    lda temp_next_lo
    cmp #<TOTAL_STEPS
    bne next_step_wrap_ok
    lda #$00
    sta temp_next_lo
    sta temp_next_hi
next_step_wrap_ok:

    // Fetch next step's v1 note
    lda temp_next_hi
    beq next_page_0
    cmp #$01
    bne next_page_2
    ldx temp_next_lo
    lda v1_seq+256,x
    jmp check_note_val
next_page_2:
    ldx temp_next_lo
    lda v1_seq+512,x
    jmp check_note_val
next_page_0:
    ldx temp_next_lo
    lda v1_seq,x

check_note_val:
    beq gate_cut_done   // If next note is 0 (sustain), keep gate on!
    lda #$20            // Next step has a new note or OFF: Gate OFF!
    sta SID_V1_CTRL
gate_cut_done:
    rts

// ==============================================================================
// 50Hz Voice 2 Chord Arpeggio & Pulse Width Modulation
// ==============================================================================
// Reuse the next-step index calculated by check_v1_gate_cut. Only
// articulate voice 3 when an actual bass or drum event is approaching.
check_v3_gate_cut:
    ldx temp_next_lo
    lda temp_next_hi
    beq v3_cut_page0
    lda v3_seq+256,x
    ora bass_seq+256,x
    jmp v3_cut_test
v3_cut_page0:
    lda v3_seq,x
    ora bass_seq,x
v3_cut_test:
    beq v3_cut_done
    lda #0
    sta SID_V3_SR
    sta SID_V3_CTRL
v3_cut_done:
    rts

update_v2_chords_pwm:
    // 1. Dynamic PWM Sweep (Shimmering analog chorus)
    inc pwm_lfo_idx
    lda pwm_lfo_idx
    and #$3f            // 0..63
    tax
    lda pwm_table_lo,x
    sta SID_V2_PW_LO
    lda pwm_table_hi,x
    sta SID_V2_PW_HI

    // 2. 50Hz Fast Arpeggiator (Cycles Root -> 3rd -> 5th every frame!)
    lda v2_active_chord
    beq arp_done
    tay
    lda chord_offset,y
    clc
    adc v2_arp_phase
    tax
    lda chord_triads,x
    tax
    lda sid_freq_lo,x
    sta SID_V2_FREQ_LO
    lda sid_freq_hi,x
    sta SID_V2_FREQ_HI

    // Advance arpeggio phase (0, 1, 2)
    inc v2_arp_phase
    lda v2_arp_phase
    cmp #$03
    bcc arp_done
    lda #$00
    sta v2_arp_phase

arp_done:
    rts

chord_offset:
    .byte 0, 0, 3, 6, 9, 12, 15, 18

chord_triads:
    .byte 37, 41, 44    // Db
    .byte 39, 42, 46    // Ebm
    .byte 44, 49, 51    // Absus4
    .byte 44, 48, 51    // Ab
    .byte 42, 46, 49    // Gb
    .byte 41, 44, 48    // Fm
    .byte 34, 37, 41    // Bbm


// ==============================================================================
// 50Hz Voice 3 Drum State Machine (Restores Bass after hits)
// ==============================================================================
update_v3_drums:
    lda v3_drum_timer
    beq drums_done
    dec v3_drum_timer
    beq drum_finished
    ldx v3_drum_timer
    lda v3_drum_type
    cmp #1
    bne snare_slide
    // SID pitch registers are WRITE ONLY: sweep from a RAM/ROM table.
    lda kick_pitch_hi,x
    sta SID_V3_FREQ_HI
    rts
snare_slide:
    cmp #2
    bne drums_done
    lda snare_pitch_hi,x
    sta SID_V3_FREQ_HI
drums_done:
    rts
drum_finished:
    jmp restore_bass
kick_pitch_hi:
    .byte $00,$02,$07
snare_pitch_hi:
    .byte $00,$0c,$18

// ==============================================================================
// 50Hz Analog Resonant Filter Sweep
// ==============================================================================
update_filter:
    inc filter_lfo
    lda filter_lfo
    and #$7f
    tax
    lda filter_table,x
    sta SID_FLT_HI
    sta filter_cutoff
    rts

// ==============================================================================
// 50Hz Visualizer: VU Meters, Cassette Tape, Radio Waves & Lyrics
// ==============================================================================
update_visualizer:
    // Decay VU meters
    lda v1_vu_val
    beq v1_vu_zero
    dec v1_vu_val
v1_vu_zero:
    lda v2_vu_val
    beq v2_vu_zero
    dec v2_vu_val
v2_vu_zero:
    lda v3_vu_val
    beq v3_vu_zero
    dec v3_vu_val
v3_vu_zero:

    // Draw Voice 1 VU Bar (Row 7, Column 18)
    ldx v1_vu_val
    lda #$07            // Row 7
    jsr draw_horizontal_bar

    // Draw Voice 2 VU Bar (Row 10, Column 18)
    ldx v2_vu_val
    lda #$0a            // Row 10
    jsr draw_horizontal_bar

    // Draw Voice 3 VU Bar (Row 13, Column 18)
    ldx v3_vu_val
    lda #$0d            // Row 13
    jsr draw_horizontal_bar

    // Draw Filter Bar (Row 16, Column 18)
    lda filter_cutoff
    lsr
    lsr
    lsr
    lsr                 // 0..15
    tax
    lda #$10            // Row 16
    jsr draw_horizontal_bar

    // Animate Rotating Cassette Tape Spokes (Row 18)
    inc anim_frame
    lda anim_frame
    lsr
    lsr
    and #$03            // 0..3
    tax
    lda cassette_spokes,x
    sta SCREEN_RAM + 18*40 + 9
    sta SCREEN_RAM + 18*40 + 30

    // Animate Radio Tower Broadcast Waves (Row 22)
    lda anim_frame
    lsr
    lsr
    lsr
    and #$03
    tax
    lda wave_chars_left,x
    sta SCREEN_RAM + 22*40 + 9
    sta SCREEN_RAM + 22*40 + 10
    lda wave_chars_right,x
    sta SCREEN_RAM + 22*40 + 29
    sta SCREEN_RAM + 22*40 + 30

    // Update Current Section Banner & Lyrics (Row 20)
    jsr update_section_display

    rts

// Draw horizontal VU bar using Zero Page Pointer ($FB/$FC)
// Accumulator = Row (0..24), X register = VU level (0..16)
draw_horizontal_bar:
    tay
    lda row_screen_lo,y
    clc
    adc #18
    sta ZP_PTR_LO
    lda row_screen_hi,y
    adc #$00
    sta ZP_PTR_HI

    // Draw active filled blocks ($a0) up to X, dim dashes ($2d) for rest
    ldy #$00
bar_fill_loop:
    cpx #$00
    beq bar_clear
    lda #$a0            // Solid block
    sta (ZP_PTR_LO),y
    dex
    iny
    cpy #16
    bcc bar_fill_loop
    rts

bar_clear:
    lda #$2d            // Dim dash '-'
    sta (ZP_PTR_LO),y
    iny
    cpy #16
    bcc bar_clear
    rts

cassette_spokes:
    .byte $2d, $6d, $7c, $2f   // '-', '\', '|', '/' rotating spokes

wave_chars_left:
    .byte $20, $20, $28, $28
wave_chars_right:
    .byte $20, $29, $29, $20

// ==============================================================================
// Section Banner & Lyrics Display (Row 20)
// ==============================================================================
update_section_display:
    // Bar Index = (step_hi * 16) + (step_lo >> 4)
    lda step_lo
    lsr
    lsr
    lsr
    lsr                 // High nibble of step_lo (0..15)
    sta temp_bar

    lda step_hi
    beq bar_hi_done
    cmp #$01
    bne bar_hi_2
    lda temp_bar
    clc
    adc #16
    sta temp_bar
    jmp bar_hi_done
bar_hi_2:
    lda temp_bar
    clc
    adc #32
    sta temp_bar
bar_hi_done:

    ldx temp_bar
    cpx #20
    bcc bar_idx_valid
    ldx #$00
bar_idx_valid:
    lda section_table,x
    cmp current_section_id
    beq sec_disp_done
    sta current_section_id

    // Setup zero page pointer to lyric string
    tax
    lda sec_str_ptrs_lo,x
    sta ZP_PTR_LO
    lda sec_str_ptrs_hi,x
    sta ZP_PTR_HI

    ldy #$00
print_sec_loop:
    lda (ZP_PTR_LO),y
    beq sec_pad_loop
    sta SCREEN_RAM + 20*40 + 2,y
    lda #$01            // Bright White text
    sta COLOR_RAM + 20*40 + 2,y
    iny
    cpy #36
    bcc print_sec_loop
    rts

sec_pad_loop:
    // Pad remaining row with spaces
    cpy #36
    bcs sec_disp_done
    lda #$20
    sta SCREEN_RAM + 20*40 + 2,y
    iny
    jmp sec_pad_loop

sec_disp_done:
    rts

// ==============================================================================
// Draw Static Title Screen Layout
// ==============================================================================
.encoding "screencode_upper"
draw_title_screen:
    // Header borders and text
    ldx #$00
draw_hdr_loop:
    lda hdr_line1,x
    beq hdr1_done
    sta SCREEN_RAM + 0*40,x
    lda #$07            // Yellow
    sta COLOR_RAM + 0*40,x
    inx
    bne draw_hdr_loop
hdr1_done:

    ldx #$00
draw_title_loop:
    lda title_text,x
    beq title_done
    sta SCREEN_RAM + 1*40,x
    lda #$01            // Bright White
    sta COLOR_RAM + 1*40,x
    inx
    bne draw_title_loop
title_done:

    ldx #$00
draw_sub_loop:
    lda sub_text,x
    beq sub_done
    sta SCREEN_RAM + 2*40,x
    lda #$0e            // Light Blue
    sta COLOR_RAM + 2*40,x
    inx
    bne draw_sub_loop
sub_done:

    ldx #$00
draw_sid_loop:
    lda sid_text,x
    beq sid_done
    sta SCREEN_RAM + 3*40,x
    lda #$03            // Cyan
    sta COLOR_RAM + 3*40,x
    inx
    bne draw_sid_loop
sid_done:

    ldx #$00
draw_sep_loop:
    lda sep_line,x
    beq sep_done
    sta SCREEN_RAM + 4*40,x
    lda #$0f            // Light Grey
    sta COLOR_RAM + 4*40,x
    inx
    bne draw_sep_loop
sep_done:

    // Channel Telemetry Labels
    jsr print_labels
    rts

print_labels:
    // Row 6: VOICE 1 [LEAD MELODY]
    ldx #0
l1_loop:
    lda lbl_v1,x
    beq l1_done
    sta SCREEN_RAM + 6*40 + 1,x
    lda #$01            // White
    sta COLOR_RAM + 6*40 + 1,x
    inx
    bne l1_loop
l1_done:

    // Set Color RAM for Row 7 VU Meter: Green
    ldx #0
v1_col_loop:
    lda #$05            // Green
    sta COLOR_RAM + 7*40 + 18,x
    inx
    cpx #16
    bcc v1_col_loop

    // Row 9: VOICE 2 [CHORDS & PWM]
    ldx #0
l2_loop:
    lda lbl_v2,x
    beq l2_done
    sta SCREEN_RAM + 9*40 + 1,x
    lda #$0e            // Light Blue
    sta COLOR_RAM + 9*40 + 1,x
    inx
    bne l2_loop
l2_done:

    // Set Color RAM for Row 10 VU Meter: Yellow
    ldx #0
v2_col_loop:
    lda #$07            // Yellow
    sta COLOR_RAM + 10*40 + 18,x
    inx
    cpx #16
    bcc v2_col_loop

    // Row 12: VOICE 3 [BASS & DRUMS]
    ldx #0
l3_loop:
    lda lbl_v3,x
    beq l3_done
    sta SCREEN_RAM + 12*40 + 1,x
    lda #$07            // Yellow
    sta COLOR_RAM + 12*40 + 1,x
    inx
    bne l3_loop
l3_done:

    // Set Color RAM for Row 13 VU Meter: Red
    ldx #0
v3_col_loop:
    lda #$02            // Red
    sta COLOR_RAM + 13*40 + 18,x
    inx
    cpx #16
    bcc v3_col_loop

    // Row 15: ANALOG RESONANT FILTER
    ldx #0
l4_loop:
    lda lbl_flt,x
    beq l4_done
    sta SCREEN_RAM + 15*40 + 1,x
    lda #$03            // Cyan
    sta COLOR_RAM + 15*40 + 1,x
    inx
    bne l4_loop
l4_done:

    // Set Color RAM for Row 16 VU Meter: Cyan
    ldx #0
flt_col_loop:
    lda #$03            // Cyan
    sta COLOR_RAM + 16*40 + 18,x
    inx
    cpx #16
    bcc flt_col_loop

    // Row 18: Cassette tape frame
    ldx #0
tape_loop:
    lda tape_frame,x
    beq tape_done
    sta SCREEN_RAM + 18*40 + 2,x
    lda #$0e
    sta COLOR_RAM + 18*40 + 2,x
    inx
    bne tape_loop
tape_done:

    // Row 22: Radio broadcast tower
    ldx #0
tower_loop:
    lda tower_text,x
    beq tower_done
    sta SCREEN_RAM + 22*40 + 0,x
    lda #$07
    sta COLOR_RAM + 22*40 + 0,x
    inx
    bne tower_loop
tower_done:

    // Row 24: Footer
    ldx #0
foot_loop:
    lda footer_text,x
    beq foot_done
    sta SCREEN_RAM + 24*40,x
    lda #$0d            // Light Green
    sta COLOR_RAM + 24*40,x
    inx
    bne foot_loop
foot_done:
    rts

// Static Screen Text Strings
hdr_line1:
    .text "========================================"
    .byte 0
title_text:
    .text "      VIDEO KILLED THE RADIO STAR       "
    .byte 0
sub_text:
    .text "          THE BUGGLES  (1979)           "
    .byte 0
sid_text:
    .text "    D-FLAT MAJOR / 131 BPM / SID        "
    .byte 0
sep_line:
    .text "----------------------------------------"
    .byte 0

lbl_v1:
    .text "CH1 LEAD : SAW + VIBRATO"
    .byte 0
lbl_v2:
    .text "CH2 CHORD: ARPEGGIO + PWM"
    .byte 0
lbl_v3:
    .text "CH3: SCORED BASS + DRUMS"
    .byte 0
lbl_flt:
    .text "ANALOG FLT: 12DB LOW-PASS"
    .byte 0

tape_frame:
    .text "  [ ( * ) == CASSETTE TAPE == ( * ) ]  "
    .byte 0

tower_text:
    .text "  (( . ))       RADIO STAR       (( . ))  "
    .byte 0

footer_text:
    .text "            DEMO BY ASTENG88            "
    .byte 0

// Section Lyric Strings
sec_str_0:
    .text "SCORE ARRANGEMENT / D-FLAT MAJOR"
    .byte 0
sec_str_1:
    .text "PIANO SCORE ADAPTED FOR THREE VOICES"
    .byte 0
sec_str_2:
    .text "VERSE / SCORE BARS 10-15"
    .byte 0
sec_str_3:
    .text "VOCAL RESPONSE / SCORE BARS 16-17"
    .byte 0
sec_str_4:
    .text "D-FLAT MAJOR / 131 BPM"
    .byte 0
sec_str_5:
    .text "BUILD / SCORE BARS 24-27"
    .byte 0
sec_str_6:
    .text "CHORUS / SCORE BARS 28-33"
    .byte 0
sec_str_7:
    .text "TURNAROUND / SCORE BARS 34-35"
    .byte 0

sec_str_ptrs_lo:
    .byte <sec_str_0, <sec_str_1, <sec_str_2, <sec_str_3
    .byte <sec_str_4, <sec_str_5, <sec_str_6, <sec_str_7

sec_str_ptrs_hi:
    .byte >sec_str_0, >sec_str_1, >sec_str_2, >sec_str_3
    .byte >sec_str_4, >sec_str_5, >sec_str_6, >sec_str_7

// Sections in this compact arrangement: score 10-17, 24-27, 28-35.
section_table:
    .byte 2,2,2,2,2,2,3,3,5,5,5,5,6,6,6,6,6,6,7,7

// ==============================================================================
// State Variables & Telemetry
// ==============================================================================
tempo_lo:           .byte 0
tempo_hi:           .byte 0
step_lo:            .byte $00
step_hi:            .byte $00
temp_bar:           .byte $00
temp_next_lo:       .byte $00
temp_next_hi:       .byte $00

cur_v1_note:        .byte $00
cur_v2_chord:       .byte $00
cur_v3_event:       .byte $00
cur_bass_note:      .byte 0

v1_note_idx:        .byte $00
v1_base_freq_lo:    .byte $00
v1_base_freq_hi:    .byte $00
v1_vib_counter:     .byte $00
v1_vib_phase:       .byte $00
v1_vib_active:      .byte $00

v2_active_chord:    .byte $00
v2_arp_phase:       .byte $00
pwm_lfo_idx:        .byte $00

v3_active_bass:     .byte $00
v3_drum_timer:      .byte $00
v3_drum_type:       .byte $00

border_flash:       .byte $00
filter_lfo:         .byte $00
filter_cutoff:      .byte $50

v1_vu_val:          .byte $00
v2_vu_val:          .byte $00
v3_vu_val:          .byte $00

anim_frame:         .byte $00
current_section_id: .byte $ff

// Screen row address lookup tables
row_screen_lo:
    // row_screen_lo:
    .byte $00, $28, $50, $78, $a0, $c8, $f0, $18, $40, $68, $90, $b8, $e0, $08, $30, $58
    .byte $80, $a8, $d0, $f8, $20, $48, $70, $98, $c0
row_screen_hi:
    // row_screen_hi:
    .byte $04, $04, $04, $04, $04, $04, $04, $05, $05, $05, $05, $05, $05, $06, $06, $06
    .byte $06, $06, $06, $06, $07, $07, $07, $07, $07

// ==============================================================================
// Tables: Frequencies, PWM LFO, Filter LFO
// ==============================================================================
// Index 0=C0, 57=A4=440 Hz. Generate BOTH bytes from the same word.
// Upper unused octaves saturate at the 16-bit oscillator limit.
.function sidPitch(n) {
    .return min(65535, round(440 * pow(2, (n-57)/12.0) * 16777216 / SID_CLOCK))
}
sid_freq_lo:
    .fill 96, <sidPitch(i)
sid_freq_hi:
    .fill 96, >sidPitch(i)

// 64-step PWM Modulation Sine Table ($0300 to $0D00)
pwm_table_lo:
    // pwm_table_lo:
    .byte $80, $8c, $97, $a3, $ae, $b9, $c3, $cc, $d5, $dd, $e4, $ea, $ef, $f3, $f6, $f7
    .byte $f8, $f7, $f6, $f3, $ef, $ea, $e4, $dd, $d5, $cc, $c3, $b9, $ae, $a3, $97, $8c
    .byte $80, $74, $69, $5d, $52, $47, $3d, $34, $2b, $23, $1c, $16, $11, $0d, $0a, $09
    .byte $08, $09, $0a, $0d, $11, $16, $1c, $23, $2b, $34, $3d, $47, $52, $5d, $69, $74
pwm_table_hi:
    // pwm_table_hi:
    .byte $08, $08, $09, $09, $0a, $0a, $0b, $0b, $0c, $0c, $0c, $0c, $0d, $0d, $0d, $0d
    .byte $0d, $0d, $0d, $0d, $0d, $0c, $0c, $0c, $0c, $0b, $0b, $0a, $0a, $09, $09, $08
    .byte $08, $08, $07, $07, $06, $06, $05, $05, $04, $04, $04, $04, $03, $03, $03, $03
    .byte $03, $03, $03, $03, $03, $04, $04, $04, $04, $05, $05, $06, $06, $07, $07, $08

// 128-step Resonant Filter Sweep Table ($30 to $90)
filter_table:
    // filter_table:
    .byte $50, $52, $54, $56, $58, $5a, $5c, $5d, $5f, $61, $63, $65, $66, $68, $69, $6b
    .byte $6c, $6e, $6f, $70, $71, $72, $73, $74, $75, $76, $76, $77, $77, $78, $78, $78
    .byte $78, $78, $78, $78, $77, $77, $76, $76, $75, $74, $73, $72, $71, $70, $6f, $6e
    .byte $6c, $6b, $69, $68, $66, $65, $63, $61, $5f, $5d, $5c, $5a, $58, $56, $54, $52
    .byte $50, $4e, $4c, $4a, $48, $46, $44, $43, $41, $3f, $3d, $3b, $3a, $38, $37, $35
    .byte $34, $32, $31, $30, $2f, $2e, $2d, $2c, $2b, $2a, $2a, $29, $29, $28, $28, $28
    .byte $28, $28, $28, $28, $29, $29, $2a, $2a, $2b, $2c, $2d, $2e, $2f, $30, $31, $32
    .byte $34, $35, $37, $38, $3a, $3b, $3d, $3f, $41, $43, $44, $46, $48, $4a, $4c, $4e

// ==============================================================================
// Score-derived compact arrangement: measures 10-17 and 24-35.
// Lead follows the piano melody, one octave lower; bar 17 is a lead rest.
// Bars 28-31 follow the descending line within the piano chord voicings.
// 0 = HOLD (not rest), $ff = gate off. Tied notes do not retrigger.
// Harmony is reduced to SID triads. Bass follows the piano reduction.
// Percussion is a new arrangement, not transcribed from the piano score.
// See radio-star-score-notes.csv for the source measure of every lead event.
// ==============================================================================
v1_seq:
    .byte $ff, $00, $31, $00, $31, $00, $33, $00, $33, $00, $31, $00, $31, $00, $33, $00 // Score 10
    .byte $33, $00, $31, $00, $31, $00, $33, $00, $33, $00, $00, $00, $ff, $00, $00, $00 // Score 11
    .byte $ff, $00, $31, $00, $31, $00, $33, $00, $33, $00, $31, $00, $31, $00, $33, $00 // Score 12
    .byte $33, $00, $31, $00, $31, $33, $00, $00, $33, $00, $00, $00, $00, $00, $00, $00 // Score 13
    .byte $ff, $00, $31, $00, $31, $00, $30, $00, $30, $00, $2e, $00, $2e, $2e, $00, $2e // Score 14
    .byte $00, $00, $2c, $00, $2c, $00, $2e, $00, $2c, $00, $00, $00, $00, $00, $00, $00 // Score 15
    .byte $38, $00, $00, $00, $3d, $00, $3a, $00, $00, $00, $00, $00, $00, $00, $00, $00 // Score 16
    .byte $ff, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00, $00 // Score 17
    .byte $38, $00, $00, $00, $3d, $00, $3a, $00, $00, $00, $31, $00, $2e, $00, $2a, $00 // Score 24
    .byte $2c, $00, $31, $00, $33, $00, $31, $00, $35, $00, $00, $00, $33, $00, $31, $00 // Score 25
    .byte $38, $00, $00, $00, $3d, $00, $3a, $00, $00, $00, $31, $00, $2e, $00, $2a, $00 // Score 26
    .byte $2c, $00, $31, $00, $33, $00, $31, $00, $35, $00, $00, $00, $33, $00, $31, $00 // Score 27
    .byte $35, $00, $36, $00, $35, $00, $33, $00, $31, $00, $30, $00, $2e, $00, $2c, $00 // Score 28
    .byte $00, $00, $2e, $00, $2a, $00, $00, $00, $2a, $00, $2c, $00, $2e, $30, $31, $33 // Score 29
    .byte $35, $00, $36, $00, $35, $00, $33, $00, $31, $00, $30, $00, $2e, $00, $2c, $00 // Score 30
    .byte $00, $00, $2e, $00, $2a, $00, $00, $00, $2a, $00, $2c, $00, $2e, $30, $31, $33 // Score 31
    .byte $35, $00, $35, $00, $00, $00, $33, $00, $00, $00, $00, $00, $33, $00, $35, $00 // Score 32
    .byte $00, $00, $31, $00, $00, $00, $31, $00, $00, $00, $00, $00, $00, $00, $00, $00 // Score 33
    .byte $31, $00, $00, $00, $00, $00, $2e, $00, $31, $00, $35, $00, $00, $00, $31, $00 // Score 34
    .byte $00, $00, $2e, $00, $00, $00, $25, $00, $29, $00, $29, $00, $00, $00, $00, $00 // Score 35

v2_seq:
    .byte $01, $00, $01, $00, $01, $00, $02, $00, $02, $00, $02, $00, $02, $00, $03, $00 // Score 10
    .byte $03, $00, $03, $00, $03, $00, $03, $00, $04, $00, $04, $00, $04, $00, $04, $00 // Score 11
    .byte $01, $00, $01, $00, $01, $00, $02, $00, $02, $00, $02, $00, $02, $00, $03, $00 // Score 12
    .byte $03, $00, $03, $00, $03, $00, $03, $00, $04, $00, $04, $00, $04, $00, $04, $00 // Score 13
    .byte $01, $00, $01, $00, $01, $00, $02, $00, $02, $00, $02, $00, $02, $00, $03, $00 // Score 14
    .byte $03, $00, $03, $00, $03, $00, $03, $00, $04, $00, $04, $00, $04, $00, $04, $00 // Score 15
    .byte $01, $00, $01, $00, $01, $00, $02, $00, $02, $00, $02, $00, $02, $00, $03, $00 // Score 16
    .byte $03, $00, $03, $00, $03, $00, $03, $00, $04, $00, $04, $00, $04, $00, $04, $00 // Score 17
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $05, $00, $05, $00, $05, $00, $05, $00 // Score 24
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $06, $00, $06, $00, $05, $00, $05, $00 // Score 25
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $05, $00, $05, $00, $05, $00, $05, $00 // Score 26
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $06, $00, $06, $00, $04, $00, $04, $00 // Score 27
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00 // Score 28
    .byte $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00 // Score 29
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00, $01, $00 // Score 30
    .byte $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00, $05, $00 // Score 31
    .byte $01, $00, $01, $00, $01, $00, $01, $00, $04, $00, $04, $00, $04, $00, $04, $00 // Score 32
    .byte $07, $00, $07, $00, $07, $00, $07, $00, $06, $00, $06, $00, $06, $00, $06, $00 // Score 33
    .byte $03, $00, $03, $00, $03, $00, $03, $00, $03, $00, $03, $00, $03, $00, $03, $00 // Score 34
    .byte $07, $00, $07, $00, $07, $00, $07, $00, $07, $00, $07, $00, $07, $00, $07, $00 // Score 35

v3_seq:
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 10
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 11
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 12
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 13
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 14
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 15
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $00, $03, $00 // Score 16
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $00, $00, $03, $00, $02, $03, $02, $03 // Score 17
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $01, $00, $03, $00, $02, $00, $03, $00 // Score 24
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $01, $00, $03, $00, $02, $00, $03, $00 // Score 25
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $01, $00, $03, $00, $02, $00, $03, $00 // Score 26
    .byte $01, $00, $03, $00, $02, $00, $03, $00, $01, $00, $03, $00, $02, $03, $02, $03 // Score 27
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 28
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 29
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 30
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 31
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 32
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 33
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 34
    .byte $01, $00, $03, $00, $02, $00, $03, $03, $01, $00, $03, $00, $02, $00, $03, $03 // Score 35

bass_seq:
    .byte $1d, $00, $1d, $00, $1d, $00, $1e, $00, $1e, $00, $1e, $00, $1e, $00, $20, $00 // Score 10
    .byte $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $1e, $00 // Score 11
    .byte $1d, $00, $1d, $00, $1d, $00, $1e, $00, $1e, $00, $1e, $00, $1e, $00, $20, $00 // Score 12
    .byte $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $1e, $00 // Score 13
    .byte $1d, $00, $1d, $00, $1d, $00, $1e, $00, $1e, $00, $1e, $00, $1e, $00, $20, $00 // Score 14
    .byte $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $1e, $00 // Score 15
    .byte $1d, $00, $1d, $00, $1d, $00, $1e, $00, $1e, $00, $1e, $00, $1e, $00, $20, $00 // Score 16
    .byte $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $20, $00, $1e, $00 // Score 17
    .byte $1d, $00, $25, $00, $29, $00, $1d, $00, $1e, $00, $25, $00, $2a, $00, $1e, $00 // Score 24
    .byte $20, $00, $25, $00, $2c, $00, $25, $00, $20, $00, $2c, $00, $1e, $00, $2a, $00 // Score 25
    .byte $1d, $00, $25, $00, $29, $00, $1d, $00, $1e, $00, $25, $00, $2a, $00, $1e, $00 // Score 26
    .byte $20, $00, $25, $00, $2c, $00, $25, $00, $20, $00, $27, $00, $20, $00, $27, $00 // Score 27
    .byte $19, $00, $19, $00, $25, $00, $19, $00, $19, $00, $19, $00, $25, $00, $19, $00 // Score 28
    .byte $1e, $00, $1e, $00, $2a, $00, $1e, $00, $1e, $00, $1e, $00, $2a, $00, $1e, $00 // Score 29
    .byte $19, $00, $19, $00, $25, $00, $19, $00, $19, $00, $19, $00, $25, $00, $19, $00 // Score 30
    .byte $1e, $00, $1e, $00, $2a, $00, $1e, $00, $1e, $00, $1e, $00, $2a, $00, $1e, $00 // Score 31
    .byte $19, $00, $20, $00, $25, $00, $20, $00, $18, $00, $20, $00, $24, $00, $20, $00 // Score 32
    .byte $16, $00, $1d, $00, $25, $00, $1d, $00, $24, $00, $1d, $00, $22, $00, $1d, $00 // Score 33
    .byte $20, $00, $20, $00, $2c, $00, $20, $00, $20, $00, $20, $00, $2c, $00, $20, $00 // Score 34
    .byte $22, $00, $22, $00, $2e, $00, $22, $00, $22, $00, $22, $00, $2e, $00, $22, $00 // Score 35

seq_end:
.assert "lead steps", v2_seq-v1_seq, TOTAL_STEPS
.assert "chord steps", v3_seq-v2_seq, TOTAL_STEPS
.assert "drum steps", bass_seq-v3_seq, TOTAL_STEPS
.assert "bass steps", seq_end-bass_seq, TOTAL_STEPS
