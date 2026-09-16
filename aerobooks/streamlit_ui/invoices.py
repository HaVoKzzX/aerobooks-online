"""Invoice list, editor, payments, PDF."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import streamlit as st

from aerobooks import db
from aerobooks.money import fmt_date, fmt_hours, fmt_money, iso_today, money
from aerobooks.pdf_invoice import invoice_pdf_bytes
from aerobooks.streamlit_ui import chrome


def render() -> None:
    if st.session_state.get("invoice_new"):
        _new()
        return
    invoice_id = st.session_state.get("invoice_id")
    if invoice_id:
        _detail(int(invoice_id))
        return
    _list()


def _list() -> None:
    chrome.page_title("Invoices", "Create, edit, mark paid, download PDF, or print.")
    if st.button("New invoice", type="primary"):
        st.session_state.invoice_new = True
        st.session_state.invoice_id = None
        st.rerun()

    status_opts = {
        "all": "All",
        "unpaid": "Unpaid",
        "overdue": "Overdue",
        "overdue_30": "30+ days overdue",
        "paid": "Paid",
        "draft": "Drafts",
        "void": "Void",
    }
    start = st.session_state.get("invoice_filter") or "all"
    if start not in status_opts:
        start = "all"
    students = {0: "All students"}
    students.update({s["id"]: s["label"] for s in db.student_options()})
    f1, f2, f3 = st.columns(3)
    with f1:
        status = st.selectbox("Filter", list(status_opts), index=list(status_opts).index(start), format_func=lambda k: status_opts[k])
    with f2:
        student_id = st.selectbox("Student", list(students), format_func=lambda i: students[i])
    with f3:
        search = st.text_input("Search")

    invoices = db.list_invoices(
        student_id=student_id or None,
        status=status,
        search=search or "",
    )
    if not invoices:
        chrome.card_md("No invoices here yet.")
        return
    total_bal = sum(money(i["balance"]) for i in invoices if i["status"] not in ("void", "paid", "draft"))
    st.caption(f"{len(invoices)} invoices · outstanding in this view {fmt_money(total_bal)}")
    for inv in invoices:
        st.markdown(
            f"<div class='ab-card'><b>{inv['number']}</b> · {inv['student_name']} "
            f"{chrome.chip(inv.get('display_status') or inv['status'])}<br>"
            f"<span class='ab-sub'>Issued {fmt_date(inv['issue_date'])} · due {fmt_date(inv['due_date'])} · "
            f"total {fmt_money(inv['total'])} · balance {fmt_money(inv['balance'])}</span></div>",
            unsafe_allow_html=True,
        )
        if st.button("Open", key=f"inv-open-{inv['id']}", use_container_width=True):
            st.session_state.invoice_id = int(inv["id"])
            st.session_state.invoice_new = False
            st.rerun()


def _new() -> None:
    if st.button("← Invoices"):
        st.session_state.invoice_new = False
        st.session_state.pop("invoice_sessions", None)
        st.rerun()
    chrome.page_title("New invoice", "Checked unbilled lessons and extra lines become the invoice.")
    options = {s["id"]: s["label"] for s in db.student_options()}
    if not options:
        st.warning("Add a student before creating an invoice.")
        if st.button("Students"):
            chrome.go("students")
        return

    ids = list(options)
    pre = st.session_state.get("invoice_student")
    if pre not in options:
        pre = ids[0]
    settings = db.get_settings()
    terms_days = int(settings.get("payment_terms_days") or 30)

    student_id = st.selectbox("Student / customer", ids, index=ids.index(pre), format_func=lambda i: options[i])
    c1, c2 = st.columns(2)
    issue = c1.date_input("Issue date", value=date.today(), format="YYYY-MM-DD")
    due_default = issue + timedelta(days=terms_days)
    due = c2.date_input("Due date", value=due_default, format="YYYY-MM-DD")
    d1, d2 = st.columns(2)
    dtype = d1.selectbox("Discount", ["none", "percent", "amount"], format_func=lambda v: {"none": "No discount", "percent": "Percent off", "amount": "Dollar off"}[v])
    dval = d2.number_input("Discount value", min_value=0.0, value=0.0, format="%.2f")
    venmo = st.checkbox("Include Venmo QR on invoice", value=bool(settings.get("venmo_username")))
    notes = st.text_area("Notes on invoice (shown to student)")
    status = st.selectbox("Save as", ["unpaid", "draft"], format_func=lambda v: "Save as unpaid" if v == "unpaid" else "Save as draft")

    sessions = db.list_sessions(student_id=int(student_id), unbilled_only=True, limit=100)
    wanted = set(st.session_state.get("invoice_sessions") or [])
    selected: list[int] = []
    st.markdown("**Unbilled training**")
    if not sessions:
        st.caption("No unbilled hours for this student. You can still add products or extra lines below.")
    else:
        st.caption("Checked items will be added to the invoice.")
        for sess in sessions:
            default = True if not wanted else sess["id"] in wanted
            label = (
                f"{fmt_date(sess['date'])} · {db.training_type_label(sess['training_type'])} · "
                f"{fmt_hours(sess['hours'])} hr · {fmt_money(sess['line_amount'])}"
                + (f" · {sess['aircraft']}" if sess.get("aircraft") else "")
            )
            if st.checkbox(label, value=default, key=f"inv-sess-{sess['id']}"):
                selected.append(int(sess["id"]))

    if "invoice_extras" not in st.session_state:
        st.session_state.invoice_extras = []
    extras: list[dict] = st.session_state.invoice_extras
    st.markdown("**Additional products & services**")
    st.caption("Books, headsets, aircraft rental pass-through, or any custom line.")
    for i, item in enumerate(list(extras)):
        cols = st.columns([5, 1])
        cols[0].write(
            f"{item['description']} · {item['quantity']:g} {item['unit']} × {fmt_money(item['unit_price'])} = "
            f"{fmt_money(item['quantity'] * item['unit_price'])}"
        )
        if cols[1].button("Remove", key=f"drop-extra-{i}"):
            extras.pop(i)
            st.rerun()

    rates = db.list_rates(active_only=True)
    with st.expander("Add a line", expanded=True):
        rate_map = {0: "Custom"}
        rate_map.update({r["id"]: r["name"] for r in rates})
        pick = st.selectbox("From rates", list(rate_map), format_func=lambda i: rate_map[i])
        desc_default = ""
        price_default = 0.0
        unit_default = "each"
        if pick:
            r = db.get_rate(int(pick))
            if r:
                desc_default = r["name"]
                price_default = float(r["price"])
                unit_default = r["unit"]
        desc = st.text_input("Description", value=desc_default)
        q1, q2, q3 = st.columns(3)
        qty = q1.number_input("Qty", min_value=0.1, value=1.0, step=0.1, format="%.1f")
        price = q2.number_input("Price", min_value=0.0, value=price_default, format="%.2f")
        unit = q3.selectbox("Unit", ["each", "hour", "flat"], index=["each", "hour", "flat"].index(unit_default) if unit_default in ("each", "hour", "flat") else 0)
        if st.button("Add line"):
            if not (desc or "").strip():
                st.warning("Description required")
            else:
                extras.append(
                    {
                        "description": desc.strip(),
                        "quantity": float(qty or 1),
                        "unit": unit,
                        "unit_price": float(price or 0),
                        "category": "product",
                    }
                )
                st.rerun()

    if st.button("Create invoice", type="primary", use_container_width=True):
        iid = db.create_invoice(
            student_id=int(student_id),
            session_ids=selected,
            extra_items=extras,
            issue_date=issue.isoformat(),
            due_date=due.isoformat(),
            discount_type=dtype,
            discount_value=dval or 0,
            notes=notes or "",
            include_venmo=bool(venmo),
            status=status,
        )
        st.session_state.invoice_extras = []
        st.session_state.invoice_new = False
        st.session_state.pop("invoice_sessions", None)
        st.session_state.invoice_id = int(iid)
        st.rerun()


def _detail(invoice_id: int) -> None:
    inv = db.get_invoice(invoice_id)
    if not inv:
        st.warning("Invoice not found.")
        if st.button("Back"):
            st.session_state.pop("invoice_id", None)
            st.rerun()
        return

    if st.button("← Invoices"):
        st.session_state.pop("invoice_id", None)
        st.rerun()

    st.markdown(
        f'<p class="ab-h1">{inv["number"]} {chrome.chip(inv.get("display_status") or inv["status"])}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="ab-sub">{inv["student_name"]} · issued {fmt_date(inv["issue_date"])} · due {fmt_date(inv["due_date"])}</p>',
        unsafe_allow_html=True,
    )

    a1, a2, a3 = st.columns(3)
    name, data = invoice_pdf_bytes(invoice_id)
    with a1:
        st.download_button("PDF", data=data, file_name=name, mime="application/pdf", use_container_width=True)
    with a2:
        st.download_button("Print / PDF", data=data, file_name=name, mime="application/pdf", key="print-pdf", use_container_width=True)
    with a3:
        if inv["status"] != "void" and money(inv["balance"]) > 0:
            if st.button("Mark paid", type="primary", use_container_width=True):
                st.session_state.pay_dialog = "paid"
                st.rerun()

    if inv.get("is_overdue_30"):
        chrome.alert(f"<b>30-day reminder:</b> this invoice is {inv['days_overdue']} days overdue.")
        st.code(db.reminder_message(inv), language=None)

    chrome.stats_html(
        [
            ("Total", fmt_money(inv["total"])),
            ("Paid", fmt_money(inv["amount_paid"])),
            ("Balance", fmt_money(inv["balance"]), "", "warn" if money(inv["balance"]) else ""),
        ]
    )

    if inv["status"] == "void":
        chrome.alert("This invoice is void. Hours were returned to unbilled.", gold=True)
        if st.button("Delete permanently"):
            db.delete_voided_invoice(invoice_id)
            st.session_state.pop("invoice_id", None)
            st.rerun()

    st.markdown("**Line items**")
    for item in inv.get("items") or []:
        cols = st.columns([4, 1, 1] if inv["status"] != "void" else [4, 1])
        cols[0].markdown(
            f"{item['description']} · {float(item['quantity']):g} {item['unit']} × "
            f"{fmt_money(item['unit_price'])} = **{fmt_money(item['amount'])}**"
        )
        if inv["status"] != "void":
            if cols[1].button("Edit", key=f"edit-item-{item['id']}"):
                st.session_state.edit_item = dict(item)
                st.rerun()
            if cols[2].button("Delete", key=f"del-item-{item['id']}"):
                db.delete_invoice_item(item["id"])
                st.rerun()
    if inv["status"] != "void" and st.button("Add line item"):
        st.session_state.add_item = True
        st.rerun()

    st.markdown(
        f"Subtotal {fmt_money(inv['subtotal'])}  \n"
        + (f"Discount -{fmt_money(inv['discount_amount'])}  \n" if money(inv["discount_amount"]) else "")
        + (f"Tax {fmt_money(inv['tax_amount'])}  \n" if money(inv["tax_amount"]) else "")
        + f"**Total {fmt_money(inv['total'])}**  \nBalance {fmt_money(inv['balance'])}"
    )

    left, right = st.columns(2)
    with left:
        st.markdown("**Edit invoice**")
        issue = st.date_input("Issue date", value=_d(inv["issue_date"]), format="YYYY-MM-DD", key="ed-issue")
        due = st.date_input("Due date", value=_d(inv["due_date"]), format="YYYY-MM-DD", key="ed-due")
        dtype = st.selectbox(
            "Discount",
            ["none", "percent", "amount"],
            index=["none", "percent", "amount"].index(inv["discount_type"] or "none"),
            format_func=lambda v: {"none": "No discount", "percent": "Percent off", "amount": "Dollar off"}[v],
        )
        dval = st.number_input("Discount value", min_value=0.0, value=float(inv["discount_value"] or 0), format="%.2f")
        tax = st.number_input("Tax rate %", min_value=0.0, value=float(inv["tax_rate"] or 0), format="%.3f")
        venmo = st.checkbox("Include Venmo QR", value=bool(inv["include_venmo"]))
        notes = st.text_area("Notes", value=inv.get("notes") or "")
        terms = st.text_area("Terms", value=inv.get("terms") or "")
        if inv["status"] != "void":
            b1, b2 = st.columns(2)
            if b1.button("Save changes", type="primary", use_container_width=True):
                db.update_invoice_fields(
                    invoice_id,
                    {
                        "issue_date": issue.isoformat(),
                        "due_date": due.isoformat(),
                        "discount_type": dtype,
                        "discount_value": dval or 0,
                        "tax_rate": tax or 0,
                        "include_venmo": venmo,
                        "notes": notes,
                        "terms": terms,
                    },
                )
                st.success("Invoice updated")
                st.rerun()
            if b2.button("Void invoice", use_container_width=True):
                db.void_invoice(invoice_id)
                st.rerun()
    with right:
        st.markdown("**Payments**")
        payments = inv.get("payments") or []
        if not payments:
            st.caption("No payments recorded.")
        for p in payments:
            st.write(
                f"{fmt_date(p['date'])} · {fmt_money(p['amount'])} · {p['method']}"
                + (f" · {p['reference']}" if p.get("reference") else "")
            )
            if st.button("Delete payment", key=f"del-pay-{p['id']}"):
                db.delete_payment(p["id"])
                st.rerun()
        if inv["status"] != "void" and money(inv["balance"]) > 0:
            if st.button("Record payment", type="primary"):
                st.session_state.pay_dialog = "record"
                st.rerun()

    if st.session_state.get("pay_dialog") == "paid":
        _mark_paid_dialog(invoice_id)
    elif st.session_state.get("pay_dialog") == "record":
        _pay_dialog(invoice_id, inv)
    if st.session_state.get("add_item"):
        _add_item_dialog(invoice_id)
    if st.session_state.get("edit_item"):
        _edit_item_dialog(invoice_id, st.session_state.edit_item)


@st.dialog("Mark invoice paid")
def _mark_paid_dialog(invoice_id: int) -> None:
    method = st.selectbox("Method", db.PAYMENT_METHODS, index=0)
    when = st.date_input("Date", value=date.today(), format="YYYY-MM-DD")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("pay_dialog", None)
        st.rerun()
    if c2.button("Mark paid", type="primary"):
        db.mark_invoice_paid(invoice_id, method, when.isoformat())
        st.session_state.pop("pay_dialog", None)
        st.rerun()


@st.dialog("Record payment")
def _pay_dialog(invoice_id: int, inv: dict) -> None:
    amount = st.number_input("Amount", min_value=0.01, value=float(money(inv["balance"])), format="%.2f")
    method = st.selectbox("Method", db.PAYMENT_METHODS)
    when = st.date_input("Date", value=date.today(), format="YYYY-MM-DD")
    ref = st.text_input("Reference (check #, last 4)")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("pay_dialog", None)
        st.rerun()
    if c2.button("Save payment", type="primary"):
        db.add_payment(invoice_id, amount, method, when.isoformat(), ref or "")
        st.session_state.pop("pay_dialog", None)
        st.rerun()


@st.dialog("Add line item")
def _add_item_dialog(invoice_id: int) -> None:
    rates = db.list_rates(active_only=True)
    rate_map = {0: "Custom"}
    rate_map.update({r["id"]: f"{r['name']} ({fmt_money(r['price'])}/{r['unit']})" for r in rates})
    pick = st.selectbox("From rates", list(rate_map), format_func=lambda i: rate_map[i])
    desc = st.text_input("Description")
    qty = st.number_input("Quantity", min_value=0.1, value=1.0, format="%.1f")
    unit = st.selectbox("Unit", ["hour", "each", "flat"])
    price = st.number_input("Unit price", min_value=0.0, value=0.0, format="%.2f")
    if pick:
        r = db.get_rate(int(pick))
        if r and not desc:
            desc = r["name"]
            price = float(r["price"])
            unit = r["unit"]
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("add_item", None)
        st.rerun()
    if c2.button("Add", type="primary"):
        db.add_invoice_item(
            invoice_id,
            {
                "rate_id": int(pick) if pick else None,
                "description": desc or "Item",
                "quantity": qty or 1,
                "unit": unit,
                "unit_price": price or 0,
                "category": "service",
            },
        )
        db.recalc_invoice(invoice_id)
        st.session_state.pop("add_item", None)
        st.rerun()


@st.dialog("Edit line")
def _edit_item_dialog(invoice_id: int, item: dict) -> None:
    desc = st.text_input("Description", value=item["description"])
    qty = st.number_input("Quantity", min_value=0.1, value=float(item["quantity"]), format="%.1f")
    unit = st.selectbox("Unit", ["hour", "each", "flat"], index=["hour", "each", "flat"].index(item.get("unit") or "each") if (item.get("unit") or "each") in ("hour", "each", "flat") else 1)
    price = st.number_input("Unit price", min_value=0.0, value=float(item["unit_price"]), format="%.2f")
    c1, c2 = st.columns(2)
    if c1.button("Cancel"):
        st.session_state.pop("edit_item", None)
        st.rerun()
    if c2.button("Save", type="primary"):
        db.update_invoice_item(
            item["id"],
            {
                "description": desc,
                "quantity": qty,
                "unit": unit,
                "unit_price": price,
                "category": item.get("category") or "service",
            },
        )
        st.session_state.pop("edit_item", None)
        st.rerun()


def _d(value) -> date:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return date.today()
