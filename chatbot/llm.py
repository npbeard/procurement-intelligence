"""
chatbot/llm.py — provider-agnostic LLM client for the Procurement Copilot.

Both supported providers expose an OpenAI-compatible Chat Completions API, so the
agent code is identical; only the base URL, key, and model name differ. Choose
the provider with CHATBOT_PROVIDER in .env:

  CHATBOT_PROVIDER=groq        (default) — free Llama hosting; needs GROQ_API_KEY
  CHATBOT_PROVIDER=databricks  — Databricks Foundation Model APIs (paid tiers only;
                                 NOT available on Databricks Free Edition)

GROQ (recommended for Databricks Free Edition):
    GROQ_API_KEY     get a free key at https://console.groq.com (no card)
    GROQ_MODEL       optional; default 'llama-3.3-70b-versatile'

DATABRICKS:
    DATABRICKS_HOST / DATABRICKS_TOKEN   (token needs the model-serving scope)
    DATABRICKS_LLM_ENDPOINT              optional; default Llama 3.3 70B endpoint

Note: the gold-layer SQL queries always use Databricks (see dashboard/db.py),
regardless of which LLM provider answers the questions.
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def provider() -> str:
    return os.environ.get("CHATBOT_PROVIDER", "groq").lower()


def model_name() -> str:
    if provider() == "databricks":
        return os.environ.get("DATABRICKS_LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
    return os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def _databricks_base_url() -> str:
    host = os.environ["DATABRICKS_HOST"].rstrip("/")
    if not host.startswith("http"):
        host = f"https://{host}"
    return f"{host}/serving-endpoints"


@lru_cache(maxsize=1)
def get_client():
    """OpenAI-compatible client for the configured provider.

    Imported lazily so the dashboard still loads if ``openai`` isn't installed —
    the Copilot page surfaces a friendly hint instead of crashing.
    """
    from openai import OpenAI

    if provider() == "databricks":
        return OpenAI(
            api_key=os.environ["DATABRICKS_TOKEN"],
            base_url=_databricks_base_url(),
        )
    # default: Groq
    return OpenAI(
        api_key=os.environ["GROQ_API_KEY"],
        base_url="https://api.groq.com/openai/v1",
    )


def is_configured() -> tuple[bool, str]:
    """(ready, reason). Cheap pre-flight so the UI can explain what's missing."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return False, "The `openai` package is not installed (pip install openai)."

    if provider() == "databricks":
        for var in ("DATABRICKS_HOST", "DATABRICKS_TOKEN"):
            if not os.environ.get(var):
                return False, f"Missing environment variable: {var}"
    else:
        if not os.environ.get("GROQ_API_KEY"):
            return False, "Missing GROQ_API_KEY (get a free key at https://console.groq.com)."
    return True, ""
