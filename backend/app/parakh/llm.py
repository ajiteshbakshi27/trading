"""
Parakh — Claude integration.

Optional: everything in Parakh works without ANTHROPIC_API_KEY (rule-based
fallbacks). With a key, Claude parses free-text trade ideas, writes plain
language autopsies and powers the copilot.

Server-side refusal fallback is enabled (``fallbacks="default"``) so a
declined request is retried on a fallback model inside the same call.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger("parakh.llm")
T = TypeVar("T", bound=BaseModel)
_BETAS = ["server-side-fallback-2026-07-01"]

SYSTEM_GUARDRAILS = (
    "You are Parakh, an analysis assistant for Indian retail traders. You help "
    "people examine and stress-test THEIR OWN trade ideas and learn from past "
    "trades. You are not a SEBI-registered investment adviser or research "
    "analyst: never tell the user to buy, sell or hold a specific security, "
    "never give price targets of your own, and never promise returns. Frame "
    "everything as analysis of the user's idea, with the evidence for and "
    "against it and what would prove it wrong. Be plain-spoken, short and "
    "concrete; use rupees (₹) and Indian market context. Use only numbers that "
    "appear in tool results or the provided data; if data is simulated, say so."
)

_client = None


def available() -> bool:
    return bool(get_settings().ANTHROPIC_API_KEY)


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=get_settings().ANTHROPIC_API_KEY,
                                      max_retries=2, timeout=90.0)
    return _client


def model() -> str:
    return get_settings().CLAUDE_MODEL


def _text_of(resp: Any) -> str:
    return "".join(getattr(b, "text", "") for b in resp.content
                   if getattr(b, "type", "") == "text").strip()


def parse(prompt: str, schema: Type[T], system: str = SYSTEM_GUARDRAILS,
          effort: str = "low") -> Optional[T]:
    """Structured extraction. Returns None on any failure (caller falls back)."""
    if not available():
        return None
    try:
        resp = client().beta.messages.parse(
            model=model(), max_tokens=4000, system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema, output_config={"effort": effort},
            betas=_BETAS, fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return None
        return resp.parsed_output
    except Exception as e:  # network, auth, validation — never break the feature
        log.warning("claude parse failed: %s", type(e).__name__)
        return None


def write(prompt: str, system: str = SYSTEM_GUARDRAILS, effort: str = "low",
          max_tokens: int = 4000) -> Optional[str]:
    """Free-text generation (summaries, autopsy narratives, briefs)."""
    if not available():
        return None
    try:
        resp = client().beta.messages.create(
            model=model(), max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort}, betas=_BETAS, fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            return None
        return _text_of(resp) or None
    except Exception as e:
        log.warning("claude write failed: %s", type(e).__name__)
        return None


def run_tools(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
              execute, system: str = SYSTEM_GUARDRAILS, max_turns: int = 6,
              effort: str = "medium") -> Optional[Dict[str, Any]]:
    """Manual agentic loop over our own tools. ``execute(name, input) -> str``.

    Returns {"answer": str, "tools_used": [...]} or None when unavailable.
    """
    if not available():
        return None
    used: List[str] = []
    msgs = list(messages)
    try:
        for _ in range(max_turns):
            resp = client().beta.messages.create(
                model=model(), max_tokens=16000, system=system, tools=tools,
                messages=msgs, output_config={"effort": effort},
                betas=_BETAS, fallbacks="default",
            )
            if resp.stop_reason == "refusal":
                return {"answer": "I can't help with that one.", "tools_used": used}
            if resp.stop_reason == "pause_turn":
                msgs.append({"role": "assistant", "content": resp.content})
                continue
            calls = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
            if not calls:
                return {"answer": _text_of(resp), "tools_used": used}
            msgs.append({"role": "assistant", "content": resp.content})
            results = []
            for call in calls:
                used.append(call.name)
                try:
                    out = execute(call.name, dict(call.input or {}))
                    results.append({"type": "tool_result", "tool_use_id": call.id,
                                    "content": out})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": call.id,
                                    "content": f"Tool error: {e}", "is_error": True})
            msgs.append({"role": "user", "content": results})
        return {"answer": "That took too many steps — try a narrower question.",
                "tools_used": used}
    except Exception as e:
        log.warning("claude tool loop failed: %s", type(e).__name__)
        return None
