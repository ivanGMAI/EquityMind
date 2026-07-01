"""Abstract data-source interface.

Decoupling the analytics from any specific vendor means a Bloomberg / Polygon /
CSV source can be dropped in later by implementing a single method. The rest of
the system depends only on :class:`DataSource`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PriceHistory


class DataSource(ABC):
    """Provider of OHLCV history for a single symbol."""

    #: Short identifier used in logs and cache keys.
    name: str = "abstract"

    @abstractmethod
    def fetch(self, ticker: str, *, period: str, interval: str) -> PriceHistory:
        """Return validated :class:`PriceHistory` for ``ticker``.

        Implementations must raise :class:`DataSourceError` on any failure
        (network, unknown symbol, empty response) rather than returning a
        partial or empty frame.
        """
        raise NotImplementedError


class DataSourceError(RuntimeError):
    """Raised when a data source cannot satisfy a fetch request."""
