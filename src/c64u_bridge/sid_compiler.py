"""Compile reverse-decompiled SID sources back into PSID/RSID containers."""

from __future__ import annotations

import ast
import json
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional, Union

from .compiler import CrossCompiler
from .sid_decompiler import SidFile, SidHeader, parse_sid


class SidCompileError(ValueError):
    """Raised when SID source cannot be assembled or packaged safely."""


@dataclass(frozen=True)
class SidCompileResult:
    output_sid: Path
    sid: SidFile
    payload_size: int
    assembler_stdout: str = ""
    assembler_stderr: str = ""


_METADATA_RE = re.compile(
    r"^\s*(?://|#)\s*C64U_SID_METADATA:\s*(\{.*\})\s*$",
    re.MULTILINE,
)
_CONSTANT_NAMES = {
    "SID_LOAD": "load_address",
    "SID_INIT": "init_address",
    "SID_PLAY": "play_address",
    "SID_SONGS": "songs",
    "SID_DEFAULT_SONG": "start_song",
    "SID_SPEED": "speed",
    "SID_FLAGS": "flags",
}


def _parse_number(value: str) -> int:
    value = value.strip()
    if value.startswith("$"):
        return int(value[1:], 16)
    return int(value, 0)


def _source_overrides(source: str) -> dict[str, int]:
    overrides: dict[str, int] = {}
    for constant, field in _CONSTANT_NAMES.items():
        match = re.search(
            rf"(?mi)^\s*(?:\.const\s+)?{constant}\s*=\s*(\$[0-9a-f]+|0x[0-9a-f]+|\d+)\s*$",
            source,
        )
        if match:
            overrides[field] = _parse_number(match.group(1))
    return overrides


