"""
QuantPulse AI — Research router.

    GET /api/research/signals        recent fused signals
    GET /api/research/evidence       evidence records
    GET /api/research/propagation   alias to /api/information/propagation

Thin read models over the research tables. Write paths live on the feature
routers; this one is for the dashboard's compact panels.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode

router = APIRouter(prefix="/api/research", tags=["research"])

#: Asset-centric view of the same event graph. Registered without a prefix so
#: the path matches the spec exactly: /api/assets/{symbol}/events.
asset_router = APIRouter(tags=["event-transmission"])


@router.get("/signals")
def signals(symbol: Optional[str] = None, limit: int = Query(default=50, ge=1, le=500)):
    from app import database as db
    rows = db.get_signal_history(limit=limit, symbol=symbol)
    return {"signals": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@router.get("/evidence")
def evidence(symbol: Optional[str] = None,
             limit: int = Query(default=100, ge=1, le=1000)):
    from app import database as db
    rows = db.list_evidence(symbol=symbol, limit=limit)
    return {"evidence": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@router.get("/events")
def events(symbol: Optional[str] = None,
           limit: int = Query(default=20, ge=1, le=200)):
    from app import database as db
    rows = db.list_market_events(limit=limit, symbol=symbol)
    return {"events": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@asset_router.get("/api/assets/{symbol}/events")
def asset_events(symbol: str, limit: int = Query(default=20, ge=1, le=200)):
    """Events whose graph includes this asset, plus its observed responses."""
    from app import database as db
    from app.services import event_transmission as et
    rows = db.list_market_events(limit=500)
    matched = []
    for row in rows:
        payload = db._unjson(row.get("payload") or "{}")
        themes = payload.get("themes") or []
        for theme_id in themes:
            theme = et.THEMES.get(theme_id)
            if theme and symbol.upper() in theme.member_symbols:
                matched.append(row)
                break
        if len(matched) >= limit:
            break
    return {
        "symbol": symbol.upper(),
        "events": matched,
        "count": len(matched),
        "note": ("An event appears here when the theme resolution places this "
                 "asset under it. This is membership, not a causal claim."),
        **mode_block(DataMode.MOCK if not matched else
                     DataMode(matched[0].get("data_mode", "mock"))),
    }
