"""Stored signal/prediction history, user portfolios and trade log."""
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app import database as db
from app.core.auth import User, require_user

router = APIRouter()


class SignalLogRequest(BaseModel):
    symbol: str
    type: str = "NO_BET"
    direction: str = "FLAT"
    confidence: float = 0.0
    price: float = 0.0
    target: float = 0.0
    stop: float = 0.0
    bullish_pct: float = 50.0
    sentiment: float = 0.0
    ofi_norm: float = 0.0
    rationale: str = ""


class PortfolioRequest(BaseModel):
    name: str = ""
    budget: float = 0.0
    currency: str = "USD"
    risk_profile: str = "balanced"
    tickers: List[str] = []
    notes: str = ""


@router.get("/api/history")
def history(limit: int = Query(default=100, ge=1, le=1000),
            symbol: Optional[str] = None,
            type: Optional[str] = None):
    """Fetch stored signal history + recent prediction edges."""
    return {
        "signals": db.get_signal_history(limit=limit, symbol=symbol, signal_type=type),
        "predictions": db.get_prediction_history(limit=min(limit, 200)),
        "backend": db.engine_info().get("backend"),
    }


@router.post("/api/history")
def log_signal(req: SignalLogRequest):
    """Manually log one signal entry."""
    n = db.save_signals([req.model_dump()])
    return {"saved": n}


@router.get("/api/portfolio")
def list_portfolio(limit: int = Query(default=50, ge=1, le=200),
                   user: User = Depends(require_user)):
    """Fetch saved user portfolio inputs."""
    return {"portfolios": db.list_portfolios(limit=limit, user_id=user.id),
            "backend": db.engine_info().get("backend")}


@router.post("/api/portfolio")
def save_portfolio(req: PortfolioRequest, user: User = Depends(require_user)):
    """Save a user portfolio input (budget must be > 0)."""
    try:
        row = db.save_portfolio(req.model_dump(), user_id=user.id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"portfolio": row}


@router.get("/api/predictions/history")
def predictions_history(limit: int = Query(default=100, ge=1, le=1000)):
    """Stored prediction-market odds and edges over time."""
    return {"predictions": db.get_prediction_history(limit=limit),
            "backend": db.engine_info().get("backend")}


@router.post("/api/portfolio/save")
def save_portfolio_alias(req: PortfolioRequest, user: User = Depends(require_user)):
    """Alias of POST /api/portfolio (spec endpoint name)."""
    return save_portfolio(req, user)


@router.get("/api/trades")
def trade_history(limit: int = Query(default=100, ge=1, le=500),
                  symbol: Optional[str] = None,
                  user: User = Depends(require_user)):
    """Routed-order + kill-switch event log."""
    return {"trades": db.list_trade_executions(limit=limit, symbol=symbol, user_id=user.id),
            "backend": db.engine_info().get("backend")}
