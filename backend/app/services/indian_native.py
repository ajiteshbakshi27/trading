"""
QuantPulse AI — Native NSE/BSE provider (no sidecar server required).

This is the same data source the ``0xramm/Indian-Stock-Market-API`` repo
wraps — Yahoo Finance's public endpoints — called directly from our backend:

  * quotes  — ``yfinance`` ``fast_info`` (last price, previous close, OHLC,
    volume, market cap). One HTTP round-trip per symbol, no crumb handshake.
  * search  — Yahoo ``v1/finance/search`` (needs no auth), filtered to
    ``.NS`` / ``.BO`` tickers, mirroring the upstream repo's ``searchYahoo``.

Payloads are shaped like the upstream ``/stock?res=num`` response
(``{status, symbol, exchange, ticker, data: {...}}``) plus a top-level
``"source": "yahoo-finance"`` tag, so callers can treat upstream-server
and native responses interchangeably.

Every function is best-effort and never raises: timeouts, network errors
and unknown tickers degrade to ``None`` / ``[]``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

#: Yahoo public search (no auth needed, same endpoint the upstream repo uses).
_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"

_UA = {"User-Agent": "QuantPulseAI/1.0 (+research)"}


def _split(symbol: str) -> tuple:
    """Split a normalised ticker into (clean, suffix).

    Index tickers (``^NSEI``) pass through with an empty suffix.
    """
    sym = symbol.strip().upper()
    if sym.startswith("^"):
        return sym, ""
    if sym.endswith(".BO"):
        return sym[:-3], ".BO"
    if sym.endswith(".NS"):
        return sym[:-3], ".NS"
    return sym, ".NS"


def _shape(clean: str, suffix: str, q: Dict[str, Any]) -> Dict[str, Any]:
    """Shape a generic Yahoo quote into the upstream ``/stock`` format."""
    data = q
    return {
        "status": "success",
        "symbol": clean,
        "exchange": "BSE" if suffix == ".BO" else "NSE",
        "ticker": f"{clean}{suffix}",
        "response_format": "numeric_only",
        "data": {
            "company_name": clean,
            "last_price": data.get("price"),
            "change": (round(data["price"] - data["previous_close"], 2)
                       if data.get("price") and data.get("previous_close")
                       else None),
            "percent_change": data.get("change_pct"),
            "previous_close": data.get("previous_close"),
            "open": data.get("open"),
            "day_high": data.get("day_high"),
            "day_low": data.get("day_low"),
            "year_high": None,
            "year_low": None,
            "volume": data.get("volume"),
            "market_cap": data.get("market_cap"),
            "currency": data.get("currency", "INR"),
        },
        "source": "yahoo-finance",
    }


def get_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch one NSE/BSE quote natively via Yahoo Finance.

    Args:
        symbol: Ticker such as ``"RELIANCE"``, ``"RELIANCE.NS"`` or
            ``"INFY.BO"`` (bare tickers default to NSE).

    Returns:
        Upstream-shaped quote dict, or ``None`` on any failure.
    """
    clean, suffix = _split(symbol)
    if not clean:
        return None
    try:
        from app.services import yahoo_finance as yfmod
        q = yfmod.get_quote(f"{clean}{suffix}")
    except Exception:
        return None
    if not isinstance(q, dict) or not q.get("price"):
        return None
    return _shape(clean, suffix, q)


def get_batch(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple NSE/BSE quotes natively (bounded thread pool).

    Symbols that fail are omitted; an empty list means "no data".
    """
    syms = [s for s in (symbols or []) if s and s.strip()]
    if not syms:
        return []
    tickers = [f"{c}{sfx}" for c, sfx in (_split(s) for s in syms)]
    try:
        from app.services import yahoo_finance as yfmod
        quotes = yfmod.get_batch(tickers)
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for q in quotes:
        if not isinstance(q, dict) or not q.get("price"):
            continue
        clean, suffix = _split(str(q.get("symbol", "")))
        if not clean:
            continue
        out.append(_shape(clean, suffix, q))
    return out


def search(query: str) -> List[Dict[str, Any]]:
    """Search Yahoo for NSE/BSE tickers by company name or symbol.

    Mirrors the upstream repo: ``.NS``/``.BO`` filter, clean symbol plus
    company name. Returns ``[]`` on any failure.
    """
    if not query or not query.strip():
        return []
    try:
        r = httpx.get(_SEARCH_URL, params={"q": query.strip(), "quotesCount": 15},
                      timeout=10.0, follow_redirects=True, headers=_UA)
        if r.status_code != 200:
            return []
        quotes = r.json().get("quotes", [])
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for q in quotes:
        sym = str(q.get("symbol", ""))
        if not (sym.endswith(".NS") or sym.endswith(".BO")):
            continue
        out.append({
            "symbol": sym.rsplit(".", 1)[0],
            "ticker": sym,
            "company_name": q.get("longname") or q.get("shortname") or sym,
            "sector": q.get("sector") or "N/A",
            "industry": q.get("industry") or "N/A",
            "source": "yahoo",
        })
    return out
