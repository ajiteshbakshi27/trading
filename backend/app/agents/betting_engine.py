"""
QuantPulse AI - Contrarian Betting Engine
BET FOR : sentiment aligns with HFT momentum + quantum fair value.
BET AGAINST (fade): crowd euphoria (>90% bullish) collides with
  weak/negative OFI and quantum overbought zones.
"""
from __future__ import annotations
from typing import Dict, List
import random


def build_signal(symbol: str, bullish_pct: float, sentiment: float,
                 ofi_norm: float, quantum_edge: float = 0.0,
                 price: float = 0.0) -> Dict:
    euphoria = bullish_pct >= 90
    panic = bullish_pct <= 10
    aligned_bull = sentiment > 0.25 and ofi_norm > 0.2
    aligned_bear = sentiment < -0.25 and ofi_norm < -0.2

    if (euphoria and ofi_norm < 0.05) or (panic and ofi_norm > -0.05):
        # Crowd extreme NOT confirmed by order flow -> fade
        direction = "SHORT" if euphoria else "LONG"
        stype = "BET_AGAINST"
        conf = min(0.95, 0.65 + abs(sentiment) * 0.2 + abs(ofi_norm) * 0.2 + 0.1)
        rationale = (
            f"Crowd {bullish_pct}% {'bullish' if euphoria else 'bearish'} "
            f"but OFI {ofi_norm:+.2f} shows flow divergence — fading hype."
        )
    elif aligned_bull or (quantum_edge > 0.05 and ofi_norm > 0):
        direction, stype = "LONG", "BET_FOR"
        conf = min(0.95, 0.55 + sentiment * 0.2 + ofi_norm * 0.2 + quantum_edge)
        rationale = f"Sentiment {sentiment:+.2f} aligned with OFI {ofi_norm:+.2f}; quantum edge {quantum_edge:+.2f}."
    elif aligned_bear or (quantum_edge < -0.05 and ofi_norm < 0):
        direction, stype = "SHORT", "BET_FOR"
        conf = min(0.95, 0.55 + abs(sentiment) * 0.2 + abs(ofi_norm) * 0.2 + abs(quantum_edge))
        rationale = f"Bearish alignment: sentiment {sentiment:+.2f}, OFI {ofi_norm:+.2f}, edge {quantum_edge:+.2f}."
    else:
        direction, stype = "FLAT", "NO_BET"
        conf = 0.35
        rationale = "Mixed signals — no edge. Standing aside."

    target = round(price * (1 + (0.03 if direction == "LONG" else -0.03 if direction == "SHORT" else 0)), 2)
    stop = round(price * (1 - (0.015 if direction == "LONG" else -0.015 if direction == "SHORT" else 0)), 2)
    return {
        "symbol": symbol, "type": stype, "direction": direction,
        "confidence": round(float(conf), 2),
        "price": round(price, 2), "target": target, "stop": stop,
        "bullish_pct": bullish_pct, "ofi_norm": ofi_norm,
        "rationale": rationale,
    }


class BettingEngine:
    def generate(self, symbols_data: List[Dict]) -> List[Dict]:
        """symbols_data: [{symbol, bullish_pct, sentiment, ofi_norm, quantum_edge, price}]"""
        return [build_signal(**{k: d.get(k, 0) if k != "symbol" else d["symbol"]
                                for k in ("symbol", "bullish_pct", "sentiment",
                                          "ofi_norm", "quantum_edge", "price")})
                for d in symbols_data]
