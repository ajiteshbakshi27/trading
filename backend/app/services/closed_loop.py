"""
QuantPulse AI — The closed research loop.

One orchestrator, one direction of travel:

    MarketEvent → Evidence → Signal → Thesis → Stress → Prediction
                → Outcome → Autopsy → Experiment → model evidence

Every stage calls the same `services.fusion.fuse`. Nothing in this module
computes a confidence of its own; it only sequences the stages and persists
what each produced. That is what makes the stress delta, the ablation delta
and the dashboard number directly comparable.

`run_live_cycle` runs the loop against whatever the feeds currently report.
`run_scenario_cycle` runs the deterministic SIMULATED narrative.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app import database as db
from app.models.common import iso, utcnow
from app.models.enums import (
    DataMode,
    Direction,
    EventCategory,
    EventType,
    FeatureKey,
    FailureMode,
    Horizon,
    Layer,
    Regime,
    weakest,
)
from app.models.information_event import Evidence, InformationEvent, MarketEvent
from app.models.prediction_outcome import (
    Autopsy,
    PredictionOutcome,
    PredictionRecord,
)
from app.models.thesis import StressTest, Thesis
from app.services import (
    event_transmission,
    feed_layer,
    fusion,
    information_propagation,
    prediction_autopsy,
    scenarios,
    signal_tournament,
    thesis_stress,
)

MODEL_VERSION = "qp-fusion-1.0"

#: Expected move implied by a confidence, for the prediction's target. Linear
#: in confidence between these two points; documented as a model convention.
_MOVE_AT_FLOOR_PCT = 1.0
_MOVE_AT_CEILING_PCT = 4.0


def expected_move_pct(confidence: float) -> float:
    span = _MOVE_AT_CEILING_PCT - _MOVE_AT_FLOOR_PCT
    return round(_MOVE_AT_FLOOR_PCT + max(0.0, min(1.0, confidence)) * span, 3)


def _evidence_rows(evidence: Sequence[Evidence], regime: Regime,
                   real: Optional[Sequence[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Flatten Evidence into fusion-input dicts, tagging regime metadata."""
    by_feature: Dict[str, List[Dict[str, Any]]] = {}
    for ev in evidence:
        row = {
            "evidence_id": ev.evidence_id,
            "event_id": ev.event_id,
            "symbol": ev.symbol,
            "layer": ev.layer.value,
            "feature": ev.feature,
            "z_score": ev.z_score,
            "magnitude": ev.magnitude,
            "direction": ev.direction.value,
            "confidence": ev.confidence,
            "observed_at": ev.observed_at,
            "data_mode": ev.data_mode.value,
            "source_label": ev.source_label,
            "raw": ev.raw,
        }
        by_feature.setdefault(ev.feature, []).append(row)
    out: List[Dict[str, Any]] = []
    for rows in by_feature.values():
        # Co-located observations of one feature are averaged, so a symbol
        # with 12 Reddit posts does not outvote 3 order-flow readings.
        merged = dict(rows[0])
        merged["z_score"] = round(sum(r["z_score"] for r in rows) / len(rows), 4)
        merged["confidence"] = round(max(r["confidence"] for r in rows), 4)
        merged["n_observations"] = len(rows)
        merged["layers"] = sorted({r["layer"] for r in rows},
                                  key=lambda l: Layer(l).order)
        merged["regime"] = regime.value
        out.append(merged)
    for row in (real or []):
        row = dict(row)
        row.setdefault("regime", regime.value)
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Stage 1-4: event → evidence → signal → thesis
# ---------------------------------------------------------------------------

def _market_state(book: Optional[Dict[str, Any]],
                  regime_metrics: Dict[str, float]) -> Dict[str, float]:
    state = dict(regime_metrics)
    if book:
        state.setdefault("spread_bps", float(book.get("spread_bps", 0.0) or 0.0))
        state.setdefault("mid", float(book.get("mid", 0.0) or 0.0))
    return state


