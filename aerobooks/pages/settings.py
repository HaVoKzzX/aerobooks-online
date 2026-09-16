"""Instructor / business identity, rates, Venmo, and invoice defaults."""

from pathlib import Path

from nicegui import ui

from aerobooks import auth, backup, db, paths
from aerobooks.money import fmt_money
from aerobooks.pdf_invoice import settings_qr_path
from aerobooks.theme import event_row, frame, page_title


def register() -> None:
    @ui.page("/settings")
    def page():
        with frame("Settings", "/settings") as user:
            if not user:
                return
            render()


def render() -> None:
    s = db.get_settings()
    user = auth.current_user() or {}
    page_title("Settings", "This information prints on every invoice.")

    with ui.tabs().classes("w-full") as tabs:
        identity = ui.tab("Identity")
        rates = ui.tab("Rates & products")
        pay = ui.tab("Venmo & invoices")
        data = ui.tab("Data") if auth.can_backup(user) else None

    with ui.tab_panels(tabs, value=identity).classes("w-full"):
        with ui.tab_panel(identity):
            _identity(s, user)
        with ui.tab_panel(rates):
            _rates(user)
        with ui.tab_panel(pay):
            _pay(s, user)
        if data is not None:
            with ui.tab_panel(data):
                _data()


def _identity(s: dict, user: dict | None = None) -> None:
    locked = bool(s.get("identity_locked") or (user or {}).get("role") == "school_instructor")
    with ui.card().classes("ab-card p-5 w-full"):
        if locked:
            with ui.element("div").classes("ab-lock-note mb-3"):
                ui.label(
                    "Invoice business name, address, and school contact are set by the flight school manager "
                    "and cannot be changed on instructor accounts."
                )
        entity = ui.select(
            {"individual": "I invoice as myself (instructor name)", "business": "I invoice as a business"},
            value=s.get("entity_type") or "individual",
            label="How invoices are headed",
        ).props("outlined dense")
        business = ui.input("Business name", value=s.get("business_name") or "").props("outlined dense")
        instructor = ui.input("Instructor name", value=s.get("instructor_name") or "").props("outlined dense")
        ui.label("If you invoice as a business, both names print: business on top, instructor underneath.").classes(
            "text-sm text-gray-600"
        )
        if locked:
            entity.props("readonly")
            business.props("readonly")
            entity.disable()
            business.disable()
        with ui.row().classes("w-full gap-3"):
            cfi = ui.input("CFI certificate #", value=s.get("cfi_number") or "").classes("flex-1").props("outlined dense")
            cfii = ui.input("CFII certificate #", value=s.get("cfii_number") or "").classes("flex-1").props(
                "outlined dense"
            )
        address = ui.input("Street address", value=s.get("address") or "").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            city = ui.input("City", value=s.get("city") or "").classes("flex-1").props("outlined dense")
            state = ui.input("State", value=s.get("state") or "").classes("w-28").props("outlined dense")
            zipc = ui.input("ZIP", value=s.get("zip") or "").classes("w-32").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            phone = ui.input("Phone", value=s.get("phone") or "").classes("flex-1").props("outlined dense")
            email = ui.input("Email", value=s.get("email") or "").classes("flex-1").props("outlined dense")
        with ui.row().classes("w-full gap-3"):
            web = ui.input("Website", value=s.get("website") or "").classes("flex-1").props("outlined dense")
            airport = ui.input("Home airport", value=s.get("home_airport") or "").classes("flex-1").props("outlined dense")

        def save():
            db.save_settings(
                {
                    "entity_type": entity.value,
                    "business_name": business.value,
                    "instructor_name": instructor.value,
                    "cfi_number": cfi.value,
                    "cfii_number": cfii.value,
                    "address": address.value,
                    "city": city.value,
                    "state": state.value,
                    "zip": zipc.value,
                    "phone": phone.value,
                    "email": email.value,
                    "website": web.value,
                    "home_airport": airport.value,
                    "setup_complete": "1",
                }
            )
            ui.notify("Identity saved — it will appear on the next invoice")

        if locked:
            for field in (address, city, state, zipc, phone, email, web, airport):
                field.props("readonly")
                field.disable()
        ui.button("Save identity", on_click=save).classes("ab-primary mt-2")


