"""My rules, discipline score, checker realism cap, export / delete my data."""
from datetime import datetime, timedelta

from app.parakh import rules, thesis_check
from app.parakh.journal import IST
from tests.test_parakh import H, client, offline  # noqa: F401  (fixtures)

CSV = ("symbol,trade_date,trade_type,quantity,price,order_execution_time,trade_id\n"
       "RELIANCE,2026-09-01,buy,10,100,2026-09-01T10:00:00,t1\n"
       "RELIANCE,2026-09-01,sell,10,110,2026-09-01T11:00:00,t2\n")


def _trip(day: int, minute: int, hold: int, pnl: float):
    entry = datetime(2026, 9, 1, 9, 15, tzinfo=IST) + timedelta(days=day, minutes=minute)
    exit_ = entry + timedelta(minutes=hold)
    return {"symbol": "INFY", "direction": "LONG", "qty": 10, "entry_price": 100.0,
            "exit_price": 100.0 + pnl / 10, "entry_at": entry.isoformat(),
            "exit_at": exit_.isoformat(), "pnl": pnl}


def test_discipline_counts_days_and_sums_exactly():
    trips = []
    for d in range(6):                                   # calm days: 1 trade each
        trips.append(_trip(d, 60, 30, 100))
    for d in range(6, 10):                               # bad days: loss, then a trade 5 minutes later
        trips.append(_trip(d, 60, 30, -200))
        trips.append(_trip(d, 95, 20, -300))
    out = rules.discipline({"cool_off_minutes": 30, "max_trades_per_day": 1}, trips)
    assert out["status"] == "ok" and out["trading_days"] == 10
    assert out["days_kept"] == 6 and out["score"] == 60
    by = {r["id"]: r for r in out["rules"]}
    assert by["cool_off_minutes"]["trades"] == 4 and by["cool_off_minutes"]["net_pnl"] == -1200
    assert by["max_trades_per_day"]["days_broken"] == 4
    assert "does not prove" in out["caveat"]


def test_discipline_withholds_score_below_floor_and_without_rules():
    trips = [_trip(d, 60, 30, 100) for d in range(3)]
    out = rules.discipline({"max_trades_per_day": 2}, trips)
    assert out["status"] == "insufficient_data" and out["score"] is None
    assert rules.discipline({"min_reward_risk": 2}, trips)["status"] == "no_rules"


def test_stop_after_losses_only_counts_closed_losses():
    day = [_trip(0, 10, 10, -100), _trip(0, 30, 10, -100), _trip(0, 60, 10, 50)]
    trips = day + [_trip(d, 60, 30, 100) for d in range(1, 6)]
    by = {r["id"]: r for r in rules.discipline({"stop_after_losses": 2}, trips)["rules"]}
    assert by["stop_after_losses"]["trades"] == 1 and by["stop_after_losses"]["net_pnl"] == 50


def test_idea_rules_are_checked_against_the_report():
    report = {"reward_risk": 1.5, "checklist_score": 80,
              "checks": [{"id": "trend", "status": "fail"}]}
    out = rules.check_idea({"min_reward_risk": 2, "with_trend_only": True, "min_checklist_score": 60}, report)
    assert out["n_rules"] == 3 and out["n_broken"] == 2
    assert {r["id"] for r in out["results"] if not r["kept"]} == {"min_reward_risk", "with_trend_only"}
    assert rules.check_idea({}, report)["n_rules"] == 0


def test_unrealistic_target_caps_the_score():
    idea = thesis_check.ParsedIdea(symbol="RELIANCE", direction="LONG", horizon_days=10)
    entry = thesis_check.build_report(idea)["entry_price"]
    r = thesis_check.build_report(thesis_check.ParsedIdea(
        symbol="RELIANCE", direction="LONG", horizon_days=10, target_price=entry * 2.3))
    by = {c["id"]: c for c in r["checks"]}
    assert by["target_realism"]["status"] == "fail"
    assert by["reward_risk"]["status"] != "pass"
    assert r["checklist_score"] <= thesis_check.UNREALISTIC_CAP and r["score_note"]


def test_rules_api_roundtrip_and_check_carries_rule_results(client):
    r = client.put("/api/parakh/rules", json={"min_reward_risk": 5, "max_trades_per_day": 3}, headers=H("alice"))
    assert r.status_code == 200 and r.json()["rules"] == {"min_reward_risk": 5, "max_trades_per_day": 3}
    assert client.get("/api/parakh/rules", headers=H("bob")).json()["rules"] == {}
    assert client.put("/api/parakh/rules", json={"max_trades_per_day": 0}, headers=H("alice")).status_code == 422
    rep = client.post("/api/parakh/check", json={"idea": "Reliance will rally in 2 weeks, 70% sure"},
                      headers=H("alice")).json()
    assert rep["rules"]["n_rules"] == 1 and rep["rules"]["n_broken"] == 1
    assert client.get("/api/parakh/rules/discipline", headers=H("alice")).json()["status"] == "insufficient_data"


def test_export_and_delete_my_data_only_touch_the_caller(client):
    for u in ("zed", "yan"):
        client.post("/api/parakh/check", json={"idea": "Reliance will rally in 2 weeks"}, headers=H(u))
        client.post("/api/parakh/journal/import", content=CSV, headers={**H(u), "Content-Type": "text/csv"})
        client.put("/api/parakh/rules", json={"max_trades_per_day": 3}, headers=H(u))
    exp = client.get("/api/parakh/account/export", headers=H("zed")).json()
    assert len(exp["ideas"]) == 1 and len(exp["trades"]) == 2 and len(exp["rules"]) == 1
    assert "access_token_enc" not in str(exp)
    assert client.delete("/api/parakh/account/data", headers=H("zed")).status_code == 400
    gone = client.delete("/api/parakh/account/data?confirm=DELETE", headers=H("zed")).json()["deleted"]
    assert gone["ideas"] == 1 and gone["trades"] == 2 and gone["rules"] == 1
    assert client.get("/api/parakh/theses", headers=H("zed")).json()["theses"] == []
    assert client.get("/api/parakh/rules", headers=H("zed")).json()["rules"] == {}
    assert len(client.get("/api/parakh/theses", headers=H("yan")).json()["theses"]) == 1
    assert client.get("/api/parakh/journal", headers=H("yan")).json()["trades"] == 2
