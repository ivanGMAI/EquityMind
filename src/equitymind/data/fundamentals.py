"""Fundamental data (valuation, profitability, classification).

Complements the price-based quantitative analytics with the headline fundamentals
an analyst reaches for first — valuation multiples (P/E, P/B), earnings (EPS),
income (dividend yield), size (market cap) and classification (sector/industry).

:class:`YFinanceFundamentals` pulls them from yfinance's ``info`` mapping, but the
parsing lives in :meth:`Fundamentals.from_info`, which is a pure function of a
dict — so it is fully testable offline without touching the network.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


def _num(value: Any) -> float | None:
    """Coerce to float, treating missing/blank/non-numeric as ``None``."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class Fundamentals:
    """Curated fundamental snapshot for one instrument."""

    ticker: str
    name: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    eps: float | None = None
    dividend_yield: float | None = None  # fraction, e.g. 0.045 = 4.5%
    return_on_equity: float | None = None  # fraction
    profit_margin: float | None = None  # fraction
    beta: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_payload(self) -> dict:
        """Report-friendly view (yields/margins expressed as percentages)."""
        pct = lambda v: None if v is None else round(v * 100.0, 2)  # noqa: E731
        return {
            "ticker": self.ticker,
            "name": self.name,
            "currency": self.currency,
            "sector": self.sector,
            "industry": self.industry,
            "market_cap": self.market_cap,
            "trailing_pe": self.trailing_pe,
            "forward_pe": self.forward_pe,
            "price_to_book": self.price_to_book,
            "eps": self.eps,
            "dividend_yield_pct": pct(self.dividend_yield),
            "return_on_equity_pct": pct(self.return_on_equity),
            "profit_margin_pct": pct(self.profit_margin),
            "beta": self.beta,
        }

    @classmethod
    def from_info(cls, ticker: str, info: dict[str, Any]) -> Fundamentals:
        """Build a snapshot from a yfinance-style ``info`` mapping."""
        return cls(
            ticker=ticker.strip().upper(),
            name=info.get("longName") or info.get("shortName"),
            currency=info.get("currency"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            market_cap=_num(info.get("marketCap")),
            trailing_pe=_num(info.get("trailingPE")),
            forward_pe=_num(info.get("forwardPE")),
            price_to_book=_num(info.get("priceToBook")),
            eps=_num(info.get("trailingEps")),
            dividend_yield=_num(info.get("dividendYield")),
            return_on_equity=_num(info.get("returnOnEquity")),
            profit_margin=_num(info.get("profitMargins")),
            beta=_num(info.get("beta")),
        )


class FundamentalsSource(ABC):
    """Provider of a :class:`Fundamentals` snapshot for a symbol."""

    name: str = "abstract"

    @abstractmethod
    def fetch(self, ticker: str) -> Fundamentals | None:
        """Return fundamentals for ``ticker``, or ``None`` if unavailable."""
        raise NotImplementedError


class YFinanceFundamentals(FundamentalsSource):
    """Fundamentals via yfinance's ``info`` mapping (best effort, non-fatal)."""

    name = "yfinance"

    def fetch(self, ticker: str) -> Fundamentals | None:
        try:
            import yfinance as yf

            info = yf.Ticker(ticker).get_info()
        except Exception as exc:  # network / vendor / parsing errors
            logger.warning("Fundamentals unavailable for %s: %s", ticker, exc)
            return None
        if not info:
            return None
        return Fundamentals.from_info(ticker, info)


def fetch_fundamentals(
    ticker: str, source: FundamentalsSource | None = None
) -> Fundamentals | None:
    """Convenience wrapper: fetch fundamentals via ``source`` (default yfinance)."""
    return (source or YFinanceFundamentals()).fetch(ticker)
