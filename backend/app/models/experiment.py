"""
QuantPulse AI — Feature 5: Adaptive Signal Tournament domain model.

An experiment is an ablation of the fusion model over a declared window. It
records exactly which features were removed, how direction/confidence were
converted to outcomes, and how large the resulting sample was. Results are
measured differences with sample sizes attached — never "winner" labels.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import INSUFFICIENT_DATA
from app.models.enums import DataMode, FeatureKey, Regime


class EvaluationMethod(BaseModel):
    """How a run turns fused signals into comparable outcomes."""

    name: str = "direction_with_floor"
    description: str = (
        "Each observation contributes one signed prediction. A run is scored "
        "on whether the predicted direction matched the observed move, on mean "
        "absolute error in percentage points, and on Brier score when binary "
        "outcome targets exist. Equity metrics are computed only from a real "
        "price path."
    )
    #: Probability above which a prediction counts as taking a position.
    action_floor: float = 0.55
    #: Observations with confidence below the floor count as abstentions and
    #: are excluded from accuracy but included in turnover/calibration.
    abstention_policy: str = "excluded_from_accuracy_counted_in_turnover"


class WindowSpec(BaseModel):
    """The dataset the experiment ran over. Required for reproducibility."""

    label: str
    start: str
    end: str
    n_observations: int = 0
    symbols: List[str] = Field(default_factory=list)
    #: Deterministic seed so a re-run reproduces the same sample.
    seed: int = 7
    data_mode: DataMode = DataMode.MOCK
    note: str = ""


class ExperimentSpec(BaseModel):
    """Configuration only — a spec has no metrics until it has been run."""

    experiment_id: str
    name: str
    model_version: str
    features_enabled: List[FeatureKey] = Field(default_factory=list)
    features_disabled: List[FeatureKey] = Field(default_factory=list)
    methodology: EvaluationMethod = Field(default_factory=EvaluationMethod)
    window: WindowSpec
    data_mode: DataMode = DataMode.MOCK
    created_at: str = ""
    description: str = ""
    status: str = "draft"  # draft | completed | failed
    #: The full-model arm this ablation is compared against.
    baseline_experiment_id: str = ""


class RunMetrics(BaseModel):
    """Only the metrics this run could actually produce are populated."""

    n: int = 0
    n_decisions: int = 0
    n_abstentions: int = 0
    directional_accuracy: Optional[float] = None
    hit_rate: Optional[float] = None
    mean_abs_error_pct: Optional[float] = None
    brier_score: Optional[float] = None
    calibration_error: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    turnover: Optional[float] = None
    mean_confidence: Optional[float] = None
    withheld: List[str] = Field(default_factory=list)
    note: str = ""


class RegimeSlice(BaseModel):
    """One regime row of the tournament matrix."""

    regime: Regime
    n: int = 0
    metrics: RunMetrics = Field(default_factory=RunMetrics)
    #: Difference vs the full-model arm, in the same units as the metric.
    delta_vs_full: Dict[str, Optional[float]] = Field(default_factory=dict)
    status: str = "ok"
    label: str = ""


class ExperimentResult(BaseModel):
    experiment_id: str
    name: str
    model_version: str
    features_disabled: List[FeatureKey] = Field(default_factory=list)
    overall: RunMetrics = Field(default_factory=RunMetrics)
    by_regime: List[RegimeSlice] = Field(default_factory=list)
    delta_vs_full: Dict[str, Optional[float]] = Field(default_factory=dict)
    n_observations: int = 0
    sample_size_note: str = ""
    data_mode: DataMode = DataMode.MOCK
    created_at: str = ""
    #: Reproducibility fingerprint: config hash + window + seed.
    fingerprint: str = ""
    status: str = "completed"
    caveat: str = (
        "Differences are measured inside QuantPulse's fusion function on this "
        "window only. They quantify marginal contribution to this model, not "
        "predictive edge in the market."
    )


class TournamentMatrix(BaseModel):
    """Rows = configurations, columns = regimes. Cell = measured value."""

    baseline_experiment_id: str = ""
    columns: List[str] = Field(default_factory=list)
    rows: List[RegimeSlice] = Field(default_factory=list)
    metric: str = "directional_accuracy"
    data_mode: DataMode = DataMode.MOCK
    status: str = "ok"
    label: str = ""
    sample_size: int = 0
    required_sample_size: int = 0
    note: str = ""


class ExperimentView(BaseModel):
    spec: ExperimentSpec
    result: Optional[ExperimentResult] = None
    status_label: str = INSUFFICIENT_DATA
