"""
QuantPulse AI - Portfolio Automated Rebalancer.
Compares current holdings vs target VQE/quantum weights and emits
whole-share buy/sell orders to close the drift.
"""
from __future__ import annotations
from typing import Dict, List, Any


def rebalance_orders(holdings: Dict[str, float], prices: Dict[str, float],
                     target_weights: Dict[str, float],
                     total_value: float | None = None) -> Dict[str, Any]:
    """
    holdings: {symbol: shares} (shares may be fractional).
    prices: {symbol: price}. Symbols missing prices are skipped.
    target_weights: {symbol: weight} (renormalized over priced symbols).
    Returns drift report + whole-share orders (positive qty = buy).
    Raises ValueError on bad input.
    """
    if not holdings:
        raise ValueError("holdings must not be empty")
    priced = {s: float(prices[s]) for s in holdings if (prices.get(s) or 0) > 0}
    if not priced:
        raise ValueError("no priced holdings")
    if total_value is None:
        total_value = sum(float(holdings[s]) * priced[s] for s in priced)
    if total_value <= 0:
        raise ValueError("portfolio value must be > 0")
    tw = {s: max(0.0, float(target_weights.get(s, 0))) for s in priced}
    # Keep explicit zero targets (full exit); renormalize positive mass.
    pos = sum(tw.values())
    orders: List[Dict[str, Any]] = []
    drifts: List[Dict[str, Any]] = []
    for s in priced:
        cur_w = holdings[s] * priced[s] / total_value
        tgt_w = (tw[s] / pos) if pos > 0 else 0.0
        drift = tgt_w - cur_w
        d_shares = drift * total_value / priced[s]
        qty = int(d_shares) if abs(d_shares) >= 1 else 0
        drifts.append({"symbol": s, "current_w": round(cur_w, 4),
                       "target_w": round(tgt_w, 4), "drift": round(drift, 4)})
        if qty != 0:
            orders.append({"symbol": s, "qty": abs(qty),
                           "side": "buy" if qty > 0 else "sell",
                           "notional": round(abs(qty) * priced[s], 2)})
    drifts.sort(key=lambda d: abs(d["drift"]), reverse=True)
    return {"total_value": round(total_value, 2), "drifts": drifts,
            "orders": orders, "n_orders": len(orders)}