def analyse(symbol: str, evidence_rows: List[Dict[str, Any]],
            regime: Regime, market_state: Dict[str, float],
            event_id: str = "", persist: bool = True) -> Dict[str, Any]:
    """Fuse evidence into a signal + thesis and persist both."""
    fused = fusion.fuse(evidence_rows)
    signal_id = f"sg_{symbol}_{int(time.time() * 1000)}"
    components = fused.get("components") or {}
    total = sum(abs(float(v)) for v in components.values()) or 1.0
    signal = {
        "signal_id": signal_id,
        "event_id": event_id,
        "symbol": symbol.upper(),
        "direction": fused["direction"].value,
        "confidence": fused["confidence"],
        "fused_score": fused["fused_score"],
        "regime": regime.value,
        "evidence_ids": [r.get("evidence_id") for r in evidence_rows],
        "data_mode": fused["data_mode"].value,
        "model_version": MODEL_VERSION,
        "components": components,
        "contributions": {k: round(abs(float(v)) / total, 4)
                          for k, v in components.items()},
        "abstaining": bool(fused.get("abstaining")),
        "trace": fused["trace"],
    }
    thesis = thesis_stress.build_thesis(
        symbol, evidence_rows, regime=regime, market_state=market_state,
        event_id=event_id, signal_id=signal_id, model_version=MODEL_VERSION,
    )
    thesis = thesis.model_copy(update={"data_mode": fused["data_mode"]})

    if persist:
        db.save_signal(signal)
        db.save_thesis(thesis.model_dump())
    return {"signal": signal, "thesis": thesis, "fused": fused,
            "regime": regime, "market_state": market_state}


# ---------------------------------------------------------------------------
# Stage 5-6: stress + prediction
# ---------------------------------------------------------------------------

def stress(thesis: Thesis, persist: bool = True) -> StressTest:
    test = thesis_stress.run_stress(thesis)
    if persist:
        db.save_stress_test(test.model_dump())
    return test


def create_prediction(thesis: Thesis, entry_price: float,
                      horizon: Horizon = Horizon.H1, regime: Optional[Regime] = None,
                      persist: bool = True) -> PredictionRecord:
    """Freeze the thesis into a dated, directional prediction.

    The evidence snapshot and feature contributions are stored on the record
    so the autopsy can read exactly what the model saw.
    """
    from app.models.prediction_outcome import FeatureContribution
    trace_rows = (thesis.fusion_trace or {}).get("features", [])
    total = sum(abs(float(r["contribution"])) for r in trace_rows
                if r.get("usable")) or 1.0
    contributions = []
    for row in trace_rows:
        try:
            feature = FeatureKey(str(row["feature"]))
        except ValueError:
            continue
        contrib = float(row["contribution"])
        contributions.append(FeatureContribution(
            feature=feature, weight=float(row["weight"]),
            z_score=float(row["z_score"]), contribution=round(contrib, 4),
            share=round(abs(contrib) / total, 4),
        ))
    minutes = horizon.minutes
    record = PredictionRecord(
        prediction_id=f"pr_{thesis.thesis_id}_{int(time.time() * 1000)}",
        thesis_id=thesis.thesis_id,
        signal_id=thesis.signal_id,
        event_id=thesis.event_id,
        symbol=thesis.symbol,
        direction=thesis.direction,
        confidence=thesis.confidence,
        fused_score=thesis.fused_score,
        entry_price=round(float(entry_price or 0.0), 4),
        expected_move_pct=expected_move_pct(thesis.confidence),
        horizon=horizon,
        created_at=iso(),
        expires_at=iso(time.time() + minutes * 60),
        regime=regime or thesis.regime,
        model_version=thesis.model_version,
        data_mode=thesis.data_mode,
        evidence=thesis.evidence,
        feature_contributions=contributions,
        status="open",
    )
    if persist:
        db.save_prediction(record.model_dump())
    return record


# ---------------------------------------------------------------------------
# Stage 7-8: outcome + autopsy
# ---------------------------------------------------------------------------

def resolve_and_autopsy(prediction: PredictionRecord, exit_price: float,
                        observed_evidence: Optional[Sequence[Dict[str, Any]]] = None,
                        realized_vol: Optional[float] = None,
                        realized_regime: Optional[Regime] = None,
                        adverse_move_pct: Optional[float] = None,
                        source: str = "", data_mode: Optional[DataMode] = None,
                        persist: bool = True) -> Tuple[PredictionOutcome, Optional[Autopsy]]:
    """Resolve, then — if the prediction was wrong — run the autopsy.

    Returns (outcome, autopsy|None). A correct prediction yields no autopsy;
    successes are not silently converted into "lessons".
    """
    outcome = prediction_autopsy.resolve(
        prediction, exit_price, realized_vol=realized_vol,
        adverse_move_pct=adverse_move_pct, source=source, data_mode=data_mode)
    if persist:
        db.save_outcome(outcome.model_dump())
        db.mark_prediction_resolved(prediction.prediction_id)
    if outcome.correct:
        return outcome, None
    autopsy = prediction_autopsy.run_autopsy(
        prediction, outcome, observed_evidence=observed_evidence,
        realized_regime=realized_regime)
    if persist:
        db.save_autopsy(autopsy.model_dump())
    return outcome, autopsy


