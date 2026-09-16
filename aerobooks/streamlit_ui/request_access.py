"""Public form to request an independent instructor or manager account."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth
from aerobooks.streamlit_ui import chrome


def render() -> None:
    if st.session_state.get("ab_request_done"):
        st.markdown(
            """
            <div class="ab-auth-hero">
              <p class="ab-brand">AeroBooks</p>
              <p class="ab-brand-sub">CFI invoicing</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        chrome.page_title("Request submitted", "The administrator will review it. You can sign in after it is approved.")
        if st.button("Back to sign in", type="primary", use_container_width=True):
            st.session_state.pop("ab_request_done", None)
            chrome.go("login")
        return

    st.markdown(
        """
        <div class="ab-auth-hero">
          <p class="ab-brand">AeroBooks</p>
          <p class="ab-brand-sub">CFI invoicing</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    chrome.page_title(
        "Request an account",
        "Independent instructors get a private books workspace. "
        "Flight school managers can add instructor logins under one business name.",
    )

    kinds = {
        "instructor": "Independent instructor (my own students and invoices)",
        "manager": "Flight school owner / manager",
    }
    account_type = st.selectbox("Account type", list(kinds), format_func=lambda k: kinds[k])
    with st.form("request_access"):
        display = st.text_input("Your name")
        organization = ""
        if account_type == "manager":
            organization = st.text_input("Flight school / business name")
        email = st.text_input("Email")
        phone = st.text_input("Phone")
        username = st.text_input("Desired username")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        notes = st.text_area("Anything the admin should know")
        submitted = st.form_submit_button("Submit request", type="primary", use_container_width=True)

    if submitted:
        if (password or "") != (confirm or ""):
            st.warning("Passwords do not match")
            return
        try:
            auth.submit_request(
                username=username or "",
                password=password or "",
                account_type=account_type,
                display_name=display or "",
                email=email or "",
                phone=phone or "",
                organization=organization or "",
                notes=notes or "",
            )
            st.session_state.ab_request_done = True
            st.rerun()
        except ValueError as err:
            st.warning(str(err))
