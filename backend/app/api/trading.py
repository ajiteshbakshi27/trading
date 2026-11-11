"""Optimizer, risk, backtest, orders, allocator, kill switch and rebalancer."""
from __future__ import annotations
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app import database as db
from app.core.auth import User, require_admin
from app.core.runtime import (BASE_PRICES, _alpaca_client, _fresh_settings,
                              hft, sent_engine, settings)
from app.quantum_hft import risk_manager
from app.quantum_hft.qaoa_optimizer import quantum_portfolio_optimize
from app.quantum_hft.quantum_risk import risk_report
from app.services import alert_service
from app.trading.allocator import allocate
from app.trading.backtester import gen_price_path, run_backtest
from app.trading.costs import estimate_costs
from app.trading.rebalancer import rebalance_orders

router = APIRouter()


class OptimizeRequest(BaseModel):
    symbols: List[str]
    expected_returns: List[float]
    cov_matrix: List[List[float]]
    risk_aversion: float = 1.0


class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str = "buy"
    order_type: str = "market"
    limit_price: Optional[float] = None


class AllocatorRequest(BaseModel):
    budget: float = 100000.0
    currency: str = "INR"
    risk_profile: str = "balanced"
    tickers: List[str] = []


class KillSwitchRequest(BaseModel):
    action: str = "trip"  # trip | reset | evaluate
    reason: str = "manual"
    equity_curve: List[float] = []


class RebalanceRequest(BaseModel):
    holdings: Dict[str, float] = {}  # {symbol: shares}
    target_weights: Dict[str, float] = {}  # {symbol: weight}; empty = quantum equal-risk
    total_value: Optional[float] = None


@router.post("/api/quantum/optimize")
def optimize(req: OptimizeRequest):
    n = len(req.expected_returns)
    if n == 0:
        raise HTTPException(status_code=422, detail="expected_returns must not be empty")
    if len(req.cov_matrix) != n or any(len(row) != n for row in req.cov_matrix):
        raise HTTPException(status_code=422,
                            detail="cov_matrix must be n x n, matching expected_returns length")
    return quantum_portfolio_optimize(req.expected_returns, req.cov_matrix,
                                      req.risk_aversion)


@router.post("/api/risk/report")
def risk(payload: Dict):
    return risk_report(payload.get("returns", []))


@router.get("/api/backtest")
def backtest(symbol: str = "NVDA", periods: int = 252, series: bool = False):
    prices = gen_price_path(BASE_PRICES.get(symbol, 100), n=periods).tolist()
    return run_backtest(prices, initial=settings.BACKTEST_INITIAL_CAPITAL,
                        commission=settings.BACKTEST_COMMISSION,
                        include_series=series)


@router.post("/api/trade")
def trade(req: OrderRequest, user: User = Depends(require_admin)):
    if req.qty <= 0:
        raise HTTPException(status_code=422, detail="qty must be > 0")
    if req.order_type not in ("market", "limit"):
        raise HTTPException(status_code=422, detail="order_type must be 'market' or 'limit'")
    if req.order_type == "limit" and (req.limit_price is None or req.limit_price <= 0):
        raise HTTPException(status_code=422, detail="limit orders need a positive limit_price")
    side = "buy" if req.side.lower() in ("buy", "long") else "sell"
    res = _alpaca_client().place_order(req.symbol, req.qty, side, req.order_type,
                                       limit_price=req.limit_price)
    # Cost estimate + execution log (best-effort, never breaks the order).
    try:
        s = _fresh_settings()
        mids = {b["symbol"]: b["mid"] for b in hft.snapshot_all()}
        px = mids.get(req.symbol.upper()) or BASE_PRICES.get(req.symbol.upper(), 0.0)
        res["costs"] = estimate_costs(float(req.qty) * px, spread_bps=5.0,
                                      fee_rate=s.FEE_RATE, fee_min=s.FEE_MIN,
                                      tax_rate=s.TAX_RATE_GAINS)
        db.save_trade_execution(req.symbol, side, float(req.qty), req.order_type,
                                str(res.get("status", "")),
                                str(res.get("id") or res.get("error", "")),
                                user_id=user.id)
    except Exception:
        pass
    return res


@router.get("/api/account")
def account(user: User = Depends(require_admin)):
    return _alpaca_client().account()


