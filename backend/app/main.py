"""
Parakh - FastAPI Entry Point
REST + WebSocket streaming with full mock fallbacks.
Run: uvicorn app.main:app --reload --port 8000

This file only wires the app together: lifespan, middleware and routers.
Endpoints live in app/api/*; shared singletons in app/core/runtime.py.
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Rate-limit budget for expensive/state-changing endpoints (per IP).
_RATE_LIMITED = {"/api/allocate", "/api/trade", "/api/kill-switch",
                 "/api/copilot", "/api/portfolio", "/api/portfolio/save",
                 # Research loop: state-changing writes
                 "/api/thesis/create", "/api/thesis", "/api/predictions",
                 "/api/experiments", "/api/demo/run", "/api/research/cycle",
                 "/api/information/events/detect"}
_RATE_WINDOW_S = 60
_RATE_MAX = 20

from app.api import (demo, divergence, event_transmission, experiments,
                     history, indian_stocks, information, monte_carlo, news,
                     paper, prediction_autopsy, reddit_extractor, research,
                     research_backtest, sentiment_divergence, snapshot,
                     system, thesis, trading)
from app.api import parakh as parakh_api
from app.api.context import ResearchContext
from app.core import state_store
from app.core.runtime import (BASE_PRICES, _av, bet_engine, hft, pred_agent,
                              sent_engine, settings, stream_client)
from app import database as db
from app.services.fusion import FUSION_PRIORS, MODEL_VERSION as FUSION_VERSION


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

# Stored prediction history must be registered before the research routers:
# `/api/predictions/{id}` would otherwise swallow `/api/predictions/history`.
app.include_router(history.router)

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
app.include_router(parakh_api.router)
app.include_router(system.router)
app.include_router(snapshot.router)
app.include_router(trading.router)

# Singletons the research routers read, resolved once at startup.
app.state.research = ResearchContext(
    hft=hft, sent_engine=sent_engine, pred_agent=pred_agent,
    bet_engine=bet_engine, stream_client=stream_client,
    base_prices=dict(BASE_PRICES),
)

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
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Parakh-Dev-User"],
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
    # Shared store: Redis when REDIS_URL works (multi-worker safe), else memory.
    if not state_store.rate_hit(f"{ip}:{path}", _RATE_WINDOW_S, _RATE_MAX):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Slow down."},
            headers={"Retry-After": str(int(_RATE_WINDOW_S))},
        )
    return await call_next(request)
