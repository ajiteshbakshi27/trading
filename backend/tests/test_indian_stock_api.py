"""
QuantPulse AI — Indian Stock Market API client tests.

Run:  python -m pytest tests/test_indian_stock_api.py -v

All HTTP is mocked (no network). Covers: symbol normalisation, base-URL
config, res=num on every quote call, the three public methods, and
timeout / network-failure degradation.
"""
from __future__ import annotations

import sys
import types

import httpx
import pytest

from app.services import indian_stock_api as isa


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class _DeadNative:
    """Native provider stub that always fails (isolates upstream tests)."""

    def get_quote(self, symbol):
        raise httpx.ConnectError("native down")

    def get_batch(self, symbols):
        raise httpx.ConnectError("native down")

    def search(self, query):
        raise httpx.ConnectError("native down")


@pytest.fixture(autouse=True)
def _no_cache():
    from app.services import yahoo_finance
    isa.clear_caches()
    yahoo_finance.clear_caches()
    yield
    isa.clear_caches()
    yahoo_finance.clear_caches()


@pytest.fixture(autouse=True)
def _no_native(monkeypatch):
    """Stub the native fallback as dead unless a test overrides it."""
    monkeypatch.setattr(isa, "_native", lambda: _DeadNative())
    yield


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

    def test_index_ticker_unsuffixed(self):
        assert isa.normalize_symbol("^NSEI") == "^NSEI"


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
        assert out["symbol"] == "RELIANCE.NS"
        assert out["price"] == 2980.5
        assert out["source"] == "indian-stock-api"
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
        assert out == [{"symbol": "RELIANCE.NS", "source": "indian-stock-api"}]
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


# ---------------------------------------------------------------------------
# Fallback chain: upstream server -> native Yahoo -> miss
# ---------------------------------------------------------------------------

class _StubNative:
    def __init__(self, quote=None, batch=None, hits=None):
        self._quote, self._batch, self._hits = quote, batch, hits

    def get_quote(self, symbol):
        if self._quote is None:
            raise httpx.ConnectError("native down")
        return self._quote

    def get_batch(self, symbols):
        if self._batch is None:
            raise httpx.ConnectError("native down")
        return self._batch

    def search(self, query):
        if self._hits is None:
            raise httpx.ConnectError("native down")
        return self._hits


def _kill_upstream(monkeypatch):
    def boom(url, params=None, **kw):
        raise httpx.ConnectError("upstream down")

    monkeypatch.setattr(httpx, "get", boom)


class TestFallbackChain:
    def test_single_falls_back_to_native(self, monkeypatch):
        _kill_upstream(monkeypatch)
        native = {"ticker": "RELIANCE.NS", "source": "yahoo-finance",
                  "data": {"last_price": 1200.5}}
        monkeypatch.setattr(isa, "_native", lambda: _StubNative(quote=native))
        out = isa.get_stock_data("RELIANCE")
        assert out is not None
        assert out["source"] == "yahoo-finance"

    def test_single_both_dead_is_none(self, monkeypatch):
        _kill_upstream(monkeypatch)
        assert isa.get_stock_data("RELIANCE") is None

    def test_batch_falls_back_to_native(self, monkeypatch):
        _kill_upstream(monkeypatch)
        native = [{"ticker": "INFY.NS", "source": "yahoo-finance"}]
        monkeypatch.setattr(isa, "_native", lambda: _StubNative(batch=native))
        out = isa.get_batch_stocks(["INFY"])
        assert len(out) == 1
        assert out[0]["source"] == "yahoo-finance"

    def test_search_falls_back_to_native(self, monkeypatch):
        _kill_upstream(monkeypatch)
        native = [{"symbol": "TCS", "source": "yahoo"}]
        monkeypatch.setattr(isa, "_native", lambda: _StubNative(hits=native))
        out = isa.search_stocks("tata")
        assert out == native


# ---------------------------------------------------------------------------
# Native provider (mocked yfinance / Yahoo HTTP)
# ---------------------------------------------------------------------------

class _FakeFI:
    last_price = 100.0
    previous_close = 98.0
    currency = "INR"
    open = 99.0
    day_high = 101.0
    day_low = 98.5
    year_high = 150.0
    year_low = 90.0
    last_volume = 1000
    market_cap = 1e9


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol

    @property
    def fast_info(self):
        if self.symbol in ("BOGUS.NS", "BOGUS"):
            raise RuntimeError("no such ticker")
        return _FakeFI()


