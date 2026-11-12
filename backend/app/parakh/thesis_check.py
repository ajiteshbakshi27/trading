"""
Parakh — Feature 1: check a trade idea BEFORE it is placed.

Input : a free-text idea ("Bank Nifty will rally after RBI, 2 weeks, 70% sure")
        or structured fields.
Output: a plain-language report —
  * checklist (trend, momentum, stretch, reward:risk, stop vs noise,
    target realism, market context, confidence gap)
  * pure-chance odds of hitting the target before the stop (Monte Carlo,
    zero drift, the stock's own volatility)
  * historical base rate from similar past setups in the same stock
  * the fusion stress test (same fuse() as the research loop)
  * "what would prove you wrong" levels

Nothing here recommends a trade. It measures the user's own idea.
"""
from __future__ import annotations

import math
import random
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from app.parakh import llm, market, universe

MC_PATHS = 2000
ANALOGUE_FLOOR = 15
UNREALISTIC_CAP = 35     # score ceiling when the target needs > 3x a typical move


# --------------------------------------------------------------------------
# 1. Parse the idea
# --------------------------------------------------------------------------

class ParsedIdea(BaseModel):
    symbol: str = Field(description="NSE symbol, e.g. RELIANCE, HDFCBANK, NIFTY, BANKNIFTY")
    direction: str = Field(description="LONG if the user expects the price to rise, SHORT if fall")
    horizon_days: int = Field(description="Trading days until the idea should play out (1-120)")
    catalyst: str = Field(default="", description="The reason / event the user gives, short")
    user_confidence: float = Field(default=0.6, description="User's stated confidence 0.5-0.99")
    target_price: Optional[float] = Field(default=None, description="Explicit target in rupees, if stated")
    stop_price: Optional[float] = Field(default=None, description="Explicit stop-loss in rupees, if stated")


_UP = r"\b(rally|rallies|rise|rises|up|upside|bull|bullish|buy|long|breakout|go higher|moon|gain|jump|surge)\b"
_DOWN = r"\b(fall|falls|drop|drops|down|downside|bear|bearish|sell|short|crash|breakdown|go lower|decline|slide|tank)\b"


def _rule_parse(text: str) -> Optional[ParsedIdea]:
    t = " " + text.lower() + " "
    symbol = None
    for alias, sym in universe.alias_table():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", t):
            symbol = sym
            break
    if not symbol:
        m = re.search(r"\b([A-Z][A-Z&-]{1,12})\b", text)
        symbol = m.group(1) if m else None
    if not symbol:
        return None
    up, down = len(re.findall(_UP, t)), len(re.findall(_DOWN, t))
    direction = "SHORT" if down > up else "LONG"
    horizon = 10
    m = re.search(r"(\d+)\s*(trading\s+)?(day|days|d|week|weeks|wk|month|months)\b", t)
    if m:
        n, unit = int(m.group(1)), m.group(3)
        horizon = n * (5 if unit.startswith("w") else 21 if unit.startswith("m") else 1)
    elif "intraday" in t or "today" in t:
        horizon = 1
    elif "next week" in t or "a week" in t:
        horizon = 5
    elif "month" in t:
        horizon = 21
    conf = 0.6
    m = re.search(r"(\d{2})\s*%\s*(sure|confident|confidence|probability|chance)?", t)
    if m and 50 <= int(m.group(1)) <= 99:
        conf = int(m.group(1)) / 100
    elif re.search(r"\b(very sure|definitely|100%|sure shot|guaranteed)\b", t):
        conf = 0.9
    def _price(word: str) -> Optional[float]:
        mm = re.search(rf"(?:{word})\D{{0,12}}(\d[\d,]*\.?\d*)", t)
        return float(mm.group(1).replace(",", "")) if mm else None
    m = re.search(r"\b(after|on|because|due to|post)\b(.{3,60}?)(,|\.|$| in \d| within)", t)
    catalyst = m.group(2).strip() if m else ""
    return ParsedIdea(symbol=universe.normalize(symbol), direction=direction,
                      horizon_days=max(1, min(120, horizon)), catalyst=catalyst,
                      user_confidence=conf, target_price=_price("target"),
                      stop_price=_price(r"stop loss|stoploss|stop|\bsl"))


