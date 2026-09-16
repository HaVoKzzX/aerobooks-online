"""SQLite data layer for AeroBooks."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from aerobooks import paths
from aerobooks.money import D, hours, iso_today, money, parse_date

APP_DIR = paths.install_dir()
DATA_DIR = paths.data_dir()
INVOICE_DIR = paths.invoice_dir()
QR_DIR = paths.qr_dir()
BACKUP_DIR = paths.local_backup_dir()
DB_PATH = paths.db_path()

DEFAULT_SETTINGS = {
    "entity_type": "individual",
    "business_name": "",
    "instructor_name": "",
    "cfi_number": "",
    "cfii_number": "",
    "address": "",
    "city": "",
    "state": "",
    "zip": "",
    "phone": "",
    "email": "",
    "website": "",
    "home_airport": "",
    "venmo_username": "",
    "venmo_note_prefix": "Flight training",
    "custom_qr_path": "",
    "invoice_prefix": "INV",
    "next_invoice_number": "1001",
    "payment_terms_days": "30",
    "invoice_footer": "Thank you for flying with me. Payment is due within 30 days of the invoice date.",
    "tax_enabled": "0",
    "tax_rate": "0",
    "tax_label": "Sales tax",
    "setup_complete": "0",
}

DEFAULT_RATES = [
    ("Dual Flight Instruction", "flight", "hour", 70.00, "Aircraft dual given (ASEL/ASES)", 1),
    ("Ground Instruction", "ground", "hour", 50.00, "One-on-one or classroom ground school", 2),
    ("Instrument Training", "instrument", "hour", 75.00, "Instrument instruction in aircraft (actual or simulated IMC)", 3),
    ("Simulator Training", "simulator", "hour", 55.00, "AATD, FTD, BATD, or aviation training device", 4),
    ("Pre / Post Flight Briefing", "briefing", "hour", 50.00, "Oral briefing associated with a lesson", 5),
    ("Night Training", "flight", "hour", 75.00, "Night dual instruction", 6),
    ("Cross-Country Dual", "flight", "hour", 70.00, "Dual cross-country instruction", 7),
    ("Complex / High Performance", "flight", "hour", 85.00, "Complex or high-performance dual", 8),
    ("Tailwheel Instruction", "flight", "hour", 80.00, "Tailwheel dual given", 9),
    ("Multi-Engine Instruction", "flight", "hour", 90.00, "Multi-engine dual given", 10),
    ("Spin Training", "flight", "hour", 85.00, "Spin awareness / spin training", 11),
    ("Stage Check", "flight", "hour", 80.00, "Stage or progress check", 12),
    ("Checkride Prep", "flight", "hour", 80.00, "Practical test preparation", 13),
    ("Flight Review (BFR)", "flight", "hour", 75.00, "14 CFR 61.56 flight review", 14),
    ("Instrument Proficiency Check", "instrument", "hour", 80.00, "14 CFR 61.57 IPC", 15),
    ("Written Test Prep", "ground", "hour", 50.00, "Knowledge test preparation", 16),
    ("Endorsement", "service", "each", 25.00, "Logbook endorsement", 17),
    ("Discovery Flight Instruction", "flight", "flat", 150.00, "Introductory flight instruction portion", 18),
    ("Materials / Supplies", "product", "each", 0.00, "Books, charts, supplies — set the price on the invoice", 19),
    ("Aircraft Rental (pass-through)", "product", "hour", 0.00, "Aircraft time billed through to the student", 20),
]

TRAINING_TYPES = [
    ("flight", "Flight Training"),
    ("ground", "Ground Training"),
    ("instrument", "Instrument Training"),
    ("simulator", "Simulator Training"),
    ("briefing", "Pre / Post Briefing"),
    ("night", "Night Training"),
    ("cross_country", "Cross-Country Dual"),
    ("complex", "Complex / High Performance"),
    ("tailwheel", "Tailwheel"),
    ("multi", "Multi-Engine"),
    ("spin", "Spin Training"),
    ("stage_check", "Stage Check"),
    ("checkride_prep", "Checkride Prep"),
    ("flight_review", "Flight Review (BFR)"),
    ("ipc", "Instrument Proficiency Check"),
    ("written_prep", "Written Test Prep"),
    ("endorsement", "Endorsement"),
    ("other", "Other Training"),
]

TYPE_TO_RATE_NAME = {
    "flight": "Dual Flight Instruction",
    "ground": "Ground Instruction",
    "instrument": "Instrument Training",
    "simulator": "Simulator Training",
    "briefing": "Pre / Post Flight Briefing",
    "night": "Night Training",
    "cross_country": "Cross-Country Dual",
    "complex": "Complex / High Performance",
    "tailwheel": "Tailwheel Instruction",
    "multi": "Multi-Engine Instruction",
    "spin": "Spin Training",
    "stage_check": "Stage Check",
    "checkride_prep": "Checkride Prep",
    "flight_review": "Flight Review (BFR)",
    "ipc": "Instrument Proficiency Check",
    "written_prep": "Written Test Prep",
    "endorsement": "Endorsement",
}

CERTIFICATE_LEVELS = [
    "Student",
    "Sport",
    "Recreational",
    "Private",
    "Instrument",
    "Commercial",
    "Multi-Engine",
    "CFI",
    "CFII",
    "MEI",
    "ATP",
    "Other",
]

INSTRUCTION_TRACKS = [
    "Private Pilot (PPL)",
    "Sport Pilot",
    "Recreational Pilot",
    "Instrument Rating (IR)",
    "Commercial Pilot (CPL)",
    "Multi-Engine Rating",
    "CFI",
    "CFII",
    "MEI",
    "Flight Review (BFR)",
    "Instrument Proficiency Check (IPC)",
    "Checkride prep only",
    "Tailwheel",
    "High Performance",
    "Complex",
    "High Altitude",
    "Pressurized",
    "Spin training",
    "Solo endorsements",
    "Night",
    "Cross-country",
    "Proficiency / Currency",
    "Discovery / intro",
    "Other",
]
GOALS = INSTRUCTION_TRACKS  # older name used in a few places

STUDENT_STATUSES = ["active", "soloed", "checkride_ready", "graduated", "inactive"]

INVOICE_STATUSES = ["draft", "unpaid", "partial", "paid", "void"]

PAYMENT_METHODS = ["Venmo", "Cash", "Check", "Card", "Zelle", "Bank transfer", "Other"]

EXPENSE_CATEGORIES = [
    "Aircraft rental",
    "Fuel",
    "Oil / maintenance",
    "Hangar / tie-down",
    "Simulator rental",
    "Charts / ForeFlight / iPad",
    "Training supplies",
    "Insurance",
    "Medical / FAA fees",
    "Travel",
    "Office / software",
    "Other",
]

MILESTONES = {
    "Private Pilot (PPL)": [
        "TSA / citizenship or Flight School Candidate",
        "Pre-solo knowledge & first solo",
        "Dual cross-country",
        "Solo cross-country (short)",
        "Solo cross-country (long / 150 nm)",
        "Night dual + 10 takeoffs/landings",
        "3 hours instrument dual",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Sport Pilot": [
        "Training start",
        "Pre-solo / first solo",
        "Cross-country dual",
        "Solo cross-country",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Recreational Pilot": [
        "Training start",
        "Pre-solo / first solo",
        "Dual and solo requirements",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Instrument Rating (IR)": [
        "Instrument ground complete",
        "Holding / intercepting / tracking",
        "Precision approaches",
        "Non-precision approaches",
        "IFR cross-country",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Commercial Pilot (CPL)": [
        "Commercial maneuvers introduced",
        "Solo / PIC cross-country (long)",
        "Complex or TAA time",
        "Commercial ground complete",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "CFI": [
        "FOI / CFI written",
        "Right-seat proficiency",
        "Spin training / endorsement",
        "Lesson plans complete",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "CFII": [
        "Instrument teaching from the right seat",
        "Approaches as instructor",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "MEI": [
        "Engine-out / Vmc from the right seat",
        "Multi teaching proficiency",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Multi-Engine Rating": [
        "Vmc / engine-out intro",
        "Multi maneuvers proficient",
        "Practical test endorsement",
        "Checkride passed",
    ],
    "Flight Review (BFR)": [
        "Ground portion (61.56)",
        "Flight portion",
        "Flight review endorsement given",
    ],
    "Instrument Proficiency Check (IPC)": [
        "Holds",
        "Approaches",
        "Unusual attitudes / intercepting",
        "IPC endorsement given",
    ],
    "Checkride prep only": [
        "ACS / PTS reviewed",
        "Weak areas identified",
        "Mock oral",
        "Mock flight",
        "Ready for examiner",
    ],
    "Tailwheel": [
        "Ground: tailwheel handling / weathervane / bounce",
        "3-point landings",
        "Wheel landings",
        "Go-arounds / directional control",
        "61.31(i) tailwheel endorsement given",
    ],
    "High Performance": [
        "Ground: HP systems / performance / mixture",
        "Dual in high-performance airplane",
        "61.31(f) high-performance endorsement given",
    ],
    "Complex": [
        "Ground: propeller, gear, flaps / failures",
        "Dual in complex airplane",
        "61.31(e) complex endorsement given",
    ],
    "High Altitude": [
        "Ground: hypoxia, pressurization, high-alt weather",
        "Training flight if required",
        "61.31(g) high-altitude endorsement given",
    ],
    "Pressurized": [
        "Pressurization / emergency descent ground",
        "Training as required",
        "Endorsement given",
    ],
    "Spin training": [
        "Spin awareness ground",
        "Incipient / developed spins",
        "Recoveries",
        "Spin endorsement given",
    ],
    "Solo endorsements": [
        "Pre-solo knowledge test",
        "Pre-solo flight training (61.87)",
        "Initial solo endorsement given",
        "90-day solo endorsement (if needed)",
        "Solo XC / airport endorsements (if needed)",
    ],
    "Night": [
        "Night dual",
        "Night takeoffs and landings",
        "Night XC (if part of this training)",
        "Night endorsement / logbook entry",
    ],
    "Cross-country": [
        "XC planning / nav dual",
        "Dual XC complete",
        "Solo XC endorsements (if applicable)",
        "Long XC (if applicable)",
    ],
    "Proficiency / Currency": [
        "Training start / goal noted",
        "Maneuvers / approaches practiced",
        "Currency or comfort goal met",
    ],
    "Discovery / intro": [
        "Intro flight complete",
        "Follow-up / enroll if they continue",
    ],
    "Other": [
        "Training start",
        "Progress check",
        "Complete",
    ],
}

# Older saved names still map to a checklist
_MILESTONE_ALIASES = {
    "Flight Review": "Flight Review (BFR)",
    "IPC": "Instrument Proficiency Check (IPC)",
}


def _ensure_dirs() -> None:
    paths.ensure_data_dirs()
    # Re-bind in case tests/env changed the data folder after import.
    global DATA_DIR, INVOICE_DIR, QR_DIR, BACKUP_DIR, DB_PATH, APP_DIR
    APP_DIR = paths.install_dir()
    DATA_DIR = paths.data_dir()
    INVOICE_DIR = paths.invoice_dir()
    QR_DIR = paths.qr_dir()
    BACKUP_DIR = paths.local_backup_dir()
    DB_PATH = paths.db_path()


@contextmanager
def get_conn():
    _ensure_dirs()
    from aerobooks.store import encrypted_db

    with encrypted_db(DB_PATH) as conn:
        _ensure_schema(conn)
        yield conn


def _row(r) -> dict | None:
    return dict(r) if r is not None else None


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


LOCKED_IDENTITY_KEYS = {
    "entity_type",
    "business_name",
    "address",
    "city",
    "state",
    "zip",
    "website",
    "home_airport",
    "invoice_prefix",
    "payment_terms_days",
    "invoice_footer",
    "tax_enabled",
    "tax_rate",
    "tax_label",
    "phone",
    "email",
    "custom_qr_path",
}

def _current_user() -> dict | None:
    try:
        from aerobooks import auth

        return auth.current_user()
    except Exception:
        return None


def _instructor_clause(alias: str = "") -> tuple[str, list]:
    user = _current_user()
    if not user or user.get("role") != "school_instructor":
        return "", []
    col = f"{alias}.instructor_user_id" if alias else "instructor_user_id"
    return f" AND {col} = ?", [int(user["id"])]


def _visible_student_ids_sql() -> tuple[str, list]:
    user = _current_user()
    if user and user.get("role") == "school_instructor":
        return "SELECT id FROM students WHERE instructor_user_id = ?", [int(user["id"])]
    return "SELECT id FROM students", []


def _can_see_student_row(student: dict | None) -> bool:
    if not student:
        return False
    user = _current_user()
    if not user:
        return True
    if user.get("role") != "school_instructor":
        return True
    return int(student.get("instructor_user_id") or 0) == int(user["id"])


def _assert_student_access(student_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, instructor_user_id FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    if not row:
        raise ValueError("Student not found")
    if not _can_see_student_row(dict(row)):
        raise PermissionError("You do not have access to this student")


def _assert_can_edit_rates() -> None:
    user = _current_user()
    if user and user.get("role") == "school_instructor":
        raise PermissionError("Training rates are set by the flight school manager.")


def _add_column(cursor, table: str, column: str, decl: str) -> None:
    cols = {r["name"] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _ensure_schema(conn) -> None:
    c = conn.cursor()
    c.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT 'hour',
                price REAL NOT NULL DEFAULT 0,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                certificate_level TEXT,
                certificate_number TEXT,
                medical_class TEXT,
                medical_expires TEXT,
                goal TEXT,
                home_airport TEXT,
                aircraft_preference TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT,
                instructor_user_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                completed_date TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                track TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'training',
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                training_type TEXT NOT NULL,
                hours REAL NOT NULL DEFAULT 0,
                aircraft TEXT,
                airport TEXT,
                rate_id INTEGER,
                rate_amount REAL NOT NULL DEFAULT 0,
                billable INTEGER NOT NULL DEFAULT 1,
                billed INTEGER NOT NULL DEFAULT 0,
                invoice_id INTEGER,
                description TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY (rate_id) REFERENCES rates(id) ON DELETE SET NULL,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                number TEXT NOT NULL UNIQUE,
                student_id INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                subtotal REAL NOT NULL DEFAULT 0,
                discount_type TEXT NOT NULL DEFAULT 'none',
                discount_value REAL NOT NULL DEFAULT 0,
                discount_amount REAL NOT NULL DEFAULT 0,
                tax_rate REAL NOT NULL DEFAULT 0,
                tax_amount REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                amount_paid REAL NOT NULL DEFAULT 0,
                balance REAL NOT NULL DEFAULT 0,
                notes TEXT,
                terms TEXT,
                include_venmo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id)
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                session_id INTEGER,
                rate_id INTEGER,
                description TEXT NOT NULL,
                category TEXT,
                quantity REAL NOT NULL DEFAULT 1,
                unit TEXT NOT NULL DEFAULT 'hour',
                unit_price REAL NOT NULL DEFAULT 0,
                amount REAL NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL,
                FOREIGN KEY (rate_id) REFERENCES rates(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL DEFAULT 'Venmo',
                reference TEXT,
                notes TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                vendor TEXT,
                student_id INTEGER,
                reimbursable INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
            );
            """
    )
    for key, value in DEFAULT_SETTINGS.items():
        c.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    existing_rates = c.execute("SELECT COUNT(*) FROM rates").fetchone()[0]
    if existing_rates == 0:
        for name, category, unit, price, description, order in DEFAULT_RATES:
            c.execute(
                """
                INSERT INTO rates (name, category, unit, price, description, is_active, sort_order)
                VALUES (?, ?, ?, ?, ?, 1, ?)
                """,
                (name, category, unit, price, description, order),
            )
    cols = {r["name"] for r in c.execute("PRAGMA table_info(milestones)").fetchall()}
    if "track" not in cols:
        c.execute("ALTER TABLE milestones ADD COLUMN track TEXT")
    _add_column(c, "students", "instructor_user_id", "INTEGER")
    _add_column(c, "expenses", "owner_user_id", "INTEGER")
    c.execute(
        """
        UPDATE milestones
        SET track = (
            SELECT CASE
                WHEN students.goal = 'Flight Review' THEN 'Flight Review (BFR)'
                WHEN students.goal = 'IPC' THEN 'Instrument Proficiency Check (IPC)'
                ELSE COALESCE(students.goal, 'Other')
            END
            FROM students WHERE students.id = milestones.student_id
        )
        WHERE track IS NULL OR track = ''
        """
    )


