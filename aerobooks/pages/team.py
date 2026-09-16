"""Flight school manager: instructor sub-accounts."""

from nicegui import ui

from aerobooks import auth, db
from aerobooks.theme import frame, page_title


def register() -> None:
    @ui.page("/team")
    def page():
        with frame("Instructors", "/team") as user:
            if not user:
                return
            if user.get("role") != "manager":
                ui.label("Only the flight school manager can add instructor accounts.")
                return
            render(user)


def render(manager: dict) -> None:
    page_title(
        "Instructors",
        "Add logins for CFIs at your school. Each instructor has their own students. "
        "Invoices always use your school business name.",
    )
    school = db.get_settings().get("business_name") or db.display_name()
    with ui.card().classes("ab-alert-gold w-full p-4 mb-4"):
        ui.label(f"Invoice business name: {school}").classes("font-semibold")
        ui.label(
            "Instructors cannot change this. Set it in Settings → Identity."
        ).classes("text-sm")

    @ui.refreshable
    def table():
        users = auth.list_tenant_users(int(manager["tenant_id"]))
        with ui.card().classes("ab-card p-5 w-full"):
            if not users:
                ui.label("No instructors yet.").classes("text-gray-600")
            else:
                for u in users:
                    with ui.row().classes("items-center w-full py-2 border-b gap-3"):
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(u.get("display_name") or u["username"]).classes("font-medium")
                            ui.label(
                                f"@{u['username']}  ·  {auth.role_label(u['role'])}  ·  {u['status']}"
                            ).classes("text-xs text-gray-500")
                        if u["role"] != "manager":
                            if u["status"] == "active":
                                ui.button(
                                    "Disable",
                                    on_click=lambda i=u: _toggle(i, "disabled", table),
                                ).props("flat dense")
                            else:
                                ui.button(
                                    "Enable",
                                    on_click=lambda i=u: _toggle(i, "active", table),
                                ).props("flat dense")
                            ui.button(
                                "Password",
                                on_click=lambda i=u: _password(i, table),
                            ).props("flat dense")
            ui.button("Add instructor", icon="person_add", on_click=lambda: _add(manager, table)).classes(
                "ab-primary mt-3"
            )

    table()


def _toggle(user: dict, status: str, refresh) -> None:
    try:
        auth.set_user_status(int(user["id"]), status)
        ui.notify(f"{user['username']} is now {status}")
        refresh.refresh()
    except ValueError as err:
        ui.notify(str(err), type="warning")


def _password(user: dict, refresh) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[420px]"):
        ui.label(f"Reset password for @{user['username']}").classes("text-lg font-semibold")
        pw = ui.input("New password", password=True, password_toggle_button=True).props("outlined dense")

        def go():
            try:
                auth.set_password(int(user["id"]), pw.value or "")
                d.close()
                ui.notify("Password updated")
                refresh.refresh()
            except ValueError as err:
                ui.notify(str(err), type="warning")

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Save password", on_click=go).classes("ab-primary")
    d.open()


def _add(manager: dict, refresh) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[480px]"):
        ui.label("New school instructor").classes("text-lg font-semibold")
        ui.label("They sign in with this username and only see the students assigned to them.").classes(
            "text-sm text-gray-600 mb-2"
        )
        display = ui.input("Instructor name").props("outlined dense")
        username = ui.input("Username").props("outlined dense")
        email = ui.input("Email").props("outlined dense")
        phone = ui.input("Phone").props("outlined dense")
        password = ui.input("Password", password=True, password_toggle_button=True).props("outlined dense")

        def go():
            try:
                auth.create_school_instructor(
                    manager,
                    username=username.value or "",
                    password=password.value or "",
                    display_name=display.value or "",
                    email=email.value or "",
                    phone=phone.value or "",
                )
                d.close()
                ui.notify("Instructor account created")
                refresh.refresh()
            except ValueError as err:
                ui.notify(str(err), type="warning")

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Create", on_click=go).classes("ab-primary")
    d.open()
