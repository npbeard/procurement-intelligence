"""
PIN Monitor Page — Who is about to buy, before the tender even opens?
Prior Information Notices (PINs) signal a buyer's intent weeks-to-months
before the formal Contract Notice. Reads from gold_pin_monitor.
"""

import pandas as pd
import plotly.express as px
import streamlit as st
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    df = db.pin_monitor()

    total = len(df)
    high_priority = int(df["priority"].sum())
    pipeline_value_b = df["expected_value"].sum() / 1e9
    avg_win = df["p_win"].mean()

    ui.render_kpis([
        ("Tracked PINs", f"{total:,}",
         "Prior Information Notices currently monitored"),
        ("High Priority", f"{high_priority:,}",
         "Flagged as high-value/high-fit by the model"),
        ("Pipeline Value", f"€{pipeline_value_b:.1f}B",
         "Sum of expected value across all tracked PINs"),
        ("Avg Win Probability", f"{avg_win:.0%}",
         "Average modeled P(win) across tracked PINs"),
    ])

    st.markdown("")

    st.subheader("Early Buyer-Intent Signals")
    only_priority = st.checkbox("Show high-priority only", value=True)
    table_df = df[df["priority"]] if only_priority else df
    st.caption(f"{len(table_df):,} PINs shown")

    display = table_df[["title", "country", "cpv_name", "value_eur",
                         "expected_value", "p_win", "days_since_pin"]].copy()
    display["value_eur"] = display["value_eur"].apply(
        lambda v: f"€{v:,.0f}" if pd.notna(v) else "—"
    )
    display["expected_value"] = display["expected_value"].apply(
        lambda v: f"€{v:,.0f}" if pd.notna(v) else "—"
    )
    display.columns = ["Title", "Country", "CPV", "Est. Value",
                       "Expected Value", "Win Prob.", "Days Since PIN"]

    col_config = {
        "Win Prob.": st.column_config.ProgressColumn(
            "Win Prob.", min_value=0, max_value=1, format="percent",
        )
    }
    st.dataframe(display.head(50), use_container_width=True,
                 hide_index=True, column_config=col_config)

    st.markdown("")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("PIN value by country")
        by_country = (df.groupby("country", dropna=False)["expected_value"]
                        .sum()
                        .reset_index()
                        .rename(columns={"expected_value": "total_b"})
                        .assign(total_b=lambda x: x["total_b"] / 1e9)
                        .sort_values("total_b", ascending=False)
                        .head(10))
        fig = px.bar(by_country, x="total_b", y="country", orientation="h",
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=350,
                          xaxis=dict(gridcolor=grid, showgrid=True, title="€B"),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        fig.update_traces(hovertemplate=ui.hover_xy("Value (€B)", "Country"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("PIN value by CPV division")
        by_cpv = (df.groupby("cpv_division", dropna=False)["expected_value"]
                    .sum()
                    .reset_index()
                    .rename(columns={"expected_value": "total_b"})
                    .assign(total_b=lambda x: x["total_b"] / 1e9)
                    .sort_values("total_b", ascending=False)
                    .head(10))
        fig = px.bar(by_cpv, x="total_b", y="cpv_division", orientation="h",
                     color_discrete_sequence=[colors[1]])
        fig.update_layout(**layout, height=350,
                          xaxis=dict(gridcolor=grid, showgrid=True, title="€B"),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        fig.update_traces(hovertemplate=ui.hover_xy("Value (€B)", "CPV Division"))
        st.plotly_chart(fig, use_container_width=True)
