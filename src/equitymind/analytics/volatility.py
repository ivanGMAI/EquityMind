"""Volatility measures.

Volatility is expressed as annualised standard deviation of daily returns, the
market-standard convention. The annualisation factor (``trading_days``) is
injected so the same code serves daily, weekly or intraday series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .returns import daily_returns


def annualized_volatility(close: pd.Series, trading_days: int = 252) -> float:
    """Annualised volatility over the full sample (fraction, e.g. 0.25 = 25%)."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return 0.0
    return float(rets.std(ddof=1) * np.sqrt(trading_days))


def rolling_volatility(close: pd.Series, window: int = 21, trading_days: int = 252) -> pd.Series:
    """Rolling annualised volatility series.

    Args:
        window: Rolling window length in bars.
        trading_days: Annualisation factor.
    """
    rets = daily_returns(close)
    if rets.empty:
        return pd.Series(dtype=float)
    return rets.rolling(window).std(ddof=1) * np.sqrt(trading_days)


def latest_rolling_volatility(close: pd.Series, window: int = 21, trading_days: int = 252) -> float:
    """Most recent value of the rolling-volatility series (0.0 if undefined)."""
    series = rolling_volatility(close, window, trading_days).dropna()
    return float(series.iloc[-1]) if not series.empty else 0.0


def downside_volatility(close: pd.Series, trading_days: int = 252, mar: float = 0.0) -> float:
    """Annualised volatility of returns below the minimum acceptable return.

    A useful complement to plain volatility: it ignores upside dispersion, which
    investors do not experience as risk.
    """
    rets = daily_returns(close)
    downside = rets[rets < mar]
    if len(downside) < 2:
        return 0.0
    return float(downside.std(ddof=1) * np.sqrt(trading_days))
