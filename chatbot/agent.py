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

import re

from openai import BadRequestError, RateLimitError

from chatbot import llm, tools

logger = logging.getLogger(__name__)

_FUNCTION_TAG_RE = re.compile(r"<function[^>]*>.*?</function>", re.DOTALL | re.IGNORECASE)


def _clean(text: str) -> str:
    """Strip residual <function>…</function> XML artifacts Llama sometimes emits."""
    return _FUNCTION_TAG_RE.sub("", text).strip()

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
- The dataset covers recent EU procurement notices (2025–2026). It contains no
  year-by-year historical breakdown. If asked about a specific past year (e.g.
  "in 2019"), clarify that the data does not filter by year and any figures shown
  reflect the full available dataset, not that year specifically.

RULES
- To answer anything quantitative, you MUST call the appropriate tool and base
  your answer strictly on its results. Never invent numbers, names, or trends.
- If a tool returns an error or empty result, say so plainly — do not guess.
- You may call several tools to assemble one answer.
- Be concise and use Markdown: short headers, bullet points, bold key figures.
- Format money readably (e.g. €4.2M, €850K) and always keep the € unit.
- If a question is clearly unrelated to EU procurement data (e.g. weather,
  coding tasks, general knowledge), decline politely WITHOUT calling any tools.
- If a question is outside this procurement data, say what you can help with instead.
"""


def _to_message_dicts(history: list[dict], max_turns: int = 6) -> list[dict]:
    """Keep only role/content from the UI history; cap to last `max_turns` pairs to bound token usage."""
    trimmed = history[-(max_turns * 2):]
    return [{"role": m["role"], "content": m["content"]} for m in trimmed]


def _retry_hint(exc: RateLimitError) -> str:
    m = re.search(r"try again in ([^\s,]+)", str(exc), re.IGNORECASE)
    return f" Try again in {m.group(1)}." if m else ""


def answer(history: list[dict]) -> dict:
    """Run one assistant turn.

    `history` is the running chat (list of {role, content}). Returns
    {"content": <markdown answer>, "tools_used": [<tool names>]}.
    """
    last_user = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), ""
    )
    if not last_user.strip():
        return {
            "content": "Please ask me a question about the EU procurement market — "
                       "e.g. top buyers, IT opportunities, country breakdowns, or market totals.",
            "tools_used": [],
        }

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
        except RateLimitError as exc:
            hint = _retry_hint(exc)
            return {
                "content": (
                    f"⏳ **Daily token limit reached on the free Groq tier.**{hint}\n\n"
                    "The limit resets every 24 hours. If this keeps happening, "
                    "ask the platform admin to upgrade to the Groq Dev tier."
                ),
                "tools_used": tools_used,
            }
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
            return {"content": _clean(fallback.choices[0].message.content or ""), "tools_used": tools_used}

        msg = resp.choices[0].message

        if not msg.tool_calls:
            content = _clean(msg.content or "")
            if not content:
                # Model returned only function-tag noise — ask it to try again in plain text.
                logger.warning("Model returned empty/artifact content; requesting plain-text retry.")
                messages.append({"role": "user", "content": "Please summarise the results in plain text now."})
                retry = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
                content = _clean(retry.choices[0].message.content or "")
            return {"content": content, "tools_used": tools_used}

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
    return {"content": _clean(final.choices[0].message.content or ""), "tools_used": tools_used}
