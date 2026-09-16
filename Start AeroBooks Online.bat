@echo off
cd /d "%~dp0"
title AeroBooks Online

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://127.0.0.1:8765 -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process http://127.0.0.1:8765; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo AeroBooks Online is already running — opened http://127.0.0.1:8765
  goto :eof
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating Python environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Python was not found. Install Python 3.10+ from python.org and try again.
    pause
    exit /b 1
  )
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  ".venv\Scripts\python.exe" -m pip install -r requirements-nicegui.txt
)

echo Starting AeroBooks Online at http://127.0.0.1:8765
echo Close this window to stop the server.
start "" http://127.0.0.1:8765
".venv\Scripts\python.exe" main.py
if errorlevel 1 pause
