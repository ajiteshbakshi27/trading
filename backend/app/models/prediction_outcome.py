"""
QuantPulse AI — Feature 4: Prediction Failure Autopsy domain model.

The loop only closes if failures are recorded as carefully as successes.
`PredictionRecord` freezes the evidence and feature contributions at issue
time, so the autopsy reads the *same* inputs the model saw rather than
reconstructing them from memory.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import INSUFFICIENT_DATA
from app.models.enums import (
    DataMode,
    Direction,
    FailureMode,
    FeatureKey,
    Horizon,
    Regime,
    Verdict,
)


class FeatureContribution(BaseModel):
    """How much one feature moved the confidence at issue time."""

    feature: FeatureKey
    weight: float
    z_score: float
    #: weight * z_score — the feature's additive contribution to fused_score.
    contribution: float
    share: float = 0.0


class PredictionRecord(BaseModel):
    prediction_id: str
    thesis_id: str = ""
    signal_id: str = ""
    event_id: str = ""
    symbol: str
    direction: Direction = Direction.FLAT
    confidence: float = 0.0
    fused_score: float = 0.0
    #: Reference price captured at issue; the outcome is measured from here.
    entry_price: float = 0.0
    expected_move_pct: float = 0.0
    horizon: Horizon = Horizon.H1
    created_at: str
    expires_at: str
    regime: Regime = Regime.UNKNOWN
    model_version: str = "qp-fusion-1.0"
    data_mode: DataMode = DataMode.MOCK
    evidence: List[Dict] = Field(default_factory=list)
    feature_contributions: List[FeatureContribution] = Field(default_factory=list)
    status: str = "open"  # open | resolved
    note: str = ""


class PredictionOutcome(BaseModel):
    outcome_id: str
    prediction_id: str
    symbol: str
    resolved_at: str
    exit_price: float = 0.0
    actual_move_pct: float = 0.0
    expected_move_pct: float = 0.0
    #: actual - expected, in percentage points. Positive = beat expectation.
    error_pct: float = 0.0
    correct: bool = False
    #: What the market did instead (used by the autopsy's regime check).
    realized_vol: Optional[float] = None
    max_adverse_move_pct: Optional[float] = None
    data_mode: DataMode = DataMode.MOCK
    resolution_source: str = ""


class SignalVerdict(BaseModel):
    """Per-feature autopsy verdict with the evidence behind it."""

    feature: FeatureKey
    label: str
    verdict: Verdict
    #: Non-causal prose: 'associated with failure', 'likely contributor'.
    wording: str
    issued_z_score: float = 0.0
    observed_z_score: Optional[float] = None
    contribution_share: float = 0.0
    evidence: List[str] = Field(default_factory=list)


class Autopsy(BaseModel):
    autopsy_id: str
    prediction_id: str
    symbol: str
    created_at: str
    direction: Direction = Direction.FLAT
    confidence: float = 0.0
    expected_move_pct: float = 0.0
    actual_move_pct: float = 0.0
    error_pct: float = 0.0
    issued_regime: Regime = Regime.UNKNOWN
    realized_regime: Optional[Regime] = None
    regime_mismatch: bool = False
    failure_mode: FailureMode = FailureMode.UNCLASSIFIED
    #: Confidence that this is the dominant failure mode, from the rule set.
    mode_likelihood: float = 0.0
    verdicts: List[SignalVerdict] = Field(default_factory=list)
    evidence_notes: List[str] = Field(default_factory=list)
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    methodology: str = (
        "Each feature's issued signal is compared with what was observed at "
        "resolution. Verdicts describe agreement between stored evidence and "
        "outcome; they do not establish that any single feature caused the "
        "failure."
    )
    disclaimer: str = (
        "Failure modes are ranked by rule agreement, not proven causation. "
        "Treat each as a likely contributor or an associated component "
        "disagreement until an experiment isolates it."
    )


class FailureCategoryCount(BaseModel):
    failure_mode: FailureMode
    label: str
    count: int
    share: float = 0.0
    mean_error_pct: float = 0.0


class BucketPerformance(BaseModel):
    """Performance for one slice (regime, signal type, horizon)."""

    bucket: str
    resolved: int
    correct: int
    accuracy: Optional[float] = None
    mean_error_pct: Optional[float] = None
    mean_confidence: Optional[float] = None
    #: Wilson-style interval on accuracy; None when the slice is too small.
    accuracy_ci: Optional[List[float]] = None
    status: str = "ok"
    label: str = ""


class ModelVersionComparison(BaseModel):
    model_version: str
    predictions: int
    resolved: int
    accuracy: Optional[float] = None
    mean_error_pct: Optional[float] = None
    brier_score: Optional[float] = None
    status: str = "ok"


class FailureAnalysis(BaseModel):
    """`/api/model/failure-analysis` — withheld until sample floor is met."""

    status: str
    label: str = ""
    total_predictions: int = 0
    resolved_predictions: int = 0
    unresolved_predictions: int = 0
    accuracy: Optional[float] = None
    mean_error_pct: Optional[float] = None
    mean_confidence: Optional[float] = None
    brier_score: Optional[float] = None
    calibration_bins: List[Dict] = Field(default_factory=list)
    failure_categories: List[FailureCategoryCount] = Field(default_factory=list)
    by_regime: List[BucketPerformance] = Field(default_factory=list)
    by_signal_type: List[BucketPerformance] = Field(default_factory=list)
    by_horizon: List[BucketPerformance] = Field(default_factory=list)
    by_model_version: List[ModelVersionComparison] = Field(default_factory=list)
    data_mode: DataMode = DataMode.MOCK
    generated_at: str = ""
    #: Why statistics are missing, when they are.
    insufficiency: Optional[Dict] = None
    note: str = ""


class FailureAnalysisView(BaseModel):
    analysis: FailureAnalysis
    label: str = INSUFFICIENT_DATA
