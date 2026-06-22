"""
Trends & Forecasts Page — What is changing?
Uses real daily notice volume from silver tables.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dashboard import db

_BLUE   = "#1F5CE6"
_PURPLE = "#7B52D4"

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
)


def render():
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

    c1, c2, c3 = st.columns(3)
    c1.metric("Notices in period", f"{total:,}")
    c2.metric("Peak day",          f"{peak:,}")
    c3.metric("Daily average",     f"{avg:.1f}")

    st.markdown("")

    # ── Daily volume chart ───────────────────────────────────────────────────
    st.subheader("Daily notice volume")
    fig = px.bar(df_filtered, x="issue_date", y="notices",
                 color_discrete_sequence=[_BLUE])
    fig.update_layout(**_LAYOUT, height=340,
                      xaxis=dict(gridcolor="#E5E7EB", showgrid=False, title=""),
                      yaxis=dict(gridcolor="#E5E7EB", showgrid=True,
                                 title="notices / day"))
    st.plotly_chart(fig, use_container_width=True)

    # ── Cumulative volume ────────────────────────────────────────────────────
    st.subheader("Cumulative notices published")
    df_filtered = df_filtered.copy()
    df_filtered["cumulative"] = df_filtered["notices"].cumsum()
    fig = px.line(df_filtered, x="issue_date", y="cumulative",
                  color_discrete_sequence=[_PURPLE])
    fig.update_layout(**_LAYOUT, height=300,
                      xaxis=dict(gridcolor="#E5E7EB", showgrid=False, title=""),
                      yaxis=dict(gridcolor="#E5E7EB", showgrid=True,
                                 title="cumulative notices"))
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "**Note:** Forecast / AI projection features will be enabled once "
        "the ML gold layer is connected (Bojana's opportunity scoring model)."
    )
