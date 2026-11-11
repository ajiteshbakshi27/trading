"""
QuantPulse AI — Indian Stocks API (NSE/BSE via 0xramm/Indian-Stock-Market-API).

    GET /api/indian/stock?symbol=RELIANCE        single quote
    GET /api/indian/batch?symbols=RELIANCE,INFY  batch quotes
    GET /api/indian/search?q=reliance            symbol search
    GET /api/indian/status                       upstream reachability

Every response carries ``data_mode``: LIVE when the upstream answered,
MOCK when it was unreachable (fallback prices apply downstream).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import indian_stock_api as isa

router = APIRouter(prefix="/api/indian", tags=["indian-stocks"])


@router.get("/stock")
def stock(symbol: str = Query(..., min_length=1, description="NSE/BSE ticker")):
    data = isa.get_stock_data(symbol)
    live = data is not None
    mode = DataMode.LIVE if live else DataMode.MOCK
    source = (data.get("source", "indian-stock-api") if isinstance(data, dict)
              else "unavailable") if live else "unavailable"
    return {
        "symbol": isa.normalize_symbol(symbol),
        "data": data,
        "data_mode": mode.value,
        "source": source,
        **mode_block(mode),
    }


@router.get("/batch")
def batch(symbols: str = Query(..., description="Comma-separated tickers")):
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    data = isa.get_batch_stocks(syms)
    live = len(data) > 0
    mode = DataMode.LIVE if live else DataMode.MOCK
    srcs = sorted({d.get("source", "?") for d in data if isinstance(d, dict)})
    return {
        "symbols": [isa.normalize_symbol(s) for s in syms],
        "results": data,
        "count": len(data),
        "data_mode": mode.value,
        "source": ",".join(srcs) if live else "unavailable",
        **mode_block(mode),
    }


@router.get("/search")
def search(q: str = Query(..., min_length=1, description="Name or ticker query")):
    data = isa.search_stocks(q)
    live = len(data) > 0
    mode = DataMode.LIVE if live else DataMode.MOCK
    srcs = sorted({d.get("source", "?") for d in data if isinstance(d, dict)})
    return {
        "query": q,
        "results": data,
        "count": len(data),
        "data_mode": mode.value,
        "source": ",".join(srcs) if live else "unavailable",
        **mode_block(mode),
    }


@router.get("/status")
def status():
    """Probe both live paths: upstream server and native Yahoo provider."""
    upstream_ok = isa._get("/search", {"q": "RELIANCE"}) is not None
    native_ok = False
    try:
        from app.services import indian_native
        native_ok = indian_native.get_quote("RELIANCE.NS") is not None
    except Exception:
        pass
    reachable = upstream_ok or native_ok
    mode = DataMode.LIVE if reachable else DataMode.MOCK
    return {
        "base_url": isa.base_url(),
        "reachable": reachable,
        "upstream_server": upstream_ok,
        "native_yahoo": native_ok,
        "data_mode": mode.value,
        **mode_block(mode),
    }
