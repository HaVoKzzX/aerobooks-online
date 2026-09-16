"""Streamlit Community Cloud secrets and first-run admin."""

from __future__ import annotations

import os
from pathlib import Path


def on_community_cloud() -> bool:
    if os.environ.get("STREAMLIT_RUNTIME") == "cloud":
        return True
    return Path("/home/adminuser").exists()


def secret(name: str, default: str = "") -> str:
    raw = os.environ.get(name, "").strip()
    if raw:
        return raw
    try:
        import streamlit as st

        raw = str(st.secrets.get(name, default) or default).strip()
        return raw
    except Exception:
        return (default or "").strip()


def bootstrap_admin() -> None:
    from aerobooks import auth

    if auth.has_admin():
        return
    username = secret("AEROBOOKS_ADMIN_USERNAME")
    password = secret("AEROBOOKS_ADMIN_PASSWORD")
    if not username or not password:
        return
    try:
        auth.create_admin(username, password, secret("AEROBOOKS_ADMIN_NAME") or username)
    except ValueError:
        pass
