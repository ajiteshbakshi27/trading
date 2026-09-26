"""
QuantPulse AI — Paper Trading API.

    GET  /api/paper/portfolio        current state + positions
    POST /api/paper/order             execute a paper order
    POST /api/paper/allocator         deploy the allocator plan as paper orders
    POST /api/paper/mark-to-market    update equity curve with current mids
    POST /api/paper/liquidate         close all positions (kill-switch)
    GET  /api/paper/orders            order history

All orders are simulated and labelled MOCK. No real money moves.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services.paper_trading import PaperLedger

router = APIRouter(prefix="/api/paper", tags=["paper-trading"])

#: One in-process ledger. Single-worker by design (render.yaml pins --workers 1).
_ledger = PaperLedger()


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=8)
    qty: float = Field(gt=0)
    side: str = "buy"
    price: float = Field(gt=0)
    source: str = "manual"


class AllocatorDeployRequest(BaseModel):
    budget: float = Field(default=100000.0, gt=0)
    risk_profile: str = "balanced"
    symbol: Optional[str] = None


@router.get("/portfolio")
def portfolio():
    return {**_ledger.snapshot(), **mode_block(DataMode.MOCK)}


@router.post("/order")
def place_order(req: PaperOrderRequest):
    try:
        order = _ledger.execute(req.symbol, req.side, req.qty, req.price,
                                 source=req.source)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "order": order.to_dict(),
        "portfolio": _ledger.snapshot(),
        **mode_block(DataMode.MOCK),
    }


@router.post("/allocator")
def deploy_allocator(req: AllocatorDeployRequest):
    """Run the allocator and deploy the resulting plan as paper orders."""
    from app.api.information import _snapshot_inputs
    from app.trading.allocator import allocate
    books, sentiment, markets, news, _ctx = _snapshot_inputs(req.symbol)
    wanted = {req.symbol.upper()} if req.symbol else set()
    rows = []
    for b in books:
        s = b["symbol"]
        if wanted and s not in wanted:
            continue
        agg = sentiment["by_ticker"].get(s, {"bullish_pct": 50, "sentiment": 0.0})
        rows.append({"symbol": s, "price": b["mid"],
                     "sentiment": agg["sentiment"],
                     "ofi_norm": b["ofi"]["ofi_norm"],
                     "bullish_pct": agg["bullish_pct"]})
    if not rows:
        raise HTTPException(status_code=422, detail="no symbols available")
    plan = allocate(req.budget, req.risk_profile, rows)

    orders = []
    prices = {ln["symbol"]: ln["price"] for ln in plan.get("lines", [])}
    # Deploy the LONG sleeve only (paper engine has no shorting yet).
    long_lines = [ln for ln in plan.get("lines", []) if ln.get("side") == "long"]
    if not long_lines:
        raise HTTPException(status_code=422, detail="allocator produced no long lines")
    # Use available cash; if the plan exceeds it, scale down.
    available = _ledger.cash
    total_long = sum(ln["amount"] for ln in long_lines) or 1.0
    scale = min(1.0, available / total_long) if total_long > available else 1.0
    for ln in long_lines:
        amount = ln["amount"] * scale
        if amount < 1.0:
            continue
        price = float(prices.get(ln["symbol"], 0.0))
        if price <= 0:
            continue
        qty = amount / price
        try:
            order = _ledger.execute(ln["symbol"], "buy", round(qty, 4), price,
                                     source="allocator")
            orders.append(order.to_dict())
        except ValueError:
            break  # out of cash
    return {
        "orders": orders,
        "plan": plan,
        "portfolio": _ledger.snapshot(),
        **mode_block(DataMode.MOCK),
    }


@router.post("/mark-to-market")
def mark_to_market():
    from app.api.information import _snapshot_inputs
    books, _s, _m, _n, _c = _snapshot_inputs(None)
    prices = {b["symbol"]: b["mid"] for b in books}
    _ledger.mark_to_market(prices)
    return {**_ledger.snapshot(), **mode_block(DataMode.MOCK)}


@router.post("/liquidate")
def liquidate(reason: str = "manual"):
    from app.api.information import _snapshot_inputs
    books, _s, _m, _n, _c = _snapshot_inputs(None)
    prices = {b["symbol"]: b["mid"] for b in books}
    orders = _ledger.liquidate_all(prices, reason=reason)
    return {
        "orders": [o.to_dict() for o in orders],
        "portfolio": _ledger.snapshot(),
        **mode_block(DataMode.MOCK),
    }


@router.get("/orders")
def orders(limit: int = 100):
    # Return the most recent executed orders from the module-level ledger.
    # The ledger does not keep a full order history in memory; the API
    # persists them separately. For now, return an empty list with the
    # portfolio state so the frontend has a stable contract.
    return {
        "orders": [],
        "count": 0,
        "portfolio": _ledger.snapshot(),
        "note": ("Order history is persisted by the backend. Use "
                 "/api/trades for the execution log."),
        **mode_block(DataMode.MOCK),
    }
