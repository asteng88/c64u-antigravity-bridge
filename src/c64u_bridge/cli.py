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
    run_parser.add_argument("file", help="Path to .py, .asm, .s, .c, or .prg file")
    run_parser.add_argument("--assembler", choices=["auto", "kickass", "acme", "cc65"], default="auto")

    # Command: transpile (Python to 6502 asm)
    trans_parser = subparsers.add_parser("transpile", help="Convert Python source to MOS 6502 assembly")
    trans_parser.add_argument("file", help="Path to input Python file (.py)")
    trans_parser.add_argument("-o", "--output", help="Path to output .asm file")
    trans_parser.add_argument("--assembler", choices=["kickass", "acme"], default="kickass")
    trans_parser.add_argument("--assemble", action="store_true", help="Also assemble to PRG using KickAssembler")
    trans_parser.add_argument("--run", action="store_true", help="DMA execute immediately on C64U")

    # Command: tui (interactive Textual IDE)
    subparsers.add_parser("tui", help="Launch interactive Textual TUI for Python-to-Assembly development")

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

    if args.command == "tui":
        from .tui import main as run_tui
        run_tui()
        return

    if args.command == "transpile":
        from .transpiler import PythonTo6502Transpiler, TranspileOptions
        src_path = Path(args.file)
        if not src_path.exists():
            print(f"Error: File not found: {src_path}", file=sys.stderr)
            sys.exit(1)
        source_code = src_path.read_text(encoding="utf-8")
        out_path = Path(args.output) if args.output else src_path.with_suffix(".asm")
        opts = TranspileOptions(assembler=args.assembler, prg_name=out_path.with_suffix(".prg").name)
        transpiler = PythonTo6502Transpiler(opts)
        result = transpiler.transpile(source_code)
        if not result.success:
            print("Transpilation failed:", file=sys.stderr)
            for err in result.errors:
                print(f"  {err}", file=sys.stderr)
            sys.exit(1)
        out_path.write_text(result.assembly, encoding="utf-8")
        print(f"Transpiled {src_path.name} -> {out_path} ({len(result.assembly.splitlines())} lines asm)")

        if args.assemble or args.run:
            compiler = CrossCompiler()
            comp_res = compiler.compile(out_path, assembler=args.assembler)
            if not comp_res.success:
                print(f"Assembly failed:\n{comp_res.error_message or comp_res.stderr or comp_res.stdout}", file=sys.stderr)
                sys.exit(1)
            print(f"Assembled: {comp_res.output_prg}")
            if args.run:
                client = C64UClient(host=args.host, port=args.port, password=args.password)
                print(f"Deploying {comp_res.output_prg.name} to C64U via DMA...")
                res = client.run_prg(comp_res.output_prg)
                print(f"DMA Run Success: {res}")
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
            elif path.suffix.lower() == ".py":
                from .transpiler import PythonTo6502Transpiler, TranspileOptions
                print(f"Transpiling Python {path.name} to 6502 assembly...")
                asm_path = path.with_suffix(".asm")
                prg_path = path.with_suffix(".prg")
                opts = TranspileOptions(prg_name=prg_path.name)
                transpiler = PythonTo6502Transpiler(opts)
                trans_res = transpiler.transpile(path.read_text(encoding="utf-8"))
                if not trans_res.success:
                    print("Transpilation failed:", file=sys.stderr)
                    for err in trans_res.errors:
                        print(f"  {err}", file=sys.stderr)
                    sys.exit(1)
                asm_path.write_text(trans_res.assembly, encoding="utf-8")
                print(f"Compiling {asm_path.name} with KickAssembler...")
                comp_res = compiler.compile(asm_path, output_prg=prg_path, assembler="kickass")
                if not comp_res.success:
                    print(f"Assembly failed:\n{comp_res.error_message or comp_res.stderr or comp_res.stdout}", file=sys.stderr)
                    sys.exit(1)
                print(f"Build successful ({prg_path.name}). Deploying to C64U via DMA...")
                res = client.run_prg(prg_path)
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
