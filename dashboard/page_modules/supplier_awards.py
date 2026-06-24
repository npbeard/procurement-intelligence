"""
Supplier & Awards Page — Who is winning?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.express as px
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    s = db.can_summary()
    winners = db.top_winners(limit=15)

    # ── Metrics ─────────────────────────────────────────────────────────────
    ui.render_kpis([
        ("Total Awards", int(s["awards"] or 0), "Contract award notices (CAN)"),
        ("Unique Winners", int(winners.shape[0]),
         "Distinct winning organisations"),
        ("Total Awarded", f"€{s['total_awarded_m'] or 0:.0f}M", None),
        ("Avg Award", f"€{s['avg_award_k'] or 0:.0f}K", None),
    ])

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
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=380,
                          xaxis=dict(gridcolor=grid, showgrid=True,
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
                     color_discrete_sequence=[colors[1]])
        fig.update_layout(**layout, height=380,
                          xaxis=dict(gridcolor=grid, showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="",
                                     autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    st.subheader("Largest awarded contracts")
    df = db.largest_can_lots(limit=10)
    df.columns = ["Title", "Country", "Awarded", "Winner", "CPV"]
    st.dataframe(df, use_container_width=True, hide_index=True)
