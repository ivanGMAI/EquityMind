"""Cross-asset comparison and ranking.

Assets are ranked by a reward-to-risk ratio — the return earned per unit of
volatility (a risk-free-rate-agnostic Sharpe proxy). This rewards steady
performers over those that merely posted a big number with wild swings, which is
how a real desk frames "which of these looks best on a risk-adjusted basis".

The composite 0-100 risk score is surfaced alongside for context but the primary
sort is intentionally return / volatility so the ranking is grounded in
observable price behaviour.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass, field

import pandas as pd

from ..analytics.metrics import AssetMetrics


@dataclass(slots=True)
class RankingEntry:
    rank: int
    ticker: str
    name: str
    return_basis: str
    return_pct: float | None
    annualized_volatility_pct: float
    risk_score: float | None
    reward_risk_ratio: float | None
    trend: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class AssetComparison:
    return_basis: str
    entries: list[RankingEntry] = field(default_factory=list)

    @property
    def best(self) -> RankingEntry | None:
        return self.entries[0] if self.entries else None

    @property
    def worst(self) -> RankingEntry | None:
        return self.entries[-1] if self.entries else None

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([e.to_dict() for e in self.entries])

    def to_payload(self) -> dict:
        return {
            "return_basis": self.return_basis,
            "ranking": [e.to_dict() for e in self.entries],
            "best": self.best.ticker if self.best else None,
            "worst": self.worst.ticker if self.worst else None,
        }


def _return_for_basis(m: AssetMetrics, basis: str) -> float | None:
    """Fractional return for ``basis`` ('cumulative' or a period like '30d')."""
    if basis == "cumulative":
        return m.cumulative_return
    return m.returns.get(basis)


def _ratio(return_frac: float | None, vol_frac: float) -> float | None:
    if return_frac is None or vol_frac <= 0:
        return None
    return round(return_frac / vol_frac, 3)


def compare_assets(
    metrics: Sequence[AssetMetrics], *, return_basis: str = "cumulative"
) -> AssetComparison:
    """Rank assets by reward-to-risk ratio (descending).

    Args:
        metrics: One :class:`AssetMetrics` per instrument.
        return_basis: ``"cumulative"`` (full-sample) or a return-period key such
            as ``"30d"``. Unknown/short windows yield a ``None`` ratio and sort
            to the bottom.
    """
    scored: list[tuple[float | None, AssetMetrics, float | None]] = []
    for m in metrics:
        ret = _return_for_basis(m, return_basis)
        ratio = _ratio(ret, m.annualized_volatility)
        scored.append((ratio, m, ret))

    # None ratios rank last; otherwise higher ratio is better.
    scored.sort(key=lambda t: (t[0] is not None, t[0] or 0.0), reverse=True)

    entries: list[RankingEntry] = []
    for rank, (ratio, m, ret) in enumerate(scored, start=1):
        entries.append(
            RankingEntry(
                rank=rank,
                ticker=m.ticker,
                name=m.name,
                return_basis=return_basis,
                return_pct=None if ret is None else round(ret * 100.0, 2),
                annualized_volatility_pct=round(m.annualized_volatility * 100.0, 2),
                risk_score=m.risk.score if m.risk else None,
                reward_risk_ratio=ratio,
                trend=m.trend.classification if m.trend else "unknown",
            )
        )
    return AssetComparison(return_basis=return_basis, entries=entries)
