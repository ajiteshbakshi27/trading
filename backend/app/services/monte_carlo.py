"""
QuantPulse AI — Monte Carlo VaR Engine.

Simulates thousands of price paths using Geometric Brownian Motion and
computes Value at Risk (VaR) and Expected Shortfall (CVaR) at configurable
confidence levels.

This is a *simulation*, not a prediction. It answers: "If the future looks
like the past, how much could I lose with 95%/99% confidence?"
"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Dict, List, Optional

from app.models.common import clamp
from app.models.enums import DataMode

#: Annual trading days (NSE/BSE convention)
TRADING_DAYS = 252


def _estimate_params(prices: List[float]) -> Dict[str, float]:
    """Estimate mu (drift) and sigma (vol) from a price series."""
    if len(prices) < 2:
        return {"mu": 0.0, "sigma": 0.02}
    rets = [(prices[i] / prices[i - 1]) - 1.0
            for i in range(1, len(prices)) if prices[i - 1] > 0]
    if not rets:
        return {"mu": 0.0, "sigma": 0.02}
    mu = sum(rets) / len(rets)
    var = sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)
    sigma = math.sqrt(var)
    return {"mu": mu, "sigma": max(sigma, 1e-6)}


def _simulate_paths(
    spot: float,
    mu: float,
    sigma: float,
    days: int,
    n_sims: int,
    seed: int = 42,
) -> List[List[float]]:
    """Generate n_sims GBM price paths of length days."""
    rng = random.Random(seed)
    paths: List[List[float]] = []
    dt = 1.0 / TRADING_DAYS
    drift = (mu - 0.5 * sigma * sigma) * dt
    vol = sigma * math.sqrt(dt)
    for _ in range(n_sims):
        path = [spot]
        for _ in range(days):
            z = rng.gauss(0.0, 1.0)
            path.append(path[-1] * math.exp(drift + vol * z))
        paths.append(path)
    return paths


def _percentile(sorted_vals: List[float], p: float) -> float:
    """Linear-interpolated percentile."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def compute_var(
    prices: List[float],
    days: int = 1,
    confidence: float = 0.95,
    n_sims: int = 10_000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Monte Carlo VaR for a single symbol.

    Returns VaR, CVaR, distribution histogram, and the simulated terminal
    prices so the frontend can render the full picture.
    """
    if not prices or len(prices) < 5:
        return {
            "status": "insufficient_data",
            "label": "INSUFFICIENT DATA",
            "note": "Need at least 5 price points for a meaningful simulation.",
            "n_sims": 0,
        }

    spot = prices[-1]
    params = _estimate_params(prices)
    mu = params["mu"]
    sigma = params["sigma"]

    paths = _simulate_paths(spot, mu, sigma, days, n_sims, seed)
    terminal = [p[-1] for p in paths]
    returns = [(t / spot - 1.0) * 100.0 for t in terminal]
    returns_sorted = sorted(returns)

    var_pct = _percentile(returns_sorted, 1.0 - confidence)
    cvar_pct = (sum(r for r in returns_sorted if r <= var_pct)
                / max(1, sum(1 for r in returns_sorted if r <= var_pct)))

    # Histogram (20 bins)
    lo, hi = returns_sorted[0], returns_sorted[-1]
    if hi - lo < 1e-9:
        hi = lo + 1.0
    n_bins = 20
    bin_width = (hi - lo) / n_bins
    bins = [0] * n_bins
    for r in returns:
        idx = min(n_bins - 1, int((r - lo) / bin_width))
        bins[idx] += 1
    histogram = [
        {"bin_start": round(lo + i * bin_width, 3),
         "bin_end": round(lo + (i + 1) * bin_width, 3),
         "count": bins[i]}
        for i in range(n_bins)
    ]

    return {
        "status": "ok",
        "label": "",
        "spot": round(spot, 4),
        "days": days,
        "confidence": confidence,
        "n_sims": n_sims,
        "mu_daily": round(mu, 6),
        "sigma_daily": round(sigma, 6),
        "var_pct": round(var_pct, 4),
        "var_amount": round(spot * var_pct / 100.0, 4),
        "cvar_pct": round(cvar_pct, 4),
        "cvar_amount": round(spot * cvar_pct / 100.0, 4),
        "max_loss_pct": round(returns_sorted[0], 4),
        "max_gain_pct": round(returns_sorted[-1], 4),
        "histogram": histogram,
        "terminal_prices": [round(t, 4) for t in terminal[:500]],
        "data_mode": DataMode.MOCK.value,
        "note": ("Monte Carlo simulation assuming GBM. Past volatility does "
                 "not guarantee future risk. This is not a prediction."),
    }


def run(
    symbol: str,
    days: int = 1,
    confidence: float = 0.95,
    n_sims: int = 10_000,
) -> Dict[str, Any]:
    """Fetch history and run Monte Carlo VaR for one symbol."""
    from app.services import feed_layer

    closes: List[float] = []
    mode = DataMode.MOCK
    frame, price_mode = feed_layer.get_history(symbol, period="1y")
    if frame is not None and len(frame) >= 5:
        try:
            closes = [float(v) for v in frame["Close"].values if v and v > 0]
            mode = price_mode
        except Exception:
            closes = []

    if not closes:
        # Deterministic fallback so the endpoint never 500s
        closes = [100.0, 101.2, 99.8, 102.1, 100.5, 103.0, 101.8]

    result = compute_var(closes, days=days, confidence=confidence,
                         n_sims=n_sims)
    result["symbol"] = symbol.upper()
    result["data_mode"] = mode.value
    return result
