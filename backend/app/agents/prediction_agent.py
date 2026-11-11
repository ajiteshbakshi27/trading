"""
Parakh - Prediction Market Arbitrage Engine
Compares crowd-implied probabilities (Polymarket/Kalshi schema)
against Quantum model fair odds to flag mispricings.
Mock feed included so UI works without API keys.
"""
from __future__ import annotations
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


def model_fair_prob(crowd_prob: float, ofi_norm: float = 0.0,
                    sentiment: float = 0.0) -> float:
    """Heuristic fair probability: crowd probability adjusted by order flow
    and de-biased away from sentiment extremes (fade hype).

    HONESTY NOTE: this is a hand-set linear heuristic, not a quantum or
    fitted model. It was previously named ``quantum_fair_prob`` and added
    random noise; both were removed. Output is deterministic.
    """
    q = crowd_prob + 0.15 * ofi_norm - 0.10 * sentiment
    return round(float(min(0.97, max(0.03, q))), 3)


#: Backwards-compatible alias (old name). Prefer ``model_fair_prob``.
def quantum_fair_prob(crowd_prob: float, ofi_norm: float = 0.0,
                      sentiment: float = 0.0, seed_jitter: bool = False) -> float:
    return model_fair_prob(crowd_prob, ofi_norm, sentiment)


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
            # Static example markets (no live Kalshi/Polymarket feed yet).
            # No fake "live" drift: the numbers are labelled MOCK.
            cp = m["crowd_prob"]
            qp = model_fair_prob(cp, float(ofi_map.get(m["id"], 0.0)),
                                 float(sent_map.get(m["id"], 0.0)))
            mkts.append({**m, "crowd_prob": round(cp, 3), "quantum_prob": qp,
                         "model_prob": qp, "data_mode": "mock"})
        return mkts

    def analyze(self, markets: List[Dict]) -> Dict:
        edges = find_edges(markets, self.min_edge)
        return {"markets": markets, "edges": edges, "n_edges": len(edges)}
