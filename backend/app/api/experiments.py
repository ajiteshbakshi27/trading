"""
QuantPulse AI — Feature 5 API: Adaptive Signal Tournament.

    POST /api/experiments            create an ablation spec (draft)
    GET  /api/experiments            list experiments
    GET  /api/experiments/{id}       one experiment + result if run
    POST /api/experiments/{id}/run   run the arm over the declared window
    GET  /api/experiments/{id}/results
    GET  /api/experiments/matrix     rows=arms, columns=regimes

Arms differ only in which features are enabled. Every arm calls the same
fusion function over the same window, so a delta is attributable to the
ablation. Results carry sample sizes; thin cells report INSUFFICIENT DATA.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.common import INSUFFICIENT_DATA, mode_block
from app.models.enums import DataMode, FeatureKey
from app.models.experiment import EvaluationMethod, ExperimentSpec, WindowSpec
from app.services import signal_tournament as st

router = APIRouter(prefix="/api/experiments", tags=["signal-tournament"])


class CreateExperimentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    features_disabled: List[FeatureKey] = Field(default_factory=list)
    n_observations: int = Field(default=60, ge=10, le=500)
    seed: int = Field(default=7, ge=0, le=10_000)
    symbols: List[str] = Field(default_factory=lambda: ["NVDA"])
    persist: bool = True


@router.post("")
def create(req: CreateExperimentRequest):
    observations, window = st.build_observation_set(
        req.symbols, n=req.n_observations, seed=req.seed)
    spec = st.make_spec(req.name, req.features_disabled, window)
    if req.persist:
        from app import database as db
        db.save_experiment(spec.model_dump())
    return {
        "experiment": spec.model_dump(),
        "status": "draft",
        "note": ("A spec has no metrics until it is run. Use "
                 "POST /api/experiments/{id}/run."),
        **mode_block(spec.data_mode),
    }


@router.get("")
def list_experiments(limit: int = 50):
    from app import database as db
    rows = db.list_experiments(limit=limit)
    for row in rows:
        row["features_enabled"] = db._unjson(row.get("features_enabled") or "[]")
        row["features_disabled"] = db._unjson(row.get("features_disabled") or "[]")
    return {"experiments": rows, "count": len(rows),
            **mode_block(DataMode.MOCK if not rows else
                         DataMode(rows[0].get("data_mode", "mock")))}


@router.get("/matrix")
def matrix(min_n: int = 20):
    """Rows = arms, columns = regimes. Thin cells report INSUFFICIENT DATA."""
    suite = st.run_suite(["NVDA"], n=60, seed=7)
    m = st.build_matrix(suite, min_n=min_n)
    return {
        "matrix": m.model_dump(),
        "metric": m.metric,
        "status": m.status,
        "label": m.label,
        "sample_size": m.sample_size,
        "required_sample_size": m.required_sample_size,
        "note": m.note,
        "caveat": ("Differences are measured inside QuantPulse's fusion function "
                   "on this window only. They quantify marginal contribution to "
                   "this model, not predictive edge in the market."),
        **mode_block(m.data_mode),
    }


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    from app import database as db
    row = db.get_experiment(experiment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    row["features_enabled"] = db._unjson(row.get("features_enabled") or "[]")
    row["features_disabled"] = db._unjson(row.get("features_disabled") or "[]")
    result = db.get_experiment_result(experiment_id)
    return {
        "experiment": row,
        "result": result,
        "status": row.get("status", "draft"),
        **mode_block(DataMode(row.get("data_mode", "mock"))),
    }


@router.post("/{experiment_id}/run")
def run(experiment_id: str, persist: bool = True):
    from app import database as db
    row = db.get_experiment(experiment_id)
    if row is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    payload = row.get("payload") or {}
    disabled = [FeatureKey(f) for f in (payload.get("features_disabled")
                                       or row.get("features_disabled") or [])]
    window = WindowSpec(
        label=row.get("window_label", ""),
        start=row.get("window_start", ""), end=row.get("window_end", ""),
        n_observations=int(row.get("n_observations", 0) or 0),
        seed=int(row.get("seed", 7) or 7),
        data_mode=DataMode(row.get("data_mode", "mock")),
    )
    observations, _ = st.build_observation_set(
        ["NVDA"], n=max(10, window.n_observations or 60), seed=window.seed)
    result = st.run_arm(row.get("name", experiment_id), "", disabled,
                        observations, window, experiment_id=experiment_id)
    if persist:
        db.save_experiment_result(result.model_dump())
        db.save_experiment({**payload, "experiment_id": experiment_id,
                            "status": "completed"})
    return {
        "result": result.model_dump(),
        "n_observations": result.n_observations,
        "sample_size_note": result.sample_size_note,
        "caveat": result.caveat,
        **mode_block(result.data_mode),
    }


@router.get("/{experiment_id}/results")
def results(experiment_id: str):
    from app import database as db
    row = db.get_experiment_result(experiment_id)
    if row is None:
        return {
            "status": "not_run",
            "label": INSUFFICIENT_DATA,
            "note": "This experiment has not been run yet.",
            **mode_block(DataMode.MOCK),
        }
    return {"result": row, **mode_block(DataMode(row.get("data_mode", "mock")))}
