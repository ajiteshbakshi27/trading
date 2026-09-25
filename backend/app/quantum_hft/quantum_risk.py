"""
QuantPulse AI - Risk Metrics (Sharpe, Sortino, VaR, CVaR)
Classical computation + quantum-VaR placeholder via Monte Carlo.
"""
from __future__ import annotations
from typing import List, Dict
import numpy as np


def _to_arr(returns: List[float]) -> np.ndarray:
    return np.array(returns, dtype=float)


def sharpe_ratio(returns: List[float], rf: float = 0.0, periods: int = 252) -> float:
    r = _to_arr(returns) - rf / periods
    if r.std() == 0 or len(r) == 0:
        return 0.0
    return float(r.mean() / r.std() * np.sqrt(periods))


def sortino_ratio(returns: List[float], rf: float = 0.0, periods: int = 252) -> float:
    r = _to_arr(returns) - rf / periods
    downside = r[r < 0]
    dd = downside.std() if len(downside) > 1 else 0.0
    if dd == 0 or len(r) == 0:
        return 0.0
    return float(r.mean() / dd * np.sqrt(periods))


def value_at_risk(returns: List[float], confidence: float = 0.95) -> Dict:
    """Historical VaR (loss positive number)."""
    r = _to_arr(returns)
    if len(r) == 0:
        return {"var": 0.0, "cvar": 0.0, "confidence": confidence}
    alpha = 1 - confidence
    var = float(-np.quantile(r, alpha))
    tail = r[r <= -var] if (r <= -var).any() else r[:1]
    cvar = float(-tail.mean())
    return {"var": round(var, 6), "cvar": round(cvar, 6), "confidence": confidence}


def quantum_var_proxy(returns: List[float], confidence: float = 0.95,
                      n_sim: int = 20000, seed: int = 7) -> Dict:
    """
    Quantum Amplitude Estimation placeholder: fit Gaussian to returns,
    Monte-Carlo sample (QAE would give quadratic speedup), report VaR/CVaR.
    """
    r = _to_arr(returns)
    if len(r) < 2:
        return {**value_at_risk(returns, confidence), "method": "historical_fallback"}
    rng = np.random.default_rng(seed)
    sims = rng.normal(r.mean(), r.std() + 1e-9, n_sim)
    alpha = 1 - confidence
    var = float(-np.quantile(sims, alpha))
    cvar = float(-sims[sims <= -var].mean())
    return {"var": round(var, 6), "cvar": round(cvar, 6),
            "confidence": confidence, "method": "qae_monte_carlo_proxy", "n_sim": n_sim}


def max_drawdown(returns: List[float]) -> float:
    """Peak-to-trough drawdown of the compounded equity curve (positive fraction)."""
    r = _to_arr(returns)
    if len(r) < 2:
        return 0.0
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    return float(np.max((peak - equity) / peak))


def risk_report(returns: List[float]) -> Dict:
    v = value_at_risk(returns)
    qv = quantum_var_proxy(returns)
    return {
        "sharpe": round(sharpe_ratio(returns), 4),
        "sortino": round(sortino_ratio(returns), 4),
        "volatility_ann": round(float(_to_arr(returns).std() * np.sqrt(252)), 6) if returns else 0.0,
        "max_drawdown": round(max_drawdown(returns), 6),
        "var_95": v["var"], "cvar_95": v["cvar"],
        "quantum_var_95": qv["var"], "quantum_cvar_95": qv["cvar"],
    }
