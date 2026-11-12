"""Tradebook X-ray: honest sums, sample floors, fair leak rule, public routes."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.parakh import journal, sample, xray
from app.parakh.journal import IST

client = TestClient(app)


def _trip(day: int, minute: int, hold: int, pnl: float, symbol: str = "INFY", hold_days: float = 0.0):
    entry = datetime(2026, 9, 1, 9, 15, tzinfo=IST) + timedelta(days=day, minutes=minute)
    exit_ = entry + timedelta(minutes=hold, days=hold_days)
    return {"symbol": symbol, "direction": "LONG", "qty": 10, "entry_price": 100.0,
            "exit_price": 100.0 + pnl / 10, "entry_at": entry.isoformat(), "exit_at": exit_.isoformat(),
            "holding_days": round((exit_ - entry).total_seconds() / 86400, 2), "pnl": pnl,
            "return_pct": pnl / 10, "thesis_id": None}


def _by_id(x):
    return {p["id"]: p for p in x["patterns"]}


def test_needs_minimum_trades():
    x = xray.build([_trip(d, 60, 30, 100) for d in range(5)])
    assert x["status"] == "insufficient_data" and x["patterns"] == []


def test_revenge_trades_are_found_and_summed_exactly():
    trips = []
    for d in range(12):
        trips.append(_trip(d, 60, 30, -200))          # loss, exits 10:45
        trips.append(_trip(d, 100, 20, -300))         # entered 10 min after the loss
    for d in range(12, 20):
        trips.append(_trip(d, 60, 30, 400))           # calm winning days
    p = _by_id(xray.build(trips))["revenge"]
    assert p["status"] == "leak" and p["n"] == 12
    assert p["net_pnl"] == -3600 and p["cost"] == 3600
    assert p["avg_pnl"] < p["avg_pnl_other_trades"]


def test_losing_group_that_beats_the_rest_is_not_a_leak():
    # Opening trades lose a little; everything else loses far more.
    trips = [_trip(d, 5, 20, -10) for d in range(10)] + [_trip(d, 200, 20, -500) for d in range(15)]
    p = _by_id(xray.build(trips))["opening_rush"]
    assert p["n"] == 10 and p["net_pnl"] < 0 and p["status"] == "no_leak"


def test_small_groups_are_insufficient_not_leaks():
    trips = [_trip(d, 200, 20, 100) for d in range(25)] + [_trip(d, 5, 20, -900) for d in range(3)]
    assert _by_id(xray.build(trips))["opening_rush"]["status"] == "insufficient_data"


def test_loss_only_groups_are_never_called_leaks():
    trips = ([_trip(d, 200, 20, 100) for d in range(20)]
             + [_trip(d, 200, 20, -1000, hold_days=5) for d in range(20, 26)])
    by = _by_id(xray.build(trips))
    for pid in ("losers_held_long", "outsized_losses"):
        assert by[pid]["status"] == "loss_shape" and by[pid]["share_of_all_losses"] == 1.0


def test_date_only_imports_do_not_guess_intraday_habits():
    trips = []
    for d in range(25):
        t = _trip(d, 0, 0, -100, hold_days=1)
        t["entry_at"] = t["entry_at"].replace("T09:15", "T00:00")
        trips.append(t)
    by = _by_id(xray.build(trips))
    assert by["revenge"]["status"] == "needs_times" and by["revenge"]["n"] == 0


def test_never_claims_money_would_be_saved():
    x = xray.build(journal.round_trips(journal.parse_csv(sample.tradebook_csv())[0]))
    text = (x["headline"] + " ".join(p["title"] + p["what"] for p in x["patterns"])).lower()
    for bad in ("would have saved", "you should", "avoid", "buy ", "sell "):
        assert bad not in text
    assert "does not prove" in x["caveat"]


def test_sample_is_deterministic_and_shows_leaks():
    assert sample.tradebook_csv() == sample.tradebook_csv.__wrapped__()
    x = xray.build(journal.round_trips(journal.parse_csv(sample.tradebook_csv())[0]))
    assert x["status"] == "ok" and x["biggest_leak"] == "revenge" and x["leaks_found"] >= 2


def test_public_xray_sample_is_labelled_and_not_stored():
    r = client.post("/api/parakh/public/xray?sample=1")
    assert r.status_code == 200
    d = r.json()
    assert d["sample"] is True and d["stored"] is False and "invented" in d["sample_label"]
    assert d["xray"]["status"] == "ok"
    assert client.get("/api/parakh/journal").json()["trades"] == 0


def test_public_xray_upload_and_bad_file():
    r = client.post("/api/parakh/public/xray",
                    files={"file": ("t.csv", sample.tradebook_csv(), "text/csv")})
    assert r.status_code == 200 and r.json()["sample"] is False
    r = client.post("/api/parakh/public/xray", files={"file": ("t.csv", "a,b\n1,2\n", "text/csv")})
    assert r.status_code == 422


def test_sample_csv_download():
    r = client.get("/api/parakh/public/sample-tradebook.csv")
    assert r.status_code == 200 and r.text.startswith("symbol,isin,trade_date")


def test_journal_xray_for_logged_in_user():
    r = client.get("/api/parakh/journal/xray")
    assert r.status_code == 200 and r.json()["xray"]["status"] == "insufficient_data"


def test_public_check_saves_nothing_and_is_rate_limited():
    before = len(client.get("/api/parakh/theses").json()["theses"])
    r = client.post("/api/parakh/public/check", json={"idea": "HDFC Bank will rally in 2 weeks", "save": True})
    assert r.status_code == 200
    d = r.json()
    assert d["trial"] is True and "thesis_id" not in d and "_label" not in d
    assert len(client.get("/api/parakh/theses").json()["theses"]) == before
    codes = [client.post("/api/parakh/public/check", json={"idea": "TCS will fall"}).status_code
             for _ in range(6)]
    assert 429 in codes
