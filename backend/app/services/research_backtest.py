"""
QuantPulse AI — Research Backtester.

Replays the closed loop over a historical price window so the platform can
report *measured* results instead of INSUFFICIENT DATA.

For each trading day t in the window:
    1. detect events from the price/vol action up to t
    2. collect evidence (news/social/prediction/flow/momentum proxies)
    3. fuse into a signal + thesis
    4. stress the thesis
    5. create a prediction for t -> t+1
    6. resolve against the *actual* next-day move
    7. autopsy failures

Everything is labelled BACKTEST. When real historical data is unreachable
the module falls back to a deterministic synthetic price path and says so —
it never presents synthetic history as real.

The output feeds the same failure-analysis and tournament code paths, so a
backtested thesis is directly comparable to a live one.
"""
from __future__ import annotations

import math
import random
import statistics
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.common import INSUFFICIENT_DATA, clamp, insufficient, iso
from app.models.enums import (
    DataMode,
    Direction,
    FeatureKey,
    Horizon,
    Regime,
    weakest,
)
from app.models.prediction_outcome import (
    Autopsy,
    FeatureContribution,
    PredictionOutcome,
    PredictionRecord,
    SignalVerdict,
)
from app.services import event_transmission, feed_layer, fusion, prediction_autopsy

MODEL_VERSION = "qp-fusion-1.0"
BACKTEST = DataMode.BACKTEST


# ---------------------------------------------------------------------------
# Historical data
# ---------------------------------------------------------------------------

def _load_prices(symbol: str, period: str = "1y") -> Tuple[Optional[List[float]], DataMode]:
    """Daily closes from yfinance. (None, MOCK) when unreachable.

    Wrapped in a timeout so a restricted or slow network cannot hang the
    backtest — the caller falls back to the deterministic synthetic path.
    """
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(feed_layer.get_history, symbol, period=period)
            frame, mode = future.result(timeout=20.0)
    except Exception:
        return None, DataMode.MOCK
    if frame is None or len(frame) < 30:
        return None, DataMode.MOCK
    try:
        closes = [float(v) for v in frame["Close"].values if v and v > 0]
        return (closes if len(closes) >= 30 else None), mode
    except Exception:
        return None, DataMode.MOCK


def _synthetic_prices(n: int, seed: int) -> List[float]:
    """Deterministic GBM price path. Used only when real history is absent."""
    rng = random.Random(seed)
    px = 100.0
    out = []
    for _ in range(n):
        px = max(1.0, px * (1 + rng.gauss(0.0004, 0.011)))
        out.append(round(px, 4))
    return out


# ---------------------------------------------------------------------------
# Per-day evidence construction
# ---------------------------------------------------------------------------

def _daily_evidence(closes: List[float], i: int,
                    rng: random.Random) -> List[Dict[str, Any]]:
    """Build one day's fusion evidence from the price path.

    INTEGRITY: only information available *before* day i is used. The forward
    return is never touched — using it would be look-ahead bias and would
    produce a flattering but meaningless accuracy number.

    In a backtest we do not have live social/news/prediction feeds for each
    historical day, so those layers are represented by a deterministic
    function of *past* price action only. This is documented as such and
    labelled BACKTEST. The construction is the same one the tournament uses
    for its synthetic observation set, so backtested and synthetic results
    are comparable.
    """
    window = closes[max(0, i - 20):i + 1]
    if len(window) < 10:
        return []
    recent = window[-10:]
    trend = (recent[-1] / recent[0] - 1.0) * 100.0
    rets = [(recent[j] / recent[j - 1] - 1.0) * 100.0
            for j in range(1, len(recent))]
    mean = sum(rets) / len(rets)
    vol = math.sqrt(sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1))

    # Deterministic pseudo-observations for the layers we cannot reconstruct.
    # Each is a function of PAST returns only. Correlations are chosen to be
    # plausible, not estimated — see README. No forward information is used.
    past_signal = trend * 0.6 + vol * 0.4
    base_corr = {
        "order_flow": 0.55,
        "momentum": 0.45,
        "prediction": 0.30,
        "news": 0.25,
        "social": 0.18,
        "quantum": 0.08,
    }
    evidence = []
    for feature, corr in base_corr.items():
        noise = rng.gauss(0.0, 0.85)
        value = corr * past_signal + noise
        layer = {
            "social": "reddit" if rng.random() < 0.6 else "x",
        }.get(feature, feature)
        evidence.append({
            "feature": feature,
            "z_score": round(max(-3.0, min(3.0, value / 0.85)), 4),
            "confidence": round(rng.uniform(0.35, 0.85), 3),
            "data_mode": BACKTEST.value,
            "layer": layer,
        })
    return evidence


