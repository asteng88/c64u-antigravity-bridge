"""
Automated Deployment Validation Report Engine for C64U Antigravity Bridge.

Records and compares post-deployment telemetry after each C64 build/DMA run:
1. Compilation success, assembler used, load/end addresses, and generated PRG size + SHA-256 hash.
2. C64U connection reachability and firmware/hardware details.
3. Program DMA load and execution status.
4. 40x25 Screen RAM ($0400-$07E7) and Color RAM ($D800-$DBE7) snapshot + active text rows.
5. Selected memory and hardware register values (6510 $01 banking, RAM IRQ/NMI vectors,
   VIC-II video/sprite/color registers, SID voice/volume state, CIA2 VIC-II bank, and custom watches).
6. Differences from the previous deployment (PRG size delta, binary hash change, modified registers,
   and row-by-row Screen RAM changes) to streamline debugging AI-generated 6502 programs.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .client import C64UClient
from .compiler import CompilationResult
from .prg_decompiler import C64_COLOR_NAMES
from .screen import format_screen, screen_code_to_ascii


DEFAULT_STATE_FILE = Path(".c64u_last_deployment.json")


@dataclass
class DeploymentDiff:
    """Comparison between the current deployment and the previous deployment."""
    has_previous: bool = False
    previous_timestamp: Optional[str] = None
    previous_source: Optional[str] = None
    prg_size_delta: int = 0
    prg_hash_changed: bool = False
    load_address_changed: Optional[str] = None
    register_changes: List[str] = field(default_factory=list)
    screen_Wait_cells_changed: int = 0
    screen_row_changes: List[str] = field(default_factory=list)


@dataclass
class DeploymentValidationReport:
    """Complete post-deployment validation snapshot and diff."""
    timestamp: str
    source_name: str
    # 1. Compilation & PRG metrics
    compilation_success: bool
    assembler_used: str = "kickass"
    prg_path: Optional[str] = None
    prg_size_bytes: int = 0
    payload_size_bytes: int = 0
    load_address: Optional[int] = None
    end_address: Optional[int] = None
    prg_sha256: str = ""
    compiler_output: str = ""
    # 2. C64U Connection & Firmware details
    c64u_connected: bool = False
    c64u_host: str = ""
    c64u_port: int = 80
    firmware_version: str = "OFFLINE"
    device_info: Dict[str, Any] = field(default_factory=dict)
    # 3. Program Load & Execution status
    execution_mode: str = "DMA_RUN"
    load_and_exec_success: bool = False
    runner_response: str = ""
    execution_error: Optional[str] = None
    # 4. Screen RAM snapshot
    screen_captured: bool = False
    screen_ascii: str = ""
    raw_screen_codes: List[int] = field(default_factory=list)
    raw_color_codes: List[int] = field(default_factory=list)
    non_blank_chars: int = 0
    active_screen_rows: List[Tuple[int, str]] = field(default_factory=list)
    # 5. Selected Memory & Register values
    registers: Dict[str, str] = field(default_factory=dict)
    watched_memory: Dict[str, str] = field(default_factory=dict)
    # 6. Differences from previous deployment
    diff: DeploymentDiff = field(default_factory=DeploymentDiff)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report state for JSON persistence and diffing."""
        return {
            "timestamp": self.timestamp,
            "source_name": self.source_name,
            "compilation_success": self.compilation_success,
            "assembler_used": self.assembler_used,
            "prg_path": self.prg_path,
            "prg_size_bytes": self.prg_size_bytes,
            "payload_size_bytes": self.payload_size_bytes,
            "load_address": self.load_address,
            "end_address": self.end_address,
            "prg_sha256": self.prg_sha256,
            "c64u_connected": self.c64u_connected,
            "c64u_host": self.c64u_host,
            "c64u_port": self.c64u_port,
            "firmware_version": self.firmware_version,
            "device_info": self.device_info,
            "execution_mode": self.execution_mode,
            "load_and_exec_success": self.load_and_exec_success,
            "runner_response": self.runner_response,
            "execution_error": self.execution_error,
            "screen_captured": self.screen_captured,
            "raw_screen_codes": self.raw_screen_codes,
            "non_blank_chars": self.non_blank_chars,
            "active_screen_rows": self.active_screen_rows,
            "registers": self.registers,
            "watched_memory": self.watched_memory,
        }

    def format_report(self, include_full_screen: bool = True) -> str:
        """Render a structured, human- and AI-readable validation report."""
        lines: List[str] = [
            "=" * 76,
            f"C64U AUTOMATED DEPLOYMENT VALIDATION REPORT // {self.source_name}",
            f"Timestamp: {self.timestamp}",
            "=" * 76,
        ]

        # 1. Compilation & PRG Size
        comp_icon = "PASS" if self.compilation_success else "FAIL"
        lines.append(f"[1] COMPILATION & PRG BINARY: {comp_icon}")
        if self.compilation_success and self.load_address is not None and self.end_address is not None:
            lines.append(
                f"    * PRG File      : {Path(self.prg_path).name if self.prg_path else '(in-memory)'} "
                f"({self.prg_size_bytes:,} bytes total / {self.payload_size_bytes:,} bytes payload)"
            )
            lines.append(
                f"    * Memory Range  : ${self.load_address:04X} - ${self.end_address:04X} "
                f"| Assembler: {self.assembler_used} | SHA-256: {self.prg_sha256}"
            )
        elif not self.compilation_success:
            lines.append(f"    * Compiler Error: {self.compiler_output.strip() or 'Unknown error'}")

        # 2. C64U Connection & Firmware Details
        conn_icon = "ONLINE" if self.c64u_connected else "OFFLINE"
        lines.append(f"[2] C64U CONNECTION & FIRMWARE: {conn_icon}")
        lines.append(
            f"    * Endpoint      : http://{self.c64u_host}:{self.c64u_port} | Firmware: {self.firmware_version}"
        )
        if self.device_info:
            extra_keys = [
                f"{k}={v}"
                for k, v in self.device_info.items()
                if k not in {"version", "errors"} and v not in (None, "", [])
            ]
            if extra_keys:
                lines.append(f"    * Device Details: {', '.join(extra_keys[:6])}")

        # 3. Program Load & Execution Status
        exec_icon = "RUNNING" if self.load_and_exec_success else ("SKIPPED" if not self.compilation_success else "FAILED")
        lines.append(f"[3] PROGRAM LOAD & EXECUTION ({self.execution_mode}): {exec_icon}")
        if self.load_and_exec_success:
            lines.append(f"    * DMA Response  : {self.runner_response}")
        elif self.execution_error:
            lines.append(f"    * DMA Error     : {self.execution_error}")

        # 4. Selected Memory & Hardware Register Values
        lines.append("[4] SELECTED MEMORY & HARDWARE REGISTERS:")
        if self.registers:
            for reg_key, reg_val in self.registers.items():
                lines.append(f"    * {reg_key:<22}: {reg_val}")
        else:
            lines.append("    * (No live register snapshot -- C64U hardware offline)")
        if self.watched_memory:
            for w_key, w_val in self.watched_memory.items():
                lines.append(f"    * Watch {w_key:<16}: {w_val}")

        # 5. Screen RAM Snapshot ($0400-$07E7)
        lines.append("[5] SCREEN RAM SNAPSHOT ($0400-$07E7):")
        if self.screen_captured:
            lines.append(
                f"    * Visible Chars : {self.non_blank_chars}/1000 non-blank cells across {len(self.active_screen_rows)} active row(s)"
            )
            if self.active_screen_rows:
                for row_idx, row_txt in self.active_screen_rows[:8]:
                    lines.append(f"      Row {row_idx:02d}: \"{row_txt}\"")
                if len(self.active_screen_rows) > 8:
                    lines.append(f"      ... (+{len(self.active_screen_rows) - 8} more non-blank rows)")
            if include_full_screen and self.screen_ascii:
                lines.append(self.screen_ascii)
        else:
            lines.append("    * (Screen RAM not captured -- C64U hardware offline)")

        # 6. Differences from Previous Deployment
        lines.append("[6] DIFFERENCES FROM PREVIOUS DEPLOYMENT:")
        if not self.diff.has_previous:
            lines.append("    * Baseline deployment recorded (no previous deployment to diff against).")
        else:
            prev_hdr = f"vs. {self.diff.previous_source or 'previous'} @ {self.diff.previous_timestamp or '?'}"
            sign = "+" if self.diff.prg_size_delta > 0 else ""
            hash_status = "MODIFIED" if self.diff.prg_hash_changed else "IDENTICAL"
            lines.append(
                f"    * Binary Diff ({prev_hdr}): Size {sign}{self.diff.prg_size_delta} bytes ({hash_status})"
            )
            if self.diff.load_address_changed:
                lines.append(f"    * Load Address  : {self.diff.load_address_changed}")
            if self.diff.register_changes:
                lines.append(f"    * Register Diffs ({len(self.diff.register_changes)}):")
                for rc in self.diff.register_changes[:10]:
                    lines.append(f"        - {rc}")
            else:
                lines.append("    * Register Diffs: None (all monitored hardware registers unchanged)")

            if self.screen_captured:
                lines.append(f"    * Screen Diff   : {self.diff.screen_Wait_cells_changed} character cell(s) changed")
                for sc in self.diff.screen_row_changes[:6]:
                    lines.append(f"        - {sc}")

        lines.append("=" * 76)
        return "\n".join(lines)


