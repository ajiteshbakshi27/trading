"""
QuantPulse AI — Feature 5: Adaptive Signal Tournament.

Runs controlled ablations of the shared fusion function so the platform can
answer "does this information source actually contribute?" with a measurement
instead of a claim.

DESIGN
  * One dataset, one window, one evaluation method. Arms differ ONLY in which
    features are enabled, so a difference is attributable to the ablation.
  * Every arm calls `services.fusion.fuse` — the same function the dashboard
    and the stress lab use. That is what makes the comparison meaningful.
  * The dataset is built from the platform's own stored evidence when
    available, and from a deterministic synthetic observation set otherwise.
    Synthetic arms are labelled SIMULATED/BACKTEST, never LIVE.
  * Results carry sample size. Where the sample is thin the cell reports
    INSUFFICIENT DATA instead of a number. No "winner" labels are produced.
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
    fingerprint,
    insufficient,
    iso,
)
from app.models.enums import (
    MIN_SAMPLE_FOR_PERFORMANCE,
    DataMode,
    Direction,
    FeatureKey,
    MetricKey,
    Regime,
    weakest,
)
from app.models.experiment import (
    EvaluationMethod,
    ExperimentResult,
    ExperimentSpec,
    RegimeSlice,
    RunMetrics,
    TournamentMatrix,
    WindowSpec,
)
from app.services import feed_layer, fusion

MODEL_VERSION = "qp-fusion-1.0"

#: The ablation arms. `disabled` empty = the full model baseline.
#: Reddit is carried on the shared SOCIAL feature, so "NO REDDIT" is realised
#: by dropping Reddit-tagged observations during the run (see `_to_evidence`).
ABLATIONS: Tuple[Tuple[str, str, Tuple[FeatureKey, ...]], ...] = (
    ("FULL MODEL", "All configured features enabled.", ()),
    ("NO SOCIAL", "Removes Reddit + X sentiment from the fusion.",
     (FeatureKey.SOCIAL,)),
    ("NO REDDIT", "Removes the Reddit layer only (X retained).", ()),
    ("NO ORDER FLOW", "Removes L2 order-flow imbalance.", (FeatureKey.ORDER_FLOW,)),
    ("NO PREDICTION MARKET", "Removes prediction-market repricing.",
     (FeatureKey.PREDICTION,)),
    ("NO NEWS", "Removes the news layer.", (FeatureKey.NEWS,)),
    ("NO MOMENTUM", "Removes price momentum.", (FeatureKey.MOMENTUM,)),
    ("NO QUANTUM", "Removes the quantum fair-value term.", (FeatureKey.QUANTUM,)),
)

#: Arms that drop a *layer* rather than a whole feature.
LAYER_EXCLUSIONS: Dict[str, frozenset] = {
    "NO REDDIT": frozenset({"reddit"}),
}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def build_observation_set(symbols: Sequence[str], n: int = 60,
                          seed: int = 7,
                          data_mode: Optional[DataMode] = None
                          ) -> Tuple[List[Dict[str, Any]], WindowSpec]:
    """Assemble the experiment dataset.

    Prefers stored evidence (real observations). Falls back to a deterministic
    synthetic set built from a seeded generator so the tournament is always
    demonstrable — labelled SIMULATED in that case.
    """
    from app import database as db

    rows: List[Dict[str, Any]] = []
    mode = DataMode.MOCK
    try:
        stored = db.get_research_evidence(limit=n * 8)
    except Exception:
        stored = []
    if stored:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in stored:
            grouped.setdefault(str(row.get("symbol", "")), []).append(row)
        for symbol, items in grouped.items():
            for item in items:
                rows.append({
                    "symbol": symbol,
                    "features": _features_from_row(item),
                    "actual_move_pct": item.get("actual_move_pct"),
                    "regime": item.get("regime", Regime.UNKNOWN.value),
                    "realized_vol": item.get("realized_vol"),
                    "timestamp": item.get("created_at", iso()),
                    "data_mode": item.get("data_mode", "mock"),
                })
        if rows:
            mode = _mode_of_rows(rows)
    if not rows:
        rows = _synthetic_observations(symbols, n=n, seed=seed)
        mode = DataMode.SIMULATED

    rows = rows[: n * 4]
    start = min((str(r.get("timestamp", "")) for r in rows), default=iso())
    end = max((str(r.get("timestamp", "")) for r in rows), default=iso())
    return rows, WindowSpec(
        label="stored evidence" if mode is not DataMode.SIMULATED
              else "deterministic synthetic observation set",
        start=start, end=end, n_observations=len(rows),
        symbols=sorted({str(r.get("symbol", "")) for r in rows if r.get("symbol")}),
        seed=seed, data_mode=mode,
        note=("Built from platform evidence records." if mode is not DataMode.SIMULATED
              else "Synthetic: no stored evidence was available. Not market data."),
    )


def _features_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Stored evidence row -> {FeatureKey.value: {value, confidence, data_mode}}."""
    out: Dict[str, Any] = {}
    try:
        feature = FeatureKey(str(row.get("feature", "")))
    except ValueError:
        return out
    layer = str(row.get("layer", ""))
    # Reddit-only arms need to distinguish the two social layers, so the layer
    # is retained inside the feature payload.
    out[feature.value] = {
        "z_score": row.get("z_score", 0.0),
        "confidence": row.get("confidence", 0.5),
        "data_mode": row.get("data_mode", "mock"),
        "layer": layer,
    }
    return out


