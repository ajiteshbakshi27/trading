"""
QuantPulse AI - Backtesting Engine
Compares Quantum/HFT vs Sentiment vs Buy&Hold on synthetic or CSV price paths.
"""
from __future__ import annotations
from typing import List, Dict, Callable
import numpy as np


def _metrics(equity: np.ndarray) -> Dict:
    rets = np.diff(equity) / (equity[:-1] + 1e-9)
    if len(rets) == 0:
        return {"return_pct": 0, "sharpe": 0, "max_dd_pct": 0, "final": float(equity[-1])}
    sharpe = float(rets.mean() / (rets.std() + 1e-9) * np.sqrt(252))
    peak = np.maximum.accumulate(equity)
    dd = float(((equity - peak) / (peak + 1e-9)).min() * 100)
    tot = float((equity[-1] / equity[0] - 1) * 100)
    return {"return_pct": round(tot, 2), "sharpe": round(sharpe, 3),
            "max_dd_pct": round(dd, 2), "final": round(float(equity[-1]), 2)}


def gen_price_path(s0: float = 100, n: int = 252, mu: float = 0.0004,
                   sigma: float = 0.02, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sigma, n)
    return s0 * np.cumprod(1 + rets)


def run_backtest(prices: List[float], initial: float = 100000.0,
                 commission: float = 0.001, include_series: bool = False,
                 max_points: int = 160) -> Dict:
    p = np.array(prices, dtype=float)
    n = len(p)
    # Strategy 1: HFT/Quantum momentum (5/20 MA cross)
    # Strategy 2: Sentiment-contrarian proxy (RSI fade)
    # Strategy 3: Buy & Hold
    def ma(x, w):
        # Trailing-window mean: only divides by the window where full data exists,
        # by the running count at the warm-up edge (np.convolve 'same' would
        # divide by w everywhere and corrupt the first w//2 points).
        c = np.cumsum(np.insert(np.asarray(x, dtype=float), 0, 0.0))
        idx = np.arange(len(x))
        lo = np.maximum(0, idx - w + 1)
        return (c[idx + 1] - c[lo]) / (idx - lo + 1)

    ma5, ma20 = ma(p, 5), ma(p, 20)
    sig_hft = np.where(ma5 > ma20, 1.0, -0.5)  # long/short-lite

    # RSI(14) fade: buy oversold, sell overbought
    delta = np.diff(p, prepend=p[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    ag = ma(gain, 14) + 1e-9; al = ma(loss, 14) + 1e-9
    rsi = 100 - 100 / (1 + ag / al)
    sig_sent = np.where(rsi < 30, 1.0, np.where(rsi > 70, -1.0, 0.0))

    results = {}
    series = {}
    for name, sig in (("hft_quantum", sig_hft), ("sentiment_contrarian", sig_sent)):
        eq = [initial]; pos = 0.0
        for i in range(1, n):
            target = sig[i] * 0.9  # 90% exposure max
            trade_frac = target - pos
            cost = abs(trade_frac) * eq[-1] * commission
            ret = pos * (p[i] / p[i-1] - 1)
            eq.append(eq[-1] * (1 + ret) - cost)
            pos = target
        results[name] = _metrics(np.array(eq))
        if include_series:
            series[name] = _downsample(eq, max_points)

    bh = initial * p / p[0]
    results["buy_hold"] = _metrics(bh)
    winner = max(results, key=lambda k: results[k]["sharpe"])
    out = {"strategies": results, "winner": winner, "periods": n}
    if include_series:
        series["buy_hold"] = _downsample(bh.tolist(), max_points)
        out["series"] = series
    return out


def _downsample(eq, max_points: int) -> List[float]:
    eq = [round(float(x), 2) for x in eq]
    if len(eq) <= max_points:
        return eq
    step = len(eq) / max_points
    return [eq[int(i * step)] for i in range(max_points)]
