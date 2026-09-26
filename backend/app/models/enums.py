"""
QuantPulse AI — Research domain enums.

One taxonomy shared by every research service. Adding a layer, a feature or
an event type here makes it available to the propagation engine, the fusion
model, the stress lab, the autopsy and the tournament at once — that shared
vocabulary is what keeps the five features one system instead of five demos.

Every str-Enum carries a tolerant _missing_ so that str(enum) leftovers
("DataMode.SIMULATED") parsed from older rows never break the read path.
"""
from __future__ import annotations

from enum import Enum


def _make_missing():
    """Return a tolerant _missing_ classmethod for a str,Enum subclass."""
    def _missing_(cls, value):
        if isinstance(value, str):
            prefix = cls.__name__ + "."
            name = (value.split(".", 1)[1].lower()
                    if value.startswith(prefix) else value.lower())
            for member in cls:
                if member.value == name or member.name.lower() == name:
                    return member
        return None
    return classmethod(_missing_)


class DataMode(str, Enum):
    """Provenance of a record. Never inferred, never defaulted to LIVE."""

    LIVE = "live"            # real feed, credentialed
    SIMULATED = "simulated"  # deterministic synthetic scenario (demo)
    MOCK = "mock"            # no credential; seeded simulator
    BACKTEST = "backtest"    # replayed historical window

    @property
    def label(self) -> str:
        return {
            DataMode.LIVE: "LIVE",
            DataMode.SIMULATED: "SIMULATED SCENARIO",
            DataMode.MOCK: "MOCK",
            DataMode.BACKTEST: "BACKTEST",
        }[self]

    _missing_ = _make_missing()


#: Ordering used when a record mixes layers of differing provenance. The
#: weakest link wins: one mocked layer makes the whole record MOCK.
MODE_STRENGTH = {
    DataMode.LIVE: 3,
    DataMode.BACKTEST: 2,
    DataMode.SIMULATED: 1,
    DataMode.MOCK: 0,
}


def weakest(*modes: DataMode) -> DataMode:
    """Roll several provenance labels up to the single honest label."""
    real = [m for m in modes if m]
    if not real:
        return DataMode.MOCK
    return min(real, key=lambda m: MODE_STRENGTH[m])


class Layer(str, Enum):
    """Information-propagation layers, in canonical observation order."""

    EVENT = "event"
    NEWS = "news"
    PREDICTION = "prediction"
    REDDIT = "reddit"
    X = "x"
    ORDER_FLOW = "order_flow"
    PRICE = "price"

    @property
    def order(self) -> int:
        return _LAYER_ORDER[self]

    _missing_ = _make_missing()


_LAYER_ORDER = {
    Layer.EVENT: 0,
    Layer.NEWS: 1,
    Layer.PREDICTION: 2,
    Layer.REDDIT: 3,
    Layer.X: 4,
    Layer.ORDER_FLOW: 5,
    Layer.PRICE: 6,
}


#: Visual signature (see design-system/quantpulse-ai/MASTER.md). One accent
#: per layer, reused by every graph, card and timeline in the product.
LAYER_ACCENT = {
    Layer.EVENT: "information",
    Layer.NEWS: "information",
    Layer.PREDICTION: "prediction",
    Layer.REDDIT: "social",
    Layer.X: "social",
    Layer.ORDER_FLOW: "orderflow",
    Layer.PRICE: "price",
}


class EventType(str, Enum):
    NEWS = "news"
    EARNINGS = "earnings"
    SOCIAL = "social"
    PREDICTION = "prediction"
    MARKET = "market"
    MACRO = "macro"
    REGULATORY = "regulatory"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    AI = "ai"
    COMMODITY = "commodity"
    RATES = "rates"
    ELECTIONS = "elections"
    COMPANY = "company"
    SECTOR = "sector"

    _missing_ = _make_missing()


class EventCategory(str, Enum):
    """Extensible taxonomy for the transmission map (F3)."""

    MACRO = "macro"
    EARNINGS = "earnings"
    REGULATORY = "regulatory"
    GEOPOLITICAL = "geopolitical"
    TECHNOLOGY = "technology"
    AI = "ai"
    COMMODITY = "commodity"
    RATES = "rates"
    ELECTIONS = "elections"
    COMPANY = "company"
    SECTOR = "sector"
    PREDICTION_MARKET = "prediction-market"
    SOCIAL = "social"

    _missing_ = _make_missing()


