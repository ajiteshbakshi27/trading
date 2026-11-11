"""
Parakh — product API. Every user-data route depends on ``require_user`` and
filters by ``user.id``. Expensive routes are rate-limited per user.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core import state_store
from app.core.auth import User, optional_user, require_user
from app.parakh import (autopsy, brief, copilot, hype_radar, india_events, journal, kite, market,
                        options, share, store, strategy_backtest, thesis_check, theses, universe)

router = APIRouter(prefix="/api/parakh", tags=["parakh"])


def limit(name: str, per_min: int):
    def dep(user: User = Depends(require_user)) -> User:
        if not state_store.rate_hit(f"u:{user.id}:{name}", 60, per_min):
            raise HTTPException(status_code=429, detail="Too many requests — wait a minute.")
        return user
    return dep


# ----------------------------------------------------------------- meta ----

@router.get("/me")
def me(user: Optional[User] = Depends(optional_user)):
    s = get_settings()
    return {"user": user.__dict__ if user else None,
            "auth_mode": "supabase" if s.auth_configured else ("disabled" if s.is_production else "dev"),
            "features": {"claude": bool(s.ANTHROPIC_API_KEY), "zerodha": kite.configured(),
                         "telegram": bool(s.TELEGRAM_BOT_TOKEN), "reddit": bool(s.REDDIT_CLIENT_ID),
                         "state_store": state_store.backend()}}


@router.get("/symbols")
def symbols(q: str = Query("", max_length=40)):
    return {"results": universe.search(q) if q else
            [{"symbol": s, "name": v[0], "sector": v[1], "kind": "stock"} for s, v in universe.STOCKS.items()]
            + [{"symbol": s, "name": v[0], "sector": "index", "kind": "index"} for s, v in universe.INDICES.items()]}


@router.get("/quote/{symbol}")
def quote(symbol: str):
    return market.quote(symbol[:20])


@router.get("/candles/{symbol}")
def candles(symbol: str, days: int = Query(180, ge=20, le=1250)):
    bars, mode = market.history(symbol[:20], days)
    return {"symbol": universe.normalize(symbol), "bars": bars, "data_mode": mode}


# ------------------------------------------------------ thesis check -------

class CheckRequest(BaseModel):
    idea: str = Field("", max_length=1000)
    symbol: Optional[str] = Field(None, max_length=20)
    direction: Optional[str] = None
    horizon_days: Optional[int] = Field(None, ge=1, le=120)
    user_confidence: Optional[float] = Field(None, ge=0.5, le=0.99)
    target_price: Optional[float] = Field(None, gt=0)
    stop_price: Optional[float] = Field(None, gt=0)
    catalyst: Optional[str] = Field(None, max_length=200)
    save: bool = True


@router.post("/check")
def check(req: CheckRequest, user: User = Depends(limit("check", 15))):
    idea, mode = (thesis_check.parse_idea(req.idea) if req.idea.strip() else (None, "fields"))
    if idea is None:
        if not req.symbol:
            raise HTTPException(status_code=422, detail="Couldn't find a stock or index in that idea. "
                                                        "Try e.g. 'HDFC Bank will rally in 2 weeks'.")
        idea = thesis_check.ParsedIdea(symbol=req.symbol, direction=req.direction or "LONG",
                                       horizon_days=req.horizon_days or 10)
        mode = "fields"
    # explicit fields override the parser
    if req.symbol: idea.symbol = universe.normalize(req.symbol)
    if req.direction: idea.direction = "SHORT" if req.direction.upper().startswith("S") else "LONG"
    if req.horizon_days: idea.horizon_days = req.horizon_days
    if req.user_confidence: idea.user_confidence = req.user_confidence
    if req.target_price: idea.target_price = req.target_price
    if req.stop_price: idea.stop_price = req.stop_price
    if req.catalyst is not None: idea.catalyst = req.catalyst
    try:
        report = thesis_check.build_report(idea)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Couldn't analyse {idea.symbol}: {type(e).__name__}")
    report["parse_mode"] = mode
    report["related_events"] = india_events.events_for_symbol(idea.symbol)
    if req.save:
        row = theses.create(user.id, report, req.idea or f"{idea.symbol} {idea.direction}")
        report["thesis_id"] = row.id
    return report


@router.get("/theses")
def list_theses(status: Optional[str] = None, user: User = Depends(require_user)):
    theses.resolve_user(user.id)
    return {"theses": [store.dump(r) for r in store.list_theses(user.id, status)]}


@router.get("/theses/{thesis_id}")
def get_thesis(thesis_id: str, user: User = Depends(require_user)):
    row = store.get_thesis(user.id, thesis_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    theses.resolve_row(row)
    return store.dump(store.get_thesis(user.id, thesis_id))


@router.post("/theses/{thesis_id}/publish")
def publish(thesis_id: str, user: User = Depends(require_user)):
    row = store.get_thesis(user.id, thesis_id)
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    row = share.publish(row)
    return {"slug": row.share_slug, "seal": row.seal_hash,
            "url": f"{get_settings().PUBLIC_APP_URL.rstrip('/')}/t/{row.share_slug}"}


@router.get("/public/thesis/{slug}")
def public_thesis(slug: str):
    try:
        return share.public_view(slug[:40])
    except KeyError:
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/leaderboard")
def leaderboard():
    return {"leaderboard": share.leaderboard(), "floor": share.LEADERBOARD_FLOOR,
            "method": "Ranked by Brier score (calibration) over resolved public ideas on live data. Lower is better."}


@router.get("/calibration")
def get_calibration(user: User = Depends(require_user)):
    theses.resolve_user(user.id)
    return theses.user_calibration(user.id)


# ------------------------------------------------------------ journal ------

@router.post("/journal/import")
async def journal_import(request: Request, file: Optional[UploadFile] = File(None),
                         user: User = Depends(limit("import", 10))):
    if file is not None:
        raw = await file.read(5_000_001)
    else:
        raw = await request.body()
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail="File too large (max 5 MB).")
    try:
        trades, fmt = journal.parse_csv(raw.decode("utf-8", errors="replace"))
    except journal.CsvError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"format": fmt, **store.add_trades(user.id, trades)}


@router.get("/journal")
def journal_view(user: User = Depends(require_user)):
    rows = store.list_trades(user.id)
    trips = journal.round_trips(rows)
    return {"trades": len(rows), "round_trips": list(reversed(trips))[:200],
            "stats": journal.stats(trips), "open_positions": journal.open_positions(rows)}


class TripAutopsyRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    entry_at: str
    exit_at: str


@router.post("/journal/autopsy")
def trip_autopsy(req: TripAutopsyRequest, user: User = Depends(limit("autopsy", 30))):
    return autopsy.diagnose(symbol=req.symbol, direction=req.direction, entry=req.entry_price,
                            exit_price=req.exit_price, entry_date=req.entry_at[:10],
                            exit_date=req.exit_at[:10], with_narrative=True)


@router.delete("/journal")
def journal_clear(user: User = Depends(require_user)):
    return {"deleted": store.delete_trades(user.id)}


# ----------------------------------------------------- watchlist / hype ----

class WatchlistRequest(BaseModel):
    symbols: List[str] = Field(default_factory=list, max_length=30)


@router.get("/watchlist")
def get_watchlist(user: User = Depends(require_user)):
    return {"symbols": store.watchlist(user.id)}


@router.put("/watchlist")
def put_watchlist(req: WatchlistRequest, user: User = Depends(require_user)):
    return {"symbols": store.set_watchlist(user.id, [universe.normalize(s)[:20] for s in req.symbols])}


@router.get("/hype")
def hype(user: User = Depends(limit("hype", 20))):
    syms = store.watchlist(user.id) or ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "TCS", "INFY"]
    return {"results": hype_radar.scan(syms), "alerts": [store.dump(a) for a in store.list_alerts(user.id, 20)]}


def _cron(x_cron_secret: str = Header("")):
    secret = get_settings().CRON_SECRET
    if not secret or x_cron_secret != secret:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/jobs/hype-alerts", dependencies=[Depends(_cron)])
def job_hype():
    return hype_radar.run_alerts()


@router.post("/jobs/resolve", dependencies=[Depends(_cron)])
def job_resolve():
    users = {r.user_id for r in store.list_theses_all_open()}
    return {"resolved": sum(theses.resolve_user(u) for u in users)}


# ------------------------------------------------------------- events ------

@router.get("/events")
def events():
    return {"events": india_events.list_events()}


@router.get("/events/{event_id}")
def event_map(event_id: str):
    try:
        return india_events.impact_map(event_id.upper())
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown event")


# ------------------------------------------------------------ options ------

class OptionLeg(BaseModel):
    kind: str = Field("CE", pattern="^(CE|PE|FUT)$")
    side: str = Field("BUY", pattern="^(BUY|SELL)$")
    strike: Optional[float] = Field(None, gt=0)
    premium: Optional[float] = Field(None, ge=0)
    lots: int = Field(1, ge=1, le=100)
    iv: Optional[float] = Field(None, gt=0, le=5)


class OptionsRequest(BaseModel):
    underlying: str = "NIFTY"
    spot: Optional[float] = Field(None, gt=0)
    days_to_expiry: float = Field(7, ge=0, le=400)
    lot_size: Optional[int] = Field(None, ge=1, le=100000)
    legs: List[OptionLeg] = Field(min_length=1, max_length=8)


@router.post("/options/analyse")
def options_analyse(req: OptionsRequest):
    spot = req.spot or float(market.quote(req.underlying)["price"])
    lot = req.lot_size or options.DEFAULT_LOTS.get(req.underlying.upper(), 1)
    try:
        return options.analyse(spot, req.days_to_expiry, [l.model_dump() for l in req.legs], lot_size=lot)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/options/lots")
def option_lots():
    return {"lots": options.DEFAULT_LOTS,
            "unverified": sorted(options.UNVERIFIED_LOTS),
            "note": "Defaults only — confirm the current exchange lot size."}


# ----------------------------------------------------------- backtest ------

class BacktestRequest(BaseModel):
    symbol: str = Field(max_length=20)
    entry_rule: str
    entry_params: Dict[str, float] = Field(default_factory=dict)
    exit_params: Dict[str, float] = Field(default_factory=dict)
    years: int = Field(3, ge=1, le=5)
    cost_pct: float = Field(strategy_backtest.DEFAULT_COST_PCT, ge=0, le=5)


@router.get("/backtest/rules")
def backtest_rules():
    return {"entry_rules": strategy_backtest.ENTRY_RULES,
            "exit_params": ["stop_pct", "target_pct", "max_hold_days", "sma_exit", "rsi_above"],
            "default_cost_pct": strategy_backtest.DEFAULT_COST_PCT}


@router.post("/backtest")
def backtest(req: BacktestRequest, user: User = Depends(limit("backtest", 10))):
    try:
        return strategy_backtest.run(universe.normalize(req.symbol), req.entry_rule, req.entry_params,
                                     req.exit_params, req.years, req.cost_pct)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ----------------------------------------------------------- settings ------

class SettingsRequest(BaseModel):
    display_name: Optional[str] = Field(None, max_length=60)
    public_handle: Optional[str] = Field(None, pattern=r"^[a-z0-9_]{3,20}$")
    telegram_chat_id: Optional[str] = Field(None, pattern=r"^-?\d{3,20}$")
    hype_alerts: Optional[bool] = None
    hype_threshold: Optional[float] = Field(None, ge=0.5, le=6)


@router.get("/settings")
def get_user_settings(user: User = Depends(require_user)):
    row = store.get_settings_row(user.id)
    conn = store.get_broker(user.id)
    d = store.dump(row)
    d["zerodha"] = {"connected": bool(conn), "broker_user_id": conn.broker_user_id if conn else None,
                    "last_sync_at": conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None}
    return d


@router.put("/settings")
def put_user_settings(req: SettingsRequest, user: User = Depends(require_user)):
    row = store.get_settings_row(user.id)
    data = req.model_dump(exclude_none=True)
    if "public_handle" in data and store.handle_taken(data["public_handle"], user.id):
        raise HTTPException(status_code=409, detail="That handle is taken.")
    for k, v in data.items():
        setattr(row, k, v)
    return store.dump(store.save_settings_row(row))


# ------------------------------------------------------------ broker -------

class KiteCallback(BaseModel):
    request_token: str = Field(min_length=6, max_length=64)


@router.get("/broker/zerodha/login-url")
def zerodha_login(user: User = Depends(require_user)):
    try:
        return {"url": kite.login_url()}
    except kite.KiteError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.post("/broker/zerodha/callback")
def zerodha_callback(req: KiteCallback, user: User = Depends(limit("kite", 10))):
    try:
        out = kite.exchange(user.id, req.request_token)
        out["sync"] = kite.sync_trades(user.id)
        return out
    except kite.KiteError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/broker/zerodha/sync")
def zerodha_sync(user: User = Depends(limit("kite", 10))):
    try:
        return kite.sync_trades(user.id)
    except kite.KiteError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/broker/zerodha")
def zerodha_disconnect(user: User = Depends(require_user)):
    store.delete_broker(user.id)
    return {"connected": False}


# --------------------------------------------------- copilot / brief -------

class CopilotRequest(BaseModel):
    question: str = Field(max_length=2000)
    history: List[Dict[str, str]] = Field(default_factory=list, max_length=20)


@router.post("/copilot")
def ask_copilot(req: CopilotRequest, user: User = Depends(limit("copilot", 12))):
    return copilot.ask(user.id, req.question, req.history)


@router.get("/brief")
def daily_brief(narrate: bool = False, user: User = Depends(require_user)):
    return brief.build(user.id, narrate=narrate)
