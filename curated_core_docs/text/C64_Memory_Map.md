# Sta.c64 Memory Map
Source: https://sta.c64.org/cbm64mem.html




## Commodore 64 memory map



| Address(hex, dec)Description


$0000-$00FF, 0-255Zero page
$00000
  Processor port data direction register. Bits:

Bit #x: 0 = Bit #x in processor port can only be
    read; 1 = Bit #x in processor port can be read and written.

Default: $2F, %00101111.
$00011Processor port. Bits:

Bits #0-#2: Configuration for memory areas
    $A000-$BFFF, $D000-$DFFF and $E000-$FFFF. Values:

%x00: RAM visible in all three areas.
%x01: RAM visible at $A000-$BFFF and
      $E000-$FFFF.
%x10: RAM visible at $A000-$BFFF; KERNAL ROM
      visible at $E000-$FFFF.
%x11: BASIC ROM visible at $A000-$BFFF; KERNAL ROM
      visible at $E000-$FFFF.
%0xx: Character ROM visible at $D000-$DFFF. (Except
      for the value %000, see above.)
%1xx: I/O area visible at $D000-$DFFF. (Except for
      the value %100, see above.)

Bit #3: Datasette output signal level.
Bit #4: Datasette button status; 0 = One or more of
    PLAY, RECORD, F.FWD or REW pressed; 1 = No button is pressed.
Bit #5: Datasette motor control; 0 = On; 1 = Off.

Default: $37, %00110111.
$00022Unused.
$0003-$00043-4Unused.
  Default: $B1AA, execution address of routine converting floating point to
  integer.
$0005-$00065-6Unused.
  Default: $B391, execution address of routine converting integer to floating
  point.
$00077Byte being searched for during
  various operations.
  Current digit of number being input.
  Low byte of first integer operand during AND and OR.
  Low byte of integer-format FAC during INT().
$00088Byte being searched for during
  various operations.
  Current byte of BASIC line during tokenization.
  High byte of first integer operand during AND and OR.
$00099Current column number during SPC()
  and TAB().
$000A10LOAD/VERIFY switch. Values:

$00: LOAD.
$01-$FF: VERIFY.

$000B11Current token during
  tokenization.
  Length of BASIC line during insertion of line.
  AND/OR switch; $00 = AND; $FF = OR.
  Number of dimensions during array operations.
$000C12Switch for array operations.
  Values:

$00: Operation was not called by DIM.
$40-$7F: Operation was called by DIM.

$000D13Current expression type. Values:

$00: Numerical.
$FF: String.

$000E14Current numerical expression type.
  Bits:

Bit #7: 0 = Floating point; 1 = Integer.

$000F15Quotation mode switch during
  tokenization; Bit #6: 0 = Normal mode; 1 = Quotation mode.
  Quotation mode switch during LIST; $01 = Normal mode; $FE = Quotation
  mode.
  Garbage collection indicator during memory allocation for string variable;
  $00-$7F = There was no garbage collection yet; $80 = Garbage collection
  already took place.
$001016Switch during fetch of variable
  name. Values:

$00: Integer variables are accepted.
$01-$FF: Integer variables are not accepted.

$001117GET/INPUT/READ switch. Values:

$00: INPUT.
$40: GET.
$98: READ.

$001218Sign during SIN() and TAN().
  Values:

$00: Positive.
$FF: Negative.

$001319Current I/O device number.
  Default: $00, keyboard for input and screen for output.
$0014-$001520-21Line number during GOSUB,
  GOTO and RUN.
  Second line number during LIST.
  Memory address during PEEK, POKE, SYS and WAIT.
$001622Pointer to next expression in string
  stack. Values: $19; $1C; $1F; $22.
  Default: $19.
$0017-$001823-24Pointer to previous
  expression in string stack.
$0019-$002125-33String stack, temporary
  area for processing string expressions (9 bytes, 3 entries).
$0022-$002534-37Temporary area for various
  operations (4 bytes).
$0026-$002938-41Auxiliary arithmetical
  register for division and multiplication (4 bytes).
$002A42Unused.
$002B-$002C43-44Pointer to beginning of
  BASIC area.
  Default: $0801, 2049.
$002D-$002E45-46Pointer to beginning of
  variable area. (End of program plus 1.)
$002F-$003047-48Pointer to beginning of
  array variable area.
$0031-$003249-50Pointer to end of array
  variable area.
$0033-$003451-52Pointer to beginning of
  string variable area. (Grows downwards from end of BASIC area.)
$0035-$003653-54Pointer to memory allocated
  for current string variable.
$0037-$003855-56Pointer to end of BASIC
  area.
  Default: $A000, 40960.
$0039-$003A57-58Current BASIC line number.
  Values:

$0000-$F9FF, 0-63999: Line number.
$FF00-$FFFF: Direct mode, no BASIC program is being
    executed.

$003B-$003C59-60Current BASIC line number
  for CONT.
$003D-$003E61-62Pointer to next BASIC
  instruction for CONT. Values:

$0000-$00FF: CONT'ing is not possible.
$0100-$FFFF: Pointer to next BASIC instruction.

$003F-$004063-64BASIC line number of
  current DATA item for READ.
$0041-$004265-66Pointer to next DATA item
  for READ.
$0043-$004467-68Pointer to input result
  during GET, INPUT and READ.
$0045-$004669-70Name and type of current
  variable. Bits:

$0045 bits #0-#6: First character of variable
    name.
$0046 bits #0-#6: Second character of variable name;
    $00 = Variable name consists of only one character.
$0045 bit #7 and $0046 bit #7:

%00: Floating-point variable.
%01: String variable.
%10: FN function, created with DEF FN.
%11: Integer variable.


$0047-$004871-72Pointer to value of current
  variable or FN function.
$0049-$004A73-74Pointer to value of current
  variable during LET.
  Value of second and third parameter during WAIT.
  Logical number and device number during OPEN.
  $0049, 73: Logical number of CLOSE.
  Device number of LOAD, SAVE and VERIFY.
$004B-$004C75-76Temporary area for saving
  original pointer to current BASIC instruction during GET, INPUT and
  READ.
$004D77Comparison operator indicator.
  Bits:

Bit #1: 1 = ">" (greater than) is present in
    expression.
Bit #2: 1 = "=" (equal to) is present in
    expression.
Bit #3: 1 = "<" (less than) is present in
    expression.

$004E-$004F78-79Pointer to current FN
  function.
$0050-$005180-81Pointer to current string
  variable during memory allocation.
$005282Unused.
$005383Step size of garbage collection.
  Values: $03; $07.
$0054-$005684-86JMP ABS machine
  instruction, jump to current BASIC function.
  $0055-$0056, 85-86: Execution address of current BASIC function.
$0057-$005B87-91Arithmetic register #3 (5
  bytes).
$005C-$006092-96Arithmetic register #4 (5
  bytes).
$0061-$006597-101FAC, arithmetic register
  #1 (5 bytes).
$0066102Sign of FAC. Bits:

Bit #7: 0 = Positive; 1 = Negative.

$0067103Number of degrees during polynomial
  evaluation.
$0068104Temporary area for various
  operations.
$0069-$006D105-109ARG, arithmetic register
  #2 (5 bytes).
$006E110Sign of ARG. Bits:

Bit #7: 0 = Positive; 1 = Negative.

$006F-$0070111-112Pointer to first string
  expression during string comparison.
$0071-$0072113-114Auxiliary pointer during
  array operations.
  Temporary area for saving original pointer to current BASIC instruction
  during VAL().
  Pointer to current item of polynomial table during polynomial
  evaluation.
$0073-$008A115-138CHRGET. Machine code
  routine to read next byte from BASIC program or direct command (24
  bytes).
  $0079, 121: CHRGOT. Read current byte from BASIC program or direct
  command.
  $007A-$007B, 122-123: Pointer to current byte in BASIC program or direct
  command.
$008B-$008F139-143Previous result of
  RND().
$0090144Value of ST variable, device status
  for serial bus and datasette input/output. Serial bus bits:

Bit #0: Transfer direction during which the timeout
    occurred; 0 = Input; 1 = Output.
Bit #1: 1 = Timeout occurred.
Bit #4: 1 = VERIFY error occurred (only during
    VERIFY), the file read from the device did not match that in the
    memory.
Bit #6: 1 = End of file has been reached.
Bit #7: 1 = Device is not present.

Datasette bits:

Bit #2: 1 = Block is too short (shorter than 192
    bytes).
Bit #3: 1 = Block is too long (longer than 192
    bytes).
Bit #4: 1 = Not all bytes read with error during pass
    1 could be corrected during pass 2, or a VERIFY error occurred, the file
    read from the device did not match that in the memory.
Bit #5: 1 = Checksum error occurred.
Bit #6: 1 = End of file has been reached (only during
    reading data files).

$0091145Stop key indicator. Values:

$7F: Stop key is pressed.
$FF: Stop key is not pressed.

$0092146Unknown. (Timing constant during
  datasette input.)
$0093147LOAD/VERIFY switch. Values:

$00: LOAD.
$01-$FF: VERIFY.

$0094148Serial bus output cache status.
  Bits:

Bit #7: 1 = Output cache dirty, must transfer cache
    contents upon next output to serial bus.

$0095149Serial bus output cache, previous
  byte to be sent to serial bus.
$0096150Unknown. (End of tape indicator
  during datasette input/output.)
$0097151Temporary area for saving original
  value of Y register during input from RS232.
  Temporary area for saving original value of X register during input from
  datasette.
$0098152Number of files currently open.
  Values: $00-$0A, 0-10.
$0099153Current input device number.
  Default: $00, keyboard.
$009A154Current output device number.
  Default: $03, screen.
$009B155Unknown. (Parity bit during
  datasette input/output.)
$009C156Unknown. (Byte ready indicator
  during datasette input/output.)
$009D157System error display switch.
  Bits:

Bit #6: 0 = Suppress I/O error messages; 1 = Display
    them.
Bit #7: 0 = Suppress system messages; 1 =  Display
    them.

$009E158Byte to be put into output buffer
  during RS232 and datasette output.
  Block header type during datasette input/output.
  Length of file name during datasette input/output.
  Error counter during LOAD from datasette. Values: $00-$3E, 0-62.
$009F159Auxiliary counter for writing file
  name into datasette buffer.
  Auxiliary counter for comparing requested file name with file name read from
  datasette during datasette input.
  Error correction counter during LOAD from datasette. Values: $00-$3E,
  0-62.
$00A0-$00A2160-162Value of TI variable,
  time of day, increased by 1 every 1/60 second (on PAL machines). Values:
  $000000-$4F19FF, 0-518399 (on PAL machines).
$00A3163EOI switch during serial bus
  output. Bits:

Bit #7: 0 = Send byte right after handshake; 1 = Do
    EOI delay first.

Bit counter during datasette output.
$00A4164Byte buffer during serial bus
  input.
  Parity during datasette input/output.
$00A5165Bit counter during serial bus
  input/output.
  Counter for sync mark during datasette output.
$00A6166Offset of current byte in datasette
  buffer.
$00A7167Bit buffer during RS232 input.
$00A8168Bit counter during RS232 input.
$00A9169Stop bit switch during RS232 input.
  Values:

$00: Data bit.
$01-$FF: Stop bit.

$00AA170Byte buffer during RS232 input.
$00AB171Parity during RS232 input.
  Computed block checksum during datasette input.
$00AC-$00AD172-173Start address for SAVE to
  serial bus.
  Pointer to current byte during SAVE to serial bus or datasette.
  Pointer to line in screen memory to be scrolled during scrolling the
  screen.
$00AE-$00AF174-175Load address read from
  input file and pointer to current byte during LOAD/VERIFY from serial
  bus.
  End address after LOAD/VERIFY from serial bus or datasette.
  End address for SAVE to serial bus or datasette.
  Pointer to line in Color RAM to be scrolled during scrolling the screen.
$00B0-$00B1176-177Unknown.
$00B2-$00B3178-179Pointer to datasette
  buffer.
  Default: $033C, 828.
$00B4180Bit counter and stop bit switch
  during RS232 output. Bits:

Bits #0-#6: Bit count.
Bit #7: 0 = Data bit; 1 = Stop bit.

