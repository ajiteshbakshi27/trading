"""
QuantPulse AI - HFT Microstructure Engine
Implements L2 order-book simulation, Order Flow Imbalance (OFI),
latency arbitrage detection, and VWAP/TWAP execution.

OFI Logic (Cont et al. 2014):
  For each level-1 quote update n:
    e_n = I(P^b_n >= P^b_{n-1}) * q^b_n - I(P^b_n <= P^b_{n-1}) * q^b_{n-1}
        - I(P^a_n <= P^a_{n-1}) * q^a_n + I(P^a_n >= P^a_{n-1}) * q^a_{n-1}
  where P^b/P^a = bid/ask price, q = size.
  Positive OFI = buying pressure -> short-term price up.
"""
from __future__ import annotations
import time
import asyncio
import random
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Deque
from collections import deque
import numpy as np

try:
    from numba import njit
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    def njit(*a, **k):
        def d(f): return f
        return d


@dataclass
class BookLevel:
    price: float
    size: float


@dataclass
class OrderBookSnapshot:
    symbol: str
    timestamp_us: int
    bids: List[BookLevel]
    asks: List[BookLevel]

    @property
    def mid_price(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return (self.bids[0].price + self.asks[0].price) / 2.0

    @property
    def spread(self) -> float:
        if not self.bids or not self.asks:
            return 0.0
        return self.asks[0].price - self.bids[0].price

    @property
    def spread_bps(self) -> float:
        m = self.mid_price
        return (self.spread / m * 1e4) if m else 0.0

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp_us": self.timestamp_us,
            "mid": round(self.mid_price, 2),
            "spread_bps": round(self.spread_bps, 2),
            "bids": [{"price": round(l.price, 2), "size": int(l.size)} for l in self.bids[:10]],
            "asks": [{"price": round(l.price, 2), "size": int(l.size)} for l in self.asks[:10]],
        }


if HAS_NUMBA:
    @njit
    def _ofi_kernel(bid_p: np.ndarray, bid_q: np.ndarray,
                    ask_p: np.ndarray, ask_q: np.ndarray) -> np.ndarray:
        n = len(bid_p)
        out = np.zeros(n, dtype=np.float64)
        for i in range(1, n):
            e = 0.0
            if bid_p[i] >= bid_p[i-1]:
                e += bid_q[i]
            if bid_p[i] <= bid_p[i-1]:
                e -= bid_q[i-1]
            if ask_p[i] <= ask_p[i-1]:
                e -= ask_q[i]
            if ask_p[i] >= ask_p[i-1]:
                e += ask_q[i-1]
            out[i] = e
        return out
else:
    def _ofi_kernel(bid_p, bid_q, ask_p, ask_q):
        n = len(bid_p)
        out = np.zeros(n)
        for i in range(1, n):
            e = 0.0
            if bid_p[i] >= bid_p[i-1]: e += bid_q[i]
            if bid_p[i] <= bid_p[i-1]: e -= bid_q[i-1]
            if ask_p[i] <= ask_p[i-1]: e -= ask_q[i]
            if ask_p[i] >= ask_p[i-1]: e += ask_q[i-1]
            out[i] = e
        return out


class OFICalculator:
    """Rolling Order Flow Imbalance with normalized signal in [-1, 1]."""
    def __init__(self, window: int = 100):
        self.window = window
        self._bid_p: Deque[float] = deque(maxlen=window)
        self._bid_q: Deque[float] = deque(maxlen=window)
        self._ask_p: Deque[float] = deque(maxlen=window)
        self._ask_q: Deque[float] = deque(maxlen=window)
        self.cumulative_ofi: float = 0.0

    def update(self, bid_price: float, bid_size: float,
               ask_price: float, ask_size: float) -> Dict:
        self._bid_p.append(bid_price); self._bid_q.append(bid_size)
        self._ask_p.append(ask_price); self._ask_q.append(ask_size)
        n = len(self._bid_p)
        if n < 2:
            return {"ofi": 0.0, "ofi_norm": 0.0, "signal": "NEUTRAL"}
        bp = np.array(self._bid_p, dtype=np.float64)
        bq = np.array(self._bid_q, dtype=np.float64)
        ap = np.array(self._ask_p, dtype=np.float64)
        aq = np.array(self._ask_q, dtype=np.float64)
        ofi_series = _ofi_kernel(bp, bq, ap, aq)
        recent = ofi_series[-min(n - 1, 20):]
        ofi_sum = float(np.sum(recent))
        depth = float(np.mean(bq[-10:]) + np.mean(aq[-10:]) + 1e-9)
        ofi_norm = float(np.tanh(ofi_sum / (10.0 * depth)))
        self.cumulative_ofi += float(ofi_series[-1])
        if ofi_norm > 0.3: signal = "BULLISH"
        elif ofi_norm < -0.3: signal = "BEARISH"
        else: signal = "NEUTRAL"
        return {"ofi": round(ofi_sum, 2), "ofi_norm": round(ofi_norm, 4),
                "cumulative": round(self.cumulative_ofi, 2), "signal": signal}