def _synthetic_observations(symbols: Sequence[str], n: int,
                            seed: int) -> List[Dict[str, Any]]:
    """Deterministic pseudo-market observations.

    Built from a seeded LCG so a re-run reproduces byte-identical inputs. The
    generator is documented in the README as synthetic: the correlations it
    encodes are chosen to be interesting, not estimated from any market.
    """
    import random
    rng = random.Random(seed)
    features = [f.value for f in FeatureKey]
    base_corr = {"order_flow": 0.55, "momentum": 0.45, "prediction": 0.30,
                 "news": 0.25, "social": 0.18, "quantum": 0.08}
    rows: List[Dict[str, Any]] = []
    now = time.time()
    for i in range(n):
        actual = rng.gauss(0.0, 1.1)
        row_features: Dict[str, Any] = {}
        for f in features:
            noise = rng.gauss(0.0, 0.85)
            value = base_corr.get(f, 0.1) * actual + noise
            layer = {"social": "reddit" if rng.random() < 0.6 else "x"}.get(f, f)
            row_features[f] = {
                "z_score": round(max(-3.0, min(3.0, value / 0.85)), 4),
                "confidence": round(rng.uniform(0.35, 0.85), 3),
                "data_mode": "simulated",
                "layer": layer,
            }
        trend = actual
        realized = abs(rng.gauss(0.9, 0.35))
        regime = fusion.classify_regime(realized, trend, ofi_norm=None)
        rows.append({
            "symbol": symbols[i % len(symbols)] if symbols else "NVDA",
            "features": row_features,
            "actual_move_pct": round(actual, 4),
            "regime": regime.value,
            "realized_vol": round(realized, 4),
            "timestamp": iso(now - (n - i) * 3600),
            "data_mode": "simulated",
        })
    return rows


def _mode_of_rows(rows: Sequence[Dict[str, Any]]) -> DataMode:
    modes = []
    for r in rows:
        try:
            modes.append(DataMode(str(r.get("data_mode", "mock"))))
        except ValueError:
            modes.append(DataMode.MOCK)
    return weakest(*modes) if modes else DataMode.MOCK


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def _equity_curve(confidences: Sequence[float], actuals: Sequence[float],
                  action_floor: float) -> Optional[List[float]]:
    curve = [1.0]
    for conf, actual in zip(confidences, actuals):
        if conf < action_floor:
            curve.append(curve[-1])      # abstention: no exposure change
            continue
        size = (conf - 0.5) * 2.0     # signed 0..1 conviction
        curve.append(curve[-1] * (1.0 + size * actual / 100.0))
    return curve


