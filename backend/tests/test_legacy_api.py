"""Smoke tests for the endpoints split out of main.py into app/api/*."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.parametrize("path", [
    "/health", "/", "/api/feeds/status", "/api/snapshot", "/api/history",
    "/api/kill-switch", "/api/predictions/history", "/api/backtest?periods=60",
    "/api/portfolio", "/api/trades",
])
def test_get_endpoints_respond(path):
    assert client.get(path).status_code == 200


def test_predictions_history_not_shadowed_by_id_route():
    body = client.get("/api/predictions/history").json()
    assert "predictions" in body and "backend" in body


def test_optimizer_validates_input():
    r = client.post("/api/quantum/optimize",
                    json={"symbols": [], "expected_returns": [], "cov_matrix": []})
    assert r.status_code == 422
    ok = client.post("/api/quantum/optimize", json={
        "symbols": ["A", "B"], "expected_returns": [0.1, 0.2],
        "cov_matrix": [[0.04, 0.01], [0.01, 0.09]]})
    assert ok.status_code == 200


def test_rebalance_and_risk_report():
    r = client.post("/api/rebalance", json={
        "holdings": {"NVDA": 10}, "target_weights": {"NVDA": 0.5, "AAPL": 0.5}})
    assert r.status_code == 200
    assert client.post("/api/risk/report",
                       json={"returns": [0.01, -0.02, 0.03]}).status_code == 200


def test_trade_rejects_bad_orders():
    assert client.post("/api/trade", json={"symbol": "AAPL", "qty": 0}).status_code == 422
    assert client.post("/api/trade", json={
        "symbol": "AAPL", "qty": 1, "order_type": "limit"}).status_code == 422


def test_option_lots_flags_unverified_sizes():
    body = client.get("/api/parakh/options/lots").json()
    assert body["lots"]["NIFTY"] == 65 and body["unverified"] == ["SENSEX"]
