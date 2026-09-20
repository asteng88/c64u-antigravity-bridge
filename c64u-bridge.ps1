$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$PSScriptRoot\.venv\Scripts\c64u-bridge.exe" @args