def _rates(user: dict | None = None) -> None:
    @ui.refreshable
    def table():
        rates = db.list_rates()
        with ui.card().classes("ab-card p-5 w-full"):
            ui.label("Training rates, products, and extra services").classes("font-semibold")
            ui.label(
                "These fill in when you log hours and when you add lines to an invoice. "
                "Set a price of $0 for pass-through items and enter the real amount on the invoice."
            ).classes("text-sm text-gray-600 mb-3")
            columns = [
                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "category", "label": "Category", "field": "category"},
                {"name": "unit", "label": "Unit", "field": "unit"},
                {"name": "price", "label": "Price", "field": "price_label"},
                {"name": "active", "label": "Active", "field": "active_label"},
                {"name": "id", "label": "id", "field": "id"},
            ]
            rows = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "unit": r["unit"],
                    "price_label": fmt_money(r["price"]),
                    "active_label": "Yes" if r["is_active"] else "Hidden",
                }
                for r in rates
            ]
            t = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
            if auth.can_edit_rates(user):
                t.add_slot(
                    "body-cell-id",
                    """
                    <q-td :props="props">
                      <q-btn flat dense icon="edit" size="sm" @click.stop="$parent.$emit('edit', props.row)" />
                    </q-td>
                    """,
                )
                t.on("edit", lambda e: rate_dialog(db.get_rate(int(event_row(e)["id"])), table.refresh))
                ui.button("Add rate or product", icon="add", on_click=lambda: rate_dialog(None, table.refresh)).classes(
                    "ab-primary mt-3"
                )
            else:
                ui.label("Rates are set by the flight school manager.").classes("text-sm text-gray-600 mt-2")

    table()


def rate_dialog(rate: dict | None, on_save) -> None:
    data = dict(rate or {})
    cats = sorted({c for _, c, _, _, _, _ in db.DEFAULT_RATES} | {"product", "service", "other"})
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[520px]"):
        ui.label("Edit rate" if rate else "New rate / product / service").classes("text-lg font-semibold")
        name = ui.input("Name", value=data.get("name") or "").props("outlined dense")
        category = ui.select(
            cats, value=data.get("category") or "flight", label="Category", new_value_mode="add-unique"
        ).props("outlined dense")
        unit = ui.select(["hour", "each", "flat"], value=data.get("unit") or "hour", label="Unit").props("outlined dense")
        price = ui.number("Price", value=data.get("price") or 0, format="%.2f", min=0).props("outlined dense")
        desc = ui.textarea("Description", value=data.get("description") or "").props("outlined dense autogrow")
        active = ui.checkbox("Active (show in pickers)", value=bool(data.get("is_active", 1)))

        def go():
            if not (name.value or "").strip():
                ui.notify("Name required", type="warning")
                return
            db.save_rate(
                {
                    "id": data.get("id"),
                    "name": name.value.strip(),
                    "category": category.value,
                    "unit": unit.value,
                    "price": price.value,
                    "description": desc.value,
                    "is_active": active.value,
                    "sort_order": data.get("sort_order") or 99,
                }
            )
            d.close()
            ui.notify("Saved")
            on_save()

        def delete():
            if data.get("id"):
                db.delete_rate(int(data["id"]))
            d.close()
            on_save()

        with ui.row().classes("justify-between w-full mt-2"):
            if data.get("id"):
                ui.button("Delete", on_click=delete).props("flat color=negative")
            else:
                ui.element("div")
            with ui.row().classes("gap-2"):
                ui.button("Cancel", on_click=d.close).props("flat")
                ui.button("Save", on_click=go).classes("ab-primary")
    d.open()


