# C64U Antigravity Bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Enabled-purple.svg)](https://modelcontextprotocol.io/)
[![Hardware: Commodore 64 Ultimate](https://img.shields.io/badge/Hardware-C64U%20%2F%20Ultimate%2064-red.svg)](https://1541u-documentation.readthedocs.io/)

An agentic developer bridge connecting **[Google Antigravity](https://antigravity.google/docs/mcp)** to the **Commodore 64 Ultimate (C64U)**. 

Write 6502/6510 Assembly, C, or Commodore BASIC in Antigravity with AI assistance, cross-compile automatically, and execute binaries instantly on physical C64 hardware via direct Direct Memory Access (DMA) over the local network.

---

## 🌟 Key Features

* **Agent-Driven C64 Development**: Integrate with Google Antigravity agents to generate, refactor, and debug 6502 assembly and C programs.
* **Sub-Second DMA Deployment**: Bypass slow disk/tape loading routines. Code compiles and runs instantly on physical silicon using the C64U `/v1/runners:run_prg` REST API.
* **Real-Time Hardware Introspection**: 
  * Read and decode Screen RAM (`$0400–$07E7`) and Color RAM (`$D800–$DBE7`) into ASCII/ANSI grids.
  * Dump and inspect Zero Page (`$0000–$00FF`), VIC-II (`$D000`), SID (`$D400`), and custom memory ranges.
  * Direct memory POKE via DMA for live parameter and palette tweaking.
* **Multi-Assembler Toolchain**: Auto-detects and invokes **KickAssembler**, **ACME**, and **CC65 / cl65**.
* **Model Context Protocol (MCP)**: Native JSON-RPC 2.0 MCP server exposes compiler and hardware control tools to Antigravity.
* **Standalone CLI**: Full-featured command-line utility for manual script execution, memory inspection, and machine resets.

---

## 🏗️ Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │                      Google Antigravity                     │
 │          (Agent / IDE / CLI + C64 Development Rules)        │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Model Context Protocol (MCP) / STDIO
 ┌──────────────────────────────▼──────────────────────────────┐
 │                  c64u-antigravity-bridge                    │
 │  ┌───────────────────────┐       ┌────────────────────────┐ │
 │  │  Compiler Orchestrator│       │    C64U REST Client    │ │
 │  │(KickAss, ACME, CC65)  │       │ (DMA, Memory, Control) │ │
 │  └───────────────────────┘       └────────────────────────┘ │
 └──────────────────────────────┬──────────────────────────────┘
                                │ HTTP REST (Port 80)
 ┌──────────────────────────────▼──────────────────────────────┐
 │                Commodore 64 Ultimate (C64U)                 │
 │           (Ultimate-64 FPGA Core / Firmware 3.11+)          │
 └─────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

1. **Hardware**: 
   * Commodore 64 Ultimate (C64U) or Ultimate 64 mainboard connected to your local network (Ethernet or Wi-Fi).
   * Firmware 3.11+ with **Web Remote Control Service** enabled (default).
2. **Host Machine**:
   * Python 3.10 or later (managed with [`uv`](https://github.com/astral-sh/uv) recommended).
   * Java Runtime Environment (for KickAssembler) or ACME / CC65 binaries in PATH.

---

## 🚀 Quick Start

### 1. Interactive Automated Setup (Recommended)

Run the interactive setup wizard, which prompts for your C64U network address, automatically downloads and installs **KickAssembler**, sets up your Python virtual environment and CLI in editable mode, generates configuration files (`.env` and `antigravity/antigravity.json`), and tests connectivity:

**On Windows (PowerShell / Command Prompt):**
```powershell
.\setup.ps1
# or
.\setup.bat
```

**Cross-Platform (Python):**
```bash
python setup_bridge.py
```

*Flags supported for non-interactive / CI runs:* `python setup_bridge.py --yes --host 192.168.1.64`

---

### 2. Manual Installation (Alternative)

If you prefer manual configuration:

```bash
git clone https://github.com/<your-username>/c64u-antigravity-bridge.git
cd c64u-antigravity-bridge

# Create virtual environment and install package in editable mode
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

Configure your environment variables or create a `.env` file in the project root:

```bash
# .env file or shell exports:
C64U_HOST="192.168.1.64"   # Replace with your C64U IP (Commodore+RESTORE -> F1 -> Network)
C64U_PORT="80"
# C64U_PASSWORD="secret"    # Optional if password enabled
KICKASS_JAR="tools/kickassembler/KickAss.jar"
```

---

## 🤖 Configuring with Google Antigravity

Add the MCP server definition to your Antigravity configuration (or configure with `/mcp` in Antigravity CLI):

```json
{
  "mcpServers": {
    "c64u-bridge": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/c64u-antigravity-bridge", "c64u-bridge", "mcp"],
      "env": {
        "C64U_HOST": "192.168.1.64",
        "KICKASS_JAR": "/usr/local/bin/KickAss.jar"
      }
    }
  }
}
```

Copy the rule guide from `antigravity/rules.md` into your Antigravity workspace rules or custom instructions to provide the agent with deep hardware context for 6502 assembly and VIC-II/SID registers.

---

## 🛠️ MCP Tool Reference for AI Agents

| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `c64_build_and_run` | `source_path`, `assembler` | Compiles assembly/C and executes immediately on C64U via DMA. |
| `c64_run_binary` | `prg_path` | DMA uploads and executes an existing `.prg` binary. |
| `c64_inspect_screen` | `use_ansi_colors` | Dumps `$0400–$07E7` and decodes PETSCII into a 40x25 grid. |
| `c64_read_memory` | `address`, `length` | Reads memory range (hex address) and returns hex dump + ASCII. |
| `c64_write_memory` | `address`, `data` | Writes hex byte sequence directly to RAM or I/O registers. |
| `c64_control` | `action` (`reset`, `reboot`, `pause`, `resume`) | Machine control commands. |
| `c64_send_keys` | `text` | Injects text directly into the C64 keyboard buffer. |
| `c64_status` | *None* | Verifies connection and returns C64U firmware and hardware details. |

---

## 🎨 Python-to-6502 Assembly Studio (Textual TUI)

`c64u-bridge` includes a full-featured retro terminal IDE powered by **[Textual](https://textual.textualize.io/)**. Write high-level Python code targeting the MOS 6502, view real-time transpiled assembly and AST hierarchy, assemble binaries, and DMA-deploy directly to your physical Commodore 64 with a single keystroke (`F5`).

Launch the interactive TUI:
```bash
c64u-bridge tui      # or: c64u-py2asm
```

### Key TUI Features:
* **Python Editor**: Syntax highlighting, line numbers, and instant AST parsing.
* **Live 6502 Assembly Tab**: Inspect generated KickAssembler or ACME code.
* **Compiler & Build Log**: Color-coded output from transpilation and KickAssembler builds.
* **AST & Symbol Tree**: Explore parsed syntax nodes and memory variable allocation.
* **C64U Hardware Tab**: Connection status, machine control (Reset, Pause, Resume), and direct POKE/PEEK memory tester.
* **One-Touch DMA Run (`F5`)**: Transpiles Python, assembles to `.prg`, and DMA runs on the C64U in under 500ms!
* **Built-in Demos (`F2`)**: Ready-to-run examples (Rainbow Raster Bars, Screen Matrix Fill, Hello World & Border Flash, SID Synth Chime).

### Python Dialect & C64 Intrinsics:
```python
# Sample: Rainbow Raster Bars
while True:
    wait_raster(50)
    border_color(COLOR_RED)
    wait_raster(90)
    border_color(COLOR_YELLOW)
    wait_raster(130)
    border_color(COLOR_BLUE)
```

Supported intrinsics:
* `poke(addr, val)` / `peek(addr)`: Direct 8-bit memory manipulation.
* `border_color(color)` / `background_color(color)`: VIC-II palette registers (`$D020`/`$D021`).
* `wait_raster(line)`: Synchronize execution with the CRT beam line (`$D012`).
* `clear_screen(char, color)`: Clear Screen RAM (`$0400`) and Color RAM (`$D800`).
* `print_str("...")` / `print_char(c)`: Output text using KERNAL `CHROUT` (`$FFD2`).
* `sid_tone(freq, waveform, ad, sr)`: Configure SID voice 1 tone generator.
* `delay(cycles)`: Cycle delay loop.
* `asm("...")`: Verbatim 6502 assembly embedding.

---

## 💻 Standalone CLI Usage

You can also use `c64u-bridge` directly from the command line (or use the root `./c64u-bridge` / `.\c64u-bridge` launchers on Windows/PowerShell):

```bash
# Launch the interactive Textual TUI
c64u-bridge tui

# Transpile a Python script to KickAssembler .asm
c64u-bridge transpile examples/rainbow_border.py

# Transpile, assemble to .prg, and immediately DMA run on C64U
c64u-bridge transpile examples/rainbow_border.py --assemble --run

# Directly run a Python file (auto-transpiles, compiles, and DMA executes)
c64u-bridge run examples/rainbow_border.py

# Check C64U status
c64u-bridge status   # (or .\c64u-bridge status)

# Compile and run an assembly file
c64u-bridge run examples/hello_world.asm

# Inspect the live screen buffer
c64u-bridge screen --color

# Dump zero page memory
c64u-bridge mem $0000 64

# Poke border color to red ($02)
c64u-bridge write $D020 02

# Send text to BASIC prompt
c64u-bridge type 'PRINT "HELLO FROM CLI"\r'

# Reset the machine
c64u-bridge reset
```

---

## 📁 Repository Structure

```
c64u-antigravity-bridge/
├── antigravity/
│   ├── antigravity.json         # MCP server configuration snippet
│   ├── rules.md                 # 6502 / VIC-II / SID guidelines for Antigravity agents
│   └── c64_memory_map.md        # Fast C64 memory map reference
├── examples/
│   ├── hello_world.asm          # Basic SYS bootstrap + screen print + color cycle
│   ├── raster_bars.asm          # VIC-II raster interrupt rainbow bar demo
│   └── sid_tone.asm             # MOS 6581/8580 sound synthesizer test
├── src/
│   └── c64u_bridge/
│       ├── __init__.py
│       ├── client.py            # C64U REST API client (DMA & machine control)
│       ├── compiler.py          # KickAss / ACME / CC65 build runner
│       ├── screen.py            # PETSCII & Screen Code decoder
│       ├── server.py            # FastMCP / JSON-RPC 2.0 stdio server
│       └── cli.py               # CLI entrypoint
├── tests/
│   ├── test_client.py           # Unit tests for C64U client
│   └── test_screen.py           # Unit tests for screen decoding
├── pyproject.toml               # Python package configuration (uv compatible)
├── LICENSE                      # MIT License
└── README.md
```

---

## 🤝 Contributing

Contributions to support additional compilers, debuggers (e.g. VICE binary monitor protocol bridge), or UDP audio/video stream capture are welcome.

1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`).
3. Commit your Changes (`git commit -m 'Add AmazingFeature'`).
4. Push to the Branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