# ---------------------------------------------------------------------------
# Live cycle
# ---------------------------------------------------------------------------

def run_live_cycle(books: Sequence[Dict[str, Any]], sentiment: Dict[str, Any],
                   markets: Sequence[Dict[str, Any]], news: Sequence[Any],
                   symbol: Optional[str] = None,
                   persist: bool = True) -> Dict[str, Any]:
    """Detect → propagate → fuse → thesis for the live snapshot."""
    mode = _snapshot_mode(books, sentiment, news)
    events = information_propagation.detect_events(
        books, sentiment, markets, news, mode=mode)
    if symbol:
        events = [e for e in events if e.symbol == symbol.upper()] or events
    if not events:
        return {"status": "no_event",
                "note": "No layer crossed its materiality threshold in this "
                        "snapshot, so no event was opened.",
                "data_mode": mode}

    event = events[0]
    evidence = information_propagation.collect_evidence(
        event, books=books, sentiment=sentiment, markets=markets, news=news)
    rows = _evidence_rows(evidence, Regime.UNKNOWN)
    fused = fusion.fuse(rows)
    chain = information_propagation.build_chain(
        event, evidence, fused,
        observed=any(e.data_mode is DataMode.LIVE for e in evidence))

    book = next((b for b in books if b["symbol"] == event.symbol), None)
    regime, metrics = fusion.regime_from_snapshot(book, _price_tail(book))
    rows = _evidence_rows(evidence, regime, real=rows)
    state = _market_state(book, metrics)
    analysis = analyse(event.symbol, rows, regime, state, event_id=event.event_id,
                       persist=persist)
    if persist:
        db.save_market_event(event.model_dump())
        db.save_evidence([r for r in rows if r.get("evidence_id")])

    graph = event_transmission.build_graph(
        event, [r["feature"] for r in rows],
        history=_historical_index(), data_mode=mode)
    return {
        "status": "ok",
        "event": event,
        "chain": chain,
        "evidence": rows,
        "graph": graph,
        "analysis": analysis,
        "regime": regime,
        "regime_metrics": metrics,
        "market_state": state,
        "data_mode": chain.rollup_mode(),
    }


def _price_tail(book: Optional[Dict[str, Any]], n: int = 24) -> List[float]:
    if not book:
        return []
    bids = [float(l["price"]) for l in book.get("bids", [])]
    return list(reversed(bids))[-n:]


def _snapshot_mode(books: Sequence[Dict[str, Any]], sentiment: Dict[str, Any],
                   news: Sequence[Any]) -> DataMode:
    modes = []
    for b in books:
        if b.get("stream"):
            modes.append(DataMode.LIVE)
        elif b.get("live"):
            modes.append(DataMode.LIVE)
        else:
            modes.append(DataMode.MOCK)
    for n in news:
        modes.append(getattr(n, "data_mode", DataMode.MOCK))
    for p in (sentiment or {}).get("posts", []):
        try:
            modes.append(DataMode(str(p.get("data_mode", "mock"))))
        except ValueError:
            modes.append(DataMode.MOCK)
    return weakest(*modes) if modes else DataMode.MOCK


