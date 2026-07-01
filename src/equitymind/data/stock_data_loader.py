"""Market data loading — yfinance source plus a cached, multi-ticker loader.

Two layers live here:

* :class:`YFinanceSource` — a concrete :class:`DataSource` that normalises the
  quirky yfinance response into a canonical :class:`PriceHistory`.
* :class:`StockDataLoader` — the orchestrator the rest of the app uses. It wires
  a source to a :class:`PriceCache` and offers convenient single / batch fetch
  methods that never raise for one bad ticker in a batch.

Supports stocks, indices and crypto transparently (yfinance uses the same
``history`` call for all of them, e.g. ``AAPL``, ``SPY``, ``BTC-USD``).
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from ..config import AssetSpec
from ..logging_config import get_logger
from .base import DataSource, DataSourceError
from .cache import PriceCache
from .models import FetchResult, PriceHistory

logger = get_logger(__name__)

_COLUMN_MAP = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adj close": "close",
    "volume": "volume",
}


def _normalise_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw yfinance frame to the canonical OHLCV schema."""
    frame = raw.copy()

    # Single-ticker downloads via yf.download can come back with a column
    # MultiIndex ((field, ticker)); flatten to the field level.
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    frame.columns = [str(c).strip().lower() for c in frame.columns]
    keep = {src: dst for src, dst in _COLUMN_MAP.items() if src in frame.columns}
    frame = frame.rename(columns=keep)[list(dict.fromkeys(keep.values()))]

    # Drop timezone so cached parquet round-trips and indices align cleanly.
    if isinstance(frame.index, pd.DatetimeIndex) and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)

    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    frame = frame.dropna(subset=["close"])
    return frame


class YFinanceSource(DataSource):
    """OHLCV history via the ``yfinance`` package."""

    name = "yfinance"

    def fetch(self, ticker: str, *, period: str, interval: str) -> PriceHistory:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover - env dependent
            raise DataSourceError("yfinance is not installed; run `pip install yfinance`") from exc

        ticker = ticker.strip().upper()
        logger.info("Fetching %s (period=%s interval=%s)", ticker, period, interval)
        try:
            handle = yf.Ticker(ticker)
            raw = handle.history(period=period, interval=interval, auto_adjust=True)
        except Exception as exc:  # network / vendor errors
            raise DataSourceError(f"{ticker}: fetch failed ({exc})") from exc

        if raw is None or raw.empty:
            raise DataSourceError(f"{ticker}: no data returned (unknown symbol?)")

        frame = _normalise_frame(raw)
        if frame.empty:
            raise DataSourceError(f"{ticker}: no usable rows after normalisation")

        currency = "USD"
        try:  # fast_info is cheap; guard against vendor breakage
            currency = (handle.fast_info.get("currency") or "USD").upper()
        except Exception:  # pragma: no cover - best effort
            pass

        return PriceHistory(ticker=ticker, frame=frame, interval=interval, currency=currency)


class StockDataLoader:
    """High-level loader: source + optional cache + batch convenience."""

    def __init__(
        self,
        source: DataSource | None = None,
        cache: PriceCache | None = None,
        *,
        default_period: str = "1y",
        default_interval: str = "1d",
    ) -> None:
        self.source = source or YFinanceSource()
        self.cache = cache
        self.default_period = default_period
        self.default_interval = default_interval

    # ------------------------------------------------------------------ single
    def load(
        self,
        asset: str | AssetSpec,
        *,
        period: str | None = None,
        interval: str | None = None,
        use_cache: bool = True,
    ) -> PriceHistory:
        """Load one instrument, consulting the cache when enabled.

        ``asset`` may be a bare ticker string or an :class:`AssetSpec`; in the
        latter case the returned history is enriched with the configured name
        and asset class.
        """
        spec = asset if isinstance(asset, AssetSpec) else None
        ticker = spec.ticker if spec else str(asset).strip().upper()
        period = period or self.default_period
        interval = interval or self.default_interval

        history: PriceHistory | None = None
        if use_cache and self.cache is not None:
            history = self.cache.get(ticker, period, interval, self.source.name)

        if history is None:
            history = self.source.fetch(ticker, period=period, interval=interval)
            if self.cache is not None:
                self.cache.put(history, period, self.source.name)

        if spec is not None:
            history.name = spec.name or history.name
            history.asset_class = spec.asset_class
        return history

    # ------------------------------------------------------------------ batch
    def load_many(
        self,
        assets: Iterable[str | AssetSpec],
        *,
        period: str | None = None,
        interval: str | None = None,
        use_cache: bool = True,
    ) -> FetchResult:
        """Load several instruments, collecting failures instead of raising."""
        result = FetchResult()
        for asset in assets:
            ticker = asset.ticker if isinstance(asset, AssetSpec) else str(asset).upper()
            try:
                result.histories[ticker] = self.load(
                    asset, period=period, interval=interval, use_cache=use_cache
                )
            except (DataSourceError, ValueError) as exc:
                logger.error("Skipping %s: %s", ticker, exc)
                result.failures[ticker] = str(exc)
        return result
