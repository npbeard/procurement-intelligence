"""
Procurement Intelligence Streamlit Dashboard
Main app with 6 business case pages
"""

import datetime
import os
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Make deployment secrets available as env vars BEFORE importing any module that
# reads them at import time (e.g. dashboard.db). On Streamlit Community Cloud the
# credentials come from st.secrets; locally they come from .env (loaded later by
# db.py / config.py). setdefault means a local .env never gets clobbered.
try:
    for _key, _val in st.secrets.items():
        os.environ.setdefault(_key, str(_val))
except Exception:
    pass  # no secrets.toml (normal for local dev) — .env will be used instead

from dashboard.page_modules import (
    executive_overview,
    opportunity_radar,
    pin_monitor,
    buyer_intelligence,
    supplier_awards,
    trends_forecasts,
    copilot,
)
from dashboard import db, ui

# Page configuration
st.set_page_config(
    page_title="Procurement Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

dark = ui.is_dark()

# Custom CSS - Professional light theme matching design
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }

    [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded' !important;
    }

    .main {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        background-color: #FFFFFF;
    }
    
    .block-container {
        max-width: 1440px !important;
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
    }
    
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    
    .stApp {
        overflow-x: hidden;
    }
    
    h1, h2, h3 {
        color: inherit !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
        display: block !important;
        visibility: visible !important;
    }
    
    .dashboard-shell {
        margin-bottom: 1rem;
        padding-top: 0.5rem;
    }
    
    .dashboard-header {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        padding: 1rem 0 1rem 0;
        border-bottom: 1px solid #E5E7EB;
        margin-bottom: 1rem;
    }
    
    .dashboard-title {
        margin: 0;
        color: inherit !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        line-height: 1.2;
    }

    .eyebrow {
        margin: 0 0 0.2rem 0;
        color: inherit !important;
        opacity: 0.65;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .dashboard-subtitle {
        color: inherit !important;
        opacity: 0.8;
        font-size: 0.95rem;
        font-weight: 500;
    }
    
    /* Metrics styling */
    .stMetric {
        background: #FFFFFF !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 10px !important;
        padding: 1.5rem !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
    }
    
    [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {
        color: #111111 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {
        color: #4B5563 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid #E5E7EB !important;
    }
    
    .stTabs [data-baseweb="tab-list"] button {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        border-radius: 999px !important;
        color: #374151 !important;
        padding: 0.6rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        font-size: 0.95rem !important;
    }

    .stTabs [data-baseweb="tab-list"] button:hover {
        border-color: #111111 !important;
        color: #111111 !important;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] button {
        background-color: #F9FAFB !important;
        border-color: #111111 !important;
        color: #111111 !important;
    }
    
    /* Dataframe styling */
    [data-testid="dataframe"] {
        background-color: transparent !important;
    }
    
    [data-testid="dataFrameContainer"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }
    
    /* Subheader styling */
    [data-testid="stHeading"] {
        color: inherit !important;
        font-weight: 700 !important;
    }

    /* Input styling */
    [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * {
        color: inherit !important;
    }

    .stNumberInput input,
    .stSelectbox select,
    [data-baseweb="select"] {
        background-color: #FFFFFF !important;
        border: 1px solid #D1D5DB !important;
        color: #111111 !important;
        border-radius: 6px !important;
    }
    
    .stNumberInput input::placeholder,
    .stSelectbox select::placeholder {
        color: #6B7280 !important;
    }
    
    .stNumberInput input:focus,
    .stSelectbox select:focus {
        border-color: #111111 !important;
        box-shadow: 0 0 0 1px #111111 !important;
    }
    
    /* Info/Warning/Alert boxes - keep a fixed light surface in both themes */
    [data-testid="stAlert"] {
        background-color: #F9FAFB !important;
        border-left: 4px solid #111111 !important;
        border-radius: 6px !important;
        color: #111111 !important;
    }

    [data-testid="stAlert"] * {
        color: #111111 !important;
        font-weight: 500 !important;
    }

    /* Sidebar - keeps a fixed light surface in both themes */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
    }

    [data-testid="stSidebar"] * {
        color: #111111 !important;
    }
    
    /* Links */
    a {
        color: inherit !important;
        text-decoration: none !important;
    }

    a:hover {
        opacity: 0.7;
        text-decoration: underline !important;
    }

    /* "Powered by Microsoft" badge - adapts to either theme via inherit */
    .ms-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-top: 0.75rem;
        opacity: 0.7;
        font-size: 0.78rem;
        font-weight: 600;
    }

    .ms-logo {
        display: inline-grid;
        grid-template-columns: 1fr 1fr;
        gap: 2px;
        width: 14px;
        height: 14px;
        flex-shrink: 0;
    }

    .ms-logo span {
        width: 100%;
        height: 100%;
    }

    .ms-text {
        color: inherit;
    }

    /* Gradient KPI cards (dashboard.ui.kpi_card) - same vivid palette
       in both themes */
    .kpi-card {
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        color: #FFFFFF;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
    }

    .kpi-label {
        font-size: 0.8rem;
        font-weight: 600;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .kpi-value {
        font-size: 1.9rem;
        font-weight: 800;
        margin-top: 0.3rem;
    }
    </style>
""", unsafe_allow_html=True)

if dark:
    st.markdown("""
        <style>
        /* ---- Dark "vivid gradient" theme override ---- */

        .main, .stApp {
            background: #0F0E17 !important;
        }

        /* Header/toolbar text - explicit colors, not `inherit`. Streamlit's
           own native text color can lag a rerun behind st.context.theme.type
           right when the theme is toggled, which left this text dark-on-dark
           during that transition. */
        [data-testid="stHeader"] * ,
        [data-testid="stToolbarActionButtonLabel"],
        [data-testid="stToolbarActionButtonIcon"],
        [data-testid="stHeaderActionElements"] * ,
        [data-testid="stStatusWidget"] * {
            color: #E5E7EB !important;
        }

        h1, h2, h3,
        .dashboard-title,
        .eyebrow,
        .dashboard-subtitle,
        [data-testid="stHeading"],
        [data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] * ,
        a {
            color: #E5E7EB !important;
        }

        .eyebrow {
            opacity: 0.65;
        }

        .dashboard-subtitle {
            opacity: 0.85;
        }

        .dashboard-header {
            border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
        }

        /* Card surfaces */
        .stMetric,
        [data-testid="dataFrameContainer"] {
            background: #1A1825 !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 16px !important;
        }

        [data-testid="stAlert"] {
            background: rgba(255, 255, 255, 0.04) !important;
            border-left: 4px solid #A78BFA !important;
        }

        [data-testid="stAlert"] * {
            color: #E5E7EB !important;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background: #15131F !important;
            border-right: 1px solid rgba(255, 255, 255, 0.06) !important;
        }

        [data-testid="stSidebar"] * {
            color: #E5E7EB !important;
        }

        [data-testid="stSidebar"] h1 {
            color: #FFFFFF !important;
        }

        [data-testid="stSidebar"] label:has(input:checked) {
            background: linear-gradient(135deg, rgba(198, 111, 242, 0.25), rgba(139, 92, 246, 0.25));
            border-radius: 10px;
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] button {
            background-color: #1A1825 !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: #C9D1D9 !important;
        }

        .stTabs [data-baseweb="tab-list"] button:hover {
            border-color: #A78BFA !important;
            color: #FFFFFF !important;
        }

        .stTabs [data-baseweb="tab"][aria-selected="true"] button {
            background: linear-gradient(135deg, #C66FF2, #8B5CF6) !important;
            border-color: transparent !important;
            color: #FFFFFF !important;
        }

        /* Inputs */
        .stNumberInput input,
        .stSelectbox select,
        [data-baseweb="select"] {
            background-color: #1A1825 !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            color: #E5E7EB !important;
        }

        </style>
    """, unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("🏛️ Procurement Intelligence Dashboard")
st.sidebar.markdown("---")

pages = {
    "📈 Executive Overview": executive_overview,
    "🎯 Opportunity Radar": opportunity_radar,
    "📡 PIN Monitor": pin_monitor,
    "👥 Buyer Intelligence": buyer_intelligence,
    "🏆 Supplier & Awards": supplier_awards,
    "📊 Trends": trends_forecasts,
    "🤖 Procurement Copilot": copilot,
}

page_descriptions = {
    "📈 Executive Overview": "Market pulse, opportunity volume, and award patterns.",
    "🎯 Opportunity Radar": "Prioritize tenders by value, urgency, and fit.",
    "📡 PIN Monitor": "Early pipeline signals — build relationships before tenders open.",
    "👥 Buyer Intelligence": "Understand who is buying and how they procure.",
    "🏆 Supplier & Awards": "See who is winning and how awards are distributed.",
    "📊 Trends": "Track how notice volume and procurement activity are changing over time.",
    "🤖 Procurement Copilot": "Ask natural-language questions about the data.",
}

selected_page = st.sidebar.radio("Navigate", list(pages.keys()))

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Procurement Intelligence Platform**
    
    Real-time market insights and tender analysis from TED eForms data.
    
    **Data Source:** Databricks Unity Catalog
    **Last Updated:** Real-time
    """
)
st.sidebar.markdown(ui.ms_badge(), unsafe_allow_html=True)

# Clean top dashboard header
st.markdown(
    f"""
    <div class="dashboard-shell">
        <div class="dashboard-header">
            <div>
                <p class="eyebrow">Procurement Dashboard</p>
                <h1 class="dashboard-title">{selected_page}</h1>
            </div>
            <div class="dashboard-subtitle">{page_descriptions[selected_page]}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ML pipeline status banner — shows if the last scoring run failed or is stale
try:
    status_df = db.pipeline_status()
    if not status_df.empty:
        last = status_df.iloc[0]
        if str(last.get("status", "")) == "FAILED":
            st.warning(
                f"ML pipeline last run **FAILED** at {last.get('run_time', 'unknown')}. "
                f"Opportunity scores and PIN data may be outdated. "
                f"Error: {str(last.get('message', ''))[:200]}"
            )
        else:
            run_time = pd.to_datetime(last.get("run_time"), errors="coerce")
            if pd.notna(run_time):
                hours_ago = (datetime.datetime.utcnow() - run_time.replace(tzinfo=None)).total_seconds() / 3600
                if hours_ago > 48:
                    st.warning(
                        f"ML scores are **{hours_ago:.0f} hours old** — last successful run at "
                        f"{last.get('run_time')}. The pipeline may not have run recently."
                    )
except Exception:
    pass

# Load and display selected page
pages[selected_page].render()
