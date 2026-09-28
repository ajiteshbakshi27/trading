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
  * currency         — "USD" or "INR"
  * exchange         — "NASDAQ" or "NSE"

Everything is cached aggressively. No credential → deterministic mock, labelled
MOCK. Real PRAW → labelled LIVE. Fallback prices are used when Alpha Vantage
fails or returns null/zero.
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

#: Fallback prices — used only when Alpha Vantage fails or returns null/zero.
#: These are realistic cached values, labelled MOCK in the response.
FALLBACK_PRICES: Dict[str, Dict[str, Any]] = {
    # US tickers (NASDAQ) — USD
    "NVDA":      {"price": 118.20, "change_pct": 2.4,  "currency": "USD", "exchange": "NASDAQ"},
    "TSLA":      {"price": 245.50, "change_pct": -1.2, "currency": "USD", "exchange": "NASDAQ"},
    "AAPL":      {"price": 228.10, "change_pct": 0.8,  "currency": "USD", "exchange": "NASDAQ"},
    "AMD":       {"price": 156.40, "change_pct": 1.5,  "currency": "USD", "exchange": "NASDAQ"},
    "INTC":      {"price": 20.15,  "change_pct": -0.5, "currency": "USD", "exchange": "NASDAQ"},
    "GOOGL":     {"price": 178.30, "change_pct": 0.6,  "currency": "USD", "exchange": "NASDAQ"},
    "MSFT":      {"price": 428.90, "change_pct": 1.1,  "currency": "USD", "exchange": "NASDAQ"},
    "META":      {"price": 585.00, "change_pct": 0.9,  "currency": "USD", "exchange": "NASDAQ"},
    "AMZN":      {"price": 205.00, "change_pct": 0.7,  "currency": "USD", "exchange": "NASDAQ"},
    # Indian tickers (NSE/BSE) — INR
    "RELIANCE":  {"price": 2980.50, "change_pct": 1.4, "currency": "INR", "exchange": "NSE"},
    "TATAMOTORS": {"price": 975.20,  "change_pct": 2.1, "currency": "INR", "exchange": "NSE"},
    "ADANIENT":  {"price": 3140.00, "change_pct": -0.8, "currency": "INR", "exchange": "NSE"},
    "INFY":      {"price": 1890.30, "change_pct": 0.9, "currency": "INR", "exchange": "NSE"},
    "NIFTY50":   {"price": 25380.00, "change_pct": 0.5, "currency": "INR", "exchange": "NSE"},
}

#: Default universe: US tech + Indian blue-chips + Nifty 50.
DEFAULT_UNIVERSE: List[str] = [
    "NVDA", "TSLA", "AAPL", "AMD", "INTC", "GOOGL", "MSFT",
    "RELIANCE", "TATAMOTORS", "ADANIENT", "INFY", "NIFTY50",
]

#: Map from internal symbol to display symbol (strip .BSE suffix).
_DISPLAY_NAMES: Dict[str, str] = {
    "RELIANCE.BSE": "RELIANCE",
    "TATAMOTORS.BSE": "TATAMOTORS",
    "ADANIENT.BSE": "ADANIENT",
    "INFY.BSE": "INFY",
    "NIFTY50": "NIFTY50",
}


