"""Trend detection.

Classifies an instrument as ``bullish`` / ``bearish`` / ``neutral`` using a
transparent, explainable rule set built on moving-average relationships rather
than a black box:

* price position relative to the slow moving average,
* the fast MA above / below the slow MA (the classic crossover regime),
* the slope of the slow MA.

A configurable neutral band keeps marginal readings from flip-flopping.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd

from .indicators import sma

TrendLabel = Literal["bullish", "bearish", "neutral"]


@dataclass(slots=True)
class TrendResult:
    classification: TrendLabel
    price: float
    fast_sma: float | None
    slow_sma: float | None
    price_vs_slow_pct: float | None
    fast_vs_slow_pct: float | None
    slow_slope_pct: float | None
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


def _slope_pct(series: pd.Series, lookback: int = 5) -> float | None:
    """Percent change of a series over the last ``lookback`` defined points."""
    clean = series.dropna()
    if len(clean) <= lookback or clean.iloc[-1 - lookback] == 0:
        return None
    return float(clean.iloc[-1] / clean.iloc[-1 - lookback] - 1.0) * 100.0


def detect_trend(
    close: pd.Series,
    fast_window: int = 20,
    slow_window: int = 50,
    neutral_band_pct: float = 1.0,
) -> TrendResult:
    """Classify the prevailing trend of ``close``.

    Args:
        close: Close-price series.
        fast_window: Fast SMA length.
        slow_window: Slow SMA length.
        neutral_band_pct: Half-width (in %) of the dead-zone around the slow MA
            within which the trend is treated as neutral.
    """
    close = close.astype(float)
    price = float(close.iloc[-1])
    fast_series = sma(close, fast_window)
    slow_series = sma(close, slow_window)

    fast_val = fast_series.dropna().iloc[-1] if fast_series.notna().any() else None
    slow_val = slow_series.dropna().iloc[-1] if slow_series.notna().any() else None

    if slow_val is None:
        return TrendResult(
            classification="neutral",
            price=price,
            fast_sma=float(fast_val) if fast_val is not None else None,
            slow_sma=None,
            price_vs_slow_pct=None,
            fast_vs_slow_pct=None,
            slow_slope_pct=None,
            rationale=(
                f"Insufficient history for a {slow_window}-bar moving average; trend undetermined."
            ),
        )

    fast_val = float(fast_val) if fast_val is not None else None
    slow_val = float(slow_val)
    price_vs_slow = (price / slow_val - 1.0) * 100.0
    fast_vs_slow = (fast_val / slow_val - 1.0) * 100.0 if fast_val is not None else None
    slope = _slope_pct(slow_series)

    above = price_vs_slow > neutral_band_pct
    below = price_vs_slow < -neutral_band_pct
    fast_up = fast_vs_slow is None or fast_vs_slow >= 0
    fast_down = fast_vs_slow is None or fast_vs_slow <= 0

    if above and fast_up:
        label: TrendLabel = "bullish"
        rationale = (
            f"Price is {price_vs_slow:+.1f}% above the {slow_window}-bar average "
            f"with the {fast_window}-bar average on top — an uptrend regime."
        )
    elif below and fast_down:
        label = "bearish"
        rationale = (
            f"Price is {price_vs_slow:+.1f}% below the {slow_window}-bar average "
            f"with the {fast_window}-bar average underneath — a downtrend regime."
        )
    else:
        label = "neutral"
        rationale = (
            f"Price sits within +/-{neutral_band_pct:.1f}% of the "
            f"{slow_window}-bar average ({price_vs_slow:+.1f}%); no decisive trend."
        )

    return TrendResult(
        classification=label,
        price=price,
        fast_sma=fast_val,
        slow_sma=slow_val,
        price_vs_slow_pct=price_vs_slow,
        fast_vs_slow_pct=fast_vs_slow,
        slow_slope_pct=slope,
        rationale=rationale,
    )
