"""Portfolio-level analytics: correlation, mean-variance optimisation, risk parity.

The per-asset analytics in :mod:`equitymind.analytics` look at one instrument at
a time; this package steps up to the portfolio view — how the instruments move
together and how they combine into diversified allocations.
"""

from __future__ import annotations

from . import correlation, optimizer
from .analyze import PortfolioMetrics, PortfolioReport, analyze_portfolio

__all__ = [
    "correlation",
    "optimizer",
    "PortfolioMetrics",
    "PortfolioReport",
    "analyze_portfolio",
]
