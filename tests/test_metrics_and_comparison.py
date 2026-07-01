from __future__ import annotations

from equitymind.analytics.metrics import compute_metrics
from equitymind.comparison import compare_assets


def test_compute_metrics_fields(uptrend_history):
    m = compute_metrics(uptrend_history)
    assert m.ticker == "UP"
    assert m.bars == len(uptrend_history)
    assert m.trend is not None and m.trend.classification == "bullish"
    assert m.risk is not None and 0 <= m.risk.score <= 100
    assert "1d" in m.returns and "30d" in m.returns


def test_metrics_payload_percentages(uptrend_history):
    payload = compute_metrics(uptrend_history).to_payload()
    assert "returns_pct" in payload
    assert payload["risk"]["score"] is not None
    assert payload["trend"]["classification"] == "bullish"


def test_metrics_payload_has_performance_and_tail_risk(uptrend_history):
    payload = compute_metrics(uptrend_history).to_payload()
    assert set(payload["performance"]) >= {"sharpe", "sortino", "calmar", "annualized_return_pct"}
    assert set(payload["tail_risk"]) >= {
        "historical_var_pct",
        "parametric_var_pct",
        "confidence_pct",
    }
    # No benchmark passed -> benchmark section omitted.
    assert "benchmark" not in payload


def test_metrics_payload_includes_benchmark_when_supplied(uptrend_history, flat_history):
    m = compute_metrics(
        uptrend_history, benchmark_close=flat_history.close, benchmark_ticker="BENCH"
    )
    payload = m.to_payload()
    assert payload["benchmark"]["benchmark"] == "BENCH"
    assert "beta" in payload["benchmark"]


def test_comparison_ranks_higher_reward_risk_first(uptrend_history, flat_history):
    m_up = compute_metrics(uptrend_history)
    m_flat = compute_metrics(flat_history)
    comp = compare_assets([m_flat, m_up], return_basis="cumulative")
    # Uptrend has positive return -> positive ratio -> ranks above flat/zero.
    assert comp.best is not None
    assert comp.best.ticker == "UP"
    assert comp.entries[0].rank == 1


def test_comparison_dataframe_shape(uptrend_history, downtrend_history):
    metrics = [compute_metrics(uptrend_history), compute_metrics(downtrend_history)]
    df = compare_assets(metrics).to_dataframe()
    assert len(df) == 2
    assert "reward_risk_ratio" in df.columns
