"""Parakh — user-scoped persistence helpers. Every function takes user_id."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from app import database as db
from app.parakh.models import (AlertLogRow, BrokerConnectionRow, JournalTradeRow,
                               ThesisCheckRow, UserRulesRow, UserSettingsRow, WatchlistRow)


def session() -> Session:
    return Session(db.get_engine())


def dump(row) -> Dict[str, Any]:
    d = row.model_dump()
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.replace(tzinfo=v.tzinfo or timezone.utc).isoformat()
    for k in ("report", "autopsy"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k]) if d[k] else None
            except ValueError:
                d[k] = None
    return d


# theses --------------------------------------------------------------------

def save_thesis(row: ThesisCheckRow) -> ThesisCheckRow:
    with session() as s:
        s.add(row)
        s.commit()
        s.refresh(row)
        return row


def get_thesis(user_id: str, thesis_id: str) -> Optional[ThesisCheckRow]:
    with session() as s:
        row = s.get(ThesisCheckRow, thesis_id)
        return row if row and row.user_id == user_id else None


def list_theses(user_id: str, status: Optional[str] = None, limit: int = 100) -> List[ThesisCheckRow]:
    with session() as s:
        q = select(ThesisCheckRow).where(ThesisCheckRow.user_id == user_id)
        if status:
            q = q.where(ThesisCheckRow.status == status)
        return list(s.exec(q.order_by(ThesisCheckRow.created_at.desc()).limit(limit)))


def list_theses_all_open(limit: int = 5000) -> List[ThesisCheckRow]:
    with session() as s:
        return list(s.exec(select(ThesisCheckRow).where(ThesisCheckRow.status == "open").limit(limit)))


def update_thesis(row: ThesisCheckRow) -> None:
    with session() as s:
        s.merge(row)
        s.commit()


# trades --------------------------------------------------------------------

def add_trades(user_id: str, trades: List[Dict[str, Any]]) -> Dict[str, int]:
    added = skipped = 0
    with session() as s:
        existing = set(s.exec(select(JournalTradeRow.dedupe_key)
                              .where(JournalTradeRow.user_id == user_id)))
        for t in trades:
            if t["dedupe_key"] in existing:
                skipped += 1
                continue
            s.add(JournalTradeRow(user_id=user_id, **t))
            existing.add(t["dedupe_key"])
            added += 1
        s.commit()
    return {"added": added, "skipped_duplicates": skipped}


def list_trades(user_id: str, limit: int = 5000) -> List[JournalTradeRow]:
    with session() as s:
        q = (select(JournalTradeRow).where(JournalTradeRow.user_id == user_id)
             .order_by(JournalTradeRow.executed_at).limit(limit))
        return list(s.exec(q))


def delete_trades(user_id: str) -> int:
    with session() as s:
        rows = list(s.exec(select(JournalTradeRow).where(JournalTradeRow.user_id == user_id)))
        for r in rows:
            s.delete(r)
        s.commit()
        return len(rows)


# watchlist / settings ------------------------------------------------------

def watchlist(user_id: str) -> List[str]:
    with session() as s:
        return [r.symbol for r in s.exec(select(WatchlistRow).where(WatchlistRow.user_id == user_id)
                                         .order_by(WatchlistRow.id))]


def set_watchlist(user_id: str, symbols: List[str]) -> List[str]:
    clean: List[str] = []
    for sym in symbols:
        sym = sym.upper().strip()
        if sym and sym not in clean:
            clean.append(sym)
    clean = clean[:30]
    with session() as s:
        for r in s.exec(select(WatchlistRow).where(WatchlistRow.user_id == user_id)):
            s.delete(r)
        for sym in clean:
            s.add(WatchlistRow(user_id=user_id, symbol=sym))
        s.commit()
    return clean


def all_watchlists() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    with session() as s:
        for r in s.exec(select(WatchlistRow)):
            out.setdefault(r.user_id, []).append(r.symbol)
    return out


def get_settings_row(user_id: str) -> UserSettingsRow:
    with session() as s:
        row = s.get(UserSettingsRow, user_id)
        return row or UserSettingsRow(user_id=user_id)


def save_settings_row(row: UserSettingsRow) -> UserSettingsRow:
    row.updated_at = datetime.now(timezone.utc)
    with session() as s:
        s.merge(row)
        s.commit()
    return row


def handle_taken(handle: str, user_id: str) -> bool:
    with session() as s:
        row = s.exec(select(UserSettingsRow).where(UserSettingsRow.public_handle == handle)).first()
        return bool(row and row.user_id != user_id)


# broker --------------------------------------------------------------------

def get_broker(user_id: str, broker: str = "zerodha") -> Optional[BrokerConnectionRow]:
    with session() as s:
        return s.exec(select(BrokerConnectionRow).where(BrokerConnectionRow.user_id == user_id,
                                                        BrokerConnectionRow.broker == broker)).first()


def save_broker(row: BrokerConnectionRow) -> None:
    with session() as s:
        old = s.exec(select(BrokerConnectionRow).where(BrokerConnectionRow.user_id == row.user_id,
                                                       BrokerConnectionRow.broker == row.broker)).first()
        if old:
            s.delete(old)
            s.commit()
        s.add(row)
        s.commit()


def delete_broker(user_id: str, broker: str = "zerodha") -> None:
    with session() as s:
        for r in s.exec(select(BrokerConnectionRow).where(BrokerConnectionRow.user_id == user_id,
                                                          BrokerConnectionRow.broker == broker)):
            s.delete(r)
        s.commit()


# alerts --------------------------------------------------------------------

def recent_alert(user_id: str, symbol: str, kind: str, since: datetime) -> bool:
    with session() as s:
        row = s.exec(select(AlertLogRow).where(AlertLogRow.user_id == user_id,
                                               AlertLogRow.symbol == symbol,
                                               AlertLogRow.kind == kind,
                                               AlertLogRow.created_at >= since)).first()
        return row is not None


def log_alert(user_id: str, symbol: str, kind: str, message: str, delivered: bool) -> None:
    with session() as s:
        s.add(AlertLogRow(user_id=user_id, symbol=symbol, kind=kind, message=message, delivered=delivered))
        s.commit()


def list_alerts(user_id: str, limit: int = 50) -> List[AlertLogRow]:
    with session() as s:
        return list(s.exec(select(AlertLogRow).where(AlertLogRow.user_id == user_id)
                           .order_by(AlertLogRow.created_at.desc()).limit(limit)))


# rules ---------------------------------------------------------------------

def get_rules(user_id: str) -> Dict[str, Any]:
    with session() as s:
        row = s.get(UserRulesRow, user_id)
        raw = row.rules if row else "{}"
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def save_rules(user_id: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    with session() as s:
        s.merge(UserRulesRow(user_id=user_id, rules=json.dumps(rules),
                             updated_at=datetime.now(timezone.utc)))
        s.commit()
    return rules


# account -------------------------------------------------------------------

_USER_TABLES = (("ideas", ThesisCheckRow), ("trades", JournalTradeRow), ("watchlist", WatchlistRow),
                ("settings", UserSettingsRow), ("rules", UserRulesRow),
                ("broker_connections", BrokerConnectionRow), ("alerts", AlertLogRow))


def export_user_data(user_id: str) -> Dict[str, Any]:
    """Everything stored for one user. Broker tokens are never included."""
    out: Dict[str, Any] = {}
    with session() as s:
        for name, model in _USER_TABLES:
            rows = [dump(r) for r in s.exec(select(model).where(model.user_id == user_id))]
            for r in rows:
                r.pop("access_token_enc", None)
            out[name] = rows
    return out


def delete_user_data(user_id: str) -> Dict[str, int]:
    """Delete every row stored for one user. Returns how many rows went, per table."""
    counts: Dict[str, int] = {}
    with session() as s:
        for name, model in _USER_TABLES:
            rows = list(s.exec(select(model).where(model.user_id == user_id)))
            for r in rows:
                s.delete(r)
            counts[name] = len(rows)
        s.commit()
    return counts
