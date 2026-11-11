"""
Parakh — Feature 5: Claude copilot with tools over the user's own data.

Claude can look up quotes, check an idea, read the user's open theses,
journal stats, calibration and watchlist hype. All answers stay inside the
analysis-not-advice guardrails in llm.SYSTEM_GUARDRAILS. Without an API key
a small rule-based responder answers the common questions.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.parakh import (calibration, hype_radar, journal, llm, market, options, store,
                        thesis_check, theses, universe)

TOOLS: List[Dict[str, Any]] = [
    {"name": "get_quote", "description": "Latest daily price and change for an NSE symbol or index (NIFTY, BANKNIFTY).",
     "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "check_idea", "description": "Run Parakh's pre-trade check on a trade idea written in plain English. Does not save it.",
     "input_schema": {"type": "object", "properties": {"idea": {"type": "string"}}, "required": ["idea"]}},
    {"name": "my_theses", "description": "The user's saved trade ideas with their status (open/hit/miss/expired) and autopsies.",
     "input_schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["open", "hit", "miss", "expired", "all"]}}}},
    {"name": "my_journal", "description": "Statistics from the user's imported trades: win rate, average win/loss, holding times, worst trades, behaviour insights.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "my_calibration", "description": "How well the user's stated confidence matches their actual hit rate.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "watchlist_hype", "description": "Reddit attention vs price divergence for the user's watchlist.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "search_symbol", "description": "Find NSE symbols by company name.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]


def _executor(user_id: str):
    def run(name: str, args: Dict[str, Any]) -> str:
        if name == "get_quote":
            return json.dumps(market.quote(args["symbol"]))
        if name == "check_idea":
            idea, mode = thesis_check.parse_idea(args["idea"])
            if not idea:
                return "Could not identify a symbol in that idea."
            r = thesis_check.build_report(idea)
            return json.dumps({k: r[k] for k in ("symbol", "direction", "entry_price", "target_price",
                                                  "stop_price", "checks", "checklist_score", "chance_odds",
                                                  "analogues", "what_proves_you_wrong", "data_mode")}, default=str)
        if name == "my_theses":
            st = args.get("status")
            rows = store.list_theses(user_id, None if st in (None, "all") else st, limit=20)
            return json.dumps([{"symbol": r.symbol, "direction": r.direction, "status": r.status,
                                "confidence": r.user_confidence, "return_pct": r.outcome_return_pct,
                                "autopsy": json.loads(r.autopsy).get("failure_modes") if r.autopsy else None}
                               for r in rows], default=str)
        if name == "my_journal":
            trips = journal.round_trips(store.list_trades(user_id))
            return json.dumps(journal.stats(trips), default=str)
        if name == "my_calibration":
            return json.dumps(theses.user_calibration(user_id), default=str)
        if name == "watchlist_hype":
            return json.dumps(hype_radar.scan(store.watchlist(user_id) or ["NIFTY"])[:10], default=str)
        if name == "search_symbol":
            return json.dumps(universe.search(args.get("query", "")))
        return f"Unknown tool {name}"
    return run


def _fallback(user_id: str, question: str) -> Dict[str, Any]:
    q = question.lower()
    if any(w in q for w in ("calibrat", "confidence", "overconfident")):
        c = theses.user_calibration(user_id)
        return {"answer": c.get("verdict") or c.get("message"), "mode": "rules"}
    if any(w in q for w in ("journal", "my trades", "win rate", "losing")):
        s = journal.stats(journal.round_trips(store.list_trades(user_id)))
        if not s.get("n"):
            return {"answer": "No trades imported yet. Upload your Zerodha tradebook CSV in Journal.", "mode": "rules"}
        ins = " ".join(s["insights"]) or "No strong behaviour pattern yet."
        return {"answer": f"{s['n']} round trips, win rate {s['win_rate'] * 100:.0f}%, net ₹{s['net_pnl']:,.0f}. {ins}",
                "mode": "rules"}
    idea, _ = thesis_check.parse_idea(question)
    if idea and any(w in q for w in ("will", "think", "rally", "fall", "buy", "sell", "long", "short")):
        r = thesis_check.build_report(idea)
        fails = [c["title"] for c in r["checks"] if c["status"] == "fail"]
        return {"answer": (f"{r['name']} {r['direction'].lower()} idea: checklist {r['checklist_score']}/100. "
                           f"Pure-chance odds of target before stop: {r['chance_odds']['p_target'] * 100:.0f}%. "
                           + (f"Red flags: {', '.join(fails)}. " if fails else "")
                           + "Open 'Check a trade' for the full report."), "mode": "rules"}
    return {"answer": ("I can check a trade idea ('Will HDFC Bank rally in 2 weeks?'), explain your journal "
                       "stats, or your calibration. Add ANTHROPIC_API_KEY on the server for full conversations."),
            "mode": "rules"}


def ask(user_id: str, question: str, history: List[Dict[str, str]] | None = None) -> Dict[str, Any]:
    question = (question or "").strip()[:2000]
    if not question:
        return {"answer": "Ask me about a trade idea, your journal or your calibration.", "mode": "rules"}
    if llm.available():
        msgs: List[Dict[str, Any]] = []
        for h in (history or [])[-8:]:
            if h.get("role") in ("user", "assistant") and h.get("content"):
                msgs.append({"role": h["role"], "content": str(h["content"])[:4000]})
        if msgs and msgs[0]["role"] != "user":
            msgs = msgs[1:]
        msgs.append({"role": "user", "content": question})
        out = llm.run_tools(msgs, TOOLS, _executor(user_id))
        if out and out.get("answer"):
            return {**out, "mode": "claude"}
    return _fallback(user_id, question)
