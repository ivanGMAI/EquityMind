"""Value-at-Risk (VaR) and Conditional VaR / Expected Shortfall (CVaR).

Two complementary estimation methods are provided:

* **Historical** — empirical quantile of the realised return distribution. Makes
  no distributional assumption and captures observed fat tails and skew, but is
  bounded by the worst move actually seen in the sample.
* **Parametric (Gaussian)** — assumes normally-distributed returns and derives
  VaR/CVaR in closed form from the mean and standard deviation. Smooth and
  extrapolates beyond the sample, but understates tail risk when returns are
  fat-tailed.

Both are reported as **positive loss fractions** (e.g. ``0.032`` means a 3.2%
loss) at a given confidence level, scaled to the requested holding horizon by the
square-root-of-time rule. Reporting both side by side makes the model risk
explicit — a hallmark of how a real risk desk frames these numbers.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .returns import daily_returns


@dataclass(slots=True)
class TailRisk:
    """VaR / CVaR estimates as positive loss fractions at ``confidence``."""

    confidence: float
    horizon_days: int
    historical_var: float = 0.0
    historical_cvar: float = 0.0
    parametric_var: float = 0.0
    parametric_cvar: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Standard-normal helpers (no SciPy dependency)
# ---------------------------------------------------------------------------
def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF via Acklam's rational approximation.

    Accurate to ~1e-9 over the open interval (0, 1) — ample for VaR quantiles.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in (0, 1)")

    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]

    p_low, p_high = 0.02425, 1.0 - 0.02425
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > p_high:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (
        (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
        * q
        / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    )


def _loss(value: float) -> float:
    """Express a (typically negative) return as a non-negative loss fraction."""
    return float(max(-value, 0.0))


def historical_var(close: pd.Series, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Historical VaR: empirical loss quantile at ``confidence``."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return 0.0
    quantile = float(np.quantile(rets, 1.0 - confidence))
    return _loss(quantile) * math.sqrt(horizon_days)


def historical_cvar(close: pd.Series, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Historical CVaR / Expected Shortfall: mean loss beyond the VaR quantile."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return 0.0
    threshold = np.quantile(rets, 1.0 - confidence)
    tail = rets[rets <= threshold]
    if tail.empty:
        return historical_var(close, confidence, horizon_days)
    return _loss(float(tail.mean())) * math.sqrt(horizon_days)


def parametric_var(close: pd.Series, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Gaussian (variance-covariance) VaR from the sample mean and volatility."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return 0.0
    mu = float(rets.mean())
    sigma = float(rets.std(ddof=1))
    if sigma == 0:
        return 0.0
    z = _norm_ppf(1.0 - confidence)  # negative
    return _loss(mu + sigma * z) * math.sqrt(horizon_days)


def parametric_cvar(close: pd.Series, confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Gaussian Expected Shortfall: closed-form tail mean of a normal."""
    rets = daily_returns(close)
    if len(rets) < 2:
        return 0.0
    mu = float(rets.mean())
    sigma = float(rets.std(ddof=1))
    if sigma == 0:
        return 0.0
    alpha = 1.0 - confidence
    z = _norm_ppf(alpha)
    # E[r | r <= VaR] under normality = mu - sigma * phi(z)/alpha.
    es = mu - sigma * _norm_pdf(z) / alpha
    return _loss(es) * math.sqrt(horizon_days)


def compute_tail_risk(
    close: pd.Series, *, confidence: float = 0.95, horizon_days: int = 1
) -> TailRisk:
    """Bundle historical and parametric VaR/CVaR at one confidence level."""
    return TailRisk(
        confidence=confidence,
        horizon_days=horizon_days,
        historical_var=round(historical_var(close, confidence, horizon_days), 5),
        historical_cvar=round(historical_cvar(close, confidence, horizon_days), 5),
        parametric_var=round(parametric_var(close, confidence, horizon_days), 5),
        parametric_cvar=round(parametric_cvar(close, confidence, horizon_days), 5),
    )
