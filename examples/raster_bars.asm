// ==============================================================================
// VIC-II Raster Interrupt Example for C64U
// Target Assembler: KickAssembler
// ==============================================================================

BasicUpstart2(start)

* = $0810 "Raster IRQ Setup"

start:
    sei             // Disable IRQ interrupts

    // Mask standard CIA1 timer interrupts
    lda #$7f
    sta $dc0d
    lda $dc0d       // Clear pending CIA interrupts

    // Configure VIC-II raster interrupt
    lda #$01
    sta $d01a       // Enable raster interrupt in VIC-II
    lda #$32        // Trigger interrupt at raster line 50 ($32)
    sta $d012
    lda $d011
    and #$7f        // High bit of raster line = 0
    sta $d011

    // Hook custom IRQ vector
    lda #<irq_top
    sta $0314
    lda #>irq_top
    sta $0315

    cli             // Re-enable interrupts
wait:
    jmp wait

irq_top:
    // Acknowledge VIC-II interrupt
    asl $d019

    // Draw rainbow raster bars
    ldx #$00
bar_loop:
    lda colors,x
    sta $d020       // Change border color
    sta $d021       // Change background color
    
    // Busy wait for one scanline (approximately 63 cycles)
    ldy #$0a
wait_line:
    dey
    bne wait_line
    nop
    nop

    inx
    cpx #$18        // 24 lines of color bars
    bne bar_loop

    // Reset background to black
    lda #$00
    sta $d020
    sta $d021

    // Jump to standard Kernal IRQ handler
    jmp $ea81

colors:
    .byte $00, $0b, $0c, $0f, $01, $07, $0a, $02
    .byte $02, $0a, $07, $01, $0f, $0c, $0b, $00
    .byte $06, $0e, $03, $01, $03, $0e, $06, $00
