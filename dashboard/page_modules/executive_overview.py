"""
Executive Overview Page — What is the market?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    tab1, tab2 = st.tabs(["OPPORTUNITIES (CN)", "AWARDS (CAN)"])

    with tab1:
        _render_opportunities(dark)

    with tab2:
        _render_awards(dark)


def _render_metrics(metrics: list[tuple]):
    """metrics: list of (label, value, help_text|None). Gradient KPI cards
    in both themes."""
    ui.render_kpis(metrics)


def _render_opportunities(dark: bool):
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    s = db.cn_summary()

    _render_metrics([
        ("Open Tenders", int(s["open_tenders"] or 0),
         "Distinct contract notices (CN)"),
        ("Countries", int(s["countries"] or 0), "Unique buyer countries"),
        ("Total Estimated", f"€{s['total_value_m'] or 0:.0f}M",
         "Sum of lot values (EUR-denominated lots only)"),
        ("Avg Lots / Tender", f"{s['avg_lots_per_tender'] or 0:.1f}",
         "Average lots per notice"),
    ])

    st.markdown("")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top countries by notice count")
        df = db.top_countries_by_notices()
        fig = px.bar(df, x="notices", y="country", orientation="h",
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=380,
                          xaxis=dict(gridcolor=grid, showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top CPV divisions")
        df = db.top_cpv_divisions()
        df["label"] = df["cpv_division"] + " – " + df["cpv_label"].str[:28]
        fig = px.bar(df, x="lots", y="label", orientation="h",
                     color_discrete_sequence=[colors[1]])
        fig.update_layout(**layout, height=380,
                          xaxis=dict(gridcolor=grid, showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Procurement type distribution")
        df = db.procurement_type_distribution()
        fig = go.Figure(go.Pie(
            labels=df["type"], values=df["lots"],
            hole=0.4,
            marker=dict(colors=colors),
            textposition="inside",
            textfont=dict(family="Inter", color="#FFFFFF", size=12),
        ))
        fig.update_layout(**{**layout, "showlegend": True}, height=340,
                          legend=dict(font=dict(color=layout["font"]["color"])))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Largest open opportunities")
        df = db.largest_cn_lots(limit=8)
        df.columns = ["Title", "Country", "Est. Value", "CPV", "Div"]
        st.dataframe(df.drop(columns=["Div"]), use_container_width=True,
                     hide_index=True)


def _render_awards(dark: bool):
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    s = db.can_summary()

    _render_metrics([
        ("Awards", int(s["awards"] or 0), None),
        ("Total Awarded", f"€{s['total_awarded_m'] or 0:.0f}M", None),
        ("Avg Award", f"€{s['avg_award_k'] or 0:.0f}K", None),
        ("Countries", int(s["countries"] or 0), None),
    ])

    st.markdown("")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top countries by award value")
        df = db.top_countries_by_award_value()
        fig = px.bar(df, x="awarded_m", y="country", orientation="h",
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=380,
                          xaxis=dict(gridcolor=grid, showgrid=True,
                                     title="€M awarded"),
                          yaxis=dict(showgrid=False, title="",
                                     autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top award winners")
        df = db.top_winners(limit=10)
        df.columns = ["Organization", "Country", "Awards", "Won (€M)", "Avg (€K)"]
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("Largest awarded contracts")
    df = db.largest_can_lots(limit=10)
    df.columns = ["Title", "Country", "Awarded", "Winner", "CPV"]
    st.dataframe(df, use_container_width=True, hide_index=True)
