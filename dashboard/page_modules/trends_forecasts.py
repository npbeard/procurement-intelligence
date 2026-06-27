"""
Trends & Forecasts Page — What is changing?
Uses real daily notice volume from silver tables.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    df = db.notice_volume_by_date()

    if df.empty:
        st.info("No date data available yet.")
        return

    df["issue_date"] = pd.to_datetime(df["issue_date"], errors="coerce")
    df = df.dropna(subset=["issue_date"]).sort_values("issue_date")

    # ── Period selector ─────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 4])
    with col1:
        period = st.selectbox("Period", ["Last 30 Days", "Last 90 Days", "All Time"])

    if period == "Last 30 Days":
        cutoff = df["issue_date"].max() - pd.Timedelta(days=30)
    elif period == "Last 90 Days":
        cutoff = df["issue_date"].max() - pd.Timedelta(days=90)
    else:
        cutoff = df["issue_date"].min()

    df_filtered = df[df["issue_date"] >= cutoff].copy()

    # ── Trend metrics ────────────────────────────────────────────────────────
    total = int(df_filtered["notices"].sum())
    peak  = int(df_filtered["notices"].max())
    days  = int((df_filtered["issue_date"].max() - df_filtered["issue_date"].min()).days) + 1
    avg   = round(total / max(days, 1), 1)

    ui.render_kpis([
        ("Notices in period", f"{total:,}", None),
        ("Peak day", f"{peak:,}", None),
        ("Daily average", f"{avg:.1f}", None),
    ])

    st.markdown("")

    # ── Daily volume chart ───────────────────────────────────────────────────
    st.subheader("Daily notice volume")
    fig = px.bar(df_filtered, x="issue_date", y="notices",
                 color_discrete_sequence=[colors[0]])
    fig.update_layout(**layout, height=340,
                      xaxis=dict(gridcolor=grid, showgrid=False, title=""),
                      yaxis=dict(gridcolor=grid, showgrid=True,
                                 title="notices / day"))
    fig.update_traces(hovertemplate=ui.hover_xy("Date", "Notices"))
    st.plotly_chart(fig, use_container_width=True)

    # ── Cumulative volume ────────────────────────────────────────────────────
    st.subheader("Cumulative notices published")
    df_filtered = df_filtered.copy()
    df_filtered["cumulative"] = df_filtered["notices"].cumsum()
    fig = px.line(df_filtered, x="issue_date", y="cumulative",
                  color_discrete_sequence=[colors[1]])
    fig.update_layout(**layout, height=300,
                      xaxis=dict(gridcolor=grid, showgrid=False, title=""),
                      yaxis=dict(gridcolor=grid, showgrid=True,
                                 title="cumulative notices"))
    fig.update_traces(hovertemplate=ui.hover_xy("Date", "Cumulative"))
    st.plotly_chart(fig, use_container_width=True)

