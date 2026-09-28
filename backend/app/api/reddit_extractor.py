"""
QuantPulse AI — Reddit Extractor API.

    GET /api/reddit/extract?subreddits=wallstreetbets,stocks&limit=25
    GET /api/reddit/extract?symbol=NVDA

Fetches live Reddit posts (or mock fallback) and returns scored, ticker-tagged
data ready for the divergence and thesis stress engines.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import reddit_extractor

router = APIRouter(prefix="/api/reddit", tags=["reddit-extractor"])


@router.get("/extract")
def extract(
    subreddits: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = Query(default=25, ge=1, le=100),
):
    subs = ([s.strip().lower() for s in subreddits.split(",") if s.strip()]
            if subreddits else None)
    result = reddit_extractor.fetch_reddit(subreddits=subs, limit_per_sub=limit)
    if symbol:
        sym = symbol.upper()
        result["posts"] = [p for p in result["posts"]
                           if sym in p.get("tickers", [])]
        result["count"] = len(result["posts"])
    return {
        **result,
        "data_mode": result["data_mode"],
        **mode_block(DataMode(result["data_mode"])),
    }
