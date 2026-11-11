"""Parakh product tests — fully offline (market data overridden)."""
from __future__ import annotations

import hashlib
import json
import math
import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import database as db
from app.config import get_settings
from app.core import state_store
from app.parakh import (calibration, journal, market, options, share, store, strategy_backtest,
                        thesis_check, theses)


def _bars(n=520, seed=1, drift=0.0004, vol=0.012, start=1000.0, end=None):
    r = random.Random(seed)
    d = (end or date.today()) - timedelta(days=int(n * 1.45))
    out, p = [], start
    while len(out) < n:
        if d.weekday() < 5:
            c = p * math.exp(drift + vol * r.gauss(0, 1))
            out.append({"date": d.isoformat(), "open": round(p, 2), "high": round(max(p, c) * 1.004, 2),
                        "low": round(min(p, c) * 0.996, 2), "close": round(c, 2), "volume": 1e6})
            p = c
        d += timedelta(days=1)
    return out


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    state_store.reset_for_tests()
    for sym, seed in (("RELIANCE", 1), ("NIFTY", 2), ("HDFCBANK", 3), ("TCS", 4), ("BANKNIFTY", 5)):
        market.set_override(sym, _bars(seed=seed))
    yield
    for sym in ("RELIANCE", "NIFTY", "HDFCBANK", "TCS", "BANKNIFTY"):
        market.set_override(sym, None)


@pytest.fixture
def client():
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    from app.main import app
    return TestClient(app)


def H(user="alice"):
    return {"X-Parakh-Dev-User": user}


# ---------------------------------------------------------------- parsing ----

def test_rule_parser_extracts_symbol_direction_horizon_confidence():
    idea = thesis_check._rule_parse("Bank Nifty will crash after RBI policy in 2 weeks, 80% sure")
    assert idea.symbol == "BANKNIFTY" and idea.direction == "SHORT"
    assert idea.horizon_days == 10 and idea.user_confidence == 0.8
    idea = thesis_check._rule_parse("buy hdfc bank target 1900 stop 1650 for 3 days")
    assert idea.symbol == "HDFCBANK" and idea.target_price == 1900 and idea.stop_price == 1650
    assert idea.horizon_days == 3


def test_chance_odds_are_deterministic_and_sum_to_one():
    a = thesis_check.chance_odds(100, 105, 97, 0.015, 10, "LONG")
    b = thesis_check.chance_odds(100, 105, 97, 0.015, 10, "LONG")
    assert a == b
    assert abs(sum(a.values()) - 1) < 0.002  # each value rounded to 3dp
    # a closer stop is hit more often
    tight = thesis_check.chance_odds(100, 105, 99.5, 0.015, 10, "LONG")
    assert tight["p_stop"] > a["p_stop"]


def test_report_has_checks_and_fixes_wrong_side_stop():
    idea = thesis_check.ParsedIdea(symbol="RELIANCE", direction="LONG", horizon_days=10,
                                   stop_price=999999.0)
    r = thesis_check.build_report(idea)
    assert r["stop_price"] < r["entry_price"] < r["target_price"]
    assert r["fixes"], "a stop above price for a long must be flagged"
    assert {c["id"] for c in r["checks"]} >= {"reward_risk", "stop_noise", "confidence_gap"}
    assert 0 <= r["checklist_score"] <= 100
    assert "not investment advice" in r["disclaimer"].lower()


# ---------------------------------------------------------------- API/auth ---

def test_check_saves_thesis_and_users_are_isolated(client):
    r = client.post("/api/parakh/check", json={"idea": "Reliance will rally in 2 weeks, 70% sure"}, headers=H("alice"))
    assert r.status_code == 200, r.text
    tid = r.json()["thesis_id"]
    assert client.get(f"/api/parakh/theses/{tid}", headers=H("alice")).status_code == 200
    assert client.get(f"/api/parakh/theses/{tid}", headers=H("bob")).status_code == 404
    assert all(t["user_id"] == "bob" for t in client.get("/api/parakh/theses", headers=H("bob")).json()["theses"])


