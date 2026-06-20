"""
Executive Overview Page
What is the market?
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

def render():
    # The main dashboard layout already shows the page title in the top header.
    
    # Tab navigation
    tab1, tab2 = st.tabs(["OPPORTUNITIES (CN)", "AWARDS (CAN)"])
    
    with tab1:
        render_opportunities()
    
    with tab2:
        render_awards()

def render_opportunities():
    """Opportunities/Notices view"""
    
    # Key metrics - using actual mock data
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Open Tenders", "437", help="Active contract notices")
    
    with col2:
        st.metric("Countries", "27", help="Geographic coverage")
    
    with col3:
        st.metric("Total Estimated", "€853M", help="Total procurement value")
    
    with col4:
        st.metric("Avg Lots/Tender", "2.3", help="Average lots per notice")
    
    st.markdown("")
    
    # Charts section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top countries by notice count")
        countries_data = pd.DataFrame({
            "Country": ["DEU", "FRA", "ITA", "ESP", "POL", "NLD", "BEL", "ROU", "PRT", "SWE"],
            "Count": [187, 156, 98, 74, 62, 45, 38, 31, 24, 21]
        })
        fig = px.bar(countries_data, x="Count", y="Country", orientation='h', 
                     color="Count", color_continuous_scale="Blues")
        fig.update_traces(marker=dict(color='#00D9FF'))
        fig.update_layout(
            showlegend=False, height=400, 
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11),
            xaxis=dict(gridcolor='rgba(0, 217, 255, 0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0, 217, 255, 0.05)', showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Top CPV categories")
        cpv_data = pd.DataFrame({
            "CPV": ["45", "72", "33", "79", "98", "34", "71", "50", "85", "92"],
            "Count": [187, 156, 98, 74, 62, 45, 38, 31, 24, 21]
        })
        fig = px.bar(cpv_data, x="Count", y="CPV", orientation='h',
                     color="Count", color_continuous_scale="Blues")
        fig.update_traces(marker=dict(color='#00D9FF'))
        fig.update_layout(
            showlegend=False, height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11),
            xaxis=dict(gridcolor='rgba(0, 217, 255, 0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0, 217, 255, 0.05)', showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Procurement type distribution
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Procurement type distribution")
        procurement_data = pd.DataFrame({
            "Type": ["Services", "Supplies", "Works"],
            "Percent": [58, 24, 18]
        })
        fig = go.Figure(data=[go.Pie(
            labels=procurement_data["Type"],
            values=procurement_data["Percent"],
            hole=.4,
            marker=dict(colors=["#00D9FF", "#FF6B9D", "#FFC857"]),
            textposition='inside',
            textfont=dict(family='Inter', color='#E6EDF3', size=12)
        )])
        fig.update_layout(
            height=350, 
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Largest opportunities")
        opportunities = pd.DataFrame({
            "Title": ["Motorway expansion", "Hospital IT modernization", "Railway maintenance", 
                     "Pharmaceutical supply", "Smart city sensors"],
            "Country": ["POL", "DEU", "FRA", "ITA", "NLD"],
            "Est. Amount": ["€48.2M", "€22.7M", "€18.5M", "€14.1M", "€11.8M"],
            "CPV": ["Construction", "IT services", "Repair & maintenance", "Medical equipment", "IT services"]
        })
        st.dataframe(opportunities, use_container_width=True, hide_index=True)

def render_awards():
    """Awards/Closed contracts view"""
    
    # Key metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("Awards", "312")
    
    with col2:
        st.metric("Total Awarded", "€621M")
    
    with col3:
        st.metric("Avg Tenders/Lot", "3.8")
    
    with col4:
        st.metric("% SME Winners", "34%")
    
    with col5:
        st.metric("Countries", "27")
    
    st.markdown("")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top countries by award value")
        award_countries = pd.DataFrame({
            "Country": ["DEU", "FRA", "ITA", "ESP", "POL", "NLD", "BEL", "ROU", "PRT", "SWE"],
            "Value": [218, 164, 142, 89, 53, 61, 42, 28, 19, 31]
        })
        fig = px.bar(award_countries, x="Value", y="Country", orientation='h',
                     color="Value", color_continuous_scale="Blues")
        fig.update_traces(marker=dict(color='#00D9FF'))
        fig.update_layout(
            showlegend=False, height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11),
            xaxis=dict(gridcolor='rgba(0, 217, 255, 0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(0, 217, 255, 0.05)', showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Competition by country (avg tenders/lot)")
        competition = pd.DataFrame({
            "Country": ["NLD", "DEU", "SWE", "BEL", "FRA", "ITA", "ESP", "POL"],
            "Tenders": [5.8, 5.2, 4.9, 4.6, 4.1, 3.7, 3.3, 2.9]
        })
        fig = px.bar(competition, x="Tenders", y="Country", orientation='h',
                     color="Tenders", color_continuous_scale="Purples")
        fig.update_traces(marker=dict(color='#A371F7'))
        fig.update_layout(
            showlegend=False, height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#8B949E', size=11),
            xaxis=dict(gridcolor='rgba(163, 113, 247, 0.1)', showgrid=True),
            yaxis=dict(gridcolor='rgba(163, 113, 247, 0.05)', showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Largest awards")
    largest_awards = pd.DataFrame({
        "Title": ["Berlin metro extension", "EHR platform rollout", "Municipal fleet electrification",
                 "Wastewater treatment upgrade", "Office cleaning services"],
        "Country": ["DEU", "FRA", "ESP", "ROU", "BEL"],
        "Awarded": ["€38.4M", "€15.3M", "€8.9M", "€6.7M", "€95.2K"],
        "Estimated": ["€42.0M", "€19.1M", "€10.2M", "€7.5M", "€120K"],
        "Savings %": ["8.6%", "19.9%", "12.7%", "10.7%", "20.7%"],
        "Tenders/Lot": [7.2, 5.1, 4.3, 3.8, 3.1],
        "SME": ["No", "No", "Yes", "No", "Yes"]
    })
    st.dataframe(largest_awards, use_container_width=True, hide_index=True)
