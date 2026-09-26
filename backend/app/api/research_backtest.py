"""
QuantPulse AI — Backtest API.

    GET /api/backtest/research?symbol=NVDA&period=1y
    GET /api/backtest/research/suite?symbols=NVDA,TSLA,AAPL&period=1y

Replays the closed loop over a historical window and reports measured results.
All records are labelled BACKTEST (or MOCK when real history is unreachable).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import INSUFFICIENT_DATA, mode_block
from app.models.enums import DataMode
from app.services import research_backtest

router = APIRouter(prefix="/api/backtest", tags=["research-backtest"])


@router.get("/research")
def backtest_symbol(symbol: str = "NVDA", period: str = "1y",
                    min_resolved: int = 20):
    result = research_backtest.run_backtest(symbol.upper(), period=period,
                                            min_resolved=min_resolved)
    return {
        "result": result,
        "status": result["status"],
        "label": result.get("label", ""),
        "data_mode": result["data_mode"],
        "data_mode_label": (DataMode(result["data_mode"]).label),
        **mode_block(DataMode(result["data_mode"])),
    }


@router.get("/research/suite")
def backtest_suite(symbols: str = "NVDA,TSLA,AAPL", period: str = "1y",
                   min_resolved: int = 20):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()][:10]
    result = research_backtest.run_suite(syms, period=period,
                                         min_resolved=min_resolved)
    return {
        "suite": result,
        "status": result["status"],
        "label": result.get("label", ""),
        "data_mode": result["data_mode"],
        **mode_block(DataMode(result["data_mode"])),
    }
