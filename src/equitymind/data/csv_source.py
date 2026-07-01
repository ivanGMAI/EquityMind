"""CSV file data source.

Loads OHLCV history from local CSV files — the natural bridge from a spreadsheet
workflow (export from Excel / a vendor terminal, drop the file in, analyse it)
and a fully offline data path for demos and tests.

:class:`CSVSource` resolves ``<data_dir>/<TICKER>.csv`` for a requested ticker;
:func:`load_csv_file` loads an explicit path ad hoc. Headers are matched
case-insensitively against common conventions (``Date``/``TRADEDATE``,
``Adj Close``/``close`` …), so files from different vendors just work.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from ..logging_config import get_logger
from .base import DataSource, DataSourceError
from .models import PriceHistory

logger = get_logger(__name__)

# Candidate header names (lower-cased) for each canonical column.
_DATE_CANDIDATES = ("date", "datetime", "tradedate", "begin", "time", "timestamp")
_FIELD_CANDIDATES: dict[str, tuple[str, ...]] = {
    "open": ("open",),
    "high": ("high",),
    "low": ("low",),
    "close": ("close", "adj close", "adjclose", "close_price", "legalcloseprice"),
    "volume": ("volume", "vol", "volrur"),
}


def _pick(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    lower = {str(c).strip().lower(): c for c in columns}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    return None


def _normalise_csv_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Coerce an arbitrary CSV frame to the canonical OHLCV schema."""
    date_col = _pick(raw.columns, _DATE_CANDIDATES)
    close_col = _pick(raw.columns, _FIELD_CANDIDATES["close"])
    if date_col is None or close_col is None:
        raise DataSourceError(
            "CSV must contain a date column and a close/price column; "
            f"found columns: {list(raw.columns)}"
        )

    index = pd.to_datetime(raw[date_col], errors="coerce")
    data: dict[str, pd.Series] = {}
    for field, candidates in _FIELD_CANDIDATES.items():
        col = _pick(raw.columns, candidates)
        if col is not None:
            data[field] = pd.to_numeric(raw[col], errors="coerce")
    frame = pd.DataFrame(data)
    frame.index = index
    frame = frame[frame.index.notna()].sort_index()
    frame = frame[~frame.index.duplicated(keep="last")].dropna(subset=["close"])
    if frame.empty:
        raise DataSourceError("CSV produced no usable rows after parsing")
    return frame


def load_csv_file(
    path: str | Path,
    *,
    ticker: str,
    interval: str = "1d",
    currency: str = "USD",
    name: str = "",
    asset_class: str = "equity",
) -> PriceHistory:
    """Load a single CSV file into a :class:`PriceHistory`."""
    path = Path(path)
    if not path.exists():
        raise DataSourceError(f"CSV file not found: {path}")
    try:
        raw = pd.read_csv(path)
    except Exception as exc:
        raise DataSourceError(f"{ticker}: failed to read CSV {path} ({exc})") from exc
    frame = _normalise_csv_frame(raw)
    return PriceHistory(
        ticker=ticker.strip().upper(),
        frame=frame,
        interval=interval,
        currency=currency,
        name=name,
        asset_class=asset_class,
    )


class CSVSource(DataSource):
    """OHLCV history from ``<data_dir>/<TICKER>.csv`` files."""

    name = "csv"

    def __init__(self, data_dir: str | Path, *, currency: str = "USD") -> None:
        self.data_dir = Path(data_dir)
        self.currency = currency

    def fetch(self, ticker: str, *, period: str, interval: str) -> PriceHistory:
        ticker = ticker.strip().upper()
        path = self.data_dir / f"{ticker}.csv"
        logger.info("Loading %s from CSV %s", ticker, path)
        history = load_csv_file(path, ticker=ticker, interval=interval, currency=self.currency)
        return _trim_to_period(history, period)


def _trim_to_period(history: PriceHistory, period: str) -> PriceHistory:
    """Trim the frame to the trailing ``period`` window (best effort)."""
    from .moex import _PERIOD_DAYS  # reuse the shared alias table

    days = _PERIOD_DAYS.get(period.lower())
    if not days or history.frame.empty:
        return history
    cutoff = history.frame.index[-1] - pd.Timedelta(days=days)
    trimmed = history.frame[history.frame.index >= cutoff]
    if trimmed.empty:
        return history
    history.frame = trimmed
    return history