def init_db() -> None:
    _ensure_dirs()
    with get_conn() as _conn:
        pass
    from aerobooks.store import encrypt_tree

    encrypt_tree(INVOICE_DIR)
    encrypt_tree(QR_DIR)
    encrypt_tree(BACKUP_DIR)


def adopt_unassigned_records(user_id: int | None) -> None:
    """After restoring a desktop backup, attach students to the signed-in instructor."""
    if not user_id:
        return
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE students
            SET instructor_user_id = ?
            WHERE instructor_user_id IS NULL OR instructor_user_id = '' OR instructor_user_id = 0
            """,
            (int(user_id),),
        )


def resolve_track(name: str | None) -> str:
    raw = (name or "").strip() or "Other"
    return _MILESTONE_ALIASES.get(raw, raw)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_settings() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    data = dict(DEFAULT_SETTINGS)
    data.update({r["key"]: r["value"] for r in rows})
    user = _current_user()
    if user and user.get("role") == "school_instructor":
        data["entity_type"] = "business"
        data["identity_locked"] = True
        if user.get("display_name"):
            data["instructor_name"] = user["display_name"]
        data["cfi_number"] = user.get("cfi_number") or ""
        data["cfii_number"] = user.get("cfii_number") or ""
        if user.get("venmo_username"):
            data["venmo_username"] = user["venmo_username"]
        if user.get("venmo_note_prefix"):
            data["venmo_note_prefix"] = user["venmo_note_prefix"]
    else:
        data["identity_locked"] = False
    return data


def get_setting(key: str, default: str = "") -> str:
    return get_settings().get(key, DEFAULT_SETTINGS.get(key, default)) or default


def set_setting(key: str, value) -> None:
    save_settings({key: value})


def save_settings(values: dict) -> None:
    user = _current_user()
    to_store = dict(values)
    if user and user.get("role") == "school_instructor":
        from aerobooks import auth

        profile = {}
        if "instructor_name" in to_store:
            profile["display_name"] = to_store.pop("instructor_name")
        if "cfi_number" in to_store:
            profile["cfi_number"] = to_store.pop("cfi_number")
        if "cfii_number" in to_store:
            profile["cfii_number"] = to_store.pop("cfii_number")
        if "venmo_username" in to_store:
            profile["venmo_username"] = to_store.pop("venmo_username")
        if "venmo_note_prefix" in to_store:
            profile["venmo_note_prefix"] = to_store.pop("venmo_note_prefix")
        if profile:
            auth.update_profile(int(user["id"]), profile)
        for locked in LOCKED_IDENTITY_KEYS:
            to_store.pop(locked, None)
        to_store.pop("setup_complete", None)
    if not to_store:
        return
    with get_conn() as conn:
        for key, value in to_store.items():
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, "" if value is None else str(value)),
            )


def display_name() -> str:
    s = get_settings()
    if s.get("entity_type") == "business" and s.get("business_name"):
        return s["business_name"]
    return s.get("instructor_name") or "AeroBooks"


def instructor_display() -> str:
    s = get_settings()
    return s.get("instructor_name") or s.get("business_name") or "Instructor"


def is_setup_complete() -> bool:
    s = get_settings()
    return bool(s.get("instructor_name") or s.get("business_name"))


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------

def list_rates(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM rates"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY sort_order, name"
    with get_conn() as conn:
        return _rows(conn.execute(sql))


def get_rate(rate_id: int) -> dict | None:
    with get_conn() as conn:
        return _row(conn.execute("SELECT * FROM rates WHERE id = ?", (rate_id,)).fetchone())


def find_rate_for_type(training_type: str) -> dict | None:
    name = TYPE_TO_RATE_NAME.get(training_type)
    with get_conn() as conn:
        if name:
            row = conn.execute(
                "SELECT * FROM rates WHERE name = ? AND is_active = 1", (name,)
            ).fetchone()
            if row:
                return _row(row)
        row = conn.execute(
            "SELECT * FROM rates WHERE category = ? AND is_active = 1 ORDER BY sort_order LIMIT 1",
            (training_type,),
        ).fetchone()
        return _row(row)


def save_rate(data: dict) -> int:
    _assert_can_edit_rates()
    with get_conn() as conn:
        if data.get("id"):
            conn.execute(
                """
                UPDATE rates
                SET name=?, category=?, unit=?, price=?, description=?, is_active=?, sort_order=?
                WHERE id=?
                """,
                (
                    data["name"],
                    data["category"],
                    data["unit"],
                    money(data.get("price")),
                    data.get("description") or "",
                    1 if data.get("is_active", True) else 0,
                    int(data.get("sort_order") or 0),
                    data["id"],
                ),
            )
            return int(data["id"])
        cur = conn.execute(
            """
            INSERT INTO rates (name, category, unit, price, description, is_active, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["category"],
                data.get("unit") or "hour",
                money(data.get("price")),
                data.get("description") or "",
                1 if data.get("is_active", True) else 0,
                int(data.get("sort_order") or 99),
            ),
        )
        return int(cur.lastrowid)


