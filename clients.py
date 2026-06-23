"""
clients.py  —  shared connections to Tavily (web search) and Claude (AI).

Centralized here so the rest of the tool doesn't repeat setup code. Reads your
API keys from the .env file. If a key is missing it raises a clear, friendly
error telling you exactly what to fix.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()  # read keys from the .env file in this folder


def _require(key, where):
    value = os.environ.get(key)
    if not value or value.strip().startswith(("tvly-xxxx", "sk-ant-xxxx")):
        raise RuntimeError(
            f"Missing {key}. Open your .env file and paste in a real key "
            f"({where}). See .env.example for the format."
        )
    return value


def tavily():
    """A Tavily web-search client."""
    from tavily import TavilyClient
    return TavilyClient(api_key=_require("TAVILY_API_KEY", "from https://tavily.com"))


def anthropic_client():
    """A Claude (Anthropic) client."""
    import anthropic
    _require("ANTHROPIC_API_KEY", "from https://console.anthropic.com")
    return anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


def ask_json(model, system, user, schema, max_tokens=8000):
    """
    Ask Claude a question and get back structured JSON that matches `schema`.

    Uses Claude's structured-output feature so the reply is always valid JSON
    in the exact shape we asked for — no fragile text parsing. Returns a Python
    dict/list parsed from that JSON.
    """
    client = anthropic_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return json.loads(text)


def ask_text(model, system, user, max_tokens=2000):
    """Ask Claude for a plain-text reply (used for email drafts)."""
    client = anthropic_client()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
