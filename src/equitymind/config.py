"""Typed, validated configuration for EquityMind.

The YAML config file (``config/config.yaml`` by default) is parsed into a nested
tree of Pydantic models. Validation happens at load time, so a malformed config
fails fast with a clear error rather than surfacing as a mysterious ``KeyError``
deep inside the analytics pipeline.

Environment variables layer on top of the file:

* ``EQUITYMIND_CONFIG``       — path to the YAML file
* ``EQUITYMIND_LLM_MODEL``    — overrides ``ai.model``
* ``EQUITYMIND_LLM_PROVIDER`` — forces ``anthropic`` or ``mock``
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

AssetClass = Literal["equity", "index", "crypto", "commodity", "fx", "other"]


class AssetSpec(BaseModel):
    """A single tracked instrument."""

    ticker: str
    name: str = ""
    asset_class: AssetClass = "equity"

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class DataConfig(BaseModel):
    period: str = "1y"
    interval: str = "1d"
    # Price data vendor: yfinance (global), moex (Moscow Exchange, RUB), or csv
    # (local files in `csv_dir`, named <TICKER>.csv).
    source: Literal["yfinance", "moex", "csv"] = "yfinance"
    csv_dir: str = "data"
    moex_market: str = "shares"
    # Optional currency override applied to the chosen source (e.g. "RUB").
    currency: str | None = None
    # Fetch fundamentals (P/E, EPS, sector...) per instrument. yfinance only;
    # off by default so the default offline path makes no extra network calls.
    include_fundamentals: bool = False
    cache_enabled: bool = True
    cache_dir: str = ".equitymind_cache"
    cache_ttl_minutes: int = Field(default=60, ge=0)


class AnalyticsConfig(BaseModel):
    return_periods_days: list[int] = [1, 7, 30]
    volatility_window: int = Field(default=21, gt=1)
    trading_days_per_year: int = Field(default=252, gt=0)
    sma_windows: list[int] = [20, 50]
    ema_windows: list[int] = [12, 26]
    rsi_window: int = Field(default=14, gt=1)
    trend_neutral_band_pct: float = Field(default=1.0, ge=0)
    # Annualised risk-free rate (fraction, e.g. 0.04 = 4%) used by the
    # risk-adjusted performance ratios (Sharpe / Sortino / alpha).
    risk_free_rate: float = Field(default=0.0, ge=0)
    # Confidence level and holding horizon for Value-at-Risk / Expected Shortfall.
    var_confidence: float = Field(default=0.95, gt=0.5, lt=1.0)
    var_horizon_days: int = Field(default=1, gt=0)


class RiskWeights(BaseModel):
    volatility: float = 0.45
    drawdown: float = 0.30
    trend: float = 0.15
    momentum: float = 0.10


class RiskConfig(BaseModel):
    weights: RiskWeights = RiskWeights()
    volatility_ceiling: float = Field(default=0.80, gt=0)
    drawdown_ceiling: float = Field(default=0.60, gt=0)


class AlertsConfig(BaseModel):
    volatility_zscore_threshold: float = 2.0
    volatility_lookback: int = Field(default=60, gt=1)


class BenchmarkConfig(BaseModel):
    """Reference instrument for beta / alpha / correlation (CAPM)."""

    enabled: bool = True
    ticker: str = "SPY"

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.strip().upper()


class PortfolioConfig(BaseModel):
    """Cross-asset portfolio analytics (correlation, mean-variance, risk parity)."""

    enabled: bool = True
    # Number of points sampled along the efficient frontier for reporting.
    frontier_points: int = Field(default=25, ge=2)


class AIConfig(BaseModel):
    model: str = "claude-opus-4-8"
    max_tokens: int = Field(default=1500, gt=0)
    effort: Literal["low", "medium", "high", "max"] = "medium"
    temperature_note: str = ""


class ReportingConfig(BaseModel):
    output_dir: str = "reports"
    include_charts: bool = True
    # Extra export formats written alongside the markdown report (also toggled by
    # the CLI --pptx / --xlsx flags).
    export_pptx: bool = False
    export_xlsx: bool = False


class Settings(BaseModel):
    """Root configuration object."""

    universe: list[AssetSpec]
    data: DataConfig = DataConfig()
    analytics: AnalyticsConfig = AnalyticsConfig()
    risk: RiskConfig = RiskConfig()
    alerts: AlertsConfig = AlertsConfig()
    benchmark: BenchmarkConfig = BenchmarkConfig()
    portfolio: PortfolioConfig = PortfolioConfig()
    ai: AIConfig = AIConfig()
    reporting: ReportingConfig = ReportingConfig()

    # ------------------------------------------------------------------ helpers
    def tickers(self) -> list[str]:
        """All configured tickers, in declaration order."""
        return [a.ticker for a in self.universe]

    def asset(self, ticker: str) -> AssetSpec | None:
        """Look up an :class:`AssetSpec` by ticker (case-insensitive)."""
        ticker = ticker.strip().upper()
        return next((a for a in self.universe if a.ticker == ticker), None)


def _apply_env_overrides(settings: Settings) -> Settings:
    if model := os.getenv("EQUITYMIND_LLM_MODEL"):
        settings.ai.model = model
    return settings


def load_settings(path: str | Path | None = None) -> Settings:
    """Load and validate settings from a YAML file.

    Args:
        path: Config path. Defaults to ``$EQUITYMIND_CONFIG`` then
            ``config/config.yaml``.

    Raises:
        FileNotFoundError: If the config file does not exist.
        pydantic.ValidationError: If the file is structurally invalid.
    """
    resolved = Path(path or os.getenv("EQUITYMIND_CONFIG") or "config/config.yaml").expanduser()
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")

    with resolved.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return _apply_env_overrides(Settings(**raw))


@lru_cache(maxsize=8)
def get_settings(path: str | None = None) -> Settings:
    """Cached accessor so repeated calls don't re-read/parse the file."""
    return load_settings(path)
