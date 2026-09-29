"""PSID/RSID parser and conservative MOS 6502 reverse decompiler.

The decompiler follows control flow from the tune's init and play addresses.
Reachable bytes are rendered as instructions; all other bytes remain exact data,
so assembler output can reproduce the original C64 memory image.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class SidDecompileError(ValueError):
    """Raised when a file is not a supported or valid SID container."""


@dataclass(frozen=True)
class SidHeader:
    magic: str
    version: int
    data_offset: int
    load_address: int
    init_address: int
    play_address: int
    songs: int
    start_song: int
    speed: int
    name: str
    author: str
    released: str
    flags: int = 0
    start_page: int = 0
    page_length: int = 0
    second_sid: int = 0
    third_sid: int = 0

    @property
    def clock(self) -> str:
        value = (self.flags >> 2) & 0x03
        return {1: "PAL", 2: "NTSC", 3: "PAL/NTSC"}.get(value, "Unknown")

    @property
    def model(self) -> str:
        value = (self.flags >> 4) & 0x03
        return {1: "6581", 2: "8580", 3: "6581/8580"}.get(value, "Unknown")


@dataclass(frozen=True)
class SidFile:
    header: SidHeader
    payload: bytes
    container_header: bytes = b""
    embedded_load_address: bool = False

    @property
    def end_address(self) -> int:
        return self.header.load_address + len(self.payload)


@dataclass(frozen=True)
class Instruction:
    address: int
    opcode: int
    mnemonic: str
    mode: str
    operand: bytes

    @property
    def size(self) -> int:
        return 1 + len(self.operand)


@dataclass(frozen=True)
class SidDecompileResult:
    sid: SidFile
    assembly: str
    python: str
    instruction_count: int
    data_byte_count: int
    warnings: tuple[str, ...]


def _be16(data: bytes, offset: int) -> int:
    return (data[offset] << 8) | data[offset + 1]


def _be32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def _text(data: bytes) -> str:
    return data.split(b"\0", 1)[0].decode("latin-1", errors="replace").strip()


def parse_sid(data: bytes) -> SidFile:
    """Parse a PSID or RSID file, including an embedded little-endian load address."""
    if len(data) < 0x76:
        raise SidDecompileError("SID file is shorter than the mandatory 118-byte header")
    magic_bytes = data[:4]
    if magic_bytes not in (b"PSID", b"RSID"):
        raise SidDecompileError("Not a PSID/RSID file (missing PSID or RSID signature)")

    magic = magic_bytes.decode("ascii")
    version = _be16(data, 4)
    if version < 1 or version > 4:
        raise SidDecompileError(f"Unsupported {magic} version {version}")
    data_offset = _be16(data, 6)
    minimum_offset = 0x76 if version == 1 else 0x7C
    if data_offset < minimum_offset or data_offset > len(data):
        raise SidDecompileError(f"Invalid SID data offset ${data_offset:04X}")

    declared_load_address = _be16(data, 8)
    load_address = declared_load_address
    init_address = _be16(data, 10)
    play_address = _be16(data, 12)
    songs = _be16(data, 14)
    start_song = _be16(data, 16)
    if songs == 0:
        raise SidDecompileError("SID header declares zero songs")
    if not 1 <= start_song <= songs:
        raise SidDecompileError("SID default song is outside the declared song range")

    payload = data[data_offset:]
    if load_address == 0:
        if len(payload) < 2:
            raise SidDecompileError("SID payload does not contain its embedded load address")
        load_address = payload[0] | (payload[1] << 8)
        payload = payload[2:]
    if not payload:
        raise SidDecompileError("SID payload is empty")
    if load_address + len(payload) > 0x10000:
        raise SidDecompileError("SID payload extends beyond the 64 KiB C64 address space")
    if init_address == 0:
        init_address = load_address

    flags = _be16(data, 118) if version >= 2 and len(data) >= 120 else 0
    header = SidHeader(
        magic=magic,
        version=version,
        data_offset=data_offset,
        load_address=load_address,
        init_address=init_address,
        play_address=play_address,
        songs=songs,
        start_song=start_song,
        speed=_be32(data, 18),
        name=_text(data[22:54]),
        author=_text(data[54:86]),
        released=_text(data[86:118]),
        flags=flags,
        start_page=data[120] if version >= 2 and len(data) > 120 else 0,
        page_length=data[121] if version >= 2 and len(data) > 121 else 0,
        second_sid=data[122] if version >= 3 and len(data) > 122 else 0,
        third_sid=data[123] if version >= 4 and len(data) > 123 else 0,
    )
    return SidFile(
        header,
        payload,
        container_header=data[:data_offset],
        embedded_load_address=declared_load_address == 0,
    )


# Official NMOS 6502 opcodes. Undocumented opcodes are deliberately emitted as
# data because their behavior differs across CPUs and often marks embedded tables.
_OPCODE_SPEC = """
00 BRK imp|01 ORA indx|05 ORA zp|06 ASL zp|08 PHP imp|09 ORA imm|0A ASL acc|0D ORA abs|0E ASL abs
10 BPL rel|11 ORA indy|15 ORA zpx|16 ASL zpx|18 CLC imp|19 ORA absy|1D ORA absx|1E ASL absx
20 JSR abs|21 AND indx|24 BIT zp|25 AND zp|26 ROL zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs|2E ROL abs
30 BMI rel|31 AND indy|35 AND zpx|36 ROL zpx|38 SEC imp|39 AND absy|3D AND absx|3E ROL absx
40 RTI imp|41 EOR indx|45 EOR zp|46 LSR zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs
50 BVC rel|51 EOR indy|55 EOR zpx|56 LSR zpx|58 CLI imp|59 EOR absy|5D EOR absx|5E LSR absx
60 RTS imp|61 ADC indx|65 ADC zp|66 ROR zp|68 PLA imp|69 ADC imm|6A ROR acc|6C JMP ind|6D ADC abs|6E ROR abs
70 BVS rel|71 ADC indy|75 ADC zpx|76 ROR zpx|78 SEI imp|79 ADC absy|7D ADC absx|7E ROR absx
81 STA indx|84 STY zp|85 STA zp|86 STX zp|88 DEY imp|8A TXA imp|8C STY abs|8D STA abs|8E STX abs
90 BCC rel|91 STA indy|94 STY zpx|95 STA zpx|96 STX zpy|98 TYA imp|99 STA absy|9A TXS imp|9D STA absx
A0 LDY imm|A1 LDA indx|A2 LDX imm|A4 LDY zp|A5 LDA zp|A6 LDX zp|A8 TAY imp|A9 LDA imm|AA TAX imp|AC LDY abs|AD LDA abs|AE LDX abs
B0 BCS rel|B1 LDA indy|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B8 CLV imp|B9 LDA absy|BA TSX imp|BC LDY absx|BD LDA absx|BE LDX absy
C0 CPY imm|C1 CMP indx|C4 CPY zp|C5 CMP zp|C6 DEC zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs|CD CMP abs|CE DEC abs
D0 BNE rel|D1 CMP indy|D5 CMP zpx|D6 DEC zpx|D8 CLD imp|D9 CMP absy|DD CMP absx|DE DEC absx
E0 CPX imm|E1 SBC indx|E4 CPX zp|E5 SBC zp|E6 INC zp|E8 INX imp|E9 SBC imm|EA NOP imp|EC CPX abs|ED SBC abs|EE INC abs
F0 BEQ rel|F1 SBC indy|F5 SBC zpx|F6 INC zpx|F8 SED imp|F9 SBC absy|FD SBC absx|FE INC absx
"""

_MODE_SIZE = {"imp": 1, "acc": 1, "imm": 2, "zp": 2, "zpx": 2, "zpy": 2,
              "indx": 2, "indy": 2, "rel": 2, "abs": 3, "absx": 3,
              "absy": 3, "ind": 3}
_OPCODES: dict[int, tuple[str, str]] = {}
for _item in _OPCODE_SPEC.replace("\n", "|").split("|"):
    _parts = _item.strip().split()
    if _parts:
        _OPCODES[int(_parts[0], 16)] = (_parts[1], _parts[2])

_BRANCHES = {"BCC", "BCS", "BEQ", "BMI", "BNE", "BPL", "BVC", "BVS"}
_TERMINATORS = {"BRK", "RTI", "RTS"}
_SID_REGISTERS = {
    0xD400: "V1_FREQ_LO", 0xD401: "V1_FREQ_HI", 0xD402: "V1_PW_LO",
    0xD403: "V1_PW_HI", 0xD404: "V1_CONTROL", 0xD405: "V1_ATTACK_DECAY",
    0xD406: "V1_SUSTAIN_RELEASE", 0xD407: "V2_FREQ_LO", 0xD408: "V2_FREQ_HI",
    0xD409: "V2_PW_LO", 0xD40A: "V2_PW_HI", 0xD40B: "V2_CONTROL",
    0xD40C: "V2_ATTACK_DECAY", 0xD40D: "V2_SUSTAIN_RELEASE", 0xD40E: "V3_FREQ_LO",
    0xD40F: "V3_FREQ_HI", 0xD410: "V3_PW_LO", 0xD411: "V3_PW_HI",
    0xD412: "V3_CONTROL", 0xD413: "V3_ATTACK_DECAY", 0xD414: "V3_SUSTAIN_RELEASE",
    0xD415: "FILTER_CUTOFF_LO", 0xD416: "FILTER_CUTOFF_HI",
    0xD417: "FILTER_RESONANCE_ROUTING", 0xD418: "FILTER_MODE_VOLUME",
    0xD419: "POT_X", 0xD41A: "POT_Y", 0xD41B: "OSC3_RANDOM", 0xD41C: "ENV3",
}


def _word(raw: bytes) -> int:
    return raw[0] | (raw[1] << 8)


def _in_image(sid: SidFile, address: int) -> bool:
    return sid.header.load_address <= address < sid.end_address


def _decode_reachable(sid: SidFile) -> tuple[dict[int, Instruction], set[int], list[str]]:
    header = sid.header
    seeds = [header.init_address]
    if header.play_address:
        seeds.append(header.play_address)
    queue = list(dict.fromkeys(address for address in seeds if _in_image(sid, address)))
    instructions: dict[int, Instruction] = {}
    occupied: set[int] = set()
    targets: set[int] = set(queue)
    warnings: list[str] = []
    base = header.load_address

    for address in seeds:
        if not _in_image(sid, address):
            warnings.append(f"entry point ${address:04X} lies outside the payload")

    while queue:
        pc = queue.pop()
        while _in_image(sid, pc) and pc not in instructions:
            offset = pc - base
            opcode = sid.payload[offset]
            spec = _OPCODES.get(opcode)
            if spec is None:
                break
            mnemonic, mode = spec
            size = _MODE_SIZE[mode]
            if offset + size > len(sid.payload):
                break
            byte_range = set(range(pc, pc + size))
            if occupied & byte_range:
                break
            operand = sid.payload[offset + 1 : offset + size]
            ins = Instruction(pc, opcode, mnemonic, mode, operand)
            instructions[pc] = ins
            occupied.update(byte_range)

            target: int | None = None
            if mode == "rel":
                displacement = operand[0] if operand[0] < 0x80 else operand[0] - 0x100
                target = (pc + 2 + displacement) & 0xFFFF
            elif mode == "abs" and mnemonic in {"JMP", "JSR"}:
                target = _word(operand)
            if target is not None and _in_image(sid, target):
                targets.add(target)
                if target not in instructions:
                    queue.append(target)

            pc += size
            if mnemonic in _TERMINATORS or mnemonic == "JMP":
                break

    return instructions, targets, warnings


def _label_map(
    sid: SidFile,
    targets: Iterable[int],
    instructions: dict[int, Instruction],
) -> dict[int, str]:
    # A corrupted or deliberately obfuscated tune can branch into the operand of
    # another decoded instruction. Do not emit an impossible mid-instruction label.
    operand_bytes = {
        address
        for instruction in instructions.values()
        for address in range(instruction.address + 1, instruction.address + instruction.size)
    }
    labels = {
        address: f"loc_{address:04x}"
        for address in targets
        if address not in operand_bytes
    }
    init = sid.header.init_address
    play = sid.header.play_address
    if init == play and play:
        labels[init] = "sid_init_play"
    else:
        if _in_image(sid, init):
            labels[init] = "sid_init"
        if play and _in_image(sid, play):
            labels[play] = "sid_play"
    return labels


def _format_instruction(ins: Instruction, labels: dict[int, str]) -> str:
    mode = ins.mode
    raw = ins.operand
    value = _word(raw) if len(raw) == 2 else (raw[0] if raw else 0)
    if mode == "imp":
        operand = ""
    elif mode == "acc":
        # KickAssembler uses the operand-less form for accumulator shifts/rotates.
        operand = ""
    elif mode == "imm":
        operand = f"#${value:02x}"
    elif mode == "zp":
        operand = f"${value:02x}"
    elif mode == "zpx":
        operand = f"${value:02x},x"
    elif mode == "zpy":
        operand = f"${value:02x},y"
    elif mode == "indx":
        operand = f"(${value:02x},x)"
    elif mode == "indy":
        operand = f"(${value:02x}),y"
    elif mode == "rel":
        displacement = value if value < 0x80 else value - 0x100
        target = (ins.address + 2 + displacement) & 0xFFFF
        operand = labels.get(target, f"${target:04x}")
    elif mode == "ind":
        operand = f"(${value:04x})"
    else:
        target = labels.get(value) if ins.mnemonic in {"JMP", "JSR"} else None
        operand = target or f"${value:04x}"
        if mode == "absx":
            operand += ",x"
        elif mode == "absy":
            operand += ",y"
    text = f"    {ins.mnemonic.lower():<4} {operand}".rstrip()
    if mode in {"abs", "absx", "absy"} and value in _SID_REGISTERS:
        text += f"  // SID {_SID_REGISTERS[value]}"
    return text


def _metadata_lines(sid: SidFile) -> list[str]:
    h = sid.header
    speeds = []
    for index in range(h.songs):
        bit = min(index, 31)
        speeds.append("CIA" if h.speed & (1 << bit) else "VBI")
    speed_summary = ", ".join(f"{i + 1}:{speed}" for i, speed in enumerate(speeds[:16]))
    if h.songs > 16:
        speed_summary += ", ..."
    metadata = {
        "magic": h.magic,
        "version": h.version,
        "data_offset": h.data_offset,
        "load_address": h.load_address,
        "init_address": h.init_address,
        "play_address": h.play_address,
        "songs": h.songs,
        "start_song": h.start_song,
        "speed": h.speed,
        "name": h.name,
        "author": h.author,
        "released": h.released,
        "flags": h.flags,
        "start_page": h.start_page,
        "page_length": h.page_length,
        "second_sid": h.second_sid,
        "third_sid": h.third_sid,
        "embedded_load_address": sid.embedded_load_address,
        "container_header": sid.container_header.hex(),
    }
    metadata_json = json.dumps(metadata, ensure_ascii=True, separators=(",", ":"))
    return [
        "// Reverse-decompiled by C64U Antigravity Bridge",
        f"// C64U_SID_METADATA: {metadata_json}",
        f"// Format: {h.magic} v{h.version} | Title: {h.name or '(untitled)'}",
        f"// Author: {h.author or '(unknown)'} | Released: {h.released or '(unknown)'}",
        f"// Songs: {h.songs} | Default: {h.start_song} | Timing: {speed_summary}",
        f"// Clock: {h.clock} | SID model: {h.model}",
        "// Static control-flow analysis is conservative. Unreachable and unknown bytes",
        "// are emitted as data so lookup tables and undocumented opcodes remain exact.",
    ]


def _render_body(sid: SidFile, instructions: dict[int, Instruction], labels: dict[int, str]) -> list[str]:
    lines: list[str] = []
    base = sid.header.load_address
    end = sid.end_address
    pc = base
    while pc < end:
        if pc in labels:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append(f"{labels[pc]}:")
        ins = instructions.get(pc)
        if ins is not None:
            lines.append(_format_instruction(ins, labels))
            pc += ins.size
            continue

        chunk: list[int] = []
        while pc < end and len(chunk) < 16:
            if chunk and (pc in instructions or pc in labels):
                break
            chunk.append(sid.payload[pc - base])
            pc += 1
            if pc in instructions or pc in labels:
                break
        lines.append("    .byte " + ",".join(f"${byte:02x}" for byte in chunk))
    return lines


def _render_assembly(sid: SidFile, body: list[str]) -> str:
    h = sid.header
    lines = _metadata_lines(sid)
    lines += [
        "",
        f".const SID_LOAD = ${h.load_address:04x}",
        f".const SID_INIT = ${h.init_address:04x}",
        f".const SID_PLAY = ${h.play_address:04x}",
        f".const SID_SONGS = {h.songs}",
        f".const SID_DEFAULT_SONG = {h.start_song}",
        f".const SID_SPEED = ${h.speed:08x}",
        f".const SID_FLAGS = ${h.flags:04x}",
        "",
        f'* = SID_LOAD "{h.name or "SID payload"}"',
        "",
        *body,
        "",
    ]
    return "\n".join(lines)


def _render_python(sid: SidFile, body: list[str]) -> str:
    h = sid.header
    escaped_title = (h.name or "untitled").replace('"', "'")
    metadata_line = _metadata_lines(sid)[1].removeprefix("// ")
    lines = [
        '"""Reverse-decompiled SID player image.',
        "",
        "The Python dialect cannot express arbitrary 6510 instructions directly, so",
        "the recovered routines are retained in asm(...). Static data is byte-exact.",
        '"""',
        "",
        f"# {metadata_line}",
        f"SID_LOAD = 0x{h.load_address:04X}",
        f"SID_INIT = 0x{h.init_address:04X}",
        f"SID_PLAY = 0x{h.play_address:04X}",
        f"SID_SONGS = {h.songs}",
        f"SID_DEFAULT_SONG = {h.start_song}",
        f"SID_SPEED = 0x{h.speed:08X}",
        f"SID_FLAGS = 0x{h.flags:04X}",
        "",
        f'# Source tune: "{escaped_title}" by {h.author or "unknown"}',
        "asm(\"\"\"",
        f'.pc = ${h.load_address:04x} "Reverse-decompiled SID payload"',
        *body,
        '\"\"\")',
        "",
    ]
    return "\n".join(lines)


def decompile_sid(data: bytes) -> SidDecompileResult:
    """Convert a SID container to annotated KickAssembler and Python-dialect source."""
    sid = parse_sid(data)
    instructions, targets, warnings = _decode_reachable(sid)
    labels = _label_map(sid, targets, instructions)
    body = _render_body(sid, instructions, labels)
    used = sum(instruction.size for instruction in instructions.values())
    return SidDecompileResult(
        sid=sid,
        assembly=_render_assembly(sid, body),
        python=_render_python(sid, body),
        instruction_count=len(instructions),
        data_byte_count=len(sid.payload) - used,
        warnings=tuple(warnings),
    )


def decompile_sid_file(path: Path) -> SidDecompileResult:
    """Read and reverse-decompile a SID file."""
    return decompile_sid(path.read_bytes())
