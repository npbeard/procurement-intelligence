"""
chatbot/agent.py — the tool-calling loop for the Procurement Copilot.

Flow:
  1. Send the conversation + tool schemas to Llama (on Databricks).
  2. If the model requests tool calls, run them against the gold layer
     (chatbot.tools.dispatch) and feed the results back.
  3. Repeat until the model returns a normal text answer (capped iterations).

The model is instructed to answer *only* from tool results, so every number it
reports is real gold-layer data, not invented.
"""
from __future__ import annotations

import json
import logging

from openai import BadRequestError

from chatbot import llm, tools

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """\
You are the Procurement Copilot for a TED (Tenders Electronic Daily) EU public-
procurement intelligence platform. You help analysts understand the European
public-procurement market.

DATA & TERMS
- All figures come from a curated Databricks "gold" layer, queried via your tools.
- CN = Contract Notice = an OPEN tender (a buying opportunity).
- CAN = Contract Award Notice = a tender that has been AWARDED to a supplier.
- "Buyers" are public contracting authorities; "suppliers"/"tenderers" win awards.
- CPV = Common Procurement Vocabulary, the EU category taxonomy (by division).
- Monetary values are in EUR.

RULES
- To answer anything quantitative, you MUST call the appropriate tool and base
  your answer strictly on its results. Never invent numbers, names, or trends.
- If a tool returns an error or empty result, say so plainly — do not guess.
- You may call several tools to assemble one answer.
- Be concise and use Markdown: short headers, bullet points, bold key figures.
- Format money readably (e.g. €4.2M, €850K) and always keep the € unit.
- If a question is outside this procurement data, say what you can help with instead.
"""


def _to_message_dicts(history: list[dict]) -> list[dict]:
    """Keep only role/content from the UI history (drop any UI-only fields)."""
    return [{"role": m["role"], "content": m["content"]} for m in history]


def answer(history: list[dict]) -> dict:
    """Run one assistant turn.

    `history` is the running chat (list of {role, content}). Returns
    {"content": <markdown answer>, "tools_used": [<tool names>]}.
    """
    client = llm.get_client()
    model = llm.model_name()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _to_message_dicts(history)
    tools_used: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools.TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except BadRequestError as exc:
            # Groq rejects when the model generates a tool call with a wrong
            # argument type (e.g. limit as "10" instead of 10). Retry without
            # tools so the model gives a plain answer rather than crashing.
            logger.warning("Tool-call validation rejected by API (%s); retrying without tools.", exc)
            fallback = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            )
            return {"content": fallback.choices[0].message.content or "", "tools_used": tools_used}

        msg = resp.choices[0].message

        if not msg.tool_calls:
            return {"content": msg.content or "", "tools_used": tools_used}

        # Echo the assistant's tool-call request, then append each tool result.
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            name = tc.function.name
            tools_used.append(name)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.dispatch(name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    # Ran out of tool rounds — ask the model to wrap up with what it has.
    messages.append(
        {"role": "user", "content": "Please give your best final answer now using the data already gathered."}
    )
    final = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
    return {"content": final.choices[0].message.content or "", "tools_used": tools_used}
