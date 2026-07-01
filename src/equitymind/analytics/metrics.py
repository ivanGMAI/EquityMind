"""Aggregate per-asset metrics.

:class:`AssetMetrics` is the single structured summary produced for each
instrument. It is the hand-off point between numerical analysis and the two
downstream consumers — the AI analyst and the report generator — so it exposes a
clean, JSON-serialisable :meth:`AssetMetrics.to_payload` view with values
pre-converted to human-friendly percentages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config import AnalyticsConfig, RiskConfig, Settings
from ..data.models import PriceHistory
from . import indicators, returns, volatility
from .benchmark import BenchmarkStats, compute_benchmark_stats
from .performance import PerformanceMetrics, compute_performance
from .risk import RiskAssessment, compute_risk
from .tail_risk import TailRisk, compute_tail_risk
from .trend import TrendResult, detect_trend


def _pct(value: float | None) -> float | None:
    """Fraction -> percentage rounded to 2dp (``None`` passes through)."""
    return None if value is None else round(value * 100.0, 2)


@dataclass(slots=True)
class AssetMetrics:
    ticker: str
    name: str
    asset_class: str
    currency: str
    as_of: str
    period_start: str
    period_end: str
    bars: int
    last_price: float
    returns: dict[str, float | None]  # fractional, keyed "1d"/"7d"/"30d"
    cumulative_return: float
    annualized_volatility: float
    rolling_volatility_latest: float
    indicators: dict[str, float | None] = field(default_factory=dict)
    trend: TrendResult | None = None
    risk: RiskAssessment | None = None
    performance: PerformanceMetrics | None = None
    tail_risk: TailRisk | None = None
    benchmark: BenchmarkStats | None = None

    # ------------------------------------------------------------------ payload
    def to_payload(self) -> dict:
        """Compact, percentage-formatted dict for the LLM and reports.

        This is deliberately *not* the raw dataclass — it presents percentages
        (not fractions) and only the fields useful for narrative generation, so
        the model receives an unambiguous, token-efficient brief.
        """
        trend = self.trend
        risk = self.risk
        perf = self.performance
        tail = self.tail_risk
        bench = self.benchmark
        payload = {
            "ticker": self.ticker,
            "name": self.name,
            "asset_class": self.asset_class,
            "currency": self.currency,
            "as_of": self.as_of,
            "window": {"start": self.period_start, "end": self.period_end, "bars": self.bars},
            "last_price": round(self.last_price, 4),
            "returns_pct": {k: _pct(v) for k, v in self.returns.items()},
            "cumulative_return_pct": _pct(self.cumulative_return),
            "volatility": {
                "annualized_pct": _pct(self.annualized_volatility),
                "rolling_latest_pct": _pct(self.rolling_volatility_latest),
            },
            "indicators": {
                k: (round(v, 4) if v is not None else None) for k, v in self.indicators.items()
            },
            "trend": {
                "classification": trend.classification if trend else "unknown",
                "price_vs_slow_ma_pct": round(trend.price_vs_slow_pct, 2)
                if trend and trend.price_vs_slow_pct is not None
                else None,
                "slow_ma_slope_pct": round(trend.slow_slope_pct, 2)
                if trend and trend.slow_slope_pct is not None
                else None,
                "rationale": trend.rationale if trend else "",
            },
            "risk": {
                "score": risk.score if risk else None,
                "band": risk.band if risk else None,
                "max_drawdown_pct": _pct(risk.max_drawdown) if risk else None,
                "components": risk.components if risk else {},
            },
            "performance": {
                "annualized_return_pct": _pct(perf.annualized_return) if perf else None,
                "sharpe": perf.sharpe if perf else None,
                "sortino": perf.sortino if perf else None,
                "calmar": perf.calmar if perf else None,
                "information_ratio": perf.information_ratio if perf else None,
            },
            "tail_risk": {
                "confidence_pct": round(tail.confidence * 100.0, 1) if tail else None,
                "horizon_days": tail.horizon_days if tail else None,
                "historical_var_pct": _pct(tail.historical_var) if tail else None,
                "historical_cvar_pct": _pct(tail.historical_cvar) if tail else None,
                "parametric_var_pct": _pct(tail.parametric_var) if tail else None,
                "parametric_cvar_pct": _pct(tail.parametric_cvar) if tail else None,
            },
        }
        if bench is not None:
            payload["benchmark"] = {
                "benchmark": bench.benchmark,
                "beta": bench.beta,
                "alpha_annual_pct": _pct(bench.alpha_annual),
                "correlation": bench.correlation,
                "r_squared": bench.r_squared,
            }
        return payload


def compute_metrics(
    history: PriceHistory,
    analytics: AnalyticsConfig | None = None,
    risk_cfg: RiskConfig | None = None,
    *,
    benchmark_close: pd.Series | None = None,
    benchmark_ticker: str = "",
) -> AssetMetrics:
    """Run the full analytics stack over one instrument.

    Args:
        history: Validated price history.
        analytics: Analytics parameters (windows, periods). Defaults applied.
        risk_cfg: Risk-scoring parameters. Defaults applied.
        benchmark_close: Optional benchmark close series enabling beta/alpha and
            the information ratio. ``None`` skips benchmark-relative stats.
        benchmark_ticker: Label for the benchmark (used in the payload).
    """
    analytics = analytics or AnalyticsConfig()
    risk_cfg = risk_cfg or RiskConfig()
    close = history.close

    ret_map = returns.compute_returns(close, analytics.return_periods_days)
    ann_vol = volatility.annualized_volatility(close, analytics.trading_days_per_year)
    roll_vol = volatility.latest_rolling_volatility(
        close, analytics.volatility_window, analytics.trading_days_per_year
    )

    ind: dict[str, float | None] = {}
    for w in analytics.sma_windows:
        ind[f"sma_{w}"] = indicators.latest(indicators.sma(close, w))
    for w in analytics.ema_windows:
        ind[f"ema_{w}"] = indicators.latest(indicators.ema(close, w))
    ind[f"rsi_{analytics.rsi_window}"] = indicators.latest(
        indicators.rsi(close, analytics.rsi_window)
    )

    fast_w = min(analytics.sma_windows) if analytics.sma_windows else 20
    slow_w = max(analytics.sma_windows) if analytics.sma_windows else 50
    trend = detect_trend(close, fast_w, slow_w, analytics.trend_neutral_band_pct)

    # Momentum feeds risk: use the longest configured return window.
    momentum_key = f"{max(analytics.return_periods_days)}d"
    risk = compute_risk(
        close,
        trend_label=trend.classification,
        momentum_return=ret_map.get(momentum_key),
        weights=risk_cfg.weights.model_dump(),
        volatility_ceiling=risk_cfg.volatility_ceiling,
        drawdown_ceiling=risk_cfg.drawdown_ceiling,
        trading_days=analytics.trading_days_per_year,
    )

    performance = compute_performance(
        close,
        risk_free_rate=analytics.risk_free_rate,
        trading_days=analytics.trading_days_per_year,
        benchmark_close=benchmark_close,
    )
    tail = compute_tail_risk(
        close,
        confidence=analytics.var_confidence,
        horizon_days=analytics.var_horizon_days,
    )
    benchmark_stats = None
    if benchmark_close is not None and benchmark_ticker:
        benchmark_stats = compute_benchmark_stats(
            close,
            benchmark_close,
            benchmark_ticker=benchmark_ticker,
            risk_free_rate=analytics.risk_free_rate,
            trading_days=analytics.trading_days_per_year,
        )

    return AssetMetrics(
        ticker=history.ticker,
        name=history.name or history.ticker,
        asset_class=history.asset_class,
        currency=history.currency,
        as_of=history.end.strftime("%Y-%m-%d"),
        period_start=history.start.strftime("%Y-%m-%d"),
        period_end=history.end.strftime("%Y-%m-%d"),
        bars=len(history),
        last_price=history.last_price,
        returns=ret_map,
        cumulative_return=returns.cumulative_return(close),
        annualized_volatility=ann_vol,
        rolling_volatility_latest=roll_vol,
        indicators=ind,
        trend=trend,
        risk=risk,
        performance=performance,
        tail_risk=tail,
        benchmark=benchmark_stats,
    )


def compute_metrics_from_settings(
    history: PriceHistory,
    settings: Settings,
    *,
    benchmark_close: pd.Series | None = None,
    benchmark_ticker: str = "",
) -> AssetMetrics:
    """Convenience wrapper pulling analytics/risk config from :class:`Settings`."""
    return compute_metrics(
        history,
        settings.analytics,
        settings.risk,
        benchmark_close=benchmark_close,
        benchmark_ticker=benchmark_ticker,
    )
