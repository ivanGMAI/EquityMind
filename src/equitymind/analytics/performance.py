"""Risk-adjusted performance ratios.

These are the headline figures a desk uses to compare instruments on a
risk-adjusted basis, rather than by raw return alone:

* **Sharpe**  — excess return per unit of *total* volatility,
* **Sortino** — excess return per unit of *downside* volatility (ignores upside
  dispersion, which investors do not experience as risk),
* **Calmar**  — annualised return per unit of worst drawdown,
* **Information ratio** — active return per unit of tracking error versus a
  benchmark.

All ratios use daily returns and are annualised with the same ``trading_days``
factor as the rest of the analytics stack. Everything is a pure function of the
price series; ``None`` is returned when the sample is too short or a denominator
is zero, so callers never divide by zero or surface a misleading figure.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .returns import daily_returns
from .risk import max_drawdown


@dataclass(slots=True)
class PerformanceMetrics:
    """Risk-adjusted performance summary for one instrument (fractions/ratios)."""

    annualized_return: float | None = None  # CAGR, fractional
    sharpe: float | None = None
    sortino: float | None = None
    calmar: float | None = None
    information_ratio: float | None = None
    risk_free_rate: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _daily_rf(risk_free_rate: float, trading_days: int) -> float:
    """Convert an annual risk-free rate into a per-bar rate (geometric)."""
    if risk_free_rate <= 0:
        return 0.0
    return (1.0 + risk_free_rate) ** (1.0 / trading_days) - 1.0


def annualized_return(close: pd.Series, trading_days: int = 252) -> float | None:
    """Compound annual growth rate (CAGR) implied by the sample.

    Annualises the full-sample total return by the number of *bars* observed, so
    it is horizon-consistent with the annualised volatility used elsewhere.
    """
    close = close.astype(float)
    n = len(close)
    if n < 2 or close.iloc[0] <= 0:
        return None
    total_growth = close.iloc[-1] / close.iloc[0]
    if total_growth <= 0:
        return None
    years = (n - 1) / trading_days
    if years <= 0:
        return None
    return float(total_growth ** (1.0 / years) - 1.0)


def sharpe_ratio(
    close: pd.Series, risk_free_rate: float = 0.0, trading_days: int = 252
) -> float | None:
    """Annualised Sharpe ratio (excess return / total volatility)."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return None
    sd = rets.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return None
    excess = rets.mean() - _daily_rf(risk_free_rate, trading_days)
    return float(excess / sd * np.sqrt(trading_days))


def sortino_ratio(
    close: pd.Series, risk_free_rate: float = 0.0, trading_days: int = 252
) -> float | None:
    """Annualised Sortino ratio (excess return / downside deviation).

    Downside deviation is taken relative to the risk-free rate as the minimum
    acceptable return, over the full sample (zeros counted for non-downside bars)
    — the convention that keeps it comparable across instruments.
    """
    rets = daily_returns(close)
    if len(rets) < 2:
        return None
    rf_daily = _daily_rf(risk_free_rate, trading_days)
    excess = rets - rf_daily
    downside = np.minimum(excess, 0.0)
    downside_dev = np.sqrt(np.mean(np.square(downside)))
    if downside_dev == 0 or np.isnan(downside_dev):
        return None
    return float(excess.mean() / downside_dev * np.sqrt(trading_days))


def calmar_ratio(close: pd.Series, trading_days: int = 252) -> float | None:
    """Annualised return divided by the absolute worst drawdown."""
    cagr = annualized_return(close, trading_days)
    mdd = max_drawdown(close)
    if cagr is None or mdd == 0:
        return None
    return float(cagr / abs(mdd))


def information_ratio(
    close: pd.Series, benchmark_close: pd.Series, trading_days: int = 252
) -> float | None:
    """Annualised active return divided by tracking error versus a benchmark."""
    a, b = _align_returns(close, benchmark_close)
    if len(a) < 2:
        return None
    active = a - b
    te = active.std(ddof=1)
    if te == 0 or np.isnan(te):
        return None
    return float(active.mean() / te * np.sqrt(trading_days))


def _align_returns(a_close: pd.Series, b_close: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Daily returns of two series aligned on their common dates."""
    a = daily_returns(a_close)
    b = daily_returns(b_close)
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    if joined.empty:
        empty = pd.Series(dtype=float)
        return empty, empty
    return joined.iloc[:, 0], joined.iloc[:, 1]


def compute_performance(
    close: pd.Series,
    *,
    risk_free_rate: float = 0.0,
    trading_days: int = 252,
    benchmark_close: pd.Series | None = None,
) -> PerformanceMetrics:
    """Compute all risk-adjusted ratios for a price series."""
    ir = (
        information_ratio(close, benchmark_close, trading_days)
        if benchmark_close is not None
        else None
    )
    return PerformanceMetrics(
        annualized_return=annualized_return(close, trading_days),
        sharpe=_round(sharpe_ratio(close, risk_free_rate, trading_days)),
        sortino=_round(sortino_ratio(close, risk_free_rate, trading_days)),
        calmar=_round(calmar_ratio(close, trading_days)),
        information_ratio=_round(ir),
        risk_free_rate=risk_free_rate,
    )


def _round(value: float | None, ndigits: int = 3) -> float | None:
    return None if value is None else round(value, ndigits)
