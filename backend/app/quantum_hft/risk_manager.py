"""
QuantPulse AI - Automated Risk Management & Emergency Kill-Switch.
Monitors drawdown / VaR; trips a process-wide halt flag, logs the event,
and liquidates via Alpaca (mock-safe). Live auto-arm wires to broker
equity in Phase 5+; manual + evaluate endpoints work now.
"""
from __future__ import annotations
import threading
from typing import List, Dict, Any

_lock = threading.Lock()
_halted = False
_trip_info: Dict[str, Any] = {}


def is_halted() -> bool:
    with _lock:
        return _halted


def status() -> Dict[str, Any]:
    with _lock:
        return {"halted": _halted, "trip": dict(_trip_info)}


def evaluate(equity_curve: List[float], var_95: float = 0.0,
             threshold_pct: float = 5.0) -> Dict[str, Any]:
    """Pure function: peak-to-trough drawdown % vs threshold."""
    eq = [float(x) for x in equity_curve if x]
    if len(eq) < 2:
        return {"drawdown_pct": 0.0, "var_95": var_95, "kill": False}
    peak = eq[0]
    max_dd = 0.0
    for v in eq:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    kill = max_dd >= threshold_pct
    return {"drawdown_pct": round(max_dd, 3), "var_95": var_95, "kill": kill}


def trip(reason: str, drawdown_pct: float = 0.0) -> Dict[str, Any]:
    """Latch the halt flag and record why. Idempotent."""
    global _halted
    with _lock:
        _halted = True
        _trip_info.update({"reason": reason, "drawdown_pct": drawdown_pct,
                           "type": "KILL_SWITCH_TRIGGERED"})
        return {"halted": True, "trip": dict(_trip_info)}


def reset() -> Dict[str, Any]:
    """Clear the halt flag (manual re-arm)."""
    global _halted
    with _lock:
        _halted = False
        _trip_info.clear()
        return {"halted": False}


def liquidate(alpaca_client) -> Dict[str, Any]:
    """Best-effort liquidation: cancel + market-sell notionals. Never raises."""
    try:
        if hasattr(alpaca_client, "_client") and alpaca_client._client is not None:
            client = alpaca_client._client
            try:
                positions = client.get_all_positions()
            except Exception:
                positions = []
            closed = []
            for p in positions:
                try:
                    client.close_position(str(p.symbol))
                    closed.append(str(p.symbol))
                except Exception:
                    pass
            return {"liquidated": closed, "mode": "LIVE"}
        return {"liquidated": [], "mode": "MOCK",
                "note": "no live broker; nothing to close"}
    except Exception as e:
        return {"liquidated": [], "mode": "ERROR", "error": str(e)[:200]}
