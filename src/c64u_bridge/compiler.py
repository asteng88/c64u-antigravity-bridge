"""
C64 Cross-Compiler & Assembler Orchestrator
Compiles 6502/6510 Assembly, C, and BASIC source code into Commodore 64 binaries (.prg).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CompilationResult:
    success: bool
    output_prg: Optional[Path]
    stdout: str
    stderr: str
    symbol_file: Optional[Path] = None
    error_message: Optional[str] = None


class CrossCompiler:
    """Orchestrates cross-compilation for 6502 assembly and C targets."""

    def __init__(
        self,
        kickass_jar: Optional[str] = None,
        acme_bin: Optional[str] = None,
        cc65_bin: Optional[str] = None,
    ):
        self.kickass_jar = kickass_jar or os.getenv("KICKASS_JAR", "KickAss.jar")
        self.acme_bin = acme_bin or os.getenv("ACME_BIN", "acme")
        self.cc65_bin = cc65_bin or os.getenv("CC65_BIN", "cl65")

    def detect_assembler(self, source_path: Path) -> str:
        """Infer best assembler based on file extension and content directives."""
        suffix = source_path.suffix.lower()
        if suffix in [".c", ".h"]:
            return "cc65"
        
        # Check source content for assembler-specific syntax
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
            if "BasicUpstart2" in content or ".pseudopc" in content or ".filenamespace" in content:
                return "kickass"
            if "!to" in content or "!src" in content or "!zone" in content:
                return "acme"
        except Exception:
            pass

        return "kickass"

    def compile(
        self,
        source_path: Union[Path, str],
        output_prg: Optional[Union[Path, str]] = None,
        assembler: str = "auto",
        extra_flags: Optional[List[str]] = None,
    ) -> CompilationResult:
        """
        Compile a source file into a C64 PRG.
        
        Args:
            source_path: Path to source file (.asm, .s, .c).
            output_prg: Optional destination .prg path.
            assembler: 'kickass', 'acme', 'cc65', or 'auto'.
            extra_flags: Additional compiler flags.
        """
        src = Path(source_path).resolve()
        if not src.exists():
            return CompilationResult(
                success=False,
                output_prg=None,
                stdout="",
                stderr="",
                error_message=f"Source file not found: {src}",
            )

        out = Path(output_prg).resolve() if output_prg else src.with_suffix(".prg")
        asm = self.detect_assembler(src) if assembler == "auto" else assembler.lower()
        flags = extra_flags or []

        if asm == "kickass":
            return self._compile_kickass(src, out, flags)
        elif asm == "acme":
            return self._compile_acme(src, out, flags)
        elif asm in ["cc65", "cl65"]:
            return self._compile_cc65(src, out, flags)
        else:
            return CompilationResult(
                success=False,
                output_prg=None,
                stdout="",
                stderr="",
                error_message=f"Unsupported assembler target: {asm}",
            )

    def _compile_kickass(self, src: Path, out: Path, flags: List[str]) -> CompilationResult:
        """Invoke KickAssembler via Java runtime."""
        java_cmd = shutil.which("java") or "java"
        cmd = [
            java_cmd,
            "-jar",
            self.kickass_jar,
            str(src),
            "-o",
            str(out),
            "-vicesymbols",
        ] + flags

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=src.parent)
            sym_file = out.with_suffix(".vs")
            return CompilationResult(
                success=(res.returncode == 0 and out.exists()),
                output_prg=out if out.exists() else None,
                stdout=res.stdout,
                stderr=res.stderr,
                symbol_file=sym_file if sym_file.exists() else None,
                error_message=None if res.returncode == 0 else (res.stderr or res.stdout),
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                output_prg=None,
                stdout="",
                stderr=str(e),
                error_message=f"KickAssembler execution error: {e}",
            )

    def _compile_acme(self, src: Path, out: Path, flags: List[str]) -> CompilationResult:
        """Invoke ACME Cross-Assembler."""
        cmd = [self.acme_bin, "-f", "cbm", "-o", str(out), str(src)] + flags
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=src.parent)
            return CompilationResult(
                success=(res.returncode == 0 and out.exists()),
                output_prg=out if out.exists() else None,
                stdout=res.stdout,
                stderr=res.stderr,
                error_message=None if res.returncode == 0 else (res.stderr or res.stdout),
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                output_prg=None,
                stdout="",
                stderr=str(e),
                error_message=f"ACME execution error: {e}",
            )

    def _compile_cc65(self, src: Path, out: Path, flags: List[str]) -> CompilationResult:
        """Invoke CC65 cl65 toolchain for C code."""
        cmd = [self.cc65_bin, "-O", "-t", "c64", "-o", str(out), str(src)] + flags
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, cwd=src.parent)
            return CompilationResult(
                success=(res.returncode == 0 and out.exists()),
                output_prg=out if out.exists() else None,
                stdout=res.stdout,
                stderr=res.stderr,
                error_message=None if res.returncode == 0 else (res.stderr or res.stdout),
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                output_prg=None,
                stdout="",
                stderr=str(e),
                error_message=f"CC65 execution error: {e}",
            )
