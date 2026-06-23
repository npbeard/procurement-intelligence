"""
Buyer Intelligence Page — Who is buying?
Powered by real silver tables via dashboard.db.
"""

import streamlit as st
import plotly.express as px
from dashboard import db

_BLUE   = "#1F5CE6"
_PURPLE = "#7B52D4"
_ORANGE = "#FF832B"
_PALETTE = [_BLUE, _PURPLE, _ORANGE, "#24A148", "#E63946", "#457B9D", "#FFB703", "#8ECAE6"]

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=False,
)


def render():
    buyers = db.top_buyers(limit=20)

    # ── Top-line metrics ────────────────────────────────────────────────────
    total_buyers   = int(buyers.shape[0])
    total_spend_m  = float(buyers["total_spend_m"].sum() or 0)
    avg_tenders    = float(buyers["tenders"].mean() or 0)

    col1, col2, col3 = st.columns(3)
    col1.metric("Top Buyers shown",  total_buyers,
                help="Ranked by total procurement spend")
    col2.metric("Combined Spend",    f"€{total_spend_m:.0f}M",
                help="Sum of EUR-denominated lot values")
    col3.metric("Avg Tenders/Buyer", f"{avg_tenders:.1f}",
                help="Average number of notices per buyer")

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
                     color_discrete_sequence=[_BLUE])
        fig.update_layout(**_LAYOUT, height=340,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Buyers by country")
        df_country = db.buyer_country_distribution(limit=12)
        fig = px.bar(df_country, x="buyers", y="country", orientation="h",
                     color_discrete_sequence=[_PURPLE])
        fig.update_layout(**_LAYOUT, height=340,
                          xaxis=dict(gridcolor="#E5E7EB", showgrid=True, title=""),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    # ── Buyer detail drill-down ─────────────────────────────────────────────
    st.subheader("Buyer Profile")

    buyer_names = buyers["buyer_name"].dropna().tolist()
    selected = st.selectbox("Select a buyer", buyer_names)

    if selected:
        row = buyers[buyers["buyer_name"] == selected].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tenders",        int(row["tenders"]))
        c2.metric("Total Spend",    f"€{row['total_spend_m']:.2f}M")
        c3.metric("Avg per Tender", f"€{row['avg_spend_k']:.0f}K")
        c4.metric("Country",        row["country"] or "—")

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
