"""
Command-Line Interface for C64U Antigravity Bridge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import C64UClient, C64UClientError
from .compiler import CrossCompiler
from .screen import format_screen
from .server import run_stdio_server, parse_address


def main():
    parser = argparse.ArgumentParser(
        prog="c64u-bridge",
        description="Commodore 64 Ultimate (C64U) Bridge & Antigravity MCP Server",
    )
    parser.add_argument("--host", help="C64U IP address or hostname (default: env C64U_HOST or c64u.local)")
    parser.add_argument("--port", type=int, default=80, help="C64U REST API port (default: 80)")
    parser.add_argument("--password", help="Optional C64U network password")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: run (build and execute)
    run_parser = subparsers.add_parser("run", help="Compile and DMA run source file or binary on C64U")
    run_parser.add_argument("file", help="Path to .asm, .s, .c, or .prg file")
    run_parser.add_argument("--assembler", choices=["auto", "kickass", "acme", "cc65"], default="auto")

    # Command: screen (dump screen buffer)
    screen_parser = subparsers.add_parser("screen", help="Inspect and display C64 screen memory ($0400-$07E7)")
    screen_parser.add_argument("--color", action="store_true", help="Enable ANSI color rendering")

    # Command: mem (read memory)
    mem_parser = subparsers.add_parser("mem", help="Dump memory block from C64")
    mem_parser.add_argument("address", help="16-bit address (e.g. '$0400', '0xD000', '1024')")
    mem_parser.add_argument("length", nargs="?", type=int, default=32, help="Number of bytes (default: 32)")

    # Command: write (write memory)
    write_parser = subparsers.add_parser("write", help="Write data to memory address")
    write_parser.add_argument("address", help="16-bit address (e.g. '$D020')")
    write_parser.add_argument("data", help="Hex string of bytes (e.g. '01' or 'A9 00 8D 20 D0')")

    # Command: reset
    reset_parser = subparsers.add_parser("reset", help="Reset the C64 machine")
    reset_parser.add_argument("--reboot", action="store_true", help="Reboot with cartridge reinitialization")

    # Command: type (send keys)
    type_parser = subparsers.add_parser("type", help="Inject keystrokes into C64 keyboard buffer")
    type_parser.add_argument("text", help="Text to type into the C64")

    # Command: status
    subparsers.add_parser("status", help="Get C64U connection and device status")

    # Command: mcp (start MCP server)
    subparsers.add_parser("mcp", help="Run the Model Context Protocol (MCP) server on stdio for Antigravity")

    args = parser.parse_args()

    if not args.command or args.command == "mcp":
        run_stdio_server()
        return

    client = C64UClient(host=args.host, port=args.port, password=args.password)
    compiler = CrossCompiler()

    try:
        if args.command == "run":
            path = Path(args.file)
            if not path.exists():
                print(f"Error: File not found: {path}", file=sys.stderr)
                sys.exit(1)

            if path.suffix.lower() == ".prg":
                print(f"Uploading and running {path.name}...")
                res = client.run_prg(path)
                print(f"Success: {res}")
            else:
                print(f"Compiling {path.name} with {args.assembler}...")
                result = compiler.compile(path, assembler=args.assembler)
                if not result.success:
                    print(f"Build failed:\n{result.error_message or result.stderr or result.stdout}", file=sys.stderr)
                    sys.exit(1)
                print(f"Build successful ({result.output_prg.name}). Deploying to C64U via DMA...")
                res = client.run_prg(result.output_prg)
                print(f"Success: {res}")

        elif args.command == "screen":
            screen_mem = client.read_memory(0x0400, 1000)
            color_mem = client.read_memory(0xD800, 1000)
            print(format_screen(screen_mem, color_mem, use_ansi=args.color))

        elif args.command == "mem":
            addr = parse_address(args.address)
            raw_bytes = client.read_memory(addr, args.length)
            for i in range(0, len(raw_bytes), 16):
                chunk = raw_bytes[i : i + 16]
                hex_part = " ".join(f"{b:02X}" for b in chunk)
                ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
                print(f"${addr + i:04X}: {hex_part:<48} | {ascii_part}")

        elif args.command == "write":
            addr = parse_address(args.address)
            res = client.write_memory(addr, args.data)
            print(f"Written data to ${addr:04X}: {res}")

        elif args.command == "reset":
            res = client.reset(reboot=args.reboot)
            print(f"Machine {res['action']} command sent.")

        elif args.command == "type":
            res = client.send_keys(args.text)
            print(f"Sent keys to keyboard buffer: {res}")

        elif args.command == "status":
            info = client.get_info()
            print("C64U Hardware Status:")
            for k, v in info.items():
                print(f"  {k}: {v}")

    except C64UClientError as e:
        print(f"C64U Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
