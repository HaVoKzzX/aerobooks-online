"""Invoice list, editor, payments, PDF, and print."""

from __future__ import annotations

from nicegui import ui, app
from fastapi import HTTPException
from fastapi.responses import FileResponse

from aerobooks import auth, db, paths
from aerobooks.money import fmt_date, fmt_hours, fmt_money, iso_today, money
from aerobooks.pdf_invoice import build_invoice_pdf
from aerobooks.theme import event_row, frame, page_title, status_chip


def register() -> None:
    @ui.page("/invoices")
    def list_page(status: str | None = None):
        with frame("Invoices", "/invoices") as user:
            if not user:
                return
            render_list(initial_status=status)

    @ui.page("/invoices/new")
    def new_page(student: int | None = None, sessions: str | None = None):
        ids: list[int] = []
        if sessions:
            for part in str(sessions).split(","):
                part = part.strip()
                if part.isdigit():
                    ids.append(int(part))
        with frame("New invoice", "/invoices") as user:
            if not user:
                return
            render_new(preselect_student=student, session_ids=ids or None)

    @ui.page("/invoices/{invoice_id}")
    def detail_page(invoice_id: int):
        with frame("Invoice", "/invoices") as user:
            if not user:
                return
            render_detail(invoice_id)

    @app.get("/api/invoices/{invoice_id}/pdf")
    def pdf_api(invoice_id: int):
        user = auth.current_user()
        if not user or user.get("role") == "admin" or not user.get("tenant_id"):
            raise HTTPException(status_code=401, detail="Sign in required")
        paths.bind_tenant(int(user["tenant_id"]))
        db.init_db()
        inv = db.get_invoice(invoice_id)
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        from aerobooks.store import decrypt_to_temp

        path = decrypt_to_temp(build_invoice_pdf(invoice_id))
        return FileResponse(path, filename=path.name, media_type="application/pdf")


def render_list(initial_status: str | None = None) -> None:
    allowed = {"all", "unpaid", "overdue", "overdue_30", "paid", "draft", "void"}
    start = initial_status if initial_status in allowed else "all"
    state = {"status": start, "search": "", "student": None}

    actions = page_title("Invoices", "Create, edit, mark paid, download PDF, or print.")
    with actions:
        ui.button("New invoice", icon="add", on_click=lambda: ui.navigate.to("/invoices/new")).classes("ab-primary")

    students = {0: "All students"}
    students.update({s["id"]: s["label"] for s in db.student_options()})

    @ui.refreshable
    def body():
        invoices = db.list_invoices(
            student_id=state["student"] or None,
            status=state["status"],
            search=state["search"],
        )
        if not invoices:
            with ui.card().classes("ab-card p-6"):
                ui.label("No invoices here yet.")
            return
        columns = [
            {"name": "number", "label": "Invoice", "field": "number"},
            {"name": "student", "label": "Student / customer", "field": "student_name", "align": "left"},
            {"name": "issue", "label": "Issued", "field": "issue_label"},
            {"name": "due", "label": "Due", "field": "due_label"},
            {"name": "total", "label": "Total", "field": "total_label"},
            {"name": "balance", "label": "Balance", "field": "balance_label"},
            {"name": "status", "label": "Status", "field": "display_status"},
            {"name": "id", "label": "id", "field": "id"},
        ]
        rows = [
            {
                "id": i["id"],
                "number": i["number"],
                "student_name": i["student_name"],
                "issue_label": fmt_date(i["issue_date"]),
                "due_label": fmt_date(i["due_date"]),
                "total_label": fmt_money(i["total"]),
                "balance_label": fmt_money(i["balance"]),
                "display_status": i.get("display_status") or i["status"],
            }
            for i in invoices
        ]
        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full ab-card")
        table.add_slot(
            "body-cell-status",
            """
            <q-td :props="props">
              <q-badge :color="props.value === 'paid' ? 'positive' : (props.value === 'overdue' ? 'negative' : (props.value === 'draft' ? 'grey' : 'warning'))" outline>
                {{ props.value }}
              </q-badge>
            </q-td>
            """,
        )
        table.on("rowClick", lambda e: ui.navigate.to(f"/invoices/{event_row(e)['id']}"))

        total_bal = sum(money(i["balance"]) for i in invoices if i["status"] not in ("void", "paid", "draft"))
        ui.label(f"{len(invoices)} invoices  ·  outstanding in this view {fmt_money(total_bal)}").classes(
            "text-sm text-gray-600 mt-2"
        )

    with ui.row().classes("items-center gap-3 mb-3 w-full flex-wrap"):
        ui.select(
            {
                "all": "All",
                "unpaid": "Unpaid",
                "overdue": "Overdue",
                "overdue_30": "30+ days overdue",
                "paid": "Paid",
                "draft": "Drafts",
                "void": "Void",
            },
            value=start,
            label="Filter",
            on_change=lambda e: _set(state, "status", e.value, body),
        ).props("outlined dense").classes("w-52")
        ui.select(
            students,
            value=0,
            label="Student",
            on_change=lambda e: _set(state, "student", None if not e.value else e.value, body),
        ).props("outlined dense").classes("w-64")
        ui.input("Search", on_change=lambda e: _set(state, "search", e.value, body)).props(
            "outlined dense debounce=250 clearable"
        ).classes("w-56")

    body()


