"""
QuantPulse AI — Feature 3: Event → Asset Transmission Map.

Builds EVENT → THEME → ASSET instead of "prediction market → BUY NVDA".

The transmission chain is driven by a declared theme taxonomy plus the
platform's own theme→symbol membership. Asset exposure strength is computed
from observed overlap, never asserted as causation.

Historical responses (`median_response_pct`) are computed ONLY from stored
outcomes of comparable past events. With no such history the field stays
`None` and the API returns `INSUFFICIENT DATA` — the module never
manufactures an X/Y/Z number to fill the gap.
"""
from __future__ import annotations

import statistics
import time
from typing import Any, Dict, List, Optional, Sequence

from app.models.common import INSUFFICIENT_DATA, iso, relation_phrase
from app.models.enums import (
    DataMode,
    EventCategory,
    EventType,
    RelationKind,
    weakest,
)
from app.models.event_graph import (
    AssetExposure,
    EventTransmissionGraph,
    GraphEdge,
    GraphNode,
    Theme,
)

#: Minimum matched observations before any historical statistic is reported.
MIN_HISTORY_OBSERVATIONS = 3

#: Extensible theme taxonomy. `members` is the platform's own mapping and is
#: the only thing that puts an asset under a theme.
THEMES: Dict[str, Theme] = {
    "ai-infrastructure": Theme(
        theme_id="ai-infrastructure", name="AI infrastructure",
        category=EventCategory.AI,
        description=("Compute, networking and accelerator demand; the theme "
                     "QuantPulse tracks most densely."),
        member_symbols=["NVDA", "AMD", "MSFT", "AMZN", "GOOGL", "META"],
    ),
    "semiconductors": Theme(
        theme_id="semiconductors", name="Semiconductors",
        category=EventCategory.SECTOR,
        description="Chip design, foundry and packaging.",
        member_symbols=["NVDA", "AMD", "INTC", "TSLA"],
    ),
    "data-centers": Theme(
        theme_id="data-centers", name="Data centers",
        category=EventCategory.SECTOR,
        description="Hyperscaler capacity, power and colocation buildout.",
        member_symbols=["MSFT", "AMZN", "GOOGL", "NVDA"],
    ),
    "cloud-software": Theme(
        theme_id="cloud-software", name="Cloud software",
        category=EventCategory.TECHNOLOGY,
        description="Recurring-revenue cloud and enterprise software.",
        member_symbols=["MSFT", "AMZN", "GOOGL"],
    ),
    "consumer-hardware": Theme(
        theme_id="consumer-hardware", name="Consumer hardware",
        category=EventCategory.COMPANY,
        description="Devices, wearables and consumer electronics.",
        member_symbols=["AAPL", "META"],
    ),
    "ev-autos": Theme(
        theme_id="ev-autos", name="EV & autonomy",
        category=EventCategory.SECTOR,
        description="Electric vehicles, autonomy and battery supply chain.",
        member_symbols=["TSLA", "AMD", "INTC"],
    ),
    "advertising": Theme(
        theme_id="advertising", name="Digital advertising",
        category=EventCategory.SECTOR,
        description="Performance-marketing and targeted-advertising platforms.",
        member_symbols=["META", "GOOGL", "AMZN"],
    ),
    "rates": Theme(
        theme_id="rates", name="Rates & macro",
        category=EventCategory.RATES,
        description="Policy rates, yields and broad index exposure.",
        member_symbols=["SPY"],
    ),
}

#: Event category → themes it activates. Additive, not exclusive.
CATEGORY_THEMES: Dict[EventCategory, List[str]] = {
    EventCategory.AI: ["ai-infrastructure", "semiconductors", "data-centers"],
    EventCategory.TECHNOLOGY: ["ai-infrastructure", "cloud-software"],
    EventCategory.EARNINGS: [],
    EventCategory.REGULATORY: ["ai-infrastructure", "ev-autos", "advertising"],
    EventCategory.GEOPOLITICAL: ["semiconductors", "rates", "data-centers"],
    EventCategory.MACRO: ["rates", "data-centers"],
    EventCategory.RATES: ["rates"],
    EventCategory.COMMODITY: ["data-centers", "ev-autos"],
    EventCategory.ELECTIONS: ["rates", "semiconductors"],
    EventCategory.COMPANY: ["ai-infrastructure", "semiconductors"],
    EventCategory.SECTOR: ["semiconductors", "cloud-software", "advertising",
                           "consumer-hardware", "ev-autos"],
    EventCategory.PREDICTION_MARKET: ["ai-infrastructure", "rates"],
    EventCategory.SOCIAL: ["ai-infrastructure", "advertising"],
}

