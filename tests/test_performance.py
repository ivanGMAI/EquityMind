from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.analytics.performance import (
    annualized_return,
    calmar_ratio,
    compute_performance,
    information_ratio,
    sharpe_ratio,
    sortino_ratio,
)


def _series(values, start="2023-01-02"):
    idx = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def _from_returns(rets, start="2023-01-02", base=100.0):
    prices = base * np.cumprod(1.0 + np.asarray(rets, dtype=float))
    return _series(np.insert(prices, 0, base), start=start)


def test_sharpe_sign_tracks_direction(uptrend_history, downtrend_history):
    assert sharpe_ratio(uptrend_history.close) > 0
    assert sharpe_ratio(downtrend_history.close) < 0


def test_annualized_return_sign(uptrend_history, downtrend_history):
    assert annualized_return(uptrend_history.close) > 0
    assert annualized_return(downtrend_history.close) < 0


def test_calmar_positive_for_uptrend(uptrend_history):
    assert calmar_ratio(uptrend_history.close) > 0


def test_sortino_at_least_sharpe_for_uptrend(uptrend_history):
    # With upside dispersion excluded, Sortino >= Sharpe for a rising series.
    s = sharpe_ratio(uptrend_history.close)
    so = sortino_ratio(uptrend_history.close)
    assert so is not None and s is not None
    assert so >= s - 1e-9


def test_higher_risk_free_lowers_sharpe(uptrend_history):
    low = sharpe_ratio(uptrend_history.close, risk_free_rate=0.0)
    high = sharpe_ratio(uptrend_history.close, risk_free_rate=0.20)
    assert high < low


def test_information_ratio_zero_active_is_none(uptrend_history):
    # Identical series => zero active return => undefined IR.
    assert information_ratio(uptrend_history.close, uptrend_history.close) is None


def test_information_ratio_defined_vs_different_benchmark(uptrend_history, flat_history):
    ir = information_ratio(uptrend_history.close, flat_history.close)
    assert ir is not None and np.isfinite(ir)


def test_insufficient_data_returns_none():
    one = _series([100.0])
    assert sharpe_ratio(one) is None
    assert annualized_return(one) is None
    assert sortino_ratio(one) is None


def test_zero_volatility_series_is_none():
    flat = _series([100.0] * 30)  # constant price => zero std
    assert sharpe_ratio(flat) is None
    assert sortino_ratio(flat) is None


def test_compute_performance_bundle(uptrend_history, flat_history):
    perf = compute_performance(
        uptrend_history.close,
        risk_free_rate=0.02,
        benchmark_close=flat_history.close,
    )
    assert perf.sharpe is not None
    assert perf.sortino is not None
    assert perf.information_ratio is not None
    assert perf.risk_free_rate == 0.02


def test_sharpe_matches_manual_calc():
    # Deterministic returns: verify against the textbook formula.
    rets = [0.01, -0.005, 0.008, -0.002, 0.012, 0.0, -0.004, 0.006]
    close = _from_returns(rets)
    r = pd.Series(rets, dtype=float)
    expected = r.mean() / r.std(ddof=1) * np.sqrt(252)
    assert sharpe_ratio(close, risk_free_rate=0.0) == pytest.approx(expected, rel=1e-6)
