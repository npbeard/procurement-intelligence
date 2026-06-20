"""
Supplier & Awards Page
Who is winning?
"""

import streamlit as st
import pandas as pd
import plotly.express as px

def render():
    st.markdown("---")
    
    # Award overview
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Awards", "2", help="Completed procurements with winners")
    
    with col2:
        st.metric("Unique Winners", "2", help="Number of winning organizations")
    
    with col3:
        st.metric("Total Award Value", "€1.2M", help="Sum of awarded contracts")
    
    with col4:
        st.metric("Avg Award Value", "€600K", help="Mean contract value awarded")
    
    st.markdown("---")
    
    # Award criteria analysis
    st.subheader("Award Criteria Breakdown")
    
    criteria = pd.DataFrame({
        "Notice ID": ["TED-2026-001", "TED-2026-001"],
        "Lot ID": ["LOT-001", "LOT-001"],
        "Criteria Type": ["price", "quality"],
        "Description": ["Lowest price", "Technical quality"],
        "Weight": [None, 50.0]
    })
    
    st.dataframe(criteria, use_container_width=True)
    
    st.markdown("---")
    
    # Award winners (organizations with awards)
    st.subheader("Award Winners")
    
    winners = pd.DataFrame({
        "Rank": [1, 2],
        "Organization": ["City of Example", "State Agency"],
        "Awards": [1, 1],
        "Total Award Value (€)": [600000, 600000],
        "Avg Award Value (€)": [600000, 600000],
        "Win Rate": ["100%", "100%"]
    })
    
    st.dataframe(winners, use_container_width=True)
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Awards by Lot")
        lots = pd.DataFrame({
            "Lot": ["LOT-001", "Unawarded"],
            "Count": [2, 0]
        })
        fig = px.pie(lots, values="Count", names="Lot", title="Award Distribution")
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Award Value Distribution")
        fig = px.box(
            pd.DataFrame({
                "Value": [600000, 600000],
                "Lot": ["LOT-001", "LOT-001"]
            }),
            y="Value",
            title="Award Value Range by Lot"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Award criteria analysis
    st.subheader("Winning Criteria Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Price", "Quality", "Other"])
    
    with tab1:
        st.info("""
        **Price-Based Awards**
        - Total: 1
        - Avg Price Weight: Not specified (lowest wins)
        """)
    
    with tab2:
        st.info("""
        **Quality-Based Awards**
        - Total: 1
        - Avg Quality Weight: 50%
        - Quality criteria valued at 50% of decision
        """)
    
    with tab3:
        st.info("""
        **Other Criteria**
        - No other weighted criteria found
        """)
    
    st.markdown("---")
    
    st.info("""
    **Key Insights:**
    - Most tenders use mixed award criteria (price + quality)
    - Average quality weight: 50% when specified
    - Geographic concentration: Mostly local/regional winners
    """)