def _set(state, key, value, refresh) -> None:
    state[key] = value
    refresh.refresh()


def render_new(preselect_student: int | None = None, session_ids: list[int] | None = None) -> None:
    options = {s["id"]: s["label"] for s in db.student_options()}
    if not options:
        ui.label("Add a student before creating an invoice.")
        ui.button("Students", on_click=lambda: ui.navigate.to("/students"))
        return

    pre_id = preselect_student if preselect_student in options else next(iter(options))
    settings = db.get_settings()
    terms_days = int(settings.get("payment_terms_days") or 30)

    selected_sessions: set[int] = set()
    extras: list[dict] = []

    ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/invoices")).props("flat round")
    ui.label("New invoice").classes("ab-h1 mb-3")

    with ui.card().classes("ab-card p-5 w-full mb-3"):
        with ui.row().classes("w-full gap-3"):
            student = ui.select(options, label="Student / customer", value=pre_id).classes("flex-1").props(
                "outlined dense"
            )
            issue = ui.input("Issue date", value=iso_today()).props("outlined dense type=date").classes("w-44")
            due = ui.input("Due date").props("outlined dense type=date").classes("w-44")

        def set_due():
            from datetime import datetime, timedelta

            try:
                d = datetime.strptime(issue.value, "%Y-%m-%d") + timedelta(days=terms_days)
                due.value = d.strftime("%Y-%m-%d")
            except Exception:
                due.value = iso_today()

        set_due()
        issue.on("update:model-value", lambda _: set_due())

        with ui.row().classes("w-full gap-3"):
            dtype = ui.select(
                {"none": "No discount", "percent": "Percent off", "amount": "Dollar off"},
                value="none",
                label="Discount",
            ).classes("w-48").props("outlined dense")
            dval = ui.number("Discount value", value=0, format="%.2f", min=0).classes("w-40").props("outlined dense")
            venmo = ui.checkbox("Include Venmo QR on invoice", value=bool(settings.get("venmo_username"))).classes(
                "mt-4"
            )
        notes = ui.textarea("Notes on invoice (shown to student)").classes("w-full").props("outlined dense autogrow")
        status = ui.select({"draft": "Save as draft", "unpaid": "Save as unpaid"}, value="unpaid", label="Save as").props(
            "outlined dense"
        ).classes("w-56")

    @ui.refreshable
    def unbilled_block():
        selected_sessions.clear()
        sessions = db.list_sessions(student_id=int(student.value), unbilled_only=True, limit=100)
        with ui.card().classes("ab-card p-5 w-full mb-3"):
            ui.label("Unbilled training").classes("font-semibold")
            if not sessions:
                ui.label("No unbilled hours for this student. You can still add products or extra lines below.").classes(
                    "text-sm text-gray-600"
                )
                return
            ui.label("Checked items will be added to the invoice.").classes("text-sm text-gray-600 mb-2")
            wanted = set(session_ids) if session_ids else None
            for sess in sessions:
                checked = True if wanted is None else sess["id"] in wanted
                if checked:
                    selected_sessions.add(sess["id"])
                ui.checkbox(
                    text=(
                        f"{fmt_date(sess['date'])}  ·  {db.training_type_label(sess['training_type'])}  ·  "
                        f"{fmt_hours(sess['hours'])} hr  ·  {fmt_money(sess['line_amount'])}"
                        + (f"  ·  {sess['aircraft']}" if sess.get("aircraft") else "")
                    ),
                    value=checked,
                    on_change=lambda e, sid=sess["id"]: (
                        selected_sessions.add(sid) if e.value else selected_sessions.discard(sid)
                    ),
                )

    student.on("update:model-value", lambda _: unbilled_block.refresh())
    unbilled_block()

    rates = db.list_rates(active_only=True)

    @ui.refreshable
    def extras_block():
        with ui.card().classes("ab-card p-5 w-full mb-3"):
            ui.label("Additional products & services").classes("font-semibold")
            ui.label("Books, headsets, aircraft rental pass-through, or any custom line.").classes(
                "text-sm text-gray-600 mb-2"
            )
            if extras:
                for i, item in enumerate(extras):
                    with ui.row().classes("items-center w-full gap-2"):
                        ui.label(
                            f"{item['description']}  ·  {item['quantity']:g} {item['unit']} × {fmt_money(item['unit_price'])} = {fmt_money(item['quantity'] * item['unit_price'])}"
                        ).classes("flex-1 text-sm")
                        ui.button(icon="delete", on_click=lambda idx=i: _drop_extra(idx)).props("flat dense round")
            with ui.row().classes("w-full gap-2 items-end"):
                desc = ui.input("Description").classes("flex-1").props("outlined dense")
                qty = ui.number("Qty", value=1, format="%.1f", min=0.1, step=0.1).classes("w-24").props("outlined dense")
                price = ui.number("Price", value=0, format="%.2f", min=0).classes("w-28").props("outlined dense")
                unit = ui.select(["each", "hour", "flat"], value="each", label="Unit").classes("w-28").props(
                    "outlined dense"
                )
                rate_pick = ui.select(
                    {r["id"]: r["name"] for r in rates},
                    label="From rates",
                ).props("outlined dense clearable").classes("w-56")

                def from_rate():
                    if not rate_pick.value:
                        return
                    r = db.get_rate(int(rate_pick.value))
                    if r:
                        desc.value = r["name"]
                        price.value = r["price"]
                        unit.value = r["unit"]

                rate_pick.on("update:model-value", lambda _: from_rate())

                def add_extra():
                    if not (desc.value or "").strip():
                        ui.notify("Description required", type="warning")
                        return
                    extras.append(
                        {
                            "description": desc.value.strip(),
                            "quantity": float(qty.value or 1),
                            "unit": unit.value,
                            "unit_price": float(price.value or 0),
                            "category": "product",
                        }
                    )
                    extras_block.refresh()

                ui.button("Add line", on_click=add_extra).props("outline")

    def _drop_extra(idx: int):
        extras.pop(idx)
        extras_block.refresh()

    extras_block()

    def create():
        if not student.value:
            ui.notify("Choose a student", type="warning")
            return
        iid = db.create_invoice(
            student_id=int(student.value),
            session_ids=list(selected_sessions),
            extra_items=extras,
            issue_date=issue.value,
            due_date=due.value,
            discount_type=dtype.value,
            discount_value=dval.value or 0,
            notes=notes.value or "",
            include_venmo=bool(venmo.value),
            status=status.value,
        )
        ui.notify(f"Invoice created")
        ui.navigate.to(f"/invoices/{iid}")

    ui.button("Create invoice", icon="check", on_click=create).classes("ab-primary")


