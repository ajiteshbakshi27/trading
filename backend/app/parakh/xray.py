"""
Parakh — Tradebook X-ray.

Takes closed round trips (from ``journal.round_trips``) and shows where the
trader's losses cluster, in rupees: trades taken right after a loss, trades
late in a busy day, losers held too long, outsized losses, the opening rush
and the worst symbol.

Integrity rules this module follows:
  * Every figure is a plain sum over the trader's own trades. Nothing is
    modelled, estimated or random.
  * A habit is only reported when it has at least ``PATTERN_FLOOR`` trades,
    and the whole report needs ``MIN_TRIPS`` round trips.
  * It reports what those trades netted. It never claims the money would have
    been saved by not taking them (that is a counterfactual we cannot know).
  * Habits overlap (a revenge trade can also be the 5th trade of the day), so
    the costs must not be added together. The output says so.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List

from app.parakh.journal import IST, _dt

MIN_TRIPS = 20            # below this the whole report is INSUFFICIENT DATA
PATTERN_FLOOR = 5         # a habit needs this many trades to be reported
REVENGE_MINUTES = 30      # "right after a loss" window
DAILY_TRADE_LIMIT = 3     # trades after this many in one day count as "late in a busy day"
OPEN_RUSH_MINUTES = 15    # first minutes after the 09:15 open

CAVEAT = ("This shows where your losses cluster. It does not prove you would have "
          "kept the money by skipping these trades.")
OVERLAP_NOTE = ("Habits overlap: one trade can count under more than one. Do not add "
                "the amounts together.")


def _ist(v: Any) -> datetime:
    return _dt(v).astimezone(IST)


def _has_times(trips: List[Dict[str, Any]]) -> bool:
    """False when the import only had dates (every time is midnight)."""
    return any((_ist(t["entry_at"]).hour, _ist(t["entry_at"]).minute) != (0, 0) for t in trips)


def _group(trips: List[Dict[str, Any]], rest: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(trips)
    net = round(sum(t["pnl"] for t in trips), 2)
    wins = sum(1 for t in trips if t["pnl"] > 0)
    return {
        "n": n, "net_pnl": net, "cost": round(max(0.0, -net), 2),
        "win_rate": round(wins / n, 3) if n else None,
        "avg_pnl": round(net / n, 2) if n else None,
        "avg_pnl_other_trades": (round(sum(t["pnl"] for t in rest) / len(rest), 2) if rest else None),
    }


def _pattern(pid: str, title: str, what: str, picked: List[Dict[str, Any]],
             all_trips: List[Dict[str, Any]], needs_times: bool = False,
             has_times: bool = True, kind: str = "habit", note: str = "") -> Dict[str, Any]:
    """kind "habit": a group chosen by WHEN/WHAT was traded, so it holds wins
    and losses and can be compared fairly with the trader's other trades.
    kind "loss_shape": a group made only of losing trades. It always nets
    negative, so it is reported as a share of all losses, never as a leak."""
    ids = {id(t) for t in picked}
    rest = [t for t in all_trips if id(t) not in ids]
    g = _group(picked, rest)
    gross_loss = -sum(t["pnl"] for t in all_trips if t["pnl"] < 0)
    if needs_times and not has_times:
        status = "needs_times"
    elif g["n"] == 0:
        status = "not_seen"
    elif g["n"] < PATTERN_FLOOR:
        status = "insufficient_data"
    elif kind == "loss_shape":
        status = "loss_shape"
    else:
        # A leak must lose money AND do worse per trade than the other trades.
        worse = g["avg_pnl_other_trades"] is None or g["avg_pnl"] < g["avg_pnl_other_trades"]
        status = "leak" if g["net_pnl"] < 0 and worse else "no_leak"
    return {"id": pid, "title": title, "what": what, "kind": kind, "status": status, **g,
            "share_of_all_losses": (round(g["cost"] / gross_loss, 3)
                                    if kind == "loss_shape" and gross_loss > 0 else None),
            "note": note,
            "examples": [{"symbol": t["symbol"], "exit_at": t["exit_at"], "pnl": t["pnl"]}
                         for t in sorted(picked, key=lambda t: t["pnl"])[:3]]}


def _revenge(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trips entered within REVENGE_MINUTES after one of the trader's losing exits."""
    loss_exits = sorted(_ist(t["exit_at"]) for t in trips if t["pnl"] < 0)
    out = []
    window = timedelta(minutes=REVENGE_MINUTES)
    for t in trips:
        entry = _ist(t["entry_at"])
        if any(x <= entry <= x + window and x.date() == entry.date()
               and x != _ist(t["exit_at"]) for x in loss_exits):
            out.append(t)
    return out


