"""
QuantPulse AI - Persistent Storage (Phase 2)
Supabase/Postgres primary via DATABASE_URL, SQLite local fallback.

Design rules:
- Auto-create tables on startup (SQLModel metadata).
- Postgres is tried first when DATABASE_URL is set; any connection
  failure falls back to local SQLite so the feed never breaks.
- All helpers degrade gracefully: writes return 0 and reads return []
  instead of raising.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlmodel import SQLModel, Field, Session, create_engine, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------- Tables -------------------------------------

class SignalHistory(SQLModel, table=True):
    """Historical trade signals with price levels and crowd sentiment."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    symbol: str = Field(index=True)
    signal_type: str = Field(default="NO_BET", index=True)
    direction: str = "FLAT"
    confidence: float = 0.0
    price: float = 0.0
    target: float = 0.0
    stop: float = 0.0
    bullish_pct: float = 50.0
    sentiment: float = 0.0
    ofi_norm: float = 0.0
    rationale: str = ""


class PredictionBet(SQLModel, table=True):
    """Recorded prediction-market odds and quantum edges over time."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    market_id: str = Field(index=True)
    question: str = ""
    crowd_prob: float = 0.0
    quantum_prob: float = 0.0
    edge: float = 0.0
    side: str = ""
    confidence: float = 0.0


class UserPortfolio(SQLModel, table=True):
    """User portfolio inputs, budgets, and allocation recommendations."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    name: str = ""
    budget: float = 0.0
    currency: str = "USD"
    risk_profile: str = "balanced"
    tickers: str = "[]"  # JSON-encoded list
    notes: str = ""


class TradeExecution(SQLModel, table=True):
    """Orders routed to paper/live brokers, plus kill-switch events."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    symbol: str = Field(index=True)
    side: str = "buy"
    qty: float = 0.0
    order_type: str = "market"
    status: str = ""  # MOCK_FILLED / FILLED / ERROR / KILL_SWITCH
    detail: str = ""  # broker id or error / kill payload (truncated)


# ------------------------------- Engine -------------------------------------

_engine = None
_engine_backend = "uninitialized"


def _make_sqlite_engine(db_path: str):
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )


def get_engine():
    """Return cached engine; Postgres first, SQLite fallback. Never raises."""
    global _engine, _engine_backend
    if _engine is not None:
        return _engine
    try:
        from app.config import get_settings
        settings = get_settings()
        db_url = (settings.DATABASE_URL or "").strip()
        if db_url:
            try:
                eng = create_engine(db_url, pool_pre_ping=True)
                with eng.connect() as conn:
                    conn.exec_driver_sql("SELECT 1")
                _engine, _engine_backend = eng, "postgres"
                return _engine
            except Exception:
                pass  # fall through to SQLite
        db_path = getattr(settings, "DB_PATH", "quantpulse.db") or "quantpulse.db"
        _engine = _make_sqlite_engine(db_path)
        _engine_backend = "sqlite"
    except Exception:
        _engine = _make_sqlite_engine("quantpulse.db")
        _engine_backend = "sqlite"
    return _engine


def reset_engine() -> None:
    """Drop cached engine (used by tests to pick up new env)."""
    global _engine, _engine_backend
    try:
        if _engine is not None:
            _engine.dispose()
    except Exception:
        pass
    _engine, _engine_backend = None, "uninitialized"


def engine_info() -> Dict[str, str]:
    get_engine()
    return {"backend": _engine_backend}


def init_db() -> Dict[str, str]:
    """Create tables if missing. Never raises."""
    try:
        SQLModel.metadata.create_all(get_engine())
        return {"status": "ok", **engine_info()}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], **engine_info()}


# ------------------------------- Writes -------------------------------------

def save_signals(signals: List[Dict[str, Any]]) -> int:
    """Persist a batch of signal dicts. Returns rows written (0 on failure)."""
    if not signals:
        return 0
    try:
        rows = [
            SignalHistory(
                symbol=str(s.get("symbol", "")),
                signal_type=str(s.get("type", "NO_BET")),
                direction=str(s.get("direction", "FLAT")),
                confidence=float(s.get("confidence", 0) or 0),
                price=float(s.get("price", 0) or 0),
                target=float(s.get("target", 0) or 0),
                stop=float(s.get("stop", 0) or 0),
                bullish_pct=float(s.get("bullish_pct", 50) or 0),
                sentiment=float(s.get("sentiment", 0) or 0),
                ofi_norm=float(s.get("ofi_norm", 0) or 0),
                rationale=str(s.get("rationale", ""))[:500],
            )
            for s in signals
        ]
        with Session(get_engine()) as session:
            session.add_all(rows)
            session.commit()
        return len(rows)
    except Exception:
        return 0


def save_predictions(edges: List[Dict[str, Any]]) -> int:
    """Persist prediction edges. Returns rows written (0 on failure)."""
    if not edges:
        return 0
    try:
        rows = [
            PredictionBet(
                market_id=str(e.get("id", "")),
                question=str(e.get("question", ""))[:300],
                crowd_prob=float(e.get("crowd_prob", 0) or 0),
                quantum_prob=float(e.get("quantum_prob", 0) or 0),
                edge=float(e.get("edge", 0) or 0),
                side=str(e.get("side", "")),
                confidence=float(e.get("confidence", 0) or 0),
            )
            for e in edges
        ]
        with Session(get_engine()) as session:
            session.add_all(rows)
            session.commit()
        return len(rows)
    except Exception:
        return 0


def save_snapshot(signals: List[Dict[str, Any]],
                  edges: List[Dict[str, Any]]) -> Dict[str, int]:
    """Persist one snapshot's signals + edges. Never raises."""
    try:
        return {"signals": save_signals(signals), "predictions": save_predictions(edges)}
    except Exception:
        return {"signals": 0, "predictions": 0}


