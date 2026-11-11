"""
Parakh — Feature 6: hype radar for a user's watchlist.

Compares crowd attention on Indian trading subreddits (r/IndianStreetBets,
r/IndianStockMarket, r/IndiaInvestments, r/DalalStreetTalks) with what price
is actually doing. Divergence between the two is what's interesting:

  * HYPE_NO_PRICE  — crowd excited, price not confirming
  * QUIET_MOVE     — big price move nobody is talking about
  * EUPHORIA       — crowd and price both stretched (crowded long)
  * PANIC          — crowd fearful and price falling hard

Without Reddit API keys, attention is SIMULATED and labelled as such.
Alerts go to the user's Telegram chat (one per symbol+kind per 6 hours).
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import get_settings
from app.core import state_store
from app.parakh import market, store, universe

SUBREDDITS = ["IndianStreetBets", "IndianStockMarket", "IndiaInvestments", "DalalStreetTalks"]
_TTL = 15 * 60
ALERT_COOLDOWN = timedelta(hours=6)


def _score_text(text: str) -> float:
    try:
        from app.agents.sentiment_agent import score_text
        return score_text(text)
    except Exception:
        return 0.0


def _reddit_posts() -> Optional[List[Dict[str, Any]]]:
    s = get_settings()
    if not (s.REDDIT_CLIENT_ID and s.REDDIT_CLIENT_SECRET):
        return None
    cached = state_store.get_json("hype:posts")
    if cached is not None:
        return cached
    try:
        import praw  # type: ignore
        reddit = praw.Reddit(client_id=s.REDDIT_CLIENT_ID, client_secret=s.REDDIT_CLIENT_SECRET,
                             user_agent="parakh-hype-radar/1.0", check_for_async=False)
        posts = []
        for sub in SUBREDDITS:
            for p in reddit.subreddit(sub).new(limit=150):
                posts.append({"t": float(p.created_utc), "text": f"{p.title} {p.selftext[:400]}",
                              "score": int(p.score or 0)})
        state_store.set_json("hype:posts", posts, ttl_s=_TTL)
        return posts
    except Exception:
        return None


def _mentions(symbol: str, posts: List[Dict[str, Any]]) -> Dict[str, float]:
    aliases = [a for a, s in universe.alias_table() if s == symbol and len(a) >= 3]
    now = datetime.now(timezone.utc).timestamp()
    day, week = [], []
    for p in posts:
        t = " " + p["text"].lower() + " "
        if any(f" {a} " in t or f"${a}" in t for a in aliases):
            age_h = (now - p["t"]) / 3600
            if age_h <= 24:
                day.append(p)
            if age_h <= 24 * 7:
                week.append(p)
    base = max(len(week) / 7.0, 0.5)
    sd = math.sqrt(base)                         # Poisson approximation
    sent = sum(_score_text(p["text"]) for p in day) / len(day) if day else 0.0
    return {"mentions_24h": len(day), "baseline_per_day": round(base, 2),
            "attention_z": round((len(day) - base) / sd, 2), "sentiment": round(sent, 3)}


def _simulated_attention(symbol: str) -> Dict[str, float]:
    seed = int(hashlib.sha256(f"{symbol}:{market.utc_today()}".encode()).hexdigest()[:8], 16)
    r = random.Random(seed)
    base = 2 + r.random() * 10
    today = max(0, int(r.gauss(base, math.sqrt(base) * (2.5 if r.random() < 0.15 else 1))))
    return {"mentions_24h": today, "baseline_per_day": round(base, 2),
            "attention_z": round((today - base) / math.sqrt(base), 2),
            "sentiment": round(max(-1, min(1, r.gauss(0.1, 0.35))), 3)}


def scan_symbol(symbol: str) -> Dict[str, Any]:
    sym = universe.normalize(symbol)
    posts = _reddit_posts()
    att = _mentions(sym, posts) if posts is not None else _simulated_attention(sym)
    social_mode = "live" if posts is not None else "simulated"
    bars, price_mode = market.history(sym, 120)
    cl = market.closes(bars)
    dvol = market.stdev(market.daily_returns(cl[-61:])) or 0.015
    r1 = cl[-1] / cl[-2] - 1 if len(cl) > 1 else 0.0
    r5 = cl[-1] / cl[-6] - 1 if len(cl) > 5 else 0.0
    price_z = round(max(abs(r1) / dvol, abs(r5) / (dvol * math.sqrt(5))) * (1 if (r5 or r1) >= 0 else -1), 2)
    hz, s = att["attention_z"], att["sentiment"]
    kind, note = None, ""
    if hz >= 2 and s > 0.4 and price_z >= 2:
        kind, note = "EUPHORIA", "Crowd and price both stretched — crowded trade, late entries are risky."
    elif hz >= 2 and s < -0.4 and price_z <= -2:
        kind, note = "PANIC", "Crowd fearful while price falls hard — capitulation or more pain; size small."
    elif hz >= 2 and abs(price_z) < 0.8:
        kind, note = "HYPE_NO_PRICE", "Lots of chatter but price isn't confirming. Hype often fades."
    elif abs(price_z) >= 2.2 and hz < 0.5:
        kind, note = "QUIET_MOVE", "A big move with little retail chatter — often institutional flow."
    divergence = round(abs(max(hz, 0.0) - abs(price_z)), 2)
    return {"symbol": sym, "name": universe.display_name(sym), "price": cl[-1],
            "change_1d_pct": round(r1 * 100, 2), "change_5d_pct": round(r5 * 100, 2),
            "price_z": price_z, **att, "divergence": divergence, "signal": kind, "note": note,
            "social_mode": social_mode, "price_mode": price_mode}


def scan(symbols: List[str]) -> List[Dict[str, Any]]:
    out = []
    for sym in symbols[:30]:
        try:
            out.append(scan_symbol(sym))
        except Exception:
            continue
    out.sort(key=lambda r: (r["signal"] is None, -r["divergence"]))
    return out


def run_alerts() -> Dict[str, Any]:
    """Scan every user's watchlist and send Telegram alerts. Cron-safe."""
    s = get_settings()
    sent = considered = 0
    since = datetime.now(timezone.utc) - ALERT_COOLDOWN
    for user_id, symbols in store.all_watchlists().items():
        prefs = store.get_settings_row(user_id)
        if not prefs.hype_alerts:
            continue
        for row in scan(symbols):
            if not row["signal"] or row["divergence"] < prefs.hype_threshold:
                continue
            considered += 1
            if store.recent_alert(user_id, row["symbol"], row["signal"], since):
                continue
            msg = (f"Parakh hype radar · {row['symbol']} · {row['signal'].replace('_', ' ').title()}\n"
                   f"{row['mentions_24h']} mentions in 24h (normal ≈{row['baseline_per_day']}), "
                   f"price {row['change_1d_pct']:+.1f}% today.\n{row['note']}"
                   + ("\n(simulated social data)" if row["social_mode"] != "live" else "")
                   + "\nNot investment advice.")
            delivered = False
            if s.TELEGRAM_BOT_TOKEN and prefs.telegram_chat_id:
                from app.services.alert_service import send_telegram
                delivered = send_telegram(s.TELEGRAM_BOT_TOKEN, prefs.telegram_chat_id, msg)
            store.log_alert(user_id, row["symbol"], row["signal"], msg, delivered)
            sent += delivered
    return {"alerts_considered": considered, "telegram_sent": sent}
