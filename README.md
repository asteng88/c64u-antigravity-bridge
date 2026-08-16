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

### 1. Installation

Clone the repository and install the bridge using `uv`:

```bash
git clone https://github.com/<your-username>/c64u-antigravity-bridge.git
cd c64u-antigravity-bridge

# Create virtual environment and install package in editable mode
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 2. Environment Configuration

Set the IP address of your C64 Ultimate (found under the C64U menu: `Commodore + RESTORE` -> `F1` -> `Network Settings`):

```bash
export C64U_HOST="192.168.1.64"   # Replace with your C64U IP
export C64U_PORT="80"
# export C64U_PASSWORD="secret"    # Optional if password enabled
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

## 💻 Standalone CLI Usage

You can also use `c64u-bridge` directly from the command line:

```bash
# Check C64U status
c64u-bridge status

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
