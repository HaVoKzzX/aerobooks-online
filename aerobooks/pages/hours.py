"""Log flight, ground, instrument, simulator, and other training hours."""

from nicegui import ui

from aerobooks import db
from aerobooks.money import fmt_date, fmt_hours, fmt_money, iso_today, money
from aerobooks.theme import event_row, frame, page_title


def register() -> None:
    @ui.page("/hours")
    def page(student: int | None = None):
        with frame("Log Hours", "/hours") as user:
            if not user:
                return
            render(preselect_student=student)


def render(preselect_student: int | None = None) -> None:
    page_title("Log hours", "Record a lesson. Billable time waits on the invoice screen until you invoice it.")

    options = {s["id"]: s["label"] for s in db.student_options() if s["status"] != "inactive"}
    if not options:
        with ui.card().classes("ab-card p-6"):
            ui.label("Add a student first.").classes("mb-2")
            ui.button("Add student", on_click=lambda: ui.navigate.to("/students")).classes("ab-primary")
        return

    type_opts = {code: label for code, label in db.TRAINING_TYPES}
    rates = db.list_rates(active_only=True)
    rate_opts = {r["id"]: f"{r['name']}  ·  {fmt_money(r['price'])}/{r['unit']}" for r in rates}
    preselect = preselect_student
    if preselect not in options:
        preselect = next(iter(options))

    with ui.card().classes("ab-card p-5 w-full mb-4"):
        with ui.row().classes("w-full gap-3"):
            student = ui.select(options, label="Student", value=preselect).classes("flex-1").props("outlined dense")
            sess_date = ui.input("Date", value=iso_today()).props("outlined dense type=date").classes("w-44")
            ttype = ui.select(type_opts, label="Training type", value="flight").classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            hrs = ui.number("Hours", value=1.0, format="%.1f", min=0, step=0.1).classes("w-32").props("outlined dense")
            rate_sel = ui.select(rate_opts, label="Rate").classes("flex-1").props("outlined dense clearable")
            rate_amt = ui.number("Rate $", value=0, format="%.2f", min=0, step=1).classes("w-36").props("outlined dense")
            billable = ui.checkbox("Billable", value=True).classes("mt-4")
        with ui.row().classes("w-full gap-3"):
            aircraft = ui.input("Aircraft / device", placeholder="N12345 or AATD").classes("flex-1").props("outlined dense")
            airport = ui.input("Airport / location").classes("flex-1").props("outlined dense")
        notes = ui.input("Notes / lesson summary").classes("w-full").props("outlined dense")

        def apply_type():
            rate = db.find_rate_for_type(ttype.value)
            if rate:
                rate_sel.value = rate["id"]
                rate_amt.value = rate["price"]
            else:
                rate_amt.value = 0

        ttype.on("update:model-value", lambda _: apply_type())

        def apply_rate():
            if rate_sel.value:
                r = db.get_rate(int(rate_sel.value))
                if r:
                    rate_amt.value = r["price"]

        rate_sel.on("update:model-value", lambda _: apply_rate())
        apply_type()

        def save():
            if not student.value:
                ui.notify("Choose a student", type="warning")
                return
            if not hrs.value or float(hrs.value) <= 0:
                ui.notify("Enter hours (or 1 for a flat/each item)", type="warning")
                return
            sid = db.save_session(
                {
                    "student_id": int(student.value),
                    "date": sess_date.value,
                    "training_type": ttype.value,
                    "hours": hrs.value,
                    "aircraft": aircraft.value,
                    "airport": airport.value,
                    "rate_id": int(rate_sel.value) if rate_sel.value else None,
                    "rate_amount": rate_amt.value or 0,
                    "billable": bool(billable.value),
                    "description": db.training_type_label(ttype.value),
                    "notes": notes.value,
                }
            )
            amount = money((hrs.value or 0) * (rate_amt.value or 0))
            ui.notify(
                f"Logged {fmt_hours(hrs.value)} hr"
                + (f" · {fmt_money(amount)}" if billable.value else " (not billed)")
            )
            notes.value = ""
            recent.refresh()

        with ui.row().classes("justify-end w-full gap-2 mt-2"):
            ui.button("Save & log another", on_click=save).classes("ab-primary")
            ui.button(
                "Save and invoice student",
                on_click=lambda: _save_and_invoice(student, save),
            ).props("outline")

    @ui.refreshable
    def recent():
        sessions = db.list_sessions(limit=40)
        ui.label("Recent lessons").classes("text-lg font-semibold mb-2")
        if not sessions:
            ui.label("Nothing logged yet.").classes("text-sm text-gray-500")
            return
        columns = [
            {"name": "date", "label": "Date", "field": "date_label"},
            {"name": "student", "label": "Student", "field": "student_name", "align": "left"},
            {"name": "type", "label": "Type", "field": "type_label", "align": "left"},
            {"name": "hours", "label": "Hours", "field": "hours_label"},
            {"name": "rate", "label": "Rate", "field": "rate_label"},
            {"name": "amount", "label": "Amount", "field": "amount_label"},
            {"name": "bill", "label": "Status", "field": "bill_label"},
            {"name": "id", "label": "id", "field": "id"},
        ]
        rows = []
        for s in sessions:
            rows.append(
                {
                    "id": s["id"],
                    "date_label": fmt_date(s["date"]),
                    "student_name": s["student_name"],
                    "type_label": db.training_type_label(s["training_type"]),
                    "hours_label": fmt_hours(s["hours"]),
                    "rate_label": fmt_money(s["rate_amount"]),
                    "amount_label": fmt_money(s["line_amount"]),
                    "bill_label": "Billed" if s["billed"] else ("Unbilled" if s["billable"] else "Not billed"),
                    "billed": s["billed"],
                }
            )
        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full ab-card")
        table.add_slot(
            "body-cell-bill",
            """
            <q-td :props="props">
              <q-badge :color="props.value === 'Billed' ? 'grey' : (props.value === 'Unbilled' ? 'warning' : 'secondary')" outline>
                {{ props.value }}
              </q-badge>
            </q-td>
            """,
        )

        def on_delete(e):
            row = event_row(e)
            try:
                db.delete_session(int(row["id"]))
                ui.notify("Deleted")
                recent.refresh()
            except ValueError as err:
                ui.notify(str(err), type="warning")

        table.add_slot(
            "body-cell-id",
            """
            <q-td :props="props">
              <q-btn flat dense icon="delete" size="sm" @click.stop="$parent.$emit('del', props.row)" />
            </q-td>
            """,
        )
        table.on("del", on_delete)

    recent()


def _save_and_invoice(student, save_fn) -> None:
    save_fn()
    if student.value:
        ui.navigate.to(f"/invoices/new?student={int(student.value)}")
