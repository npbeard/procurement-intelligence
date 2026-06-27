"""
Procurement Copilot Page — natural-language Q&A over the gold layer.

A Streamlit-native chat that sends the user's question to an LLM (Groq by
default, or Databricks Foundation Model APIs) with tool access to the gold-layer
queries in `dashboard.db`. Every figure in an answer comes from a real
gold-table query.
"""

import streamlit as st

from chatbot import agent, llm

SUGGESTIONS = [
    "What's the total market value and how many open tenders are there?",
    "Who are the top 5 buyers by spend?",
    "What are the best IT opportunities right now?",
    "Which suppliers have won the most?",
    "Which countries publish the most notices?",
    "Break down procurement by type.",
]


def render():
    st.markdown("---")
    st.info(
        "Ask me anything about procurement trends, market opportunities, buyers, "
        "suppliers, or tenders. I answer in natural language using live gold-layer data."
    )

    # Allow users to paste a Groq key directly in the UI without needing .env
    import os
    if not os.environ.get("GROQ_API_KEY"):
        with st.expander("🔑 Enter Groq API key to enable Copilot", expanded=True):
            st.markdown("Get a free key at [console.groq.com](https://console.groq.com) — no credit card needed.")
            key_input = st.text_input("Groq API Key", type="password", placeholder="gsk_...")
            if key_input:
                os.environ["GROQ_API_KEY"] = key_input
                llm.get_client.cache_clear()
                st.success("Key saved for this session.")
                st.rerun()

    ready, reason = llm.is_configured()
    if not ready:
        st.warning(f"⚠️ Copilot not ready: **{reason}**")

    st.markdown("---")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Render history (a stored tool trace is shown in its own expander).
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("tools_used"):
                with st.expander("🔧 Data sources used"):
                    st.write(", ".join(f"`{t}`" for t in message["tools_used"]))

    # A suggestion button or the chat box can both supply the next question.
    user_input = st.chat_input("Ask about tenders, buyers, suppliers, opportunities…")
    pending = st.session_state.pop("pending_prompt", None)
    prompt = user_input or pending

    if prompt:
        if not ready:
            st.error("Can't answer yet — see the configuration notice above.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Querying the gold layer…"):
                    try:
                        result = agent.answer(st.session_state.messages)
                        content = result["content"] or "_(No answer returned.)_"
                        tools_used = result["tools_used"]
                    except Exception as exc:
                        detail = f"{type(exc).__name__}: {exc}"
                        cause = getattr(exc, "__cause__", None)
                        if cause:
                            detail += f"\n\n_underlying cause:_ `{type(cause).__name__}: {cause}`"
                        content = f"⚠️ Sorry, something went wrong:\n\n`{detail}`"
                        tools_used = []
                st.markdown(content)
                if tools_used:
                    with st.expander("🔧 Data sources used"):
                        st.write(", ".join(f"`{t}`" for t in tools_used))
            st.session_state.messages.append(
                {"role": "assistant", "content": content, "tools_used": tools_used}
            )

    st.markdown("---")
    st.subheader("💡 Try asking")
    cols = st.columns(2)
    for i, suggestion in enumerate(SUGGESTIONS):
        if cols[i % 2].button(suggestion, key=f"sug_{i}", use_container_width=True):
            st.session_state.pending_prompt = suggestion
            st.rerun()

    if st.session_state.messages:
        st.markdown("")
        if st.button("🗑️ Clear conversation"):
            st.session_state.messages = []
            st.rerun()