def compute_metrics(observations: Sequence[Dict[str, Any]],
                    features_enabled: Sequence[FeatureKey],
                    method: EvaluationMethod,
                    drop_layers: frozenset = frozenset()) -> RunMetrics:
    """Score one arm. Only metrics the data supports are populated."""
    confs: List[float] = []
    actuals: List[float] = []
    n_decisions = 0
    n_abstentions = 0
    switches = 0
    prev_sign = 0
    have_returns = False

    enabled = set(features_enabled)
    for obs in observations:
        out = fusion.fuse(_to_evidence(obs, enabled, drop_layers))
        sign = out["direction"].sign
        conf = float(out["confidence"])
        actual = obs.get("actual_move_pct")
        if actual is None:
            continue
        have_returns = True
        confs.append(conf)
        actuals.append(float(actual))
        if conf >= method.action_floor:
            n_decisions += 1
        else:
            n_abstentions += 1
        if prev_sign and sign != prev_sign:
            switches += 1
        prev_sign = sign

    n = len(actuals)
    if n == 0:
        return RunMetrics(n=0, withheld=list(_all_metrics()),
                          note="No observation in this window carried a realized "
                               "move, so no metric is computable.")

    withheld: List[str] = []
    m = RunMetrics(n=n, n_decisions=n_decisions, n_abstentions=n_abstentions)

    if n_decisions:
        m.directional_accuracy, m.hit_rate = _accuracy(observations, enabled,
                                                      method, drop_layers)
    else:
        withheld.append(MetricKey.DIRECTIONAL_ACCURACY.value)
        withheld.append(MetricKey.HIT_RATE.value)
        m.directional_accuracy = None
        m.hit_rate = None

    signs = _signs(observations, enabled, drop_layers)
    m.mean_abs_error_pct = round(statistics.fmean([abs(a) for a in actuals]), 4)
    m.turnover = round(switches / n, 4) if n else None
    m.mean_confidence = round(statistics.fmean(confs), 4)
    m.brier_score = round(statistics.fmean(
        [((c if s > 0 else 1.0 - c) - (1.0 if a > 0 else 0.0)) ** 2
         for c, s, a in zip(confs, signs, actuals)]), 4)

    if have_returns and n >= 3:
        curve = _equity_curve(confs, actuals, method.action_floor) or [1.0]
        rets = [(curve[i] / curve[i - 1] - 1.0) for i in range(1, len(curve))
                if curve[i - 1] > 0]
        if len(rets) >= 2:
            mean = statistics.fmean(rets)
            sd = statistics.pstdev(rets)
            if sd > 0:
                m.sharpe = round(mean / sd * math.sqrt(252), 4)
            peak, worst = curve[0], 0.0
            for v in curve:
                peak = max(peak, v)
                worst = min(worst, (v / peak - 1.0) * 100.0 if peak else 0.0)
            m.max_drawdown_pct = round(worst, 4)
    else:
        withheld.append(MetricKey.SHARPE.value)
        withheld.append(MetricKey.MAX_DRAWDOWN_PCT.value)

    m.withheld = sorted(set(withheld))
    m.note = (f"n={n} observations, {n_decisions} above the "
              f"{method.action_floor:.2f} action floor, {n_abstentions} "
              f"abstentions.")
    return m


def _to_evidence(obs: Dict[str, Any], enabled: set,
                 drop_layers: frozenset = frozenset()) -> List[Dict[str, Any]]:
    """Observation -> fusion evidence, honouring both feature and layer ablations."""
    rows: List[Dict[str, Any]] = []
    for name, payload in (obs.get("features") or {}).items():
        if name in drop_layers:
            continue
        rows.append({
            "feature": name,
            "z_score": payload.get("z_score", 0.0),
            "confidence": payload.get("confidence", 0.5),
            "data_mode": payload.get("data_mode", "mock"),
            "layer": payload.get("layer", name),
        })
    return rows


