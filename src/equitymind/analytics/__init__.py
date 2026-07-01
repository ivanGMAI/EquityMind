"""Quantitative analytics: returns, volatility, indicators, trend and risk.

Individual functions live in focused modules; :mod:`metrics` aggregates them
into a single :class:`AssetMetrics` summary per instrument.
"""

from __future__ import annotations

from . import benchmark, indicators, performance, returns, risk, tail_risk, trend, volatility
from .benchmark import BenchmarkStats, compute_benchmark_stats
from .metrics import (
    AssetMetrics,
    compute_metrics,
    compute_metrics_from_settings,
)
from .performance import PerformanceMetrics, compute_performance
from .risk import RiskAssessment, compute_risk, max_drawdown
from .tail_risk import TailRisk, compute_tail_risk
from .trend import TrendResult, detect_trend

__all__ = [
    "returns",
    "volatility",
    "indicators",
    "trend",
    "risk",
    "performance",
    "tail_risk",
    "benchmark",
    "AssetMetrics",
    "compute_metrics",
    "compute_metrics_from_settings",
    "RiskAssessment",
    "compute_risk",
    "max_drawdown",
    "PerformanceMetrics",
    "compute_performance",
    "TailRisk",
    "compute_tail_risk",
    "BenchmarkStats",
    "compute_benchmark_stats",
    "TrendResult",
    "detect_trend",
]
