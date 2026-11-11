"""Live snapshot, copilot, candles and the websocket tick stream."""
from __future__ import annotations
import asyncio
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app import copilot
from app import database as db
from app.core.runtime import (BASE_PRICES, _apply_live_quotes,
                              _apply_stream_ticks, _av, _feed_status,
                              _fresh_settings, bet_engine, hft, pred_agent,
                              sent_engine)
from app.quantum_hft import risk_manager
from app.services import alert_service

router = APIRouter()


class CopilotRequest(BaseModel):
    question: str = ""


@router.get("/api/snapshot")
def snapshot():
    # Kill-switch: halted -> no new signals, feed stays alive with marker.
    if risk_manager.is_halted():
        books = hft.snapshot_all()
        return {"books": books, "sentiment": {"posts": [], "by_ticker": {}},
                "prediction": {"markets": [], "edges": []}, "signals": [],
                "halted": True, "kill": risk_manager.status().get("trip", {}),
                "feeds": _feed_status(), "saved": {"signals": 0, "predictions": 0}}
    books = hft.snapshot_all()
    # Priority: real-time stream ticks -> cached AV quotes -> simulator.
    stream_report = _apply_stream_ticks(books)
    live_report = _apply_live_quotes(books)
    live_report["stream"] = stream_report
    if stream_report["live_symbols"]:
        live_report["mode"] = "alpaca_stream"
        live_report["live_symbols"] = sorted(
            set(live_report["live_symbols"]) | set(stream_report["live_symbols"]))
    # Live Reddit when keys exist; deterministic mock otherwise.
    try:
        s0 = _fresh_settings()
        live_posts = (sent_engine.reddit_live(s0.REDDIT_CLIENT_ID, s0.REDDIT_CLIENT_SECRET)
                      if s0.has_reddit else None)
    except Exception:
        live_posts = None
    sent = sent_engine.aggregate(posts=live_posts)
    markets = pred_agent.fetch_mock()
    analysis = pred_agent.analyze(markets)
    sig_input = []
    for b in books:
        s = b["symbol"]
        agg = sent["by_ticker"].get(s, {"bullish_pct": 50, "sentiment": 0.0})
        sig_input.append({"symbol": s, "bullish_pct": agg["bullish_pct"],
                          "sentiment": agg["sentiment"],
                          "ofi_norm": b["ofi"]["ofi_norm"],
                          # No quantum model feeds live signals: the old
                          # random.uniform() placeholder was removed because a
                          # random input contradicts the integrity contract.
                          "quantum_edge": 0.0,
                          "price": b["mid"]})
    signals = bet_engine.generate(sig_input)
    # Phase 2: persist signals + prediction edges (best-effort, never breaks feed).
    try:
        saved = db.save_snapshot(signals, analysis.get("edges", []))
    except Exception:
        saved = {"signals": 0, "predictions": 0}
    # Alerts: high-confidence fades + hot edges -> Telegram/Discord (best-effort).
    try:
        s = _fresh_settings()
        alerts = alert_service.maybe_alert(
            signals, analysis.get("edges", []),
            bot_token=s.TELEGRAM_BOT_TOKEN or "", chat_id=s.TELEGRAM_CHAT_ID or "",
            discord_url=s.DISCORD_WEBHOOK_URL or "")
    except Exception:
        alerts = {"sent": 0, "mode": "error"}
    return {"books": books, "sentiment": sent, "prediction": analysis,
            "signals": signals, "feeds": _feed_status(), "saved": saved,
            "halted": False, "alerts": alerts, "market_data": live_report}


@router.post("/api/copilot")
def copilot_chat(req: CopilotRequest):
    """Plain-language quant explainer over the live snapshot."""
    snap = snapshot()
    # Avoid recursive persistence noise: snapshot already saved; just answer.
    return copilot.answer(req.question, snap)


