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

    priority_df = df[df["priority"] == True] if "priority" in df.columns else df.iloc[0:0]
    total_ev_m  = df["pin_ev_m"].sum() if "pin_ev_m" in df.columns else 0.0
    days_med    = df["days_since_pin"].median() if "days_since_pin" in df.columns else 0

    # ── KPIs ────────────────────────────────────────────────────────────────
    ui.render_kpis([
        ("Total PINs",      int(len(df)),              "Prior Information Notices with known value"),
        ("Priority PINs",   int(len(priority_df)),     "Affinity ≥ 0.60 AND value ≥ €500K"),
        ("Pipeline EV",     f"€{total_ev_m:.1f}M",    "Expected value across all PINs"),
        ("Avg Days Open",   f"{days_med:.0f}d",        "Median days since PIN publication"),
    ])

    st.markdown("")

    # ── Country filter ───────────────────────────────────────────────────────
    country_col = "country" if "country" in df.columns else None
    all_countries = sorted(df[country_col].dropna().unique().tolist()) if country_col else []
    selected_countries = st.multiselect(
        "Filter by buyer country", all_countries, default=[], key="pin_country"
    )
    view = df[df[country_col].isin(selected_countries)] if (selected_countries and country_col) else df

    st.markdown("")

    # ── Priority PINs table ──────────────────────────────────────────────────
    st.subheader("Priority PINs")
    prio_view = view[view["priority"] == True].copy() if "priority" in view.columns else view.copy()

    if prio_view.empty:
        st.info("No priority PINs match the current filter.")
    else:
        # Only include columns that actually exist in this table version
        col_map = {
            "lot_name":       "Opportunity",
            "buyer_name":     "Buyer",
            "country":        "Country",
            "product_line":   "Product Line",
            "value_m":        "Value (€M)",
            "affinity_score": "Affinity",
            "days_since_pin": "Days Open",
            "pin_ev_m":       "Priority EV (€M)",
        }
        available = {k: v for k, v in col_map.items() if k in prio_view.columns}
        display = prio_view[list(available.keys())].copy()
        display.columns = list(available.values())
        display.insert(0, "#", range(1, len(display) + 1))
        st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("")

    # ── Charts ───────────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Expected value by country")
        count_col = "lot_name"  # always present; use as row count proxy
        by_country = (
            view.groupby("country", dropna=False)
            .agg(ev=("pin_ev_m", "sum"), count=(count_col, "count"))
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
        all_col_map = {
            "lot_name":       "Opportunity",
            "buyer_name":     "Buyer",
            "country":        "Country",
            "product_line":   "Product Line",
            "issue_date":     "Published",
            "value_m":        "Value (€M)",
            "affinity_score": "Affinity",
            "days_since_pin": "Days Open",
            "pin_ev_m":       "Priority EV (€M)",
            "priority":       "Priority",
        }
        avail = {k: v for k, v in all_col_map.items() if k in view.columns}
        all_display = view[list(avail.keys())].copy()
        all_display.columns = list(avail.values())
        st.dataframe(all_display, use_container_width=True, hide_index=True)