def _pay(s: dict, user: dict | None = None) -> None:
    locked = bool(s.get("identity_locked") or (user or {}).get("role") == "school_instructor")
    with ui.card().classes("ab-card p-5 w-full mb-3"):
        ui.label("Venmo").classes("font-semibold")
        ui.label(
            "Enter the username people already pay you with (the part after venmo.com/). "
            "AeroBooks generates a QR code automatically and prints it on the invoice with the amount and invoice number filled in."
        ).classes("text-sm text-gray-600 mb-2")
        venmo = ui.input("Venmo username", value=s.get("venmo_username") or "", placeholder="yourname").props(
            "outlined dense prefix=@"
        )
        note = ui.input(
            "Payment note prefix",
            value=s.get("venmo_note_prefix") or "Flight training",
        ).props("outlined dense")
        if locked:
            ui.label(
                "Leave Venmo blank to use the flight school's payment QR on invoices. "
                "Fill it in only if students should pay you directly."
            ).classes("text-sm text-gray-600 mb-2")
        ui.label("Optional: upload your official Venmo QR screenshot if you prefer that over the generated code.").classes(
            "text-sm text-gray-600 mt-2"
        )
        custom_label = ui.label(s.get("custom_qr_path") or "No custom QR uploaded").classes("text-xs text-gray-500")

        async def on_upload(e):
            from aerobooks.store import maybe_encrypt_existing_file

            dest = db.QR_DIR / "custom_venmo_qr.png"
            dest.parent.mkdir(parents=True, exist_ok=True)
            await e.file.save(dest)
            maybe_encrypt_existing_file(dest)
            db.set_setting("custom_qr_path", str(dest))
            custom_label.set_text(str(dest))
            ui.notify("Custom QR saved")
            preview.refresh()

        ui.upload(on_upload=on_upload, auto_upload=True, max_files=1).props('accept="image/*" label="Upload QR image"')
        ui.button(
            "Clear custom QR (use generated)",
            on_click=lambda: (db.set_setting("custom_qr_path", ""), custom_label.set_text("No custom QR uploaded"), preview.refresh()),
        ).props("flat")

        def save_venmo():
            db.save_settings(
                {
                    "venmo_username": (venmo.value or "").lstrip("@").strip(),
                    "venmo_note_prefix": note.value,
                }
            )
            ui.notify("Venmo settings saved")
            preview.refresh()

        ui.button("Save Venmo", on_click=save_venmo).classes("ab-primary mt-2")

        @ui.refreshable
        def preview():
            path = settings_qr_path()
            username = db.get_setting("venmo_username")
            if path and path.exists():
                from aerobooks.store import decrypt_to_temp

                ui.label(f"QR preview for @{username}" if username else "Custom Venmo QR").classes("mt-3 font-medium")
                ui.image(str(decrypt_to_temp(path))).classes("w-40 h-40")
            elif username:
                ui.label("Save to generate a preview.").classes("text-sm text-gray-500 mt-2")
            else:
                ui.label("No Venmo username yet — invoices will omit the QR until you add one.").classes(
                    "text-sm text-amber-800 mt-2"
                )

        preview()

    with ui.card().classes("ab-card p-5 w-full"):
        ui.label("Invoice defaults").classes("font-semibold")
        if locked:
            with ui.element("div").classes("ab-lock-note mb-3"):
                ui.label("Invoice numbering, terms, and tax are set by the flight school manager.")
        prefix = ui.input("Invoice number prefix", value=s.get("invoice_prefix") or "INV").props("outlined dense")
        nxt = ui.input("Next invoice number", value=s.get("next_invoice_number") or "1001").props("outlined dense")
        terms_days = ui.number(
            "Payment terms (days)", value=int(s.get("payment_terms_days") or 30), min=0, step=1
        ).props("outlined dense")
        ui.label("Unpaid invoices past this many days are overdue. At 30 days they appear as a reminder on the dashboard.").classes(
            "text-sm text-gray-600"
        )
        tax_on = ui.checkbox("Add tax to invoices", value=s.get("tax_enabled") == "1")
        tax_rate = ui.number("Tax rate %", value=float(s.get("tax_rate") or 0), format="%.3f", min=0).props(
            "outlined dense"
        )
        tax_label = ui.input("Tax label", value=s.get("tax_label") or "Sales tax").props("outlined dense")
        footer = ui.textarea("Default invoice terms / footer", value=s.get("invoice_footer") or "").props(
            "outlined dense autogrow"
        )

        def save_inv():
            db.save_settings(
                {
                    "invoice_prefix": prefix.value,
                    "next_invoice_number": nxt.value,
                    "payment_terms_days": str(int(terms_days.value or 30)),
                    "tax_enabled": "1" if tax_on.value else "0",
                    "tax_rate": str(tax_rate.value or 0),
                    "tax_label": tax_label.value,
                    "invoice_footer": footer.value,
                }
            )
            ui.notify("Invoice defaults saved")

        if locked:
            for field in (prefix, nxt, terms_days, tax_rate, tax_label, footer):
                field.props("readonly")
                field.disable()
            tax_on.disable()
        else:
            ui.button("Save invoice defaults", on_click=save_inv).classes("ab-primary mt-2")