class L2Simulator:
    """Geometric-Brownian mid-price + mean-reverting depth simulator (mock L2 feed)."""
    def __init__(self, symbol: str, base_price: float, depth: int = 10,
                 tick_size: float = 0.01, seed: Optional[int] = None):
        self.symbol = symbol
        self.mid = base_price
        self.depth = depth
        self.tick_size = tick_size
        self.rng = random.Random(seed)
        self.vol = 0.0008
        self.ofi_calc = OFICalculator()

    def step(self) -> Tuple[OrderBookSnapshot, Dict]:
        # Microstructure momentum: small drift + noise
        drift = self.rng.gauss(0, self.vol) * self.mid
        self.mid = max(1.0, self.mid + drift)
        spread = max(self.tick_size, self.mid * 0.0005)
        bids, asks = [], []
        for i in range(self.depth):
            bp = self.mid - spread / 2 - i * self.tick_size * self.rng.uniform(1, 3)
            ap = self.mid + spread / 2 + i * self.tick_size * self.rng.uniform(1, 3)
            # Size inversely related to distance (realistic book shape)
            bsize = max(10, int(self.rng.expovariate(1 / 500) / (1 + i * 0.4)))
            asize = max(10, int(self.rng.expovariate(1 / 500) / (1 + i * 0.4)))
            bids.append(BookLevel(round(bp, 2), float(bsize)))
            asks.append(BookLevel(round(ap, 2), float(asize)))
        snap = OrderBookSnapshot(
            symbol=self.symbol,
            timestamp_us=int(time.time() * 1e6),
            bids=bids, asks=asks,
        )
        ofi = self.ofi_calc.update(bids[0].price, bids[0].size,
                                   asks[0].price, asks[0].size)
        return snap, ofi

    async def stream(self, interval_ms: int = 100):
        while True:
            snap, ofi = self.step()
            yield {"book": snap.to_dict(), "ofi": ofi}
            await asyncio.sleep(interval_ms / 1000.0)


class LatencyArbitrageDetector:
    """Detects cross-venue price dislocation > threshold (simulated second venue)."""
    def __init__(self, threshold_bps: float = 8.0, latency_us: int = 350):
        self.threshold_bps = threshold_bps
        self.latency_us = latency_us

    def check(self, venue_a_mid: float, venue_b_mid: float) -> Dict:
        if venue_a_mid <= 0 or venue_b_mid <= 0:
            return {"opportunity": False}
        disloc_bps = abs(venue_a_mid - venue_b_mid) / venue_a_mid * 1e4
        opp = disloc_bps > self.threshold_bps
        return {
            "opportunity": opp,
            "dislocation_bps": round(disloc_bps, 2),
            "latency_us": self.latency_us,
            "direction": "BUY_A_SELL_B" if venue_b_mid > venue_a_mid else "BUY_B_SELL_A",
            "edge_bps": round(max(0, disloc_bps - self.threshold_bps), 2),
        }


@dataclass
class ExecutionSlice:
    timestamp_us: int
    price: float
    qty: float
    venue: str = "SIM"


class VWAPExecutor:
    """Slices parent order proportionally to historical volume curve."""
    def execute(self, total_qty: float, price_path: List[float],
                volume_curve: Optional[List[float]] = None) -> Dict:
        n = len(price_path)
        if n == 0 or total_qty <= 0: return {"avg_price": 0, "slices": []}
        if volume_curve is None or len(volume_curve) != n:
            volume_curve = [1.0 / n] * n
        total_vol = sum(volume_curve)
        if total_vol <= 0:
            volume_curve = [1.0 / n] * n
            total_vol = 1.0
        slices = []
        px_qty = 0.0
        for px, v in zip(price_path, volume_curve):
            q = total_qty * v / total_vol
            # Linear temporary impact: 0.5 bps per 1% of ADV slice
            impact = px * 0.00005 * (q / (total_qty + 1e-9) * n)
            exec_px = px + impact
            px_qty += exec_px * q
            slices.append({"price": round(exec_px, 4), "qty": round(q, 2)})
        return {"avg_price": round(px_qty / total_qty, 4),
                "slices": slices, "algo": "VWAP"}


class TWAPExecutor:
    """Equal slices across N intervals with optional randomization."""
    def execute(self, total_qty: float, price_path: List[float]) -> Dict:
        n = len(price_path)
        if n == 0 or total_qty <= 0: return {"avg_price": 0, "slices": []}
        q = total_qty / n
        px_qty = sum(p * q for p in price_path)
        return {"avg_price": round(px_qty / total_qty, 4),
                "slices": [{"price": round(p, 4), "qty": round(q, 2)} for p in price_path],
                "algo": "TWAP"}


# Multi-symbol manager for FastAPI streaming
class HFTManager:
    def __init__(self, symbols: Dict[str, float]):
        # Stable seed per symbol (hash() is randomized per process).
        self.sims = {s: L2Simulator(s, p,
                                    seed=sum(ord(c) * (i + 1) for i, c in enumerate(s)) % 10000)
                     for s, p in symbols.items()}
        self.arb = LatencyArbitrageDetector()

    def snapshot_all(self) -> List[Dict]:
        out = []
        for sym, sim in self.sims.items():
            snap, ofi = sim.step()
            # Simulate second venue with small noise for arb check
            venue_b = snap.mid_price * (1 + random.gauss(0, 0.0004))
            arb = self.arb.check(snap.mid_price, venue_b)
            d = snap.to_dict()
            d["ofi"] = ofi
            d["arb"] = arb
            out.append(d)
        return out
