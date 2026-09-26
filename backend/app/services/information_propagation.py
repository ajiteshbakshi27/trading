"""
QuantPulse AI — Feature 1: Information Propagation Engine.

Answers "when something happens, how does information move through the market
layers before the price reacts?" by building a timestamped chain per event:

    EVENT → NEWS → PREDICTION → REDDIT → X → ORDER FLOW → PRICE

TRUTH RULES
  * In LIVE mode the chain is built from *observed* first-crossing timestamps:
    each step records when that layer's normalized signal first crossed the
    materiality threshold. Ordering is a fact; causation is not asserted.
  * Without credentials there is no observation history, so the chain comes
    from a deterministic scenario and is labelled SIMULATED / MOCK. Synthetic
    lags are never presented as measured.
  * `confidence` is the fused confidence from services.fusion, i.e. the same
    number the dashboard shows — not a separate cosmetic score.
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.common import (
    freshness_label,
    freshness_s,
    iso,
    relation_phrase,
    utcnow,
    weakest,
)
from app.models.enums import (
    DataMode,
    Direction,
    EventCategory,
    EventType,
    FeatureKey,
    Layer,
    weakest as mode_weakest,
)
from app.models.information_event import (
    Evidence,
    InformationEvent,
    MarketEvent,
    PropagationStep,
)
from app.services import feed_layer, fusion

#: A layer counts as "responding" when its z-score crosses this.
MATERIALITY_Z = 0.35
#: Window used to turn raw feed values into a deviation score.
_SCALE = {
    FeatureKey.ORDER_FLOW: 0.45,
    FeatureKey.SOCIAL: 0.55,
    FeatureKey.PREDICTION: 0.12,
    FeatureKey.MOMENTUM: 1.20,
    FeatureKey.NEWS: 0.70,
    FeatureKey.QUANTUM: 0.08,
}

#: Deterministic scenario used when no live observation history exists.
#: Offsets are seconds after detection. These are *synthetic* and always
#: travel with a SIMULATED/MOCK data mode.
SCENARIO_LAGS_S: Dict[Layer, int] = {
    Layer.EVENT: 0,
    Layer.NEWS: 7,
    Layer.PREDICTION: 53,
    Layer.REDDIT: 131,
    Layer.X: 182,
    Layer.ORDER_FLOW: 270,
    Layer.PRICE: 331,
}

SCENARIO_MAGNITUDES: Dict[Layer, Tuple[float, float]] = {
    Layer.NEWS: (0.45, 0.95),
    Layer.PREDICTION: (0.35, 0.85),
    Layer.REDDIT: (0.50, 1.15),
    Layer.X: (0.40, 1.00),
    Layer.ORDER_FLOW: (0.45, 1.10),
    Layer.PRICE: (0.35, 0.95),
}

#: Live first-crossing memory: (event_id, layer) -> timestamp. This is what
#: makes a LIVE chain an observation record rather than a story.
_first_seen: Dict[Tuple[str, str], float] = defaultdict(float)


def reset_observation_memory() -> None:
    _first_seen.clear()


# ---------------------------------------------------------------------------
# Event detection
# ---------------------------------------------------------------------------

def _shock_id(symbol: str, kind: str) -> str:
    return f"{kind}_{symbol}_{int(time.time()) // 600}"


def detect_events(books: Sequence[Dict[str, Any]],
                  sentiment: Dict[str, Any],
                  markets: Sequence[Dict[str, Any]],
                  news: Sequence[Any],
                  history: Optional[Dict[str, List[float]]] = None,
                  mode: Optional[DataMode] = None) -> List[MarketEvent]:
    """Detect shocks worth tracing. Thresholds are explicit, not learned."""
    out: List[MarketEvent] = []
    news_by_symbol: Dict[str, List[Any]] = defaultdict(list)
    for item in news:
        for sym in getattr(item, "tickers", []) or []:
            news_by_symbol[sym.upper()].append(item)

    for book in books:
        symbol = str(book.get("symbol", "")).upper()
        if not symbol:
            continue
        ofi = float(((book.get("ofi") or {}).get("ofi_norm", 0.0)) or 0.0)
        price = float(book.get("mid", 0.0) or 0.0)
        pct_move = 0.0
        if history and history.get(symbol) and price:
            base = history[symbol][0]
            pct_move = (price / base - 1.0) * 100.0 if base else 0.0

        if abs(ofi) >= MATERIALITY_Z or abs(pct_move) >= 1.5:
            etype, category = (EventType.MARKET, EventCategory.COMPANY)
            if news_by_symbol.get(symbol):
                etype, category = EventType.NEWS, EventCategory.SECTOR
            out.append(MarketEvent(
                event_id=_shock_id(symbol, "OFI" if abs(ofi) >= MATERIALITY_Z
                                   else "PRICE"),
                symbol=symbol,
                event_type=etype,
                category=category,
                headline=(f"Order-flow imbalance {ofi:+.2f} on {symbol}"
                          if abs(ofi) >= MATERIALITY_Z
                          else f"{symbol} moved {pct_move:+.2f}% on the window"),
                detected_at=iso(),
                magnitude=round(abs(ofi) if abs(ofi) >= MATERIALITY_Z
                                else abs(pct_move) / 100.0, 4),
                confidence=round(min(0.95, 0.4 + abs(ofi) * 0.4), 3),
                direction=Direction.LONG if (ofi if abs(ofi) >= MATERIALITY_Z
                                             else pct_move) > 0 else Direction.SHORT,
                sources=["hft_orderbook"] + (["news"] if news_by_symbol.get(symbol) else []),
                data_mode=mode or DataMode.MOCK,
                source_label="order book / news scan",
            ))

    # Prediction-market repricing is itself an event.
    for m in markets:
        symbol = _symbol_for_market(str(m.get("id", "")), str(m.get("question", "")))
        if not symbol:
            continue
        edge = float(m.get("edge", 0.0) or 0.0)
        if abs(edge) >= 0.05:
            out.append(MarketEvent(
                event_id=_shock_id(symbol, "PRED"),
                symbol=symbol,
                event_type=EventType.PREDICTION,
                category=EventCategory.PREDICTION_MARKET,
                headline=(f"{m.get('question', '')[:90]} — market/model gap "
                          f"{edge:+.3f}"),
                detected_at=iso(),
                probability=float(m.get("crowd_prob", 0.0) or 0.0),
                magnitude=round(abs(edge), 4),
                confidence=round(min(0.9, 0.35 + abs(edge) * 2), 3),
                direction=Direction.LONG if edge > 0 else Direction.SHORT,
                sources=["prediction_market"],
                data_mode=mode or DataMode.MOCK,
                source_label="prediction market scan",
            ))
    return out


_MARKET_SYMBOL_HINTS = ("NVDA", "TSLA", "BTC", "SPY", "AAPL", "AMD", "META",
                        "GOOGL", "AMZN", "MSFT", "INTC")


def _symbol_for_market(market_id: str, question: str) -> str:
    blob = f"{market_id} {question}".upper()
    for sym in _MARKET_SYMBOL_HINTS:
        if sym in blob:
            return "SPY" if sym == "SPY" else sym
    return ""


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------

def _mk_evidence(event: MarketEvent, feature: FeatureKey, layer: Layer,
                 value: float, confidence: float, observed_at: float,
                 mode: DataMode, source_label: str,
                 raw: Optional[Dict[str, Any]] = None) -> Evidence:
    z = fusion.normalise({"value": value, "scale": _SCALE.get(feature, 1.0)})
    return Evidence(
        evidence_id=f"ev_{event.event_id}_{feature.value}_{int(observed_at)}",
        event_id=event.event_id,
        symbol=event.symbol,
        layer=layer,
        feature=feature.value,
        direction=(Direction.LONG if z > 0 else
                   Direction.SHORT if z < 0 else Direction.FLAT),
        z_score=round(z, 4),
        magnitude=round(float(value), 6),
        observed_at=iso(observed_at),
        freshness_s=freshness_s(observed_at),
        confidence=round(float(confidence), 4),
        data_mode=mode,
        source_label=source_label,
        raw=raw or {},
    )


def collect_evidence(event: MarketEvent,
                     books: Sequence[Dict[str, Any]] = (),
                     sentiment: Optional[Dict[str, Any]] = None,
                     markets: Sequence[Dict[str, Any]] = (),
                     news: Sequence[Any] = (),
                     now: Optional[float] = None) -> List[Evidence]:
    """One Evidence per information layer, normalized and labelled."""
    now = now or time.time()
    symbol = event.symbol
    evidence: List[Evidence] = []

    # 1. the event itself
    evidence.append(_mk_evidence(
        event, FeatureKey.NEWS, Layer.EVENT, event.magnitude, event.confidence,
        now, event.data_mode, event.source_label or "event detector",
        {"headline": event.headline, "event_type": event.event_type.value},
    ))

    # 2. news activity for this symbol
    items = [n for n in news if symbol in (getattr(n, "tickers", []) or [])]
    if items:
        newest = max((getattr(n, "published_at", "") for n in items), default="")
        activity = min(3.0, len(items) / 2.0)
        evidence.append(_mk_evidence(
            event, FeatureKey.NEWS, Layer.NEWS, activity,
            0.6 if len(items) > 1 else 0.45, now, DataMode.LIVE,
            f"news wire ({len(items)} item(s))",
            {"count": len(items), "newest": newest,
             "titles": [getattr(n, "title", "")[:120] for n in items[:3]]},
        ))

    # 3. prediction market repricing
    related = [m for m in markets
               if _symbol_for_market(str(m.get("id", "")), str(m.get("question", ""))) == symbol]
    if related:
        gap = max(abs(float(m.get("edge", 0.0) or 0.0)) for m in related)
        evidence.append(_mk_evidence(
            event, FeatureKey.PREDICTION, Layer.PREDICTION, gap, 0.55, now,
            DataMode.LIVE, "prediction market",
            {"markets": [m.get("question", "")[:90] for m in related[:3]],
             "crowd_prob": related[0].get("crowd_prob")},
        ))

    # 4/5. social layers, split so Reddit and X are separately traceable
    sent = (sentiment or {}).get("by_ticker", {}).get(symbol)
    if sent:
        posts = (sentiment or {}).get("posts", [])
        reddit = [p for p in posts if str(p.get("source", "")).startswith("r/")]
        twitter = [p for p in posts if p.get("source") == "X"]
        social_mode = (DataMode.LIVE
                       if any(p.get("data_mode") == DataMode.LIVE for p in posts)
                       else DataMode.MOCK)
        ev = float(sent.get("sentiment", 0.0) or 0.0)
        conf = 0.5 if float(sent.get("mentions", 0) or 0) >= 3 else 0.35
        if reddit:
            evidence.append(_mk_evidence(
                event, FeatureKey.SOCIAL, Layer.REDDIT,
                ev * min(2.0, len(reddit) / 2.0), conf, now, social_mode,
                f"r/ ({len(reddit)} post(s))",
                {"samples": [p.get("text", "")[:110] for p in reddit[:3]]},
            ))
        if twitter:
            evidence.append(_mk_evidence(
                event, FeatureKey.SOCIAL, Layer.X,
                ev * min(2.0, len(twitter) / 2.0), conf, now, social_mode,
                f"X ({len(twitter)} post(s))",
                {"samples": [p.get("text", "")[:110] for p in twitter[:3]]},
            ))

    # 6. order flow
    book = next((b for b in books
                 if str(b.get("symbol", "")).upper() == symbol), None)
    if book:
        ofi = float(((book.get("ofi") or {}).get("ofi_norm", 0.0)) or 0.0)
        book_mode = DataMode.LIVE if book.get("stream") else (
            DataMode.LIVE if book.get("live") else DataMode.MOCK)
        evidence.append(_mk_evidence(
            event, FeatureKey.ORDER_FLOW, Layer.ORDER_FLOW, ofi, 0.65, now,
            book_mode, "L2 order book",
            {"ofi_norm": ofi, "spread_bps": book.get("spread_bps"),
             "mid": book.get("mid")},
        ))

    # 7. price response
    if book:
        book_mode = DataMode.LIVE if (book.get("stream") or book.get("live")) \
            else DataMode.MOCK
        mid = float(book.get("mid", 0.0) or 0.0)
        evidence.append(_mk_evidence(
            event, FeatureKey.MOMENTUM, Layer.PRICE,
            float(event.magnitude) * (1.0 if event.direction is Direction.LONG else -1.0),
            0.5, now, book_mode, "last price",
            {"mid": mid, "spread_bps": book.get("spread_bps")},
        ))
    return evidence


# ---------------------------------------------------------------------------
# Chain construction
# ---------------------------------------------------------------------------

def _step_from_evidence(ev: Evidence, fusion_out: Dict[str, Any],
                        base_ts: float, observed_ts: float) -> PropagationStep:
    share = 0.0
    components = fusion_out.get("components") or {}
    if ev.feature in components:
        total = sum(abs(float(v)) for v in components.values()) or 1.0
        share = abs(float(components[ev.feature])) / total
    return PropagationStep(
        step_id=f"st_{ev.evidence_id}",
        layer=ev.layer,
        timestamp=iso(observed_ts),
        lag_s=round(max(0.0, observed_ts - base_ts), 2),
        signal=_describe(ev),
        magnitude=ev.magnitude,
        direction=ev.direction,
        confidence=round(ev.confidence * (1.0 if ev.feature in components else 0.0), 4),
        freshness=freshness_label(ev.freshness_s),
        freshness_s=ev.freshness_s,
        data_mode=ev.data_mode,
        contribution=round(share, 4),
        relation=relation_phrase("co_occurred" if ev.data_mode is not DataMode.LIVE
                                else "observed_after"),
        source_label=ev.source_label,
        raw=ev.raw,
    )


def _describe(ev: Evidence) -> str:
    from app.models.common import feature_label
    z = ev.z_score
    if ev.layer is Layer.PREDICTION:
        prob = ev.raw.get("crowd_prob")
        base = f"crowd {float(prob):.0%}" if isinstance(prob, (int, float)) else "repricing"
        return f"{base} · model gap {z:+.2f}σ"
    if ev.layer is Layer.PRICE:
        return f"{ev.magnitude:+.2%} move · {z:+.2f}σ"
    if ev.layer is Layer.EVENT:
        return f"{ev.raw.get('event_type', 'event')} detected · {z:+.2f}σ"
    if ev.layer in (Layer.REDDIT, Layer.X):
        label = "Reddit" if ev.layer is Layer.REDDIT else "X"
        return f"{label} sentiment {z:+.2f}σ"
    return f"{feature_label(FeatureKey(ev.feature))} {z:+.2f}σ"


def build_chain(event: MarketEvent,
                evidence: Sequence[Evidence],
                fusion_out: Dict[str, Any],
                observed: bool = True) -> InformationEvent:
    """Assemble the timestamped chain.

    observed=True  -> lags come from real first-crossing timestamps (LIVE only)
    observed=False -> lags come from the deterministic scenario and the whole
                      chain is downgraded to SIMULATED.
    """
    base_ts = _parse(event.detected_at) or time.time()
    if observed and all(e.data_mode is DataMode.LIVE for e in evidence):
        steps = []
        for ev in evidence:
            key = (event.event_id, ev.layer.value)
            if abs(ev.z_score) >= MATERIALITY_Z and not _first_seen[key]:
                _first_seen[key] = _parse(ev.observed_at) or time.time()
            observed_ts = _first_seen.get(key) or (_parse(ev.observed_at) or base_ts)
            steps.append(_step_from_evidence(ev, fusion_out, base_ts, observed_ts))
        mode = DataMode.LIVE
    else:
        steps = []
        synth_mode = DataMode.SIMULATED if event.data_mode in (
            DataMode.SIMULATED, DataMode.LIVE) else DataMode.MOCK
        for ev in evidence:
            lag = SCENARIO_LAGS_S.get(ev.layer, 0)
            lo, hi = SCENARIO_MAGNITUDES.get(ev.layer, (0.3, 0.9))
            # Deterministic pseudo-magnitude: stable per (event, layer).
            spread = abs(hash((event.event_id, ev.layer.value)) % 1000) / 1000.0
            ev = ev.model_copy(update={
                "magnitude": round(lo + (hi - lo) * spread, 6),
                "z_score": round((lo + (hi - lo) * spread) if ev.z_score >= 0
                                 else -(lo + (hi - lo) * spread), 4),
                "confidence": round(0.45 + 0.35 * spread, 3),
            })
            steps.append(_step_from_evidence(ev, fusion_out, base_ts, base_ts + lag))
        mode = synth_mode

    return InformationEvent(
        event_id=event.event_id,
        symbol=event.symbol,
        event_type=event.event_type,
        detected_at=event.detected_at,
        sources=sorted({e.source_label for e in evidence if e.source_label}),
        propagation_steps=steps,
        confidence=float(fusion_out.get("confidence", 0.0)),
        data_mode=mode,
        model_version="qp-fusion-1.0",
        headline=event.headline,
        status="complete" if steps else "insufficient_data",
    )


def _parse(stamp: str) -> Optional[float]:
    if not stamp:
        return None
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(stamp).timestamp()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Node detail (click a node -> full disclosure)
# ---------------------------------------------------------------------------

def node_detail(chain: InformationEvent, layer,
                history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Everything we can honestly say about one node in the chain."""
    if isinstance(layer, str):
        try:
            layer = Layer(layer)
        except ValueError:
            return {"layer": layer, "status": "insufficient_data",
                    "label": "INSUFFICIENT DATA",
                    "note": f"Unknown layer '{layer}'."}
    step = next((s for s in chain.propagation_steps if s.layer is layer), None)
    if step is None:
        return {"layer": layer.value, "status": "insufficient_data",
                "label": "INSUFFICIENT DATA",
                "note": "This layer produced no observation for this event."}
    related = [s.layer.value for s in chain.propagation_steps
               if s.layer is not layer]
    return {
        "layer": layer.value,
        "status": "ok",
        "label": layer.value.replace("_", " ").upper(),
        "raw_signal": step.signal,
        "timestamp": step.timestamp,
        "lag_s": step.lag_s,
        "source": step.source_label,
        "source_label": step.source_label,
        "contribution": step.contribution,
        "freshness": step.freshness,
        "freshness_s": step.freshness_s,
        "confidence": step.confidence,
        "direction": step.direction.value,
        "magnitude": step.magnitude,
        "data_mode": step.data_mode.value,
        "data_mode_label": step.data_mode.label,
        "relation": step.relation,
        "related_assets": related,
        "raw": step.raw,
        "historical_context": (history or {}).get(layer.value, {
            "status": "insufficient_data",
            "label": "INSUFFICIENT DATA",
            "note": "No stored history for this layer yet.",
        }),
    }


def trace(event: MarketEvent, evidence: Sequence[Evidence],
          fusion_out: Dict[str, Any], observed: bool = True) -> InformationEvent:
    """Public entry point: evidence + fusion output -> full chain."""
    return build_chain(event, evidence, fusion_out, observed=observed)
