from __future__ import annotations

import numpy as np
import pytest

from equitymind.derivatives import payoff as pf


def _grid(S=100.0):
    return np.linspace(0.01, 3.0 * S, 6000)


def test_long_call_profile():
    premium = 5.0
    legs = pf.long_call(strike=100.0, premium=premium)
    summ = pf.strategy_summary(legs, _grid())
    assert summ.breakevens == pytest.approx([105.0], abs=0.1)
    assert summ.max_loss == pytest.approx(-premium, abs=0.05)
    assert summ.max_profit_unbounded is True
    assert summ.max_loss_unbounded is False


def test_long_put_profile():
    premium = 4.0
    legs = pf.long_put(strike=100.0, premium=premium)
    summ = pf.strategy_summary(legs, _grid())
    assert summ.breakevens == pytest.approx([96.0], abs=0.1)
    # Max profit near S->0 is strike - premium.
    assert summ.max_profit == pytest.approx(100.0 - premium, abs=0.1)


def test_bull_call_spread_is_capped():
    legs = pf.bull_call_spread(100.0, 110.0, long_premium=6.0, short_premium=2.0)
    summ = pf.strategy_summary(legs, _grid())
    net = 6.0 - 2.0  # net debit
    assert summ.net_cost == pytest.approx(net)
    assert summ.max_loss == pytest.approx(-net, abs=0.05)
    assert summ.max_profit == pytest.approx(10.0 - net, abs=0.1)  # width - debit
    assert summ.max_profit_unbounded is False
    assert summ.max_loss_unbounded is False


def test_straddle_has_two_breakevens():
    legs = pf.straddle(100.0, call_premium=5.0, put_premium=4.0)
    summ = pf.strategy_summary(legs, _grid())
    assert len(summ.breakevens) == 2
    lo, hi = summ.breakevens
    assert lo == pytest.approx(91.0, abs=0.2)  # 100 - 9 total premium
    assert hi == pytest.approx(109.0, abs=0.2)  # 100 + 9


def test_short_leg_is_a_credit():
    short_call = pf.Leg("call", quantity=-1.0, strike=100.0, entry=5.0)
    assert pf.leg_cost(short_call) == pytest.approx(-5.0)  # premium received


def test_covered_call_caps_upside():
    legs = pf.covered_call(spot_entry=100.0, strike=110.0, premium=3.0)
    spots = _grid()
    pnl = pf.strategy_pnl(legs, spots)
    summ = pf.strategy_summary(legs, spots)
    # Above the short strike, P&L is flat (capped) at (110 - 100) + 3 = 13.
    assert summ.max_profit == pytest.approx(13.0, abs=0.1)
    assert summ.max_profit_unbounded is False
    assert pnl.shape == spots.shape


def test_strategy_pnl_matches_manual_at_point():
    legs = pf.long_call(strike=100.0, premium=5.0)
    # At spot 130: intrinsic 30 - premium 5 = 25.
    assert float(pf.strategy_pnl(legs, np.array([130.0]))[0]) == pytest.approx(25.0)
