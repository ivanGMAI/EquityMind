from __future__ import annotations

import numpy as np

from equitymind.alerts.volatility_alerts import detect_volatility_spike
from equitymind.backtesting.trend_backtest import backtest_sma_crossover


def test_backtest_runs(uptrend_history):
    result = backtest_sma_crossover(uptrend_history, fast_window=20, slow_window=50)
    assert result is not None
    assert result.ticker == "UP"
    assert 0.0 <= result.exposure_pct <= 100.0
    assert result.caveats  # caveats are always surfaced


def test_backtest_none_when_too_short(uptrend_history):
    short = uptrend_history
    short.frame = short.frame.iloc[:30]
    assert backtest_sma_crossover(short, fast_window=20, slow_window=50) is None


def test_volatility_spike_detected():
    # Calm baseline then a sharp jump to trigger a rolling-vol spike.
    from tests.conftest import make_history

    calm = np.linspace(100, 101, 120)
    shock = np.array([101, 90, 112, 88, 115, 85])  # violent swings at the end
    prices = np.concatenate([calm, shock])
    hist = make_history(prices, ticker="SPIKE")
    alert = detect_volatility_spike(hist, window=10, lookback=60, zscore_threshold=1.5)
    assert alert is not None
    assert alert.kind == "volatility_spike"


def test_no_spike_on_calm_series():
    from tests.conftest import make_history

    prices = np.linspace(100, 105, 180)
    hist = make_history(prices, ticker="CALM")
    assert detect_volatility_spike(hist) is None
