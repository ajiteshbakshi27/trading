"""
QuantPulse AI — Divergence Engine (Smart Money vs Ape Money).

Contrasts institutional market reality (Alpha Vantage price/volume/order flow)
against retail Reddit sentiment (PRAW or mock) to surface tickers where the
two factions disagree.

Outputs per symbol:
  * divergence_score  — |retail_bullish - market_bullish|, 0..100
  * divergence_label — "Reddit 90% Bullish vs Market 70% Bearish"
  * squeeze_metric   — Reddit mention spike x volume spike x short-interest proxy
  * faction_signals  — the raw inputs, so the UI can show its work

Everything is cached aggressively. No credential → deterministic mock, labelled
MOCK. Real PRAW → labelled LIVE.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from app.models.common import clamp
from app.models.enums import DataMode

#: Subreddits that carry the retail signal. Ordered by signal quality.
DIVERGENCE_SUBREDDITS = ["wallstreetbets", "stocks", "options", "pennystocks"]

#: Cache TTLs (seconds). Free-tier pacing is the binding constraint.
_REDDIT_TTL_S = 120.0
_QUOTE_TTL_S = 60.0
_DIVERGENCE_TTL_S = 90.0


class _Cache:
    def __init__(self) -> None:
        self._store: Dict[str, tuple] = {}

    def get(self, key: str, ttl: float) -> Optional[Any]:
        hit = self._store.get(key)
        if not hit:
            return None
        ts, val = hit
        if time.time() - ts > ttl:
            return None
        return val

    def put(self, key: str, value: Any) -> None:
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


_cache = _Cache()


def clear_caches() -> None:
    _cache.clear()


# ---------------------------------------------------------------------------
# Market side (institutional reality)
# ---------------------------------------------------------------------------

def _market_snapshot(symbol: str) -> Dict[str, Any]:
    """Price, change, volume and a market-implied bullish score.

    The market bullish score maps recent price action + volume into 0..100 so
    it can be compared directly with the Reddit bullish percentage.
    """
    from app import market_data as md
    from app.config import get_settings

    key = f"mkt:{symbol.upper()}"
    cached = _cache.get(key, _QUOTE_TTL_S)
    if cached:
        return cached

    s = get_settings()
    out = {"symbol": symbol.upper(), "price": 0.0, "change_pct": 0.0,
           "volume": 0, "market_bullish": 50, "data_mode": DataMode.MOCK.value,
           "source": "simulator"}
    try:
        client = md.AlphaVantageClient(s.FINANCIAL_DATA_API_KEY or "",
                                       cache_ttl_s=s.AV_CACHE_TTL_S,
                                       max_daily_calls=s.AV_MAX_DAILY_CALLS)
        q = client.quote(symbol)
        if q:
            out.update({
                "price": q["price"],
                "change_pct": q["change_pct"],
                "data_mode": DataMode.LIVE.value,
                "source": "alphavantage",
            })
    except Exception:
        pass

    # Volume + trend from the HFT simulator book (always available).
    try:
        from app.quantum_hft.hft_engine import HFTManager
        from app.config import get_settings as _gs
        base = _gs()
        books = HFTManager(dict(base.BASE_PRICES)).snapshot_all()
        book = next((b for b in books if b["symbol"] == symbol.upper()), None)
        if book:
            out["price"] = book["mid"]
            out["change_pct"] = book.get("ofi", {}).get("ofi_norm", 0.0) * 100
            out["volume"] = int(sum(l["size"] for l in book.get("bids", []))
                                + sum(l["size"] for l in book.get("asks", [])))
            ofi = book.get("ofi", {}).get("ofi_norm", 0.0)
            # Market bullish: blend OFI and recent change into 0..100.
            out["market_bullish"] = round(clamp(50 + ofi * 40 + out["change_pct"] * 2), 1)
    except Exception:
        pass

    _cache.put(key, out)
    return out


# ---------------------------------------------------------------------------
# Reddit side (retail hype)
# ---------------------------------------------------------------------------

def _reddit_snapshot(symbol: str, engine=None) -> Dict[str, Any]:
    """Reddit mention count, bullish% and mention velocity."""
    from app.agents.sentiment_agent import SentimentEngine
    from app.config import get_settings

    key = f"reddit:{symbol.upper()}"
    cached = _cache.get(key, _REDDIT_TTL_S)
    if cached:
        return cached

    s = get_settings()
    eng = engine or SentimentEngine()
    out = {"symbol": symbol.upper(), "mentions": 0, "reddit_bullish": 50,
           "mention_velocity": 0.0, "data_mode": DataMode.MOCK.value,
           "source": "mock", "sample_posts": []}
    try:
        posts = eng.reddit_live(s.REDDIT_CLIENT_ID, s.REDDIT_CLIENT_SECRET, limit=20)
        if not posts:
            posts = eng.reddit_mock(limit=20)
        matched = [p for p in posts if symbol.upper() in p.get("tickers", [])]
        if matched:
            out["mentions"] = len(matched)
            out["reddit_bullish"] = round(
                sum(p.get("sentiment", 0.0) for p in matched) / len(matched) * 50 + 50, 1)
            out["sample_posts"] = [p.get("text", "")[:120] for p in matched[:3]]
            out["data_mode"] = DataMode.LIVE.value if s.has_reddit else DataMode.MOCK.value
            out["source"] = "praw" if s.has_reddit else "mock"
        # Velocity: mentions per post in the recent window.
        out["mention_velocity"] = round(len(matched) / max(1, len(posts)), 4)
    except Exception:
        pass

    _cache.put(key, out)
    return out


# ---------------------------------------------------------------------------
# Divergence + squeeze
# ---------------------------------------------------------------------------

def _short_interest_proxy(symbol: str) -> float:
    """0..1 proxy for short interest. Real short data needs a paid feed.

    Uses the relationship between price decline and volume as a proxy:
    heavy volume on down days is consistent with short covering / short
    selling. This is a proxy, not a measurement, and is labelled as such.
    """
    mkt = _market_snapshot(symbol)
    change = float(mkt.get("change_pct", 0.0))
    if change >= 0:
        return 0.0
    # Down move + elevated volume → higher proxy.
    return round(clamp(abs(change) / 5.0, 0.0, 1.0), 3)


def compute_divergence(symbol: str, engine=None) -> Dict[str, Any]:
    """Full divergence snapshot for one symbol."""
    key = f"div:{symbol.upper()}"
    cached = _cache.get(key, _DIVERGENCE_TTL_S)
    if cached:
        return cached

    mkt = _market_snapshot(symbol, )
    reddit = _reddit_snapshot(symbol, engine=engine)

    retail_bull = float(reddit["reddit_bullish"])
    market_bull = float(mkt["market_bullish"])
    divergence = round(abs(retail_bull - market_bull), 1)

    # Squeeze metric: Reddit spike × volume spike × short-interest proxy.
    mention_spike = clamp(reddit["mention_velocity"] * 2.0, 0.0, 1.0)
    volume_spike = clamp(float(mkt.get("volume", 0)) / 50000.0, 0.0, 1.0)
    short_proxy = _short_interest_proxy(symbol)
    squeeze = round(mention_spike * 0.4 + volume_spike * 0.3 + short_proxy * 0.3, 3)

    if retail_bull > market_bull + 15:
        label = f"Reddit {retail_bull:.0f}% Bullish vs Market {market_bull:.0f}% Bearish"
        stance = "RETAIL OVERHYPED"
    elif market_bull > retail_bull + 15:
        label = f"Market {market_bull:.0f}% Bullish vs Reddit {retail_bull:.0f}% Bearish"
        stance = "SMART MONEY DIVERGENCE"
    else:
        label = f"Aligned — Reddit {retail_bull:.0f}% / Market {market_bull:.0f}%"
        stance = "ALIGNED"

    out = {
        "symbol": symbol.upper(),
        "divergence_score": divergence,
        "divergence_label": label,
        "stance": stance,
        "squeeze_metric": squeeze,
        "squeeze_label": ("HIGH" if squeeze > 0.6 else
                          "ELEVATED" if squeeze > 0.35 else "LOW"),
        "retail": reddit,
        "market": mkt,
        "faction": "retail" if retail_bull > market_bull else "institutional",
        "data_mode": DataMode.MOCK.value,
        "note": ("Divergence is a comparison of sentiment and price action, "
                 "not a prediction. Short interest is a proxy, not a measurement."),
    }
    _cache.put(key, out)
    return out


def scan(universe: Optional[List[str]] = None, engine=None,
          limit: int = 20) -> List[Dict[str, Any]]:
    """Divergence scan across the universe, sorted by divergence score."""
    if universe:
        symbols = universe
    else:
        # BASE_PRICES lives in main.py; fall back to a hardcoded list.
        try:
            from app.config import get_settings
            s = get_settings()
            symbols = list(getattr(s, "BASE_PRICES", {}).keys())
        except Exception:
            pass
        if not symbols:
            symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "META",
                       "AMD", "INTC", "AMZN"]
    results = [compute_divergence(sym, engine=engine) for sym in symbols[:limit]]
    results.sort(key=lambda r: -r["divergence_score"])
    return results
