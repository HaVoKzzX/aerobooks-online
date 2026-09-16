"""Accounts, passwords, access requests, and the current session."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone

from contextvars import ContextVar

from aerobooks import paths

_force_user: ContextVar[dict | None] = ContextVar("aerobooks_user", default=None)

ROLES = ("admin", "instructor", "manager", "school_instructor")
ACCOUNT_TYPES = ("instructor", "manager")
USER_STATUSES = ("active", "disabled")
REQUEST_STATUSES = ("pending", "approved", "rejected")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")

PBKDF2_ROUNDS = 200_000


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ROUNDS,
    )
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    digest, _ = hash_password(password, salt)
    return hmac.compare_digest(digest, password_hash or "")


def get_conn():
    paths.ensure_base_dirs()
    from aerobooks.store import encrypted_db

    return encrypted_db(paths.auth_db_path())


def _row(r) -> dict | None:
    return dict(r) if r is not None else None


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


def init_auth() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                kind TEXT NOT NULL,
                owner_user_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                display_name TEXT,
                email TEXT,
                phone TEXT,
                cfi_number TEXT,
                cfii_number TEXT,
                venmo_username TEXT,
                venmo_note_prefix TEXT,
                tenant_id INTEGER,
                created_by_user_id INTEGER,
                created_at TEXT NOT NULL,
                last_login TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );

            CREATE TABLE IF NOT EXISTS account_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                account_type TEXT NOT NULL,
                display_name TEXT,
                email TEXT,
                phone TEXT,
                organization TEXT,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                reviewed_at TEXT,
                reviewed_by INTEGER,
                reject_reason TEXT
            );
            """
        )


def has_admin() -> bool:
    with get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
    return bool(n)


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def get_user_by_username(username: str) -> dict | None:
    with get_conn() as conn:
        return _row(
            conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (normalize_username(username),),
            ).fetchone()
        )


def username_taken(username: str) -> bool:
    name = normalize_username(username)
    with get_conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone():
            return True
        if conn.execute(
            "SELECT 1 FROM account_requests WHERE username = ? AND status = 'pending'",
            (name,),
        ).fetchone():
            return True
    return False


def validate_username(username: str) -> str:
    name = normalize_username(username)
    if not USERNAME_RE.match(name):
        raise ValueError("Username must be 3–32 letters, numbers, or underscores.")
    return name


def validate_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    return password


