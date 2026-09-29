"""
C64U REST API Client
Provides synchronous and asynchronous methods to interact with the Commodore 64 Ultimate (C64U) hardware.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import httpx

from .env import load_env

# Ensure .env is loaded
load_env()


class C64UClientError(Exception):
    """Base exception for C64U client operations."""
    pass


class C64UClient:
    """Client for controlling the Commodore 64 Ultimate (C64U) via its HTTP REST API."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize the C64U REST client.
        
        Args:
            host: IP address or hostname of the C64U (defaults to env C64U_HOST or 'c64u.local').
            port: REST API port (defaults to env C64U_PORT or 80).
            password: Optional network security password (defaults to env C64U_PASSWORD).
            timeout: Request timeout in seconds.
        """
        self.host = host or os.getenv("C64U_HOST", "c64u.local")
        if port is not None:
            self.port = port
        elif os.getenv("C64U_PORT"):
            self.port = int(os.environ["C64U_PORT"])
        else:
            self.port = 80
        self.password = password or os.getenv("C64U_PASSWORD")
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}/v1"

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if self.password:
            headers["X-Password"] = self.password
        return headers

    def get_info(self) -> Dict[str, Any]:
        """Fetch device information, firmware version, and hardware status."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(f"{self.base_url}/info", headers=self._headers())
                if res.status_code == 200:
                    return res.json()
                # Fallback to /about endpoint if /info is not present on older firmware
                about_res = client.get(f"{self.base_url}/about", headers=self._headers())
                about_res.raise_for_status()
                return about_res.json()
        except Exception as e:
            raise C64UClientError(f"Failed to connect to C64U at {self.base_url}: {e}") from e

    def run_prg(self, prg: Union[bytes, Path, str]) -> Dict[str, Any]:
        """
        DMA upload and execute a compiled Commodore 64 .prg binary immediately.
        
        Args:
            prg: Raw binary bytes or path to the .prg file.
        """
        data = prg.read_bytes() if isinstance(prg, Path) else (Path(prg).read_bytes() if isinstance(prg, str) else prg)
        url = f"{self.base_url}/runners:run_prg"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, content=data, headers=self._headers())
                res.raise_for_status()
                return res.json() if res.content else {"status": "success", "bytes_sent": len(data)}
        except Exception as e:
            raise C64UClientError(f"Failed to DMA run PRG: {e}") from e

    def load_prg(self, prg: Union[bytes, Path, str]) -> Dict[str, Any]:
        """DMA load a .prg into memory at its start address without automatic execution."""
        data = prg.read_bytes() if isinstance(prg, Path) else (Path(prg).read_bytes() if isinstance(prg, str) else prg)
        url = f"{self.base_url}/runners:load_prg"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, content=data, headers=self._headers())
                res.raise_for_status()
                return res.json() if res.content else {"status": "success", "bytes_sent": len(data)}
        except Exception as e:
            raise C64UClientError(f"Failed to DMA load PRG: {e}") from e

    def run_crt(self, crt: Union[bytes, Path, str]) -> Dict[str, Any]:
        """Upload and execute a Cartridge image (.crt)."""
        data = crt.read_bytes() if isinstance(crt, Path) else (Path(crt).read_bytes() if isinstance(crt, str) else crt)
        url = f"{self.base_url}/runners:run_crt"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, content=data, headers=self._headers())
                res.raise_for_status()
                return res.json() if res.content else {"status": "success", "bytes_sent": len(data)}
        except Exception as e:
            raise C64UClientError(f"Failed to run Cartridge: {e}") from e

    def play_sid(
        self,
        sid: Union[bytes, Path, str],
        song: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Upload a PSID/RSID file and start the Ultimate's built-in SID player.

        Args:
            sid: Raw SID bytes or a path to a .sid file.
            song: Optional one-based subtune number. The SID's default is used
                when this is omitted.
        """
        if song is not None and song < 1:
            raise ValueError("SID song number must be 1 or greater")

        if isinstance(sid, Path):
            data = sid.read_bytes()
            filename = sid.name
        elif isinstance(sid, str):
            path = Path(sid)
            data = path.read_bytes()
            filename = path.name
        else:
            data = sid
            filename = "music.sid"

        headers = self._headers()
        headers.update(
            {
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{filename.replace(chr(34), "_")}"',
            }
        )
        params = {"songnr": str(song)} if song is not None else None
        url = f"{self.base_url}/runners:sidplay"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, content=data, params=params, headers=headers)
                res.raise_for_status()
                result = res.json() if res.content else {"status": "success"}
                errors = result.get("errors", []) if isinstance(result, dict) else []
                if errors:
                    raise C64UClientError("; ".join(str(error) for error in errors))
                if isinstance(result, dict):
                    result.setdefault("bytes_sent", len(data))
                return result
        except C64UClientError:
            raise
        except Exception as e:
            raise C64UClientError(f"Failed to play SID on C64U: {e}") from e

    def read_memory(self, address: int, length: int) -> bytes:
        """
        Read a block of memory from the C64 via DMA.
        
        Args:
            address: 16-bit start address in hex/int (e.g. 0x0400 for Screen RAM, 0xD000 for VIC-II).
            length: Number of bytes to read.
        """
        params = {"address": f"{address:04X}", "length": str(length)}
        headers = self._headers()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                # Official Ultimate 64 endpoint: /machine:readmem (without underscore)
                url = f"{self.base_url}/machine:readmem"
                res = client.get(url, params=params, headers=headers)
                if res.status_code == 404:
                    # Fallback to alternate naming if on non-standard firmware
                    res = client.get(f"{self.base_url}/machine:read_mem", params=params, headers=headers)
                res.raise_for_status()
                # API returns raw binary data
                return res.content
        except Exception as e:
            raise C64UClientError(f"Failed to read memory at ${address:04X}: {e}") from e

    def write_memory(self, address: int, data: Union[bytes, List[int], str]) -> Dict[str, Any]:
        """
        Write data directly into C64 memory / registers via DMA.
        
        Args:
            address: 16-bit start address.
            data: Raw bytes, list of integers, or hex string.
        """
        if isinstance(data, list):
            payload = bytes(data)
        elif isinstance(data, str):
            payload = bytes.fromhex(data.replace(" ", "").replace("$", ""))
        else:
            payload = data

        chunk_size = 64
        headers = self._headers()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                url = f"{self.base_url}/machine:writemem"
                for offset in range(0, len(payload), chunk_size):
                    chunk = payload[offset : offset + chunk_size]
                    cur_addr = address + offset
                    params = {"address": f"{cur_addr:04X}", "data": chunk.hex()}
                    res = client.put(url, params=params, headers=headers)
                    res.raise_for_status()
                return {"status": "success", "bytes_written": len(payload)}
        except Exception as e:
            raise C64UClientError(f"Failed to write memory at ${address:04X}: {e}") from e

    def reset(self, reboot: bool = False) -> Dict[str, Any]:
        """Reset or reboot the C64 machine."""
        endpoint = "reboot" if reboot else "reset"
        url = f"{self.base_url}/machine:{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.put(url, headers=self._headers())
                res.raise_for_status()
                return {"status": "success", "action": endpoint}
        except Exception as e:
            raise C64UClientError(f"Failed to {endpoint} machine: {e}") from e

    def pause(self) -> Dict[str, Any]:
        """Pause the 6510 CPU via DMA."""
        url = f"{self.base_url}/machine:pause"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.put(url, headers=self._headers())
                res.raise_for_status()
                return {"status": "paused"}
        except Exception as e:
            raise C64UClientError(f"Failed to pause machine: {e}") from e

    def resume(self) -> Dict[str, Any]:
        """Resume the 6510 CPU from paused state."""
        url = f"{self.base_url}/machine:resume"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.put(url, headers=self._headers())
                res.raise_for_status()
                return {"status": "resumed"}
        except Exception as e:
            raise C64UClientError(f"Failed to resume machine: {e}") from e

    def send_keys(self, text: str, delay_ms: int = 40) -> Dict[str, Any]:
        """
        Inject keystrokes directly into the C64 keyboard buffer.
        
        Args:
            text: String to type (supports PETSCII conversions and \r for Return).
            delay_ms: Inter-character delay in milliseconds.
        """
        url = f"{self.base_url}/machine:sendkey"
        payload = {"keys": text, "delay": delay_ms}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._headers())
                res.raise_for_status()
                return {"status": "keys_sent", "text": text}
        except Exception as e:
            raise C64UClientError(f"Failed to send keystrokes: {e}") from e
