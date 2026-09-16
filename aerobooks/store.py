"""Encrypted SQLite connections and file I/O.

Uses a real on-disk SQLite file (not :memory: deserialize). Streamlit Cloud
cannot reliably journal an in-memory WAL snapshot, and cannot write SQLite
into the cloned repo at /mount/src.
"""

from __future__ import annotations

import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

from aerobooks.crypto import decrypt_bytes, encrypt_bytes, is_encrypted

_global = threading.Lock()
_path_locks: dict[str, threading.RLock] = {}
_local = threading.local()


class _Frame:
    __slots__ = ("conn", "depth")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.depth = 1


def _path_lock(key: str) -> threading.RLock:
    with _global:
        lock = _path_locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _path_locks[key] = lock
        return lock


def enc_path(path: Path) -> Path:
    path = Path(path)
    if path.name.endswith(".enc"):
        return path
    return path.with_name(path.name + ".enc")


def _materialize_working_db(path: Path) -> None:
    """Make sure path is a usable plaintext SQLite file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encrypted = enc_path(path)
    if path.exists() and path.stat().st_size and path.read_bytes()[:16].startswith(b"SQLite format 3"):
        return
    if encrypted.exists():
        raw = decrypt_bytes(encrypted.read_bytes())
        tmp = path.with_suffix(path.suffix + ".load")
        tmp.write_bytes(raw)
        tmp.replace(path)
        return
    if path.exists() and is_encrypted(path.read_bytes()[:8] if path.stat().st_size else b""):
        raw = decrypt_bytes(path.read_bytes())
        path.write_bytes(raw)


def _read_sqlite_blob(path: Path) -> bytes:
    _materialize_working_db(path)
    path = Path(path)
    if not path.exists():
        return b""
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        return conn.serialize() if hasattr(conn, "serialize") else path.read_bytes()
    finally:
        conn.close()


def export_sqlite(path: Path) -> bytes:
    """Plain SQLite bytes for a portable AeroBooks backup zip."""
    key = str(Path(path).resolve())
    frames = getattr(_local, "frames", None) or {}
    if key in frames:
        frames[key].conn.commit()
        conn = frames[key].conn
        if hasattr(conn, "serialize"):
            return conn.serialize()
    _materialize_working_db(path)
    p = Path(path)
    return p.read_bytes() if p.exists() else b""


def _persist_encrypted(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    try:
        payload = encrypt_bytes(path.read_bytes())
        dest = enc_path(path)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(dest)
    except OSError:
        pass


@contextmanager
def encrypted_db(path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    frames = getattr(_local, "frames", None)
    if frames is None:
        _local.frames = frames = {}
    existing = frames.get(key)
    if existing:
        existing.depth += 1
        try:
            yield existing.conn
        finally:
            existing.depth -= 1
        return

    lock = _path_lock(key)
    lock.acquire()
    try:
        _materialize_working_db(path)
        conn = sqlite3.connect(str(path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.Error:
            pass
        frames[key] = _Frame(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            frames.pop(key, None)
            _persist_encrypted(path)
    finally:
        lock.release()


def secure_write(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = encrypt_bytes(data)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def secure_read(path: Path) -> bytes:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    raw = path.read_bytes()
    if is_encrypted(raw):
        return decrypt_bytes(raw)
    return raw


def maybe_encrypt_existing_file(path: Path) -> None:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return
    raw = path.read_bytes()
    if not raw or is_encrypted(raw):
        return
    secure_write(path, raw)


def encrypt_tree(folder: Path, suffixes: tuple[str, ...] = (".pdf", ".png", ".jpg", ".jpeg", ".zip")) -> None:
    folder = Path(folder)
    if not folder.exists():
        return
    for item in folder.rglob("*"):
        if item.is_file() and item.suffix.lower() in suffixes:
            maybe_encrypt_existing_file(item)


def decrypt_to_temp(path: Path) -> Path:
    data = secure_read(path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=path.suffix)
    tmp.write(data)
    tmp.close()
    return Path(tmp.name)