def parse_idea(text: str) -> Tuple[Optional[ParsedIdea], str]:
    """AI model first (if configured), rules as fallback. Returns (idea, mode)."""
    text = (text or "").strip()[:1000]
    if not text:
        return None, "none"
    idea = llm.parse(
        "Extract the trade idea from this message by an Indian retail trader. "
        "Map company or index names to NSE symbols (indices: NIFTY, BANKNIFTY, "
        "SENSEX). If no horizon is stated use 10. If no confidence is stated "
        f"use 0.6.\n\nMessage: {text}", ParsedIdea)
    if idea is not None:
        idea.symbol = universe.normalize(idea.symbol)
        idea.direction = "SHORT" if idea.direction.upper().startswith("S") else "LONG"
        idea.horizon_days = max(1, min(120, int(idea.horizon_days or 10)))
        idea.user_confidence = max(0.5, min(0.99, float(idea.user_confidence or 0.6)))
        return idea, (llm.provider() or "claude")
    idea = _rule_parse(text)
    return idea, ("rules" if idea else "none")


# --------------------------------------------------------------------------
# 2. Measurements
# --------------------------------------------------------------------------

def chance_odds(entry: float, target: float, stop: float, daily_vol: float,
                horizon: int, direction: str, seed: int = 7) -> Dict[str, float]:
    """Zero-drift Monte Carlo: P(target before stop within horizon).

    'Pure chance' baseline — what a coin-flip market with this stock's own
    volatility gives you. Deterministic (fixed seed)."""
    rng = random.Random(seed)
    hit = stopped = 0
    sub = 4  # intraday sub-steps so barriers are touched realistically
    sig = daily_vol / math.sqrt(sub)
    for _ in range(MC_PATHS):
        p = entry
        outcome = 0
        for _ in range(horizon * sub):
            p *= math.exp(rng.gauss(-0.5 * sig * sig, sig))
            if direction == "LONG":
                if p >= target: outcome = 1; break
                if p <= stop: outcome = -1; break
            else:
                if p <= target: outcome = 1; break
                if p >= stop: outcome = -1; break
        if outcome == 1: hit += 1
        elif outcome == -1: stopped += 1
    n = float(MC_PATHS)
    return {"p_target": round(hit / n, 3), "p_stop": round(stopped / n, 3),
            "p_neither": round((MC_PATHS - hit - stopped) / n, 3)}


