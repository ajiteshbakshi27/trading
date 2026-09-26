"""
QuantPulse AI — Feature 3: Event → Asset Transmission domain model.

The graph is EVENT → THEME → ASSET. Relationships are typed by
`RelationKind`, whose vocabulary deliberately excludes causation. Historical
response statistics are Optional and stay None until the platform has
actually observed enough matching events to compute them.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.common import INSUFFICIENT_DATA, relation_phrase
from app.models.enums import (
    DataMode,
    EventCategory,
    EventType,
    RelationKind,
)


class Theme(BaseModel):
    theme_id: str
    name: str
    category: EventCategory = EventCategory.SECTOR
    description: str = ""
    #: Universe membership used to derive candidate assets for the theme.
    member_symbols: List[str] = Field(default_factory=list)


class AssetExposure(BaseModel):
    """How one asset relates to an event, plus what history actually shows."""

    symbol: str
    relation: RelationKind = RelationKind.POTENTIALLY_AFFECTED
    wording: str = Field(relation_phrase("associated"))
    strength: float = 0.0
    #: Median historical response in % over matched past events. None =
    #: not enough observations to state a number.
    median_response_pct: Optional[float] = None
    response_window: str = "1d"
    n_observations: int = 0
    observations: List[Dict] = Field(default_factory=list)
    data_mode: DataMode = DataMode.MOCK
    historical_status: str = "insufficient_data"
    historical_label: str = INSUFFICIENT_DATA
    note: str = ""

    @property
    def has_history(self) -> bool:
        return self.median_response_pct is not None


class GraphNode(BaseModel):
    node_id: str
    node_type: str  # event | theme | asset
    label: str
    sublabel: str = ""
    data_mode: DataMode = DataMode.MOCK
    meta: Dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    edge_id: str
    source: str
    target: str
    relation: RelationKind = RelationKind.ASSOCIATED
    wording: str = Field(relation_phrase("associated"))
    strength: float = 0.0
    n_observations: int = 0
    data_mode: DataMode = DataMode.MOCK
    note: str = ""


class EventTransmissionGraph(BaseModel):
    """Full graph for one event: nodes, edges and per-asset history."""

    event_id: str
    symbol: str
    headline: str
    event_type: EventType = EventType.MARKET
    category: EventCategory = EventCategory.COMPANY
    probability: Optional[float] = None
    themes: List[Theme] = Field(default_factory=list)
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    exposures: List[AssetExposure] = Field(default_factory=list)
    data_mode: DataMode = DataMode.MOCK
    model_version: str = "qp-fusion-1.0"
    detected_at: str = ""
    #: Populated when no asset in the graph has historical observations.
    historical_status: str = "insufficient_data"
    historical_label: str = INSUFFICIENT_DATA
    #: Vocabulary actually used, echoed so the UI never has to guess.
    relation_vocabulary: List[str] = Field(
        default_factory=lambda: ["observed", "historical", "correlated",
                                 "associated", "potentially affected"])
    disclaimer: str = (
        "Relationships shown are observed co-occurrence and ordering. "
        "QuantPulse does not assert that any event caused any asset move."
    )
