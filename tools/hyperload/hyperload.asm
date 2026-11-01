// HYPERLOAD: fast tape loader with border stripes. Assembled by hyperload_tool.py, which passes the
// load address, page count and entry point on the command line.
//
// The tape holds a normal KERNAL file whose header carries the loader. The header sits in
// the tape buffer ($033C-$03FB), and its data block ($02A7-$0303) holds the exit code and
// overwrites the BASIC idle vector, so when LOAD finishes BASIC jumps straight to it.
//
// Then a stream of single pulses, one per bit, least significant bit first:
//   pilot of 0 bits, a 1 bit, SYNC, then for each page: 256 bytes and their XOR
//
// The screen stays blanked and interrupts off. No bad lines, sprites or IRQs can delay
// the polling, so it can read the CIA directly.

.const START = cmdLineVars.get("start").asNumber()
.const PAGES = cmdLineVars.get("pages").asNumber()
.const ENTRY = cmdLineVars.get("entry").asNumber()
.const THRESHOLD = cmdLineVars.get("threshold").asNumber()
.const SYNC = cmdLineVars.get("sync").asNumber()
.const PILOT_MIN = 64           // zero bits in a row that count as a pilot

.const value = $02
.const ptr   = $fb
.const count = $fd
.const sum   = $fe
.const long  = $ff

* = $02a7 "Exit code"
// Put the machine back as a reset leaves it, then start the program
start_program:
        lda #$37                // bit 5 set: motor off
        sta $01
        jsr $ff84               // IOINIT
        jsr $ff8a               // RESTOR
        jsr $ff81               // CINT
        lda #$1b
        sta $d011
        lda #$83
        sta $0302
        lda #$a4
        sta $0303
        cli
        jmp ENTRY

// Checksum failed: stop the tape and hold a red screen
fail:   lda #$37
        sta $01
        lda #2
        sta $d020
        jmp *

.assert "the exit code ends below the vectors", * <= $0300, true
* = $0300 "BASIC vectors"
        .word $e38b             // the error vector, as it was
        .word boot              // the idle vector: LOAD ends up here

* = $0351 "Loader"
boot:
        sei
        lda #$7f
        sta $dc0d
        sta $dd0d
        lda $dc0d
        lda $dd0d
        lda #0
        sta $d015
        lda #$0b                // screen off: no bad lines, and the border fills it
        sta $d011
        lda #$07                // bit 5 clear: motor on
        sta $01
        lda #<THRESHOLD
        sta $dc04
        lda #>THRESHOLD
        sta $dc05

search: ldy #PILOT_MIN
!:      jsr read_bit
        bcs search
        dey
        bne !-
!:      jsr read_bit            // the pilot ends with the first 1
        bcc !-
        jsr read_byte
        cmp #SYNC
        bne search

        lda #<START
        sta ptr
        lda #>START
        sta ptr + 1
        lda #PAGES
        sta count
page:   ldy #0
        sty sum
!:      jsr read_byte
        sta (ptr),y
        eor sum
        sta sum
        iny
        bne !-
        jsr read_byte
        cmp sum
        beq !+
        jmp fail
!:      inc ptr + 1
        dec count
        bne page
        jmp start_program

read_byte:
        ldx #8
!:      jsr read_bit
        ror value
        dex
        bne !-
        lda value
        rts

// One pulse: carry set if the timer ran out before the next edge. Reading $DC0D clears
// its flags, so the timer's flag has to be kept if it arrives first.
read_bit:
        lda #0
        sta long
!:      lda $dc0d
        beq !-
        lsr                     // bit 0, timer A ran out, into carry
        rol long
        and #$08                // bit 4 moved to bit 3: tape edge
        beq !-
        lda #$19                // restart: one-shot, load from latch
        sta $dc0e
        inc $d020               // the stripes
        lda long
        cmp #1
        rts

.assert "the loader fits the tape header", * <= $03fc, true
