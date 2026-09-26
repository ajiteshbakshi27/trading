"""
QuantPulse AI — Feature 1: Information Propagation domain model.

A `MarketEvent` is the atom of the loop. It produces `Evidence` (one per
information layer), and those observations are ordered into an
`InformationEvent` chain showing *when* each layer moved relative to the
event and to the price.

The chain reports ordering and co-occurrence only. Layer N being observed
after layer N-1 is a timestamp fact; it is never rendered as causation.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.common import (
    relation_phrase,
    rollup,
)
from app.models.enums import (
    DataMode,
    Direction,
    EventCategory,
    EventType,
    Layer,
    RelationKind,
)


class PropagationStep(BaseModel):
    """One layer's observation inside a propagation chain."""

    step_id: str
    layer: Layer
    timestamp: str
    lag_s: float = Field(0.0, description="Seconds after the event was detected")
    signal: str = Field(description="Raw signal as observed, e.g. '+18% mentions'")
    magnitude: float = 0.0
    direction: Direction = Direction.FLAT
    confidence: float = 0.0
    freshness: str = "realtime"
    freshness_s: float = 0.0
    data_mode: DataMode = DataMode.MOCK
    #: What this layer contributed to the fused signal (0 when unavailable).
    contribution: float = 0.0
    #: Approved non-causal wording describing the relation to the prior step.
    relation: str = Field(relation_phrase("preceded"))
    source_label: str = ""
    raw: Dict = Field(default_factory=dict, description="Untransformed observation")

    @property
    def accent(self) -> str:
        from app.models.enums import LAYER_ACCENT
        return LAYER_ACCENT.get(self.layer, "information")


class MarketEvent(BaseModel):
    """A detected event. Root of the chain MarketEvent → … → Experiment."""

    event_id: str
    symbol: str
    event_type: EventType = EventType.MARKET
    category: EventCategory = EventCategory.COMPANY
    headline: str = ""
    body: str = ""
    detected_at: str
    #: Model-implied or crowd-implied probability in [0,1] when the event is
    #: a probability-bearing one (prediction markets, macro releases).
    probability: Optional[float] = None
    magnitude: float = 0.0
    confidence: float = 0.0
    direction: Direction = Direction.FLAT
    themes: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    #: Provenance of the raw observation that triggered detection.
    source_label: str = ""

    @field_validator("symbol")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class Evidence(BaseModel):
    """A single normalized observation. Every service speaks this type."""

    evidence_id: str
    event_id: str
    symbol: str
    layer: Layer
    feature: str
    direction: Direction = Direction.FLAT
    #: Standardised score in [-3, 3]. This is the fusion model's input.
    z_score: float = 0.0
    magnitude: float = 0.0
    observed_at: str
    freshness_s: float = 0.0
    confidence: float = 0.0
    data_mode: DataMode = DataMode.MOCK
    source_label: str = ""
    #: Fraction of final confidence attributable to this observation.
    contribution: float = 0.0
    raw: Dict = Field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.data_mode is not None and abs(self.z_score) > 0


class InformationEvent(BaseModel):
    """Container for one full propagation chain (API response shape)."""

    event_id: str
    symbol: str
    event_type: EventType
    detected_at: str
    sources: List[str] = Field(default_factory=list)
    propagation_steps: List[PropagationStep] = Field(default_factory=list)
    confidence: float = 0.0
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    headline: str = ""
    #: Set when the chain could not be completed from available data.
    status: str = "complete"

    @field_validator("propagation_steps")
    @classmethod
    def _ordered(cls, v: List[PropagationStep]) -> List[PropagationStep]:
        # Canonical layer order, then timestamp. Deterministic for the UI.
        return sorted(v, key=lambda s: (s.layer.order, s.timestamp))

    @property
    def layers_covered(self) -> List[Layer]:
        return [s.layer for s in self.propagation_steps]

    @property
    def span_s(self) -> float:
        if len(self.propagation_steps) < 2:
            return 0.0
        return round(self.propagation_steps[-1].lag_s
                     - self.propagation_steps[0].lag_s, 2)

    def rollup_mode(self) -> DataMode:
        return rollup(self.data_mode,
                      *[s.data_mode for s in self.propagation_steps])


class TransmissionLink(BaseModel):
    """Edge in the event → theme → asset graph (Feature 3)."""

    from_node: str
    to_node: str
    relation: RelationKind = RelationKind.ASSOCIATED
    #: Non-causal prose for the UI, e.g. "observed after".
    wording: str = Field(relation_phrase("associated"))
    strength: float = 0.0
    n_observations: int = 0
    #: Populated only from stored history; None means "not enough data".
    median_response_pct: Optional[float] = None
    data_mode: DataMode = DataMode.MOCK
    note: str = ""
