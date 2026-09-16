"""Students, progress, notes, and balances."""

from nicegui import ui

from aerobooks import auth, backup, db
from aerobooks.money import fmt_date, fmt_hours, fmt_money, iso_today
from aerobooks.theme import event_row, frame, page_title, stat_card, status_chip


def register() -> None:
    @ui.page("/students")
    def list_page():
        with frame("Students", "/students") as user:
            if not user:
                return
            render_list(user)

    @ui.page("/students/{student_id}")
    def detail_page(student_id: int):
        with frame("Student", "/students") as user:
            if not user:
                return
            render_detail(student_id)


def render_list(user: dict | None = None) -> None:
    user = user or auth.current_user() or {}
    is_manager = user.get("role") == "manager"
    state = {"search": "", "status": "active", "instructor": "all"}

    actions = page_title("Students", "People you train, their hours, and what they owe.")
    with actions:
        ui.button("Add student", icon="person_add", on_click=lambda: student_dialog()).classes("ab-primary")

    @ui.refreshable
    def body():
        instructor_id = None
        if state["instructor"] not in ("", "all"):
            instructor_id = int(state["instructor"])
        students = db.list_students(
            status=state["status"],
            search=state["search"],
            instructor_user_id=instructor_id,
        )
        if not students:
            with ui.card().classes("ab-card p-6"):
                ui.label("No students match this filter.").classes("text-gray-600")
                ui.button("Add your first student", on_click=lambda: student_dialog()).classes("ab-gold mt-2")
            return
        columns = [
            {"name": "name", "label": "Student", "field": "full_name", "align": "left", "sortable": True},
            {"name": "goal", "label": "Instructing", "field": "goal", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
            {"name": "hours", "label": "Hours", "field": "hours_label", "align": "right"},
            {"name": "unbilled", "label": "Unbilled", "field": "unbilled_label", "align": "right"},
            {"name": "owed", "label": "Owed", "field": "owed_label", "align": "right"},
            {"name": "last", "label": "Last lesson", "field": "last_label", "align": "left"},
        ]
        if is_manager:
            columns.insert(1, {"name": "instructor", "label": "Instructor", "field": "instructor_name", "align": "left"})
        rows = []
        for s in students:
            rows.append(
                {
                    "id": s["id"],
                    "full_name": s["full_name"],
                    "instructor_name": s.get("instructor_name") or "—",
                    "goal": s.get("goal") or "—",
                    "status": s.get("status") or "active",
                    "hours_label": fmt_hours(s["total_hours"]),
                    "unbilled_label": fmt_hours(s["unbilled_hours"]),
                    "owed_label": fmt_money(s["owed"]),
                    "last_label": fmt_date(s.get("last_session")),
                }
            )
        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full ab-card")
        table.add_slot(
            "body-cell-status",
            """
            <q-td :props="props">
              <q-badge :color="props.value === 'active' ? 'positive' : (props.value === 'inactive' ? 'grey' : 'primary')" outline>
                {{ props.value.replace('_', ' ') }}
              </q-badge>
            </q-td>
            """,
        )
        table.on("rowClick", lambda e: ui.navigate.to(f"/students/{event_row(e)['id']}"))

    with ui.row().classes("items-center gap-3 mb-3 w-full"):
        ui.input("Search name, email, phone", on_change=lambda e: _set(state, "search", e.value, body)).props(
            "dense outlined clearable debounce=250"
        ).classes("w-64")
        ui.select(
            {
                "all": "All statuses",
                "active": "Active",
                "soloed": "Soloed",
                "checkride_ready": "Checkride ready",
                "graduated": "Graduated",
                "inactive": "Inactive",
            },
            value="active",
            on_change=lambda e: _set(state, "status", e.value, body),
        ).props("dense outlined").classes("w-48")
        if is_manager and user.get("tenant_id"):
            instructors = {str(u["id"]): u.get("display_name") or u["username"] for u in auth.instructor_options(int(user["tenant_id"]))}
            ui.select(
                {"all": "All instructors", **instructors},
                value="all",
                on_change=lambda e: _set(state, "instructor", e.value, body),
            ).props("dense outlined").classes("w-56")

    body()


def _set(state, key, value, refresh) -> None:
    state[key] = value or ""
    refresh.refresh()


def student_dialog(student: dict | None = None) -> None:
    data = dict(student or {})
    dialog = ui.dialog()
    with dialog, ui.card().classes("w-[720px] max-w-[95vw] p-5"):
        ui.label("Edit student" if student else "New student").classes("text-xl font-semibold")
        with ui.row().classes("w-full gap-3"):
            first = ui.input("First name", value=data.get("first_name") or "").classes("flex-1").props("outlined dense")
            last = ui.input("Last name", value=data.get("last_name") or "").classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            email = ui.input("Email", value=data.get("email") or "").classes("flex-1").props("outlined dense")
            phone = ui.input("Phone", value=data.get("phone") or "").classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            address = ui.input("Address", value=data.get("address") or "").classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            city = ui.input("City", value=data.get("city") or "").classes("flex-1").props("outlined dense")
            st = ui.input("State", value=data.get("state") or "").classes("w-24").props("outlined dense")
            zipc = ui.input("ZIP", value=data.get("zip") or "").classes("w-28").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            level = ui.select(
                db.CERTIFICATE_LEVELS,
                label="Certificate level",
                value=data.get("certificate_level") or "Student",
            ).classes("flex-1").props("outlined dense")
            cert = ui.input("Certificate #", value=data.get("certificate_number") or "").classes("flex-1").props(
                "outlined dense"
            )
        with ui.row().classes("w-full gap-3"):
            goal = ui.select(
                db.INSTRUCTION_TRACKS,
                label="Currently instructing",
                value=data.get("goal") or "Private Pilot (PPL)",
            ).classes("flex-1").props("outlined dense")
            status = ui.select(db.STUDENT_STATUSES, label="Status", value=data.get("status") or "active").classes(
                "w-48"
            ).props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            medical = ui.select(
                ["None", "Student", "Third class", "Second class", "First class", "BasicMed"],
                label="Medical",
                value=data.get("medical_class") or "Third class",
            ).classes("flex-1").props("outlined dense")
            medical_exp = ui.input("Medical expires", value=data.get("medical_expires") or "").props(
                "outlined dense type=date"
            ).classes("flex-1")
        with ui.row().classes("w-full gap-3"):
            airport = ui.input("Home airport", value=data.get("home_airport") or "").classes("flex-1").props(
                "outlined dense"
            )
            ac = ui.input("Usual aircraft", value=data.get("aircraft_preference") or "").classes("flex-1").props(
                "outlined dense"
            )
        notes = ui.textarea("Standing notes", value=data.get("notes") or "").classes("w-full").props(
            "outlined dense autogrow"
        )
        user = auth.current_user() or {}
        instructor_select = None
        if user.get("role") == "manager" and user.get("tenant_id"):
            options = {
                str(u["id"]): u.get("display_name") or u["username"]
                for u in auth.instructor_options(int(user["tenant_id"]))
            }
            current = str(data.get("instructor_user_id") or user.get("id") or "")
            instructor_select = ui.select(
                options,
                value=current if current in options else (next(iter(options), None)),
                label="Assigned instructor",
            ).props("outlined dense")

        def save():
            if not first.value or not last.value:
                ui.notify("First and last name are required", type="warning")
                return
            payload = {
                "id": data.get("id"),
                "first_name": first.value.strip(),
                "last_name": last.value.strip(),
                "email": email.value,
                "phone": phone.value,
                "address": address.value,
                "city": city.value,
                "state": st.value,
                "zip": zipc.value,
                "certificate_level": level.value,
                "certificate_number": cert.value,
                "goal": goal.value,
                "status": status.value,
                "medical_class": medical.value,
                "medical_expires": medical_exp.value,
                "home_airport": airport.value,
                "aircraft_preference": ac.value,
                "notes": notes.value,
            }
            if instructor_select and instructor_select.value:
                payload["instructor_user_id"] = int(instructor_select.value)
            sid = db.save_student(payload)
            dialog.close()
            ui.notify("Student saved")
            ui.navigate.to(f"/students/{sid}")

        with ui.row().classes("justify-between w-full items-center gap-2 mt-2"):
            if data.get("id"):
                ui.button(
                    "Delete student",
                    icon="delete",
                    on_click=lambda: _confirm_delete_student(int(data["id"]), dialog),
                ).props("flat color=negative")
            else:
                ui.element("div")
            with ui.row().classes("gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save).classes("ab-primary")
    dialog.open()


def _confirm_delete_student(student_id: int, edit_dialog) -> None:
    info = db.student_delete_summary(student_id)
    confirm = ui.dialog()
    with confirm, ui.card().classes("p-5 w-[560px] max-w-[95vw]"):
        ui.label(f"Delete {info['full_name']}?").classes("text-xl font-semibold")
        ui.label("This cannot be undone. It removes this student and:").classes("text-sm mt-2")
        ui.label(
            f"• {info['sessions']} training session(s)  ({fmt_hours(info['hours'])} hours)\n"
            f"• {info['invoices']} invoice(s)\n"
            f"• {info['notes']} note(s), plus progress and contact info"
        ).classes("text-sm whitespace-pre-wrap mt-1")
        ui.label("Would you like to save a full backup of AeroBooks before continuing?").classes(
            "text-sm font-medium mt-3"
        )
        ui.label("The backup is a zip of every student, invoice, and setting — not only this person.").classes(
            "text-xs text-gray-500"
        )

        def do_delete(*, with_backup: bool) -> None:
            try:
                if with_backup:
                    dest = backup.create_backup_zip()
                    ui.download.file(dest)
                    ui.notify(f"Backup saved to {dest}", timeout=5000)
                db.delete_student(student_id)
                confirm.close()
                edit_dialog.close()
                ui.notify(f"{info['full_name']} deleted")
                ui.navigate.to("/students")
            except Exception as err:
                ui.notify(str(err), type="negative", timeout=8000)

        with ui.row().classes("justify-end w-full gap-2 mt-4 flex-wrap"):
            ui.button("Cancel", on_click=confirm.close).props("flat")
            ui.button(
                "Delete without backup",
                on_click=lambda: do_delete(with_backup=False),
            ).props("flat color=negative")
            ui.button(
                "Save backup, then delete",
                icon="save",
                on_click=lambda: do_delete(with_backup=True),
            ).classes("ab-primary")
    confirm.open()


def render_detail(student_id: int) -> None:
    student = db.get_student(student_id)
    if not student:
        ui.label("Student not found.")
        ui.button("Back", on_click=lambda: ui.navigate.to("/students"))
        return

    with ui.row().classes("items-start justify-between w-full mb-3"):
        with ui.column().classes("gap-0"):
            with ui.row().classes("items-center gap-3"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/students")).props("flat round")
                ui.label(student["full_name"]).classes("ab-h1")
                status_chip(student["status"])
            bits = [b for b in [student.get("goal"), student.get("certificate_level"), student.get("email"), student.get("phone")] if b]
            ui.label("  ·  ".join(bits)).classes("ab-sub ml-12")
        with ui.row().classes("gap-2"):
            ui.button("Edit", icon="edit", on_click=lambda: student_dialog(student)).props("outline")
            ui.button(
                "Log hours",
                icon="flight",
                on_click=lambda: ui.navigate.to(f"/hours?student={student_id}"),
            ).props("outline")
            ui.button(
                "Invoice",
                icon="receipt_long",
                on_click=lambda: ui.navigate.to(f"/invoices/new?student={student_id}"),
            ).classes("ab-primary")

    with ui.row().classes("gap-3 w-full mb-4 flex-wrap"):
        stat_card("Total hours", fmt_hours(student["total_hours"]))
        stat_card("Unbilled", fmt_hours(student["unbilled_hours"]), fmt_money(student["unbilled_amount"]))
        stat_card("Owed", fmt_money(student["owed"]), "Open invoice balance", "warn" if student["owed"] else "")
        stat_card("Paid", fmt_money(student["paid"]))
        stat_card("Last lesson", fmt_date(student.get("last_session")))

    hours_map = student.get("hours_by_type") or {}
    if hours_map:
        with ui.card().classes("ab-card p-4 w-full mb-4"):
            ui.label("Hours by type").classes("font-semibold mb-2")
            with ui.row().classes("gap-2 flex-wrap"):
                for code, hrs in sorted(hours_map.items(), key=lambda x: -x[1]):
                    with ui.card().classes("p-3"):
                        ui.label(db.training_type_label(code)).classes("text-xs text-gray-500")
                        ui.label(fmt_hours(hrs)).classes("text-xl font-bold")

    with ui.row().classes("gap-4 w-full items-start"):
        with ui.card().classes("ab-card p-4 flex-1"):
            ui.label("Progress").classes("text-lg font-semibold")
            ui.label(
                "Certificate they already hold is under Edit. This list is only what you are teaching — "
                "useful when you are not their primary CFI."
            ).classes("text-xs text-gray-500 mb-2")
            counts = db.track_progress_counts(student_id)
            track_options = {}
            for name in db.INSTRUCTION_TRACKS:
                if name in counts:
                    done, total = counts[name]
                    track_options[name] = f"{name}  ({done}/{total})"
                else:
                    track_options[name] = name
            current_track = db.resolve_track(student.get("goal") or "Private Pilot (PPL)")
            if current_track not in track_options:
                current_track = next(iter(track_options))

            @ui.refreshable
            def progress_list(track: str = current_track):
                items = db.list_milestones(student_id, track)
                if not items:
                    ui.label("No checklist for this training yet.").classes("text-sm text-gray-600 mt-2")
                    ui.button(
                        "Load checklist",
                        on_click=lambda t=track: _seed(student_id, t),
                    ).props("outline").classes("mt-1")
                for m in items:
                    with ui.row().classes("items-center w-full"):
                        ui.checkbox(
                            text=m["name"],
                            value=bool(m["completed"]),
                            on_change=lambda e, mid=m["id"]: (
                                db.set_milestone(mid, e.value),
                                progress_list.refresh(track),
                            ),
                        )
                        if m.get("completed_date"):
                            ui.label(fmt_date(m["completed_date"])).classes("text-xs text-gray-500 ml-auto")
                with ui.row().classes("w-full items-center gap-2 mt-2"):
                    new_m = ui.input("Add a custom item").props("dense outlined").classes("flex-1")
                    ui.button(
                        "Add",
                        on_click=lambda t=track, field=new_m: _add_milestone(student_id, field, t),
                    ).props("flat")

            def on_track_change(e):
                track = e.value
                db.set_instruction_track(student_id, track)
                db.seed_milestones(student_id, track)
                progress_list.refresh(track)

            ui.select(
                track_options,
                value=current_track,
                label="What are you instructing?",
                on_change=on_track_change,
            ).props("outlined dense").classes("w-full")
            db.seed_milestones(student_id, current_track)
            progress_list(current_track)

        with ui.card().classes("ab-card p-4 flex-1"):
            ui.label("Notes").classes("text-lg font-semibold")
            with ui.row().classes("w-full gap-2 items-start"):
                note_body = ui.textarea("Add a note").props("outlined dense autogrow").classes("flex-1")
                ui.button("Save note", on_click=lambda: _add_note(student_id, note_body)).classes("ab-primary")
            notes = db.list_notes(student_id)
            if not notes and not (student.get("notes") or "").strip():
                ui.label("No notes yet.").classes("text-sm text-gray-500")
            if student.get("notes"):
                with ui.card().classes("p-3 bg-amber-50"):
                    ui.label("Standing notes").classes("text-xs uppercase text-gray-500")
                    ui.label(student["notes"]).classes("text-sm whitespace-pre-wrap")
            for n in notes:
                with ui.row().classes("w-full items-start justify-between py-2 border-b"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"{fmt_date(n['date'])}  ·  {n['category']}").classes("text-xs text-gray-500")
                        ui.label(n["body"]).classes("text-sm whitespace-pre-wrap")
                    ui.button(icon="delete", on_click=lambda nid=n["id"]: _del_note(student_id, nid)).props(
                        "flat dense round"
                    )

    unbilled = [s for s in db.list_sessions(student_id=student_id, unbilled_only=True, limit=100)]
    if unbilled:
        with ui.card().classes("ab-card p-4 w-full mt-4"):
            with ui.row().classes("items-center justify-between w-full mb-2"):
                with ui.column().classes("gap-0"):
                    ui.label("Unbilled training").classes("text-lg font-semibold")
                    ui.label(
                        f"{fmt_hours(student['unbilled_hours'])} hr  ·  {fmt_money(student['unbilled_amount'])} ready to bill"
                    ).classes("text-sm text-gray-600")
                ui.button(
                    "Invoice all unbilled",
                    icon="receipt_long",
                    on_click=lambda: _go_invoice(student_id, [s["id"] for s in unbilled]),
                ).classes("ab-primary")
            columns = [
                {"name": "date", "label": "Date", "field": "date_label"},
                {"name": "type", "label": "Type", "field": "type_label", "align": "left"},
                {"name": "hours", "label": "Hours", "field": "hours_label"},
                {"name": "amount", "label": "Amount", "field": "amount_label"},
                {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
            ]
            rows = [
                {
                    "id": s["id"],
                    "date_label": fmt_date(s["date"]),
                    "type_label": db.training_type_label(s["training_type"]),
                    "hours_label": fmt_hours(s["hours"]),
                    "amount_label": fmt_money(s["line_amount"]),
                    "notes": s.get("notes") or s.get("description") or "",
                }
                for s in unbilled
            ]
            unbilled_table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
                selection="multiple",
            ).classes("w-full")
            unbilled_table.selected = list(rows)
            ui.button(
                "Invoice selected",
                icon="receipt_long",
                on_click=lambda: _invoice_selected(student_id, unbilled_table),
            ).props("outline").classes("mt-2")

    with ui.card().classes("ab-card p-4 w-full mt-4"):
        ui.label("Training log").classes("text-lg font-semibold")
        ui.label("Select unbilled lessons and invoice them, or open a billed lesson’s invoice.").classes(
            "text-sm text-gray-600 mb-2"
        )
        sessions = db.list_sessions(student_id=student_id, limit=50)
        if not sessions:
            ui.label("No hours logged yet.").classes("text-sm text-gray-500")
        else:
            columns = [
                {"name": "date", "label": "Date", "field": "date"},
                {"name": "type", "label": "Type", "field": "type_label", "align": "left"},
                {"name": "hours", "label": "Hours", "field": "hours_label"},
                {"name": "ac", "label": "Aircraft", "field": "aircraft"},
                {"name": "bill", "label": "Billing", "field": "bill_label"},
                {"name": "notes", "label": "Notes", "field": "notes", "align": "left"},
            ]
            rows = [
                {
                    "id": s["id"],
                    "invoice_id": s.get("invoice_id"),
                    "billed": bool(s["billed"]),
                    "billable": bool(s["billable"]),
                    "date": fmt_date(s["date"]),
                    "type_label": db.training_type_label(s["training_type"]),
                    "hours_label": fmt_hours(s["hours"]),
                    "aircraft": s.get("aircraft") or "—",
                    "bill_label": "Billed" if s["billed"] else ("Unbilled" if s["billable"] else "Not billed"),
                    "notes": s.get("notes") or s.get("description") or "",
                }
                for s in sessions
            ]
            log_table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
                selection="multiple",
            ).classes("w-full")
            log_table.add_slot(
                "body-cell-bill",
                """
                <q-td :props="props">
                  <q-badge :color="props.value === 'Billed' ? 'grey' : (props.value === 'Unbilled' ? 'warning' : 'secondary')" outline>
                    {{ props.value }}
                  </q-badge>
                </q-td>
                """,
            )

            def on_log_click(e):
                row = event_row(e)
                if row.get("billed") and row.get("invoice_id"):
                    ui.navigate.to(f"/invoices/{row['invoice_id']}")

            log_table.on("rowClick", on_log_click)
            with ui.row().classes("gap-2 mt-2"):
                ui.button(
                    "Invoice selected",
                    icon="receipt_long",
                    on_click=lambda: _invoice_selected(student_id, log_table),
                ).classes("ab-primary")
                ui.button(
                    "Open invoice",
                    icon="open_in_new",
                    on_click=lambda: _open_selected_invoice(log_table),
                ).props("outline")

    with ui.card().classes("ab-card p-4 w-full mt-4"):
        ui.label("Invoices").classes("text-lg font-semibold mb-2")
        invoices = db.list_invoices(student_id=student_id)
        if not invoices:
            ui.label("No invoices for this student.").classes("text-sm text-gray-500")
        else:
            columns = [
                {"name": "number", "label": "Invoice", "field": "number"},
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
                    "issue_label": fmt_date(i["issue_date"]),
                    "due_label": fmt_date(i["due_date"]),
                    "total_label": fmt_money(i["total"]),
                    "balance_label": fmt_money(i["balance"]),
                    "display_status": i.get("display_status") or i["status"],
                }
                for i in invoices
            ]
            table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
            table.on("rowClick", lambda e: ui.navigate.to(f"/invoices/{event_row(e)['id']}"))


def _go_invoice(student_id: int, session_ids: list[int]) -> None:
    ids = [int(i) for i in session_ids if i]
    if not ids:
        ui.notify("Select at least one unbilled lesson", type="warning")
        return
    qs = ",".join(str(i) for i in ids)
    ui.navigate.to(f"/invoices/new?student={student_id}&sessions={qs}")


def _invoice_selected(student_id: int, table) -> None:
    selected = list(table.selected or [])
    ids = []
    for row in selected:
        if row.get("billed"):
            continue
        if "billable" in row and not row.get("billable") and row.get("bill_label") == "Not billed":
            continue
        if row.get("bill_label") == "Billed":
            continue
        ids.append(int(row["id"]))
    if not ids:
        ui.notify("Select unbilled lessons to invoice", type="warning")
        return
    _go_invoice(student_id, ids)


def _open_selected_invoice(table) -> None:
    selected = list(table.selected or [])
    for row in selected:
        if row.get("invoice_id"):
            ui.navigate.to(f"/invoices/{row['invoice_id']}")
            return
    ui.notify("Select a billed lesson, or click a billed row", type="warning")


def _seed(student_id, goal) -> None:
    db.seed_milestones(student_id, goal or "")
    ui.navigate.reload()


def _add_milestone(student_id, field, track) -> None:
    if not (field.value or "").strip():
        return
    db.add_milestone(student_id, field.value, track)
    ui.navigate.reload()


def _add_note(student_id, field) -> None:
    if not (field.value or "").strip():
        return
    db.add_note(student_id, field.value)
    ui.navigate.reload()


def _del_note(student_id, note_id) -> None:
    db.delete_note(note_id)
    ui.navigate.reload()
