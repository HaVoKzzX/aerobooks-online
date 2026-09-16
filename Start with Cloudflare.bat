@echo off
cd /d "%~dp0"
title AeroBooks Online + Cloudflare tunnel

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

if not exist "tools\cloudflared.exe" (
  echo Downloading cloudflared...
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\download_cloudflared.ps1"
  if errorlevel 1 (
    echo Could not download cloudflared.
    pause
    exit /b 1
  )
)

echo Starting AeroBooks Online...
start "AeroBooks Online" cmd /c ""%~dp0.venv\Scripts\python.exe" "%~dp0main.py""

echo Waiting for the app to come up...
powershell -NoProfile -Command "for ($i=0; $i -lt 30; $i++) { try { Invoke-WebRequest -Uri http://127.0.0.1:8765 -UseBasicParsing -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Seconds 1 } }; exit 1"
if errorlevel 1 (
  echo The app did not start on http://127.0.0.1:8765
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  Cloudflare will print a https://....trycloudflare.com URL
echo  Share that link with instructors. It changes each time you
echo  start this script unless you use a named Cloudflare tunnel.
echo ============================================================
echo.
tools\cloudflared.exe tunnel --url http://127.0.0.1:8765
if errorlevel 1 pause
