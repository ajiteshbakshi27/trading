"""
QuantPulse AI — Feature 1 API: Information Propagation.

    GET /api/information/events            list detected events
    GET /api/information/events/{id}       one event + its evidence
    GET /api/information/propagation/{id} the timestamped layer chain
    GET /api/information/propagation/{id}/node/{layer}  node detail

Chains are built from observed first-crossing timestamps when the feeds are
live, and from a deterministic scenario otherwise. The response always says
which of the two happened.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Request
from pydantic import BaseModel, Field

from app.api.context import get_ctx
from app.models.common import INSUFFICIENT_DATA, mode_block
from app.models.enums import DataMode, Layer, weakest
from app.models.information_event import InformationEvent, MarketEvent
from app.services import feed_layer, information_propagation as ip

router = APIRouter(prefix="/api/information", tags=["information-propagation"])


class DetectRequest(BaseModel):
    symbol: Optional[str] = None
    persist: bool = True


def _snapshot_inputs(symbol: Optional[str]):
    """Pull the current market state through the normalized feed layer."""
    from app.config import get_settings
    s = get_settings()
    ctx = get_ctx_from_settings(s)
    books = (ctx.hft.snapshot_all() if ctx.hft is not None else [])
    if symbol:
        books = [b for b in books if b.get("symbol") == symbol.upper()]
    sentiment = (ctx.sent_engine.aggregate(posts=ctx.sent_engine.reddit_mock(10)
                                          + ctx.sent_engine.twitter_mock(10))
                 if ctx.sent_engine is not None else {"posts": [], "by_ticker": {}})
    markets, _ = feed_layer.get_prediction_markets(ctx.pred_agent)
    news, _ = feed_layer.get_news(symbol=symbol, limit=12)
    return books, sentiment, markets, news, ctx


def get_ctx_from_settings(s):
    """Build a lightweight context from app settings (no request needed)."""
    from app.api.context import ResearchContext
    from app.quantum_hft.hft_engine import HFTManager
    from app.agents.sentiment_agent import SentimentEngine
    from app.agents.prediction_agent import PredictionAgent
    return ResearchContext(
        hft=HFTManager(dict(s.BASE_PRICES)) if hasattr(s, "BASE_PRICES") else None,
        sent_engine=SentimentEngine(),
        pred_agent=PredictionAgent(),
        base_prices=dict(getattr(s, "BASE_PRICES", {})),
    )


@router.get("/events")
def list_events(symbol: Optional[str] = None, limit: int = Query(default=20, ge=1, le=200)):
    """Detected events, newest first. Empty when nothing crossed a threshold."""
    from app import database as db
    rows = db.list_market_events(limit=limit, symbol=symbol)
    return {
        "events": rows,
        "count": len(rows),
        "note": ("Events are opened when a layer crosses its materiality "
                 "threshold. An empty list means no shock was detected, not "
                 "that the market is flat."),
        **mode_block(DataMode.MOCK if not rows else
                     DataMode(rows[0].get("data_mode", "mock")),
                     note="Provenance is per-event; the block reflects the newest."),
    }


@router.post("/events/detect")
def detect(req: DetectRequest, request: Request):
    """Run detection over the current snapshot and return the chains."""
    books, sentiment, markets, news, ctx = _snapshot_inputs(req.symbol)
    mode = _mode_of(books, sentiment, news)
    events = ip.detect_events(books, sentiment, markets, news, mode=mode)
    if not events:
        return {
            "events": [], "count": 0,
            "status": "no_event",
            "note": ("No layer crossed its materiality threshold in this "
                     "snapshot, so no event was opened. This is not a claim "
                     "that the market is flat."),
            **mode_block(mode),
        }
    out = []
    from app import database as db
    for event in events:
        evidence = ip.collect_evidence(event, books=books, sentiment=sentiment,
                                       markets=markets, news=news)
        rows = _rows_for_fuse(evidence)
        fused = ip.fuse(rows)
        chain = ip.build_chain(event, evidence, fused,
                               observed=any(e.data_mode is DataMode.LIVE
                                            for e in evidence))
        if req.persist:
            db.save_market_event(event.model_dump())
            db.save_evidence([r for r in rows if r.get("evidence_id")])
        out.append({
            "event": event.model_dump(),
            "chain": chain.model_dump(),
            "confidence": fused["confidence"],
            "chain_mode": ("observed" if chain.data_mode is DataMode.LIVE
                           else "simulated_sequence"),
        })
    return {
        "events": [o["event"] for o in out],
        "chains": [o["chain"] for o in out],
        "count": len(out),
        **mode_block(mode),
    }


def _rows_for_fuse(evidence) -> List[Dict[str, Any]]:
    rows = []
    for ev in evidence:
        rows.append({
            "feature": ev.feature, "z_score": ev.z_score,
            "confidence": ev.confidence, "data_mode": ev.data_mode.value,
            "layer": ev.layer.value, "evidence_id": ev.evidence_id,
            "magnitude": ev.magnitude, "direction": ev.direction.value,
            "observed_at": ev.observed_at, "source_label": ev.source_label,
            "raw": ev.raw,
        })
    return rows


def _mode_of(books, sentiment, news) -> DataMode:
    modes = []
    for b in books:
        modes.append(DataMode.LIVE if (b.get("stream") or b.get("live"))
                     else DataMode.MOCK)
    for n in news:
        modes.append(getattr(n, "data_mode", DataMode.MOCK))
    return weakest(*modes) if modes else DataMode.MOCK


@router.get("/events/{event_id}")
def get_event(event_id: str):
    from app import database as db
    row = db.get_market_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    evidence = db.list_evidence(event_id=event_id, limit=200)
    return {
        "event": row,
        "evidence": evidence,
        "evidence_count": len(evidence),
        **mode_block(DataMode(row.get("data_mode", "mock"))),
    }


@router.get("/propagation/{event_id}")
def get_propagation(event_id: str):
    """The timestamped chain for one event."""
    from app import database as db
    row = db.get_market_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    evidence = db.list_evidence(event_id=event_id, limit=200)
    if not evidence:
        return {
            "event_id": event_id,
            "status": "insufficient_data",
            "label": INSUFFICIENT_DATA,
            "propagation_steps": [],
            "note": ("No evidence was recorded for this event, so no chain can "
                     "be drawn. This is not a claim that nothing happened."),
            **mode_block(DataMode(row.get("data_mode", "mock"))),
        }
    from app.services import fusion
    rows = [{
        "feature": e.get("feature", ""),
        "z_score": e.get("z_score", 0.0),
        "confidence": e.get("confidence", 0.0),
        "data_mode": e.get("data_mode", "mock"),
        "layer": e.get("layer", ""),
    } for e in evidence]
    fused = fusion.fuse(rows)
    chain = ip.build_chain(
        MarketEvent(**{k: row.get(k) for k in (
            "event_id", "symbol", "event_type", "category", "headline",
            "detected_at", "probability", "magnitude", "confidence",
            "direction", "themes", "sources", "data_mode", "model_version",
            "source_label")}),
        [type("E", (), {
            "evidence_id": e.get("evidence_id", ""),
            "event_id": e.get("event_id", ""),
            "symbol": e.get("symbol", ""),
            "layer": Layer(e.get("layer", "event")),
            "feature": e.get("feature", ""),
            "z_score": e.get("z_score", 0.0),
            "magnitude": e.get("magnitude", 0.0),
            "direction": e.get("direction", "FLAT"),
            "confidence": e.get("confidence", 0.0),
            "observed_at": e.get("created_at", ""),
            "data_mode": DataMode(e.get("data_mode", "mock")),
            "source_label": e.get("source_label", ""),
            "raw": {},
        })() for e in evidence],
        fused,
        observed=all(e.get("data_mode") == "live" for e in evidence),
    )
    return {
        "event_id": chain.event_id,
        "symbol": chain.symbol,
        "event_type": chain.event_type.value,
        "detected_at": chain.detected_at,
        "headline": chain.headline,
        "sources": chain.sources,
        "propagation_steps": [s.model_dump() for s in chain.propagation_steps],
        "confidence": chain.confidence,
        "span_s": chain.span_s,
        "layers_covered": [l.value for l in chain.layers_covered],
        "status": chain.status,
        "chain_mode": ("observed" if chain.data_mode is DataMode.LIVE
                       else "simulated_sequence" if chain.data_mode is DataMode.SIMULATED
                       else "mock"),
        "chain_mode_note": (
            "Lags are observed first-crossing timestamps."
            if chain.data_mode is DataMode.LIVE else
            "Lags come from a deterministic scenario because no live observation "
            "history exists. They are not measurements."),
        **mode_block(chain.data_mode),
    }


@router.get("/propagation/{event_id}/node/{layer}")
def get_node(event_id: str, layer: str):
    """Full disclosure for one node: raw signal, source, contribution, history."""
    try:
        target = Layer(layer)
    except ValueError:
        raise HTTPException(status_code=422,
                            detail=f"unknown layer '{layer}'. Valid: "
                                   f"{[l.value for l in Layer]}")
    from app import database as db
    row = db.get_market_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    evidence = db.list_evidence(event_id=event_id, limit=200)
    from app.services import fusion
    rows = [{"feature": e.get("feature", ""), "z_score": e.get("z_score", 0.0),
             "confidence": e.get("confidence", 0.0),
             "data_mode": e.get("data_mode", "mock"),
             "layer": e.get("layer", "")} for e in evidence]
    fused = fusion.fuse(rows)
    chain = ip.build_chain(
        MarketEvent(**{k: row.get(k) for k in (
            "event_id", "symbol", "event_type", "category", "headline",
            "detected_at", "probability", "magnitude", "confidence",
            "direction", "themes", "sources", "data_mode", "model_version",
            "source_label")}),
        [type("E", (), {
            "evidence_id": e.get("evidence_id", ""),
            "event_id": e.get("event_id", ""),
            "symbol": e.get("symbol", ""),
            "layer": Layer(e.get("layer", "event")),
            "feature": e.get("feature", ""),
            "z_score": e.get("z_score", 0.0),
            "magnitude": e.get("magnitude", 0.0),
            "direction": e.get("direction", "FLAT"),
            "confidence": e.get("confidence", 0.0),
            "observed_at": e.get("created_at", ""),
            "data_mode": DataMode(e.get("data_mode", "mock")),
            "source_label": e.get("source_label", ""),
            "raw": {},
        })() for e in evidence],
        fused,
        observed=all(e.get("data_mode") == "live" for e in evidence),
    )
    history = {}
    for e in evidence:
        history[e.get("layer", "")] = {
            "status": "ok" if e.get("actual_move_pct") is not None
                      else "insufficient_data",
            "label": "" if e.get("actual_move_pct") is not None else INSUFFICIENT_DATA,
            "n_observations": 1 if e.get("actual_move_pct") is not None else 0,
            "note": ("Resolved observation available."
                     if e.get("actual_move_pct") is not None else
                     "No resolved observation for this layer yet."),
        }
    return ip.node_detail(chain, target, history=history)