def delete_rate(rate_id: int) -> None:
    _assert_can_edit_rates()
    with get_conn() as conn:
        conn.execute("DELETE FROM rates WHERE id = ?", (rate_id,))


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

def list_students(status: str | None = None, search: str = "", instructor_user_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM students WHERE 1=1"
    params: list = []
    clause, clause_params = _instructor_clause()
    sql += clause
    params.extend(clause_params)
    if instructor_user_id and not clause:
        sql += " AND instructor_user_id = ?"
        params.append(int(instructor_user_id))
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    if search:
        like = f"%{search.strip()}%"
        sql += " AND (first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR phone LIKE ?)"
        params.extend([like, like, like, like])
    sql += " ORDER BY last_name, first_name"
    with get_conn() as conn:
        students = _rows(conn.execute(sql, params))
    for s in students:
        _attach_student_summary(s)
    return students


def get_student(student_id: int) -> dict | None:
    with get_conn() as conn:
        student = _row(conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone())
    if student and _can_see_student_row(student):
        _attach_student_summary(student)
        return student
    return None


def _attach_student_summary(student: dict) -> None:
    sid = student["id"]
    with get_conn() as conn:
        hours_rows = _rows(
            conn.execute(
                """
                SELECT training_type, SUM(hours) AS hours
                FROM sessions WHERE student_id = ?
                GROUP BY training_type
                """,
                (sid,),
            )
        )
        totals = conn.execute(
            """
            SELECT
                COALESCE(SUM(hours), 0) AS total_hours,
                COALESCE(SUM(CASE WHEN billable = 1 AND billed = 0 THEN hours ELSE 0 END), 0) AS unbilled_hours,
                COALESCE(SUM(CASE WHEN billable = 1 AND billed = 0 THEN hours * rate_amount ELSE 0 END), 0) AS unbilled_amount
            FROM sessions WHERE student_id = ?
            """,
            (sid,),
        ).fetchone()
        last = conn.execute(
            "SELECT MAX(date) AS last_date FROM sessions WHERE student_id = ?",
            (sid,),
        ).fetchone()
        owed = conn.execute(
            """
            SELECT COALESCE(SUM(balance), 0) AS owed
            FROM invoices
            WHERE student_id = ? AND status NOT IN ('void', 'draft')
            """,
            (sid,),
        ).fetchone()
        paid = conn.execute(
            """
            SELECT COALESCE(SUM(amount_paid), 0) AS paid
            FROM invoices
            WHERE student_id = ? AND status NOT IN ('void')
            """,
            (sid,),
        ).fetchone()
    student["hours_by_type"] = {r["training_type"]: r["hours"] for r in hours_rows}
    student["total_hours"] = hours(totals["total_hours"])
    student["unbilled_hours"] = hours(totals["unbilled_hours"])
    student["unbilled_amount"] = money(totals["unbilled_amount"])
    student["last_session"] = last["last_date"]
    student["owed"] = money(owed["owed"])
    student["paid"] = money(paid["paid"])
    student["full_name"] = f"{student['first_name']} {student['last_name']}".strip()
    student["instructor_name"] = ""
    iid = student.get("instructor_user_id")
    if iid:
        try:
            from aerobooks import auth

            instructor = auth.get_user(int(iid))
            if instructor:
                student["instructor_name"] = instructor.get("display_name") or instructor.get("username") or ""
        except Exception:
            pass


def save_student(data: dict) -> int:
    init_db()
    now = iso_today()
    user = _current_user()
    fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip",
        "certificate_level",
        "certificate_number",
        "medical_class",
        "medical_expires",
        "goal",
        "home_airport",
        "aircraft_preference",
        "status",
        "notes",
        "instructor_user_id",
    ]
    instructor_id = data.get("instructor_user_id")
    if user and user.get("role") == "school_instructor":
        instructor_id = user["id"]
    elif instructor_id in (None, "", 0, "0"):
        instructor_id = user["id"] if user else None
    payload = dict(data)
    payload["instructor_user_id"] = int(instructor_id) if instructor_id else None
    values = [payload.get(f) or "" for f in fields]
    values[-1] = payload["instructor_user_id"]
    if not values[-3]:
        values[-3] = "active"
    with get_conn() as conn:
        if data.get("id"):
            _assert_student_access(int(data["id"]))
            sets = ", ".join(f"{f}=?" for f in fields)
            conn.execute(
                f"UPDATE students SET {sets}, updated_at=? WHERE id=?",
                (*values, now, data["id"]),
            )
            return int(data["id"])
        cur = conn.execute(
            f"""
            INSERT INTO students ({", ".join(fields)}, created_at, updated_at)
            VALUES ({", ".join("?" for _ in fields)}, ?, ?)
            """,
            (*values, now, now),
        )
        student_id = int(cur.lastrowid)
    seed_milestones(student_id, data.get("goal") or "")
    return student_id