def _sid_from_metadata(source: str) -> Optional[SidFile]:
    match = _METADATA_RE.search(source)
    if not match:
        return None
    try:
        metadata = json.loads(match.group(1))
        header = SidHeader(
            magic=str(metadata["magic"]),
            version=int(metadata["version"]),
            data_offset=int(metadata["data_offset"]),
            load_address=int(metadata["load_address"]),
            init_address=int(metadata["init_address"]),
            play_address=int(metadata["play_address"]),
            songs=int(metadata["songs"]),
            start_song=int(metadata["start_song"]),
            speed=int(metadata["speed"]),
            name=str(metadata.get("name", "")),
            author=str(metadata.get("author", "")),
            released=str(metadata.get("released", "")),
            flags=int(metadata.get("flags", 0)),
            start_page=int(metadata.get("start_page", 0)),
            page_length=int(metadata.get("page_length", 0)),
            second_sid=int(metadata.get("second_sid", 0)),
            third_sid=int(metadata.get("third_sid", 0)),
        )
        raw_header = bytes.fromhex(str(metadata.get("container_header", "")))
        return SidFile(
            header=header,
            payload=b"",
            container_header=raw_header,
            embedded_load_address=bool(metadata.get("embedded_load_address", False)),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SidCompileError(f"Invalid C64U SID metadata: {exc}") from exc


def _encode_text(value: str) -> bytes:
    return value.encode("latin-1", errors="replace")[:32].ljust(32, b"\0")


def build_sid(sid: SidFile, payload: bytes) -> bytes:
    """Build a SID container around an assembled load image."""
    h = sid.header
    if h.magic not in {"PSID", "RSID"}:
        raise SidCompileError(f"Unsupported SID magic: {h.magic}")
    if not 1 <= h.version <= 4:
        raise SidCompileError(f"Unsupported {h.magic} version {h.version}")
    if not payload:
        raise SidCompileError("Assembled SID payload is empty")
    if h.load_address + len(payload) > 0x10000:
        raise SidCompileError("Assembled SID payload extends beyond the 64 KiB address space")
    if not 1 <= h.start_song <= h.songs:
        raise SidCompileError("SID default song is outside the declared song range")

    minimum_offset = 0x76 if h.version == 1 else 0x7C
    data_offset = max(h.data_offset, minimum_offset)
    raw_header = sid.container_header[:data_offset]
    header = bytearray(raw_header.ljust(data_offset, b"\0"))
    header[0:4] = h.magic.encode("ascii")
    header[4:6] = h.version.to_bytes(2, "big")
    header[6:8] = data_offset.to_bytes(2, "big")
    header[8:10] = (0 if sid.embedded_load_address else h.load_address).to_bytes(2, "big")
    header[10:12] = h.init_address.to_bytes(2, "big")
    header[12:14] = h.play_address.to_bytes(2, "big")
    header[14:16] = h.songs.to_bytes(2, "big")
    header[16:18] = h.start_song.to_bytes(2, "big")
    header[18:22] = h.speed.to_bytes(4, "big")
    header[22:54] = _encode_text(h.name)
    header[54:86] = _encode_text(h.author)
    header[86:118] = _encode_text(h.released)
    if h.version >= 2:
        header[118:120] = h.flags.to_bytes(2, "big")
        header[120] = h.start_page
        header[121] = h.page_length
    if h.version >= 3:
        header[122] = h.second_sid
    if h.version >= 4:
        header[123] = h.third_sid

    data = bytes(header)
    if sid.embedded_load_address:
        data += h.load_address.to_bytes(2, "little")
    data += payload

    # Reparse the result so malformed metadata never produces a silent bad file.
    parse_sid(data)
    return data


def _extract_python_assembly(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SidCompileError(f"Invalid Python SID source: {exc}") from exc
    blocks: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "asm":
            value = node.args[0]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                blocks.append(value.value)
    if not blocks:
        raise SidCompileError("Python SID source does not contain an asm(\"\"\"...\"\"\") block")
    return "\n\n".join(blocks)


def _normalize_legacy_decompiler_assembly(source: str) -> str:
    """Accept older C64U decompiler output that emitted KickAssembler-invalid `a`."""
    return re.sub(
        r"(?mi)^(\s*(?:asl|lsr|rol|ror))\s+a(\s*(?://.*)?)$",
        r"\1\2",
        source,
    )


def _default_output_path(source_path: Path) -> Path:
    stem = source_path.stem
    if stem.lower().endswith("_decompiled"):
        stem = stem[: -len("_decompiled")]
    return source_path.with_name(f"{stem}_compiled.sid")


def _inferred_template_path(source_path: Path) -> Optional[Path]:
    stem = source_path.stem
    if stem.lower().endswith("_decompiled"):
        candidate = source_path.with_name(f"{stem[:-len('_decompiled')]}.sid")
        if candidate.is_file():
            return candidate
    return None


def compile_sid_source(
    source_path: Union[Path, str],
    output_sid: Optional[Union[Path, str]] = None,
    template_sid: Optional[Union[Path, str]] = None,
    assembler: str = "kickass",
    compiler: Optional[CrossCompiler] = None,
    source_text: Optional[str] = None,
) -> SidCompileResult:
    """Assemble a decompiled ASM/Python source and package it as SID."""
    source = Path(source_path).resolve()
    if not source.is_file():
        raise SidCompileError(f"SID source file not found: {source}")
    if source.suffix.lower() not in {".asm", ".s", ".py"}:
        raise SidCompileError("SID source must be a .asm, .s, or .py file")

    text = source_text if source_text is not None else source.read_text(encoding="utf-8")
    template_path = Path(template_sid).resolve() if template_sid else _inferred_template_path(source)
    if template_path:
        if not template_path.is_file():
            raise SidCompileError(f"Template SID file not found: {template_path}")
        base_sid = parse_sid(template_path.read_bytes())
    else:
        base_sid = _sid_from_metadata(text)
        if base_sid is None:
            raise SidCompileError(
                "SID metadata is missing; use a C64U-decompiled source or provide --template"
            )

    overrides = _source_overrides(text)
    header = replace(base_sid.header, **overrides)
    base_sid = replace(base_sid, header=header)
    output = Path(output_sid).resolve() if output_sid else _default_output_path(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_source: Optional[Path] = None
    compile_source = source
    assembly = _extract_python_assembly(text) if source.suffix.lower() == ".py" else text
    assembly = _normalize_legacy_decompiler_assembly(assembly)
    if source.suffix.lower() == ".py" or source_text is not None or assembly != text:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".asm",
            prefix=f".{source.stem}_sidbuild_",
            dir=source.parent,
            encoding="utf-8",
            delete=False,
        ) as temp_source:
            temp_source.write(assembly)
            temporary_source = Path(temp_source.name)
            compile_source = temporary_source

    compile_driver = compiler or CrossCompiler()
    try:
        with tempfile.TemporaryDirectory(prefix="c64u_sidbuild_") as temp_dir:
            prg_path = Path(temp_dir) / f"{source.stem}.prg"
            compiled = compile_driver.compile(
                compile_source,
                output_prg=prg_path,
                assembler=assembler,
            )
            if not compiled.success or not compiled.output_prg:
                detail = compiled.error_message or compiled.stderr or compiled.stdout
                raise SidCompileError(f"SID payload assembly failed: {detail}")
            prg = compiled.output_prg.read_bytes()
            if len(prg) < 3:
                raise SidCompileError("Assembler produced an empty or invalid PRG")
            load_address = int.from_bytes(prg[:2], "little")
            if load_address != header.load_address:
                raise SidCompileError(
                    f"Assembler load address ${load_address:04X} does not match SID_LOAD "
                    f"${header.load_address:04X}"
                )
            payload = prg[2:]
            sid_bytes = build_sid(base_sid, payload)
            output.write_bytes(sid_bytes)
            rebuilt = parse_sid(sid_bytes)
            return SidCompileResult(
                output_sid=output,
                sid=rebuilt,
                payload_size=len(payload),
                assembler_stdout=compiled.stdout,
                assembler_stderr=compiled.stderr,
            )
    finally:
        if temporary_source is not None:
            temporary_source.unlink(missing_ok=True)
