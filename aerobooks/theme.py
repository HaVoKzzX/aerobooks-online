"""Shared layout, colors, and small UI helpers."""

from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from aerobooks import auth, db
from aerobooks.money import fmt_hours, fmt_money

NAVY = "#1B365D"
GOLD = "#C4A35A"
INK = "#1C1917"
PAPER = "#F4F1EA"
NAV = [
    ("/", "Dashboard", "space_dashboard"),
    ("/students", "Students", "school"),
    ("/hours", "Log Hours", "flight"),
    ("/invoices", "Invoices", "receipt_long"),
    ("/expenses", "Expenses", "account_balance_wallet"),
    ("/earnings", "Earnings", "trending_up"),
    ("/settings", "Settings", "settings"),
]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Libre+Baskerville:wght@700&display=swap');

:root {
  --ab-navy: #1B365D;
  --ab-navy-2: #152A4A;
  --ab-gold: #C4A35A;
  --ab-paper: #F4F1EA;
  --ab-ink: #1C1917;
  --ab-muted: #6B6459;
}

body, .q-page, .nicegui-content {
  font-family: 'DM Sans', 'Segoe UI', sans-serif;
  background: var(--ab-paper) !important;
  color: var(--ab-ink);
}

.ab-header {
  background: var(--ab-navy) !important;
  color: white;
  min-height: 56px;
}
.ab-header .q-btn { color: white; }

