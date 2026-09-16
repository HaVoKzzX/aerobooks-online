"""Flight school manager: instructor sub-accounts."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth, db
from aerobooks.streamlit_ui import chrome


def render(user: dict) -> None:
    if user.get("role") != "manager":
        st.warning("Only the flight school manager can add instructor accounts.")
        return
    chrome.page_title(
        "Instructors",
        "Add logins for CFIs at your school. Each instructor has their own students. "
        "Invoices always use your school business name.",
    )
    school = db.get_settings().get("business_name") or db.display_name()
    chrome.alert(f"<b>Invoice business name: {school}</b><br>Instructors cannot change this. Set it in Settings.", gold=True)

    if st.button("Add instructor", type="primary"):
        st.session_state.add_instructor = True
        st.rerun()

    users = auth.list_tenant_users(int(user["tenant_id"]))
    if not users:
        st.caption("No instructors yet.")
    for u in users:
        st.markdown(
            f"<div class='ab-card'><b>{u.get('display_name') or u['username']}</b> "
            f"{chrome.chip(u['status'])}<br>"
            f"<span class='ab-sub'>@{u['username']} · {auth.role_label(u['role'])}</span></div>",
            unsafe_allow_html=True,
        )
        if u["role"] != "manager":
            c1, c2 = st.columns(2)
            if u["status"] == "active":
                if c1.button("Disable", key=f"dis-{u['id']}"):
                    auth.set_user_status(int(u["id"]), "disabled")
                    st.rerun()
            else:
                if c1.button("Enable", key=f"en-{u['id']}"):
                    auth.set_user_status(int(u["id"]), "active")
                    st.rerun()
            if c2.button("Password", key=f"pw-{u['id']}"):
                st.session_state.reset_pw_user = int(u["id"])
                st.rerun()

    if st.session_state.get("add_instructor"):
        _add(user)
    if st.session_state.get("reset_pw_user"):
        _password(int(st.session_state.reset_pw_user))


@st.dialog("New school instructor")
def _add(manager: dict) -> None:
    st.caption("They sign in with this username and only see the students assigned to them.")
    display = st.text_input("Instructor name")
    username = st.text_input("Username")
    email = st.text_input("Email")
    phone = st.text_input("Phone")
    password = st.text_input("Password", type="password")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("add_instructor", None)
        st.rerun()
    if c2.button("Create", type="primary"):
        try:
            auth.create_school_instructor(
                manager,
                username=username or "",
                password=password or "",
                display_name=display or "",
                email=email or "",
                phone=phone or "",
            )
            st.session_state.pop("add_instructor", None)
            st.rerun()
        except ValueError as err:
            st.warning(str(err))


@st.dialog("Reset password")
def _password(user_id: int) -> None:
    pw = st.text_input("New password", type="password")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("reset_pw_user", None)
        st.rerun()
    if c2.button("Save password", type="primary"):
        try:
            auth.set_password(user_id, pw or "")
            st.session_state.pop("reset_pw_user", None)
            st.rerun()
        except ValueError as err:
            st.warning(str(err))
