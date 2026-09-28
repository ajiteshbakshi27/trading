"""
QuantPulse AI — Monte Carlo VaR API.

    GET /api/monte-carlo/var?symbol=NVDA&days=1&confidence=0.95&sims=10000

Returns simulated VaR, Expected Shortfall, and a distribution histogram.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import monte_carlo

router = APIRouter(prefix="/api/monte-carlo", tags=["monte-carlo"])


@router.get("/var")
def var(
    symbol: str = "NVDA",
    days: int = Query(default=1, ge=1, le=30),
    confidence: float = Query(default=0.95, ge=0.80, le=0.999),
    sims: int = Query(default=10_000, ge=1_000, le=50_000),
):
    result = monte_carlo.run(symbol.upper(), days=days,
                             confidence=confidence, n_sims=sims)
    return {
        "result": result,
        "status": result["status"],
        "label": result.get("label", ""),
        "data_mode": result["data_mode"],
        **mode_block(DataMode(result["data_mode"])),
    }
