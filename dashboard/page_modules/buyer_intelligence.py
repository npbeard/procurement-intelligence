"""
Buyer Intelligence Page — Who is buying?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.express as px
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    buyers = db.top_buyers(limit=20)

    # ── Top-line metrics ────────────────────────────────────────────────────
    total_buyers  = int(buyers.shape[0])
    total_spend_m = float(buyers["total_spend_m"].sum() or 0)
    avg_tenders   = float(buyers["tenders"].mean() or 0)

    _render_metrics([
        ("Top Buyers shown", total_buyers, "Ranked by total procurement spend"),
        ("Combined Spend", f"€{total_spend_m:.0f}M",
         "Sum of EUR-denominated lot values"),
        ("Avg Tenders/Buyer", f"{avg_tenders:.1f}",
         "Average number of notices per buyer"),
    ])

    st.markdown("")

    # ── Buyer ranking table ─────────────────────────────────────────────────
    st.subheader("Top Buyers by Spend")
    display = buyers.copy()
    display.columns = ["Buyer", "Country", "Type", "Tenders",
                       "Total Spend (€M)", "Avg Spend (€K)"]
    display.insert(0, "Rank", range(1, len(display) + 1))
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("")

    # ── Two analysis charts ─────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Buyers by legal type")
        df_type = db.buyer_type_distribution()
        fig = px.bar(df_type, x="buyers", y="type", orientation="h",
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=340,
                          xaxis=dict(gridcolor=grid, showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Buyers by country")
        df_country = db.buyer_country_distribution(limit=12)
        fig = px.bar(df_country, x="buyers", y="country", orientation="h",
                     color_discrete_sequence=[colors[1]])
        fig.update_layout(**layout, height=340,
                          xaxis=dict(gridcolor=grid, showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    # ── Buyer detail drill-down ─────────────────────────────────────────────
    st.subheader("Buyer Profile")

    buyer_names = buyers["buyer_name"].dropna().tolist()
    selected = st.selectbox("Select a buyer", buyer_names)

    if selected:
        row = buyers[buyers["buyer_name"] == selected].iloc[0]

        _render_metrics([
            ("Tenders", int(row["tenders"]), None),
            ("Total Spend", f"€{row['total_spend_m']:.2f}M", None),
            ("Avg per Tender", f"€{row['avg_spend_k']:.0f}K", None),
            ("Country", row["country"] or "—", None),
        ])

        st.markdown("")

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"""
**Organisation type**
{row['type'] or 'Not specified'}

**Country**
{row['country'] or 'Not specified'}
""")
        with col2:
            st.info(f"""
**Procurement activity**
- {int(row['tenders'])} tender(s) published
- Average contract: €{row['avg_spend_k']:.0f}K
- Total procurement budget: €{row['total_spend_m']:.2f}M
""")


def _render_metrics(metrics: list[tuple]):
    """metrics: list of (label, value, help_text|None). Gradient KPI cards
    in both themes."""
    ui.render_kpis(metrics)
