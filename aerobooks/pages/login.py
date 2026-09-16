"""Sign-in and first-run administrator setup."""

from nicegui import ui

from aerobooks import auth
from aerobooks.theme import auth_shell


def register() -> None:
    @ui.page("/login")
    def login_page():
        if not auth.has_admin():
            ui.navigate.to("/setup")
            return
        user = auth.current_user()
        if user:
            ui.navigate.to("/admin" if user["role"] == "admin" else "/")
            return
        with auth_shell("Sign in"):
            ui.label("Sign in").classes("text-2xl font-semibold mb-1")
            ui.label("Use the username you requested, after it has been approved.").classes(
                "text-sm text-gray-600 mb-4"
            )
            username = ui.input("Username").props("outlined dense autocomplete=username").classes("w-full")
            password = ui.input("Password", password=True, password_toggle_button=True).props(
                "outlined dense autocomplete=current-password"
            ).classes("w-full")

            def go():
                try:
                    user = auth.authenticate(username.value or "", password.value or "")
                    auth.login_user(user)
                except ValueError as err:
                    ui.notify(str(err), type="warning")

            password.on("keydown.enter", lambda _: go())
            ui.button("Sign in", on_click=go).classes("ab-primary w-full mt-2")
            with ui.row().classes("justify-between w-full mt-3"):
                ui.link("Request an account", "/request").classes("text-sm")

    @ui.page("/setup")
    def setup_page():
        if auth.has_admin():
            ui.navigate.to("/login")
            return
        with auth_shell("Create administrator"):
            ui.label("Create the administrator").classes("text-2xl font-semibold mb-1")
            ui.label(
                "This is the only account that can approve independent instructors and flight school managers."
            ).classes("text-sm text-gray-600 mb-4")
            display = ui.input("Your name").props("outlined dense").classes("w-full")
            username = ui.input("Admin username").props("outlined dense").classes("w-full")
            password = ui.input("Password", password=True, password_toggle_button=True).props("outlined dense").classes(
                "w-full"
            )
            confirm = ui.input("Confirm password", password=True, password_toggle_button=True).props(
                "outlined dense"
            ).classes("w-full")

            def go():
                if (password.value or "") != (confirm.value or ""):
                    ui.notify("Passwords do not match", type="warning")
                    return
                try:
                    user = auth.create_admin(
                        username.value or "",
                        password.value or "",
                        display.value or "",
                    )
                    auth.login_user(user)
                    ui.notify("Administrator account created")
                except ValueError as err:
                    ui.notify(str(err), type="warning")

            ui.button("Create admin account", on_click=go).classes("ab-primary w-full mt-2")
