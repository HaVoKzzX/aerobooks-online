"""Administrator: approve account requests and manage users."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth
from aerobooks.streamlit_ui import chrome


def render_requests(admin: dict) -> None:
    chrome.page_title("Account requests", "Approve independent instructors and flight school managers.")
    pending = auth.list_requests("pending")
    if not pending:
        chrome.card_md("No pending requests.")
    else:
        for req in pending:
            kind = "Flight school manager" if req["account_type"] == "manager" else "Independent instructor"
            bits = [kind]
            if req.get("organization"):
                bits.append(f"School: {req['organization']}")
            contact = " · ".join(x for x in (req.get("email"), req.get("phone")) if x)
            extra = f"<br>{req['notes']}" if req.get("notes") else ""
            st.markdown(
                f"<div class='ab-card'><b>{req['display_name']} · @{req['username']}</b><br>"
                f"<span class='ab-sub'>{' · '.join(bits)}"
                + (f" · {contact}" if contact else "")
                + f"<br>Requested {req['created_at']}</span>{extra}</div>",
                unsafe_allow_html=True,
            )
            c1, c2 = st.columns(2)
            if c1.button("Approve", key=f"ap-{req['id']}", type="primary", use_container_width=True):
                try:
                    auth.approve_request(req["id"], admin["id"])
                    st.success(f"Approved {req['username']}")
                    st.rerun()
                except ValueError as err:
                    st.warning(str(err))
            if c2.button("Reject", key=f"rj-{req['id']}", use_container_width=True):
                st.session_state.reject_id = int(req["id"])
                st.rerun()

    reviewed = [r for r in auth.list_requests("all") if r["status"] != "pending"][:20]
    if reviewed:
        st.markdown("**Recently reviewed**")
        for req in reviewed:
            st.markdown(
                f"{chrome.chip(req['status'])} {req['display_name']} (@{req['username']}) · {req.get('reviewed_at') or ''}",
                unsafe_allow_html=True,
            )

    if st.session_state.get("reject_id"):
        _reject(admin, int(st.session_state.reject_id))


def render_users(_admin: dict) -> None:
    chrome.page_title("Users", "Every account on this AeroBooks server.")
    users = auth.list_users()
    for u in users:
        st.markdown(
            f"<div class='ab-card'><b>@{u['username']}</b> {u.get('display_name') or ''} "
            f"{chrome.chip(u['status'])}<br>"
            f"<span class='ab-sub'>{auth.role_label(u['role'])} · {u.get('tenant_name') or '—'}</span></div>",
            unsafe_allow_html=True,
        )
        if u["role"] != "admin":
            c1, c2 = st.columns(2)
            if u["status"] == "active":
                if c1.button("Disable", key=f"udis-{u['id']}"):
                    try:
                        auth.set_user_status(int(u["id"]), "disabled")
                        st.rerun()
                    except ValueError as err:
                        st.warning(str(err))
            else:
                if c1.button("Enable", key=f"uen-{u['id']}"):
                    auth.set_user_status(int(u["id"]), "active")
                    st.rerun()
            if c2.button("Password", key=f"upw-{u['id']}"):
                st.session_state.admin_pw = int(u["id"])
                st.rerun()

    st.markdown("**Workspaces**")
    for t in auth.list_tenants():
        kind = "Flight school" if t["kind"] == "school" else "Independent"
        st.markdown(
            f"<div class='ab-card'><b>{t['name']}</b><br>"
            f"<span class='ab-sub'>{kind} · {t['user_count']} user(s) · owner @{t.get('owner_username') or '—'}</span></div>",
            unsafe_allow_html=True,
        )

    if st.session_state.get("admin_pw"):
        _password(int(st.session_state.admin_pw))


@st.dialog("Reject request")
def _reject(admin: dict, request_id: int) -> None:
    reason = st.text_input("Reason (optional)")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("reject_id", None)
        st.rerun()
    if c2.button("Reject", type="primary"):
        try:
            auth.reject_request(request_id, admin["id"], reason or "")
            st.session_state.pop("reject_id", None)
            st.rerun()
        except ValueError as err:
            st.warning(str(err))


@st.dialog("Reset password")
def _password(user_id: int) -> None:
    pw = st.text_input("New password", type="password")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("admin_pw", None)
        st.rerun()
    if c2.button("Save password", type="primary"):
        try:
            auth.set_password(user_id, pw or "")
            st.session_state.pop("admin_pw", None)
            st.rerun()
        except ValueError as err:
            st.warning(str(err))
