"""
Commodore 64 PRG, D64, and TAP 6502 Reverse Decompiler

Reconstructs clean, richly commented KickAssembler (.asm) and Python-transpiler (.py) source
from extracted C64 PRG executables, disk images (.d64), and tape images (.tap).

Features:
- C64 BASIC V2 detokenizer ($0800/$0801), SYS (addr) and POKE vector detector
- Multi-pass recursive + heuristic 6502 machine code discovery (follows JMP/JSR/branches,
  RAM/KERNAL vector tables $0300-$0333, IRQ/NMI setup pairs, and post-RTS subroutines)
- Smart label classification (entry_main, irq_handler_xxxx, sub_xxxx, loc_xxxx)
- Rich educational comments:
  - Architecture & Hardware Subsystem overview header
  - Subroutine banners with caller cross-references and subsystem tags
  - Instruction-level explanations (C64 palette colors, 6510 $01 memory banking,
    VIC-II screen/charset/multicolor/sprite bits, SID waveforms & volume,
    CIA timers/VIC banks, KERNAL API calls, Screen/Color RAM, CPU flags)
- Multi-stage Loader / Main Game / Both decompilation scope support for TAP and D64 media
- Note on KickAssembler: KickAssembler (KickAss.jar) is a 6502/6510 macro assembler and does
  not contain a built-in disassembler/decompiler class; this module generates 100% compatible
  KickAssembler v5.x source syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

from .d64 import read_d64_file
from .tap import TapStage, extract_prgs_from_tap, extract_tap_stages


# Commodore 64 BASIC V2 Token Mapping ($80 - $CB)
BASIC_TOKENS: Dict[int, str] = {
    0x80: "END", 0x81: "FOR", 0x82: "NEXT", 0x83: "DATA", 0x84: "INPUT#",
    0x85: "INPUT", 0x86: "DIM", 0x87: "READ", 0x88: "LET", 0x89: "GOTO",
    0x8A: "RUN", 0x8B: "IF", 0x8C: "RESTORE", 0x8D: "GOSUB", 0x8E: "RETURN",
    0x8F: "REM", 0x90: "STOP", 0x91: "ON", 0x92: "WAIT", 0x93: "LOAD",
    0x94: "SAVE", 0x95: "VERIFY", 0x96: "DEF", 0x97: "POKE", 0x98: "PRINT#",
    0x99: "PRINT", 0x9A: "CONT", 0x9B: "LIST", 0x9C: "CLR", 0x9D: "CMD",
    0x9E: "SYS", 0x9F: "OPEN", 0xA0: "CLOSE", 0xA1: "GET", 0xA2: "NEW",
    0xA3: "TAB(", 0xA4: "TO", 0xA5: "FN", 0xA6: "SPC(", 0xA7: "THEN",
    0xA8: "NOT", 0xA9: "STEP", 0xAA: "+", 0xAB: "-", 0xAC: "*",
    0xAD: "/", 0xAE: "^", 0xAF: "AND", 0xB0: "OR", 0xB1: ">",
    0xB2: "=", 0xB3: "<", 0xB4: "SGN", 0xB5: "INT", 0xB6: "ABS",
    0xB7: "USR", 0xB8: "FRE", 0xB9: "POS", 0xBA: "SQR", 0xBB: "RND",
    0xBC: "LOG", 0xBD: "EXP", 0xBE: "COS", 0xBF: "SIN", 0xC0: "TAN",
    0xC1: "ATN", 0xC2: "PEEK", 0xC3: "LEN", 0xC4: "STR$", 0xC5: "VAL",
    0xC6: "ASC", 0xC7: "CHR$", 0xC8: "LEFT$", 0xC9: "RIGHT$", 0xCA: "MID$",
    0xCB: "GO",
}

# MOS 6502 Opcode specifications (Mnemonic, Addressing Mode)
_OPCODE_SPEC = """
00 BRK imp|01 ORA indx|05 ORA zp|06 ASL zp|08 PHP imp|09 ORA imm|0A ASL acc|0D ORA abs|0E ASL abs
10 BPL rel|11 ORA indy|15 ORA zpx|16 ASL zpx|18 CLC imp|19 ORA absy|1D ORA absx|1E ASL absx
20 JSR abs|21 AND indx|24 BIT zp|25 AND zp|26 ROL zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs|2E ROL abs
30 BMI rel|31 AND indy|35 AND zpx|36 ROL zpx|38 SEC imp|39 AND absy|3D AND absx|3E ROL absx
40 RTI imp|41 EOR indx|45 EOR zp|46 LSR zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs
50 BVC rel|51 EOR indy|55 EOR zpx|56 LSR zpx|58 CLI imp|59 EOR absy|5D EOR absx|5E LSR absx
60 RTS imp|61 ADC indx|65 ADC zp|66 ROR zp|68 PLA imp|69 ADC imm|6A ROR acc|6D ADC abs|6E ROR abs|6C JMP ind
70 BVS rel|71 ADC indy|75 ADC zpx|76 ROR zpx|78 SEI imp|79 ADC absy|7D ADC absx|7E ROR absx
81 STA indx|84 STY zp|85 STA zp|86 STX zp|88 DEY imp|8A TXA imp|8C STY abs|8D STA abs|8E STX abs
89 NOP imm|80 NOP imm
90 BCC rel|91 STA indy|94 STY zpx|95 STA zpx|96 STX zpy|98 TYA imp|99 STA absy|9A TXS imp|9D STA absx
A0 LDY imm|A1 LDA indx|A2 LDX imm|A4 LDY zp|A5 LDA zp|A6 LDX zp|A8 TAY imp|A9 LDA imm|AA TAX imp|AC LDY abs|AD LDA abs|AE LDX abs
B0 BCS rel|B1 LDA indy|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B8 CLV imp|B9 LDA absy|BA TSX imp|BC LDY absx|BD LDA absx|BE LDX absy
C0 CPY imm|C1 CMP indx|C4 CPY zp|C5 CMP zp|C6 DEC zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs|CD CMP abs|CE DEC abs
D0 BNE rel|D1 CMP indy|D5 CMP zpx|D6 DEC zpx|D8 CLD imp|D9 CMP absy|DD CMP absx|DE DEC absx
E0 CPX imm|E1 SBC indx|E4 CPX zp|E5 SBC zp|E6 INC zp|E8 INX imp|E9 SBC imm|EA NOP imp|EC CPX abs|ED SBC abs|EE INC abs
F0 BEQ rel|F1 SBC indy|F5 SBC zpx|F6 INC zpx|F8 SED imp|F9 SBC absy|FD SBC absx|FE INC absx
"""

_MODE_SIZE = {
    "imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2,
    "indx": 2, "indy": 2, "rel": 2, "abs": 3, "absx": 3,
    "absy": 3, "ind": 3,
}

_OPCODES: Dict[int, Tuple[str, str]] = {}
for _item in _OPCODE_SPEC.replace("\n", "|").split("|"):
    _parts = _item.strip().split()
    if _parts:
        _OPCODES[int(_parts[0], 16)] = (_parts[1], _parts[2])

_BRANCHES = {"BCC", "BCS", "BEQ", "BMI", "BNE", "BPL", "BVC", "BVS"}
_TERMINATORS = {"BRK", "RTI", "RTS"}

# C64 16-Color Palette Names
C64_COLOR_NAMES: Dict[int, str] = {
    0: "Black", 1: "White", 2: "Red", 3: "Cyan",
    4: "Purple", 5: "Green", 6: "Blue", 7: "Yellow",
    8: "Orange", 9: "Brown", 10: "Light Red", 11: "Dark Grey",
    12: "Medium Grey", 13: "Light Green", 14: "Light Blue", 15: "Light Grey",
}

# C64 RAM Vector Table ($0300 - $0332)
C64_RAM_VECTORS: Dict[int, str] = {
    0x0300: "BASIC_IERROR (Warm Start / Error Message Vector)",
    0x0302: "BASIC_IMAIN (Main BASIC Loop Vector)",
    0x0304: "BASIC_ICRNCH (Tokenize Crunch Vector)",
    0x0306: "BASIC_IQPLOP (LIST Token Vector)",
    0x0308: "BASIC_IGONE (Execute Next Token Vector)",
    0x030A: "BASIC_IEVAL (Evaluate Expression Vector)",
    0x0314: "RAM_IRQ_VECTOR (Hardware Interrupt Service Vector)",
    0x0316: "RAM_BRK_VECTOR (BRK Instruction Vector)",
    0x0318: "RAM_NMI_VECTOR (RESTORE / Non-Maskable Interrupt Vector)",
    0x031A: "KERNAL_IOPEN (OPEN Vector)",
    0x031C: "KERNAL_ICLOSE (CLOSE Vector)",
    0x031E: "KERNAL_ICHKIN (CHKIN Vector)",
    0x0320: "KERNAL_ICKOUT (CHKOUT Vector)",
    0x0322: "KERNAL_ICLRCH (CLRCHN Vector)",
    0x0324: "KERNAL_IBASIN (CHRIN Vector)",
    0x0326: "KERNAL_IBSOUT (CHROUT Vector -- often hijacked for autostart)",
    0x0328: "KERNAL_ISTOP (STOP Key Check Vector)",
    0x032A: "KERNAL_IGETIN (GETIN Vector)",
    0x032C: "KERNAL_ICLALL (CLALL Vector)",
    0x032E: "KERNAL_USRCMD (User Command Vector)",
    0x0330: "KERNAL_ILOAD (LOAD Vector)",
    0x0332: "KERNAL_ISAVE (SAVE Vector)",
}

# C64 Hardware and KERNAL Symbol Annotations
HARDWARE_REGISTERS: Dict[int, str] = {
    # 6510 Zero Page CPU Port
    0x0000: "CPU_PORT_DDR (6510 Data Direction Register)",
    0x0001: "CPU_PORT (Banking: RAM/ROM/IO & Cassette Motor/Sense)",
    # Common C64 Zero Page OS Pointers
    0x0002: "ZP_UNUSED_02 (Free Zero-Page Pointer Lo)",
    0x0090: "KERNAL_STATUS (ST: I/O Status Word)",
    0x0093: "KERNAL_VERCK (0=Load, 1=Verify Flag)",
    0x00AE: "KERNAL_EAL_LO (Program End / Tape Load Address Lo)",
    0x00AF: "KERNAL_EAL_HI (Program End / Tape Load Address Hi)",
    0x00B2: "KERNAL_TAPE1_LO (Tape Buffer Pointer Lo)",
    0x00B3: "KERNAL_TAPE1_HI (Tape Buffer Pointer Hi)",
    0x00BA: "KERNAL_FA (Current Device Number: 1=Tape, 8=Disk)",
    0x00C5: "KERNAL_LSTX (Current Key Matrix Coordinate Pressed)",
    0x00C6: "KERNAL_NDX (Number of Chars in Keyboard Buffer)",
    # VIC-II ($D000 - $D02E)
    0xD000: "VIC_SP0_X (Sprite 0 X Position)", 0xD001: "VIC_SP0_Y (Sprite 0 Y Position)",
    0xD002: "VIC_SP1_X (Sprite 1 X Position)", 0xD003: "VIC_SP1_Y (Sprite 1 Y Position)",
    0xD004: "VIC_SP2_X (Sprite 2 X Position)", 0xD005: "VIC_SP2_Y (Sprite 2 Y Position)",
    0xD006: "VIC_SP3_X (Sprite 3 X Position)", 0xD007: "VIC_SP3_Y (Sprite 3 Y Position)",
    0xD008: "VIC_SP4_X (Sprite 4 X Position)", 0xD009: "VIC_SP4_Y (Sprite 4 Y Position)",
    0xD00A: "VIC_SP5_X (Sprite 5 X Position)", 0xD00B: "VIC_SP5_Y (Sprite 5 Y Position)",
    0xD00C: "VIC_SP6_X (Sprite 6 X Position)", 0xD00D: "VIC_SP6_Y (Sprite 6 Y Position)",
    0xD00E: "VIC_SP7_X (Sprite 7 X Position)", 0xD00F: "VIC_SP7_Y (Sprite 7 Y Position)",
    0xD010: "VIC_SP_MSB_X (Sprites 0-7 X Position Bit 8)",
    0xD011: "VIC_SCROLY_CTRL1 (Screen On/25 Rows/BMM/Raster Bit 8)",
    0xD012: "VIC_RASTER (Rasterline Counter / Compare IRQ Line)",
    0xD013: "VIC_LIGHTPEN_X", 0xD014: "VIC_LIGHTPEN_Y",
    0xD015: "VIC_SP_ENABLE (Sprite Display Enable Bitmask)",
    0xD016: "VIC_SCROLX_CTRL2 (Multicolor/40 Cols/Scroll X)",
    0xD017: "VIC_SP_Y_EXPAND (Sprite Double Height Bitmask)",
    0xD018: "VIC_MEMORY_PTR (Screen Matrix & Charset/Bitmap Base)",
    0xD019: "VIC_IRQ_FLAGS (Raster / Sprite Collision IRQ Flags)",
    0xD01A: "VIC_IRQ_ENABLE (Raster IRQ / Sprite IRQ Enable)",
    0xD01B: "VIC_SP_BG_PRIORITY (Sprite vs Foreground Priority)",
    0xD01C: "VIC_SP_MULTICOLOR_EN (Sprite Multicolor Mode Bitmask)",
    0xD01D: "VIC_SP_X_EXPAND (Sprite Double Width Bitmask)",
    0xD01E: "VIC_SP_SP_COLLISION (Sprite-to-Sprite Collision Latches)",
    0xD01F: "VIC_SP_BG_COLLISION (Sprite-to-Background Collision Latches)",
    0xD020: "VIC_BORDER_COLOR",
    0xD021: "VIC_BG_COLOR0",
    0xD022: "VIC_BG_COLOR1 (Extended/Multicolor BG 1)",
    0xD023: "VIC_BG_COLOR2 (Extended/Multicolor BG 2)",
    0xD024: "VIC_BG_COLOR3 (Extended BG 3)",
    0xD025: "VIC_SP_MC_COLOR0 (Sprite Shared Multicolor 0)",
    0xD026: "VIC_SP_MC_COLOR1 (Sprite Shared Multicolor 1)",
    0xD027: "VIC_SP0_COLOR", 0xD028: "VIC_SP1_COLOR", 0xD029: "VIC_SP2_COLOR", 0xD02A: "VIC_SP3_COLOR",
    0xD02B: "VIC_SP4_COLOR", 0xD02C: "VIC_SP5_COLOR", 0xD02D: "VIC_SP6_COLOR", 0xD02E: "VIC_SP7_COLOR",
    # SID ($D400 - $D41C)
    0xD400: "SID_V1_FREQ_LO", 0xD401: "SID_V1_FREQ_HI", 0xD402: "SID_V1_PW_LO", 0xD403: "SID_V1_PW_HI",
    0xD404: "SID_V1_CTRL (Voice 1 Waveform & Gate)", 0xD405: "SID_V1_ATTACK_DECAY", 0xD406: "SID_V1_SUSTAIN_RELEASE",
    0xD407: "SID_V2_FREQ_LO", 0xD408: "SID_V2_FREQ_HI", 0xD409: "SID_V2_PW_LO", 0xD40A: "SID_V2_PW_HI",
    0xD40B: "SID_V2_CTRL (Voice 2 Waveform & Gate)", 0xD40C: "SID_V2_ATTACK_DECAY", 0xD40D: "SID_V2_SUSTAIN_RELEASE",
    0xD40E: "SID_V3_FREQ_LO", 0xD40F: "SID_V3_FREQ_HI", 0xD410: "SID_V3_PW_LO", 0xD411: "SID_V3_PW_HI",
    0xD412: "SID_V3_CTRL (Voice 3 Waveform & Gate)", 0xD413: "SID_V3_ATTACK_DECAY", 0xD414: "SID_V3_SUSTAIN_RELEASE",
    0xD415: "SID_FILTER_CUTOFF_LO", 0xD416: "SID_FILTER_CUTOFF_HI",
    0xD417: "SID_FILTER_RESONANCE_ROUTING", 0xD418: "SID_FILTER_MODE_VOLUME",
    0xD41B: "SID_OSC3_RANDOM (Voice 3 Oscillator / Random Byte Readout)",
    # CIA1 ($DC00 - $DC0F)
    0xDC00: "CIA1_PORT_A (Data Port A: Joystick 2 / Key Matrix Col)",
    0xDC01: "CIA1_PORT_B (Data Port B: Joystick 1 / Key Matrix Row)",
    0xDC02: "CIA1_DDR_A", 0xDC03: "CIA1_DDR_B",
    0xDC04: "CIA1_TIMER_A_LO", 0xDC05: "CIA1_TIMER_A_HI",
    0xDC06: "CIA1_TIMER_B_LO", 0xDC07: "CIA1_TIMER_B_HI",
    0xDC0D: "CIA1_INTERRUPT_CTRL (Timer/Tape Pulse Interrupt Control & Status)",
    0xDC0E: "CIA1_CONTROL_A (Timer A Control)", 0xDC0F: "CIA1_CONTROL_B (Timer B Control)",
    # CIA2 ($DD00 - $DD0F)
    0xDD00: "CIA2_PORT_A (VIC-II 16KB Bank Select / IEC Serial Bus)",
    0xDD01: "CIA2_PORT_B (User Port)",
    0xDD02: "CIA2_DDR_A", 0xDD03: "CIA2_DDR_B",
    0xDD04: "CIA2_TIMER_A_LO", 0xDD05: "CIA2_TIMER_A_HI",
    0xDD06: "CIA2_TIMER_B_LO", 0xDD07: "CIA2_TIMER_B_HI",
    0xDD0D: "CIA2_INTERRUPT_CTRL (NMI Timer Control & Status)",
    0xDD0E: "CIA2_CONTROL_A", 0xDD0F: "CIA2_CONTROL_B",
    # Standard Vector Locations in RAM & Hardware Vectors
    0x0314: "RAM_IRQ_VECTOR_LO", 0x0315: "RAM_IRQ_VECTOR_HI",
    0x0316: "RAM_BRK_VECTOR_LO", 0x0317: "RAM_BRK_VECTOR_HI",
    0x0318: "RAM_NMI_VECTOR_LO", 0x0319: "RAM_NMI_VECTOR_HI",
    0xFFFA: "HW_NMI_VECTOR_LO", 0xFFFB: "HW_NMI_VECTOR_HI",
    0xFFFC: "HW_RESET_VECTOR_LO", 0xFFFD: "HW_RESET_VECTOR_HI",
    0xFFFE: "HW_IRQ_VECTOR_LO", 0xFFFF: "HW_IRQ_VECTOR_HI",
    # Standard KERNAL & Internal ROM Entry Points
    0xEA31: "KERNAL_IRQ_MAIN (Standard KERNAL IRQ Service & Keyboard Scan)",
    0xEA81: "KERNAL_IRQ_EXIT (Restore A/X/Y Registers & RTI from IRQ)",
    0xFE47: "KERNAL_NMI_EXIT (Default NMI Exit Handler)",
    0xFF81: "KERNAL_CINT (Initialize Screen Editor & VIC-II)",
    0xFF84: "KERNAL_IOINIT (Initialize CIA Timers & I/O Devices)",
    0xFF87: "KERNAL_RAMTAS (Clear RAM & Set Tape Buffer Pointers)",
    0xFF8A: "KERNAL_RESTOR (Restore Default I/O & Interrupt Vectors)",
    0xFF90: "KERNAL_SETMSG (Control KERNAL Status Messages)",
    0xFF93: "KERNAL_SECOND (Send Secondary Address after LISTEN)",
    0xFF96: "KERNAL_TKSA (Send Secondary Address after TALK)",
    0xFFA5: "KERNAL_ACPTR (Read Byte from IEC Serial Bus)",
    0xFFA8: "KERNAL_CIOUT (Write Byte to IEC Serial Bus)",
    0xFFAB: "KERNAL_UNTLK (Send UNTALK on IEC Bus)",
    0xFFAE: "KERNAL_UNLSN (Send UNLISTEN on IEC Bus)",
    0xFFB1: "KERNAL_LISTEN (Command Device on IEC Bus to LISTEN)",
    0xFFB4: "KERNAL_TALK (Command Device on IEC Bus to TALK)",
    0xFFBA: "KERNAL_SETLFS (Set Logical File, Device & Secondary Addr)",
    0xFFBD: "KERNAL_SETNAM (Set Filename Pointer in X/Y & Length in A)",
    0xFFC0: "KERNAL_OPEN (Open Logical File Channel)",
    0xFFC3: "KERNAL_CLOSE (Close Logical File Channel)",
    0xFFC6: "KERNAL_CHKIN (Set Input Channel)",
    0xFFC9: "KERNAL_CHKOUT (Set Output Channel)",
    0xFFCC: "KERNAL_CLRCHN (Restore Default I/O Channels)",
    0xFFCF: "KERNAL_CHRIN (Input Byte from Active Channel)",
    0xFFD2: "KERNAL_CHROUT (Output Character in A to Screen/Channel)",
    0xFFD5: "KERNAL_LOAD (Load RAM from Device: A=0 Load, A=1 Verify)",
    0xFFD8: "KERNAL_SAVE (Save RAM to Device)",
    0xFFE1: "KERNAL_STOP (Check RUN/STOP Key Status)",
    0xFFE4: "KERNAL_GETIN (Read Character from Keyboard Queue into A)",
    0xFFE7: "KERNAL_CLALL (Close All Open Files & Channels)",
    0xFFEA: "KERNAL_UDTIM (Increment Real-Time Jiffy Clock)",
    0xFFF0: "KERNAL_PLOT (Carry=0 Set / Carry=1 Read Cursor Row X, Col Y)",
    0xFFF3: "KERNAL_IOBASE (Return Base Address of I/O Block in X/Y)",
}


@dataclass(frozen=True)
class DisassembledInstruction:
    address: int
    opcode: int
    mnemonic: str
    mode: str
    operand: bytes

    @property
    def size(self) -> int:
        return 1 + len(self.operand)


@dataclass
class MediaStageInfo:
    """Metadata describing a decompilable stage inside a TAP or D64 file."""
    index: int
    name: str
    role: str  # "loader" or "main"
    load_address: int
    end_address: int
    size: int
    description: str
    entry_points: List[int] = field(default_factory=list)


@dataclass
class PrgDecompileResult:
    filename: str
    load_address: int
    end_address: int
    payload_size: int
    basic_lines: List[Tuple[int, str]]
    has_basic_sys: bool
    sys_address: Optional[int]
    entry_points: List[int]
    assembly: str
    python: str
    instruction_count: int
    data_byte_count: int
    warnings: List[str]
    scope: str = "both"
    stages_decompiled: List[str] = field(default_factory=list)


def detokenize_basic(prg_payload: bytes, base_address: int) -> Tuple[List[Tuple[int, str]], Optional[int], int]:
    """
    Parse tokenized Commodore 64 BASIC lines starting at base_address ($0801 or $0800).
    Supports both `SYS 2064` and `SYS (2064)` syntax, and stops cleanly if the BASIC
    line-link pointer leaves the program range or points backward.

    Returns:
        Tuple of (list_of_lines, sys_entry_address_or_None, bytes_consumed_by_basic)
    """
    lines: List[Tuple[int, str]] = []
    sys_address: Optional[int] = None
    total_len = len(prg_payload)
    end_address = base_address + total_len

    # Some tape/disk blocks load at $0800 with 1 leading padding/header byte before $0801
    offset = 0
    if base_address == 0x0800 and total_len >= 6:
        cand_ptr = prg_payload[1] | (prg_payload[2] << 8)
        if 0x0803 <= cand_ptr < end_address:
            offset = 1

    while offset < total_len:
        if offset + 2 <= total_len and prg_payload[offset] == 0 and prg_payload[offset + 1] == 0:
            offset += 2  # End of BASIC program marker (0x00 0x00)
            break
        if offset + 4 >= total_len:
            break

        line_start_addr = base_address + offset
        next_line_ptr = prg_payload[offset] | (prg_payload[offset + 1] << 8)
        line_num = prg_payload[offset + 2] | (prg_payload[offset + 3] << 8)

        # Validate that next_line_ptr looks like a genuine BASIC link pointer
        if next_line_ptr != 0 and (next_line_ptr <= line_start_addr or next_line_ptr > end_address + 256):
            break
        if line_num > 63999:
            break

        offset += 4
        line_tokens: List[str] = []
        in_quotes = False

        while offset < total_len:
            byte = prg_payload[offset]
            offset += 1
            if byte == 0:
                break
            if byte == ord('"'):
                in_quotes = not in_quotes
                line_tokens.append('"')
            elif not in_quotes and byte in BASIC_TOKENS:
                line_tokens.append(" " + BASIC_TOKENS[byte] + " ")
            elif 0x20 <= byte <= 0x7E:
                line_tokens.append(chr(byte))
            else:
                line_tokens.append(f"<{byte:02X}>")

        text = "".join(line_tokens).strip()
        text = re.sub(r"\s+", " ", text)
        lines.append((line_num, text))

        # Check for SYS <addr> or SYS (<addr>) pattern
        match = re.search(r"\bSYS\s*\(?\s*(\d+)\s*\)?", text, re.IGNORECASE)
        if match and sys_address is None:
            sys_val = int(match.group(1))
            if 0 <= sys_val <= 0xFFFF:
                sys_address = sys_val

    return lines, sys_address, offset


def _extract_basic_poke_seeds(
    basic_lines: List[Tuple[int, str]],
    load_address: int,
    end_address: int,
) -> List[int]:
    """
    Inspect detokenized BASIC lines for POKE statements that set IRQ/NMI/WarmStart vectors
    (e.g. `POKE 65535,17: POKE 65534,3` -> $1103 in Bruce Lee) or jump into machine code.
    """
    pokes: Dict[int, int] = {}
    seeds: List[int] = []
    for _, text in basic_lines:
        for m in re.finditer(r"\bPOKE\s*(\d+)\s*,\s*(\d+)", text, re.IGNORECASE):
            addr = int(m.group(1))
            val = int(m.group(2))
            if 0 <= addr <= 0xFFFF and 0 <= val <= 0xFF:
                pokes[addr] = val

    # Vector pairs (lo_addr, hi_addr) commonly poked by BASIC loaders
    vector_pairs = [
        (65534, 65535),  # $FFFE/$FFFF Hardware IRQ vector
        (65530, 65531),  # $FFFA/$FFFB Hardware NMI vector
        (65532, 65533),  # $FFFC/$FFFD Hardware Reset vector
        (788, 789),      # $0314/$0315 RAM IRQ vector
        (790, 791),      # $0316/$0317 RAM BRK vector
        (792, 793),      # $0318/$0319 RAM NMI vector
        (768, 769),      # $0300/$0301 BASIC IERROR vector
        (770, 771),      # $0302/$0303 BASIC IMAIN vector
    ]
    for lo_addr, hi_addr in vector_pairs:
        if lo_addr in pokes and hi_addr in pokes:
            target = pokes[lo_addr] | (pokes[hi_addr] << 8)
            if load_address <= target < end_address and target not in seeds:
                seeds.append(target)
                # Many loaders (like Bruce Lee) have a companion NMI/IRQ routine right after
                # the first vector handler or referenced nearby.
    return seeds


def _detect_vector_table_region(
    payload: bytes,
    load_address: int,
) -> Tuple[int, Dict[int, int]]:
    """
    If a program loads into the C64 RAM vector area ($0300..$0333), such as Donkey Kong's
    loader at $0316, identify the 16-bit vectors in $0300..$0333 so we emit `.word` entries
    instead of misinterpreting vector addresses as opcodes.

    Returns:
        Tuple of (code_start_offset_after_vectors, {vector_addr: target_16bit_addr})
    """
    end_address = load_address + len(payload)
    if not (0x0300 <= load_address <= 0x0332):
        return 0, {}

    vectors: Dict[int, int] = {}
    vec_end = min(0x0334, end_address)
    addr = load_address
    while addr + 2 <= vec_end:
        off = addr - load_address
        target = payload[off] | (payload[off + 1] << 8)
        vectors[addr] = target
        addr += 2

    return (vec_end - load_address), vectors


def _is_plausible_code_run(
    payload: bytes,
    load_address: int,
    start_addr: int,
    known_instructions: Dict[int, DisassembledInstruction],
    min_instructions: int = 4,
) -> bool:
    """
    Verify whether `start_addr` begins a valid, plausible sequence of 6502 instructions
    that terminates cleanly (`RTS`, `RTI`, `JMP`, conditional branch + valid follow, or
    reaches already-verified instructions) without encountering illegal opcodes, `BRK`,
    or graphics/sprite padding runs ($FF / $00).
    """
    end_address = load_address + len(payload)
    start_off = start_addr - load_address
    if start_off < 0 or start_off + 4 > len(payload):
        return False

    # Graphics/sprite data often contains repeated $FF or $00 bytes mixed with $20 (space = JSR)
    window = payload[start_off : min(len(payload), start_off + 12)]
    if window.count(0xFF) >= 4 or window.count(0x00) >= 5:
        return False

    pc = start_addr
    count = 0
    zero_page_or_hw_refs = 0

    while load_address <= pc < end_address and count < 48:
        if pc in known_instructions:
            return count >= 2

        off = pc - load_address
        opcode = payload[off]
        # Exclude BRK (0x00) and undocumented 2-byte NOPs (0x80, 0x89) during heuristic scans
        if opcode in {0x00, 0x80, 0x89}:
            return False
        spec = _OPCODES.get(opcode)
        if spec is None:
            return False

        mnemonic, mode = spec
        size = _MODE_SIZE[mode]
        if off + size > len(payload):
            return False

        operand = payload[off + 1 : off + size]
        if mode in {"abs", "absx", "absy"} and len(operand) == 2:
            val = operand[0] | (operand[1] << 8)
            if val == 0xFFFF or val == 0x0000:
                return False
            if (0xD000 <= val <= 0xDFFF) or (0xFF81 <= val <= 0xFFF3) or (load_address <= val < end_address):
                zero_page_or_hw_refs += 1
        elif mode in {"zp", "zpx", "zpy"}:
            if operand[0] != 0xFF:
                zero_page_or_hw_refs += 1

        count += 1
        pc += size

        if mnemonic in {"RTS", "RTI", "JMP"}:
            return count >= min_instructions and zero_page_or_hw_refs >= 1

    return count >= max(min_instructions, 6) and zero_page_or_hw_refs >= 2


def _discover_irq_and_helper_seeds(
    payload: bytes,
    load_address: int,
    instructions: Dict[int, DisassembledInstruction],
) -> List[int]:
    """
    Scan already-decoded instructions (and nearby bytes) for:
    1. Vector writes (`LDA #<addr; STA $0314` / `LDX #>addr; STX $0315` or `$FFFE/$FFFF` or `$0318/$0319`)
    2. Classic 6502 initialization prologues (`SEI; CLD`, `LDX #$FF; TXS`, `SEI; LDA #`, `SEI; LDX #`)
    3. Adjacent subroutine entry points immediately following `RTS`/`RTI`/`JMP`
    4. `JSR $xxxx` calls to in-range addresses across the binary
    """
    end_address = load_address + len(payload)
    new_seeds: List[int] = []

    def in_range(a: int) -> bool:
        return load_address <= a < end_address

    # 1. Track immediate loads written to vector registers ($0314/$0315, $0318/$0319, $FFFE/$FFFF, $FFFA/$FFFB)
    sorted_addrs = sorted(instructions.keys())
    imm_reg: Dict[str, int] = {}
    vec_writes: Dict[int, int] = {}

    for addr in sorted_addrs:
        ins = instructions[addr]
        if ins.mode == "imm" and ins.mnemonic in {"LDA", "LDX", "LDY"}:
            imm_reg[ins.mnemonic[-1]] = ins.operand[0]
        elif ins.mode == "abs" and ins.mnemonic in {"STA", "STX", "STY"}:
            reg = ins.mnemonic[-1]
            dest = ins.operand[0] | (ins.operand[1] << 8)
            if reg in imm_reg and dest in {0x0314, 0x0315, 0x0316, 0x0317, 0x0318, 0x0319, 0xFFFA, 0xFFFB, 0xFFFE, 0xFFFF}:
                vec_writes[dest] = imm_reg[reg]

    for lo_vec, hi_vec in [(0x0314, 0x0315), (0x0316, 0x0317), (0x0318, 0x0319), (0xFFFA, 0xFFFB), (0xFFFE, 0xFFFF)]:
        if lo_vec in vec_writes and hi_vec in vec_writes:
            target = vec_writes[lo_vec] | (vec_writes[hi_vec] << 8)
            if in_range(target) and target not in instructions and target not in new_seeds:
                new_seeds.append(target)

    # 2. Scan for classic 6502 entry-point prologues (e.g. $0900 `SEI; CLD; LDX #$FF; TXS` in Bruce Lee)
    for off in range(0, len(payload) - 6):
        b0, b1, b2 = payload[off], payload[off + 1], payload[off + 2]
        if (b0 == 0x78 and b1 in {0xD8, 0xA9, 0xA2, 0xA0}) or (b0 == 0xA2 and b1 == 0xFF and b2 == 0x9A):
            cand = load_address + off
            if cand not in instructions and cand not in new_seeds:
                if _is_plausible_code_run(payload, load_address, cand, instructions, min_instructions=4):
                    new_seeds.append(cand)

    # 3. Check bytes immediately after RTS / RTI / JMP instructions
    for addr in sorted_addrs:
        ins = instructions[addr]
        if ins.mnemonic in {"RTS", "RTI", "JMP"}:
            cand = addr + ins.size
            if in_range(cand) and cand not in instructions and cand not in new_seeds:
                if _is_plausible_code_run(payload, load_address, cand, instructions, min_instructions=3):
                    new_seeds.append(cand)

    # 4. Scan binary for `JSR $xxxx` (0x20 lo hi) pointing inside [load_address, end_address)
    # where both caller and target are inside plausible 6502 code runs
    for off in range(0, len(payload) - 2):
        if payload[off] == 0x20:  # JSR abs
            target = payload[off + 1] | (payload[off + 2] << 8)
            caller = load_address + off
            if in_range(target) and target not in instructions and target not in new_seeds:
                if _is_plausible_code_run(payload, load_address, caller, instructions, min_instructions=4) and \
                   _is_plausible_code_run(payload, load_address, target, instructions, min_instructions=3):
                    new_seeds.append(target)
                    if caller not in instructions and caller not in new_seeds:
                        new_seeds.append(caller)

    return new_seeds


def _disassemble_reachable(
    payload: bytes,
    load_address: int,
    seeds: List[int],
    reserved_Before_offset: int = 0,
) -> Tuple[Dict[int, DisassembledInstruction], Set[int], List[str]]:
    """
    Follow 6502 control flow from seed entry points and iteratively discover helper
    subroutines, IRQ handlers, and jump-table targets.
    """
    end_address = load_address + len(payload)
    min_code_addr = load_address + reserved_Before_offset

    def in_range(addr: int) -> bool:
        return min_code_addr <= addr < end_address

    queue = [s for s in seeds if in_range(s)]
    instructions: Dict[int, DisassembledInstruction] = {}
    occupied: Set[int] = set(range(load_address, min_code_addr))
    targets: Set[int] = set(queue)
    warnings: List[str] = []

    for s in seeds:
        if not (load_address <= s < end_address):
            warnings.append(f"Entry point ${s:04X} lies outside program memory (${load_address:04X}-${end_address:04X})")

    # Iterative control-flow + subroutine discovery loop (up to 6 passes)
    for _pass in range(6):
        while queue:
            pc = queue.pop(0)
            while in_range(pc) and pc not in instructions:
                offset = pc - load_address
                opcode = payload[offset]
                # Stop at BRK (0x00) if we already decoded instructions in this run
                if opcode == 0x00 and pc not in seeds:
                    break
                spec = _OPCODES.get(opcode)
                if spec is None:
                    break

                mnemonic, mode = spec
                size = _MODE_SIZE[mode]
                if offset + size > len(payload):
                    break

                byte_range = set(range(pc, pc + size))
                if occupied & byte_range:
                    break

                operand = payload[offset + 1 : offset + size]
                ins = DisassembledInstruction(pc, opcode, mnemonic, mode, operand)
                instructions[pc] = ins
                occupied.update(byte_range)

                target: Optional[int] = None
                if mode == "rel":
                    disp = operand[0] if operand[0] < 0x80 else operand[0] - 0x100
                    target = (pc + 2 + disp) & 0xFFFF
                elif mode == "abs" and mnemonic in {"JMP", "JSR"}:
                    target = operand[0] | (operand[1] << 8)

                if target is not None and in_range(target):
                    targets.add(target)
                    if target not in instructions:
                        queue.append(target)

                pc += size
                if mnemonic in _TERMINATORS or mnemonic == "JMP":
                    break

        extra_seeds = _discover_irq_and_helper_seeds(payload, load_address, instructions)
        extra_seeds = [s for s in extra_seeds if in_range(s) and s not in occupied]
        if not extra_seeds:
            break
        for s in extra_seeds:
            targets.add(s)
            queue.append(s)

    return instructions, targets, warnings


def _analyze_call_graph(
    instructions: Dict[int, DisassembledInstruction],
    seeds: List[int],
    sys_address: Optional[int],
) -> Tuple[Set[int], Set[int], Dict[int, List[int]]]:
    """
    Classify target addresses into:
    - `jsr_targets`: Subroutine entry points called via `JSR`
    - `irq_targets`: Interrupt handlers (ending in `RTI`, jumping to `$EA31`/`$EA81`, or vector seeds)
    - `callers_of`: Mapping `target_addr -> sorted list of caller addresses`
    """
    jsr_targets: Set[int] = set()
    irq_targets: Set[int] = set()
    callers_of: Dict[int, List[int]] = {}

    for addr, ins in sorted(instructions.items()):
        target: Optional[int] = None
        if ins.mode == "abs" and ins.mnemonic in {"JSR", "JMP"}:
            target = ins.operand[0] | (ins.operand[1] << 8)
            if ins.mnemonic == "JSR":
                jsr_targets.add(target)
        elif ins.mode == "rel":
            disp = ins.operand[0] if ins.operand[0] < 0x80 else ins.operand[0] - 0x100
            target = (addr + 2 + disp) & 0xFFFF

        if target is not None:
            callers_of.setdefault(target, [])
            if addr not in callers_of[target]:
                callers_of[target].append(addr)

    # Identify routines that end with RTI or jump to KERNAL IRQ exit ($EA31 / $EA81)
    sorted_addrs = sorted(instructions.keys())
    for seed in seeds:
        if seed == sys_address:
            continue
        # Walk up to 64 instructions from seed to see if it finishes with RTI or JMP $EA31/$EA81
        pc = seed
        for _ in range(64):
            ins = instructions.get(pc)
            if ins is None:
                break
            if ins.mnemonic == "RTI":
                irq_targets.add(seed)
                break
            if ins.mnemonic == "JMP" and ins.mode == "abs":
                jmp_dest = ins.operand[0] | (ins.operand[1] << 8)
                if jmp_dest in {0xEA31, 0xEA81, 0xFE47}:
                    irq_targets.add(seed)
                    break
                break
            if ins.mnemonic == "RTS":
                break
            pc += ins.size

    return jsr_targets, irq_targets, callers_of


def _build_label_map(
    load_address: int,
    targets: Set[int],
    instructions: Dict[int, DisassembledInstruction],
    sys_address: Optional[int],
    jsr_targets: Optional[Set[int]] = None,
    irq_targets: Optional[Set[int]] = None,
) -> Dict[int, str]:
    """Generate meaningful labels (`entry_main`, `irq_handler_xxxx`, `sub_xxxx`, `loc_xxxx`)."""
    operand_bytes = {
        addr
        for ins in instructions.values()
        for addr in range(ins.address + 1, ins.address + ins.size)
    }
    jsr_set = jsr_targets or set()
    irq_set = irq_targets or set()

    labels: Dict[int, str] = {}
    for addr in sorted(targets):
        if addr in operand_bytes:
            continue
        if addr in irq_set:
            labels[addr] = f"irq_handler_{addr:04x}"
        elif addr in jsr_set:
            labels[addr] = f"sub_{addr:04x}"
        else:
            labels[addr] = f"loc_{addr:04x}"

    if sys_address is not None and sys_address not in operand_bytes:
        labels[sys_address] = "entry_main"
    elif load_address in labels and load_address not in irq_set:
        labels[load_address] = "start"

    return labels


def _explain_instruction(
    ins: DisassembledInstruction,
    prev_ins: Optional[DisassembledInstruction],
) -> Optional[str]:
    """
    Generate a rich, human-readable inline explanation of what a 6502 instruction is doing
    on the Commodore 64 (hardware registers, immediate values, banking bits, colors, CPU flags).
    """
    mode = ins.mode
    mnem = ins.mnemonic
    raw = ins.operand
    val = (raw[0] | (raw[1] << 8)) if len(raw) == 2 else (raw[0] if raw else 0)

    # Track immediate value loaded in the immediately preceding instruction (e.g. LDA #$xx -> STA $xxxx)
    imm_prev: Optional[int] = None
    if prev_ins is not None and prev_ins.mode == "imm" and prev_ins.mnemonic in {"LDA", "LDX", "LDY"}:
        if (mnem in {"STA", "STX", "STY"} and mnem[-1] == prev_ins.mnemonic[-1]) or (mnem == "JSR" and prev_ins.mnemonic == "LDA"):
            imm_prev = prev_ins.operand[0]

    # 1. Implied CPU Status / Control Instructions
    if mode == "imp":
        imp_notes = {
            "SEI": "Disable maskable IRQ interrupts (prevent KERNAL/timer interruption)",
            "CLI": "Re-enable maskable IRQ interrupts",
            "CLD": "Clear Decimal Mode flag (ensure standard binary 6502 arithmetic)",
            "SED": "Enable BCD Decimal Mode arithmetic (often used for score counters)",
            "CLC": "Clear Carry flag before ADC addition or bit rotation",
            "SEC": "Set Carry flag before SBC subtraction or bit rotation",
            "PHA": "Push Accumulator (A) onto hardware stack ($0100-$01FF)",
            "PLA": "Pull Accumulator (A) from hardware stack ($0100-$01FF)",
            "PHP": "Push Processor Status flags onto stack",
            "PLP": "Restore Processor Status flags from stack",
            "RTI": "Return from Interrupt (restores CPU status flags & PC from stack)",
            "RTS": "Return from Subroutine to caller",
        }
        return imp_notes.get(mnem)

    # 2. Indirect Jump `JMP ($xxxx)`
    if mode == "ind" and mnem == "JMP":
        if val in C64_RAM_VECTORS:
            return f"Indirect jump via {C64_RAM_VECTORS[val]}"
        return f"Indirect jump through 16-bit pointer at ${val:04X}-${val+1:04X}"

    # 3. Absolute / Zero-Page Memory & Hardware Register Access
    if mode in {"abs", "absx", "absy", "zp", "zpx", "zpy"}:
        base_note = HARDWARE_REGISTERS.get(val)
        detail = ""

        # 6510 CPU Banking Port ($01)
        if val == 0x0001 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            loram = imm_prev & 1
            hiram = (imm_prev >> 1) & 1
            charen = (imm_prev >> 2) & 1
            if (loram, hiram, charen) == (1, 1, 1):
                detail = f"Set ${imm_prev:02X}: Default C64 map (BASIC ROM + KERNAL ROM + I/O active)"
            elif (loram, hiram, charen) == (0, 1, 1):
                detail = f"Set ${imm_prev:02X}: Bank out BASIC ROM ($A000-$BFFF -> RAM); keep KERNAL & I/O active"
            elif (loram, hiram, charen) == (1, 0, 1) or (loram, hiram, charen) == (0, 0, 1):
                detail = f"Set ${imm_prev:02X}: Bank out BASIC & KERNAL ROMs; expose RAM + I/O ($D000-$DFFF)"
            elif charen == 0 and (loram or hiram):
                detail = f"Set ${imm_prev:02X}: Map Character Generator ROM into $D000-$DFFF"
            elif (loram, hiram, charen) == (0, 0, 0):
                detail = f"Set ${imm_prev:02X}: Expose all 64KB RAM ($0000-$FFFF, I/O & ROMs banked out)"

        # VIC-II Color Registers ($D020 - $D02E)
        elif 0xD020 <= val <= 0xD02E and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            cname = C64_COLOR_NAMES.get(imm_prev & 0x0F, f"Color {imm_prev & 0x0F}")
            detail = f"Set color to {cname} (${imm_prev & 0x0F:02X})"

        # VIC-II Control Register 1 ($D011)
        elif val == 0xD011 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            scr_on = "Screen ON" if (imm_prev & 0x10) else "Blank Screen (hide display for fast load/init)"
            bmm = "Bitmap Mode" if (imm_prev & 0x20) else "Text/Tile Mode"
            rows = "25 Rows" if (imm_prev & 0x08) else "24 Rows"
            detail = f"${imm_prev:02X} -> {scr_on}, {bmm}, {rows}, Y-Scroll={imm_prev & 7}"

        # VIC-II Control Register 2 ($D016)
        elif val == 0xD016 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            mcm = "Multicolor ON" if (imm_prev & 0x10) else "Hi-Res Standard Mode"
            cols = "40 Columns" if (imm_prev & 0x08) else "38 Columns"
            detail = f"${imm_prev:02X} -> {mcm}, {cols}, X-Scroll={imm_prev & 7}"

        # VIC-II Memory Pointers ($D018)
        elif val == 0xD018 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            scr_ofs = ((imm_prev >> 4) & 0x0F) * 0x0400
            chr_ofs = ((imm_prev >> 1) & 0x07) * 0x0800
            detail = f"${imm_prev:02X} -> Screen offset +${scr_ofs:04X}, Charset/Bitmap offset +${chr_ofs:04X}"

        # VIC-II Sprite Enable ($D015)
        elif val == 0xD015 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            if imm_prev == 0:
                detail = "Disable all 8 hardware sprites"
            else:
                enabled = [str(i) for i in range(8) if imm_prev & (1 << i)]
                detail = f"Enable Sprite(s): {', '.join(enabled)}"

        # VIC-II Interrupt Status ($D019)
        elif val == 0xD019 and mnem in {"STA", "ASL", "LSR", "DEC", "INC"}:
            detail = "Acknowledge VIC-II Raster/Sprite interrupt flag"

        # SID Voice Control ($D404, $D40B, $D412)
        elif val in {0xD404, 0xD40B, 0xD412} and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            waves = []
            if imm_prev & 0x80: waves.append("Noise")
            if imm_prev & 0x40: waves.append("Pulse")
            if imm_prev & 0x20: waves.append("Sawtooth")
            if imm_prev & 0x10: waves.append("Triangle")
            gate = "Gate ON (Attack/Sustain)" if (imm_prev & 0x01) else "Gate OFF (Release)"
            w_str = "+".join(waves) if waves else "No Waveform"
            detail = f"${imm_prev:02X} -> {w_str}, {gate}"

        # SID Volume & Filter Mode ($D418)
        elif val == 0xD418 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            vol = imm_prev & 0x0F
            fmodes = []
            if imm_prev & 0x10: fmodes.append("Low-Pass")
            if imm_prev & 0x20: fmodes.append("Band-Pass")
            if imm_prev & 0x40: fmodes.append("High-Pass")
            f_str = f"Filter: {'/'.join(fmodes)}" if fmodes else "No Filter"
            detail = f"Master Volume = {vol}/15 ({f_str})"

        # CIA Interrupt Control ($DC0D / $DD0D)
        elif val in {0xDC0D, 0xDD0D} and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            if imm_prev == 0x7F:
                detail = "Disable all CIA timer interrupt sources ($7F)"
            elif imm_prev & 0x80:
                detail = f"Enable CIA interrupt mask (${imm_prev:02X})"

        # CIA2 Port A VIC-II Bank ($DD00)
        elif val == 0xDD00 and mnem in {"STA", "STX", "STY"} and imm_prev is not None:
            bank_idx = 3 - (imm_prev & 0x03)
            bank_base = bank_idx * 0x4000
            detail = f"Select VIC-II 16KB Bank {bank_idx} (${bank_base:04X}-${bank_base+0x3FFF:04X})"

        # KERNAL CHROUT ($FFD2) with immediate character
        elif val == 0xFFD2 and mnem == "JSR" and imm_prev is not None:
            petscii_ctrl = {
                0x93: "Clear Screen (CLR)", 0x13: "Cursor Home", 0x0E: "Switch to Lowercase/Uppercase Charset",
                0x8E: "Switch to Uppercase/Graphics Charset", 0x0D: "Carriage Return",
                0x05: "White Text", 0x1C: "Red Text", 0x1E: "Green Text", 0x1F: "Blue Text",
                0x90: "Black Text", 0x9E: "Yellow Text", 0x9F: "Cyan Text",
            }
            if imm_prev in petscii_ctrl:
                detail = f"Print PETSCII ${imm_prev:02X}: {petscii_ctrl[imm_prev]}"
            elif 0x20 <= imm_prev <= 0x5F:
                detail = f"Print character '{chr(imm_prev)}'"

        if base_note and detail:
            return f"{base_note} -- {detail}"
        if base_note:
            return base_note

        # Memory region annotations for Screen RAM, Sprite Pointers, Color RAM, Tape Buffer
        if 0x07F8 <= val <= 0x07FF:
            return f"Default Screen Sprite {val - 0x07F8} Shape Pointer"
        if 0x0400 <= val <= 0x07E7:
            row, col = divmod(val - 0x0400, 40)
            return f"Default Screen Matrix RAM ($0400 + {val - 0x0400}, Row {row} Col {col})"
        if 0xD800 <= val <= 0xDBE7:
            row, col = divmod(val - 0xD800, 40)
            return f"VIC-II Color RAM ($D800 + {val - 0xD800}, Row {row} Col {col})"
        if 0xD400 < val <= 0xD41C:
            return f"SID Sound Synthesizer Register (${val:04X})"
        if 0x033C <= val <= 0x03FB:
            return f"Cassette Tape Buffer TBUFFR (${val:04X}, offset +{val - 0x033C})"
        if 0xA000 <= val <= 0xBFFF and mnem in {"JMP", "JSR"}:
            return f"Call BASIC ROM Routine (${val:04X})"
        if 0xE000 <= val <= 0xFFF9 and mnem in {"JMP", "JSR"}:
            return f"Call KERNAL ROM Internal Routine (${val:04X})"

    return None


def _summarize_routine_subsystems(
    start_addr: int,
    instructions: Dict[int, DisassembledInstruction],
) -> List[str]:
    """Scan up to 40 instructions of a routine starting at `start_addr` and summarize its purpose."""
    tags: List[str] = []
    pc = start_addr
    for _ in range(40):
        ins = instructions.get(pc)
        if ins is None:
            break
        if ins.mode in {"abs", "absx", "absy"} and len(ins.operand) == 2:
            val = ins.operand[0] | (ins.operand[1] << 8)
            if 0xD000 <= val <= 0xD010 or val in {0xD015, 0xD017, 0xD01B, 0xD01C, 0xD01D} or 0xD025 <= val <= 0xD02E:
                if "VIC-II Sprites" not in tags:
                    tags.append("VIC-II Sprites")
            elif val in {0xD011, 0xD012, 0xD016, 0xD018, 0xD019, 0xD01A, 0xD020, 0xD021, 0xD022, 0xD023}:
                if "VIC-II Video/Raster" not in tags:
                    tags.append("VIC-II Video/Raster")
            elif 0xD400 <= val <= 0xD41C:
                if "SID Audio" not in tags:
                    tags.append("SID Audio")
            elif 0xD800 <= val <= 0xDBE7 or 0x0400 <= val <= 0x07E7:
                if "Screen/Color RAM" not in tags:
                    tags.append("Screen/Color RAM")
            elif 0xDC00 <= val <= 0xDC01:
                if "Joystick/Keyboard Input" not in tags:
                    tags.append("Joystick/Keyboard Input")
            elif 0xDC04 <= val <= 0xDC0F or 0xDD04 <= val <= 0xDD0F:
                if "CIA Timers/IRQ" not in tags:
                    tags.append("CIA Timers/IRQ")
            elif val == 0xDD00:
                if "VIC-II Bank Select" not in tags:
                    tags.append("VIC-II Bank Select")
            elif val in {0x0314, 0x0315, 0x0318, 0x0319, 0xFFFE, 0xFFFF, 0xFFFA, 0xFFFB}:
                if "Interrupt Vector Setup" not in tags:
                    tags.append("Interrupt Vector Setup")
            elif 0xFF81 <= val <= 0xFFF3:
                if "KERNAL OS API" not in tags:
                    tags.append("KERNAL OS API")
        elif ins.mode in {"zp", "zpx", "zpy"} and ins.operand[0] == 0x01:
            if "6510 Memory Banking ($01)" not in tags:
                tags.append("6510 Memory Banking ($01)")

        pc += ins.size
        if ins.mnemonic in {"RTS", "RTI", "JMP"}:
            break
    return tags


def _build_architecture_overview(
    name: str,
    load_address: int,
    end_address: int,
    instructions: Dict[int, DisassembledInstruction],
    basic_lines: List[Tuple[int, str]],
    sys_address: Optional[int],
    jsr_targets: Set[int],
    irq_targets: Set[int],
    vectors_table: Dict[int, int],
) -> List[str]:
    """Generate a high-level architectural overview comment block explaining how the program works."""
    subsystems: Set[str] = set()
    kernal_calls: Set[str] = set()

    for ins in instructions.values():
        if ins.mode in {"abs", "absx", "absy"} and len(ins.operand) == 2:
            val = ins.operand[0] | (ins.operand[1] << 8)
            if 0xD000 <= val <= 0xD02E:
                subsystems.add("MOS 6569/6567 VIC-II Video Controller ($D000-$D02E)")
            elif 0xD400 <= val <= 0xD41C:
                subsystems.add("MOS 6581/8580 SID Sound Synthesizer ($D400-$D41C)")
            elif 0xD800 <= val <= 0xDBE7:
                subsystems.add("VIC-II 40x25 Color RAM Matrix ($D800-$DBE7)")
            elif 0xDC00 <= val <= 0xDC0F:
                subsystems.add("MOS 6526 CIA #1 (Joysticks, Keyboard, IRQ Timers, Tape Pulses)")
            elif 0xDD00 <= val <= 0xDD0F:
                subsystems.add("MOS 6526 CIA #2 (VIC-II 16KB Bank Switching, NMI Timers, Serial IEC)")
            elif 0xFF81 <= val <= 0xFFF3 and ins.mnemonic in {"JSR", "JMP"}:
                kname = HARDWARE_REGISTERS.get(val, f"${val:04X}").split(" (")[0]
                kernal_calls.add(f"${val:04X} {kname}")
        elif ins.mode in {"zp", "zpx", "zpy"} and ins.operand[0] == 0x01:
            subsystems.add("MOS 6510 CPU Port ($01 RAM/ROM/IO Bank Switching & Cassette Control)")

    lines = [
        "// " + "-" * 76,
        f"// PROGRAM ARCHITECTURE & HARDWARE ANALYSIS -- {name}",
        "// " + "-" * 76,
        f"// * Memory Footprint : ${load_address:04X} - ${end_address:04X} ({end_address - load_address:,} bytes)",
        f"// * Disassembled Code: {len(instructions):,} 6502 instructions, {len(jsr_targets)} subroutines, {len(irq_targets)} IRQ/NMI handlers",
    ]
    if sys_address is not None:
        lines.append(f"// * Execution Entry  : BASIC stub launches machine code via SYS ${sys_address:04X} ({sys_address})")
    elif vectors_table:
        lines.append(f"// * Execution Entry  : Overwrites C64 RAM vector table (${min(vectors_table):04X}-${max(vectors_table)+1:04X}) for autostart")

    if subsystems:
        lines.append("// * Hardware Chips Used:")
        for s in sorted(subsystems):
            lines.append(f"//     - {s}")
    if kernal_calls:
        lines.append(f"// * KERNAL ROM Calls : {', '.join(sorted(kernal_calls)[:6])}")
    lines.append("// " + "-" * 76)
    return lines


def _format_instruction(
    ins: DisassembledInstruction,
    labels: Dict[int, str],
    prev_ins: Optional[DisassembledInstruction] = None,
) -> str:
    mode = ins.mode
    raw = ins.operand
    val = (raw[0] | (raw[1] << 8)) if len(raw) == 2 else (raw[0] if raw else 0)

    if mode in {"imp", "acc"}:
        op_str = ""
    elif mode == "imm":
        op_str = f"#${val:02x}"
    elif mode == "zp":
        op_str = f"${val:02x}"
    elif mode == "zpx":
        op_str = f"${val:02x},x"
    elif mode == "zpy":
        op_str = f"${val:02x},y"
    elif mode == "indx":
        op_str = f"(${val:02x},x)"
    elif mode == "indy":
        op_str = f"(${val:02x}),y"
    elif mode == "rel":
        disp = val if val < 0x80 else val - 0x100
        target = (ins.address + 2 + disp) & 0xFFFF
        op_str = labels.get(target, f"${target:04x}")
    elif mode == "ind":
        op_str = f"(${val:04x})"
    else:  # abs, absx, absy
        target_label = labels.get(val) if ins.mnemonic in {"JMP", "JSR"} else None
        op_str = target_label or f"${val:04x}"
        if mode == "absx":
            op_str += ",x"
        elif mode == "absy":
            op_str += ",y"

    text = f"    {ins.mnemonic.lower():<4} {op_str}".rstrip()

    explanation = _explain_instruction(ins, prev_ins)
    if explanation:
        text = f"{text:<28} // {explanation}"

    return text


def _render_asm_body(
    payload: bytes,
    load_address: int,
    instructions: Dict[int, DisassembledInstruction],
    labels: Dict[int, str],
    start_offset: int = 0,
    jsr_targets: Optional[Set[int]] = None,
    irq_targets: Optional[Set[int]] = None,
    callers_of: Optional[Dict[int, List[int]]] = None,
    vectors_table: Optional[Dict[int, int]] = None,
) -> List[str]:
    lines: List[str] = []
    end = load_address + len(payload)
    pc = load_address + start_offset
    jsr_set = jsr_targets or set()
    irq_set = irq_targets or set()
    callers = callers_of or {}
    vec_map = vectors_table or {}
    prev_ins: Optional[DisassembledInstruction] = None

    while pc < end:
        # 1. If this address is part of a C64 RAM Vector Table ($0300-$0333), emit `.word` with explanation
        if pc in vec_map and pc + 2 <= end:
            target = vec_map[pc]
            vec_desc = C64_RAM_VECTORS.get(pc, f"RAM Vector ${pc:04X}")
            target_lbl = labels.get(target, f"${target:04x}")
            lines.append(f"    .word {target_lbl:<18} // ${pc:04X}: {vec_desc} -> ${target:04X}")
            pc += 2
            prev_ins = None
            continue

        # 2. Emit label and explanatory routine banner if `pc` is a known target
        if pc in labels:
            lbl = labels[pc]
            if lines and lines[-1] != "":
                lines.append("")

            if lbl == "entry_main" or lbl == "start":
                tags = _summarize_routine_subsystems(pc, instructions)
                tag_str = f" | Touches: {', '.join(tags)}" if tags else ""
                lines.append(f"// --- Main Entry Point (${pc:04X}){tag_str} ---")
            elif pc in irq_set or lbl.startswith("irq_handler_"):
                tags = _summarize_routine_subsystems(pc, instructions)
                tag_str = f" | Touches: {', '.join(tags)}" if tags else ""
                lines.append(f"// === Hardware / Raster Interrupt Service Routine (${pc:04X}){tag_str} ===")
            elif pc in jsr_set or lbl.startswith("sub_"):
                caller_list = callers.get(pc, [])
                caller_str = ", ".join(f"${c:04X}" for c in caller_list[:6])
                if len(caller_list) > 6:
                    caller_str += f" (+{len(caller_list) - 6} more)"
                tags = _summarize_routine_subsystems(pc, instructions)
                meta = []
                if caller_str:
                    meta.append(f"Called from: {caller_str}")
                if tags:
                    meta.append(f"Subsystems: {', '.join(tags)}")
                meta_str = f" ({' | '.join(meta)})" if meta else ""
                lines.append(f"// --- Subroutine {lbl} @ ${pc:04X}{meta_str} ---")

            lines.append(f"{lbl}:")

        # 3. Emit disassembled instruction if present
        ins = instructions.get(pc)
        if ins is not None:
            lines.append(_format_instruction(ins, labels, prev_ins))
            prev_ins = ins
            pc += ins.size
            continue

        # 4. Otherwise emit consecutive data bytes (with ASCII preview comment when printable)
        prev_ins = None
        chunk_start = pc
        chunk: List[int] = []
        while pc < end and len(chunk) < 16:
            if chunk and (pc in instructions or pc in labels or pc in vec_map):
                break
            chunk.append(payload[pc - load_address])
            pc += 1
            if pc in instructions or pc in labels or pc in vec_map:
                break

        hex_str = ", ".join(f"${b:02x}" for b in chunk)
        ascii_chars = "".join(chr(b) if 0x20 <= b <= 0x5F else "." for b in chunk)
        printable_count = sum(1 for b in chunk if (0x20 <= b <= 0x5F and b != 0x20))
        if printable_count >= 4:
            lines.append(f"    .byte {hex_str}  // ${chunk_start:04X}: \"{ascii_chars}\"")
        else:
            lines.append(f"    .byte {hex_str}  // ${chunk_start:04X}")

    return lines


def decompile_prg(
    prg_data: bytes,
    name: str = "PROGRAM",
    extra_entry_points: Optional[List[int]] = None,
    stage_description: Optional[str] = None,
) -> PrgDecompileResult:
    """
    Decompile raw Commodore PRG binary bytes into richly commented KickAssembler and Python source.

    Args:
        prg_data: Raw PRG bytes (starts with 2-byte little-endian load address).
        name: Program name label.
        extra_entry_points: Optional additional known 6502 entry points (e.g. from turbo tape loader).
        stage_description: Optional human-readable description of this stage (e.g. Loader vs Main Game).
    """
    if len(prg_data) < 2:
        raise ValueError("Invalid PRG: File is shorter than 2 bytes.")

    load_address = prg_data[0] | (prg_data[1] << 8)
    payload = prg_data[2:]
    end_address = load_address + len(payload)

    basic_lines: List[Tuple[int, str]] = []
    sys_address: Optional[int] = None
    basic_bytes_len = 0

    # 1. Check for C64 BASIC program header at $0801 or $0800
    if load_address in {0x0800, 0x0801}:
        basic_lines, sys_address, basic_bytes_len = detokenize_basic(payload, load_address)

    # 2. Check if the binary loads over the C64 RAM Vector Table ($0300-$0333)
    vec_offset, vectors_table = _detect_vector_table_region(payload, load_address)

    # 3. Determine seed entry points
    seeds: List[int] = []
    if sys_address is not None and load_address <= sys_address < end_address:
        seeds.append(sys_address)

    # Add seeds discovered from BASIC POKE vector pairs (e.g. Bruce Lee POKE 65535,17: POKE 65534,3)
    for poke_seed in _extract_basic_poke_seeds(basic_lines, load_address, end_address):
        if poke_seed not in seeds:
            seeds.append(poke_seed)

    # Add seeds from RAM vector table entries (e.g. Donkey Kong $0316 -> $0363)
    for vec_target in vectors_table.values():
        if load_address <= vec_target < end_address and vec_target not in seeds:
            seeds.append(vec_target)

    # Add caller-supplied entry points (e.g. TapStage entry_points)
    if extra_entry_points:
        for ep in extra_entry_points:
            if load_address <= ep < end_address and ep not in seeds:
                seeds.append(ep)

    # If BASIC program has machine code immediately after the BASIC lines (even without a literal SYS number)
    if basic_lines and basic_bytes_len > 0 and (load_address + basic_bytes_len) < end_address:
        post_basic = load_address + basic_bytes_len
        if post_basic not in seeds and _is_plausible_code_run(payload, load_address, post_basic, {}, min_instructions=2):
            seeds.append(post_basic)

    # Fallback: seed right after any vector table or at load_address
    if not seeds:
        fallback_seed = load_address + vec_offset
        if load_address <= fallback_seed < end_address:
            seeds.append(fallback_seed)
        else:
            seeds.append(load_address)

    skip_basic_bytes = basic_bytes_len if (basic_lines and (sys_address is not None or seeds)) else 0
    reserved_offset = max(skip_basic_bytes, vec_offset)

    instructions, targets, warnings = _disassemble_reachable(
        payload,
        load_address,
        seeds,
        reserved_Before_offset=reserved_offset,
    )
    jsr_targets, irq_targets, callers_of = _analyze_call_graph(instructions, seeds, sys_address)
    labels = _build_label_map(load_address, targets, instructions, sys_address, jsr_targets, irq_targets)

    body_lines = _render_asm_body(
        payload=payload,
        load_address=load_address,
        instructions=instructions,
        labels=labels,
        start_offset=skip_basic_bytes if sys_address is not None else 0,
        jsr_targets=jsr_targets,
        irq_targets=irq_targets,
        callers_of=callers_of,
        vectors_table=vectors_table,
    )

    # 1. Build KickAssembler Source
    header_caution = [
        "// " + "=" * 76,
        "// ⚠️  ETHICAL USE & COPYRIGHT CAUTION:",
        "// This code was reverse-decompiled from a Commodore 64 program binary.",
        "// The original work may be subject to copyright.",
        "// Use this reconstructed source exclusively for technique review, educational",
        "// analysis, and self-improvement.",
        "// Do not copy someone else's hard work. Learn from it, but don't be a thief!",
        "// " + "=" * 76,
        "",
        f"// Target: MOS 6510 / VIC-II / SID | File: {name}",
        f"// Memory: ${load_address:04X} - ${end_address:04X} ({len(payload)} bytes)",
    ]
    if stage_description:
        header_caution.append(f"// Stage : {stage_description}")

    header_caution.extend(
        _build_architecture_overview(
            name=name,
            load_address=load_address,
            end_address=end_address,
            instructions=instructions,
            basic_lines=basic_lines,
            sys_address=sys_address,
            jsr_targets=jsr_targets,
            irq_targets=irq_targets,
            vectors_table=vectors_table,
        )
    )

    if basic_lines:
        header_caution.append("// Recovered BASIC V2 Listing:")
        for lno, text in basic_lines:
            header_caution.append(f"//   {lno} {text}")

    asm_lines = list(header_caution)
    asm_lines.append("")

    if sys_address is not None and basic_lines:
        entry_label = labels.get(sys_address, f"entry_${sys_address:04x}")
        code_start = sys_address if sys_address > 0x0801 else (load_address + skip_basic_bytes)
        asm_lines.extend([
            f":BasicUpstart2({entry_label})",
            "",
            f'* = ${code_start:04x} "{name} Machine Code"',
            "",
        ])
    else:
        asm_lines.extend([
            f'* = ${load_address:04x} "{name} Payload"',
            "",
        ])

    asm_lines.extend(body_lines)
    assembly_src = "\n".join(asm_lines) + "\n"

    # 2. Build Python Transpiler Source
    py_lines = [
        '"""',
        "ETHICAL USE & COPYRIGHT CAUTION:",
        "This code was reverse-decompiled from a Commodore 64 program binary.",
        "The original work may be subject to copyright.",
        "Use this reconstructed source exclusively for technique review, educational",
        "analysis, and self-improvement. Learn from it, but don't be a thief!",
        '"""',
        "",
        f"# Reverse-decompiled C64 program: {name}",
        f"LOAD_ADDRESS = 0x{load_address:04X}",
        f"END_ADDRESS = 0x{end_address:04X}",
        "",
        'asm("""',
    ]
    if sys_address is not None and basic_lines:
        entry_label = labels.get(sys_address, f"entry_${sys_address:04x}")
        code_start = sys_address if sys_address > 0x0801 else (load_address + skip_basic_bytes)
        py_lines.extend([
            f":BasicUpstart2({entry_label})",
            f'* = ${code_start:04x} "{name}"',
        ])
    else:
        py_lines.append(f'* = ${load_address:04x} "{name}"')

    py_lines.extend(body_lines)
    py_lines.extend(['""")', ""])
    python_src = "\n".join(py_lines)

    used_inst_bytes = sum(ins.size for ins in instructions.values())
    data_bytes = len(payload) - used_inst_bytes - skip_basic_bytes

    return PrgDecompileResult(
        filename=name,
        load_address=load_address,
        end_address=end_address,
        payload_size=len(payload),
        basic_lines=basic_lines,
        has_basic_sys=sys_address is not None,
        sys_address=sys_address,
        entry_points=seeds,
        assembly=assembly_src,
        python=python_src,
        instruction_count=len(instructions),
        data_byte_count=max(0, data_bytes),
        warnings=warnings,
        scope="both",
        stages_decompiled=[name],
    )


