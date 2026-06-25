"""
Procurement Copilot Page
Natural-language interface to the TED procurement database.
Powered by Chainlit (separate deployment) — this page links out to it.
"""

import streamlit as st
from dashboard import db, ui


def render():
    st.markdown("---")

    st.info(
        "The Procurement Copilot is hosted as a dedicated Chainlit app for the best "
        "conversational experience. Click the button below to open it."
    )

    st.link_button(
        "Open Procurement Copilot",
        url=st.secrets.get("CHATBOT_URL", "#"),
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("What you can ask the Copilot")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Market Intelligence**
        - "Top 5 IT tenders in Spain this week"
        - "Which CPV categories have the highest average value?"
        - "How many contract awards were published yesterday?"
        - "Which countries publish the most IT tenders?"
        """)
    with col2:
        st.markdown("""
        **Opportunity Analysis**
        - "Show me open tenders above €1M in Germany"
        - "Who are the top buyers of cloud services?"
        - "Which tenders close in the next 14 days?"
        - "What did the Ministry of Finance procure last month?"
        """)

    st.markdown("---")
    st.subheader("Live Dataset Snapshot")

    try:
        cn  = db.cn_summary()
        can = db.can_summary()
        ui.render_kpis([
            ("Open Tenders (CN)",    f"{cn.get('notices', 0):,}",  None),
            ("Contract Awards (CAN)", f"{can.get('notices', 0):,}", None),
            ("Lots Indexed",          f"{cn.get('lots', 0) + can.get('lots', 0):,}", None),
        ])
    except Exception:
        st.caption("Live stats unavailable — check Databricks connection.")
