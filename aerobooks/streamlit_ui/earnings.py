"""Earnings, hours, and expense snapshot."""

from __future__ import annotations

from datetime import date

import plotly.graph_objects as go
import streamlit as st

from aerobooks import db
from aerobooks.money import fmt_hours, fmt_money
from aerobooks.streamlit_ui import chrome


def render() -> None:
    today = date.today()
    chrome.page_title("Earnings", "What you billed, what you collected, and what it cost to instruct.")
    years = list(range(today.year, today.year - 6, -1))
    year = st.selectbox("Year", years)
    monthly = db.monthly_earnings(int(year))
    stats = db.dashboard_stats()
    ytd_billed = sum(m["billed"] for m in monthly)
    ytd_hours = sum(m["hours"] for m in monthly)
    collected = stats["ytd_collected"] if year == today.year else sum(m["collected"] for m in monthly)
    chrome.stats_html(
        [
            ("YTD collected", fmt_money(collected)),
            ("YTD billed", fmt_money(ytd_billed)),
            ("YTD expenses", fmt_money(sum(m["expenses"] for m in monthly))),
            (
                "YTD net",
                fmt_money(sum(m["net"] for m in monthly)),
                "",
                "good" if sum(m["net"] for m in monthly) >= 0 else "warn",
            ),
            ("YTD hours", fmt_hours(ytd_hours)),
            ("Outstanding AR", fmt_money(stats["outstanding"])),
        ]
    )

    fig = go.Figure()
    fig.add_bar(name="Collected", x=[m["label"] for m in monthly], y=[m["collected"] for m in monthly], marker_color="#1B365D")
    fig.add_bar(name="Expenses", x=[m["label"] for m in monthly], y=[m["expenses"] for m in monthly], marker_color="#C4A35A")
    fig.update_layout(
        barmode="group",
        height=320,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h"),
        yaxis_tickprefix="$",
        title=f"{year} collected vs expenses",
    )
    st.plotly_chart(fig, use_container_width=True)

    start, end = f"{year}-01-01", f"{year + 1}-01-01"
    by_type = db.hours_by_type_range(start, end)
    if by_type:
        pie = go.Figure(
            data=[go.Pie(labels=[r["label"] for r in by_type], values=[r["hours"] for r in by_type], hole=0.45)]
        )
        pie.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=30, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            title=f"{year} hours by training type",
        )
        st.plotly_chart(pie, use_container_width=True)

    table = [
        {
            "Month": m["label"],
            "Hours": fmt_hours(m["hours"]),
            "Billed": fmt_money(m["billed"]),
            "Collected": fmt_money(m["collected"]),
            "Expenses": fmt_money(m["expenses"]),
            "Net": fmt_money(m["net"]),
        }
        for m in monthly
    ]
    st.dataframe(table, hide_index=True, use_container_width=True)
