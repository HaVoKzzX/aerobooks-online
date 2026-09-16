"""Log flight, ground, instrument, simulator, and other training hours."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from aerobooks import db
from aerobooks.money import fmt_date, fmt_hours, fmt_money, money
from aerobooks.streamlit_ui import chrome


def render() -> None:
    chrome.page_title("Log hours", "Record a lesson. Billable time waits on the invoice screen until you invoice it.")

    options = {s["id"]: s["label"] for s in db.student_options() if s["status"] != "inactive"}
    if not options:
        chrome.card_md("Add a student first.")
        if st.button("Add student", type="primary"):
            chrome.go("students")
        return

    type_opts = {code: label for code, label in db.TRAINING_TYPES}
    rates = db.list_rates(active_only=True)
    rate_opts = {r["id"]: f"{r['name']}  ·  {fmt_money(r['price'])}/{r['unit']}" for r in rates}

    ids = list(options)
    preselect = st.session_state.get("hours_student")
    if preselect not in options:
        preselect = ids[0]

    student_id = st.selectbox("Student", ids, index=ids.index(preselect), format_func=lambda i: options[i])
    c1, c2 = st.columns(2)
    sess_date = c1.date_input("Date", value=date.today(), format="YYYY-MM-DD")
    ttype = c2.selectbox("Training type", list(type_opts), format_func=lambda c: type_opts[c])

    default_rate = db.find_rate_for_type(ttype)
    rate_ids = [None] + list(rate_opts)
    default_rate_id = default_rate["id"] if default_rate else None
    if f"hours_type_seen" not in st.session_state:
        st.session_state.hours_type_seen = ttype
        st.session_state.hours_rate_id = default_rate_id
        st.session_state.hours_rate_amt = float(default_rate["price"]) if default_rate else 0.0
    elif st.session_state.hours_type_seen != ttype:
        st.session_state.hours_type_seen = ttype
        st.session_state.hours_rate_id = default_rate_id
        st.session_state.hours_rate_amt = float(default_rate["price"]) if default_rate else 0.0

    c3, c4, c5 = st.columns(3)
    hrs = c3.number_input("Hours", min_value=0.0, value=1.0, step=0.1, format="%.1f")
    rate_id = c4.selectbox(
        "Rate",
        rate_ids,
        index=rate_ids.index(st.session_state.hours_rate_id) if st.session_state.hours_rate_id in rate_opts else 0,
        format_func=lambda i: "— none —" if i is None else rate_opts[i],
        key="hours_rate_id",
    )
    if rate_id:
        picked = db.get_rate(int(rate_id))
        if picked and st.session_state.get("_hours_rate_synced") != rate_id:
            st.session_state.hours_rate_amt = float(picked["price"])
            st.session_state._hours_rate_synced = rate_id
    rate_amt = c5.number_input("Rate $", min_value=0.0, step=1.0, format="%.2f", key="hours_rate_amt")
    billable = st.checkbox("Billable", value=True)

    c6, c7 = st.columns(2)
    aircraft = c6.text_input("Aircraft / device", placeholder="N12345 or AATD")
    airport = c7.text_input("Airport / location")
    notes = st.text_input("Notes / lesson summary")

    def save() -> None:
        if not student_id:
            st.warning("Choose a student")
            return
        if not hrs or float(hrs) <= 0:
            st.warning("Enter hours (or 1 for a flat/each item)")
            return
        db.save_session(
            {
                "student_id": int(student_id),
                "date": sess_date.isoformat(),
                "training_type": ttype,
                "hours": hrs,
                "aircraft": aircraft,
                "airport": airport,
                "rate_id": int(rate_id) if rate_id else None,
                "rate_amount": rate_amt or 0,
                "billable": bool(billable),
                "description": db.training_type_label(ttype),
                "notes": notes,
            }
        )
        amount = money((hrs or 0) * (rate_amt or 0))
        msg = f"Logged {fmt_hours(hrs)} hr"
        if billable:
            msg += f" · {fmt_money(amount)}"
        else:
            msg += " (not billed)"
        st.session_state.hours_flash = msg

    b1, b2 = st.columns(2)
    if b1.button("Save & log another", type="primary", use_container_width=True):
        save()
        st.rerun()
    if b2.button("Save and invoice student", use_container_width=True):
        save()
        chrome.go("invoices", invoice_new=True, invoice_id=None, invoice_student=int(student_id))

    if st.session_state.get("hours_flash"):
        st.success(st.session_state.pop("hours_flash"))

    st.markdown("**Recent lessons**")
    sessions = db.list_sessions(limit=40)
    if not sessions:
        st.caption("Nothing logged yet.")
        return
    for s in sessions:
        bill = "Billed" if s["billed"] else ("Unbilled" if s["billable"] else "Not billed")
        st.markdown(
            f"<div class='ab-card'><b>{fmt_date(s['date'])} · {s['student_name']}</b> "
            f"{chrome.chip('paid' if bill == 'Billed' else ('unpaid' if bill == 'Unbilled' else 'draft'))}<br>"
            f"{db.training_type_label(s['training_type'])} · {fmt_hours(s['hours'])} hr · "
            f"{fmt_money(s['line_amount'])}</div>",
            unsafe_allow_html=True,
        )
        if not s["billed"]:
            if st.button("Delete", key=f"del-sess-{s['id']}"):
                try:
                    db.delete_session(int(s["id"]))
                    st.rerun()
                except ValueError as err:
                    st.warning(str(err))