#: Keywords that activate a theme regardless of the event's category. Kept
#: explicit and inspectable — this is a mapping, not a claim about the world.
KEYWORD_THEMES: List[tuple] = [
    ("ai infrastructure", ["ai-infrastructure", "data-centers"]),
    ("data cent", ["data-centers"]),
    ("hyperscaler", ["data-centers", "ai-infrastructure"]),
    ("capex", ["data-centers", "ai-infrastructure"]),
    ("accelerator", ["semiconductors", "ai-infrastructure"]),
    ("gpu", ["semiconductors", "ai-infrastructure"]),
    ("foundry", ["semiconductors"]),
    ("chip", ["semiconductors"]),
    ("semiconductor", ["semiconductors"]),
    ("cloud", ["cloud-software"]),
    ("saas", ["cloud-software"]),
    ("ev ", ["ev-autos"]),
    ("electric vehicle", ["ev-autos"]),
    ("autonom", ["ev-autos"]),
    ("ad platform", ["advertising"]),
    ("advertising", ["advertising"]),
    ("wearable", ["consumer-hardware"]),
    ("iphone", ["consumer-hardware"]),
    ("fed", ["rates"]),
    ("rate cut", ["rates"]),
    ("yield", ["rates"]),
    ("tariff", ["semiconductors", "rates"]),
    ("export control", ["semiconductors", "ai-infrastructure"]),
]


def themes_for(event_category: EventCategory, text: str = "") -> List[Theme]:
    """Resolve the active themes from category plus explicit keyword matches."""
    ids: List[str] = list(CATEGORY_THEMES.get(event_category, []))
    blob = (text or "").lower()
    for needle, mapped in KEYWORD_THEMES:
        if needle in blob:
            ids.extend(mapped)
    seen, out = set(), []
    for tid in ids:
        if tid in THEMES and tid not in seen:
            seen.add(tid)
            out.append(THEMES[tid])
    return out


#: Symbol → the theme ids the most recent event resolution attributed to it.
_symbol_themes: Dict[str, List[str]] = {}


def primary_symbol_themes(symbol: str) -> List[str]:
    return _symbol_themes.get(symbol.upper(), [])


def register_symbol_themes(symbol: str, theme_ids: Sequence[str]) -> None:
    _symbol_themes[symbol.upper()] = list(theme_ids)


def _member_index() -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for theme in THEMES.values():
        for member in theme.member_symbols:
            index.setdefault(member, []).append(theme.theme_id)
    return index


def THEMES_BY_MEMBER(symbol: str) -> List[str]:
    return _MEMBER_THEMES.get(symbol.upper(), [])


_MEMBER_THEMES = _member_index()


def _strength(asset: str, primary: str, shared_themes: int,
              ai_flagged: bool) -> float:
    """Transparent overlap score in [0,1] — inspectable, no hidden weights.

    primary asset            -> 1.00
    shares a theme           -> 0.45 base
    plus the AI flag         -> +0.25
    plus a second shared one -> +0.10 (capped)
    """
    if asset == primary:
        return 1.0
    score = 0.45 if shared_themes else 0.20
    if ai_flagged:
        score += 0.25
    if shared_themes > 1:
        score += 0.10
    return round(min(1.0, score), 4)


# ---------------------------------------------------------------------------
# Historical response computation
# ---------------------------------------------------------------------------

