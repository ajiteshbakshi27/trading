"""
Parakh — Feature 10: no-code strategy backtests on real daily NSE data,
with the honesty checks most retail backtesters skip.

Rules
  * signals are computed on day t's close and filled at day t+1's OPEN
    (no look-ahead),
  * Indian delivery costs are charged on every fill (configurable),
  * results are split in-sample (first 70%) / out-of-sample (last 30%),
  * parameters are nudged ±20% to test sensitivity,
  * warnings fire for: too few trades, too-good Sharpe / win-rate,
    in-vs-out-of-sample collapse, parameter fragility, survivorship bias,
    simulated data.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from app.parakh import market

# Approx. round-trip delivery cost on NSE: STT 0.1% each side + exchange,
# SEBI, stamp duty (buy) and GST. ~0.25% total; users can edit.
DEFAULT_COST_PCT = 0.25

ENTRY_RULES = {
    "sma_cross_up": "Fast SMA crosses above slow SMA",
    "rsi_below": "RSI(14) drops below a level (buy the dip)",
    "breakout": "Close above the highest close of the last N days",
    "price_above_sma": "Close crosses above an SMA",
}
EXIT_RULES = {"stop_pct", "target_pct", "max_hold_days", "sma_cross_down", "rsi_above"}


def _sma_series(cl: List[float], n: int) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(cl)
    s = 0.0
    for i, c in enumerate(cl):
        s += c
        if i >= n:
            s -= cl[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def _rsi_series(cl: List[float], n: int = 14) -> List[Optional[float]]:
    out: List[Optional[float]] = [None] * len(cl)
    for i in range(n, len(cl)):
        out[i] = market.rsi(cl[: i + 1], n)
    return out


def _entry_fn(rule: str, p: Dict[str, float], cl: List[float]) -> Callable[[int], bool]:
    if rule == "sma_cross_up":
        f, s = _sma_series(cl, int(p.get("fast", 20))), _sma_series(cl, int(p.get("slow", 50)))
        return lambda i: (i > 0 and None not in (f[i], s[i], f[i - 1], s[i - 1])
                          and f[i - 1] <= s[i - 1] and f[i] > s[i])
    if rule == "rsi_below":
        r, lvl = _rsi_series(cl), float(p.get("level", 30))
        return lambda i: i > 0 and r[i] is not None and r[i - 1] is not None and r[i - 1] >= lvl > r[i]
    if rule == "breakout":
        n = int(p.get("lookback", 55))
        return lambda i: i > n and cl[i] > max(cl[i - n:i])
    if rule == "price_above_sma":
        s = _sma_series(cl, int(p.get("period", 50)))
        return lambda i: i > 0 and s[i] is not None and s[i - 1] is not None and cl[i - 1] <= s[i - 1] and cl[i] > s[i]
    raise ValueError(f"Unknown entry rule {rule!r}. Choose from: {', '.join(ENTRY_RULES)}")


def simulate(bars: List[market.Bar], entry_rule: str, entry_params: Dict[str, float],
             exit_params: Dict[str, float], cost_pct: float = DEFAULT_COST_PCT,
             start: int = 0, end: Optional[int] = None) -> Dict[str, Any]:
    cl = market.closes(bars)
    end = end or len(bars)
    want = _entry_fn(entry_rule, entry_params, cl)
    stop = float(exit_params.get("stop_pct", 0) or 0) / 100
    target = float(exit_params.get("target_pct", 0) or 0) / 100
    max_hold = int(exit_params.get("max_hold_days", 0) or 0)
    sma_exit = _sma_series(cl, int(exit_params.get("sma_exit", 0))) if exit_params.get("sma_exit") else None
    rsi_exit_lvl = exit_params.get("rsi_above")
    rsi_s = _rsi_series(cl) if rsi_exit_lvl else None
    trades: List[Dict[str, Any]] = []
    equity, curve = 1.0, []
    i = max(start, 1)
    pos = None
    while i < end - 1:
        if pos is None:
            if want(i):
                px = bars[i + 1]["open"]                     # fill next open
                pos = {"entry_i": i + 1, "entry": px}
                i += 1
                continue
        else:
            b = bars[i]
            exit_px, reason = None, ""
            if stop and b["low"] <= pos["entry"] * (1 - stop):
                exit_px, reason = min(b["open"], pos["entry"] * (1 - stop)), "stop"
            elif target and b["high"] >= pos["entry"] * (1 + target):
                exit_px, reason = max(b["open"], pos["entry"] * (1 + target)), "target"
            elif max_hold and i - pos["entry_i"] >= max_hold:
                exit_px, reason = bars[i + 1]["open"], "time"
            elif sma_exit and sma_exit[i] and cl[i] < sma_exit[i]:
                exit_px, reason = bars[i + 1]["open"], "sma"
            elif rsi_s and rsi_s[i] and rsi_s[i] > float(rsi_exit_lvl):
                exit_px, reason = bars[i + 1]["open"], "rsi"
            if exit_px is not None:
                gross = exit_px / pos["entry"] - 1
                net = gross - cost_pct / 100
                equity *= 1 + net
                trades.append({"entry_date": bars[pos["entry_i"]]["date"], "exit_date": b["date"],
                               "entry": round(pos["entry"], 2), "exit": round(exit_px, 2),
                               "return_pct": round(net * 100, 2), "reason": reason,
                               "days": i - pos["entry_i"]})
                pos = None
        curve.append({"date": bars[i]["date"], "equity": round(equity, 4)})
        i += 1
    return _metrics(trades, curve, bars[start:end])


def _metrics(trades: List[Dict[str, Any]], curve: List[Dict[str, Any]],
             bars: List[market.Bar]) -> Dict[str, Any]:
    n = len(trades)
    rets = [t["return_pct"] / 100 for t in trades]
    total = (curve[-1]["equity"] - 1) if curve else 0.0
    years = max(len(bars) / 252, 1e-9)
    cagr = (1 + total) ** (1 / years) - 1 if total > -1 else -1.0
    eq = [c["equity"] for c in curve] or [1.0]
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak else 0)
    daily = [eq[k] / eq[k - 1] - 1 for k in range(1, len(eq)) if eq[k - 1]]
    sd = market.stdev(daily)
    sharpe = (sum(daily) / len(daily)) / sd * math.sqrt(252) if daily and sd else 0.0
    bh = (bars[-1]["close"] / bars[0]["close"] - 1) if len(bars) > 1 else 0.0
    return {"trades": n, "total_return_pct": round(total * 100, 2), "cagr_pct": round(cagr * 100, 2),
            "max_drawdown_pct": round(mdd * 100, 2), "sharpe": round(sharpe, 2),
            "win_rate": round(sum(r > 0 for r in rets) / n, 3) if n else None,
            "avg_trade_pct": round(sum(rets) / n * 100, 2) if n else None,
            "buy_hold_return_pct": round(bh * 100, 2),
            "trade_list": trades[-50:], "equity_curve": curve[:: max(1, len(curve) // 300)]}


def run(symbol: str, entry_rule: str, entry_params: Dict[str, float],
        exit_params: Dict[str, float], years: int = 3,
        cost_pct: float = DEFAULT_COST_PCT) -> Dict[str, Any]:
    bars, mode = market.history(symbol, min(1250, 252 * max(1, years) + 60))
    if len(bars) < 200:
        raise ValueError("Not enough price history for a meaningful backtest.")
    full = simulate(bars, entry_rule, entry_params, exit_params, cost_pct)
    split = int(len(bars) * 0.7)
    ins = simulate(bars, entry_rule, entry_params, exit_params, cost_pct, 0, split)
    oos = simulate(bars, entry_rule, entry_params, exit_params, cost_pct, split, len(bars))
    sens = []
    for f in (0.8, 1.2):
        p2 = {k: (v * f if isinstance(v, (int, float)) else v) for k, v in entry_params.items()}
        r = simulate(bars, entry_rule, p2, exit_params, cost_pct)
        sens.append({"params": {k: round(v, 2) for k, v in p2.items()},
                     "total_return_pct": r["total_return_pct"], "trades": r["trades"]})
    warnings: List[str] = []
    if mode != "live":
        warnings.append("Price data is SIMULATED (live NSE data unavailable). Results mean nothing for real trading.")
    if full["trades"] < 30:
        warnings.append(f"Only {full['trades']} trades — far too few to trust. Aim for 30+.")
    if full["sharpe"] > 2.5:
        warnings.append(f"Sharpe {full['sharpe']} is unusually high for a daily strategy — suspect overfitting or a data quirk.")
    if full["win_rate"] and full["win_rate"] > 0.8 and full["trades"] >= 10:
        warnings.append("Win rate above 80% — check that losses aren't being hidden by a wide or missing stop.")
    if ins["trades"] >= 5 and oos["trades"] >= 3 and ins["avg_trade_pct"] and oos["avg_trade_pct"] is not None:
        if ins["avg_trade_pct"] > 0 and oos["avg_trade_pct"] < ins["avg_trade_pct"] * 0.3:
            warnings.append("Performance collapses out-of-sample (last 30% of data) — classic sign of curve-fitting.")
    rets = [s["total_return_pct"] for s in sens] + [full["total_return_pct"]]
    if max(rets) - min(rets) > max(20.0, abs(full["total_return_pct"])):
        warnings.append("Small parameter changes swing results a lot — the edge is fragile.")
    if full["total_return_pct"] < full["buy_hold_return_pct"]:
        warnings.append("It did worse than simply buying and holding over the same period.")
    warnings.append("Survivorship bias: the stock list is today's large caps; companies that fell out of favour or delisted aren't tested.")
    return {"symbol": symbol, "data_mode": mode, "entry_rule": entry_rule, "entry_params": entry_params,
            "exit_params": exit_params, "cost_pct_round_trip": cost_pct, "full": full,
            "in_sample": {k: v for k, v in ins.items() if k not in ("trade_list", "equity_curve")},
            "out_of_sample": {k: v for k, v in oos.items() if k not in ("trade_list", "equity_curve")},
            "sensitivity": sens, "warnings": warnings,
            "method": "Signals on close, fills at next open; costs on every round trip; 70/30 in/out-of-sample split; ±20% parameter nudge."}
