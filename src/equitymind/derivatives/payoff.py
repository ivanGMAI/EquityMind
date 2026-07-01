"""Option strategy payoff / P&L at expiry.

A strategy is a list of :class:`Leg` objects — long/short calls, puts or the
underlying — each with a per-unit entry cost (option premium or underlying entry
price). Sign conventions:

* ``quantity`` > 0 is long, < 0 is short.
* ``entry`` is the per-unit price paid (options: the premium; underlying: the
  price). A short leg *receives* its entry, which the ``quantity * entry`` cost
  term handles automatically (negative quantity → negative cost → credit).

:func:`strategy_pnl` evaluates net profit across a grid of terminal underlying
prices (payoff minus entry cost), and :func:`strategy_summary` extracts the
break-even points, maximum profit and maximum loss over that grid — the numbers
behind a payoff diagram. Named constructors build the classic structures.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np

LegKind = Literal["call", "put", "underlying"]


@dataclass(slots=True)
class Leg:
    """One position in a strategy."""

    kind: LegKind
    quantity: float = 1.0  # +long / -short
    strike: float = 0.0  # ignored for the underlying
    entry: float = 0.0  # per-unit premium (options) or price (underlying)
    label: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class StrategySummary:
    """Payoff-diagram characteristics of a strategy over a price grid."""

    max_profit: float
    max_loss: float
    breakevens: list[float] = field(default_factory=list)
    net_cost: float = 0.0  # net debit (+) paid / credit (−) received at entry
    max_profit_unbounded: bool = False
    max_loss_unbounded: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def leg_payoff(leg: Leg, spot) -> np.ndarray:
    """Terminal payoff of a leg (excluding entry cost) at each ``spot``."""
    s = np.asarray(spot, dtype=float)
    if leg.kind == "call":
        intrinsic = np.maximum(s - leg.strike, 0.0)
    elif leg.kind == "put":
        intrinsic = np.maximum(leg.strike - s, 0.0)
    elif leg.kind == "underlying":
        intrinsic = s
    else:  # pragma: no cover - guarded by the type
        raise ValueError(f"unknown leg kind: {leg.kind}")
    return leg.quantity * intrinsic


def leg_cost(leg: Leg) -> float:
    """Net entry cost of a leg (positive = debit paid, negative = credit)."""
    return leg.quantity * leg.entry


def strategy_pnl(legs: list[Leg], spot) -> np.ndarray:
    """Net profit/loss of the whole strategy at each terminal ``spot``."""
    s = np.asarray(spot, dtype=float)
    total = np.zeros_like(s, dtype=float)
    for leg in legs:
        total = total + leg_payoff(leg, s) - leg_cost(leg)
    return total


def net_cost(legs: list[Leg]) -> float:
    """Net debit (+) or credit (−) to open the strategy."""
    return float(sum(leg_cost(leg) for leg in legs))


def _breakevens(spots: np.ndarray, pnl: np.ndarray) -> list[float]:
    """Zero-crossings of the P&L curve, linearly interpolated on the grid."""
    out: list[float] = []
    for i in range(len(pnl) - 1):
        y0, y1 = pnl[i], pnl[i + 1]
        if y0 == 0.0:
            out.append(float(spots[i]))
        elif y0 * y1 < 0.0:  # sign change between grid points
            x0, x1 = spots[i], spots[i + 1]
            out.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)))
    if pnl[-1] == 0.0:
        out.append(float(spots[-1]))
    return out


def strategy_summary(legs: list[Leg], spots) -> StrategySummary:
    """Break-evens, max profit and max loss of a strategy over ``spots``.

    Because the grid is finite, profit/loss achieved only at an endpoint is
    flagged as potentially unbounded (e.g. a naked long call's upside).
    """
    s = np.asarray(spots, dtype=float)
    pnl = strategy_pnl(legs, s)
    max_profit = float(np.max(pnl))
    max_loss = float(np.min(pnl))
    n = len(s)
    # Open-endedness only comes from the upside (S -> infinity): a profit/loss is
    # unbounded when the extreme sits at the top of the grid *and* the curve is
    # still sloping there (a flat plateau at the edge is bounded). The downside
    # edge (S -> 0) is always bounded because prices cannot go negative.
    right_slope = (pnl[-1] - pnl[-2]) / (s[-1] - s[-2]) if n >= 2 else 0.0
    tol = 1e-7
    return StrategySummary(
        max_profit=max_profit,
        max_loss=max_loss,
        breakevens=sorted(_breakevens(s, pnl)),
        net_cost=net_cost(legs),
        max_profit_unbounded=bool(int(np.argmax(pnl)) == n - 1 and right_slope > tol),
        max_loss_unbounded=bool(int(np.argmin(pnl)) == n - 1 and right_slope < -tol),
    )


# ---------------------------------------------------------------------------
# Named strategy constructors
# ---------------------------------------------------------------------------
def long_call(strike: float, premium: float, quantity: float = 1.0) -> list[Leg]:
    return [Leg("call", quantity, strike, premium, "long call")]


def long_put(strike: float, premium: float, quantity: float = 1.0) -> list[Leg]:
    return [Leg("put", quantity, strike, premium, "long put")]


def covered_call(
    spot_entry: float, strike: float, premium: float, quantity: float = 1.0
) -> list[Leg]:
    """Long the underlying, short a call against it."""
    return [
        Leg("underlying", quantity, 0.0, spot_entry, "long underlying"),
        Leg("call", -quantity, strike, premium, "short call"),
    ]


def protective_put(
    spot_entry: float, strike: float, premium: float, quantity: float = 1.0
) -> list[Leg]:
    """Long the underlying, long a put as insurance."""
    return [
        Leg("underlying", quantity, 0.0, spot_entry, "long underlying"),
        Leg("put", quantity, strike, premium, "long put"),
    ]


def straddle(
    strike: float, call_premium: float, put_premium: float, quantity: float = 1.0
) -> list[Leg]:
    """Long a call and a put at the same strike (long volatility)."""
    return [
        Leg("call", quantity, strike, call_premium, "long call"),
        Leg("put", quantity, strike, put_premium, "long put"),
    ]


def strangle(
    put_strike: float,
    call_strike: float,
    put_premium: float,
    call_premium: float,
    quantity: float = 1.0,
) -> list[Leg]:
    """Long an out-of-the-money put and call (cheaper long-volatility play)."""
    return [
        Leg("put", quantity, put_strike, put_premium, "long put"),
        Leg("call", quantity, call_strike, call_premium, "long call"),
    ]


def bull_call_spread(
    long_strike: float,
    short_strike: float,
    long_premium: float,
    short_premium: float,
    quantity: float = 1.0,
) -> list[Leg]:
    """Long a lower-strike call, short a higher-strike call (capped upside)."""
    return [
        Leg("call", quantity, long_strike, long_premium, "long call"),
        Leg("call", -quantity, short_strike, short_premium, "short call"),
    ]
