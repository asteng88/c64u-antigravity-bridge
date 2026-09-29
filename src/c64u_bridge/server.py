"""
Model Context Protocol (MCP) Server for Google Antigravity & AI Agents
Bridges Antigravity development sessions directly to Commodore 64 Ultimate hardware.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .client import C64UClient, C64UClientError
from .compiler import CrossCompiler
from .screen import format_screen


def create_tool_definitions() -> List[Dict[str, Any]]:
    """Return JSON schema tool specifications for Antigravity."""
    return [
        {
            "name": "c64_build_and_run",
            "description": "Compiles 6502 assembly or C source code into a C64 PRG binary and executes it immediately on the Commodore 64 Ultimate (C64U) via DMA.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Absolute or relative path to the 6502 assembly (.asm/.s) or C source file."
                    },
                    "assembler": {
                        "type": "string",
                        "enum": ["auto", "kickass", "acme", "cc65"],
                        "default": "auto",
                        "description": "Cross-assembler to invoke. Defaults to auto-detection based on file syntax."
                    }
                },
                "required": ["source_path"]
            }
        },
        {
            "name": "c64_run_binary",
            "description": "Uploads and executes an existing compiled .prg binary directly onto the C64U hardware via DMA.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "prg_path": {
                        "type": "string",
                        "description": "Path to the .prg file."
                    }
                },
                "required": ["prg_path"]
            }
        },
        {
            "name": "c64_play_sid",
            "description": "Uploads a PSID/RSID music file and starts it in the C64U built-in SID player.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sid_path": {
                        "type": "string",
                        "description": "Path to the .sid file."
                    },
                    "song": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Optional one-based subtune number; omit to use the file default."
                    }
                },
                "required": ["sid_path"]
            }
        },
        {
            "name": "c64_compile_sid",
            "description": "Assembles a C64U-decompiled ASM/Python source back into a PSID/RSID file.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to the decompiled .asm, .s, or .py source."
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Optional destination .sid path."
                    },
                    "template_path": {
                        "type": "string",
                        "description": "Optional original .sid file for metadata preservation."
                    },
                    "assembler": {
                        "type": "string",
                        "enum": ["kickass", "acme"],
                        "default": "kickass"
                    }
                },
                "required": ["source_path"]
            }
        },
        {
            "name": "c64_inspect_screen",
            "description": "Reads the C64 standard Screen RAM ($0400-$07E7) and Color RAM ($D800-$DBE7) from hardware and returns a formatted 40x25 ASCII grid.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "use_ansi_colors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to return ANSI colored escape sequences."
                    }
                }
            }
        },
        {
            "name": "c64_read_memory",
            "description": "Reads a block of memory from the C64 (e.g. Zero Page $0000-$00FF, VIC-II $D000, SID $D400, or program space).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "16-bit address in hex (e.g. '$0400', '0xD000', or 'd020') or integer."
                    },
                    "length": {
                        "type": "integer",
                        "default": 32,
                        "description": "Number of bytes to read."
                    }
                },
                "required": ["address"]
            }
        },
        {
            "name": "c64_write_memory",
            "description": "Writes byte values directly into C64 memory or hardware registers via DMA.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "16-bit address in hex or decimal."
                    },
                    "data": {
                        "type": "string",
                        "description": "Space-separated or contiguous hex string of bytes (e.g. 'A9 01 8D 20 D0' or '00FF01')."
                    }
                },
                "required": ["address", "data"]
            }
        },
        {
            "name": "c64_control",
            "description": "Sends hardware control commands to the C64 (reset, reboot, pause, resume).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["reset", "reboot", "pause", "resume"],
                        "description": "Hardware control action to execute."
                    }
                },
                "required": ["action"]
            }
        },
        {
            "name": "c64_send_keys",
            "description": "Injects text keystrokes directly into the C64 keyboard buffer (e.g. typing BASIC commands).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to type into the C64. Use \\r for Return."
                    }
                },
                "required": ["text"]
            }
        },
        {
            "name": "c64_status",
            "description": "Checks connectivity and retrieves firmware and device information from the C64U hardware.",
            "inputSchema": {
                "type": "object",
                "properties": {}
            }
        }
    ]


def parse_address(addr_str: str) -> int:
    """Parse address string supporting $, 0x, and decimal formats."""
    s = addr_str.strip()
    if s.startswith("$"):
        return int(s[1:], 16)
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    try:
        return int(s, 16) if any(c in "abcdefABCDEF" for c in s) else int(s)
    except ValueError:
        return int(s, 16)


class MCPServerHandler:
    """Handles MCP tool invocations and state."""

    def __init__(self, client: Optional[C64UClient] = None, compiler: Optional[CrossCompiler] = None):
        self.client = client or C64UClient()
        self.compiler = compiler or CrossCompiler()

    def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Route tool calls to appropriate backend methods."""
        try:
            if name == "c64_build_and_run":
                src_path = args.get("source_path")
                assembler = args.get("assembler", "auto")
                result = self.compiler.compile(src_path, assembler=assembler)
                if not result.success:
                    return f"❌ Compilation Failed:\n{result.error_message or result.stderr or result.stdout}"

                res = self.client.run_prg(result.output_prg)
                return (
                    f"✅ Successfully compiled {Path(src_path).name} to {result.output_prg.name} "
                    f"and launched on C64U via DMA.\n"
                    f"Runner Response: {res}"
                )

            elif name == "c64_run_binary":
                prg_path = Path(args.get("prg_path"))
                if not prg_path.exists():
                    return f"❌ File not found: {prg_path}"
                res = self.client.run_prg(prg_path)
                return f"✅ Executed {prg_path.name} on C64U via DMA: {res}"

            elif name == "c64_play_sid":
                sid_path = Path(args.get("sid_path"))
                if not sid_path.is_file():
                    return f"❌ File not found: {sid_path}"
                if sid_path.suffix.lower() != ".sid":
                    return f"❌ Expected a .sid file: {sid_path}"
                song = args.get("song")
                res = self.client.play_sid(sid_path, song=int(song) if song is not None else None)
                tune = f"subtune {song}" if song is not None else "default subtune"
                return f"✅ Playing {sid_path.name} ({tune}) on the C64U SID player: {res}"

            elif name == "c64_compile_sid":
                from .sid_compiler import compile_sid_source

                source_path = Path(args.get("source_path"))
                if not source_path.is_file():
                    return f"❌ File not found: {source_path}"
                result = compile_sid_source(
                    source_path,
                    output_sid=args.get("output_path"),
                    template_sid=args.get("template_path"),
                    assembler=args.get("assembler", "kickass"),
                    compiler=self.compiler,
                )
                h = result.sid.header
                return (
                    f"✅ Compiled {source_path.name} to {result.output_sid.name} "
                    f"({result.payload_size} bytes, load ${h.load_address:04X}, "
                    f"init ${h.init_address:04X}, play ${h.play_address:04X})"
                )

            elif name == "c64_inspect_screen":
                screen_mem = self.client.read_memory(0x0400, 1000)
                color_mem = self.client.read_memory(0xD800, 1000)
                formatted = format_screen(
                    screen_mem,
                    color_mem,
                    use_ansi=args.get("use_ansi_colors", False),
                )
                return f"📺 Current C64 Screen Buffer ($0400-$07E7):\n{formatted}"

            elif name == "c64_read_memory":
                addr = parse_address(str(args.get("address")))
                length = int(args.get("length", 32))
                raw_bytes = self.client.read_memory(addr, length)

                # Format hex dump with ASCII sidebar
                lines = []
                for i in range(0, len(raw_bytes), 16):
                    chunk = raw_bytes[i : i + 16]
                    hex_part = " ".join(f"{b:02X}" for b in chunk)
                    ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                    lines.append(f"${addr + i:04X}: {hex_part:<48} | {ascii_part}")
                return "\n".join(lines)

            elif name == "c64_write_memory":
                addr = parse_address(str(args.get("address")))
                data = args.get("data", "")
                res = self.client.write_memory(addr, data)
                return f"✅ Written data to ${addr:04X}: {res}"

            elif name == "c64_control":
                action = args.get("action")
                if action == "reset":
                    res = self.client.reset(reboot=False)
                elif action == "reboot":
                    res = self.client.reset(reboot=True)
                elif action == "pause":
                    res = self.client.pause()
                elif action == "resume":
                    res = self.client.resume()
                else:
                    return f"❌ Unknown action: {action}"
                return f"✅ Machine control executed: {res}"

            elif name == "c64_send_keys":
                text = args.get("text", "")
                res = self.client.send_keys(text)
                return f"✅ Keystrokes sent to keyboard buffer: {res}"

            elif name == "c64_status":
                info = self.client.get_info()
                return f"🖥️ C64U Status:\n{json.dumps(info, indent=2)}"

            else:
                return f"❌ Unrecognized tool: {name}"

        except C64UClientError as e:
            return f"❌ C64U Communication Error: {e}"
        except Exception as e:
            return f"❌ Error executing {name}: {e}"


def run_stdio_server():
    """Run standard JSON-RPC 2.0 MCP server over stdio for Antigravity integration."""
    handler = MCPServerHandler()
    tools = create_tool_definitions()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "c64u-antigravity-bridge",
                            "version": "0.1.0"
                        },
                        "capabilities": {
                            "tools": {}
                        }
                    }
                }
            elif method == "tools/list":
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "tools": tools
                    }
                }
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result_text = handler.execute_tool(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ]
                    }
                }
            elif method == "notifications/initialized":
                continue
            else:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }

            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


def main():
    run_stdio_server()


if __name__ == "__main__":
    main()