def _historical_index() -> Dict[str, List[Dict[str, Any]]]:
    """Resolved outcomes grouped by symbol, for transmission history.

    Only records that actually carry a realized move are indexed; an
    unresolved prediction contributes nothing rather than a zero.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for pair in db.resolved_pairs(limit=1000):
        pred, outcome = pair["prediction"], pair["outcome"]
        payload = db.get_thesis(pred.get("thesis_id", "")) or {}
        event_type = (payload.get("payload") and "news") or "news"
        try:
            event_type = _event_type_of(pred) or "news"
        except Exception:
            pass
        out.setdefault(str(pred.get("symbol", "")).upper(), []).append({
            "symbol": pred.get("symbol"),
            "event_type": event_type,
            "response_pct": outcome.get("actual_move_pct"),
            "created_at": str(pred.get("created_at", "")),
            "data_mode": outcome.get("data_mode", "mock"),
        })
    return out


def _event_type_of(pred: Dict[str, Any]) -> str:
    """Event type a prediction descended from, via its stored event."""
    event_id = pred.get("event_id")
    if not event_id:
        return "news"
    row = db.get_market_event(str(event_id))
    return str((row or {}).get("event_type", "news"))


# ---------------------------------------------------------------------------
# Scenario cycle (deterministic demo)
# ---------------------------------------------------------------------------

def run_scenario_cycle(persist: bool = True) -> Dict[str, Any]:
    """Walk the full loop on the deterministic SIMULATED scenario."""
    payload = scenarios.event_payload()
    event = MarketEvent(**payload)
    mode = DataMode.SIMULATED

    evidence = [Evidence(**row) for row in scenarios.evidence_payload()]
    rows = _evidence_rows(evidence, scenarios.EXPECTED_REGIME)
    fused = fusion.fuse(rows)

    chain = InformationEvent(
        event_id=event.event_id, symbol=event.symbol, event_type=event.event_type,
        detected_at=event.detected_at, sources=["scenario"],
        confidence=fused["confidence"], data_mode=mode,
        model_version=MODEL_VERSION, headline=event.headline,
    )
    steps = []
    from app.models.information_event import PropagationStep
    for item in scenarios.chain_payload():
        steps.append(PropagationStep(
            step_id=item["step_id"], layer=Layer(item["layer"]),
            timestamp=item["timestamp"], lag_s=item["lag_s"],
            signal=item["signal"], magnitude=item["magnitude"],
            direction=(Direction.LONG if (item["z_score"] or 0) > 0
                       else Direction.SHORT),
            confidence=item["confidence"], freshness="realtime",
            data_mode=mode, contribution=abs(item["z_score"]) / 3.0,
            relation="synthetic sequence step",
            source_label=item["source_label"],
        ))
    chain = chain.model_copy(update={"propagation_steps": steps})

    state = scenarios.market_state()
    analysis = analyse(event.symbol, rows, scenarios.EXPECTED_REGIME, state,
                       event_id=event.event_id, persist=persist)

    # Stamp the resolved outcome onto the evidence rows so they become usable
    # tournament samples. Without an actual move, a row cannot be scored.
    exit_move = float(scenarios.outcome_payload()["exit_move_pct"])
    for row in rows:
        row["actual_move_pct"] = round(row.get("z_score", 0.0) * exit_move, 4)
        row["realized_vol"] = float(scenarios.outcome_payload()["realized_vol"])
        row["regime"] = scenarios.EXPECTED_REGIME.value

    graph = event_transmission.build_graph(
        event, [r["feature"] for r in rows], history={}, data_mode=mode)
    if persist:
        db.save_market_event(event.model_dump())
        db.save_evidence(rows)

    thesis: Thesis = analysis["thesis"]
    test = stress(thesis, persist=persist)
    outcome_cfg = scenarios.outcome_payload()
    entry = float(outcome_cfg["entry_price"])
    prediction = create_prediction(thesis, entry,
                                   horizon=scenarios.OUTCOME["horizon"],
                                   persist=persist)
    exit_price = round(entry * (1 + float(outcome_cfg["exit_move_pct"]) / 100.0), 4)
    outcome, autopsy = resolve_and_autopsy(
        prediction, exit_price,
        observed_evidence=outcome_cfg["observed_evidence"],
        realized_vol=outcome_cfg["realized_vol"],
        realized_regime=Regime(outcome_cfg["realized_regime"]),
        adverse_move_pct=outcome_cfg["exit_move_pct"],
        source=outcome_cfg["resolution_source"], data_mode=mode,
        persist=persist)

    suite = signal_tournament.run_suite(["NVDA"], n=scenarios.TOURNAMENT_N,
                                        seed=scenarios.TOURNAMENT_SEED)
    results = signal_tournament.attach_deltas(suite)
    matrix = signal_tournament.build_matrix(suite)
    if persist:
        for res in results:
            db.save_experiment_result(res.model_dump())
            db.save_experiment({
                "experiment_id": res.experiment_id, "name": res.name,
                "model_version": res.model_version, "status": "completed",
                "window": suite["window"].model_dump(),
                "methodology": suite["methodology"].model_dump(),
                "data_mode": res.data_mode, "fingerprint": res.fingerprint,
            })

    return {
        "status": "ok",
        "scenario_id": scenarios.SCENARIO_ID,
        "scenario_label": scenarios.SCENARIO_LABEL,
        "event": event,
        "chain": chain,
        "evidence": rows,
        "graph": graph,
        "analysis": analysis,
        "thesis": thesis,
        "stress": test,
        "prediction": prediction,
        "outcome": outcome,
        "autopsy": autopsy,
        "tournament": {"results": results, "matrix": matrix,
                       "window": suite["window"],
                       "methodology": suite["methodology"]},
        "data_mode": mode,
    }
