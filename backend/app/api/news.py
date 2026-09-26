"""
QuantPulse AI — News Catalyst API.

    GET /api/news                 live news for the whole universe
    GET /api/news?symbols=NVDA,TSLA   live news for specific symbols

Headlines are tagged with lexicon/VADER sentiment and a faction
(retail/institutional) inferred from the divergence scan.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import news_engine

router = APIRouter(prefix="/api/news", tags=["news-catalyst"])


@router.get("")
def news(symbols: Optional[str] = None, limit: int = Query(default=12, ge=1, le=30)):
    syms = ([s.strip().upper() for s in symbols.split(",") if s.strip()]
            if symbols else None)
    result = news_engine.fetch_news(symbols=syms, limit=limit)
    return {
        "items": result["items"],
        "count": result["count"],
        "hot_divergence": result["hot_divergence"],
        "data_mode": result["data_mode"],
        "source": result["source"],
        "note": result["note"],
        **mode_block(DataMode(result["data_mode"])),
    }