# ------------------------------- Reads --------------------------------------

def _dump(obj: SQLModel) -> Dict[str, Any]:
    d = obj.model_dump()
    if isinstance(d.get("created_at"), datetime):
        d["created_at"] = d["created_at"].isoformat()
    return d


def get_signal_history(limit: int = 100, symbol: Optional[str] = None,
                       signal_type: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        limit = max(1, min(int(limit), 1000))
        with Session(get_engine()) as session:
            q = select(SignalHistory).order_by(SignalHistory.id.desc()).limit(limit)
            rows = list(session.exec(q))
        out = [_dump(r) for r in rows]
        if symbol:
            out = [r for r in out if r["symbol"] == symbol]
        if signal_type:
            out = [r for r in out if r["signal_type"] == signal_type]
        return out
    except Exception:
        return []


def get_prediction_history(limit: int = 100) -> List[Dict[str, Any]]:
    try:
        limit = max(1, min(int(limit), 1000))
        with Session(get_engine()) as session:
            q = select(PredictionBet).order_by(PredictionBet.id.desc()).limit(limit)
            return [_dump(r) for r in session.exec(q)]
    except Exception:
        return []


def save_portfolio(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate + store a user portfolio input. Raises ValueError on bad input."""
    import json
    try:
        budget = float(data.get("budget", 0))
    except (TypeError, ValueError):
        raise ValueError("budget must be a number")
    if budget <= 0:
        raise ValueError("budget must be > 0")
    tickers = data.get("tickers", [])
    if isinstance(tickers, str):
        tickers = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    tickers = [str(t).upper() for t in (tickers or [])][:20]
    row = UserPortfolio(
        name=str(data.get("name", ""))[:100],
        budget=budget,
        currency=str(data.get("currency", "USD"))[:8].upper(),
        risk_profile=str(data.get("risk_profile", "balanced"))[:32].lower(),
        tickers=json.dumps(tickers),
        notes=str(data.get("notes", ""))[:500],
    )
    with Session(get_engine()) as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return _dump(row)


def list_portfolios(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        limit = max(1, min(int(limit), 200))
        with Session(get_engine()) as session:
            q = select(UserPortfolio).order_by(UserPortfolio.id.desc()).limit(limit)
            return [_dump(r) for r in session.exec(q)]
    except Exception:
        return []


def save_trade_execution(symbol: str, side: str, qty: float,
                         order_type: str, status: str, detail: str = "") -> int:
    """Log one routed order. Returns 1 on success, 0 on failure."""
    try:
        with Session(get_engine()) as session:
            session.add(TradeExecution(
                symbol=str(symbol).upper(), side=str(side).lower(),
                qty=float(qty or 0), order_type=str(order_type),
                status=str(status)[:32], detail=str(detail)[:500]))
            session.commit()
        return 1
    except Exception:
        return 0


def list_trade_executions(limit: int = 100,
                          symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        limit = max(1, min(int(limit), 500))
        with Session(get_engine()) as session:
            q = select(TradeExecution).order_by(TradeExecution.id.desc()).limit(limit)
            rows = [_dump(r) for r in session.exec(q)]
        if symbol:
            rows = [r for r in rows if r["symbol"] == symbol.upper()]
        return rows
    except Exception:
        return []
