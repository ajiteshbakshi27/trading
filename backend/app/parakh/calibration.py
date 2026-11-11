"""
Parakh — Feature 4: personal calibration.

"When you say 80% sure, how often are you right?"  Each resolved thesis is
a forecast (the user's stated confidence that the target is hit before the
stop within the horizon) and an outcome (1 if hit, else 0).

Scores are withheld below a sample floor so a lucky streak of three isn't
presented as skill.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

SCORE_FLOOR = 10
BINS = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]


def compute(pairs: Sequence[Tuple[float, int]], dated: Sequence[Tuple[str, float, int]] = ()) -> Dict[str, Any]:
    """pairs: (stated_confidence, hit 0/1)."""
    n = len(pairs)
    out: Dict[str, Any] = {"n": n, "floor": SCORE_FLOOR}
    bins: List[Dict[str, Any]] = []
    for lo, hi in BINS:
        sel = [(p, y) for p, y in pairs if lo <= p < hi]
        k = len(sel)
        bins.append({"range": f"{int(lo * 100)}–{min(100, int(hi * 100))}%",
                     "stated": round(sum(p for p, _ in sel) / k, 3) if k else None,
                     "actual": round(sum(y for _, y in sel) / k, 3) if k else None,
                     "n": k})
    out["bins"] = bins
    if n < SCORE_FLOOR:
        out.update({"status": "insufficient",
                    "message": f"{n} resolved ideas so far — your score appears after {SCORE_FLOOR}."})
        return out
    brier = sum((p - y) ** 2 for p, y in pairs) / n
    avg_conf = sum(p for p, _ in pairs) / n
    hit_rate = sum(y for _, y in pairs) / n
    gap = avg_conf - hit_rate
    # 0..100 where 100 = perfect; 75 ≈ always saying 50% (Brier 0.25)
    score = round(max(0.0, 1 - brier) * 100)
    if gap > 0.15:
        verdict = (f"Overconfident: you average {avg_conf * 100:.0f}% confidence but are right "
                   f"{hit_rate * 100:.0f}% of the time.")
    elif gap < -0.15:
        verdict = (f"Underconfident: you're right {hit_rate * 100:.0f}% of the time while saying "
                   f"{avg_conf * 100:.0f}%. Trust your process a bit more.")
    else:
        verdict = "Well calibrated: your stated confidence roughly matches your hit rate."
    out.update({"status": "ok", "brier": round(brier, 4), "score": score,
                "avg_confidence": round(avg_conf, 3), "hit_rate": round(hit_rate, 3),
                "overconfidence_gap": round(gap, 3), "verdict": verdict})
    if dated:
        series, roll = [], []
        for date, p, y in sorted(dated):
            roll.append((p - y) ** 2)
            window = roll[-SCORE_FLOOR:]
            if len(roll) >= SCORE_FLOOR:
                series.append({"date": date[:10],
                               "score": round(max(0.0, 1 - sum(window) / len(window)) * 100)})
        out["trend"] = series
    return out
