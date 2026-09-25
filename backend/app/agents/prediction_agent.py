"""
QuantPulse AI - Prediction Market Arbitrage Engine
Compares crowd-implied probabilities (Polymarket/Kalshi schema)
against Quantum model fair odds to flag mispricings.
Mock feed included so UI works without API keys.
"""
from __future__ import annotations
import random
from typing import List, Dict

MOCK_MARKETS = [
    {"id": "FED_CUT_DEC", "question": "Fed rate cut in December?",
     "crowd_prob": 0.68, "volume": 4_200_000},
    {"id": "NVDA_BEAT_Q", "question": "NVDA beats earnings expectations?",
     "crowd_prob": 0.82, "volume": 1_150_000},
    {"id": "SPY_ATH_30D", "question": "S&P 500 new ATH in 30 days?",
     "crowd_prob": 0.55, "volume": 890_000},
    {"id": "TSLA_UP_10P", "question": "TSLA up 10%+ this month?",
     "crowd_prob": 0.31, "volume": 640_000},
    {"id": "BTC_100K", "question": "BTC above $100k EOY?",
     "crowd_prob": 0.74, "volume": 5_600_000},
    {"id": "RECESSION_2027", "question": "US recession in H1 2027?",
     "crowd_prob": 0.22, "volume": 1_900_000},
]


def quantum_fair_prob(crowd_prob: float, ofi_norm: float = 0.0,
                      sentiment: float = 0.0, seed_jitter: bool = True) -> float:
    """
    Toy quantum-fair-value: crowd prob adjusted by microstructure (OFI)
    and debiased from sentiment extremes (fade hype).
    """
    q = crowd_prob + 0.15 * ofi_norm - 0.10 * sentiment
    if seed_jitter:
        q += random.gauss(0, 0.02)
    return round(float(min(0.97, max(0.03, q))), 3)


def find_edges(markets: List[Dict], min_edge: float = 0.07) -> List[Dict]:
    """Flag markets where |quantum - crowd| >= min_edge."""
    out = []
    for m in markets:
        qp = m.get("quantum_prob", m["crowd_prob"])
        edge = round(qp - m["crowd_prob"], 3)
        if abs(edge) >= min_edge:
            side = "YES" if edge > 0 else "NO"
            out.append({**m, "edge": edge, "side": f"BUY {side}",
                        "confidence": round(min(0.95, abs(edge) * 3), 2)})
    return sorted(out, key=lambda x: abs(x["edge"]), reverse=True)


class PredictionAgent:
    def __init__(self, min_edge: float = 0.07):
        self.min_edge = min_edge

    def fetch_mock(self, ofi_map: Dict[str, float] = None,
                   sent_map: Dict[str, float] = None) -> List[Dict]:
        ofi_map, sent_map = ofi_map or {}, sent_map or {}
        mkts = []
        for m in MOCK_MARKETS:
            # Drift crowd prob slightly each poll for "live" feel
            cp = min(0.97, max(0.03, m["crowd_prob"] + random.gauss(0, 0.01)))
            qp = quantum_fair_prob(cp, random.uniform(-0.4, 0.4),
                                   random.uniform(-0.5, 0.5))
            mkts.append({**m, "crowd_prob": round(cp, 3), "quantum_prob": qp})
        return mkts

    def analyze(self, markets: List[Dict]) -> Dict:
        edges = find_edges(markets, self.min_edge)
        return {"markets": markets, "edges": edges, "n_edges": len(edges)}