def _decode_row_ascii(screen_mem: bytes, row: int) -> str:
    """Convert a 40-byte row of C64 screen codes into a stripped ASCII string."""
    row_bytes = screen_mem[row * 40 : (row + 1) * 40]
    return "".join(screen_code_to_ascii(b) for b in row_bytes).rstrip()


def _capture_registers(client: C64UClient) -> Dict[str, str]:
    """Read and decode key C64 hardware and OS registers via non-invasive DMA reads."""
    regs: Dict[str, str] = {}

    # 1. Zero Page $0000-$0001 (CPU Port DDR & Banking)
    try:
        zp = client.read_memory(0x0000, 2)
        if len(zp) >= 2:
            ddr, port = zp[0], zp[1]
            loram, hiram, charen = port & 1, (port >> 1) & 1, (port >> 2) & 1
            bank_desc = f"LORAM={loram} HIRAM={hiram} CHAREN={charen}"
            regs["$00/$01 CPU Port"] = f"DDR=${ddr:02X}, PORT=${port:02X} ({bank_desc})"
    except Exception:
        pass

    # 2. RAM Interrupt Vectors ($0314-$0319: IRQ, BRK, NMI)
    try:
        vec = client.read_memory(0x0314, 6)
        if len(vec) >= 6:
            irq = vec[0] | (vec[1] << 8)
            brk = vec[2] | (vec[3] << 8)
            nmi = vec[4] | (vec[5] << 8)
            regs["$0314-$0319 Vectors"] = f"IRQ=${irq:04X}, BRK=${brk:04X}, NMI=${nmi:04X}"
    except Exception:
        pass

    # 3. VIC-II Video Controller ($D011-$D02E)
    try:
        vic = client.read_memory(0xD011, 0x1E)  # $D011 .. $D02E (30 bytes)
        if len(vic) >= 0x12:
            d011 = vic[0x00]  # $D011
            d012 = vic[0x01] | ((d011 & 0x80) << 1)
            d015 = vic[0x04]  # $D015
            d016 = vic[0x05]  # $D016
            d018 = vic[0x07]  # $D018
            d019 = vic[0x08]  # $D019
            d01a = vic[0x09]  # $D01A
            d020 = vic[0x0F] & 0x0F  # $D020
            d021 = vic[0x10] & 0x0F  # $D021

            scr_on = "ON" if (d011 & 0x10) else "BLANKED"
            mode = "BITMAP" if (d011 & 0x20) else "TEXT"
            mcm = "MULTICOLOR" if (d016 & 0x10) else "HIRES"
            regs["$D011/$D016 Display"] = (
                f"CTRL1=${d011:02X} ({scr_on}, {mode}), CTRL2=${d016:02X} ({mcm}), RASTER=${d012:03X}"
            )

            scr_ofs = ((d018 >> 4) & 0x0F) * 0x0400
            chr_ofs = ((d018 >> 1) & 0x07) * 0x0800
            regs["$D018 Memory Ptr"] = f"${d018:02X} (Screen +${scr_ofs:04X}, Charset/BMP +${chr_ofs:04X})"

            b_col = C64_COLOR_NAMES.get(d020, str(d020))
            bg_col = C64_COLOR_NAMES.get(d021, str(d021))
            regs["$D020/$D021 Colors"] = f"Border=${d020:02X} ({b_col}), BG0=${d021:02X} ({bg_col})"

            sp_list = [str(i) for i in range(8) if d015 & (1 << i)]
            sp_desc = f"Sprites {', '.join(sp_list)} ON" if sp_list else "All OFF"
            regs["$D015/$D01A Spr/IRQ"] = f"SP_EN=${d015:02X} ({sp_desc}), IRQ_EN=${d01a:02X}, IRQ_FLG=${d019:02X}"
    except Exception:
        pass

    # 4. SID Sound Synthesizer ($D400-$D418)
    try:
        sid = client.read_memory(0xD400, 25)
        if len(sid) >= 25:
            v1_f = sid[0] | (sid[1] << 8)
            v1_c = sid[4]
            v2_f = sid[7] | (sid[8] << 8)
            v2_c = sid[11]
            v3_f = sid[14] | (sid[15] << 8)
            v3_c = sid[18]
            vol = sid[24] & 0x0F
            regs["$D400-$D418 SID"] = (
                f"V1(F=${v1_f:04X} C=${v1_c:02X}) V2(F=${v2_f:04X} C=${v2_c:02X}) "
                f"V3(F=${v3_f:04X} C=${v3_c:02X}) Vol={vol}/15"
            )
    except Exception:
        pass

    # 5. CIA2 VIC-II 16KB Bank ($DD00)
    try:
        dd00 = client.read_memory(0xDD00, 1)
        if dd00:
            bank_idx = 3 - (dd00[0] & 0x03)
            bank_base = bank_idx * 0x4000
            regs["$DD00 VIC-II Bank"] = f"${dd00[0]:02X} (Bank {bank_idx}: ${bank_base:04X}-${bank_base + 0x3FFF:04X})"
    except Exception:
        pass

    return regs


