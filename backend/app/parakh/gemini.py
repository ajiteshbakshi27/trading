"""
Parakh — Google Gemini backend for the AI layer (free-tier friendly).

Used by ``app.parakh.llm`` when GEMINI_API_KEY is set and no Anthropic key is.
Plain REST over httpx, so there is no extra dependency. The key travels in a
header, never in a URL, and is never logged.

Every function returns None on any failure so callers fall back to rules.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

from app.config import get_settings

log = logging.getLogger("parakh.gemini")
T = TypeVar("T", bound=BaseModel)
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 60.0


def available() -> bool:
    return bool(get_settings().GEMINI_API_KEY)


def model() -> str:
    return get_settings().GEMINI_MODEL


def _post(body: Dict[str, Any]) -> Dict[str, Any]:
    """One generateContent call. Raises on HTTP / network errors."""
    r = httpx.post(f"{BASE_URL}/models/{model()}:generateContent",
                   headers={"x-goog-api-key": get_settings().GEMINI_API_KEY or ""},
                   json=body, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _parts(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    cands = resp.get("candidates") or []
    if not cands:                       # blocked prompt or empty answer
        return []
    return (cands[0].get("content") or {}).get("parts") or []


def _text(parts: List[Dict[str, Any]]) -> str:
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def _system(system: str) -> Dict[str, Any]:
    return {"parts": [{"text": system}]}


def write(prompt: str, system: str, max_tokens: int = 4000) -> Optional[str]:
    try:
        resp = _post({"system_instruction": _system(system),
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens}})
        return _text(_parts(resp)) or None
    except Exception as e:
        log.warning("gemini write failed: %s", type(e).__name__)
        return None


def parse(prompt: str, schema: Type[T], system: str) -> Optional[T]:
    """Structured extraction: ask for JSON, then validate it with the schema."""
    ask = (f"{prompt}\n\nReply with one JSON object only, matching this JSON "
           f"schema:\n{json.dumps(schema.model_json_schema())}")
    try:
        resp = _post({"system_instruction": _system(system),
                      "contents": [{"role": "user", "parts": [{"text": ask}]}],
                      "generationConfig": {"maxOutputTokens": 4000,
                                           "responseMimeType": "application/json"}})
        raw = _text(_parts(resp))
        if not raw:
            return None
        return schema.model_validate_json(raw)
    except Exception as e:  # network, quota, bad JSON, validation
        log.warning("gemini parse failed: %s", type(e).__name__)
        return None


def _declarations(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Anthropic-style tool defs -> Gemini function declarations."""
    out = []
    for t in tools:
        d: Dict[str, Any] = {"name": t["name"], "description": t.get("description", "")}
        params = t.get("input_schema") or {}
        if params.get("properties"):    # Gemini rejects an object with no properties
            d["parameters"] = params
        out.append(d)
    return out


def _contents(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"role": "model" if m["role"] == "assistant" else "user",
             "parts": [{"text": str(m["content"])}]} for m in messages]


def run_tools(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
              execute: Callable[[str, Dict[str, Any]], str], system: str,
              max_turns: int = 6) -> Optional[Dict[str, Any]]:
    """Tool loop. Returns {"answer", "tools_used"} or None on failure."""
    used: List[str] = []
    contents = _contents(messages)
    body = {"system_instruction": _system(system),
            "tools": [{"function_declarations": _declarations(tools)}],
            "generationConfig": {"maxOutputTokens": 8000}}
    try:
        for _ in range(max_turns):
            parts = _parts(_post({**body, "contents": contents}))
            if not parts:
                return {"answer": "I can't help with that one.", "tools_used": used}
            calls = [p["functionCall"] for p in parts if p.get("functionCall")]
            if not calls:
                return {"answer": _text(parts), "tools_used": used}
            # Echo the model turn back unchanged (keeps any thought signatures).
            contents.append({"role": "model", "parts": parts})
            results = []
            for call in calls:
                name = call.get("name", "")
                used.append(name)
                try:
                    out = execute(name, dict(call.get("args") or {}))
                    payload = {"result": out}
                except Exception as e:
                    payload = {"error": f"Tool error: {e}"}
                results.append({"functionResponse": {"name": name, "response": payload}})
            contents.append({"role": "user", "parts": results})
        return {"answer": "That took too many steps — try a narrower question.",
                "tools_used": used}
    except Exception as e:
        log.warning("gemini tool loop failed: %s", type(e).__name__)
        return None
