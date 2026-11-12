"""
Parakh — sample tradebook for demos and the "try it" button.

SAMPLE DATA. These are invented trades, not anyone's real trading and not
market data. Prices are made up around round numbers. The file is generated
from a fixed seed so every run gives the same tradebook, in the same column
layout as a Zerodha Console tradebook export.

The invented trader has three habits on purpose, so the X-ray has something
to find: trading again right after a loss, over-trading on some days, and
holding a few losing positions for days.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import List, Tuple

SEED = 20261112
START = date(2026, 8, 3)
TRADING_DAYS = 60
LABEL = "Sample tradebook: invented trades for demonstration. Not real trading or market data."
HEADER = ("symbol,isin,trade_date,exchange,segment,series,trade_type,auction,"
          "quantity,price,trade_id,order_id,order_execution_time")

#: symbol -> made-up reference price
_BOOK = {"RELIANCE": 1340.0, "HDFCBANK": 1720.0, "INFY": 1510.0,
         "SBIN": 815.0, "TATAMOTORS": 690.0, "ICICIBANK": 1265.0}


def _days() -> List[date]:
    out, d = [], START
    while len(out) < TRADING_DAYS:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _rows() -> List[Tuple[datetime, str, str, int, float]]:
    """(time, symbol, side, qty, price) executions."""
    rng = random.Random(SEED)
    days = _days()
    rows: List[Tuple[datetime, str, str, int, float]] = []

    def trip(day: date, minute: int, hold_min: int, sym: str, qty: int, ret_pct: float,
             exit_day: date | None = None) -> datetime:
        entry_t = datetime(day.year, day.month, day.day, 9, 15) + timedelta(minutes=minute)
        ref = _BOOK[sym] * (1 + rng.uniform(-0.03, 0.03))
        entry = round(ref, 2)
        exit_ = round(entry * (1 + ret_pct / 100), 2)
        if exit_day is None:
            exit_t = entry_t + timedelta(minutes=hold_min)
        else:
            exit_t = datetime(exit_day.year, exit_day.month, exit_day.day, 9, 15) + timedelta(minutes=hold_min)
        rows.append((entry_t, sym, "buy", qty, entry))
        rows.append((exit_t, sym, "sell", qty, exit_))
        return exit_t

    syms = list(_BOOK)
    for i, day in enumerate(days):
        busy = i % 6 == 4                      # every 6th day the trader over-trades
        minute = rng.choice([4, 9, 40, 55, 70])
        planned = 2 if not busy else 6
        for k in range(planned):
            sym = rng.choice(syms)
            qty = rng.choice([20, 30, 40, 50])
            late = k >= 3
            # Planned trades: small edge. Late trades on busy days: worse.
            win = rng.random() < (0.36 if late else 0.56)
            ret = rng.uniform(0.35, 1.1) if win else -rng.uniform(0.3, 0.9)
            hold = rng.randint(20, 75)
            exit_t = trip(day, minute, hold, sym, qty, ret)
            minute += hold + rng.randint(25, 70)
            # Habit 1: after a loss, often jumps straight back in with more size.
            if not win and rng.random() < 0.6 and minute < 330:
                gap = rng.randint(3, 22)
                start = int((exit_t - datetime(day.year, day.month, day.day, 9, 15)).total_seconds() // 60) + gap
                rwin = rng.random() < 0.3
                rret = rng.uniform(0.3, 0.8) if rwin else -rng.uniform(0.6, 1.5)
                rhold = rng.randint(10, 40)
                trip(day, start, rhold, rng.choice(syms), qty * 2, rret)
                minute = max(minute, start + rhold + 20)
            if minute > 345:
                break
        # Habit 3: now and then a delivery trade that goes wrong and is held for days.
        if i % 9 == 2 and i + 9 < len(days):
            trip(day, 30, 200, "TATAMOTORS", 60, -rng.uniform(4.0, 7.5),
                 exit_day=days[i + rng.randint(6, 9)])
        if i % 11 == 5 and i + 3 < len(days):
            trip(day, 45, 120, "ICICIBANK", 40, rng.uniform(1.5, 3.0),
                 exit_day=days[i + rng.randint(1, 2)])
    rows.sort(key=lambda r: r[0])
    return rows


@lru_cache(maxsize=1)
def tradebook_csv() -> str:
    """The sample tradebook as Zerodha-style CSV text."""
    lines = [HEADER]
    for n, (t, sym, side, qty, price) in enumerate(_rows(), start=1):
        lines.append(f"{sym},INE000000000,{t:%Y-%m-%d},NSE,EQ,EQ,{side},false,{qty},{price:.2f},"
                     f"S{n:06d},O{(n + 1) // 2:06d},{t:%Y-%m-%dT%H:%M:%S}")
    return "\n".join(lines) + "\n"
