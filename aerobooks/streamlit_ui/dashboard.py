"""Home dashboard with overdue reminders and this-month snapshot."""

from __future__ import annotations

import streamlit as st

from aerobooks import db
from aerobooks.money import fmt_date, fmt_hours, fmt_money
from aerobooks.streamlit_ui import chrome


def render(user: dict | None = None) -> None:
    stats = db.dashboard_stats()
    s = db.get_settings()
    who = db.instructor_display()
    hello = f"Welcome back{', ' + who if who != 'Instructor' else ''}."
    chrome.page_title("Dashboard", hello)
    chrome.workspace_actions(user or {})

    if not db.is_setup_complete():
        chrome.alert(
            "<b>Finish setup so invoices look professional.</b><br>"
            "Add your name (or business name), address, rates, and Venmo username in Settings.",
            gold=True,
        )
        if st.button("Open Settings"):
            chrome.go("settings")

    if stats["overdue_30_count"]:
        chrome.alert(
            f"<b>{stats['overdue_30_count']} invoice(s) are 30+ days overdue — "
            f"{fmt_money(stats['overdue_30_amount'])}</b><br>"
            "Send a reminder, or open the invoice to record a payment."
        )
        for inv in db.list_invoices(status="overdue_30"):
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            with c1:
                st.markdown(
                    f"**{inv['number']} · {inv['student_name']}**<br>"
                    f"<span class='ab-sub'>{fmt_money(inv['balance'])} due {fmt_date(inv['due_date'])} · "
                    f"{inv['days_overdue']} days overdue</span>",
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Reminder", key=f"dash-rem-{inv['id']}"):
                    st.session_state[f"copied-{inv['id']}"] = db.reminder_message(inv)
            with c3:
                if st.button("Open", key=f"dash-open-{inv['id']}"):
                    chrome.go("invoices", invoice_id=int(inv["id"]), invoice_new=False)
            with c4:
                if st.button("Mark paid", key=f"dash-paid-{inv['id']}"):
                    db.mark_invoice_paid(int(inv["id"]))
                    st.success("Marked paid")
                    st.rerun()
            copied = st.session_state.get(f"copied-{inv['id']}")
            if copied:
                st.code(copied, language=None)
    elif stats["overdue_count"]:
        chrome.alert(
            f"<b>{stats['overdue_count']} invoice(s) past due — {fmt_money(stats['overdue_amount'])}</b>",
            gold=True,
        )
        if st.button("Review unpaid invoices"):
            chrome.go("invoices", invoice_filter="unpaid", invoice_id=None, invoice_new=False)

    chrome.stats_html(
        [
            ("Collected this month", fmt_money(stats["collected_month"]), "Payments received"),
            ("Billed this month", fmt_money(stats["billed_month"])),
            (
                "Outstanding",
                fmt_money(stats["outstanding"]),
                f"{stats['overdue_count']} past due",
                "warn" if stats["outstanding"] else "",
            ),
            (
                "Net this month",
                fmt_money(stats["net_month"]),
                f"Expenses {fmt_money(stats['expenses_month'])}",
                "good" if stats["net_month"] >= 0 else "warn",
            ),
        ]
    )
    chrome.stats_html(
        [
            ("Active students", str(stats["active_students"])),
            ("Hours this month", fmt_hours(stats["hours_month"])),
            (
                "Unbilled hours",
                fmt_hours(stats["unbilled_hours"]),
                fmt_money(stats["unbilled_amount"]) + " ready to invoice",
                "gold" if stats["unbilled_hours"] else "",
            ),
            ("YTD collected", fmt_money(stats["ytd_collected"]), f"Net {fmt_money(stats['ytd_net'])}"),
        ]
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown('<p class="ab-card-title">Unbilled training</p>', unsafe_allow_html=True)
        unbilled = db.list_sessions(unbilled_only=True, limit=8)
        if not unbilled:
            st.caption("Nothing waiting to invoice. Nice.")
        else:
            for sess_row in unbilled:
                st.markdown(
                    f"{sess_row['student_name']} · {db.training_type_label(sess_row['training_type'])} · "
                    f"{fmt_hours(sess_row['hours'])} hr  \n"
                    f":gray[{fmt_date(sess_row['date'])}]"
                )
            if st.button("Create invoice from unbilled"):
                chrome.go("invoices", invoice_new=True, invoice_id=None)
    with col_b:
        st.markdown('<p class="ab-card-title">Recent invoices</p>', unsafe_allow_html=True)
        recent = db.list_invoices()[:8]
        if not recent:
            st.caption("No invoices yet.")
        else:
            for inv in recent:
                label = f"{inv['number']} · {inv['student_name']}"
                if st.button(label, key=f"dash-inv-{inv['id']}"):
                    chrome.go("invoices", invoice_id=int(inv["id"]), invoice_new=False)
                st.markdown(
                    f"{chrome.chip(inv.get('display_status') or inv['status'])} "
                    f"{fmt_money(inv['balance'] if inv['balance'] else inv['total'])}",
                    unsafe_allow_html=True,
                )
    with col_c:
        st.markdown('<p class="ab-card-title">Watch list</p>', unsafe_allow_html=True)
        alerts = stats["medical_alerts"]
        if not alerts:
            st.caption("No medicals expiring in the next 60 days.")
        else:
            st.caption("Student medicals")
            for m in alerts:
                st.write(f"{m['first_name']} {m['last_name']} · expires {fmt_date(m['medical_expires'])}")
        if not (s.get("venmo_username") or "").strip():
            st.warning("Venmo username is not set — invoices will not include a QR code.")