def student_delete_summary(student_id: int) -> dict:
    _assert_student_access(student_id)
    with get_conn() as conn:
        student = _row(conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone())
        if not student:
            raise ValueError("Student not found")
        sessions = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(hours), 0) AS hours FROM sessions WHERE student_id = ?",
            (student_id,),
        ).fetchone()
        invoices = conn.execute(
            "SELECT COUNT(*) AS n FROM invoices WHERE student_id = ? AND status != 'void'",
            (student_id,),
        ).fetchone()[0]
        notes = conn.execute(
            "SELECT COUNT(*) AS n FROM notes WHERE student_id = ?", (student_id,)
        ).fetchone()[0]
    return {
        "id": student_id,
        "full_name": f"{student['first_name']} {student['last_name']}".strip(),
        "sessions": sessions["n"] or 0,
        "hours": hours(sessions["hours"]),
        "invoices": invoices or 0,
        "notes": notes or 0,
    }


def delete_student(student_id: int) -> None:
    """Remove a student and all of their training records and invoices."""
    _assert_student_access(student_id)
    with get_conn() as conn:
        exists = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if not exists:
            raise ValueError("Student not found")
        invoice_ids = [
            r["id"]
            for r in conn.execute("SELECT id FROM invoices WHERE student_id = ?", (student_id,)).fetchall()
        ]
        if invoice_ids:
            placeholders = ",".join("?" * len(invoice_ids))
            conn.execute(
                f"UPDATE sessions SET billed = 0, invoice_id = NULL WHERE invoice_id IN ({placeholders})",
                invoice_ids,
            )
            conn.execute(f"DELETE FROM payments WHERE invoice_id IN ({placeholders})", invoice_ids)
            conn.execute(f"DELETE FROM invoice_items WHERE invoice_id IN ({placeholders})", invoice_ids)
            conn.execute(f"DELETE FROM invoices WHERE id IN ({placeholders})", invoice_ids)
        conn.execute("UPDATE expenses SET student_id = NULL WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


def student_options() -> list[dict]:
    sql = "SELECT id, first_name, last_name, status FROM students WHERE 1=1"
    clause, params = _instructor_clause()
    sql += clause + " ORDER BY last_name, first_name"
    with get_conn() as conn:
        rows = _rows(conn.execute(sql, params))
    return [
        {"id": r["id"], "label": f"{r['last_name']}, {r['first_name']}", "status": r["status"]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Milestones & notes
# ---------------------------------------------------------------------------

def seed_milestones(student_id: int, goal: str, *, replace_track: bool = False) -> None:
    track = resolve_track(goal)
    names = MILESTONES.get(track) or MILESTONES["Other"]
    with get_conn() as conn:
        if replace_track:
            conn.execute(
                "DELETE FROM milestones WHERE student_id = ? AND COALESCE(track, '') = ?",
                (student_id, track),
            )
        existing = conn.execute(
            "SELECT COUNT(*) FROM milestones WHERE student_id = ? AND COALESCE(track, '') = ?",
            (student_id, track),
        ).fetchone()[0]
        if existing:
            return
        for i, name in enumerate(names):
            conn.execute(
                "INSERT INTO milestones (student_id, name, completed, sort_order, track) VALUES (?, ?, 0, ?, ?)",
                (student_id, name, i, track),
            )


def list_milestones(student_id: int, track: str | None = None) -> list[dict]:
    sql = "SELECT * FROM milestones WHERE student_id = ?"
    params: list = [student_id]
    if track:
        sql += " AND COALESCE(track, '') = ?"
        params.append(resolve_track(track))
    sql += " ORDER BY sort_order, id"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params))


def track_progress_counts(student_id: int) -> dict[str, tuple[int, int]]:
    """track -> (completed, total)."""
    with get_conn() as conn:
        rows = _rows(
            conn.execute(
                """
                SELECT COALESCE(track, 'Other') AS track,
                       SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) AS done,
                       COUNT(*) AS total
                FROM milestones
                WHERE student_id = ?
                GROUP BY COALESCE(track, 'Other')
                """,
                (student_id,),
            )
        )
    return {r["track"]: (int(r["done"] or 0), int(r["total"] or 0)) for r in rows}


def set_instruction_track(student_id: int, track: str) -> None:
    track = resolve_track(track)
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET goal=?, updated_at=? WHERE id=?",
            (track, iso_today(), student_id),
        )


