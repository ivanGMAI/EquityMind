from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.analytics import indicators


def _series(values):
    idx = pd.bdate_range(start="2023-01-02", periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_sma_matches_manual():
    s = _series([1, 2, 3, 4, 5])
    result = indicators.sma(s, 3).dropna()
    assert result.iloc[0] == pytest.approx(2.0)  # mean(1,2,3)
    assert result.iloc[-1] == pytest.approx(4.0)  # mean(3,4,5)


def test_ema_last_value_reasonable():
    s = _series(list(range(1, 21)))
    ema = indicators.ema(s, 5)
    assert ema.iloc[-1] < s.iloc[-1]  # trails a rising series
    assert not ema.isna().any()


def test_rsi_bounds_and_uptrend():
    s = _series(list(np.linspace(100, 200, 60)))
    rsi = indicators.rsi(s, 14).dropna()
    assert rsi.between(0, 100).all()
    # Monotonic rise -> RSI pinned high.
    assert rsi.iloc[-1] > 80


def test_rsi_downtrend_low():
    s = _series(list(np.linspace(200, 100, 60)))
    rsi = indicators.rsi(s, 14).dropna()
    assert rsi.iloc[-1] < 20


def test_bollinger_ordering():
    s = _series(list(np.linspace(100, 120, 40)))
    bb = indicators.bollinger_bands(s, window=20)
    valid = bb.upper.dropna().index
    assert (bb.upper.loc[valid] >= bb.middle.loc[valid]).all()
    assert (bb.lower.loc[valid] <= bb.middle.loc[valid]).all()


def test_latest_helper():
    s = _series([1, 2, 3])
    assert indicators.latest(indicators.sma(s, 2)) == pytest.approx(2.5)
    assert indicators.latest(pd.Series([np.nan, np.nan])) is None
