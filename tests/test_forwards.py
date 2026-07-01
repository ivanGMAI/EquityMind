from __future__ import annotations

import math

import numpy as np
import pytest

from equitymind.derivatives import forwards


def test_forward_price_cost_of_carry():
    f = forwards.forward_price(100.0, 1.0, 0.05, income_yield=0.02)
    assert f == pytest.approx(100.0 * math.exp(0.03), abs=1e-9)


def test_forward_equals_spot_when_carry_zero():
    assert forwards.forward_price(100.0, 2.0, 0.04, income_yield=0.04) == pytest.approx(100.0)


def test_implied_carry_inverts_forward_price():
    f = forwards.forward_price(100.0, 0.5, 0.06, income_yield=0.01)
    carry = forwards.implied_carry(100.0, f, 0.5)
    assert carry == pytest.approx(0.06 - 0.01, abs=1e-9)


def test_basis_sign():
    assert forwards.basis(100.0, 103.0) == pytest.approx(3.0)
    assert forwards.basis(100.0, 98.0) == pytest.approx(-2.0)


def test_forward_payoff_linear():
    payoff = forwards.forward_payoff(np.array([90.0, 100.0, 110.0]), forward_entry=100.0)
    assert list(payoff) == pytest.approx([-10.0, 0.0, 10.0])
    short = forwards.forward_payoff(np.array([110.0]), forward_entry=100.0, quantity=-1.0)
    assert float(short[0]) == pytest.approx(-10.0)


def test_analyze_forward_bundle():
    q = forwards.analyze_forward(100.0, 0.5, 0.05, income_yield=0.02, observed_futures=103.0)
    assert q.fair_forward == pytest.approx(forwards.forward_price(100.0, 0.5, 0.05, 0.02))
    assert q.basis == pytest.approx(3.0)
    assert q.fair_basis == pytest.approx(q.fair_forward - 100.0)
    assert q.implied_carry is not None


def test_invalid_spot_raises():
    with pytest.raises(ValueError):
        forwards.forward_price(0.0, 1.0, 0.05)


def test_implied_carry_none_on_degenerate():
    assert forwards.implied_carry(100.0, 103.0, 0.0) is None
    assert forwards.implied_carry(0.0, 103.0, 1.0) is None
