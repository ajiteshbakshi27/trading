"""
QuantPulse AI - Telegram / Discord webhook alerts (best-effort, never raises).
Fires on high-confidence BET_AGAINST (fade crowd) and high-discrepancy
prediction edges. No keys -> mock mode, payload returned unsent.
"""
from __future__ import annotations
import json
import urllib.request
from typing import List, Dict, Any

FADE_CONF_THRESHOLD = 0.75
EDGE_ABS_THRESHOLD = 0.12


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 8) -> bool:
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token or not chat_id:
        return False
    return _post_json(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                      {"chat_id": chat_id, "text": text[:3500]})


def send_discord(webhook_url: str, text: str) -> bool:
    if not webhook_url:
        return False
    return _post_json(webhook_url, {"content": text[:1900]})


def build_messages(signals: List[Dict[str, Any]],
                   edges: List[Dict[str, Any]]) -> List[str]:
    """Select alert-worthy events and format plain-text messages."""
    out = []
    for s in signals or []:
        if (s.get("type") == "BET_AGAINST"
                and float(s.get("confidence", 0) or 0) >= FADE_CONF_THRESHOLD):
            out.append(
                f"🚨 FADE CROWD: {s.get('symbol')} {s.get('direction')} "
                f"conf {float(s.get('confidence', 0)) * 100:.0f}% — "
                f"{str(s.get('rationale', ''))[:160]}")
    for e in edges or []:
        if abs(float(e.get("edge", 0) or 0)) >= EDGE_ABS_THRESHOLD:
            out.append(
                f"⚡ PRED EDGE: {e.get('question', '')} "
                f"crowd {float(e.get('crowd_prob', 0)) * 100:.1f}% → "
                f"quantum {float(e.get('quantum_prob', 0)) * 100:.1f}% "
                f"({e.get('side', '')})")
    return out


def maybe_alert(signals, edges, bot_token="", chat_id="",
                discord_url="") -> Dict[str, Any]:
    """Send at most a few messages. Always returns a report, never raises."""
    try:
        messages = build_messages(signals, edges)[:5]
        if not messages:
            return {"sent": 0, "checked": len(signals or []) + len(edges or []),
                    "mode": "mock" if not (bot_token or discord_url) else "live"}
        sent = 0
        for m in messages:
            ok = False
            if bot_token and chat_id:
                ok = send_telegram(bot_token, chat_id, m) or ok
            if discord_url:
                ok = send_discord(discord_url, m) or ok
            sent += 1 if ok else 0
        return {"sent": sent, "total": len(messages),
                "mode": "live" if (bot_token or discord_url) else "mock",
                "messages": messages}
    except Exception as e:
        return {"sent": 0, "error": str(e)[:200], "mode": "error"}
