"""Mean-variance portfolio mathematics (NumPy only, no SciPy).

Closed-form and iterative solvers for the classic Markowitz problem, kept
dependency-light and robust:

* ``portfolio_return`` / ``portfolio_volatility`` / ``portfolio_sharpe`` — the
  characteristics of an arbitrary weight vector,
* ``min_variance_weights`` — the global minimum-variance portfolio (closed form),
* ``max_sharpe_weights`` — the tangency (maximum-Sharpe) portfolio (closed form),
* ``risk_parity_weights`` — equal-risk-contribution weights (fixed-point iteration),
* ``efficient_frontier`` — the frontier sampled by sweeping target returns
  (exact Lagrange solution per point).

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


def _target_return_weights(mean_returns, cov, target: float) -> np.ndarray | None:
    """Minimum-variance weights for a given target return (Lagrange closed form).

    Solves ``min wᵀΣw`` s.t. ``wᵀ1 = 1`` and ``wᵀμ = target``. Returns ``None``
    when the system is degenerate (all expected returns equal, singular Σ).
    """
    mu = _as_array(mean_returns)
    cov = np.asarray(cov, dtype=float)
    ones = np.ones(len(mu))
    inv = np.linalg.pinv(cov)
    a = float(ones @ inv @ ones)
    b = float(ones @ inv @ mu)
    c = float(mu @ inv @ mu)
    d = a * c - b * b
    if not np.isfinite(d) or abs(d) < 1e-14:
        return None
    lam = (c - b * target) / d
    gam = (a * target - b) / d
    w = lam * (inv @ ones) + gam * (inv @ mu)
    return w if np.all(np.isfinite(w)) else None


def max_sharpe_weights(mean_returns, cov, risk_free_rate: float = 0.0) -> np.ndarray:
    """Maximum-Sharpe weights, robust to falling markets.

    The classic tangency formula ``Σ⁻¹(μ − r_f)`` maximises Sharpe only while
    ``1ᵀΣ⁻¹(μ − r_f) > 0`` (the tangency lies on the efficient branch). When
    every excess return is negative — a market-wide drawdown — that formula
    lands on the *inefficient* branch and can return a portfolio with a worse
    Sharpe than minimum variance. In that regime we instead scan the frontier
    segment spanned by the assets' expected returns and pick the best Sharpe
    found there (this bounds leverage; the unconstrained supremum is otherwise
    reached only at infinite risk).
    """
    mu = _as_array(mean_returns)
    cov = np.asarray(cov, dtype=float)
    excess = mu - risk_free_rate
    inv = np.linalg.pinv(cov)
    raw = inv @ excess
    total = raw.sum()
    if np.isfinite(total) and total > 1e-12:
        return _normalise(raw)

    best_w = min_variance_weights(cov)
    best_s = portfolio_sharpe(best_w, mu, cov, risk_free_rate)
    for target in np.linspace(mu.min(), mu.max(), 200):
        w = _target_return_weights(mu, cov, target)
        if w is None:
            break
        s = portfolio_sharpe(w, mu, cov, risk_free_rate)
        if s is not None and (best_s is None or s > best_s):
            best_w, best_s = w, s
    return best_w


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
    """Sample the minimum-variance frontier by sweeping target returns.

    Each point is the exact Lagrange solution of ``min wᵀΣw`` at a target
    return; targets span the assets' expected returns, so the curve always
    stretches from the worst to the best asset regardless of the sign of the
    returns (a two-fund sweep between min-variance and tangency degenerates to
    a stub when those portfolios nearly coincide, e.g. in a drawdown). Returns
    ``[{"return", "volatility"}, ...]`` sorted by volatility; both hyperbola
    branches are included — the consumer draws the efficient one.
    """
    mu = _as_array(mean_returns)
    cov = np.asarray(cov, dtype=float)

    points: list[dict] = []
    for target in np.linspace(mu.min(), mu.max(), n_points):
        w = _target_return_weights(mu, cov, target)
        if w is None:  # degenerate inputs: single point (min variance)
            w = min_variance_weights(cov)
        points.append(
            {
                "return": round(portfolio_return(w, mu), 6),
                "volatility": round(portfolio_volatility(w, cov), 6),
            }
        )
        if len(points) > 1 and points[-1] == points[-2]:
            points.pop()
    points.sort(key=lambda p: p["volatility"])
    return points
