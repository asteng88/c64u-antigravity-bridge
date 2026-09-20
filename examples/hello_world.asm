// ==============================================================================
// Hello World for Commodore 64 Ultimate (C64U)
// Target Assembler: KickAssembler
// ==============================================================================

BasicUpstart2(main)

* = $0810 "Main Program"

main:
    // Set background ($D021) and border ($D020) colors to black
    lda #$00
    sta $d020
    sta $d021

    // Clear the screen memory ($0400-$07E7) with space ($20)
    ldx #$00
clear_loop:
    lda #$20
    sta $0400,x
    sta $0500,x
    sta $0600,x
    sta $06e8,x
    lda #$01       // White text in color RAM ($D800)
    sta $d800,x
    sta $d900,x
    sta $da00,x
    sta $dae8,x
    inx
    bne clear_loop

    // Print message to screen RAM starting at row 10 ($0590)
    ldx #$00
print_loop:
    lda message,x
    beq loop
    sta $0590,x
    inx
    jmp print_loop

loop:
    // Cycle border color continuously to show active execution
    inc $d020
    
    // Simple delay loop
    ldx #$00
    ldy #$00
delay:
    inx
    bne delay
    iny
    bne delay

    jmp loop

message:
    // Screen codes for "HELLO C64U FROM ANTIGRAVITY!"
    .text "HELLO C64U FROM ANTIGRAVITY!"
    .byte $00
