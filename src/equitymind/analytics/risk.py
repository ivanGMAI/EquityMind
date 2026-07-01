"""Composite risk scoring on a 0-100 scale.

The score blends four intuitive, independently-interpretable components:

* **volatility** — annualised dispersion of returns,
* **drawdown** — depth of the worst peak-to-trough decline,
* **trend**    — a down-trend is riskier than an up-trend,
* **momentum** — recent negative momentum raises risk.

Each component is normalised to 0-100 against a configurable ceiling, then
combined with renormalised weights. Keeping the pieces visible (they are
returned alongside the headline number) makes the score auditable rather than a
mystery figure — important for anything a real desk would rely on.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from .volatility import annualized_volatility

# Default component weights; renormalised at runtime.
DEFAULT_WEIGHTS: dict[str, float] = {
    "volatility": 0.45,
    "drawdown": 0.30,
    "trend": 0.15,
    "momentum": 0.10,
}

_TREND_RISK = {"bullish": 15.0, "neutral": 50.0, "bearish": 100.0}


@dataclass(slots=True)
class RiskAssessment:
    score: float
    band: str
    components: dict[str, float] = field(default_factory=dict)
    annualized_volatility: float = 0.0
    max_drawdown: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def max_drawdown(close: pd.Series) -> float:
    """Worst peak-to-trough decline as a negative fraction (e.g. -0.35)."""
    close = close.astype(float)
    if close.empty:
        return 0.0
    running_max = close.cummax()
    drawdowns = close / running_max - 1.0
    return float(drawdowns.min())


def _band(score: float) -> str:
    if score < 25:
        return "Low"
    if score < 50:
        return "Moderate"
    if score < 75:
        return "Elevated"
    return "High"


def _clip(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(np.clip(value, lo, hi))


def compute_risk(
    close: pd.Series,
    *,
    trend_label: str = "neutral",
    momentum_return: float | None = None,
    weights: dict[str, float] | None = None,
    volatility_ceiling: float = 0.80,
    drawdown_ceiling: float = 0.60,
    trading_days: int = 252,
) -> RiskAssessment:
    """Compute a composite 0-100 risk score for a price series.

    Args:
        close: Close-price series.
        trend_label: ``bullish`` / ``bearish`` / ``neutral``.
        momentum_return: Recent fractional return (e.g. 30d) used for the
            momentum component. ``None`` treats momentum as neutral.
        weights: Component weights; renormalised so they need not sum to 1.
        volatility_ceiling: Annualised vol mapped to a component score of 100.
        drawdown_ceiling: Drawdown depth mapped to a component score of 100.
        trading_days: Annualisation factor for volatility.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    total_w = sum(weights.values()) or 1.0

    ann_vol = annualized_volatility(close, trading_days)
    mdd = max_drawdown(close)

    vol_score = _clip(ann_vol / volatility_ceiling * 100.0)
    dd_score = _clip(abs(mdd) / drawdown_ceiling * 100.0)
    trend_score = _TREND_RISK.get(trend_label, 50.0)
    # +/-10% momentum spans the full 0-100 range around a neutral 50.
    mom = 0.0 if momentum_return is None else momentum_return
    momentum_score = _clip(50.0 - mom * 500.0)

    components = {
        "volatility": vol_score,
        "drawdown": dd_score,
        "trend": trend_score,
        "momentum": momentum_score,
    }
    score = sum(components[k] * weights.get(k, 0.0) for k in components) / total_w
    score = round(_clip(score), 1)

    rationale = (
        f"Risk {score}/100 ({_band(score)}): annualised volatility "
        f"{ann_vol * 100:.1f}%, max drawdown {mdd * 100:.1f}%, {trend_label} trend."
    )
    return RiskAssessment(
        score=score,
        band=_band(score),
        components={k: round(v, 1) for k, v in components.items()},
        annualized_volatility=ann_vol,
        max_drawdown=mdd,
        rationale=rationale,
    )
