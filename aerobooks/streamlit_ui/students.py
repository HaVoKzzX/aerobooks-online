"""Students, progress, notes, and balances."""

from __future__ import annotations

import streamlit as st

from aerobooks import auth, backup, db
from aerobooks.money import fmt_date, fmt_hours, fmt_money
from aerobooks.streamlit_ui import chrome


def render(user: dict) -> None:
    if st.session_state.get("pending_backup"):
        st.download_button(
            "Download backup made before delete",
            data=st.session_state.pending_backup,
            file_name=st.session_state.get("pending_backup_name") or "AeroBooks-backup.zip",
        )
    student_id = st.session_state.get("student_id")
    if student_id:
        _detail(int(student_id), user)
        return
    _list(user)


def _list(user: dict) -> None:
    chrome.page_title("Students", "People you train, their hours, and what they owe.")
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("Add student", type="primary", use_container_width=True):
            st.session_state.student_dialog = "new"
            st.rerun()

    is_manager = user.get("role") == "manager"
    filters = st.expander("Filters", expanded=True)
    with filters:
        f1, f2, f3 = st.columns(3)
        with f1:
            search = st.text_input("Search name, email, phone")
        with f2:
            status_opts = {
                "active": "Active",
                "all": "All statuses",
                "soloed": "Soloed",
                "checkride_ready": "Checkride ready",
                "graduated": "Graduated",
                "inactive": "Inactive",
            }
            status = st.selectbox("Status", list(status_opts), format_func=lambda k: status_opts[k])
        instructor_id = None
        with f3:
            if is_manager and user.get("tenant_id"):
                instructors = auth.instructor_options(int(user["tenant_id"]))
                labels = {"all": "All instructors"}
                labels.update({str(u["id"]): (u.get("display_name") or u["username"]) for u in instructors})
                picked = st.selectbox("Instructor", list(labels), format_func=lambda k: labels[k])
                if picked != "all":
                    instructor_id = int(picked)

    students = db.list_students(status=status, search=search or "", instructor_user_id=instructor_id)
    if not students:
        chrome.card_md("No students match this filter.")
        if st.button("Add your first student"):
            st.session_state.student_dialog = "new"
            st.rerun()
    else:
        for s in students:
            bits = [s.get("goal") or "—", f"{fmt_hours(s['total_hours'])} hr"]
            if s.get("unbilled_hours"):
                bits.append(f"{fmt_hours(s['unbilled_hours'])} unbilled")
            if s.get("owed"):
                bits.append(f"{fmt_money(s['owed'])} owed")
            if is_manager:
                bits.insert(0, s.get("instructor_name") or "—")
            st.markdown(
                f"<div class='ab-card'><div class='ab-row'>"
                f"<div><b>{s['full_name']}</b> {chrome.chip(s.get('status') or 'active')}"
                f"<div class='ab-sub'>{' · '.join(bits)} · last {fmt_date(s.get('last_session'))}</div></div>"
                f"</div></div>",
                unsafe_allow_html=True,
            )
            if st.button("Open", key=f"open-stu-{s['id']}", use_container_width=True):
                st.session_state.student_id = int(s["id"])
                st.rerun()

    if st.session_state.get("student_dialog") == "new":
        _student_dialog(user)


