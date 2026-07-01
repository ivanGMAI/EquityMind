from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.analytics.benchmark import (
    alpha,
    beta,
    compute_benchmark_stats,
    correlation,
)


def _from_returns(rets, start="2023-01-02", base=100.0):
    prices = base * np.cumprod(1.0 + np.asarray(rets, dtype=float))
    idx = pd.bdate_range(start=start, periods=len(prices) + 1)
    return pd.Series(np.insert(prices, 0, base), index=idx, dtype=float)


@pytest.fixture
def bench_returns():
    rng = np.random.default_rng(7)
    return rng.normal(0.0004, 0.011, 300)


def test_beta_vs_self_is_one(bench_returns):
    b = _from_returns(bench_returns)
    assert beta(b, b) == pytest.approx(1.0, rel=1e-9)
    assert correlation(b, b) == pytest.approx(1.0, rel=1e-9)


def test_beta_of_leveraged_asset(bench_returns):
    b = _from_returns(bench_returns)
    a = _from_returns(2.0 * bench_returns)  # returns exactly 2x the benchmark
    assert beta(a, b) == pytest.approx(2.0, rel=1e-6)
    assert correlation(a, b) == pytest.approx(1.0, rel=1e-6)


def test_negative_beta_for_inverse(bench_returns):
    b = _from_returns(bench_returns)
    a = _from_returns(-1.0 * bench_returns)
    assert beta(a, b) < 0
    assert correlation(a, b) == pytest.approx(-1.0, rel=1e-6)


def test_alpha_near_zero_vs_self(bench_returns):
    b = _from_returns(bench_returns)
    assert alpha(b, b, risk_free_rate=0.0) == pytest.approx(0.0, abs=1e-9)


def test_compute_benchmark_stats_fields(bench_returns):
    b = _from_returns(bench_returns)
    a = _from_returns(1.3 * bench_returns + 0.0002)
    stats = compute_benchmark_stats(a, b, benchmark_ticker="SPY", risk_free_rate=0.03)
    assert stats.benchmark == "SPY"
    assert stats.beta is not None
    assert stats.r_squared is not None and 0.0 <= stats.r_squared <= 1.0
    assert stats.observations > 0


def test_misaligned_calendars_align_on_overlap():
    rng = np.random.default_rng(3)
    a = _from_returns(rng.normal(0, 0.01, 100), start="2023-01-02")
    b = _from_returns(rng.normal(0, 0.01, 100), start="2023-02-01")  # offset window
    # Overlapping dates only -> still computable, correlation within [-1, 1].
    corr = correlation(a, b)
    assert corr is None or -1.0 <= corr <= 1.0
