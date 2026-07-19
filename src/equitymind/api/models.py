"""Pydantic models for API requests and responses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Request to start a new analysis."""

    tickers: list[str] = Field(..., description="List of ticker symbols (e.g. ['SBER', 'GAZP'])")
    period: str = Field(
        default="1y", description="Historical period: 1mo, 3mo, 6mo, 1y, 2y, 5y, max"
    )
    interval: str = Field(default="1d", description="Bar interval: 1d, 1wk, 1mo")
    return_basis: str = Field(
        default="cumulative", description="Ranking basis: cumulative, 30d, 7d, 1d"
    )
    with_ai: bool = Field(default=True, description="Include AI-generated commentary")
    with_backtest: bool = Field(default=True, description="Include trend backtest")
    source: str = Field(default="yfinance", description="Data source: moex, yfinance, csv")


class JobStatus(str, Enum):
    """Job execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(slots=True)
class AnalysisJob:
    """In-memory state of an analysis job."""

    job_id: str
    status: JobStatus
    progress: float  # 0.0 to 1.0
    current_step: str
    request: AnalysisRequest
    result: dict[str, Any] | None = None
    error: str | None = None
    #: The live AnalysisReport object — kept so the tool-using agent can be
    #: bound to it after the run (the serialized ``result`` is not enough).
    report: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON."""
        return {
            "job_id": self.job_id,
            "status": self.status.value,
            "progress": self.progress,
            "current_step": self.current_step,
            "error": self.error,
        }


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: str
    progress: float = Field(..., ge=0, le=1, description="Progress 0.0-1.0")
    current_step: str = Field(..., description="Name of current processing step")
    error: str | None = None


class JobSubmitResponse(BaseModel):
    """Response when submitting a new job."""

    job_id: str
    status: str
    message: str


class AgentRequest(BaseModel):
    """Question for the tool-using agent, bound to a finished analysis job."""

    job_id: str = Field(..., description="ID of a completed analysis job")
    question: str = Field(..., min_length=1, max_length=2000)


class OptionsRequest(BaseModel):
    """Inputs for the Black-Scholes options lab."""

    strategy: str = Field(
        default="long_call",
        description=(
            "long_call | long_put | straddle | covered_call | protective_put | bull_call_spread"
        ),
    )
    spot: float = Field(default=100.0, gt=0)
    strike: float = Field(default=100.0, gt=0)
    strike2: float = Field(default=110.0, gt=0, description="Upper strike (bull call spread)")
    maturity_years: float = Field(default=0.5, gt=0, le=30)
    volatility: float = Field(default=0.25, gt=0, le=5)
    rate: float = Field(default=0.08, ge=-1, le=1)
    dividend_yield: float = Field(default=0.0, ge=0, le=1)


class AssetMetricsResponse(BaseModel):
    """Metrics for a single asset."""

    ticker: str
    last_price: float | None = None
    returns_1d: float | None = None
    returns_7d: float | None = None
    returns_30d: float | None = None
    cumulative_return: float | None = None
    annualized_return: float | None = None
    volatility_pct: float | None = None
    sharpe: float | None = None
    sortino: float | None = None
    max_drawdown: float | None = None


class ComparisonEntryResponse(BaseModel):
    """Single row in ranking table."""

    ticker: str
    return_pct: float
    volatility_pct: float
    sharpe: float | None = None
    rank: int | None = None


class AnalysisResultResponse(BaseModel):
    """Complete analysis result."""

    generated_at: str
    ai_provider: str
    ai_model: str
    assets: dict[str, dict[str, Any]] = Field(default_factory=dict)
    comparison: list[ComparisonEntryResponse] = Field(default_factory=list)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    failures: dict[str, str] = Field(default_factory=dict)
