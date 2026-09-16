"""Instructor / business identity, rates, Venmo, backups, and restore."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from aerobooks import auth, backup, db, paths
from aerobooks.money import fmt_money
from aerobooks.pdf_invoice import settings_qr_path
from aerobooks.store import decrypt_to_temp, maybe_encrypt_existing_file, secure_read
from aerobooks.streamlit_ui import chrome


def render(user: dict) -> None:
    s = db.get_settings()
    chrome.page_title("Settings", "This information prints on every invoice.")
    tabs = st.tabs(
        ["Identity", "Rates & products", "Venmo & invoices"]
        + (["Data"] if auth.can_backup(user) else [])
    )
    with tabs[0]:
        _identity(s, user)
    with tabs[1]:
        _rates(user)
    with tabs[2]:
        _pay(s, user)
    if auth.can_backup(user):
        with tabs[3]:
            _data(user)


def _identity(s: dict, user: dict) -> None:
    locked = bool(s.get("identity_locked") or user.get("role") == "school_instructor")
    if locked:
        chrome.alert(
            "Invoice business name, address, and school contact are set by the flight school manager "
            "and cannot be changed on instructor accounts.",
            gold=True,
        )
    entity = st.selectbox(
        "How invoices are headed",
        ["individual", "business"],
        index=0 if (s.get("entity_type") or "individual") == "individual" else 1,
        format_func=lambda v: "I invoice as myself (instructor name)" if v == "individual" else "I invoice as a business",
        disabled=locked,
    )
    business = st.text_input("Business name", value=s.get("business_name") or "", disabled=locked)
    instructor = st.text_input("Instructor name", value=s.get("instructor_name") or "")
    st.caption("If you invoice as a business, both names print: business on top, instructor underneath.")
    c1, c2 = st.columns(2)
    cfi = c1.text_input("CFI certificate #", value=s.get("cfi_number") or "")
    cfii = c2.text_input("CFII certificate #", value=s.get("cfii_number") or "")
    address = st.text_input("Street address", value=s.get("address") or "", disabled=locked)
    c3, c4, c5 = st.columns([2, 1, 1])
    city = c3.text_input("City", value=s.get("city") or "", disabled=locked)
    state = c4.text_input("State", value=s.get("state") or "", disabled=locked)
    zipc = c5.text_input("ZIP", value=s.get("zip") or "", disabled=locked)
    phone = c1.text_input("Phone", value=s.get("phone") or "", disabled=locked)
    email = c2.text_input("Email", value=s.get("email") or "", disabled=locked)
    web = c1.text_input("Website", value=s.get("website") or "", disabled=locked)
    airport = c2.text_input("Home airport", value=s.get("home_airport") or "", disabled=locked)
    if st.button("Save identity", type="primary"):
        db.save_settings(
            {
                "entity_type": entity,
                "business_name": business,
                "instructor_name": instructor,
                "cfi_number": cfi,
                "cfii_number": cfii,
                "address": address,
                "city": city,
                "state": state,
                "zip": zipc,
                "phone": phone,
                "email": email,
                "website": web,
                "home_airport": airport,
                "setup_complete": "1",
            }
        )
        st.success("Identity saved — it will appear on the next invoice")


def _rates(user: dict) -> None:
    st.markdown("**Training rates, products, and extra services**")
    st.caption("These fill in when you log hours and when you add lines to an invoice.")
    rates = db.list_rates()
    for r in rates:
        st.markdown(
            f"<div class='ab-card'><b>{r['name']}</b> · {fmt_money(r['price'])}/{r['unit']} "
            f"{chrome.chip('active' if r['is_active'] else 'inactive')}<br>"
            f"<span class='ab-sub'>{r['category']}</span></div>",
            unsafe_allow_html=True,
        )
        if auth.can_edit_rates(user) and st.button("Edit", key=f"rate-{r['id']}"):
            st.session_state.edit_rate = int(r["id"])
            st.rerun()
    if auth.can_edit_rates(user):
        if st.button("Add rate or product", type="primary"):
            st.session_state.edit_rate = 0
            st.rerun()
    else:
        st.caption("Rates are set by the flight school manager.")
    if "edit_rate" in st.session_state:
        rid = st.session_state.edit_rate
        _rate_dialog(None if rid == 0 else db.get_rate(int(rid)))


@st.dialog("Rate / product")
def _rate_dialog(rate: dict | None) -> None:
    data = dict(rate or {})
    cats = sorted({c for _, c, _, _, _, _ in db.DEFAULT_RATES} | {"product", "service", "other"})
    name = st.text_input("Name", value=data.get("name") or "")
    category = st.selectbox("Category", cats, index=_idx(cats, data.get("category") or "flight"))
    unit = st.selectbox("Unit", ["hour", "each", "flat"], index=_idx(["hour", "each", "flat"], data.get("unit") or "hour"))
    price = st.number_input("Price", min_value=0.0, value=float(data.get("price") or 0), format="%.2f")
    desc = st.text_area("Description", value=data.get("description") or "")
    active = st.checkbox("Active (show in pickers)", value=bool(data.get("is_active", 1)))
    c1, c2, c3 = st.columns(3)
    if c1.button("Cancel"):
        st.session_state.pop("edit_rate", None)
        st.rerun()
    if data.get("id") and c2.button("Delete"):
        db.delete_rate(int(data["id"]))
        st.session_state.pop("edit_rate", None)
        st.rerun()
    if c3.button("Save", type="primary"):
        if not (name or "").strip():
            st.warning("Name required")
        else:
            db.save_rate(
                {
                    "id": data.get("id"),
                    "name": name.strip(),
                    "category": category,
                    "unit": unit,
                    "price": price,
                    "description": desc,
                    "is_active": active,
                    "sort_order": data.get("sort_order") or 99,
                }
            )
            st.session_state.pop("edit_rate", None)
            st.rerun()


def _pay(s: dict, user: dict) -> None:
    locked = bool(s.get("identity_locked") or user.get("role") == "school_instructor")
    st.markdown("**Venmo**")
    st.caption("Enter the username people already pay you with (the part after venmo.com/).")
    venmo = st.text_input("Venmo username", value=s.get("venmo_username") or "")
    note = st.text_input("Payment note prefix", value=s.get("venmo_note_prefix") or "Flight training")
    uploaded = st.file_uploader("Optional custom Venmo QR image", type=["png", "jpg", "jpeg"])
    if uploaded:
        dest = db.QR_DIR / "custom_venmo_qr.png"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(uploaded.getvalue())
        maybe_encrypt_existing_file(dest)
        db.set_setting("custom_qr_path", str(dest))
        st.success("Custom QR saved")
    if st.button("Clear custom QR (use generated)"):
        db.set_setting("custom_qr_path", "")
        st.rerun()
    if st.button("Save Venmo", type="primary"):
        db.save_settings(
            {
                "venmo_username": (venmo or "").lstrip("@").strip(),
                "venmo_note_prefix": note,
            }
        )
        st.success("Venmo settings saved")
        st.rerun()
    path = settings_qr_path()
    username = db.get_setting("venmo_username")
    if path and path.exists():
        st.caption(f"QR preview for @{username}" if username else "Custom Venmo QR")
        st.image(decrypt_to_temp(path), width=160)
    elif username:
        st.caption("Save to generate a preview.")
    else:
        st.warning("No Venmo username yet — invoices will omit the QR until you add one.")

    st.markdown("**Invoice defaults**")
    if locked:
        chrome.alert("Invoice numbering, terms, and tax are set by the flight school manager.", gold=True)
    prefix = st.text_input("Invoice number prefix", value=s.get("invoice_prefix") or "INV", disabled=locked)
    nxt = st.text_input("Next invoice number", value=s.get("next_invoice_number") or "1001", disabled=locked)
    terms_days = st.number_input(
        "Payment terms (days)", min_value=0, value=int(s.get("payment_terms_days") or 30), disabled=locked
    )
    tax_on = st.checkbox("Add tax to invoices", value=s.get("tax_enabled") == "1", disabled=locked)
    tax_rate = st.number_input("Tax rate %", min_value=0.0, value=float(s.get("tax_rate") or 0), format="%.3f", disabled=locked)
    tax_label = st.text_input("Tax label", value=s.get("tax_label") or "Sales tax", disabled=locked)
    footer = st.text_area("Default invoice terms / footer", value=s.get("invoice_footer") or "", disabled=locked)
    if not locked and st.button("Save invoice defaults", type="primary"):
        db.save_settings(
            {
                "invoice_prefix": prefix,
                "next_invoice_number": nxt,
                "payment_terms_days": str(int(terms_days or 30)),
                "tax_enabled": "1" if tax_on else "0",
                "tax_rate": str(tax_rate or 0),
                "tax_label": tax_label,
                "invoice_footer": footer,
            }
        )
        st.success("Invoice defaults saved")


def _data(user: dict) -> None:
    st.markdown("**Switch from desktop AeroBooks**")
    st.caption(
        "Upload a backup zip from the original AeroBooks program, or pick one already in "
        "Documents\\AeroBooks Backups. Students, hours, invoices, and settings come across. "
        "The zip you download from here also restores in the original desktop app."
    )
    desktop = paths.original_desktop_backup_dir()
    st.write(f"Desktop backup folder: `{desktop}`")

    uploaded = st.file_uploader("Choose an AeroBooks backup zip", type=["zip"])
    if uploaded and st.button("Restore uploaded backup", type="primary"):
        incoming = paths.local_backup_dir() / "incoming-restore.zip"
        incoming.parent.mkdir(parents=True, exist_ok=True)
        incoming.write_bytes(uploaded.getvalue())
        maybe_encrypt_existing_file(incoming)
        try:
            safety = backup.restore_from_zip(incoming)
            msg = "Backup restored."
            if safety:
                msg += f" Safety copy: {safety.name}"
            st.success(msg)
            st.rerun()
        except Exception as err:
            st.error(str(err))

    st.markdown("**Save a backup**")
    st.caption(
        "Creates the same zip the desktop app uses: students, hours, invoices, payments, "
        "expenses, settings, rates, invoice PDFs, and Venmo QR codes."
    )
    if st.button("Save backup now", type="primary"):
        dest = backup.create_backup_zip()
        st.session_state.backup_download = dest
        st.success(f"Backup saved to {dest}")
    dest = st.session_state.get("backup_download")
    if dest:
        path = Path(dest)
        if path.exists():
            st.download_button(
                "Download backup zip",
                data=secure_read(path) if _maybe_enc(path) else path.read_bytes(),
                file_name=path.name,
                mime="application/zip",
            )

    st.markdown("**Saved backups**")
    rows = backup.list_backups()
    if not rows:
        st.caption("No backups yet. Click Save backup now, or copy a zip from the original AeroBooks.")
    for row in rows:
        st.markdown(
            f"<div class='ab-card'><b>{row['name']}</b> · {row.get('source') or ''}<br>"
            f"<span class='ab-sub'>{row['modified']} · {_size_label(row['size'])} · {row['folder']}</span></div>",
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns(2)
        if c1.button("Restore", key=f"rst-{row['path']}"):
            try:
                backup.restore_from_zip(Path(row["path"]))
                st.success("Backup restored.")
                st.rerun()
            except Exception as err:
                st.error(str(err))
        try:
            payload = secure_read(Path(row["path"]))
        except Exception:
            payload = Path(row["path"]).read_bytes()
        c2.download_button("Download", data=payload, file_name=row["name"], key=f"dl-{row['path']}")

    with st.expander("Where files live on this server"):
        st.write(f"Data folder: `{paths.data_dir()}`")
        st.write(f"Database (encrypted): `{paths.db_path()}.enc`")
        st.write(f"Invoice PDFs: `{paths.invoice_dir()}`")
        st.write(f"Backups: `{paths.documents_backup_dir()}`")
        st.caption("Databases, PDFs, QR codes, and server-side backups are encrypted with AES-256-GCM.")


def _maybe_enc(path: Path) -> bool:
    from aerobooks.crypto import is_encrypted

    try:
        return is_encrypted(path.read_bytes()[:16])
    except Exception:
        return False


def _size_label(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def _idx(options, value) -> int:
    try:
        return list(options).index(value)
    except ValueError:
        return 0