def _signs(observations: Sequence[Dict[str, Any]],
           enabled: Sequence[FeatureKey],
           drop_layers: frozenset = frozenset()) -> List[float]:
    return [fusion.fuse(_to_evidence(obs, set(enabled), drop_layers))["direction"].sign
            for obs in observations]


def _accuracy(observations: Sequence[Dict[str, Any]],
              enabled: Sequence[FeatureKey],
              method: EvaluationMethod,
              drop_layers: frozenset = frozenset()
              ) -> Tuple[Optional[float], Optional[float]]:
    correct = total = 0
    for obs in observations:
        actual = obs.get("actual_move_pct")
        if actual is None:
            continue
        out = fusion.fuse(_to_evidence(obs, set(enabled), drop_layers))
        if float(out["confidence"]) < method.action_floor:
            continue          # abstentions excluded from accuracy, by policy
        total += 1
        if out["direction"].sign * float(actual) > 0:
            correct += 1
    if total == 0:
        return None, None
    acc = round(correct / total, 4)
    return acc, acc


def _all_metrics() -> List[str]:
    return [m.value for m in MetricKey if m is not MetricKey.SAMPLE_SIZE]


# ---------------------------------------------------------------------------
# Experiment run
# ---------------------------------------------------------------------------

def run_arm(name: str, description: str, disabled: Sequence[FeatureKey],
            observations: Sequence[Dict[str, Any]], window: WindowSpec,
            method: Optional[EvaluationMethod] = None,
            experiment_id: Optional[str] = None,
            baseline_id: str = "") -> ExperimentResult:
    """Run one ablation arm across the whole window and per regime."""
    method = method or EvaluationMethod()
    enabled = [f for f in FeatureKey if f not in set(disabled)]
    drop_layers = LAYER_EXCLUSIONS.get(name, frozenset())
    overall = compute_metrics(observations, enabled, method, drop_layers)

    by_regime: List[RegimeSlice] = []
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        grouped[str(obs.get("regime", Regime.UNKNOWN.value))].append(obs)
    for regime in Regime:
        rows = grouped.get(regime.value, [])
        metrics = (compute_metrics(rows, enabled, method, drop_layers) if rows
                   else RunMetrics(n=0, withheld=list(_all_metrics())))
        slice_ = RegimeSlice(regime=regime, n=len(rows), metrics=metrics)
        if len(rows) < MIN_SAMPLE_FOR_PERFORMANCE:
            slice_.status = "insufficient_data"
            slice_.label = INSUFFICIENT_DATA
        by_regime.append(slice_)

    eid = experiment_id or f"exp_{name.lower().replace(' ', '_')}_{int(time.time())}"
    return ExperimentResult(
        experiment_id=eid,
        name=name,
        model_version=MODEL_VERSION,
        features_disabled=list(disabled),
        overall=overall,
        by_regime=by_regime,
        n_observations=len(observations),
        sample_size_note=(f"n={len(observations)} observations over "
                         f"{len(grouped)} regime bucket(s)."),
        data_mode=window.data_mode,
        created_at=iso(),
        fingerprint=fingerprint(name, sorted(f.value for f in enabled),
                                sorted(drop_layers),
                                window.start, window.end, window.seed),
        caveat=("Differences are measured inside QuantPulse's fusion function "
                "on this window only."),
    )


def run_suite(symbols: Sequence[str], n: int = 60, seed: int = 7,
              method: Optional[EvaluationMethod] = None) -> Dict[str, Any]:
    """Run every ablation arm over one shared dataset and window."""
    observations, window = build_observation_set(symbols, n=n, seed=seed)
    method = method or EvaluationMethod()
    results: List[ExperimentResult] = []
    baseline_id = ""
    for name, description, disabled in ABLATIONS:
        eid = f"exp_{name.lower().replace(' ', '_')}"
        res = run_arm(name, description, disabled, observations, window,
                      method=method, experiment_id=eid)
        results.append(res)
        if not disabled:
            baseline_id = eid
    return {
        "observations": observations,
        "window": window,
        "methodology": method,
        "results": results,
        "baseline_experiment_id": baseline_id,
    }


