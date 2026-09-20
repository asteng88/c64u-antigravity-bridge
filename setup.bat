@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    uv run python "%~dp0setup_bridge.py" %*
    goto end
)

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0setup_bridge.py" %*
    goto end
)

python "%~dp0setup_bridge.py" %*

:end
endlocal