.ab-drawer {
  background: #10233F !important;
  color: #F7F4EC !important;
  padding: 12px 10px 24px 10px;
}
.ab-drawer .q-drawer__content { color: #F7F4EC; }
.ab-brand {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 22px;
  letter-spacing: 0.02em;
  color: #FFFcf7 !important;
}
.ab-brand-sub { color: #E8C56A !important; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; }

.ab-nav-btn,
.ab-drawer .ab-nav-btn.q-btn,
.ab-drawer .ab-nav-btn .q-btn__content,
.ab-drawer .ab-nav-btn .q-btn__content span {
  justify-content: flex-start !important;
  color: #FFFcf7 !important;
}
.ab-nav-btn {
  width: 100%;
  border-radius: 10px;
  font-weight: 600;
}
.ab-drawer .ab-nav-btn .q-icon {
  color: #E8C56A !important;
}
.ab-nav-active,
.ab-drawer .ab-nav-active.q-btn,
.ab-drawer .ab-nav-active .q-btn__content,
.ab-drawer .ab-nav-active .q-btn__content span {
  background: rgba(232, 197, 106, 0.22) !important;
  color: #ffffff !important;
}

.ab-content { padding: 20px 28px 40px 28px; max-width: 1280px; }

.ab-h1 {
  font-family: 'Libre Baskerville', Georgia, serif;
  font-size: 28px;
  color: var(--ab-navy);
  margin: 0;
}
.ab-sub { color: var(--ab-muted); font-size: 14px; }

.ab-card {
  background: #FFFcf7;
  border: 1px solid #E6E0D4;
  border-radius: 14px;
  box-shadow: 0 1px 2px rgba(27,54,93,0.04);
}
.ab-stat {
  min-width: 160px;
  flex: 1;
}
.ab-stat .ab-stat-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ab-muted);
}
.ab-stat .ab-stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--ab-navy);
  line-height: 1.2;
}
.ab-stat.warn .ab-stat-value { color: #9B2C2C; }
.ab-stat.good .ab-stat-value { color: #1B7A4E; }
.ab-stat.gold .ab-stat-value { color: #8A6A2A; }

.ab-chip {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 2px 8px;
}
.ab-status-paid { background: #E4F5EA; color: #1B7A4E; }
.ab-status-unpaid { background: #FFF3D6; color: #8A6A2A; }
.ab-status-partial { background: #E8F1FA; color: #1B365D; }
.ab-status-overdue { background: #FDECEC; color: #9B2C2C; }
.ab-status-draft { background: #EEECE7; color: #5C564C; }
.ab-status-void { background: #EEECE7; color: #8A847A; text-decoration: line-through; }
.ab-status-active { background: #E4F5EA; color: #1B7A4E; }
.ab-status-soloed { background: #E8F1FA; color: #1B365D; }
.ab-status-checkride_ready { background: #FFF3D6; color: #8A6A2A; }
.ab-status-graduated { background: #EDE7F6; color: #5E35B1; }
.ab-status-inactive { background: #EEECE7; color: #8A847A; }

.ab-alert {
  background: #FDECEC;
  border-left: 4px solid #9B2C2C;
  border-radius: 10px;
}
.ab-alert-gold {
  background: #FFF6E0;
  border-left: 4px solid #C4A35A;
  border-radius: 10px;
}

.q-table { background: transparent; }
.q-table th { font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: #6B6459; }
.q-btn.ab-primary { background: var(--ab-navy) !important; color: white !important; }
.q-btn.ab-gold { background: var(--ab-gold) !important; color: #1B365D !important; font-weight: 600; }

.ab-auth {
  min-height: 100vh;
  background:
    radial-gradient(1200px 500px at 10% -10%, rgba(196,163,90,0.18), transparent 50%),
    linear-gradient(180deg, #10233F 0%, #1B365D 42%, #F4F1EA 42%);
}
.ab-auth-card {
  width: 100%;
  max-width: 460px;
  background: #FFFcf7;
  border-radius: 16px;
  border: 1px solid #E6E0D4;
  box-shadow: 0 18px 40px rgba(11,31,58,0.18);
}
.ab-lock-note {
  background: #FFF6E0;
  border-left: 4px solid #C4A35A;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: #5C564C;
}
"""


def apply_theme() -> None:
    ui.colors(
        primary=NAVY,
        secondary=GOLD,
        accent="#3D7EA6",
        dark="#0B1F3A",
        positive="#1B7A4E",
        negative="#B42318",
        warning="#C4A35A",
        info="#3D7EA6",
    )
    ui.add_head_html(f"<style>{CSS}</style>")
    ui.dark_mode(False)


def event_row(e) -> dict:
    """Pull the table row dict out of a NiceGUI/Quasar event."""
    args = getattr(e, "args", e)
    if isinstance(args, dict) and "id" in args:
        return args
    if isinstance(args, (list, tuple)):
        for item in reversed(args):
            if isinstance(item, dict) and "id" in item:
                return item
    raise ValueError("Could not read table row from event")


def status_chip(status: str) -> None:
    label = (status or "").replace("_", " ")
    ui.label(label).classes(f"ab-chip ab-status-{status}")


def stat_card(label: str, value: str, hint: str = "", kind: str = "") -> None:
    cls = f"ab-card ab-stat p-4 {kind}".strip()
    with ui.card().classes(cls):
        ui.label(label).classes("ab-stat-label")
        ui.label(value).classes("ab-stat-value")
        if hint:
            ui.label(hint).classes("text-xs text-gray-500 mt-1")


def page_title(title: str, subtitle: str = ""):
    with ui.row().classes("items-end justify-between w-full mb-4 gap-3"):
        with ui.column().classes("gap-0"):
            ui.label(title).classes("ab-h1")
            if subtitle:
                ui.label(subtitle).classes("ab-sub")
        return ui.row().classes("items-center gap-2")


def _nav_items(user: dict) -> list[tuple[str, str, str]]:
    items = list(NAV)
    if user.get("role") == "manager":
        items.insert(-1, ("/team", "Instructors", "groups"))
    return items


@contextmanager
def frame(title: str, path: str):
    apply_theme()
    user = auth.ensure_workspace_user()
    if not user:
        yield None
        return
    ui.page_title(f"{title} · AeroBooks")
    stats = db.dashboard_stats()
    overdue = stats["overdue_30_count"]
    who = user.get("display_name") or user.get("username") or ""

    with ui.header().classes("ab-header items-center justify-between px-4"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("flight_takeoff", size="28px").style("color: #C4A35A")
            with ui.column().classes("gap-0"):
                ui.label("AeroBooks").classes("text-lg font-bold leading-none")
                ui.label(db.display_name()).classes("text-xs opacity-80")
        with ui.row().classes("items-center gap-3"):
            if overdue:
                ui.button(
                    f"{overdue} overdue 30+ days",
                    icon="warning",
                    on_click=lambda: ui.navigate.to("/invoices?status=overdue_30"),
                ).props("flat dense").classes("text-amber-200")
            ui.button("Log hours", icon="add", on_click=lambda: ui.navigate.to("/hours")).props("flat dense")
            ui.button("New invoice", icon="receipt", on_click=lambda: ui.navigate.to("/invoices/new")).props(
                "unelevated dense"
            ).classes("ab-gold")
            ui.button(who, icon="logout", on_click=auth.logout).props("flat dense").tooltip("Sign out")

    with ui.left_drawer(fixed=True, bordered=False).classes("ab-drawer").props("width=220"):
        ui.label("AeroBooks").classes("ab-brand px-2 mt-2")
        ui.label(auth.role_label(user["role"])).classes("ab-brand-sub px-2 mb-4")
        for href, label, icon in _nav_items(user):
            active = path == href or (href != "/" and path.startswith(href))
            btn = ui.button(label, icon=icon, on_click=lambda h=href: ui.navigate.to(h)).props(
                "flat no-caps unelevated text-color=white"
            ).classes("ab-nav-btn" + (" ab-nav-active" if active else ""))
            if href == "/invoices" and stats["overdue_count"]:
                btn.props(f'badge="{stats["overdue_count"]}"')

    with ui.column().classes("ab-content w-full"):
        yield user


@contextmanager
def auth_shell(title: str):
    apply_theme()
    ui.page_title(f"{title} · AeroBooks")
    with ui.column().classes("ab-auth w-full items-center justify-center px-4 py-10"):
        with ui.column().classes("items-center mb-6"):
            ui.icon("flight_takeoff", size="48px").style("color: #E8C56A")
            ui.label("AeroBooks").classes("ab-brand text-center")
            ui.label("CFI invoicing").classes("ab-brand-sub")
        with ui.card().classes("ab-auth-card p-6"):
            yield


@contextmanager
def admin_frame(title: str, path: str):
    apply_theme()
    user = auth.ensure_admin()
    if not user:
        yield None
        return
    ui.page_title(f"{title} · AeroBooks Admin")
    pending = auth.pending_request_count()
    with ui.header().classes("ab-header items-center justify-between px-4"):
        with ui.row().classes("items-center gap-3"):
            ui.icon("admin_panel_settings", size="28px").style("color: #C4A35A")
            with ui.column().classes("gap-0"):
                ui.label("AeroBooks Admin").classes("text-lg font-bold leading-none")
                ui.label(user.get("display_name") or user["username"]).classes("text-xs opacity-80")
        ui.button("Sign out", icon="logout", on_click=auth.logout).props("flat dense")
    with ui.left_drawer(fixed=True, bordered=False).classes("ab-drawer").props("width=220"):
        ui.label("Admin").classes("ab-brand px-2 mt-2")
        ui.label("Access control").classes("ab-brand-sub px-2 mb-4")
        for href, label, icon in (
            ("/admin", "Requests", "how_to_reg"),
            ("/admin/users", "Users", "group"),
        ):
            active = path == href
            btn = ui.button(label, icon=icon, on_click=lambda h=href: ui.navigate.to(h)).props(
                "flat no-caps unelevated text-color=white"
            ).classes("ab-nav-btn" + (" ab-nav-active" if active else ""))
            if href == "/admin" and pending:
                btn.props(f'badge="{pending}"')
    with ui.column().classes("ab-content w-full"):
        yield user
