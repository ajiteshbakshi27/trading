"""
QuantPulse AI — Feature 4 API: Prediction Failure Autopsy.

    GET  /api/predictions                 list predictions
    GET  /api/predictions/{id}            one prediction (+ outcome if resolved)
    POST /api/predictions/{id}/resolve    measure against a realized price
    GET  /api/predictions/{id}/autopsy    failure analysis (only if wrong)
    GET  /api/model/failure-analysis      aggregate, withheld below the floor

Resolution requires a real exit price. The autopsy only runs when the
prediction was wrong; a correct prediction produces no autopsy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.common import INSUFFICIENT_DATA, insufficient, mode_block
from app.models.enums import DataMode, MIN_SAMPLE_FOR_PERFORMANCE, Regime
from app.models.prediction_outcome import PredictionRecord
from app.services import prediction_autopsy

router = APIRouter(prefix="/api", tags=["prediction-autopsy"])


class ResolveRequest(BaseModel):
    exit_price: float = Field(gt=0, description="realized price at resolution")
    realized_vol: Optional[float] = None
    realized_regime: Optional[Regime] = None
    max_adverse_move_pct: Optional[float] = None
    observed_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = ""
    persist: bool = True


@router.get("/predictions")
def list_predictions(symbol: Optional[str] = None, status: Optional[str] = None,
                     limit: int = 100):
    from app import database as db
    rows = db.list_predictions(limit=limit, symbol=symbol, status=status)
    return {"predictions": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str):
    from app import database as db
    row = db.get_prediction(prediction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    outcome = db.get_outcome(prediction_id)
    autopsy = db.get_autopsy(prediction_id)
    return {
        "prediction": row,
        "outcome": outcome,
        "autopsy": autopsy,
        "status": row.get("status", "open"),
        **mode_block(DataMode(row.get("data_mode", "mock"))),
    }


@router.post("/predictions/{prediction_id}/resolve")
def resolve(prediction_id: str, req: ResolveRequest):
    from app import database as db
    row = db.get_prediction(prediction_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    if row.get("status") == "resolved":
        raise HTTPException(status_code=409,
                            detail="prediction already resolved")
    prediction = PredictionRecord(**row.get("payload") or row)
    outcome, autopsy = prediction_autopsy.resolve_and_autopsy(
        prediction, req.exit_price,
        observed_evidence=req.observed_evidence,
        realized_vol=req.realized_vol,
        realized_regime=req.realized_regime,
        adverse_move_pct=req.max_adverse_move_pct,
        source=req.source,
        persist=req.persist)
    return {
        "outcome": outcome.model_dump(),
        "autopsy": (autopsy.model_dump() if autopsy else None),
        "correct": outcome.correct,
        "error_pct": outcome.error_pct,
        "note": ("No autopsy was run: the prediction resolved correctly. "
                 "Failures are analysed, successes are not converted into "
                 "lessons." if outcome.correct else
                 "The prediction resolved incorrectly, so an autopsy was run."),
        **mode_block(outcome.data_mode),
    }


@router.get("/predictions/{prediction_id}/autopsy")
def get_autopsy(prediction_id: str):
    from app import database as db
    row = db.get_autopsy(prediction_id)
    if row is None:
        pred = db.get_prediction(prediction_id)
        if pred is None:
            raise HTTPException(status_code=404, detail="prediction not found")
        return {
            "status": "no_autopsy",
            "label": INSUFFICIENT_DATA,
            "note": ("No autopsy exists for this prediction. Autopsies are only "
                     "produced when a prediction resolves incorrectly."),
            **mode_block(DataMode(pred.get("data_mode", "mock"))),
        }
    return {"autopsy": row, **mode_block(DataMode(row.get("data_mode", "mock")))}


@router.get("/model/failure-analysis")
def failure_analysis():
    """Aggregate performance. Withheld until the sample floor is met."""
    from app import database as db
    pairs = db.resolved_pairs(limit=1000)
    autopsies = db.list_autopsies(limit=1000)
    records = []
    outcomes = []
    for pair in pairs:
        try:
            records.append(PredictionRecord(**pair["prediction"].get("payload")
                                           or pair["prediction"]))
        except Exception:
            continue
        outcomes.append(pair["outcome"])
    from app.models.prediction_outcome import PredictionOutcome
    outcome_objs = []
    for o in outcomes:
        try:
            outcome_objs.append(PredictionOutcome(**o))
        except Exception:
            continue
    combined = list(zip(records, outcome_objs))
    analysis = prediction_autopsy.failure_analysis(combined, autopsies=autopsies)
    return {
        "analysis": analysis.model_dump(),
        "label": analysis.label,
        "status": analysis.status,
        "insufficiency": analysis.insufficiency,
        "methodology": ("Performance is computed only from resolved predictions "
                        "that carry a realized move. Below the sample floor the "
                        "API returns INSUFFICIENT DATA instead of a number."),
        **mode_block(analysis.data_mode),
    }
