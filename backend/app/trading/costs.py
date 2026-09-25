"""
QuantPulse AI - Fee / Slippage / Tax pre-trade estimator.
Flat, currency-agnostic model (rates from Settings):
  fee      = max(FEE_MIN, notional * FEE_RATE)
  slippage = notional * spread_bps/1e4 * 0.5   (crossing half the spread)
  tax      = TAX_RATE_GAINS * max(projected_profit, 0)  (estimate only)
All estimates; never blocks execution.
"""
from __future__ import annotations
from typing import Dict


def estimate_costs(notional: float, spread_bps: float = 5.0,
                   projected_profit: float = 0.0,
                   fee_rate: float = 0.0005, fee_min: float = 1.0,
                   tax_rate: float = 0.15) -> Dict[str, float]:
    notional = max(0.0, float(notional or 0))
    fee = max(fee_min, notional * fee_rate) if notional > 0 else 0.0
    slippage = notional * max(0.0, spread_bps) / 1e4 * 0.5
    tax = tax_rate * max(0.0, float(projected_profit or 0))
    total = fee + slippage + tax
    net_profit = float(projected_profit or 0) - total
    return {
        "notional": round(notional, 2),
        "fee": round(fee, 2),
        "slippage": round(slippage, 2),
        "est_tax_on_profit": round(tax, 2),
        "total_cost": round(total, 2),
        "net_projected_profit": round(net_profit, 2),
    }