def create_admin(username: str, password: str, display_name: str = "") -> dict:
    if has_admin():
        raise ValueError("An administrator account already exists.")
    name = validate_username(username)
    validate_password(password)
    if username_taken(name):
        raise ValueError("That username is already taken.")
    pw_hash, salt = hash_password(password)
    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (
                username, password_hash, salt, role, status, display_name,
                email, created_at
            ) VALUES (?, ?, ?, 'admin', 'active', ?, '', ?)
            """,
            (name, pw_hash, salt, (display_name or name).strip(), now),
        )
        user_id = int(cur.lastrowid)
    return get_user(user_id)


def submit_request(
    *,
    username: str,
    password: str,
    account_type: str,
    display_name: str,
    email: str = "",
    phone: str = "",
    organization: str = "",
    notes: str = "",
) -> int:
    name = validate_username(username)
    validate_password(password)
    if account_type not in ACCOUNT_TYPES:
        raise ValueError("Choose independent instructor or flight school manager.")
    if username_taken(name):
        raise ValueError("That username is already taken.")
    if account_type == "manager" and not (organization or "").strip():
        raise ValueError("Flight school / business name is required for a manager account.")
    if not (display_name or "").strip():
        raise ValueError("Your name is required.")
    pw_hash, salt = hash_password(password)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO account_requests (
                username, password_hash, salt, account_type, display_name,
                email, phone, organization, notes, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                name,
                pw_hash,
                salt,
                account_type,
                display_name.strip(),
                (email or "").strip(),
                (phone or "").strip(),
                (organization or "").strip(),
                (notes or "").strip(),
                _now(),
            ),
        )
        return int(cur.lastrowid)


def list_requests(status: str | None = "pending") -> list[dict]:
    sql = "SELECT * FROM account_requests WHERE 1=1"
    params: list = []
    if status and status != "all":
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return _rows(conn.execute(sql, params))


def get_request(request_id: int) -> dict | None:
    with get_conn() as conn:
        return _row(
            conn.execute("SELECT * FROM account_requests WHERE id = ?", (request_id,)).fetchone()
        )


def pending_request_count() -> int:
    with get_conn() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM account_requests WHERE status = 'pending'"
            ).fetchone()[0]
        )


def _create_tenant(name: str, kind: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tenants (name, kind, created_at) VALUES (?, ?, ?)",
            (name, kind, _now()),
        )
        return int(cur.lastrowid)


def _set_tenant_owner(tenant_id: int, user_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tenants SET owner_user_id = ? WHERE id = ?",
            (user_id, tenant_id),
        )


def _insert_user(
    *,
    username: str,
    password_hash: str,
    salt: str,
    role: str,
    display_name: str,
    email: str = "",
    phone: str = "",
    tenant_id: int | None = None,
    created_by_user_id: int | None = None,
    cfi_number: str = "",
    cfii_number: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (
                username, password_hash, salt, role, status, display_name,
                email, phone, cfi_number, cfii_number, tenant_id,
                created_by_user_id, created_at
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                password_hash,
                salt,
                role,
                display_name,
                email,
                phone,
                cfi_number,
                cfii_number,
                tenant_id,
                created_by_user_id,
                _now(),
            ),
        )
        return int(cur.lastrowid)


def _seed_tenant(tenant_id: int, *, kind: str, display_name: str, organization: str = "") -> None:
    from aerobooks import db

    previous = paths.current_tenant_id()
    paths.bind_tenant(tenant_id)
    try:
        db.init_db()
        if kind == "school":
            db.save_settings(
                {
                    "entity_type": "business",
                    "business_name": organization or display_name,
                    "instructor_name": display_name,
                    "setup_complete": "0",
                }
            )
        else:
            db.save_settings(
                {
                    "entity_type": "individual",
                    "instructor_name": display_name,
                    "business_name": "",
                    "setup_complete": "0",
                }
            )
    finally:
        paths.bind_tenant(previous)


def approve_request(request_id: int, admin_id: int) -> dict:
    req = get_request(request_id)
    if not req:
        raise ValueError("Request not found.")
    if req["status"] != "pending":
        raise ValueError("This request has already been reviewed.")
    if get_user_by_username(req["username"]):
        raise ValueError("That username was taken after the request was submitted.")

    kind = "school" if req["account_type"] == "manager" else "independent"
    tenant_name = (req["organization"] or req["display_name"] or req["username"]).strip()
    tenant_id = _create_tenant(tenant_name, kind)
    role = "manager" if req["account_type"] == "manager" else "instructor"
    user_id = _insert_user(
        username=req["username"],
        password_hash=req["password_hash"],
        salt=req["salt"],
        role=role,
        display_name=req["display_name"] or req["username"],
        email=req.get("email") or "",
        phone=req.get("phone") or "",
        tenant_id=tenant_id,
    )
    _set_tenant_owner(tenant_id, user_id)
    _seed_tenant(
        tenant_id,
        kind=kind,
        display_name=req["display_name"] or req["username"],
        organization=req.get("organization") or "",
    )
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE account_requests
            SET status = 'approved', reviewed_at = ?, reviewed_by = ?
            WHERE id = ?
            """,
            (_now(), admin_id, request_id),
        )
    return get_user(user_id)


