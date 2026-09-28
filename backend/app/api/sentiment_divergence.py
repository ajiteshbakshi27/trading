"""
QuantPulse AI — Cross-Platform Sentiment Divergence API.

    GET /api/divergence/cross-platform?limit=12
    GET /api/divergence/cross-platform/{symbol}

Measures how much sentiment disagrees across Reddit, X and Prediction Markets.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import sentiment_divergence

router = APIRouter(prefix="/api/divergence", tags=["sentiment-divergence"])


@router.get("/cross-platform")
def cross_platform(symbols: Optional[str] = None,
                    limit: int = Query(default=12, ge=1, le=30)):
    syms = ([s.strip().upper() for s in symbols.split(",") if s.strip()]
            if symbols else None)
    results = sentiment_divergence.scan(universe=syms, limit=limit)
    return {
        "results": results,
        "count": len(results),
        "data_mode": DataMode.MOCK.value,
        "note": ("Divergence measures cross-platform sentiment spread. High "
                 "divergence means platforms disagree — one side is likely wrong."),
        **mode_block(DataMode.MOCK),
    }


@router.get("/cross-platform/{symbol}")
def cross_platform_symbol(symbol: str):
    result = sentiment_divergence.compute_divergence(symbol.upper())
    return {
        "result": result,
        "data_mode": result["data_mode"],
        **mode_block(DataMode(result["data_mode"])),
    }