def analogues(bars: List[market.Bar], direction: str, target_pct: float,
              stop_pct: float, horizon: int) -> Dict[str, Any]:
    """Past days in THIS stock with a similar setup; how did the same
    target/stop distances play out over the same horizon?"""
    cl = market.closes(bars)
    n = len(cl)
    if n < 120 + horizon:
        return {"n": 0, "hit_rate": None, "note": "Not enough history."}
    def setup(i: int) -> Tuple[int, int]:
        mom = cl[i] / cl[i - 20] - 1
        vol20 = market.stdev(market.daily_returns(cl[i - 20:i + 1])) * math.sqrt(20) or 1e-9
        z = mom / vol20
        bucket = -1 if z < -0.5 else 1 if z > 0.5 else 0
        s50 = sum(cl[i - 50:i]) / 50
        return bucket, (1 if cl[i] > s50 else -1)
    now = setup(n - 1)
    hits = misses = neither = 0
    examples: List[Dict[str, Any]] = []
    i = 60
    while i < n - horizon - 1:
        if setup(i) == now:
            e = cl[i]
            tgt = e * (1 + target_pct) if direction == "LONG" else e * (1 - target_pct)
            stp = e * (1 - stop_pct) if direction == "LONG" else e * (1 + stop_pct)
            res = 0
            for b in bars[i + 1:i + 1 + horizon]:
                hit_t = b["high"] >= tgt if direction == "LONG" else b["low"] <= tgt
                hit_s = b["low"] <= stp if direction == "LONG" else b["high"] >= stp
                if hit_s: res = -1; break          # same-day tie counts as a stop
                if hit_t: res = 1; break
            hits += res == 1; misses += res == -1; neither += res == 0
            if len(examples) < 5 and res != 0:
                examples.append({"date": bars[i]["date"], "result": "target" if res == 1 else "stop"})
            i += max(1, horizon // 2)               # thin overlapping windows
        else:
            i += 1
    total = hits + misses + neither
    if total < ANALOGUE_FLOOR:
        return {"n": total, "hit_rate": None, "examples": examples,
                "note": f"Only {total} similar setups — below the {ANALOGUE_FLOOR}-sample floor."}
    return {"n": total, "hit_rate": round(hits / total, 3),
            "stop_rate": round(misses / total, 3), "examples": examples,
            "note": "Same stock, same trend/momentum setup, same % target and stop."}


def _applicable(scenario: Any, present: set) -> bool:
    from app.services.thesis_stress import SCENARIO_BY_ID
    spec = SCENARIO_BY_ID.get(scenario)
    target = getattr(spec, "target", None)
    return str(getattr(target, "value", target)) in present


def _check(cid: str, title: str, status: str, detail: str) -> Dict[str, str]:
    return {"id": cid, "title": title, "status": status, "detail": detail}


def _fmt(x: float) -> str:
    return f"₹{x:,.2f}"


def build_report(idea: ParsedIdea) -> Dict[str, Any]:
    from app.models.enums import Regime
    from app.services import thesis_stress
    sym = universe.normalize(idea.symbol)
    bars, mode = market.history(sym, 500)
    cl = market.closes(bars)
    entry = cl[-1]
    long = idea.direction == "LONG"
    atr = market.atr(bars, 14) or entry * 0.015
    rets = market.daily_returns(cl[-61:])
    dvol = market.stdev(rets) or 0.015
    h = idea.horizon_days

    stop = idea.stop_price or (entry - 1.5 * atr if long else entry + 1.5 * atr)
    target = idea.target_price or (entry + 3.0 * atr if long else entry - 3.0 * atr)
    # sanity: a stop/target on the wrong side is a user error we flag + fix
    fixes = []
    if long and stop >= entry or (not long and stop <= entry):
        fixes.append("Your stop was on the wrong side of the price; replaced with a 1.5×ATR stop.")
        stop = entry - 1.5 * atr if long else entry + 1.5 * atr
    if long and target <= entry or (not long and target >= entry):
        fixes.append("Your target was on the wrong side of the price; replaced with a 3×ATR target.")
        target = entry + 3 * atr if long else entry - 3 * atr
    risk, reward = abs(entry - stop), abs(target - entry)
    rr = reward / risk if risk else 0.0
    target_pct, stop_pct = reward / entry, risk / entry

    s20, s50, s200 = market.sma(cl, 20), market.sma(cl, 50), market.sma(cl, 200)
    rsi = market.rsi(cl, 14) or 50.0
    mom20 = cl[-1] / cl[-21] - 1 if len(cl) > 21 else 0.0
    exp_move = entry * dvol * math.sqrt(h)

    checks: List[Dict[str, str]] = []
    if s50 and s200:
        up_trend = entry > s50 > s200
        down_trend = entry < s50 < s200
        with_trend = (long and up_trend) or (not long and down_trend)
        against = (long and down_trend) or (not long and up_trend)
        if up_trend or down_trend:
            shape = ("Your idea goes with the trend." if with_trend
                     else "Your idea fights the trend — these fail more often.")
        elif entry > s50 and entry > s200:
            shape = ("Price is above both averages, but the 50-day is still below the 200-day, "
                     "so the up-trend is not confirmed yet.")
        elif entry < s50 and entry < s200:
            shape = ("Price is below both averages, but the 50-day is still above the 200-day, "
                     "so the down-trend is not confirmed yet.")
        else:
            shape = "Price is between its two averages: no clear trend."
        checks.append(_check("trend", "Trend", "pass" if with_trend else "fail" if against else "warn",
            f"Price {_fmt(entry)} vs 50-day avg {_fmt(s50)} and 200-day avg {_fmt(s200)}. " + shape))
    checks.append(_check("momentum", "Recent momentum",
        "pass" if (mom20 > 0) == long else "warn",
        f"Last 20 trading days: {mom20 * 100:+.1f}%."))
    stretched = (long and rsi > 70) or (not long and rsi < 30)
    checks.append(_check("stretch", "Stretched?", "warn" if stretched else "pass",
        f"RSI(14) is {rsi:.0f}. " + ("Already stretched in your direction — late entries often get shaken out."
                                     if stretched else "Not stretched.")))
    need_sigma = reward / exp_move if exp_move else 0
    far = need_sigma > 2      # a far-off target makes reward:risk look good on paper only
    checks.append(_check("reward_risk", "Reward : risk",
        "fail" if rr < 1.3 else "warn" if (rr < 2 or far) else "pass",
        f"Risking {_fmt(risk)} to make {_fmt(reward)} → {rr:.1f} : 1."
        + (" This only looks good because the target is very far away (see Target realism)."
           if far and rr >= 2 else "")))
    stop_atr = risk / atr if atr else 0
    checks.append(_check("stop_noise", "Stop vs daily noise", "fail" if stop_atr < 1 else "warn" if stop_atr < 1.3 else "pass",
        f"Stop is {stop_atr:.1f}× the average daily range ({_fmt(atr)}). "
        + ("Normal daily noise can hit it." if stop_atr < 1 else "Reasonable room.")))
    checks.append(_check("target_realism", "Target realism",
        "pass" if need_sigma <= 1 else "warn" if need_sigma <= 2 else "fail",
        f"A typical {h}-day move is about ±{_fmt(exp_move)}; your target needs {need_sigma:.1f}× that."))

    nifty_note = None
    if sym not in ("NIFTY", "SENSEX"):
        nb, _ = market.history("NIFTY", 260)
        ncl = market.closes(nb)
        n50 = market.sma(ncl, 50)
        if n50:
            mkt_up = ncl[-1] > n50
            ok = mkt_up == long
            nifty_note = "NIFTY above its 50-day average" if mkt_up else "NIFTY below its 50-day average"
            checks.append(_check("market", "Market backdrop", "pass" if ok else "warn",
                nifty_note + (" — supports your direction." if ok else " — a headwind for your direction.")))

    odds = chance_odds(entry, target, stop, dvol, h, idea.direction)
    analog = analogues(bars, idea.direction, target_pct, stop_pct, h)
    base = analog.get("hit_rate")
    reference = base if base is not None else odds["p_target"]
    gap = idea.user_confidence - reference
    checks.append(_check("confidence_gap", "Your confidence vs the odds",
        "pass" if gap <= 0.1 else "warn" if gap <= 0.25 else "fail",
        f"You said {idea.user_confidence * 100:.0f}%. "
        + (f"Similar past setups hit this target {base * 100:.0f}% of the time (n={analog['n']}). "
           if base is not None else "")
        + f"Pure chance gives {odds['p_target'] * 100:.0f}%."))

    # Fusion stress test — same function as the research loop.
    vol20 = market.stdev(market.daily_returns(cl[-21:])) * math.sqrt(20) or 1e-9
    evidence = [
        {"feature": "momentum", "z_score": round(max(-3, min(3, mom20 / vol20)), 3),
         "confidence": 0.7, "data_mode": "live" if mode == "live" else "mock", "layer": "momentum"},
    ]
    if s200:
        trend_z = max(-3, min(3, (entry / s200 - 1) / (dvol * math.sqrt(60))))
        evidence.append({"feature": "momentum", "z_score": round(trend_z, 3), "confidence": 0.6,
                         "data_mode": evidence[0]["data_mode"], "layer": "trend"})
    stress: Dict[str, Any] = {}
    try:
        th = thesis_stress.build_thesis(sym, evidence, regime=Regime.UNKNOWN)
        st = thesis_stress.run_stress(th)
        d = st.model_dump()
        present = {str(e["feature"]) for e in evidence}
        mdir = th.direction.value if hasattr(th.direction, "value") else str(th.direction)
        agrees = (mdir == "LONG" and long) or (mdir == "SHORT" and not long)
        stress = {"model_direction": mdir, "model_agrees": agrees if mdir != "FLAT" else None,
                  "model_confidence": round(th.confidence, 3),
                  "robustness": d.get("robustness") if mdir != "FLAT" else None,
                  "label": d.get("robustness_label") if mdir != "FLAT"
                           else "No clear lean in price data, so there's nothing to stress-test",
                  "worst_case_confidence": d.get("worst_case_confidence"),
                  "scenarios": [{"scenario": str(r.get("label") or r.get("scenario")),
                                 "survives": r.get("survives"), "flipped": r.get("flipped"),
                                 "confidence": r.get("perturbed_confidence")}
                                for r in d.get("scenarios", [])
                                if _applicable(r.get("scenario"), present)],
                  "not_applicable": [str(r.get("label")) for r in d.get("scenarios", [])
                                     if not _applicable(r.get("scenario"), present)],
                  "note": ("Price-only evidence (momentum + trend) run through the shared "
                           "fusion model and attacked under the 7 stress rules. Rules whose "
                           "feature is absent are reported, not scored as passes.")}
    except Exception as e:
        stress = {"error": f"stress test unavailable: {type(e).__name__}"}

    weights = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
    score = round(100 * sum(weights[c["status"]] for c in checks) / max(1, len(checks)))
    score_note = ""
    if need_sigma > 3 and score > UNREALISTIC_CAP:
        score = UNREALISTIC_CAP
        score_note = (f"Score held at {UNREALISTIC_CAP}: the target needs {need_sigma:.1f}× a typical "
                      f"{h}-day move, so the other checks matter little.")
    wrong = [
        f"A daily close {'below' if long else 'above'} {_fmt(stop)} (your stop).",
        f"No move to {_fmt(target)} within {h} trading days — the idea has timed out; exit and re-think.",
    ]
    if nifty_note:
        wrong.append(f"NIFTY closing {'below' if long else 'above'} its 50-day average ({_fmt(market.sma(market.closes(market.history('NIFTY', 260)[0]), 50) or 0)}).")
    if idea.catalyst:
        wrong.append(f"The catalyst ({idea.catalyst}) happens and price doesn't respond within 2 sessions.")

    return {
        "symbol": sym, "name": universe.display_name(sym), "direction": idea.direction,
        "horizon_days": h, "catalyst": idea.catalyst, "user_confidence": idea.user_confidence,
        "entry_price": round(entry, 2), "target_price": round(target, 2), "stop_price": round(stop, 2),
        "reward_risk": round(rr, 2), "atr": round(atr, 2), "as_of": bars[-1]["date"],
        "data_mode": mode, "checks": checks, "checklist_score": score, "score_note": score_note,
        "chance_odds": odds, "analogues": analog, "stress": stress,
        "what_proves_you_wrong": wrong, "fixes": fixes,
        "disclaimer": ("Parakh analyses your own idea. It is not investment advice or a "
                       "recommendation to buy or sell. Past patterns do not guarantee outcomes."),
    }


def new_id() -> str:
    return "th_" + uuid.uuid4().hex[:16]