@st.dialog("Student", width="large")
def _student_dialog(user: dict, student: dict | None = None) -> None:
    user = user or {}
    if user.get("tenant_id"):
        from aerobooks import auth, paths

        auth.bind_user(user)
        paths.bind_tenant(int(user["tenant_id"]))
        db.init_db()
    data = dict(student or {})
    c1, c2 = st.columns(2)
    first = c1.text_input("First name", value=data.get("first_name") or "")
    last = c2.text_input("Last name", value=data.get("last_name") or "")
    email = c1.text_input("Email", value=data.get("email") or "")
    phone = c2.text_input("Phone", value=data.get("phone") or "")
    address = st.text_input("Address", value=data.get("address") or "")
    c3, c4, c5 = st.columns([2, 1, 1])
    city = c3.text_input("City", value=data.get("city") or "")
    state = c4.text_input("State", value=data.get("state") or "")
    zipc = c5.text_input("ZIP", value=data.get("zip") or "")
    d1, d2 = st.columns(2)
    level = d1.selectbox(
        "Certificate level",
        db.CERTIFICATE_LEVELS,
        index=_index(db.CERTIFICATE_LEVELS, data.get("certificate_level") or "Student"),
    )
    cert = d2.text_input("Certificate #", value=data.get("certificate_number") or "")
    goal = d1.selectbox(
        "Currently instructing",
        db.INSTRUCTION_TRACKS,
        index=_index(db.INSTRUCTION_TRACKS, data.get("goal") or "Private Pilot (PPL)"),
    )
    status = d2.selectbox(
        "Status",
        db.STUDENT_STATUSES,
        index=_index(db.STUDENT_STATUSES, data.get("status") or "active"),
    )
    medicals = ["None", "Student", "Third class", "Second class", "First class", "BasicMed"]
    medical = d1.selectbox("Medical", medicals, index=_index(medicals, data.get("medical_class") or "Third class"))
    medical_exp = d2.date_input(
        "Medical expires",
        value=_date_or_none(data.get("medical_expires")) or __import__("datetime").date.today(),
        format="YYYY-MM-DD",
    )
    airport = d1.text_input("Home airport", value=data.get("home_airport") or "")
    ac = d2.text_input("Usual aircraft", value=data.get("aircraft_preference") or "")
    notes = st.text_area("Standing notes", value=data.get("notes") or "")

    instructor_id = None
    if user.get("role") == "manager" and user.get("tenant_id"):
        options = {
            str(u["id"]): u.get("display_name") or u["username"]
            for u in auth.instructor_options(int(user["tenant_id"]))
        }
        current = str(data.get("instructor_user_id") or user.get("id") or "")
        keys = list(options)
        instructor_id = st.selectbox(
            "Assigned instructor",
            keys,
            index=keys.index(current) if current in options else 0,
            format_func=lambda k: options[k],
        )

    b1, b2 = st.columns(2)
    save = b1.button("Save", type="primary", use_container_width=True)
    cancel = b2.button("Cancel", use_container_width=True)
    if cancel:
        st.session_state.pop("student_dialog", None)
        st.rerun()
    if save:
        if not first.strip() or not last.strip():
            st.warning("First and last name are required")
            return
        payload = {
            "id": data.get("id"),
            "first_name": first.strip(),
            "last_name": last.strip(),
            "email": email,
            "phone": phone,
            "address": address,
            "city": city,
            "state": state,
            "zip": zipc,
            "certificate_level": level,
            "certificate_number": cert,
            "goal": goal,
            "status": status,
            "medical_class": medical,
            "medical_expires": medical_exp.isoformat() if medical_exp else "",
            "home_airport": airport,
            "aircraft_preference": ac,
            "notes": notes,
        }
        if instructor_id:
            payload["instructor_user_id"] = int(instructor_id)
        try:
            sid = db.save_student(payload)
        except Exception as err:
            st.error(f"Could not save student: {err}")
            return
        st.session_state.student_id = int(sid)
        st.session_state.pop("student_dialog", None)
        st.success("Student saved")
        st.rerun()

    if data.get("id"):
        if st.button("Delete student", type="secondary"):
            st.session_state.delete_student_id = int(data["id"])
            st.rerun()