def _late_in_busy_day(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_day: Dict[Any, List[Dict[str, Any]]] = defaultdict(list)
    for t in trips:
        by_day[_ist(t["entry_at"]).date()].append(t)
    out = []
    for day_trips in by_day.values():
        day_trips.sort(key=lambda t: _ist(t["entry_at"]))
        out.extend(day_trips[DAILY_TRADE_LIMIT:])
    return out


def _losers_held_long(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    wins = [t["holding_days"] for t in trips if t["pnl"] > 0]
    if not wins:
        return []
    avg_win_hold = sum(wins) / len(wins)
    return [t for t in trips if t["pnl"] < 0 and t["holding_days"] > max(2 * avg_win_hold, 1.0)]


def _outsized_losses(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    wins = [t["pnl"] for t in trips if t["pnl"] > 0]
    if not wins:
        return []
    avg_win = sum(wins) / len(wins)
    return [t for t in trips if t["pnl"] < -2 * avg_win]


def _opening_rush(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for t in trips:
        e = _ist(t["entry_at"])
        minutes = e.hour * 60 + e.minute
        if 9 * 60 + 15 <= minutes < 9 * 60 + 15 + OPEN_RUSH_MINUTES:
            out.append(t)
    return out


def _worst_symbol(trips: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_sym: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in trips:
        by_sym[t["symbol"]].append(t)
    eligible = {s: ts for s, ts in by_sym.items() if len(ts) >= PATTERN_FLOOR}
    if len(by_sym) < 2 or not eligible:
        return []
    worst = min(eligible, key=lambda s: (sum(t["pnl"] for t in eligible[s]), s))
    return eligible[worst]


def build(trips: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the X-ray from closed round trips."""
    n = len(trips)
    base = {"n_trips": n, "min_trips": MIN_TRIPS, "pattern_floor": PATTERN_FLOOR,
            "caveat": CAVEAT, "overlap_note": OVERLAP_NOTE,
            "charges_note": "P&L is before brokerage, STT and other charges, so real results are lower."}
    if n < MIN_TRIPS:
        return {**base, "status": "insufficient_data", "patterns": [], "headline":
                f"Not enough closed trades yet ({n} of {MIN_TRIPS} needed) to call anything a habit."}

    times = _has_times(trips)
    worst_sym = _worst_symbol(trips)
    specs: List[tuple] = [
        ("revenge", "Trades right after a loss",
         f"Entered within {REVENGE_MINUTES} minutes of closing a losing trade, on the same day.",
         _revenge(trips) if times else [], True, "habit", ""),
        ("late_in_busy_day", f"Trades after your {DAILY_TRADE_LIMIT}rd of the day",
         f"Every trade you opened after already opening {DAILY_TRADE_LIMIT} that day.",
         _late_in_busy_day(trips) if times else [], True, "habit", ""),
        ("opening_rush", "Trades in the opening rush",
         f"Entered in the first {OPEN_RUSH_MINUTES} minutes after the 09:15 open.",
         _opening_rush(trips) if times else [], True, "habit", ""),
        ("worst_symbol", f"Your worst symbol{': ' + worst_sym[0]['symbol'] if worst_sym else ''}",
         "The symbol where your closed trades lost the most in total.",
         worst_sym, False, "habit",
         "Picked because it is your worst, so part of this is bad luck, not habit."),
        ("losers_held_long", "Losing trades you held on to",
         "Losing trades held more than twice as long as your average winning trade.",
         _losers_held_long(trips), False, "loss_shape", ""),
        ("outsized_losses", "Losses much bigger than your wins",
         "Single losses larger than twice your average win.",
         _outsized_losses(trips), False, "loss_shape", ""),
    ]
    patterns = [_pattern(pid, title, what, picked, trips, needs_times=nt, has_times=times,
                         kind=kind, note=note)
                for pid, title, what, picked, nt, kind, note in specs]
    order = {"leak": 0, "loss_shape": 1, "no_leak": 2, "insufficient_data": 3,
             "needs_times": 4, "not_seen": 5}
    patterns.sort(key=lambda p: (order[p["status"]], -p["cost"], p["id"]))

    leaks = [p for p in patterns if p["status"] == "leak"]
    net = round(sum(t["pnl"] for t in trips), 2)
    first = min(_ist(t["entry_at"]) for t in trips).date().isoformat()
    last = max(_ist(t["exit_at"]) for t in trips).date().isoformat()
    if leaks:
        top = leaks[0]
        headline = (f"{top['title']}: {top['n']} trades that together lost "
                    f"₹{top['cost']:,.0f}.")
    else:
        headline = "None of the habits we check is losing you money in this tradebook."
    return {**base, "status": "ok", "period": {"from": first, "to": last},
            "net_pnl": net, "has_intraday_times": times,
            "leaks_found": len(leaks), "biggest_leak": leaks[0]["id"] if leaks else None,
            "headline": headline, "patterns": patterns}
