"""
QuantPulse AI — Paper Trading Engine.

A virtual ledger that turns research theses into paper orders with real P&L
tracking. No real money moves; everything is simulated and labelled MOCK.

The engine:
  * starts with a configurable virtual cash balance (default ₹1,00,000)
  * executes buy/sell orders against the current simulated mid price
  * tracks realized + unrealized P&L per position
  * computes portfolio equity, daily returns, Sharpe and max drawdown
  * liquidates all positions on a kill-switch trip

Every order is persisted so the research loop can measure its own tradable
performance — closing the loop from signal to P&L.
"""
from __future__ import annotations

import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.models.common import clamp, iso
from app.models.enums import DataMode, Direction

DEFAULT_BUDGET = 100_000.0
COMMISSION_RATE = 0.0005
MIN_FEE = 1.0
TAX_RATE_GAINS = 0.15


@dataclass
class PaperPosition:
    symbol: str
    qty: float = 0.0
    avg_entry: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.qty * self.avg_entry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": round(self.qty, 4),
            "avg_entry": round(self.avg_entry, 4),
            "realized_pnl": round(self.realized_pnl, 2),
        }


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    qty: float
    price: float
    notional: float
    fee: float
    tax: float
    net: float
    timestamp: str
    source: str = "manual"  # manual | allocator | thesis | kill_switch

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": round(self.qty, 4),
            "price": round(self.price, 4),
            "notional": round(self.notional, 2),
            "fee": round(self.fee, 2),
            "tax": round(self.tax, 2),
            "net": round(self.net, 2),
            "timestamp": self.timestamp,
            "source": self.source,
        }


class PaperLedger:
    """In-memory + persisted virtual portfolio."""

    def __init__(self, budget: float = DEFAULT_BUDGET):
        self.initial_cash = budget
        self.cash = budget
        self.positions: Dict[str, PaperPosition] = {}
        self.equity_curve: List[float] = [budget]
        self._prices: Dict[str, float] = {}
        self._day = ""
        self._day_start_equity = budget

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, symbol: str, side: str, qty: float, price: float,
                source: str = "manual") -> PaperOrder:
        """Execute one paper order. Returns the order record."""
        qty = max(0.0, float(qty))
        if qty <= 0:
            raise ValueError("qty must be > 0")
        price = max(0.0, float(price))
        notional = qty * price
        fee = max(MIN_FEE, notional * COMMISSION_RATE)
        tax = 0.0
        net = notional + fee if side == "buy" else notional - fee - tax

        if side == "buy":
            if net > self.cash:
                raise ValueError(
                    f"insufficient cash: need {net:.2f}, have {self.cash:.2f}")
            self.cash -= net
            pos = self.positions.setdefault(symbol, PaperPosition(symbol))
            total_cost = pos.qty * pos.avg_entry + notional
            pos.qty += qty
            pos.avg_entry = total_cost / pos.qty if pos.qty else 0.0
        else:
            pos = self.positions.get(symbol)
            if not pos or pos.qty < qty:
                raise ValueError(f"insufficient {symbol} to sell: {qty}")
            # Realized P&L = (sell_price - avg_entry) * qty - fees
            gross = (price - pos.avg_entry) * qty
            tax = max(0.0, gross) * TAX_RATE_GAINS
            pos.realized_pnl += gross - fee - tax
            self.cash += notional - fee - tax
            pos.qty -= qty
            if pos.qty <= 1e-9:
                del self.positions[symbol]

        order = PaperOrder(
            order_id=f"po_{int(time.time() * 1000)}",
            symbol=symbol.upper(),
            side=side.lower(),
            qty=qty,
            price=price,
            notional=round(notional, 2),
            fee=round(fee, 2),
            tax=round(tax, 2),
            net=round(net, 2),
            timestamp=iso(),
            source=source,
        )
        return order

    def mark_to_market(self, prices: Dict[str, float]) -> None:
        """Update the equity curve with current mid prices."""
        self._prices = {k.upper(): float(v) for k, v in (prices or {}).items()}
        invested = self.market_value
        self._day_start_equity = self.cash + invested
        self.equity_curve.append(round(self._day_start_equity, 2))

    # ------------------------------------------------------------------
    # Liquidation
    # ------------------------------------------------------------------

    def liquidate_all(self, prices: Dict[str, float],
                      reason: str = "kill_switch") -> List[PaperOrder]:
        """Close every position at the given prices."""
        orders: List[PaperOrder] = []
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            price = float(prices.get(symbol, pos.avg_entry))
            if pos.qty > 0 and price > 0:
                orders.append(self.execute(symbol, "sell", pos.qty, price,
                                           source=reason))
        return orders

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @property
    def invested(self) -> float:
        return sum(p.qty * p.avg_entry for p in self.positions.values())

    @property
    def market_value(self) -> float:
        """Positions valued at the last marked market price (fallback: cost)."""
        total = 0.0
        for p in self.positions.values():
            price = float((self._prices or {}).get(p.symbol, p.avg_entry))
            total += p.qty * price
        return total

    @property
    def equity(self) -> float:
        return self.cash + self.market_value

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.qty * (p.avg_entry - p.avg_entry) for p in self.positions.values())

    @property
    def realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    @property
    def total_pnl(self) -> float:
        return self.equity - self.initial_cash

    @property
    def total_pnl_pct(self) -> float:
        return (self.total_pnl / self.initial_cash) * 100.0 if self.initial_cash else 0.0

    def returns(self) -> List[float]:
        """Daily simple returns from the equity curve."""
        curve = self.equity_curve
        if len(curve) < 2:
            return []
        return [(curve[i] / curve[i - 1] - 1.0) * 100.0
                for i in range(1, len(curve)) if curve[i - 1] > 0]

    def sharpe(self, periods_per_year: int = 252) -> Optional[float]:
        rets = self.returns()
        if len(rets) < 2:
            return None
        mean = statistics.fmean(rets)
        sd = statistics.pstdev(rets)
        if sd == 0:
            return None
        return round(mean / sd * math.sqrt(periods_per_year), 4)

    def max_drawdown_pct(self) -> float:
        peak = self.equity_curve[0] if self.equity_curve else 0.0
        worst = 0.0
        for v in self.equity_curve:
            peak = max(peak, v)
            if peak > 0:
                worst = min(worst, (v / peak - 1.0) * 100.0)
        return round(worst, 4)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "initial_cash": round(self.initial_cash, 2),
            "cash": round(self.cash, 2),
            "invested": round(self.invested, 2),
            "market_value": round(self.market_value, 2),
            "equity": round(self.equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "total_pnl": round(self.total_pnl, 2),
            "total_pnl_pct": round(self.total_pnl_pct, 4),
            "sharpe": self.sharpe(),
            "max_drawdown_pct": self.max_drawdown_pct(),
            "positions": [p.to_dict() for p in self.positions.values()],
            "position_count": len(self.positions),
            "data_mode": DataMode.MOCK.value,
            "data_mode_label": DataMode.MOCK.label,
        }
