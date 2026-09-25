"""
QuantPulse AI - Real-time Alpaca data websocket stream.
Maintains a persistent connection to Alpaca data v2 (trades + quotes),
auto-reconnects with backoff, and keeps the latest tick per symbol.

No credentials -> disconnected (idle), callers fall back to Alpha Vantage,
then to the simulator. Never raises into the request path.
"""
from __future__ import annotations
import asyncio
import json
import time
from typing import Dict, List, Optional, Any

WS_URL = "wss://stream.data.alpaca.markets/v2/{feed}"


class StreamClient:
    def __init__(self, api_key: str = "", secret_key: str = "",
                 feed: str = "iex", max_age_s: float = 5.0):
        self.api_key = api_key or ""
        self.secret_key = secret_key or ""
        self.feed = (feed or "iex").lower()
        self.max_age_s = max(1.0, float(max_age_s or 5.0))
        self._ticks: Dict[str, Dict[str, Any]] = {}
        self._connected = False
        self._last_error = ""
        self._task: Optional[asyncio.Task] = None
        self._stop = False

    # ------------------------------ state ----------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def status(self) -> Dict[str, Any]:
        now = time.time()
        ages = {s: round(now - t["ts"], 1) for s, t in self._ticks.items()}
        return {"configured": self.configured, "connected": self._connected,
                "feed": self.feed, "symbols": sorted(self._ticks.keys()),
                "ages_s": ages, "last_error": self._last_error}

    def inject_tick(self, symbol: str, price: float) -> None:
        """Test hook: pretend a live tick arrived."""
        self._ticks[symbol.upper()] = {"price": float(price), "ts": time.time()}

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Latest tick + freshness. None when never seen."""
        t = self._ticks.get(symbol.upper())
        if not t:
            return None
        age = time.time() - t["ts"]
        return {"symbol": symbol.upper(), "price": t["price"],
                "age_s": round(age, 1), "stale": age > self.max_age_s,
                "source": "alpaca_stream"}

    # ---------------------------- connection --------------------------------
    async def _run_once(self, symbols: List[str]) -> None:
        import websockets
        url = WS_URL.format(feed=self.feed)
        async with websockets.connect(url, max_size=4_000_000) as ws:
            await ws.send(json.dumps({"action": "auth", "key": self.api_key,
                                      "secret": self.secret_key}))
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(raw)
            if isinstance(msg, list):
                msg = msg[0] if msg else {}
            if msg.get("T") == "error":
                raise ConnectionError(str(msg.get("msg", "auth failed")))
            syms = [s.upper() for s in symbols]
            await ws.send(json.dumps({"action": "subscribe",
                                      "trades": syms, "quotes": syms}))
            # The subscribe reply carries auth errors (402) — fail fast here
            # instead of idling on a dead connection.
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            try:
                sub = json.loads(raw)
                first = sub[0] if isinstance(sub, list) and sub else sub
            except ValueError:
                first = {}
            if isinstance(first, dict) and first.get("T") == "error":
                raise ConnectionError(str(first.get("msg", "subscribe failed")))
            self._connected = True
            self._last_error = ""
            async for raw in ws:
                try:
                    batch = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(batch, dict):
                    batch = [batch]
                for m in batch:
                    if m.get("T") not in ("t", "q"):
                        continue
                    sym = str(m.get("S", "")).upper()
                    px = m.get("p") if m.get("T") == "t" else m.get("ap")
                    try:
                        price = float(px)
                    except (TypeError, ValueError):
                        continue
                    if price > 0 and sym:
                        self._ticks[sym] = {"price": price, "ts": time.time()}

    async def run_forever(self, symbols: List[str]) -> None:
        """Reconnect loop. Returns immediately when unconfigured."""
        if not self.configured:
            self._last_error = "missing ALPACA_API_KEY/SECRET"
            return
        delay = 2.0
        while not self._stop:
            try:
                await self._run_once(list(symbols))
                delay = 2.0  # clean exit shouldn't happen; reset backoff
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._last_error = str(e)[:200]
            await asyncio.sleep(min(delay, 60.0))
            delay *= 2
        self._connected = False

    def start(self, symbols: List[str]) -> Optional[asyncio.Task]:
        """Spawn background task (no-op when already running)."""
        if self._task is None or self._task.done():
            self._stop = False
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                return None
            self._task = loop.create_task(self.run_forever(list(symbols)))
        return self._task

    async def stop(self) -> None:
        self._stop = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._connected = False
