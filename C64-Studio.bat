@echo off
REM ============================================================================
REM C64 STUDIO // Commodore 64 Multi-Language IDE (6502 ASM / C / Python)
REM Integrated with Google Antigravity CLI (`agy`) & C64U Hardware DMA Bridge
REM ============================================================================
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m c64u_bridge %*
    exit /b 0
)

where pythonw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" pythonw -m c64u_bridge %*
    exit /b 0
)

python -m c64u_bridge %*
