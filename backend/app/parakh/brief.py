"""Parakh — Feature 11: the 1-minute daily brief."""
from __future__ import annotations

from typing import Any, Dict

from app.parakh import hype_radar, llm, market, store, theses


def build(user_id: str, narrate: bool = False) -> Dict[str, Any]:
    theses.resolve_user(user_id)
    open_rows = store.list_theses(user_id, "open", limit=20)
    recent = [r for r in store.list_theses(user_id, limit=30) if r.status != "open"][:5]
    nifty = market.quote("NIFTY")
    bank = market.quote("BANKNIFTY")
    wl = store.watchlist(user_id)
    hype = [h for h in hype_radar.scan(wl) if h["signal"]][:5] if wl else []
    open_view = []
    for r in open_rows:
        q = market.quote(r.symbol)
        long = r.direction == "LONG"
        to_target = (r.target_price - q["price"]) / q["price"] * 100 * (1 if long else -1)
        to_stop = (q["price"] - r.stop_price) / q["price"] * 100 * (1 if long else -1)
        open_view.append({"id": r.id, "symbol": r.symbol, "direction": r.direction, "price": q["price"],
                          "to_target_pct": round(to_target, 2), "to_stop_pct": round(to_stop, 2),
                          "near_stop": to_stop < 1.0})
    cal = theses.user_calibration(user_id)
    out = {
        "market": {"nifty": nifty, "banknifty": bank},
        "open_ideas": open_view,
        "recently_resolved": [{"id": r.id, "symbol": r.symbol, "status": r.status,
                               "return_pct": r.outcome_return_pct} for r in recent],
        "hype_alerts": hype, "watchlist": wl,
        "calibration": {k: cal.get(k) for k in ("status", "score", "verdict", "message", "n")},
        "data_mode": nifty["data_mode"],
    }
    if narrate and llm.available():
        out["summary"] = llm.write("Write a 4-line morning brief for this trader from the data. "
                                   "No advice, just what to watch.\n" + str(out), max_tokens=1200)
    return out
