"""
Parakh — NSE market data.

Daily OHLCV from Yahoo Finance (``.NS`` tickers, ``^NSEI`` etc.) cached in the
shared store. When the network or Yahoo is unavailable the module returns a
deterministic simulated series and labels it ``simulated`` — callers MUST
surface ``data_mode`` so users never mistake it for real prices.
"""
from __future__ import annotations

import hashlib
import math
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.core import state_store
from app.parakh import universe

LIVE = "live"
SIMULATED = "simulated"
_TTL_S = 15 * 60

Bar = Dict[str, float]  # {"date": "YYYY-MM-DD", open, high, low, close, volume}

# Test hook: symbol -> bars. Lets tests run fully offline and deterministic.
_OVERRIDES: Dict[str, List[Bar]] = {}


def set_override(symbol: str, bars: Optional[List[Bar]]) -> None:
    sym = universe.normalize(symbol)
    if bars is None:
        _OVERRIDES.pop(sym, None)
    else:
        _OVERRIDES[sym] = bars


def _fetch_yahoo(symbol: str, days: int) -> Optional[List[Bar]]:
    # Circuit breaker: one failure pauses Yahoo calls for 5 minutes so a
    # blocked network doesn't make every request wait on retries.
    if state_store.get_json("yahoo_down"):
        return None
    try:
        import yfinance as yf  # type: ignore
        period = "2y" if days > 365 else "1y" if days > 180 else "6mo"
        if days > 730:
            period = "5y"
        df = yf.Ticker(universe.yahoo_ticker(symbol)).history(
            period=period, interval="1d", auto_adjust=True)
        if df is None or df.empty:
            state_store.set_json("yahoo_down", True, ttl_s=300)
            return None
        bars = []
        for idx, row in df.iterrows():
            bars.append({"date": idx.strftime("%Y-%m-%d"),
                         "open": round(float(row["Open"]), 2),
                         "high": round(float(row["High"]), 2),
                         "low": round(float(row["Low"]), 2),
                         "close": round(float(row["Close"]), 2),
                         "volume": float(row.get("Volume", 0) or 0)})
        return bars if len(bars) >= 30 else None
    except Exception:
        state_store.set_json("yahoo_down", True, ttl_s=300)
        return None


def _seed(symbol: str) -> int:
    return int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)


def simulated_bars(symbol: str, days: int = 500) -> List[Bar]:
    """Deterministic geometric random walk, business days only. SIMULATED."""
    rng = random.Random(_seed(symbol))
    price = 100 + rng.random() * 2400
    vol = 0.012 + rng.random() * 0.012
    drift = (rng.random() - 0.45) * 0.0008
    end = date.today()
    d = end - timedelta(days=int(days * 1.45))
    bars: List[Bar] = []
    while d <= end:
        if d.weekday() < 5:
            ret = drift + vol * rng.gauss(0, 1)
            if rng.random() < 0.01:                      # occasional gap day
                ret += rng.choice([-1, 1]) * vol * 4
            o = price
            c = max(1.0, price * math.exp(ret))
            hi = max(o, c) * (1 + abs(rng.gauss(0, vol / 2)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, vol / 2)))
            bars.append({"date": d.isoformat(), "open": round(o, 2),
                         "high": round(hi, 2), "low": round(lo, 2),
                         "close": round(c, 2),
                         "volume": float(int(1e5 + rng.random() * 5e6))})
            price = c
        d += timedelta(days=1)
    return bars[-days:]


def history(symbol: str, days: int = 400) -> Tuple[List[Bar], str]:
    """Daily bars (oldest first) and their data mode."""
    sym = universe.normalize(symbol)
    if sym in _OVERRIDES:
        return _OVERRIDES[sym][-days:], LIVE
    key = f"bars:{sym}:{days}"
    cached = state_store.get_json(key)
    if cached:
        return cached["bars"], cached["mode"]
    bars = _fetch_yahoo(sym, days)
    mode = LIVE
    if not bars:
        bars, mode = simulated_bars(sym, max(days, 300)), SIMULATED
    bars = bars[-days:]
    state_store.set_json(key, {"bars": bars, "mode": mode},
                         ttl_s=_TTL_S if mode == LIVE else 300)
    return bars, mode


def closes(bars: List[Bar]) -> List[float]:
    return [float(b["close"]) for b in bars]


def quote(symbol: str) -> Dict[str, object]:
    bars, mode = history(symbol, 60)
    last, prev = bars[-1], bars[-2] if len(bars) > 1 else bars[-1]
    chg = (last["close"] / prev["close"] - 1) * 100 if prev["close"] else 0.0
    return {"symbol": universe.normalize(symbol), "name": universe.display_name(symbol),
            "price": last["close"], "change_pct": round(chg, 2), "as_of": last["date"],
            "data_mode": mode}


# ----------------------------- indicators ---------------------------------

def sma(values: List[float], n: int) -> Optional[float]:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def daily_returns(values: List[float]) -> List[float]:
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1]]


def stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def atr(bars: List[Bar], n: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    window = trs[-n:]
    return sum(window) / len(window)


def rsi(values: List[float], n: int = 14) -> Optional[float]:
    if len(values) <= n:
        return None
    gains = losses = 0.0
    for i in range(len(values) - n, len(values)):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return 100 - 100 / (1 + rs)


def annual_vol(values: List[float], lookback: int = 60) -> float:
    return stdev(daily_returns(values[-(lookback + 1):])) * math.sqrt(252)


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()
