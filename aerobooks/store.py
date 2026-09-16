"""Encrypted SQLite connections and file I/O."""

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


def _read_sqlite_blob(path: Path) -> bytes:
    encrypted = enc_path(path)
    if encrypted.exists():
        return decrypt_bytes(encrypted.read_bytes())
    if path.exists():
        shm = Path(str(path) + "-shm")
        if shm.exists():
            try:
                shm.unlink()
            except OSError:
                pass
        try:
            conn = sqlite3.connect(str(path))
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                conn.execute("PRAGMA journal_mode=DELETE")
                conn.commit()
                blob = conn.serialize()
            finally:
                conn.close()
            return blob
        except sqlite3.Error:
            raw = path.read_bytes()
            if raw.startswith(b"SQLite format 3"):
                return raw
            raise
    return b""


def _scrub_plaintext_sqlite(path: Path) -> None:
    for leftover in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if leftover.exists():
            try:
                leftover.unlink()
            except OSError:
                pass


def _save_sqlite_blob(path: Path, blob: bytes) -> None:
    dest = enc_path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    payload = encrypt_bytes(blob)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(dest)
    _scrub_plaintext_sqlite(path)


def export_sqlite(path: Path) -> bytes:
    """Plain SQLite bytes for a portable AeroBooks backup zip."""
    key = str(Path(path).resolve())
    frames = getattr(_local, "frames", None) or {}
    if key in frames:
        frames[key].conn.commit()
        return frames[key].conn.serialize()
    return _read_sqlite_blob(Path(path))


@contextmanager
def encrypted_db(path: Path):
    path = Path(path)
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
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    blob = _read_sqlite_blob(path)
    if blob:
        conn.deserialize(blob)
    # Deserialized desktop DBs are often WAL; :memory: cannot use WAL.
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA foreign_keys = ON")
    frames[key] = _Frame(conn)
    try:
        yield conn
        conn.commit()
        _save_sqlite_blob(path, conn.serialize())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        frames.pop(key, None)
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
