"""
QuantPulse AI — Deterministic demo scenario.

`NVDA_EVENT_001` is a *synthetic* scenario, not a record of a real event.
It exists so the complete loop is demonstrable with no credentials:

    event → propagation → signal → thesis → stress → prediction
          → outcome → autopsy → experiment

Every record it produces carries DataMode.SIMULATED and is labelled
SIMULATED SCENARIO in the UI. Nothing here is presented as market history.

The numbers are hand-chosen to tell a coherent story (a bullish information
cascade that nevertheless fails, because volatility expanded and momentum
reversed). They are not fitted, not estimated, and not derived from any
real tape.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.models.common import iso
from app.models.enums import (
    DataMode,
    Direction,
    EventCategory,
    EventType,
    FailureMode,
    FeatureKey,
    Horizon,
    Layer,
    Regime,
)

SCENARIO_ID = "NVDA_EVENT_001"
SCENARIO_LABEL = "SIMULATED SCENARIO"

#: Fixed clock so the narrative is byte-identical on every run. 10:02:11 local
#: on a fixed date; the UI renders the clock time only.
T0 = 1_789_200_000.0

HEADLINE = ("Hyperscaler capex guidance lifted; AI infrastructure demand "
            "accelerates into the quarter")

#: The layer observations, in canonical order. Magnitudes are synthetic.
LAYERS: List[Dict[str, Any]] = [
    {"layer": Layer.EVENT, "feature": FeatureKey.NEWS, "lag_s": 0,
     "signal": "synthetic headline detected", "magnitude": 0.62,
     "z_score": 0.62, "confidence": 0.55, "source_label": "scenario detector"},
    {"layer": Layer.NEWS, "feature": FeatureKey.NEWS, "lag_s": 7,
     "signal": "news activity +18%", "magnitude": 0.72,
     "z_score": 0.72, "confidence": 0.62, "source_label": "news wire (scenario)"},
    {"layer": Layer.PREDICTION, "feature": FeatureKey.PREDICTION, "lag_s": 53,
     "signal": "crowd 64% → 72%", "magnitude": 0.58,
     "z_score": 0.58, "confidence": 0.60,
     "source_label": "prediction market (scenario)"},
    {"layer": Layer.REDDIT, "feature": FeatureKey.SOCIAL, "lag_s": 131,
     "signal": "reddit velocity +41%", "magnitude": 0.84,
     "z_score": 0.84, "confidence": 0.66, "source_label": "r/ (scenario)"},
    {"layer": Layer.X, "feature": FeatureKey.SOCIAL, "lag_s": 182,
     "signal": "X velocity +27%", "magnitude": 0.51,
     "z_score": 0.51, "confidence": 0.55, "source_label": "X (scenario)"},
    {"layer": Layer.ORDER_FLOW, "feature": FeatureKey.ORDER_FLOW, "lag_s": 270,
     "signal": "order-flow imbalance +21%", "magnitude": 0.91,
     "z_score": 0.91, "confidence": 0.74,
     "source_label": "L2 order book (scenario)"},
    {"layer": Layer.PRICE, "feature": FeatureKey.MOMENTUM, "lag_s": 331,
     "signal": "price response +1.8%", "magnitude": 0.44,
     "z_score": 0.44, "confidence": 0.52, "source_label": "last price (scenario)"},
]

#: The thesis the cascade produces. Bullish, but not overwhelming.
EXPECTED_DIRECTION = Direction.LONG
EXPECTED_REGIME = Regime.TREND

#: What actually happens: volatility expands and momentum inverts, so the
#: prediction resolves wrong and the autopsy has something real to find.
OUTCOME: Dict[str, Any] = {
    "exit_move_pct": -4.1,
    "expected_move_pct": 2.7,
    "realized_vol": 3.4,
    "issued_vol": 1.1,
    "realized_regime": Regime.HIGH_VOL,
    "resolution_source": "SIMULATED outcome (scenario NVDA_EVENT_001)",
    #: Observed layer signs at resolution. Order flow held; social and
    #: momentum did not. This is what the autopsy reads.
    "observed_evidence": [
        {"feature": FeatureKey.ORDER_FLOW.value, "z_score": 0.42},
        {"feature": FeatureKey.SOCIAL.value, "z_score": -0.38},
        {"feature": FeatureKey.PREDICTION.value, "z_score": 0.21},
        {"feature": FeatureKey.MOMENTUM.value, "z_score": -0.77},
    ],
    "expected_failure_mode": FailureMode.VOLATILITY_UNDERESTIMATION,
    "entry_price": 131.40,
    "horizon": Horizon.D1,
}

#: Held-out synthetic observations for the tournament, so the demo's research
#: step has a sample to measure. Deterministic; correlations are chosen, not
#: estimated. Seeded in signal_tournament when no stored evidence exists.
TOURNAMENT_N = 72
TOURNAMENT_SEED = 11


def event_payload() -> Dict[str, Any]:
    """The MarketEvent the scenario starts from."""
    return {
        "event_id": SCENARIO_ID,
        "symbol": "NVDA",
        "event_type": EventType.AI,
        "category": EventCategory.AI,
        "headline": HEADLINE,
        "body": ("Synthetic headline used for the QuantPulse demo narrative. "
                 "Not a real market event."),
        "detected_at": iso(T0),
        "probability": 0.72,
        "magnitude": 0.62,
        "confidence": 0.55,
        "direction": Direction.LONG,
        "themes": ["ai-infrastructure", "semiconductors", "data-centers"],
        "sources": ["scenario"],
        "data_mode": DataMode.SIMULATED,
        "model_version": "qp-fusion-1.0",
        "source_label": SCENARIO_LABEL,
    }


def evidence_payload() -> List[Dict[str, Any]]:
    """Layer observations, as fusion evidence."""
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(LAYERS):
        out.append({
            "evidence_id": f"ev_{SCENARIO_ID}_{row['layer'].value}",
            "event_id": SCENARIO_ID,
            "symbol": "NVDA",
            "layer": row["layer"].value,
            "feature": row["feature"].value,
            "z_score": row["z_score"],
            "magnitude": row["magnitude"],
            "direction": (Direction.LONG if row["z_score"] > 0
                          else Direction.SHORT if row["z_score"] < 0
                          else Direction.FLAT),
            "confidence": row["confidence"],
            "observed_at": iso(T0 + row["lag_s"]),
            "data_mode": DataMode.SIMULATED,
            "source_label": row["source_label"],
            "raw": {"lag_s": row["lag_s"], "signal": row["signal"],
                    "scenario": SCENARIO_ID},
        })
    return out


def chain_payload() -> List[Dict[str, Any]]:
    """The propagation chain, pre-rendered for the flow graph."""
    return [{
        "step_id": f"st_{SCENARIO_ID}_{row['layer'].value}",
        "layer": row["layer"].value,
        "timestamp": iso(T0 + row["lag_s"]),
        "clock": _clock(T0 + row["lag_s"]),
        "lag_s": row["lag_s"],
        "signal": row["signal"],
        "magnitude": row["magnitude"],
        "z_score": row["z_score"],
        "confidence": row["confidence"],
        "source_label": row["source_label"],
        "data_mode": DataMode.SIMULATED.value,
        "data_mode_label": DataMode.SIMULATED.label,
        "relation": "synthetic sequence step",
    } for row in LAYERS]


def _clock(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")


def market_state() -> Dict[str, float]:
    """Market state at thesis time — drives the vol/liquidity scenarios."""
    return {"realized_vol": OUTCOME["issued_vol"], "spread_bps": 6.5,
            "mid": OUTCOME["entry_price"]}


def outcome_payload() -> Dict[str, Any]:
    out = dict(OUTCOME)
    out["data_mode"] = DataMode.SIMULATED
    out["symbol"] = "NVDA"
    out["resolved_at"] = iso(T0 + 24 * 3600)
    return out


#: The 11 beats the /demo page walks through.
DEMO_BEATS: List[Dict[str, str]] = [
    {"step": "1", "key": "event", "title": "Choose NVDA",
     "body": "The desk selects a single symbol. Everything downstream is "
             "scoped to it."},
    {"step": "2", "key": "detected", "title": "Event detected",
     "body": "A synthetic event is registered with a probability and a "
             "provenance label."},
    {"step": "3", "key": "trace", "title": "Trace information",
     "body": "The propagation engine assembles the layer chain and timestamps "
             "each step."},
    {"step": "4", "key": "propagation", "title": "Show propagation",
     "body": "Seven layers, from news to price response, each with magnitude, "
             "direction and freshness."},
    {"step": "5", "key": "thesis", "title": "Generate thesis",
     "body": "Evidence is fused once. The result is a direction and a "
             "confidence with a traceable breakdown."},
    {"step": "6", "key": "stress", "title": "Stress thesis",
     "body": "Seven named perturbations re-run the same fusion. Robustness is "
             "the share of scenarios that survive."},
    {"step": "7", "key": "prediction", "title": "Create prediction",
     "body": "The thesis becomes a dated, directional prediction with the "
             "evidence frozen at issue."},
    {"step": "8", "key": "outcome", "title": "Resolve outcome",
     "body": "A simulated outcome resolves the prediction — in this scenario, "
             "incorrectly."},
    {"step": "9", "key": "autopsy", "title": "Run autopsy",
     "body": "Each stored feature is compared with what was observed, and a "
             "likely failure mode is ranked."},
    {"step": "10", "key": "tournament", "title": "Run signal tournament",
     "body": "Ablation arms re-run the same fusion over one shared window."},
    {"step": "11", "key": "conclusion", "title": "Research conclusions",
     "body": "Measured differences, sample sizes and the limits of the "
             "evidence, stated plainly."},
]
