"""
QuantPulse AI — Feature 4: Prediction Failure Autopsy.

When a prediction resolves wrong, this module asks *which component of the
model disagreed with what actually happened* — using the evidence frozen at
issue time, not a reconstruction.

RULES
  * Verdicts compare an issued signal with the observed outcome. They describe
    agreement or disagreement, never causation.
  * `failure_mode` is chosen by an explicit rule ladder and reported with a
    likelihood, not as a proven cause. Every autopsy carries a disclaimer.
  * Performance aggregates withhold all numbers until the sample floor is met
    (`models.common.insufficient`).
"""
from __future__ import annotations

import math
import statistics
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.common import (
    INSUFFICIENT_DATA,
    clamp,
    insufficient,
    iso,
)
from app.models.enums import (
    MIN_SAMPLE_FOR_PERFORMANCE,
    DataMode,
    Direction,
    FailureMode,
    FeatureKey,
    Horizon,
    Regime,
    Verdict,
    weakest,
)
from app.models.prediction_outcome import (
    Autopsy,
    BucketPerformance,
    FailureAnalysis,
    FailureCategoryCount,
    ModelVersionComparison,
    PredictionOutcome,
    PredictionRecord,
    SignalVerdict,
)
from app.services import fusion

_FAILURE_LABELS = {
    FailureMode.REGIME_MISCLASSIFICATION: "Regime misclassification",
    FailureMode.VOLATILITY_UNDERESTIMATION: "Volatility underestimation",
    FailureMode.SENTIMENT_DECEIVERY: "Social sentiment did not persist",
    FailureMode.FLOW_DECAY: "Order-flow signal decayed after entry",
    FailureMode.PREDICTION_DIVERGENCE: "Prediction market diverged",
    FailureMode.LIQUIDITY_EXHAUSTION: "Liquidity exhausted",
    FailureMode.CONFLICTING_EVIDENCE: "Conflicting evidence at issue time",
    FailureMode.UNCLASSIFIED: "Unclassified",
}


def failure_label(mode: FailureMode) -> str:
    return _FAILURE_LABELS.get(mode, "Unclassified")


# ---------------------------------------------------------------------------
# Outcome resolution
# ---------------------------------------------------------------------------

def resolve(prediction: PredictionRecord, exit_price: float,
            realized_vol: Optional[float] = None,
            adverse_move_pct: Optional[float] = None,
            source: str = "", data_mode: Optional[DataMode] = None
            ) -> PredictionOutcome:
    """Measure a prediction against a realized price.

    `correct` is directional AND magnitude-aware: a LONG that rises less than
    the abstention floor is not counted as a win, and a LONG that falls is a
    loss regardless of size.
    """
    entry = float(prediction.entry_price or 0.0)
    move = 0.0
    if entry > 0 and exit_price > 0:
        move = (exit_price / entry - 1.0) * 100.0
    signed = move * prediction.direction.sign
    correct = signed > 0.0
    expected = float(prediction.expected_move_pct or 0.0)
    error = signed - expected
    return PredictionOutcome(
        outcome_id=f"oc_{prediction.prediction_id}_{int(time.time() * 1000)}",
        prediction_id=prediction.prediction_id,
        symbol=prediction.symbol,
        resolved_at=iso(),
        exit_price=round(float(exit_price or 0.0), 4),
        actual_move_pct=round(move, 4),
        expected_move_pct=round(expected, 4),
        error_pct=round(error, 4),
        correct=bool(correct),
        realized_vol=(round(float(realized_vol), 4)
                      if realized_vol is not None else None),
        max_adverse_move_pct=(round(float(adverse_move_pct), 4)
                              if adverse_move_pct is not None else None),
        data_mode=data_mode or prediction.data_mode,
        resolution_source=source or "supplied price",
    )


# ---------------------------------------------------------------------------
# Autopsy
# ---------------------------------------------------------------------------

