"""Technical indicators: moving averages, RSI and Bollinger bands.

Each function returns a pandas object aligned to the input index, so indicators
can be charted or fed into higher-level signals without re-indexing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average over ``window`` bars."""
    return series.astype(float).rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    """Exponential moving average with span ``window``."""
    return series.astype(float).ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Wilder's Relative Strength Index (0-100).

    Values above 70 are conventionally "overbought", below 30 "oversold".
    """
    close = series.astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    # Wilder smoothing == EMA with alpha = 1/window.
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()

    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    result = 100.0 - (100.0 / (1.0 + rs))
    # When avg_loss is zero the asset only rose -> RSI 100.
    return result.fillna(100.0).where(avg_gain.notna())


@dataclass(slots=True)
class BollingerBands:
    middle: pd.Series
    upper: pd.Series
    lower: pd.Series


def bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0) -> BollingerBands:
    """Bollinger bands: SMA middle band +/- ``num_std`` rolling std deviations."""
    close = series.astype(float)
    mid = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std(ddof=0)
    return BollingerBands(middle=mid, upper=mid + num_std * std, lower=mid - num_std * std)


def latest(series: pd.Series) -> float | None:
    """Last non-NaN value of a series, or ``None`` if entirely undefined."""
    clean = series.dropna()
    return float(clean.iloc[-1]) if not clean.empty else None
