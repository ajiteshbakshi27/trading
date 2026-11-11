"""
QuantPulse AI — Indian Stock Market API Client (NSE/BSE).

Two live paths, one interface:

  1. Upstream server — the ``0xramm/Indian-Stock-Market-API`` service when it
     is running (``INDIAN_STOCK_API_URL``, default ``http://localhost:5000``).
  2. Native fallback — Yahoo Finance called directly from this backend
     (:mod:`app.services.indian_native`, the same source the upstream repo
     wraps). No sidecar server needed.

Every public function tries (1) then (2) and degrades to ``None`` / ``[]``
so callers fall back to cached or mock data. Payloads carry a top-level
``"source"`` tag (``"indian-stock-api"`` or ``"yahoo-finance"``) so labels
downstream stay truthful (LIVE vs MOCK).

Conventions shared by both paths:
  * ``res=num`` is attached to every upstream quote request (raw numbers).
  * Tickers are normalised with a ``.NS`` suffix unless ``.NS``/``.BO``.
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
        >>> normalize_symbol("^NSEI")
        '^NSEI'
    """
    sym = symbol.strip().upper()
    if sym.startswith("^"):
        return sym  # index ticker (e.g. ^NSEI) — never suffixed
    if sym.endswith(".NS") or sym.endswith(".BO"):
        return sym
    return f"{sym}.NS"


def _tag_upstream(data: Any) -> Any:
    """Shallow-tag an upstream payload with its source (no caller mutation)."""
    if isinstance(data, dict):
        tagged = dict(data)
        tagged.setdefault("source", "indian-stock-api")
        return tagged
    if isinstance(data, list):
        return [dict(d, source=d.get("source", "indian-stock-api"))
                if isinstance(d, dict) else d for d in data]
    return data


def _native() -> Any:
    """Lazy import of the native provider (keeps yfinance out of import time)."""
    from app.services import indian_native
    return indian_native


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


def _resolve_single(symbol: str) -> Optional[Dict[str, Any]]:
    """Upstream server first, native Yahoo fallback. Never raises."""
    data = _get("/stock", {"symbol": symbol})
    if data is not None:
        return _tag_upstream(data)
    try:
        return _native().get_quote(symbol)
    except Exception:
        return None


def _resolve_batch(normalized: List[str]) -> List[Dict[str, Any]]:
    """Upstream batch first, native Yahoo fallback. Never raises."""
    data = _get("/stock/list", {"symbols": ",".join(normalized)})
    if isinstance(data, list) and data:
        return _tag_upstream(data)
    if isinstance(data, dict) and data:  # some versions return one object
        return [_tag_upstream(data)]
    try:
        return _native().get_batch(normalized)
    except Exception:
        return []


def _resolve_search(query: str) -> List[Dict[str, Any]]:
    """Upstream search first, native Yahoo fallback. Never raises."""
    data = _get("/search", {"q": query})
    if isinstance(data, list) and data:
        return _tag_upstream(data)
    try:
        return _native().search(query)
    except Exception:
        return []


def get_stock_data(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch a single NSE/BSE stock quote.

    Tries the upstream ``GET /stock?symbol=<SYMBOL>&res=num`` first, then
    the native Yahoo provider (same source, no sidecar server). Symbol is
    normalised with :func:`normalize_symbol`.

    Args:
        symbol: Ticker such as ``"RELIANCE"`` or ``"INFY.BO"``.

    Returns:
        Upstream-shaped quote dict (with a ``"source"`` tag) on success,
        else ``None``. Results are cached for 30 seconds.
    """
    sym = normalize_symbol(symbol)
    key = f"stock:{sym}"
    cached = _cache.get(key, _CACHE_TTL_S)
    if cached is not None:
        return cached
    data = _resolve_single(sym)
    if data is not None:
        _cache.put(key, data)
    return data


def get_batch_stocks(symbols_list: List[str]) -> List[Dict[str, Any]]:
    """Fetch multiple NSE/BSE quotes in one call.

    Tries upstream ``GET /stock/list?symbols=<S1,S2>&res=num``, then the
    native Yahoo provider.

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
    data = _resolve_batch(normalized)
    _cache.put(key, data)
    return data


def search_stocks(query: str) -> List[Dict[str, Any]]:
    """Search NSE/BSE symbols by name or ticker.

    Tries upstream ``GET /search?q=<QUERY>``, then native Yahoo search.

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
    data = _resolve_search(query.strip())
    _cache.put(key, data)
    return data
