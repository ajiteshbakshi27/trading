"""
QuantPulse AI - Quantum Portfolio Optimizer (VQE / QAOA)
Uses PennyLane when available; falls back to classical mean-variance
so the app runs without quantum dependencies.
"""
from __future__ import annotations
from typing import List, Dict, Optional
import numpy as np

try:
    import pennylane as qml
    HAS_PENNYLANE = True
except ImportError:
    HAS_PENNYLANE = False


def _classical_min_variance(cov: np.ndarray) -> np.ndarray:
    """Closed-form min-variance weights: w = Sigma^-1 1 / (1^T Sigma^-1 1)."""
    n = cov.shape[0]
    try:
        inv = np.linalg.inv(cov + np.eye(n) * 1e-6)
    except np.linalg.LinAlgError:
        return np.ones(n) / n
    ones = np.ones(n)
    w = inv @ ones / (ones @ inv @ ones)
    return np.clip(w, 0, 1) / np.clip(w, 0, 1).sum()


def quantum_portfolio_optimize(
    expected_returns: List[float],
    cov_matrix: List[List[float]],
    risk_aversion: float = 1.0,
    max_iter: int = 60,
) -> Dict:
    """
    QAOA-style portfolio selection.
    - n assets -> n qubits. Bitstring = include/exclude (then renormalized).
    - Cost = -mu^T w + gamma * w^T Sigma w  (minimize).
    Falls back to classical solver if PennyLane missing.
    """
    mu = np.array(expected_returns, dtype=float)
    cov = np.array(cov_matrix, dtype=float)
    n = len(mu)
    if n == 0:
        return {"weights": [], "method": "none", "expected_return": 0, "volatility": 0}

    if not HAS_PENNYLANE or n > 8:
        w = _classical_min_variance(cov)
        # Tilt by returns
        tilt = np.clip(mu - mu.min() + 0.01, 0, None)
        w = 0.6 * w + 0.4 * tilt / tilt.sum()
        w = w / w.sum()
        port_ret = float(w @ mu)
        port_vol = float(np.sqrt(w @ cov @ w))
        return {
            "weights": [round(float(x), 4) for x in w],
            "method": "classical_min_variance_fallback",
            "expected_return": round(port_ret, 6),
            "volatility": round(port_vol, 6),
            "sharpe_proxy": round(port_ret / (port_vol + 1e-9), 4),
        }

    # --- PennyLane QAOA simulation ---
    # Map cost to Ising Hamiltonian diagonal: use QAOA on MaxCut-like mixer
    # with cost encoded via single-Z (return bias) + ZZ (covariance) terms.
    dev = qml.device("default.qubit", wires=n)

    # Normalize coefficients for stable optimization
    mu_n = mu / (np.abs(mu).max() + 1e-9)
    cov_n = cov / (np.abs(cov).max() + 1e-9)

    coeffs, obs = [], []
    for i in range(n):
        coeffs.append(float(-mu_n[i]))  # favor high-return assets
        obs.append(qml.PauliZ(i))
    for i in range(n):
        for j in range(i + 1, n):
            coeffs.append(float(risk_aversion * cov_n[i, j]))
            obs.append(qml.PauliZ(i) @ qml.PauliZ(j))
    H = qml.Hamiltonian(coeffs, obs)

    def qaoa_layer(gamma, alpha):
        qml.ApproxTimeEvolution(H, gamma, 1)
        for w in range(n):
            qml.RX(2 * alpha, wires=w)

    @qml.qnode(dev)
    def circuit(params):
        for w in range(n):
            qml.Hadamard(wires=w)
        # p=2 layers
        qaoa_layer(params[0], params[1])
        qaoa_layer(params[2], params[3])
        return qml.expval(H)

    # Simple gradient descent (PennyLane 0.45+: use trainable pnp array)
    try:
        from pennylane import numpy as pnp
        params = pnp.array([0.5, 0.5, 0.5, 0.5], requires_grad=True)
        lr = 0.15
        gfn = qml.grad(circuit)
        for _ in range(max_iter):
            grad = gfn(params)
            params = params - lr * grad
        params_np = np.array(params)
    except Exception:
        # Quantum grad failed -> fall back to heuristic params
        params_np = np.array([0.5, 0.5, 0.5, 0.5])

    # Sample most-likely bitstring
    @qml.qnode(dev)
    def prob_circuit(params):
        for w in range(n):
            qml.Hadamard(wires=w)
        qaoa_layer(params[0], params[1])
        qaoa_layer(params[2], params[3])
        return qml.probs(wires=list(range(n)))

    probs = prob_circuit(params_np)
    best = int(np.argmax(probs))
    bits = [(best >> (n - 1 - i)) & 1 for i in range(n)]
    if sum(bits) == 0:
        bits[0] = 1
    # Weight by returns among selected
    sel_ret = np.array([mu[i] if bits[i] else 0 for i in range(n)])
    sel_ret = np.clip(sel_ret, 0, None)
    w = sel_ret / sel_ret.sum() if sel_ret.sum() > 0 else np.ones(n) / n

    port_ret = float(w @ mu)
    port_vol = float(np.sqrt(w @ cov @ w))
    return {
        "weights": [round(float(x), 4) for x in w],
        "method": "pennylane_qaoa_p2",
        "bitstring": "".join(map(str, bits)),
        "expected_return": round(port_ret, 6),
        "volatility": round(port_vol, 6),
        "sharpe_proxy": round(port_ret / (port_vol + 1e-9), 4),
    }


def quantum_option_price_proxy(S: float, K: float, T: float, r: float,
                               sigma: float, option: str = "call") -> Dict:
    """Black-Scholes closed form (quantum amplitude-estimation placeholder)."""
    from math import log, sqrt, exp, erf
    def N(x): return 0.5 * (1 + erf(x / sqrt(2)))
    if T <= 0 or sigma <= 0 or S <= 0:
        payoff = max(S - K, 0) if option == "call" else max(K - S, 0)
        return {"price": round(payoff, 4), "method": "intrinsic"}
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    if option == "call":
        px = S * N(d1) - K * exp(-r * T) * N(d2)
    else:
        px = K * exp(-r * T) * N(-d2) - S * N(-d1)
    return {"price": round(float(px), 4), "method": "black_scholes_proxy",
            "d1": round(float(d1), 4), "d2": round(float(d2), 4)}
