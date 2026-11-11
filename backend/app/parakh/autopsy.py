"""
Parakh — Feature 3: automatic post-trade autopsy.

Works for both a resolved thesis check and a closed journal round trip.
Each failure mode is a named rule with the evidence that triggered it and a
likelihood weight. Language is deliberately "likely contributed", never
"caused": we rank explanations, we don't prove them.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from app.parakh import llm, market

LABELS = {
    "stop_too_tight": "Stop inside normal daily noise",
    "against_trend": "Fought the trend",
    "chased": "Chased an already-stretched move",
    "overconfident": "Confidence far above the odds",
    "unrealistic_target": "Target needed an unusually big move",
    "event_gap": "Hit by a gap / news day",
    "market_drag": "The whole market moved against you",
    "wrong_timing": "Right idea, wrong timing",
    "held_too_long": "Loss allowed to grow past the plan",
    "lucky_win": "Won despite a weak setup",
}


def _mode(key: str, likelihood: float, evidence: str) -> Dict[str, Any]:
    return {"mode": key, "label": LABELS[key], "likelihood": round(likelihood, 2), "evidence": evidence}


def diagnose(*, symbol: str, direction: str, entry: float, exit_price: float,
             entry_date: str, exit_date: str, stop: Optional[float] = None,
             target: Optional[float] = None, horizon: Optional[int] = None,
             user_confidence: Optional[float] = None,
             report: Optional[Dict[str, Any]] = None,
             with_narrative: bool = False) -> Dict[str, Any]:
    long = direction == "LONG"
    ret = (exit_price / entry - 1) * (1 if long else -1) if entry else 0.0
    won = ret > 0
    bars, mode = market.history(symbol, 500)
    idx = {b["date"]: i for i, b in enumerate(bars)}
    i0 = idx.get(entry_date) or next((i for i, b in enumerate(bars) if b["date"] >= entry_date), None)
    i1 = idx.get(exit_date) or next((i for i, b in enumerate(bars) if b["date"] >= exit_date), len(bars) - 1)
    pre = bars[: (i0 or 0) + 1]
    held = bars[(i0 or 0): i1 + 1] if i0 is not None else []
    atr = market.atr(pre, 14) if len(pre) > 15 else (report or {}).get("atr") or entry * 0.015
    cl_pre = market.closes(pre)
    dvol = market.stdev(market.daily_returns(cl_pre[-61:])) if len(cl_pre) > 20 else 0.015
    checks = {c["id"]: c for c in (report or {}).get("checks", [])}
    modes: List[Dict[str, Any]] = []

    if not won:
        if stop and atr:
            dist = abs(entry - stop) / atr
            if dist < 1.0:
                modes.append(_mode("stop_too_tight", 0.8 - 0.3 * dist,
                                   f"Stop was {dist:.1f}× the average daily range (₹{atr:,.2f})."))
        if checks.get("trend", {}).get("status") == "fail":
            modes.append(_mode("against_trend", 0.6, checks["trend"]["detail"]))
        elif len(cl_pre) > 200:
            s50, s200 = market.sma(cl_pre, 50), market.sma(cl_pre, 200)
            if s50 and s200 and ((long and entry < s50 < s200) or (not long and entry > s50 > s200)):
                modes.append(_mode("against_trend", 0.55, "Entry was against the 50/200-day trend."))
        if checks.get("stretch", {}).get("status") == "warn":
            modes.append(_mode("chased", 0.45, checks["stretch"]["detail"]))
        else:
            r = market.rsi(cl_pre, 14) if len(cl_pre) > 15 else None
            if r and ((long and r > 70) or (not long and r < 30)):
                modes.append(_mode("chased", 0.45, f"RSI(14) was {r:.0f} at entry."))
        if checks.get("target_realism", {}).get("status") == "fail":
            modes.append(_mode("unrealistic_target", 0.5, checks["target_realism"]["detail"]))
        if user_confidence is not None and report:
            ref = (report.get("analogues") or {}).get("hit_rate") or (report.get("chance_odds") or {}).get("p_target")
            if ref is not None and user_confidence - ref > 0.25:
                modes.append(_mode("overconfident", 0.5,
                                   f"You said {user_confidence * 100:.0f}%; the odds were about {ref * 100:.0f}%."))
        if held and dvol:
            for j in range(1, len(held)):
                r = held[j]["open"] / held[j - 1]["close"] - 1
                if abs(r) > 3 * dvol and ((r < 0) == long):
                    modes.append(_mode("event_gap", 0.55,
                                       f"{held[j]['date']}: opened {r * 100:+.1f}% vs previous close."))
                    break
        if held and symbol not in ("NIFTY", "SENSEX"):
            nb, _ = market.history("NIFTY", 500)
            nidx = {b["date"]: b["close"] for b in nb}
            a, b_ = nidx.get(held[0]["date"]), nidx.get(held[-1]["date"])
            if a and b_:
                nret = (b_ / a - 1) * (1 if long else -1)
                if nret < -0.015:
                    modes.append(_mode("market_drag", min(0.7, 0.3 + abs(nret) * 10),
                                       f"NIFTY moved {nret * 100:+.1f}% against your direction while you held."))
        if target and horizon and i1 is not None:
            after = bars[i1 + 1: i1 + 1 + horizon]
            for b in after:
                if (long and b["high"] >= target) or (not long and b["low"] <= target):
                    modes.append(_mode("wrong_timing", 0.6,
                                       f"Price reached your target ₹{target:,.2f} on {b['date']}, after you were out."))
                    break
        if stop and ((long and exit_price < stop * 0.98) or (not long and exit_price > stop * 1.02)):
            modes.append(_mode("held_too_long", 0.6,
                               f"Exited at ₹{exit_price:,.2f}, beyond the planned stop ₹{stop:,.2f}."))
    else:
        score = (report or {}).get("checklist_score")
        if score is not None and score < 50:
            modes.append(_mode("lucky_win", 0.5,
                               f"Pre-trade checklist score was {score}/100. Don't let a win reinforce a weak process."))

    modes.sort(key=lambda m: -m["likelihood"])
    lessons = {
        "stop_too_tight": "Place stops beyond 1–1.5× the average daily range, and size the position down to keep rupee risk the same.",
        "against_trend": "Require a reason stronger than 'it's cheap' before fighting the 50/200-day trend.",
        "chased": "Wait for a pullback when RSI is stretched in your direction.",
        "overconfident": "Write down the odds before you trade; size by them, not by how sure you feel.",
        "unrealistic_target": "Set targets within about 1× the typical move for your holding period.",
        "event_gap": "Check results dates and events inside your holding period; reduce size through them.",
        "market_drag": "Your stock trade was partly a NIFTY trade. Check the index backdrop first.",
        "wrong_timing": "Your read was right but early: use a wider time window or wait for confirmation.",
        "held_too_long": "Honour the stop you planned. Decide the exit before the entry.",
        "lucky_win": "Review what the checklist flagged; a repeatable process matters more than one outcome.",
    }
    out = {
        "symbol": symbol, "direction": direction, "outcome": "win" if won else "loss",
        "return_pct": round(ret * 100, 2), "entry_price": entry, "exit_price": exit_price,
        "entry_date": entry_date, "exit_date": exit_date, "data_mode": mode,
        "failure_modes": modes,
        "top_lesson": lessons.get(modes[0]["mode"]) if modes else
            ("Clean result — the setup and the outcome agreed." if won else
             "No rule matched clearly; this may simply have been an unlucky draw."),
        "method": "Rule-based: each mode is a named check with its evidence; likelihoods rank explanations, they do not prove cause.",
    }
    if with_narrative and llm.available():
        out["narrative"] = llm.write(
            "Write a 3-sentence plain-English autopsy for this Indian retail trader. "
            "Be kind but direct. Use only these facts:\n" + str(out), effort="low", max_tokens=1500)
    return out
