"""Monthly training-related expenditures."""

from __future__ import annotations

from datetime import date

import streamlit as st

from aerobooks import db
from aerobooks.money import fmt_date, fmt_money, iso_today, money
from aerobooks.streamlit_ui import chrome


def render() -> None:
    today = date.today()
    chrome.page_title("Expenses", "Hangar, fuel, charts, insurance — anything you spend to instruct.")
    if st.button("Add expense", type="primary"):
        st.session_state.expense_dialog = True
        st.rerun()

    years = list(range(today.year, today.year - 6, -1))
    months = {m: date(2000, m, 1).strftime("%B") for m in range(1, 13)}
    cats = ["all"] + db.EXPENSE_CATEGORIES
    c1, c2, c3 = st.columns(3)
    year = c1.selectbox("Year", years)
    month = c2.selectbox("Month", list(months), index=today.month - 1, format_func=lambda m: months[m])
    category = c3.selectbox("Category", cats, format_func=lambda c: "All categories" if c == "all" else c)

    rows = db.list_expenses(year=int(year), month=int(month), category=category)
    total = money(sum(r["amount"] for r in rows))
    reimbursable = money(sum(r["amount"] for r in rows if r.get("reimbursable")))
    chrome.stats_html(
        [
            ("This period", fmt_money(total), f"{len(rows)} entries"),
            ("Marked reimbursable", fmt_money(reimbursable)),
        ]
    )
    if not rows:
        st.caption("No expenses in this period.")
    else:
        for r in rows:
            st.markdown(
                f"<div class='ab-card'><b>{fmt_date(r['date'])} · {fmt_money(r['amount'])}</b> · {r['category']}<br>"
                f"<span class='ab-sub'>{r.get('description') or ''} {r.get('vendor') or ''} {r.get('student_name') or ''}</span></div>",
                unsafe_allow_html=True,
            )
            if st.button("Delete", key=f"del-exp-{r['id']}"):
                db.delete_expense(int(r["id"]))
                st.rerun()

    if st.session_state.get("expense_dialog"):
        _expense_dialog()


@st.dialog("Add expense")
def _expense_dialog() -> None:
    students = {0: "— none —"}
    students.update({s["id"]: s["label"] for s in db.student_options()})
    when = st.date_input("Date", value=date.today(), format="YYYY-MM-DD")
    cat = st.selectbox("Category", db.EXPENSE_CATEGORIES)
    amount = st.number_input("Amount", min_value=0.0, value=0.0, format="%.2f")
    desc = st.text_input("Description")
    vendor = st.text_input("Vendor")
    student = st.selectbox("Related student (optional)", list(students), format_func=lambda i: students[i])
    reimb = st.checkbox("Reimbursable / pass-through")
    notes = st.text_input("Notes")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("expense_dialog", None)
        st.rerun()
    if c2.button("Save", type="primary"):
        db.save_expense(
            {
                "date": when.isoformat(),
                "category": cat,
                "amount": amount,
                "description": desc,
                "vendor": vendor,
                "student_id": student or None,
                "reimbursable": reimb,
                "notes": notes,
            }
        )
        st.session_state.pop("expense_dialog", None)
        st.rerun()
