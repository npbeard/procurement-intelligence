"""
Opportunity Radar Page — Which tenders should we prioritize?
Pulls real CN lots from silver; scores from gold once ML is wired.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard import db

_BLUE   = "#1F5CE6"
_PURPLE = "#7B52D4"
_ORANGE = "#FF832B"

_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
)

# IT-relevant CPV divisions (72=IT services, 48=software, 30=office/computing)
_IT_DIVISIONS = {"72", "48", "30"}


@st.cache_data(ttl=300, show_spinner=False)
def _load_cn_lots() -> pd.DataFrame:
    return db.query("""
        SELECT
            notice_publication_id,
            lot_id,
            COALESCE(lot_name, 'Unnamed lot')   AS title,
            buyer_country_code                  AS country,
            buyer_name,
            cpv_code,
            cpv_name,
            cpv_division,
            procurement_type                    AS type,
            lot_value_eur,
            submission_deadline_date            AS deadline
        FROM capstone.ted.silver_lots_enriched
        WHERE notice_type = 'ContractNotice'
        ORDER BY lot_value_eur DESC NULLS LAST
        LIMIT 500
    """)


def render():
    df = _load_cn_lots()

    # ── Sidebar-style filters (rendered inline) ─────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        min_val = st.number_input("Min Value (€)", 0, 100_000_000, 0, step=100_000,
                                  format="%d")
    with col2:
        countries = ["All"] + sorted(df["country"].dropna().unique().tolist())
        country   = st.selectbox("Country", countries)

    with col3:
        types     = ["All"] + sorted(df["type"].dropna().unique().tolist())
        proc_type = st.selectbox("Procurement Type", types)

    with col4:
        it_only = st.checkbox("IT-relevant only (CPV 72/48/30)", value=False)

    # ── Apply filters ────────────────────────────────────────────────────────
    mask = pd.Series(True, index=df.index)
    if min_val > 0:
        mask &= df["lot_value_eur"].fillna(0) >= min_val
    if country != "All":
        mask &= df["country"] == country
    if proc_type != "All":
        mask &= df["type"] == proc_type
    if it_only:
        mask &= df["cpv_division"].isin(_IT_DIVISIONS)

    filtered = df[mask].copy()
    st.caption(f"{len(filtered):,} lots match current filters")

    st.markdown("")

    # ── Opportunity table ────────────────────────────────────────────────────
    st.subheader("Matching Opportunities")

    display = filtered[["title", "country", "lot_value_eur",
                         "type", "cpv_name", "deadline"]].copy()
    display["lot_value_eur"] = display["lot_value_eur"].apply(
        lambda v: f"€{v:,.0f}" if pd.notna(v) else "—"
    )
    display.columns = ["Title", "Country", "Value", "Type", "CPV", "Deadline"]
    st.dataframe(display.head(50), use_container_width=True, hide_index=True)

    st.info(
        "**Priority Score** column will appear here once Bojana's ML model "
        "is connected (reads from `capstone.ted.gold_opportunity_scores`)."
    )

    st.markdown("")

    # ── Value distribution chart ─────────────────────────────────────────────
    plot_df = filtered[filtered["lot_value_eur"].notna()].copy()

    if not plot_df.empty:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Value by country")
            by_country = (plot_df.groupby("country", dropna=False)["lot_value_eur"]
                                 .sum()
                                 .reset_index()
                                 .rename(columns={"lot_value_eur": "total_m"})
                                 .assign(total_m=lambda x: x["total_m"] / 1e6)
                                 .sort_values("total_m", ascending=False)
                                 .head(10))
            fig = px.bar(by_country, x="total_m", y="country", orientation="h",
                         color_discrete_sequence=[_BLUE])
            fig.update_layout(**_LAYOUT, height=350,
                              xaxis=dict(gridcolor="#E5E7EB", showgrid=True,
                                         title="€M"),
                              yaxis=dict(showgrid=False, title="",
                                         autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Value by CPV division")
            by_cpv = (plot_df.groupby("cpv_division", dropna=False)["lot_value_eur"]
                             .sum()
                             .reset_index()
                             .rename(columns={"lot_value_eur": "total_m"})
                             .assign(total_m=lambda x: x["total_m"] / 1e6)
                             .sort_values("total_m", ascending=False)
                             .head(10))
            fig = px.bar(by_cpv, x="total_m", y="cpv_division", orientation="h",
                         color_discrete_sequence=[_PURPLE])
            fig.update_layout(**_LAYOUT, height=350,
                              xaxis=dict(gridcolor="#E5E7EB", showgrid=True,
                                         title="€M"),
                              yaxis=dict(showgrid=False, title="",
                                         autorange="reversed"))
            st.plotly_chart(fig, use_container_width=True)
