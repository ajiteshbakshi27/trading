"""
QuantPulse AI — Generic Yahoo Finance quote provider (no key required).

Used for US tickers (NASDAQ/NYSE) and anything else Yahoo resolves. NSE/BSE
traffic goes through :mod:`app.services.indian_native`, which shapes these
quotes into the upstream Indian-API response format.

Every function is best-effort and never raises: timeouts, unknown tickers
and network errors degrade to ``None`` / ``[]``. Per-symbol results are
cached for 60 seconds so snapshot ticks and scans stay cheap.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Dict, List, Optional

#: Per-symbol budget (seconds). Bounds request latency when Yahoo is slow.
TIMEOUT_S = 12.0

#: Quote cache TTL (seconds).
_CACHE_TTL_S = 60.0

_cache: Dict[str, tuple] = {}


def clear_caches() -> None:
    """Clear cached quotes (useful in tests)."""
    _cache.clear()


def _cached(symbol: str) -> Optional[Dict[str, Any]]:
    hit = _cache.get(symbol.upper())
    if not hit:
        return None
    ts, val = hit
    if time.time() - ts > _CACHE_TTL_S:
        return None
    return val


def _fetch_fast_info(symbol: str) -> Optional[Any]:
    """Return a yfinance FastInfo object, or None. Runs in a worker thread."""
    def _go() -> Optional[Any]:
        import yfinance as yf
        return yf.Ticker(symbol.strip().upper()).fast_info

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_go).result(timeout=TIMEOUT_S)
    except (FutureTimeout, Exception):
        return None


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _vol(fi: Any) -> Optional[int]:
    for name in ("last_volume", "day_volume", "volume"):
        try:
            v = int(float(getattr(fi, name)))
            if v > 0:
                return v
        except (TypeError, ValueError, AttributeError):
            continue
    return None


def get_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch one live quote via Yahoo Finance.

    Args:
        symbol: Any Yahoo ticker: ``"NVDA"``, ``"RELIANCE.NS"``, ``"^NSEI"``.

    Returns:
        ``{"symbol", "price", "change_pct", "previous_close", "open",
        "day_high", "day_low", "volume", "market_cap", "currency",
        "source": "yahoo-finance"}`` or ``None``. Cached 60 s.
    """
    sym = symbol.strip().upper()
    if not sym:
        return None
    hit = _cached(sym)
    if hit is not None:
        return hit
    fi = _fetch_fast_info(sym)
    if fi is None:
        return None
    try:
        last = _num(fi.last_price)
        prev = _num(fi.previous_close)
        if last is None or prev is None:
            return None
        try:
            currency = fi.currency or "USD"
        except Exception:
            currency = "USD"
        out = {
            "symbol": sym,
            "price": round(last, 2),
            "change_pct": round((last - prev) / prev * 100.0, 2),
            "previous_close": round(prev, 2),
            "open": _num(getattr(fi, "open", None)),
            "day_high": _num(getattr(fi, "day_high", None)),
            "day_low": _num(getattr(fi, "day_low", None)),
            "volume": _vol(fi),
            "market_cap": _num(getattr(fi, "market_cap", None)),
            "currency": currency,
            "source": "yahoo-finance",
        }
    except Exception:
        return None
    _cache[sym] = (time.time(), out)
    return out


def get_batch(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple live quotes (bounded thread pool, 60 s cache).

    Symbols that fail are omitted; an empty list means "no data".
    """
    syms = [s for s in (symbols or []) if s and s.strip()]
    if not syms:
        return []
    out: List[Dict[str, Any]] = []
    try:
        with ThreadPoolExecutor(max_workers=min(4, len(syms))) as pool:
            futs = {pool.submit(get_quote, s): s for s in syms}
            deadline = time.time() + TIMEOUT_S + 5.0
            for fut in futs:
                remaining = max(1.0, deadline - time.time())
                try:
                    q = fut.result(timeout=remaining)
                except (FutureTimeout, Exception):
                    continue
                if isinstance(q, dict):
                    out.append(q)
    except Exception:
        pass
    return out


#: History cache: yahoo_ticker -> (timestamp, candles). 15-min TTL —
#: daily bars move slowly, no need to hammer Yahoo per refresh.
_HISTORY_TTL_S = 900.0
_history_cache: Dict[str, tuple] = {}


def _resolve_history_ticker(symbol: str) -> List[str]:
    """Candidate Yahoo tickers to try in order.

    Bare Indian names (``RELIANCE``) need the ``.NS`` suffix; US names
    and ``^`` indices pass through unchanged.
    """
    sym = symbol.strip().upper()
    if not sym or sym.startswith("^") or "." in sym:
        return [sym] if sym else []
    # US tickers work bare; Indian bare names need .NS. Try bare first
    # (correct for US), then .NS (correct for NSE).
    return [sym, f"{sym}.NS"]


def get_candles(symbol: str, n: int = 120) -> Optional[List[Dict[str, Any]]]:
    """Daily OHLC candles via Yahoo Finance, chart-ready.

    Args:
        symbol: Any ticker — ``"NVDA"``, ``"TMPV"`` (tries ``TMPV.NS``),
            ``"RELIANCE.NS"``, ``"^NSEI"``.
        n: Max bars to return (most recent kept).

    Returns:
        List of ``{"time", "open", "high", "low", "close"}`` with unix-
        second timestamps (lightweight-charts daily format), or ``None``.
        Cached 15 min. Never raises.
    """
    sym = symbol.strip().upper()
    if not sym or n <= 0:
        return None
    cache_key = f"{sym}:{n}"
    hit = _history_cache.get(cache_key)
    if hit and time.time() - hit[0] < _HISTORY_TTL_S:
        return hit[1]

    period = "3mo" if n <= 60 else ("6mo" if n <= 130 else "1y")

    def _go() -> Optional[List[Dict[str, Any]]]:
        import yfinance as yf
        for candidate in _resolve_history_ticker(sym):
            try:
                frame = yf.Ticker(candidate).history(period=period,
                                                     auto_adjust=True)
            except Exception:
                continue
            if frame is None or len(frame) < 20:
                continue
            try:
                out: List[Dict[str, Any]] = []
                for ts, row in frame.tail(n).iterrows():
                    try:
                        epoch = int(ts.timestamp())
                    except Exception:
                        continue
                    try:
                        o, h, l, c = (float(row["Open"]), float(row["High"]),
                                      float(row["Low"]), float(row["Close"]))
                    except (KeyError, TypeError, ValueError):
                        continue
                    if min(o, h, l, c) <= 0:
                        continue
                    out.append({"time": epoch, "open": round(o, 2),
                                "high": round(h, 2), "low": round(l, 2),
                                "close": round(c, 2)})
                if len(out) >= 20:
                    return out
            except Exception:
                continue
        return None

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            candles = pool.submit(_go).result(timeout=TIMEOUT_S + 8.0)
    except (FutureTimeout, Exception):
        return None
    if candles:
        _history_cache[cache_key] = (time.time(), candles)
    return candles