def reject_request(request_id: int, admin_id: int, reason: str = "") -> None:
    req = get_request(request_id)
    if not req:
        raise ValueError("Request not found.")
    if req["status"] != "pending":
        raise ValueError("This request has already been reviewed.")
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE account_requests
            SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, reject_reason = ?
            WHERE id = ?
            """,
            (_now(), admin_id, (reason or "").strip(), request_id),
        )


def list_users() -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                """
                SELECT u.*, t.name AS tenant_name, t.kind AS tenant_kind
                FROM users u
                LEFT JOIN tenants t ON t.id = u.tenant_id
                ORDER BY u.role, u.username
                """
            )
        )


def list_tenants() -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                """
                SELECT t.*,
                       u.username AS owner_username,
                       (SELECT COUNT(*) FROM users WHERE tenant_id = t.id) AS user_count
                FROM tenants t
                LEFT JOIN users u ON u.id = t.owner_user_id
                ORDER BY t.created_at DESC
                """
            )
        )


def set_user_status(user_id: int, status: str) -> None:
    if status not in USER_STATUSES:
        raise ValueError("Invalid status.")
    user = get_user(user_id)
    if not user:
        raise ValueError("User not found.")
    if user["role"] == "admin":
        raise ValueError("The administrator account cannot be disabled.")
    with get_conn() as conn:
        conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))


def set_password(user_id: int, password: str) -> None:
    validate_password(password)
    pw_hash, salt = hash_password(password)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
            (pw_hash, salt, user_id),
        )


def update_profile(user_id: int, fields: dict) -> None:
    allowed = {
        "display_name",
        "email",
        "phone",
        "cfi_number",
        "cfii_number",
        "venmo_username",
        "venmo_note_prefix",
    }
    sets = []
    params = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        sets.append(f"{key} = ?")
        params.append("" if value is None else str(value).strip())
    if not sets:
        return
    params.append(user_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)


def authenticate(username: str, password: str) -> dict:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"], user["salt"]):
        raise ValueError("Incorrect username or password.")
    if user["status"] != "active":
        raise ValueError("This account is disabled. Contact the administrator.")
    with get_conn() as conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (_now(), user["id"]))
    return get_user(user["id"]) or user


def bind_user(user: dict | None) -> None:
    _force_user.set(user)
    if user and user.get("tenant_id"):
        paths.bind_tenant(int(user["tenant_id"]))
    elif user is None:
        paths.bind_tenant(None)


def login_user(user: dict) -> None:
    from nicegui import app, ui

    app.storage.user["user_id"] = user["id"]
    app.storage.user["tenant_id"] = user.get("tenant_id")
    app.storage.user["role"] = user["role"]
    app.storage.user["username"] = user["username"]
    bind_user(user)
    if user.get("tenant_id"):
        from aerobooks import db

        db.init_db()
    if user["role"] == "admin":
        ui.navigate.to("/admin")
    else:
        ui.navigate.to("/")


def logout() -> None:
    from nicegui import app, ui

    try:
        app.storage.user.clear()
    except Exception:
        pass
    bind_user(None)
    ui.navigate.to("/login")


def current_user() -> dict | None:
    uid = None
    forced = _force_user.get()
    if forced:
        uid = forced.get("id")
    if not uid:
        try:
            from nicegui import app

            uid = app.storage.user.get("user_id")
        except Exception:
            uid = None
    if not uid:
        return None
    user = get_user(int(uid))
    if not user or user["status"] != "active":
        return None
    if user.get("tenant_id"):
        paths.bind_tenant(int(user["tenant_id"]))
    return user


def ensure_workspace_user() -> dict | None:
    from nicegui import ui

    if not has_admin():
        ui.navigate.to("/setup")
        return None
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return None
    if user["role"] == "admin":
        ui.navigate.to("/admin")
        return None
    if not user.get("tenant_id"):
        ui.navigate.to("/login")
        return None
    paths.bind_tenant(int(user["tenant_id"]))
    from aerobooks import db

    db.init_db()
    return user


def ensure_admin() -> dict | None:
    from nicegui import ui

    if not has_admin():
        ui.navigate.to("/setup")
        return None
    user = current_user()
    if not user:
        ui.navigate.to("/login")
        return None
    if user["role"] != "admin":
        ui.navigate.to("/")
        return None
    return user


def create_school_instructor(
    manager: dict,
    *,
    username: str,
    password: str,
    display_name: str,
    email: str = "",
    phone: str = "",
) -> dict:
    if manager.get("role") != "manager":
        raise ValueError("Only a flight school manager can add instructors.")
    name = validate_username(username)
    validate_password(password)
    if username_taken(name):
        raise ValueError("That username is already taken.")
    if not (display_name or "").strip():
        raise ValueError("Instructor name is required.")
    pw_hash, salt = hash_password(password)
    user_id = _insert_user(
        username=name,
        password_hash=pw_hash,
        salt=salt,
        role="school_instructor",
        display_name=display_name.strip(),
        email=(email or "").strip(),
        phone=(phone or "").strip(),
        tenant_id=int(manager["tenant_id"]),
        created_by_user_id=int(manager["id"]),
    )
    return get_user(user_id)


def list_tenant_users(tenant_id: int) -> list[dict]:
    with get_conn() as conn:
        return _rows(
            conn.execute(
                """
                SELECT * FROM users
                WHERE tenant_id = ?
                ORDER BY CASE role WHEN 'manager' THEN 0 ELSE 1 END, display_name, username
                """,
                (tenant_id,),
            )
        )


def instructor_options(tenant_id: int) -> list[dict]:
    users = list_tenant_users(tenant_id)
    return [
        u
        for u in users
        if u["role"] in ("manager", "school_instructor", "instructor") and u["status"] == "active"
    ]


def role_label(role: str) -> str:
    return {
        "admin": "Administrator",
        "instructor": "Independent instructor",
        "manager": "Flight school manager",
        "school_instructor": "School instructor",
    }.get(role, role)


def is_school_instructor(user: dict | None = None) -> bool:
    user = user or current_user()
    return bool(user and user.get("role") == "school_instructor")


def is_manager(user: dict | None = None) -> bool:
    user = user or current_user()
    return bool(user and user.get("role") == "manager")


def can_manage_team(user: dict | None = None) -> bool:
    return is_manager(user)


def can_edit_business(user: dict | None = None) -> bool:
    user = user or current_user()
    return bool(user and user.get("role") in ("instructor", "manager"))


def can_edit_rates(user: dict | None = None) -> bool:
    return can_edit_business(user)


def can_backup(user: dict | None = None) -> bool:
    return can_edit_business(user)
