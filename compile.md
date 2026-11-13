# Compiling C64 Studio & Setup Executables

This guide explains how to build the standalone Windows distribution of **C64 Studio** (`C64-Studio.exe`) and its companion **C64-Studio-Setup.exe** installer so users can run the IDE without installing Python.

---

## 1. Prerequisites

- **Windows 10/11** (64-bit) to produce Windows `.exe` binaries
- **Python 3.10+** with **Tkinter** (`tcl`/`tk`) included (standard on official python.org Windows installers and `uv`-managed Python builds)
- **`uv`** (recommended) or `pip`

---

## 2. Set Up the Build Environment

From the repository root:

### Using `uv` (recommended)

```powershell
uv venv .venv
uv pip install -e . --python .\.venv\Scripts\python.exe
uv pip install pyinstaller --python .\.venv\Scripts\python.exe
```

### Using standard `python` / `pip`

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip install pyinstaller
```

---

## 3. Build the Executables

Run `build_exe.py` using the virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe build_exe.py
```

This runs PyInstaller to produce:

- `dist/C64-Studio/C64-Studio.exe` (`--onedir --windowed`, runtime libraries in `dist/C64-Studio/_internal/`)
- `dist/C64-Studio/C64-Studio-Setup.exe` (`--onefile --console`)
- `dist/C64-Studio/tools/` (game-dev and build tools, excluding `__pycache__`)
- `dist/C64-Studio/examples/` (sample C64 projects)

### Optional Build Flags

- Build only `C64-Studio-Setup.exe`:
  ```powershell
  .\.venv\Scripts\python.exe build_exe.py --skip-studio
  ```
- Build only `C64-Studio.exe` (note: PyInstaller `--onedir` recreates `dist/C64-Studio/`, so run a full build without `--skip-setup` when preparing a final release folder):
  ```powershell
  .\.venv\Scripts\python.exe build_exe.py --skip-setup
  ```

---

## 4. Distributing & Running the Compiled App

To distribute C64 Studio to another machine (no Python installation required):

1. Zip or copy the entire `dist/C64-Studio/` folder.
2. On the target machine, run **`C64-Studio-Setup.exe`** first. It will:
   - Configure your Commodore 64 Ultimate (`C64U_HOST`, `C64U_PORT`, `C64U_PASSWORD`)
   - Download **KickAssembler** (`tools/kickassembler/KickAss.jar`)
   - Download portable **Eclipse Temurin JRE 17** (`tools/java/`) if Java is not present
   - Download **Oscar64** (`tools/oscar64/`) for C/C++ builds
   - Write `.env` next to `C64-Studio.exe`
3. Launch **`C64-Studio.exe`**.

> Tip: `C64-Studio-Setup.exe` also supports non-interactive flags such as `--non-interactive` (`-y`), `--host <ip>`, `--port <port>`, `--password <pwd>`, `--skip-kickass`, `--skip-java`, `--skip-oscar64`, and `--skip-test`. Run `C64-Studio-Setup.exe --help` for details.

---

## 5. Verify the Build

Run the packaging and IDE test suites:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_packaging.py tests/test_tui.py -q
```

Smoke-test the compiled binaries directly:

```powershell
.\dist\C64-Studio\C64-Studio-Setup.exe --help
.\dist\C64-Studio\C64-Studio.exe --run-script .\dist\C64-Studio\tools\build\build_tool.py --help
.\dist\C64-Studio\C64-Studio.exe
```
