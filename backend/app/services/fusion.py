"""
QuantPulse AI — Signal fusion (the loop's single decision function).

One function, `fuse()`, turns normalized Evidence into a direction and a
confidence. It is called from exactly three places:

  1. live signal generation            -> what the dashboard shows
  2. the Thesis Stress Lab             -> confidence under perturbation
  3. the Adaptive Signal Tournament    -> confidence with features ablated

Because all three share it, a stress-test delta and an ablation delta mean
the same thing, and the tournament is genuinely measuring this model's
marginal feature contributions rather than a parallel toy model.

INTEGRITY
  * weights below are configured PRIORS, hand-set and documented as such.
    They are not fitted parameters, and nothing in the API implies they are.
  * the function is pure and deterministic given (evidence, feature set).
  * `trace` is returned so the UI can show why a number came out.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.models.common import clamp, logistic
from app.models.enums import DataMode, Direction, FeatureKey, Regime, weakest

#: Fusion priors. Hand-configured, NOT fitted. Documented as priors in the
#: README and echoed in every fusion_trace so nobody mistakes them for
#: learned parameters.
FUSION_PRIORS: Dict[FeatureKey, float] = {
    FeatureKey.ORDER_FLOW: 1.00,   # most direct, lowest-latency observation
    FeatureKey.SOCIAL: 0.55,      # slower, noisier, crowding-prone
    FeatureKey.PREDICTION: 0.70,   # probability-bearing, market-implied
    FeatureKey.MOMENTUM: 0.60,     # price-derived, regime-dependent
    FeatureKey.NEWS: 0.80,         # event-driven, bursts
    FeatureKey.QUANTUM: 0.35,      # exploratory; small prior on purpose
}

#: Bias is shrunk toward the abstention floor by this much when evidence is
#: thin, so a single noisy observation cannot produce a high confidence.
THIN_EVIDENCE_SHRINK = 0.65
MIN_EVIDENCE_FOR_FULL_CONFIDENCE = 3.0
#: z-scores are clipped here; a 6-sigma claim from one noisy feed is noise.
Z_CLIP = 3.0
#: Confidence at or below this is treated as "no position" downstream.
NEUTRAL_FLOOR = 0.5
ACTION_FLOOR = 0.55

#: The single fusion version. Signals, stress tests and tournament ablations
#: all report this so a delta is always attributable to the same function.
MODEL_VERSION = "qp-fusion-1.0"


def _clip_z(z: float) -> float:
    return max(-Z_CLIP, min(Z_CLIP, float(z)))


def normalise(raw: Dict[str, Any] | None) -> float:
    """Map a loose feature value into a z-score in [-3, 3].

    Inputs are bounded by construction (sentiment in [-1,1], OFI in [-1,1],
    probabilities in [0,1]) so the mapping is explicit rather than statistical.
    """
    if not raw:
        return 0.0
    try:
        v = float(raw.get("value", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
    scale = float(raw.get("scale", 1.0) or 1.0)
    if scale == 0:
        return 0.0
    return _clip_z(v / scale)


class FusionTrace:
    """Per-feature accounting for one fuse() call."""

    def __init__(self) -> None:
        self.rows: List[Dict[str, object]] = []
        self.modes: List[DataMode] = []

    def add(self, feature: FeatureKey, weight: float, z: float, conf: float,
            usable: bool) -> None:
        self.rows.append({
            "feature": feature.value,
            "weight": round(weight, 4),
            "z_score": round(z, 4),
            "confidence": round(conf, 4),
            "usable": usable,
            "contribution": round(weight * z, 4),
        })
        self.modes.append(conf)

    def to_dict(self) -> Dict[str, object]:
        usable = [r for r in self.rows if r["usable"]]
        denom = sum(abs(float(r["contribution"])) for r in usable) or 1.0
        for r in self.rows:
            r["share"] = round(abs(float(r["contribution"])) / denom, 4)
        return {
            "features": self.rows,
            "n_usable": len(usable),
            "n_disabled": sum(1 for r in self.rows if not r["usable"]
                              and float(r["z_score"]) == 0.0),
            "weights_are": "configured priors (hand-set, not fitted)",
            "z_clip": Z_CLIP,
        }


def fuse(evidence: Sequence[Dict[str, Any]],
         features_enabled: Optional[Iterable[FeatureKey]] = None,
         data_mode: Optional[DataMode] = None) -> Dict[str, object]:
    """Fuse normalized evidence into a direction and a confidence.

    evidence items: {feature, z_score, confidence, data_mode, ...}
    returns: {direction, confidence, fused_score, components, trace, data_mode,
              evidence_weight, n_evidence}
    """
    enabled = set(features_enabled) if features_enabled is not None else set(FeatureKey)
    trace = FusionTrace()
    modes: List[DataMode] = []
    weighted: List[Tuple[float, float]] = []   # (weight*z, confidence)
    n_considered = 0

    for item in evidence:
        try:
            feature = FeatureKey(str(item.get("feature", "")))
        except ValueError:
            continue
        n_considered += 1
        z = _clip_z(item.get("z_score", 0.0) or 0.0)
        try:
            obs_conf = clamp(float(item.get("confidence", 0.0) or 0.0))
        except (TypeError, ValueError):
            obs_conf = 0.0
        # An observation only counts if its own confidence clears a floor;
        # a low-confidence feed reading must not move the thesis.
        usable = (feature in enabled) and (abs(z) > 0.0) and (obs_conf >= 0.30)
        if not usable:
            trace.add(feature, 0.0, z, obs_conf, False)
            continue
        # Observation confidence attenuates the feature's prior weight.
        w = FUSION_PRIORS[feature] * (0.5 + 0.5 * obs_conf)
        contribution = w * z
        weighted.append((contribution, obs_conf))
        trace.add(feature, w, z, obs_conf, True)
        try:
            modes.append(DataMode(str(item.get("data_mode", "mock"))))
        except ValueError:
            modes.append(DataMode.MOCK)

    if not weighted:
        return {
            "direction": Direction.FLAT,
            "confidence": round(clamp(0.5 - 0.0), 4),
            "fused_score": 0.0,
            "components": {},
            "trace": trace.to_dict(),
            "data_mode": weakest(*modes) if modes else (data_mode or DataMode.MOCK),
            "evidence_weight": 0.0,
            "n_evidence": 0,
            "abstaining": True,
        }

    fused_score = sum(c for c, _ in weighted)
    # Total observation weight drives how much the score is trusted.
    evidence_weight = sum(obs_conf for _, obs_conf in weighted)
    shrink = 1.0
    if evidence_weight < MIN_EVIDENCE_FOR_FULL_CONFIDENCE:
        shrink = (evidence_weight / MIN_EVIDENCE_FOR_FULL_CONFIDENCE) * THIN_EVIDENCE_SHRINK
    effective = fused_score * (THIN_EVIDENCE_SHRINK + (1 - THIN_EVIDENCE_SHRINK) * min(1.0, shrink))
    # Confidence = P(direction correct) proxy, centred on the neutral floor.
    confidence = clamp(logistic(effective))

    if effective > 0.12:
        direction = Direction.LONG
    elif effective < -0.12:
        direction = Direction.SHORT
    else:
        direction = Direction.FLAT
        confidence = min(confidence, NEUTRAL_FLOOR)

    return {
        "direction": direction,
        "confidence": round(confidence, 4),
        "fused_score": round(effective, 4),
        "raw_fused_score": round(fused_score, 4),
        "components": {r["feature"]: r["contribution"]
                       for r in trace.to_dict()["features"] if r["usable"]},
        "trace": trace.to_dict(),
        "data_mode": weakest(*modes) if modes else (data_mode or DataMode.MOCK),
        "evidence_weight": round(evidence_weight, 3),
        "n_evidence": len(weighted),
        "n_considered": n_considered,
        "abstaining": confidence < ACTION_FLOOR,
    }


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------

def classify_regime(realized_vol: Optional[float],
                    trend: Optional[float],
                    ofi_norm: Optional[float] = None) -> Regime:
    """Rule-based regime label. Deliberately simple and inspectable.

    realized_vol: annualized-ish % stdev of recent returns (None -> unknown)
    trend: % move over the classification window
    """
    if realized_vol is None or trend is None:
        return Regime.UNKNOWN
    try:
        vol, tr = float(realized_vol), float(trend)
    except (TypeError, ValueError):
        return Regime.UNKNOWN
    if vol >= 2.2:
        return Regime.HIGH_VOL
    if abs(tr) >= 1.5:
        return Regime.TREND
    if abs(tr) <= 0.35 and (ofi_norm is None or abs(float(ofi_norm)) < 0.15):
        return Regime.RANGE_BOUND
    if abs(tr) < 1.0:
        return Regime.MEAN_REVERSION
    return Regime.RANGE_BOUND


def regime_from_snapshot(book: Dict[str, Any], history: Optional[Sequence[float]] = None,
                         window: int = 20) -> Tuple[Regime, Dict[str, float]]:
    """Classify the live regime from the HFT book plus a return history."""
    metrics: Dict[str, float] = {}
    trend = None
    vol = None
    if history and len(history) >= 5:
        series = [float(p) for p in history[-window:] if p and p > 0]
        if len(series) >= 5:
            trend = (series[-1] / series[0] - 1.0) * 100.0
            rets = [(series[i] / series[i - 1] - 1.0) * 100.0
                    for i in range(1, len(series))]
            mean = sum(rets) / len(rets)
            var = sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1)
            vol = math.sqrt(var)
            metrics = {"trend_pct": round(trend, 3), "realized_vol": round(vol, 3)}
    ofi = ((book or {}).get("ofi") or {}).get("ofi_norm")
    return classify_regime(vol, trend, ofi), metrics


def headline(evidence: Sequence[Dict[str, Any]], symbol: str) -> str:
    """One-line, non-causal summary of what the evidence shows."""
    named = []
    for item in evidence:
        try:
            f = FeatureKey(str(item.get("feature", "")))
        except ValueError:
            continue
        z = float(item.get("z_score", 0.0) or 0.0)
        if abs(z) < 0.15:
            continue
        from app.models.common import feature_label
        named.append(f"{feature_label(f)} {z:+.2f}")
    if not named:
        return f"{symbol}: no layer shows a material deviation yet."
    return f"{symbol}: " + ", ".join(named[:4]) + "."
