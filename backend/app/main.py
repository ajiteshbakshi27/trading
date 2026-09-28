"""
QuantPulse AI - FastAPI Entry Point
REST + WebSocket streaming with full mock fallbacks.
Run: uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations
import asyncio
import random
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Rate-limit budget for expensive/state-changing endpoints (per IP).
_RATE_LIMITED = {"/api/allocate", "/api/trade", "/api/kill-switch",
                 "/api/copilot", "/api/portfolio", "/api/portfolio/save",
                 # Research loop: state-changing writes
                 "/api/thesis/create", "/api/thesis", "/api/predictions",
                 "/api/experiments", "/api/demo/run", "/api/research/cycle",
                 "/api/information/events/detect"}
_RATE_WINDOW_S = 60
_RATE_MAX = 20
_BUCKETS: Dict[str, List[float]] = {}
# Alpha Vantage refresh budget per snapshot tick (keeps cold starts fast).
_AV_REFRESH_PER_TICK = 2

from app.config import get_settings, MOCK_DATA_CONFIG
from app.quantum_hft.hft_engine import HFTManager, VWAPExecutor, TWAPExecutor
from app.quantum_hft.qaoa_optimizer import quantum_portfolio_optimize
from app.quantum_hft.quantum_risk import risk_report
from app.agents.sentiment_agent import SentimentEngine
from app.agents.prediction_agent import PredictionAgent
from app.agents.betting_engine import BettingEngine
from app.trading.alpaca_client import AlpacaClient
from app.trading.backtester import run_backtest, gen_price_path
from app.trading.allocator import allocate, RISK_PROFILES
from app.trading.rebalancer import rebalance_orders
from app.trading.costs import estimate_costs
from app.quantum_hft import risk_manager
from app.services import alert_service
from app import market_data as md
from app.streaming import StreamClient
from app import copilot
from app import database as db
from app.api import (demo, divergence, event_transmission, experiments,
                     indian_stocks, information, monte_carlo, news, paper,
                     prediction_autopsy, reddit_extractor, research,
                     research_backtest, sentiment_divergence, thesis)
from app.api.context import ResearchContext
from app.services.fusion import FUSION_PRIORS, MODEL_VERSION as FUSION_VERSION
settings = get_settings()

# Real-time Alpaca stream (idle until ALPACA_API_KEY+SECRET are set).
stream_client = StreamClient(settings.alpaca_key or "",
                             settings.alpaca_secret or "",
                             feed=settings.ALPACA_DATA_FEED,
                             max_age_s=settings.STREAM_MAX_AGE_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stream_client.start(list(BASE_PRICES))
    # Prime the market-data cache off the event loop so no request pays the
    # cold-start cost (Alpha Vantage is paced at ~1 req/s).
    warm_task = asyncio.create_task(_warm_market_data())
    try:
        yield
    finally:
        warm_task.cancel()
        await stream_client.stop()


async def _warm_market_data() -> None:
    try:
        client = _av()
        if client is None:
            return
        await asyncio.to_thread(client.warm, list(BASE_PRICES))
    except Exception:
        pass  # cache stays cold; the per-tick cap still bounds latency


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION,
              lifespan=lifespan)

# Research routers: included additively; no existing route is replaced.
app.include_router(information.router)
app.include_router(thesis.router)
app.include_router(event_transmission.router)
app.include_router(prediction_autopsy.router)
app.include_router(experiments.router)
app.include_router(demo.router)
app.include_router(research.router)
app.include_router(research.asset_router)
app.include_router(research_backtest.router)
app.include_router(paper.router)
app.include_router(divergence.router)
app.include_router(news.router)
app.include_router(monte_carlo.router)
app.include_router(sentiment_divergence.router)
app.include_router(reddit_extractor.router)
app.include_router(indian_stocks.router)

# Phase 2: create tables (Postgres when DATABASE_URL works, else SQLite).
# Never blocks startup: failures degrade to in-memory-safe fallbacks.
try:
    db.init_db()
    db.register_model_version(FUSION_VERSION,
                              "Shared research fusion function: one fuse() for "
                              "signals, stress tests and tournament ablations.",
                              {k.value: v for k, v in FUSION_PRIORS.items()})
except Exception:
    pass

# CORS: explicit allowlist only. Never "*" together with credentials —
# a wildcard would silently defeat the Vercel/Render allowlist in config.py.
_allowed = [o.strip().rstrip("/") for o in settings.CORS_ORIGINS if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline hardening headers for a public deploy."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if request.url.path.startswith("/api") or request.url.path == "/health":
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def rate_limit(request, call_next):
    """In-process limiter for expensive / state-changing endpoints.
    Single-worker by design (run uvicorn with --workers 1)."""
    path = request.url.path
    limited = (
        path.startswith("/ws/")
        or path in _RATE_LIMITED
    )
    if not limited:
        return await call_next(request)
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _BUCKETS.setdefault(ip, [])
    cutoff = now - _RATE_WINDOW_S
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= _RATE_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Slow down."},
            headers={"Retry-After": str(int(_RATE_WINDOW_S))},
        )
    bucket.append(now)
    return await call_next(request)

BASE_PRICES = {"AAPL": 232.0, "MSFT": 428.0, "NVDA": 131.0, "TSLA": 248.0,
               "GOOGL": 176.0, "META": 585.0, "AMD": 122.0, "INTC": 24.0,
               "AMZN": 205.0}
hft = HFTManager(BASE_PRICES)
sent_engine = SentimentEngine(universe=list(BASE_PRICES))
pred_agent = PredictionAgent()
bet_engine = BettingEngine()
alpaca = AlpacaClient(settings.alpaca_key, settings.alpaca_secret,
                      settings.ALPACA_BASE_URL)

# Singletons the research routers read, resolved once at startup.
app.state.research = ResearchContext(
    hft=hft, sent_engine=sent_engine, pred_agent=pred_agent,
    bet_engine=bet_engine, stream_client=stream_client,
    base_prices=dict(BASE_PRICES),
)


def _fresh_settings():
    """Read current settings (clears test-injected staleness via lru cache reset safe)."""
    return get_settings()


def _feed_status() -> Dict:
    return _fresh_settings().feed_status()


def _alpaca_client() -> AlpacaClient:
    s = _fresh_settings()
    return AlpacaClient(s.alpaca_key, s.alpaca_secret, s.ALPACA_BASE_URL)


_av_client: Optional[Any] = None
_av_key: Optional[str] = None


def _av() -> Optional[md.AlphaVantageClient]:
    """Cached Alpha Vantage client (rebuilt if the key changes). Shares the
    60s cache + daily budget across snapshot and WS ticks."""
    global _av_client, _av_key
    s = _fresh_settings()
    key = s.FINANCIAL_DATA_API_KEY
    if not key:
        return None
    if _av_client is None or _av_key != key:
        _av_client = md.AlphaVantageClient(key, cache_ttl_s=s.AV_CACHE_TTL_S,
                                           max_daily_calls=s.AV_MAX_DAILY_CALLS)
        _av_key = key
    return _av_client


def _apply_live_quotes(books: List[Dict]) -> Dict[str, Any]:
    """Overlay cached live quotes onto simulated books (mid = live price).
    Skips books already covered by the real-time stream (saves AV budget).
    Returns usage report. Never raises; failures keep simulator mids."""
    report: Dict[str, Any] = {"mode": "mock_simulator", "live_symbols": []}
    try:
        client = _av()
        if client is None:
            return report
        uncovered = [b["symbol"] for b in books if "stream" not in b]
        # Cap refresh work per tick: a cold snapshot must stay fast. Symbols
        # not refreshed this tick keep the simulator mid (60s cache covers
        # the rest on the next passes).
        quotes = client.quotes(uncovered, limit=_AV_REFRESH_PER_TICK)
        for b in books:
            q = quotes.get(b["symbol"])
            if q:
                md.recenter_book(b, q["price"])
                b["live"] = q
                report["live_symbols"].append(b["symbol"])
        if report["live_symbols"]:
            report["mode"] = "alphavantage"
        report["usage"] = client.usage()
    except Exception:
        pass
    return report


def _apply_stream_ticks(books: List[Dict],
                        client: Optional[StreamClient] = None) -> Dict[str, Any]:
    """Overlay real-time stream ticks (fresh or stale-flagged).
    Never raises; no ticks -> books untouched."""
    report: Dict[str, Any] = {"mode": "mock_simulator", "live_symbols": [],
                              "stale_symbols": []}
    try:
        client = client or stream_client
        for b in books:
            q = client.get_quote(b["symbol"])
            if q:
                md.recenter_book(b, q["price"])
                b["stream"] = q
                if q["stale"]:
                    report["stale_symbols"].append(b["symbol"])
                else:
                    report["live_symbols"].append(b["symbol"])
        if report["live_symbols"] or report["stale_symbols"]:
            report["mode"] = "alpaca_stream"
        report["status"] = client.status()
    except Exception:
        pass
    return report


class OptimizeRequest(BaseModel):
    symbols: List[str]
    expected_returns: List[float]
    cov_matrix: List[List[float]]
    risk_aversion: float = 1.0


class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str = "buy"
    order_type: str = "market"
    limit_price: Optional[float] = None


@app.get("/health")
def health():
    """Liveness + readiness. No secrets, ever."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "halted": risk_manager.is_halted(),
        "db": db.engine_info().get("backend"),
        "feeds": _feed_status(),
    }