def _combine_stage_results(
    results: List[PrgDecompileResult],
    title: str,
    scope: str,
) -> PrgDecompileResult:
    """Combine one or more stage PrgDecompileResults into a unified, multi-section decompilation."""
    if not results:
        raise ValueError("No stages provided to combine.")
    if len(results) == 1:
        single = results[0]
        single.scope = scope
        return single

    # Choose the primary (largest code or main) result for top-level metadata
    primary = max(results, key=lambda r: (r.instruction_count, r.payload_size))
    combined_asm_parts: List[str] = [
        "// " + "=" * 76,
        f"// MULTI-STAGE DECOMPILATION: {title} (Scope: {scope.upper()})",
        f"// Stages Included ({len(results)}): " + ", ".join(
            f"{r.filename} (${r.load_address:04X}-${r.end_address:04X}, {r.instruction_count} insns)"
            for r in results
        ),
        "// " + "=" * 76,
        "",
    ]
    combined_py_parts: List[str] = []
    all_basic: List[Tuple[int, str]] = []
    all_entries: List[int] = []
    all_warnings: List[str] = []
    total_ins = 0
    total_data = 0
    total_payload = 0

    for idx, res in enumerate(results, 1):
        combined_asm_parts.extend([
            "// " + "#" * 76,
            f"// STAGE {idx}/{len(results)}: {res.filename} (${res.load_address:04X} - ${res.end_address:04X})",
            "// " + "#" * 76,
            res.assembly.strip(),
            "",
        ])
        combined_py_parts.append(f"# === STAGE {idx}/{len(results)}: {res.filename} ===\n" + res.python.strip())
        all_basic.extend(res.basic_lines)
        for ep in res.entry_points:
            if ep not in all_entries:
                all_entries.append(ep)
        all_warnings.extend(res.warnings)
        total_ins += res.instruction_count
        total_data += res.data_byte_count
        total_payload += res.payload_size

    return PrgDecompileResult(
        filename=title,
        load_address=primary.load_address,
        end_address=primary.end_address,
        payload_size=total_payload,
        basic_lines=all_basic,
        has_basic_sys=any(r.has_basic_sys for r in results),
        sys_address=primary.sys_address or next((r.sys_address for r in results if r.sys_address), None),
        entry_points=all_entries,
        assembly="\n".join(combined_asm_parts) + "\n",
        python="\n\n".join(combined_py_parts) + "\n",
        instruction_count=total_ins,
        data_byte_count=total_data,
        warnings=all_warnings,
        scope=scope,
        stages_decompiled=[r.filename for r in results],
    )


