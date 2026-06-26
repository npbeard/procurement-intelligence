"""
Opportunity Radar Page — Which tenders should we prioritize?
Reads from gold_it_lots (IT-filtered CN lots, pre-built by dbt daily).
opportunity_score column populates automatically once Bojana's XGBoost
model writes to capstone.ted.gold_opportunity_scores.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard import db, ui


def render():
    theme = ui.chart_theme(ui.is_dark())
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    df = db.it_lots(limit=500)

    # ── Filters ──────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    with col1:
        min_val = st.number_input("Min Value (€)", 0, 100_000_000, 0,
                                  step=100_000, format="%d")
    with col2:
        countries = ["All"] + sorted(df["country"].dropna().unique().tolist())
        country   = st.selectbox("Country", countries)

    with col3:
        types     = ["All"] + sorted(df["type"].dropna().unique().tolist())
        proc_type = st.selectbox("Procurement Type", types)

    # ── Apply filters ────────────────────────────────────────────────────────
    mask = pd.Series(True, index=df.index)
    if min_val > 0:
        mask &= df["lot_value_eur"].fillna(0) >= min_val
    if country != "All":
        mask &= df["country"] == country
    if proc_type != "All":
        mask &= df["type"] == proc_type

    filtered = df[mask].copy()
    st.caption(f"{len(filtered):,} IT-relevant lots match current filters")

    st.markdown("")

    # ── Opportunity table ────────────────────────────────────────────────────
    st.subheader("IT Opportunities")

    has_ml_score = filtered["opportunity_score"].notna().any()
    score_col    = "opportunity_score" if has_ml_score else "value_proxy_score"
    score_label  = "ML Score" if has_ml_score else "Value Score (proxy)"

    display_cols  = ["title", "country", "lot_value_eur", "type", "cpv_name", "deadline", score_col]
    display_names = ["Title", "Country", "Value", "Type", "CPV", "Deadline", score_label]

    # predicted_competition arrives as a raw probability (0–1); bucket it for display
    has_competition = (
        "predicted_competition" in filtered.columns
        and filtered["predicted_competition"].notna().any()
    )
    if has_competition:
        def _comp_label(v):
            if pd.isna(v): return "—"
            return "Low" if v < 0.4 else ("Medium" if v < 0.7 else "High")
        filtered = filtered.copy()
        filtered["competition"] = filtered["predicted_competition"].map(_comp_label)
        display_cols.append("competition")
        display_names.append("Competition")

    display = filtered[display_cols].copy()

    # opportunity_score is raw expected value (€); percentile-rank to 0–10 for the progress bar
    if has_ml_score:
        display[score_col] = (filtered[score_col].rank(pct=True) * 10).round(1)

    display["lot_value_eur"] = display["lot_value_eur"].apply(
        lambda v: f"€{v:,.0f}" if pd.notna(v) else "—"
    )
    display.columns = display_names

    col_config = {
        score_label: st.column_config.ProgressColumn(
            score_label, min_value=0, max_value=10,
        )
    }
    st.dataframe(display.head(50), use_container_width=True,
                 hide_index=True, column_config=col_config)

    if not has_ml_score:
        st.info(
            "Showing **value proxy score** (log-scaled lot value). "
            "Bojana's ML competition/attractiveness score will replace this "
            "once `capstone.ted.gold_opportunity_scores` is written."
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
                         color_discrete_sequence=[colors[0]])
            fig.update_layout(**layout, height=350,
                              xaxis=dict(gridcolor=grid, showgrid=True,
                                         title="€M"),
                              yaxis=dict(showgrid=False, title="",
                                         autorange="reversed"))
            fig.update_traces(hovertemplate=ui.hover_xy("Value (€M)", "Country"))
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
                         color_discrete_sequence=[colors[1]])
            fig.update_layout(**layout, height=350,
                              xaxis=dict(gridcolor=grid, showgrid=True,
                                         title="€M"),
                              yaxis=dict(showgrid=False, title="",
                                         autorange="reversed"))
            fig.update_traces(hovertemplate=ui.hover_xy("Value (€M)", "CPV Division"))
            st.plotly_chart(fig, use_container_width=True)
