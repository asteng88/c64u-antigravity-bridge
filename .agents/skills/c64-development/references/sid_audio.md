# The Definitive MOS 6581 / 8580 SID Audio Programming Guide

The MOS 6581 (and 8580) Sound Interface Device (SID) is one of the most expressive synthesizer chips in computing history. It features 3 independent hardware voices, 4 analog/digital waveforms per voice, pulse width modulation, oscillator sync, ring modulation, dedicated ADSR envelope generators, and a 12dB/octave multi-mode resonant analog filter.

---

## 1. SID Register Map ($D400 - $D41C)

Each voice occupies 7 contiguous registers:
* **Voice 1**: `$D400 - $D406`
* **Voice 2**: `$D407 - $D40D`
* **Voice 3**: `$D40E - $D414`

### Voice Register Offsets (Add `$00` for Voice 1, `$07` for Voice 2, `$0E` for Voice 3)

| Offset | Register | Description | Bits / Range |
| :--- | :--- | :--- | :--- |
| `+$00` | `FREQ_LO` | Frequency register low byte | Bits 0-7 |
| `+$01` | `FREQ_HI` | Frequency register high byte | Bits 8-15 |
| `+$02` | `PW_LO` | Pulse width low byte | Bits 0-7 |
| `+$03` | `PW_HI` | Pulse width high nibble | Bits 8-11 (Bits 12-15 unused) |
| `+$04` | `CONTROL` | Voice control / waveform select | See Control Register breakdown below |
| `+$05` | `ATTACK_DECAY`| Attack (high nibble) and Decay (low nibble) | High: 0-15, Low: 0-15 |
| `+$06` | `SUSTAIN_RELEASE` | Sustain (high nibble) and Release (low nibble) | High: 0-15, Low: 0-15 |

### Global Filter & Volume Registers

| Address | Name | Description |
| :--- | :--- | :--- |
| `$D415` | `CUTOFF_LO` | Filter Cutoff Low 3 bits (bits 0-2) |
| `$D416` | `CUTOFF_HI` | Filter Cutoff High 8 bits (bits 3-10) -> 11-bit cutoff total ($0000-$07FF) |
| `$D417` | `RES_ROUTING`| Bits 4-7: Filter Resonance (0-15). Bits 0-3: Filter Voice Routing (Bit 0=V1, Bit 1=V2, Bit 2=V3, Bit 3=Ext Audio) |
| `$D418` | `MODE_VOLUME`| Bits 0-3: Master Volume (0-15). Bit 4: Low-Pass. Bit 5: Band-Pass. Bit 6: High-Pass. Bit 7: Voice 3 Off (Mute voice 3 from audio output; allows V3 to be used as modulation LFO or random noise generator) |
| `$D419` | `POT_X` | Paddle 1 X value (Read-only A/D converter) |
| `$D41A` | `POT_Y` | Paddle 1 Y value (Read-only A/D converter) |
| `$D41B` | `OSC3_RANDOM`| Voice 3 oscillator output (Read-only, 8-bit random noise or waveform sample) |
| `$D41C` | `ENV3` | Voice 3 envelope output (Read-only, 8-bit current amplitude 0-255) |

> [!CAUTION]
> **REGISTERS $D400 - $D418 ARE STRICTLY WRITE-ONLY!**
> Reading any voice register (`$D400 - $D414`) or filter register (`$D415 - $D418`) returns unconnected open-bus / floating line capacitance garbage. You **CANNOT** perform read-modify-write instructions (e.g., `dec $d40f`, `asl $d404`, or `lda $d401; sbc #$06; sta $d401`) on SID sound registers! All pitch sweeps, drum pitch drops, and volume envelopes must maintain their state in zero-page/RAM or step through ROM lookup tables. Only `$D419 - $D41C` are readable.

---

## 2. Voice Control Register (`$D404 / $D40B / $D412`)

