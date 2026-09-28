"""
QuantPulse AI — Indian Stock Market API Client (NSE/BSE).

Wraps the ``0xramm/Indian-Stock-Market-API`` Flask service, which serves
live NSE/BSE quotes scraped from public market pages.

Endpoints used (upstream docs):
    GET /stock?symbol=<SYMBOL>&res=num
    GET /stock/list?symbols=<S1,S2>&res=num
    GET /search?q=<QUERY>

Conventions:
  * Base URL is configurable via the ``INDIAN_STOCK_API_URL`` environment
    variable and defaults to ``http://localhost:5000`` (local Flask dev).
  * ``res=num`` is attached to every quote request so the upstream returns
    raw numbers instead of formatted currency strings (``₹2,980.50``).
  * Tickers are normalised with a ``.NS`` suffix unless they already end in
    ``.NS`` or ``.BO``.
  * Every call is best-effort: timeouts, connection errors and non-200
    responses degrade to ``None`` / ``[]`` so callers fall back to cached or
    mock data. Labels elsewhere stay truthful (LIVE vs MOCK).

Example:
    >>> from app.services import indian_stock_api as isa
    >>> isa.get_stock_data("RELIANCE")   # doctest: +SKIP
    {'symbol': 'RELIANCE.NS', 'price': 2980.5, ...}
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import httpx

#: Default upstream — local dev server for 0xramm/Indian-Stock-Market-API.
DEFAULT_BASE_URL = "http://localhost:5000"

#: Name of the environment variable overriding the base URL.
BASE_URL_ENV_VAR = "INDIAN_STOCK_API_URL"

#: Per-request timeout (seconds). The upstream is a single-instance Flask
#: app, so be generous but never block a request cycle indefinitely.
TIMEOUT_S = 10.0

#: Response cache TTL (seconds). Upstream refreshes every few seconds in
#: market hours; 30 s keeps us polite without going stale.
_CACHE_TTL_S = 30.0


class _Cache:
    """Tiny TTL cache so batch scans don't hammer the free upstream."""

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
    """Clear all cached upstream responses (useful in tests)."""
    _cache.clear()


def base_url() -> str:
    """Return the configured upstream base URL (no trailing slash)."""
    return os.environ.get(BASE_URL_ENV_VAR, DEFAULT_BASE_URL).rstrip("/")


def normalize_symbol(symbol: str) -> str:
    """Normalise a ticker to carry an exchange suffix.

    Args:
        symbol: Raw ticker, e.g. ``"reliance"``, ``"INFY.BO"``.

    Returns:
        Uppercased ticker with ``.NS`` appended unless it already ends in
        ``.NS`` or ``.BO``.

    Example:
        >>> normalize_symbol("RELIANCE")
        'RELIANCE.NS'
        >>> normalize_symbol("INFY.BO")
        'INFY.BO'
    """
    sym = symbol.strip().upper()
    if sym.endswith(".NS") or sym.endswith(".BO"):
        return sym
    return f"{sym}.NS"


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    """Issue a GET against the upstream with ``res=num`` always attached.

    Args:
        path: Upstream path, e.g. ``"/stock"``.
        params: Extra query parameters merged alongside ``res=num``.

    Returns:
        Parsed JSON payload, or ``None`` on timeout, network failure,
        non-200 status, or invalid JSON. Never raises.
    """
    merged: Dict[str, Any] = {"res": "num"}
    if params:
        merged.update(params)
    url = f"{base_url()}{path}"
    try:
        r = httpx.get(
            url,
            params=merged,
            timeout=TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "QuantPulseAI/1.0 (+research)"},
        )
        if r.status_code != 200:
            return None
        return r.json()
    except (httpx.TimeoutException, httpx.RequestError, ValueError):
        # Timeout / DNS / connection reset / bad JSON → graceful miss.
        return None
    except Exception:
        return None


def get_stock_data(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch a single NSE/BSE stock quote.

    Calls ``GET /stock?symbol=<SYMBOL>&res=num`` (symbol normalised with
    :func:`normalize_symbol`).

    Args:
        symbol: Ticker such as ``"RELIANCE"`` or ``"INFY.BO"``.

    Returns:
        Parsed JSON dict on success, else ``None``. Results are cached
        for 30 seconds.
    """
    sym = normalize_symbol(symbol)
    key = f"stock:{sym}"
    cached = _cache.get(key, _CACHE_TTL_S)
    if cached is not None:
        return cached
    data = _get("/stock", {"symbol": sym})
    if data is not None:
        _cache.put(key, data)
    return data


def get_batch_stocks(symbols_list: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple NSE/BSE quotes in one call.

    Calls ``GET /stock/list?symbols=<S1,S2>&res=num``.

    Args:
        symbols_list: Tickers, each normalised with :func:`normalize_symbol`.

    Returns:
        List of per-symbol payloads. Symbols that fail are omitted, so an
        empty list means "no data" (never an exception).
    """
    if not symbols_list:
        return []
    normalized = [normalize_symbol(s) for s in symbols_list]
    key = f"batch:{','.join(sorted(normalized))}"
    cached = _cache.get(key, _CACHE_TTL_S)
    if cached is not None:
        return cached
    data = _get("/stock/list", {"symbols": ",".join(normalized)})
    if data is not None:
        _cache.put(key, data)
    return data if isinstance(data, list) else []


def search_stocks(query: str) -> List[Dict[str, Any]]:
    """Search the upstream symbol catalogue by name or ticker.

    Calls ``GET /search?q=<QUERY>``.

    Args:
        query: Free-text search, e.g. ``"reliance"``.

    Returns:
        List of matching stock dicts, or ``[]`` on failure/empty query.
    """
    if not query or not query.strip():
        return []
    key = f"search:{query.strip().upper()}"
    cached = _cache.get(key, _CACHE_TTL_S)
    if cached is not None:
        return cached
    data = _get("/search", {"q": query.strip()})
    if data is not None:
        _cache.put(key, data)
    return data if isinstance(data, list) else []
