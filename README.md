# C64U Antigravity Bridge

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-Enabled-purple.svg)](https://modelcontextprotocol.io/)
[![Hardware: Commodore 64 Ultimate](https://img.shields.io/badge/Hardware-C64U%20%2F%20Ultimate%2064-red.svg)](https://1541u-documentation.readthedocs.io/)

An agentic development environment and bridge connecting **[Google Antigravity](https://antigravity.google/docs/mcp)** and AI coding agents directly to physical **Commodore 64 Ultimate (C64U)** and **Ultimate 64** hardware using the Model Context Protocol (MCP) and the C64U REST/DMA interface.

> **Write code with AI. Run it instantly on real Commodore 64 hardware. Let the agent inspect the result and iterate.**

Rather than treating AI as an isolated code generator, the bridge creates a seamless **closed-loop hardware development cycle**:

```text
┌──────────────┐     MCP      ┌──────────────────┐
│ Antigravity  │ ───────────▶ │ C64U Bridge      │
│ AI Agent     │              │                  │
└──────────────┘              └────────┬─────────┘
                                      │ Compile / DMA / REST
                                      ▼
                             ┌────────────────────┐
                             │ Physical C64U      │
                             │ 6510 / VIC-II / SID│
                             └─────────┬──────────┘
                                       │
                              Screen / RAM / State
                                       │
                                       └──────▶ AI verifies
```

### The Closed-Loop Workflow:
1. **Prompt the Agent**: Ask Antigravity to create or modify 6502 assembly or Python code.
2. **Compile / Transpile**: The bridge automatically cross-compiles assembly or transpiles Python.
3. **Sub-Second DMA Deployment**: The generated `.prg` binary is injected directly into C64 RAM via high-speed DMA over the local network.
4. **Physical Execution**: The code runs immediately on the real MOS 6510 CPU / Ultimate FPGA core.
5. **Hardware Introspection**: Antigravity reads back the live 40×25 screen matrix, color RAM, zero page, or I/O registers.
6. **Iterate & Refine**: The agent inspects the actual output, diagnoses layout or logic issues, and updates the code.

---

## ⚡ See It in Action

Give Antigravity a single natural prompt:

> *"Create a C64 program that displays a message, cycles the border colors, deploy it to my C64U, and inspect the screen to verify that it ran correctly."*

Antigravity will:
1. Generate the 6502 assembly source file.
2. Invoke `c64_build_and_run` via MCP to compile with KickAssembler and DMA-push the binary to the C64.
3. Call `c64_inspect_screen` to read back the PETSCII character matrix and verify the rendered text.
4. Report back the verified results directly in chat.

---

## 🐍 Python to 6502: High-Level Retro Development

While 6502 assembly remains preferred for cycle-critical raster splits and demoscene effects, the bridge includes a built-in **Python-to-6502 AST transpiler**. You can write standard Python and run it directly on bare-metal Commodore 64 hardware:

```python
# rainbow_border.py — runs on physical C64 silicon!
while True:
    wait_raster(50)
    border_color(COLOR_RED)

    wait_raster(250)
    border_color(COLOR_BLACK)
```

The transpiler parses Python's Abstract Syntax Tree (AST), maps high-level loops, arithmetic, and hardware intrinsics (`poke`, `peek`, `border_color`, `background_color`, `wait_raster`, `sid_tone`, `print_str`, `clear_screen`) into clean, efficient 6502 assembly, and automatically builds it into a runnable PRG:

```text
Python (.py) ──▶ 6502/6510 Assembly (.asm) ──▶ KickAss / ACME ──▶ DMA ──▶ Physical C64
```

```bash
# Run Python directly on physical C64 hardware with one command:
c64u-bridge run examples/rainbow_border.py
```

---

## 💡 Why This Project?

Traditional retro-computing development with AI typically stops at generating assembly code in a chat box. From there, developers face a tedious manual cycle: copying code, running local cross-compilers, mounting virtual disk images (`.d64`), launching emulators or swapping physical SD cards, and manually eyeballing results.

The **C64U Antigravity Bridge** explores an emerging form of AI-assisted retro-computing development:
* **Real Hardware Target**: Code runs on physical Commodore 64 silicon and the Ultimate FPGA core rather than software emulators.
* **Zero Disk-Image Shuffling**: High-speed DMA injection transfers and runs binaries in milliseconds without disk mounting or reset cartridges.
* **Bidirectional AI Introspection**: The AI agent doesn't just write code—it reads screen RAM (`$0400–$07E7`), Color RAM (`$D800–$DBE7`), and hardware registers back from the physical machine to verify behavior.
* **Modern Agent Protocols**: Standard Model Context Protocol (MCP) support connects seamlessly to Google Antigravity and compatible AI tooling.

---

## 🌟 Key Features

1. **AI ↔ Physical C64 Closed-Loop Development**: Integrated master skill (`c64-development`) gives Antigravity agents deep architectural knowledge of the MOS 6510 CPU, VIC-II graphics, and SID sound synthesizer with automated DMA deploy-and-inspect verification.
2. **Sub-Second DMA Deployment**: Bypass disk drives and slow tape routines entirely. Programs compile and launch on physical silicon in less than a second via the C64U REST API.
3. **Live Hardware Introspection**:
   * Reads and decodes Screen RAM (`$0400–$07E7`) and Color RAM (`$D800–$DBE7`) into formatted PETSCII/ANSI grids inside agent conversation.
   * Dumps and inspects Zero Page (`$0000–$00FF`), VIC-II (`$D000`), SID (`$D400`), and custom RAM ranges.
   * Direct memory write (`c64_write_memory` / POKE) for live parameter, palette, and variable tweaking without recompiling.
4. **Model Context Protocol (MCP)**: Native JSON-RPC 2.0 stdio MCP server exposes compilation, binary execution, screen introspection, memory inspection, keystroke injection, and hardware reset tools to AI agents.
5. **Python-to-6502 Transpilation**: Write high-level Python utilizing C64 hardware intrinsics (`poke`, `peek`, `wait_raster`, `border_color`, `sid_tone`, `print_str`, `clear_screen`, `delay`, `asm`), auto-generating documented KickAssembler or ACME source.
6. **Multi-Assembler Toolchain Support**: Auto-detects directives and invokes **KickAssembler** (v5.x), **ACME**, or **CC65 / cl65**.
7. **Comprehensive SID Audio Tooling**:
   * Direct PSID/RSID playback via the C64U built-in hardware SID player (`Ctrl+P`, CLI `sidplay`, or MCP `c64_play_sid`).
   * SID round-trip decompiler and recompiler: reverse-engineers `.sid` files into editable assembly/Python and rebuilds validated PSID/RSID containers.
8. **Retro Sprite Studio (HTML5 Canvas & 6502 Generator)**:
   * Visual browser canvas editor (`c64u-bridge sprite`).
   * Supports both **Single Sprite Mode** (High-Resolution 24×21, 1-bit per pixel) and **Multicolor Mode** (12×21 double-pixels with 4 simultaneous colors).
   * 50-level Undo/Redo history (`Ctrl+Z`, `Ctrl+Y`), drawing tools (Pen, Erase, Flood Fill, Shift, Flip, Invert, Clear).
   * Live KickAssembler binary assembly output (`.byte %xxxxxxxx`) and VIC-II color register setup routines.
9. **Tape Image Mastering (`.tap`)**: Cassette tape mastering engine (`c64u-bridge tap`). Packages PRGs, compiles assembly, or transpiles Python into bit-accurate `.tap` images with standard KERNAL headers, sync marks, and pilot tones.
10. **Interactive Textual TUI**: Full-featured terminal IDE (`c64u-bridge tui`) with live Python editor, AST viewer, generated 6502 assembly view, build log, tiered menus, and single-keystroke DMA deployment (`F5`).

---

## 🏗️ Architecture

```text
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
   * Python 3.10 or later ([`uv`](https://github.com/astral-sh/uv) recommended).
   * Java Runtime Environment (for KickAssembler v5.x) or ACME / CC65 binaries in PATH.

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
# .env configuration:
C64U_HOST="192.168.1.64"   # Replace with your C64U IP (Commodore+RESTORE -> F1 -> Network)
C64U_PORT="80"
# C64U_PASSWORD="secret"    # Optional if network password enabled
KICKASS_JAR="tools/kickassembler/KickAss.jar"
```

---

## 🎨 C64 Retro Sprite Studio (Web / Browser)

Launch the visual HTML5 sprite editor directly in your default web browser:
```bash
c64u-bridge sprite
```

### Features:
* **Single Sprite Mode (24×21 Hires)**: High-resolution single-pixel editing. Every pixel is completely independent with zero adjacent-pixel pairing.
* **Multicolor Mode (12×21 / 4 Colors)**: Full support for VIC-II multicolor sprites:
  * `%00`: Transparent / Background (`$D021`)
  * `%01`: Extra Color 1 (`$D025`)
  * `%10`: Main Sprite Color (`$D027`)
  * `%11`: Extra Color 2 (`$D026`)
* **Intelligent Palette & Brush Selection**: Clicking a color from the 16-color C64 swatch bar switches your active brush without altering existing pixels.
* **50-Level Undo & Redo**: Full history support with `↩️ Undo` / `↪️ Redo` buttons and standard `Ctrl+Z` / `Ctrl+Y` shortcuts.
* **Instant 6502 Assembly Generation**: The right-hand panel renders KickAssembler `.byte %xxxxxxxx` matrix data and complete VIC-II register initialization routines in real-time.
* **One-Click Export**: Copy assembly to clipboard, download `.asm`, or export raw 64-byte `.bin` binaries.

---

## 📼 Cassette Tape Image Mastering (`.tap`)

Export programs to authentic Commodore 64 `.tap` tape images compatible with tape emulators (Tapecart, 1530 C2N, Ultimate-II+ Tape Emulation):

```bash
# Export an existing .prg to .tap
c64u-bridge tap game_dev/heliscape.prg -o heliscape.tap

# Compile .asm and master to .tap with custom tape label
c64u-bridge tap game_dev/heliscape.asm --name "HELISCAPE 64"

# Transpile Python and export to .tap
c64u-bridge tap examples/rainbow_border.py
```

---

## 🕹️ Interactive Textual TUI IDE

Launch the interactive terminal IDE:
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
* **SID Tools**:
  * `Ctrl+D`: Decompile SID to ASM + Python
  * `Ctrl+B`: Compile the loaded SID assembly back to `.sid`
  * `Ctrl+P`: Play the selected/compiled SID on C64U

---

## 💻 Standalone CLI Reference

```bash
# Launch interactive TUI IDE
c64u-bridge tui

# Launch HTML5 Sprite Studio in web browser
c64u-bridge sprite

# Compile and DMA run an assembly file
c64u-bridge run game_dev/heliscape.asm

# Directly run a Python file (auto-transpiles, compiles, and DMA executes)
c64u-bridge run examples/rainbow_border.py

# Upload a SID tune and start the C64U built-in player
c64u-bridge sidplay examples/Commodore.sid

# Play a specific one-based subtune
c64u-bridge sidplay examples/Commodore.sid --song 1

# Rebuild a decompiled source into a SID container
c64u-bridge sidcompile examples/Commodore_decompiled.asm

# Supply an explicit metadata template and output path
c64u-bridge sidcompile examples/Commodore_decompiled.asm --template examples/Commodore.sid -o compiled.sid

# Export PRG, ASM, or Python to .tap tape image
c64u-bridge tap game_dev/heliscape.asm --name "HELISCAPE"

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
        "KICKASS_JAR": "tools/kickassembler/KickAss.jar"
      }
    }
  }
}
```

### MCP Tool Reference for AI Agents:
| Tool Name | Parameters | Description |
| :--- | :--- | :--- |
| `c64_build_and_run` | `source_path`, `assembler` | Compiles assembly/C source and executes immediately on C64U via DMA. |
| `c64_run_binary` | `prg_path` | DMA uploads and executes an existing `.prg` binary. |
| `c64_play_sid` | `sid_path`, optional `song` | Uploads PSID/RSID music and starts the C64U built-in SID player. |
| `c64_compile_sid` | `source_path`, optional `output_path`, `template_path`, `assembler` | Reassembles decompiled ASM/Python into a validated SID container. |
| `c64_inspect_screen` | `use_ansi_colors` | Dumps `$0400–$07E7` Screen RAM and `$D800–$DBE7` Color RAM into a 40×25 grid. |
| `c64_read_memory` | `address`, `length` | Reads memory range (hex/decimal address) and returns hex dump + ASCII. |
| `c64_write_memory` | `address`, `data` | Writes hex byte sequence directly to RAM or I/O registers via DMA. |
| `c64_control` | `action` (`reset`, `reboot`, `pause`, `resume`) | Machine control commands. |
| `c64_send_keys` | `text` | Injects text directly into the C64 keyboard buffer. |
| `c64_status` | *None* | Verifies connection and returns C64U firmware and hardware details. |

---

## 💡 Prompting in Antigravity

Antigravity comes preloaded with the authoritative **`c64-development`** master skill and workspace hardware guidelines ([`AGENTS.md`](AGENTS.md)). You can describe your goals naturally.

### Example Prompts:
* **VIC-II Graphics & Splits**: *"Create a stable double-IRQ raster split with a dark blue sky and desert floor, deploy it, and check the screen."*
* **SID Music & Sound Effects**: *"Compose a 3-voice in-game theme with an arpeggiated bassline on Voice 1, pulse-width modulated lead on Voice 2, and noise percussion on Voice 3."*
* **Deployment & Verification**: *"Compile `game_dev/heliscape.asm`, run it on my C64U, and inspect the screen to verify the HUD and sprites."*
* **Memory Inspection**: *"Read memory at `$0002` for 32 bytes to inspect the zero-page game state and player coordinates."*
* **Hardware Iteration**: *"Reset the machine, change the border color to black, and inject a spacebar keypress."*

---

## 🚁 Featured Showcase: Heliscape: Rescue Protocol

Explore [`game_dev/heliscape.asm`](game_dev/heliscape.asm) for a complete, production-grade 6502 tactical rescue game demonstrating the full power of the bridge:

* **Player Chopper Physics**: Sub-pixel fractional velocity, 3-way directional orientation (facing right, hover, facing left), landing pad docking at base, ceiling altitude boundary, shields, and cargo capacity for up to 16 hostages.
* **Animated Sprites**: 4-frame animated main/tail rotor blades, animated hostage walking and waving states, and multi-frame animated explosions.
* **Intelligent Ground & Air Combatants**:
  * Enemy Tank patrols with an independent rotating 3-position turret (facing left, center, right).
  * Enemy Jet interceptors flying across altitude corridors with dual afterburners.
  * Ballistic trajectory projectiles for player vulcan cannon bullets and enemy tank/jet shells.
* **Destructible Compound Barracks**: Dual hostage compound buildings with independent hit point counters that crack and crumble under fire.
* **Multi-Voice SID 6581/8580 Audio Engine**:
  * Voice 1: Driving tactical in-game soundtrack and 4-note hostage rescue chime.
  * Voice 2: Helicopter turbine hum with real-time 12-bit PWM LFO modulation.
  * Voice 3: White noise gunfire, explosion sound effects, and analog resonant filter sweeps.
* **VIC-II Split Raster Interrupts**: Multi-stage raster IRQs driving the tactical status HUD, active combat airspace, and scrolling desert landscape.

---

## 📁 Repository Structure

```text
c64u-antigravity-bridge/
├── .agents/
│   ├── rules/c64-bridge.md      # Auto-loaded agent rules
│   └── skills/c64-development/  # Authoritative C64 engineering master skill
│       ├── SKILL.md             # Master architecture guide
│       ├── references/          # VIC-II, SID, Memory & Transpiler manuals
│       └── examples/            # Stable IRQ & SID tracker engines
├── .github/
│   ├── ISSUE_TEMPLATE/          # Structured bug report & feature request templates
│   ├── pull_request_template.md # PR checklist (tests, hardware model, IP policy)
│   └── REPOSITORY_SETUP.md      # Recommended topics, descriptions, and setup guidance
├── antigravity/
│   ├── antigravity.json         # MCP server configuration snippet
│   ├── rules.md                 # 6502 / VIC-II / SID guidelines
│   └── c64_memory_map.md        # Fast C64 memory map reference
├── game_dev/
│   ├── heliscape.asm            # Production 6502 tactical rescue game
│   ├── heliscape.prg            # Compiled C64 binary
│   └── heliscape.tap            # Mastered cassette tape image
├── examples/
│   ├── hello_world.asm          # SYS bootstrap + color cycle
│   ├── rainbow_border.py        # Python-to-6502 raster demo
│   ├── Commodore.sid            # Sample SID music container
│   ├── Commodore_decompiled.asm # Decompiled SID assembly
│   └── SID_Radio_Star.asm       # Chiptune music source
├── src/
│   └── c64u_bridge/
│       ├── client.py            # C64U REST API client (DMA & machine control)
│       ├── compiler.py          # KickAss / ACME / CC65 build orchestrator
│       ├── screen.py            # PETSCII & Screen Code decoder
│       ├── server.py            # JSON-RPC 2.0 stdio MCP server
│       ├── sid_compiler.py      # Reassembles decompiled source into SID containers
│       ├── sid_decompiler.py    # Decompiles SID binaries into ASM/Python
│       ├── sprite.py            # Mathematical C64 sprite engine
│       ├── tap.py               # TAP cassette tape mastering engine
│       ├── transpiler.py        # Python AST to 6502 assembly compiler
│       ├── tui.py               # Interactive Textual TUI IDE
│       ├── web/
│       │   └── sprite_studio.html # Browser HTML5 Retro Sprite Studio
│       └── cli.py               # Unified CLI entrypoint
├── tests/                       # Complete pytest test suite (51 tests)
├── CONTRIBUTING.md               # Contribution guidelines & hardware testing info
├── SECURITY.md                  # Network security policy & disclosure
├── pyproject.toml               # Python package configuration (uv compatible)
├── LICENSE                      # MIT License
└── README.md
```

---

## 🤝 Contributing

Contributions, hardware testing reports, and community demos are warmly welcomed!

We are especially interested in:
* **Hardware & Firmware Testing**: Telemetry and compatibility reports across Ultimate 64, Ultimate-II+, and various firmware versions.
* **Transpiler Enhancements**: Expanding Python-to-6502 language support, optimizations, and C64 hardware intrinsics.
* **Inspection Tools**: New MCP inspection utilities for sprite attributes, SID voice state, and raster timing.
* **Demos & Examples**: High-quality homebrew games, demoscene effects, and SID compositions.

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution guidelines and [`SECURITY.md`](SECURITY.md) for our network security recommendations.

---

## 📜 License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for more information.
