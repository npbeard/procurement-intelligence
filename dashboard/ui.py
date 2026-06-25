"""
dashboard/ui.py — shared dark/light theming helpers.

Streamlit's Settings -> Theme toggle can't be detected from CSS alone
(`prefers-color-scheme` only sees the OS preference). `st.context.theme.type`
reflects the actual rendered theme regardless of how it was triggered, so
page modules call `is_dark()` instead of relying on a media query.
"""
from __future__ import annotations

import html

import streamlit as st

GRADIENTS = [
    "linear-gradient(135deg, #C66FF2 0%, #8B5CF6 100%)",  # violet/pink
    "linear-gradient(135deg, #22D3EE 0%, #3B82F6 100%)",  # cyan/blue
    "linear-gradient(135deg, #FB923C 0%, #EC4899 100%)",  # orange/pink
    "linear-gradient(135deg, #2DD4BF 0%, #22C55E 100%)",  # teal/green
]

_LIGHT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#374151", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=False,
)
_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#C9D1D9", size=11),
    margin=dict(l=0, r=0, t=30, b=0),
    showlegend=False,
)

_LIGHT_GRID = "#E5E7EB"
_DARK_GRID = "rgba(255,255,255,0.08)"

_LIGHT_COLORS = ["#1F5CE6", "#7B52D4", "#FF832B", "#24A148", "#E63946", "#457B9D"]
_DARK_COLORS = ["#22D3EE", "#EC4899", "#A78BFA", "#2DD4BF", "#FB923C", "#60A5FA"]


def is_dark() -> bool:
    """True if Streamlit's currently-rendered theme is dark."""
    return st.context.theme.type == "dark"


def chart_theme(dark: bool) -> dict:
    """Plotly layout/gridline/palette appropriate for the active theme."""
    return {
        "layout": dict(_DARK_LAYOUT if dark else _LIGHT_LAYOUT),
        "grid": _DARK_GRID if dark else _LIGHT_GRID,
        "colors": _DARK_COLORS if dark else _LIGHT_COLORS,
    }


def kpi_card(label: str, value: str, help_text: str | None = None, index: int = 0) -> str:
    """One gradient KPI tile. `index` cycles through GRADIENTS."""
    gradient = GRADIENTS[index % len(GRADIENTS)]
    title_attr = f' title="{html.escape(help_text)}"' if help_text else ""
    return (
        f'<div class="kpi-card" style="background:{gradient};"{title_attr}>'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(str(value))}</div>'
        f"</div>"
    )


def render_kpis(items: list[tuple]) -> None:
    """Render a row of gradient KPI cards.

    items: list of (label, value) or (label, value, help_text) tuples.
    """
    cols = st.columns(len(items))
    for i, (col, item) in enumerate(zip(cols, items)):
        label, value = item[0], item[1]
        help_text = item[2] if len(item) > 2 else None
        with col:
            st.markdown(kpi_card(label, value, help_text, i), unsafe_allow_html=True)


def ms_badge() -> str:
    """'Powered by Microsoft' mark, drawn in CSS from Microsoft's own
    four-square brand colors — avoids fetching/redistributing a logo asset."""
    return (
        '<div class="ms-badge">'
        '<span class="ms-logo">'
        '<span style="background:#F25022;"></span>'
        '<span style="background:#7FBA00;"></span>'
        '<span style="background:#00A4EF;"></span>'
        '<span style="background:#FFB900;"></span>'
        "</span>"
        '<span class="ms-text">Powered by Microsoft</span>'
        "</div>"
    )
