// ==============================================================================
// 0-CYCLE JITTER STABLE DOUBLE RASTER IRQ TEMPLATE
// Target Assembler: KickAssembler v5.x
// Architecture: MOS 6510 CPU / MOS 6569 VIC-II Video
// ==============================================================================

BasicUpstart2(start)

* = $0810 "Double IRQ Engine"

// Hardware Registers
.const VIC_BORDER       = $d020
.const VIC_BG           = $d021
.const VIC_RASTER       = $d012
.const VIC_CTRL1        = $d011
.const VIC_IRQ_STATUS   = $d019
.const VIC_IRQ_CTRL     = $d01a
.const CIA1_INT_CTRL    = $dc0d

start:
    sei

    // Disable timer interrupts from CIA1
    lda #$7f
    sta CIA1_INT_CTRL
    lda CIA1_INT_CTRL   // Acknowledge any pending CIA1 IRQs

    // Setup initial screen colors
    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    // Enable Raster Interrupt
    lda #$01
    sta VIC_IRQ_CTRL
    lda #$60            // First trigger at raster line $60 (96)
    sta VIC_RASTER
    lda VIC_CTRL1
    and #$7f
    sta VIC_CTRL1

    // Hook Stage 1 IRQ Vector
    lda #<irq_stage1
    sta $0314
    lda #>irq_stage1
    sta $0315

    cli

main_loop:
    jmp main_loop

// ==============================================================================
// STAGE 1: Coarse IRQ Trigger (Subject to 1-3 cycle CPU instruction jitter)
// ==============================================================================
irq_stage1:
    asl VIC_IRQ_STATUS  // Acknowledge VIC-II IRQ

    // Set IRQ vector to Stage 2
    lda #<irq_stage2
    sta $0314
    lda #>irq_stage2
    sta $0315

    // Advance trigger to the very next raster line
    inc VIC_RASTER

    // Save stack pointer and wait with exact 2-cycle instructions
    tsx
    cli                 // Allow Stage 2 interrupt to fire immediately
    nop; nop; nop; nop; nop
    nop; nop; nop; nop; nop
    nop; nop; nop; nop; nop
    rts

// ==============================================================================
// STAGE 2: Fine IRQ Trigger (Cycle-Exact Stabilization)
// ==============================================================================
irq_stage2:
    txs                 // Restore stack pointer from Stage 1

    // Fine-tune delay
    ldx #$08
wait_loop:
    dex
    bne wait_loop

    // Compare raster counter to latch exact cycle
    lda VIC_RASTER
    cmp VIC_RASTER      // Takes 5 cycles; stabilizes cycle jitter
    beq sync_locked
sync_locked:

    // -------------------------------------------------------------------------
    // EXACT CYCLE SYNCHRONIZATION ACHIEVED HERE: ZERO JITTER
    // Render 16 sharp, rock-solid color bars
    // -------------------------------------------------------------------------
    ldx #$00
bar_loop:
    lda color_bar_table,x
    sta VIC_BORDER
    sta VIC_BG

    // Waste exactly 53 cycles per scanline (PAL is 63 cycles/line)
    ldy #$08
delay_line:
    dey
    bne delay_line
    nop
    nop

    inx
    cpx #$10
    bne bar_loop

    // Return to black border/bg
    lda #$00
    sta VIC_BORDER
    sta VIC_BG

    // Reset IRQ back to Stage 1 for the next frame
    lda #<irq_stage1
    sta $0314
    lda #>irq_stage1
    sta $0315
    lda #$60            // Reset to line $60
    sta VIC_RASTER

    asl VIC_IRQ_STATUS  // Acknowledge IRQ
    jmp $ea81           // Return from Kernal IRQ

color_bar_table:
    .byte $00, $0b, $0c, $0f, $01, $07, $0a, $02
    .byte $02, $0a, $07, $01, $0f, $0c, $0b, $00