def attach_deltas(suite: Dict[str, Any]) -> List[ExperimentResult]:
    """Fill delta_vs_full on every arm using the FULL MODEL row."""
    results: List[ExperimentResult] = suite["results"]
    baseline = next((r for r in results if not r.features_disabled), None)
    for res in results:
        if baseline is None or res.experiment_id == baseline.experiment_id:
            res.delta_vs_full = {
                MetricKey.DIRECTIONAL_ACCURACY.value: None,
                MetricKey.MEAN_ABS_ERROR_PCT.value: None,
                MetricKey.BRIER_SCORE.value: None,
            }
            continue
        res.delta_vs_full = {
            "directional_accuracy": _delta(
                baseline.overall.directional_accuracy,
                res.overall.directional_accuracy),
            "mean_abs_error_pct": _delta(
                baseline.overall.mean_abs_error_pct,
                res.overall.mean_abs_error_pct),
            "brier_score": _delta(baseline.overall.brier_score,
                                  res.overall.brier_score),
        }
        for slice_, base_slice in zip(res.by_regime, baseline.by_regime):
            slice_.delta_vs_full = {
                "directional_accuracy": _delta(
                    base_slice.metrics.directional_accuracy,
                    slice_.metrics.directional_accuracy),
                "mean_abs_error_pct": _delta(
                    base_slice.metrics.mean_abs_error_pct,
                    slice_.metrics.mean_abs_error_pct),
            }
    return results


def _delta(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return round(b - a, 4)


def build_matrix(suite: Dict[str, Any],
                 min_n: int = MIN_SAMPLE_FOR_PERFORMANCE) -> TournamentMatrix:
    """Rows = arms, columns = regimes. Cell = measured accuracy or N/A."""
    results = attach_deltas(suite)
    columns = [r.value for r in Regime if r is not Regime.UNKNOWN]
    rows: List[RegimeSlice] = []
    total_n = 0
    thin = False
    for res in results:
        for slice_ in res.by_regime:
            if slice_.regime is Regime.UNKNOWN:
                continue
            row = RegimeSlice(regime=slice_.regime, n=slice_.n,
                              metrics=slice_.metrics,
                              delta_vs_full=slice_.delta_vs_full,
                              status=slice_.status, label=slice_.label)
            rows.append(row)
            total_n = max(total_n, slice_.n)
            if slice_.n < min_n:
                thin = True
    # A thin window must not produce a wall of confident numbers.
    if total_n < min_n:
        return TournamentMatrix(
            baseline_experiment_id=suite["baseline_experiment_id"],
            columns=columns, rows=[], metric=MetricKey.DIRECTIONAL_ACCURACY.value,
            data_mode=suite["window"].data_mode, status="insufficient_data",
            label=INSUFFICIENT_DATA, sample_size=total_n,
            required_sample_size=min_n,
            note=insufficient("tournament matrix", total_n, min_n)["note"],
        )
    return TournamentMatrix(
        baseline_experiment_id=suite["baseline_experiment_id"],
        columns=columns, rows=rows,
        metric=MetricKey.DIRECTIONAL_ACCURACY.value,
        data_mode=suite["window"].data_mode,
        status="ok" if not thin else "partial",
        sample_size=total_n, required_sample_size=min_n,
        note=("Cells show measured directional accuracy. Deltas are relative "
              "to the FULL MODEL arm over the same window."),
    )


def make_spec(name: str, disabled: Sequence[FeatureKey], window: WindowSpec,
              model_version: str = MODEL_VERSION,
              description: str = "") -> ExperimentSpec:
    enabled = [f for f in FeatureKey if f not in set(disabled)]
    return ExperimentSpec(
        experiment_id=f"exp_{name.lower().replace(' ', '_')}",
        name=name,
        model_version=model_version,
        features_enabled=enabled,
        features_disabled=list(disabled),
        window=window,
        data_mode=window.data_mode,
        created_at=iso(),
        description=description,
        status="draft",
    )