def _fake_yf(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance",
                        types.SimpleNamespace(Ticker=_FakeTicker))


class TestNativeProvider:
    def test_quote_shapes_like_upstream(self, monkeypatch):
        from app.services import indian_native
        _fake_yf(monkeypatch)
        q = indian_native.get_quote("RELIANCE")
        assert q["status"] == "success"
        assert q["ticker"] == "RELIANCE.NS"
        assert q["exchange"] == "NSE"
        assert q["data"]["last_price"] == 100.0
        assert q["data"]["percent_change"] == pytest.approx(2.04, abs=0.01)
        assert q["source"] == "yahoo-finance"

    def test_quote_bo_exchange(self, monkeypatch):
        from app.services import indian_native
        _fake_yf(monkeypatch)
        q = indian_native.get_quote("INFY.BO")
        assert q["exchange"] == "BSE"
        assert q["ticker"] == "INFY.BO"

    def test_quote_index_ticker(self, monkeypatch):
        from app.services import indian_native
        _fake_yf(monkeypatch)
        q = indian_native.get_quote("^NSEI")
        assert q["ticker"] == "^NSEI"
        assert q["exchange"] == "NSE"
        assert q["data"]["last_price"] == 100.0

    def test_quote_unknown_is_none(self, monkeypatch):
        from app.services import indian_native
        _fake_yf(monkeypatch)
        assert indian_native.get_quote("BOGUS") is None

    def test_search_filters_indian_tickers(self, monkeypatch):
        from app.services import indian_native

        def fake_get(url, params=None, **kw):
            assert "yahoo" in url
            return _FakeResponse({"quotes": [
                {"symbol": "RELIANCE.NS", "longname": "Reliance Industries"},
                {"symbol": "AAPL", "longname": "Apple Inc"},
                {"symbol": "INFY.BO", "shortname": "Infosys"},
            ]})

        monkeypatch.setattr(httpx, "get", fake_get)
        out = indian_native.search("reliance")
        assert [h["ticker"] for h in out] == ["RELIANCE.NS", "INFY.BO"]

    def test_search_failure_is_empty(self, monkeypatch):
        from app.services import indian_native

        def boom(url, params=None, **kw):
            raise httpx.ConnectTimeout("slow")

        monkeypatch.setattr(httpx, "get", boom)
        assert indian_native.search("reliance") == []


# ---------------------------------------------------------------------------
# Generic Yahoo provider (US market) + divergence fallback
# ---------------------------------------------------------------------------

class TestYahooFinance:
    def test_us_quote(self, monkeypatch):
        from app.services import yahoo_finance
        _fake_yf(monkeypatch)
        q = yahoo_finance.get_quote("NVDA")
        assert q["symbol"] == "NVDA"
        assert q["price"] == 100.0
        assert q["change_pct"] == pytest.approx(2.04, abs=0.01)
        assert q["currency"] == "INR"  # fake fixture currency
        assert q["source"] == "yahoo-finance"

    def test_blank_symbol_is_none(self, monkeypatch):
        from app.services import yahoo_finance
        _fake_yf(monkeypatch)
        assert yahoo_finance.get_quote("   ") is None

    def test_batch_skips_failures(self, monkeypatch):
        from app.services import yahoo_finance
        _fake_yf(monkeypatch)
        out = yahoo_finance.get_batch(["NVDA", "BOGUS"])
        assert [q["symbol"] for q in out] == ["NVDA"]

    def test_results_cached(self, monkeypatch):
        from app.services import yahoo_finance
        _fake_yf(monkeypatch)
        a = yahoo_finance.get_quote("NVDA")
        b = yahoo_finance.get_quote("NVDA")
        assert a == b


class _DeadAV:
    def __init__(self, *a, **k):
        pass

    def quote(self, symbol):
        return None


class TestUSDivergenceFallback:
    def test_us_falls_back_to_yahoo(self, monkeypatch):
        from app.services import divergence_engine
        from app import market_data as md
        _fake_yf(monkeypatch)
        monkeypatch.setattr(md, "AlphaVantageClient", _DeadAV)
        divergence_engine.clear_caches()
        d = divergence_engine.compute_divergence("NVDA")
        m = d["market"]
        assert m["source"] == "yahoo-finance"
        assert m["data_mode"] == "live"
        assert m["price"] == 100.0
