"""Sign-in and first-run administrator setup."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth, cloud
from aerobooks.streamlit_ui import chrome, session as sess


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="ab-auth-hero">
          <p class="ab-brand">AeroBooks</p>
          <p class="ab-brand-sub">CFI invoicing</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    chrome.page_title(title, subtitle)


def render_setup() -> None:
    if cloud.on_community_cloud() and not (
        cloud.secret("AEROBOOKS_ADMIN_USERNAME") and cloud.secret("AEROBOOKS_ADMIN_PASSWORD")
    ):
        _hero("Administrator not configured", "This public Streamlit app will not let a stranger create the admin account.")
        st.error(
            "In [share.streamlit.io](https://share.streamlit.io) open this app → **Settings → Secrets** "
            "and paste the values from `.streamlit/secrets.toml.example`. Reboot the app after saving."
        )
        return
    _hero(
        "Create the administrator",
        "This is the only account that can approve independent instructors and flight school managers.",
    )
    with st.form("setup_admin"):
        display = st.text_input("Your name")
        username = st.text_input("Admin username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create admin account", type="primary", use_container_width=True)
    if submitted:
        if password != confirm:
            st.warning("Passwords do not match")
            return
        try:
            user = auth.create_admin(username or "", password or "", display or "")
            sess.login(user["username"], password)
            st.rerun()
        except ValueError as err:
            st.warning(str(err))


def render_login() -> None:
    _hero("Sign in", "Use the username you requested, after it has been approved.")
    with st.form("sign_in"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submitted:
        try:
            sess.login(username or "", password or "")
            st.rerun()
        except ValueError as err:
            st.warning(str(err))
    st.caption("Need an account? Open **Request access** in the sidebar.")
