@echo off
cd /d "%~dp0"
title AeroBooks Online (Streamlit)

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
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri http://127.0.0.1:8501 -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process http://127.0.0.1:8501; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo AeroBooks Streamlit is already running — opened http://127.0.0.1:8501
  goto :eof
)

echo Starting AeroBooks Online (Streamlit) at http://127.0.0.1:8501
echo Close this window to stop the server.
start "" http://127.0.0.1:8501
".venv\Scripts\python.exe" -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --browser.gatherUsageStats false
if errorlevel 1 pause
