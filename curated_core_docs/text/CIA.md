# CIA
Source: https://www.c64-wiki.com/wiki/CIA

Production year/date of this CIA: 1985 - calendar week 13

## Contents


- [1 Description](#Description)
- [2 Details of the CIA 6526](#Details_of_the_CIA_6526)
- [3 Memory addresses of the CIAs](#Memory_addresses_of_the_CIAs)

[3.1 CIA 1](#CIA_1)
[3.2 CIA 2](#CIA_2)
[3.3 Pinout](#Pinout)
- [4 Failure Symptoms](#Failure_Symptoms)
- [5 Links](#Links)



## Description[edit | edit source]

The CIA (Complex Interface Adapter) is an interface chip used in the [Commodore](/wiki/Commodore) [homecomputer](/wiki/Homecomputer). It controls most of the I/O processes and contains as well the internal timer (clock). The CIA was developed from the Semiconductor manufacturer [MOS Technology](/wiki/MOS_Technology), which was taken over in 1976 by Commodore. Inside the [C64](/wiki/C64) there are two CIA 6526 chips used; later C64-versions may also use the 6526A or the 8521.


## Details of the CIA 6526[edit | edit source]

- 16 single programmable In- and Output lines
The lines are lead through open collector with internal pullups.
In the C64 some of these lines are used to monitor/control the I/O devices (keyboard, joystick, iec, etc.), some are connected with the [VIC](/wiki/VIC) to define which area of memory it can address, others are for free disposition and are available at the [userport](/wiki/Userport).
- 8- or 16-Bit data transport (reading or writing) with handshaking.
- 2 independent 16-bit interval timers
each timer consists of a 16 bit-latch (start value) and the actual 16 bit-timer
the latch can be set directly, the timer can only be read indirectly via the latch.
- 24-h-timeclock (AM/PM) with programmable alarm
- 8-bit shift register for serial In- and Output.
- 2 TTL-inputs
- CMOS-compatible
- Pulsing: 1 MHz (6526) or 2 MHz (6526A)

## Memory addresses of the CIAs[edit | edit source]

The following memory addresses are used from the two CIA-Chips in the C64:


### CIA 1[edit | edit source]



Paddles, 

| AddressHex | AddressDec | Register | Function | Remark |
| --- | --- | --- | --- | --- |
| Address area: $DC00-$DCFF, 56320-56575 Tasks: Keyboard, Joystick, Paddles, Datasette, IRQ control |
| $DC00 | 56320 | 0PRA | Data Port A | Monitoring/control of the 8 data lines of Port A. The lines are used for multiple purposes: Read/Write: Bit 0..7 keyboard matrix columns Read: Joystick Port 2: Bit 0..3 Direction (Up/Down/Left/Right), Bit 4 Fire button. 0 = activated. Read: Lightpen: Bit 4 (as fire button), connected also with "/LP" (Pin 9) of the VIC Read: Paddles: Bit 2..3 Fire buttons, Bit 6..7 Switch control port 1 (%01=Paddles A) or 2 (%10=Paddles B) |
| $DC01 | 56321 | 1PRB | Data Port B | Monitoring/control of the 8 data lines of Port B. The lines are used for multiple purposes: Read/Write: Bit 0..7 keyboard matrix rows Read: Joystick Port 1: Bit 0..3 Direction (Up/Down/Left/Right), Bit 4 Fire button. 0 = activated. Read: Bit 6: Timer A: Toggle/Impulse output (see register 14 bit 2) Read: Bit 7: Timer B: Toggle/Impulse output (see register 15 bit 2) |
| $DC02 | 56322 | 2DDRA | Data DirectionPort A | Bit X: 0=Input (read only), 1=Output (read and write) |
| $DC03 | 56323 | 3DDRB | Data DirectionPort B | Bit X: 0=Input (read only), 1=Output (read and write) |
| $DC04 | 56324 | 4TA LO | Timer ALow Byte | Read: actual value Timer A (Low Byte) Writing: Set latch of Timer A (Low Byte) |
| $DC05 | 56325 | 5TA HI | Timer AHigh Byte | Read: actual value Timer A (High Byte) Writing: Set latch of timer A (High Byte) - if the timer is stopped, the high-byte will automatically be re-set as well |
| $DC06 | 56326 | 6TB LO | Timer BLow Byte | Read: actual value Timer B (Low Byte) Writing: Set latch of Timer B (Low Byte) |
| $DC07 | 56327 | 7TB HI | Timer BHigh Byte | Read: actual value Timer B (High Byte) Writing: Set latch of timer B (High Byte) - if the timer is stopped, the high-byte will automatically be re-set as well |
| $DC08 | 56328 | 8TOD 10THS | Real Time Clock1/10s | Read: Bit 0..3: Tenth seconds in BCD-format ($0-$9) Bit 4..7: always 0 Writing: Bit 0..3: if CRB-Bit7=0: Set the tenth seconds in BCD-format Bit 0..3: if CRB-Bit7=1: Set the tenth seconds of the alarm time in BCD-format |
| $DC09 | 56329 | 9TOD SEC | Real Time ClockSeconds | Bit 0..3: Single seconds in BCD-format ($0-$9) Bit 4..6: Ten seconds in BCD-format ($0-$5) Bit 7: always 0 |
| $DC0A | 56330 | 10TOD MIN | Real Time ClockMinutes | Bit 0..3: Single minutes in BCD-format( $0-$9) Bit 4..6: Ten minutes in BCD-format ($0-$5) Bit 7: always 0 |
| $DC0B | 56331 | 11TOD HR | Real Time ClockHours | Bit 0..3: Single hours in BCD-format ($0-$9) Bit 4..6: Ten hours in BCD-format ($0-$5) Bit 7: Differentiation AM/PM, 0=AM, 1=PM Writing into this register stops TOD, until register 8 (TOD 10THS) will be read. |
| $DC0C | 56332 | 12SDR | Serialshift register | The byte within this register will be shifted bitwise to or from the SP-pin with every positive slope at the CNT-pin. |
| $DC0D | 56333 | 13ICR | Interrupt Controland status | CIA1 is connected to the IRQ-Line. Read: (Bit0..4 = INT DATA, Origin of the interrupt) Bit 0: 1 = Underflow Timer A Bit 1: 1 = Underflow Timer B Bit 2: 1 = Time of day and alarm time is equal Bit 3: 1 = SDR full or empty, so full byte was transferred, depending of operating mode serial bus Bit 4: 1 = IRQ Signal occured at FLAG-pin (cassette port Data input, serial bus SRQ IN) Bit 5..6: always 0 Bit 7: 1 = IRQ An interrupt occured, so at least one bit of INT MASK and INT DATA is set in both registers. Flags will be cleared after reading the register! Write: (Bit 0..4 = INT MASK, Interrupt mask) Bit 0: 1 = Interrupt release through timer A underflow Bit 1: 1 = Interrupt release through timer B underflow Bit 2: 1 = Interrupt release if clock=alarmtime Bit 3: 1 = Interrupt release if a complete byte has been received/sent. Bit 4: 1 = Interrupt release if a positive slope occurs at the FLAG-Pin. Bit 5..6: unused Bit 7: Source bit. 0 = set bits 0..4 are clearing the according mask bit. 1 = set bits 0..4 are setting the according mask bit. If all bits 0..4 are cleared, there will be no change to the mask. |
| $DC0E | 56334 | 14CRA | Control Timer A | Bit 0: 0 = Stop timer; 1 = Start timer Bit 1: 1 = Indicates a timer underflow at port B in bit 6. Bit 2: 0 = Through a timer overflow, bit 6 of port B will get high for one cycle , 1 = Through a timer underflow, bit 6 of port B will be inverted Bit 3: 0 = Timer-restart after underflow (latch will be reloaded), 1 = Timer stops after underflow. Bit 4: 1 = Load latch into the timer once. Bit 5: 0 = Timer counts system cycles, 1 = Timer counts positive slope at CNT-pin Bit 6: Direction of the serial shift register, 0 = SP-pin is input (read), 1 = SP-pin is output (write) Bit 7: Real Time Clock, 0 = 60 Hz, 1 = 50 Hz |
| $DC0F | 56335 | 15CRB | Control Timer B | Bit 0: 0 = Stop timer; 1 = Start timer Bit 1: 1 = Indicates a timer underflow at port B in bit 7. Bit 2: 0 = Through a timer overflow, bit 7 of port B will get high for one cycle , 1 = Through a timer underflow, bit 7 of port B will be inverted Bit 3: 0 = Timer-restart after underflow (latch will be reloaded), 1 = Timer stops after underflow. Bit 4: 1 = Load latch into the timer once. Bit 5..6:  %00 = Timer counts System cycle %01 = Timer counts positive slope on CNT-pin %10 = Timer counts underflow of timer A %11 = Timer counts underflow of timer A if the CNT-pin is high Bit 7: 0 = Writing into the TOD register sets the clock time, 1 = Writing into the TOD register sets the alarm time. |
| $DC10-$DCFF | 56336-56575 | - | - | The CIA 1 register are mirrored each 16 Bytes |


### CIA 2[edit | edit source]

The second CIA-chip is identical to the first. Therefore in the following table are only entries which are specific to the usage in the C64.


| AddressHex | AddressDec | Register | Function | Remark |
| --- | --- | --- | --- | --- |
| Address range: $DD00-$DDFF, 56576-56831 Tasks: Serial bus, RS-232, VIC memory, NMI control |
| $DD00 | 56576 | 0PRA | Data Port A | Bit 0..1: Select the position of the VIC-memory %00, 0: Bank 3: $C000-$FFFF, 49152-65535 %01, 1: Bank 2: $8000-$BFFF, 32768-49151 %10, 2: Bank 1: $4000-$7FFF, 16384-32767 %11, 3: Bank 0: $0000-$3FFF, 0-16383 (standard) Bit 2: RS-232: TXD Output, userport: Data PA 2 (pin M) Bit 3..5: serial bus Output (0=High/Inactive, 1=Low/Active)  Bit 3: ATN OUT Bit 4: CLOCK OUT Bit 5: DATA OUT Bit 6..7: serial bus Input (0=Low/Active, 1=High/Inactive)  Bit 6: CLOCK IN Bit 7: DATA IN |
| $DD01 | 56577 | 1PRB | Data Port B | Bit 0..7: userport Data PB 0-7 (Pins C,D,E,F,H,J,K,L) The KERNAL offers several RS232-Routines, which use the pins as followed: Bit 0, 3..7: RS-232: reading  Bit 0: RXD Bit 3: RI Bit 4: DCD Bit 5: User port pin J Bit 6: CTS Bit 7: DSR Bit 1..5: RS-232: writing  Bit 1: RTS Bit 2: DTR Bit 3: RI Bit 4: DCD Bit 5: User port pin J |
| $DD02 | 56578 | 2DDRA | Data directionPort A | see CIA 1 |
| $DD03 | 56579 | 3DDRB | Data directionPort B | see CIA 1 |
| $DD04 | 56580 | 4TA LO | Timer ALow Byte | see CIA 1 |
| $DD05 | 56581 | 5TA HI | Timer AHigh Byte | see CIA 1 |
| $DD06 | 56582 | 6TB LO | Timer BLow Byte | see CIA 1 |
| $DD07 | 56583 | 7TB HI | Timer BHigh Byte | see CIA 1 |
| $DD08 | 56584 | 8TOD 10THS | Real Time Clock1/10s | see CIA 1 |
| $DD09 | 56585 | 9TOD SEC | Real Time ClockSeconds | see CIA 1 |
| $DD0A | 56586 | 10TOD MIN | Real Time ClockMinutes | see CIA 1 |
| $DD0B | 56587 | 11TOD HR | Real Time ClockHours | see CIA 1 |
| $DD0C | 56588 | 12SDR | Serialshift register | see CIA 1 |
| $DD0D | 56589 | 13ICR | Interrupt controland status | CIA2 is connected to the NMI-Line. Bit 4: 1 = NMI Signal occured at FLAG-pin (RS-232 data received) Bit 7: 1 = NMI An interrupt occured, so at least one bit of INT MASK and INT DATA is set in both registers. |
| $DD0E | 56590 | 14CRA | Control Timer A | see CIA 1 |
| $DD0F | 56591 | 15CRB | Control Timer B | see CIA 1 |


### Pinout[edit | edit source]


|  | Pin | Description |
| --- | --- | --- |
|  | Vss | Ground connection 0V |
| PA0 - PA7 | I/O-Port A Bit0-7 Bidirectional parallel port |
| PB0 - PB7 | I/O-Port B Bit0-7 Bidirectional parallel port |
| /PC | Port Control - Handshake output, Low pulse after read/write on port B. |
| TOD | Time Of Day clock input, either 50Hz or 60Hz input. |
| Vcc | 5VDC input |
| /IRQ | Interrupt Request, output to CPU's IRQ input |
| R/W | High-level = Read (Move data from CIA), Low-level = Write (Move data to CIA) |
| /CS | Chip Select - low level means active CIA. |
| /FLAG | Negative edge IRQ input, can be used as handshake for either parallel port. |
| /phi2 | Processor Φ2 clock, data transfers occur only on high signal level. |
| DB0 - DB7 | Bidirectional data bus Bits 0 - 7 |
| /RES | Reset input, low signal initiates CIA. |
| RS0 - RS3 | Register Select -  Used to interface internal registers with bidirectional ports. |
| SP | Serial Port - bidirectional, internal shift register converts CPU parallel data into serial data and vice-versa. |
| CNT | Count - Internal timers can count pulses to this input. Can be used for frequency dependent operations. |


## Failure Symptoms[edit | edit source]

CIA 1

- Startup screen normal, but no cursor.
- No keyboard or control port access but cartridge works.
- Partial failure: some keys or joystick positions don't work, one character appears ahead of startup cursor or random characters appear at startup. Blank screen if chip is shorted (remove to check) and chip may get hot to the touch.
CIA 2

- Startup screen normal.
- No serial or user port access.
- "File not found" error when drive accessed.
- Cartridge works.
- Characters may show as blocks on startup screen.

## Links[edit | edit source]


|  | Wikipedia: MOS_Technology_CIA |
| --- | --- |
|  | Wikipedia: MOS_Technology_CIA |

- [MOS 6526 CIA data sheet (PDF Format)](http://www.6502.org/documents/datasheets/mos/mos_6526_cia.pdf)
- [Mapping the C64](http://www.unusedino.de/ec64/technical/project64/mapping_c64.html) - e.g. details about programming the CIA
- [The CIA 6526 in the Commodore Computer Online Museum](http://cbmmuseum.kuto.de/zusatz_6526_cia.html)

[Hardware internals of the C64](/wiki/Hardware_internals_of_the_C64) · [Hardware portal](/wiki/Portal:Hardware)
Components of the C64: [CPU](/wiki/MOS_6510) · [VIC](/wiki/VIC) · [SID](/wiki/SID) · CIA · [PLA](/wiki/PLA_(C64_chip)) · [RAM](/wiki/RAM) · [ROM](/wiki/ROM) · [Color RAM](/wiki/Color_RAM)

Interfaces of the C64: [Control Port](/wiki/Control_Port) · [Expansion Port](/wiki/Expansion_Port) · [Userport](/wiki/Userport) · [Cassette Port](/wiki/Cassette_Port) · [Power Supply Connector](/wiki/Power_Supply_Connector) · [A/V Jack](/wiki/A/V_Jack) · [RF Jack](/wiki/RF_Jack) · [Serial Port](/wiki/Serial_Port)




Retrieved from "[https://www.c64-wiki.com/index.php?title=CIA&oldid=43997](https://www.c64-wiki.com/index.php?title=CIA&oldid=43997)"