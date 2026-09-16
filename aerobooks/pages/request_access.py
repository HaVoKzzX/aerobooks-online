"""Public form to request an independent instructor or manager account."""

from nicegui import ui

from aerobooks import auth
from aerobooks.theme import apply_theme, auth_shell


def register() -> None:
    @ui.page("/request")
    def page():
        apply_theme()
        if not auth.has_admin():
            ui.navigate.to("/setup")
            return
        if auth.current_user():
            ui.navigate.to("/")
            return

        state = {"done": False}

        @ui.refreshable
        def body():
            if state["done"]:
                with auth_shell("Request sent"):
                    ui.icon("mark_email_read", size="40px").classes("text-green-700")
                    ui.label("Request submitted").classes("text-2xl font-semibold mt-2")
                    ui.label(
                        "The administrator will review it. You can sign in after it is approved."
                    ).classes("text-sm text-gray-600 mt-2 mb-4")
                    ui.button("Back to sign in", on_click=lambda: ui.navigate.to("/login")).classes("ab-primary")
                return

            with auth_shell("Request access"):
                ui.label("Request an account").classes("text-2xl font-semibold mb-1")
                ui.label(
                    "Independent instructors get a private books workspace. "
                    "Flight school managers can add instructor logins under one business name."
                ).classes("text-sm text-gray-600 mb-4")
                account_type = ui.select(
                    {
                        "instructor": "Independent instructor (my own students and invoices)",
                        "manager": "Flight school owner / manager",
                    },
                    value="instructor",
                    label="Account type",
                ).props("outlined dense").classes("w-full")
                display = ui.input("Your name").props("outlined dense").classes("w-full")
                organization = ui.input("Flight school / business name").props("outlined dense").classes("w-full")
                email = ui.input("Email").props("outlined dense").classes("w-full")
                phone = ui.input("Phone").props("outlined dense").classes("w-full")
                username = ui.input("Desired username").props("outlined dense").classes("w-full")
                password = ui.input("Password", password=True, password_toggle_button=True).props(
                    "outlined dense"
                ).classes("w-full")
                confirm = ui.input("Confirm password", password=True, password_toggle_button=True).props(
                    "outlined dense"
                ).classes("w-full")
                notes = ui.textarea("Anything the admin should know").props("outlined dense autogrow").classes("w-full")

                def toggle():
                    organization.set_visibility(account_type.value == "manager")

                account_type.on("update:model-value", lambda _: toggle())
                toggle()

                def go():
                    if (password.value or "") != (confirm.value or ""):
                        ui.notify("Passwords do not match", type="warning")
                        return
                    try:
                        auth.submit_request(
                            username=username.value or "",
                            password=password.value or "",
                            account_type=account_type.value,
                            display_name=display.value or "",
                            email=email.value or "",
                            phone=phone.value or "",
                            organization=organization.value or "",
                            notes=notes.value or "",
                        )
                        state["done"] = True
                        body.refresh()
                    except ValueError as err:
                        ui.notify(str(err), type="warning")

                ui.button("Submit request", on_click=go).classes("ab-primary w-full mt-2")
                ui.link("Already have an account? Sign in", "/login").classes("text-sm mt-3")

        body()
