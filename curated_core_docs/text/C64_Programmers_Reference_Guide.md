# Commodore 64 Programmer's Reference Guide
Source: https://www.c64-wiki.com/wiki/Commodore_64_Programmer%27s_Reference_Guide




| Commodore 64 Programmer's Reference Guide |
| --- |
| Commodore 64 Programmer's Reference Guide Cover | Language | English (American) |
| Author(s) | Commodore Business Machines, Inc. |
| Publisher | Howard W. Sams & Co. Inc |
| Year | 1982 |
| ISBN | ISBN 0-672-22056-3 |
| Original price | USD, 19.95, GBP 9.95 |
| Media | {{{Media}}} |
| Pages | 504 |
| Last Edition | First Edition Fourth Printing (1983) |
| Genre | Programming Guide |
| Information |  |






## Contents


- [1 Back Cover](#Back_Cover)
- [2 Table of Contents (Abridged)](#Table_of_Contents_(Abridged))
- [3 Extract](#Extract)
- [4 Schematic Diagram](#Schematic_Diagram)
- [5 Versions](#Versions)
- [6 Reviews](#Reviews)
- [7 Links](#Links)
- [8 References](#References)





## Back Cover[edit | edit source]



| ABOUT THE COMMODORE 64 PROGRAMMER'S REFERENCE GUIDE...   
Game cartridge compatibility... spectacular sound... arcade style
graphics... and high caliber computing capabilities make
the Commodore 64 the most advanced personal computer in
its class for home, business and educational use.   
The COMMODORE 64 PROGRAMMER'S REFERENCE GUIDE tells 
you everything you need to know about your Commodore 64.
The perfect companion to your Commodore 64 User's Guide,
this manual presents detailed information on everything from
graphics and sound to advanced machine language 
techniques. This book is a must for everyone from the beginner
to the advanced programmer.   
For the beginner, the most complicated topics are explained
with many sample programs and an easy-to-read writing style.
For the advanced programmer, this book has been subjected
to heavy pre-testing with your needs in mind. And it's
designed so that you can easily get the most out of your
Commodore 64's extensive capabilities. | First Edition Back Cover |
| --- | --- |
| ABOUT THE COMMODORE 64 PROGRAMMER'S REFERENCE GUIDE...    Game cartridge compatibility... spectacular sound... arcade style graphics... and high caliber computing capabilities make the Commodore 64 the most advanced personal computer in its class for home, business and educational use.    The COMMODORE 64 PROGRAMMER'S REFERENCE GUIDE tells  you everything you need to know about your Commodore 64. The perfect companion to your Commodore 64 User's Guide, this manual presents detailed information on everything from graphics and sound to advanced machine language  techniques. This book is a must for everyone from the beginner to the advanced programmer.    For the beginner, the most complicated topics are explained with many sample programs and an easy-to-read writing style. For the advanced programmer, this book has been subjected to heavy pre-testing with your needs in mind. And it's designed so that you can easily get the most out of your Commodore 64's extensive capabilities. | First Edition Back Cover |



## Table of Contents (Abridged)[edit | edit source]

This table of contents has been reproduced to include only the chapter and appendix headings, along with the first-level section headings. The original has second-level section headings.


```
 TABLE OF CONTENTS

 INTRODUCTION ...................................................   ix
    o What's Included? ..........................................    x
    o How to Use This Reference Guide ...........................   xi
    o Commodore 64 Applications Guide ...........................  xii
    o Commodore Information Network ............................. xvii

 1. BASIC PROGRAMMING RULES .....................................    1
    o Introduction ..............................................    2
    o Screen Display Codes (BASIC Character Set) ................    2
    o Programming Numbers and Variables .........................    4
    o Expressions and Operators .................................    9
    o Programming Techniques ....................................   18

 2. BASIC LANGUAGE VOCABULARY ...................................   29
    o Introduction ..............................................   30
    o BASIC Keywords, Abbreviations, and Function Types .........   31
    o Description of BASIC Keywords (Alphabetical) ..............   35
    o The Commodore 64 Keyboard and Features ....................   93
    o Screen Editor .............................................   94

 3. PROGRAMMING GRAPHICS ON THE
    COMMODORE 64 ................................................   99
    o Graphics Overview .........................................  100
    o Graphics locations ........................................  101
    o Standard Character Mode ...................................  107
    o Programmable Characters ...................................  108
    o Multi-Color Mode Graphics .................................  115
    o Extended Background Color Mode ............................  120
    o Bit Mapped Graphics .......................................  121
    o Multi-Color Bit Map Mode ..................................  127
    o Smooth Scrolling ..........................................  128
    o Sprites ...................................................  131
    o Other Graphics Features ...................................  150
    o Programming Sprites-Another Look ..........................  153

4. PROGRAMMING SOUND AND MUSIC
    ON YOUR COMMODORE 64 ........................................  183
    o Introduction ..............................................  184
    o Using Multiple Voices .....................................  187
    o Changing Waveforms ........................................  192
    o The Envelope Generator ....................................  196
    o Filtering .................................................  199
    o Advanced Techniques .......................................  202
    o Synchronization and Ring Modulation .......................  207

 5. BASIC TO MACHINE LANGUAGE ...................................  209
    o What is Machine Language? .................................  210
    o How Do You Write Machine Language Programs? ...............  214
    o Hexadecimal Notation ......................................  215
    o Addressing Modes ..........................................  221
    o Indexing ..................................................  223
    o Subroutines ...............................................  228
    o Useful Tips for the Beginner ..............................  229
    o Approaching a Large Task ..................................  230
    o MCS6510 Microprocessor Instruction Set ....................  232
    o Memory Management on the Commodore 64 .....................  260
    o The KERNAL ................................................  268
    o KERNAL Power-Up Activities ................................  269
    o Using Machine Language From BASIC .........................  307
    o Commodore 64 Memory Map ...................................  310

 6. INPUT/OUTPUT GUIDE ..........................................  335
    o Introduction ..............................................  336
    o Output to the TV ..........................................  336
    o Output to Other Devices ...................................  337
    o The Game Ports ............................................  343
    o RS-232 Interface Description ..............................  348
    o The User Port .............................................  359
    o The Serial Bus ............................................  362
    o The Expansion Port ........................................  366
    o Z-80 Microprocessor Cartridge .............................  368

 APPENDICES .....................................................  373
    A.  Abbreviations for BASIC Keywords ........................  374
    B.  Screen Display Codes ....................................  376
    C.  ASCII and CHR$ Codes ....................................  379
    D.  Screen and Color Memory Maps ............................  382
    E.  Music Note Values .......................................  384
    F.  Bibliography ............................................  388
    G.  VIC Chip Register Map ...................................  391
    H.  Deriving Mathematical Functions .........................  394
    I.  Pinouts for Input/Output Devices ........................  395
    J.  Converting Standard BASIC Programs to
          Commodore 64 BASIC ....................................  398
    K.  Error Messages ..........................................  400
    L.  6510 Microprocessor Chip Specifications .................  402
    M.  6526 Complex Interface Adapter (CIA)
          Chip Specifications ...................................  419
    N.  6566/6567 (VIC-II) Chip Specifications ..................  436
    0.  6581 Sound Interface Device (SID) Chip Specifications ...  457
    P.  Glossary ................................................  482

 INDEX ..........................................................  483

 COMMODORE 64 QUICK REFERENCE CARD ..............................  487

 SCHEMATIC DIAGRAM OF THE COMMODORE 64 ..........................  491

```


## Extract[edit | edit source]

Page 210:


```
 WHAT IS MACHINE LANGUAGE?
 
   At the heart of every microcomputer,  is  a  central  microprocessor.  It's
 a  very  special  microchip  which  is  the  "brain"  of  the  computer.  The
 Commodore 64 is  no  exception.  Every  microprocessor  understands  its  own
 language of  instructions.  These  instructions are  called machine  language
 instructions.  To  put  it  more  precisely,  machine language  is  the  ONLY
 programming  language that your  Commodore 64  understands.  It is the NATIVE
 language of the machine.

```


## Schematic Diagram[edit | edit source]

A 370mm x 500mm double-sided fold-out schematic diagram is included in the book. It identified all the ICs and circuit pathways between the power supply, components and external connections (such as the [user port](/wiki/user_port), [expansion port](/wiki/expansion_port) and [serial bus](/wiki/serial_bus)).



| Commodore 64 Schematic Diagram (left) | Commodore 64 Schematic Diagram (right) |
| --- | --- |
| Commodore 64 Schematic Diagram (left) | Commodore 64 Schematic Diagram (right) |





## Versions[edit | edit source]



| Country | Edition | Printing | Year | Front Cover | Inside Cover | Reverse Cover | Remarks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| USA | First Edition | First Printing | 1982 | First Edition First Printing [1] | First Edition First Printing | First Edition First Printing | Plastic Spiral Bound |
| USA | First Edition | Second Printing |  | First Edition Second Printing | First Edition Second Printing | First Edition Second Printing | Plastic Spiral Bound |
| USA | First Edition | Third Printing | 1983 | First Edition Third Printing [2] | First Edition Third Printing | First Edition Third Printing | Plastic Spiral Bound |
| England | First Edition | Fourth Printing | 1983 | First Edition Fourth Printing [3] | First Edition Fourth Printing | First Edition Fourth Printing | Steel Spiral Bound |
| USA | First Edition | Fifth Printing | 1983 | First Edition Fifth Printing | First Edition Fifth Printing | First Edition Fifth Printing |  |
| USA | First Edition | Sixth Printing | 1983 | First Edition Sixth Printing | First Edition Sixth Printing | First Edition Sixth Printing |  |
| USA | First Edition | Seventh Printing | 1983 | First Edition Seventh Printing | First Edition Seventh Printing | First Edition Seventh Printing | Plastic Spiral Bound with Text |
| USA | First Edition | Eighth Printing | 1983 | First Edition Eighth Printing [4] | First Edition Eighth Printing | First Edition Eighth Printing | Plastic Spiral Bound |
| USA | First Edition | Ninth Printing |  | First Edition Ninth Printing | First Edition Ninth Printing | First Edition Ninth Printing |  |
| USA | First Edition | Tenth Printing | 1984 | First Edition Tenth Printing | First Edition Tenth Printing | First Edition Tenth Printing | Plastic Spiral Bound with Text |
| USA | First Edition | Eleventh Printing | 1984 | First Edition Eleventh Printing | First Edition Eleventh Printing | First Edition Eleventh Printing | Plastic Spiral Bound with Text |
| USA | First Edition | Twelfth Printing | 1985 | First Edition Twelfth Printing | First Edition Twelfth Printing | First Edition Twelfth Printing | Plastic Spiral Bound |
| USA | First Edition | Thirteenth Printing |  | First Edition Thirteenth Printing | First Edition Thirteenth Printing | First Edition Thirteenth Printing |  |
| USA | First Edition | Fourteenth Printing |  | First Edition Fourteenth Printing | First Edition Fourteenth Printing | First Edition Fourteenth Printing |  |
| USA | First Edition | Fifteenth Printing |  | First Edition Fifteenth Printing | First Edition Fifteenth Printing | First Edition Fifteenth Printing |  |
| USA | First Edition | Sixteenth Printing |  | First Edition Sixteenth Printing | First Edition Sixteenth Printing | First Edition Sixteenth Printing |  |
| USA | First Edition | Seventeenth Printing |  | First Edition Seventeenth Printing | First Edition Seventeenth Printing | First Edition Seventeenth Printing |  |
| USA | First Edition | Eighteenth Printing |  | First Edition Eighteenth Printing | First Edition Eighteenth Printing | First Edition Eighteenth Printing |  |
| USA | First Edition | Nineteenth Printing |  | First Edition Nineteenth Printing | First Edition Nineteenth Printing | First Edition Nineteenth Printing |  |
| USA | First Edition | Twentieth Printing |  | First Edition Twentieth Printing | First Edition Twentieth Printing | First Edition Twentieth Printing |  |
| USA | First Edition | Twenty-First Printing | 1989 | First Edition Twenty-First Printing | First Edition Twenty-First Printing | First Edition Twenty-First Printing | Glue Bound |
| Canada | First Edition | Fourth Printing | 1984 | First Edition Fourth Printing (French) | First Edition Fourth Printing (French) | First Edition Fourth Printing (French) |  |
| Australia | First Edition | Second Australian Printing | 1984 | First Edition Second Australian Printing | First Edition Second Australian Printing | First Edition Second Australian Printing | Plastic Spiral Bound with Text |
| USA | Second Edition | First Printing |  | Second Edition [5] | Second Edition First Printing | Second Edition First Printing | Glue Bound |
| USA | Third Edition | First Printing |  | Third Edition [6] | Third Edition First Printing | Third Edition First Printing | Glue Bound |



## Reviews[edit | edit source]

Amazon Customer[[7]](#cite_note-7): "Once you have exhausted the user guide for the C64, this is your next step. It will give you all the information you require to get started with machine code. It also explains how to make use of all the ports on the C64. It is possible to use ( or build) a serial interface to hook up to a regular PC. I found the information on the User Port particularly useful for home automation and robotics."
[Jodigi](/wiki/User:Jodigi): "A very good and helpful book for advanced programmers learn more basics and technical details about the C64 and also special programming knowledge, but not enough."
[Charliefourzero](/wiki/User:Charliefourzero): "It is hard to see how anyone could program the C64 without having read this book. Where the C64 User Guide helps you turn on the computer, this book helps you understand how it works. It should be the bedrock for understanding the C64 both from a software and hardware perspective. It is not perfect, but then CBM honestly did not know exactly how the C64 would be used by its hardcore fans. The book covers all the main areas in sufficient detail; which required at least 500 pages! Simply, a 'must read'.


## Links[edit | edit source]

- [Commodore 64 Programmer's Reference Guide (Text Version)](http://www.zimmers.net/cbmpics/cbm/c64/c64prg.txt) at zimmers.net, accessed 27 September 2014
- [Commodore 64 Programmer's Reference Guide (HTML Version)](http://www.devili.iki.fi/Computers/Commodore/C64/Programmers_Reference/page_iii.html), accessed 27 September 2014
- [Commodore 64 Programmer's Reference Guide (PDF Version)](http://www.classiccmp.org/cini/pdf/Commodore/C64%20Programmer's%20Reference%20Guide.pdf), accessed 27 September 2014
- [Commodore 64 Programmer's Reference Guide in chapters (PDF)](http://www.commodore.ca/commodore-manuals/commodore-64-programmers-reference-guide/) at commodore.ca, accessed 30 September 2014

## References[edit | edit source]


- [↑](#cite_ref-1) [Amazon.com](http://www.amazon.com/gp/customer-media/product-gallery/0672220563/ref=cm_cr_dp_cust_img_see_all_img1),accessed 27 September 2014
- [↑](#cite_ref-2) [Commodore Computers](http://www.commodore.ca/manuals/c64_programmers_reference/c64-programmers_reference_guide-00-toc_introduction.pdf),accessed 27 September 2014
- [↑](#cite_ref-3) [Amazon.com](http://www.amazon.com/gp/customer-media/product-gallery/0672220563/ref=cm_cr_dp_cust_img_see_all_img1),accessed 27 September 2014
- [↑](#cite_ref-4) [Amazon.com](http://www.amazon.com/gp/customer-media/product-gallery/0672220563/ref=cm_cr_dp_cust_img_see_all_img1),accessed 27 September 2014
- [↑](#cite_ref-5) [Amazon.com](http://www.amazon.com/gp/customer-media/product-gallery/0672220563/ref=cm_cr_dp_cust_img_see_all_img1),accessed 27 September 2014
- [↑](#cite_ref-6) [Amazon.com](http://www.amazon.com/gp/customer-media/product-gallery/0672220563/ref=cm_cr_dp_cust_img_see_all_img1),accessed 27 September 2014
- [↑](#cite_ref-7) [Amazon Customer Review](http://www.amazon.com/Commodore-64-Programmers-Reference-Guide/product-reviews/0672220563/ref=dpx_acr_txt?showViewpoints=1), accessed 27 September 2014





Retrieved from "[https://www.c64-wiki.com/index.php?title=Commodore_64_Programmer%27s_Reference_Guide&oldid=35157](https://www.c64-wiki.com/index.php?title=Commodore_64_Programmer%27s_Reference_Guide&oldid=35157)"