def _detail(student_id: int, user: dict) -> None:
    student = db.get_student(student_id)
    if not student:
        st.warning("Student not found.")
        if st.button("Back"):
            st.session_state.pop("student_id", None)
            st.rerun()
        return

    if st.button("← Students"):
        st.session_state.pop("student_id", None)
        st.rerun()

    st.markdown(
        f'<p class="ab-h1">{student["full_name"]} {chrome.chip(student["status"])}</p>',
        unsafe_allow_html=True,
    )
    bits = [b for b in [student.get("goal"), student.get("certificate_level"), student.get("email"), student.get("phone")] if b]
    st.markdown(f'<p class="ab-sub">{" · ".join(bits)}</p>', unsafe_allow_html=True)

    a1, a2, a3 = st.columns(3)
    with a1:
        if st.button("Edit", use_container_width=True):
            st.session_state.student_dialog = f"edit-{student_id}"
            st.rerun()
    with a2:
        if st.button("Log hours", use_container_width=True):
            chrome.go("hours", hours_student=student_id)
    with a3:
        if st.button("Invoice", type="primary", use_container_width=True):
            chrome.go("invoices", invoice_new=True, invoice_id=None, invoice_student=student_id)

    chrome.stats_html(
        [
            ("Total hours", fmt_hours(student["total_hours"])),
            ("Unbilled", fmt_hours(student["unbilled_hours"]), fmt_money(student["unbilled_amount"])),
            ("Owed", fmt_money(student["owed"]), "Open invoice balance", "warn" if student["owed"] else ""),
            ("Paid", fmt_money(student["paid"])),
            ("Last lesson", fmt_date(student.get("last_session"))),
        ]
    )

    hours_map = student.get("hours_by_type") or {}
    if hours_map:
        st.markdown("**Hours by type**")
        chips = " ".join(
            f"<span class='ab-chip ab-status-partial'>{db.training_type_label(code)} {fmt_hours(hrs)}</span>"
            for code, hrs in sorted(hours_map.items(), key=lambda x: -x[1])
        )
        st.markdown(chips, unsafe_allow_html=True)

    pcol, ncol = st.columns(2)
    with pcol:
        st.markdown("**Progress**")
        st.caption("Certificate they already hold is under Edit. This list is only what you are teaching.")
        counts = db.track_progress_counts(student_id)
        track_options = []
        labels = {}
        for name in db.INSTRUCTION_TRACKS:
            track_options.append(name)
            if name in counts:
                done, total = counts[name]
                labels[name] = f"{name} ({done}/{total})"
            else:
                labels[name] = name
        current_track = db.resolve_track(student.get("goal") or "Private Pilot (PPL)")
        if current_track not in track_options:
            current_track = track_options[0]
        track = st.selectbox(
            "What are you instructing?",
            track_options,
            index=track_options.index(current_track),
            format_func=lambda n: labels.get(n, n),
        )
        if track != current_track:
            db.set_instruction_track(student_id, track)
            db.seed_milestones(student_id, track)
            st.rerun()
        db.seed_milestones(student_id, track)
        items = db.list_milestones(student_id, track)
        if not items:
            st.caption("No checklist for this training yet.")
            if st.button("Load checklist"):
                db.seed_milestones(student_id, track)
                st.rerun()
        for m in items:
            checked = st.checkbox(
                m["name"] + (f"  ·  {fmt_date(m['completed_date'])}" if m.get("completed_date") else ""),
                value=bool(m["completed"]),
                key=f"ms-{m['id']}",
            )
            if bool(checked) != bool(m["completed"]):
                db.set_milestone(m["id"], checked)
                st.rerun()
        new_m = st.text_input("Add a custom item", key=f"new-ms-{student_id}")
        if st.button("Add item") and new_m.strip():
            db.add_milestone(student_id, new_m, track)
            st.rerun()

    with ncol:
        st.markdown("**Notes**")
        note_body = st.text_area("Add a note", key=f"note-{student_id}")
        if st.button("Save note") and (note_body or "").strip():
            db.add_note(student_id, note_body)
            st.rerun()
        if student.get("notes"):
            chrome.alert(f"<b>Standing notes</b><br>{student['notes']}", gold=True)
        notes = db.list_notes(student_id)
        if not notes and not (student.get("notes") or "").strip():
            st.caption("No notes yet.")
        for n in notes:
            st.markdown(f":gray[{fmt_date(n['date'])} · {n['category']}]  \n{n['body']}")
            if st.button("Delete note", key=f"del-note-{n['id']}"):
                db.delete_note(n["id"])
                st.rerun()

    unbilled = db.list_sessions(student_id=student_id, unbilled_only=True, limit=100)
    if unbilled:
        st.markdown("**Unbilled training**")
        st.caption(f"{fmt_hours(student['unbilled_hours'])} hr · {fmt_money(student['unbilled_amount'])} ready to bill")
        if st.button("Invoice all unbilled", type="primary"):
            ids = [s["id"] for s in unbilled]
            chrome.go("invoices", invoice_new=True, invoice_id=None, invoice_student=student_id, invoice_sessions=ids)
        rows = [
            {
                "Date": fmt_date(s["date"]),
                "Type": db.training_type_label(s["training_type"]),
                "Hours": fmt_hours(s["hours"]),
                "Amount": fmt_money(s["line_amount"]),
                "Notes": s.get("notes") or s.get("description") or "",
            }
            for s in unbilled
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)

    st.markdown("**Training log**")
    sessions = db.list_sessions(student_id=student_id, limit=50)
    if not sessions:
        st.caption("No hours logged yet.")
    else:
        rows = [
            {
                "Date": fmt_date(s["date"]),
                "Type": db.training_type_label(s["training_type"]),
                "Hours": fmt_hours(s["hours"]),
                "Aircraft": s.get("aircraft") or "—",
                "Billing": "Billed" if s["billed"] else ("Unbilled" if s["billable"] else "Not billed"),
                "Notes": s.get("notes") or s.get("description") or "",
            }
            for s in sessions
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)

    st.markdown("**Invoices**")
    invoices = db.list_invoices(student_id=student_id)
    if not invoices:
        st.caption("No invoices for this student.")
    else:
        for inv in invoices:
            st.markdown(
                f"{inv['number']} · {fmt_date(inv['issue_date'])} · {fmt_money(inv['total'])} · "
                f"{chrome.chip(inv.get('display_status') or inv['status'])}",
                unsafe_allow_html=True,
            )
            if st.button("Open invoice", key=f"stu-inv-{inv['id']}"):
                chrome.go("invoices", invoice_id=int(inv["id"]), invoice_new=False)

    if st.session_state.get("student_dialog") == f"edit-{student_id}":
        _student_dialog(user, student)

    if st.session_state.get("delete_student_id") == student_id:
        _delete_confirm(student_id)


