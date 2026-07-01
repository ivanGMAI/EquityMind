"""Portfolio-level analysis: correlation, allocations and the efficient frontier.

Combines the correlation/covariance building blocks with the mean-variance
solvers into a single :class:`PortfolioReport`. For a universe of instruments it
reports the correlation structure and four reference allocations — equal-weight
(the naive baseline), minimum-variance, maximum-Sharpe (tangency) and
risk-parity — each with its expected return, volatility and Sharpe ratio, plus a
sampled efficient frontier for context.

Everything is annualised (arithmetic mean returns × trading days; annualised
covariance) so the return/volatility figures are directly comparable to the
per-asset metrics elsewhere in the system.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field

import numpy as np

from ..data.models import PriceHistory
from . import optimizer
from .correlation import (
    average_pairwise_correlation,
    correlation_matrix,
    covariance_matrix,
    returns_matrix,
)


@dataclass(slots=True)
class PortfolioMetrics:
    """A single allocation and its annualised characteristics."""

    label: str
    weights: dict[str, float]  # ticker -> weight in percent
    expected_return_pct: float | None
    volatility_pct: float | None
    sharpe: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class PortfolioReport:
    """Cross-asset portfolio view over the analysed universe."""

    tickers: list[str]
    observations: int
    risk_free_rate: float
    average_correlation: float
    correlation: dict[str, dict[str, float]] = field(default_factory=dict)
    allocations: dict[str, PortfolioMetrics] = field(default_factory=dict)
    frontier: list[dict] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "tickers": self.tickers,
            "observations": self.observations,
            "risk_free_rate_pct": round(self.risk_free_rate * 100.0, 2),
            "average_correlation": round(self.average_correlation, 3),
            "correlation": self.correlation,
            "allocations": {k: v.to_dict() for k, v in self.allocations.items()},
        }

    def to_dict(self) -> dict:
        payload = self.to_payload()
        payload["frontier"] = self.frontier
        return payload


def _weights_dict(tickers: list[str], weights: np.ndarray) -> dict[str, float]:
    return {t: round(float(w) * 100.0, 2) for t, w in zip(tickers, weights, strict=False)}


def _metrics(
    label: str,
    tickers: list[str],
    weights: np.ndarray,
    mean_annual: np.ndarray,
    cov_annual: np.ndarray,
    risk_free_rate: float,
) -> PortfolioMetrics:
    sharpe = optimizer.portfolio_sharpe(weights, mean_annual, cov_annual, risk_free_rate)
    return PortfolioMetrics(
        label=label,
        weights=_weights_dict(tickers, weights),
        expected_return_pct=round(optimizer.portfolio_return(weights, mean_annual) * 100.0, 2),
        volatility_pct=round(optimizer.portfolio_volatility(weights, cov_annual) * 100.0, 2),
        sharpe=None if sharpe is None else round(sharpe, 3),
    )


def analyze_portfolio(
    histories: Mapping[str, PriceHistory],
    *,
    risk_free_rate: float = 0.0,
    trading_days: int = 252,
    frontier_points: int = 25,
) -> PortfolioReport | None:
    """Build a :class:`PortfolioReport`; ``None`` if fewer than two usable assets.

    Requires at least two instruments with overlapping history and a couple of
    return observations, otherwise correlation/covariance are undefined.
    """
    rets = returns_matrix(histories)
    if rets.shape[1] < 2 or len(rets) < 2:
        return None

    tickers = list(rets.columns)
    corr = correlation_matrix(rets)
    cov_annual = covariance_matrix(rets, trading_days).to_numpy()
    mean_annual = rets.mean().to_numpy() * trading_days
    n = len(tickers)

    equal_w = np.full(n, 1.0 / n)
    min_var_w = optimizer.min_variance_weights(cov_annual)
    max_sharpe_w = optimizer.max_sharpe_weights(mean_annual, cov_annual, risk_free_rate)
    risk_parity_w = optimizer.risk_parity_weights(cov_annual)

    allocations = {
        "equal_weight": _metrics(
            "Equal weight", tickers, equal_w, mean_annual, cov_annual, risk_free_rate
        ),
        "min_variance": _metrics(
            "Minimum variance", tickers, min_var_w, mean_annual, cov_annual, risk_free_rate
        ),
        "max_sharpe": _metrics(
            "Maximum Sharpe (tangency)",
            tickers,
            max_sharpe_w,
            mean_annual,
            cov_annual,
            risk_free_rate,
        ),
        "risk_parity": _metrics(
            "Risk parity", tickers, risk_parity_w, mean_annual, cov_annual, risk_free_rate
        ),
    }

    frontier = optimizer.efficient_frontier(
        mean_annual, cov_annual, n_points=frontier_points, risk_free_rate=risk_free_rate
    )

    corr_dict = {
        row: {col: round(float(corr.loc[row, col]), 3) for col in tickers} for row in tickers
    }

    return PortfolioReport(
        tickers=tickers,
        observations=len(rets),
        risk_free_rate=risk_free_rate,
        average_correlation=average_pairwise_correlation(corr),
        correlation=corr_dict,
        allocations=allocations,
        frontier=frontier,
    )
