"""
QuantPulse AI - Alpaca Paper Trading Client
Wraps alpaca-py; dry-run mock when keys are missing.
"""
from __future__ import annotations
from typing import Dict, Optional


class AlpacaClient:
    def __init__(self, api_key: Optional[str], secret_key: Optional[str],
                 base_url: str = "https://paper-api.alpaca.markets",
                 paper: bool = True):
        self.paper = paper
        self.live = bool(api_key and secret_key)
        self._client = None
        if self.live:
            try:
                from alpaca.trading.client import TradingClient
                self._client = TradingClient(api_key, secret_key, paper=paper)
            except Exception:
                self.live = False

    def place_order(self, symbol: str, qty: float, side: str = "buy",
                    order_type: str = "market",
                    limit_price: Optional[float] = None) -> Dict:
        if not self.live or self._client is None:
            return {"status": "MOCK_FILLED", "symbol": symbol, "qty": qty,
                    "side": side, "type": order_type, "paper": True}
        try:
            from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            s = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
            req = (MarketOrderRequest(symbol=symbol, qty=qty, side=s,
                                      time_in_force=TimeInForce.DAY)
                   if order_type == "market" else
                   LimitOrderRequest(symbol=symbol, qty=qty, side=s,
                                     time_in_force=TimeInForce.DAY,
                                     limit_price=limit_price))
            o = self._client.submit_order(req)
            return {"status": o.status.value if hasattr(o.status, "value") else str(o.status),
                    "symbol": symbol, "qty": qty, "side": side, "id": str(o.id)}
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "symbol": symbol}

    def account(self) -> Dict:
        if not self.live or self._client is None:
            return {"equity": 100000.0, "cash": 100000.0, "mode": "MOCK_PAPER"}
        try:
            a = self._client.get_account()
            return {"equity": float(a.equity), "cash": float(a.cash), "mode": "LIVE_PAPER"}
        except Exception as e:
            return {"equity": 0, "error": str(e)}