def test_production_without_auth_config_refuses(client, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        r = client.get("/api/parakh/theses")
        assert r.status_code == 503
        assert client.post("/api/kill-switch", json={"action": "trip"}).status_code == 503
    finally:
        monkeypatch.setenv("ENVIRONMENT", "test")
        get_settings.cache_clear()


def test_hs256_supabase_token_is_verified(client, monkeypatch):
    import jwt
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "s" * 40)
    get_settings.cache_clear()
    try:
        good = jwt.encode({"sub": "u-123", "email": "a@b.in", "aud": "authenticated"}, "s" * 40, algorithm="HS256")
        bad = jwt.encode({"sub": "u-123", "aud": "authenticated"}, "x" * 40, algorithm="HS256")
        assert client.get("/api/parakh/me", headers={"Authorization": f"Bearer {good}"}).json()["user"]["id"] == "u-123"
        assert client.get("/api/parakh/theses", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
        assert client.get("/api/parakh/theses").status_code == 401
    finally:
        monkeypatch.delenv("SUPABASE_JWT_SECRET")
        get_settings.cache_clear()


# --------------------------------------------------------------- resolution --

def test_thesis_resolves_hit_and_gets_autopsy(client):
    full = _bars(seed=9, drift=0.0)
    cut = len(full) - 12
    market.set_override("TCS", full[:cut])
    rep = client.post("/api/parakh/check", json={"symbol": "TCS", "direction": "LONG", "horizon_days": 10,
                                                 "user_confidence": 0.9}, headers=H("carol")).json()
    entry = rep["entry_price"]
    # Next bars: strong rally through the target
    fut, p = [], entry
    d0 = date.fromisoformat(full[cut - 1]["date"])
    for k in range(1, 12):
        p *= 1.03
        fut.append({"date": (d0 + timedelta(days=k)).isoformat(), "open": p / 1.03, "high": p * 1.01,
                    "low": p / 1.031, "close": p, "volume": 1e6})
    market.set_override("TCS", full[:cut] + fut)
    row = client.get(f"/api/parakh/theses/{rep['thesis_id']}", headers=H("carol")).json()
    assert row["status"] == "hit"
    assert row["outcome_return_pct"] > 0
    assert row["autopsy"]["outcome"] == "win"


def test_calibration_withholds_below_floor_then_scores():
    few = calibration.compute([(0.8, 1)] * 3)
    assert few["status"] == "insufficient" and "score" not in few
    many = calibration.compute([(0.8, 1)] * 6 + [(0.8, 0)] * 6)
    assert many["status"] == "ok" and many["overconfidence_gap"] == pytest.approx(0.3)
    assert "Overconfident" in many["verdict"]


# ------------------------------------------------------------------ journal --

ZERODHA = """symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time
RELIANCE,INE002A01018,2026-09-01,NSE,EQ,EQ,buy,false,10,1300.5,111,9001,2026-09-01T09:20:11
RELIANCE,INE002A01018,2026-09-05,NSE,EQ,EQ,sell,false,4,1260,112,9002,2026-09-05T14:10:00
RELIANCE,INE002A01018,2026-09-08,NSE,EQ,EQ,sell,false,6,1350,113,9003,2026-09-08T14:10:00
TCS,INE467B01029,2026-09-02,NSE,EQ,EQ,sell,false,5,4100,114,9004,2026-09-02T10:00:00
TCS,INE467B01029,2026-09-03,NSE,EQ,EQ,buy,false,5,4050,115,9005,2026-09-03T10:00:00
"""


def test_zerodha_csv_fifo_round_trips_and_shorts():
    trades, fmt = journal.parse_csv(ZERODHA)
    assert fmt == "zerodha_tradebook" and len(trades) == 5
    trips = journal.round_trips(trades)
    rel = [t for t in trips if t["symbol"] == "RELIANCE"]
    assert [t["qty"] for t in rel] == [4, 6]
    assert rel[0]["pnl"] == pytest.approx((1260 - 1300.5) * 4)
    tcs = [t for t in trips if t["symbol"] == "TCS"][0]
    assert tcs["direction"] == "SHORT" and tcs["pnl"] == pytest.approx(250)


def test_journal_import_dedupes(client):
    r1 = client.post("/api/parakh/journal/import", content=ZERODHA, headers=H("dave")).json()
    r2 = client.post("/api/parakh/journal/import", content=ZERODHA, headers=H("dave")).json()
    assert r1["added"] == 5 and r2["added"] == 0 and r2["skipped_duplicates"] == 5
    j = client.get("/api/parakh/journal", headers=H("dave")).json()
    assert j["stats"]["n"] == 3
    assert client.get("/api/parakh/journal", headers=H("erin")).json()["trades"] == 0


def test_bad_csv_gives_readable_error(client):
    r = client.post("/api/parakh/journal/import", content="a,b\n1,2\n", headers=H())
    assert r.status_code == 422 and "columns" in r.json()["detail"]


# ------------------------------------------------------------------ options --

def test_put_call_parity_and_iv_roundtrip():
    s, k, t, v = 24000, 24000, 30 / 365, 0.15
    c, p = options.bs_price(s, k, t, v, "CE"), options.bs_price(s, k, t, v, "PE")
    assert c - p == pytest.approx(s - k * math.exp(-options.RISK_FREE * t), rel=1e-6)
    assert options.implied_vol(c, s, k, t, "CE") == pytest.approx(0.15, abs=1e-3)


def test_bear_call_spread_limits_and_naked_short_warning():
    r = options.analyse(24000, 7, [{"kind": "CE", "side": "SELL", "strike": 24300, "premium": 80},
                                   {"kind": "CE", "side": "BUY", "strike": 24500, "premium": 30}], lot_size=75)
    assert r["max_profit"] == pytest.approx(50 * 75)
    assert r["max_loss"] == pytest.approx(-150 * 75)
    assert r["breakevens"] and abs(r["breakevens"][0] - 24350) < 2
    naked = options.analyse(24000, 7, [{"kind": "CE", "side": "SELL", "strike": 24300, "premium": 80}], lot_size=75)
    assert naked["max_loss"] is None and any("Unlimited" in w for w in naked["warnings"])


# ----------------------------------------------------------------- backtest --

def test_backtest_fills_next_open_and_warns():
    bars = market.history("RELIANCE", 800)[0]
    r = strategy_backtest.run("RELIANCE", "sma_cross_up", {"fast": 10, "slow": 30},
                              {"stop_pct": 5, "target_pct": 8, "max_hold_days": 20})
    by_date = {b["date"]: b for b in bars}
    for t in r["full"]["trade_list"]:
        assert t["entry"] == pytest.approx(by_date[t["entry_date"]]["open"], rel=1e-6)
    assert any("Survivorship" in w for w in r["warnings"])
    assert "out_of_sample" in r and len(r["sensitivity"]) == 2


# -------------------------------------------------------------------- share --

def test_public_seal_is_verifiable(client):
    rep = client.post("/api/parakh/check", json={"idea": "HDFC Bank will rally in 1 week"}, headers=H("fay")).json()
    pub = client.post(f"/api/parakh/theses/{rep['thesis_id']}/publish", headers=H("fay")).json()
    view = client.get(f"/api/parakh/public/thesis/{pub['slug']}").json()
    blob = json.dumps(view["terms"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(blob.encode()).hexdigest() == view["seal"] == pub["seal"]
    assert view["seal_valid"] is True
    # another user can't publish it
    assert client.post(f"/api/parakh/theses/{rep['thesis_id']}/publish", headers=H("gus")).status_code == 404


def test_cron_jobs_need_secret(client):
    assert client.post("/api/parakh/jobs/hype-alerts").status_code == 403


def test_copilot_fallback_without_key(client):
    r = client.post("/api/parakh/copilot", json={"question": "what is my calibration?"}, headers=H()).json()
    assert r["mode"] == "rules" and r["answer"]
