"""
PIN Monitor Page — Early pipeline signals from Prior Information Notices.

PINs are published by buyers weeks or months before the actual contract
notice appears. High-priority PINs give Microsoft's sales team advance
notice to build relationships with the buyer before the tender formally
opens. Reads from gold_pin_monitor (the ML pipeline's PIN scoring output).
"""

import plotly.express as px
import streamlit as st
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    st.markdown(
        "_Prior Information Notices (PINs) are advance signals of upcoming "
        "IT procurement. High-priority PINs have strong buyer affinity and "
        "contract values above €500K — ideal for proactive "
        "relationship-building._"
    )
    st.markdown("")

    with st.spinner("Loading PIN data…"):
        try:
            df = db.pin_monitor_lots()
        except Exception as e:
            st.error(f"Could not load PIN data: {e}")
            return

    if df.empty:
        st.info(
            "No PIN data available yet. The ML pipeline writes this table "
            "after it has been trained on at least one run."
        )
        return

    priority_df = df[df["priority"]]
    total_ev_m = df["pin_ev_m"].sum()
    days_med = df["days_since_pin"].median()

    ui.render_kpis([
        ("Total PINs", f"{len(df):,}",
         "Prior Information Notices with known value"),
        ("Priority PINs", f"{len(priority_df):,}",
         "Affinity ≥ 0.60 AND value ≥ €500K"),
        ("Pipeline EV", f"€{total_ev_m:.1f}M",
         "Expected value across all PINs"),
        ("Avg Days Open", f"{days_med:.0f}d",
         "Median days since PIN publication"),
    ])

    st.markdown("")

    all_countries = sorted(df["country"].dropna().unique().tolist())
    selected_countries = st.multiselect(
        "Filter by buyer country", all_countries, default=[]
    )
    view = df[df["country"].isin(selected_countries)] if selected_countries else df

    st.subheader("PIN Signals")
    only_priority = st.checkbox("Show high-priority only", value=True)
    table_df = view[view["priority"]] if only_priority else view
    st.caption(f"{len(table_df):,} PINs shown")

    display = table_df[["title", "buyer_name", "country", "product_line",
                         "value_m", "pin_ev_m", "p_win",
                         "days_since_pin"]].copy()
    display.columns = ["Title", "Buyer", "Country", "Product Line",
                       "Value (€M)", "Pipeline EV (€M)", "Win Prob.",
                       "Days Open"]

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
        st.subheader("Pipeline EV by country")
        by_country = (view.groupby("country", dropna=False)["pin_ev_m"]
                         .sum()
                         .reset_index()
                         .sort_values("pin_ev_m", ascending=False)
                         .head(12))
        fig = px.bar(by_country, x="pin_ev_m", y="country", orientation="h",
                     color_discrete_sequence=[colors[0]])
        fig.update_layout(**layout, height=360,
                          xaxis=dict(gridcolor=grid, showgrid=True, title="€M"),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        fig.update_traces(hovertemplate=ui.hover_xy("EV (€M)", "Country"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Pipeline EV by product line")
        by_line = (view.groupby("product_line", dropna=False)["pin_ev_m"]
                     .sum()
                     .reset_index()
                     .sort_values("pin_ev_m", ascending=False))
        fig = px.bar(by_line, x="pin_ev_m", y="product_line", orientation="h",
                     color_discrete_sequence=[colors[2]])
        fig.update_layout(**layout, height=360,
                          xaxis=dict(gridcolor=grid, showgrid=True, title="€M"),
                          yaxis=dict(showgrid=False, title="", autorange="reversed"))
        fig.update_traces(hovertemplate=ui.hover_xy("EV (€M)", "Product Line"))
        st.plotly_chart(fig, use_container_width=True)
