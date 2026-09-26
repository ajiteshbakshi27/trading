"""
QuantPulse AI — Normalized feed layer for the research loop.

The five new features must not each grow their own Reddit/X/Alpaca client.
Everything they read passes through here, which guarantees one place owns
credential handling, caching and the LIVE/MOCK/SIMULATED label.

Upstream providers, all optional:
  * market prices  -> app.market_data.AlphaVantageClient / streaming.StreamClient
  * order flow     -> app.quantum_hft.hft_engine.HFTManager
  * social         -> app.agents.sentiment_agent.SentimentEngine (reddit live/mock)
  * prediction mkt -> app.agents.prediction_agent.PredictionAgent
  * news           -> yfinance per-ticker + public RSS (no key required)

Every accessor returns `(payload, data_mode)`. It never raises into a request
path and never returns a live label for simulator data.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.common import fingerprint, iso
from app.models.enums import DataMode

_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")

# Public market-news RSS feeds. No API key, no rate-limit contract to break.
RSS_FEEDS: Tuple[Tuple[str, str], ...] = (
    ("CNBC Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml"
                      "?partnerId=wrss01&id=20910258"),
    ("MarketWatch Top", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
)

# Headlines are matched to tickers by name/alias, not by keyword guessing.
SYMBOL_ALIASES: Dict[str, Tuple[str, ...]] = {
    "NVDA": ("nvidia", "nvda"),
    "AAPL": ("apple", "aapl"),
    "MSFT": ("microsoft", "msft"),
    "TSLA": ("tesla", "tsla"),
    "GOOGL": ("alphabet", "google", "googl"),
    "META": ("meta platforms", "facebook", "meta"),
    "AMD": ("amd", "advanced micro"),
    "INTC": ("intel", "intc"),
    "AMZN": ("amazon", "amzn"),
}

#: Cache TTLs. News is slow-moving; quotes are already cached upstream.
_NEWS_TTL_S = 300.0
_SOCIAL_TTL_S = 120.0


@dataclass
class NewsItem:
    title: str
    url: str = ""
    publisher: str = ""
    published_at: str = ""
    tickers: List[str] = field(default_factory=list)
    summary: str = ""
    data_mode: DataMode = DataMode.MOCK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title[:300],
            "url": self.url,
            "publisher": self.publisher,
            "published_at": self.published_at,
            "tickers": self.tickers,
            "summary": self.summary[:400],
            "data_mode": self.data_mode.value,
            "data_mode_label": self.data_mode.label,
        }


@dataclass
class SocialItem:
    text: str
    source: str
    engagement: int = 0
    tickers: List[str] = field(default_factory=list)
    sentiment: float = 0.0
    posted_at: str = ""
    data_mode: DataMode = DataMode.MOCK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text[:300],
            "source": self.source,
            "engagement": self.engagement,
            "tickers": self.tickers,
            "sentiment": self.sentiment,
            "posted_at": self.posted_at,
            "data_mode": self.data_mode.value,
            "data_mode_label": self.data_mode.label,
        }


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

class _TTLCache:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}

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


_cache = _TTLCache()


def clear_caches() -> None:
    """Test hook / manual refresh."""
    _cache.clear()


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def _match_tickers(*texts: str) -> List[str]:
    blob = " ".join(t for t in texts if t).lower()
    found: List[str] = []
    for sym, aliases in SYMBOL_ALIASES.items():
        if any(a in blob for a in aliases):
            found.append(sym)
    return sorted(found)


def _rss_items(limit: int) -> List[NewsItem]:
    """Parse public RSS. Returns [] on any failure (mock fallback applies)."""
    import httpx
    import xml.etree.ElementTree as ET

    out: List[NewsItem] = []
    for publisher, url in RSS_FEEDS:
        try:
            r = httpx.get(url, timeout=6.0, follow_redirects=True,
                          headers={"User-Agent": "QuantPulseAI/1.0 (+research)"})
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
        except Exception:
            continue
        for node in root.iter():
            tag = node.tag.split("}")[-1]
            if tag != "item":
                continue
            title = link = desc = pub = ""
            for child in node:
                ctag = child.tag.split("}")[-1]
                text = (child.text or "").strip()
                if ctag == "title":
                    title = text
                elif ctag == "link":
                    link = text
                elif ctag == "description":
                    desc = re.sub(r"<[^>]+>", " ", text).strip()
                elif ctag == "pubDate":
                    pub = text
            if not title:
                continue
            tickers = _match_tickers(title, desc)
            if not tickers:
                continue  # a US-markets feed entry with no tracked ticker
            out.append(NewsItem(
                title=title, url=link, publisher=publisher, summary=desc,
                published_at=_rfc_to_iso(pub) or iso(),
                tickers=tickers, data_mode=DataMode.LIVE,
            ))
            if len(out) >= limit * 3:
                break
        if len(out) >= limit * 3:
            break
    return out


def _rfc_to_iso(value: str) -> str:
    if not value:
        return ""
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except Exception:
        return value


def _yfinance_news(symbols: List[str]) -> List[NewsItem]:
    try:
        import yfinance as yf
    except ImportError:
        return []
    out: List[NewsItem] = []
    for sym in symbols:
        try:
            for raw in (yf.Ticker(sym).news or [])[:6]:
                content = raw.get("content", raw) or {}
                title = str(content.get("title", "")).strip()
                if not title:
                    continue
                stamp = content.get("pubDate") or content.get("displayTime")
                published = ""
                if isinstance(stamp, int):
                    published = iso(stamp)
                elif isinstance(stamp, str):
                    published = stamp
                provider = (content.get("provider") or {}) or {}
                out.append(NewsItem(
                    title=title,
                    url=str((content.get("canonicalUrl") or {}).get("url", "")),
                    publisher=str(provider.get("displayName", "Yahoo Finance")),
                    published_at=published or iso(),
                    tickers=[sym],
                    summary=str(content.get("summary", ""))[:400],
                    data_mode=DataMode.LIVE,
                ))
        except Exception:
            continue
    return out


_MOCK_HEADLINES = [
    ("Chipmaker guides above consensus as data-centre demand accelerates", "NVDA"),
    ("Hyperscaler capex guidance lifted for the quarter", "MSFT"),
    ("Cloud unit growth steadies; margins expand", "GOOGL"),
    ("E-commerce margins surprise to the upside on logistics costs", "AMZN"),
    ("Smartphone demand improves; services mix rises", "AAPL"),
    ("EV price cuts continue; deliveries miss the high end", "TSLA"),
    ("Accelerated-computing orders accelerate again", "AMD"),
    ("Foundry losses narrow; capital spending trimmed", "INTC"),
    ("Ad platform revenue beats; engagement growth steadies", "META"),
    ("Treasury yields slip as the market prices a policy shift", "SPY"),
]


def mock_news(limit: int = 12, seed_offset: int = 0) -> List[NewsItem]:
    """Deterministic headlines. Labelled MOCK — never presented as real."""
    now = time.time()
    out: List[NewsItem] = []
    for i in range(limit):
        title, sym = _MOCK_HEADLINES[(i + seed_offset) % len(_MOCK_HEADLINES)]
        out.append(NewsItem(
            title=title, publisher="QuantPulse mock wire",
            published_at=iso(now - (i * 420)),
            tickers=[sym], summary="Synthetic headline for offline demonstration.",
            data_mode=DataMode.MOCK,
        ))
    return out


def get_news(symbol: Optional[str] = None, limit: int = 12) -> Tuple[List[NewsItem], DataMode]:
    """Live news where reachable; deterministic mock otherwise. Never raises."""
    key = f"news:{symbol or 'ALL'}:{limit}"
    cached = _cache.get(key, _NEWS_TTL_S)
    if cached:
        return cached

    items = _yfinance_news([symbol.upper()]) if symbol else _rss_items(limit)
    if not items and not symbol:
        items = _rss_items(limit)
    if items:
        items.sort(key=lambda n: n.published_at, reverse=True)
        if symbol:
            items = [n for n in items if symbol.upper() in n.tickers] or items
        result = (items[:limit], DataMode.LIVE)
    else:
        result = (mock_news(limit), DataMode.MOCK)
    _cache.put(key, result)
    return result


# ---------------------------------------------------------------------------
# Social
# ---------------------------------------------------------------------------

def get_social(symbol: Optional[str] = None, limit: int = 20,
               engine=None) -> Tuple[List[SocialItem], DataMode]:
    """Normalized social stream from the existing SentimentEngine.

    `engine` is the app-level SentimentEngine instance; when omitted the
    caller falls back to a locally constructed one. Live Reddit requires
    credentials; the mode label reflects what actually answered.
    """
    from app.agents.sentiment_agent import SentimentEngine
    from app.config import get_settings

    eng = engine or SentimentEngine()
    s = get_settings()
    key = f"social:{symbol or 'ALL'}:{limit}:{int(s.has_reddit)}:{int(s.has_twitter)}"
    cached = _cache.get(key, _SOCIAL_TTL_S)
    if cached:
        return cached

    mode = DataMode.MOCK
    posts: List[Dict[str, Any]] = []
    if s.has_reddit:
        try:
            posts = eng.reddit_live(s.REDDIT_CLIENT_ID, s.REDDIT_CLIENT_SECRET,
                                    limit=max(5, limit // 2))
            if posts:
                mode = DataMode.LIVE
        except Exception:
            posts = []
    if not posts:
        posts = eng.reddit_mock(limit=max(5, limit // 2)) + eng.twitter_mock(
            limit=max(5, limit // 2))
        mode = DataMode.MOCK

    now = time.time()
    items: List[SocialItem] = []
    for i, p in enumerate(posts):
        if symbol and symbol.upper() not in [t.upper() for t in p.get("tickers", [])]:
            continue
        items.append(SocialItem(
            text=p.get("text", ""),
            source=p.get("source", "social"),
            engagement=int(p.get("upvotes", p.get("likes", 0)) or 0),
            tickers=[t.upper() for t in p.get("tickers", [])],
            sentiment=float(p.get("sentiment", 0.0) or 0.0),
            posted_at=iso(now - i * 45),
            data_mode=mode,
        ))
        if len(items) >= limit:
            break
    result = (items, mode)
    _cache.put(key, result)
    return result


# ---------------------------------------------------------------------------
# Prediction markets
# ---------------------------------------------------------------------------

def get_prediction_markets(agent=None) -> Tuple[List[Dict[str, Any]], DataMode]:
    """Existing PredictionAgent feed, labelled by actual source."""
    from app.agents.prediction_agent import PredictionAgent
    from app.config import get_settings

    s = get_settings()
    live = bool(s.KALSHI_API_KEY or s.POLYMARKET_API_KEY)
    ag = agent or PredictionAgent()
    try:
        markets = ag.fetch_mock()
    except Exception:
        markets = []
    return markets, (DataMode.LIVE if (live and markets) else DataMode.MOCK)


# ---------------------------------------------------------------------------
# Historical prices (used by transmission history + tournament windows)
# ---------------------------------------------------------------------------

def get_history(symbol: str, period: str = "6mo") -> Tuple[Optional[Any], DataMode]:
    """Daily OHLCV frame from yfinance, or (None, MOCK) when unreachable.

    No API key needed. Returns a pandas DataFrame when available so the
    forecast and historical-response code can compute real numbers; callers
    must treat None as INSUFFICIENT DATA, never substitute invented values.
    """
    key = f"hist:{symbol.upper()}:{period}"
    cached = _cache.get(key, 900.0)
    if cached is not None:
        return cached
    try:
        import yfinance as yf
        frame = yf.Ticker(symbol.upper()).history(period=period,
                                                  auto_adjust=True)
        if frame is not None and len(frame) >= 20:
            result = (frame, DataMode.LIVE)
            _cache.put(key, result)
            return result
    except Exception:
        pass
    return (None, DataMode.MOCK)


def get_intraday_returns(symbol: str, days: int = 1) -> Tuple[Optional[List[float]], DataMode]:
    """Intraday percentage returns, used for realized-vol and hit-rate work."""
    frame, mode = get_history(symbol, period="5d")
    if frame is None:
        return (None, DataMode.MOCK)
    try:
        import numpy as np
        close = frame["Close"].astype(float).values
        if len(close) < 5:
            return (None, DataMode.MOCK)
        rets = np.diff(close) / close[:-1] * 100.0
        return ([float(r) for r in rets[-days:]], mode)
    except Exception:
        return (None, DataMode.MOCK)


def feed_health() -> Dict[str, Any]:
    """Compact provenance report for the research surfaces."""
    from app.config import get_settings
    s = get_settings()
    try:
        from app.streaming import StreamClient  # noqa: F401
    except Exception:
        pass
    return {
        "feeds": s.feed_status(),
        "has_reddit": s.has_reddit,
        "has_twitter": s.has_twitter,
        "has_financial_data": s.has_financial_data,
        "history_provider": "yfinance",
        "note": "Research services read through this layer only.",
    }