| Bit | Hex | Function | Description |
| :--- | :--- | :--- | :--- |
| **0** | `$01` | **GATE** | `1` = Trigger Attack/Decay/Sustain envelope (Note On). `0` = Trigger Release envelope (Note Off). |
| **1** | `$02` | **SYNC** | Hard-syncs voice oscillator with another voice. Voice 1 syncs to Voice 3; Voice 2 syncs to Voice 1; Voice 3 syncs to Voice 2. Produces cutting, metallic lead sounds. |
| **2** | `$04` | **RING MOD** | Ring-modulates triangle wave with another voice's frequency. Voice 1 mods with Voice 3; Voice 2 with Voice 1; Voice 3 with Voice 2. Ideal for metallic bells, gongs, robotic sci-fi tones. |
| **3** | `$08` | **TEST** | `1` = Resets oscillator phase and holds it at zero. Always set to 0 during sound output. Set to 1 briefly to synchronize oscillator start. |
| **4** | `$10` | **TRIANGLE** | Triangle waveform. Very mellow, flute-like, pure bass, sub-bass. |
| **5** | `$20` | **SAWTOOTH** | Sawtooth waveform. Rich in even and odd harmonics. Great for brass, punchy bass, aggressive synth leads, strings. |
| **6** | `$40` | **PULSE** | Variable Pulse / Square waveform. Controlled by PW registers. Classic 8-bit sounds, hollow oboes, strings with PWM. |
| **7** | `$80` | **NOISE** | Pseudo-random noise. Percussion (snare, hi-hat), explosions, wind, water, gunfire. |

> [!IMPORTANT]
> **GATE BIT REQUIRES 0 -> 1 TRANSITION TO RETRIGGER ATTACK!**
> On the MOS 6581 and 8580 SID, writing Gate ON (`$01`) when Gate was already `1` does **NOT** reset the envelope! The internal ADSR generator stays in the Sustain or Decay phase. If consecutive notes of the same pitch are played without clearing Gate, the voice emits one continuous, unarticulated drone. To articulate repeated notes or ensure fresh Attack transients, Gate **must be cleared to 0** for at least 1 frame (~20 ms) before the new note triggers.

> **Note on Combined Waveforms**: Setting multiple waveform bits simultaneously (e.g. `$31` for Triangle + Sawtooth) creates unique hybrid timbres on physical SID chips. The 6581 produces gritty analog saturation; the 8580 produces cleaner combined outputs.

---

## 3. Note Frequency Calculation & Chromatic Lookup Table

The SID frequency formula is:
$$\text{FreqReg} = \frac{\text{Freq}_{\text{Hz}} \times 16777216}{\text{Clock}_{\text{Hz}}}$$

* **PAL Factor**: $16777216 / 985248 \approx 17.0284$
* **NTSC Factor**: $16777216 / 1022727 \approx 16.4045$

### Complete Chromatic Note Table (PAL - KickAssembler Data Table)