def set_milestone(milestone_id: int, completed: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE milestones SET completed=?, completed_date=? WHERE id=?",
            (1 if completed else 0, iso_today() if completed else None, milestone_id),
        )


def add_milestone(student_id: int, name: str, track: str | None = None) -> None:
    track = resolve_track(track)
    with get_conn() as conn:
        order = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1 FROM milestones
            WHERE student_id = ? AND COALESCE(track, '') = ?
            """,
            (student_id, track),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO milestones (student_id, name, completed, sort_order, track) VALUES (?, ?, 0, ?, ?)",
            (student_id, name.strip(), order, track),
        )


def delete_milestone(milestone_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM milestones WHERE id = ?", (milestone_id,))


def list_notes(student_id: int) -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                "SELECT * FROM notes WHERE student_id = ? ORDER BY date DESC, id DESC",
                (student_id,),
            )
        )


def add_note(student_id: int, body: str, category: str = "training", note_date: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notes (student_id, date, category, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (student_id, note_date or iso_today(), category, body.strip(), iso_today()),
        )


def delete_note(note_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))


# ---------------------------------------------------------------------------
# Sessions / hours
# ---------------------------------------------------------------------------

def list_sessions(
    student_id: int | None = None,
    unbilled_only: bool = False,
    limit: int | None = 200,
) -> list[dict]:
    sql = """
        SELECT s.*, st.first_name, st.last_name,
               (st.first_name || ' ' || st.last_name) AS student_name
        FROM sessions s
        JOIN students st ON st.id = s.student_id
        WHERE 1=1
    """
    params: list = []
    if student_id:
        sql += " AND s.student_id = ?"
        params.append(student_id)
    if unbilled_only:
        sql += " AND s.billable = 1 AND s.billed = 0"
    clause, clause_params = _instructor_clause("st")
    sql += clause
    params.extend(clause_params)
    sql += " ORDER BY s.date DESC, s.id DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with get_conn() as conn:
        rows = _rows(conn.execute(sql, params))
    for r in rows:
        r["line_amount"] = money(D(r.get("hours") or 0) * D(r.get("rate_amount") or 0))
    return rows


def get_session(session_id: int) -> dict | None:
    with get_conn() as conn:
        row = _row(
            conn.execute(
                """
                SELECT s.*, st.first_name, st.last_name, st.instructor_user_id
                FROM sessions s JOIN students st ON st.id = s.student_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
        )
    if row and not _can_see_student_row(row):
        return None
    return row


