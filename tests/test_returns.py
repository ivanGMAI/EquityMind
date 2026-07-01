from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.analytics import returns


def _series(values, start="2023-01-02"):
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_cumulative_return_simple():
    s = _series([100, 110])
    assert returns.cumulative_return(s) == pytest.approx(0.10)


def test_cumulative_return_short_series_is_zero():
    assert returns.cumulative_return(_series([100])) == 0.0


def test_daily_returns_length():
    s = _series([100, 101, 102, 100])
    assert len(returns.daily_returns(s)) == 3


def test_period_return_calendar_lookback():
    # Daily bars; a 7-calendar-day window spans ~5 business days.
    prices = np.linspace(100, 120, 30)
    idx = pd.bdate_range(start="2023-01-02", periods=30)
    s = pd.Series(prices, index=idx)
    r = returns.period_return(s, 7)
    assert r is not None and r > 0


def test_period_return_none_when_too_short():
    s = _series([100, 101])
    # 400 calendar days ago does not exist in a 2-point series.
    assert returns.period_return(s, 400) is None


def test_compute_returns_keys():
    s = _series(list(np.linspace(100, 130, 60)))
    out = returns.compute_returns(s, [1, 7, 30])
    assert set(out) == {"1d", "7d", "30d"}


def test_cumulative_return_series_starts_at_one():
    s = _series([50, 55, 60])
    curve = returns.cumulative_return_series(s)
    assert curve.iloc[0] == pytest.approx(1.0)
    assert curve.iloc[-1] == pytest.approx(1.2)