```kickassembler
// Recommended Pattern: Mathematical compile-time pitch calculation (PAL/NTSC switchable)
// Index 0 = C-0, 57 = A-4 (440 Hz)
.const NTSC = false
.const SID_CLOCK = NTSC ? 1022727 : 985248

.function sidPitch(n) {
    .return min(65535, round(440 * pow(2, (n-57)/12.0) * 16777216 / SID_CLOCK))
}

sid_freq_lo: .fill 96, <sidPitch(i)
sid_freq_hi: .fill 96, >sidPitch(i)

// Or Pre-computed Static Table:
sid_freq_lo:
    // Octave 0
    .byte $17,$18,$1a,$1b,$1d,$1f,$20,$22,$25,$27,$29,$2c
    // Octave 1
    .byte $2e,$31,$34,$37,$3a,$3d,$41,$45,$49,$4e,$52,$57
    // Octave 2
    .byte $5d,$62,$68,$6e,$75,$7c,$83,$8b,$93,$9c,$a5,$af
    // Octave 3
    .byte $ba,$c5,$d1,$dd,$eb,$f8,$07,$16,$26,$37,$4a,$5e
    // Octave 4
    .byte $74,$8a,$a2,$bb,$d5,$f1,$0e,$2d,$4c,$6e,$93,$bc
    // Octave 5
    .byte $e7,$14,$44,$76,$ab,$e3,$1d,$5a,$99,$dc,$27,$77
    // Octave 6
    .byte $cf,$28,$88,$ed,$56,$c6,$3b,$b3,$32,$b9,$4e,$ee
    // Octave 7
    .byte $9e,$50,$10,$da,$ad,$8d,$76,$66,$64,$72,$9c,$dc

sid_freq_hi:
    // Octave 0
    .byte $01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01,$01
    // Octave 1
    .byte $02,$02,$02,$02,$02,$02,$02,$02,$02,$02,$02,$02
    // Octave 2
    .byte $04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04,$04
    // Octave 3
    .byte $08,$08,$08,$08,$08,$08,$09,$09,$09,$09,$09,$09
    // Octave 4
    .byte $11,$11,$11,$11,$11,$11,$12,$12,$12,$12,$12,$12
    // Octave 5
    .byte $22,$23,$23,$23,$23,$23,$24,$24,$24,$24,$25,$25
    // Octave 6
    .byte $45,$46,$46,$46,$47,$47,$48,$48,$49,$49,$4a,$4a
    // Octave 7
    .byte $8b,$8c,$8d,$8d,$8e,$8f,$90,$91,$92,$93,$94,$95
```

---

## 4. ADSR Envelope Timings

The SID envelope generator consists of 4 distinct phases:
* **Attack**: Time to ramp from 0 to maximum volume ($F).
* **Decay**: Time to fall from peak volume to the Sustain level.
* **Sustain**: Volume level maintained as long as the Gate bit is 1 ($0 - $F).
* **Release**: Time to decay from Sustain level back to 0 once Gate bit becomes 0.

### ADSR Value Lookup (Approximate Durations)

| Nibble Value | Attack Time | Decay / Release Time |
| :---: | :--- | :--- |
| `$0` | 2 ms | 6 ms |
| `$1` | 8 ms | 24 ms |
| `$2` | 16 ms | 48 ms |
| `$3` | 24 ms | 72 ms |
| `$4` | 38 ms | 114 ms |
| `$5` | 56 ms | 168 ms |
| `$6` | 68 ms | 204 ms |
| `$7` | 80 ms | 240 ms |
| `$8` | 100 ms | 300 ms |
| `$9` | 250 ms | 750 ms |
| `$A` | 500 ms | 1.5 s |
| `$B` | 800 ms | 2.4 s |
| `$C` | 1.0 s | 3.0 s |
| `$D` | 3.0 s | 9.0 s |
| `$E` | 5.0 s | 15.0 s |
| `$F` | 8.0 s | 24.0 s |

---

## 5. Pulse Width Modulation (PWM)

The Pulse Width register is 12-bit (`$000` to `$FFF` / 0 to 4095).
* Duty cycle formula: `Duty = (PW / 4095) * 100%`.
* `$0800` (2048) represents a 50% square wave (equal high and low periods).
* `$0100` is a narrow 6.25% pulse (thin, nasal, buzzy).

### Dynamic PWM Sweep Technique (LFO):
Sweeping PW up and down every frame (50Hz) creates lush chorusing strings and fat analog basslines.
```kickassembler
update_pwm:
    lda pwm_direction
    bne pwm_down
pwm_up:
    lda sid_pw_val
    clc
    adc #$10
    sta sid_pw_val
    sta $d402           // Voice 1 PW Lo
    lda sid_pw_hi
    adc #$00
    sta sid_pw_hi
    sta $d403           // Voice 1 PW Hi
    cmp #$0d            // Max sweep ceiling
    bcc pwm_done
    lda #$01
    sta pwm_direction
    rts
pwm_down:
    lda sid_pw_val
    sec
    sbc #$10
    sta sid_pw_val
    sta $d402
    lda sid_pw_hi
    sbc #$00
    sta sid_pw_hi
    sta $d403
    cmp #$02            // Min sweep floor
    bcs pwm_done
    lda #$00
    sta pwm_direction
pwm_done:
    rts
```