@st.dialog("Delete student?")
def _delete_confirm(student_id: int) -> None:
    info = db.student_delete_summary(student_id)
    st.session_state.pop("delete_student_id", None)
    st.write(f"Delete **{info['full_name']}**? This cannot be undone. It removes:")
    st.write(
        f"- {info['sessions']} training session(s) ({fmt_hours(info['hours'])} hours)\n"
        f"- {info['invoices']} invoice(s)\n"
        f"- {info['notes']} note(s), plus progress and contact info"
    )
    st.caption("Would you like to save a full backup of AeroBooks before continuing?")
    c1, c2, c3 = st.columns(3)
    if c1.button("Cancel"):
        st.rerun()
    if c2.button("Delete without backup"):
        db.delete_student(student_id)
        st.session_state.pop("student_id", None)
        st.rerun()
    if c3.button("Backup, then delete", type="primary"):
        dest = backup.create_backup_zip()
        st.session_state.pending_backup = dest.read_bytes()
        st.session_state.pending_backup_name = dest.name
        db.delete_student(student_id)
        st.session_state.pop("student_id", None)
        st.rerun()


def _index(options, value) -> int:
    try:
        return list(options).index(value)
    except ValueError:
        return 0


def _date_or_none(value):
    from datetime import date, datetime

    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
