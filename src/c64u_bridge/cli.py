"""
Hub Launcher for C64 Studio & C64U Antigravity Bridge.

Launches the full-screen Tkinter **C64 Studio** (`c64_studio.py`) multi-language IDE
(6502 Assembly, C/Oscar64, Python + Google Antigravity CLI) as the central hub by default,
while routing headless `mcp` invocations to the Model Context Protocol stdio server
(`server.py`) for Google Antigravity agents.
"""

from __future__ import annotations

import sys
from typing import Optional


def main(argv: Optional[list[str]] = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)

    # Headless MCP server mode for Google Antigravity AI agents
    if args and args[0].lower() == "mcp":
        from .server import run_stdio_server

        run_stdio_server()
        return

    # Subcommand aliases (`c64u-bridge c64-studio`, `studio`, `tui`) -> boot into C64 Studio
    if args and args[0].lower() in ("c64-studio", "studio", "tui"):
        args = args[1:]

    from .c64_studio import main as run_studio_hub

    run_studio_hub(args)


if __name__ == "__main__":
    main()