def _verdict_for(feature: FeatureKey, issued_z: float, issued_share: float,
                 realized: Optional[float],
                 direction: Direction) -> SignalVerdict:
    from app.models.common import feature_label
    label = feature_label(feature)
    if realized is None:
        return SignalVerdict(
            feature=feature, label=label, verdict=Verdict.UNAVAILABLE,
            wording="no observation available at resolution",
            issued_z_score=round(issued_z, 4), contribution_share=issued_share,
            evidence=["This layer produced no resolved observation to compare."],
        )
    agree = (issued_z >= 0) == (realized >= 0) if issued_z else False
    if abs(issued_z) < 0.15:
        return SignalVerdict(
            feature=feature, label=label, verdict=Verdict.NEUTRAL,
            wording="issued signal was immaterial; no direction claimed",
            issued_z_score=round(issued_z, 4), observed_z_score=round(realized, 4),
            contribution_share=issued_share,
            evidence=[f"issued z={issued_z:+.2f} (below materiality)"],
        )
    if agree:
        return SignalVerdict(
            feature=feature, label=label, verdict=Verdict.SUPPORTED,
            wording="issued direction was observed after entry",
            issued_z_score=round(issued_z, 4), observed_z_score=round(realized, 4),
            contribution_share=issued_share,
            evidence=[f"issued z={issued_z:+.2f}; observed z={realized:+.2f} — "
                      f"same sign"],
        )
    return SignalVerdict(
        feature=feature, label=label, verdict=Verdict.CONTRADICTED,
        wording="issued direction was not observed at resolution",
        issued_z_score=round(issued_z, 4), observed_z_score=round(realized, 4),
        contribution_share=issued_share,
        evidence=[f"issued z={issued_z:+.2f}; observed z={realized:+.2f} — "
                  f"opposite sign"],
    )


def _classify_failure(verdicts: Sequence[SignalVerdict],
                      prediction: PredictionRecord,
                      outcome: PredictionOutcome,
                      realized_regime: Optional[Regime],
                      shares: Dict[str, float]) -> Tuple[FailureMode, float, List[str]]:
    """Explicit rule ladder. Returns (mode, likelihood, evidence notes)."""
    notes: List[str] = []
    by_feature = {v.feature.value: v for v in verdicts}
    contradicted = [v for v in verdicts if v.verdict is Verdict.CONTRADICTED]

    regime_mismatch = (realized_regime is not None
                       and realized_regime is not prediction.regime)
    # Compare realized vol against the issue-time expectation the thesis
    # recorded, when one was stored on the prediction's evidence.
    issued_vol_expected = shares.get("_issued_vol", 0.0) or 0.0
    vol_under = False
    if issued_vol_expected and outcome.realized_vol is not None:
        vol_under = outcome.realized_vol > issued_vol_expected * 1.5
        if vol_under:
            notes.append(
                f"realized volatility {outcome.realized_vol:.3f} exceeded the "
                f"issued expectation {issued_vol_expected:.3f}")

    if regime_mismatch:
        notes.append(f"issued regime {prediction.regime.value} but the realized "
                     f"window was labelled {realized_regime.value}")

    # Highest-contribution contradicted feature drives the mode.
    top_contradicted = max(contradicted,
                           key=lambda v: v.contribution_share) if contradicted else None

    if regime_mismatch and regime_mismatch:
        return (FailureMode.REGIME_MISCLASSIFICATION,
                round(clamp(0.5 + 0.2 * (top_contradicted.contribution_share
                                         if top_contradicted else 0.3)), 3),
                notes)
    if vol_under:
        return FailureMode.VOLATILITY_UNDERESTIMATION, 0.55, notes
    if top_contradicted and top_contradicted.feature is FeatureKey.ORDER_FLOW:
        return (FailureMode.FLOW_DECAY,
                round(clamp(0.4 + top_contradicted.contribution_share), 3), notes)
    if top_contradicted and top_contradicted.feature is FeatureKey.SOCIAL:
        return (FailureMode.SENTIMENT_DECEIVERY,
                round(clamp(0.4 + top_contradicted.contribution_share), 3), notes)
    if top_contradicted and top_contradicted.feature is FeatureKey.PREDICTION:
        return (FailureMode.PREDICTION_DIVERGENCE,
                round(clamp(0.4 + top_contradicted.contribution_share), 3), notes)
    if outcome.max_adverse_move_pct is not None and \
            abs(outcome.max_adverse_move_pct) > 1.5 * max(abs(outcome.actual_move_pct), 0.1):
        return FailureMode.LIQUIDITY_EXHAUSTION, 0.5, notes
    if len(contradicted) >= 2:
        return (FailureMode.CONFLICTING_EVIDENCE,
                round(clamp(0.3 + 0.1 * len(contradicted)), 3), notes)
    if by_feature and all(v.verdict is Verdict.SUPPORTED for v in verdicts):
        notes.append("Every stored feature was observed in the issued direction; "
                     "the failure is associated with an unmodelled factor.")
        return FailureMode.UNCLASSIFIED, 0.3, notes
    return FailureMode.UNCLASSIFIED, 0.25, notes


