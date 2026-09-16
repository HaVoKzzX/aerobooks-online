"""AeroBooks Online — multi-user CFI invoicing."""

from __future__ import annotations

import os
from multiprocessing import freeze_support

freeze_support()

from nicegui import ui

from aerobooks import auth, paths
from aerobooks.pages import register

auth.init_auth()
register()


def _run() -> None:
    host = os.environ.get("AEROBOOKS_HOST", "0.0.0.0")
    port = int(os.environ.get("AEROBOOKS_PORT", "8765"))
    icon = paths.icon_path()
    ui.run(
        title="AeroBooks",
        reload=False,
        show=False,
        favicon=str(icon) if icon else "✈️",
        storage_secret=paths.storage_secret(),
        native=False,
        host=host,
        port=port,
    )


if __name__ in {"__main__", "__mp_main__"}:
    _run()