def save_session(data: dict) -> int:
    _assert_student_access(int(data["student_id"]))
    now = iso_today()
    payload = (
        int(data["student_id"]),
        data.get("date") or iso_today(),
        data["training_type"],
        hours(data.get("hours")),
        data.get("aircraft") or "",
        data.get("airport") or "",
        data.get("rate_id"),
        money(data.get("rate_amount")),
        1 if data.get("billable", True) else 0,
        data.get("description") or training_type_label(data["training_type"]),
        data.get("notes") or "",
    )
    with get_conn() as conn:
        if data.get("id"):
            conn.execute(
                """
                UPDATE sessions
                SET student_id=?, date=?, training_type=?, hours=?, aircraft=?, airport=?,
                    rate_id=?, rate_amount=?, billable=?, description=?, notes=?
                WHERE id=?
                """,
                (*payload, data["id"]),
            )
            return int(data["id"])
        cur = conn.execute(
            """
            INSERT INTO sessions (
                student_id, date, training_type, hours, aircraft, airport,
                rate_id, rate_amount, billable, billed, description, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (*payload, now),
        )
        return int(cur.lastrowid)


def delete_session(session_id: int) -> None:
    sess = get_session(session_id)
    if not sess:
        raise ValueError("Session not found")
    with get_conn() as conn:
        row = conn.execute("SELECT billed FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row and row["billed"]:
            raise ValueError("This session is already on an invoice. Remove it from the invoice first.")
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def training_type_label(code: str) -> str:
    for value, label in TRAINING_TYPES:
        if value == code:
            return label
    return code.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------

def next_invoice_number() -> str:
    s = get_settings()
    prefix = (s.get("invoice_prefix") or "INV").strip() or "INV"
    try:
        n = int(s.get("next_invoice_number") or 1001)
    except ValueError:
        n = 1001
    number = f"{prefix}-{n}"
    with get_conn() as conn:
        while conn.execute("SELECT 1 FROM invoices WHERE number = ?", (number,)).fetchone():
            n += 1
            number = f"{prefix}-{n}"
    return number


def _consume_invoice_number(number: str) -> None:
    s = get_settings()
    prefix = (s.get("invoice_prefix") or "INV").strip() or "INV"
    try:
        current = int(s.get("next_invoice_number") or 1001)
    except ValueError:
        current = 1001
    try:
        used = int(number.split("-")[-1])
    except ValueError:
        used = current
    set_setting("next_invoice_number", str(max(current, used + 1)))


def list_invoices(
    student_id: int | None = None,
    status: str | None = None,
    search: str = "",
) -> list[dict]:
    sql = """
        SELECT i.*,
               (st.first_name || ' ' || st.last_name) AS student_name,
               st.email AS student_email
        FROM invoices i
        JOIN students st ON st.id = i.student_id
        WHERE 1=1
    """
    params: list = []
    if student_id:
        sql += " AND i.student_id = ?"
        params.append(student_id)
    if status == "unpaid":
        sql += " AND i.status IN ('unpaid', 'partial', 'overdue') AND i.balance > 0.005"
    elif status == "overdue":
        sql += " AND i.status NOT IN ('paid', 'void', 'draft') AND i.balance > 0.005 AND i.due_date < ?"
        params.append(iso_today())
    elif status == "overdue_30":
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        sql += " AND i.status NOT IN ('paid', 'void', 'draft') AND i.balance > 0.005 AND i.due_date <= ?"
        params.append(cutoff)
    elif status and status != "all":
        sql += " AND i.status = ?"
        params.append(status)
    if search:
        like = f"%{search.strip()}%"
        sql += " AND (i.number LIKE ? OR st.first_name LIKE ? OR st.last_name LIKE ?)"
        params.extend([like, like, like])
    clause, clause_params = _instructor_clause("st")
    sql += clause
    params.extend(clause_params)
    sql += " ORDER BY i.issue_date DESC, i.id DESC"
    with get_conn() as conn:
        invoices = _rows(conn.execute(sql, params))
    for inv in invoices:
        _decorate_invoice(inv)
    return invoices


def get_invoice(invoice_id: int) -> dict | None:
    with get_conn() as conn:
        inv = _row(
            conn.execute(
                """
                SELECT i.*,
                       (st.first_name || ' ' || st.last_name) AS student_name,
                       st.email AS student_email, st.phone AS student_phone,
                       st.address AS student_address, st.city AS student_city,
                       st.state AS student_state, st.zip AS student_zip,
                       st.instructor_user_id
                FROM invoices i
                JOIN students st ON st.id = i.student_id
                WHERE i.id = ?
                """,
                (invoice_id,),
            ).fetchone()
        )
    if not inv or not _can_see_student_row(inv):
        return None
    inv["items"] = list_invoice_items(invoice_id)
    inv["payments"] = list_payments(invoice_id)
    _decorate_invoice(inv)
    return inv


def _decorate_invoice(inv: dict) -> None:
    due = parse_date(inv.get("due_date"))
    today = date.today()
    inv["days_overdue"] = (today - due).days if due and inv["status"] not in ("paid", "void", "draft") and money(inv.get("balance")) > 0 else 0
    if inv["days_overdue"] < 0:
        inv["days_overdue"] = 0
    if inv["status"] not in ("paid", "void", "draft") and money(inv.get("balance")) > 0.005 and due and due < today:
        inv["display_status"] = "overdue"
    else:
        inv["display_status"] = inv["status"]
    inv["is_overdue_30"] = inv["days_overdue"] >= 30


def list_invoice_items(invoice_id: int) -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY sort_order, id",
                (invoice_id,),
            )
        )


def list_payments(invoice_id: int) -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY date, id",
                (invoice_id,),
            )
        )


def create_invoice(
    student_id: int,
    session_ids: list[int] | None = None,
    extra_items: list[dict] | None = None,
    issue_date: str | None = None,
    due_date: str | None = None,
    discount_type: str = "none",
    discount_value: float = 0,
    notes: str = "",
    terms: str | None = None,
    include_venmo: bool = True,
    status: str = "unpaid",
) -> int:
    _assert_student_access(int(student_id))
    s = get_settings()
    issue = issue_date or iso_today()
    terms_days = int(s.get("payment_terms_days") or 30)
    due = due_date or (parse_date(issue) + timedelta(days=terms_days)).isoformat()
    number = next_invoice_number()
    now = iso_today()
    tax_rate = money(s.get("tax_rate") or 0) if s.get("tax_enabled") == "1" else 0
    footer = terms if terms is not None else (s.get("invoice_footer") or "")
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoices (
                number, student_id, issue_date, due_date, status,
                discount_type, discount_value, tax_rate, notes, terms,
                include_venmo, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                number,
                student_id,
                issue,
                due,
                status,
                discount_type,
                money(discount_value),
                tax_rate,
                notes,
                footer,
                1 if include_venmo else 0,
                now,
                now,
            ),
        )
        invoice_id = int(cur.lastrowid)
    _consume_invoice_number(number)
    order = 0
    for sid in session_ids or []:
        sess = get_session(sid)
        if not sess or sess["billed"]:
            continue
        qty = hours(sess["hours"]) if sess.get("hours") else 1
        unit_price = money(sess["rate_amount"])
        add_invoice_item(
            invoice_id,
            {
                "session_id": sid,
                "rate_id": sess.get("rate_id"),
                "description": _session_item_description(sess),
                "category": sess["training_type"],
                "quantity": qty,
                "unit": "hour",
                "unit_price": unit_price,
                "sort_order": order,
            },
        )
        _mark_session_billed(sid, invoice_id, True)
        order += 1
    for item in extra_items or []:
        item = dict(item)
        item["sort_order"] = order
        add_invoice_item(invoice_id, item)
        order += 1
    recalc_invoice(invoice_id)
    return invoice_id


def _session_item_description(sess: dict) -> str:
    label = sess.get("description") or training_type_label(sess["training_type"])
    extra = []
    if sess.get("aircraft"):
        extra.append(sess["aircraft"])
    if sess.get("airport"):
        extra.append(sess["airport"])
    date_s = sess.get("date") or ""
    suffix = f" - {date_s}"
    if extra:
        suffix += f" ({', '.join(extra)})"
    return f"{label}{suffix}"


def add_invoice_item(invoice_id: int, item: dict) -> int:
    qty = float(item.get("quantity") or 1)
    price = money(item.get("unit_price"))
    amount = money(D(qty) * D(price))
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO invoice_items (
                invoice_id, session_id, rate_id, description, category,
                quantity, unit, unit_price, amount, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                invoice_id,
                item.get("session_id"),
                item.get("rate_id"),
                item.get("description") or "Item",
                item.get("category") or "service",
                qty,
                item.get("unit") or "each",
                price,
                amount,
                int(item.get("sort_order") or 0),
            ),
        )
        return int(cur.lastrowid)


def update_invoice_item(item_id: int, item: dict) -> None:
    qty = float(item.get("quantity") or 1)
    price = money(item.get("unit_price"))
    amount = money(D(qty) * D(price))
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE invoice_items
            SET description=?, category=?, quantity=?, unit=?, unit_price=?, amount=?
            WHERE id=?
            """,
            (
                item.get("description") or "Item",
                item.get("category") or "service",
                qty,
                item.get("unit") or "each",
                price,
                amount,
                item_id,
            ),
        )
        row = conn.execute("SELECT invoice_id FROM invoice_items WHERE id = ?", (item_id,)).fetchone()
    if row:
        recalc_invoice(row["invoice_id"])


def delete_invoice_item(item_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT invoice_id, session_id FROM invoice_items WHERE id = ?", (item_id,)
        ).fetchone()
        if not row:
            return
        conn.execute("DELETE FROM invoice_items WHERE id = ?", (item_id,))
        invoice_id = row["invoice_id"]
        session_id = row["session_id"]
    if session_id:
        _mark_session_billed(session_id, None, False)
    recalc_invoice(invoice_id)


def _mark_session_billed(session_id: int, invoice_id: int | None, billed: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET billed=?, invoice_id=? WHERE id=?",
            (1 if billed else 0, invoice_id, session_id),
        )


