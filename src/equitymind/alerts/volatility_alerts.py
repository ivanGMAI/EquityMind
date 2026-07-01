"""Volatility-spike alerting.

Flags instruments whose latest rolling volatility is anomalously high relative
to its own recent history (a z-score against the trailing mean/std of the
rolling-vol series). This is a simple, explainable early-warning signal a desk
might wire into a monitor.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from ..analytics.volatility import rolling_volatility
from ..data.models import PriceHistory

Severity = Literal["info", "warning", "critical"]


@dataclass(slots=True)
class Alert:
    ticker: str
    kind: str
    severity: Severity
    message: str
    value: float
    threshold: float
    as_of: str

    def to_dict(self) -> dict:
        return asdict(self)


def detect_volatility_spike(
    history: PriceHistory,
    *,
    window: int = 21,
    lookback: int = 60,
    zscore_threshold: float = 2.0,
    trading_days: int = 252,
) -> Alert | None:
    """Return an :class:`Alert` if the latest rolling vol is a statistical spike.

    Args:
        history: Price history to evaluate.
        window: Rolling-volatility window.
        lookback: Number of trailing rolling-vol observations used as the
            baseline distribution.
        zscore_threshold: Z-score above which a spike is flagged.
        trading_days: Annualisation factor.
    """
    vol = rolling_volatility(history.close, window, trading_days).dropna()
    if len(vol) < max(lookback // 2, 5) + 1:
        return None

    latest = float(vol.iloc[-1])
    baseline = vol.iloc[-(lookback + 1) : -1]
    if len(baseline) < 5:
        return None

    mean = float(baseline.mean())
    std = float(baseline.std(ddof=1))
    if std <= 0:
        return None

    z = (latest - mean) / std
    if z < zscore_threshold:
        return None

    severity: Severity = "critical" if z >= zscore_threshold + 1 else "warning"
    return Alert(
        ticker=history.ticker,
        kind="volatility_spike",
        severity=severity,
        message=(
            f"{history.ticker}: annualised volatility {latest * 100:.1f}% is "
            f"{z:.1f}σ above its trailing {len(baseline)}-obs mean "
            f"({mean * 100:.1f}%)."
        ),
        value=round(latest, 4),
        threshold=round(zscore_threshold, 2),
        as_of=history.end.strftime("%Y-%m-%d"),
    )


def scan_volatility_spikes(
    histories: dict[str, PriceHistory],
    *,
    window: int = 21,
    lookback: int = 60,
    zscore_threshold: float = 2.0,
    trading_days: int = 252,
) -> list[Alert]:
    """Run :func:`detect_volatility_spike` across a set of instruments."""
    alerts: list[Alert] = []
    for history in histories.values():
        alert = detect_volatility_spike(
            history,
            window=window,
            lookback=lookback,
            zscore_threshold=zscore_threshold,
            trading_days=trading_days,
        )
        if alert is not None:
            alerts.append(alert)
    return alerts
