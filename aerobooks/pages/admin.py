"""Administrator: approve account requests and manage users."""

from nicegui import ui

from aerobooks import auth
from aerobooks.theme import admin_frame, page_title


def register() -> None:
    @ui.page("/admin")
    def requests_page():
        with admin_frame("Requests", "/admin") as user:
            if not user:
                return
            _requests(user)

    @ui.page("/admin/users")
    def users_page():
        with admin_frame("Users", "/admin/users") as user:
            if not user:
                return
            _users(user)


def _requests(admin: dict) -> None:
    page_title("Account requests", "Approve independent instructors and flight school managers.")

    @ui.refreshable
    def body():
        pending = auth.list_requests("pending")
        if not pending:
            with ui.card().classes("ab-card p-6"):
                ui.label("No pending requests.").classes("text-gray-600")
        else:
            for req in pending:
                with ui.card().classes("ab-card p-4 w-full mb-2"):
                    kind = (
                        "Flight school manager"
                        if req["account_type"] == "manager"
                        else "Independent instructor"
                    )
                    with ui.row().classes("items-start justify-between w-full gap-3"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"{req['display_name']}  ·  @{req['username']}").classes("font-semibold")
                            ui.label(kind).classes("text-sm text-gray-600")
                            if req.get("organization"):
                                ui.label(f"School: {req['organization']}").classes("text-sm")
                            contact = "  ·  ".join(x for x in (req.get("email"), req.get("phone")) if x)
                            if contact:
                                ui.label(contact).classes("text-sm text-gray-600")
                            if req.get("notes"):
                                ui.label(req["notes"]).classes("text-sm mt-1")
                            ui.label(f"Requested {req['created_at']}").classes("text-xs text-gray-500 mt-1")
                        with ui.row().classes("gap-2"):
                            ui.button(
                                "Approve",
                                icon="check",
                                on_click=lambda r=req: _approve(admin, r, body),
                            ).classes("ab-primary")
                            ui.button(
                                "Reject",
                                icon="close",
                                on_click=lambda r=req: _reject(admin, r, body),
                            ).props("outline color=negative")

        reviewed = [r for r in auth.list_requests("all") if r["status"] != "pending"][:20]
        if reviewed:
            ui.label("Recently reviewed").classes("font-semibold mt-6 mb-2")
            for req in reviewed:
                with ui.row().classes("w-full py-2 border-b items-center"):
                    ui.label(
                        f"{req['status'].title()}  ·  {req['display_name']} (@{req['username']})"
                    ).classes("flex-1 text-sm")
                    ui.label(req.get("reviewed_at") or "").classes("text-xs text-gray-500")

    body()


def _approve(admin: dict, req: dict, refresh) -> None:
    try:
        user = auth.approve_request(req["id"], admin["id"])
        ui.notify(f"Approved {user['username']}")
        refresh.refresh()
    except ValueError as err:
        ui.notify(str(err), type="warning")


def _reject(admin: dict, req: dict, refresh) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[420px]"):
        ui.label(f"Reject @{req['username']}?").classes("text-lg font-semibold")
        reason = ui.input("Reason (optional)").props("outlined dense")

        def go():
            try:
                auth.reject_request(req["id"], admin["id"], reason.value or "")
                d.close()
                ui.notify("Request rejected")
                refresh.refresh()
            except ValueError as err:
                ui.notify(str(err), type="warning")

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Reject", on_click=go).props("color=negative")
    d.open()


def _users(admin: dict) -> None:
    page_title("Users", "Every account on this AeroBooks server.")

    @ui.refreshable
    def body():
        users = auth.list_users()
        columns = [
            {"name": "username", "label": "Username", "field": "username", "align": "left"},
            {"name": "name", "label": "Name", "field": "display_name", "align": "left"},
            {"name": "role", "label": "Role", "field": "role_label", "align": "left"},
            {"name": "tenant", "label": "Workspace", "field": "tenant_name", "align": "left"},
            {"name": "status", "label": "Status", "field": "status", "align": "left"},
            {"name": "id", "label": "", "field": "id"},
        ]
        rows = [
            {
                "id": u["id"],
                "username": u["username"],
                "display_name": u.get("display_name") or "",
                "role_label": auth.role_label(u["role"]),
                "tenant_name": u.get("tenant_name") or "—",
                "status": u["status"],
                "role": u["role"],
            }
            for u in users
        ]
        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full ab-card")
        table.add_slot(
            "body-cell-id",
            """
            <q-td :props="props">
              <q-btn flat dense label="Disable" size="sm" v-if="props.row.role !== 'admin' && props.row.status === 'active'"
                     @click.stop="$parent.$emit('disable', props.row)" />
              <q-btn flat dense label="Enable" size="sm" v-if="props.row.role !== 'admin' && props.row.status !== 'active'"
                     @click.stop="$parent.$emit('enable', props.row)" />
              <q-btn flat dense label="Password" size="sm" v-if="props.row.role !== 'admin'"
                     @click.stop="$parent.$emit('password', props.row)" />
            </q-td>
            """,
        )
        table.on("disable", lambda e: _set_status(e, "disabled", body))
        table.on("enable", lambda e: _set_status(e, "active", body))
        table.on("password", lambda e: _password_dialog(e, body))

        ui.label("Workspaces").classes("font-semibold mt-6 mb-2")
        for t in auth.list_tenants():
            with ui.row().classes("w-full py-2 border-b"):
                with ui.column().classes("gap-0 flex-1"):
                    ui.label(t["name"]).classes("font-medium")
                    ui.label(
                        f"{'Flight school' if t['kind'] == 'school' else 'Independent'}  ·  "
                        f"{t['user_count']} user(s)  ·  owner @{t.get('owner_username') or '—'}"
                    ).classes("text-xs text-gray-500")

    body()


def _row_from_event(e) -> dict:
    args = getattr(e, "args", e)
    if isinstance(args, dict) and "id" in args:
        return args
    if isinstance(args, (list, tuple)):
        for item in reversed(args):
            if isinstance(item, dict) and "id" in item:
                return item
    raise ValueError("Could not read table row")


def _set_status(e, status: str, refresh) -> None:
    row = _row_from_event(e)
    try:
        auth.set_user_status(int(row["id"]), status)
        ui.notify(f"{row['username']} is now {status}")
        refresh.refresh()
    except ValueError as err:
        ui.notify(str(err), type="warning")


def _password_dialog(e, refresh) -> None:
    row = _row_from_event(e)
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[420px]"):
        ui.label(f"Reset password for @{row['username']}").classes("text-lg font-semibold")
        pw = ui.input("New password", password=True, password_toggle_button=True).props("outlined dense")

        def go():
            try:
                auth.set_password(int(row["id"]), pw.value or "")
                d.close()
                ui.notify("Password updated")
                refresh.refresh()
            except ValueError as err:
                ui.notify(str(err), type="warning")

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Save password", on_click=go).classes("ab-primary")
    d.open()
