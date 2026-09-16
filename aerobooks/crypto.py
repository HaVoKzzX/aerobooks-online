"""AES-256-GCM encryption for data at rest.

The data folder can be copied; without this machine's key (Windows DPAPI)
or AEROBOOKS_DATA_KEY, the files are unreadable.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

MAGIC = b"ABENC1"
NONCE_LEN = 12
KEY_LEN = 32
INFO = b"aerobooks-online-data-v1"


def _dpapi_protect(raw: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = DATA_BLOB(len(raw), ctypes.create_string_buffer(raw, len(raw)))
    blob_out = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _dpapi_unprotect(blob: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = DATA_BLOB(len(blob), ctypes.create_string_buffer(blob, len(blob)))
    blob_out = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _env_key() -> bytes | None:
    raw = os.environ.get("AEROBOOKS_DATA_KEY", "").strip()
    if not raw and "streamlit" in sys.modules:
        try:
            import streamlit as st

            raw = str(st.secrets.get("AEROBOOKS_DATA_KEY", "")).strip()
        except Exception:
            raw = ""
    if not raw:
        return None
    try:
        import base64

        decoded = base64.b64decode(raw)
        if len(decoded) == KEY_LEN:
            return decoded
    except Exception:
        pass
    return HKDF(algorithm=hashes.SHA256(), length=KEY_LEN, salt=None, info=INFO).derive(
        raw.encode("utf-8")
    )


def _key_file() -> Path:
    from aerobooks import paths

    if os.name == "nt":
        return paths.base_data_dir() / "master.key.dpapi"
    return Path.home() / ".aerobooks_data_key"


def load_or_create_key() -> bytes:
    env = _env_key()
    if env:
        return env
    path = _key_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stored = path.read_bytes()
        if os.name == "nt":
            return _dpapi_unprotect(stored)
        if len(stored) == KEY_LEN:
            return stored
        raise ValueError("AeroBooks data key file is invalid.")
    key = secrets.token_bytes(KEY_LEN)
    if os.name == "nt":
        path.write_bytes(_dpapi_protect(key))
    else:
        path.write_bytes(key)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return key


def is_encrypted(data: bytes | None) -> bool:
    return bool(data) and data.startswith(MAGIC)


def encrypt_bytes(plain: bytes, *, key: bytes | None = None) -> bytes:
    key = key or load_or_create_key()
    nonce = secrets.token_bytes(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plain, INFO)
    return MAGIC + nonce + ct


def decrypt_bytes(blob: bytes, *, key: bytes | None = None) -> bytes:
    if not is_encrypted(blob):
        return blob
    key = key or load_or_create_key()
    nonce = blob[len(MAGIC) : len(MAGIC) + NONCE_LEN]
    ct = blob[len(MAGIC) + NONCE_LEN :]
    try:
        return AESGCM(key).decrypt(nonce, ct, INFO)
    except Exception as err:
        raise ValueError(
            "Could not decrypt AeroBooks data. This copy was encrypted on another "
            "computer, or AEROBOOKS_DATA_KEY does not match."
        ) from err