def render_detail(invoice_id: int) -> None:
    inv = db.get_invoice(invoice_id)
    if not inv:
        ui.label("Invoice not found.")
        return

    with ui.row().classes("items-center justify-between w-full mb-3"):
        with ui.row().classes("items-center gap-3"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/invoices")).props("flat round")
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(inv["number"]).classes("ab-h1")
                    status_chip(inv.get("display_status") or inv["status"])
                ui.label(f"{inv['student_name']}  ·  issued {fmt_date(inv['issue_date'])}  ·  due {fmt_date(inv['due_date'])}").classes(
                    "ab-sub"
                )
        with ui.row().classes("gap-2"):
            ui.button("PDF", icon="picture_as_pdf", on_click=lambda: _download_pdf(invoice_id)).classes("ab-primary")
            ui.button("Print", icon="print", on_click=lambda: _print_pdf(invoice_id)).props("outline")
            if inv["status"] != "void" and money(inv["balance"]) > 0:
                ui.button("Mark paid", icon="paid", on_click=lambda: _paid_dialog(invoice_id)).classes("ab-gold")

    if inv.get("is_overdue_30"):
        with ui.card().classes("ab-alert w-full p-3 mb-3"):
            ui.label(f"30-day reminder: this invoice is {inv['days_overdue']} days overdue.").classes("font-medium")
            ui.button("Copy reminder message", on_click=lambda: _copy_reminder(inv)).props("flat dense")

    with ui.row().classes("gap-3 w-full mb-3 flex-wrap"):
        with ui.card().classes("ab-card p-4"):
            ui.label("Total").classes("ab-stat-label")
            ui.label(fmt_money(inv["total"])).classes("ab-stat-value")
        with ui.card().classes("ab-card p-4"):
            ui.label("Paid").classes("ab-stat-label")
            ui.label(fmt_money(inv["amount_paid"])).classes("ab-stat-value")
        with ui.card().classes("ab-card p-4" + (" warn" if money(inv["balance"]) else "")):
            ui.label("Balance").classes("ab-stat-label")
            ui.label(fmt_money(inv["balance"])).classes("ab-stat-value")

    if inv["status"] == "void":
        with ui.card().classes("ab-alert-gold w-full p-3 mb-3"):
            ui.label("This invoice is void. Hours were returned to unbilled.").classes("text-sm")
            ui.button(
                "Delete permanently",
                icon="delete_forever",
                on_click=lambda: _confirm_delete_voided(invoice_id, inv["number"]),
            ).props("flat color=negative dense")

    with ui.card().classes("ab-card p-5 w-full mb-3"):
        ui.label("Line items").classes("font-semibold mb-2")
        for item in inv.get("items") or []:
            with ui.row().classes("items-center w-full gap-2 py-1 border-b"):
                ui.label(item["description"]).classes("flex-1 text-sm")
                ui.label(f"{float(item['quantity']):g} {item['unit']}").classes("w-24 text-sm text-right")
                ui.label(fmt_money(item["unit_price"])).classes("w-24 text-sm text-right")
                ui.label(fmt_money(item["amount"])).classes("w-24 text-sm text-right font-medium")
                if inv["status"] != "void":
                    ui.button(icon="edit", on_click=lambda it=item: _edit_item_dialog(invoice_id, it)).props(
                        "flat dense round"
                    )
                    ui.button(icon="delete", on_click=lambda it=item: _delete_item(invoice_id, it["id"])).props(
                        "flat dense round"
                    )
        if inv["status"] != "void":
            ui.button("Add line item", icon="add", on_click=lambda: _add_item_dialog(invoice_id)).props("outline").classes(
                "mt-2"
            )

        with ui.column().classes("items-end w-full mt-3 gap-1"):
            ui.label(f"Subtotal  {fmt_money(inv['subtotal'])}").classes("text-sm")
            if money(inv["discount_amount"]):
                ui.label(f"Discount  -{fmt_money(inv['discount_amount'])}").classes("text-sm")
            if money(inv["tax_amount"]):
                ui.label(f"Tax  {fmt_money(inv['tax_amount'])}").classes("text-sm")
            ui.label(f"Total  {fmt_money(inv['total'])}").classes("text-lg font-bold")
            ui.label(f"Balance  {fmt_money(inv['balance'])}").classes("text-sm")

    with ui.row().classes("gap-4 w-full items-start"):
        with ui.card().classes("ab-card p-5 flex-1"):
            ui.label("Edit invoice").classes("font-semibold mb-2")
            issue = ui.input("Issue date", value=inv["issue_date"]).props("outlined dense type=date")
            due = ui.input("Due date", value=inv["due_date"]).props("outlined dense type=date")
            dtype = ui.select(
                {"none": "No discount", "percent": "Percent off", "amount": "Dollar off"},
                value=inv["discount_type"] or "none",
                label="Discount",
            ).props("outlined dense")
            dval = ui.number("Discount value", value=inv["discount_value"] or 0, format="%.2f", min=0).props(
                "outlined dense"
            )
            tax = ui.number("Tax rate %", value=inv["tax_rate"] or 0, format="%.3f", min=0).props("outlined dense")
            venmo = ui.checkbox("Include Venmo QR", value=bool(inv["include_venmo"]))
            notes = ui.textarea("Notes", value=inv.get("notes") or "").props("outlined dense autogrow")
            terms = ui.textarea("Terms", value=inv.get("terms") or "").props("outlined dense autogrow")

            def save_fields():
                db.update_invoice_fields(
                    invoice_id,
                    {
                        "issue_date": issue.value,
                        "due_date": due.value,
                        "discount_type": dtype.value,
                        "discount_value": dval.value or 0,
                        "tax_rate": tax.value or 0,
                        "include_venmo": venmo.value,
                        "notes": notes.value,
                        "terms": terms.value,
                    },
                )
                ui.notify("Invoice updated")
                ui.navigate.reload()

            with ui.row().classes("gap-2 mt-2"):
                if inv["status"] != "void":
                    ui.button("Save changes", on_click=save_fields).classes("ab-primary")
                    ui.button("Void invoice", on_click=lambda: _void(invoice_id)).props("flat color=negative")
                else:
                    ui.button(
                        "Delete permanently",
                        icon="delete_forever",
                        on_click=lambda: _confirm_delete_voided(invoice_id, inv["number"]),
                    ).props("flat color=negative")

        with ui.card().classes("ab-card p-5 flex-1"):
            ui.label("Payments").classes("font-semibold mb-2")
            payments = inv.get("payments") or []
            if not payments:
                ui.label("No payments recorded.").classes("text-sm text-gray-600")
            for p in payments:
                with ui.row().classes("items-center w-full"):
                    ui.label(
                        f"{fmt_date(p['date'])}  ·  {fmt_money(p['amount'])}  ·  {p['method']}"
                        + (f"  ·  {p['reference']}" if p.get("reference") else "")
                    ).classes("flex-1 text-sm")
                    ui.button(icon="delete", on_click=lambda pid=p["id"]: _del_pay(invoice_id, pid)).props(
                        "flat dense round"
                    )
            if inv["status"] != "void" and money(inv["balance"]) > 0:
                ui.button("Record payment", icon="attach_money", on_click=lambda: _pay_dialog(invoice_id, inv)).classes(
                    "ab-gold mt-2"
                )


def _download_pdf(invoice_id: int) -> None:
    from aerobooks.store import decrypt_to_temp

    path = build_invoice_pdf(invoice_id)
    ui.download.file(decrypt_to_temp(path))


def _print_pdf(invoice_id: int) -> None:
    from aerobooks.store import decrypt_to_temp

    path = build_invoice_pdf(invoice_id)
    ui.download.file(decrypt_to_temp(path))
    ui.notify("PDF downloaded — open it and print, or use your browser print dialog.")


def _copy_reminder(inv: dict) -> None:
    try:
        ui.clipboard.write(db.reminder_message(inv))
        ui.notify("Reminder copied")
    except Exception:
        ui.notify(db.reminder_message(inv), timeout=8000)


def _paid_dialog(invoice_id: int) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-96"):
        ui.label("Mark invoice paid").classes("text-lg font-semibold")
        method = ui.select(db.PAYMENT_METHODS, value="Venmo", label="Method").props("outlined dense")
        when = ui.input("Date", value=iso_today()).props("outlined dense type=date")

        def go():
            db.mark_invoice_paid(invoice_id, method.value, when.value)
            d.close()
            ui.notify("Marked paid")
            ui.navigate.reload()

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Mark paid", on_click=go).classes("ab-gold")
    d.open()


def _pay_dialog(invoice_id: int, inv: dict) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-96"):
        ui.label("Record payment").classes("text-lg font-semibold")
        amount = ui.number("Amount", value=money(inv["balance"]), format="%.2f", min=0.01).props("outlined dense")
        method = ui.select(db.PAYMENT_METHODS, value="Venmo", label="Method").props("outlined dense")
        when = ui.input("Date", value=iso_today()).props("outlined dense type=date")
        ref = ui.input("Reference (check #, last 4)").props("outlined dense")

        def go():
            db.add_payment(invoice_id, amount.value, method.value, when.value, ref.value or "")
            d.close()
            ui.notify("Payment saved")
            ui.navigate.reload()

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Save payment", on_click=go).classes("ab-primary")
    d.open()


def _add_item_dialog(invoice_id: int) -> None:
    rates = db.list_rates(active_only=True)
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[560px]"):
        ui.label("Add line item").classes("text-lg font-semibold")
        rate_pick = ui.select({r["id"]: f"{r['name']} ({fmt_money(r['price'])}/{r['unit']})" for r in rates}, label="From rates").props(
            "outlined dense clearable"
        )
        desc = ui.input("Description").props("outlined dense")
        qty = ui.number("Quantity", value=1, format="%.1f", min=0.1).props("outlined dense")
        unit = ui.select(["hour", "each", "flat"], value="each", label="Unit").props("outlined dense")
        price = ui.number("Unit price", value=0, format="%.2f").props("outlined dense")

        def from_rate():
            if not rate_pick.value:
                return
            r = db.get_rate(int(rate_pick.value))
            if r:
                desc.value = r["name"]
                price.value = r["price"]
                unit.value = r["unit"]

        rate_pick.on("update:model-value", lambda _: from_rate())

        def go():
            db.add_invoice_item(
                invoice_id,
                {
                    "rate_id": int(rate_pick.value) if rate_pick.value else None,
                    "description": desc.value or "Item",
                    "quantity": qty.value or 1,
                    "unit": unit.value,
                    "unit_price": price.value or 0,
                    "category": "service",
                },
            )
            db.recalc_invoice(invoice_id)
            d.close()
            ui.navigate.reload()

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Add", on_click=go).classes("ab-primary")
    d.open()


def _edit_item_dialog(invoice_id: int, item: dict) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[520px]"):
        ui.label("Edit line").classes("text-lg font-semibold")
        desc = ui.input("Description", value=item["description"]).props("outlined dense")
        qty = ui.number("Quantity", value=item["quantity"], format="%.1f", min=0.1).props("outlined dense")
        unit = ui.select(["hour", "each", "flat"], value=item.get("unit") or "each", label="Unit").props("outlined dense")
        price = ui.number("Unit price", value=item["unit_price"], format="%.2f").props("outlined dense")

        def go():
            db.update_invoice_item(
                item["id"],
                {
                    "description": desc.value,
                    "quantity": qty.value,
                    "unit": unit.value,
                    "unit_price": price.value,
                    "category": item.get("category") or "service",
                },
            )
            d.close()
            ui.navigate.reload()

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Save", on_click=go).classes("ab-primary")
    d.open()


def _delete_item(invoice_id: int, item_id: int) -> None:
    db.delete_invoice_item(item_id)
    ui.notify("Line removed")
    ui.navigate.reload()


def _del_pay(invoice_id: int, payment_id: int) -> None:
    db.delete_payment(payment_id)
    ui.navigate.reload()


def _void(invoice_id: int) -> None:
    db.void_invoice(invoice_id)
    ui.notify("Invoice voided")
    ui.navigate.reload()


def _confirm_delete_voided(invoice_id: int, number: str) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[480px]"):
        ui.label(f"Delete {number}?").classes("text-lg font-semibold")
        ui.label(
            "This permanently removes the voided invoice. It cannot be undone. "
            "Training hours stay in the log as unbilled."
        ).classes("text-sm mt-2")

        def go():
            try:
                deleted = db.delete_voided_invoice(invoice_id)
                d.close()
                ui.notify(f"{deleted} deleted")
                ui.navigate.to("/invoices")
            except Exception as err:
                ui.notify(str(err), type="negative")

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Delete permanently", on_click=go).props("color=negative unelevated")
    d.open()
