"""
QuantPulse AI — Indian Stock Market API client tests.

Run:  python -m pytest tests/test_indian_stock_api.py -v

All HTTP is mocked (no network). Covers: symbol normalisation, base-URL
config, res=num on every quote call, the three public methods, and
timeout / network-failure degradation.
"""
from __future__ import annotations

import httpx
import pytest

from app.services import indian_stock_api as isa


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _no_cache():
    isa.clear_caches()
    yield
    isa.clear_caches()


# ---------------------------------------------------------------------------
# Symbol normalisation + config
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_bare_ticker_gets_ns(self):
        assert isa.normalize_symbol("RELIANCE") == "RELIANCE.NS"

    def test_lowercase_normalised(self):
        assert isa.normalize_symbol("infy") == "INFY.NS"

    def test_ns_preserved(self):
        assert isa.normalize_symbol("TCS.NS") == "TCS.NS"

    def test_bo_preserved(self):
        assert isa.normalize_symbol("RELIANCE.BO") == "RELIANCE.BO"


class TestBaseUrl:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("INDIAN_STOCK_API_URL", raising=False)
        assert isa.base_url() == "http://localhost:5000"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("INDIAN_STOCK_API_URL", "http://api:5000/")
        assert isa.base_url() == "http://api:5000"


# ---------------------------------------------------------------------------
# Public methods (mocked httpx)
# ---------------------------------------------------------------------------

class TestGetStockData:
    def test_calls_stock_with_res_num(self, monkeypatch):
        seen = {}

        def fake_get(url, params=None, **kw):
            seen["url"] = url
            seen["params"] = params
            return _FakeResponse({"symbol": "RELIANCE.NS", "price": 2980.5})

        monkeypatch.setattr(httpx, "get", fake_get)
        out = isa.get_stock_data("RELIANCE")
        assert out == {"symbol": "RELIANCE.NS", "price": 2980.5}
        assert seen["url"].endswith("/stock")
        assert seen["params"]["symbol"] == "RELIANCE.NS"
        assert seen["params"]["res"] == "num"  # raw numbers, not ₹ strings

    def test_timeout_returns_none(self, monkeypatch):
        def boom(url, params=None, **kw):
            raise httpx.ConnectTimeout("slow upstream")

        monkeypatch.setattr(httpx, "get", boom)
        assert isa.get_stock_data("RELIANCE") is None

    def test_network_failure_returns_none(self, monkeypatch):
        def boom(url, params=None, **kw):
            raise httpx.ConnectError("no route")

        monkeypatch.setattr(httpx, "get", boom)
        assert isa.get_stock_data("INFY") is None

    def test_non_200_returns_none(self, monkeypatch):
        monkeypatch.setattr(httpx, "get",
                            lambda url, params=None, **kw: _FakeResponse({}, 500))
        assert isa.get_stock_data("TCS") is None


class TestBatch:
    def test_calls_list_with_res_num(self, monkeypatch):
        seen = {}

        def fake_get(url, params=None, **kw):
            seen["url"] = url
            seen["params"] = params
            return _FakeResponse([{"symbol": "RELIANCE.NS", "price": 1.0},
                                  {"symbol": "INFY.NS", "price": 2.0}])

        monkeypatch.setattr(httpx, "get", fake_get)
        out = isa.get_batch_stocks(["RELIANCE", "INFY.BO"])
        assert len(out) == 2
        assert seen["url"].endswith("/stock/list")
        assert seen["params"]["res"] == "num"
        assert "RELIANCE.NS" in seen["params"]["symbols"]
        assert "INFY.BO" in seen["params"]["symbols"]

    def test_empty_input_no_request(self, monkeypatch):
        def boom(url, params=None, **kw):  # pragma: no cover
            raise AssertionError("should not be called")

        monkeypatch.setattr(httpx, "get", boom)
        assert isa.get_batch_stocks([]) == []


class TestSearch:
    def test_calls_search(self, monkeypatch):
        seen = {}

        def fake_get(url, params=None, **kw):
            seen["url"] = url
            seen["params"] = params
            return _FakeResponse([{"symbol": "RELIANCE.NS"}])

        monkeypatch.setattr(httpx, "get", fake_get)
        out = isa.search_stocks("reliance")
        assert out == [{"symbol": "RELIANCE.NS"}]
        assert seen["url"].endswith("/search")
        assert seen["params"]["q"] == "reliance"

    def test_blank_query_no_request(self, monkeypatch):
        def boom(url, params=None, **kw):  # pragma: no cover
            raise AssertionError("should not be called")

        monkeypatch.setattr(httpx, "get", boom)
        assert isa.search_stocks("   ") == []


# ---------------------------------------------------------------------------
# Example usage (also serves as a smoke demo against mocks)
# ---------------------------------------------------------------------------

def test_example_usage(monkeypatch):
    """Quick example: fetch one quote + a batch + a search."""
    def fake_get(url, params=None, **kw):
        if url.endswith("/stock"):
            return _FakeResponse({"symbol": params["symbol"], "price": 100.0})
        if url.endswith("/stock/list"):
            return _FakeResponse([{"symbol": s, "price": 100.0}
                                  for s in params["symbols"].split(",")])
        return _FakeResponse([{"symbol": "RELIANCE.NS"}])

    monkeypatch.setattr(httpx, "get", fake_get)

    quote = isa.get_stock_data("RELIANCE")          # -> /stock?symbol=RELIANCE.NS&res=num
    batch = isa.get_batch_stocks(["RELIANCE", "INFY"])  # -> /stock/list?symbols=...&res=num
    hits = isa.search_stocks("reliance")            # -> /search?q=reliance

    assert quote["symbol"] == "RELIANCE.NS"
    assert len(batch) == 2
    assert hits[0]["symbol"] == "RELIANCE.NS"
