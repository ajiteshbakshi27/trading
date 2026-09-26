"""
QuantPulse AI — Feature 2 API: Thesis Stress Lab.

    POST /api/thesis/create            fuse evidence into a testable thesis
    POST /api/thesis/{id}/stress-test perturb + re-fuse under 7 named rules
    GET  /api/thesis/{id}             thesis + latest stress test
    GET  /api/thesis/theses           list all theses

Confidence always comes from services.fusion.fuse. The stress test re-runs the
same function on perturbed evidence, so the delta is a measurement.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.common import mode_block
from app.models.enums import DataMode, FeatureKey, Regime
from app.models.thesis import Thesis, ThesisView
from app.services import thesis_stress

router = APIRouter(prefix="/api/thesis", tags=["thesis-stress-lab"])


class CreateThesisRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=8)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    regime: Regime = Regime.UNKNOWN
    market_state: Dict[str, float] = Field(default_factory=dict)
    event_id: str = ""
    signal_id: str = ""
    features_enabled: Optional[List[FeatureKey]] = None
    persist: bool = True


@router.post("/create")
def create(req: CreateThesisRequest):
    if not req.evidence:
        raise HTTPException(status_code=422,
                            detail="evidence must not be empty: a thesis needs "
                                   "at least one observation")
    thesis = thesis_stress.build_thesis(
        req.symbol, req.evidence, regime=req.regime,
        market_state=req.market_state, event_id=req.event_id,
        signal_id=req.signal_id, features_enabled=req.features_enabled,
    )
    if req.persist:
        from app import database as db
        db.save_thesis(thesis.model_dump())
    return {
        "thesis": thesis.model_dump(),
        "primary_evidence": thesis.primary_evidence,
        "contradictions": [c.model_dump() for c in thesis.contradictions],
        "fusion_trace": thesis.fusion_trace,
        **mode_block(thesis.data_mode),
    }


@router.get("/theses")
def list_theses(symbol: Optional[str] = None,
                limit: int = Query(default=50, ge=1, le=200)):
    from app import database as db
    try:
        from sqlmodel import Session, select
        with Session(db.get_engine()) as session:
            q = select(db.ThesisRow).order_by(db.ThesisRow.id.desc())
            if symbol:
                q = q.where(db.ThesisRow.symbol == symbol.upper())
            rows = list(session.exec(q.limit(max(1, min(limit, 200)))))
        out = []
        for r in rows:
            d = db._dump(r)
            d["payload"] = db._unjson(r.payload or "{}")
            out.append(d)
        return {"theses": out, "count": len(out),
                **mode_block(DataMode.MOCK if not out else
                             DataMode(out[0].get("data_mode", "mock")))}
    except Exception:
        return {"theses": [], "count": 0, **mode_block(DataMode.MOCK)}


@router.post("/{thesis_id}/stress-test")
def stress_test(thesis_id: str, persist: bool = True):
    from app import database as db
    row = db.get_thesis(thesis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="thesis not found")
    thesis = Thesis(**row.get("payload") or row)
    test = thesis_stress.run_stress(thesis)
    if persist:
        db.save_stress_test(test.model_dump())
    return {
        "stress_test": test.model_dump(),
        "baseline_confidence": test.baseline_confidence,
        "mean_perturbed_confidence": test.mean_perturbed_confidence,
        "worst_case_confidence": test.worst_case_confidence,
        "robustness": test.robustness,
        "fragility": test.fragility,
        "robustness_label": test.robustness_label,
        "scenarios": [s.model_dump() for s in test.scenarios],
        "notes": test.notes,
        "methodology": test.methodology,
        **mode_block(test.data_mode),
    }


@router.get("/{thesis_id}")
def get_thesis(thesis_id: str):
    from app import database as db
    row = db.get_thesis(thesis_id)
    if row is None:
        raise HTTPException(status_code=404, detail="thesis not found")
    thesis = Thesis(**row.get("payload") or row)
    latest = db.latest_stress_test(thesis_id)
    view = ThesisView(thesis=thesis, latest_stress=latest)
    return {
        "thesis": view.thesis.model_dump(),
        "latest_stress": (view.latest_stress.model_dump()
                          if view.latest_stress else None),
        "relation_wording": view.relation_wording,
        **mode_block(view.thesis.data_mode),
    }
