"""Home dashboard with overdue reminders and this-month snapshot."""

from nicegui import ui

from aerobooks import db
from aerobooks.money import fmt_date, fmt_hours, fmt_money
from aerobooks.theme import frame, stat_card, status_chip


def register() -> None:
    @ui.page("/")
    def page():
        with frame("Dashboard", "/") as user:
            if not user:
                return
            render()


def render() -> None:
    stats = db.dashboard_stats()
    s = db.get_settings()

    with ui.row().classes("items-end justify-between w-full mb-4"):
        with ui.column().classes("gap-0"):
            ui.label("Dashboard").classes("ab-h1")
            who = db.instructor_display()
            ui.label(f"Welcome back{', ' + who if who != 'Instructor' else ''}.").classes("ab-sub")
        with ui.row().classes("gap-2"):
            ui.button("Log hours", icon="flight", on_click=lambda: ui.navigate.to("/hours")).props("outline")
            ui.button("New invoice", icon="receipt_long", on_click=lambda: ui.navigate.to("/invoices/new")).classes(
                "ab-primary"
            )

    if not db.is_setup_complete():
        with ui.card().classes("ab-alert-gold w-full p-4 mb-4"):
            ui.label("Finish setup so invoices look professional").classes("font-semibold")
            ui.label(
                "Add your name (or business name), address, rates, and Venmo username in Settings. "
                "AeroBooks will put them on every invoice automatically."
            ).classes("text-sm")
            ui.button("Open Settings", on_click=lambda: ui.navigate.to("/settings")).props("unelevated").classes(
                "ab-gold mt-2"
            )

    if stats["overdue_30_count"]:
        with ui.card().classes("ab-alert w-full p-4 mb-4"):
            ui.label(
                f"{stats['overdue_30_count']} invoice(s) are 30+ days overdue — {fmt_money(stats['overdue_30_amount'])}"
            ).classes("font-semibold")
            ui.label("Send a reminder, or open the invoice to record a payment.").classes("text-sm mb-2")
            overdue = db.list_invoices(status="overdue_30")
            for inv in overdue:
                with ui.row().classes("items-center justify-between w-full py-1 border-b"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"{inv['number']}  ·  {inv['student_name']}").classes("font-medium")
                        ui.label(
                            f"{fmt_money(inv['balance'])} due {fmt_date(inv['due_date'])}  ·  {inv['days_overdue']} days overdue"
                        ).classes("text-xs text-gray-600")
                    with ui.row().classes("gap-1"):
                        ui.button(
                            "Copy reminder",
                            on_click=lambda i=inv: _copy_reminder(i),
                        ).props("flat dense")
                        ui.button(
                            "Open",
                            on_click=lambda i=inv: ui.navigate.to(f"/invoices/{i['id']}"),
                        ).props("flat dense")
                        ui.button(
                            "Mark paid",
                            on_click=lambda i=inv: _mark_paid(i["id"]),
                        ).props("flat dense")

    elif stats["overdue_count"]:
        with ui.card().classes("ab-alert-gold w-full p-4 mb-4"):
            ui.label(
                f"{stats['overdue_count']} invoice(s) past due — {fmt_money(stats['overdue_amount'])}"
            ).classes("font-semibold")
            ui.button("Review unpaid invoices", on_click=lambda: ui.navigate.to("/invoices")).props("flat")

    with ui.row().classes("gap-3 w-full mb-4 flex-wrap"):
        stat_card("Collected this month", fmt_money(stats["collected_month"]), "Payments received")
        stat_card("Billed this month", fmt_money(stats["billed_month"]))
        stat_card(
            "Outstanding",
            fmt_money(stats["outstanding"]),
            f"{stats['overdue_count']} past due",
            "warn" if stats["outstanding"] else "",
        )
        stat_card(
            "Net this month",
            fmt_money(stats["net_month"]),
            f"Expenses {fmt_money(stats['expenses_month'])}",
            "good" if stats["net_month"] >= 0 else "warn",
        )

    with ui.row().classes("gap-3 w-full mb-4 flex-wrap"):
        stat_card("Active students", str(stats["active_students"]))
        stat_card("Hours this month", fmt_hours(stats["hours_month"]))
        stat_card(
            "Unbilled hours",
            fmt_hours(stats["unbilled_hours"]),
            fmt_money(stats["unbilled_amount"]) + " ready to invoice",
            "gold" if stats["unbilled_hours"] else "",
        )
        stat_card("YTD collected", fmt_money(stats["ytd_collected"]), f"Net {fmt_money(stats['ytd_net'])}")

    with ui.row().classes("gap-4 w-full items-start"):
        with ui.card().classes("ab-card flex-1 p-4"):
            ui.label("Unbilled training").classes("text-lg font-semibold mb-2")
            unbilled = db.list_sessions(unbilled_only=True, limit=8)
            if not unbilled:
                ui.label("Nothing waiting to invoice. Nice.").classes("text-sm text-gray-500")
            else:
                for sess in unbilled:
                    with ui.row().classes("items-center justify-between w-full py-1"):
                        ui.label(
                            f"{sess['student_name']}  ·  {db.training_type_label(sess['training_type'])}  ·  {fmt_hours(sess['hours'])} hr"
                        ).classes("text-sm")
                        ui.label(fmt_date(sess["date"])).classes("text-xs text-gray-500")
                ui.button(
                    "Create invoice from unbilled",
                    on_click=lambda: ui.navigate.to("/invoices/new"),
                ).props("outline").classes("mt-2")

        with ui.card().classes("ab-card flex-1 p-4"):
            ui.label("Recent invoices").classes("text-lg font-semibold mb-2")
            recent = db.list_invoices()[:8]
            if not recent:
                ui.label("No invoices yet.").classes("text-sm text-gray-500")
            else:
                for inv in recent:
                    with ui.row().classes("items-center justify-between w-full py-1 cursor-pointer").on(
                        "click", lambda i=inv: ui.navigate.to(f"/invoices/{i['id']}")
                    ):
                        with ui.row().classes("items-center gap-2"):
                            ui.label(inv["number"]).classes("font-medium text-sm")
                            ui.label(inv["student_name"]).classes("text-sm text-gray-600")
                            status_chip(inv.get("display_status") or inv["status"])
                        ui.label(fmt_money(inv["balance"] if inv["balance"] else inv["total"])).classes("text-sm")

        with ui.card().classes("ab-card flex-1 p-4"):
            ui.label("Watch list").classes("text-lg font-semibold mb-2")
            alerts = stats["medical_alerts"]
            if not alerts:
                ui.label("No medicals expiring in the next 60 days.").classes("text-sm text-gray-500")
            else:
                ui.label("Student medicals").classes("text-xs uppercase tracking-wide text-gray-500")
                for m in alerts:
                    ui.label(
                        f"{m['first_name']} {m['last_name']}  ·  expires {fmt_date(m['medical_expires'])}"
                    ).classes("text-sm")
            if not (s.get("venmo_username") or "").strip():
                ui.label("Venmo username is not set — invoices will not include a QR code.").classes(
                    "text-sm text-amber-800 mt-3"
                )


def _copy_reminder(inv: dict) -> None:
    text = db.reminder_message(inv)
    try:
        ui.clipboard.write(text)
        ui.notify("Reminder copied to clipboard")
    except Exception:
        ui.notify(text, timeout=8000)


def _mark_paid(invoice_id: int) -> None:
    db.mark_invoice_paid(invoice_id)
    ui.notify("Marked paid")
    ui.navigate.reload()
