"""Parakh — thesis lifecycle: create from a check, resolve against prices."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.parakh import autopsy, calibration, market, store, thesis_check
from app.parakh.models import ThesisCheckRow


def create(user_id: str, report: Dict[str, Any], idea_text: str) -> ThesisCheckRow:
    row = ThesisCheckRow(
        id=thesis_check.new_id(), user_id=user_id, symbol=report["symbol"],
        direction=report["direction"], horizon_days=report["horizon_days"],
        entry_price=report["entry_price"], target_price=report["target_price"],
        stop_price=report["stop_price"], user_confidence=report["user_confidence"],
        idea_text=idea_text[:1000], catalyst=(report.get("catalyst") or "")[:200],
        report=json.dumps(report, default=str),
        robustness=float((report.get("stress") or {}).get("robustness") or 0.0),
        base_rate=(report.get("analogues") or {}).get("hit_rate"),
        data_mode=report.get("data_mode", "live"),
    )
    # Anchor the thesis to the bar it was priced on, so resolution starts the next bar.
    row.created_at = datetime.now(timezone.utc)
    return store.save_thesis(row)


def resolve_row(row: ThesisCheckRow) -> bool:
    """Walk bars after the thesis date. Returns True if the row changed."""
    if row.status != "open":
        return False
    report = json.loads(row.report or "{}")
    as_of = report.get("as_of") or row.created_at.date().isoformat()
    bars, _ = market.history(row.symbol, 500)
    after = [b for b in bars if b["date"] > as_of]
    if not after:
        return False
    long = row.direction == "LONG"
    status, exit_bar, exit_px = None, None, None
    for k, b in enumerate(after[: row.horizon_days]):
        hit_s = b["low"] <= row.stop_price if long else b["high"] >= row.stop_price
        hit_t = b["high"] >= row.target_price if long else b["low"] <= row.target_price
        if hit_s:                            # same-day tie resolves as a stop (conservative)
            status, exit_bar, exit_px = "miss", b, row.stop_price
            break
        if hit_t:
            status, exit_bar, exit_px = "hit", b, row.target_price
            break
    if status is None and len(after) >= row.horizon_days:
        exit_bar = after[row.horizon_days - 1]
        status, exit_px = "expired", exit_bar["close"]
    if status is None:
        return False
    row.status = status
    row.exit_price = round(float(exit_px), 2)
    row.resolved_at = datetime.now(timezone.utc)
    sign = 1 if long else -1
    row.outcome_return_pct = round((row.exit_price / row.entry_price - 1) * 100 * sign, 2)
    row.autopsy = json.dumps(autopsy.diagnose(
        symbol=row.symbol, direction=row.direction, entry=row.entry_price,
        exit_price=row.exit_price, entry_date=as_of, exit_date=exit_bar["date"],
        stop=row.stop_price, target=row.target_price, horizon=row.horizon_days,
        user_confidence=row.user_confidence, report=report), default=str)
    store.update_thesis(row)
    return True


def resolve_user(user_id: str) -> int:
    n = 0
    for row in store.list_theses(user_id, status="open", limit=500):
        try:
            n += resolve_row(row)
        except Exception:
            continue
    return n


def user_calibration(user_id: str) -> Dict[str, Any]:
    rows = [r for r in store.list_theses(user_id, limit=2000) if r.status != "open"]
    pairs = [(r.user_confidence, 1 if r.status == "hit" else 0) for r in rows]
    dated = [((r.resolved_at or r.created_at).isoformat(), r.user_confidence,
              1 if r.status == "hit" else 0) for r in rows]
    out = calibration.compute(pairs, dated)
    # Parakh's own reference forecast on the same ideas: is the user beating the base rate?
    ref = [((r.base_rate if r.base_rate is not None else 0.5), 1 if r.status == "hit" else 0) for r in rows]
    if len(ref) >= calibration.SCORE_FLOOR:
        out["reference_brier"] = round(sum((p - y) ** 2 for p, y in ref) / len(ref), 4)
        out["reference_note"] = ("Brier score of the historical base rate on the same ideas. "
                                 "Lower is better; if yours is higher, the base rate forecast better than you.")
    return out
