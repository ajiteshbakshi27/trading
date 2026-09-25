"""
QuantPulse AI - Copilot quantitative reasoning engine.
Rule-based explainer over the live snapshot (no LLM key required):
answers "why this signal", "how to allocate", "risk", and "edge" questions
in plain language. If COPILOT_LLM_URL is configured, the frontend may
add a pass-through; the engine below always works offline of it.
"""
from __future__ import annotations
import re
from typing import Dict, Any, List


def _num(tok: str) -> float | None:
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)", tok.replace(",", ""))
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


def answer(question: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    q = (question or "").strip()
    ql = q.lower()
    signals: List[Dict[str, Any]] = snapshot.get("signals", []) or []
    pred = snapshot.get("prediction", {}) or {}
    edges = pred.get("edges", []) or []
    by_sym = {s.get("symbol", "").upper(): s for s in signals}

    # 1) Why a signal on SYM? Match against live symbols first
    # (a naive ticker regex would grab words like "WHY").
    up = q.upper()
    sym = next((s for s in by_sym if re.search(rf"\b{re.escape(s)}\b", up)), "")
    if ("why" in ql or "explain" in ql) and sym in by_sym:
        s = by_sym[sym]
        return {
            "answer": (
                f"{sym}: {s.get('type', '').replace('_', ' ')} "
                f"{s.get('direction', '')} at confidence "
                f"{float(s.get('confidence', 0)) * 100:.0f}%. "
                f"Crowd is {s.get('bullish_pct', 50)}% bullish while order-flow "
                f"imbalance reads {float(s.get('ofi_norm', 0)):+.2f}. {s.get('rationale', '')} "
                f"Target {s.get('target')}, stop {s.get('stop')}."
            ),
            "topic": "signal", "symbol": sym,
        }

    if ("why" in ql or "explain" in ql) and not sym:
        fades = [s for s in signals if s.get("type") == "BET_AGAINST"]
        if fades:
            s = fades[0]
            return {
                "answer": (
                    f"Top fade right now is {s.get('symbol')} "
                    f"({s.get('direction')}, confidence "
                    f"{float(s.get('confidence', 0)) * 100:.0f}%). {s.get('rationale', '')} "
                    f"Name a ticker for a deeper breakdown."
                ),
                "topic": "signal", "symbol": s.get("symbol", ""),
            }

    # 2) Allocation guidance.
    if "allocat" in ql or "lakh" in ql or "invest" in ql or "100000" in q.replace(",", ""):
        amt = _num(q) or 100000.0
        risk = "aggressive" if "aggress" in ql else "hft" if "arbitrage" in ql or "hft" in ql else "balanced"
        longs = [s for s in signals if s.get("direction") == "LONG"]
        shorts = [s for s in signals if s.get("direction") == "SHORT"]
        top = ", ".join(s.get("symbol", "") for s in longs[:3]) or "top quantum weights"
        hedge = ", ".join(s.get("symbol", "") for s in shorts[:2]) or "none flagged"
        return {
            "answer": (
                f"For {amt:,.0f} ({risk}): open /allocator with that budget and "
                f"risk profile — it converts quantum weights to whole shares. "
                f"Current LONG-leaning names: {top}. Hedge candidates: {hedge}. "
                f"Use the allocator's projected return vs drawdown to sanity-check "
                f"before sending any buy orders."
            ),
            "topic": "allocator", "suggested_budget": amt, "suggested_risk": risk,
        }

    # 3) Risk / drawdown / kill-switch.
    if "risk" in ql or "drawdown" in ql or "kill" in ql or "var" in ql:
        n_against = sum(1 for s in signals if s.get("type") == "BET_AGAINST")
        return {
            "answer": (
                f"Right now {n_against} active fade-crowd signal(s). "
                f"Risk is managed per-trade via target/stop levels on each card, "
                f"plus the portfolio kill-switch (default 5% drawdown) in the navbar — "
                f"tripping it halts new signals and liquidates live positions. "
                f"Size positions so no single stop-out costs more than ~1% of budget."
            ),
            "topic": "risk",
        }

    # 4) Prediction edges.
    if "edge" in ql or "predict" in ql or "arbitrage" in ql or "bet" in ql:
        if edges:
            top_e = edges[0]
            return {
                "answer": (
                    f"Top mispricing: '{top_e.get('question', '')}' — crowd "
                    f"{float(top_e.get('crowd_prob', 0)) * 100:.1f}% vs quantum "
                    f"{float(top_e.get('quantum_prob', 0)) * 100:.1f}% "
                    f"({top_e.get('side', '')}, edge {float(top_e.get('edge', 0)) * 100:+.1f}pp). "
                    f"Positive edge means the model prices YES above the crowd."
                ),
                "topic": "prediction",
            }
        return {"answer": "No prediction edges above threshold right now.", "topic": "prediction"}

    # 0) Default briefing.
    n_for = sum(1 for s in signals if s.get("type") == "BET_FOR")
    n_against = sum(1 for s in signals if s.get("type") == "BET_AGAINST")
    return {
        "answer": (
            f"Live board: {n_for} Bet-For and {n_against} fade-crowd signals. "
            f"Ask e.g. 'Why BET_AGAINST on TSLA?', 'How to allocate 100000 aggressive?', "
            f"'Any prediction edges?' or 'What is my risk?'"
        ),
        "topic": "briefing",
    }
