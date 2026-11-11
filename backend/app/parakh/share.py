"""
Parakh — Feature 8: verified public track records.

A thesis made public gets a slug and a SHA-256 seal over its original terms
(idea, symbol, direction, entry, target, stop, horizon, confidence, the
price date it was checked on, and creation time). Parakh has no edit
endpoint for theses and resolution is automatic, so anyone can recompute
the seal from the public page and confirm nothing was changed after the
fact. The leaderboard ranks by calibration (Brier score), not by profit.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any, Dict, List

from sqlmodel import select

from app.parakh import calibration, store
from app.parakh.models import ThesisCheckRow, UserSettingsRow

LEADERBOARD_FLOOR = 10


def canonical_terms(row: ThesisCheckRow) -> Dict[str, Any]:
    report = json.loads(row.report or "{}")
    return {"id": row.id, "symbol": row.symbol, "direction": row.direction,
            "entry_price": row.entry_price, "target_price": row.target_price,
            "stop_price": row.stop_price, "horizon_days": row.horizon_days,
            "user_confidence": row.user_confidence, "idea_text": row.idea_text,
            "priced_on": report.get("as_of", ""),
            "created_at": row.created_at.replace(tzinfo=None).isoformat(timespec="seconds")}


def seal(row: ThesisCheckRow) -> str:
    blob = json.dumps(canonical_terms(row), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def publish(row: ThesisCheckRow) -> ThesisCheckRow:
    if not row.is_public:
        row.is_public = True
        row.share_slug = row.share_slug or secrets.token_urlsafe(8)
        row.seal_hash = seal(row)
        store.update_thesis(row)
    return row


def public_view(slug: str) -> Dict[str, Any]:
    with store.session() as s:
        row = s.exec(select(ThesisCheckRow).where(ThesisCheckRow.share_slug == slug,
                                                  ThesisCheckRow.is_public == True)).first()  # noqa: E712
        if not row:
            raise KeyError(slug)
        prefs = s.get(UserSettingsRow, row.user_id)
    report = json.loads(row.report or "{}")
    terms = canonical_terms(row)
    return {
        "terms": terms, "seal": row.seal_hash, "seal_valid": seal(row) == row.seal_hash,
        "how_to_verify": "sha256 of the JSON 'terms' with sorted keys and no spaces must equal 'seal'.",
        "author": (prefs.public_handle if prefs and prefs.public_handle else "anonymous"),
        "status": row.status, "exit_price": row.exit_price,
        "outcome_return_pct": row.outcome_return_pct,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
        "checklist_score": report.get("checklist_score"), "name": report.get("name"),
        "data_mode": row.data_mode,
    }


def leaderboard(limit: int = 50) -> List[Dict[str, Any]]:
    with store.session() as s:
        handles = {r.user_id: r.public_handle for r in
                   s.exec(select(UserSettingsRow).where(UserSettingsRow.public_handle != None))}  # noqa: E711
        rows = list(s.exec(select(ThesisCheckRow).where(ThesisCheckRow.is_public == True,  # noqa: E712
                                                        ThesisCheckRow.status != "open")))
    by_user: Dict[str, List[ThesisCheckRow]] = {}
    for r in rows:
        if r.user_id in handles and r.data_mode == "live":
            by_user.setdefault(r.user_id, []).append(r)
    board = []
    for uid, rs in by_user.items():
        if len(rs) < LEADERBOARD_FLOOR:
            continue
        c = calibration.compute([(r.user_confidence, 1 if r.status == "hit" else 0) for r in rs])
        board.append({"handle": handles[uid], "n": c["n"], "brier": c["brier"],
                      "calibration_score": c["score"], "hit_rate": c["hit_rate"],
                      "avg_confidence": c["avg_confidence"]})
    board.sort(key=lambda b: (b["brier"], -b["n"]))
    for i, b in enumerate(board, 1):
        b["rank"] = i
    return board[:limit]
