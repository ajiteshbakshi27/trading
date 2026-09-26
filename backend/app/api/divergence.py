"""
QuantPulse AI — Divergence API (Smart Money vs Ape Money).

    GET /api/divergence              full scan across the universe
    GET /api/divergence/{symbol}     one symbol's divergence snapshot

Every response carries data_mode and a note that divergence is a comparison,
not a prediction.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import divergence_engine

router = APIRouter(prefix="/api/divergence", tags=["divergence"])


@router.get("")
def scan(symbols: Optional[str] = None, limit: int = Query(default=20, ge=1, le=50)):
    syms = ([s.strip().upper() for s in symbols.split(",") if s.strip()]
            if symbols else None)
    results = divergence_engine.scan(universe=syms, limit=limit)
    return {
        "results": results,
        "count": len(results),
        "data_mode": DataMode.MOCK.value,
        "note": ("Divergence compares retail sentiment with market price action. "
                 "It is not a prediction and does not establish causation."),
        **mode_block(DataMode.MOCK),
    }


@router.get("/{symbol}")
def get_divergence(symbol: str):
    result = divergence_engine.compute_divergence(symbol.upper())
    return {
        "result": result,
        "data_mode": result["data_mode"],
        **mode_block(DataMode(result["data_mode"])),
    }
