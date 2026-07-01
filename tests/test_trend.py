from __future__ import annotations

from equitymind.analytics.trend import detect_trend


def test_bullish(uptrend_history):
    result = detect_trend(uptrend_history.close, 20, 50, 1.0)
    assert result.classification == "bullish"
    assert result.price_vs_slow_pct is not None and result.price_vs_slow_pct > 0


def test_bearish(downtrend_history):
    result = detect_trend(downtrend_history.close, 20, 50, 1.0)
    assert result.classification == "bearish"


def test_neutral(flat_history):
    result = detect_trend(flat_history.close, 20, 50, 1.0)
    assert result.classification == "neutral"


def test_insufficient_history_is_neutral(uptrend_history):
    short = uptrend_history.close.iloc[:10]
    result = detect_trend(short, 20, 50, 1.0)
    assert result.classification == "neutral"
    assert result.slow_sma is None


def test_result_serialisable(uptrend_history):
    result = detect_trend(uptrend_history.close)
    d = result.to_dict()
    assert d["classification"] == "bullish"
    assert "rationale" in d
