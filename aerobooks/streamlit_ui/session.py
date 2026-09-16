"""Bind the current Streamlit visitor to an AeroBooks user and tenant."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth, cloud, db, paths

USER_KEY = "ab_user_id"


def bootstrap() -> dict | None:
    auth.init_auth()
    cloud.bootstrap_admin()
    uid = st.session_state.get(USER_KEY)
    if not uid:
        auth.bind_user(None)
        paths.bind_tenant(None)
        return None
    user = auth.get_user(int(uid))
    if not user or user.get("status") != "active":
        logout()
        return None
    auth.bind_user(user)
    if user.get("tenant_id"):
        paths.bind_tenant(int(user["tenant_id"]))
        db.init_db()
    return user


def login(username: str, password: str) -> dict:
    user = auth.authenticate(username, password)
    st.session_state[USER_KEY] = int(user["id"])
    auth.bind_user(user)
    if user.get("tenant_id"):
        paths.bind_tenant(int(user["tenant_id"]))
        db.init_db()
    return user


def logout() -> None:
    auth.bind_user(None)
    paths.bind_tenant(None)
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def current() -> dict | None:
    return auth.current_user()
