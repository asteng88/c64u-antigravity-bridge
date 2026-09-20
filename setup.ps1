# C64U Antigravity Bridge - Setup PowerShell Script
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $ScriptDir

# Check for uv, then venv python, then system python
$UvCmd = Get-Command uv -ErrorAction SilentlyContinue
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if ($UvCmd) {
    & uv run python "$ScriptDir\setup_bridge.py" @args
} elseif (Test-Path $VenvPython) {
    & $VenvPython "$ScriptDir\setup_bridge.py" @args
} else {
    & python "$ScriptDir\setup_bridge.py" @args
}
