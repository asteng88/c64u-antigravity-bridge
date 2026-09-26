# C64U Antigravity Bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Enabled-purple.svg)](https://modelcontextprotocol.io/)
[![Hardware: Commodore 64 Ultimate](https://img.shields.io/badge/Hardware-C64U%20%2F%20Ultimate%2064-red.svg)](https://1541u-documentation.readthedocs.io/)

An agentic developer bridge connecting **[Google Antigravity](https://antigravity.google/docs/mcp)** directly to physical **Commodore 64 Ultimate (C64U)** and **Ultimate 64** hardware. 

Write 6502/6510 Assembly, Python, C, or Commodore BASIC in Antigravity with AI assistance, cross-compile automatically, master cassette tape images (`.tap`), design colorful sprites in the HTML5 Retro Sprite Studio, and deploy binaries instantly to physical C64 hardware via direct Direct Memory Access (DMA) over the local network.

---

## 🌟 Key Features

* **Agent-Driven C64 Development**: Built-in master skill (`c64-development`) equips Google Antigravity agents with deep hardware knowledge for the MOS 6510 CPU, VIC-II graphics, and MOS 6581/8580 SID sound synthesizer.
* **Sub-Second DMA Deployment**: Bypass slow disk/tape loading routines. Code compiles and runs instantly on physical silicon using the C64U REST API.
* **Real-Time Hardware Introspection**: 
  * Read and decode Screen RAM (`$0400–$07E7`) and Color RAM (`$D800–$DBE7`) into formatted ASCII/ANSI grids directly in agent conversation.
  * Dump and inspect Zero Page (`$0000–$00FF`), VIC-II (`$D000`), SID (`$D400`), and custom memory ranges.
  * Direct 64-byte chunked memory POKE/writemem via DMA for live parameter and palette tweaking.
* **Retro Sprite Studio (HTML5 & 6502 ASM Generator)**:
  * Full-featured visual browser canvas editor (`c64u-bridge sprite`).
  * Supports both **Single Sprite Mode** (High-Resolution 24×21, 1-bit per pixel) and **Multicolor Mode** (12×21 double-pixels with 4 simultaneous colors: Background `$D021`, Extra Color 1 `$D025`, Sprite Color `$D027`, Extra Color 2 `$D026`).
  * 50-level Undo/Redo history (`Ctrl+Z`, `Ctrl+Y`) and drawing tools (Pen, Erase, Flood Fill, Shift, Flip, Invert, Clear).
  * Generates cycle-exact KickAssembler binary assembly (`.byte %xxxxxxxx`) and VIC-II color register setup routines.
  * Preloaded with the authentic multicolor Commodore (C=) "Chicken Lips" logo.
* **Tape Image Mastering (`.tap`)**: Full C64 cassette tape mastering engine (`c64u-bridge tap`). Packages PRGs, compiles assembly, or transpiles Python into bit-accurate `.tap` images with standard KERNAL headers, sync marks, and pilot tones.
* **Multi-Assembler Toolchain**: Auto-detects and invokes **KickAssembler** (v5.x), **ACME**, and **CC65 / cl65**.
* **Python-to-6502 Transpiler & Textual TUI**: Develop in Python using C64 hardware intrinsics (`poke`, `peek`, `wait_raster`, `border_color`, `sid_tone`), view live AST and generated assembly, and deploy with one keystroke (`F5`).
* **Model Context Protocol (MCP)**: Native JSON-RPC 2.0 MCP server exposes compiler, screen inspection, and hardware control tools to Antigravity agents.

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
 │  ├───────────────────────┤       ├────────────────────────┤ │
 │  │ Python-to-6502 Engine │       │  HTML5 Sprite Studio   │ │
 │  ├───────────────────────┤       ├────────────────────────┤ │
 │  │ TAP Cassette Masterer │       │ Two-Row Textual TUI IDE│ │
 │  └───────────────────────┘       └────────────────────────┘ │
 └──────────────────────────────┬──────────────────────────────┘
                                │ HTTP REST (Port 80) / DMA
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

Run the interactive setup wizard, which prompts for your C64U network address, downloads and configures **KickAssembler**, sets up your Python virtual environment and CLI in editable mode, generates configuration files (`.env` and `antigravity/antigravity.json`), and verifies connectivity:

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

```bash
git clone https://github.com/asteng88/c64u-antigravity-bridge.git
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

## 🎨 C64 Retro Sprite Studio (Web / Browser)

Launch the visual HTML5 sprite editor directly in your default web browser:
```bash
c64u-bridge sprite
```

### Features:
* **Single Sprite Mode (24×21 Hires)**: High-resolution single-pixel editing. Every pixel is completely independent with zero adjacent-pixel pairing. Pen, Erase, and Flood Fill operate strictly on $1\times 1$ boundaries.
* **Multicolor Mode (12×21 / 4 Colors)**: Full support for the VIC-II multi-color architecture within the same sprite boundary:
  * `%00`: Transparent / Background (`$D021`)
  * `%01`: Extra Color 1 (`$D025`)
  * `%10`: Main Sprite Color (`$D027`)
  * `%11`: Extra Color 2 (`$D026`)
* **Intelligent Palette & Brush Selection**: Clicking a color from the 16-color C64 swatch bar switches your active drawing brush without modifying previously drawn pixels.
* **50-Level Undo & Redo**: Full history support with interactive `↩️ Undo` / `↪️ Redo` toolbar buttons and standard `Ctrl+Z` / `Ctrl+Y` keyboard shortcuts.
* **Instant 6502 Assembly Generation**: The right-hand panel renders KickAssembler `.byte %xxxxxxxx` matrix data and complete VIC-II register initialization routines in real-time.
* **One-Click Export**: Copy assembly to clipboard, download `.asm`, or export raw 64-byte `.bin` binaries.

---

## 📼 Cassette Tape Image Mastering (`.tap`)

Export your programs to authentic Commodore 64 `.tap` tape images compatible with physical tape emulators (e.g. Tapecart, 1530 C2N, Ultimate-II+ Tape Emulation):

```bash
# Export an existing .prg to .tap
c64u-bridge tap game_dev/choplifter.prg -o choplifter.tap

# Compile .asm and master to .tap with custom tape label
c64u-bridge tap game_dev/choplifter.asm --name "CHOPLIFTER 64"

# Transpile Python and export to .tap
c64u-bridge tap examples/rainbow_border.py
```

---

## 🕹️ Interactive Textual TUI IDE

Launch the two-row terminal IDE:
```bash
c64u-bridge tui
```

### Keyboard Shortcuts & Toolbar:
* **Row 1 (`F1–F8`)**:
  * `F1`: Help & Documentation
  * `F2`: Built-in Code Presets (Rainbow Border, Screen Matrix, Hello World, SID Chime)
  * `F3`: Project File Browser (Navigate `game_dev/`, `examples/`, and root)
  * `F4`: Refresh C64U Connection & Telemetry
  * `F5`: One-Touch Transpile, Assemble & DMA Run
  * `F6`: Transpile Python to 6502 Assembly
  * `F7`: Assemble with KickAssembler
  * `F8`: Reset C64U Machine
* **Row 2 (`Shift+F1–Shift+F8`)**:
  * `Shift+F1`: Save Source File
  * `Shift+F2`: Export to `.tap` Cassette Image
  * `Shift+F3`: Quick Load PRG via DMA
  * `Shift+F4`: Pause 6510 CPU
  * `Shift+F5`: Resume 6510 CPU
  * `Shift+F6`: Screen Dump ($0400 Screen RAM & $D800 Color RAM)
  * `Shift+F7`: Cold Reboot C64U
  * `Shift+F8`: Quit TUI

---

## 💻 Standalone CLI Reference

```bash
# Launch interactive TUI IDE
c64u-bridge tui

# Launch HTML5 Sprite Studio in web browser
c64u-bridge sprite

# Compile and DMA run an assembly file
c64u-bridge run game_dev/choplifter.asm

# Directly run a Python file (auto-transpiles, compiles, and DMA executes)
c64u-bridge run examples/rainbow_border.py

# Export PRG, ASM, or Python to .tap tape image
c64u-bridge tap game_dev/choplifter.asm --name "CHOPLIFTER"

# Inspect the live C64 screen buffer (40x25 text + colors)
c64u-bridge screen --color

# Dump zero page memory
c64u-bridge mem $0000 64

# Write data directly to memory (POKE border color to red)
c64u-bridge write $D020 02

# Send keystrokes into C64 keyboard buffer
c64u-bridge type 'PRINT "HELLO FROM ANTIGRAVITY"\r'

# Check C64U hardware status & firmware version
c64u-bridge status

# Reset the machine
c64u-bridge reset
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

### MCP Tool Reference for AI Agents:
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `c64_build_and_run` | `source_path`, `assembler` | Compiles assembly/C/Python and executes immediately on C64U via DMA. |
| `c64_run_binary` | `prg_path` | DMA uploads and executes an existing `.prg` binary. |
| `c64_inspect_screen` | `use_ansi_colors` | Dumps `$0400–$07E7` and decodes PETSCII into a 40x25 grid. |
| `c64_read_memory` | `address`, `length` | Reads memory range (hex address) and returns hex dump + ASCII. |
| `c64_write_memory` | `address`, `data` | Writes hex byte sequence directly to RAM or I/O registers via DMA. |
| `c64_control` | `action` (`reset`, `reboot`, `pause`, `resume`) | Machine control commands. |
| `c64_send_keys` | `text` | Injects text directly into the C64 keyboard buffer. |
| `c64_status` | *None* | Verifies connection and returns C64U firmware and hardware details. |

---

## 💡 Helpful Hints for Prompting in Antigravity

Antigravity comes preloaded with the authoritative **`c64-development`** master skill and workspace hardware guidelines (`AGENTS.md`). You do not need to memorize rigid syntax or special prompt formats—simply describe your goals naturally.

Here are some best practices and examples to get the absolute best results:

### 1. Requesting Demoscene Graphics & VIC-II Effects
Be specific about the visual effect you want. Antigravity understands cycle-exact MOS 6502 timing:
* *"Create a stable 0-cycle jitter double-IRQ raster split with a dark blue sky and desert floor."*
* *"Implement a multiplexer for 16 sprites across the screen with smooth vertical bobbing."*
* *"Write an FLI (Flexible Line Interpretation) demo in KickAssembler that displays a colorful logo."*
* *"Add hardware fine horizontal scrolling for a multi-layered parallax background."*

### 2. Crafting Rich SID Music & Sound Effects
Antigravity knows all registers of the MOS 6581 / 8580 sound synthesizer:
* *"Compose a 3-voice in-game battle theme with an arpeggiated bassline on Voice 1, chorused pulse-width modulated lead on Voice 2, and percussion on Voice 3."*
* *"Create an explosion sound effect with an analog low-pass resonant filter sweep that decays from high cutoff to sub-bass."*
* *"Generate an authentic Arabic/Middle Eastern modal melody (Hijaz scale) for the intro sequence."*

### 3. Hardware Deployment & In-Chat Verification
Combine building, execution, and screen inspection in a single prompt:
* *"Compile `game_dev/choplifter.asm`, run it on my C64U, and inspect the screen to verify the HUD and sprites."*
* *"Read memory at `$0020` for 16 bytes to check the zero-page player coordinates and game state."*
* *"Reset the C64, deploy the new binary, and type spacebar to begin gameplay."*

### 4. Language Strategies: Assembly vs. Python
* **KickAssembler Assembly (`.asm`) — Preferred**: Always request assembly when you want maximum performance, 60fps arcade gameplay, cycle-exact raster splits, or complex SID music routines. Standard KickAss directives like `BasicUpstart2()`, `.align $40`, and `* = $0810` are automatically followed.
* **Python (`.py`)**: Use Python when you want to prototype gameplay math, collision algorithms, or text-based tools. Antigravity will use the transpiler to generate 6502 assembly and compile it.

### 5. Iterative Refinement
* *"The helicopter sprite feels too bulky—refactor the sprite binary into a sleek attack chopper."*
* *"Randomize enemy jet sorties across 16 different altitude corridors and have them enter one at a time."*
* *"Export the finished program into a `.tap` cassette image titled 'RESCUE MISSION'."*

---

## 🚁 Featured Showcase: Choplifter 64 Enhanced

Explore [`game_dev/choplifter.asm`](file:///c:/Users/asten/OneDrive/Documents/Python/pythonProject/c64u-antigravity-bridge/game_dev/choplifter.asm) for a complete, production-grade 6502 action rescue game demonstrating the full power of the bridge:
* **Sleek Multicolor Airwolf Chopper**: 4-color multi-color sprite with animated twin-turbine intake and spinning main/tail rotors.
* **Supersonic Enemy Jet Interceptors**: Random height sorties across 16 authentic flight levels (high altitude sweeps to low-altitude strafing runs) entering from either direction with bomb momentum physics, flak defense, mid-air dogfights, and collisions.
* **Full 3-Voice SID Audio Engine**:
  * Voice 1: Driving C-minor tactical bass rhythm & 4-note ascending hostage rescue fanfares.
  * Voice 2: Chorused twin turbine hum with 12-bit PWM and periodic heavy rotor blade chops.
  * Voice 3: Vulcan cannon gunfire and heavy explosions featuring real-time analog resonant filter sweeps.
* **Active Battlefield**: Dual destructible POW barracks, fleeing hostages with animated waving/running states, medical landing compound, and real-time tactical radar HUD.

---

## 📁 Repository Structure

```
c64u-antigravity-bridge/
├── .agents/
│   ├── rules/c64-bridge.md      # Auto-loaded agent rules
│   └── skills/c64-development/  # Authoritative C64 engineering master skill
│       ├── SKILL.md             # Master architecture guide
│       ├── references/          # VIC-II, SID, Memory & Transpiler manuals
│       └── examples/            # Stable IRQ & SID tracker engines
├── antigravity/
│   ├── antigravity.json         # MCP server configuration snippet
│   ├── rules.md                 # 6502 / VIC-II / SID guidelines
│   └── c64_memory_map.md        # Fast C64 memory map reference
├── game_dev/
│   ├── choplifter.asm           # Production 6502 Choplifter arcade game
│   └── choplifter.prg           # Compiled C64 binary
├── examples/
│   ├── hello_world.asm          # SYS bootstrap + color cycle
│   ├── rainbow_border.py        # Python-to-6502 raster demo
│   └── sid_tone.asm             # MOS 6581/8580 sound synthesizer test
├── src/
│   └── c64u_bridge/
│       ├── client.py            # C64U REST API client (DMA & machine control)
│       ├── compiler.py          # KickAss / ACME / CC65 build runner
│       ├── screen.py            # PETSCII & Screen Code decoder
│       ├── server.py            # FastMCP / JSON-RPC 2.0 stdio server
│       ├── sprite.py            # Mathematical C64 sprite engine
│       ├── tap.py               # TAP cassette tape mastering engine
│       ├── transpiler.py        # Python AST to 6502 assembly compiler
│       ├── tui.py               # Interactive two-row Textual TUI IDE
│       ├── web/
│       │   └── sprite_studio.html # Browser HTML5 Retro Sprite Studio
│       └── cli.py               # Unified CLI entrypoint
├── tests/                       # Complete pytest test suite (39 tests)
├── pyproject.toml               # Python package configuration (uv compatible)
├── LICENSE                      # MIT License
└── README.md
```

---

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
