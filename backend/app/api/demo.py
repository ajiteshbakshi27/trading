"""
QuantPulse AI — Demo + research overview API.

    GET /api/demo                      the deterministic SIMULATED scenario
    POST /api/demo/run                 walk the full loop on the scenario
    GET /api/research/cycle            run the loop over the live snapshot
    GET /api/research/overview         signals, model evidence, feed status

The demo is synthetic and always labelled SIMULATED SCENARIO. It exists so the
complete loop is demonstrable with no credentials.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from app.models.common import mode_block
from app.models.enums import DataMode
from app.services import closed_loop, scenarios

router = APIRouter(tags=["demo", "research"])


@router.get("/api/demo")
def demo_scenario():
    """The scenario definition, before anything is run."""
    return {
        "scenario_id": scenarios.SCENARIO_ID,
        "scenario_label": scenarios.SCENARIO_LABEL,
        "symbol": "NVDA",
        "headline": scenarios.HEADLINE,
        "beats": scenarios.DEMO_BEATS,
        "event": scenarios.event_payload(),
        "chain": scenarios.chain_payload(),
        "outcome": scenarios.outcome_payload(),
        "note": ("This is a synthetic narrative, not a record of a real event. "
                 "Every record it produces is labelled SIMULATED."),
        **mode_block(DataMode.SIMULATED),
    }


@router.post("/api/demo/run")
def demo_run(persist: bool = True):
    """Walk the complete loop: event → … → experiment."""
    result = closed_loop.run_scenario_cycle(persist=persist)
    return _serialise_cycle(result)


@router.get("/api/research/cycle")
def research_cycle(symbol: str = "NVDA", persist: bool = True):
    """Run the loop over whatever the feeds currently report."""
    from app.api.information import _snapshot_inputs
    books, sentiment, markets, news, _ctx = _snapshot_inputs(symbol or None)
    result = closed_loop.run_live_cycle(books, sentiment, markets, news,
                                        symbol=symbol, persist=persist)
    if result.get("status") == "no_event":
        return {**result, **mode_block(result.get("data_mode", DataMode.MOCK))}
    return _serialise_cycle(result)


@router.get("/api/research/overview")
def research_overview():
    """Signals, model evidence and feed provenance in one payload."""
    from app import database as db
    from app.config import get_settings
    s = get_settings()
    latest = db.latest_thesis()
    predictions = db.list_predictions(limit=500)
    resolved = db.resolved_pairs(limit=1000)
    experiments = db.list_experiments(limit=50)
    return {
        "feeds": s.feed_status(),
        "feed_health": {"has_reddit": s.has_reddit, "has_twitter": s.has_twitter,
                        "has_financial_data": s.has_financial_data,
                        "history_provider": "yfinance"},
        "latest_thesis": latest,
        "counts": {
            "predictions": len(predictions),
            "resolved": len(resolved),
            "experiments": len(experiments),
            "autopsies": len(db.list_autopsies(limit=1000)),
        },
        "model_versions": _model_versions(),
        "note": ("Counts are raw record counts, not performance. Performance "
                 "is reported by /api/model/failure-analysis once the sample "
                 "floor is met."),
        **mode_block(DataMode.MOCK),
    }


def _model_versions() -> list:
    from app import database as db
    try:
        from sqlmodel import Session, select
        with Session(db.get_engine()) as session:
            rows = list(session.exec(select(db.ModelVersionRow)))
            return [{"model_version": r.model_version,
                     "description": r.description,
                     "active": r.active,
                     "created_at": str(r.created_at)} for r in rows]
    except Exception:
        return []


def _serialise_cycle(result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn the orchestrator's Pydantic objects into an API payload."""
    out: Dict[str, Any] = {"status": result.get("status")}
    for key in ("event", "chain", "graph", "thesis", "stress", "prediction",
                "outcome", "autopsy", "analysis", "tournament", "regime",
                "regime_metrics", "market_state", "evidence", "scenario_id",
                "scenario_label"):
        value = result.get(key)
        if value is None:
            continue
        if hasattr(value, "model_dump"):
            out[key] = value.model_dump()
        elif isinstance(value, dict):
            out[key] = value
        elif isinstance(value, list):
            out[key] = [v.model_dump() if hasattr(v, "model_dump") else v
                        for v in value]
        else:
            out[key] = value
    out["data_mode"] = result.get("data_mode", DataMode.MOCK).value
    out["data_mode_label"] = result.get("data_mode", DataMode.MOCK).label
    return out
