"""
Parakh — Feature 2: Zerodha Kite Connect sync.

Flow: user clicks Connect → Kite login → Kite redirects to our frontend with
?request_token=… → backend exchanges it (checksum = SHA-256(api_key +
request_token + api_secret)) for an access token, stored encrypted.

Kite access tokens expire every morning (~06:00 IST) and the /trades
endpoint only returns the current day's executions, so Parakh syncs daily
and uses the Console tradebook CSV for history.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.config import get_settings
from app.parakh import crypto, journal, store, universe
from app.parakh.models import BrokerConnectionRow

API = "https://api.kite.trade"
LOGIN = "https://kite.zerodha.com/connect/login"


class KiteError(RuntimeError):
    pass


def configured() -> bool:
    s = get_settings()
    return bool(s.KITE_API_KEY and s.KITE_API_SECRET)


def login_url(state: str = "") -> str:
    if not configured():
        raise KiteError("Zerodha Kite Connect is not configured on this server.")
    url = f"{LOGIN}?v=3&api_key={get_settings().KITE_API_KEY}"
    return url + (f"&redirect_params=state%3D{state}" if state else "")


def _headers(access_token: str = "") -> Dict[str, str]:
    h = {"X-Kite-Version": "3"}
    if access_token:
        h["Authorization"] = f"token {get_settings().KITE_API_KEY}:{access_token}"
    return h


def exchange(user_id: str, request_token: str) -> Dict[str, Any]:
    s = get_settings()
    if not configured():
        raise KiteError("Zerodha Kite Connect is not configured on this server.")
    checksum = hashlib.sha256(f"{s.KITE_API_KEY}{request_token}{s.KITE_API_SECRET}".encode()).hexdigest()
    r = httpx.post(f"{API}/session/token", headers=_headers(),
                   data={"api_key": s.KITE_API_KEY, "request_token": request_token, "checksum": checksum},
                   timeout=15)
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code != 200 or body.get("status") != "success":
        raise KiteError(body.get("message") or f"Kite login failed ({r.status_code}).")
    data = body["data"]
    store.save_broker(BrokerConnectionRow(user_id=user_id, broker="zerodha",
                                          broker_user_id=str(data.get("user_id", "")),
                                          access_token_enc=crypto.encrypt(data["access_token"])))
    return {"connected": True, "broker_user_id": data.get("user_id")}


def sync_trades(user_id: str) -> Dict[str, Any]:
    conn = store.get_broker(user_id, "zerodha")
    if not conn:
        raise KiteError("Zerodha is not connected.")
    token = crypto.decrypt(conn.access_token_enc)
    r = httpx.get(f"{API}/trades", headers=_headers(token), timeout=15)
    if r.status_code == 403:
        raise KiteError("Your Zerodha session expired (they reset every morning). Reconnect to sync.")
    body = r.json()
    if r.status_code != 200 or body.get("status") != "success":
        raise KiteError(body.get("message") or f"Kite sync failed ({r.status_code}).")
    trades: List[Dict[str, Any]] = []
    for t in body.get("data", []):
        when = t.get("fill_timestamp") or t.get("exchange_timestamp") or t.get("order_timestamp")
        trades.append({
            "dedupe_key": f"z:{t.get('trade_id')}", "broker": "zerodha",
            "symbol": universe.normalize(str(t.get("tradingsymbol", ""))),
            "exchange": str(t.get("exchange", "NSE")),
            "segment": "EQ" if t.get("exchange") in ("NSE", "BSE") else "FO",
            "side": str(t.get("transaction_type", "BUY")).upper(),
            "qty": float(t.get("quantity", 0)), "price": float(t.get("average_price", 0)),
            "executed_at": journal._parse_dt(str(when)), "order_id": str(t.get("order_id", "")),
        })
    res = store.add_trades(user_id, trades)
    conn.last_sync_at = datetime.now(timezone.utc)
    store.save_broker(conn)
    return {**res, "fetched": len(trades),
            "note": "Kite returns today's trades only; import Console tradebook CSV for history."}