def inspect_media_stages(path: Union[str, Path]) -> List[MediaStageInfo]:
    """
    Inspect a `.tap`, `.d64`, or `.prg` file and return its decompilable stages
    classified as `"loader"` or `"main"`.
    Used by the UI to ask the user whether to decompile the Loader, Main Game, or Both.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")

    ext = p.suffix.lower()
    stages: List[MediaStageInfo] = []

    if ext == ".tap":
        tap_stages = extract_tap_stages(p.read_bytes())
        for idx, st in enumerate(tap_stages):
            if len(st.prg_data) < 2:
                continue
            la = st.prg_data[0] | (st.prg_data[1] << 8)
            sz = len(st.prg_data) - 2
            stages.append(
                MediaStageInfo(
                    index=idx,
                    name=st.name,
                    role=st.role,
                    load_address=la,
                    end_address=la + sz,
                    size=sz,
                    description=st.description,
                    entry_points=list(st.entry_points),
                )
            )
    elif ext == ".d64":
        disk = read_d64_file(p)
        prgs = disk.extract_all_prgs()
        if len(prgs) == 1:
            fname, fbytes = prgs[0]
            la = fbytes[0] | (fbytes[1] << 8) if len(fbytes) >= 2 else 0x0801
            sz = max(0, len(fbytes) - 2)
            stages.append(
                MediaStageInfo(
                    index=0,
                    name=fname,
                    role="main",
                    load_address=la,
                    end_address=la + sz,
                    size=sz,
                    description=f"D64 Program '{fname}' (${la:04X}-${la+sz:04X})",
                )
            )
        elif len(prgs) > 1:
            max_sz = max(len(b) for _, b in prgs)
            for idx, (fname, fbytes) in enumerate(prgs):
                la = fbytes[0] | (fbytes[1] << 8) if len(fbytes) >= 2 else 0x0801
                sz = max(0, len(fbytes) - 2)
                # First small PRG on multi-file disk is typically the boot/fastloader stub
                is_loader = (idx == 0 and len(fbytes) < max_sz * 0.6) or ("BOOT" in fname.upper() or "LOAD" in fname.upper())
                role = "loader" if is_loader else "main"
                role_label = "Disk Boot / Loader" if role == "loader" else "Main Game / Program"
                stages.append(
                    MediaStageInfo(
                        index=idx,
                        name=fname,
                        role=role,
                        load_address=la,
                        end_address=la + sz,
                        size=sz,
                        description=f"{role_label}: '{fname}' (${la:04X}-${la+sz:04X}, {sz} bytes)",
                    )
                )
    elif ext == ".prg":
        fbytes = p.read_bytes()
        la = fbytes[0] | (fbytes[1] << 8) if len(fbytes) >= 2 else 0x0801
        sz = max(0, len(fbytes) - 2)
        stages.append(
            MediaStageInfo(
                index=0,
                name=p.stem,
                role="main",
                load_address=la,
                end_address=la + sz,
                size=sz,
                description=f"PRG Executable '{p.stem}' (${la:04X}-${la+sz:04X})",
            )
        )

    return stages


def decompile_prg_file(path: Union[str, Path]) -> PrgDecompileResult:
    """Read and decompile a C64 PRG file."""
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"PRG file not found: {p}")
    return decompile_prg(p.read_bytes(), name=p.stem)


def decompile_d64_file(
    path: Union[str, Path],
    file_name_or_index: Optional[Union[str, int]] = None,
    scope: str = "both",
) -> PrgDecompileResult:
    """
    Extract and decompile PRG file(s) from a .d64 disk image.

    Args:
        path: Path to .d64 disk image.
        file_name_or_index: Specific PRG filename or 0-based index. If None, uses `scope`.
        scope: `"loader"`, `"main"`, or `"both"` (used when file_name_or_index is None).
    """
    disk = read_d64_file(path)
    prgs = disk.extract_all_prgs()
    if not prgs:
        raise ValueError(f"No PRG files found on D64 disk image: {path}")

    # If a specific file was requested by index or name, decompile that file directly
    if file_name_or_index is not None:
        selected_name = ""
        selected_prg = b""
        if isinstance(file_name_or_index, int):
            if 0 <= file_name_or_index < len(prgs):
                selected_name, selected_prg = prgs[file_name_or_index]
            else:
                raise IndexError(f"File index {file_name_or_index} out of range (disk contains {len(prgs)} PRGs)")
        else:
            target = str(file_name_or_index).strip().upper()
            for fname, fbytes in prgs:
                if fname.upper() == target:
                    selected_name = fname
                    selected_prg = fbytes
                    break
            if not selected_prg:
                raise FileNotFoundError(f"File '{file_name_or_index}' not found on D64 disk image {path}")

        res = decompile_prg(selected_prg, name=selected_name)
        res.scope = scope
        return res

    # Otherwise classify disk PRGs by role ("loader" vs "main")
    stages_meta = inspect_media_stages(path)
    norm_scope = scope.lower().strip()
    if norm_scope not in {"loader", "main", "both"}:
        norm_scope = "both"

    selected_indices = [
        st.index for st in stages_meta
        if norm_scope == "both" or st.role == norm_scope
    ]
    if not selected_indices:
        # Fallback if disk only has one role
        selected_indices = [0] if norm_scope == "loader" else [len(prgs) - 1]

    stage_results: List[PrgDecompileResult] = []
    for idx in selected_indices:
        fname, fbytes = prgs[idx]
        desc = stages_meta[idx].description if idx < len(stages_meta) else None
        stage_results.append(decompile_prg(fbytes, name=fname, stage_description=desc))

    title = disk.disk_name or Path(path).stem.upper()
    return _combine_stage_results(stage_results, title=title, scope=norm_scope)


def decompile_tap_file(
    path: Union[str, Path],
    file_index: Optional[int] = None,
    scope: str = "both",
) -> PrgDecompileResult:
    """
    Extract and decompile stage(s) from a .tap cassette tape image (supports both KERNAL
    blocks and Bleepload / Freeload / Pavloda turbo tape streams).

    Args:
        path: Path to .tap image.
        file_index: Optional explicit stage index. If None (default), filters stages by `scope`.
        scope: `"loader"` (KERNAL/Turbo loader stages only),
               `"main"` (Main game payload stages only), or
               `"both"` (All loader + main game stages combined).
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"TAP file not found: {p}")

    tap_bytes = p.read_bytes()
    stages = extract_tap_stages(tap_bytes)
    if not stages:
        raise ValueError(f"No valid PRG blocks found in TAP image: {p}")

    if file_index is not None:
        if file_index < 0 or file_index >= len(stages):
            raise IndexError(f"TAP file index {file_index} out of range ({len(stages)} stages available)")
        st = stages[file_index]
        res = decompile_prg(
            st.prg_data,
            name=st.name,
            extra_entry_points=st.entry_points,
            stage_description=st.description,
        )
        res.scope = scope
        return res

    norm_scope = scope.lower().strip()
    if norm_scope not in {"loader", "main", "both"}:
        norm_scope = "both"

    filtered = [
        st for st in stages
        if norm_scope == "both" or st.role == norm_scope
    ]
    if not filtered:
        filtered = list(stages)

    stage_results: List[PrgDecompileResult] = []
    for st in filtered:
        stage_results.append(
            decompile_prg(
                st.prg_data,
                name=st.name,
                extra_entry_points=st.entry_points,
                stage_description=st.description,
            )
        )

    return _combine_stage_results(stage_results, title=p.stem.upper(), scope=norm_scope)
