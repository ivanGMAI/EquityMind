"""Black–Scholes–Merton option pricing, Greeks and implied volatility.

European options on an underlying paying a continuous dividend / carry yield
``q``. All rates are continuously compounded and annualised; ``T`` is the time to
expiry in years and ``sigma`` the annualised volatility.

The Greeks use their standard analytic forms. Two scaling conventions matter in
practice, so both the raw analytic value and the trader-friendly scaling are made
available (see :class:`OptionQuote`):

* **vega**  — raw is per 1.00 (100 vol points) change in ``sigma``; traders quote
  it per 1 vol point (``vega / 100``).
* **theta** — raw is per year; traders quote it per calendar day (``theta / 365``).
* **rho**   — raw is per 1.00 (100 bp×100) change in ``r``; per 1% is ``rho / 100``.

No SciPy dependency: the normal CDF uses :func:`math.erf`. Degenerate inputs
(``T <= 0`` or ``sigma <= 0``) collapse to the discounted intrinsic/forward value
so callers never hit a division by zero.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Literal

OptionType = Literal["call", "put"]

_SQRT2 = math.sqrt(2.0)
_INV_SQRT_2PI = 1.0 / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF via the error function (stdlib, no SciPy)."""
    return 0.5 * (1.0 + math.erf(x / _SQRT2))


def _norm_pdf(x: float) -> float:
    return _INV_SQRT_2PI * math.exp(-0.5 * x * x)


def _check_type(option_type: str) -> OptionType:
    if option_type not in ("call", "put"):
        raise ValueError(f"option_type must be 'call' or 'put', got {option_type!r}")
    return option_type  # type: ignore[return-value]


@dataclass(slots=True)
class OptionQuote:
    """A priced option with its full Greek profile.

    ``vega_per_pct`` / ``theta_per_day`` / ``rho_per_pct`` are the desk-friendly
    scalings of the raw analytic Greeks (see the module docstring).
    """

    option_type: OptionType
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    d1: float
    d2: float

    @property
    def vega_per_pct(self) -> float:
        return self.vega / 100.0

    @property
    def theta_per_day(self) -> float:
        return self.theta / 365.0

    @property
    def rho_per_pct(self) -> float:
        return self.rho / 100.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(
            vega_per_pct=round(self.vega_per_pct, 6),
            theta_per_day=round(self.theta_per_day, 6),
            rho_per_pct=round(self.rho_per_pct, 6),
        )
        return d


def _d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float) -> tuple[float, float]:
    vol_sqrt_t = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def _intrinsic(S: float, K: float, T: float, r: float, q: float, option_type: OptionType) -> float:
    """Deterministic value when there is no optionality (T<=0 or sigma<=0)."""
    if T <= 0:
        payoff = max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)
        return float(payoff)
    fwd = S * math.exp(-q * T)
    disc_k = K * math.exp(-r * T)
    value = fwd - disc_k if option_type == "call" else disc_k - fwd
    return float(max(value, 0.0))


def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    *,
    option_type: str = "call",
    q: float = 0.0,
) -> float:
    """Black–Scholes–Merton price of a European option."""
    option_type = _check_type(option_type)
    if S <= 0 or K <= 0:
        raise ValueError("spot and strike must be positive")
    if T <= 0 or sigma <= 0:
        return _intrinsic(S, K, T, r, q, option_type)

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    disc_s = S * math.exp(-q * T)
    disc_k = K * math.exp(-r * T)
    if option_type == "call":
        return float(disc_s * _norm_cdf(d1) - disc_k * _norm_cdf(d2))
    return float(disc_k * _norm_cdf(-d2) - disc_s * _norm_cdf(-d1))


def price_and_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    *,
    option_type: str = "call",
    q: float = 0.0,
) -> OptionQuote:
    """Price plus the full set of analytic Greeks as an :class:`OptionQuote`."""
    option_type = _check_type(option_type)
    if S <= 0 or K <= 0:
        raise ValueError("spot and strike must be positive")

    price = bs_price(S, K, T, r, sigma, option_type=option_type, q=q)

    # Degenerate case: no meaningful Greeks; report a step delta and zeros.
    if T <= 0 or sigma <= 0:
        itm = (S > K) if option_type == "call" else (S < K)
        delta = (1.0 if option_type == "call" else -1.0) if itm else 0.0
        return OptionQuote(option_type, price, delta, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    sqrt_t = math.sqrt(T)
    disc_q = math.exp(-q * T)
    disc_r = math.exp(-r * T)
    pdf_d1 = _norm_pdf(d1)

    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t
    common_theta = -(S * disc_q * pdf_d1 * sigma) / (2.0 * sqrt_t)

    if option_type == "call":
        delta = disc_q * _norm_cdf(d1)
        theta = common_theta - r * K * disc_r * _norm_cdf(d2) + q * S * disc_q * _norm_cdf(d1)
        rho = K * T * disc_r * _norm_cdf(d2)
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta = common_theta + r * K * disc_r * _norm_cdf(-d2) - q * S * disc_q * _norm_cdf(-d1)
        rho = -K * T * disc_r * _norm_cdf(-d2)

    return OptionQuote(
        option_type=option_type,
        price=float(price),
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho=float(rho),
        d1=float(d1),
        d2=float(d2),
    )


def implied_volatility(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    *,
    option_type: str = "call",
    q: float = 0.0,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> float | None:
    """Back out the volatility that reprices a European option to ``price``.

    Newton–Raphson (using vega) with a robust bisection fallback. Returns ``None``
    when the target price violates no-arbitrage bounds or no root is found.
    """
    option_type = _check_type(option_type)
    if price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return None

    # No-arbitrage bounds: discounted intrinsic <= price <= discounted underlying.
    lower = _intrinsic(S, K, T, r, q, option_type)
    upper = S * math.exp(-q * T) if option_type == "call" else K * math.exp(-r * T)
    if price < lower - 1e-12 or price > upper + 1e-12:
        return None

    sigma = 0.2
    lo, hi = 1e-6, 5.0
    for _ in range(max_iter):
        model = bs_price(S, K, T, r, sigma, option_type=option_type, q=q)
        diff = model - price
        if abs(diff) < tol:
            return float(sigma)
        # Maintain a bracket for the fallback.
        if diff > 0:
            hi = sigma
        else:
            lo = sigma
        d1, _ = _d1_d2(S, K, T, r, sigma, q)
        vega = S * math.exp(-q * T) * _norm_pdf(d1) * math.sqrt(T)
        if vega < 1e-10:
            break
        step = diff / vega
        sigma_next = sigma - step
        if not (lo < sigma_next < hi):  # keep the iterate inside the bracket
            sigma_next = 0.5 * (lo + hi)
        sigma = sigma_next

    # Bisection fallback.
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        diff = bs_price(S, K, T, r, mid, option_type=option_type, q=q) - price
        if abs(diff) < tol:
            return float(mid)
        if diff > 0:
            hi = mid
        else:
            lo = mid
    return float(0.5 * (lo + hi))