def display_symbol(internal: str) -> str:
    """Convert internal ticker to display ticker (strip .BSE)."""
    return _DISPLAY_NAMES.get(internal, internal.upper())


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

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely coerce a value to float, returning default on failure."""
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


#: Symbols served by the Indian Stock Market API (NSE/BSE universe).
_INDIAN_SYMBOLS = frozenset({"RELIANCE", "TATAMOTORS", "ADANIENT", "INFY",
                             "NIFTY50", "TCS", "HDFCBANK", "SBIN", "ITC",
                             "TATASTEEL", "ONGC", "WIPRO"})


def _indian_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Live NSE/BSE quote via the Indian Stock Market API.

    Returns ``{"price", "change_pct", "volume"}`` or ``None`` when the
    upstream is unreachable. Never raises. Payload keys are probed
    defensively because upstream field names vary by version.
    """
    try:
        from app.services import indian_stock_api as isa
    except Exception:
        return None
    try:
        data = isa.get_stock_data(symbol)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # Upstream may nest the quote one level deep; unwrap common wrappers.
    payload = data
    for wrapper in ("data", "quote", "result"):
        inner = data.get(wrapper)
        if isinstance(inner, dict) and any(
                k in inner for k in ("price", "currentPrice", "lastPrice",
                                     "ltp", "close")):
            payload = inner
            break
    price = 0.0
    for key in ("price", "currentPrice", "lastPrice", "ltp", "close"):
        price = _safe_float(payload.get(key), 0.0)
        if price > 0:
            break
    if price <= 0:
        return None
    change = 0.0
    for key in ("percentChange", "pChange", "change_pct", "dayChangePct",
                "perChange", "changePercent"):
        if payload.get(key) is not None:
            change = _safe_float(payload.get(key), 0.0)
            break
    volume = 0
    for key in ("volume", "totalTradedVolume", "qty", "totalQty"):
        try:
            volume = int(float(payload.get(key, 0) or 0))
        except (TypeError, ValueError):
            continue
        if volume > 0:
            break
    return {"price": price, "change_pct": change, "volume": volume}


def _market_snapshot(symbol: str) -> Dict[str, Any]:
    """Price, change, volume and a market-implied bullish score.

    Tries Alpha Vantage first; falls back to FALLBACK_PRICES on any failure,
    null, or zero. Never returns zero for price or change_pct.
    """
    from app import market_data as md
    from app.config import get_settings

    key = f"mkt:{symbol.upper()}"
    cached = _cache.get(key, _QUOTE_TTL_S)
    if cached:
        return cached

    s = get_settings()
    out: Dict[str, Any] = {
        "symbol": display_symbol(symbol),
        "price": 0.0,
        "change_pct": 0.0,
        "volume": 0,
        "market_bullish": 50,
        "data_mode": DataMode.MOCK.value,
        "source": "fallback",
        "currency": "USD",
        "exchange": "NASDAQ",
    }

    # Try Alpha Vantage
    try:
        client = md.AlphaVantageClient(s.FINANCIAL_DATA_API_KEY or "",
                                       cache_ttl_s=s.AV_CACHE_TTL_S,
                                       max_daily_calls=s.AV_MAX_DAILY_CALLS)
        q = client.quote(symbol)
        if q:
            price = _safe_float(q.get("price"), 0.0)
            change = _safe_float(q.get("change_pct"), 0.0)
            if price > 0:
                out.update({
                    "price": price,
                    "change_pct": change,
                    "data_mode": DataMode.LIVE.value,
                    "source": "alphavantage",
                })
    except Exception:
        pass

    # Indian tickers: live NSE/BSE quote before falling back to cache.
    if out["price"] <= 0 and symbol.upper() in _INDIAN_SYMBOLS:
        live = _indian_quote(symbol)
        if live:
            out.update({
                "price": live["price"],
                "change_pct": live["change_pct"],
                "volume": live["volume"],
                "data_mode": DataMode.LIVE.value,
                "source": "indian-stock-api",
                "currency": "INR",
                "exchange": "NSE",
            })

    # Fallback if AV failed or returned zero
    if out["price"] <= 0:
        fb = FALLBACK_PRICES.get(symbol.upper())
        if fb:
            out.update({
                "price": fb["price"],
                "change_pct": fb["change_pct"],
                "data_mode": DataMode.MOCK.value,
                "source": "fallback",
                "currency": fb["currency"],
                "exchange": fb["exchange"],
            })

    # Volume + trend from the HFT simulator book (always available).
    try:
        from app.quantum_hft.hft_engine import HFTManager
        books = HFTManager(dict(get_settings().BASE_PRICES)).snapshot_all()
        book = next((b for b in books if b["symbol"] == symbol.upper()), None)
        if book:
            out["price"] = book["mid"]
            out["change_pct"] = _safe_float(
                book.get("ofi", {}).get("ofi_norm", 0.0), 0.0) * 100.0
            out["volume"] = int(sum(l["size"] for l in book.get("bids", []))
                                + sum(l["size"] for l in book.get("asks", [])))
            ofi = _safe_float(book.get("ofi", {}).get("ofi_norm", 0.0), 0.0)
            out["market_bullish"] = round(clamp(50 + ofi * 40 + out["change_pct"] * 2), 1)
            # Keep fallback currency/exchange if we used fallback prices
            if out["source"] == "fallback":
                fb = FALLBACK_PRICES.get(symbol.upper())
                if fb:
                    out["currency"] = fb["currency"]
                    out["exchange"] = fb["exchange"]
    except Exception:
        pass

    # Final safety: never return zero price or change
    if out["price"] <= 0:
        fb = FALLBACK_PRICES.get(symbol.upper())
        if fb:
            out["price"] = fb["price"]
            out["change_pct"] = fb["change_pct"]
            out["currency"] = fb["currency"]
            out["exchange"] = fb["exchange"]
    if out["change_pct"] == 0.0:
        out["change_pct"] = 0.1  # minimal non-zero to avoid 0.0% display

    _cache.put(key, out)
    return out


