"""Shared Streamlit layout: CSS, sidebar brand, stats, chips, navigation."""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from aerobooks import auth, db, paths
from aerobooks.streamlit_ui.css import CSS
from aerobooks.streamlit_ui import session as sess

PAGES: dict[str, object] = {}
LOGO = Path(__file__).resolve().parent.parent / "assets" / "aerobooks_logo.png"


def apply_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def register_pages(pages: dict[str, object]) -> None:
    PAGES.clear()
    PAGES.update(pages)


def go(name: str, **state) -> None:
    for key, value in state.items():
        if value is None:
            st.session_state.pop(key, None)
        else:
            st.session_state[key] = value
    target = PAGES.get(name)
    if target is not None:
        st.switch_page(target)
    else:
        st.rerun()


def chip(status: str) -> str:
    label = escape((status or "").replace("_", " "))
    cls = escape(status or "draft")
    return f'<span class="ab-chip ab-status-{cls}">{label}</span>'


def stats_html(items: list[tuple]) -> None:
    """items: (label, value, hint='', kind='')"""
    parts = ['<div class="ab-stats">']
    for item in items:
        label, value = item[0], item[1]
        hint = item[2] if len(item) > 2 else ""
        kind = item[3] if len(item) > 3 else ""
        parts.append(
            f'<div class="ab-stat {escape(kind)}">'
            f'<div class="ab-stat-label">{escape(str(label))}</div>'
            f'<div class="ab-stat-value">{escape(str(value))}</div>'
        )
        if hint:
            parts.append(f'<div class="ab-stat-hint">{escape(str(hint))}</div>')
        parts.append("</div>")
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def page_title(title: str, subtitle: str = "") -> None:
    st.markdown(f'<p class="ab-h1">{escape(title)}</p>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="ab-sub">{escape(subtitle)}</p>', unsafe_allow_html=True)


def alert(text: str, *, gold: bool = False) -> None:
    cls = "ab-alert-gold" if gold else "ab-alert"
    st.markdown(f'<div class="{cls}">{text}</div>', unsafe_allow_html=True)


def card_md(html: str) -> None:
    st.markdown(f'<div class="ab-card">{html}</div>', unsafe_allow_html=True)


def sidebar_brand(user: dict | None) -> None:
    with st.sidebar:
        if LOGO.exists():
            st.image(str(LOGO), width=56)
        st.markdown('<p class="ab-brand">AeroBooks</p>', unsafe_allow_html=True)
        if user and user.get("role") == "admin":
            st.markdown(
                '<p class="ab-brand-sub">Access control</p>',
                unsafe_allow_html=True,
            )
        elif user:
            st.markdown(
                f'<p class="ab-brand-sub">{escape(auth.role_label(user["role"]))}</p>',
                unsafe_allow_html=True,
            )
            try:
                name = db.display_name()
            except Exception:
                name = ""
            if name:
                st.caption(name)
        else:
            st.markdown(
                '<p class="ab-brand-sub">CFI invoicing</p>',
                unsafe_allow_html=True,
            )

        if user:
            who = user.get("display_name") or user.get("username") or ""
            st.caption(f"Signed in as {who}")
            if st.button("Sign out", use_container_width=True):
                sess.logout()
                st.rerun()


def workspace_actions(user: dict) -> None:
    if user.get("role") == "admin":
        return
    try:
        stats = db.dashboard_stats()
        overdue = stats.get("overdue_30_count") or 0
    except Exception:
        overdue = 0
        stats = {}
    cols = st.columns(3 if overdue else 2)
    if overdue:
        with cols[0]:
            if st.button(f"{overdue} overdue 30+", use_container_width=True):
                go("invoices", invoice_id=None, invoice_new=False, invoice_filter="overdue_30")
        with cols[1]:
            if st.button("Log hours", use_container_width=True):
                go("hours")
        with cols[2]:
            if st.button("New invoice", type="primary", use_container_width=True):
                go("invoices", invoice_new=True, invoice_id=None)
    else:
        with cols[0]:
            if st.button("Log hours", use_container_width=True):
                go("hours")
        with cols[1]:
            if st.button("New invoice", type="primary", use_container_width=True):
                go("invoices", invoice_new=True, invoice_id=None)
    if overdue and stats.get("overdue_count"):
        pass