#: Allowed relationship vocabulary. Causal language is deliberately absent:
#: the platform reports co-occurrence and ordering, never causation it has
#: not demonstrated.
RELATION_VOCABULARY = ("observed", "historical", "correlated", "associated",
                       "potentially affected")


class RelationKind(str, Enum):
    OBSERVED = "observed"
    HISTORICAL = "historical"
    CORRELATED = "correlated"
    ASSOCIATED = "associated"
    POTENTIALLY_AFFECTED = "potentially affected"

    _missing_ = _make_missing()


#: Causality is not in this enum on purpose — see RELATION_VOCABULARY.
CAUSAL_CLAIMS_FORBIDDEN = ("caused", "causes", "proved", "proven", "guaranteed",
                           "because of", "due to this event", "led to")


class FeatureKey(str, Enum):
    """Fusion inputs. The tournament ablates exactly these keys."""

    ORDER_FLOW = "order_flow"
    SOCIAL = "social"
    PREDICTION = "prediction"
    MOMENTUM = "momentum"
    NEWS = "news"
    QUANTUM = "quantum"

    _missing_ = _make_missing()


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

    @property
    def sign(self) -> float:
        return {"LONG": 1.0, "SHORT": -1.0, "FLAT": 0.0}[self.value]

    _missing_ = _make_missing()


class Regime(str, Enum):
    TREND = "trend"
    HIGH_VOL = "high_vol"
    MEAN_REVERSION = "mean_reversion"
    RANGE_BOUND = "range_bound"
    UNKNOWN = "unknown"

    _missing_ = _make_missing()


class Horizon(str, Enum):
    """Prediction horizon. Minutes are used so mock scenarios can resolve."""

    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def minutes(self) -> int:
        return {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}[self.value]

    _missing_ = _make_missing()


class StressScenario(str, Enum):
    """Named perturbations. Values are multipliers applied to evidence."""

    SENTIMENT_DETERIORATION = "sentiment_deterioration"
    ORDER_FLOW_REVERSAL = "order_flow_reversal"
    PREDICTION_DISAGREEMENT = "prediction_disagreement"
    VOLATILITY_EXPANSION = "volatility_expansion"
    LIQUIDITY_DETERIORATION = "liquidity_deterioration"
    MOMENTUM_REVERSAL = "momentum_reversal"
    CONFLICTING_SOURCE = "conflicting_source"

    _missing_ = _make_missing()


class Verdict(str, Enum):
    """Per-component autopsy verdict. Never 'proved correct'."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    NEUTRAL = "neutral"
    UNAVAILABLE = "unavailable"

    _missing_ = _make_missing()


class FailureMode(str, Enum):
    REGIME_MISCLASSIFICATION = "regime_misclassification"
    VOLATILITY_UNDERESTIMATION = "volatility_underestimation"
    SENTIMENT_DECEIVERY = "sentiment_deceit"
    FLOW_DECAY = "flow_decay"
    PREDICTION_DIVERGENCE = "prediction_divergence"
    LIQUIDITY_EXHAUSTION = "liquidity_exhaustion"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    UNCLASSIFIED = "unclassified"

    _missing_ = _make_missing()


class MetricKey(str, Enum):
    """Metrics the tournament may compute. Only what the run can support."""

    DIRECTIONAL_ACCURACY = "directional_accuracy"
    HIT_RATE = "hit_rate"
    MEAN_ABS_ERROR_PCT = "mean_abs_error_pct"
    BRIER_SCORE = "brier_score"
    CALIBRATION_ERROR = "calibration_error"
    SHARPE = "sharpe"
    MAX_DRAWDOWN_PCT = "max_drawdown_pct"
    TURNOVER = "turnover"
    MEAN_CONFIDENCE = "mean_confidence"
    SAMPLE_SIZE = "sample_size"

    _missing_ = _make_missing()


#: Below this many resolved observations, performance statistics are withheld
#: and the API returns INSUFFICIENT DATA instead of a number.
MIN_SAMPLE_FOR_PERFORMANCE = 20
