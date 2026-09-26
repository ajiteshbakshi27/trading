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

from app.models.enums import DataMode


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


# --------------------- Research loop (event → … → experiment) ----------------
# Every table carries created_at / updated_at / data_mode / model_version so a
# record can always be traced back to the feed that produced it and the model
# that consumed it. Payloads are JSON strings: the shapes are owned by the
# Pydantic models in app.models, and duplicating them here would let the two
# drift.


class _ResearchRow(SQLModel):
    """Shared provenance columns for every research record."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow, index=True)
    data_mode: str = Field(default="mock", index=True)
    model_version: str = Field(default="qp-fusion-1.0", index=True)


class MarketEventRow(_ResearchRow, table=True):
    event_id: str = Field(index=True)
    symbol: str = Field(index=True)
    event_type: str = "market"
    category: str = "company"
    headline: str = ""
    probability: Optional[float] = None
    magnitude: float = 0.0
    confidence: float = 0.0
    direction: str = "FLAT"
    themes: str = "[]"
    payload: str = ""


class EventEvidenceRow(_ResearchRow, table=True):
    evidence_id: str = Field(index=True)
    event_id: str = Field(index=True)
    symbol: str = Field(index=True)
    layer: str = "event"
    feature: str = ""
    z_score: float = 0.0
    direction: str = "FLAT"
    confidence: float = 0.0
    contribution: float = 0.0
    regime: str = "unknown"
    actual_move_pct: Optional[float] = None
    realized_vol: Optional[float] = None
    payload: str = ""


class SignalRow(_ResearchRow, table=True):
    signal_id: str = Field(index=True)
    event_id: str = Field(index=True, default="")
    symbol: str = Field(index=True)
    direction: str = "FLAT"
    confidence: float = 0.0
    fused_score: float = 0.0
    regime: str = "unknown"
    evidence_ids: str = "[]"
    payload: str = ""


class ThesisRow(_ResearchRow, table=True):
    thesis_id: str = Field(index=True)
    signal_id: str = Field(default="", index=True)
    event_id: str = Field(default="", index=True)
    symbol: str = Field(index=True)
    direction: str = "FLAT"
    confidence: float = 0.0
    fused_score: float = 0.0
    regime: str = "unknown"
    payload: str = ""


class ThesisStressTestRow(_ResearchRow, table=True):
    stress_id: str = Field(index=True)
    thesis_id: str = Field(index=True)
    symbol: str = Field(index=True)
    baseline_confidence: float = 0.0
    mean_perturbed_confidence: float = 0.0
    worst_case_confidence: float = 0.0
    robustness: float = 0.0
    fragility: float = 0.0
    payload: str = ""


class PredictionRow(_ResearchRow, table=True):
    prediction_id: str = Field(index=True)
    thesis_id: str = Field(default="", index=True)
    signal_id: str = Field(default="", index=True)
    event_id: str = Field(default="", index=True)
    symbol: str = Field(index=True)
    direction: str = "FLAT"
    confidence: float = 0.0
    entry_price: float = 0.0
    expected_move_pct: float = 0.0
    horizon: str = "1h"
    expires_at: Optional[datetime] = Field(default=None, index=True)
    regime: str = "unknown"
    status: str = Field(default="open", index=True)
    payload: str = ""


class PredictionOutcomeRow(_ResearchRow, table=True):
    outcome_id: str = Field(index=True)
    prediction_id: str = Field(index=True)
    symbol: str = Field(index=True)
    exit_price: float = 0.0
    actual_move_pct: float = 0.0
    expected_move_pct: float = 0.0
    error_pct: float = 0.0
    correct: bool = False
    realized_vol: Optional[float] = None
    resolution_source: str = ""


class PredictionAutopsyRow(_ResearchRow, table=True):
    autopsy_id: str = Field(index=True)
    prediction_id: str = Field(index=True)
    symbol: str = Field(index=True)
    failure_mode: str = "unclassified"
    mode_likelihood: float = 0.0
    error_pct: float = 0.0
    issued_regime: str = "unknown"
    realized_regime: Optional[str] = None
    payload: str = ""


class ExperimentRow(_ResearchRow, table=True):
    experiment_id: str = Field(index=True)
    name: str = ""
    status: str = "draft"
    window_label: str = ""
    window_start: str = ""
    window_end: str = ""
    n_observations: int = 0
    seed: int = 7
    features_enabled: str = "[]"
    features_disabled: str = "[]"
    methodology: str = ""
    fingerprint: str = ""


class ExperimentResultRow(_ResearchRow, table=True):
    result_id: str = Field(index=True)
    experiment_id: str = Field(index=True)
    n: int = 0
    n_decisions: int = 0
    directional_accuracy: Optional[float] = None
    mean_abs_error_pct: Optional[float] = None
    brier_score: Optional[float] = None
    sharpe: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    turnover: Optional[float] = None
    payload: str = ""


class ModelVersionRow(SQLModel, table=True):
    """Registry of fusion model versions, so evidence stays attributable."""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    model_version: str = Field(index=True)
    description: str = ""
    priors: str = "{}"
    active: bool = True


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
    """Create tables if missing, then apply additive migrations. Never raises."""
    try:
        SQLModel.metadata.create_all(get_engine())
        added = _migrate_additive()
        out = {"status": "ok", **engine_info()}
        if added:
            out["migrations"] = added
        return out
    except Exception as e:
        return {"status": "error", "error": str(e)[:200], **engine_info()}


#: Columns added after a table first shipped. Applied with ALTER TABLE so an
#: existing deployment keeps its data — no destructive schema changes.
_ADDITIVE_COLUMNS: Dict[str, Dict[str, str]] = {
    "market_events": {"probability": "REAL", "themes": "TEXT"},
    "event_evidence": {"actual_move_pct": "REAL", "realized_vol": "REAL",
                       "regime": "TEXT", "contribution": "REAL"},
    "signals": {"event_id": "TEXT", "fused_score": "REAL", "regime": "TEXT"},
    "theses": {"event_id": "TEXT", "signal_id": "TEXT", "fused_score": "REAL",
               "regime": "TEXT"},
    "predictions": {"signal_id": "TEXT", "event_id": "TEXT", "regime": "TEXT",
                    "status": "TEXT"},
    "experiments": {"fingerprint": "TEXT", "seed": "INTEGER", "methodology": "TEXT"},
}

_POSTGRES_SERIAL = "SERIAL PRIMARY KEY"


def _migrate_additive() -> List[str]:
    """Add missing columns without dropping or rewriting anything."""
    added: List[str] = []
    try:
        engine = get_engine()
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        present = set(inspector.get_table_names())
        with engine.begin() as conn:
            for table, columns in _ADDITIVE_COLUMNS.items():
                if table not in present:
                    continue
                existing = {c["name"] for c in inspector.get_columns(table)}
                for name, coltype in columns.items():
                    if name in existing:
                        continue
                    ddl = (f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"
                           if _engine_backend == "postgres"
                           else f"ALTER TABLE {table} ADD COLUMN {name} {coltype}")
                    conn.execute(text(ddl))
                    added.append(f"{table}.{name}")
    except Exception:
        # A failed migration must never stop the service; create_all already
        # guaranteed the new tables exist for fresh databases.
        return added
    return added


def mode_from_str(v: Any) -> DataMode:
    """Parse a stored data_mode. Tolerant of str(enum) leftovers.

    `str(DataMode.SIMULATED)` yields "DataMode.SIMULATED" on Python 3.12,
    which is not a valid enum value. Accept the value, the name, or the
    str(enum) form so old rows never 500 the read path.
    """
    if isinstance(v, DataMode):
        return v
    s = str(v).strip()
    if not s:
        return DataMode.MOCK
    try:
        return DataMode(s)
    except ValueError:
        pass
    if s.startswith("DataMode."):
        try:
            return DataMode(s.split(".", 1)[1].lower())
        except ValueError:
            pass
    return DataMode.MOCK


def _mode_str(v: Any) -> str:
    """Store the enum *value*, never str(enum) (which yields 'DataMode.X')."""
    if isinstance(v, DataMode):
        return v.value
    return mode_from_str(v).value


def _mode_of(record: Dict[str, Any]) -> DataMode:
    return mode_from_str(record.get("data_mode", "mock"))


def _json(value: Any) -> str:
    import json
    try:
        return json.dumps(value, default=str)
    except Exception:
        return "{}"


def _unjson(value: Optional[str]) -> Any:
    import json
    if not value:
        return {}
    try:
        return json.loads(value)
    except Exception:
        return {}


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


# ------------------------- Research loop writes -----------------------------

def _upsert(row) -> bool:
    try:
        with Session(get_engine()) as session:
            session.add(row)
            session.commit()
        return True
    except Exception:
        return False


def save_market_event(event: Dict[str, Any]) -> bool:
    return _upsert(MarketEventRow(
        event_id=str(event.get("event_id", "")),
        symbol=str(event.get("symbol", "")).upper(),
        event_type=str(event.get("event_type", "market")),
        category=str(event.get("category", "company")),
        headline=str(event.get("headline", ""))[:400],
        probability=event.get("probability"),
        magnitude=float(event.get("magnitude", 0.0) or 0.0),
        confidence=float(event.get("confidence", 0.0) or 0.0),
        direction=str(event.get("direction", "FLAT")),
        themes=_json(event.get("themes", [])),
        data_mode=_mode_str(event.get("data_mode", "mock")),
        model_version=str(event.get("model_version", "qp-fusion-1.0")),
        payload=_json(event),
    ))


def save_evidence(rows: List[Dict[str, Any]]) -> int:
    """Persist evidence. `actual_move_pct` is what makes an observation
    usable as a tournament sample, so the loop writes it once resolved."""
    if not rows:
        return 0
    out = [EventEvidenceRow(
        evidence_id=str(r.get("evidence_id", "")),
        event_id=str(r.get("event_id", "")),
        symbol=str(r.get("symbol", "")).upper(),
        layer=str(r.get("layer", "event")),
        feature=str(r.get("feature", "")),
        z_score=float(r.get("z_score", 0.0) or 0.0),
        direction=str(r.get("direction", "FLAT")),
        confidence=float(r.get("confidence", 0.0) or 0.0),
        contribution=float(r.get("contribution", 0.0) or 0.0),
        regime=str(r.get("regime", "unknown")),
        actual_move_pct=r.get("actual_move_pct"),
        realized_vol=r.get("realized_vol"),
        data_mode=_mode_str(r.get("data_mode", "mock")),
        model_version=str(r.get("model_version", "qp-fusion-1.0")),
        payload=_json(r),
    ) for r in rows]
    try:
        with Session(get_engine()) as session:
            session.add_all(out)
            session.commit()
        return len(out)
    except Exception:
        return 0


def save_signal(signal: Dict[str, Any]) -> bool:
    return _upsert(SignalRow(
        signal_id=str(signal.get("signal_id", "")),
        event_id=str(signal.get("event_id", "")),
        symbol=str(signal.get("symbol", "")).upper(),
        direction=str(signal.get("direction", "FLAT")),
        confidence=float(signal.get("confidence", 0.0) or 0.0),
        fused_score=float(signal.get("fused_score", 0.0) or 0.0),
        regime=str(signal.get("regime", "unknown")),
        evidence_ids=_json(signal.get("evidence_ids", [])),
        data_mode=_mode_str(signal.get("data_mode", "mock")),
        model_version=str(signal.get("model_version", "qp-fusion-1.0")),
        payload=_json(signal),
    ))


def save_thesis(thesis: Dict[str, Any]) -> bool:
    return _upsert(ThesisRow(
        thesis_id=str(thesis.get("thesis_id", "")),
        signal_id=str(thesis.get("signal_id", "")),
        event_id=str(thesis.get("event_id", "")),
        symbol=str(thesis.get("symbol", "")).upper(),
        direction=str(thesis.get("direction", "FLAT")),
        confidence=float(thesis.get("confidence", 0.0) or 0.0),
        fused_score=float(thesis.get("fused_score", 0.0) or 0.0),
        regime=str(thesis.get("regime", "unknown")),
        data_mode=_mode_str(thesis.get("data_mode", "mock")),
        model_version=str(thesis.get("model_version", "qp-fusion-1.0")),
        payload=_json(thesis),
    ))


def save_stress_test(test: Dict[str, Any]) -> bool:
    return _upsert(ThesisStressTestRow(
        stress_id=str(test.get("stress_id", "")),
        thesis_id=str(test.get("thesis_id", "")),
        symbol=str(test.get("symbol", "")).upper(),
        baseline_confidence=float(test.get("baseline_confidence", 0.0) or 0.0),
        mean_perturbed_confidence=float(test.get("mean_perturbed_confidence", 0.0) or 0.0),
        worst_case_confidence=float(test.get("worst_case_confidence", 0.0) or 0.0),
        robustness=float(test.get("robustness", 0.0) or 0.0),
        fragility=float(test.get("fragility", 0.0) or 0.0),
        data_mode=_mode_str(test.get("data_mode", "mock")),
        model_version=str(test.get("model_version", "qp-fusion-1.0")),
        payload=_json(test),
    ))


def save_prediction(pred: Dict[str, Any]) -> bool:
    expires = pred.get("expires_at")
    exp_dt = None
    if expires:
        try:
            from datetime import datetime as _dt
            exp_dt = _dt.fromisoformat(str(expires))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        except Exception:
            exp_dt = None
    return _upsert(PredictionRow(
        prediction_id=str(pred.get("prediction_id", "")),
        thesis_id=str(pred.get("thesis_id", "")),
        signal_id=str(pred.get("signal_id", "")),
        event_id=str(pred.get("event_id", "")),
        symbol=str(pred.get("symbol", "")).upper(),
        direction=str(pred.get("direction", "FLAT")),
        confidence=float(pred.get("confidence", 0.0) or 0.0),
        entry_price=float(pred.get("entry_price", 0.0) or 0.0),
        expected_move_pct=float(pred.get("expected_move_pct", 0.0) or 0.0),
        horizon=str(pred.get("horizon", "1h")),
        expires_at=exp_dt,
        regime=str(pred.get("regime", "unknown")),
        status=str(pred.get("status", "open")),
        data_mode=_mode_str(pred.get("data_mode", "mock")),
        model_version=str(pred.get("model_version", "qp-fusion-1.0")),
        payload=_json(pred),
    ))


def mark_prediction_resolved(prediction_id: str) -> bool:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(PredictionRow).where(
                    PredictionRow.prediction_id == prediction_id)).first()
            if row is None:
                return False
            row.status = "resolved"
            row.updated_at = _utcnow()
            session.add(row)
            session.commit()
        return True
    except Exception:
        return False


def save_outcome(outcome: Dict[str, Any]) -> bool:
    return _upsert(PredictionOutcomeRow(
        outcome_id=str(outcome.get("outcome_id", "")),
        prediction_id=str(outcome.get("prediction_id", "")),
        symbol=str(outcome.get("symbol", "")).upper(),
        exit_price=float(outcome.get("exit_price", 0.0) or 0.0),
        actual_move_pct=float(outcome.get("actual_move_pct", 0.0) or 0.0),
        expected_move_pct=float(outcome.get("expected_move_pct", 0.0) or 0.0),
        error_pct=float(outcome.get("error_pct", 0.0) or 0.0),
        correct=bool(outcome.get("correct", False)),
        realized_vol=outcome.get("realized_vol"),
        resolution_source=str(outcome.get("resolution_source", ""))[:200],
        data_mode=_mode_str(outcome.get("data_mode", "mock")),
    ))


def save_autopsy(autopsy: Dict[str, Any]) -> bool:
    return _upsert(PredictionAutopsyRow(
        autopsy_id=str(autopsy.get("autopsy_id", "")),
        prediction_id=str(autopsy.get("prediction_id", "")),
        symbol=str(autopsy.get("symbol", "")).upper(),
        failure_mode=str(autopsy.get("failure_mode", "unclassified")),
        mode_likelihood=float(autopsy.get("mode_likelihood", 0.0) or 0.0),
        error_pct=float(autopsy.get("error_pct", 0.0) or 0.0),
        issued_regime=str(autopsy.get("issued_regime", "unknown")),
        realized_regime=autopsy.get("realized_regime"),
        data_mode=_mode_str(autopsy.get("data_mode", "mock")),
        model_version=str(autopsy.get("model_version", "qp-fusion-1.0")),
        payload=_json(autopsy),
    ))


def save_experiment(spec: Dict[str, Any]) -> bool:
    return _upsert(ExperimentRow(
        experiment_id=str(spec.get("experiment_id", "")),
        name=str(spec.get("name", "")),
        status=str(spec.get("status", "draft")),
        window_label=str((spec.get("window") or {}).get("label", "")),
        window_start=str((spec.get("window") or {}).get("start", "")),
        window_end=str((spec.get("window") or {}).get("end", "")),
        n_observations=int((spec.get("window") or {}).get("n_observations", 0) or 0),
        seed=int((spec.get("window") or {}).get("seed", 7) or 7),
        features_enabled=_json([f.value for f in
                                (spec.get("features_enabled") or [])]
                               if spec.get("features_enabled")
                               and not isinstance(spec.get("features_enabled")[0], str)
                               else spec.get("features_enabled", [])),
        features_disabled=_json([f.value for f in
                                 (spec.get("features_disabled") or [])]
                                if spec.get("features_disabled")
                                and not isinstance(spec.get("features_disabled")[0], str)
                                else spec.get("features_disabled", [])),
        methodology=str((spec.get("methodology") or {}).get("name", "")),
        fingerprint=str(spec.get("fingerprint", "")),
        data_mode=_mode_str(spec.get("data_mode", "mock")),
        model_version=str(spec.get("model_version", "qp-fusion-1.0")),
    ))


def save_experiment_result(result: Dict[str, Any]) -> bool:
    overall = result.get("overall") or {}
    return _upsert(ExperimentResultRow(
        result_id=f"rs_{result.get('experiment_id', '')}",
        experiment_id=str(result.get("experiment_id", "")),
        n=int(overall.get("n", 0) or 0),
        n_decisions=int(overall.get("n_decisions", 0) or 0),
        directional_accuracy=overall.get("directional_accuracy"),
        mean_abs_error_pct=overall.get("mean_abs_error_pct"),
        brier_score=overall.get("brier_score"),
        sharpe=overall.get("sharpe"),
        max_drawdown_pct=overall.get("max_drawdown_pct"),
        turnover=overall.get("turnover"),
        data_mode=_mode_str(result.get("data_mode", "mock")),
        model_version=str(result.get("model_version", "qp-fusion-1.0")),
        payload=_json(result),
    ))


def register_model_version(version: str, description: str = "",
                           priors: Optional[Dict[str, Any]] = None) -> bool:
    try:
        with Session(get_engine()) as session:
            existing = session.exec(
                select(ModelVersionRow).where(
                    ModelVersionRow.model_version == version)).first()
            if existing is not None:
                return True
            session.add(ModelVersionRow(
                model_version=version, description=description[:400],
                priors=_json(priors or {}), active=True))
            session.commit()
        return True
    except Exception:
        return False


# ------------------------- Research loop reads ------------------------------

def list_market_events(limit: int = 50,
                       symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            q = select(MarketEventRow).order_by(MarketEventRow.id.desc())
            if symbol:
                q = q.where(MarketEventRow.symbol == symbol.upper())
            rows = list(session.exec(q.limit(max(1, min(limit, 500)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def get_market_event(event_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(MarketEventRow).where(
                    MarketEventRow.event_id == event_id)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def list_evidence(event_id: Optional[str] = None,
                  symbol: Optional[str] = None,
                  limit: int = 500) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            q = select(EventEvidenceRow).order_by(EventEvidenceRow.id.desc())
            if event_id:
                q = q.where(EventEvidenceRow.event_id == event_id)
            if symbol:
                q = q.where(EventEvidenceRow.symbol == symbol.upper())
            rows = list(session.exec(q.limit(max(1, min(limit, 2000)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def get_research_evidence(limit: int = 200) -> List[Dict[str, Any]]:
    """Evidence rows that carry a realized move — i.e. usable as an
    experiment sample. Rows without one are not silently treated as zero."""
    try:
        rows = list_evidence(limit=limit * 5)
        usable = [r for r in rows if r.get("actual_move_pct") is not None]
        return usable[: max(1, limit)]
    except Exception:
        return []


def get_thesis(thesis_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(ThesisRow).where(ThesisRow.thesis_id == thesis_id)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def latest_thesis(symbol: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            q = select(ThesisRow).order_by(ThesisRow.id.desc())
            if symbol:
                q = q.where(ThesisRow.symbol == symbol.upper())
            row = session.exec(q.limit(1)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def latest_stress_test(thesis_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(ThesisStressTestRow).where(
                    ThesisStressTestRow.thesis_id == thesis_id)
                .order_by(ThesisStressTestRow.id.desc()).limit(1)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def list_predictions(limit: int = 100, symbol: Optional[str] = None,
                     status: Optional[str] = None) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            q = select(PredictionRow).order_by(PredictionRow.id.desc())
            if symbol:
                q = q.where(PredictionRow.symbol == symbol.upper())
            if status:
                q = q.where(PredictionRow.status == status)
            rows = list(session.exec(q.limit(max(1, min(limit, 500)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def get_prediction(prediction_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(PredictionRow).where(
                    PredictionRow.prediction_id == prediction_id)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def get_outcome(prediction_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(PredictionOutcomeRow).where(
                    PredictionOutcomeRow.prediction_id == prediction_id)
                .order_by(PredictionOutcomeRow.id.desc()).limit(1)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def get_autopsy(prediction_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(PredictionAutopsyRow).where(
                    PredictionAutopsyRow.prediction_id == prediction_id)
                .order_by(PredictionAutopsyRow.id.desc()).limit(1)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def list_autopsies(limit: int = 200) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            rows = list(session.exec(
                select(PredictionAutopsyRow)
                .order_by(PredictionAutopsyRow.id.desc())
                .limit(max(1, min(limit, 1000)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def resolved_pairs(limit: int = 500) -> List[Dict[str, Any]]:
    """Predictions joined to their outcomes — the analysis input set."""
    try:
        preds = {p["prediction_id"]: p for p in list_predictions(limit=limit * 2)}
        out: List[Dict[str, Any]] = []
        for outcome in list_outcomes(limit=limit * 2):
            pred = preds.get(outcome["prediction_id"])
            if pred:
                out.append({"prediction": pred, "outcome": outcome})
        return out[: max(1, limit)]
    except Exception:
        return []


def list_outcomes(limit: int = 500) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            rows = list(session.exec(
                select(PredictionOutcomeRow)
                .order_by(PredictionOutcomeRow.id.desc())
                .limit(max(1, min(limit, 1000)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def list_experiments(limit: int = 50) -> List[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            rows = list(session.exec(
                select(ExperimentRow).order_by(ExperimentRow.id.desc())
                .limit(max(1, min(limit, 200)))))
        return [_dump(r) for r in rows]
    except Exception:
        return []


def get_experiment(experiment_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(ExperimentRow).where(
                    ExperimentRow.experiment_id == experiment_id)).first()
            return _dump(row) if row else None
    except Exception:
        return None


def get_experiment_result(experiment_id: str) -> Optional[Dict[str, Any]]:
    try:
        with Session(get_engine()) as session:
            row = session.exec(
                select(ExperimentResultRow).where(
                    ExperimentResultRow.experiment_id == experiment_id)
                .order_by(ExperimentResultRow.id.desc()).limit(1)).first()
            return _dump(row) if row else None
    except Exception:
        return None
