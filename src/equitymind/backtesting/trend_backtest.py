"""Simple trend (SMA-crossover) backtester.

Evaluates whether the moving-average trend signal used by the analytics layer
would have added value historically, using a transparent long/flat rule: hold
the asset when the fast SMA is above the slow SMA, sit in cash otherwise, acting
on the *next* bar to avoid look-ahead bias.

This is a research/diagnostic tool for judging signal quality — it is not a
trading recommendation and makes the usual backtest caveats (no costs, no
slippage, in-sample) explicit in its output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from ..analytics.indicators import sma
from ..data.models import PriceHistory


@dataclass(slots=True)
class BacktestResult:
    ticker: str
    strategy: str
    bars: int
    total_return_pct: float
    buy_and_hold_return_pct: float
    excess_return_pct: float
    n_trades: int
    win_rate_pct: float | None
    exposure_pct: float
    max_drawdown_pct: float
    sharpe_like: float | None
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    return float((equity / running_max - 1.0).min())


def _trade_returns(position: pd.Series, gross: pd.Series) -> list[float]:
    """Per-trade returns for each contiguous long segment."""
    trades: list[float] = []
    in_trade = False
    cum = 1.0
    for pos, g in zip(position, gross, strict=False):
        if pos == 1:
            cum *= 1.0 + g
            in_trade = True
        elif in_trade:
            trades.append(cum - 1.0)
            cum, in_trade = 1.0, False
    if in_trade:
        trades.append(cum - 1.0)
    return trades


def backtest_sma_crossover(
    history: PriceHistory,
    *,
    fast_window: int = 20,
    slow_window: int = 50,
    trading_days: int = 252,
) -> BacktestResult | None:
    """Backtest a long/flat SMA-crossover strategy on one instrument.

    Returns ``None`` if the history is too short to form the slow SMA.
    """
    close = history.close
    if len(close) <= slow_window + 1:
        return None

    fast = sma(close, fast_window)
    slow = sma(close, slow_window)
    signal = (fast > slow).astype(float)
    # Trade on the next bar (no look-ahead); flat until both SMAs exist.
    position = signal.shift(1).fillna(0.0)

    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position * daily_ret
    equity = (1.0 + strat_ret).cumprod()

    total_return = float(equity.iloc[-1] - 1.0)
    bh_return = float(close.iloc[-1] / close.iloc[0] - 1.0)

    entries = int(((position == 1) & (position.shift(1) != 1)).sum())
    trade_rets = _trade_returns(position, daily_ret)
    wins = sum(1 for r in trade_rets if r > 0)
    win_rate = (wins / len(trade_rets) * 100.0) if trade_rets else None

    std = float(strat_ret.std(ddof=1))
    sharpe = float(strat_ret.mean() / std * np.sqrt(trading_days)) if std > 0 else None

    return BacktestResult(
        ticker=history.ticker,
        strategy=f"SMA {fast_window}/{slow_window} long-flat crossover",
        bars=len(close),
        total_return_pct=round(total_return * 100.0, 2),
        buy_and_hold_return_pct=round(bh_return * 100.0, 2),
        excess_return_pct=round((total_return - bh_return) * 100.0, 2),
        n_trades=entries,
        win_rate_pct=round(win_rate, 1) if win_rate is not None else None,
        exposure_pct=round(float(position.mean()) * 100.0, 1),
        max_drawdown_pct=round(_max_drawdown(equity) * 100.0, 2),
        sharpe_like=round(sharpe, 2) if sharpe is not None else None,
        caveats=[
            "In-sample; no transaction costs, slippage, or financing modelled.",
            "Long/flat only; past signal performance does not imply future value.",
        ],
    )
