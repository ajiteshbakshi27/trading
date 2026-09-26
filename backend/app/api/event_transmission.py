"""
QuantPulse AI — Feature 3 API: Event → Asset Transmission.

    GET /api/events                       list events (alias of information)
    GET /api/events/{id}                  one event
    GET /api/events/{id}/assets           the EVENT → THEME → ASSET graph
    GET /api/assets/{symbol}/events       events that touched this asset

Relationships are typed by RelationKind; causal vocabulary is not available
in the schema. Historical response stats stay null until enough comparable
resolved events exist.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.common import INSUFFICIENT_DATA, mode_block
from app.models.enums import DataMode
from app.services import event_transmission as et

router = APIRouter(prefix="/api/events", tags=["event-transmission"])


@router.get("")
def list_events(symbol: Optional[str] = None,
                limit: int = Query(default=20, ge=1, le=200)):
    from app import database as db
    rows = db.list_market_events(limit=limit, symbol=symbol)
    return {"events": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@router.get("/{event_id}")
def get_event(event_id: str):
    from app import database as db
    row = db.get_market_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    return {"event": row, **mode_block(DataMode(row.get("data_mode", "mock")))}


@router.get("/{event_id}/assets")
def get_assets(event_id: str):
    """The transmission graph: nodes, edges, exposures, honest history."""
    from app import database as db
    row = db.get_market_event(event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    evidence = db.list_evidence(event_id=event_id, limit=200)
    features = [e.get("feature", "") for e in evidence if e.get("feature")]
    history = _history_index()
    graph = et.build_graph(_event_from_row(row), features, history=history,
                           data_mode=DataMode(row.get("data_mode", "mock")),
                           event_id=event_id)
    return {
        "event_id": graph.event_id,
        "symbol": graph.symbol,
        "headline": graph.headline,
        "event_type": graph.event_type.value,
        "category": graph.category.value,
        "probability": graph.probability,
        "themes": [t.model_dump() for t in graph.themes],
        "nodes": [n.model_dump() for n in graph.nodes],
        "edges": [e.model_dump() for e in graph.edges],
        "exposures": [e.model_dump() for e in graph.exposures],
        "historical_status": graph.historical_status,
        "historical_label": graph.historical_label,
        "relation_vocabulary": graph.relation_vocabulary,
        "disclaimer": graph.disclaimer,
        **mode_block(graph.data_mode),
    }


def _event_from_row(row: Dict[str, Any]):
    from app import database as db
    from app.models.enums import EventCategory, EventType
    payload = db._unjson(row.get("payload") or "{}")
    return type("E", (), {
        "symbol": row.get("symbol", ""),
        "headline": row.get("headline", ""),
        "event_type": EventType(row.get("event_type", "market")),
        "category": EventCategory(row.get("category", "company")),
        "event_id": row.get("event_id", ""),
        "probability": payload.get("probability"),
        "detected_at": row.get("created_at", ""),
    })()


def _history_index() -> Dict[str, List[Dict[str, Any]]]:
    from app.services.closed_loop import _historical_index
    return _historical_index()
