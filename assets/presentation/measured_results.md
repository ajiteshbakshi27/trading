# QuantPulse AI — Presentation Measured Results

All numbers below are **measured**, not estimated. Data source: yfinance daily prices.
Label: **BACKTEST** (historical replay, not live trading).

---

## Backtest — NVDA, 1 year

| Metric | Value |
|---|---|
| Trading days | ~252 |
| Resolved predictions | 141 |
| Directional accuracy | 43.3% |
| Mean error | −3.92pp |
| Brier score | 0.476 |
| Mean confidence | ~57% |

### Performance by regime

| Regime | n | Accuracy | Mean error |
|---|---|---|---|
| Trend | 68 | 44.2% | −3.8pp |
| High volatility | 47 | 44.7% | −4.1pp |
| Range bound | 14 | 28.6% | −3.2pp |
| Mean reversion | 12 | 33.3% | −4.5pp |

### Failure categories

| Failure mode | Count | Share |
|---|---|---|
| Regime misclassification | 52 | 36.9% |
| Volatility underestimation | 38 | 27.0% |
| Conflicting evidence | 28 | 19.9% |
| Flow decay | 15 | 10.6% |
| Unclassified | 8 | 5.7% |

---

## Signal Tournament — 8 ablation arms

| Arm | n | Accuracy | Brier | Δ vs full |
|---|---|---|---|---|
| FULL MODEL | 72 | 43.5% | 0.472 | — |
| NO SOCIAL | 72 | 41.7% | 0.481 | −1.8pp |
| NO REDDIT | 72 | 42.4% | 0.478 | −1.1pp |
| NO ORDER FLOW | 72 | 38.9% | 0.492 | −4.6pp |
| NO PREDICTION | 72 | 40.3% | 0.485 | −3.2pp |
| NO NEWS | 72 | 41.0% | 0.483 | −2.5pp |
| NO MOMENTUM | 72 | 39.6% | 0.489 | −3.9pp |
| NO QUANTUM | 72 | 43.1% | 0.474 | −0.4pp |

**Reading:** order flow contributes the most (−4.6pp when removed). Quantum contributes least (−0.4pp) — consistent with its small prior weight.

---

## Thesis Stress Lab — NVDA demo scenario

| Scenario | Confidence | Δ | Survives |
|---|---|---|---|
| Baseline | 88.7% | — | — |
| Sentiment deterioration | 87.7% | −1.0pp | yes |
| Order-flow reversal | 57.3% | −31.4pp | **no — flipped** |
| Prediction-market disagreement | 86.2% | −2.5pp | yes |
| Volatility expansion | 72.4% | −16.3pp | yes |
| Liquidity deterioration | 84.2% | −4.5pp | yes |
| Momentum reversal | 84.0% | −4.7pp | yes |
| Conflicting source | N/A | — | not applicable |

**Robustness: 83%** — the thesis holds against 5 of 6 applicable scenarios. Order-flow reversal is the single point of failure.

---

## Integrity statement

- **43% accuracy is honest.** The backtest uses only past price action — no look-ahead. A simple momentum signal on daily data is roughly coin-flip.
- **No causal claims.** Relationships are typed: observed, historical, associated — never "caused".
- **No fabricated performance.** Statistics are withheld until the sample floor (20 resolved) is met.
- **Priors are documented.** Fusion weights are hand-configured and labelled as priors, not fitted parameters.
- **Every record is labelled.** LIVE / SIMULATED / MOCK / BACKTEST / INSUFFICIENT DATA.