---

## 6. The Multi-Mode Resonant Filter

The SID contains an analog state-variable filter.
* **Cutoff Frequency (11 bits)**:
  * Low 3 bits in `$D415` (bits 0-2).
  * High 8 bits in `$D416`.
  * Range: ~$30 Hz to ~$12 kHz.
* **Resonance (`$D417` bits 4-7)**: Values `$00` to `$F0`. Higher values emphasize frequencies near cutoff, producing classic acid/synth resonance whistles.
* **Voice Routing (`$D417` bits 0-3)**:
  * Bit 0: Voice 1 filtered
  * Bit 1: Voice 2 filtered
  * Bit 2: Voice 3 filtered
  * Bit 3: External audio in filtered
* **Filter Mode (`$D418` bits 4-7)**:
  * `$10`: Low-Pass (Allows bass through, cuts highs — warm, deep).
  * `$20`: Band-Pass (Only allows frequencies around cutoff — telephone, vocal, wah-wah).
  * `$40`: High-Pass (Allows highs through, cuts bass — crisp, sizzling, thin).
  * `$50`: Notch (Combines Low-Pass and High-Pass — phasey, hollow).

---

## 7. Sound Effects (SFX) State Machine

In games and interactive demos, SFX must play over music or on dedicated channels without blocking CPU execution.

### Laser / Zap Effect:
* Pitch starts high, sweeps downward rapidly every frame.
* Fast attack, fast decay. Sawtooth or pulse wave.
```kickassembler
sfx_laser_init:
    lda #$00
    sta $d405           // Attack 0, Decay 0
    lda #$00
    sta $d406           // Sustain 0, Release 0
    lda #$00
    sta laser_freq_lo
    lda #$30
    sta laser_freq_hi
    lda #$21            // Sawtooth + Gate
    sta $d404
    lda #$0f
    sta laser_active
    rts

sfx_laser_play:
    lda laser_active
    beq laser_done
    dec laser_active
    lda laser_freq_hi
    sec
    sbc #$03            // Rapid downward pitch drop
    sta laser_freq_hi
    sta $d401
    lda laser_freq_lo
    sta $d400
    lda laser_active
    bne laser_done
    lda #$20            // Gate off
    sta $d404
laser_done:
    rts
```

### Explosion Effect:
* White Noise waveform (`$81`).
* Low pitch (`$D401` = `$04 - $08`).
* Instant attack, medium decay (`$08` or `$09`).
* Sweeping filter cutoff downward as volume decays gives cinematic impact.

---

## 8. Complete 50Hz Music Driver Architecture

A standard C64 music engine is called on every PAL VBlank (50 Hz / Raster line 0):
1. **Song Table**: List of pattern indexes for Voice 1, Voice 2, and Voice 3.
2. **Pattern Sequencer**: Steps through note events (pitch, note delay/speed, instrument index).
3. **Instrument Tables**:
   * **Waveform table**: Steps through waveforms (e.g. noise burst for 2 frames then triangle).
   * **Arpeggio table**: Semitone pitch offsets relative to root note (e.g. 0, 4, 7 for major chord cycling at 50Hz).
   * **Pitch vibrato table**: Up/down pitch delta.
   * **Filter sweep table**: Dynamic cutoff updates.

---

## 9. Production Tracker Engine Architecture & Hardware Rules

