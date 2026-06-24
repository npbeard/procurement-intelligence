"""
Procurement Copilot Page
Can users ask anything naturally?
"""

import streamlit as st
from dashboard import ui

def render():
    st.markdown("---")
    
    st.info("""
    Ask me anything about procurement trends, market opportunities, buyer profiles, 
    supplier performance, or tender analysis. I can answer in natural language!
    """)
    
    st.markdown("---")
    
    # Chat interface
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # User input
    user_input = st.chat_input("Ask me about procurement trends, tenders, buyers, suppliers...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Generate response (mock for now)
        response = generate_response(user_input)
        
        # Add assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": response
        })
        
        # Rerun to display new messages
        st.rerun()
    
    st.markdown("---")
    
    # Suggested queries
    st.subheader("💡 Try asking:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Market Intelligence**
        - "What's the total market value this month?"
        - "Which procurement types are growing?"
        - "Who are the top buyers?"
        - "What's the market forecast for Q2?"
        """)
    
    with col2:
        st.markdown("""
        **Opportunity Analysis**
        - "What are the best opportunities for services?"
        - "Which tenders are expiring soon?"
        - "What's the average contract value?"
        - "Which regions have the most tenders?"
        """)
    
    st.markdown("---")
    
    # Conversation context
    st.subheader("📊 Current Dataset Context")
    
    ui.render_kpis([
        ("Notices Indexed", "2", None),
        ("Lots Analyzed", "2", None),
        ("Organizations", "2", None),
    ])

    st.markdown("")

    st.info("""
    **Copilot Capabilities:**
    - Natural language queries about market trends
    - Tender and buyer analysis
    - Supplier performance metrics
    - Custom filtering and search
    - Comparative analysis
    - Forecasting and recommendations
    """)

def generate_response(query: str) -> str:
    """Generate a response to user query (mock implementation)"""
    
    query_lower = query.lower()
    
    # Market analysis
    if "market" in query_lower and "value" in query_lower:
        return """Based on the current data:

**Total Market Value: €1.2M**
- This represents 2 active procurement notices
- Average tender value: €600K
- Market is showing steady growth trends

The procurement market shows healthy activity with mixed procurement types (50% services, 50% supplies)."""
    
    elif "buyers" in query_lower or "who is buying" in query_lower:
        return """**Top Buyers in Market:**

1. **City of Example** - €600K total spend
   - 1 tender published
   - Type: PUBLIC_BODY
   - Location: Example City, EX

2. **State Agency** - €600K total spend
   - 1 tender published
   - Type: PUBLIC_BODY
   - Location: State Capital, EX

Both are government entities with similar spending patterns."""
    
    elif "opportunities" in query_lower or "priority" in query_lower:
        return """**Top Opportunities to Pursue:**

1. **TED-2026-001** (IT Services)
   - Value: €600K
   - Buyer: City of Example
   - Priority Score: 9.2/10
   - Deadline: 14 days

2. **TED-2026-002** (Office Supplies)
   - Value: €600K
   - Buyer: State Agency
   - Priority Score: 8.7/10
   - Deadline: 13 days

Both represent strong market opportunities with reasonable deadlines."""
    
    elif "forecast" in query_lower or "trend" in query_lower:
        return """**Market Forecast & Trends:**

📈 **30-Day Outlook:**
- Expected new tenders: 15-18
- Confidence level: 87%
- Expected value: €7.2M - €8.1M

📊 **Growth Trends:**
- Services segment: ↑ 18% growth
- Supplies segment: ↓ 3% slight decline
- Overall market sentiment: Positive

**Recommendation:** Focus procurement strategy on services opportunities given the upward trend."""
    
    elif "services" in query_lower or "supplies" in query_lower:
        return """**Procurement Segment Analysis:**

**Services Procurement (50% of market)**
- Total value: €600K
- 1 active tender
- Growth trend: ↑ 18%
- Primary CPV: 72000000 (IT Services)

**Supplies Procurement (50% of market)**
- Total value: €600K
- 1 active tender
- Growth trend: ↓ 3%
- Primary CPV: 30125000 (Office Supplies)

Services showing stronger growth potential."""
    
    else:
        return f"""I can help you with procurement intelligence! 

Your query: "{query}"

I can answer questions about:
- Market trends and forecasts
- Buyer profiles and spending patterns
- Tender opportunities and priorities
- Supplier awards and performance
- Procurement segments and CPV categories

Try asking something specific about the market, opportunities, or buyers, and I'll provide detailed insights!"""
