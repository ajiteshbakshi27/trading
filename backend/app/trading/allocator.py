"""
QuantPulse AI - Smart Capital Allocator (Phase 4)
Combines Quantum Portfolio Optimization (QAOA/VQE proxy), social-sentiment
momentum, and HFT risk metrics into a whole-share allocation plan.

Honesty notes:
- Expected returns are proxies mapped from live sentiment
  (mu = 4% + 12% * sentiment); volatilities blend base vol with
  sentiment/OFI dispersion. Projections are model estimates, not guarantees.
- Short/Hedge lines are reported as notional (no cash outlay); only LONG
  cost must fit inside the cash budget.
"""
from __future__ import annotations
from typing import List, Dict, Any

from app.quantum_hft.qaoa_optimizer import quantum_portfolio_optimize
from app.agents.betting_engine import build_signal

RISK_PROFILES = ("aggressive", "balanced", "hft-arb")
RISK_ALIASES = {"conservative": "balanced", "moderate": "balanced",
                "high-frequency": "hft-arb", "arb": "hft-arb"}
HEDGE_PCT = {"aggressive": 0.10, "balanced": 0.20, "hft-arb": 0.50}


def _cov_matrix(vols: List[float], corr: float = 0.3) -> List[List[float]]:
    n = len(vols)
    return [
        [(vols[i] ** 2 if i == j else corr * vols[i] * vols[j]) for j in range(n)]
        for i in range(n)
    ]


def allocate(budget: float, risk_profile: str,
             rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    rows: [{symbol, price, sentiment, ofi_norm, bullish_pct}]
    Returns whole-share plan with LONG cost <= budget.
    Raises ValueError on bad input.
    """
    if not isinstance(budget, (int, float)) or budget <= 0:
        raise ValueError("budget must be > 0")
    risk_profile = RISK_ALIASES.get(str(risk_profile or "balanced").lower(),
                                      str(risk_profile or "balanced").lower())
    if risk_profile not in RISK_PROFILES:
        raise ValueError(f"risk_profile must be one of {RISK_PROFILES}")
    clean = [r for r in rows
             if r.get("symbol") and (r.get("price") or 0) > 0]
    if not clean:
        raise ValueError("no priced tickers to allocate")

    n = len(clean)
    sentiments = [float(r.get("sentiment", 0) or 0) for r in clean]
    ofis = [float(r.get("ofi_norm", 0) or 0) for r in clean]
    bulls = [float(r.get("bullish_pct", 50) or 50) for r in clean]
    prices = [float(r["price"]) for r in clean]
    symbols = [str(r["symbol"]) for r in clean]

    # Sentiment-momentum return/vol proxies (annualized).
    mus = [0.04 + 0.12 * s for s in sentiments]
    vols = [0.20 + 0.10 * abs(s) + 0.05 * abs(o)
            for s, o in zip(sentiments, ofis)]
    opt = quantum_portfolio_optimize(mus, _cov_matrix(vols), risk_aversion=1.0)
    weights = list(opt.get("weights", []))
    if len(weights) != n or sum(weights) <= 0:
        weights = [1.0 / n] * n
    tot = sum(weights)
    weights = [w / tot for w in weights]

    # Risk-profile shaping.
    if risk_profile == "aggressive":
        sharp = [w ** 1.5 for w in weights]
        s = sum(sharp) or 1.0
        weights = [w / s for w in sharp]

    # Direction per ticker from the contrarian engine.
    infos = [build_signal(symbols[i], bulls[i], sentiments[i], ofis[i],
                          quantum_edge=0.0, price=prices[i])
             for i in range(n)]

    hedge_pct = HEDGE_PCT[risk_profile]
    if risk_profile == "hft-arb":
        # Market-neutral: top-3 scores LONG, bottom-2 SHORT (notional).
        # Ranks are disjoint by construction so a symbol is never both.
        scores = sorted(range(n),
                        key=lambda i: sentiments[i] + ofis[i] + weights[i])
        n_long = min(3, max(1, n // 2))
        n_short = min(2, n - n_long)
        long_idx = scores[n - n_long:][::-1]
        short_idx = scores[:n_short]
    else:
        long_idx = [i for i in range(n) if infos[i]["direction"] == "LONG"]
        if not long_idx:  # fallback: top weights LONG so plan is never empty
            long_idx = sorted(range(n), key=lambda i: weights[i],
                              reverse=True)[: max(1, min(3, n))]
        short_idx = [i for i in range(n)
                     if infos[i]["direction"] == "SHORT" and i not in long_idx]

    long_budget = budget * (1 - hedge_pct)
    short_notional = budget * hedge_pct
    lw = sum(weights[i] for i in long_idx) or 1.0

    lines: List[Dict[str, Any]] = []
    long_cost = 0.0
    for i in long_idx:
        alloc = long_budget * weights[i] / lw
        shares = int(alloc // prices[i])
        cost = round(shares * prices[i], 2)
        long_cost += cost
        lines.append({
            "symbol": symbols[i], "direction": "LONG",
            "type": infos[i]["type"], "shares": shares,
            "price": round(prices[i], 2), "cost": cost,
            "weight": round(weights[i] / lw * (1 - hedge_pct), 4),
            "target": infos[i]["target"], "rationale": infos[i]["rationale"],
        })
    sw = sum(weights[i] for i in short_idx) or 1.0
    short_total = 0.0
    for i in short_idx:
        notional = round(short_notional * weights[i] / sw, 2)
        short_total += notional
        lines.append({
            "symbol": symbols[i], "direction": "SHORT",
            "type": infos[i]["type"],
            "shares": int(notional // prices[i]),
            "price": round(prices[i], 2), "cost": 0.0,
            "notional": notional,
            "weight": round(-weights[i] / sw * hedge_pct, 4),
            "target": infos[i]["target"], "rationale": infos[i]["rationale"],
        })

    leftover = round(budget - long_cost, 2)
    # Projections as fractions of budget (longs +, shorts -).
    exp_ret = 0.0
    for ln in lines:
        mu = mus[symbols.index(ln["symbol"])]
        frac = (ln["cost"] if ln["direction"] == "LONG" else ln["notional"]) / budget
        exp_ret += frac * mu if ln["direction"] == "LONG" else -frac * mu
    wvec = [ln["weight"] for ln in lines]
    cov = _cov_matrix(vols)
    # Map line weights back to full n-vector for vol math.
    full = [0.0] * n
    for ln in lines:
        full[symbols.index(ln["symbol"])] += ln["weight"]
    var = sum(full[i] * full[j] * cov[i][j] for i in range(n) for j in range(n))
    vol = max(0.0, var) ** 0.5

    return {
        "budget": round(float(budget), 2),
        "risk_profile": risk_profile,
        "method": opt.get("method", "unknown"),
        "lines": lines,
        "long_cost": round(long_cost, 2),
        "short_notional": round(short_total, 2),
        "leftover_cash": leftover,
        "invested_pct": round(long_cost / budget * 100, 2),
        "projected_return_pct": round(exp_ret * 100, 2),
        "estimated_vol_pct": round(vol * 100, 2),
        "estimated_drawdown_pct": round(vol * 1.5 * 100, 2),
    }