def _compute_diff(
    current: DeploymentValidationReport,
    previous_data: Optional[Dict[str, Any]],
) -> DeploymentDiff:
    """Compare current deployment report with the previous deployment dictionary."""
    if not previous_data:
        return DeploymentDiff(has_previous=False)

    diff = DeploymentDiff(
        has_previous=True,
        previous_timestamp=previous_data.get("timestamp"),
        previous_source=previous_data.get("source_name"),
    )

    prev_size = int(previous_data.get("prg_size_bytes") or 0)
    diff.prg_size_delta = current.prg_size_bytes - prev_size

    prev_hash = str(previous_data.get("prg_sha256") or "")
    diff.prg_hash_changed = bool(current.prg_sha256 and prev_hash and current.prg_sha256 != prev_hash)

    prev_load = previous_data.get("load_address")
    if prev_load is not None and current.load_address is not None and int(prev_load) != current.load_address:
        diff.load_address_changed = f"${int(prev_load):04X} -> ${current.load_address:04X}"

    # Compare registers
    prev_regs: Dict[str, str] = previous_data.get("registers") or {}
    for k, cur_val in current.registers.items():
        old_val = prev_regs.get(k)
        if old_val is not None and old_val != cur_val:
            diff.register_changes.append(f"{k}: [{old_val}] -> [{cur_val}]")

    # Compare Screen RAM
    prev_screen: List[int] = previous_data.get("raw_screen_codes") or []
    if current.raw_screen_codes and len(prev_screen) == len(current.raw_screen_codes):
        changed_cells = sum(1 for a, b in zip(prev_screen, current.raw_screen_codes) if a != b)
        diff.screen_Wait_cells_changed = changed_cells
        if changed_cells > 0:
            prev_bytes = bytes(prev_screen)
            cur_bytes = bytes(current.raw_screen_codes)
            for r in range(25):
                old_row = _decode_row_ascii(prev_bytes, r)
                new_row = _decode_row_ascii(cur_bytes, r)
                if old_row != new_row:
                    diff.screen_row_changes.append(f"Row {r:02d}: \"{old_row}\" -> \"{new_row}\"")

    return diff