def _data() -> None:
    with ui.card().classes("ab-card p-5 w-full mb-3"):
        ui.label("Where your files live").classes("font-semibold")
        ui.label(
            "This online copy stores each instructor or flight school in its own data folder on the server. "
            "Backups for a school include every instructor under that school. "
            "A zip from the original AeroBooks program restores here, and a zip you save here restores there."
        ).classes("text-sm text-gray-600 mb-2")
        ui.label(f"Data folder: {paths.data_dir()}").classes("text-sm text-gray-600")
        ui.label(f"Database: {paths.db_path()}").classes("text-sm text-gray-600")
        ui.label(f"Invoice PDFs: {paths.invoice_dir()}").classes("text-sm text-gray-600")
        ui.label(f"Backups: {paths.documents_backup_dir()}").classes("text-sm text-gray-600")
        with ui.row().classes("gap-2 mt-2"):
            ui.button(
                "Open data folder",
                icon="folder_open",
                on_click=lambda: backup.open_folder(paths.data_dir()),
            ).props("outline")
            ui.button(
                "Open backups folder",
                icon="folder_special",
                on_click=lambda: backup.open_folder(paths.documents_backup_dir()),
            ).props("outline")

    with ui.card().classes("ab-card p-5 w-full mb-3"):
        ui.label("Save a backup").classes("font-semibold")
        ui.label(
            "Creates one zip file with everything: students, hours, invoices, payments, expenses, "
            "settings, rates, invoice PDFs, and Venmo QR codes. Save a copy to a USB drive or cloud folder."
        ).classes("text-sm text-gray-600 mb-2")

        def save_backup():
            dest = backup.create_backup_zip()
            ui.download.file(dest)
            ui.notify(f"Backup saved to {dest}")
            listing.refresh()

        ui.button("Save backup now", icon="save", on_click=save_backup).classes("ab-primary")

    with ui.card().classes("ab-card p-5 w-full mb-3"):
        ui.label("Restore a backup").classes("font-semibold")
        ui.label(
            "This replaces the current students, invoices, and settings with the backup. "
            "AeroBooks first saves a safety copy of whatever is here now."
        ).classes("text-sm text-gray-600 mb-2")

        async def on_restore_upload(e):
            from aerobooks.store import maybe_encrypt_existing_file

            incoming = paths.local_backup_dir() / "incoming-restore.zip"
            incoming.parent.mkdir(parents=True, exist_ok=True)
            await e.file.save(incoming)
            maybe_encrypt_existing_file(incoming)
            _confirm_restore(incoming, listing)

        ui.upload(
            on_upload=on_restore_upload,
            auto_upload=True,
            max_files=1,
        ).props('accept=".zip" label="Choose an AeroBooks backup zip"')

    @ui.refreshable
    def listing():
        rows = backup.list_backups()
        with ui.card().classes("ab-card p-5 w-full"):
            ui.label("Saved backups on this computer").classes("font-semibold")
            if not rows:
                ui.label("No backups yet. Click Save backup now.").classes("text-sm text-gray-600")
                return
            for row in rows:
                with ui.row().classes("items-center w-full py-2 border-b"):
                    with ui.column().classes("gap-0 flex-1"):
                        ui.label(row["name"]).classes("font-medium text-sm")
                        ui.label(f"{row['modified']}  ·  {_size_label(row['size'])}  ·  {row['folder']}").classes(
                            "text-xs text-gray-500"
                        )
                    ui.button(
                        "Restore",
                        on_click=lambda p=row["path"]: _confirm_restore(Path(p), listing),
                    ).props("outline dense")
                    ui.button(
                        "Open",
                        on_click=lambda p=row["path"]: backup.os_start(Path(p).parent),
                    ).props("flat dense")

    listing()


def _size_label(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _confirm_restore(zip_path: Path, listing) -> None:
    d = ui.dialog()
    with d, ui.card().classes("p-5 w-[520px]"):
        ui.label("Restore this backup?").classes("text-lg font-semibold")
        ui.label(str(zip_path)).classes("text-xs text-gray-500")
        ui.label(
            "Current data will be replaced. A safety copy is saved first in Documents\\AeroBooks Backups."
        ).classes("text-sm mt-2")

        def go():
            try:
                safety = backup.restore_from_zip(zip_path)
                d.close()
                msg = "Backup restored. Reload the page to see it."
                if safety:
                    msg += f" Safety copy: {safety.name}"
                ui.notify(msg, timeout=8000)
                listing.refresh()
                ui.navigate.reload()
            except Exception as err:
                ui.notify(str(err), type="negative", timeout=8000)

        with ui.row().classes("justify-end w-full gap-2 mt-3"):
            ui.button("Cancel", on_click=d.close).props("flat")
            ui.button("Restore backup", on_click=go).classes("ab-primary")
    d.open()
