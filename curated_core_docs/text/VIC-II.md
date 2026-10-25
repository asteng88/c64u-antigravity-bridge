# VIC
Source: https://www.c64-wiki.com/wiki/VIC

VIC is an acronym for Video Interface Chip and is the collective name for a number of microchips. The VIC controls the graphics routines ([chars](/wiki/Char), [sprites](/wiki/Sprite), [graphic modes](/wiki/Graphic_mode)) for many computers manufactured by [Commodore](/wiki/Commodore). The microchips were produced by the semiconductor manufacturer [MOS Technology](/wiki/MOS_Technology), which [Commodore](/wiki/Commodore) took over in 1976.


## Contents


- [1 VIC-I](#VIC-I)
- [2 VIC-II](#VIC-II)

[2.1 Memory addresses of the VIC-II](#Memory_addresses_of_the_VIC-II)
[2.2 VIC-II Technical Details](#VIC-II_Technical_Details)
- [3 VIC-III](#VIC-III)
- [4 Microprocessor Identification](#Microprocessor_Identification)

[4.1 Notes](#Notes)
- [5 References](#References)



## VIC-I[edit | edit source]

VIC-I, MOS 6560 Revision 101, Manufactured in week 44 of 1981
VIC-I, MOS 6561 Revision E, Manufactured in week 44 of 1981
VIC-I, MOS 6561 Revision 101, Manufactured in week 10 of 1983
The VIC-I (cardinality added retrospectively) was designed for [Commodore](/wiki/Commodore) [VIC-20](/wiki/VIC-20) colour video graphics applications such as that required by low cost CRT terminals, biomedical monitors, control systems displays and arcade or home video games.  It provides all of the circuitry necessary for generating colour programmable character graphics with high screen resolution.  The VIC-I also incorporates sound effects and A/D converters for use in a video game environment.  Its features are:

- Fully expandable system with a 16K byte address space.
- System uses industry standard 8 bit wide ROMS and 4 bit wide RAMS
- Mask programmable sync generation (NTSC-6560, PAL-6561)
- On-chip colour generation (16 colours)
- Up to 600 independently programmable and movable background locations on a standard TV.
- Screen centering capability
- Screen grid size up to 192 Horizontal by 200 Vertical dots
- Two selectable graphic character sizes.
- On-chip sound system including:
White noise generator
Amplitude modulator
Two on-chip 8 bit A/D converters
- On-chip DMA and address generation
- No CPU wait states or screen hash during screen refresh
- Interlaced/Non-Interlaced registers
- Light gun/pen for target games
- 2 modes of colour operation

## VIC-II[edit | edit source]

VIC-II, MOS 6569 Revision 1, Manufactured in week 24 of 1983
VIC-II, MOS 6569 Revision 3, Manufactured in week 43 of 1984
VIC-II, MOS 6569 Revision 3, Manufactured in week 05 of 1986
VIC-II, MOS 6569 Revision 5, Manufactured in week 33 of 1986
The VIC-II is the [microchip](/index.php?title=integrated_circuit&action=edit&redlink=1) tasked with generating [Y/C](/index.php?title=S-Video&action=edit&redlink=1) video signals (combined to [composite video](/index.php?title=composite_video&action=edit&redlink=1) in the RF modulator) and [DRAM](/wiki/dynamic_random_access_memory) [refresh](/index.php?title=memory_refresh&action=edit&redlink=1) signals in the [C64](/wiki/C64) and [C128](/wiki/C128) range of [home computers](/wiki/home_computer).  The VIC-II typically accesses the memory alternately with the CPU. However, it can also freeze the CPU briefly and access the memory with higher bandwidth during that time. This happens in the so-called "[Badlines](/index.php?title=Badlines&action=edit&redlink=1)" and is necessary since the bandwidth would otherwise be insufficient.  The VIC-II is connected to the [Color RAM](/wiki/Color_RAM) via a dedicated four bits data bus.  Its features are:

- 16 kB [address space](/index.php?title=address_space&action=edit&redlink=1) for screen, character and [sprite](/wiki/sprite) memory
- 320 × 200 pixels video resolution (160 × 200 in multi-color mode)
- 40 × 25 characters text resolution
- Three character display modes and two bitmap modes
- 16 colors
- Concurrent handling of 8 [sprites](/wiki/sprite) per [scanline](/index.php?title=scanline&action=edit&redlink=1), each of 24 × 21 pixels (12 × 21 multicolor)
- [Raster interrupt](/wiki/Raster_interrupt) (see details, below)
- Smooth [scrolling](/wiki/scrolling)
- Independent dynamic [RAM refresh](/index.php?title=Memory_refresh&action=edit&redlink=1) (an unusual feature for a graphics processor)
- [Bus mastering](/index.php?title=Bus_mastering&action=edit&redlink=1) for a 6502-style [system bus](/index.php?title=computer_bus&action=edit&redlink=1); CPU and VIC-II accessing the bus during alternating half-[clock cycles](/index.php?title=clock_cycle&action=edit&redlink=1) (the VIC-II will halt the CPU when it needs extra cycles)
Succeeding MOS's original VIC, the VIC-II was one of the two chips mainly responsible for the C64's success; the other microchip being the MOS 6581 [SID](/wiki/SID)).


### Memory addresses of the VIC-II[edit | edit source]


| Hex Address | Dec Address | Page | Contents |
| --- | --- | --- | --- |
| $D000-$D3FF | 53248-54271 | Page 208-211 | VIC-II registers |
| $D800-$DBE7 | 55296-56295 | Page 216-219 | Color RAM |

- [Sprites](/wiki/Sprite) lie at address MEM(Start of screen mem + $03F8 + sprite number)*64
- The start of the [Screen RAM](/wiki/Screen_RAM) is set by $DD00 (the VIC bank, see [CIA 2](/wiki/CIA#CIA_2)) and $D018.

### VIC-II Technical Details[edit | edit source]

The operation of the VIC-II is thoroughly described in the document "[The MOS 6567/6569 video controller (VIC-II) and its application in the Commodore 64](https://www.cebix.net/VIC-Article.txt)" (1996) by Christian Bauer. A slightly more readable timing overview can be found [here](/wiki/File:vic-ii-timing.pdf).
Notes on the document:

- The cycle count starts at 1; for example, [VICE](/wiki/VICE) starts counting at 0.
- The document refers to ø0; in other sources, Phi1 (ø0 low) and Phi2 (ø0 high) are often mentioned.
- Writing to $D011/$D012 can immediately trigger a raster IRQ, provided no raster IRQ has yet been triggered in the current line.
- The vertical "expansion flip-flop" is somewhat misleadingly named; its state actually indicates whether a line in the sprite data should currently be skipped or not (MCBASE, +3 in two steps: +2 in cycle 15, +1 in cycle 16). For standard-size sprites, this flag is always set. For vertically double-sized sprites, it is cleared in the first line, then alternates each raster line.
- Sprite crunch/sprite stretching by clearing bits in $D017 shifts MC(BASE) in a slightly different manner than stated in the document.[[1]](#cite_note-1)
- VCBASE and MCBASE are used to reset VC and MC to their initial values. VCBASE is the offset into the screen memory (in standard text mode: 0 for raster lines 51-58, 40 for raster lines 59-66, and so on), while MCBASE is the byte offset within the sprite data (0, 3, 6, 9, etc. for standard-size sprites; 0, 0, 3, 3, 6, 6, 9, 9, etc. for vertically double-height sprites). Each line for a sprite data is comprised of three bytes.
- VMLI is not a pointer but rather a 40-bit shift register that controls the 40 enable bits of the VIC-II’s internal "40×12 bit video matrix/color line." When switching from idle to display mode, a "1" is shifted into the register and then continues to shift after each C/G access.
- A Badline triggered as early as cycle 15 results in a VSP offset of 1. Presumably, the transition from idle to display mode does not occur on the falling edge of ø0 but rather on the rising edge.[[2]](#cite_note-2)
- Example of access timing (in standard text mode) for the second line of the character in the top left corner ($0400):
The character and its color are determined by the C-access on line 51 (a Badline) in the second half of cycle 15.
The character pixels displayed are determined by the G-access on line 52 in the first half of cycle 16.
The background color for the character is determined by the state of $D021 on line 52 at the end of cycle 17.[[3]](#cite_note-3)

## VIC-III[edit | edit source]

VIC-III, CSG 4567 Revision 5, Manufactured in Week 50 of 1990
Graphics in the [C65](/wiki/C65) (also known as the [C64DX](/wiki/C64DX)) were to be provided by the VIC-III (designated the CSG 4567, and named as the "Bill" chip for designer Bill Gardei).  Its features are:

- Support of standard [C64](/wiki/C64) video modes.
- Textmode with 40/80 × 25 characters (featuring blink, bold, and underline).
- True bitplane VGA-style graphics:
320x200x256
640x200x256
640x400x16
1280x200x16
1280x400x4
- Palette of 4096 colours.
- Special facility for address resolution (Display Address Translator [DAT]) of the C64 pixel coordinate system.
- PAL only, no NTSC (but the RGB output works just fine with the 1084S).
- Synchronizable with external video source (Genlock).
- Integrated DMA-Controller (Bit blit).
- Reportedly can display Amiga OCS IFF.

## Microprocessor Identification[edit | edit source]

- [MOS Technology 6560](/wiki/MOS_Technology_6560) – VIC-I for ([NTSC](/wiki/NTSC)) VIC-20
- [MOS Technology 6561](/index.php?title=MOS_Technology_6561&action=edit&redlink=1) – VIC-I for ([PAL](/wiki/PAL)) VIC-20. Revision: -101/E
- [MOS Technology 6564](/wiki/MOS_Technology_6564) – VIC-I for Colour PET
- [MOS Technology 6566](/wiki/MOS_Technology_6566) – VIC-II for [MAX Machine](/index.php?title=MAX_Machine&action=edit&redlink=1)
- [MOS Technology 6567](/wiki/MOS_Technology_6567) – VIC-II for (NTSC) C64, SX-64, PET 64, C64GS. Revision: R56A/R7/R8/R9
- [MOS Technology 6569](/wiki/MOS_Technology_6569) – VIC-II for (PAL) C64, SX-64, PET 64, C64GS, MAX Machine. Revision: R1/R3/R4/R5 (R1 = only 5 lumas)
- [MOS Technology 6572](/wiki/MOS_Technology_6572) – VIC-II (PAL-N)
- [MOS Technology 6573](/wiki/MOS_Technology_6573) – VIC-II (PAL-M)
- [MOS Technology 8562](/wiki/MOS_Technology_8562) – VIC-II (NTSC)
- [MOS Technology 8564](/wiki/MOS_Technology_8564) – VIC-II for (NTSC) C128, C128D, C128DCR
- [MOS Technology 8565](/wiki/MOS_Technology_8565) – VIC-II for (PAL-B) C64. Revision: R2
- [MOS Technology 8566](/wiki/MOS_Technology_8566) – VIC-II for (PAL-B) C128, C128D, C128DCR
- [MOS Technology 8569](/wiki/MOS_Technology_8569) – VIC-II for (PAL-N) C128, C128D, C128DCR

### Notes[edit | edit source]

- The NMOS variants 6566/67/69 require +12V on Pin 13/Vdd; the HMOS-II variants (8562/65) require only +5V DC.
- The 856x variants exhibit the [Grey Dots](http://www.csdb.dk/forums/index.php?roomid=11&topicid=78186) problem.

## References[edit | edit source]


- [↑](#cite_ref-1) See [Sprite Crunch handling code in VICE](https://github.com/VICE-Team/svn-mirror/blob/1508c9d55202867ca9843e230f1a984cfefcb350/vice/src/viciisc/vicii-mem.c#L194).
- [↑](#cite_ref-2) x64sc in VICE performs the G access first in 
```
vicii-cycle.c/vicii_cycle()
```
, then checks for a badline condition in 
```
check_badline()
```
 and switches to Display Mode if necessary. Kawari checks for a badline condition first [[1]](https://github.com/randyrossi/vicii-kawari/blob/39bcdae7c2767042bee44f0c2ea37a1b40f8f96f/hdl/vicii.v#L444) but doesn't change the mode, then increments VC in the next half cycle (if in Display Mode), then switches from Idle to Display Mode (on a badline condition) [[2]](https://github.com/randyrossi/vicii-kawari/blob/39bcdae7c2767042bee44f0c2ea37a1b40f8f96f/hdl/matrix.v#L49).
- [↑](#cite_ref-3) See the 12 pixel delay remark in section 3.6.1. of the VIC article.


[Hardware internals of the C64](/wiki/Hardware_internals_of_the_C64) · [Hardware portal](/wiki/Portal:Hardware)
Components of the C64: [CPU](/wiki/MOS_6510) · VIC · [SID](/wiki/SID) · [CIA](/wiki/CIA) · [PLA](/wiki/PLA_(C64_chip)) · [RAM](/wiki/RAM) · [ROM](/wiki/ROM) · [Color RAM](/wiki/Color_RAM)

Interfaces of the C64: [Control Port](/wiki/Control_Port) · [Expansion Port](/wiki/Expansion_Port) · [Userport](/wiki/Userport) · [Cassette Port](/wiki/Cassette_Port) · [Power Supply Connector](/wiki/Power_Supply_Connector) · [A/V Jack](/wiki/A/V_Jack) · [RF Jack](/wiki/RF_Jack) · [Serial Port](/wiki/Serial_Port)




Retrieved from "[https://www.c64-wiki.com/index.php?title=VIC&oldid=44578](https://www.c64-wiki.com/index.php?title=VIC&oldid=44578)"