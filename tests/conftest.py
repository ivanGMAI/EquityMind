"""Shared pytest fixtures.

Everything here is synthetic and offline — no network, no yfinance — so the test
suite is deterministic and fast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from equitymind.data.models import PriceHistory


def _frame(prices: np.ndarray, start: str = "2023-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start=start, periods=len(prices))
    close = pd.Series(prices, index=idx, dtype=float)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(len(prices), 1_000_000.0),
        }
    )


def make_history(prices, *, ticker: str = "TEST", **kwargs) -> PriceHistory:
    """Build a :class:`PriceHistory` from a price array."""
    prices = np.asarray(prices, dtype=float)
    return PriceHistory(ticker=ticker, frame=_frame(prices), **kwargs)


@pytest.fixture
def uptrend_history() -> PriceHistory:
    # Steadily rising with mild noise; long enough for a 50-bar SMA.
    rng = np.random.default_rng(1)
    prices = 100 * (1.0 + 0.004) ** np.arange(160) + rng.normal(0, 0.2, 160)
    return make_history(prices, ticker="UP")


@pytest.fixture
def downtrend_history() -> PriceHistory:
    rng = np.random.default_rng(2)
    prices = 200 * (1.0 - 0.004) ** np.arange(160) + rng.normal(0, 0.2, 160)
    return make_history(prices, ticker="DOWN")


@pytest.fixture
def flat_history() -> PriceHistory:
    rng = np.random.default_rng(3)
    prices = 100 + rng.normal(0, 0.3, 160)
    return make_history(prices, ticker="FLAT")


@pytest.fixture
def analysis_report():
    """A fully-populated AnalysisReport (metrics, comparison, portfolio, AI) offline."""
    from datetime import datetime, timezone

    from equitymind.ai.analyst import MarketAnalyst
    from equitymind.ai.providers import MockProvider
    from equitymind.analytics.metrics import compute_metrics
    from equitymind.comparison.compare_assets import compare_assets
    from equitymind.pipeline import AnalysisReport, AssetAnalysis
    from equitymind.portfolio.analyze import analyze_portfolio

    def _hist(seed, drift, ticker, asset_class, vol=0.9):
        rng = np.random.default_rng(seed)
        prices = 100 * (1 + drift) ** np.arange(220) + np.cumsum(rng.normal(0, vol, 220))
        prices = np.abs(prices) + 10
        return make_history(prices, ticker=ticker, asset_class=asset_class, name=ticker)

    histories = {
        "AAA": _hist(1, 0.003, "AAA", "equity"),
        "BBB": _hist(2, 0.001, "BBB", "equity"),
        "GLD": _hist(4, 0.0015, "GLD", "commodity", 0.6),
        "SPY": _hist(3, 0.0015, "SPY", "index", 0.6),
    }
    analyst = MarketAnalyst(MockProvider())
    analyses = {}
    for ticker, hist in histories.items():
        bench = None if ticker == "SPY" else histories["SPY"].close
        m = compute_metrics(
            hist, benchmark_close=bench, benchmark_ticker="" if bench is None else "SPY"
        )
        analyses[ticker] = AssetAnalysis(history=hist, metrics=m, commentary=analyst.analyze(m))

    return AnalysisReport(
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        ai_provider="mock",
        ai_model="rule-based",
        assets=analyses,
        comparison=compare_assets([a.metrics for a in analyses.values()]),
        portfolio=analyze_portfolio(histories, risk_free_rate=0.04),
    )
