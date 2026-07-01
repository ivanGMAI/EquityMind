"""Forwards and futures: fair value, payoff, basis and implied carry.

Uses the continuous cost-of-carry model: the fair forward price is the spot
compounded at the net carry rate (financing rate ``r`` less any income yield
``q`` — dividends for equities, the foreign rate for FX, or a convenience-yield
adjustment for commodities). Everything is a plain function of the inputs.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(slots=True)
class ForwardQuote:
    """Fair forward price and its relationship to an observed futures price."""

    fair_forward: float
    basis: float | None = None  # observed futures − spot
    fair_basis: float | None = None  # fair forward − spot
    implied_carry: float | None = None  # rate implied by the observed price

    def to_dict(self) -> dict:
        return asdict(self)


def forward_price(spot: float, T: float, r: float, income_yield: float = 0.0) -> float:
    """Fair forward/futures price under continuous cost of carry.

    ``F = S · e^{(r − q)·T}`` for spot ``S``, financing rate ``r``, income yield
    ``q`` and time to delivery ``T`` (years).
    """
    if spot <= 0:
        raise ValueError("spot must be positive")
    if T < 0:
        raise ValueError("T must be non-negative")
    return float(spot * math.exp((r - income_yield) * T))


def forward_payoff(spot_at_expiry, forward_entry: float, quantity: float = 1.0):
    """P&L of a forward/futures position at delivery: ``qty · (S_T − F₀)``."""
    import numpy as np

    s = np.asarray(spot_at_expiry, dtype=float)
    return quantity * (s - forward_entry)


def basis(spot: float, futures: float) -> float:
    """Futures basis: observed futures price minus spot."""
    return float(futures - spot)


def implied_carry(spot: float, futures: float, T: float) -> float | None:
    """Net carry rate implied by an observed futures price: ``ln(F/S)/T``."""
    if spot <= 0 or futures <= 0 or T <= 0:
        return None
    return float(math.log(futures / spot) / T)


def analyze_forward(
    spot: float,
    T: float,
    r: float,
    *,
    income_yield: float = 0.0,
    observed_futures: float | None = None,
) -> ForwardQuote:
    """Fair forward price plus basis / implied-carry diagnostics vs. the market."""
    fair = forward_price(spot, T, r, income_yield)
    quote = ForwardQuote(fair_forward=fair, fair_basis=fair - spot)
    if observed_futures is not None:
        quote.basis = basis(spot, observed_futures)
        quote.implied_carry = implied_carry(spot, observed_futures, T)
    return quote
