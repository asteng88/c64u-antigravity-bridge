// ==============================================================================
// SID Synthesizer Test for Commodore 64 (MOS 6581/8580)
// Target Assembler: KickAssembler
// ==============================================================================

BasicUpstart2(main)

* = $0810 "SID Sound Generator"

main:
    // Reset all SID registers ($D400-$D418)
    ldx #$18
    lda #$00
clear_sid:
    sta $d400,x
    dex
    bpl clear_sid

    // Set Master Volume to Maximum (15) and no filter routing
    lda #$0f
    sta $d418

    // Set Voice 1 Attack/Decay (Fast attack, short decay)
    lda #$09        // Attack = 0, Decay = 9
    sta $d405

    // Set Voice 1 Sustain/Release (High sustain, medium release)
    lda #$a4        // Sustain = 10, Release = 4
    sta $d406

    // Set Voice 1 Frequency (440Hz Concert A = ~$1C48 in SID pitch)
    lda #$48
    sta $d400       // Low byte
    lda #$1c
    sta $d401       // High byte

    // Start Gate with Sawtooth Waveform ($21 = Sawtooth + Gate bit)
    lda #$21
    sta $d404

    // Keep running
hold:
    jmp hold
