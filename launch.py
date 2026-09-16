"""Install dependencies if needed, then start AeroBooks Online."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    print("=" * 60)
    print("AeroBooks Online — CFI invoicing")
    print("=" * 60)
    print()
    try:
        import nicegui  # noqa: F401
        import qrcode  # noqa: F401
        import reportlab  # noqa: F401
        import plotly  # noqa: F401
    except ImportError:
        print("Installing requirements (first run)...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
        )
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements-nicegui.txt")]
        )
        print()

    host = os.environ.get("AEROBOOKS_HOST", "0.0.0.0")
    port = os.environ.get("AEROBOOKS_PORT", "8765")
    print(f"AeroBooks Online is listening on http://{host}:{port}")
    print("On this computer: http://127.0.0.1:8765")
    print("To share it on the internet, run  Start with Cloudflare.bat")
    print("Close this window to exit.")
    print()
    subprocess.call([sys.executable, str(ROOT / "main.py")])


if __name__ == "__main__":
    main()
