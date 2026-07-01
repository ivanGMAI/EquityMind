"""Return calculations.

All functions operate on a close-price :class:`pandas.Series` indexed by date and
are pure (no I/O, no mutation of the input). Period returns use *calendar*
look-back so a "7d return" means "versus the last close roughly 7 calendar days
ago" — matching how such figures are quoted, and robust to weekends/holidays.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


def daily_returns(close: pd.Series) -> pd.Series:
    """Simple period-over-period returns (fractional, e.g. 0.01 = +1%)."""
    return close.astype(float).pct_change().dropna()


def log_returns(close: pd.Series) -> pd.Series:
    """Continuously-compounded (log) returns."""
    close = close.astype(float)
    return np.log(close / close.shift(1)).dropna()


def _price_n_calendar_days_ago(close: pd.Series, days: int) -> float | None:
    """Last close at or before ``last_date - days``; ``None`` if unavailable."""
    if close.empty:
        return None
    target = close.index[-1] - pd.Timedelta(days=days)
    prior = close.loc[:target]
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def period_return(close: pd.Series, days: int) -> float | None:
    """Fractional return over the trailing ``days`` calendar days.

    Returns ``None`` when the history is too short to cover the window.
    """
    close = close.astype(float)
    past = _price_n_calendar_days_ago(close, days)
    if past is None or past == 0:
        return None
    return float(close.iloc[-1]) / past - 1.0


def compute_returns(close: pd.Series, periods_days: Iterable[int]) -> dict[str, float | None]:
    """Return a ``{"<n>d": fractional_return}`` map for the requested windows."""
    return {f"{d}d": period_return(close, d) for d in periods_days}


def cumulative_return(close: pd.Series) -> float:
    """Total fractional return across the full sample."""
    close = close.astype(float)
    if len(close) < 2 or close.iloc[0] == 0:
        return 0.0
    return float(close.iloc[-1] / close.iloc[0] - 1.0)


def cumulative_return_series(close: pd.Series) -> pd.Series:
    """Growth of 1 unit invested at the first bar (for equity-curve charts)."""
    close = close.astype(float)
    if close.empty:
        return close
    return close / close.iloc[0]
