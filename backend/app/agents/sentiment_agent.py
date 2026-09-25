"""
QuantPulse AI - Unified Sentiment Agent (Reddit + X/Twitter)
Live API when keys exist; deterministic mock feed otherwise.
Sentiment: VADER if installed, else lightweight lexicon fallback.
"""
from __future__ import annotations
import re
import random
from typing import List, Dict, Optional, ClassVar
from dataclasses import dataclass

TICKER_RE = re.compile(r"\$?([A-Z]{2,5})\b")
SUBREDDITS = ["wallstreetbets", "stocks", "options"]

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
    HAS_VADER = True
except ImportError:
    HAS_VADER = False

_BULL = {"moon", "bull", "buy", "calls", "long", "beat", "upgrade", "breakout",
         "squeeze", "gains", "rip", "pump", "ath", "bullish"}
_BEAR = {"dump", "bear", "sell", "puts", "short", "miss", "downgrade", "crash",
         "rug", "tank", "dip", "bearish", "fud"}


def score_text(text: str) -> float:
    """Return compound sentiment in [-1, 1]."""
    if HAS_VADER:
        try:
            return float(_VADER.polarity_scores(text).get("compound", 0.0))
        except Exception:
            pass
    t = text.lower()
    b = sum(1 for w in _BULL if w in t)
    s = sum(1 for w in _BEAR if w in t)
    if b == 0 and s == 0:
        return 0.0
    return (b - s) / max(b + s, 1)


MOCK_POSTS = [
    ("NVDA earnings beat, datacenter moon! $NVDA calls printing", "wallstreetbets", 4821),
    ("$TSLA deliveries miss, puts city. Selling into hype", "stocks", 1932),
    ("$AMD breakout above resistance, volume insane, long", "options", 874),
    ("$AAPL upgrade by street, steady buy and hold", "stocks", 654),
    ("$META AI capex squeeze bears, squeeze incoming?", "wallstreetbets", 2310),
    ("$MSFT Azure growth slows, mild sell risk", "stocks", 402),
    ("$GOOGL search moat intact, bullish long term", "stocks", 511),
    ("$INTC foundry dump continues, avoid", "stocks", 233),
]
MOCK_TWEETS = [
    "$NVDA to $200? Crowd euphoria building fast",
    "$TSLA robotaxi hype vs weak order flow, careful",
    "$AMD momentum + unusual call flow",
    "$SPY melt-up, everyone 100% bullish — contrarian alarm",
    "$AAPL quiet accumulation, smart money bidding",
]


def extract_tickers(text: str, universe: List[str]) -> List[str]:
    found = set(TICKER_RE.findall(text.upper()))
    return sorted([t for t in found if t in set(universe)])


@dataclass
class SentimentEngine:
    universe: List[str] = None

    def __post_init__(self):
        if self.universe is None:
            self.universe = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "META", "AMD", "INTC"]

    def reddit_mock(self, limit: int = 20) -> List[Dict]:
        out = []
        for i in range(limit):
            txt, sub, votes = random.choice(MOCK_POSTS)
            votes = int(votes * random.uniform(0.7, 1.3))
            tickers = extract_tickers(txt, self.universe) or [random.choice(self.universe)]
            out.append({"source": f"r/{sub}", "text": txt, "upvotes": votes,
                        "tickers": tickers, "sentiment": round(score_text(txt), 3)})
        return out

    def twitter_mock(self, limit: int = 20) -> List[Dict]:
        out = []
        for _ in range(limit):
            txt = random.choice(MOCK_TWEETS)
            tickers = extract_tickers(txt, self.universe) or [random.choice(self.universe)]
            out.append({"source": "X", "text": txt,
                        "likes": random.randint(10, 5000), "tickers": tickers,
                        "sentiment": round(score_text(txt), 3)})
        return out

    def aggregate(self, reddit_limit: int = 15, twitter_limit: int = 15,
                  posts: Optional[List[Dict]] = None) -> Dict:
        if posts is None:
            posts = self.reddit_mock(reddit_limit) + self.twitter_mock(twitter_limit)
        by_ticker: Dict[str, Dict] = {}
        for p in posts:
            w = 1 + min(p.get("upvotes", p.get("likes", 1)), 5000) / 1000.0
            for t in p["tickers"]:
                d = by_ticker.setdefault(t, {"count": 0, "wsum": 0.0, "wtot": 0.0})
                d["count"] += 1
                d["wsum"] += p["sentiment"] * w
                d["wtot"] += w
        agg = {}
        for t, d in by_ticker.items():
            avg = d["wsum"] / max(d["wtot"], 1e-9)
            # bullish_pct proxy: map [-1,1] -> [0,100]
            bull = round((avg + 1) / 2 * 100, 1)
            agg[t] = {"mentions": d["count"], "sentiment": round(avg, 3),
                      "bullish_pct": bull,
                      "label": "EUPHORIA" if bull > 90 else "BULLISH" if bull > 60
                               else "BEARISH" if bull < 40 else "NEUTRAL"}
        return {"posts": posts[:30], "by_ticker": agg}

    # Live hooks (graceful fallback to mock). Live Reddit responses are
    # cached so polling snapshot() doesn't hammer the API every second.
    # ClassVar: shared class state, not dataclass fields.
    _reddit_cache: ClassVar[List[Dict]] = []
    _reddit_ts: ClassVar[float] = 0.0
    _REDDIT_TTL_S: ClassVar[float] = 120.0

    def reddit_live(self, client_id: Optional[str], secret: Optional[str],
                    limit: int = 10) -> List[Dict]:
        import time
        now = time.time()
        if self._reddit_cache and now - self._reddit_ts < self._REDDIT_TTL_S:
            return self._reddit_cache
        if not client_id or not secret:
            return self.reddit_mock()
        try:
            import praw
            reddit = praw.Reddit(client_id=client_id, client_secret=secret,
                                 user_agent="QuantPulse AI v1.0")
            out = []
            for sub in SUBREDDITS:
                for post in reddit.subreddit(sub).hot(limit=limit):
                    txt = f"{post.title} {post.selftext[:300]}"
                    out.append({"source": f"r/{sub}", "text": txt[:400],
                                "upvotes": post.score,
                                "tickers": extract_tickers(txt, self.universe),
                                "sentiment": round(score_text(txt), 3)})
            result = out or self.reddit_mock()
            self._reddit_cache, self._reddit_ts = result, now
            return result
        except Exception:
            return self.reddit_mock()
