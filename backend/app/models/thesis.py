"""
QuantPulse AI — Feature 2: Thesis Stress Lab domain model.

A `Thesis` is a testable hypothesis, not a BUY/SELL label. The Stress Lab
perturbs the stored evidence under explicit, named rules and re-runs the
*same* fusion function used to produce the original confidence, so the
robustness number is a measurement rather than a score someone invented.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import relation_phrase
from app.models.enums import DataMode, Direction, Regime, StressScenario


class Contradiction(BaseModel):
    """Evidence pointing against the thesis. Always surfaced, never hidden."""

    evidence_id: str
    layer: str
    feature: str
    reason: str
    z_score: float = 0.0
    data_mode: DataMode = DataMode.MOCK


class Thesis(BaseModel):
    thesis_id: str
    symbol: str
    direction: Direction = Direction.FLAT
    confidence: float = 0.0
    #: The fusion model's signed input. Recomputed under stress.
    fused_score: float = 0.0
    evidence: List[Dict] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    regime: Regime = Regime.UNKNOWN
    created_at: str
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    #: Links back into the loop.
    signal_id: str = ""
    event_id: str = ""
    #: Market state captured at thesis time (vol, spread, depth) for the
    #: liquidity/volatility scenarios to perturb.
    market_state: Dict = Field(default_factory=dict)
    plain_language: str = ""
    #: Full record of the fusion call that produced this confidence.
    fusion_trace: Dict = Field(default_factory=dict)

    @property
    def primary_evidence(self) -> List[Dict]:
        return sorted(self.evidence,
                      key=lambda e: -abs(float(e.get("contribution", 0) or 0)))[:3]


class ScenarioSpec(BaseModel):
    """The perturbation rule, stated before it is applied."""

    scenario: StressScenario
    label: str
    #: Which evidence feature the rule targets.
    target: str
    #: Multiplier applied to the targeted z-score.
    multiplier: float = 1.0
    #: Additive shock applied after scaling (e.g. volatility expansion).
    additive: float = 0.0
    description: str = ""
    rule: str = Field(description="Literal formula, shown in the UI")

    def apply_to(self, z: float) -> float:
        return round(self.multiplier * z + self.additive, 6)


class ScenarioResult(BaseModel):
    """One perturbed recomputation."""

    scenario: StressScenario
    label: str
    rule: str
    perturbed_confidence: float
    delta_confidence: float
    flipped: bool = Field(description="Thesis direction inverted under this rule")
    survives: bool = Field(description="Confidence stayed above the neutral floor")
    perturbed_evidence: List[Dict] = Field(default_factory=list)
    components: Dict = Field(default_factory=dict)


class StressTest(BaseModel):
    stress_id: str
    thesis_id: str
    symbol: str
    direction: Direction = Direction.FLAT
    baseline_confidence: float = 0.0
    #: Mean confidence across the perturbed runs. Computed, never assigned.
    mean_perturbed_confidence: float = 0.0
    worst_case_confidence: float = 0.0
    #: 0..1 = share of scenarios that flip the thesis or drop it below floor.
    fragility: float = 0.0
    #: 0..1 = share of scenarios where the original direction survives.
    robustness: float = 0.0
    robustness_label: str = ""
    scenarios: List[ScenarioResult] = Field(default_factory=list)
    neutral_floor: float = 0.5
    created_at: str
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    methodology: str = (
        "Each scenario perturbs one named evidence feature under an explicit "
        "multiplier rule, then re-runs the identical fusion function used to "
        "produce the baseline. Robustness = share of scenarios where the "
        "original direction survives above the neutral confidence floor."
    )
    notes: List[str] = Field(default_factory=list)


class ThesisView(BaseModel):
    """API envelope: thesis + optional latest stress test."""

    thesis: Thesis
    latest_stress: Optional[StressTest] = None
    relation_wording: str = Field(relation_phrase("associated"))
