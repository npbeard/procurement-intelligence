"""
Supplier & Awards Page — Who is winning?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.express as px
from dashboard import db

_BLUE   = "#1F5CE6"
_PURPLE = "#7B52D4"
_ORANGE = "#FF832B"
_PALETTE = [_BLUE, _PURPLE, _ORANGE, "#24A148", "#E63946", "#457B9D"]

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=False,
)


def render():
    s = db.can_summary()
    winners = db.top_winners(limit=15)

    # ── Metrics ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Awards",    int(s["awards"] or 0),
                help="Contract award notices (CAN)")
    col2.metric("Unique Winners",  int(winners.shape[0]),
                help="Distinct winning organisations")
    col3.metric("Total Awarded",   f"€{s['total_awarded_m'] or 0:.0f}M")
    col4.metric("Avg Award",       f"€{s['avg_award_k'] or 0:.0f}K")

    st.markdown("")

    # ── Winners table ────────────────────────────────────────────────────────
    st.subheader("Top Award Winners")
    display = winners.copy()
    display.columns = ["Organization", "Country", "Awards", "Won (€M)", "Avg (€K)"]
    display.insert(0, "Rank", range(1, len(display) + 1))
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("")

    # ── Charts ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Award value by winner")
        df = winners.head(10)
        fig = px.bar(df, x="total_won_m", y="organization", orientation="h",
                     color_discrete_sequence=[_BLUE])
        fig.update_layout(**_LAYOUT, height=380,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True,
                                     title="€M won"),
                          yaxis=dict(showgrid=False, title="",
                                     autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Winners by country")
        by_country = (winners.groupby("country", dropna=False)
                             .agg(awards=("awards", "sum"))
                             .reset_index()
                             .sort_values("awards", ascending=False)
                             .head(12))
        fig = px.bar(by_country, x="awards", y="country", orientation="h",
                     color_discrete_sequence=[_PURPLE])
        fig.update_layout(**_LAYOUT, height=380,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="",
                                     autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    st.subheader("Largest awarded contracts")
    df = db.largest_can_lots(limit=10)
    df.columns = ["Title", "Country", "Awarded", "Winner", "CPV"]
    st.dataframe(df, use_container_width=True, hide_index=True)
