from __future__ import annotations

import numpy as np
import pandas as pd

from equitymind.analytics import volatility


def _series(values):
    idx = pd.bdate_range(start="2023-01-02", periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_annualized_volatility_nonnegative(uptrend_history):
    v = volatility.annualized_volatility(uptrend_history.close)
    assert v >= 0.0


def test_flat_series_low_vol():
    s = _series([100.0] * 50)
    assert volatility.annualized_volatility(s) == 0.0


def test_noisier_series_has_higher_vol():
    rng = np.random.default_rng(0)
    calm = _series(100 + rng.normal(0, 0.1, 200))
    wild = _series(100 + rng.normal(0, 2.0, 200))
    assert volatility.annualized_volatility(wild) > volatility.annualized_volatility(calm)


def test_latest_rolling_volatility_defined(uptrend_history):
    v = volatility.latest_rolling_volatility(uptrend_history.close, window=21)
    assert v >= 0.0


def test_rolling_volatility_series_length(uptrend_history):
    series = volatility.rolling_volatility(uptrend_history.close, window=21)
    # Same index space as daily returns (one shorter than prices).
    assert len(series) == len(uptrend_history.close) - 1
