"""
QuantPulse AI — News Catalyst Engine.

Fetches live financial headlines via the Alpha Vantage NEWS_SENTIMENT
function and tags each with AI sentiment (Bullish/Bearish/Neutral) so the UI
can show *what is driving* the institutional flow or the retail hype.

Aggressive caching keeps every call inside the free tier. The existing
AlphaVantageClient owns the pacing + circuit breaker, so this module never
makes a raw HTTP call of its own.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.models.common import clamp
from app.models.enums import DataMode

_NEWS_TTL_S = 300.0
_TICKER_TICKERS = ("NVDA", "TSLA", "AAPL", "AMD", "MSFT", "GOOGL", "META",
                   "INTC", "AMZN", "SPY", "QQQ", "MSFT")


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


_cache = _Cache()


def clear_caches() -> None:
    _cache.clear()


def _sentiment_tag(score: float) -> str:
    if score > 0.15:
        return "Bullish"
    if score < -0.15:
        return "Bearish"
    return "Neutral"


def _tickers_in(text: str) -> List[str]:
    blob = text.upper()
    return [t for t in _TICKER_TICKERS if t in blob]


def _score_text(text: str) -> float:
    """Lightweight lexicon scoring. VADER when available."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return float(SentimentIntensityAnalyzer().polarity_scores(text).get("compound", 0.0))
    except Exception:
        pass
    bull = {"moon", "bull", "buy", "calls", "long", "beat", "upgrade", "breakout",
            "squeeze", "gains", "rip", "pump", "ath", "bullish", "surge", "rally"}
    bear = {"dump", "bear", "sell", "puts", "short", "miss", "downgrade", "crash",
            "rug", "tank", "dip", "bearish", "fud", "plunge", "selloff"}
    words = set(text.lower().split())
    b = len(words & bull)
    s = len(words & bear)
    if b == 0 and s == 0:
        return 0.0
    return (b - s) / max(b + s, 1)


def fetch_news(symbols: Optional[List[str]] = None,
                limit: int = 12) -> Dict[str, Any]:
    """Live news for the given symbols (or the whole universe).

    Returns items with ticker, headline, url, source, published_at,
    sentiment_score, sentiment_tag and faction ('retail' if the headline
    names a high-divergence ticker, 'institutional' otherwise).
    """
    key = f"news:{','.join(sorted(symbols or []))}:{limit}"
    cached = _cache.get(key, _NEWS_TTL_S)
    if cached:
        return cached

    from app import market_data as md
    from app.config import get_settings
    from app.services.divergence_engine import scan

    s = get_settings()
    target = symbols or list(getattr(s, "BASE_PRICES", {}).keys())

    # Divergence scan so the news engine knows which tickers are "hot".
    hot: Dict[str, float] = {}
    try:
        for row in scan(engine=None, limit=20):
            hot[row["symbol"]] = row["divergence_score"]
    except Exception:
        pass

    items: List[Dict[str, Any]] = []
    mode = DataMode.MOCK
    source_label = "mock wire"

    try:
        client = md.AlphaVantageClient(s.FINANCIAL_DATA_API_KEY or "",
                                       cache_ttl_s=s.AV_CACHE_TTL_S,
                                       max_daily_calls=s.AV_MAX_DAILY_CALLS)
        data = client._get({"function": "NEWS_SENTIMENT",
                            "tickers": ",".join(target[:5])})
        if data and "feed" in data:
            mode = DataMode.LIVE
            source_label = "alphavantage"
            for raw in data["feed"][:limit * 2]:
                title = str(raw.get("title", "")).strip()
                if not title:
                    continue
                summary = str(raw.get("summary", ""))
                text = f"{title} {summary}"
                score = _score_text(text)
                tickers = _tickers_in(text)
                faction = ("retail" if any(hot.get(t, 0) > 30 for t in tickers)
                           else "institutional")
                items.append({
                    "title": title[:200],
                    "url": raw.get("url", ""),
                    "source": raw.get("source", ""),
                    "published_at": raw.get("time_published", ""),
                    "summary": summary[:300],
                    "tickers": tickers,
                    "sentiment_score": round(score, 3),
                    "sentiment_tag": _sentiment_tag(score),
                    "faction": faction,
                    "data_mode": mode.value,
                })
                if len(items) >= limit:
                    break
    except Exception:
        pass

    if not items:
        # Deterministic mock news so the section is never empty. Labelled MOCK.
        mock_headlines = [
            ("NVDA", "Nvidia orders accelerate as AI capex guidance rises"),
            ("TSLA", "Tesla deliveries miss street estimates; margins compress"),
            ("AAPL", "Apple services growth steadies; iPhone cycle improves"),
            ("AMD", "AMD gains ground in data-center GPU market"),
            ("MSFT", "Microsoft cloud growth re-accelerates; AI workloads rise"),
            ("GOOGL", "Alphabet ad revenue beats; search engagement grows"),
            ("META", "Meta capex squeeze continues; ad pricing improves"),
            ("INTC", "Intel foundry losses narrow; backlog builds"),
            ("AMZN", "Amazon margins expand on logistics efficiency"),
            ("NVDA", "Reddit sentiment for Nvidia hits euphoria as analysts raise targets"),
        ]
        rng = _MockRng()
        for sym, title in mock_headlines[:limit]:
            score = rng.uniform(-0.4, 0.5)
            items.append({
                "title": title,
                "url": "",
                "source": "QuantPulse mock wire",
                "published_at": "",
                "summary": "Synthetic headline for offline demonstration.",
                "tickers": [sym],
                "sentiment_score": score,
                "sentiment_tag": "Bullish" if score > 0 else "Bearish" if score < 0 else "Neutral",
                "faction": "retail" if hot.get(sym, 0) > 30 else "institutional",
                "data_mode": DataMode.MOCK.value,
            })

    return {
        "items": items,
        "count": len(items),
        "symbols": target,
        "hot_divergence": hot,
        "data_mode": mode.value,
        "source": source_label,
        "cached_for_s": _NEWS_TTL_S,
        "note": ("News sentiment is lexicon/VADER scoring of headlines. "
                 "Faction is inferred from the divergence scan, not from the "
                 "publisher. Always verify before acting."),
    }


class _MockRng:
    def __init__(self) -> None:
        self._state = 42

    def uniform(self, lo: float, hi: float) -> float:
        self._state = (self._state * 1103515245 + 12345) & 0x7FFFFFFF
        return lo + (hi - lo) * (self._state / 0x7FFFFFFF)
