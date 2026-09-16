"""Monthly training-related expenditures."""

from datetime import date

from nicegui import ui

from aerobooks import db
from aerobooks.money import fmt_date, fmt_money, iso_today, money
from aerobooks.theme import event_row, frame, page_title, stat_card


def register() -> None:
    @ui.page("/expenses")
    def page():
        with frame("Expenses", "/expenses") as user:
            if not user:
                return
            render()


def render() -> None:
    today = date.today()
    state = {"year": today.year, "month": today.month, "category": "all"}

    actions = page_title("Expenses", "Hangar, fuel, charts, insurance — anything you spend to instruct.")
    with actions:
        ui.button("Add expense", icon="add", on_click=lambda: expense_dialog(on_save=body.refresh)).classes("ab-primary")

    cats = ["all"] + db.EXPENSE_CATEGORIES
    years = {y: str(y) for y in range(today.year, today.year - 6, -1)}
    months = {m: date(2000, m, 1).strftime("%B") for m in range(1, 13)}

    @ui.refreshable
    def body():
        rows = db.list_expenses(year=state["year"], month=state["month"], category=state["category"])
        total = money(sum(r["amount"] for r in rows))
        reimbursable = money(sum(r["amount"] for r in rows if r.get("reimbursable")))
        with ui.row().classes("gap-3 w-full mb-3"):
            stat_card("This period", fmt_money(total), f"{len(rows)} entries")
            stat_card("Marked reimbursable", fmt_money(reimbursable))
        if not rows:
            ui.label("No expenses in this period.").classes("text-sm text-gray-600")
            return
        columns = [
            {"name": "date", "label": "Date", "field": "date_label"},
            {"name": "category", "label": "Category", "field": "category", "align": "left"},
            {"name": "desc", "label": "Description", "field": "description", "align": "left"},
            {"name": "vendor", "label": "Vendor", "field": "vendor"},
            {"name": "student", "label": "Student", "field": "student_name"},
            {"name": "amount", "label": "Amount", "field": "amount_label"},
            {"name": "id", "label": "id", "field": "id"},
        ]
        table_rows = [
            {
                "id": r["id"],
                "date_label": fmt_date(r["date"]),
                "category": r["category"],
                "description": r.get("description") or "",
                "vendor": r.get("vendor") or "",
                "student_name": r.get("student_name") or "",
                "amount_label": fmt_money(r["amount"]),
            }
            for r in rows
        ]
        table = ui.table(columns=columns, rows=table_rows, row_key="id").classes("w-full ab-card")
        table.add_slot(
            "body-cell-id",
            """
            <q-td :props="props">
              <q-btn flat dense icon="delete" size="sm" @click.stop="$parent.$emit('del', props.row)" />
            </q-td>
            """,
        )

        def on_del(e):
            row = event_row(e)
            db.delete_expense(int(row["id"]))
            ui.notify("Deleted")
            body.refresh()

        table.on("del", on_del)

    with ui.row().classes("gap-3 mb-3"):
        ui.select(
            years, value=today.year, label="Year", on_change=lambda e: _set(state, "year", int(e.value), body)
        ).props("outlined dense").classes("w-32")
        ui.select(
            months, value=today.month, label="Month", on_change=lambda e: _set(state, "month", int(e.value), body)
        ).props("outlined dense").classes("w-40")
        ui.select(
            {c: "All categories" if c == "all" else c for c in cats},
            value="all",
            label="Category",
            on_change=lambda e: _set(state, "category", e.value, body),
        ).props("outlined dense").classes("w-64")

    body()


def _set(state, key, value, refresh) -> None:
    state[key] = value
    refresh.refresh()


def expense_dialog(expense: dict | None = None, on_save=None) -> None:
    data = dict(expense or {})
    students = {None: "— none —"}
    students.update({s["id"]: s["label"] for s in db.student_options()})
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[560px]"):
        ui.label("Add expense").classes("text-lg font-semibold")
        when = ui.input("Date", value=data.get("date") or iso_today()).props("outlined dense type=date")
        cat = ui.select(db.EXPENSE_CATEGORIES, value=data.get("category") or "Fuel", label="Category").props(
            "outlined dense"
        )
        amount = ui.number("Amount", value=data.get("amount") or 0, format="%.2f", min=0).props("outlined dense")
        desc = ui.input("Description", value=data.get("description") or "").props("outlined dense")
        vendor = ui.input("Vendor", value=data.get("vendor") or "").props("outlined dense")
        student = ui.select(students, value=data.get("student_id"), label="Related student (optional)").props(
            "outlined dense"
        )
        reimb = ui.checkbox("Reimbursable / pass-through", value=bool(data.get("reimbursable")))
        notes = ui.input("Notes", value=data.get("notes") or "").props("outlined dense")

        def go():
            db.save_expense(
                {
                    "id": data.get("id"),
                    "date": when.value,
                    "category": cat.value,
                    "amount": amount.value,
                    "description": desc.value,
                    "vendor": vendor.value,
                    "student_id": student.value,
                    "reimbursable": reimb.value,
                    "notes": notes.value,
                }
            )
            d.close()
            ui.notify("Expense saved")
            if on_save:
                on_save()

        with ui.row().classes("justify-end w-full gap-2"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Save", on_click=go).classes("ab-primary")
    d.open()
