"""Domain objects for market data.

:class:`PriceHistory` is the canonical container passed between the data layer
and the analytics layer. Standardising on a single, validated shape (lowercase
OHLCV columns on a sorted ``DatetimeIndex``) means every analytics function can
make firm assumptions about its input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

# Canonical column names every downstream module relies on.
OHLCV_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")


@dataclass(slots=True)
class PriceHistory:
    """Validated OHLCV history for a single instrument.

    Attributes:
        ticker: The instrument symbol (upper-case).
        frame: DataFrame indexed by a sorted, tz-naive ``DatetimeIndex`` with at
            least the columns in :data:`OHLCV_COLUMNS` (``close`` mandatory).
        interval: Bar size the data was sampled at (e.g. ``"1d"``).
        currency: Reporting currency for the price series.
        name: Human-readable instrument name.
        asset_class: Free-form grouping label (equity / index / crypto / ...).
    """

    ticker: str
    frame: pd.DataFrame
    interval: str = "1d"
    currency: str = "USD"
    name: str = ""
    asset_class: str = "equity"

    def __post_init__(self) -> None:
        if "close" not in self.frame.columns:
            raise ValueError(f"{self.ticker}: price frame missing required 'close' column")
        if self.frame.empty:
            raise ValueError(f"{self.ticker}: price frame is empty")
        if not isinstance(self.frame.index, pd.DatetimeIndex):
            raise ValueError(f"{self.ticker}: frame index must be a DatetimeIndex")
        # Enforce chronological order; analytics assume ascending time.
        if not self.frame.index.is_monotonic_increasing:
            self.frame = self.frame.sort_index()

    # ------------------------------------------------------------------ views
    @property
    def close(self) -> pd.Series:
        """Adjusted close price series (the primary analytical series)."""
        return self.frame["close"].astype(float)

    @property
    def volume(self) -> pd.Series:
        return self.frame.get("volume", pd.Series(dtype=float)).astype(float)

    @property
    def start(self) -> datetime:
        return self.frame.index[0].to_pydatetime()

    @property
    def end(self) -> datetime:
        return self.frame.index[-1].to_pydatetime()

    @property
    def last_price(self) -> float:
        return float(self.close.iloc[-1])

    def __len__(self) -> int:  # number of bars
        return len(self.frame)

    def tail(self, n: int) -> pd.DataFrame:
        return self.frame.tail(n)


@dataclass(slots=True)
class FetchResult:
    """Outcome of a multi-ticker fetch, separating hits from failures."""

    histories: dict[str, PriceHistory] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> list[str]:
        return list(self.histories)

    def __getitem__(self, ticker: str) -> PriceHistory:
        return self.histories[ticker.upper()]

    def __contains__(self, ticker: str) -> bool:
        return ticker.upper() in self.histories
