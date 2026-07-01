"""Derivatives toolkit: option pricing, Greeks, strategy payoffs and forwards.

A self-contained layer for analysing derivative instruments alongside the cash
analytics:

* :mod:`black_scholes` — European option pricing, the full set of Greeks and
  implied-volatility inversion,
* :mod:`payoff` — option strategy payoff / P&L diagrams and their break-evens,
* :mod:`forwards` — forward / futures fair value, basis and implied carry.
"""

from __future__ import annotations

from . import black_scholes, forwards, payoff
from .black_scholes import (
    OptionQuote,
    bs_price,
    implied_volatility,
    price_and_greeks,
)
from .forwards import ForwardQuote, analyze_forward, forward_price
from .payoff import Leg, StrategySummary, strategy_pnl, strategy_summary

__all__ = [
    "black_scholes",
    "payoff",
    "forwards",
    "OptionQuote",
    "bs_price",
    "price_and_greeks",
    "implied_volatility",
    "Leg",
    "StrategySummary",
    "strategy_pnl",
    "strategy_summary",
    "ForwardQuote",
    "forward_price",
    "analyze_forward",
]
