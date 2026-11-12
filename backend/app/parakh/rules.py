"""
Parakh — My rules.

The trader writes their own rules once. Parakh then does two things:

  * ``check_idea``  — before a trade: is this idea inside the trader's rules?
  * ``discipline``  — after trades: on how many trading days were the rules kept?

Integrity rules this module follows:
  * The rules are the trader's own. Parakh never suggests a value as "correct".
  * Every figure is a plain count or sum over the trader's own trades.
  * The discipline score is withheld below ``MIN_DAYS`` trading days.
  * It reports what rule-breaking trades netted. It never claims the money
    would have been saved by following the rule.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.parakh.xray import _has_times, _ist

MIN_DAYS = 5              # below this many trading days no discipline score is shown

IDEA_RULES = ("min_reward_risk", "with_trend_only", "min_checklist_score")
TRADE_RULES = ("max_trades_per_day", "stop_after_losses", "cool_off_minutes")
ALL_RULES = IDEA_RULES + TRADE_RULES

CAVEAT = ("This counts where your own rules were broken. It does not prove you would "
          "have kept the money by following them.")


def clean(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Keep only known rules that are switched on (not None / False)."""
    out: Dict[str, Any] = {}
    for k in ALL_RULES:
        v = (raw or {}).get(k)
        if v is None or v is False:
            continue
        out[k] = v
    return out


def _title(rule: str, v: Any) -> str:
    return {
        "min_reward_risk": f"Reward must be at least {v:g}× the risk",
        "with_trend_only": "No trades against the trend",
        "min_checklist_score": f"Checklist score must be {v} or more",
        "max_trades_per_day": f"At most {v} trades a day",
        "stop_after_losses": f"Stop for the day after {v} losing trade{'s' if v != 1 else ''}",
        "cool_off_minutes": f"Wait {v} minutes after a loss",
    }[rule]


# ---------------------------------------------------------------- ideas ----

def check_idea(rules: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    """Compare one idea report with the trader's idea rules."""
    rules = clean(rules)
    results: List[Dict[str, Any]] = []
    if "min_reward_risk" in rules:
        need, got = float(rules["min_reward_risk"]), float(report.get("reward_risk") or 0)
        results.append({"id": "min_reward_risk", "title": _title("min_reward_risk", need),
                        "kept": got >= need, "detail": f"This idea is {got:.1f} : 1."})
    if "with_trend_only" in rules:
        trend = next((c for c in report.get("checks", []) if c["id"] == "trend"), None)
        if trend is not None:
            results.append({"id": "with_trend_only", "title": _title("with_trend_only", True),
                            "kept": trend["status"] != "fail",
                            "detail": ("This idea fights the trend." if trend["status"] == "fail"
                                       else "This idea does not fight the trend.")})
    if "min_checklist_score" in rules:
        need, got = int(rules["min_checklist_score"]), int(report.get("checklist_score") or 0)
        results.append({"id": "min_checklist_score", "title": _title("min_checklist_score", need),
                        "kept": got >= need, "detail": f"This idea scores {got}."})
    broken = [r for r in results if not r["kept"]]
    return {"n_rules": len(results), "n_broken": len(broken), "results": results,
            "verdict": ("You have no idea rules set." if not results else
                        "Inside your rules." if not broken else
                        f"Breaks {len(broken)} of your {len(results)} rule{'s' if len(results) != 1 else ''}.")}


# --------------------------------------------------------------- trades ----

def discipline(rules: Dict[str, Any], trips: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How often were the trade rules kept, day by day?"""
    rules = {k: v for k, v in clean(rules).items() if k in TRADE_RULES}
    if not rules:
        return {"status": "no_rules", "rules": [],
                "message": "Set at least one trading-day rule to get a discipline score."}
    by_day: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in sorted(trips, key=lambda t: _ist(t["entry_at"])):
        by_day[_ist(t["entry_at"]).date().isoformat()].append(t)
    has_times = _has_times(trips) if trips else False

    broke: Dict[str, List[Dict[str, Any]]] = {k: [] for k in rules}
    days_broken: Dict[str, set] = {k: set() for k in rules}
    day_rows: List[Dict[str, Any]] = []
    for day, ts in sorted(by_day.items()):
        today: set = set()
        for i, t in enumerate(ts):
            entry = _ist(t["entry_at"])
            earlier_losses = [p for p in ts[:i] if p["pnl"] < 0 and _ist(p["exit_at"]) <= entry]
            hit: List[str] = []
            if "max_trades_per_day" in rules and i >= int(rules["max_trades_per_day"]):
                hit.append("max_trades_per_day")
            if has_times and "stop_after_losses" in rules and len(earlier_losses) >= int(rules["stop_after_losses"]):
                hit.append("stop_after_losses")
            if has_times and "cool_off_minutes" in rules:
                gap = timedelta(minutes=int(rules["cool_off_minutes"]))
                if any(entry - _ist(p["exit_at"]) < gap for p in earlier_losses):
                    hit.append("cool_off_minutes")
            for k in hit:
                broke[k].append(t)
                days_broken[k].add(day)
                today.add(k)
        day_rows.append({"date": day, "trades": len(ts), "net_pnl": round(sum(t["pnl"] for t in ts), 2),
                         "broken": sorted(today)})

    n_days = len(day_rows)
    out_rules = []
    for k, v in rules.items():
        needs_times = k != "max_trades_per_day" and not has_times
        net = round(sum(t["pnl"] for t in broke[k]), 2)
        out_rules.append({
            "id": k, "title": _title(k, v),
            "status": "needs_times" if needs_times else "broken" if broke[k] else "kept",
            "trades": len(broke[k]), "days_broken": len(days_broken[k]),
            "net_pnl": None if needs_times else net,
        })
    out: Dict[str, Any] = {"rules": out_rules, "trading_days": n_days, "min_days": MIN_DAYS,
                           "recent_days": day_rows[-10:][::-1], "caveat": CAVEAT}
    if n_days < MIN_DAYS:
        out.update(status="insufficient_data", score=None,
                   message=f"Not enough data yet ({n_days} of {MIN_DAYS} trading days needed).")
        return out
    kept = sum(1 for d in day_rows if not d["broken"])
    out.update(status="ok", days_kept=kept, score=round(100 * kept / n_days),
               headline=f"You kept your rules on {kept} of {n_days} trading days.")
    return out