def historical_response(symbol: str, event_type,
                        history: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Median % move of `symbol` over past comparable resolved events.

    `history` is a list of stored observation dicts with keys
    {symbol, event_type, response_pct, data_mode}. Returns
    INSUFFICIENT DATA until at least MIN_HISTORY_OBSERVATIONS match.

    `event_type` accepts both an EventType enum and its string value so the
    function is robust to how callers store the field.
    """
    etype = event_type.value if hasattr(event_type, "value") else str(event_type)
    matches = [h for h in history
               if str(h.get("symbol", "")).upper() == symbol.upper()
               and str(h.get("event_type", "")) == etype
               and h.get("response_pct") is not None]
    if len(matches) < MIN_HISTORY_OBSERVATIONS:
        return {
            "status": "insufficient_data",
            "label": INSUFFICIENT_DATA,
            "n_observations": len(matches),
            "required": MIN_HISTORY_OBSERVATIONS,
            "median_response_pct": None,
            "median_response_abs_pct": None,
            "observations": [],
            "note": ("Fewer than the required number of comparable resolved "
                     "events exist, so no response statistic is reported."),
        }
    values = [float(h["response_pct"]) for h in matches]
    modes = []
    for h in matches:
        try:
            modes.append(DataMode(str(h.get("data_mode", "mock"))))
        except ValueError:
            modes.append(DataMode.MOCK)
    return {
        "status": "ok",
        "label": "",
        "n_observations": len(matches),
        "required": MIN_HISTORY_OBSERVATIONS,
        "median_response_pct": round(float(statistics.median(values)), 3),
        "median_response_abs_pct": round(
            float(statistics.median([abs(v) for v in values])), 3),
        "stdev_response_pct": round(
            float(statistics.pstdev(values)) if len(values) > 1 else 0.0, 3),
        "observations": matches[-10:],
        "data_mode": weakest(*modes).value,
        "note": "Median over stored resolved events of the same type.",
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(event, evidence_features: Optional[Sequence[str]] = None,
                history: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                data_mode: Optional[DataMode] = None,
                event_id: Optional[str] = None) -> EventTransmissionGraph:
    """Assemble the full transmission graph for one event."""
    symbol = str(getattr(event, "symbol", "") or "").upper()
    headline = str(getattr(event, "headline", "") or "")
    category = getattr(event, "category", EventCategory.COMPANY)
    etype = getattr(event, "event_type", EventType.MARKET)
    eid = event_id or str(getattr(event, "event_id", ""))
    features = list(evidence_features or [])
    history = history or {}

    active = themes_for(category, f"{headline} {' '.join(features)}")
    register_symbol_themes(symbol, [t.theme_id for t in active])
    primary_theme_ids = [t.theme_id for t in active]

    nodes: List[GraphNode] = [
        GraphNode(node_id=eid, node_type="event", label=symbol or "EVENT",
                  sublabel=headline[:90], data_mode=data_mode or DataMode.MOCK,
                  meta={"probability": getattr(event, "probability", None),
                        "event_type": getattr(etype, "value", str(etype))}),
    ]
    edges: List[GraphEdge] = []

    # event → theme
    for theme in active:
        nodes.append(GraphNode(
            node_id=theme.theme_id, node_type="theme", label=theme.name,
            sublabel=theme.description[:80], data_mode=data_mode or DataMode.MOCK,
            meta={"category": theme.category.value,
                  "members": theme.member_symbols},
        ))
        edges.append(GraphEdge(
            edge_id=f"{eid}->{theme.theme_id}", source=eid, target=theme.theme_id,
            relation=RelationKind.ASSOCIATED, wording=relation_phrase("associated"),
            strength=1.0, data_mode=data_mode or DataMode.MOCK,
            note="Theme activated by event category and explicit keyword mapping.",
        ))

    # theme → asset, with exposure strength and honest history
    exposures: List[AssetExposure] = []
    seen_assets = set()
    ai_flagged = "ai" in features or "ai-infrastructure" in primary_theme_ids
    for theme in active:
        for member in theme.member_symbols:
            if member in seen_assets:
                continue
            seen_assets.add(member)
            hist = historical_response(member, etype, history.get(member, []))
            shared = len(set(theme.theme_id for theme in active)
                         & set(THEMES_BY_MEMBER(member)))
            strength = _strength(member, symbol, shared, ai_flagged)
            nodes.append(GraphNode(
                node_id=member, node_type="asset", label=member,
                sublabel=("primary" if member == symbol
                          else hist["label"] or "no history yet"),
                data_mode=DataMode(hist.get("data_mode",
                                            (data_mode or DataMode.MOCK).value)),
                meta={"strength": strength,
                      "n_observations": hist["n_observations"],
                      "median_response_pct": hist["median_response_pct"]},
            ))
            edges.append(GraphEdge(
                edge_id=f"{theme.theme_id}->{member}",
                source=theme.theme_id, target=member,
                relation=(RelationKind.HISTORICAL if hist["status"] == "ok"
                          else RelationKind.POTENTIALLY_AFFECTED),
                wording=relation_phrase("historical" if hist["status"] == "ok"
                                        else "potentially affected"),
                strength=strength,
                n_observations=hist["n_observations"],
                data_mode=DataMode(hist.get("data_mode", (data_mode or DataMode.MOCK).value)),
                note=hist.get("note", ""),
            ))
            exposures.append(AssetExposure(
                symbol=member,
                relation=(RelationKind.HISTORICAL if hist["status"] == "ok"
                          else RelationKind.POTENTIALLY_AFFECTED),
                wording=relation_phrase("historical" if hist["status"] == "ok"
                                        else "potentially affected"),
                strength=strength,
                median_response_pct=hist.get("median_response_pct"),
                n_observations=hist["n_observations"],
                observations=hist.get("observations", []),
                data_mode=DataMode(hist.get("data_mode", (data_mode or DataMode.MOCK).value)),
                historical_status=hist["status"],
                historical_label=hist.get("label", ""),
                note=hist.get("note", ""),
            ))

    exposures.sort(key=lambda e: -e.strength)
    has_history = any(e.has_history for e in exposures)
    graph_mode = weakest(
        data_mode or DataMode.MOCK,
        *[DataMode(e.data_mode.value) for e in exposures],
    )
    return EventTransmissionGraph(
        event_id=eid,
        symbol=symbol,
        headline=headline,
        event_type=etype,
        category=category,
        probability=getattr(event, "probability", None),
        themes=active,
        nodes=nodes,
        edges=edges,
        exposures=exposures,
        data_mode=graph_mode,
        detected_at=str(getattr(event, "detected_at", iso())),
        historical_status="ok" if has_history else "insufficient_data",
        historical_label="" if has_history else INSUFFICIENT_DATA,
    )