@router.get("/api/candles")
def candles(symbol: str = "NVDA", n: int = Query(default=120, ge=20, le=500)):
    """Seeded OHLC candles + agent signal markers for chart overlays."""
    import random as _r
    sym = symbol.upper()
    # Live intraday first (cached); seeded walk as fallback.
    try:
        client = _av()
        if client is not None:
            live = client.intraday(sym)
            if live and len(live) >= 20:
                live = live[-n:]
                markers = []
                try:
                    for j, s in enumerate(db.get_signal_history(limit=200, symbol=sym)[:8]):
                        idx = len(live) - 1 - j * max(1, len(live) // 10)
                        if idx < 0:
                            break
                        is_buy = s.get("direction") == "LONG"
                        markers.append({"time": live[idx]["time"],
                                        "position": "belowBar" if is_buy else "aboveBar",
                                        "color": "#22C55E" if is_buy else "#EF4444",
                                        "shape": "arrowUp" if is_buy else "arrowDown",
                                        "text": f"{s.get('signal_type', '')} {s.get('confidence', 0)}"})
                except Exception:
                    pass
                return {"symbol": sym, "candles": live, "markers": markers,
                        "source": "alphavantage"}
    except Exception:
        pass
    # Yahoo Finance daily history (no key) before the seeded simulator.
    # This is what the dashboard quotes already use — charts were the one
    # endpoint still AV-or-simulator, hence "old data" once AV quota ran out.
    try:
        from app.services import yahoo_finance as yfmod
        yh = yfmod.get_candles(sym, n=n)
        if yh and len(yh) >= 20:
            markers = []
            try:
                for j, s in enumerate(db.get_signal_history(limit=200, symbol=sym)[:8]):
                    idx = len(yh) - 1 - j * max(1, len(yh) // 10)
                    if idx < 0:
                        break
                    is_buy = s.get("direction") == "LONG"
                    markers.append({"time": yh[idx]["time"],
                                    "position": "belowBar" if is_buy else "aboveBar",
                                    "color": "#22C55E" if is_buy else "#EF4444",
                                    "shape": "arrowUp" if is_buy else "arrowDown",
                                    "text": f"{s.get('signal_type', '')} {s.get('confidence', 0)}"})
            except Exception:
                pass
            return {"symbol": sym, "candles": yh, "markers": markers,
                    "source": "yahoo-finance"}
    except Exception:
        pass
    base = BASE_PRICES.get(sym, 100.0)
    rng = _r.Random(abs(hash(sym)) % (2 ** 31))
    px = base * 0.92
    out = []
    t = 1_700_000_000
    for i in range(n):
        o = px
        drift = rng.gauss(0.0006, 0.012) * o
        c = max(1.0, o + drift)
        h = max(o, c) * (1 + abs(rng.gauss(0, 0.004)))
        l = min(o, c) * (1 - abs(rng.gauss(0, 0.004)))
        out.append({"time": t + i * 86400, "open": round(o, 2),
                    "high": round(h, 2), "low": round(l, 2),
                    "close": round(c, 2)})
        px = c
    # Overlay latest stored signals as markers near the right edge.
    markers = []
    try:
        for j, s in enumerate(db.get_signal_history(limit=200, symbol=sym)[:8]):
            idx = n - 1 - j * max(1, n // 10)
            if idx < 0:
                break
            is_buy = s.get("direction") == "LONG"
            markers.append({"time": out[idx]["time"],
                            "position": "belowBar" if is_buy else "aboveBar",
                            "color": "#22C55E" if is_buy else "#EF4444",
                            "shape": "arrowUp" if is_buy else "arrowDown",
                            "text": f"{s.get('signal_type', '')} {s.get('confidence', 0)}"})
    except Exception:
        pass
    return {"symbol": sym, "candles": out, "markers": markers,
            "source": "simulator"}


@router.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # snapshot() is blocking (DB writes + market-data pacing sleeps):
            # run it in a worker thread so the event loop keeps serving others.
            data = await asyncio.to_thread(snapshot)
            await ws.send_json({"type": "tick", "data": data})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        try: await ws.close()
        except Exception: pass
