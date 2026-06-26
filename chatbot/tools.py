"""
chatbot/tools.py — the bridge between the LLM and the gold layer.

Each entry in TOOLS is an OpenAI-style function schema the model can call. The
model never writes SQL: it picks a tool + arguments, and `dispatch()` runs the
matching pre-built query from `dashboard.db` (which reads the Databricks gold
tables). This keeps answers grounded in real gold-layer data and makes it
impossible for the model to run arbitrary/unsafe SQL.
"""
from __future__ import annotations

import json

import pandas as pd

from dashboard import db


# --- tool schemas advertised to the model ----------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": (
                "High-level market totals: open tenders (Contract Notices / CN) "
                "and awarded contracts (Contract Award Notices / CAN) — counts, "
                "countries covered, and total/average value in EUR. Use for "
                "'how big is the market', 'total value', 'how many tenders'."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_buyers",
            "description": "Public buyers (contracting authorities) ranked by total spend in EUR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many buyers (default 10, max 50)."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_suppliers",
            "description": "Winning suppliers/tenderers ranked by total value won in EUR (from awards).",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many suppliers (default 10, max 50)."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_countries",
            "description": "Buyer countries ranked either by number of notices or by total awarded value (EUR).",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "enum": ["notices", "award_value"],
                        "description": "Rank by notice volume or by awarded value. Default 'notices'.",
                    },
                    "limit": {"type": "integer", "description": "How many countries (default 10)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_cpv_sectors",
            "description": (
                "Top procurement sectors by lot volume, grouped by CPV division "
                "(Common Procurement Vocabulary — the EU category taxonomy)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many sectors (default 10)."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "procurement_type_breakdown",
            "description": "Distribution of lots by procurement type (e.g. services, supplies, works).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "it_opportunities",
            "description": (
                "Open IT-related tender lots ranked by opportunity score — the "
                "'Opportunity Radar'. Includes value, buyer, country, deadline, "
                "and predicted competition. Use for 'best opportunities', "
                "'which tenders should we pursue', 'IT tenders'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many opportunities (default 10, max 50)."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "largest_lots",
            "description": "The biggest individual lots by value (EUR), for open tenders (CN) or awards (CAN).",
            "parameters": {
                "type": "object",
                "properties": {
                    "notice_type": {
                        "type": "string",
                        "enum": ["CN", "CAN"],
                        "description": "CN = open tenders, CAN = awarded contracts. Default 'CN'.",
                    },
                    "limit": {"type": "integer", "description": "How many lots (default 10)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notice_volume_over_time",
            "description": "Daily count of published notices over time — for trend questions.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def _clamp(value, default: int, hi: int = 50) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(n, hi))


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list of plain dicts (NaN/dates made JSON-safe)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


# --- dispatch ---------------------------------------------------------------
def dispatch(name: str, args: dict) -> str:
    """Run the gold-layer query for a tool call; return a JSON string for the model."""
    args = args or {}
    try:
        if name == "get_market_summary":
            result = {"open_tenders_cn": db.cn_summary(), "awards_can": db.can_summary()}
        elif name == "top_buyers":
            result = _records(db.top_buyers(_clamp(args.get("limit"), 10)))
        elif name == "top_suppliers":
            result = _records(db.top_winners(_clamp(args.get("limit"), 10)))
        elif name == "top_countries":
            limit = _clamp(args.get("limit"), 10)
            if args.get("metric") == "award_value":
                result = _records(db.top_countries_by_award_value(limit))
            else:
                result = _records(db.top_countries_by_notices(limit))
        elif name == "top_cpv_sectors":
            result = _records(db.top_cpv_divisions(_clamp(args.get("limit"), 10)))
        elif name == "procurement_type_breakdown":
            result = _records(db.procurement_type_distribution())
        elif name == "it_opportunities":
            result = _records(db.it_lots(_clamp(args.get("limit"), 10)))
        elif name == "largest_lots":
            limit = _clamp(args.get("limit"), 10)
            if args.get("notice_type") == "CAN":
                result = _records(db.largest_can_lots(limit))
            else:
                result = _records(db.largest_cn_lots(limit))
        elif name == "notice_volume_over_time":
            result = _records(db.notice_volume_by_date())
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:  # surface DB/connection errors to the model
        return json.dumps({"error": f"Query failed: {exc}"})

    return json.dumps(result, default=str)
