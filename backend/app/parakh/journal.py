"""
Parakh — trade journal.

Imports executions (Zerodha Console tradebook CSV, a generic CSV, or the
Kite Connect API), pairs them into round trips FIFO (long and short), and
computes behaviour statistics: win rate, average win vs loss, holding time
of winners vs losers (the disposition effect), and over-trading.
"""
from __future__ import annotations

import csv
import hashlib
import io
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from app.parakh import universe

#: Indian broker exports are in IST; naive timestamps are read as IST.
IST = timezone(timedelta(hours=5, minutes=30))

MAX_ROWS = 20000


class CsvError(ValueError):
    pass


def _parse_dt(value: str) -> datetime:
    v = (value or "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(v[:19], fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value.strip())
        return dt if dt.tzinfo else dt.replace(tzinfo=IST)
    except ValueError:
        raise CsvError(f"Unrecognised date: {value!r}")


def _num(v: Any) -> float:
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        raise CsvError(f"Not a number: {v!r}")


def _key(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:32]


def parse_csv(text: str) -> Tuple[List[Dict[str, Any]], str]:
    """Return (trades, detected_format). Raises CsvError with a readable message."""
    if not text.strip():
        raise CsvError("The file is empty.")
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    fields = {(f or "").strip().lower(): f for f in (reader.fieldnames or [])}
    def col(*names: str) -> Optional[str]:
        for n in names:
            if n in fields:
                return fields[n]
        return None
    sym_c = col("symbol", "tradingsymbol", "scrip", "instrument", "stock")
    side_c = col("trade_type", "side", "type", "transaction_type", "buy/sell", "action")
    qty_c = col("quantity", "qty", "shares")
    px_c = col("price", "trade_price", "avg_price", "average_price", "rate")
    dt_c = col("order_execution_time", "trade_date", "date", "datetime", "time", "executed_at", "fill_timestamp")
    if not all([sym_c, side_c, qty_c, px_c, dt_c]):
        raise CsvError("Couldn't find the columns we need. Expected symbol, side (buy/sell), "
                       "quantity, price and date. Zerodha Console → Reports → Tradebook "
                       "exports work as-is.")
    fmt = "zerodha_tradebook" if col("trade_id") and col("order_execution_time") else "generic"
    id_c, ord_c = col("trade_id"), col("order_id")
    exch_c, seg_c = col("exchange"), col("segment")
    out: List[Dict[str, Any]] = []
    for n, row in enumerate(reader, start=2):
        if n > MAX_ROWS:
            raise CsvError(f"File has more than {MAX_ROWS} rows; split it.")
        if not (row.get(sym_c) or "").strip():
            continue
        side_raw = (row.get(side_c) or "").strip().lower()
        side = "BUY" if side_raw in ("buy", "b", "long") else "SELL" if side_raw in ("sell", "s", "short") else None
        if side is None:
            raise CsvError(f"Row {n}: side must be buy or sell, got {row.get(side_c)!r}")
        # Zerodha splits date and time across trade_date / order_execution_time
        when = row.get(dt_c) or row.get(col("trade_date") or "", "")
        qty, price = abs(_num(row.get(qty_c))), _num(row.get(px_c))
        if qty <= 0 or price <= 0:
            continue
        sym = universe.normalize((row.get(sym_c) or "").split("-")[0] if fmt == "zerodha_tradebook"
                                 and (row.get(seg_c) or "EQ").upper() == "EQ" else (row.get(sym_c) or ""))
        executed = _parse_dt(when)
        tid = (row.get(id_c) or "").strip() if id_c else ""
        out.append({
            "dedupe_key": f"z:{tid}" if tid else _key(sym, side, qty, price, executed.isoformat()),
            "broker": "zerodha" if fmt == "zerodha_tradebook" else "csv",
            "symbol": sym, "exchange": ((row.get(exch_c) or "NSE").strip().upper() if exch_c else "NSE"),
            "segment": ((row.get(seg_c) or "EQ").strip().upper() if seg_c else "EQ"),
            "side": side, "qty": qty, "price": price, "executed_at": executed,
            "order_id": (row.get(ord_c) or "").strip() if ord_c else "",
        })
    if not out:
        raise CsvError("No trades found in the file.")
    return out, fmt


def round_trips(trades: Iterable[Any]) -> List[Dict[str, Any]]:
    """FIFO-pair executions into closed round trips (supports shorts)."""
    books: Dict[str, Deque[List[Any]]] = defaultdict(deque)  # symbol -> [[side, qty, price, dt, thesis]]
    trips: List[Dict[str, Any]] = []
    for t in sorted(trades, key=lambda x: _get(x, "executed_at")):
        sym, side = _get(t, "symbol"), _get(t, "side")
        qty, price, dt = float(_get(t, "qty")), float(_get(t, "price")), _get(t, "executed_at")
        book = books[sym]
        while qty > 1e-9 and book and book[0][0] != side:
            lot = book[0]
            m = min(qty, lot[1])
            direction = "LONG" if lot[0] == "BUY" else "SHORT"
            entry, exit_ = lot[2], price
            pnl = (exit_ - entry) * m * (1 if direction == "LONG" else -1)
            trips.append({
                "symbol": sym, "direction": direction, "qty": m,
                "entry_price": round(entry, 4), "exit_price": round(exit_, 4),
                "entry_at": _iso(lot[3]), "exit_at": _iso(dt),
                "holding_days": round(max(0.0, (_dt(dt) - _dt(lot[3])).total_seconds() / 86400), 2),
                "pnl": round(pnl, 2),
                "return_pct": round((exit_ / entry - 1) * 100 * (1 if direction == "LONG" else -1), 2),
                "thesis_id": lot[4] or _get(t, "thesis_id"),
            })
            lot[1] -= m
            qty -= m
            if lot[1] <= 1e-9:
                book.popleft()
        if qty > 1e-9:
            book.append([side, qty, price, dt, _get(t, "thesis_id")])
    trips.sort(key=lambda r: r["exit_at"])
    return trips


def open_positions(trades: Iterable[Any]) -> List[Dict[str, Any]]:
    books: Dict[str, float] = defaultdict(float)
    cost: Dict[str, float] = defaultdict(float)
    for t in sorted(trades, key=lambda x: _get(x, "executed_at")):
        q = float(_get(t, "qty")) * (1 if _get(t, "side") == "BUY" else -1)
        books[_get(t, "symbol")] += q
        cost[_get(t, "symbol")] += q * float(_get(t, "price"))
    return [{"symbol": s, "qty": round(q, 4), "direction": "LONG" if q > 0 else "SHORT",
             "avg_price": round(abs(cost[s] / q), 2) if q else 0}
            for s, q in books.items() if abs(q) > 1e-9]


def stats(trips: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(trips)
    if n == 0:
        return {"n": 0}
    wins = [t for t in trips if t["pnl"] > 0]
    losses = [t for t in trips if t["pnl"] <= 0]
    avg = lambda xs, k: round(sum(x[k] for x in xs) / len(xs), 2) if xs else 0.0
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    hold_w, hold_l = avg(wins, "holding_days"), avg(losses, "holding_days")
    days = {t["exit_at"][:10] for t in trips}
    per_day = n / max(1, len(days))
    insights: List[str] = []
    if wins and losses and hold_l > hold_w * 1.5 and hold_l - hold_w > 0.5:
        insights.append(f"You hold losers {hold_l:.1f} days vs winners {hold_w:.1f} days — the classic "
                        "'cut winners, ride losers' pattern (disposition effect).")
    if wins and losses and abs(avg(losses, "pnl")) > avg(wins, "pnl") * 1.5:
        insights.append(f"Your average loss (₹{abs(avg(losses, 'pnl')):,.0f}) is much bigger than your "
                        f"average win (₹{avg(wins, 'pnl'):,.0f}). Tighter, pre-planned exits would help.")
    if per_day > 6:
        insights.append(f"About {per_day:.0f} round trips per active day — costs and impulsive trades add up.")
    worst = sorted(trips, key=lambda t: t["pnl"])[:3]
    by_sym: Dict[str, float] = defaultdict(float)
    for t in trips:
        by_sym[t["symbol"]] += t["pnl"]
    return {
        "n": n, "wins": len(wins), "losses": len(losses),
        "win_rate": round(len(wins) / n, 3),
        "net_pnl": round(sum(t["pnl"] for t in trips), 2),
        "avg_win": avg(wins, "pnl"), "avg_loss": avg(losses, "pnl"),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "avg_hold_winners_days": hold_w, "avg_hold_losers_days": hold_l,
        "trades_per_active_day": round(per_day, 2),
        "worst_trades": worst,
        "by_symbol": sorted(({"symbol": k, "pnl": round(v, 2)} for k, v in by_sym.items()),
                            key=lambda r: r["pnl"]),
        "insights": insights,
        "note": "P&L is before brokerage, STT and other charges.",
    }


def _get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def _dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return _parse_dt(str(v))


def _iso(v: Any) -> str:
    return _dt(v).isoformat()
