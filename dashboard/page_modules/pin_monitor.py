"""
PIN Monitor Page — Early pipeline signals from Prior Information Notices.

PINs are published by buyers weeks or months before the actual contract notice
appears.  High-affinity PINs give Microsoft's sales team advance notice to
build relationships with the buyer before the tender formally opens.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from dashboard import db, ui


def render():
    dark = ui.is_dark()
    theme = ui.chart_theme(dark)
    colors, grid, layout = theme["colors"], theme["grid"], theme["layout"]

    st.markdown(
        "_Prior Information Notices (PINs) are advance signals of upcoming IT "
        "procurement. High-priority PINs have strong buyer affinity and contract "
        "values above €500K — ideal for proactive relationship-building._"
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
            "No PIN data available yet. The ML pipeline writes this table after "
            "it has been trained on at least one run."
        )
        return

    priority_df = df[df["priority"] == True]
    total_ev_m = df["pin_ev_m"].sum()

    # ── KPIs ────────────────────────────────────────────────────────────────
    ui.render_kpis([
        ("Total PINs",      int(len(df)),              "Prior Information Notices with known value"),
        ("Priority PINs",   int(len(priority_df)),     "Affinity ≥ 0.60 AND value ≥ €500K"),
        ("Pipeline EV",     f"€{total_ev_m:.1f}M",    "Expected value across all PINs"),
        ("Avg Days Open",   f"{df['days_since_pin'].median():.0f}d",
                                                        "Median days since PIN publication"),
    ])

    st.markdown("")

    # ── Country filter ───────────────────────────────────────────────────────
    all_countries = sorted(df["country"].dropna().unique().tolist())
    selected_countries = st.multiselect(
        "Filter by buyer country", all_countries, default=[], key="pin_country"
    )
    view = df[df["country"].isin(selected_countries)] if selected_countries else df

    st.markdown("")

    # ── Priority PINs table ──────────────────────────────────────────────────
    st.subheader("Priority PINs")
    prio_view = view[view["priority"] == True].copy()

    if prio_view.empty:
        st.info("No priority PINs match the current filter.")
    else:
        display = prio_view[[
            "lot_name", "buyer_name", "country", "product_line",
            "value_m", "affinity_score", "days_since_pin", "pin_ev_m",
        ]].copy()
        display.columns = [
            "Opportunity", "Buyer", "Country", "Product Line",
            "Value (€M)", "Affinity", "Days Open", "Priority EV (€M)",
        ]
        display.insert(0, "#", range(1, len(display) + 1))
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("")

    # ── Charts ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Expected value by country")
        by_country = (
            view.groupby("country", dropna=False)
            .agg(ev=("pin_ev_m", "sum"), count=("lot_id", "count"))
            .reset_index()
            .sort_values("ev", ascending=False)
            .head(12)
        )
        fig = px.bar(
            by_country, x="ev", y="country", orientation="h",
            color_discrete_sequence=[colors[0]],
        )
        fig.update_layout(
            **layout, height=360,
            xaxis=dict(gridcolor=grid, showgrid=True, title="Pipeline EV (€M)"),
            yaxis=dict(showgrid=False, title="", autorange="reversed"),
        )
        fig.update_traces(hovertemplate=ui.hover_xy("EV (€M)", "Country"))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("PINs by product line")
        by_line = (
            view.groupby("product_line", dropna=False)
            .agg(count=("lot_id", "count"), ev=("pin_ev_m", "sum"))
            .reset_index()
            .sort_values("ev", ascending=False)
        )
        fig = px.bar(
            by_line, x="ev", y="product_line", orientation="h",
            color_discrete_sequence=[colors[2]],
        )
        fig.update_layout(
            **layout, height=360,
            xaxis=dict(gridcolor=grid, showgrid=True, title="Pipeline EV (€M)"),
            yaxis=dict(showgrid=False, title="", autorange="reversed"),
        )
        fig.update_traces(hovertemplate=ui.hover_xy("EV (€M)", "Product Line"))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("")

    # ── Full PIN table ───────────────────────────────────────────────────────
    with st.expander("All PINs", expanded=False):
        all_display = view[[
            "lot_name", "buyer_name", "country", "product_line",
            "issue_date", "value_m", "affinity_score", "days_since_pin",
            "pin_ev_m", "priority",
        ]].copy()
        all_display.columns = [
            "Opportunity", "Buyer", "Country", "Product Line",
            "Published", "Value (€M)", "Affinity", "Days Open",
            "Priority EV (€M)", "Priority",
        ]
        st.dataframe(all_display, use_container_width=True, hide_index=True)