### 9.1 Fractional-Frame BPM Timing (16-Bit Phase Accumulator)
Integer frame counting (`tick_timer == 5`) limits tempos to integer divisors of the frame rate (e.g., 50/5 = 150 BPM, 50/6 = 125 BPM) and drifts. Production engines use a 16-bit phase accumulator for arbitrary BPMs:
```kickassembler
.const NTSC = false
.const FRAME_RATE = NTSC ? 59.826 : 50.125
.const BPM = 132
// Four sixteenth-note steps per quarter note:
.const STEP_RATE = round(BPM * 4 * 65536 / (60 * FRAME_RATE))

irq_handler:
    // Accumulate step phase
    clc
    lda tempo_lo
    adc #<STEP_RATE
    sta tempo_lo
    lda tempo_hi
    adc #>STEP_RATE
    sta tempo_hi
    bcc no_music_step
    jsr step_sequencer          // Advance sequence when accumulator overflows
    jmp modulation

no_music_step:
    // Predictive lookahead: test if next frame will overflow
    clc
    lda tempo_lo
    adc #<STEP_RATE
    lda tempo_hi
    adc #>STEP_RATE
    bcc modulation
    jsr check_gate_cut          // Release 1 frame (~20 ms) before next note!
```

### 9.2 Predictive Lookahead Gate Cut
Because SID ADSR requires a `0 -> 1` Gate transition to re-attack, consecutive notes of the same or different pitch will slur if Gate remains 1. Testing whether the *next* frame will trigger an event allows lowering the Gate (`#$20`) for exactly 1 frame (20 ms):
```kickassembler
check_gate_cut:
    // Look ahead to next step in sequence
    lda next_step_note
    beq gate_cut_done           // If next note is sustain (0), keep gate high!
    lda #$20                    // Gate OFF (Waveform without Gate bit)
    sta SID_V1_CTRL
gate_cut_done:
    rts
```

### 9.3 Voice Multiplexing (Shared Drum & Bass Order of Operations)
When Voice 3 shares bass and percussion (kick/snare/hi-hat):
1. **Advance old drum timer before triggering new hits**: Execute `update_drums` *before* the sequencer step so 1-frame hits (e.g. hi-hats) survive until the next IRQ rather than vanishing instantly.
2. **Refresh harmonic root before downbeat kick**: Read the new bar's chord root at `step & 15 == 0` *before* triggering the kick. When the kick finishes, bass restores to the *new* bar's tonic instead of the previous bar's harmony.
3. **Write-only sweep table**: Never read `$D40F` to pitch-slide drums (`lda $d40f; sbc #$06; sta $d40f` is invalid). Use a ROM/RAM table (`kick_pitch_hi,x`).

### 9.4 16-Bit Safe Vibrato
Vibrato modulation added to frequency low byte must propagate carry/borrow to frequency high byte. Otherwise, when low byte underflows (e.g. `$00` + `$FF`), pitch jumps 256 units upward instead of dropping 1 unit:
```kickassembler
    lda v1_base_freq_lo
    clc
    adc vib_table_lo,x
    sta SID_V1_FREQ_LO
    lda v1_base_freq_hi
    adc vib_table_hi,x          // $00 for positive, $FF for negative delta
    sta SID_V1_FREQ_HI
```

### 9.5 CIA1 Keyboard Polling
When polling the Space bar or keys in demo main loops (`$DC01`), ensure CIA1 Data Direction Registers are initialized:
```kickassembler
    lda #$ff
    sta $dc02                   // CIA1 Port A: Outputs (column select)
    lda #$00
    sta $dc03                   // CIA1 Port B: Inputs (row read)
    lda #$7f
    sta $dc00                   // Select column 7 (Space bar row)
```

### 9.6 Compile-Time Table Length Assertions
Prevent silent sequence desynchronization between voice tracks using KickAssembler assertions:
```kickassembler
seq_end:
.assert "lead length",   v2_seq - v1_seq, TOTAL_STEPS
.assert "chord length",  v3_seq - v2_seq, TOTAL_STEPS
.assert "rhythm length", seq_end - v3_seq, TOTAL_STEPS
```
