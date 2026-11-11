"""Shared runtime singletons and helpers used by the API routers.

Moved out of main.py so each router can import what it needs without
importing the app itself (no circular imports). Importing this module is
cheap and side-effect free apart from building the in-memory engines.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from app import market_data as md
from app.agents.betting_engine import BettingEngine
from app.agents.prediction_agent import PredictionAgent
from app.agents.sentiment_agent import SentimentEngine
from app.config import get_settings
from app.quantum_hft.hft_engine import HFTManager
from app.streaming import StreamClient
from app.trading.alpaca_client import AlpacaClient

settings = get_settings()

# Alpha Vantage refresh budget per snapshot tick (keeps cold starts fast).
_AV_REFRESH_PER_TICK = 2

# Real-time Alpaca stream (idle until ALPACA_API_KEY+SECRET are set).
stream_client = StreamClient(settings.alpaca_key or "",
                             settings.alpaca_secret or "",
                             feed=settings.ALPACA_DATA_FEED,
                             max_age_s=settings.STREAM_MAX_AGE_S)

BASE_PRICES = {"AAPL": 232.0, "MSFT": 428.0, "NVDA": 131.0, "TSLA": 248.0,
               "GOOGL": 176.0, "META": 585.0, "AMD": 122.0, "INTC": 24.0,
               "AMZN": 205.0}
hft = HFTManager(BASE_PRICES)
sent_engine = SentimentEngine(universe=list(BASE_PRICES))
pred_agent = PredictionAgent()
bet_engine = BettingEngine()
alpaca = AlpacaClient(settings.alpaca_key, settings.alpaca_secret,
                      settings.ALPACA_BASE_URL)


def _fresh_settings():
    """Read current settings (clears test-injected staleness via lru cache reset safe)."""
    return get_settings()


def _feed_status() -> Dict:
    return _fresh_settings().feed_status()


def _alpaca_client() -> AlpacaClient:
    s = _fresh_settings()
    return AlpacaClient(s.alpaca_key, s.alpaca_secret, s.ALPACA_BASE_URL)


_av_client: Optional[Any] = None
_av_key: Optional[str] = None


def _av() -> Optional[md.AlphaVantageClient]:
    """Cached Alpha Vantage client (rebuilt if the key changes). Shares the
    60s cache + daily budget across snapshot and WS ticks."""
    global _av_client, _av_key
    s = _fresh_settings()
    key = s.FINANCIAL_DATA_API_KEY
    if not key:
        return None
    if _av_client is None or _av_key != key:
        _av_client = md.AlphaVantageClient(key, cache_ttl_s=s.AV_CACHE_TTL_S,
                                           max_daily_calls=s.AV_MAX_DAILY_CALLS)
        _av_key = key
    return _av_client


def _apply_live_quotes(books: List[Dict]) -> Dict[str, Any]:
    """Overlay cached live quotes onto simulated books (mid = live price).
    Priority: Alpha Vantage first, then Yahoo Finance (no key needed) for
    books AV didn't cover. Skips books already covered by the real-time
    stream. Returns usage report. Never raises; failures keep simulator mids."""
    report: Dict[str, Any] = {"mode": "mock_simulator", "live_symbols": []}
    try:
        client = _av()
        if client is not None:
            uncovered = [b["symbol"] for b in books if "stream" not in b]
            # Cap refresh work per tick: a cold snapshot must stay fast. Symbols
            # not refreshed this tick keep the simulator mid (60s cache covers
            # the rest on the next passes).
            quotes = client.quotes(uncovered, limit=_AV_REFRESH_PER_TICK)
            for b in books:
                q = quotes.get(b["symbol"])
                if q:
                    md.recenter_book(b, q["price"])
                    b["live"] = q
                    report["live_symbols"].append(b["symbol"])
            if report["live_symbols"]:
                report["mode"] = "alphavantage"
            report["usage"] = client.usage()
    except Exception:
        pass
    # Yahoo Finance covers whatever AV missed (or everything when no AV key).
    # 60 s internal cache keeps per-tick cost near zero.
    try:
        from app.services import yahoo_finance as yfmod
        still_sim = [b["symbol"] for b in books
                     if "stream" not in b and "live" not in b]
        if still_sim:
            for q in yfmod.get_batch(still_sim):
                b = next((x for x in books if x["symbol"] == q["symbol"]), None)
                if b and (q.get("price") or 0) > 0:
                    md.recenter_book(b, q["price"])
                    b["live"] = {"price": q["price"],
                                 "change_pct": q.get("change_pct", 0.0),
                                 "source": "yahoo-finance"}
                    report["live_symbols"].append(b["symbol"])
            if report["live_symbols"] and report["mode"] == "mock_simulator":
                report["mode"] = "yahoo-finance"
            elif report["live_symbols"]:
                report["mode"] += "+yahoo-finance"
    except Exception:
        pass
    return report


def _apply_stream_ticks(books: List[Dict],
                        client: Optional[StreamClient] = None) -> Dict[str, Any]:
    """Overlay real-time stream ticks (fresh or stale-flagged).
    Never raises; no ticks -> books untouched."""
    report: Dict[str, Any] = {"mode": "mock_simulator", "live_symbols": [],
                              "stale_symbols": []}
    try:
        client = client or stream_client
        for b in books:
            q = client.get_quote(b["symbol"])
            if q:
                md.recenter_book(b, q["price"])
                b["stream"] = q
                if q["stale"]:
                    report["stale_symbols"].append(b["symbol"])
                else:
                    report["live_symbols"].append(b["symbol"])
        if report["live_symbols"] or report["stale_symbols"]:
            report["mode"] = "alpaca_stream"
        report["status"] = client.status()
    except Exception:
        pass
    return report