def run_autopsy(prediction: PredictionRecord, outcome: PredictionOutcome,
                observed_evidence: Optional[Sequence[Dict[str, Any]]] = None,
                realized_regime: Optional[Regime] = None,
                autopsy_id: Optional[str] = None) -> Autopsy:
    """Compare the frozen evidence against what was observed at resolution."""
    observed: Dict[str, float] = {}
    for row in (observed_evidence or []):
        try:
            observed[str(row.get("feature", ""))] = float(row.get("z_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue

    shares: Dict[str, float] = {}
    for row in prediction.evidence:
        feat = str(row.get("feature", ""))
        shares[feat] = max(shares.get(feat, 0.0),
                           float(row.get("contribution", 0.0) or 0.0))
        # Issue-time volatility expectation, when the thesis recorded one.
        if row.get("role") == "issued_volatility":
            try:
                shares["_issued_vol"] = float(row.get("value", 0.0) or 0.0)
            except (TypeError, ValueError):
                pass

    verdicts: List[SignalVerdict] = []
    for contrib in prediction.feature_contributions:
        feature = contrib.feature
        issued_z = 0.0
        for row in prediction.evidence:
            if str(row.get("feature", "")) == feature.value:
                try:
                    issued_z = float(row.get("z_score", 0.0) or 0.0)
                except (TypeError, ValueError):
                    issued_z = 0.0
                break
        verdicts.append(_verdict_for(
            feature, issued_z, round(contrib.share, 4),
            observed.get(feature.value), prediction.direction))

    mode, likelihood, notes = _classify_failure(verdicts, prediction, outcome,
                                               realized_regime, shares)
    modes: List[DataMode] = [prediction.data_mode, outcome.data_mode]
    return Autopsy(
        autopsy_id=autopsy_id or f"ap_{prediction.prediction_id}",
        prediction_id=prediction.prediction_id,
        symbol=prediction.symbol,
        created_at=iso(),
        direction=prediction.direction,
        confidence=prediction.confidence,
        expected_move_pct=prediction.expected_move_pct,
        actual_move_pct=outcome.actual_move_pct,
        error_pct=outcome.error_pct,
        issued_regime=prediction.regime,
        realized_regime=realized_regime,
        regime_mismatch=bool(realized_regime is not None
                             and realized_regime is not prediction.regime),
        failure_mode=mode,
        mode_likelihood=likelihood,
        verdicts=verdicts,
        evidence_notes=notes,
        data_mode=weakest(*modes),
        model_version=prediction.model_version,
    )


# ---------------------------------------------------------------------------
# Aggregate failure analysis
# ---------------------------------------------------------------------------

def _wilson(successes: int, n: int, z: float = 1.96) -> List[float]:
    if n <= 0:
        return [0.0, 0.0]
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4)]


def _bucket(name: str, rows: Sequence[Tuple[PredictionRecord, PredictionOutcome]],
            min_n: int = 5) -> BucketPerformance:
    n = len(rows)
    if n < min_n:
        return BucketPerformance(
            bucket=name, resolved=n, correct=sum(1 for _, o in rows if o.correct),
            status="insufficient_data", label=INSUFFICIENT_DATA,
        )
    correct = sum(1 for _, o in rows if o.correct)
    errs = [abs(o.error_pct) for _, o in rows]
    confs = [p.confidence for p, _ in rows]
    return BucketPerformance(
        bucket=name, resolved=n, correct=correct,
        accuracy=round(correct / n, 4),
        mean_error_pct=round(statistics.fmean(errs), 4),
        mean_confidence=round(statistics.fmean(confs), 4),
        accuracy_ci=_wilson(correct, n),
        status="ok",
    )


