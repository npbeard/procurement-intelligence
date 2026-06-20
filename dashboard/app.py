"""
Procurement Intelligence Streamlit Dashboard
Main app with 6 business case pages
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard.pages import (
    executive_overview,
    opportunity_radar,
    buyer_intelligence,
    supplier_awards,
    trends_forecasts,
    copilot
)

# Page configuration
st.set_page_config(
    page_title="Procurement Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Professional light theme matching design
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }
    
    html, body, [class*="css"] {
        background-color: #FFFFFF !important;
        color: #111111 !important;
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
    
    .stApp > header {
        background: transparent !important;
    }
    
    .stApp {
        overflow-x: hidden;
    }
    
    h1, h2, h3 {
        color: #111111 !important;
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
        color: #111111 !important;
        font-size: 2rem !important;
        font-weight: 800 !important;
        line-height: 1.2;
    }
    
    .eyebrow {
        margin: 0 0 0.2rem 0;
        color: #6B7280 !important;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.75rem;
        font-weight: 700;
    }
    
    .dashboard-subtitle {
        color: #4B5563 !important;
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
    
    [data-testid="metricValue"] {
        color: #111111 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    [data-testid="metricLabel"] {
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
    [data-testid="stSubheader"] {
        color: #111111 !important;
        font-weight: 700 !important;
    }
    
    /* Text styling */
    p, span, label, div {
        color: #111111 !important;
    }
    
    /* Input styling */
    .stNumberInput input,
    .stSelectbox select,
    .stMultiSelect:has(> div) {
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
    
    /* Info/Warning/Alert boxes */
    [data-testid="stAlert"] {
        background-color: #F9FAFB !important;
        border-left: 4px solid #111111 !important;
        border-radius: 6px !important;
        color: #111111 !important;
    }
    
    [data-testid="stAlert"] p {
        color: #111111 !important;
        font-weight: 500 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2 {
        color: #111111 !important;
    }
    
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: #111111 !important;
    }
    
    /* Links */
    a {
        color: #111111 !important;
        text-decoration: none !important;
    }
    
    a:hover {
        color: #4B5563 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("🏛️ Procurement Intelligence")
st.sidebar.markdown("---")

pages = {
    "📈 Executive Overview": executive_overview,
    "🎯 Opportunity Radar": opportunity_radar,
    "👥 Buyer Intelligence": buyer_intelligence,
    "🏆 Supplier & Awards": supplier_awards,
    "📊 Trends & Forecasts": trends_forecasts,
    "🤖 Procurement Copilot": copilot,
}

page_descriptions = {
    "📈 Executive Overview": "Market pulse, opportunity volume, and award patterns.",
    "🎯 Opportunity Radar": "Prioritize tenders by value, urgency, and fit.",
    "👥 Buyer Intelligence": "Understand who is buying and how they procure.",
    "🏆 Supplier & Awards": "See who is winning and how awards are distributed.",
    "📊 Trends & Forecasts": "Track changing demand and forecast future signals.",
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

# Load and display selected page
pages[selected_page].render()
