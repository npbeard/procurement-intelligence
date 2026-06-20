"""
Opportunity Radar Page
Which tenders should we prioritize?
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def render():
    st.markdown("")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        min_value = st.number_input("Min Tender Value (€)", 0, 50000000, 1000000, step=100000)
    
    with col2:
        procurement_types = st.multiselect(
            "Procurement Types",
            ["Services", "Supplies", "Works"],
            default=["Services", "Supplies", "Works"]
        )
    
    with col3:
        country_filter = st.selectbox(
            "Country Filter",
            ["All"] + ["DEU", "FRA", "ITA", "ESP", "POL", "NLD", "BEL", "ROU", "PRT", "SWE"],
            index=0
        )
    
    st.markdown("")
    
    # Opportunity scoring
    st.subheader("Top Opportunities by Priority Score")
    
    opportunities = pd.DataFrame({
        "Rank": [1, 2, 3, 4, 5],
        "Title": [
            "Motorway expansion - A4 corridor",
            "Hospital IT modernization",
            "Railway maintenance framework",
            "Pharmaceutical supply agreement",
            "Smart city sensor network"
        ],
        "Country": ["POL", "DEU", "FRA", "ITA", "NLD"],
        "Value (€)": [48200000, 22700000, 18500000, 14100000, 11800000],
        "Type": ["Works", "Services", "Services", "Supplies", "Services"],
        "CPV": ["45000000", "72000000", "50000000", "33000000", "72000000"],
        "Deadline": ["45 days", "32 days", "28 days", "15 days", "21 days"],
        "Priority": [9.8, 9.5, 8.9, 8.3, 7.9]
    })
    
    st.dataframe(
        opportunities,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Priority": st.column_config.ProgressColumn(
                "Priority Score",
                min_value=0,
                max_value=10,
            ),
        }
    )
    
    st.markdown("")
    
    # Priority matrix
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Value vs. Deadline (Urgency Matrix)")
        
        fig = px.scatter(
            opportunities,
            x="Deadline",
            y="Value (€)",
            size="Priority",
            color="Priority",
            hover_data=["Title", "Country"],
            title="",
            color_continuous_scale="Blues",
            text="Rank"
        )
        fig.update_traces(textposition='top center', marker=dict(color='#00D9FF'))
        fig.update_layout(
            height=400, 
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11),
            xaxis=dict(gridcolor='rgba(0, 217, 255, 0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0, 217, 255, 0.1)', showgrid=True)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Opportunities by Type & Country")
        
        type_country = pd.DataFrame({
            "Type": ["Services", "Supplies", "Works"],
            "Count": [3, 1, 1]
        })
        
        fig = px.pie(type_country, values="Count", names="Type",
                    color_discrete_sequence=["#00D9FF", "#FF6B9D", "#FFC857"])
        fig.update_layout(
            height=400, 
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("")
    
    st.info("""
    **💡 Smart Prioritization:**
    - **Priority Score** = (Value × Market Fit × Time Urgency) / Competition
    - Sort by deadline for near-term opportunities
    - Filter by type and value to focus on relevant tenders
    """)

