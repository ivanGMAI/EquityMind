from __future__ import annotations

import pandas as pd
import pytest

from equitymind.analytics.risk import compute_risk, max_drawdown


def _series(values):
    idx = pd.bdate_range(start="2023-01-02", periods=len(values))
    return pd.Series(values, index=idx, dtype=float)


def test_max_drawdown_negative():
    s = _series([100, 120, 60, 90])
    dd = max_drawdown(s)
    assert dd == pytest.approx(-0.5)  # 120 -> 60


def test_max_drawdown_monotonic_up_is_zero():
    s = _series([100, 101, 102, 103])
    assert max_drawdown(s) == 0.0


def test_risk_score_within_bounds(uptrend_history, downtrend_history):
    up = compute_risk(uptrend_history.close, trend_label="bullish")
    down = compute_risk(downtrend_history.close, trend_label="bearish")
    for r in (up, down):
        assert 0.0 <= r.score <= 100.0
        assert r.band in {"Low", "Moderate", "Elevated", "High"}


def test_bearish_scores_higher_than_bullish(uptrend_history):
    same = uptrend_history.close
    bullish = compute_risk(same, trend_label="bullish", momentum_return=0.05)
    bearish = compute_risk(same, trend_label="bearish", momentum_return=-0.05)
    assert bearish.score > bullish.score


def test_components_present(uptrend_history):
    r = compute_risk(uptrend_history.close, trend_label="neutral")
    assert set(r.components) == {"volatility", "drawdown", "trend", "momentum"}
