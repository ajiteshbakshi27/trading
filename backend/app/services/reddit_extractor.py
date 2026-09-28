"""
QuantPulse AI — Reddit Data Extractor.

Fetches r/wallstreetbets, r/stocks, r/options posts via Reddit's public
JSON endpoints (no auth required, rate-limited). Falls back to deterministic
mock posts when Reddit is unreachable or rate-limited.

Every post is scored with the same lexicon/VADER pipeline as the main
sentiment engine, so Reddit data flows directly into the divergence and
thesis stress models.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

import httpx

SUBREDDITS = ["wallstreetbets", "stocks", "options", "pennystocks"]
UA = {"User-Agent": "QuantPulseAI/1.0 (research; contact: trader@quantpulse.ai)"}

#: Cache TTL — Reddit rate-limits unauthenticated requests hard.
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
# Fetching
# ---------------------------------------------------------------------------

def _fetch_subreddit(sub: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Fetch hot posts from a subreddit via public JSON endpoint."""
    url = f"https://www.reddit.com/r/{sub}/hot.json?limit={limit}"
    try:
        r = httpx.get(url, headers=UA, timeout=10.0, follow_redirects=True)
        if r.status_code != 200:
            return []
        data = r.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            title = str(d.get("title", "")).strip()
            if not title:
                continue
            posts.append({
                "id": d.get("id", ""),
                "title": title,
                "selftext": str(d.get("selftext", ""))[:500],
                "upvotes": int(d.get("score", 0) or 0),
                "comments": int(d.get("num_comments", 0) or 0),
                "subreddit": sub,
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "created_utc": float(d.get("created_utc", 0) or 0),
            })
        return posts
    except Exception:
        return []


def fetch_reddit(
    subreddits: Optional[List[str]] = None,
    limit_per_sub: int = 25,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Fetch posts from multiple subreddits. Cached to respect rate limits."""
    subs = subreddits or SUBREDDITS
    cache_key = f"reddit:{','.join(subs)}:{limit_per_sub}"
    if use_cache:
        cached = _cache.get(cache_key, _TTL_S)
        if cached:
            return cached

    all_posts: List[Dict[str, Any]] = []
    live = False
    for sub in subs:
        posts = _fetch_subreddit(sub, limit_per_sub)
        if posts:
            live = True
        all_posts.extend(posts)
        time.sleep(0.5)  # pace between subreddits

    if not all_posts:
        all_posts = _mock_posts()

    # Score each post
    for post in all_posts:
        text = f"{post['title']} {post['selftext']}"
        post["sentiment"] = round(_score_text(text), 3)
        post["tickers"] = _extract_tickers(text)

    result = {
        "posts": all_posts,
        "count": len(all_posts),
        "subreddits": subs,
        "data_mode": "live" if live else "mock",
        "source": "reddit" if live else "mock",
        "note": ("Live Reddit data" if live else
                 "Reddit unreachable or rate-limited; using mock posts."),
    }
    _cache.put(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Scoring (same pipeline as sentiment_agent)
# ---------------------------------------------------------------------------

_BULL = {"moon", "bull", "buy", "calls", "long", "beat", "upgrade", "breakout",
         "squeeze", "gains", "rip", "pump", "ath", "bullish", "surge", "rally",
         "tendies", "diamond", "hands", "yolo", "all in", "undervalued"}
_BEAR = {"dump", "bear", "sell", "puts", "short", "miss", "downgrade", "crash",
         "rug", "tank", "dip", "bearish", "fud", "paper", "bag", "overvalued",
         "bubble", "correction", "liquidation"}


def _score_text(text: str) -> float:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        return float(SentimentIntensityAnalyzer().polarity_scores(text).get("compound", 0.0))
    except Exception:
        pass
    words = set(re.findall(r"\b\w+\b", text.lower()))
    b = len(words & _BULL)
    s = len(words & _BEAR)
    if b == 0 and s == 0:
        return 0.0
    return (b - s) / max(b + s, 1)


def _extract_tickers(text: str) -> List[str]:
    return [t.upper() for t in re.findall(r"\$?([A-Z]{2,5})\b", text)]


# ---------------------------------------------------------------------------
# Mock fallback (deterministic, realistic)
# ---------------------------------------------------------------------------

def _mock_posts() -> List[Dict[str, Any]]:
    """Deterministic mock Reddit posts for offline mode."""
    mock = [
        ("NVDA", "Nvidia earnings beat, datacenter moon! $NVDA calls printing", 4821, 342),
        ("TSLA", "$TSLA deliveries miss, puts city. Selling into hype", 1932, 218),
        ("AMD", "$AMD breakout above resistance, volume insane, long", 874, 95),
        ("AAPL", "$AAPL upgrade by street, steady buy and hold", 654, 41),
        ("META", "$META AI capex squeeze bears, squeeze incoming?", 2310, 187),
        ("MSFT", "$MSFT Azure growth slows, mild sell risk", 402, 33),
        ("GOOGL", "$GOOGL search moat intact, bullish long term", 511, 28),
        ("INTC", "$INTC foundry dump continues, avoid", 233, 19),
        ("AMZN", "$AMZN e-commerce margins surprise to the upside", 720, 55),
        ("SPY", "$SPY melt-up, everyone 100% bullish — contrarian alarm", 1540, 120),
        ("RELIANCE", "Reliance Jio IPO next? Retail bulls loading up", 3200, 250),
        ("TATAMOTORS", "Tata Motors EV order book explodes, long term hold", 2100, 180),
        ("INFY", "Infosys deal wins accelerate, IT sector bottoming?", 1800, 140),
    ]
    out = []
    for i, (sym, title, upvotes, comments) in enumerate(mock):
        out.append({
            "id": f"mock_{i}",
            "title": title,
            "selftext": "",
            "upvotes": upvotes,
            "comments": comments,
            "subreddit": "wallstreetbets" if i < 10 else "stocks",
            "url": "",
            "created_utc": time.time() - i * 3600,
        })
    return out
