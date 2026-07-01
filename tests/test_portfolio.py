from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.data.models import PriceHistory
from equitymind.portfolio import optimizer
from equitymind.portfolio.analyze import analyze_portfolio
from equitymind.portfolio.correlation import (
    average_pairwise_correlation,
    correlation_matrix,
    covariance_matrix,
    returns_matrix,
)


def _history(rets, ticker, start="2023-01-02", base=100.0):
    prices = base * np.cumprod(1.0 + np.asarray(rets, dtype=float))
    prices = np.insert(prices, 0, base)
    idx = pd.bdate_range(start=start, periods=len(prices))
    close = pd.Series(prices, index=idx, dtype=float)
    frame = pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1e6}
    )
    return PriceHistory(ticker=ticker, frame=frame, name=ticker)


@pytest.fixture
def three_assets():
    rng = np.random.default_rng(11)
    n = 400
    a = rng.normal(0.0008, 0.012, n)
    b = rng.normal(0.0003, 0.020, n)
    c = rng.normal(0.0005, 0.008, n)
    return {
        "AAA": _history(a, "AAA"),
        "BBB": _history(b, "BBB"),
        "CCC": _history(c, "CCC"),
    }


# ---- correlation building blocks -------------------------------------------
def test_returns_matrix_alignment(three_assets):
    rm = returns_matrix(three_assets)
    assert list(rm.columns) == ["AAA", "BBB", "CCC"]
    assert rm.notna().all().all()


def test_correlation_matrix_diagonal_one(three_assets):
    corr = correlation_matrix(returns_matrix(three_assets))
    assert np.allclose(np.diag(corr.to_numpy()), 1.0)


def test_covariance_is_annualised(three_assets):
    rm = returns_matrix(three_assets)
    daily = rm.cov(ddof=1).to_numpy()
    annual = covariance_matrix(rm, trading_days=252).to_numpy()
    assert np.allclose(annual, daily * 252)


def test_average_pairwise_correlation_range(three_assets):
    avg = average_pairwise_correlation(correlation_matrix(returns_matrix(three_assets)))
    assert -1.0 <= avg <= 1.0


# ---- optimiser --------------------------------------------------------------
def test_weights_sum_to_one(three_assets):
    cov = covariance_matrix(returns_matrix(three_assets)).to_numpy()
    mu = returns_matrix(three_assets).mean().to_numpy() * 252
    for w in (
        optimizer.min_variance_weights(cov),
        optimizer.max_sharpe_weights(mu, cov),
        optimizer.risk_parity_weights(cov),
    ):
        assert w.sum() == pytest.approx(1.0, rel=1e-9)


def test_min_variance_has_lowest_volatility(three_assets):
    cov = covariance_matrix(returns_matrix(three_assets)).to_numpy()
    n = cov.shape[0]
    equal = np.full(n, 1.0 / n)
    mv = optimizer.min_variance_weights(cov)
    assert (
        optimizer.portfolio_volatility(mv, cov)
        <= optimizer.portfolio_volatility(equal, cov) + 1e-12
    )


def test_max_sharpe_beats_equal_weight(three_assets):
    rm = returns_matrix(three_assets)
    cov = covariance_matrix(rm).to_numpy()
    mu = rm.mean().to_numpy() * 252
    n = cov.shape[0]
    equal = np.full(n, 1.0 / n)
    ms = optimizer.max_sharpe_weights(mu, cov, risk_free_rate=0.0)
    assert (
        optimizer.portfolio_sharpe(ms, mu, cov) >= optimizer.portfolio_sharpe(equal, mu, cov) - 1e-9
    )


def test_risk_parity_equalises_contributions(three_assets):
    cov = covariance_matrix(returns_matrix(three_assets)).to_numpy()
    w = optimizer.risk_parity_weights(cov)
    assert np.all(w > 0)  # long-only
    rc = optimizer.risk_contributions(w, cov)
    assert rc.max() - rc.min() < 0.02  # contributions roughly equal


def test_efficient_frontier_sorted_and_sized(three_assets):
    rm = returns_matrix(three_assets)
    cov = covariance_matrix(rm).to_numpy()
    mu = rm.mean().to_numpy() * 252
    frontier = optimizer.efficient_frontier(mu, cov, n_points=20)
    assert len(frontier) == 20
    vols = [p["volatility"] for p in frontier]
    assert vols == sorted(vols)


# ---- report -----------------------------------------------------------------
def test_analyze_portfolio_report(three_assets):
    rep = analyze_portfolio(three_assets, risk_free_rate=0.03)
    assert rep is not None
    assert set(rep.allocations) == {"equal_weight", "min_variance", "max_sharpe", "risk_parity"}
    # each allocation's weights cover all tickers and sum ~100%
    for alloc in rep.allocations.values():
        assert set(alloc.weights) == set(rep.tickers)
        assert sum(alloc.weights.values()) == pytest.approx(100.0, abs=0.5)
    payload = rep.to_payload()
    assert "correlation" in payload and "allocations" in payload


def test_analyze_portfolio_needs_two_assets():
    rng = np.random.default_rng(1)
    single = {"AAA": _history(rng.normal(0, 0.01, 100), "AAA")}
    assert analyze_portfolio(single) is None
