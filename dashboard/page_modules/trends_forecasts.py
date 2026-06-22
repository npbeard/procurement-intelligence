"""
Trends & Forecasts Page
What is changing?
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

def render():
    st.markdown("---")
    
    # Time period selector
    col1, col2, col3 = st.columns(3)
    
    with col1:
        period = st.selectbox(
            "Analysis Period",
            ["Last 30 Days", "Last 90 Days", "Last Year", "All Time"],
            index=1
        )
    
    with col2:
        metric_type = st.selectbox(
            "Metric",
            ["Tender Count", "Total Value", "Avg Tender Value"],
            index=0
        )
    
    with col3:
        forecast_enabled = st.checkbox("Show Forecast", value=True)
    
    st.markdown("---")
    
    # Historical data (mock time series)
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    tender_counts = np.cumsum(np.random.randint(0, 2, 60))
    tender_values = np.cumsum(np.random.randint(50000, 150000, 60))
    
    trend_data = pd.DataFrame({
        "Date": dates,
        "Tender Count": tender_counts,
        "Total Value": tender_values,
        "Avg Value": tender_values / (tender_counts + 1)
    })
    
    # Plot trends
    if metric_type == "Tender Count":
        fig = px.line(
            trend_data,
            x="Date",
            y="Tender Count",
            title="Tender Volume Trend",
            markers=True
        )
    elif metric_type == "Total Value":
        fig = px.line(
            trend_data,
            x="Date",
            y="Total Value",
            title="Total Procurement Value Trend",
            markers=True
        )
    else:
        fig = px.line(
            trend_data,
            x="Date",
            y="Avg Value",
            title="Average Tender Value Trend",
            markers=True
        )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Trend analysis
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "30-Day Trend",
            "+12%",
            help="Tenders published in last 30 days vs prior month"
        )
    
    with col2:
        st.metric(
            "Value Growth",
            "+5.2%",
            help="YoY procurement value growth"
        )
    
    with col3:
        st.metric(
            "Market Volatility",
            "8.3%",
            help="Standard deviation of tender values"
        )
    
    st.markdown("---")
    
    # Forecast section
    if forecast_enabled:
        st.subheader("AI-Powered Forecast")
        
        forecast_col1, forecast_col2 = st.columns(2)
        
        with forecast_col1:
            st.info("""
            **30-Day Forecast**
            - Expected Tenders: 15-18
            - Confidence: 87%
            - Expected Value: €7.2M - €8.1M
            """)
        
        with forecast_col2:
            st.info("""
            **90-Day Forecast**
            - Expected Tenders: 42-48
            - Confidence: 72%
            - Expected Value: €21M - €24M
            """)
        
        # Forecast visualization
        forecast_dates = pd.date_range(start=datetime.now(), periods=30, freq='D')
        forecast_values = np.cumsum(np.random.randint(200000, 400000, 30))
        
        forecast_df = pd.DataFrame({
            "Date": forecast_dates,
            "Forecast": forecast_values
        })
        
        fig = px.line(
            forecast_df,
            x="Date",
            y="Forecast",
            title="30-Day Procurement Value Forecast",
            markers=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Market segment trends
    st.subheader("Segment Trends")
    
    segment_col1, segment_col2 = st.columns(2)
    
    with segment_col1:
        st.info("""
        **Services Procurement**
        - Change: ↑ 18%
        - Share: 50%
        - Forecast: Continued growth
        """)
    
    with segment_col2:
        st.info("""
        **Supplies Procurement**
        - Change: ↓ 3%
        - Share: 50%
        - Forecast: Slight decline
        """)
    
    st.markdown("---")
    
    st.warning("""
    **📌 Key Observations:**
    - Procurement market shows steady growth trend
    - Services segment outpacing supplies growth
    - Seasonal patterns may affect Q4 volumes
    - Regional concentration increasing
    """)
