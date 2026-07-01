"""Chart rendering with matplotlib.

Uses the non-interactive ``Agg`` backend so charts render identically on a
server, in a container, or inside Streamlit. Functions return
:class:`matplotlib.figure.Figure` objects (for the dashboard) and a helper saves
them to PNG (for markdown/PDF reports).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")  # headless-safe; must precede pyplot import
import matplotlib.pyplot as plt  # noqa: E402

from ..analytics.indicators import sma  # noqa: E402
from ..analytics.returns import cumulative_return_series  # noqa: E402
from ..analytics.volatility import rolling_volatility  # noqa: E402
from ..data.models import PriceHistory  # noqa: E402

_FIGSIZE = (10, 5)


def price_chart(
    history: PriceHistory,
    sma_windows: Iterable[int] = (20, 50),
    title: str | None = None,
) -> plt.Figure:
    """Close price with overlaid simple moving averages."""
    fig, ax = plt.subplots(figsize=_FIGSIZE)
    close = history.close
    ax.plot(close.index, close.values, label="Close", linewidth=1.4, color="#1f77b4")
    for w in sma_windows:
        line = sma(close, w)
        ax.plot(line.index, line.values, label=f"SMA {w}", linewidth=1.0, alpha=0.9)
    ax.set_title(title or f"{history.ticker} — price & moving averages")
    ax.set_ylabel(f"Price ({history.currency})")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def volatility_chart(
    history: PriceHistory, window: int = 21, trading_days: int = 252
) -> plt.Figure:
    """Rolling annualised volatility over time."""
    fig, ax = plt.subplots(figsize=_FIGSIZE)
    vol = rolling_volatility(history.close, window, trading_days) * 100.0
    ax.plot(vol.index, vol.values, color="#d62728", linewidth=1.2)
    ax.fill_between(vol.index, vol.values, alpha=0.15, color="#d62728")
    ax.set_title(f"{history.ticker} — {window}-bar annualised volatility")
    ax.set_ylabel("Volatility (%)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig


def comparison_chart(
    histories: dict[str, PriceHistory], title: str = "Relative performance (rebased to 100)"
) -> plt.Figure:
    """Normalised cumulative-return curves for several instruments."""
    fig, ax = plt.subplots(figsize=_FIGSIZE)
    for ticker, history in histories.items():
        curve = cumulative_return_series(history.close) * 100.0
        ax.plot(curve.index, curve.values, label=ticker, linewidth=1.3)
    ax.axhline(100.0, color="grey", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.set_title(title)
    ax.set_ylabel("Growth of 100")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def payoff_diagram(
    spots: Sequence[float],
    pnl: Sequence[float],
    *,
    breakevens: Sequence[float] | None = None,
    spot_marker: float | None = None,
    title: str = "Option strategy payoff at expiry",
    currency: str = "",
) -> plt.Figure:
    """Profit/loss of a derivative strategy across terminal underlying prices."""
    x = np.asarray(spots, dtype=float)
    y = np.asarray(pnl, dtype=float)
    fig, ax = plt.subplots(figsize=_FIGSIZE)
    ax.axhline(0.0, color="grey", linewidth=0.9, linestyle="--", alpha=0.7)
    ax.plot(x, y, color="#1f77b4", linewidth=1.6, label="P&L")
    ax.fill_between(x, y, 0.0, where=(y >= 0).tolist(), color="#2ca02c", alpha=0.15)
    ax.fill_between(x, y, 0.0, where=(y < 0).tolist(), color="#d62728", alpha=0.15)
    for be in breakevens or []:
        ax.axvline(be, color="#ff7f0e", linewidth=0.9, linestyle=":", alpha=0.8)
    if spot_marker is not None:
        ax.axvline(spot_marker, color="black", linewidth=0.8, alpha=0.5, label="spot")
    ax.set_title(title)
    ax.set_xlabel(f"Underlying price at expiry ({currency})".strip())
    ax.set_ylabel("Profit / loss")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    return fig


def save_figure(fig: plt.Figure, path: str | Path, *, dpi: int = 120) -> Path:
    """Write a figure to disk and close it to release memory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return path