def _regime_at(closes: List[float], i: int) -> Regime:
    window = closes[max(0, i - 20):i + 1]
    if len(window) < 10:
        return Regime.UNKNOWN
    recent = window[-10:]
    trend = (recent[-1] / recent[0] - 1.0) * 100.0
    rets = [(recent[j] / recent[j - 1] - 1.0) * 100.0
            for j in range(1, len(recent))]
    mean = sum(rets) / len(rets)
    vol = math.sqrt(sum((r - mean) ** 2 for r in rets) / max(1, len(rets) - 1))
    return fusion.classify_regime(vol, trend)


# ---------------------------------------------------------------------------
# The replay loop
# ---------------------------------------------------------------------------

def run_backtest(symbol: str, period: str = "1y", min_resolved: int = 20,
                 seed: int = 7) -> Dict[str, Any]:
    """Replay the closed loop over a historical window.

    Returns a result dict with measured metrics, per-regime breakdown, and
    the list of resolved predictions (for provenance + failure analysis).
    """
    closes, price_mode = _load_prices(symbol, period)
    source = "yfinance"
    if closes is None:
        closes = _synthetic_prices(252, seed)
        price_mode = DataMode.MOCK
        source = "synthetic (deterministic GBM)"
    # A historical replay is a BACKTEST even when the price feed is real:
    # the event/evidence/social layers are reconstructed, not observed.
    # MOCK is reserved for the case where even the price path is synthetic.
    data_mode = DataMode.BACKTEST if price_mode is not DataMode.MOCK else DataMode.MOCK

    rng = random.Random(seed + abs(hash(symbol)) % 1000)
    resolved: List[Dict[str, Any]] = []
    n_days = 0
    regime_counts: Dict[str, int] = {}

    # Walk the window; skip the first 20 days (warmup) and the last (no t+1).
    for i in range(20, len(closes) - 1):
        n_days += 1
        regime = _regime_at(closes, i)
        regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1

        evidence = _daily_evidence(closes, i, rng)
        fused = fusion.fuse(evidence)
        if fused["abstaining"]:
            continue

        direction = fused["direction"]
        confidence = fused["confidence"]
        entry = closes[i]
        actual_fwd = (closes[i + 1] / entry - 1.0) * 100.0
        exit_px = closes[i + 1]
        signed = actual_fwd * direction.sign
        correct = signed > 0.0
        expected = round(clamp(confidence) * 4.0, 3)

        pred_id = f"bt_{symbol}_{i}_{int(time.time() * 1000)}"
        trace_rows = fused["trace"]["features"]
        total = sum(abs(float(r["contribution"])) for r in trace_rows
                    if r.get("usable")) or 1.0
        contributions = []
        for row in trace_rows:
            try:
                feat = FeatureKey(str(row["feature"]))
            except ValueError:
                continue
            contrib = float(row["contribution"])
            contributions.append(FeatureContribution(
                feature=feat, weight=float(row["weight"]),
                z_score=float(row["z_score"]), contribution=round(contrib, 4),
                share=round(abs(contrib) / total, 4),
            ))

        prediction = PredictionRecord(
            prediction_id=pred_id,
            symbol=symbol.upper(),
            direction=direction,
            confidence=confidence,
            fused_score=fused["fused_score"],
            entry_price=round(entry, 4),
            expected_move_pct=expected,
            horizon=Horizon.D1,
            created_at=iso(),
            expires_at=iso(),
            regime=regime,
            model_version=MODEL_VERSION,
            data_mode=data_mode,
            evidence=evidence,
            feature_contributions=contributions,
            status="resolved",
        )
        outcome = prediction_autopsy.resolve(
            prediction, exit_px, source="backtest replay", data_mode=data_mode)

        record = {
            "day_index": i,
            "entry_price": round(entry, 4),
            "exit_price": round(exit_px, 4),
            "direction": direction.value,
            "confidence": round(confidence, 4),
            "expected_move_pct": expected,
            "actual_move_pct": round(actual_fwd, 4),
            "signed_move_pct": round(signed, 4),
            "correct": bool(correct),
            "regime": regime.value,
            "error_pct": round(signed - expected, 4),
            "data_mode": data_mode.value,
        }

        if not correct:
            realized_regime = _regime_at(closes, min(i + 1, len(closes) - 1))
            autopsy = prediction_autopsy.run_autopsy(
                prediction, outcome, realized_regime=realized_regime)
            record["autopsy"] = {
                "failure_mode": autopsy.failure_mode.value,
                "mode_likelihood": autopsy.mode_likelihood,
                "regime_mismatch": autopsy.regime_mismatch,
            }
        resolved.append(record)

    # Aggregate. Withhold everything below the sample floor.
    n = len(resolved)
    if n < min_resolved:
        return {
            "status": "insufficient_data",
            "label": INSUFFICIENT_DATA,
            "symbol": symbol.upper(),
            "period": period,
            "source": source,
            "n_days": n_days,
            "n_resolved": n,
            "required": min_resolved,
            "regime_distribution": regime_counts,
            "data_mode": data_mode.value,
            "note": insufficient("backtest results", n, min_resolved)["note"],
            "predictions": resolved,
        }

    correct = sum(1 for r in resolved if r["correct"])
    errs = [r["error_pct"] for r in resolved]
    confs = [r["confidence"] for r in resolved]
    by_regime: Dict[str, List[Dict[str, Any]]] = {}
    for r in resolved:
        by_regime.setdefault(r["regime"], []).append(r)
    regime_rows = []
    for regime, rows in by_regime.items():
        c = sum(1 for r in rows if r["correct"])
        regime_rows.append({
            "regime": regime,
            "n": len(rows),
            "accuracy": round(c / len(rows), 4),
            "mean_error_pct": round(statistics.fmean([r["error_pct"] for r in rows]), 4),
        })
    return {
        "status": "ok",
        "label": "",
        "symbol": symbol.upper(),
        "period": period,
        "source": source,
        "n_days": n_days,
        "n_resolved": n,
        "required": min_resolved,
        "accuracy": round(correct / n, 4),
        "mean_error_pct": round(statistics.fmean(errs), 4),
        "mean_confidence": round(statistics.fmean(confs), 4),
        "brier_score": round(statistics.fmean(
            [((c if r["direction"] == "LONG" else 1.0 - c)
              - (1.0 if r["correct"] else 0.0)) ** 2 for r, c in zip(resolved, confs)]), 4),
        "regime_distribution": regime_counts,
        "by_regime": regime_rows,
        "failure_categories": _failure_categories(resolved),
        "data_mode": data_mode.value,
        "note": (f"Backtested over {n_days} trading days ({source}). "
                 f"Accuracy is directional; error is signed-minus-expected."),
        "predictions": resolved[:200],
    }


