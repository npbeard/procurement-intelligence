"""
Executive Overview Page — What is the market?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from dashboard import db

# Consistent colour palette for white background
_BLUE   = "#1F5CE6"
_PURPLE = "#7B52D4"
_ORANGE = "#FF832B"
_GREEN  = "#24A148"
_PALETTE = [_BLUE, _PURPLE, _ORANGE, _GREEN, "#E63946", "#457B9D"]

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=False,
)


def render():
    tab1, tab2 = st.tabs(["OPPORTUNITIES (CN)", "AWARDS (CAN)"])

    with tab1:
        _render_opportunities()

    with tab2:
        _render_awards()


def _render_opportunities():
    s = db.cn_summary()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Open Tenders",      int(s["open_tenders"] or 0),
                help="Distinct contract notices (CN)")
    col2.metric("Countries",         int(s["countries"] or 0),
                help="Unique buyer countries")
    col3.metric("Total Estimated",   f"€{s['total_value_m'] or 0:.0f}M",
                help="Sum of lot values (EUR-denominated lots only)")
    col4.metric("Avg Lots / Tender", f"{s['avg_lots_per_tender'] or 0:.1f}",
                help="Average lots per notice")

    st.markdown("")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top countries by notice count")
        df = db.top_countries_by_notices()
        fig = px.bar(df, x="notices", y="country", orientation="h",
                     color_discrete_sequence=[_BLUE])
        fig.update_layout(**_LAYOUT, height=380,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top CPV divisions")
        df = db.top_cpv_divisions()
        df["label"] = df["cpv_division"] + " – " + df["cpv_label"].str[:28]
        fig = px.bar(df, x="lots", y="label", orientation="h",
                     color_discrete_sequence=[_PURPLE])
        fig.update_layout(**_LAYOUT, height=380,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Procurement type distribution")
        df = db.procurement_type_distribution()
        fig = go.Figure(go.Pie(
            labels=df["type"], values=df["lots"],
            hole=0.4,
            marker=dict(colors=_PALETTE),
            textposition="inside",
            textfont=dict(family="Inter", color="#FFFFFF", size=12),
        ))
        fig.update_layout(**_LAYOUT, height=340, showlegend=True,
                          legend=dict(font=dict(color="#374151")))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Largest open opportunities")
        df = db.largest_cn_lots(limit=8)
        df.columns = ["Title", "Country", "Est. Value", "CPV", "Div"]
        st.dataframe(df.drop(columns=["Div"]), use_container_width=True,
                     hide_index=True)


def _render_awards():
    s = db.can_summary()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Awards",        int(s["awards"] or 0))
    col2.metric("Total Awarded", f"€{s['total_awarded_m'] or 0:.0f}M")
    col3.metric("Avg Award",     f"€{s['avg_award_k'] or 0:.0f}K")
    col4.metric("Countries",     int(s["countries"] or 0))

    st.markdown("")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top countries by award value")
        df = db.top_countries_by_award_value()
        fig = px.bar(df, x="awarded_m", y="country", orientation="h",
                     color_discrete_sequence=[_BLUE])
        fig.update_layout(**_LAYOUT, height=380,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True,
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
