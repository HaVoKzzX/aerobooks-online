# -*- mode: python ; coding: utf-8 -*-
# Run from the AeroBooks folder:
#   .venv\Scripts\pyinstaller.exe --noconfirm --clean packaging\AeroBooks.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
ICON = ROOT / "packaging" / "aerobooks.ico"

datas = []
binaries = []
hiddenimports = collect_submodules("aerobooks") + [
    "engineio.async_drivers.asgi",
    "socketio",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "plotly",
    "qrcode",
    "reportlab",
    "PIL",
]

for pkg in ("nicegui", "plotly", "reportlab", "qrcode"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

if ICON.exists():
    datas.append((str(ICON), "."))
assets = ROOT / "aerobooks" / "assets"
if assets.exists():
    datas.append((str(assets), "aerobooks/assets"))
logo_png = ROOT / "packaging" / "aerobooks_logo.png"
if logo_png.exists():
    datas.append((str(logo_png), "."))

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AeroBooks",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ICON) if ICON.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AeroBooks",
)