def _failure_categories(resolved: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets: Dict[str, List[float]] = {}
    for r in resolved:
        mode = (r.get("autopsy") or {}).get("failure_mode", "unclassified")
        buckets.setdefault(mode, []).append(r["error_pct"])
    total = sum(len(v) for v in buckets.values()) or 1
    return [
        {"failure_mode": mode, "count": len(vals),
         "share": round(len(vals) / total, 4),
         "mean_error_pct": round(statistics.fmean(vals), 4)}
        for mode, vals in sorted(buckets.items(), key=lambda kv: -len(kv[1]))
    ]


# ---------------------------------------------------------------------------
# Multi-symbol suite
# ---------------------------------------------------------------------------

def run_suite(symbols: Sequence[str], period: str = "1y",
              min_resolved: int = 20, seed: int = 7) -> Dict[str, Any]:
    """Run the backtest for several symbols and aggregate."""
    results = [run_backtest(s, period=period, min_resolved=min_resolved, seed=seed)
               for s in symbols]
    combined = [r for res in results for r in res.get("predictions", [])]
    modes = []
    for res in results:
        try:
            modes.append(DataMode(res.get("data_mode", "mock")))
        except ValueError:
            modes.append(DataMode.MOCK)
    aggregate: Dict[str, Any] = {
        "status": "ok",
        "symbols": [s.upper() for s in symbols],
        "period": period,
        "n_resolved_total": len(combined),
        "data_mode": weakest(*modes).value if modes else DataMode.MOCK.value,
        "results": results,
    }
    if len(combined) >= min_resolved:
        correct = sum(1 for r in combined if r["correct"])
        aggregate["accuracy"] = round(correct / len(combined), 4)
        aggregate["mean_error_pct"] = round(
            statistics.fmean([r["error_pct"] for r in combined]), 4)
    else:
        aggregate["status"] = "insufficient_data"
        aggregate["label"] = INSUFFICIENT_DATA
    return aggregate
