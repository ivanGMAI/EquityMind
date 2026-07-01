"""Benchmark-relative statistics (CAPM: beta, alpha) and correlation.

Positions the instrument against a market benchmark (e.g. SPY):

* **beta**  — sensitivity to benchmark moves, ``cov(asset, bench) / var(bench)``.
  β>1 amplifies market moves, β<1 dampens them, β<0 moves against the market.
* **alpha** — annualised Jensen's alpha: the average return *not* explained by
  benchmark exposure at the given risk-free rate. Positive alpha = out-performance
  beyond what the beta exposure would predict.
* **correlation / R²** — how much of the instrument's variance is co-movement
  with the benchmark (diversification context).

All figures are estimated from daily returns aligned on common trading dates, so
mismatched calendars (e.g. crypto vs. equities) are handled correctly. Any figure
is ``None`` when the overlapping sample is too short or a denominator is zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .performance import _align_returns, _daily_rf


@dataclass(slots=True)
class BenchmarkStats:
    """Instrument statistics relative to a market benchmark."""

    benchmark: str
    beta: float | None = None
    alpha_annual: float | None = None  # fractional, annualised
    correlation: float | None = None
    r_squared: float | None = None
    observations: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def beta(asset_close: pd.Series, benchmark_close: pd.Series) -> float | None:
    """CAPM beta of the asset versus the benchmark (daily returns)."""
    a, b = _align_returns(asset_close, benchmark_close)
    if len(a) < 2:
        return None
    var_b = b.var(ddof=1)
    if var_b == 0 or np.isnan(var_b):
        return None
    cov = np.cov(a.to_numpy(), b.to_numpy(), ddof=1)[0, 1]
    return float(cov / var_b)


def correlation(asset_close: pd.Series, benchmark_close: pd.Series) -> float | None:
    """Pearson correlation of daily returns with the benchmark."""
    a, b = _align_returns(asset_close, benchmark_close)
    if len(a) < 2:
        return None
    if a.std(ddof=1) == 0 or b.std(ddof=1) == 0:
        return None
    return float(np.corrcoef(a.to_numpy(), b.to_numpy())[0, 1])


def alpha(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    *,
    risk_free_rate: float = 0.0,
    trading_days: int = 252,
) -> float | None:
    """Annualised Jensen's alpha from the CAPM regression."""
    a, b = _align_returns(asset_close, benchmark_close)
    if len(a) < 2:
        return None
    var_b = b.var(ddof=1)
    if var_b == 0 or np.isnan(var_b):
        return None
    rf_daily = _daily_rf(risk_free_rate, trading_days)
    beta_val = float(np.cov(a.to_numpy(), b.to_numpy(), ddof=1)[0, 1] / var_b)
    # Daily Jensen alpha = mean(r_a - rf) - beta * mean(r_b - rf); annualise.
    daily_alpha = (a.mean() - rf_daily) - beta_val * (b.mean() - rf_daily)
    return float(daily_alpha * trading_days)


def compute_benchmark_stats(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    *,
    benchmark_ticker: str,
    risk_free_rate: float = 0.0,
    trading_days: int = 252,
) -> BenchmarkStats:
    """Compute beta, alpha, correlation and R² against a benchmark series."""
    a, b = _align_returns(asset_close, benchmark_close)
    n = len(a)
    corr = correlation(asset_close, benchmark_close)
    return BenchmarkStats(
        benchmark=benchmark_ticker,
        beta=_round(beta(asset_close, benchmark_close)),
        alpha_annual=_round(
            alpha(
                asset_close,
                benchmark_close,
                risk_free_rate=risk_free_rate,
                trading_days=trading_days,
            ),
            4,
        ),
        correlation=_round(corr),
        r_squared=_round(None if corr is None else corr * corr),
        observations=n,
    )


def _round(value: float | None, ndigits: int = 3) -> float | None:
    return None if value is None else round(value, ndigits)
