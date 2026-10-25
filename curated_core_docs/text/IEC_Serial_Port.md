# Serial Port
Source: https://www.c64-wiki.com/wiki/Serial_Port

Serial interface of a C64
The serial bus (IEC or CBM bus) is the standard interface for connecting external devices as [disk drives](/wiki/disk_drive) or [printers](/wiki/Printer). Technically, it is a commodore-specific variant of the parallel [IEEE-488/IEC-625](/wiki/IEEE-488)-Bus, therefore it is often called IEC bus or CBM bus. This interface variant is not compatible with [RS232](/wiki/RS232), which is the standard for the serial interface for IBM-compatible PCs.
Since serial ports are usually used only for the connection of two devices (e.g. RS232) the IEC bus is a serial [bus](/index.php?title=Bus&action=edit&redlink=1). More than only one device can be connected, therefore most of the peripheral devices have loop-through connectors. Theoretically there are up to 31 devices possible ([device numbers](/wiki/Device_number) 0 to 30, 31 is reserved for UNTALK/UNLISTEN).
However, the operating system of the C64 can use only the device numbers 4 to 30, because 0-3 are already used internally. Practically the upper limit is at around 8 devices. The reason for this is, that the [chips](/wiki/Chip) (inverting driver 7406) in the C64 can handle a maximum load current of 40 mA. And any device, which is connected to the serial bus draws 5mA. However, nothing prevents a single physical device from responding to more than one address.
The selection, with which device data will be exchanged, will be done with the device number. This number between 4 and 30 must be selected on the device and must be unique. Standard for printers is 4, for the first floppy drive 8.
The timing of the bus is specified quite tightly. So if a [PC](/wiki/PC) is connected with an appropriate cable (see [X1541](/wiki/X1541)) to a floppy drive and is transmitting data - or vice versa (i.e. the PC emulates a floppy for a C64) everything may work fine. But if you use a multitasking OS (Windows, Linux,...) it will not work without using a complex circuit with own intelligence because of the maximum allowed latency of only a few micro seconds (especially when using a [fast loader](/wiki/Fast_loader)). For this reason software as [64HDD](/index.php?title=64HDD&action=edit&redlink=1) and [1541EMU](/wiki/1541EMU) are running under DOS only.
In standard operation ([LOAD](/wiki/LOAD), unmodified [KERNAL](/wiki/KERNAL)-routines) the serial bus is capable to transmit 400 byte/second using a [1541](/wiki/1541) and approx. 650 bytes/second using an [SD2IEC](/wiki/SD2IEC). With [JiffyDOS](/wiki/JiffyDOS) and a 1541 approx. 2.4 kbyte/second are transmitted while JiffyDOS and a SD2IEC achieve 8.6 kbyte/second. The theoretic maximum is at about 20-25 kbyte/second[[1]](#cite_note-1).



## Contents


- [1 Pin assignment](#Pin_assignment)
- [2 Signal description](#Signal_description)
- [3 Expansions](#Expansions)
- [4 Links](#Links)

[4.1 Footnotes](#Footnotes)



## Pin assignment[edit | edit source]

The serial interface is a 6-pin [DIN connector](http://en.wikipedia.org/wiki/DIN_connector) (DIN 45322).

Pin assignment



| Pin | Description | Signal direction | Remark |
| --- | --- | --- | --- |
| 1 | SERIAL SRQ | IN | Serial Service Request In, at the C128 "Fast Serial Clock" |
| 2 | GND | - | Ground, signal ground (0V) |
| 3 | SERIAL ATN | OUT | Attention, for the selection of a device at beginning/end of a transmission |
| 4 | SERIAL CLK | IN/OUT | Clock (for data transmission) |
| 5 | SERIAL DATA | IN/OUT | Data |
| 6 | SERIAL RESET | OUT(/IN) | Reset, in older VIC-20 unused |


## Signal description[edit | edit source]

- Attention: a lot of fast loaders use these signals differently! The here described pin assignment is valid only for the standard usage of the bus.
- All signals (except from GND) are LOW-active. If they are inactive they are on a voltage level of about 5V (HIGH).
- Electrically, all signals are [open collector](http://en.wikipedia.org/wiki/Open_collector), to keep the bus behaviour.

SRQ: Serial Service Request in
Any device can draw this signal to LOW, to request data exchange with the computer. The C64 does not use this signal, but it is connected with the read line of the [cassette port](/wiki/Cassette_port) (although this can only detect signal edges, but not signal levels).
The [C128](/wiki/C128) uses this line as "[Fast Serial Clock](/wiki/Fast_serial_bus_protocol)" for the [1571](/wiki/1571)/[1581](/wiki/1581) disk drive.
ATN: Serial Attention out
If this signal is LOW and a [byte](/wiki/Byte) is sent, all connected devices on the bus are interpreting this as a command. As soon as the C64 draws ATN to LOW, all other devices are waiting for the transmission of the address (device number). The addressed device has to answer within a defined time frame, else the C64 assumes, that this device is not present and gives an error message. After the [device number](/wiki/Device_number) the [secondary address](/index.php?title=Secondary_Address&action=edit&redlink=1) will be sent, ATN stays LOW. Before the first "normal" byte it will go back to HIGH state.
CLK: Serial Clock in/out
This signal is the clock of the transmitted data. The clock will be generated by the device which sends the data. At the rising edge of CLK, the receiver takes over the actual DATA bit.
DATA: Serial Data in/out
The data will be transferred via this line sequentially [bit](/wiki/Bit) by bit. A byte transmission starts with bit 0 [LSB](/wiki/LSB) and ends with bit 7 [MSB](/wiki/MSB) for the standard protocol, or the reverse for the [fast protocol](/wiki/Fast_serial_bus_protocol).
RESET: Serial Reset
This generates a [reset](/wiki/Reset) at the connected devices. Early models of the C64 allowed to use it as input to reset the computer (Reset-button), at later models this is not possible any more. Therefore a reset-button switch should be connected to the [user port](/wiki/Userport).


## Expansions[edit | edit source]

- It is possible to increase the number of physically connected devices on the bus. To do this in some of the devices the 1kΩ resistors must be removed. Attention: If they will be removed in all devices, the bus will not work any more.
- [Power over Serial](/index.php?title=Power_over_Serial&action=edit&redlink=1) Voltage for low consumption devices.

## Links[edit | edit source]


|  | Wikipedia: CBM-Bus |
| --- | --- |
|  | Wikipedia: CBM-Bus |

- [Book Die Floppy 1541](http://www.trikaliotis.net/Book#vic1541) including notes on the serial bus
- [IEC disected](http://www.zimmers.net/anonftp/pub/cbm/programming/serial-bus.pdf), in-depth details to the IEC-protocol, 2008, compiled by J. Derogee
- [HOW THE VIC/64 SERIAL BUS WORKS](http://groups.google.com/group/comp.sys.cbm/msg/6af215495544add2), (short) article from the Compute! July 1983 by Jim Butterfield
- [C64-Netzwerk mit dem seriellen Bus](http://www.webnet.at/c64/serielles_netzwerk.htm), Networking via the serial bus

### Footnotes[edit | edit source]


- [↑](#cite_ref-1) [What is sd2iec's speed?](http://www.c64-wiki.com/index.php/sd2iec_%28firmware%29#What_is_sd2iec.27s_speed.3F)


[Control Port](/wiki/Control_Port) · [Expansion Port](/wiki/Expansion_Port) · [User Port](/wiki/User_Port) · [Cassette Port](/wiki/Cassette_Port) · [Power Supply Connector](/wiki/Power_Supply_Connector)
[A/V Jack](/wiki/A/V_Jack) · [RF Jack](/wiki/RF_Jack) · Serial Port


[RS-232](/wiki/RS-232) · [IEEE-488](/wiki/IEEE-488) · [Centronics Interface](/wiki/Centronics_Interface) · [SCSI](/index.php?title=SCSI&action=edit&redlink=1) · [Ethernet](/index.php?title=Ethernet&action=edit&redlink=1) · [WLAN](/wiki/WLAN) · [Clockport](/index.php?title=Clockport&action=edit&redlink=1)




Retrieved from "[https://www.c64-wiki.com/index.php?title=Serial_Port&oldid=43025](https://www.c64-wiki.com/index.php?title=Serial_Port&oldid=43025)"