# Contributing to C64U Antigravity Bridge

Thank you for your interest in contributing to the **C64U Antigravity Bridge**! This project connects Google Antigravity and AI coding agents directly to physical Commodore 64 Ultimate and Ultimate 64 hardware via MCP, REST, and direct DMA.

Whether you are testing hardware compatibility, submitting bug reports, adding assembler integrations, or expanding Python-to-6502 transpiler intrinsics, your contributions are welcome.

---

## Ways to Contribute

* **Hardware Testing & Telemetry**: Test the bridge against different Commodore 64 Ultimate hardware configurations, FPGA revisions, and network topologies (Ethernet vs. Wi-Fi).
* **Firmware Compatibility**: Report behavior across Ultimate firmware releases (v3.11+, v3.12+, etc.) to ensure reliable REST API and DMA operation.
* **Bug Reports & Feature Requests**: Identify bugs in the CLI, TUI, MCP server, or transpiler, or propose new agent-assisted workflows.
* **Assembler & Toolchain Integrations**: Help expand and refine support for KickAssembler, ACME, CC65/cl65, or other 6502 cross-compilers.
* **Python-to-6502 Transpiler**: Add support for more Python language constructs, standard library intrinsics, VIC-II graphics routines, and SID music generators.
* **SID & VIC-II Tooling**: Enhance the HTML5 Retro Sprite Studio, SID decompiler/recompiler, or cassette `.tap` mastering engine.
* **Documentation & Examples**: Improve guides, write new sample programs in `examples/`, or add demo code in `game_dev/`.

---

## Reporting Hardware Bugs

When submitting hardware-related bug reports or communication issues, please include:

1. **Hardware Model**: Physical C64 with Ultimate-II+, Ultimate 64, or Ultimate 64 Elite.
2. **Firmware Version**: Ultimate firmware version (e.g., 3.11, 3.12, beta build).
3. **Host Operating System**: Windows, macOS, or Linux (including version).
4. **Python Version**: Python runtime version (`python --version`).
5. **Assembler & Toolchain**: Cross-assembler in use (KickAssembler v5.x with Java version, ACME, or CC65).
6. **Connection Method**: Ethernet or Wi-Fi, static IP or hostname (`c64u.local`).
7. **Reproduction Steps**: Minimal steps or code snippet that reproduces the issue.
8. **Observed vs. Expected Behavior**: Output logs, stack traces, or C64 screen readouts.

Please use the provided [GitHub Bug Report Template](.github/ISSUE_TEMPLATE/bug_report.yml).

---

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/asteng88/c64u-antigravity-bridge.git
   cd c64u-antigravity-bridge
   ```

2. **Set up the virtual environment**:
   Using [`uv`](https://github.com/astral-sh/uv) (recommended):
   ```bash
   uv venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate

   uv pip install -e ".[dev]"
   ```
   Or using standard `pip`:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -e ".[dev]"
   ```

3. **Run the test suite**:
   ```bash
   pytest
   ```
   Ensure all tests pass before opening a pull request.

---

## Pull Request Guidelines

Before submitting a Pull Request:

1. **Tests Must Pass**: Run `pytest` locally and verify all tests pass without errors.
2. **Add Tests for New Features**: If you add new transpiler nodes, MCP endpoints, or CLI subcommands, include corresponding unit tests in `tests/`.
3. **No Unnecessary Binary Artifacts**: Do not commit generated build outputs (`.prg`, `.tap`, `.sym`, `.vs`, `.class`, temporary caches). Keep example binaries minimal and deliberate.
4. **Strict Intellectual Property Policy**: **Never commit copyrighted commercial C64 software, commercial game ROMs, commercial SID rips, or proprietary disk images.** All code and assets in this repository must be original, public domain, or permissively licensed open-source works.
5. **Document Changes**: If your change adds CLI options, environment variables, or MCP capabilities, update `README.md` and related docs.
6. **Hardware Context**: If your PR addresses hardware-specific behavior (such as DMA timing, REST endpoints, or firmware variations), note the tested hardware model and firmware version in the PR description.

---

## Code Style

* Follow [PEP 8](https://peps.python.org/pep-0008/) conventions for Python code.
* Use type annotations where practical.
* For 6502 assembly examples, use clean, well-commented code compatible with KickAssembler v5.x or ACME.

Thank you for helping push real-hardware retro-computing forward with modern AI development tooling!
