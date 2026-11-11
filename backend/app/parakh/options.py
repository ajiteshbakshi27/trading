"""
Parakh — Feature 9: F&O analytics for Indian index/stock options.

Black-Scholes (European; NSE index options are European-style) prices and
greeks, implied volatility, multi-leg payoff at expiry, breakevens, max
profit/loss, and probability of profit under a lognormal model at the
legs' implied volatility.

Lot sizes change by NSE circular — the defaults below are a convenience and
the UI tells users to confirm the current lot size.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from scipy.optimize import brentq
from scipy.stats import norm

RISK_FREE = 0.065  # approx. Indian 91-day T-bill yield; editable per request
DEFAULT_LOTS = {"NIFTY": 75, "BANKNIFTY": 35, "FINNIFTY": 65, "MIDCPNIFTY": 140, "SENSEX": 20}


def bs_price(spot: float, strike: float, t: float, vol: float, kind: str, r: float = RISK_FREE) -> float:
    if t <= 0 or vol <= 0:
        return max(0.0, spot - strike) if kind == "CE" else max(0.0, strike - spot)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if kind == "CE":
        return float(spot * norm.cdf(d1) - strike * math.exp(-r * t) * norm.cdf(d2))
    return float(strike * math.exp(-r * t) * norm.cdf(-d2) - spot * norm.cdf(-d1))


def greeks(spot: float, strike: float, t: float, vol: float, kind: str, r: float = RISK_FREE) -> Dict[str, float]:
    t = max(t, 1e-6)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    pdf = norm.pdf(d1)
    if kind == "CE":
        delta = norm.cdf(d1)
        theta = (-spot * pdf * vol / (2 * math.sqrt(t)) - r * strike * math.exp(-r * t) * norm.cdf(d2)) / 365
    else:
        delta = norm.cdf(d1) - 1
        theta = (-spot * pdf * vol / (2 * math.sqrt(t)) + r * strike * math.exp(-r * t) * norm.cdf(-d2)) / 365
    return {"delta": round(float(delta), 4), "gamma": round(float(pdf / (spot * vol * math.sqrt(t))), 6),
            "theta_per_day": round(float(theta), 3), "vega_per_1pct": round(float(spot * pdf * math.sqrt(t) / 100), 3)}


def implied_vol(price: float, spot: float, strike: float, t: float, kind: str, r: float = RISK_FREE) -> Optional[float]:
    intrinsic = max(0.0, spot - strike) if kind == "CE" else max(0.0, strike - spot)
    if price <= intrinsic or t <= 0:
        return None
    try:
        return round(float(brentq(lambda v: bs_price(spot, strike, t, v, kind, r) - price, 1e-4, 5.0, xtol=1e-6)), 4)
    except ValueError:
        return None


def analyse(spot: float, days_to_expiry: float, legs: List[Dict[str, Any]],
            lot_size: int = 1, r: float = RISK_FREE, iv_default: float = 0.15) -> Dict[str, Any]:
    """legs: [{kind: CE|PE|FUT, side: BUY|SELL, strike, premium, lots, iv?}]"""
    if spot <= 0:
        raise ValueError("spot must be positive")
    if not legs:
        raise ValueError("add at least one leg")
    t = max(days_to_expiry, 0.0) / 365.0
    enriched, net_premium = [], 0.0
    net = {"delta": 0.0, "gamma": 0.0, "theta_per_day": 0.0, "vega_per_1pct": 0.0}
    ivs = []
    for leg in legs:
        kind = str(leg.get("kind", "CE")).upper()
        side = 1 if str(leg.get("side", "BUY")).upper() == "BUY" else -1
        lots = int(leg.get("lots", 1) or 1)
        qty = side * lots * lot_size
        strike = float(leg.get("strike") or spot)
        prem = float(leg.get("premium") or 0)
        e = {**leg, "kind": kind, "qty": qty, "strike": strike}
        if kind == "FUT":
            prem = prem or spot
            e["premium"] = prem
            net["delta"] += qty
        else:
            iv = leg.get("iv")
            iv = float(iv) if iv else (implied_vol(prem, spot, strike, t, kind, r) if prem else None)
            iv = iv or iv_default
            ivs.append(iv)
            if not prem:
                prem = round(bs_price(spot, strike, t, iv, kind, r), 2)
            g = greeks(spot, strike, t, iv, kind, r)
            for k in net:
                net[k] += g[k] * qty
            e.update({"premium": prem, "iv": round(iv, 4), "greeks": g})
            net_premium += -qty * prem    # +credit / -debit
        enriched.append(e)

    def payoff(s: float) -> float:
        total = 0.0
        for e in enriched:
            if e["kind"] == "FUT":
                total += e["qty"] * (s - e["premium"])
            elif e["kind"] == "CE":
                total += e["qty"] * (max(0.0, s - e["strike"]) - e["premium"])
            else:
                total += e["qty"] * (max(0.0, e["strike"] - s) - e["premium"])
        return total

    lo, hi = spot * 0.7, spot * 1.3
    steps = 240
    grid = [lo + (hi - lo) * i / steps for i in range(steps + 1)]
    curve = [{"spot": round(s, 2), "pnl": round(payoff(s), 2)} for s in grid]
    pnls = [c["pnl"] for c in curve]
    breakevens = []
    for a, b in zip(curve, curve[1:]):
        if (a["pnl"] <= 0 < b["pnl"]) or (a["pnl"] >= 0 > b["pnl"]):
            x = a["spot"] + (b["spot"] - a["spot"]) * (-a["pnl"]) / ((b["pnl"] - a["pnl"]) or 1e-9)
            breakevens.append(round(x, 2))
    # unbounded if payoff still sloping at the grid edge
    slope_hi = payoff(hi * 1.5) - payoff(hi)
    slope_lo = payoff(lo * 0.5) - payoff(lo)
    max_profit = None if slope_hi > 1e-6 or slope_lo > 1e-6 else round(max(pnls), 2)
    max_loss = None if slope_hi < -1e-6 or slope_lo < -1e-6 else round(min(pnls), 2)
    # probability of profit at expiry: lognormal with the average leg IV
    sigma = (sum(ivs) / len(ivs)) if ivs else iv_default
    pop = 0.0
    if t > 0:
        mu = math.log(spot) + (r - 0.5 * sigma * sigma) * t
        sd = sigma * math.sqrt(t)
        n = 2000
        for i in range(n):
            z = norm.ppf((i + 0.5) / n)
            if payoff(math.exp(mu + sd * z)) > 0:
                pop += 1
        pop /= n
    else:
        pop = 1.0 if payoff(spot) > 0 else 0.0
    one_sd = spot * sigma * math.sqrt(max(t, 1 / 365))
    warnings = []
    if max_loss is None:
        warnings.append("Unlimited loss: at least one side of this position has no cap. Brokers will block large margin; a gap can wipe out far more than the premium.")
    if any(e["kind"] != "FUT" and e["qty"] < 0 for e in enriched) and days_to_expiry < 2:
        warnings.append("Short options into expiry: gamma is extreme; small index moves swing P&L sharply.")
    if pop > 0.75 and (max_loss is None or (max_profit and abs(max_loss) > 3 * max_profit)):
        warnings.append("High win-probability but the losses are much bigger than the gains — the expected value can still be negative.")
    return {
        "spot": spot, "days_to_expiry": days_to_expiry, "lot_size": lot_size,
        "legs": enriched, "net_premium": round(net_premium, 2),
        "position_type": "credit" if net_premium > 0 else "debit",
        "net_greeks": {k: round(v, 4) for k, v in net.items()},
        "breakevens": breakevens, "max_profit": max_profit, "max_loss": max_loss,
        "probability_of_profit": round(pop, 3), "expected_move_1sd": round(one_sd, 2),
        "payoff": curve, "warnings": warnings,
        "assumptions": f"Black-Scholes, r={r:.1%}, lognormal at average IV {sigma:.1%}. "
                       "Ignores brokerage, STT and early assignment. Confirm current NSE lot size.",
    }
