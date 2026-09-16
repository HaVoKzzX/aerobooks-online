"""Install vs data locations for the multi-user online edition.

Auth lives in one shared database. Each independent instructor and each
flight school gets a tenant folder with its own AeroBooks database, PDFs,
and QR codes so users cannot see each other's records.
"""

from __future__ import annotations

import os
import sys
from contextvars import ContextVar
from pathlib import Path

APP_NAME = "AeroBooks Online"
APP_VERSION = "2.0.0"

_tenant_id: ContextVar[int | None] = ContextVar("aerobooks_tenant_id", default=None)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def meipass() -> Path | None:
    raw = getattr(sys, "_MEIPASS", None)
    return Path(raw) if raw else None


_DATA_ROOT: Path | None = None


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def base_data_dir() -> Path:
    global _DATA_ROOT
    override = os.environ.get("AEROBOOKS_DATA")
    if override:
        return Path(override)
    if _DATA_ROOT is not None:
        return _DATA_ROOT
    candidates: list[Path] = []
    # Streamlit Community Cloud mounts the repo at /mount/src as a bad place
    # for SQLite (read-only or no journal files). Keep books in a writable dir.
    try:
        from aerobooks.cloud import on_community_cloud

        cloud = on_community_cloud()
    except Exception:
        cloud = False
    if cloud or Path("/mount/src").exists():
        candidates.append(Path.home() / ".aerobooks-data")
        candidates.append(Path("/tmp/aerobooks-data"))
    candidates.append(install_dir() / "data")
    for path in candidates:
        if _writable_dir(path):
            _DATA_ROOT = path
            return path
    _DATA_ROOT = candidates[-1]
    return _DATA_ROOT


def auth_db_path() -> Path:
    return base_data_dir() / "auth.db"


def storage_secret_path() -> Path:
    return base_data_dir() / "storage_secret.txt"


def bind_tenant(tenant_id: int | None) -> None:
    _tenant_id.set(int(tenant_id) if tenant_id else None)


def current_tenant_id() -> int | None:
    tid = _tenant_id.get()
    if tid:
        return int(tid)
    try:
        from nicegui import app

        stored = app.storage.user.get("tenant_id")
        if stored:
            return int(stored)
    except Exception:
        pass
    return None


def tenant_data_dir(tenant_id: int | None = None) -> Path:
    tid = tenant_id if tenant_id is not None else current_tenant_id()
    if not tid:
        return base_data_dir() / "system"
    return base_data_dir() / "tenants" / str(int(tid))


def data_dir() -> Path:
    return tenant_data_dir()


def documents_backup_dir() -> Path:
    return tenant_data_dir() / "backups"


def original_desktop_backup_dir() -> Path:
    """Where the local AeroBooks desktop app saves backup zips."""
    user = os.environ.get("USERPROFILE")
    base = Path(user) / "Documents" if user else Path.home() / "Documents"
    return base / "AeroBooks Backups"


def invoice_dir() -> Path:
    return data_dir() / "invoices"


def qr_dir() -> Path:
    return data_dir() / "qr"


def local_backup_dir() -> Path:
    return data_dir() / "backups"


def db_path() -> Path:
    return data_dir() / "aerobooks.db"


def icon_path() -> Path | None:
    for candidate in (
        install_dir() / "aerobooks.ico",
        install_dir() / "packaging" / "aerobooks.ico",
        Path(__file__).resolve().parent.parent / "packaging" / "aerobooks.ico",
    ):
        if candidate.exists():
            return candidate
    return None


def ensure_base_dirs() -> None:
    base_data_dir().mkdir(parents=True, exist_ok=True)


def ensure_data_dirs() -> None:
    ensure_base_dirs()
    for folder in (data_dir(), invoice_dir(), qr_dir(), local_backup_dir()):
        folder.mkdir(parents=True, exist_ok=True)


def storage_secret() -> str:
    ensure_base_dirs()
    path = storage_secret_path()
    if path.exists():
        secret = path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
    import secrets as _secrets

    secret = _secrets.token_hex(32)
    path.write_text(secret, encoding="utf-8")
    return secret
