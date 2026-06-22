"""
Buyer Intelligence Page
Who is buying?
"""

import streamlit as st
import pandas as pd
import plotly.express as px

def render():
    st.markdown("---")
    
    # Buyer overview metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Buyers", "2", help="Unique contracting entities")
    
    with col2:
        st.metric("Avg Tenders/Buyer", "1", help="Average procurements per entity")
    
    with col3:
        st.metric("Total Spend", "€1.2M", help="Aggregate procurement value")
    
    st.markdown("---")
    
    # Buyer ranking
    st.subheader("Top Buyers")
    
    buyers = pd.DataFrame({
        "Rank": [1, 2],
        "Buyer Name": ["City of Example", "State Agency"],
        "Country": ["EX", "EX"],
        "City": ["Example City", "State Capital"],
        "Type": ["PUBLIC_BODY", "PUBLIC_BODY"],
        "Tenders": [1, 1],
        "Total Spend (€)": [600000, 600000],
        "Avg Spend (€)": [600000, 600000]
    })
    
    st.dataframe(buyers, use_container_width=True)
    
    st.markdown("---")
    
    # Buyer analysis
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Buyers by Type")
        buyer_type = pd.DataFrame({
            "Type": ["PUBLIC_BODY"],
            "Count": [2]
        })
        st.bar_chart(buyer_type.set_index("Type"))
    
    with col2:
        st.subheader("Buyers by Country")
        country_data = pd.DataFrame({
            "Country": ["EX"],
            "Count": [2]
        })
        st.bar_chart(country_data.set_index("Country"))
    
    st.markdown("---")
    
    # Buyer detail
    st.subheader("Detailed Buyer Profile")
    
    selected_buyer = st.selectbox("Select Buyer", buyers["Buyer Name"].tolist())
    
    buyer_detail = buyers[buyers["Buyer Name"] == selected_buyer].iloc[0]
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Tenders", int(buyer_detail["Tenders"]))
    
    with col2:
        st.metric("Total Spend", f"€{buyer_detail['Total Spend (€)']:,.0f}")
    
    with col3:
        st.metric("Avg Tender", f"€{buyer_detail['Avg Spend (€)']:,.0f}")
    
    with col4:
        st.metric("Organization Type", buyer_detail["Type"])
    
    st.markdown("---")
    
    # Procurement patterns
    st.subheader("Procurement Patterns")
    
    patterns_col1, patterns_col2 = st.columns(2)
    
    with patterns_col1:
        st.info("""
        **Location Information**
        - City: {}
        - Country: {}
        """.format(buyer_detail["City"], buyer_detail["Country"]))
    
    with patterns_col2:
        st.info("""
        **Spending Profile**
        - Total Procurements: {}
        - Aggregated Budget: €{:,.0f}
        """.format(int(buyer_detail["Tenders"]), buyer_detail["Total Spend (€)"]))
