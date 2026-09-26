"""
QuantPulse AI — Research truth layer.

Every record that leaves the API carries its provenance. This module owns the
vocabulary the product uses to describe what it does and does not know, so no
service has to invent its own hedging language.

Rules enforced here:
  * a record is never labelled LIVE unless a credentialed feed produced it
  * a mixed record rolls up to the weakest provenance (MODE_STRENGTH)
  * statistics below a sample floor return INSUFFICIENT DATA, never a number
  * relationship wording comes from RELATION_VOCABULARY, never causal claims
"""
from __future__ import annotations

import hashlib
import math
import time
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Sequence

from app.models.enums import (
    CAUSAL_CLAIMS_FORBIDDEN,
    MIN_SAMPLE_FOR_PERFORMANCE,
    DataMode,
    FeatureKey,
    MetricKey,
    weakest,
)

INSUFFICIENT_DATA = "INSUFFICIENT DATA"

#: Wording the product is allowed to use when relating two observations.
RELATION_PHRASES = {
    "preceded": "preceded",
    "observed_after": "observed after",
    "associated": "associated with",
    "historical": "historical relationship",
    "co_occurred": "co-occurred with",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: Optional[float] = None) -> str:
    return datetime.fromtimestamp(ts if ts is not None else time.time(),
                                 tz=timezone.utc).isoformat()


def freshness_s(observed_at: float, now: Optional[float] = None) -> float:
    """Age of an observation in seconds (never negative)."""
    return round(max(0.0, (now if now is not None else time.time()) - observed_at), 2)


def freshness_label(age_s: float) -> str:
    if age_s <= 30:
        return "realtime"
    if age_s <= 300:
        return "recent"
    if age_s <= 3600:
        return "stale_1h"
    return "stale"


class InsufficientData(Exception):
    """Raised when a computation needs more observations than exist."""


def require_sample(n: int, needed: int = MIN_SAMPLE_FOR_PERFORMANCE,
                   what: str = "performance statistics") -> None:
    if n < needed:
        raise InsufficientData(
            f"{what} withheld: {n} resolved observation(s), "
            f"{needed} required before reporting")


def insufficient(what: str, have: int, needed: int = MIN_SAMPLE_FOR_PERFORMANCE
                 ) -> dict:
    """The canonical 'we do not know yet' payload."""
    return {
        "status": "insufficient_data",
        "label": INSUFFICIENT_DATA,
        "what": what,
        "sample_size": have,
        "required_sample_size": needed,
        "metrics": {},
        "note": "No numbers are reported until the sample floor is met.",
    }


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def safe_logit(p: float, eps: float = 1e-6) -> float:
    p = clamp(p, eps, 1 - eps)
    return math.log(p / (1 - p))


def logistic(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, x))))


# --------------------------------------------------------------------------
# Truthful relationship wording
# --------------------------------------------------------------------------

def relation_phrase(kind: str) -> str:
    """Map a relation kind to approved prose. Causal words are impossible."""
    return {
        "preceded": RELATION_PHRASES["preceded"],
        "observed_after": RELATION_PHRASES["observed_after"],
        "associated": RELATION_PHRASES["associated"],
        "historical": RELATION_PHRASES["historical"],
        "co_occurred": RELATION_PHRASES["co_occurred"],
    }.get(kind, RELATION_PHRASES["associated"])


def assert_no_causal_claims(text: str) -> str:
    """Guard used on generated prose. Replaces causal words rather than lying."""
    out = text
    for word in CAUSAL_CLAIMS_FORBIDDEN:
        if word in out.lower():
            out = out.replace(word, "co-occurred with")
    return out


def caveat(mode: DataMode, extra: Optional[str] = None) -> str:
    """One-line provenance banner shown next to every research panel."""
    base = {
        DataMode.LIVE: "Live credentialed feeds.",
        DataMode.SIMULATED: "SIMULATED SCENARIO — synthetic data, not a real event.",
        DataMode.MOCK: "MOCK FEED — no credentials configured; seeded simulator.",
        DataMode.BACKTEST: "BACKTEST — replayed historical window, not live.",
    }[mode]
    return f"{base} {extra}" if extra else base


# --------------------------------------------------------------------------
# Provenance rollup
# --------------------------------------------------------------------------

def rollup(*modes: DataMode) -> DataMode:
    return weakest(*modes)


def mode_block(mode: DataMode, **extra) -> dict:
    """Uniform data-mode metadata attached to every new response."""
    block = {"data_mode": mode.value, "data_mode_label": mode.label,
             "caveat": caveat(mode)}
    block.update(extra)
    return block


# --------------------------------------------------------------------------
# Metric support checks
# --------------------------------------------------------------------------

def metric_is_computable(metric: MetricKey, has_returns: bool,
                         has_brier_targets: bool = False,
                         has_equity: bool = False) -> bool:
    """Only report a metric when the run can actually produce it."""
    if metric in (MetricKey.SAMPLE_SIZE, MetricKey.MEAN_CONFIDENCE,
                  MetricKey.DIRECTIONAL_ACCURACY, MetricKey.HIT_RATE,
                  MetricKey.MEAN_ABS_ERROR_PCT, MetricKey.TURNOVER):
        return True
    if metric is MetricKey.BRIER_SCORE:
        return has_brier_targets
    if metric is MetricKey.CALIBRATION_ERROR:
        return has_brier_targets
    if metric in (MetricKey.SHARPE, MetricKey.MAX_DRAWDOWN_PCT):
        return has_equity and has_returns
    return False


def feature_label(key: FeatureKey) -> str:
    return {
        FeatureKey.ORDER_FLOW: "Order flow",
        FeatureKey.SOCIAL: "Social sentiment",
        FeatureKey.PREDICTION: "Prediction market",
        FeatureKey.MOMENTUM: "Momentum",
        FeatureKey.NEWS: "News",
        FeatureKey.QUANTUM: "Quantum fair value",
    }[key]


def enabled_features(keys: Sequence[FeatureKey]) -> List[str]:
    return [k.value for k in keys]


def all_features() -> List[FeatureKey]:
    return list(FeatureKey)


def iter_unique(values: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def fingerprint(*parts: Any) -> str:
    """Stable short hash over a configuration — experiment reproducibility."""
    import hashlib
    blob = "|".join(str(p) for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
