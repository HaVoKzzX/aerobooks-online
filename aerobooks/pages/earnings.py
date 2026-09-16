"""Earnings, hours, and expense snapshot."""

from datetime import date

import plotly.graph_objects as go
from nicegui import ui

from aerobooks import db
from aerobooks.money import fmt_hours, fmt_money
from aerobooks.theme import frame, page_title, stat_card


def register() -> None:
    @ui.page("/earnings")
    def page():
        with frame("Earnings", "/earnings") as user:
            if not user:
                return
            render()


def render() -> None:
    today = date.today()
    page_title("Earnings", "What you billed, what you collected, and what it cost to instruct.")

    year_sel = ui.select(
        {y: str(y) for y in range(today.year, today.year - 6, -1)},
        value=today.year,
        label="Year",
    ).props("outlined dense").classes("w-32 mb-3")

    @ui.refreshable
    def body():
        year = int(year_sel.value)
        monthly = db.monthly_earnings(year)
        stats = db.dashboard_stats()
        ytd_billed = sum(m["billed"] for m in monthly)
        ytd_hours = sum(m["hours"] for m in monthly)

        with ui.row().classes("gap-3 w-full mb-4 flex-wrap"):
            stat_card("YTD collected", fmt_money(stats["ytd_collected"] if year == today.year else sum(m["collected"] for m in monthly)))
            stat_card("YTD billed", fmt_money(ytd_billed))
            stat_card("YTD expenses", fmt_money(sum(m["expenses"] for m in monthly)))
            stat_card(
                "YTD net",
                fmt_money(sum(m["net"] for m in monthly)),
                kind="good" if sum(m["net"] for m in monthly) >= 0 else "warn",
            )
            stat_card("YTD hours", fmt_hours(ytd_hours))
            stat_card("Outstanding AR", fmt_money(stats["outstanding"]))

        fig = go.Figure()
        fig.add_bar(name="Collected", x=[m["label"] for m in monthly], y=[m["collected"] for m in monthly], marker_color="#1B365D")
        fig.add_bar(name="Expenses", x=[m["label"] for m in monthly], y=[m["expenses"] for m in monthly], marker_color="#C4A35A")
        fig.update_layout(
            barmode="group",
            height=320,
            margin=dict(l=20, r=20, t=30, b=20),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h"),
            yaxis_tickprefix="$",
            title=f"{year} collected vs expenses",
        )
        ui.plotly(fig).classes("w-full ab-card p-2 mb-4")

        start, end = f"{year}-01-01", f"{year+1}-01-01"
        by_type = db.hours_by_type_range(start, end)
        if by_type:
            pie = go.Figure(
                data=[
                    go.Pie(
                        labels=[r["label"] for r in by_type],
                        values=[r["hours"] for r in by_type],
                        hole=0.45,
                    )
                ]
            )
            pie.update_layout(
                height=320,
                margin=dict(l=20, r=20, t=30, b=20),
                paper_bgcolor="rgba(0,0,0,0)",
                title=f"{year} hours by training type",
            )
            ui.plotly(pie).classes("w-full ab-card p-2 mb-4")

        columns = [
            {"name": "month", "label": "Month", "field": "label"},
            {"name": "hours", "label": "Hours", "field": "hours_label"},
            {"name": "billed", "label": "Billed", "field": "billed_label"},
            {"name": "collected", "label": "Collected", "field": "collected_label"},
            {"name": "expenses", "label": "Expenses", "field": "expenses_label"},
            {"name": "net", "label": "Net", "field": "net_label"},
        ]
        rows = [
            {
                "label": m["label"],
                "hours_label": fmt_hours(m["hours"]),
                "billed_label": fmt_money(m["billed"]),
                "collected_label": fmt_money(m["collected"]),
                "expenses_label": fmt_money(m["expenses"]),
                "net_label": fmt_money(m["net"]),
            }
            for m in monthly
        ]
        ui.table(columns=columns, rows=rows).classes("w-full ab-card")

    year_sel.on("update:model-value", lambda _: body.refresh())
    body()
