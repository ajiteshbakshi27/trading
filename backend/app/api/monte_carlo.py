"""
QuantPulse AI — Monte Carlo VaR API.

    GET /api/monte-carlo/var?symbol=NVDA&days=1&confidence=0.95&sims=10000

Simulates thousands of price paths using Geometric Brownian Motion and
reports Value at Risk (VaR) and Expected Shortfall (CVaR) at the requested
confidence level and horizon.

This is a *simulation*, not a prediction. It answers: "If the future looks
like the past, how much could I lose with X% confidence?"
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.services import monte_carlo

router = APIRouter(prefix="/api/monte-carlo", tags=["monte-carlo"])


@router.get("/var")
def var(
    symbol: str = "NVDA",
    days: int = Query(default=1, ge=1, le=30),
    confidence: float = Query(default=0.95, ge=0.80, le=0.999),
    sims: int = Query(default=10_000, ge=1_000, le=50_000),
):
    result = monte_carlo.run(
        symbol.upper(), days=days, confidence=confidence, n_sims=sims
    )
    return {
        "result": result,
        "data_mode": result["data_mode"],
        "note": ("Monte Carlo simulation assuming GBM. Past volatility does "
                 "not guarantee future risk. This is not a prediction."),
    }
