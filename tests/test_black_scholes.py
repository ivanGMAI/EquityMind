from __future__ import annotations

import math

import pytest

from equitymind.derivatives.black_scholes import (
    bs_price,
    implied_volatility,
    price_and_greeks,
)

# Canonical textbook case (Hull): S=K=100, T=1, r=5%, sigma=20%.
BASE = dict(S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20)


def test_known_textbook_values():
    call = bs_price(option_type="call", **BASE)
    put = bs_price(option_type="put", **BASE)
    assert call == pytest.approx(10.4506, abs=1e-3)
    assert put == pytest.approx(5.5735, abs=1e-3)


def test_put_call_parity():
    q = 0.0
    call = bs_price(option_type="call", **BASE)
    put = bs_price(option_type="put", **BASE)
    S, K, T, r = BASE["S"], BASE["K"], BASE["T"], BASE["r"]
    lhs = call - put
    rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
    assert lhs == pytest.approx(rhs, abs=1e-9)


def test_delta_bounds_and_relation():
    call = price_and_greeks(option_type="call", **BASE)
    put = price_and_greeks(option_type="put", **BASE)
    assert 0.0 < call.delta < 1.0
    assert -1.0 < put.delta < 0.0
    # call delta - put delta = e^{-qT} = 1 for q=0
    assert call.delta - put.delta == pytest.approx(1.0, abs=1e-9)


def test_gamma_vega_positive_and_equal_across_types():
    call = price_and_greeks(option_type="call", **BASE)
    put = price_and_greeks(option_type="put", **BASE)
    assert call.gamma > 0 and call.vega > 0
    # gamma and vega are identical for calls and puts at the same strike.
    assert call.gamma == pytest.approx(put.gamma, abs=1e-12)
    assert call.vega == pytest.approx(put.vega, abs=1e-12)


def test_greek_scalings():
    q = price_and_greeks(option_type="call", **BASE)
    assert q.vega_per_pct == pytest.approx(q.vega / 100.0)
    assert q.theta_per_day == pytest.approx(q.theta / 365.0)
    assert q.rho_per_pct == pytest.approx(q.rho / 100.0)


def test_price_monotonic_in_vol_and_spot():
    lo = bs_price(S=100, K=100, T=1, r=0.05, sigma=0.10, option_type="call")
    hi = bs_price(S=100, K=100, T=1, r=0.05, sigma=0.30, option_type="call")
    assert hi > lo  # vega positive
    cheap = bs_price(S=90, K=100, T=1, r=0.05, sigma=0.2, option_type="call")
    rich = bs_price(S=110, K=100, T=1, r=0.05, sigma=0.2, option_type="call")
    assert rich > cheap  # delta positive


@pytest.mark.parametrize("sigma", [0.05, 0.15, 0.35, 0.8])
@pytest.mark.parametrize("K", [80.0, 100.0, 125.0])
@pytest.mark.parametrize("otype", ["call", "put"])
def test_implied_vol_reprices(sigma, K, otype):
    # The invariant that always holds: the recovered vol reprices the option.
    # (For deep ITM/OTM low-vega options the vol itself is ill-conditioned even
    # though the price match is exact.)
    price = bs_price(S=100, K=K, T=0.75, r=0.03, sigma=sigma, option_type=otype)
    iv = implied_volatility(price, 100, K, 0.75, 0.03, option_type=otype)
    assert iv is not None
    assert bs_price(S=100, K=K, T=0.75, r=0.03, sigma=iv, option_type=otype) == pytest.approx(
        price, abs=1e-6
    )


@pytest.mark.parametrize("sigma", [0.1, 0.2, 0.45])
@pytest.mark.parametrize("otype", ["call", "put"])
def test_implied_vol_recovers_sigma_near_atm(sigma, otype):
    # Near ATM vega is healthy, so the vol itself is recovered precisely.
    price = bs_price(S=100, K=100, T=1.0, r=0.03, sigma=sigma, option_type=otype)
    iv = implied_volatility(price, 100, 100, 1.0, 0.03, option_type=otype)
    assert iv == pytest.approx(sigma, abs=1e-5)


def test_implied_vol_out_of_bounds_returns_none():
    # Price below discounted intrinsic is impossible -> no solution.
    assert implied_volatility(0.0001, 120, 100, 1, 0.05, option_type="call") is None
    # Price above the underlying is impossible for a call.
    assert implied_volatility(150.0, 100, 100, 1, 0.05, option_type="call") is None


def test_expired_and_zero_vol_are_intrinsic():
    assert bs_price(S=120, K=100, T=0.0, r=0.05, sigma=0.2, option_type="call") == pytest.approx(
        20.0
    )
    assert bs_price(S=90, K=100, T=0.0, r=0.05, sigma=0.2, option_type="put") == pytest.approx(10.0)
    # sigma=0 -> discounted intrinsic of the forward.
    zero = bs_price(S=100, K=100, T=1, r=0.05, sigma=0.0, option_type="call")
    assert zero == pytest.approx(100 - 100 * math.exp(-0.05), abs=1e-9)


def test_dividend_yield_lowers_call_raises_put():
    call_no_q = bs_price(option_type="call", q=0.0, **BASE)
    call_q = bs_price(option_type="call", q=0.04, **BASE)
    put_no_q = bs_price(option_type="put", q=0.0, **BASE)
    put_q = bs_price(option_type="put", q=0.04, **BASE)
    assert call_q < call_no_q
    assert put_q > put_no_q


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        bs_price(S=-1, K=100, T=1, r=0.05, sigma=0.2)
    with pytest.raises(ValueError):
        price_and_greeks(S=100, K=100, T=1, r=0.05, sigma=0.2, option_type="banana")
