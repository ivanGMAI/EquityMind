"""Mean-variance portfolio mathematics (NumPy only, no SciPy).

Closed-form and iterative solvers for the classic Markowitz problem, kept
dependency-light and robust:

* ``portfolio_return`` / ``portfolio_volatility`` / ``portfolio_sharpe`` — the
  characteristics of an arbitrary weight vector,
* ``min_variance_weights`` — the global minimum-variance portfolio (closed form),
* ``max_sharpe_weights`` — the tangency (maximum-Sharpe) portfolio (closed form),
* ``risk_parity_weights`` — equal-risk-contribution weights (fixed-point iteration),
* ``efficient_frontier`` — the frontier traced via two-fund separation.

The covariance matrix is inverted with the Moore–Penrose pseudo-inverse so a
near-singular matrix (highly correlated assets, short samples) degrades
gracefully instead of raising. Unconstrained closed forms may imply short
positions (negative weights); ``risk_parity_weights`` is long-only by construction.
"""

from __future__ import annotations

import numpy as np


def _as_array(x) -> np.ndarray:
    return np.asarray(x, dtype=float).reshape(-1)


def portfolio_return(weights, mean_returns) -> float:
    """Expected portfolio return for a weight vector (same units as inputs)."""
    return float(_as_array(weights) @ _as_array(mean_returns))


def portfolio_volatility(weights, cov) -> float:
    """Portfolio volatility ``sqrt(wᵀ Σ w)`` (same units as ``cov``'s sqrt)."""
    w = _as_array(weights)
    variance = float(w @ np.asarray(cov, dtype=float) @ w)
    return float(np.sqrt(max(variance, 0.0)))


def portfolio_sharpe(weights, mean_returns, cov, risk_free_rate: float = 0.0) -> float | None:
    """Sharpe ratio of a weight vector (inputs must already be annualised)."""
    vol = portfolio_volatility(weights, cov)
    if vol == 0:
        return None
    return float((portfolio_return(weights, mean_returns) - risk_free_rate) / vol)


def _normalise(weights: np.ndarray) -> np.ndarray:
    total = weights.sum()
    if total == 0 or not np.isfinite(total):
        return np.full(len(weights), 1.0 / len(weights))
    return weights / total


def min_variance_weights(cov) -> np.ndarray:
    """Global minimum-variance weights ``Σ⁻¹1 / (1ᵀΣ⁻¹1)`` (sum to 1)."""
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    ones = np.ones(n)
    inv = np.linalg.pinv(cov)
    return _normalise(inv @ ones)


def max_sharpe_weights(mean_returns, cov, risk_free_rate: float = 0.0) -> np.ndarray:
    """Tangency (max-Sharpe) weights ``Σ⁻¹(μ − r_f)`` normalised to sum to 1."""
    mu = _as_array(mean_returns)
    cov = np.asarray(cov, dtype=float)
    excess = mu - risk_free_rate
    inv = np.linalg.pinv(cov)
    raw = inv @ excess
    if raw.sum() == 0 or not np.isfinite(raw.sum()):
        return min_variance_weights(cov)
    return _normalise(raw)


def risk_parity_weights(cov, *, iters: int = 500, tol: float = 1e-8) -> np.ndarray:
    """Equal-risk-contribution (long-only) weights via fixed-point iteration.

    Each asset ends up contributing an equal share of total portfolio risk — a
    more robust diversification target than equal capital weighting when
    volatilities differ widely. Falls back to equal weights if iteration stalls.
    """
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    w = np.full(n, 1.0 / n)
    budget = np.full(n, 1.0 / n)
    for _ in range(iters):
        marginal = cov @ w
        # Guard against non-positive marginal risk (near-singular / bad input).
        marginal = np.where(np.abs(marginal) < 1e-15, 1e-15, marginal)
        w_new = _normalise(budget / marginal)
        if not np.all(np.isfinite(w_new)):
            return np.full(n, 1.0 / n)
        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new
    return w


def risk_contributions(weights, cov) -> np.ndarray:
    """Fractional share of total portfolio variance contributed by each asset."""
    w = _as_array(weights)
    cov = np.asarray(cov, dtype=float)
    variance = float(w @ cov @ w)
    if variance <= 0:
        return np.full(len(w), 1.0 / len(w))
    return (w * (cov @ w)) / variance


def efficient_frontier(
    mean_returns, cov, *, n_points: int = 25, risk_free_rate: float = 0.0
) -> list[dict]:
    """Sample the efficient frontier via two-fund separation.

    Every frontier portfolio is a linear combination of the minimum-variance and
    tangency portfolios; sweeping the mixing coefficient traces the curve without
    any iterative optimiser. Returns ``[{"return", "volatility"}, ...]`` sorted by
    volatility.
    """
    mu = _as_array(mean_returns)
    cov = np.asarray(cov, dtype=float)
    w_mv = min_variance_weights(cov)
    w_tan = max_sharpe_weights(mu, cov, risk_free_rate)

    points: list[dict] = []
    for alpha in np.linspace(-0.5, 1.5, n_points):
        w = _normalise(alpha * w_tan + (1.0 - alpha) * w_mv)
        points.append(
            {
                "return": round(portfolio_return(w, mu), 6),
                "volatility": round(portfolio_volatility(w, cov), 6),
            }
        )
    points.sort(key=lambda p: p["volatility"])
    return points