def update_invoice_fields(invoice_id: int, fields: dict) -> None:
    if not get_invoice(invoice_id):
        raise ValueError("Invoice not found")
    allowed = {
        "issue_date",
        "due_date",
        "status",
        "discount_type",
        "discount_value",
        "tax_rate",
        "notes",
        "terms",
        "include_venmo",
        "student_id",
    }
    sets = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in {"discount_value", "tax_rate"}:
            value = money(value)
        if key == "include_venmo":
            value = 1 if value else 0
        sets.append(f"{key}=?")
        params.append(value)
    if not sets:
        return
    sets.append("updated_at=?")
    params.append(iso_today())
    params.append(invoice_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE invoices SET {', '.join(sets)} WHERE id=?", params)
    recalc_invoice(invoice_id)


def recalc_invoice(invoice_id: int) -> dict:
    with get_conn() as conn:
        inv = _row(conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
        items = _rows(
            conn.execute("SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        )
        paid = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS paid FROM payments WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()["paid"]
    subtotal = money(sum(D(i["amount"]) for i in items))
    dtype = inv["discount_type"] or "none"
    dval = D(inv["discount_value"] or 0)
    if dtype == "percent":
        discount = money(D(subtotal) * dval / Decimal_100())
    elif dtype == "amount":
        discount = money(min(dval, D(subtotal)))
    else:
        discount = 0.0
    taxable = money(D(subtotal) - D(discount))
    tax = money(D(taxable) * D(inv["tax_rate"] or 0) / Decimal_100())
    total = money(D(taxable) + D(tax))
    amount_paid = money(paid)
    balance = money(D(total) - D(amount_paid))
    status = inv["status"]
    if status not in ("void", "draft"):
        if balance <= 0.005 and amount_paid > 0:
            status = "paid"
        elif amount_paid > 0.005:
            status = "partial"
        else:
            status = "unpaid"
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE invoices
            SET subtotal=?, discount_amount=?, tax_amount=?, total=?,
                amount_paid=?, balance=?, status=?, updated_at=?
            WHERE id=?
            """,
            (subtotal, discount, tax, total, amount_paid, max(balance, 0.0), status, iso_today(), invoice_id),
        )
    return get_invoice(invoice_id)


def Decimal_100():
    from decimal import Decimal as Dec

    return Dec("100")


def add_payment(invoice_id: int, amount, method: str, pay_date: str | None = None, reference: str = "", notes: str = "") -> None:
    if not get_invoice(invoice_id):
        raise ValueError("Invoice not found")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO payments (invoice_id, date, amount, method, reference, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (invoice_id, pay_date or iso_today(), money(amount), method or "Venmo", reference, notes),
        )
    recalc_invoice(invoice_id)


def delete_payment(payment_id: int) -> None:
    with get_conn() as conn:
        row = conn.execute("SELECT invoice_id FROM payments WHERE id = ?", (payment_id,)).fetchone()
        if not row:
            return
        conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
        invoice_id = row["invoice_id"]
    recalc_invoice(invoice_id)


def mark_invoice_paid(invoice_id: int, method: str = "Venmo", pay_date: str | None = None) -> None:
    inv = get_invoice(invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    remaining = money(inv["balance"])
    if remaining > 0.005:
        add_payment(invoice_id, remaining, method, pay_date, notes="Marked paid")
    else:
        update_invoice_fields(invoice_id, {"status": "paid"})


def void_invoice(invoice_id: int) -> None:
    inv = get_invoice(invoice_id)
    if not inv:
        return
    for item in inv.get("items") or []:
        if item.get("session_id"):
            _mark_session_billed(item["session_id"], None, False)
    with get_conn() as conn:
        conn.execute(
            "UPDATE invoices SET status='void', balance=0, updated_at=? WHERE id=?",
            (iso_today(), invoice_id),
        )


def delete_voided_invoice(invoice_id: int) -> str:
    """Permanently remove a voided invoice. Returns the invoice number."""
    inv = get_invoice(invoice_id)
    if not inv:
        raise ValueError("Invoice not found")
    if inv["status"] != "void":
        raise ValueError("Only voided invoices can be deleted. Void it first.")
    number = inv["number"]
    for item in inv.get("items") or []:
        if item.get("session_id"):
            _mark_session_billed(item["session_id"], None, False)
    with get_conn() as conn:
        conn.execute("UPDATE sessions SET invoice_id = NULL, billed = 0 WHERE invoice_id = ?", (invoice_id,))
        conn.execute("DELETE FROM payments WHERE invoice_id = ?", (invoice_id,))
        conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    pdf = INVOICE_DIR / f"{number}.pdf"
    if pdf.exists():
        pdf.unlink()
    qr = QR_DIR / f"invoice_{invoice_id}.png"
    if qr.exists():
        qr.unlink()
    return number


def reminder_message(invoice: dict) -> str:
    s = get_settings()
    venmo = s.get("venmo_username") or ""
    name = (invoice.get("student_name") or "there").split()[0]
    days = invoice.get("days_overdue") or 0
    pay = f" You can pay via Venmo @{venmo}." if venmo else ""
    return (
        f"Hi {name}, this is a friendly reminder that invoice {invoice['number']} "
        f"for {_fmt(invoice['balance'])} was due on {invoice['due_date']} "
        f"and is now {days} days overdue.{pay} Thank you!"
    )


def _fmt(v) -> str:
    from aerobooks.money import fmt_money

    return fmt_money(v)


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

def list_expenses(year: int | None = None, month: int | None = None, category: str | None = None) -> list[dict]:
    sql = """
        SELECT e.*, (st.first_name || ' ' || st.last_name) AS student_name
        FROM expenses e
        LEFT JOIN students st ON st.id = e.student_id
        WHERE 1=1
    """
    params: list = []
    user = _current_user()
    if user and user.get("role") == "school_instructor":
        sql += " AND e.owner_user_id = ?"
        params.append(int(user["id"]))
    if year and month:
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year+1:04d}-01-01"
        else:
            end = f"{year:04d}-{month+1:02d}-01"
        sql += " AND e.date >= ? AND e.date < ?"
        params.extend([start, end])
    elif year:
        sql += " AND e.date >= ? AND e.date < ?"
        params.extend([f"{year:04d}-01-01", f"{year+1:04d}-01-01"])
    if category and category != "all":
        sql += " AND e.category = ?"
        params.append(category)
    sql += " ORDER BY e.date DESC, e.id DESC"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params))


def save_expense(data: dict) -> int:
    user = _current_user()
    owner_id = data.get("owner_user_id") or (user["id"] if user else None)
    if data.get("student_id"):
        _assert_student_access(int(data["student_id"]))
    with get_conn() as conn:
        if data.get("id"):
            existing = conn.execute(
                "SELECT owner_user_id FROM expenses WHERE id = ?", (data["id"],)
            ).fetchone()
            if not existing:
                raise ValueError("Expense not found")
            if user and user.get("role") == "school_instructor":
                if int(existing["owner_user_id"] or 0) != int(user["id"]):
                    raise PermissionError("You do not have access to this expense")
            conn.execute(
                """
                UPDATE expenses
                SET date=?, category=?, amount=?, description=?, vendor=?, student_id=?, reimbursable=?, notes=?
                WHERE id=?
                """,
                (
                    data.get("date") or iso_today(),
                    data["category"],
                    money(data.get("amount")),
                    data.get("description") or "",
                    data.get("vendor") or "",
                    data.get("student_id") or None,
                    1 if data.get("reimbursable") else 0,
                    data.get("notes") or "",
                    data["id"],
                ),
            )
            return int(data["id"])
        cur = conn.execute(
            """
            INSERT INTO expenses (date, category, amount, description, vendor, student_id, reimbursable, notes, created_at, owner_user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("date") or iso_today(),
                data["category"],
                money(data.get("amount")),
                data.get("description") or "",
                data.get("vendor") or "",
                data.get("student_id") or None,
                1 if data.get("reimbursable") else 0,
                data.get("notes") or "",
                iso_today(),
                int(owner_id) if owner_id else None,
            ),
        )
        return int(cur.lastrowid)


def delete_expense(expense_id: int) -> None:
    user = _current_user()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT owner_user_id FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        if not existing:
            return
        if user and user.get("role") == "school_instructor":
            if int(existing["owner_user_id"] or 0) != int(user["id"]):
                raise PermissionError("You do not have access to this expense")
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))


# ---------------------------------------------------------------------------
# Dashboard / earnings
# ---------------------------------------------------------------------------

def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start = f"{year:04d}-{month:02d}-01"
    if month == 12:
        end = f"{year+1:04d}-01-01"
    else:
        end = f"{year:04d}-{month+1:02d}-01"
    return start, end


def dashboard_stats() -> dict:
    today = date.today()
    start, end = _month_bounds(today.year, today.month)
    ytd_start = f"{today.year:04d}-01-01"
    cutoff_30 = (today - timedelta(days=30)).isoformat()
    vis, vis_params = _visible_student_ids_sql()
    user = _current_user()
    exp_sql = "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date >= ? AND date < ?"
    exp_params: list = [start, end]
    ytd_exp_sql = "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date >= ?"
    ytd_exp_params: list = [ytd_start]
    if user and user.get("role") == "school_instructor":
        exp_sql += " AND owner_user_id = ?"
        exp_params.append(int(user["id"]))
        ytd_exp_sql += " AND owner_user_id = ?"
        ytd_exp_params.append(int(user["id"]))
    with get_conn() as conn:
        active_students = conn.execute(
            f"SELECT COUNT(*) FROM students WHERE status NOT IN ('inactive', 'graduated') AND id IN ({vis})",
            vis_params,
        ).fetchone()[0]
        hours_month = conn.execute(
            f"SELECT COALESCE(SUM(hours), 0) FROM sessions WHERE date >= ? AND date < ? AND student_id IN ({vis})",
            (start, end, *vis_params),
        ).fetchone()[0]
        hours_by_type = _rows(
            conn.execute(
                f"""
                SELECT training_type, SUM(hours) AS hours
                FROM sessions WHERE date >= ? AND date < ? AND student_id IN ({vis})
                GROUP BY training_type
                """,
                (start, end, *vis_params),
            )
        )
        unbilled = conn.execute(
            f"""
            SELECT COALESCE(SUM(hours), 0) AS hours,
                   COALESCE(SUM(hours * rate_amount), 0) AS amount
            FROM sessions WHERE billable = 1 AND billed = 0 AND student_id IN ({vis})
            """,
            vis_params,
        ).fetchone()
        collected_month = conn.execute(
            f"""
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE p.date >= ? AND p.date < ? AND i.student_id IN ({vis})
            """,
            (start, end, *vis_params),
        ).fetchone()[0]
        billed_month = conn.execute(
            f"""
            SELECT COALESCE(SUM(total), 0) FROM invoices
            WHERE issue_date >= ? AND issue_date < ? AND status != 'void'
              AND student_id IN ({vis})
            """,
            (start, end, *vis_params),
        ).fetchone()[0]
        outstanding = conn.execute(
            f"""
            SELECT COALESCE(SUM(balance), 0) FROM invoices
            WHERE status NOT IN ('paid', 'void', 'draft') AND balance > 0
              AND student_id IN ({vis})
            """,
            vis_params,
        ).fetchone()[0]
        overdue = conn.execute(
            f"""
            SELECT COUNT(*) AS n, COALESCE(SUM(balance), 0) AS amount
            FROM invoices
            WHERE status NOT IN ('paid', 'void', 'draft') AND balance > 0 AND due_date < ?
              AND student_id IN ({vis})
            """,
            (iso_today(), *vis_params),
        ).fetchone()
        overdue_30 = conn.execute(
            f"""
            SELECT COUNT(*) AS n, COALESCE(SUM(balance), 0) AS amount
            FROM invoices
            WHERE status NOT IN ('paid', 'void', 'draft') AND balance > 0 AND due_date <= ?
              AND student_id IN ({vis})
            """,
            (cutoff_30, *vis_params),
        ).fetchone()
        expenses_month = conn.execute(exp_sql, exp_params).fetchone()[0]
        ytd_collected = conn.execute(
            f"""
            SELECT COALESCE(SUM(p.amount), 0)
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE p.date >= ? AND i.student_id IN ({vis})
            """,
            (ytd_start, *vis_params),
        ).fetchone()[0]
        ytd_expenses = conn.execute(ytd_exp_sql, ytd_exp_params).fetchone()[0]
        medicals = _rows(
            conn.execute(
                f"""
                SELECT id, first_name, last_name, medical_expires
                FROM students
                WHERE medical_expires IS NOT NULL AND medical_expires != ''
                  AND status NOT IN ('inactive', 'graduated')
                  AND id IN ({vis})
                ORDER BY medical_expires
                """,
                vis_params,
            )
        )
    soon = []
    for m in medicals:
        d = parse_date(m["medical_expires"])
        if d and 0 <= (d - today).days <= 60:
            soon.append(m)
        elif d and d < today:
            soon.append(m)
    return {
        "active_students": active_students,
        "hours_month": hours(hours_month),
        "hours_by_type": hours_by_type,
        "unbilled_hours": hours(unbilled["hours"]),
        "unbilled_amount": money(unbilled["amount"]),
        "collected_month": money(collected_month),
        "billed_month": money(billed_month),
        "outstanding": money(outstanding),
        "overdue_count": overdue["n"],
        "overdue_amount": money(overdue["amount"]),
        "overdue_30_count": overdue_30["n"],
        "overdue_30_amount": money(overdue_30["amount"]),
        "expenses_month": money(expenses_month),
        "net_month": money(D(collected_month) - D(expenses_month)),
        "ytd_collected": money(ytd_collected),
        "ytd_expenses": money(ytd_expenses),
        "ytd_net": money(D(ytd_collected) - D(ytd_expenses)),
        "medical_alerts": soon,
    }


def monthly_earnings(year: int | None = None) -> list[dict]:
    year = year or date.today().year
    rows = []
    vis, vis_params = _visible_student_ids_sql()
    user = _current_user()
    with get_conn() as conn:
        for month in range(1, 13):
            start, end = _month_bounds(year, month)
            billed = conn.execute(
                f"""
                SELECT COALESCE(SUM(total), 0) FROM invoices
                WHERE issue_date >= ? AND issue_date < ? AND status != 'void'
                  AND student_id IN ({vis})
                """,
                (start, end, *vis_params),
            ).fetchone()[0]
            collected = conn.execute(
                f"""
                SELECT COALESCE(SUM(p.amount), 0)
                FROM payments p
                JOIN invoices i ON i.id = p.invoice_id
                WHERE p.date >= ? AND p.date < ? AND i.student_id IN ({vis})
                """,
                (start, end, *vis_params),
            ).fetchone()[0]
            exp_sql = "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date >= ? AND date < ?"
            exp_params: list = [start, end]
            if user and user.get("role") == "school_instructor":
                exp_sql += " AND owner_user_id = ?"
                exp_params.append(int(user["id"]))
            expense = conn.execute(exp_sql, exp_params).fetchone()[0]
            hrs = conn.execute(
                f"SELECT COALESCE(SUM(hours), 0) FROM sessions WHERE date >= ? AND date < ? AND student_id IN ({vis})",
                (start, end, *vis_params),
            ).fetchone()[0]
            rows.append(
                {
                    "month": month,
                    "label": date(year, month, 1).strftime("%b"),
                    "billed": money(billed),
                    "collected": money(collected),
                    "expenses": money(expense),
                    "net": money(D(collected) - D(expense)),
                    "hours": hours(hrs),
                }
            )
    return rows


def hours_by_type_range(start: str, end: str) -> list[dict]:
    vis, vis_params = _visible_student_ids_sql()
    with get_conn() as conn:
        rows = _rows(
            conn.execute(
                f"""
                SELECT training_type, SUM(hours) AS hours
                FROM sessions WHERE date >= ? AND date < ? AND student_id IN ({vis})
                GROUP BY training_type
                ORDER BY hours DESC
                """,
                (start, end, *vis_params),
            )
        )
    for r in rows:
        r["label"] = training_type_label(r["training_type"])
        r["hours"] = hours(r["hours"])
    return rows


def backup_database() -> Path:
    from aerobooks.backup import create_backup_zip

    return create_backup_zip()