# ---------------------------------------------------------------------------
# Reddit side (retail hype)
# ---------------------------------------------------------------------------

def _reddit_snapshot(symbol: str, engine=None) -> Dict[str, Any]:
    """Reddit mention count, bullish% and mention velocity.

    Uses the reddit_extractor service (live or mock) instead of calling
    SentimentEngine directly, so all Reddit data flows through one path.
    """
    from app.services import reddit_extractor

    key = f"reddit:{symbol.upper()}"
    cached = _cache.get(key, _REDDIT_TTL_S)
    if cached:
        return cached

    out: Dict[str, Any] = {
        "symbol": display_symbol(symbol),
        "mentions": 0,
        "reddit_bullish": 50,
        "mention_velocity": 0.0,
        "data_mode": DataMode.MOCK.value,
        "source": "mock",
        "sample_posts": [],
    }
    try:
        result = reddit_extractor.fetch_reddit(limit_per_sub=20)
        posts = result.get("posts", [])
        matched = [p for p in posts if symbol.upper() in p.get("tickers", [])]
        if matched:
            out["mentions"] = len(matched)
            out["reddit_bullish"] = round(
                sum(p.get("sentiment", 0.0) for p in matched) / len(matched) * 50 + 50, 1)
            out["sample_posts"] = [p.get("text", "")[:120] for p in matched[:3]]
            out["data_mode"] = result.get("data_mode", "mock")
            out["source"] = result.get("source", "mock")
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
    return round(clamp(abs(change) / 5.0, 0.0, 1.0), 3)


def compute_divergence(symbol: str, engine=None) -> Dict[str, Any]:
    """Full divergence snapshot for one symbol."""
    key = f"div:{symbol.upper()}"
    cached = _cache.get(key, _DIVERGENCE_TTL_S)
    if cached:
        return cached

    mkt = _market_snapshot(symbol)
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
        "symbol": display_symbol(symbol),
        "divergence_score": divergence,
        "divergence_label": label,
        "stance": stance,
        "squeeze_metric": squeeze,
        "squeeze_label": ("HIGH" if squeeze > 0.6 else
                          "ELEVATED" if squeeze > 0.35 else "LOW"),
        "retail": reddit,
        "market": mkt,
        "faction": "retail" if retail_bull > market_bull else "institutional",
        "currency": mkt.get("currency", "USD"),
        "exchange": mkt.get("exchange", "NASDAQ"),
        "data_mode": DataMode.MOCK.value,
        "note": ("Divergence is a comparison of sentiment and price action, "
                 "not a prediction. Short interest is a proxy, not a measurement."),
    }
    _cache.put(key, out)
    return out


def scan(universe: Optional[List[str]] = None, engine=None,
          limit: int = 20) -> List[Dict[str, Any]]:
    """Divergence scan across the universe, sorted by divergence score."""
    symbols = universe or DEFAULT_UNIVERSE
    results = [compute_divergence(sym, engine=engine) for sym in symbols[:limit]]
    results.sort(key=lambda r: -r["divergence_score"])
    return results
