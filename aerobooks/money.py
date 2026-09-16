"""Money and display helpers."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime


def D(value) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value) -> float:
    return float(D(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def hours(value) -> float:
    return float(D(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fmt_money(value) -> str:
    amount = money(value)
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def fmt_hours(value) -> str:
    return f"{hours(value):.1f}"


def fmt_date(value) -> str:
    if not value:
        return "—"
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime("%b %d, %Y")
    text = str(value)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return str(value)


def iso_today() -> str:
    return date.today().isoformat()


def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def days_between(start, end=None) -> int | None:
    start_d = parse_date(start)
    end_d = parse_date(end) or date.today()
    if not start_d:
        return None
    return (end_d - start_d).days
