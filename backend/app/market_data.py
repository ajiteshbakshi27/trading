"""
QuantPulse AI - Alpha Vantage live market data (prices + intraday).
Free-tier guards: 60s response cache + daily call budget (default 20/25).
Any failure (no key, rate limit, network) returns None -> caller falls
back to the HFT simulator. Never raises to the request path.
"""
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import httpx

BASE_URL = "https://www.alphavantage.co/query"


class RateLimited(Exception):
    pass


class AlphaVantageClient:
    def __init__(self, api_key: str, cache_ttl_s: int = 60,
                 max_daily_calls: int = 20, min_gap_s: float = 1.2):
        self.api_key = api_key
        self.ttl = max(10, int(cache_ttl_s))
        self.max_daily = max(1, int(max_daily_calls))
        self.min_gap_s = max(0.0, float(min_gap_s))
        self._cache: Dict[str, tuple] = {}
        self._day = self._today()
        self._used = 0
        self._last_call_ts = 0.0

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def usage(self) -> Dict[str, Any]:
        if self._day != self._today():
            self._day, self._used = self._today(), 0
        return {"used_today": self._used, "daily_budget": self.max_daily,
                "cached_keys": len(self._cache)}

    def _get(self, params: Dict[str, str]) -> Dict[str, Any] | None:
        if not self.api_key:
            return None
        key = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        now = time.time()
        hit = self._cache.get(key)
        if hit and now - hit[0] < self.ttl:
            return hit[1]
        if self._day != self._today():
            self._day, self._used = self._today(), 0
        if self._used >= self.max_daily:
            return hit[1] if hit else None  # serve stale over nothing
        # Free-tier pacing: max ~1 request/second or AV returns Information.
        gap = now - self._last_call_ts
        if self._last_call_ts and gap < self.min_gap_s:
            time.sleep(self.min_gap_s - gap)
        try:
            r = httpx.get(BASE_URL, params={**params, "apikey": self.api_key},
                          timeout=5.0)
            self._last_call_ts = time.time()
            if r.status_code != 200:
                return hit[1] if hit else None
            data = r.json()
        except Exception:
            return hit[1] if hit else None
        if "Note" in data or "Information" in data:
            # Rate-limited / key issue: serve stale cache, never raise here.
            return hit[1] if hit else None
        self._used += 1
        self._cache[key] = (now, data)
        return data

    def quote(self, symbol: str) -> Dict[str, Any] | None:
        """GLOBAL_QUOTE -> {price, change_pct, source} or None."""
        data = self._get({"function": "GLOBAL_QUOTE", "symbol": symbol.upper()})
        if not data:
            return None
        q = data.get("Global Quote", {}) or {}
        try:
            price = float(q.get("05. price", 0) or 0)
        except (TypeError, ValueError):
            return None
        if price <= 0:
            return None
        pct = str(q.get("10. change percent", "0%")).replace("%", "")
        try:
            change_pct = float(pct)
        except ValueError:
            change_pct = 0.0
        return {"symbol": symbol.upper(), "price": round(price, 2),
                "change_pct": round(change_pct, 2), "source": "alphavantage",
                "trading_day": q.get("07. latest trading day", "")}

    def quotes(self, symbols: List[str],
               limit: int | None = None) -> Dict[str, Dict[str, Any]]:
        """Quotes for symbols. `limit` caps how many *cache misses* are
        fetched in one pass so a cold snapshot never blocks the request."""
        out: Dict[str, Dict[str, Any]] = {}
        misses = 0
        for s in symbols:
            q = self.quote(s)
            if q:
                out[s.upper()] = q
            elif limit is None or misses < limit:
                misses += 1
        return out

    def intraday(self, symbol: str,
                 interval: str = "60min") -> List[Dict[str, Any]] | None:
        """TIME_SERIES_INTRADAY -> candle list (oldest first) or None."""
        data = self._get({"function": "TIME_SERIES_INTRADAY",
                          "symbol": symbol.upper(), "interval": interval,
                          "outputsize": "compact"})
        if not data:
            return None
        series = None
        for k, v in data.items():
            if k.lower().startswith("time series"):
                series = v
                break
        if not series:
            return None
        out = []
        for ts in sorted(series.keys()):
            b = series[ts]
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=timezone.utc)
                out.append({
                    "time": int(dt.timestamp()),
                    "open": round(float(b["1. open"]), 2),
                    "high": round(float(b["2. high"]), 2),
                    "low": round(float(b["3. low"]), 2),
                    "close": round(float(b["4. close"]), 2)})
            except (KeyError, ValueError):
                continue
        return out or None


def recenter_book(book: Dict[str, Any], live_price: float) -> Dict[str, Any]:
    """Shift a simulated L2 book so mid == live quote (keeps depth shape)."""
    try:
        mid = float(book.get("mid", 0) or 0)
        if mid <= 0 or live_price <= 0:
            return book
        shift = round(live_price - mid, 2)
        for side in ("bids", "asks"):
            for lvl in book.get(side, []):
                lvl["price"] = round(float(lvl["price"]) + shift, 2)
        book["mid"] = round(live_price, 2)
        return book
    except Exception:
        return book