class DeploymentValidator:
    """
    Executes post-deployment verification against C64U hardware and maintains
    previous deployment state for automated diff generation.
    """

    def __init__(self, state_file: Optional[Path] = DEFAULT_STATE_FILE):
        self.state_file = state_file
        self._last_report_dict: Optional[Dict[str, Any]] = None
        if self.state_file and self.state_file.is_file():
            try:
                self._last_report_dict = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                self._last_report_dict = None

    def validate_deployment(
        self,
        client: C64UClient,
        source_name: str,
        prg_path: Optional[Union[str, Path]] = None,
        compilation_result: Optional[CompilationResult] = None,
        assembler_used: str = "kickass",
        execution_mode: str = "DMA_RUN",
        load_and_exec_success: bool = False,
        runner_response: str = "",
        execution_error: Optional[str] = None,
        settle_delay_sec: float = 0.08,
        watch_addresses: Optional[List[Tuple[int, int]]] = None,
    ) -> DeploymentValidationReport:
        """
        Collect compilation, firmware, execution, Screen RAM, register telemetry,
        and compute differences from the previous deployment.
        """
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        comp_ok = True if compilation_result is None else compilation_result.success
        comp_out = ""
        if compilation_result is not None:
            comp_out = compilation_result.error_message or compilation_result.stderr or compilation_result.stdout or ""
            if compilation_result.output_prg and prg_path is None:
                prg_path = compilation_result.output_prg

        resolved_prg = Path(prg_path).resolve() if prg_path else None
        prg_size = 0
        payload_size = 0
        load_addr: Optional[int] = None
        end_addr: Optional[int] = None
        prg_hash = ""

        if resolved_prg and resolved_prg.is_file():
            raw_prg = resolved_prg.read_bytes()
            prg_size = len(raw_prg)
            prg_hash = hashlib.sha256(raw_prg).hexdigest()[:16]
            if len(raw_prg) >= 2:
                load_addr = raw_prg[0] | (raw_prg[1] << 8)
                payload_size = len(raw_prg) - 2
                end_addr = load_addr + payload_size

        report = DeploymentValidationReport(
            timestamp=now_str,
            source_name=source_name,
            compilation_success=comp_ok,
            assembler_used=assembler_used,
            prg_path=str(resolved_prg) if resolved_prg else None,
            prg_size_bytes=prg_size,
            payload_size_bytes=payload_size,
            load_address=load_addr,
            end_address=end_addr,
            prg_sha256=prg_hash,
            compiler_output=comp_out,
            c64u_host=client.host,
            c64u_port=client.port,
            execution_mode=execution_mode,
            load_and_exec_success=load_and_exec_success,
            runner_response=str(runner_response),
            execution_error=execution_error,
        )

        # Query C64U device/firmware info
        try:
            info = client.get_info()
            report.c64u_connected = True
            report.device_info = dict(info) if isinstance(info, dict) else {"info": str(info)}
            report.firmware_version = str(
                report.device_info.get("version")
                or report.device_info.get("firmware")
                or report.device_info.get("product")
                or "ONLINE"
            )
        except Exception as exc:
            report.c64u_connected = False
            if not report.execution_error:
                report.execution_error = str(exc)

        # If connected and program executed, wait briefly for 6510 init code to settle before sampling RAM
        if report.c64u_connected:
            if load_and_exec_success and settle_delay_sec > 0:
                time.sleep(settle_delay_sec)

            # Capture Screen RAM ($0400-$07E7) and Color RAM ($D800-$DBE7)
            try:
                screen_mem = client.read_memory(0x0400, 1000)
                color_mem: Optional[bytes] = None
                try:
                    color_mem = client.read_memory(0xD800, 1000)
                except Exception:
                    pass

                if screen_mem and len(screen_mem) >= 1000:
                    report.screen_captured = True
                    report.raw_screen_codes = list(screen_mem[:1000])
                    if color_mem:
                        report.raw_color_codes = list(color_mem[:1000])
                    report.screen_ascii = format_screen(screen_mem, color_mem, use_ansi=False)
                    # Screen code 0x20 (32) is space
                    report.non_blank_chars = sum(1 for b in screen_mem[:1000] if b not in {0x20, 0xA0})
                    for r in range(25):
                        row_str = _decode_row_ascii(screen_mem, r)
                        if row_str.strip():
                            report.active_screen_rows.append((r, row_str))
            except Exception:
                pass

            # Capture Selected Hardware & OS Registers
            report.registers = _capture_registers(client)

            # Capture any custom watched memory ranges
            if watch_addresses:
                for addr, length in watch_addresses:
                    try:
                        w_bytes = client.read_memory(addr, max(1, min(64, length)))
                        hex_dump = " ".join(f"{b:02X}" for b in w_bytes)
                        report.watched_memory[f"${addr:04X} ({len(w_bytes)}B)"] = hex_dump
                    except Exception:
                        pass

        # Compute diff against previous deployment
        report.diff = _compute_diff(report, self._last_report_dict)

        # Save current report as the new baseline for next deployment
        if report.compilation_success:
            self._last_report_dict = report.to_dict()
            if self.state_file:
                try:
                    self.state_file.write_text(json.dumps(self._last_report_dict, indent=2), encoding="utf-8")
                except Exception:
                    pass

        return report
