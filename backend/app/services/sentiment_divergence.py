"""
QuantPulse AI — Cross-Platform Sentiment Divergence.

Measures how much sentiment *disagrees across platforms* for the same ticker.
Reddit may be euphoric while X is neutral and the prediction market is bearish —
that disagreement is itself a signal.

Outputs per symbol:
  * divergence_score — 0..1, how far apart the platforms are
  * outlier_platform — which platform disagrees most with the others
  * retail_split — e.g. "Reddit 86% bull vs X 57% bull"
  * per_platform — the raw sentiment from each source

All values are labelled MOCK unless a live credential produced them.
"""
from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional

from app.models.common import clamp
from app.models.enums import DataMode

#: Cache TTL — social sentiment is slow-moving.
_TTL_S = 120.0


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


# ---------------------------------------------------------------------------
# Per-platform sentiment collection
# ---------------------------------------------------------------------------

def _reddit_sentiment(symbol: str, engine=None) -> Dict[str, Any]:
    from app.agents.sentiment_agent import SentimentEngine
    from app.config import get_settings

    s = get_settings()
    eng = engine or SentimentEngine()
    out = {"source": "reddit", "sentiment": 0.0, "bullish_pct": 50.0,
           "mentions": 0, "data_mode": DataMode.MOCK.value}
    try:
        posts = eng.reddit_live(s.REDDIT_CLIENT_ID, s.REDDIT_CLIENT_SECRET, limit=20)
        if not posts:
            posts = eng.reddit_mock(limit=20)
        matched = [p for p in posts if symbol.upper() in p.get("tickers", [])]
        if matched:
            avg = sum(p.get("sentiment", 0.0) for p in matched) / len(matched)
            out.update({
                "sentiment": round(avg, 4),
                "bullish_pct": round(avg * 50 + 50, 1),
                "mentions": len(matched),
                "data_mode": DataMode.LIVE.value if s.has_reddit else DataMode.MOCK.value,
            })
    except Exception:
        pass
    return out


def _x_sentiment(symbol: str, engine=None) -> Dict[str, Any]:
    from app.agents.sentiment_agent import SentimentEngine
    from app.config import get_settings

    s = get_settings()
    eng = engine or SentimentEngine()
    out = {"source": "x", "sentiment": 0.0, "bullish_pct": 50.0,
           "mentions": 0, "data_mode": DataMode.MOCK.value}
    try:
        posts = eng.twitter_mock(limit=20)
        matched = [p for p in posts if symbol.upper() in p.get("tickers", [])]
        if matched:
            avg = sum(p.get("sentiment", 0.0) for p in matched) / len(matched)
            out.update({
                "sentiment": round(avg, 4),
                "bullish_pct": round(avg * 50 + 50, 1),
                "mentions": len(matched),
                "data_mode": DataMode.MOCK.value,
            })
    except Exception:
        pass
    return out


def _prediction_sentiment(symbol: str) -> Dict[str, Any]:
    from app.services.divergence_engine import FALLBACK_PRICES

    out = {"source": "prediction", "sentiment": 0.0, "bullish_pct": 50.0,
           "mentions": 0, "data_mode": DataMode.MOCK.value}
    try:
        from app.agents.prediction_agent import PredictionAgent
        markets = PredictionAgent().fetch_mock()
        matched = [m for m in markets
                   if symbol.upper() in str(m.get("id", "")).upper()
                   or symbol.upper() in str(m.get("question", "")).upper()]
        if matched:
            prob = float(matched[0].get("crowd_prob", 0.5))
            out.update({
                "sentiment": round(prob * 2 - 1, 4),
                "bullish_pct": round(prob * 100, 1),
                "mentions": 1,
                "data_mode": DataMode.MOCK.value,
            })
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Divergence computation
# ---------------------------------------------------------------------------

def compute_divergence(symbol: str, engine=None) -> Dict[str, Any]:
    """Full cross-platform divergence snapshot for one symbol."""
    key = f"xdiv:{symbol.upper()}"
    cached = _cache.get(key, _TTL_S)
    if cached:
        return cached

    reddit = _reddit_sentiment(symbol, engine=engine)
    x = _x_sentiment(symbol, engine=engine)
    prediction = _prediction_sentiment(symbol)

    platforms = [reddit, x, prediction]
    bullish_values = [p["bullish_pct"] for p in platforms]
    sentiments = [p["sentiment"] for p in platforms]

    # Divergence = normalised spread of bullish% across platforms.
    mean_bull = sum(bullish_values) / len(bullish_values)
    variance = sum((b - mean_bull) ** 2 for b in bullish_values) / len(bullish_values)
    std = math.sqrt(variance)
    # Max possible std for 3 values in [0,100] is ~47; normalise to 0..1.
    divergence = round(clamp(std / 47.0), 4)

    # Outlier = platform furthest from the mean.
    outlier = max(platforms, key=lambda p: abs(p["bullish_pct"] - mean_bull))

    # Retail split: Reddit vs X disagreement.
    reddit_bull = reddit["bullish_pct"]
    x_bull = x["bullish_pct"]
    split = f"Reddit {reddit_bull:.0f}% bull vs X {x_bull:.0f}% bull"

    if divergence > 0.4:
        label = "EXTREME platform disagreement"
    elif divergence > 0.2:
        label = "Significant platform disagreement"
    elif divergence > 0.08:
        label = "Moderate platform disagreement"
    else:
        label = "Platforms aligned"

    out = {
        "symbol": symbol.upper(),
        "divergence_score": divergence,
        "divergence_label": label,
        "outlier_platform": outlier["source"],
        "outlier_bullish_pct": outlier["bullish_pct"],
        "retail_split": split,
        "per_platform": platforms,
        "mean_bullish_pct": round(mean_bull, 1),
        "data_mode": DataMode.MOCK.value,
        "note": ("Divergence measures cross-platform sentiment spread. High "
                 "divergence means platforms disagree — one side is likely "
                 "wrong. This is not a prediction."),
    }
    _cache.put(key, out)
    return out


def scan(universe: Optional[List[str]] = None, limit: int = 12) -> List[Dict[str, Any]]:
    """Cross-platform divergence scan, sorted by score."""
    from app.services.divergence_engine import DEFAULT_UNIVERSE
    symbols = universe or DEFAULT_UNIVERSE
    results = [compute_divergence(sym) for sym in symbols[:limit]]
    results.sort(key=lambda r: -r["divergence_score"])
    return results
