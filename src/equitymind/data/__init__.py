"""Data acquisition layer: sources, caching and the canonical price model."""

from __future__ import annotations

from .base import DataSource, DataSourceError
from .cache import PriceCache
from .csv_source import CSVSource, load_csv_file
from .fundamentals import (
    Fundamentals,
    FundamentalsSource,
    YFinanceFundamentals,
    fetch_fundamentals,
)
from .models import OHLCV_COLUMNS, FetchResult, PriceHistory
from .moex import MoexSource
from .stock_data_loader import StockDataLoader, YFinanceSource

__all__ = [
    "DataSource",
    "DataSourceError",
    "PriceCache",
    "PriceHistory",
    "FetchResult",
    "OHLCV_COLUMNS",
    "StockDataLoader",
    "YFinanceSource",
    "MoexSource",
    "CSVSource",
    "load_csv_file",
    "Fundamentals",
    "FundamentalsSource",
    "YFinanceFundamentals",
    "fetch_fundamentals",
]
