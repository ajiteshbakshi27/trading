"""Gemini backend: provider choice, structured parse, tool loop, failure fallback.

No network: httpx.post is replaced with a fake that returns canned responses.
"""
import pytest

from app.config import get_settings
from app.parakh import copilot, gemini, llm, thesis_check


class _Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._data


def _text_resp(text):
    return _Resp({"candidates": [{"content": {"role": "model", "parts": [{"text": text}]}}]})


@pytest.fixture
def gemini_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(s, "GEMINI_API_KEY", "test-key")
    calls = []

    def install(responses):
        it = iter(responses)

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append({"url": url, "headers": headers, "json": json})
            return next(it)
        monkeypatch.setattr(gemini.httpx, "post", fake_post)
        return calls
    return install


def test_provider_order(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", None)
    monkeypatch.setattr(s, "GEMINI_API_KEY", None)
    assert llm.provider() is None and not llm.available()
    monkeypatch.setattr(s, "GEMINI_API_KEY", "g")
    assert llm.provider() == "gemini"
    monkeypatch.setattr(s, "ANTHROPIC_API_KEY", "a")
    assert llm.provider() == "claude"


def test_parse_idea_with_gemini(gemini_on):
    calls = gemini_on([_text_resp('{"symbol": "HDFCBANK", "direction": "LONG", '
                                  '"horizon_days": 10, "catalyst": "", "user_confidence": 0.7}')])
    idea, mode = thesis_check.parse_idea("HDFC Bank will rally in 2 weeks")
    assert mode == "gemini" and idea.symbol == "HDFCBANK" and idea.direction == "LONG"
    # key goes in a header, never in the URL
    assert "test-key" not in calls[0]["url"]
    assert calls[0]["headers"]["x-goog-api-key"] == "test-key"


def test_bad_json_falls_back_to_rules(gemini_on):
    gemini_on([_text_resp("not json at all")])
    idea, mode = thesis_check.parse_idea("HDFC Bank will rally in 2 weeks")
    assert mode == "rules" and idea is not None


def test_http_error_falls_back(gemini_on):
    gemini_on([_Resp({}, status=429)])
    assert llm.write("hello") is None


def test_copilot_tool_loop(gemini_on, monkeypatch):
    monkeypatch.setattr(copilot.market, "quote",
                        lambda sym: {"symbol": sym, "price": 100.0, "data_mode": "simulated"})
    calls = gemini_on([
        _Resp({"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "get_quote", "args": {"symbol": "RELIANCE"}}}]}}]}),
        _text_resp("RELIANCE is at ₹100 (simulated data)."),
    ])
    out = copilot.ask("dev-user", "What is RELIANCE at?")
    assert out["mode"] == "gemini" and out["tools_used"] == ["get_quote"]
    assert "100" in out["answer"]
    second = calls[1]["json"]["contents"]
    assert second[-1]["parts"][0]["functionResponse"]["name"] == "get_quote"
    # tools without parameters must not send an empty object schema
    decls = calls[0]["json"]["tools"][0]["function_declarations"]
    assert "parameters" not in next(d for d in decls if d["name"] == "my_journal")
