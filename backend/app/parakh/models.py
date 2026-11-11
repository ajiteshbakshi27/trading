"""
Parakh — per-user tables.

Every row carries ``user_id``; every query in the Parakh routers filters by
it. Theses are append-only from the user's side: there is no edit endpoint,
and resolution is automatic, which is what makes the public track record
verifiable (see ``share.seal``).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ThesisCheckRow(SQLModel, table=True):
    __tablename__ = "parakh_theses"
    id: str = Field(primary_key=True)
    user_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now, index=True)
    symbol: str = Field(index=True)
    direction: str = "LONG"            # LONG | SHORT
    horizon_days: int = 10
    entry_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    user_confidence: float = 0.6       # what the user said (0..1)
    idea_text: str = ""
    catalyst: str = ""
    report: str = "{}"                 # JSON: full check report
    robustness: float = 0.0
    base_rate: Optional[float] = None  # historical analogue hit-rate
    data_mode: str = "live"
    status: str = Field(default="open", index=True)   # open | hit | miss | expired
    resolved_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    outcome_return_pct: Optional[float] = None
    autopsy: str = ""                  # JSON
    is_public: bool = Field(default=False, index=True)
    share_slug: Optional[str] = Field(default=None, index=True)
    seal_hash: str = ""


class JournalTradeRow(SQLModel, table=True):
    __tablename__ = "parakh_trades"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    dedupe_key: str = Field(index=True)   # broker trade id or content hash
    broker: str = "csv"
    symbol: str = Field(index=True)
    exchange: str = "NSE"
    segment: str = "EQ"
    side: str = "BUY"
    qty: float = 0.0
    price: float = 0.0
    executed_at: datetime = Field(index=True)
    order_id: str = ""
    thesis_id: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_now)


class WatchlistRow(SQLModel, table=True):
    __tablename__ = "parakh_watchlist"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    symbol: str
    created_at: datetime = Field(default_factory=_now)


class UserSettingsRow(SQLModel, table=True):
    __tablename__ = "parakh_user_settings"
    user_id: str = Field(primary_key=True)
    display_name: str = ""
    public_handle: Optional[str] = Field(default=None, index=True)
    telegram_chat_id: str = ""
    hype_alerts: bool = True
    hype_threshold: float = 2.0
    updated_at: datetime = Field(default_factory=_now)


class BrokerConnectionRow(SQLModel, table=True):
    __tablename__ = "parakh_broker_connections"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    broker: str = "zerodha"
    broker_user_id: str = ""
    access_token_enc: str = ""
    connected_at: datetime = Field(default_factory=_now)
    last_sync_at: Optional[datetime] = None


class AlertLogRow(SQLModel, table=True):
    __tablename__ = "parakh_alert_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    symbol: str
    kind: str
    message: str
    delivered: bool = False
    created_at: datetime = Field(default_factory=_now, index=True)
