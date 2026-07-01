from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.analytics.tail_risk import (
    _norm_ppf,
    compute_tail_risk,
    historical_cvar,
    historical_var,
    parametric_var,
)


def _from_returns(rets, start="2023-01-02", base=100.0):
    prices = base * np.cumprod(1.0 + np.asarray(rets, dtype=float))
    idx = pd.bdate_range(start=start, periods=len(prices) + 1)
    return pd.Series(np.insert(prices, 0, base), index=idx, dtype=float)


@pytest.fixture
def noisy_close():
    rng = np.random.default_rng(42)
    return _from_returns(rng.normal(0.0005, 0.02, 400))


def test_var_is_positive_loss(noisy_close):
    assert historical_var(noisy_close, 0.95) > 0
    assert parametric_var(noisy_close, 0.95) > 0


def test_cvar_at_least_var(noisy_close):
    var = historical_var(noisy_close, 0.95)
    cvar = historical_cvar(noisy_close, 0.95)
    assert cvar >= var - 1e-12


def test_higher_confidence_increases_var(noisy_close):
    assert historical_var(noisy_close, 0.99) >= historical_var(noisy_close, 0.95)
    assert parametric_var(noisy_close, 0.99) >= parametric_var(noisy_close, 0.95)


def test_horizon_scaling_sqrt_time(noisy_close):
    one = parametric_var(noisy_close, 0.95, horizon_days=1)
    four = parametric_var(noisy_close, 0.95, horizon_days=4)
    assert four == pytest.approx(2.0 * one, rel=1e-9)


def test_norm_ppf_known_quantiles():
    assert _norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-4)
    assert _norm_ppf(0.95) == pytest.approx(1.644854, abs=1e-4)
    assert _norm_ppf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert _norm_ppf(0.025) == pytest.approx(-1.959964, abs=1e-4)


def test_norm_ppf_rejects_out_of_range():
    with pytest.raises(ValueError):
        _norm_ppf(0.0)
    with pytest.raises(ValueError):
        _norm_ppf(1.0)


def test_compute_tail_risk_fields(noisy_close):
    tr = compute_tail_risk(noisy_close, confidence=0.95, horizon_days=1)
    assert tr.confidence == 0.95
    assert tr.horizon_days == 1
    assert tr.historical_var > 0
    assert tr.parametric_var > 0
    d = tr.to_dict()
    assert set(d) >= {"historical_var", "historical_cvar", "parametric_var", "parametric_cvar"}


def test_short_series_is_zero():
    close = pd.Series([100.0], index=pd.bdate_range("2023-01-02", periods=1))
    assert historical_var(close) == 0.0
    assert parametric_var(close) == 0.0