Bit counter during datasette input/output.
$00B5181Bit buffer (in bit #2) during RS232
  output.
$00B6182Byte buffer during RS232
  output.
$00B7183Length of file name or disk
  command; first parameter of LOAD, SAVE and VERIFY or fourth parameter of
  OPEN. Values:

$00: No parameter.
$01-$FF: Parameter length.

$00B8184Logical number of current file.
$00B9185Secondary address of current
  file.
$00BA186Device number of current file.
$00BB-$00BC187-188Pointer to current file
  name or disk command; first parameter of LOAD, SAVE and VERIFY or fourth
  parameter of OPEN.
$00BD189Parity during RS232 output.
  Byte buffer during datasette input/output.
$00BE190Block counter during datasette
  input/output.
$00BF191Unknown.
$00C0192Datasette motor switch. Values:

$00: No button was pressed, motor has been switched
    off. If a button is pressed on the datasette, must switch motor on.
$01-$FF: Motor is on.

$00C1-$00C2193-194Start address during SAVE
  to serial bus, LOAD and VERIFY from datasette and SAVE to datasette.
  Pointer to current byte during memory test.
$00C3-$00C4195-196Start address for a
  secondary address of 0 for LOAD and VERIFY from serial bus or datasette.
  Pointer to ROM table of default vectors during initialization of I/O
  vectors.
$00C5197Matrix code of key previously
  pressed. Values:

$00-$3F: Keyboard matrix code.
$40: No key was pressed at the time of previous
    check.

$00C6198Length of keyboard buffer.
  Values:

$00, 0: Buffer is empty.
$01-$0A, 1-10: Buffer length.

$00C7199Reverse mode switch. Values:

$00: Normal mode.
$12: Reverse mode.

$00C8200Length of line minus 1 during
  screen input. Values: $27, 39; $4F, 79.
$00C9201Cursor row during screen input.
  Values: $00-$18, 0-24.
$00CA202Cursor column during screen input.
  Values: $00-$27, 0-39.
$00CB203Matrix code of key currently being
  pressed. Values:

$00-$3F: Keyboard matrix code.
$40: No key is currently pressed.

$00CC204Cursor visibility switch.
  Values:

$00: Cursor is on.
$01-$FF: Cursor is off.

$00CD205Delay counter for changing cursor
  phase. Values:

$00, 0: Must change cursor phase.
$01-$14, 1-20: Delay.

$00CE206Screen code of character under
  cursor.
$00CF207Cursor phase switch. Values:

$00: Cursor off phase, original character
    visible.
$01: Cursor on phase, reverse character visible.

$00D0208End of line switch during screen
  input. Values:

$00: Return character reached, end of line.
$01-$FF: Still reading characters from line.

$00D1-$00D2209-210Pointer to current line
  in screen memory.
$00D3211Current cursor column. Values:
  $00-$27, 0-39.
$00D4212Quotation mode switch. Values:

$00: Normal mode.
$01: Quotation mode.

$00D5213Length of current screen line minus
  1. Values: $27, 39; $4F, 79.
$00D6214Current cursor row. Values:
  $00-$18, 0-24.
$00D7215PETSCII code of character during
  screen input/output.
  Bit buffer during datasette input.
  Block checksum during datasette output.
$00D8216Number of insertions. Values:

$00: No insertions made, normal mode, control codes
    change screen layout or behavior.
$01-$FF: Number of insertions, when inputting this
    many character next, those must be turned into control codes, similarly to
    quotation mode.

$00D9-$00F1217-241High byte of pointers to
  each line in screen memory (25 bytes). Values:

$00-$7F: Pointer high byte.
$80-$FF: No pointer, line is an extension of previous
    line on screen.

$00F2242Temporary area during scrolling the
  screen.
$00F3-$00F4243-244Pointer to current line
  in Color RAM.
$00F5-$00F6245-246Pointer to current
  conversion table during conversion from keyboard matrix codes to PETSCII
  codes.
$00F7-$00F8247-248Pointer to RS232 input
  buffer. Values:

$0000-$00FF: No buffer defined, a new buffer must be
    allocated upon RS232 input.
$0100-$FFFF: Buffer pointer.

$00F9-$00FA249-250Pointer to RS232 output
  buffer. Values:

$0000-$00FF: No buffer defined, a new buffer must be
    allocated upon RS232 output.
$0100-$FFFF: Buffer pointer.

$00FB-$00FE251-254Unused (4 bytes).
$00FF-$010A255-266Buffer for conversion
  from floating point to string (12 bytes.)

$0100-$01FF, 256-511Processor
  stack
$00FF-$010A255-266Buffer for conversion
  from floating point to string (12 bytes.)
$0100-$013D256-317Pointers to bytes read
  with error during datasette input (62 bytes, 31 entries).
$0100-$01FF256-511Processor stack. Also
  used for storing data related to FOR and GOSUB.

$0200-$02FF, 512-767
$0200-$0258512-600Input buffer, storage
  area for data read from screen (89 bytes).
$0259-$0262601-610Logical numbers assigned
  to files (10 bytes, 10 entries).
$0263-$026C611-620Device numbers assigned
  to files (10 bytes, 10 entries).
$026D-$0276621-630Secondary addresses
  assigned to files (10 bytes, 10 entries).
$0277-$0280631-640Keyboard buffer (10
  bytes, 10 entries).
$0281-$0282641-642Pointer to beginning of
  BASIC area after memory test.
  Default: $0800, 2048.
$0283-$0284643-644Pointer to end of BASIC
  area after memory test.
  Default: $A000, 40960.
$0285645Unused. (Serial bus timeout.)
$0286646Current color, cursor color.
  Values: $00-$0F, 0-15.
$0287647Color of character under cursor.
  Values: $00-$0F, 0-15.
$0288648High byte of pointer to screen
  memory for screen input/output.
  Default: $04, $0400, 1024.
$0289649Maximum length of keyboard buffer.
  Values:

$00, 0: No buffer.
$01-$0F, 1-15: Buffer size.

$028A650Keyboard repeat switch. Bits:

Bits #6-#7:

%00: Only cursor up/down, cursor left/right, Insert/Delete
      and Space repeat.
%01: No key repeats.
%1x: All keys repeat.


$028B651Delay counter during repeat
  sequence, for delaying between successive repeats. Values:

$00, 0: Must repeat key.
$01-$04, 1-4: Delay repetition.

$028C652Repeat sequence delay counter, for
  delaying before first repetition. Values:

$00, 0: Must start repeat sequence.
$01-$10, 1-16: Delay repeat sequence.

$028D653Shift key indicator. Bits:

Bit #0: 1 = One or more of left Shift, right Shift or
    Shift Lock is currently being pressed or locked.
Bit #1: 1 = Commodore is currently being pressed.
Bit #2: 1 = Control is currently being pressed.

$028E654Previous value of shift key
  indicator. Bits:

Bit #0: 1 = One or more of left Shift, right Shift or
    Shift Lock was pressed or locked at the time of previous check.
Bit #1: 1 = Commodore was pressed at the time of
    previous check.
Bit #2: 1 = Control was pressed at the time of
    previous check.

$028F-$0290655-656Execution address of
  routine that, based on the status of shift keys, sets the pointer at memory
  address $00F5-$00F6 to the appropriate conversion table for converting
  keyboard matrix codes to PETSCII codes.
  Default: $EB48.
$0291657Commodore-Shift switch. Bits:

Bit #7: 0 = Commodore-Shift is enabled, the key combination
    will toggle between the uppercase/graphics and lowercase/uppercase character
    set; 1 = Commodore-Shift is disabled.

$0292658Scroll direction switch during
  scrolling the screen. Values:

$00: Insertion of line before current line, current
    line and all lines below it must be scrolled 1 line downwards.
$01-$FF: Bottom of screen reached, complete screen
    must be scrolled 1 line upwards.

$0293659RS232 control register. Bits:

Bits #0-#3: Baud rate, transfer speed. Values:

%0000: User specified.
%0001: 50 bit/s.
%0010: 75 bit/s.
%0011: 110 bit/s.
%0100: 150 bit/s.
%0101: 300 bit/s.
%0110: 600 bit/s.
%0111: 1200 bit/s.
%1000: 2400 bit/s.
%1001: 1800 bit/s.
%1010: 2400 bit/s.
%1011: 3600 bit/s.
%1100: 4800 bit/s.
%1101: 7200 bit/s.
%1110: 9600 bit/s.
%1111: 19200 bit/s.

Bits #5-#6: Byte size, number of data bits per byte;
    %00 = 8; %01 = 7, %10 = 6; %11 = 5.
Bit #7: Number of stop bits; 0 = 1 stop bit; 1 = 2
    stop bits.

$0294660RS232 command register. Bits:

Bit #0: Synchronization type; 0 = 3 lines; 1 = X
    lines.
Bit #4: Transmission type; 0 = Duplex; 1 = Half
    duplex.
Bits #5-#7: Parity mode. Values:

%xx0: No parity check, bit #7 does not exist.
%001: Odd parity.
%011: Even parity.
%101: No parity check, bit #7 is always 1.
%111: No parity check, bit #7 is always 0.


$0295-$0296661-662Default value of RS232
  output timer, based on baud rate. (Must be filled with actual value before
  RS232 input/output if baud rate is "user specified" in RS232 control
  register, memory address $0293.)
$0297663Value of ST variable, device status
  for RS232 input/output. Bits:

Bit #0: 1 = Parity error occurred.
Bit #1: 1 = Frame error, a stop bit with the value of
    0, occurred.
Bit #2: 1 = Input buffer underflow occurred, too much
    data has arrived but it has not been read from the buffer in time.
Bit #3: 1 = Input buffer is empty, nothing to
    read.
Bit #4: 0 = Sender is Clear To Send; 1 = Sender is
    not ready to send data to receiver.
Bit #6: 0 = Receiver reports Data Set Ready; 1 =
    Receiver is not ready to receive data.
Bit #7: 1 = Carrier loss, a stop bit and a data byte
    both with the value of 0, detected.

$0298664RS232 byte size, number of data
  bits per data byte, default value for bit counters.
$0299-$029A665-666Default value of RS232
  input timer, based on baud rate. (Calculated automatically from default
  value of RS232 output timer, at memory address $0295-$0296.)
$029B667Offset of byte received in RS232
  input buffer.
$029C668Offset of current byte in RS232
  input buffer.
$029D669Offset of byte to send in RS232
  output buffer.
$029E670Offset of current byte in RS232
  output buffer.
$029F-$02A0671-672Temporary area for saving
  pointer to original interrupt service routine during datasette input output.
  Values:

$0000-$00FF: No datasette input/output took place yet
    or original pointer has been already restored.
$0100-$FFFF: Original pointer, datasette input/output
    currently in progress.

$02A1673Temporary area for saving original
  value of CIA#2 interrupt control register, at memory address $DD0D, during
  RS232 input/output.
$02A2674Temporary area for saving original
  value of CIA#1 timer #1 control register, at memory address $DC0E, during
  datasette input/output.
$02A3675Temporary area for saving original
  value of CIA#1 interrupt control register, at memory address $DC0D, during
  datasette input/output.
$02A4676Temporary area for saving original
  value of CIA#1 timer #1 control register, at memory address $DC0E, during
  datasette input/output.
$02A5677Number of line currently being
  scrolled during scrolling the screen.
$02A6678PAL/NTSC switch, for selecting
  RS232 baud rate from the proper table. Values:

$00: NTSC.
$01: PAL.

$02A7-$02FF679-767Unused (89 bytes).

$0300-$03FF, 768-1023
$0300-$0301768-769Execution address of warm
  reset, displaying optional BASIC error message and entering BASIC idle
  loop.
  Default: $E38B.
$0302-$0303770-771Execution address of
  BASIC idle loop.
  Default: $A483.
$0304-$0305772-773Execution address of
  BASIC line tokenizer routine.
  Default: $A57C.
$0306-$0307774-775Execution address of
  BASIC token decoder routine.
  Default: $A71A.
$0308-$0309776-777Execution address of
  BASIC instruction executor routine.
  Default: $A7E4.
$030A-$030B778-779Execution address of
  routine reading next item of BASIC expression.
  Default: $AE86.
$030C780Default value of register A for
  SYS.
  Value of register A after SYS.
$030D781Default value of register X for
  SYS.
  Value of register X after SYS.
$030E782Default value of register Y for
  SYS.
  Value of register Y after SYS.
$030F783Default value of status register
  for SYS.
  Value of status register after SYS.
$0310-$0312784-786JMP ABS machine
  instruction, jump to USR() function.
  $0311-$0312, 785-786: Execution address of USR() function.
$0313787Unused.
$0314-$0315788-789Execution address of
  interrupt service routine.
  Default: $EA31.
$0316-$0317790-791Execution address of BRK
  service routine.
  Default: $FE66.
$0318-$0319792-793Execution address of
  non-maskable interrupt service routine.
  Default: $FE47.
$031A-$031B794-795Execution address of
  OPEN, routine opening files.
  Default: $F34A.
$031C-$031D796-797Execution address of
  CLOSE, routine closing files.
  Default: $F291.
$031E-$031F798-799Execution address of
  CHKIN, routine defining file as default input.
  Default: $F20E.
$0320-$0321800-801Execution address of
  CHKOUT, routine defining file as default output.
  Default: $F250.
$0322-$0323802-803Execution address of
  CLRCHN, routine initializing input/output.
  Default: $F333.
$0324-$0325804-805Execution address of
  CHRIN, data input routine, except for keyboard and RS232 input.
  Default: $F157.
$0326-$0327806-807Execution address of
  CHROUT, general purpose data output routine.
  Default: $F1CA.
$0328-$0329808-809Execution address of
  STOP, routine checking the status of Stop key indicator, at memory address
  $0091.
  Default: $F6ED.
$032A-$032B810-811Execution address of
  GETIN, general purpose data input routine.
  Default: $F13E.
$032C-$032D812-813Execution address of
  CLALL, routine initializing input/output and clearing all file assignment
  tables.
  Default: $F32F.
$032E-$032F814-815Unused.
  Default: $FE66.
$0330-$0331816-817Execution address of
  LOAD, routine loading files.
  Default: $F4A5.
$0332-$0333818-819Execution address of
  SAVE, routine saving files.
  Default: $F5ED.
$0334-$033B820-827Unused (8 bytes).
$033C-$03FB828-1019Datasette buffer (192
  bytes).
$03FC-$03FF1020-1023Unused (4 bytes).

$0400-$07FF, 1024-2047Default screen
  memory
$0400-$07E71024-2023Default area of screen
  memory (1000 bytes).
$07E8-$07F72024-2039Unused (16 bytes).
$07F8-$07FF2040-2047Default area for sprite
  pointers (8 bytes).

$0800-$9FFF, 2048-40959BASIC area
$08002048Unused. (Must contain a value of 0
  so that the BASIC program can be RUN.)
$0801-$9FFF2049-40959Default BASIC area
  (38911 bytes).
$8000-$9FFF32768-40959Optional cartridge
  ROM (8192 bytes).
  $8000-$8001, 32768-32769: Execution address of cold reset.
  $8002-$8003, 32770-32771: Execution address of non-maskable interrupt
  service routine.
  $8004-$8008, 32772-32776: Cartridge signature. If contains the uppercase
  PETSCII string "CBM80" ($C3,$C2,$CD,$38,$30) then the routine vectors are
  accepted by the KERNAL.

$A000-$BFFF, 40960-49151BASIC ROM
$A000-$BFFF40960-49151BASIC ROM or RAM area
  (8192 bytes); depends on the value of bits #0-#2 of the processor port at
  memory address $0001:

%x00, %x01 or %x10: RAM area.
%x11: BASIC ROM.


$C000-$CFFF, 49152-53247Upper RAM
  area
$C000-$CFFF49152-53247Upper RAM area (4096
  bytes).

$D000-$DFFF, 53248-57343I/O Area
$D000-$DFFF53248-57343I/O Area (memory
  mapped chip registers), Character ROM or RAM area (4096 bytes); depends on
  the value of bits #0-#2 of the processor port at memory address $0001:

%x00: RAM area.
%0xx: Character ROM. (Except for the value %000, see
    above.)
%1xx: I/O Area. (Except for the value %100, see
    above.)


$D000-$DFFF, 53248-57343Character
  ROM
$D000-$DFFF53248-57343Character ROM, shape
  of characters (4096 bytes).
$D000-$D7FF53248-55295Shape of characters
  in uppercase/graphics character set (2048 bytes, 256 entries).
$D800-$DFFF55295-57343Shape of characters
  in lowercase/uppercase character set (2048 bytes, 256 entries).

$D000-$D3FF, 53248-54271VIC-II; video
  display
$D00053248Sprite #0 X-coordinate (only bits
  #0-#7).
$D00153249Sprite #0 Y-coordinate.
$D00253250Sprite #1 X-coordinate (only bits
  #0-#7).
$D00353251Sprite #1 Y-coordinate.
$D00453252Sprite #2 X-coordinate (only bits
  #0-#7).
$D00553253Sprite #2 Y-coordinate.
$D00653254Sprite #3 X-coordinate (only bits
  #0-#7).
$D00753255Sprite #3 Y-coordinate.
$D00853256Sprite #4 X-coordinate (only bits
  #0-#7).
$D00953257Sprite #4 Y-coordinate.
$D00A53258Sprite #5 X-coordinate (only bits
  #0-#7).
$D00B53259Sprite #5 Y-coordinate.
$D00C53260Sprite #6 X-coordinate (only bits
  #0-#7).
$D00D53261Sprite #6 Y-coordinate.
$D00E53262Sprite #7 X-coordinate (only bits
  #0-#7).
$D00F53263Sprite #7 Y-coordinate.
$D01053264Sprite #0-#7 X-coordinates (bit
  #8). Bits:

Bit #x: Sprite #x X-coordinate bit #8.

$D01153265Screen control register #1.
  Bits:

Bits #0-#2: Vertical raster scroll.
Bit #3: Screen height; 0 = 24 rows; 1 = 25 rows.
Bit #4: 0 = Screen off, complete screen is covered by
    border; 1 = Screen on, normal screen contents are visible.
Bit #5: 0 = Text mode; 1 = Bitmap mode.
Bit #6: 1 = Extended background mode on.
Bit #7: Read: Current raster line (bit #8).
    Write: Raster line to generate interrupt at (bit #8).

Default: $1B, %00011011.
$D01253266Read: Current raster line (bits
  #0-#7).
  Write: Raster line to generate interrupt at (bits #0-#7).
$D01353267Light pen X-coordinate (bits
  #1-#8).
  Read-only.
$D01453268Light pen Y-coordinate.
  Read-only.
$D01553269Sprite enable register. Bits:

Bit #x: 1 = Sprite #x is enabled, drawn onto the
    screen.

$D01653270Screen control register #2.
  Bits:

Bits #0-#2: Horizontal raster scroll.
Bit #3: Screen width; 0 = 38 columns; 1 = 40
    columns.
Bit #4: 1 = Multicolor mode on.

Default: $C8, %11001000.
$D01753271Sprite double height register.
  Bits:

Bit #x: 1 = Sprite #x is stretched to double
    height.

$D01853272Memory setup register. Bits:

Bits #1-#3: In text mode, pointer to character memory
    (bits #11-#13), relative to VIC bank, memory address $DD00. Values:

%000, 0: $0000-$07FF, 0-2047.
%001, 1: $0800-$0FFF, 2048-4095.
%010, 2: $1000-$17FF, 4096-6143.
%011, 3: $1800-$1FFF, 6144-8191.
%100, 4: $2000-$27FF, 8192-10239.
%101, 5: $2800-$2FFF, 10240-12287.
%110, 6: $3000-$37FF, 12288-14335.
%111, 7: $3800-$3FFF, 14336-16383.

Values %010 and %011 in VIC bank #0 and #2 select
    Character ROM instead.
    In bitmap mode, pointer to bitmap memory (bit #13), relative to VIC bank,
    memory address $DD00. Values:

%0xx, 0: $0000-$1FFF, 0-8191.
%1xx, 4: $2000-$3FFF, 8192-16383.

Bits #4-#7: Pointer to screen memory (bits #10-#13),
    relative to VIC bank, memory address $DD00. Values:

%0000, 0: $0000-$03FF, 0-1023.
%0001, 1: $0400-$07FF, 1024-2047.
%0010, 2: $0800-$0BFF, 2048-3071.
%0011, 3: $0C00-$0FFF, 3072-4095.
%0100, 4: $1000-$13FF, 4096-5119.
%0101, 5: $1400-$17FF, 5120-6143.
%0110, 6: $1800-$1BFF, 6144-7167.
%0111, 7: $1C00-$1FFF, 7168-8191.
%1000, 8: $2000-$23FF, 8192-9215.
%1001, 9: $2400-$27FF, 9216-10239.
%1010, 10: $2800-$2BFF, 10240-11263.
%1011, 11: $2C00-$2FFF, 11264-12287.
%1100, 12: $3000-$33FF, 12288-13311.
%1101, 13: $3400-$37FF, 13312-14335.
%1110, 14: $3800-$3BFF, 14336-15359.
%1111, 15: $3C00-$3FFF, 15360-16383.


$D01953273Interrupt status register. Read
  bits:

Bit #0: 1 = Current raster line is equal to the
    raster line to generate  interrupt at.
Bit #1: 1 = Sprite-background collision occurred.
Bit #2: 1 = Sprite-sprite collision occurred.
Bit #3: 1 = Light pen signal arrived.
Bit #7: 1 = An event (or more events), that may generate an
    interrupt, occurred and it has not been (not all of them have been) acknowledged
    yet.

Write bits:

Bit #0: 1 = Acknowledge raster interrupt.
Bit #1: 1 = Acknowledge sprite-background collision
    interrupt.
Bit #2: 1 = Acknowledge sprite-sprite collision
    interrupt.
Bit #3: 1 = Acknowledge light pen interrupt.

$D01A53274Interrupt control register.
  Bits:

Bit #0: 1 = Raster interrupt enabled.
Bit #1: 1 = Sprite-background collision interrupt
    enabled.
Bit #2: 1 = Sprite-sprite collision interrupt
    enabled.
Bit #3: 1 = Light pen interrupt enabled.

$D01B53275Sprite priority register.
  Bits:

Bit #x: 0 = Sprite #x is drawn in front of screen
    contents; 1 = Sprite #x is behind screen contents.

$D01C53276Sprite multicolor mode register.
  Bits:

Bit #x: 0 = Sprite #x is single color; 1 = Sprite #x
    is multicolor.

$D01D53277Sprite double width register.
  Bits:

Bit #x: 1 = Sprite #x is stretched to double
    width.

$D01E53278Sprite-sprite collision register.
  Read bits:

Bit #x: 1 = Sprite #x collided with another
    sprite.

Write: Enable further detection of sprite-sprite
  collisions.
$D01F53279Sprite-background collision
  register. Read bits:

Bit #x: 1 = Sprite #x collided with background.

Write: Enable further detection of sprite-background
  collisions.
$D02053280Border color (only bits
  #0-#3).
$D02153281Background color (only bits
  #0-#3).
$D02253282Extra background color #1 (only
  bits #0-#3).
$D02353283Extra background color #2 (only
  bits #0-#3).
$D02453284Extra background color #3 (only
  bits #0-#3).
$D02553285Sprite extra color #1 (only bits
  #0-#3).
$D02653286Sprite extra color #2 (only bits
  #0-#3).
$D02753287Sprite #0 color (only bits
  #0-#3).
$D02853288Sprite #1 color (only bits
  #0-#3).
$D02953289Sprite #2 color (only bits
  #0-#3).
$D02A53290Sprite #3 color (only bits
  #0-#3).
$D02B53291Sprite #4 color (only bits
  #0-#3).
$D02C53292Sprite #5 color (only bits
  #0-#3).
$D02D53293Sprite #6 color (only bits
  #0-#3).
$D02E53294Sprite #7 color (only bits
  #0-#3).
$D02F-$D03F53295-53311Unusable (17
  bytes).
$D040-$D3FF53312-54271VIC-II register
  images (repeated every $40, 64 bytes).

$D400-$D7FF, 54272-55295SID; audio
$D400-$D40154272-54273Voice #1
  frequency.
  Write-only.
$D402-$D40354274-54275Voice #1 pulse
  width.
  Write-only.
$D40454276Voice #1 control register.
  Bits:

Bit #0: 0 = Voice off, Release cycle; 1 = Voice on,
    Attack-Decay-Sustain cycle.
Bit #1: 1 = Synchronization enabled.
Bit #2: 1 = Ring modulation enabled.
Bit #3: 1 = Disable voice, reset noise generator.
Bit #4: 1 = Triangle waveform enabled.
Bit #5: 1 = Saw waveform enabled.
Bit #6: 1 = Rectangle waveform enabled.
Bit #7: 1 = Noise enabled.

Write-only.
$D40554277Voice #1 Attack and Decay length.
  Bits:

Bits #0-#3: Decay length. Values:

%0000, 0: 6 ms.
%0001, 1: 24 ms.
%0010, 2: 48 ms.
%0011, 3: 72 ms.
%0100, 4: 114 ms.
%0101, 5: 168 ms.
%0110, 6: 204 ms.
%0111, 7: 240 ms.
%1000, 8: 300 ms.
%1001, 9: 750 ms.
%1010, 10: 1.5 s.
%1011, 11: 2.4 s.
%1100, 12: 3 s.
%1101, 13: 9 s.
%1110, 14: 15 s.
%1111, 15: 24 s.

Bits #4-#7: Attack length. Values:

%0000, 0: 2 ms.
%0001, 1: 8 ms.
%0010, 2: 16 ms.
%0011, 3: 24 ms.
%0100, 4: 38 ms.
%0101, 5: 56 ms.
%0110, 6: 68 ms.
%0111, 7: 80 ms.
%1000, 8: 100 ms.
%1001, 9: 250 ms.
%1010, 10: 500 ms.
%1011, 11: 800 ms.
%1100, 12: 1 s.
%1101, 13: 3 s.
%1110, 14: 5 s.
%1111, 15: 8 s.


Write-only.
$D40654278Voice #1 Sustain volume and
  Release length. Bits:

Bits #0-#3: Release length. Values:

%0000, 0: 6 ms.
%0001, 1: 24 ms.
%0010, 2: 48 ms.
%0011, 3: 72 ms.
%0100, 4: 114 ms.
%0101, 5: 168 ms.
%0110, 6: 204 ms.
%0111, 7: 240 ms.
%1000, 8: 300 ms.
%1001, 9: 750 ms.
%1010, 10: 1.5 s.
%1011, 11: 2.4 s.
%1100, 12: 3 s.
%1101, 13: 9 s.
%1110, 14: 15 s.
%1111, 15: 24 s.

Bits #4-#7: Sustain volume.

Write-only.
$D407-$D40854279-54280Voice #2
  frequency.Write-only.
$D409-$D40A54281-54282Voice #2 pulse
  width.Write-only.
$D40B54283Voice #2 control register.
  Write-only.
$D40C54284Voice #2 Attack and Decay
  length.
  Write-only.
$D40D54285Voice #2 Sustain volume and
  Release length.
  Write-only.
$D40E-$D40F54286-54287Voice #3
  frequency.
  Write-only.
$D410-$D41154288-54289Voice #3 pulse
  width.
  Write-only.
$D41254290Voice #3 control register.
  Write-only.
$D41354291Voice #3 Attack and Decay
  length.
  Write-only.
$D41454292Voice #3 Sustain volume and
  Release length.
  Write-only.
$D41554293Filter cut off frequency (bits
  #0-#2).
  Write-only.
$D41654294Filter cut off frequency (bits
  #3-#10).
  Write-only.
$D41754295Filter control. Bits:

Bit #0: 1 = Voice #1 filtered.
Bit #1: 1 = Voice #2 filtered.
Bit #2: 1 = Voice #3 filtered.
Bit #3: 1 = External voice filtered.
Bits #4-#7: Filter resonance.

Write-only.
$D41854296Volume and filter modes.
  Bits:

Bits #0-#3: Volume.
Bit #4: 1 = Low pass filter enabled.
Bit #5: 1 = Band pass filter enabled.
Bit #6: 1 = High pass filter enabled.
Bit #7: 1 = Voice #3 disabled.

Write-only.
$D41954297X value of paddle selected at
  memory address $DC00. (Updates at every 512 system cycles.)
  Read-only.
$D41A54298Y value of paddle selected at
  memory address $DC00. (Updates at every 512 system cycles.)
  Read-only.
$D41B54299Voice #3 waveform output.
  Read-only.
$D41C54300Voice #3 ADSR output.
  Read-only.
$D41D-$D41F54301-54303Unusable (3
  bytes).
$D420-$D7FF54304-55295SID register images
  (repeated every $20, 32 bytes).

$D800-$DBFF, 55296-56319Color RAM
$D800-$DBE755296-56295Color RAM (1000
  bytes, only bits #0-#3).
$DBE8-$DBFF56296-56319Unused (24 bytes,
  only bits #0-#3).

$DC00-$DCFF, 56320-56575CIA#1; inputs
  (keyboard, joystick, mouse), datasette, IRQ control
$DC0056320Port A, keyboard matrix columns
  and joystick #2. Read bits:

Bit #0: 0 = Port 2 joystick up pressed.
Bit #1: 0 = Port 2 joystick down pressed.
Bit #2: 0 = Port 2 joystick left pressed.
Bit #3: 0 = Port 2 joystick right pressed.
Bit #4: 0 = Port 2 joystick fire pressed.

Write bits:

Bit #x: 0 = Select keyboard matrix column #x.
Bits #6-#7: Paddle selection; %01 = Paddle #1; %10 =
    Paddle #2.

$DC0156321Port B, keyboard matrix rows and
  joystick #1. Bits:

Bit #x: 0 = A key is currently being pressed in
    keyboard matrix row #x, in the column selected at memory address
    $DC00.
Bit #0: 0 = Port 1 joystick up pressed.
Bit #1: 0 = Port 1 joystick down pressed.
Bit #2: 0 = Port 1 joystick left pressed.
Bit #3: 0 = Port 1 joystick right pressed.
Bit #4: 0 = Port 1 joystick fire pressed.

$DC0256322Port A data direction
  register.

Bit #x: 0 = Bit #x in port A can only be read; 1 =
    Bit #x in port A can be read and written.

$DC0356323Port B data direction
  register.

Bit #x: 0 = Bit #x in port B can only be read; 1 =
    Bit #x in port B can be read and written.

$DC04-$DC0556324-56325Timer A. Read:
  Current timer value.
  Write: Set timer start value.
$DC06-$DC0756326-56327Timer B. Read:
  Current timer value.
  Write: Set timer start value.
$DC0856328Time of Day, tenth seconds (in
  BCD). Values: $00-$09. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0956329Time of Day, seconds (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0A56330Time of Day, minutes (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0B56331Time of Day, hours (in BCD). Read
  bits:

Bits #0-#5: Hours.
Bit #7: 0 = AM; 1 = PM.

Write: Set TOD or alarm time.
$DC0C56332Serial shift register. (Bits are
  read and written upon every positive edge of the CNT pin.)
$DC0D56333Interrupt control and status
  register. Read bits:

Bit #0: 1 = Timer A underflow occurred.
Bit #1: 1 = Timer B underflow occurred.
Bit #2: 1 = TOD is equal to alarm time.
Bit #3: 1 = A complete byte has been received into or
    sent from serial shift register.
Bit #4: Signal level on FLAG pin, datasette
    input.
Bit #7: An interrupt has been generated.

Write bits:

Bit #0: 1 = Enable interrupts generated by timer A
    underflow.
Bit #1: 1 = Enable interrupts generated by timer B
    underflow.
Bit #2: 1 = Enable TOD alarm interrupt.
Bit #3: 1 = Enable interrupts generated by a byte
    having been  received/sent via serial shift register.
Bit #4: 1 = Enable interrupts generated by positive
    edge on FLAG pin.
Bit #7: Fill bit; bits #0-#6, that are set to 1, get
    their values from this bit; bits #0-#6, that are set to 0, are left
    unchanged.

$DC0E56334Timer A control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #6.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #6; 1 = upon timer underflow, generate a positive edge on port B bit #6
    for 1 system cycle.
  Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bit #5: 0 = Timer counts system cycles; 1 = Timer
    counts positive edges on CNT pin.
Bit #6: Serial shift register direction; 0 = Input,
    read; 1 = Output, write.
Bit #7: TOD speed; 0 = 60 Hz; 1 = 50 Hz.

$DC0F56335Timer B control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #7.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #7; 1 = upon timer underflow, generate a positive edge on port B bit #7
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bits #5-#6: %00 = Timer counts system cycles; %01 =
    Timer counts positive edges on CNT pin; %10 = Timer counts underflows of
    timer A; %11 = Timer counts underflows of timer A occurring along with a
    positive edge on CNT pin.
Bit #7: 0 = Writing into TOD registers sets TOD; 1 =
    Writing into TOD registers sets alarm time.

$DC10-$DCFF56336-56575CIA#1 register images
  (repeated every $10, 16 bytes).

$DD00-$DDFF, 56576-56831CIA#2; serial
  bus, RS232, NMI control
$DD0056576Port A, serial bus access.
  Bits:

Bits #0-#1: VIC bank. Values:

%00, 0: Bank #3, $C000-$FFFF, 49152-65535.
%01, 1: Bank #2, $8000-$BFFF, 32768-49151.
%10, 2: Bank #1, $4000-$7FFF, 16384-32767.
%11, 3: Bank #0, $0000-$3FFF, 0-16383.

Bit #2: RS232 TXD line, output bit.
Bit #3: Serial bus ATN OUT; 0 = High; 1 = Low.
Bit #4: Serial bus CLOCK OUT; 0 = High; 1 = Low.
Bit #5: Serial bus DATA OUT; 0 = High; 1 = Low.
Bit #6: Serial bus CLOCK IN; 0 = Low; 1 = High.
Bit #7: Serial bus DATA IN; 0 = Low; 1 = High.

$DD0156577Port B, RS232 access. Read
  bits:

Bit #0: RS232 RXD line, input bit.
Bit #3: RS232 RI line.
Bit #4: RS232 DCD line.
Bit #5: User port H pin.
Bit #6: RS232 CTS line; 1 = Sender is ready to
    send.
Bit #7: RS232 DSR line; 1 = Receiver is ready to
    receive.

Write bits:

Bit #1: RS232 RTS line. 1 = Sender is ready to
    send.
Bit #2: RS232 DTR line. 1 = Receiver is ready to
    receive.
Bit #3: RS232 RI line.
Bit #4: RS232 DCD line.
Bit #5: User port H pin.

$DD0256578Port A data direction
  register.

Bit #x: 0 = Bit #x in port A can only be read; 1 =
    Bit #x in port A can be read and written.

$DD0356579Port B data direction
  register.

Bit #x: 0 = Bit #x in port B can only be read; 1 =
    Bit #x in port B can be read and written.

$DD04-$DD0556580-56581Timer A. Read:
  Current timer value.
  Write: Set timer start value.
$DD06-$DD0756582-56583Timer B. Read:
  Current timer value.
  Write: Set timer start value.
$DD0856584Time of Day, tenth seconds (in
  BCD). Values: $00-$09. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0956585Time of Day, seconds (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0A56586Time of Day, minutes (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0B56587Time of Day, hours (in BCD). Read
  bits:

Bits #0-#5: Hours.
Bit #7: 0 = AM; 1 = PM.

Write: Set TOD or alarm time.
$DD0C56588Serial shift register. (Bits are
  read and written upon every positive edge of the CNT pin.)
$DD0D56589Interrupt control and status
  register. Read bits:

Bit #0: 1 = Timer A underflow occurred.
Bit #1: 1 = Timer B underflow occurred.
Bit #2: 1 = TOD is equal to alarm time.
Bit #3: 1 = A complete byte has been received into or
    sent from serial shift register.
Bit #4: Signal level on FLAG pin.
Bit #7: A non-maskable interrupt has been
    generated.

Write bits:

Bit #0: 1 = Enable non-maskable interrupts generated
    by timer A underflow.
Bit #1: 1 = Enable non-maskable interrupts generated
    by timer B underflow.
Bit #2: 1 = Enable TOD alarm non-maskable
    interrupt.
Bit #3: 1 = Enable non-maskable interrupts generated
    by a byte having been received/sent via serial shift register.
Bit #4: 1 = Enable non-maskable interrupts generated
    by positive edge on FLAG pin.
Bit #7: Fill bit; bits #0-#6, that are set to 1, get
    their values from this bit; bits #0-#6, that are set to 0, are left
    unchanged.

$DD0E56590Timer A control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #6.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #6; 1 = upon timer underflow, generate a positive edge on port B bit #6
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bit #5: 0 = Timer counts system cycles; 1 = Timer
    counts positive edges on CNT pin.
Bit #6: Serial shift register direction; 0 = Input,
    read; 1 = Output, write.
Bit #7: TOD speed; 0 = 60 Hz; 1 = 50 Hz.

$DD0F56591Timer B control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #7.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #7; 1 = upon timer underflow, generate a positive edge on port B bit #7
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bits #5-#6: %00 = Timer counts system cycles; %01 =
    Timer counts positive edges on CNT pin; %10 = Timer counts underflows of
    timer A; %11 = Timer counts underflows of timer A occurring along with a
    positive edge on CNT pin.
Bit #7: 0 = Writing into TOD registers sets TOD; 1 =
    Writing into TOD registers sets alarm time.

$DD10-$DDFF56592-56831CIA#2 register images
  (repeated every $10, 16 bytes).

$DE00-$DEFF, 56832-57087I/O Area
  #1
$DE00-$DEFF56832-57087I/O Area #1, memory
  mapped registers or machine code routines of optional external devices (256
  bytes). Layout and contents depend on the actual device.

$DF00-$DFFF, 57088-57343I/O Area
  #2
$DF00-$DFFF57088-57343I/O Area #2, memory
  mapped registers or machine code routines of optional external devices (256
  bytes). Layout and contents depend on the actual device.


$E000-$FFFF, 57344-65535KERNAL ROM
$E000-$FFFF57344-65535KERNAL ROM or RAM
  area (8192 bytes); depends on the value of bits #0-#2 of the processor port
  at memory address $0001:

%x0x: RAM area.
%x1x: KERNAL ROM.


$FFFA-$FFFF, 65530-65535Hardware
  vectors
$FFFA-$FFFB65530-65531Execution address of
  non-maskable interrupt service routine.
  Default: $FE43.
$FFFC-$FFFD65532-65533Execution address of
  cold reset.
  Default: $FCE2.
$FFFE-$FFFF65534-65535Execution address of
  interrupt service routine.
  Default: $FF48. | Description


$0000-$00FF, 0-255Zero page
$00000
  Processor port data direction register. Bits:

Bit #x: 0 = Bit #x in processor port can only be
    read; 1 = Bit #x in processor port can be read and written.

Default: $2F, %00101111.
$00011Processor port. Bits:

Bits #0-#2: Configuration for memory areas
    $A000-$BFFF, $D000-$DFFF and $E000-$FFFF. Values:

%x00: RAM visible in all three areas.
%x01: RAM visible at $A000-$BFFF and
      $E000-$FFFF.
%x10: RAM visible at $A000-$BFFF; KERNAL ROM
      visible at $E000-$FFFF.
%x11: BASIC ROM visible at $A000-$BFFF; KERNAL ROM
      visible at $E000-$FFFF.
%0xx: Character ROM visible at $D000-$DFFF. (Except
      for the value %000, see above.)
%1xx: I/O area visible at $D000-$DFFF. (Except for
      the value %100, see above.)

Bit #3: Datasette output signal level.
Bit #4: Datasette button status; 0 = One or more of
    PLAY, RECORD, F.FWD or REW pressed; 1 = No button is pressed.
Bit #5: Datasette motor control; 0 = On; 1 = Off.

Default: $37, %00110111.
$00022Unused.
$0003-$00043-4Unused.
  Default: $B1AA, execution address of routine converting floating point to
  integer.
$0005-$00065-6Unused.
  Default: $B391, execution address of routine converting integer to floating
  point.
$00077Byte being searched for during
  various operations.
  Current digit of number being input.
  Low byte of first integer operand during AND and OR.
  Low byte of integer-format FAC during INT().
$00088Byte being searched for during
  various operations.
  Current byte of BASIC line during tokenization.
  High byte of first integer operand during AND and OR.
$00099Current column number during SPC()
  and TAB().
$000A10LOAD/VERIFY switch. Values:

$00: LOAD.
$01-$FF: VERIFY.

$000B11Current token during
  tokenization.
  Length of BASIC line during insertion of line.
  AND/OR switch; $00 = AND; $FF = OR.
  Number of dimensions during array operations.
$000C12Switch for array operations.
  Values:

$00: Operation was not called by DIM.
$40-$7F: Operation was called by DIM.

$000D13Current expression type. Values:

$00: Numerical.
$FF: String.

$000E14Current numerical expression type.
  Bits:

Bit #7: 0 = Floating point; 1 = Integer.

$000F15Quotation mode switch during
  tokenization; Bit #6: 0 = Normal mode; 1 = Quotation mode.
  Quotation mode switch during LIST; $01 = Normal mode; $FE = Quotation
  mode.
  Garbage collection indicator during memory allocation for string variable;
  $00-$7F = There was no garbage collection yet; $80 = Garbage collection
  already took place.
$001016Switch during fetch of variable
  name. Values:

$00: Integer variables are accepted.
$01-$FF: Integer variables are not accepted.

$001117GET/INPUT/READ switch. Values:

$00: INPUT.
$40: GET.
$98: READ.

$001218Sign during SIN() and TAN().
  Values:

$00: Positive.
$FF: Negative.

$001319Current I/O device number.
  Default: $00, keyboard for input and screen for output.
$0014-$001520-21Line number during GOSUB,
  GOTO and RUN.
  Second line number during LIST.
  Memory address during PEEK, POKE, SYS and WAIT.
$001622Pointer to next expression in string
  stack. Values: $19; $1C; $1F; $22.
  Default: $19.
$0017-$001823-24Pointer to previous
  expression in string stack.
$0019-$002125-33String stack, temporary
  area for processing string expressions (9 bytes, 3 entries).
$0022-$002534-37Temporary area for various
  operations (4 bytes).
$0026-$002938-41Auxiliary arithmetical
  register for division and multiplication (4 bytes).
$002A42Unused.
$002B-$002C43-44Pointer to beginning of
  BASIC area.
  Default: $0801, 2049.
$002D-$002E45-46Pointer to beginning of
  variable area. (End of program plus 1.)
$002F-$003047-48Pointer to beginning of
  array variable area.
$0031-$003249-50Pointer to end of array
  variable area.
$0033-$003451-52Pointer to beginning of
  string variable area. (Grows downwards from end of BASIC area.)
$0035-$003653-54Pointer to memory allocated
  for current string variable.
$0037-$003855-56Pointer to end of BASIC
  area.
  Default: $A000, 40960.
$0039-$003A57-58Current BASIC line number.
  Values:

$0000-$F9FF, 0-63999: Line number.
$FF00-$FFFF: Direct mode, no BASIC program is being
    executed.

$003B-$003C59-60Current BASIC line number
  for CONT.
$003D-$003E61-62Pointer to next BASIC
  instruction for CONT. Values:

$0000-$00FF: CONT'ing is not possible.
$0100-$FFFF: Pointer to next BASIC instruction.

$003F-$004063-64BASIC line number of
  current DATA item for READ.
$0041-$004265-66Pointer to next DATA item
  for READ.
$0043-$004467-68Pointer to input result
  during GET, INPUT and READ.
$0045-$004669-70Name and type of current
  variable. Bits:

$0045 bits #0-#6: First character of variable
    name.
$0046 bits #0-#6: Second character of variable name;
    $00 = Variable name consists of only one character.
$0045 bit #7 and $0046 bit #7:

%00: Floating-point variable.
%01: String variable.
%10: FN function, created with DEF FN.
%11: Integer variable.


$0047-$004871-72Pointer to value of current
  variable or FN function.
$0049-$004A73-74Pointer to value of current
  variable during LET.
  Value of second and third parameter during WAIT.
  Logical number and device number during OPEN.
  $0049, 73: Logical number of CLOSE.
  Device number of LOAD, SAVE and VERIFY.
$004B-$004C75-76Temporary area for saving
  original pointer to current BASIC instruction during GET, INPUT and
  READ.
$004D77Comparison operator indicator.
  Bits:

Bit #1: 1 = ">" (greater than) is present in
    expression.
Bit #2: 1 = "=" (equal to) is present in
    expression.
Bit #3: 1 = "<" (less than) is present in
    expression.

$004E-$004F78-79Pointer to current FN
  function.
$0050-$005180-81Pointer to current string
  variable during memory allocation.
$005282Unused.
$005383Step size of garbage collection.
  Values: $03; $07.
$0054-$005684-86JMP ABS machine
  instruction, jump to current BASIC function.
  $0055-$0056, 85-86: Execution address of current BASIC function.
$0057-$005B87-91Arithmetic register #3 (5
  bytes).
$005C-$006092-96Arithmetic register #4 (5
  bytes).
$0061-$006597-101FAC, arithmetic register
  #1 (5 bytes).
$0066102Sign of FAC. Bits:

Bit #7: 0 = Positive; 1 = Negative.

$0067103Number of degrees during polynomial
  evaluation.
$0068104Temporary area for various
  operations.
$0069-$006D105-109ARG, arithmetic register
  #2 (5 bytes).
$006E110Sign of ARG. Bits:

Bit #7: 0 = Positive; 1 = Negative.

$006F-$0070111-112Pointer to first string
  expression during string comparison.
$0071-$0072113-114Auxiliary pointer during
  array operations.
  Temporary area for saving original pointer to current BASIC instruction
  during VAL().
  Pointer to current item of polynomial table during polynomial
  evaluation.
$0073-$008A115-138CHRGET. Machine code
  routine to read next byte from BASIC program or direct command (24
  bytes).
  $0079, 121: CHRGOT. Read current byte from BASIC program or direct
  command.
  $007A-$007B, 122-123: Pointer to current byte in BASIC program or direct
  command.
$008B-$008F139-143Previous result of
  RND().
$0090144Value of ST variable, device status
  for serial bus and datasette input/output. Serial bus bits:

Bit #0: Transfer direction during which the timeout
    occurred; 0 = Input; 1 = Output.
Bit #1: 1 = Timeout occurred.
Bit #4: 1 = VERIFY error occurred (only during
    VERIFY), the file read from the device did not match that in the
    memory.
Bit #6: 1 = End of file has been reached.
Bit #7: 1 = Device is not present.

Datasette bits:

Bit #2: 1 = Block is too short (shorter than 192
    bytes).
Bit #3: 1 = Block is too long (longer than 192
    bytes).
Bit #4: 1 = Not all bytes read with error during pass
    1 could be corrected during pass 2, or a VERIFY error occurred, the file
    read from the device did not match that in the memory.
Bit #5: 1 = Checksum error occurred.
Bit #6: 1 = End of file has been reached (only during
    reading data files).

$0091145Stop key indicator. Values:

$7F: Stop key is pressed.
$FF: Stop key is not pressed.

$0092146Unknown. (Timing constant during
  datasette input.)
$0093147LOAD/VERIFY switch. Values:

$00: LOAD.
$01-$FF: VERIFY.

$0094148Serial bus output cache status.
  Bits:

Bit #7: 1 = Output cache dirty, must transfer cache
    contents upon next output to serial bus.

$0095149Serial bus output cache, previous
  byte to be sent to serial bus.
$0096150Unknown. (End of tape indicator
  during datasette input/output.)
$0097151Temporary area for saving original
  value of Y register during input from RS232.
  Temporary area for saving original value of X register during input from
  datasette.
$0098152Number of files currently open.
  Values: $00-$0A, 0-10.
$0099153Current input device number.
  Default: $00, keyboard.
$009A154Current output device number.
  Default: $03, screen.
$009B155Unknown. (Parity bit during
  datasette input/output.)
$009C156Unknown. (Byte ready indicator
  during datasette input/output.)
$009D157System error display switch.
  Bits:

Bit #6: 0 = Suppress I/O error messages; 1 = Display
    them.
Bit #7: 0 = Suppress system messages; 1 =  Display
    them.

$009E158Byte to be put into output buffer
  during RS232 and datasette output.
  Block header type during datasette input/output.
  Length of file name during datasette input/output.
  Error counter during LOAD from datasette. Values: $00-$3E, 0-62.
$009F159Auxiliary counter for writing file
  name into datasette buffer.
  Auxiliary counter for comparing requested file name with file name read from
  datasette during datasette input.
  Error correction counter during LOAD from datasette. Values: $00-$3E,
  0-62.
$00A0-$00A2160-162Value of TI variable,
  time of day, increased by 1 every 1/60 second (on PAL machines). Values:
  $000000-$4F19FF, 0-518399 (on PAL machines).
$00A3163EOI switch during serial bus
  output. Bits:

Bit #7: 0 = Send byte right after handshake; 1 = Do
    EOI delay first.

Bit counter during datasette output.
$00A4164Byte buffer during serial bus
  input.
  Parity during datasette input/output.
$00A5165Bit counter during serial bus
  input/output.
  Counter for sync mark during datasette output.
$00A6166Offset of current byte in datasette
  buffer.
$00A7167Bit buffer during RS232 input.
$00A8168Bit counter during RS232 input.
$00A9169Stop bit switch during RS232 input.
  Values:

$00: Data bit.
$01-$FF: Stop bit.

$00AA170Byte buffer during RS232 input.
$00AB171Parity during RS232 input.
  Computed block checksum during datasette input.
$00AC-$00AD172-173Start address for SAVE to
  serial bus.
  Pointer to current byte during SAVE to serial bus or datasette.
  Pointer to line in screen memory to be scrolled during scrolling the
  screen.
$00AE-$00AF174-175Load address read from
  input file and pointer to current byte during LOAD/VERIFY from serial
  bus.
  End address after LOAD/VERIFY from serial bus or datasette.
  End address for SAVE to serial bus or datasette.
  Pointer to line in Color RAM to be scrolled during scrolling the screen.
$00B0-$00B1176-177Unknown.
$00B2-$00B3178-179Pointer to datasette
  buffer.
  Default: $033C, 828.
$00B4180Bit counter and stop bit switch
  during RS232 output. Bits:

Bits #0-#6: Bit count.
Bit #7: 0 = Data bit; 1 = Stop bit.

Bit counter during datasette input/output.
$00B5181Bit buffer (in bit #2) during RS232
  output.
$00B6182Byte buffer during RS232
  output.
$00B7183Length of file name or disk
  command; first parameter of LOAD, SAVE and VERIFY or fourth parameter of
  OPEN. Values:

$00: No parameter.
$01-$FF: Parameter length.

$00B8184Logical number of current file.
$00B9185Secondary address of current
  file.
$00BA186Device number of current file.
$00BB-$00BC187-188Pointer to current file
  name or disk command; first parameter of LOAD, SAVE and VERIFY or fourth
  parameter of OPEN.
$00BD189Parity during RS232 output.
  Byte buffer during datasette input/output.
$00BE190Block counter during datasette
  input/output.
$00BF191Unknown.
$00C0192Datasette motor switch. Values:

$00: No button was pressed, motor has been switched
    off. If a button is pressed on the datasette, must switch motor on.
$01-$FF: Motor is on.

$00C1-$00C2193-194Start address during SAVE
  to serial bus, LOAD and VERIFY from datasette and SAVE to datasette.
  Pointer to current byte during memory test.
$00C3-$00C4195-196Start address for a
  secondary address of 0 for LOAD and VERIFY from serial bus or datasette.
  Pointer to ROM table of default vectors during initialization of I/O
  vectors.
$00C5197Matrix code of key previously
  pressed. Values:

$00-$3F: Keyboard matrix code.
$40: No key was pressed at the time of previous
    check.

$00C6198Length of keyboard buffer.
  Values:

$00, 0: Buffer is empty.
$01-$0A, 1-10: Buffer length.

$00C7199Reverse mode switch. Values:

$00: Normal mode.
$12: Reverse mode.

$00C8200Length of line minus 1 during
  screen input. Values: $27, 39; $4F, 79.
$00C9201Cursor row during screen input.
  Values: $00-$18, 0-24.
$00CA202Cursor column during screen input.
  Values: $00-$27, 0-39.
$00CB203Matrix code of key currently being
  pressed. Values:

$00-$3F: Keyboard matrix code.
$40: No key is currently pressed.

$00CC204Cursor visibility switch.
  Values:

$00: Cursor is on.
$01-$FF: Cursor is off.

$00CD205Delay counter for changing cursor
  phase. Values:

$00, 0: Must change cursor phase.
$01-$14, 1-20: Delay.

$00CE206Screen code of character under
  cursor.
$00CF207Cursor phase switch. Values:

$00: Cursor off phase, original character
    visible.
$01: Cursor on phase, reverse character visible.

$00D0208End of line switch during screen
  input. Values:

$00: Return character reached, end of line.
$01-$FF: Still reading characters from line.

$00D1-$00D2209-210Pointer to current line
  in screen memory.
$00D3211Current cursor column. Values:
  $00-$27, 0-39.
$00D4212Quotation mode switch. Values:

$00: Normal mode.
$01: Quotation mode.

$00D5213Length of current screen line minus
  1. Values: $27, 39; $4F, 79.
$00D6214Current cursor row. Values:
  $00-$18, 0-24.
$00D7215PETSCII code of character during
  screen input/output.
  Bit buffer during datasette input.
  Block checksum during datasette output.
$00D8216Number of insertions. Values:

$00: No insertions made, normal mode, control codes
    change screen layout or behavior.
$01-$FF: Number of insertions, when inputting this
    many character next, those must be turned into control codes, similarly to
    quotation mode.

$00D9-$00F1217-241High byte of pointers to
  each line in screen memory (25 bytes). Values:

$00-$7F: Pointer high byte.
$80-$FF: No pointer, line is an extension of previous
    line on screen.

$00F2242Temporary area during scrolling the
  screen.
$00F3-$00F4243-244Pointer to current line
  in Color RAM.
$00F5-$00F6245-246Pointer to current
  conversion table during conversion from keyboard matrix codes to PETSCII
  codes.
$00F7-$00F8247-248Pointer to RS232 input
  buffer. Values:

$0000-$00FF: No buffer defined, a new buffer must be
    allocated upon RS232 input.
$0100-$FFFF: Buffer pointer.

$00F9-$00FA249-250Pointer to RS232 output
  buffer. Values:

$0000-$00FF: No buffer defined, a new buffer must be
    allocated upon RS232 output.
$0100-$FFFF: Buffer pointer.

$00FB-$00FE251-254Unused (4 bytes).
$00FF-$010A255-266Buffer for conversion
  from floating point to string (12 bytes.)

$0100-$01FF, 256-511Processor
  stack
$00FF-$010A255-266Buffer for conversion
  from floating point to string (12 bytes.)
$0100-$013D256-317Pointers to bytes read
  with error during datasette input (62 bytes, 31 entries).
$0100-$01FF256-511Processor stack. Also
  used for storing data related to FOR and GOSUB.

$0200-$02FF, 512-767
$0200-$0258512-600Input buffer, storage
  area for data read from screen (89 bytes).
$0259-$0262601-610Logical numbers assigned
  to files (10 bytes, 10 entries).
$0263-$026C611-620Device numbers assigned
  to files (10 bytes, 10 entries).
$026D-$0276621-630Secondary addresses
  assigned to files (10 bytes, 10 entries).
$0277-$0280631-640Keyboard buffer (10
  bytes, 10 entries).
$0281-$0282641-642Pointer to beginning of
  BASIC area after memory test.
  Default: $0800, 2048.
$0283-$0284643-644Pointer to end of BASIC
  area after memory test.
  Default: $A000, 40960.
$0285645Unused. (Serial bus timeout.)
$0286646Current color, cursor color.
  Values: $00-$0F, 0-15.
$0287647Color of character under cursor.
  Values: $00-$0F, 0-15.
$0288648High byte of pointer to screen
  memory for screen input/output.
  Default: $04, $0400, 1024.
$0289649Maximum length of keyboard buffer.
  Values:

$00, 0: No buffer.
$01-$0F, 1-15: Buffer size.

$028A650Keyboard repeat switch. Bits:

Bits #6-#7:

%00: Only cursor up/down, cursor left/right, Insert/Delete
      and Space repeat.
%01: No key repeats.
%1x: All keys repeat.


$028B651Delay counter during repeat
  sequence, for delaying between successive repeats. Values:

$00, 0: Must repeat key.
$01-$04, 1-4: Delay repetition.

$028C652Repeat sequence delay counter, for
  delaying before first repetition. Values:

$00, 0: Must start repeat sequence.
$01-$10, 1-16: Delay repeat sequence.

$028D653Shift key indicator. Bits:

Bit #0: 1 = One or more of left Shift, right Shift or
    Shift Lock is currently being pressed or locked.
Bit #1: 1 = Commodore is currently being pressed.
Bit #2: 1 = Control is currently being pressed.

$028E654Previous value of shift key
  indicator. Bits:

Bit #0: 1 = One or more of left Shift, right Shift or
    Shift Lock was pressed or locked at the time of previous check.
Bit #1: 1 = Commodore was pressed at the time of
    previous check.
Bit #2: 1 = Control was pressed at the time of
    previous check.

$028F-$0290655-656Execution address of
  routine that, based on the status of shift keys, sets the pointer at memory
  address $00F5-$00F6 to the appropriate conversion table for converting
  keyboard matrix codes to PETSCII codes.
  Default: $EB48.
$0291657Commodore-Shift switch. Bits:

Bit #7: 0 = Commodore-Shift is enabled, the key combination
    will toggle between the uppercase/graphics and lowercase/uppercase character
    set; 1 = Commodore-Shift is disabled.

$0292658Scroll direction switch during
  scrolling the screen. Values:

$00: Insertion of line before current line, current
    line and all lines below it must be scrolled 1 line downwards.
$01-$FF: Bottom of screen reached, complete screen
    must be scrolled 1 line upwards.

$0293659RS232 control register. Bits:

Bits #0-#3: Baud rate, transfer speed. Values:

%0000: User specified.
%0001: 50 bit/s.
%0010: 75 bit/s.
%0011: 110 bit/s.
%0100: 150 bit/s.
%0101: 300 bit/s.
%0110: 600 bit/s.
%0111: 1200 bit/s.
%1000: 2400 bit/s.
%1001: 1800 bit/s.
%1010: 2400 bit/s.
%1011: 3600 bit/s.
%1100: 4800 bit/s.
%1101: 7200 bit/s.
%1110: 9600 bit/s.
%1111: 19200 bit/s.

Bits #5-#6: Byte size, number of data bits per byte;
    %00 = 8; %01 = 7, %10 = 6; %11 = 5.
Bit #7: Number of stop bits; 0 = 1 stop bit; 1 = 2
    stop bits.

$0294660RS232 command register. Bits:

Bit #0: Synchronization type; 0 = 3 lines; 1 = X
    lines.
Bit #4: Transmission type; 0 = Duplex; 1 = Half
    duplex.
Bits #5-#7: Parity mode. Values:

%xx0: No parity check, bit #7 does not exist.
%001: Odd parity.
%011: Even parity.
%101: No parity check, bit #7 is always 1.
%111: No parity check, bit #7 is always 0.


$0295-$0296661-662Default value of RS232
  output timer, based on baud rate. (Must be filled with actual value before
  RS232 input/output if baud rate is "user specified" in RS232 control
  register, memory address $0293.)
$0297663Value of ST variable, device status
  for RS232 input/output. Bits:

Bit #0: 1 = Parity error occurred.
Bit #1: 1 = Frame error, a stop bit with the value of
    0, occurred.
Bit #2: 1 = Input buffer underflow occurred, too much
    data has arrived but it has not been read from the buffer in time.
Bit #3: 1 = Input buffer is empty, nothing to
    read.
Bit #4: 0 = Sender is Clear To Send; 1 = Sender is
    not ready to send data to receiver.
Bit #6: 0 = Receiver reports Data Set Ready; 1 =
    Receiver is not ready to receive data.
Bit #7: 1 = Carrier loss, a stop bit and a data byte
    both with the value of 0, detected.

$0298664RS232 byte size, number of data
  bits per data byte, default value for bit counters.
$0299-$029A665-666Default value of RS232
  input timer, based on baud rate. (Calculated automatically from default
  value of RS232 output timer, at memory address $0295-$0296.)
$029B667Offset of byte received in RS232
  input buffer.
$029C668Offset of current byte in RS232
  input buffer.
$029D669Offset of byte to send in RS232
  output buffer.
$029E670Offset of current byte in RS232
  output buffer.
$029F-$02A0671-672Temporary area for saving
  pointer to original interrupt service routine during datasette input output.
  Values:

$0000-$00FF: No datasette input/output took place yet
    or original pointer has been already restored.
$0100-$FFFF: Original pointer, datasette input/output
    currently in progress.

$02A1673Temporary area for saving original
  value of CIA#2 interrupt control register, at memory address $DD0D, during
  RS232 input/output.
$02A2674Temporary area for saving original
  value of CIA#1 timer #1 control register, at memory address $DC0E, during
  datasette input/output.
$02A3675Temporary area for saving original
  value of CIA#1 interrupt control register, at memory address $DC0D, during
  datasette input/output.
$02A4676Temporary area for saving original
  value of CIA#1 timer #1 control register, at memory address $DC0E, during
  datasette input/output.
$02A5677Number of line currently being
  scrolled during scrolling the screen.
$02A6678PAL/NTSC switch, for selecting
  RS232 baud rate from the proper table. Values:

$00: NTSC.
$01: PAL.

$02A7-$02FF679-767Unused (89 bytes).

$0300-$03FF, 768-1023
$0300-$0301768-769Execution address of warm
  reset, displaying optional BASIC error message and entering BASIC idle
  loop.
  Default: $E38B.
$0302-$0303770-771Execution address of
  BASIC idle loop.
  Default: $A483.
$0304-$0305772-773Execution address of
  BASIC line tokenizer routine.
  Default: $A57C.
$0306-$0307774-775Execution address of
  BASIC token decoder routine.
  Default: $A71A.
$0308-$0309776-777Execution address of
  BASIC instruction executor routine.
  Default: $A7E4.
$030A-$030B778-779Execution address of
  routine reading next item of BASIC expression.
  Default: $AE86.
$030C780Default value of register A for
  SYS.
  Value of register A after SYS.
$030D781Default value of register X for
  SYS.
  Value of register X after SYS.
$030E782Default value of register Y for
  SYS.
  Value of register Y after SYS.
$030F783Default value of status register
  for SYS.
  Value of status register after SYS.
$0310-$0312784-786JMP ABS machine
  instruction, jump to USR() function.
  $0311-$0312, 785-786: Execution address of USR() function.
$0313787Unused.
$0314-$0315788-789Execution address of
  interrupt service routine.
  Default: $EA31.
$0316-$0317790-791Execution address of BRK
  service routine.
  Default: $FE66.
$0318-$0319792-793Execution address of
  non-maskable interrupt service routine.
  Default: $FE47.
$031A-$031B794-795Execution address of
  OPEN, routine opening files.
  Default: $F34A.
$031C-$031D796-797Execution address of
  CLOSE, routine closing files.
  Default: $F291.
$031E-$031F798-799Execution address of
  CHKIN, routine defining file as default input.
  Default: $F20E.
$0320-$0321800-801Execution address of
  CHKOUT, routine defining file as default output.
  Default: $F250.
$0322-$0323802-803Execution address of
  CLRCHN, routine initializing input/output.
  Default: $F333.
$0324-$0325804-805Execution address of
  CHRIN, data input routine, except for keyboard and RS232 input.
  Default: $F157.
$0326-$0327806-807Execution address of
  CHROUT, general purpose data output routine.
  Default: $F1CA.
$0328-$0329808-809Execution address of
  STOP, routine checking the status of Stop key indicator, at memory address
  $0091.
  Default: $F6ED.
$032A-$032B810-811Execution address of
  GETIN, general purpose data input routine.
  Default: $F13E.
$032C-$032D812-813Execution address of
  CLALL, routine initializing input/output and clearing all file assignment
  tables.
  Default: $F32F.
$032E-$032F814-815Unused.
  Default: $FE66.
$0330-$0331816-817Execution address of
  LOAD, routine loading files.
  Default: $F4A5.
$0332-$0333818-819Execution address of
  SAVE, routine saving files.
  Default: $F5ED.
$0334-$033B820-827Unused (8 bytes).
$033C-$03FB828-1019Datasette buffer (192
  bytes).
$03FC-$03FF1020-1023Unused (4 bytes).

$0400-$07FF, 1024-2047Default screen
  memory
$0400-$07E71024-2023Default area of screen
  memory (1000 bytes).
$07E8-$07F72024-2039Unused (16 bytes).
$07F8-$07FF2040-2047Default area for sprite
  pointers (8 bytes).

$0800-$9FFF, 2048-40959BASIC area
$08002048Unused. (Must contain a value of 0
  so that the BASIC program can be RUN.)
$0801-$9FFF2049-40959Default BASIC area
  (38911 bytes).
$8000-$9FFF32768-40959Optional cartridge
  ROM (8192 bytes).
  $8000-$8001, 32768-32769: Execution address of cold reset.
  $8002-$8003, 32770-32771: Execution address of non-maskable interrupt
  service routine.
  $8004-$8008, 32772-32776: Cartridge signature. If contains the uppercase
  PETSCII string "CBM80" ($C3,$C2,$CD,$38,$30) then the routine vectors are
  accepted by the KERNAL.

$A000-$BFFF, 40960-49151BASIC ROM
$A000-$BFFF40960-49151BASIC ROM or RAM area
  (8192 bytes); depends on the value of bits #0-#2 of the processor port at
  memory address $0001:

%x00, %x01 or %x10: RAM area.
%x11: BASIC ROM.


$C000-$CFFF, 49152-53247Upper RAM
  area
$C000-$CFFF49152-53247Upper RAM area (4096
  bytes).

$D000-$DFFF, 53248-57343I/O Area
$D000-$DFFF53248-57343I/O Area (memory
  mapped chip registers), Character ROM or RAM area (4096 bytes); depends on
  the value of bits #0-#2 of the processor port at memory address $0001:

%x00: RAM area.
%0xx: Character ROM. (Except for the value %000, see
    above.)
%1xx: I/O Area. (Except for the value %100, see
    above.)


$D000-$DFFF, 53248-57343Character
  ROM
$D000-$DFFF53248-57343Character ROM, shape
  of characters (4096 bytes).
$D000-$D7FF53248-55295Shape of characters
  in uppercase/graphics character set (2048 bytes, 256 entries).
$D800-$DFFF55295-57343Shape of characters
  in lowercase/uppercase character set (2048 bytes, 256 entries).

$D000-$D3FF, 53248-54271VIC-II; video
  display
$D00053248Sprite #0 X-coordinate (only bits
  #0-#7).
$D00153249Sprite #0 Y-coordinate.
$D00253250Sprite #1 X-coordinate (only bits
  #0-#7).
$D00353251Sprite #1 Y-coordinate.
$D00453252Sprite #2 X-coordinate (only bits
  #0-#7).
$D00553253Sprite #2 Y-coordinate.
$D00653254Sprite #3 X-coordinate (only bits
  #0-#7).
$D00753255Sprite #3 Y-coordinate.
$D00853256Sprite #4 X-coordinate (only bits
  #0-#7).
$D00953257Sprite #4 Y-coordinate.
$D00A53258Sprite #5 X-coordinate (only bits
  #0-#7).
$D00B53259Sprite #5 Y-coordinate.
$D00C53260Sprite #6 X-coordinate (only bits
  #0-#7).
$D00D53261Sprite #6 Y-coordinate.
$D00E53262Sprite #7 X-coordinate (only bits
  #0-#7).
$D00F53263Sprite #7 Y-coordinate.
$D01053264Sprite #0-#7 X-coordinates (bit
  #8). Bits:

Bit #x: Sprite #x X-coordinate bit #8.

$D01153265Screen control register #1.
  Bits:

Bits #0-#2: Vertical raster scroll.
Bit #3: Screen height; 0 = 24 rows; 1 = 25 rows.
Bit #4: 0 = Screen off, complete screen is covered by
    border; 1 = Screen on, normal screen contents are visible.
Bit #5: 0 = Text mode; 1 = Bitmap mode.
Bit #6: 1 = Extended background mode on.
Bit #7: Read: Current raster line (bit #8).
    Write: Raster line to generate interrupt at (bit #8).

Default: $1B, %00011011.
$D01253266Read: Current raster line (bits
  #0-#7).
  Write: Raster line to generate interrupt at (bits #0-#7).
$D01353267Light pen X-coordinate (bits
  #1-#8).
  Read-only.
$D01453268Light pen Y-coordinate.
  Read-only.
$D01553269Sprite enable register. Bits:

Bit #x: 1 = Sprite #x is enabled, drawn onto the
    screen.

$D01653270Screen control register #2.
  Bits:

Bits #0-#2: Horizontal raster scroll.
Bit #3: Screen width; 0 = 38 columns; 1 = 40
    columns.
Bit #4: 1 = Multicolor mode on.

Default: $C8, %11001000.
$D01753271Sprite double height register.
  Bits:

Bit #x: 1 = Sprite #x is stretched to double
    height.

$D01853272Memory setup register. Bits:

Bits #1-#3: In text mode, pointer to character memory
    (bits #11-#13), relative to VIC bank, memory address $DD00. Values:

%000, 0: $0000-$07FF, 0-2047.
%001, 1: $0800-$0FFF, 2048-4095.
%010, 2: $1000-$17FF, 4096-6143.
%011, 3: $1800-$1FFF, 6144-8191.
%100, 4: $2000-$27FF, 8192-10239.
%101, 5: $2800-$2FFF, 10240-12287.
%110, 6: $3000-$37FF, 12288-14335.
%111, 7: $3800-$3FFF, 14336-16383.

Values %010 and %011 in VIC bank #0 and #2 select
    Character ROM instead.
    In bitmap mode, pointer to bitmap memory (bit #13), relative to VIC bank,
    memory address $DD00. Values:

%0xx, 0: $0000-$1FFF, 0-8191.
%1xx, 4: $2000-$3FFF, 8192-16383.

Bits #4-#7: Pointer to screen memory (bits #10-#13),
    relative to VIC bank, memory address $DD00. Values:

%0000, 0: $0000-$03FF, 0-1023.
%0001, 1: $0400-$07FF, 1024-2047.
%0010, 2: $0800-$0BFF, 2048-3071.
%0011, 3: $0C00-$0FFF, 3072-4095.
%0100, 4: $1000-$13FF, 4096-5119.
%0101, 5: $1400-$17FF, 5120-6143.
%0110, 6: $1800-$1BFF, 6144-7167.
%0111, 7: $1C00-$1FFF, 7168-8191.
%1000, 8: $2000-$23FF, 8192-9215.
%1001, 9: $2400-$27FF, 9216-10239.
%1010, 10: $2800-$2BFF, 10240-11263.
%1011, 11: $2C00-$2FFF, 11264-12287.
%1100, 12: $3000-$33FF, 12288-13311.
%1101, 13: $3400-$37FF, 13312-14335.
%1110, 14: $3800-$3BFF, 14336-15359.
%1111, 15: $3C00-$3FFF, 15360-16383.


$D01953273Interrupt status register. Read
  bits:

Bit #0: 1 = Current raster line is equal to the
    raster line to generate  interrupt at.
Bit #1: 1 = Sprite-background collision occurred.
Bit #2: 1 = Sprite-sprite collision occurred.
Bit #3: 1 = Light pen signal arrived.
Bit #7: 1 = An event (or more events), that may generate an
    interrupt, occurred and it has not been (not all of them have been) acknowledged
    yet.

Write bits:

Bit #0: 1 = Acknowledge raster interrupt.
Bit #1: 1 = Acknowledge sprite-background collision
    interrupt.
Bit #2: 1 = Acknowledge sprite-sprite collision
    interrupt.
Bit #3: 1 = Acknowledge light pen interrupt.

$D01A53274Interrupt control register.
  Bits:

Bit #0: 1 = Raster interrupt enabled.
Bit #1: 1 = Sprite-background collision interrupt
    enabled.
Bit #2: 1 = Sprite-sprite collision interrupt
    enabled.
Bit #3: 1 = Light pen interrupt enabled.

$D01B53275Sprite priority register.
  Bits:

Bit #x: 0 = Sprite #x is drawn in front of screen
    contents; 1 = Sprite #x is behind screen contents.

$D01C53276Sprite multicolor mode register.
  Bits:

Bit #x: 0 = Sprite #x is single color; 1 = Sprite #x
    is multicolor.

$D01D53277Sprite double width register.
  Bits:

Bit #x: 1 = Sprite #x is stretched to double
    width.

$D01E53278Sprite-sprite collision register.
  Read bits:

Bit #x: 1 = Sprite #x collided with another
    sprite.

Write: Enable further detection of sprite-sprite
  collisions.
$D01F53279Sprite-background collision
  register. Read bits:

Bit #x: 1 = Sprite #x collided with background.

Write: Enable further detection of sprite-background
  collisions.
$D02053280Border color (only bits
  #0-#3).
$D02153281Background color (only bits
  #0-#3).
$D02253282Extra background color #1 (only
  bits #0-#3).
$D02353283Extra background color #2 (only
  bits #0-#3).
$D02453284Extra background color #3 (only
  bits #0-#3).
$D02553285Sprite extra color #1 (only bits
  #0-#3).
$D02653286Sprite extra color #2 (only bits
  #0-#3).
$D02753287Sprite #0 color (only bits
  #0-#3).
$D02853288Sprite #1 color (only bits
  #0-#3).
$D02953289Sprite #2 color (only bits
  #0-#3).
$D02A53290Sprite #3 color (only bits
  #0-#3).
$D02B53291Sprite #4 color (only bits
  #0-#3).
$D02C53292Sprite #5 color (only bits
  #0-#3).
$D02D53293Sprite #6 color (only bits
  #0-#3).
$D02E53294Sprite #7 color (only bits
  #0-#3).
$D02F-$D03F53295-53311Unusable (17
  bytes).
$D040-$D3FF53312-54271VIC-II register
  images (repeated every $40, 64 bytes).

$D400-$D7FF, 54272-55295SID; audio
$D400-$D40154272-54273Voice #1
  frequency.
  Write-only.
$D402-$D40354274-54275Voice #1 pulse
  width.
  Write-only.
$D40454276Voice #1 control register.
  Bits:

Bit #0: 0 = Voice off, Release cycle; 1 = Voice on,
    Attack-Decay-Sustain cycle.
Bit #1: 1 = Synchronization enabled.
Bit #2: 1 = Ring modulation enabled.
Bit #3: 1 = Disable voice, reset noise generator.
Bit #4: 1 = Triangle waveform enabled.
Bit #5: 1 = Saw waveform enabled.
Bit #6: 1 = Rectangle waveform enabled.
Bit #7: 1 = Noise enabled.

Write-only.
$D40554277Voice #1 Attack and Decay length.
  Bits:

Bits #0-#3: Decay length. Values:

%0000, 0: 6 ms.
%0001, 1: 24 ms.
%0010, 2: 48 ms.
%0011, 3: 72 ms.
%0100, 4: 114 ms.
%0101, 5: 168 ms.
%0110, 6: 204 ms.
%0111, 7: 240 ms.
%1000, 8: 300 ms.
%1001, 9: 750 ms.
%1010, 10: 1.5 s.
%1011, 11: 2.4 s.
%1100, 12: 3 s.
%1101, 13: 9 s.
%1110, 14: 15 s.
%1111, 15: 24 s.

Bits #4-#7: Attack length. Values:

%0000, 0: 2 ms.
%0001, 1: 8 ms.
%0010, 2: 16 ms.
%0011, 3: 24 ms.
%0100, 4: 38 ms.
%0101, 5: 56 ms.
%0110, 6: 68 ms.
%0111, 7: 80 ms.
%1000, 8: 100 ms.
%1001, 9: 250 ms.
%1010, 10: 500 ms.
%1011, 11: 800 ms.
%1100, 12: 1 s.
%1101, 13: 3 s.
%1110, 14: 5 s.
%1111, 15: 8 s.


Write-only.
$D40654278Voice #1 Sustain volume and
  Release length. Bits:

Bits #0-#3: Release length. Values:

%0000, 0: 6 ms.
%0001, 1: 24 ms.
%0010, 2: 48 ms.
%0011, 3: 72 ms.
%0100, 4: 114 ms.
%0101, 5: 168 ms.
%0110, 6: 204 ms.
%0111, 7: 240 ms.
%1000, 8: 300 ms.
%1001, 9: 750 ms.
%1010, 10: 1.5 s.
%1011, 11: 2.4 s.
%1100, 12: 3 s.
%1101, 13: 9 s.
%1110, 14: 15 s.
%1111, 15: 24 s.

Bits #4-#7: Sustain volume.

Write-only.
$D407-$D40854279-54280Voice #2
  frequency.Write-only.
$D409-$D40A54281-54282Voice #2 pulse
  width.Write-only.
$D40B54283Voice #2 control register.
  Write-only.
$D40C54284Voice #2 Attack and Decay
  length.
  Write-only.
$D40D54285Voice #2 Sustain volume and
  Release length.
  Write-only.
$D40E-$D40F54286-54287Voice #3
  frequency.
  Write-only.
$D410-$D41154288-54289Voice #3 pulse
  width.
  Write-only.
$D41254290Voice #3 control register.
  Write-only.
$D41354291Voice #3 Attack and Decay
  length.
  Write-only.
$D41454292Voice #3 Sustain volume and
  Release length.
  Write-only.
$D41554293Filter cut off frequency (bits
  #0-#2).
  Write-only.
$D41654294Filter cut off frequency (bits
  #3-#10).
  Write-only.
$D41754295Filter control. Bits:

Bit #0: 1 = Voice #1 filtered.
Bit #1: 1 = Voice #2 filtered.
Bit #2: 1 = Voice #3 filtered.
Bit #3: 1 = External voice filtered.
Bits #4-#7: Filter resonance.

Write-only.
$D41854296Volume and filter modes.
  Bits:

Bits #0-#3: Volume.
Bit #4: 1 = Low pass filter enabled.
Bit #5: 1 = Band pass filter enabled.
Bit #6: 1 = High pass filter enabled.
Bit #7: 1 = Voice #3 disabled.

Write-only.
$D41954297X value of paddle selected at
  memory address $DC00. (Updates at every 512 system cycles.)
  Read-only.
$D41A54298Y value of paddle selected at
  memory address $DC00. (Updates at every 512 system cycles.)
  Read-only.
$D41B54299Voice #3 waveform output.
  Read-only.
$D41C54300Voice #3 ADSR output.
  Read-only.
$D41D-$D41F54301-54303Unusable (3
  bytes).
$D420-$D7FF54304-55295SID register images
  (repeated every $20, 32 bytes).

$D800-$DBFF, 55296-56319Color RAM
$D800-$DBE755296-56295Color RAM (1000
  bytes, only bits #0-#3).
$DBE8-$DBFF56296-56319Unused (24 bytes,
  only bits #0-#3).

$DC00-$DCFF, 56320-56575CIA#1; inputs
  (keyboard, joystick, mouse), datasette, IRQ control
$DC0056320Port A, keyboard matrix columns
  and joystick #2. Read bits:

Bit #0: 0 = Port 2 joystick up pressed.
Bit #1: 0 = Port 2 joystick down pressed.
Bit #2: 0 = Port 2 joystick left pressed.
Bit #3: 0 = Port 2 joystick right pressed.
Bit #4: 0 = Port 2 joystick fire pressed.

Write bits:

Bit #x: 0 = Select keyboard matrix column #x.
Bits #6-#7: Paddle selection; %01 = Paddle #1; %10 =
    Paddle #2.

$DC0156321Port B, keyboard matrix rows and
  joystick #1. Bits:

Bit #x: 0 = A key is currently being pressed in
    keyboard matrix row #x, in the column selected at memory address
    $DC00.
Bit #0: 0 = Port 1 joystick up pressed.
Bit #1: 0 = Port 1 joystick down pressed.
Bit #2: 0 = Port 1 joystick left pressed.
Bit #3: 0 = Port 1 joystick right pressed.
Bit #4: 0 = Port 1 joystick fire pressed.

$DC0256322Port A data direction
  register.

Bit #x: 0 = Bit #x in port A can only be read; 1 =
    Bit #x in port A can be read and written.

$DC0356323Port B data direction
  register.

Bit #x: 0 = Bit #x in port B can only be read; 1 =
    Bit #x in port B can be read and written.

$DC04-$DC0556324-56325Timer A. Read:
  Current timer value.
  Write: Set timer start value.
$DC06-$DC0756326-56327Timer B. Read:
  Current timer value.
  Write: Set timer start value.
$DC0856328Time of Day, tenth seconds (in
  BCD). Values: $00-$09. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0956329Time of Day, seconds (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0A56330Time of Day, minutes (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DC0B56331Time of Day, hours (in BCD). Read
  bits:

Bits #0-#5: Hours.
Bit #7: 0 = AM; 1 = PM.

Write: Set TOD or alarm time.
$DC0C56332Serial shift register. (Bits are
  read and written upon every positive edge of the CNT pin.)
$DC0D56333Interrupt control and status
  register. Read bits:

Bit #0: 1 = Timer A underflow occurred.
Bit #1: 1 = Timer B underflow occurred.
Bit #2: 1 = TOD is equal to alarm time.
Bit #3: 1 = A complete byte has been received into or
    sent from serial shift register.
Bit #4: Signal level on FLAG pin, datasette
    input.
Bit #7: An interrupt has been generated.

Write bits:

Bit #0: 1 = Enable interrupts generated by timer A
    underflow.
Bit #1: 1 = Enable interrupts generated by timer B
    underflow.
Bit #2: 1 = Enable TOD alarm interrupt.
Bit #3: 1 = Enable interrupts generated by a byte
    having been  received/sent via serial shift register.
Bit #4: 1 = Enable interrupts generated by positive
    edge on FLAG pin.
Bit #7: Fill bit; bits #0-#6, that are set to 1, get
    their values from this bit; bits #0-#6, that are set to 0, are left
    unchanged.

$DC0E56334Timer A control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #6.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #6; 1 = upon timer underflow, generate a positive edge on port B bit #6
    for 1 system cycle.
  Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bit #5: 0 = Timer counts system cycles; 1 = Timer
    counts positive edges on CNT pin.
Bit #6: Serial shift register direction; 0 = Input,
    read; 1 = Output, write.
Bit #7: TOD speed; 0 = 60 Hz; 1 = 50 Hz.

$DC0F56335Timer B control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #7.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #7; 1 = upon timer underflow, generate a positive edge on port B bit #7
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bits #5-#6: %00 = Timer counts system cycles; %01 =
    Timer counts positive edges on CNT pin; %10 = Timer counts underflows of
    timer A; %11 = Timer counts underflows of timer A occurring along with a
    positive edge on CNT pin.
Bit #7: 0 = Writing into TOD registers sets TOD; 1 =
    Writing into TOD registers sets alarm time.

$DC10-$DCFF56336-56575CIA#1 register images
  (repeated every $10, 16 bytes).

$DD00-$DDFF, 56576-56831CIA#2; serial
  bus, RS232, NMI control
$DD0056576Port A, serial bus access.
  Bits:

Bits #0-#1: VIC bank. Values:

%00, 0: Bank #3, $C000-$FFFF, 49152-65535.
%01, 1: Bank #2, $8000-$BFFF, 32768-49151.
%10, 2: Bank #1, $4000-$7FFF, 16384-32767.
%11, 3: Bank #0, $0000-$3FFF, 0-16383.

Bit #2: RS232 TXD line, output bit.
Bit #3: Serial bus ATN OUT; 0 = High; 1 = Low.
Bit #4: Serial bus CLOCK OUT; 0 = High; 1 = Low.
Bit #5: Serial bus DATA OUT; 0 = High; 1 = Low.
Bit #6: Serial bus CLOCK IN; 0 = Low; 1 = High.
Bit #7: Serial bus DATA IN; 0 = Low; 1 = High.

$DD0156577Port B, RS232 access. Read
  bits:

Bit #0: RS232 RXD line, input bit.
Bit #3: RS232 RI line.
Bit #4: RS232 DCD line.
Bit #5: User port H pin.
Bit #6: RS232 CTS line; 1 = Sender is ready to
    send.
Bit #7: RS232 DSR line; 1 = Receiver is ready to
    receive.

Write bits:

Bit #1: RS232 RTS line. 1 = Sender is ready to
    send.
Bit #2: RS232 DTR line. 1 = Receiver is ready to
    receive.
Bit #3: RS232 RI line.
Bit #4: RS232 DCD line.
Bit #5: User port H pin.

$DD0256578Port A data direction
  register.

Bit #x: 0 = Bit #x in port A can only be read; 1 =
    Bit #x in port A can be read and written.

$DD0356579Port B data direction
  register.

Bit #x: 0 = Bit #x in port B can only be read; 1 =
    Bit #x in port B can be read and written.

$DD04-$DD0556580-56581Timer A. Read:
  Current timer value.
  Write: Set timer start value.
$DD06-$DD0756582-56583Timer B. Read:
  Current timer value.
  Write: Set timer start value.
$DD0856584Time of Day, tenth seconds (in
  BCD). Values: $00-$09. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0956585Time of Day, seconds (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0A56586Time of Day, minutes (in BCD).
  Values: $00-$59. Read: Current TOD value.
  Write: Set TOD or alarm time.
$DD0B56587Time of Day, hours (in BCD). Read
  bits:

Bits #0-#5: Hours.
Bit #7: 0 = AM; 1 = PM.

Write: Set TOD or alarm time.
$DD0C56588Serial shift register. (Bits are
  read and written upon every positive edge of the CNT pin.)
$DD0D56589Interrupt control and status
  register. Read bits:

Bit #0: 1 = Timer A underflow occurred.
Bit #1: 1 = Timer B underflow occurred.
Bit #2: 1 = TOD is equal to alarm time.
Bit #3: 1 = A complete byte has been received into or
    sent from serial shift register.
Bit #4: Signal level on FLAG pin.
Bit #7: A non-maskable interrupt has been
    generated.

Write bits:

Bit #0: 1 = Enable non-maskable interrupts generated
    by timer A underflow.
Bit #1: 1 = Enable non-maskable interrupts generated
    by timer B underflow.
Bit #2: 1 = Enable TOD alarm non-maskable
    interrupt.
Bit #3: 1 = Enable non-maskable interrupts generated
    by a byte having been received/sent via serial shift register.
Bit #4: 1 = Enable non-maskable interrupts generated
    by positive edge on FLAG pin.
Bit #7: Fill bit; bits #0-#6, that are set to 1, get
    their values from this bit; bits #0-#6, that are set to 0, are left
    unchanged.

$DD0E56590Timer A control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #6.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #6; 1 = upon timer underflow, generate a positive edge on port B bit #6
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bit #5: 0 = Timer counts system cycles; 1 = Timer
    counts positive edges on CNT pin.
Bit #6: Serial shift register direction; 0 = Input,
    read; 1 = Output, write.
Bit #7: TOD speed; 0 = 60 Hz; 1 = 50 Hz.

$DD0F56591Timer B control register.
  Bits:

Bit #0: 0 = Stop timer; 1 = Start timer.
Bit #1: 1 = Indicate timer underflow on port B bit
    #7.
Bit #2: 0 = Upon timer underflow, invert port B bit
    #7; 1 = upon timer underflow, generate a positive edge on port B bit #7
    for 1 system cycle.
Bit #3: 0 = Timer restarts upon underflow; 1 = Timer
    stops upon underflow.
Bit #4: 1 = Load start value into timer.
Bits #5-#6: %00 = Timer counts system cycles; %01 =
    Timer counts positive edges on CNT pin; %10 = Timer counts underflows of
    timer A; %11 = Timer counts underflows of timer A occurring along with a
    positive edge on CNT pin.
Bit #7: 0 = Writing into TOD registers sets TOD; 1 =
    Writing into TOD registers sets alarm time.

$DD10-$DDFF56592-56831CIA#2 register images
  (repeated every $10, 16 bytes).

$DE00-$DEFF, 56832-57087I/O Area
  #1
$DE00-$DEFF56832-57087I/O Area #1, memory
  mapped registers or machine code routines of optional external devices (256
  bytes). Layout and contents depend on the actual device.

$DF00-$DFFF, 57088-57343I/O Area
  #2
$DF00-$DFFF57088-57343I/O Area #2, memory
  mapped registers or machine code routines of optional external devices (256
  bytes). Layout and contents depend on the actual device.


$E000-$FFFF, 57344-65535KERNAL ROM
$E000-$FFFF57344-65535KERNAL ROM or RAM
  area (8192 bytes); depends on the value of bits #0-#2 of the processor port
  at memory address $0001:

%x0x: RAM area.
%x1x: KERNAL ROM.


$FFFA-$FFFF, 65530-65535Hardware
  vectors
$FFFA-$FFFB65530-65531Execution address of
  non-maskable interrupt service routine.
  Default: $FE43.
$FFFC-$FFFD65532-65533Execution address of
  cold reset.
  Default: $FCE2.
$FFFE-$FFFF65534-65535Execution address of
  interrupt service routine.
  Default: $FF48. |
| --- | --- |

