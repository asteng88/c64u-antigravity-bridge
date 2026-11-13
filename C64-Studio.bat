@echo off
REM ============================================================================
REM C64 STUDIO // Commodore 64 Multi-Language IDE (6502 ASM / C / Python / SID)
REM Integrated with Google Antigravity CLI (agy) and C64U Hardware DMA Bridge
REM ============================================================================
setlocal
cd /d "%~dp0"

REM Always prepend src to PYTHONPATH so moving the repo across drives works
if defined PYTHONPATH (
    set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%~dp0src"
)

REM 1. Prefer project virtualenv (.venv)
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -c "import tkinter, c64u_bridge.c64_studio" >nul 2>nul
    if not errorlevel 1 (
        if exist "%~dp0.venv\Scripts\pythonw.exe" (
            start "" "%~dp0.venv\Scripts\pythonw.exe" -m c64u_bridge %*
            exit /b 0
        )
        start "" "%~dp0.venv\Scripts\python.exe" -m c64u_bridge %*
        exit /b 0
    )
    echo [C64 Studio] Startup check failed in .venv - running with console diagnostics:
    "%~dp0.venv\Scripts\python.exe" -m c64u_bridge %*
    if errorlevel 1 pause
    exit /b %ERRORLEVEL%
)

REM 2. Fallback to uv run if uv is installed
where uv >nul 2>nul
if not errorlevel 1 (
    uv run python -m c64u_bridge %*
    if errorlevel 1 pause
    exit /b %ERRORLEVEL%
)

REM 3. Fallback to system Python
where python >nul 2>nul
if not errorlevel 1 (
    python -c "import tkinter, c64u_bridge.c64_studio" >nul 2>nul
    if not errorlevel 1 (
        where pythonw >nul 2>nul
        if not errorlevel 1 (
            start "" pythonw -m c64u_bridge %*
            exit /b 0
        )
    )
    python -m c64u_bridge %*
    if errorlevel 1 pause
    exit /b %ERRORLEVEL%
)

echo [C64 Studio] ERROR: Python was not found in .venv or on PATH.
echo Run setup.bat first to initialize the environment.
pause
exit /b 1