@app.get("/")
def root():
    """API root — points to docs and health. The frontend is a separate app."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
        "snapshot": "/api/snapshot",
        "note": "This is the API backend. The frontend is deployed separately (Vercel).",
    }


@app.get("/api/feeds/status")
def feeds_status():
    """Phase 1: report live vs mock source per feed without changing data shapes."""
    feeds = _feed_status()
    try:
        st = stream_client.status()
        feeds["stream"] = ("live" if st["connected"]
                           else "configured" if st["configured"] else "mock")
    except Exception:
        feeds["stream"] = "mock"
    return {"feeds": feeds}


@app.get("/api/snapshot")
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
                          "quantum_edge": random.uniform(-0.08, 0.08),
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


@app.post("/api/quantum/optimize")
def optimize(req: OptimizeRequest):
    n = len(req.expected_returns)
    if n == 0:
        raise HTTPException(status_code=422, detail="expected_returns must not be empty")
    if len(req.cov_matrix) != n or any(len(row) != n for row in req.cov_matrix):
        raise HTTPException(status_code=422,
                            detail="cov_matrix must be n x n, matching expected_returns length")
    return quantum_portfolio_optimize(req.expected_returns, req.cov_matrix,
                                      req.risk_aversion)


@app.post("/api/risk/report")
def risk(payload: Dict):
    return risk_report(payload.get("returns", []))


@app.get("/api/backtest")
def backtest(symbol: str = "NVDA", periods: int = 252, series: bool = False):
    prices = gen_price_path(BASE_PRICES.get(symbol, 100), n=periods).tolist()
    return run_backtest(prices, initial=settings.BACKTEST_INITIAL_CAPITAL,
                        commission=settings.BACKTEST_COMMISSION,
                        include_series=series)


@app.post("/api/trade")
def trade(req: OrderRequest):
    if req.qty <= 0:
        raise HTTPException(status_code=422, detail="qty must be > 0")
    if req.order_type not in ("market", "limit"):
        raise HTTPException(status_code=422, detail="order_type must be 'market' or 'limit'")
    if req.order_type == "limit" and (req.limit_price is None or req.limit_price <= 0):
        raise HTTPException(status_code=422, detail="limit orders need a positive limit_price")
    side = "buy" if req.side.lower() in ("buy", "long") else "sell"
    res = _alpaca_client().place_order(req.symbol, req.qty, side, req.order_type,
                                       limit_price=req.limit_price)
    # Cost estimate + execution log (best-effort, never breaks the order).
    try:
        s = _fresh_settings()
        mids = {b["symbol"]: b["mid"] for b in hft.snapshot_all()}
        px = mids.get(req.symbol.upper()) or BASE_PRICES.get(req.symbol.upper(), 0.0)
        res["costs"] = estimate_costs(float(req.qty) * px, spread_bps=5.0,
                                      fee_rate=s.FEE_RATE, fee_min=s.FEE_MIN,
                                      tax_rate=s.TAX_RATE_GAINS)
        db.save_trade_execution(req.symbol, side, float(req.qty), req.order_type,
                                str(res.get("status", "")),
                                str(res.get("id") or res.get("error", "")))
    except Exception:
        pass
    return res


@app.get("/api/account")
def account():
    return _alpaca_client().account()


class SignalLogRequest(BaseModel):
    symbol: str
    type: str = "NO_BET"
    direction: str = "FLAT"
    confidence: float = 0.0
    price: float = 0.0
    target: float = 0.0
    stop: float = 0.0
    bullish_pct: float = 50.0
    sentiment: float = 0.0
    ofi_norm: float = 0.0
    rationale: str = ""


class PortfolioRequest(BaseModel):
    name: str = ""
    budget: float = 0.0
    currency: str = "USD"
    risk_profile: str = "balanced"
    tickers: List[str] = []
    notes: str = ""


@app.get("/api/history")
def history(limit: int = Query(default=100, ge=1, le=1000),
            symbol: Optional[str] = None,
            type: Optional[str] = None):
    """Fetch stored signal history + recent prediction edges."""
    return {
        "signals": db.get_signal_history(limit=limit, symbol=symbol, signal_type=type),
        "predictions": db.get_prediction_history(limit=min(limit, 200)),
        "backend": db.engine_info().get("backend"),
    }


@app.post("/api/history")
def log_signal(req: SignalLogRequest):
    """Manually log one signal entry."""
    n = db.save_signals([req.model_dump()])
    return {"saved": n}


@app.get("/api/portfolio")
def list_portfolio(limit: int = Query(default=50, ge=1, le=200)):
    """Fetch saved user portfolio inputs."""
    return {"portfolios": db.list_portfolios(limit=limit),
            "backend": db.engine_info().get("backend")}


@app.post("/api/portfolio")
def save_portfolio(req: PortfolioRequest):
    """Save a user portfolio input (budget must be > 0)."""
    try:
        row = db.save_portfolio(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"portfolio": row}


class AllocatorRequest(BaseModel):
    budget: float = 100000.0
    currency: str = "INR"
    risk_profile: str = "balanced"
    tickers: List[str] = []


@app.post("/api/allocate")
def allocate_capital(req: AllocatorRequest):
    """Smart capital allocator: quantum weights + sentiment + HFT risk."""
    try:
        books = hft.snapshot_all()
        sent = sent_engine.aggregate()
        rows = []
        wanted = {t.upper() for t in (req.tickers or [])}
        for b in books:
            s = b["symbol"]
            if wanted and s not in wanted:
                continue
            agg = sent["by_ticker"].get(s, {"bullish_pct": 50, "sentiment": 0.0})
            rows.append({"symbol": s, "price": b["mid"],
                         "sentiment": agg["sentiment"],
                         "ofi_norm": b["ofi"]["ofi_norm"],
                         "bullish_pct": agg["bullish_pct"]})
        plan = allocate(req.budget, req.risk_profile, rows)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    plan["currency"] = (req.currency or "USD").upper()
    # Pre-trade cost estimate on the LONG sleeve (best-effort).
    try:
        s = _fresh_settings()
        proj_profit = plan["long_cost"] * plan["projected_return_pct"] / 100
        plan["costs"] = estimate_costs(
            plan["long_cost"], spread_bps=5.0, projected_profit=proj_profit,
            fee_rate=s.FEE_RATE, fee_min=s.FEE_MIN, tax_rate=s.TAX_RATE_GAINS)
        plan["net_projected_return_pct"] = round(
            plan["costs"]["net_projected_profit"] / plan["budget"] * 100, 2)
    except Exception:
        pass
    # Best-effort portfolio log (never breaks the plan).
    try:
        db.save_portfolio({"name": f"allocator-{plan['risk_profile']}",
                           "budget": plan["budget"], "currency": plan["currency"],
                           "risk_profile": plan["risk_profile"],
                           "tickers": [ln["symbol"] for ln in plan["lines"]],
                           "notes": "auto-saved allocator plan"})
    except Exception:
        pass
    return plan


class CopilotRequest(BaseModel):
    question: str = ""


class KillSwitchRequest(BaseModel):
    action: str = "trip"  # trip | reset | evaluate
    reason: str = "manual"
    equity_curve: List[float] = []


class RebalanceRequest(BaseModel):
    holdings: Dict[str, float] = {}  # {symbol: shares}
    target_weights: Dict[str, float] = {}  # {symbol: weight}; empty = quantum equal-risk
    total_value: Optional[float] = None


@app.get("/api/predictions/history")
def predictions_history(limit: int = Query(default=100, ge=1, le=1000)):
    """Stored prediction-market odds and edges over time."""
    return {"predictions": db.get_prediction_history(limit=limit),
            "backend": db.engine_info().get("backend")}


@app.post("/api/portfolio/save")
def save_portfolio_alias(req: PortfolioRequest):
    """Alias of POST /api/portfolio (spec endpoint name)."""
    return save_portfolio(req)


@app.get("/api/trades")
def trade_history(limit: int = Query(default=100, ge=1, le=500),
                  symbol: Optional[str] = None):
    """Routed-order + kill-switch event log."""
    return {"trades": db.list_trade_executions(limit=limit, symbol=symbol),
            "backend": db.engine_info().get("backend")}


@app.post("/api/copilot")
def copilot_chat(req: CopilotRequest):
    """Plain-language quant explainer over the live snapshot."""
    snap = snapshot()
    # Avoid recursive persistence noise: snapshot already saved; just answer.
    return copilot.answer(req.question, snap)


@app.get("/api/kill-switch")
def kill_status():
    s = _fresh_settings()
    return {**risk_manager.status(),
            "threshold_pct": s.KILL_SWITCH_DRAWNDOWN_PCT}


@app.post("/api/kill-switch")
def kill_switch(req: KillSwitchRequest):
    """trip (halts signals + liquidates) | reset (re-arm) | evaluate (dry-run)."""
    s = _fresh_settings()
    if req.action == "reset":
        return risk_manager.reset()
    if req.action == "evaluate":
        ev = risk_manager.evaluate(req.equity_curve,
                                   threshold_pct=s.KILL_SWITCH_DRAWNDOWN_PCT)
        if ev["kill"]:
            risk_manager.trip("auto-evaluate", ev["drawdown_pct"])
            db.save_trade_execution("ALL", "sell", 0, "market", "KILL_SWITCH",
                                    f"drawdown {ev['drawdown_pct']}%")
        return {**ev, **risk_manager.status()}
    # trip
    liq = risk_manager.liquidate(_alpaca_client())
    out = risk_manager.trip(req.reason or "manual", 0.0)
    db.save_trade_execution("ALL", "sell", 0, "market", "KILL_SWITCH",
                            f"{req.reason}; liq={liq.get('mode')}")
    try:
        s2 = _fresh_settings()
        alert_service.maybe_alert(
            [{"type": "BET_AGAINST", "symbol": "PORTFOLIO", "direction": "FLAT",
              "confidence": 1.0, "rationale": f"KILL SWITCH: {req.reason}"}],
            [], bot_token=s2.TELEGRAM_BOT_TOKEN or "",
            chat_id=s2.TELEGRAM_CHAT_ID or "",
            discord_url=s2.DISCORD_WEBHOOK_URL or "")
    except Exception:
        pass
    return {**out, "liquidation": liq}


@app.post("/api/rebalance")
def rebalance(req: RebalanceRequest):
    """Drift vs target weights -> whole-share buy/sell orders."""
    try:
        books = {b["symbol"]: b["mid"] for b in hft.snapshot_all()}
        targets = {k.upper(): float(v) for k, v in (req.target_weights or {}).items()}
        if not targets:
            n = len(books)
            targets = {s: 1.0 / n for s in books}
        holdings = {k.upper(): float(v) for k, v in (req.holdings or {}).items()}
        return rebalance_orders(holdings, books, targets, req.total_value)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/candles")
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


@app.websocket("/ws/stream")
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