def failure_analysis(pairs: Sequence[Tuple[PredictionRecord, PredictionOutcome]],
                     autopsies: Sequence[Autopsy] = (),
                     data_mode: Optional[DataMode] = None,
                     min_n: int = MIN_SAMPLE_FOR_PERFORMANCE) -> FailureAnalysis:
    """Aggregate performance. Returns INSUFFICIENT DATA below the floor."""
    total = len(pairs) + len([a for a in autopsies]) * 0  # total tracked elsewhere
    resolved = len(pairs)
    if resolved < min_n:
        return FailureAnalysis(
            status="insufficient_data",
            label=INSUFFICIENT_DATA,
            total_predictions=total,
            resolved_predictions=resolved,
            unresolved_predictions=max(0, total - resolved),
            data_mode=data_mode or DataMode.MOCK,
            generated_at=iso(),
            insufficiency=insufficient("model performance statistics",
                                        resolved, min_n),
            note=("Statistics are withheld until the resolved-observation floor "
                  "is met. No partial numbers are shown."),
        )

    correct = sum(1 for _, o in pairs if o.correct)
    errs = [o.error_pct for _, o in pairs]
    confs = [p.confidence for p, _ in pairs]
    brier = _brier(pairs)
    return FailureAnalysis(
        status="ok",
        total_predictions=total,
        resolved_predictions=resolved,
        unresolved_predictions=max(0, total - resolved),
        accuracy=round(correct / resolved, 4),
        mean_error_pct=round(statistics.fmean(errs), 4),
        mean_confidence=round(statistics.fmean(confs), 4),
        brier_score=brier,
        calibration_bins=_calibration(pairs),
        failure_categories=_failure_categories(autopsies, pairs),
        by_regime=[_bucket(r.value, [p for p in pairs
                                     if p[0].regime.value == r.value])
                   for r in Regime if r is not Regime.UNKNOWN],
        by_signal_type=[_bucket(d.value, [p for p in pairs
                                          if p[0].direction.value == d.value])
                        for d in Direction],
        by_horizon=[_bucket(h.value, [p for p in pairs
                                      if p[0].horizon.value == h.value])
                    for h in Horizon],
        by_model_version=_by_version(pairs),
        data_mode=weakest(*[o.data_mode for _, o in pairs]),
        generated_at=iso(),
        note=(f"Computed over {resolved} resolved observations. Accuracy is "
              f"directional; error is actual-minus-expected in percentage "
              f"points."),
    )


def _brier(pairs: Sequence[Tuple[PredictionRecord, PredictionOutcome]]
           ) -> Optional[float]:
    """Brier score on direction, using confidence as the probability."""
    if not pairs:
        return None
    total = 0.0
    for p, o in pairs:
        prob = clamp(p.confidence if p.direction is Direction.LONG
                     else 1.0 - p.confidence)
        actual = 1.0 if o.correct else 0.0
        total += (prob - actual) ** 2
    return round(total / len(pairs), 4)

def _calibration(pairs: Sequence[Tuple[PredictionRecord, PredictionOutcome]],
                 bins: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    edges = [i / bins for i in range(bins + 1)]
    for i in range(bins):
        lo, hi = edges[i], edges[i + 1]
        rows = [(p, o) for p, o in pairs if lo <= clamp(p.confidence) < hi
                or (i == bins - 1 and clamp(p.confidence) == 1.0)]
        if not rows:
            continue
        correct = sum(1 for _, o in rows if o.correct)
        out.append({
            "bin": f"{lo:.1f}-{hi:.1f}",
            "n": len(rows),
            "mean_confidence": round(statistics.fmean([p.confidence for p, _ in rows]), 4),
            "accuracy": round(correct / len(rows), 4),
            "accuracy_ci": _wilson(correct, len(rows)),
        })
    return out


def _failure_categories(autopsies: Sequence[Autopsy],
                        pairs: Sequence[Tuple[PredictionRecord, PredictionOutcome]]
                        ) -> List[FailureCategoryCount]:
    err_by_pred = {o.prediction_id: o.error_pct for _, o in pairs}
    buckets: Dict[FailureMode, List[float]] = defaultdict(list)
    for a in autopsies:
        buckets[a.failure_mode].append(err_by_pred.get(a.prediction_id, 0.0))
    total = sum(len(v) for v in buckets.values()) or 1
    return sorted(
        [FailureCategoryCount(
            failure_mode=mode, label=failure_label(mode), count=len(vals),
            share=round(len(vals) / total, 4),
            mean_error_pct=round(statistics.fmean(vals), 4))
         for mode, vals in buckets.items()],
        key=lambda c: -c.count)


def _by_version(pairs: Sequence[Tuple[PredictionRecord, PredictionOutcome]]
                ) -> List[ModelVersionComparison]:
    groups: Dict[str, List[Tuple[PredictionRecord, PredictionOutcome]]] = defaultdict(list)
    for p, o in pairs:
        groups[p.model_version].append((p, o))
    out: List[ModelVersionComparison] = []
    for version, rows in groups.items():
        correct = sum(1 for _, o in rows if o.correct)
        out.append(ModelVersionComparison(
            model_version=version,
            predictions=len(rows), resolved=len(rows),
            accuracy=round(correct / len(rows), 4) if len(rows) >= 5 else None,
            mean_error_pct=(round(statistics.fmean([o.error_pct for _, o in rows]), 4)
                            if len(rows) >= 5 else None),
            brier_score=_brier(rows) if len(rows) >= 5 else None,
            status="ok" if len(rows) >= 5 else "insufficient_data",
        ))
    return sorted(out, key=lambda m: m.model_version)
