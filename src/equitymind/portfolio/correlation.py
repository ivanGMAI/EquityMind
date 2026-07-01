"""Cross-asset return, correlation and covariance matrices.

The building blocks for any portfolio view. Everything starts from a single
aligned daily-returns matrix (one column per instrument, inner-joined on common
trading dates) so equities, indices and crypto with different calendars combine
correctly. Correlation and covariance are derived from that matrix; covariance is
annualised to match the return/volatility conventions used elsewhere.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

from ..analytics.returns import daily_returns
from ..data.models import PriceHistory


def returns_matrix(histories: Mapping[str, PriceHistory]) -> pd.DataFrame:
    """Aligned daily-returns DataFrame (columns = tickers, common dates only)."""
    series: dict[str, pd.Series] = {
        ticker: daily_returns(h.close) for ticker, h in histories.items()
    }
    if not series:
        return pd.DataFrame()
    frame = pd.concat(series, axis=1, join="inner")
    frame.columns = list(series.keys())
    return frame.dropna()


def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix of the return columns."""
    if returns_df.empty:
        return pd.DataFrame()
    return returns_df.corr()


def covariance_matrix(returns_df: pd.DataFrame, trading_days: int = 252) -> pd.DataFrame:
    """Annualised covariance matrix of the return columns."""
    if returns_df.empty:
        return pd.DataFrame()
    return returns_df.cov(ddof=1) * trading_days


def average_pairwise_correlation(corr: pd.DataFrame) -> float:
    """Mean of the off-diagonal correlations (0.0 for <2 assets)."""
    if corr.empty or corr.shape[0] < 2:
        return 0.0
    m = corr.to_numpy()
    off_diag = m[~np.eye(m.shape[0], dtype=bool)]
    return float(np.nanmean(off_diag))
