"""Serve AeroBooks Online as a mobile-friendly Streamlit app."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from aerobooks import auth
from aerobooks.streamlit_ui import (
    admin,
    chrome,
    dashboard,
    earnings,
    expenses,
    hours,
    invoices,
    login,
    request_access,
    session as sess,
    settings,
    students,
    team,
)
from aerobooks.streamlit_ui.chrome import LOGO

st.set_page_config(
    page_title="AeroBooks",
    page_icon=str(LOGO) if LOGO.exists() else "✈️",
    layout="wide",
    initial_sidebar_state="auto",
)

chrome.apply_theme()
user = sess.bootstrap()


def page_setup():
    login.render_setup()


def page_login():
    login.render_login()


def page_request():
    request_access.render()


def page_admin_requests():
    admin.render_requests(sess.current())


def page_admin_users():
    admin.render_users(sess.current())


def page_dashboard():
    dashboard.render(sess.current())


def page_students():
    students.render(sess.current())


def page_hours():
    hours.render()


def page_invoices():
    invoices.render()


def page_expenses():
    expenses.render()


def page_earnings():
    earnings.render()


def page_settings():
    settings.render(sess.current())


def page_team():
    team.render(sess.current())


if not auth.has_admin():
    nav_pages = [st.Page(page_setup, title="Create admin", icon="🛠️", default=True)]
    named = {}
elif not user:
    nav_pages = [
        st.Page(page_login, title="Sign in", icon="✈️", default=True),
        st.Page(page_request, title="Request access", icon="📝"),
    ]
    named = {"login": nav_pages[0], "request": nav_pages[1]}
elif user["role"] == "admin":
    nav_pages = [
        st.Page(page_admin_requests, title="Requests", icon="✅", default=True),
        st.Page(page_admin_users, title="Users", icon="👥"),
    ]
    named = {"admin": nav_pages[0], "admin_users": nav_pages[1]}
else:
    nav_pages = [
        st.Page(page_dashboard, title="Dashboard", icon="📊", default=True),
        st.Page(page_students, title="Students", icon="🎓"),
        st.Page(page_hours, title="Log Hours", icon="🛫"),
        st.Page(page_invoices, title="Invoices", icon="🧾"),
        st.Page(page_expenses, title="Expenses", icon="💳"),
        st.Page(page_earnings, title="Earnings", icon="📈"),
    ]
    named = {
        "dashboard": nav_pages[0],
        "students": nav_pages[1],
        "hours": nav_pages[2],
        "invoices": nav_pages[3],
        "expenses": nav_pages[4],
        "earnings": nav_pages[5],
    }
    if user.get("role") == "manager":
        team_page = st.Page(page_team, title="Instructors", icon="👥")
        nav_pages.append(team_page)
        named["team"] = team_page
    settings_page = st.Page(page_settings, title="Settings", icon="⚙️")
    nav_pages.append(settings_page)
    named["settings"] = settings_page

chrome.sidebar_brand(user)
chrome.register_pages(named)
st.navigation(nav_pages).run()