@router.post("/api/allocate")
def allocate_capital(req: AllocatorRequest):
    """Smart capital allocator: quantum weights + sentiment + HFT risk."""
    try:
        books = hft.snapshot_all()
        sent = sent_engine.aggregate()
        rows = []
        wanted = {t.upper() for t in (req.tickers or [])}
        for b in books:
            s = b["symbol"]
            if wanted and s not in wanted:
                continue
            agg = sent["by_ticker"].get(s, {"bullish_pct": 50, "sentiment": 0.0})
            rows.append({"symbol": s, "price": b["mid"],
                         "sentiment": agg["sentiment"],
                         "ofi_norm": b["ofi"]["ofi_norm"],
                         "bullish_pct": agg["bullish_pct"]})
        plan = allocate(req.budget, req.risk_profile, rows)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    plan["currency"] = (req.currency or "USD").upper()
    # Pre-trade cost estimate on the LONG sleeve (best-effort).
    try:
        s = _fresh_settings()
        proj_profit = plan["long_cost"] * plan["projected_return_pct"] / 100
        plan["costs"] = estimate_costs(
            plan["long_cost"], spread_bps=5.0, projected_profit=proj_profit,
            fee_rate=s.FEE_RATE, fee_min=s.FEE_MIN, tax_rate=s.TAX_RATE_GAINS)
        plan["net_projected_return_pct"] = round(
            plan["costs"]["net_projected_profit"] / plan["budget"] * 100, 2)
    except Exception:
        pass
    # Best-effort portfolio log (never breaks the plan).
    try:
        db.save_portfolio({"name": f"allocator-{plan['risk_profile']}",
                           "budget": plan["budget"], "currency": plan["currency"],
                           "risk_profile": plan["risk_profile"],
                           "tickers": [ln["symbol"] for ln in plan["lines"]],
                           "notes": "auto-saved allocator plan"})
    except Exception:
        pass
    return plan


@router.get("/api/kill-switch")
def kill_status():
    s = _fresh_settings()
    return {**risk_manager.status(),
            "threshold_pct": s.KILL_SWITCH_DRAWNDOWN_PCT}


@router.post("/api/kill-switch")
def kill_switch(req: KillSwitchRequest, user: User = Depends(require_admin)):
    """trip (halts signals + liquidates) | reset (re-arm) | evaluate (dry-run)."""
    s = _fresh_settings()
    if req.action == "reset":
        return risk_manager.reset()
    if req.action == "evaluate":
        ev = risk_manager.evaluate(req.equity_curve,
                                   threshold_pct=s.KILL_SWITCH_DRAWNDOWN_PCT)
        if ev["kill"]:
            risk_manager.trip("auto-evaluate", ev["drawdown_pct"])
            db.save_trade_execution("ALL", "sell", 0, "market", "KILL_SWITCH",
                                    f"drawdown {ev['drawdown_pct']}%")
        return {**ev, **risk_manager.status()}
    # trip
    liq = risk_manager.liquidate(_alpaca_client())
    out = risk_manager.trip(req.reason or "manual", 0.0)
    db.save_trade_execution("ALL", "sell", 0, "market", "KILL_SWITCH",
                            f"{req.reason}; liq={liq.get('mode')}")
    try:
        s2 = _fresh_settings()
        alert_service.maybe_alert(
            [{"type": "BET_AGAINST", "symbol": "PORTFOLIO", "direction": "FLAT",
              "confidence": 1.0, "rationale": f"KILL SWITCH: {req.reason}"}],
            [], bot_token=s2.TELEGRAM_BOT_TOKEN or "",
            chat_id=s2.TELEGRAM_CHAT_ID or "",
            discord_url=s2.DISCORD_WEBHOOK_URL or "")
    except Exception:
        pass
    return {**out, "liquidation": liq}


@router.post("/api/rebalance")
def rebalance(req: RebalanceRequest):
    """Drift vs target weights -> whole-share buy/sell orders."""
    try:
        books = {b["symbol"]: b["mid"] for b in hft.snapshot_all()}
        targets = {k.upper(): float(v) for k, v in (req.target_weights or {}).items()}
        if not targets:
            n = len(books)
            targets = {s: 1.0 / n for s in books}
        holdings = {k.upper(): float(v) for k, v in (req.holdings or {}).items()}
        return rebalance_orders(holdings, books, targets, req.total_value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
