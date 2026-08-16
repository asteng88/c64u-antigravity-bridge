"""
C64U REST API Client
Provides synchronous and asynchronous methods to interact with the Commodore 64 Ultimate (C64U) hardware.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import httpx


class C64UClientError(Exception):
    """Base exception for C64U client operations."""
    pass


class C64UClient:
    """Client for controlling the Commodore 64 Ultimate (C64U) via its HTTP REST API."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 80,
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
        self.port = int(os.getenv("C64U_PORT", str(port)))
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

    def read_memory(self, address: int, length: int) -> bytes:
        """
        Read a block of memory from the C64.
        
        Args:
            address: 16-bit start address in hex/int (e.g. 0x0400 for Screen RAM, 0xD000 for VIC-II).
            length: Number of bytes to read.
        """
        url = f"{self.base_url}/machine:read_mem"
        params = {"address": f"{address:04X}", "length": str(length)}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params, headers=self._headers())
                res.raise_for_status()
                # API returns raw binary or hex string depending on headers
                return res.content
        except Exception as e:
            raise C64UClientError(f"Failed to read memory at ${address:04X}: {e}") from e

    def write_memory(self, address: int, data: Union[bytes, List[int], str]) -> Dict[str, Any]:
        """
        Write data directly into C64 memory / registers.
        
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

        url = f"{self.base_url}/machine:write_mem"
        params = {"address": f"{address:04X}"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, params=params, content=payload, headers=self._headers())
                res.raise_for_status()
                return res.json() if res.content else {"status": "success", "bytes_written": len(payload)}
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
