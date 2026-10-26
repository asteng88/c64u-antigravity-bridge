"""
C64 Cross-Compiler & Assembler Orchestrator
Compiles 6502/6510 Assembly, C, and BASIC source code into Commodore 64 binaries (.prg).
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union


from .env import find_default_kickass_jar, load_env

# Ensure .env is loaded
load_env()

KICKASS_FRONT_PAGE_URL = "http://theweb.dk/KickAssembler/_FrontPage.html"
KICKASS_UPDATES_URL = "http://theweb.dk/KickAssembler/_Updates.html"
KICKASS_DOWNLOAD_URL = "http://theweb.dk/KickAssembler/KickAssembler.zip"


def _parse_version_tuple(ver_str: Optional[str]) -> Tuple[int, ...]:
    """Convert version string like '5.25' into a comparable integer tuple (5, 25)."""
    if not ver_str:
        return (0,)
    nums = [int(p) for p in re.findall(r"\d+", ver_str)]
    return tuple(nums) if nums else (0,)


@dataclass
class KickAssVersionStatus:
    """Result of checking installed vs. upstream KickAssembler version."""
    installed_version: Optional[str]
    latest_version: Optional[str]
    update_available: bool
    jar_path: Path
    download_url: str = KICKASS_DOWNLOAD_URL
    has_decompiler: bool = False  # KickAss.jar is a macro assembler only; no built-in decompiler class
    status_message: str = ""
    error: Optional[str] = None


@dataclass
class CompilationResult:
    success: bool
    output_prg: Optional[Path]
    stdout: str
    stderr: str
    symbol_file: Optional[Path] = None
    output_tap: Optional[Path] = None
    output_d64: Optional[Path] = None
    error_message: Optional[str] = None

    def to_tap(self, tap_path: Optional[Union[str, Path]] = None, tape_name: Optional[str] = None) -> Optional[Path]:
        """Convert the compiled PRG binary to a standard .tap cassette tape image."""
        if not self.success or not self.output_prg or not self.output_prg.exists():
            return None
        from .tap import save_prg_to_tap
        tap = save_prg_to_tap(self.output_prg, tap_path=tap_path, tape_name=tape_name)
        self.output_tap = tap
        return tap

    def to_d64(
        self,
        d64_path: Optional[Union[str, Path]] = None,
        disk_name: Optional[str] = None,
        disk_id: str = "2A",
    ) -> Optional[Path]:
        """Package the compiled PRG binary into a standard 1541 .d64 disk image."""
        if not self.success or not self.output_prg or not self.output_prg.exists():
            return None
        from .d64 import save_prg_to_d64
        d64 = save_prg_to_d64(self.output_prg, d64_path=d64_path, disk_name=disk_name, disk_id=disk_id)
        self.output_d64 = d64
        return d64


class CrossCompiler:
    """Orchestrates cross-compilation for 6502 assembly and C targets."""

    def __init__(
        self,
        kickass_jar: Optional[str] = None,
        acme_bin: Optional[str] = None,
        cc65_bin: Optional[str] = None,
    ):
        detected_jar = find_default_kickass_jar()
        default_jar = str(detected_jar) if detected_jar else "KickAss.jar"
        self.kickass_jar = kickass_jar or os.getenv("KICKASS_JAR") or default_jar
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

    def compile_to_tap(
        self,
        source_path: Union[Path, str],
        output_tap: Optional[Union[Path, str]] = None,
        tape_name: Optional[str] = None,
        assembler: str = "auto",
        extra_flags: Optional[List[str]] = None,
    ) -> CompilationResult:
        """
        Compile source file to PRG and automatically export to a Commodore 64 .tap cassette image.
        """
        res = self.compile(source_path=source_path, assembler=assembler, extra_flags=extra_flags)
        if res.success and res.output_prg:
            res.to_tap(tap_path=output_tap, tape_name=tape_name)
        return res

    def compile_to_d64(
        self,
        source_path: Union[Path, str],
        output_d64: Optional[Union[Path, str]] = None,
        disk_name: Optional[str] = None,
        disk_id: str = "2A",
        assembler: str = "auto",
        extra_flags: Optional[List[str]] = None,
    ) -> CompilationResult:
        """
        Compile source file to PRG and automatically package into a standard 1541 .d64 disk image.
        """
        res = self.compile(source_path=source_path, assembler=assembler, extra_flags=extra_flags)
        if res.success and res.output_prg:
            res.to_d64(d64_path=output_d64, disk_name=disk_name, disk_id=disk_id)
        return res

    def get_installed_kickass_version(self) -> Optional[str]:
        """
        Query the local KickAss.jar for its version string (e.g. '5.25').
        First attempts `java -jar KickAss.jar`, with a fallback to scanning KickAss.jar binary strings.
        """
        jar_path = Path(self.kickass_jar)
        if not jar_path.exists():
            return None

        java_cmd = shutil.which("java") or "java"
        try:
            res = subprocess.run(
                [java_cmd, "-jar", str(jar_path)],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            m = re.search(r"Kick\s+Assembler\s+v?(\d+\.\d+[a-z0-9]*)", combined, re.IGNORECASE)
            if m:
                return m.group(1)
        except Exception:
            pass

        # Fallback: scan class constants inside KickAss.jar without launching JVM
        try:
            with zipfile.ZipFile(jar_path, "r") as zf:
                for name in zf.namelist():
                    if name.endswith("KickAssembler.class") or name.endswith("Version.class"):
                        raw = zf.read(name).decode("latin-1", errors="ignore")
                        m = re.search(r"v?(\d+\.\d{1,3})", raw)
                        if m:
                            return m.group(1)
        except Exception:
            pass

        return None

    def get_latest_kickass_version(self, timeout: float = 4.0) -> Optional[str]:
        """
        Query the official KickAssembler website (theweb.dk/KickAssembler) for the latest release version.
        """
        for url in (KICKASS_FRONT_PAGE_URL, KICKASS_UPDATES_URL):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "C64U-Antigravity-Bridge/1.0 (KickAssembler Version Checker)"},
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                m = re.search(r"Kick\s*Assembler\s*V?(\d+\.\d+[a-z0-9]*)", html, re.IGNORECASE)
                if m:
                    return m.group(1)
            except Exception:
                continue
        return None

    def check_kickass_version(self, timeout: float = 4.0) -> KickAssVersionStatus:
        """
        Compare the locally installed KickAssembler version against the latest upstream release.
        Also notes that KickAss.jar is an assembler only (has_decompiler=False), so our built-in
        KickAssembler v5.x reverse decompiler handles decompilation.
        """
        jar_path = Path(self.kickass_jar)
        installed = self.get_installed_kickass_version()
        latest = self.get_latest_kickass_version(timeout=timeout)

        if installed is None and not jar_path.exists():
            return KickAssVersionStatus(
                installed_version=None,
                latest_version=latest,
                update_available=True,
                jar_path=jar_path,
                status_message=(
                    f"KickAssembler JAR not found at {jar_path}. "
                    + (f"Latest upstream is v{latest}." if latest else "Download available.")
                ),
            )

        if latest is None:
            return KickAssVersionStatus(
                installed_version=installed,
                latest_version=None,
                update_available=False,
                jar_path=jar_path,
                status_message=f"KickAssembler v{installed or '?'} installed (offline / could not reach theweb.dk).",
                error="Could not reach official KickAssembler server to check for updates.",
            )

        inst_tuple = _parse_version_tuple(installed)
        lat_tuple = _parse_version_tuple(latest)
        update_avail = lat_tuple > inst_tuple

        if update_avail:
            msg = f"KickAssembler update available: installed v{installed or '?'} -> latest v{latest}!"
        else:
            msg = f"KickAssembler v{installed} is up to date (latest upstream: v{latest})."

        return KickAssVersionStatus(
            installed_version=installed,
            latest_version=latest,
            update_available=update_avail,
            jar_path=jar_path,
            status_message=msg,
        )

    def update_kickassembler(
        self,
        download_url: str = KICKASS_DOWNLOAD_URL,
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout: float = 20.0,
    ) -> Tuple[bool, str]:
        """
        Download the latest KickAssembler.zip from the official site and update KickAss.jar in place.
        """
        def _notify(msg: str) -> None:
            if progress_callback:
                progress_callback(msg)

        jar_path = Path(self.kickass_jar).resolve()
        target_dir = jar_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            _notify(f"DOWNLOADING KICKASSEMBLER FROM {download_url}...")
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "C64U-Antigravity-Bridge/1.0 (KickAssembler Updater)"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                zip_bytes = resp.read()

            _notify(f"EXTRACTING KICKASS.JAR ({len(zip_bytes):,} BYTES)...")
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                jar_entries = [n for n in zf.namelist() if n.lower().endswith("kickass.jar")]
                if not jar_entries:
                    return False, "Downloaded archive did not contain KickAss.jar."

                jar_data = zf.read(jar_entries[0])
                tmp_jar = jar_path.with_suffix(".jar.tmp")
                tmp_jar.write_bytes(jar_data)
                tmp_jar.replace(jar_path)

                # Also update KickAss.cfg if present in the archive
                cfg_entries = [n for n in zf.namelist() if n.lower().endswith("kickass.cfg")]
                if cfg_entries:
                    (target_dir / "KickAss.cfg").write_bytes(zf.read(cfg_entries[0]))

            new_ver = self.get_installed_kickass_version() or "latest"
            msg = f"KickAssembler successfully updated to v{new_ver} ({jar_path.name})."
            _notify(msg)
            return True, msg
        except Exception as exc:
            err = f"Failed to update KickAssembler: {exc}"
            _notify(err)
            return False, err
