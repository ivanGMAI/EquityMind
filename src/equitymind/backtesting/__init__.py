"""Backtesting utilities for trend signals."""

from __future__ import annotations

from .trend_backtest import BacktestResult, backtest_sma_crossover

__all__ = ["BacktestResult", "backtest_sma_crossover"]
