"""End-to-end orchestration.

:class:`IntelligencePipeline` is the single entry point that composes every
layer — data loading, analytics, AI commentary, comparison, alerting and
backtesting — into one :class:`AnalysisReport`. The CLI, the REST API and
tests all drive the system through this class, so the wiring lives in exactly
one place.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .ai.analyst import MarketAnalyst, MarketCommentary
from .ai.providers import build_provider
from .alerts.volatility_alerts import Alert, scan_volatility_spikes
from .analytics.metrics import AssetMetrics, compute_metrics_from_settings
from .backtesting.trend_backtest import BacktestResult, backtest_sma_crossover
from .comparison.compare_assets import AssetComparison, compare_assets
from .config import AssetSpec, Settings, get_settings
from .data.cache import PriceCache
from .data.csv_source import CSVSource
from .data.fundamentals import Fundamentals, FundamentalsSource, YFinanceFundamentals
from .data.models import PriceHistory
from .data.moex import MoexSource
from .data.stock_data_loader import DataSource, StockDataLoader, YFinanceSource
from .logging_config import get_logger
from .portfolio.analyze import PortfolioReport, analyze_portfolio

if TYPE_CHECKING:  # only used in a type annotation
    import pandas as pd

logger = get_logger(__name__)


@dataclass(slots=True)
class AssetAnalysis:
    """Everything computed for a single instrument."""

    history: PriceHistory
    metrics: AssetMetrics
    commentary: MarketCommentary | None = None
    backtest: BacktestResult | None = None
    fundamentals: Fundamentals | None = None


@dataclass(slots=True)
class AnalysisReport:
    """Aggregated output of a pipeline run."""

    generated_at: str
    ai_provider: str
    ai_model: str
    assets: dict[str, AssetAnalysis] = field(default_factory=dict)
    comparison: AssetComparison | None = None
    portfolio: PortfolioReport | None = None
    alerts: list[Alert] = field(default_factory=list)
    failures: dict[str, str] = field(default_factory=dict)
    #: Benchmark used for beta/alpha, kept for relative-performance charts.
    benchmark_ticker: str | None = None
    benchmark_close: pd.Series | None = None

    def metrics_list(self) -> list[AssetMetrics]:
        return [a.metrics for a in self.assets.values()]


class IntelligencePipeline:
    """Compose the full analysis stack from a :class:`Settings` object."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        loader: StockDataLoader | None = None,
        analyst: MarketAnalyst | None = None,
        fundamentals_source: FundamentalsSource | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.loader = loader or self._build_loader(self.settings)
        self.analyst = analyst or self._build_analyst(self.settings)
        self.fundamentals_source = fundamentals_source or (
            YFinanceFundamentals() if self.settings.data.include_fundamentals else None
        )

    # ------------------------------------------------------------------ wiring
    @staticmethod
    def _build_source(settings: Settings) -> DataSource:
        data = settings.data
        if data.source == "moex":
            return MoexSource(market=data.moex_market, currency=data.currency or "RUB")
        if data.source == "csv":
            return CSVSource(data.csv_dir, currency=data.currency or "USD")
        return YFinanceSource()

    @classmethod
    def _build_loader(cls, settings: Settings) -> StockDataLoader:
        cache = (
            PriceCache(settings.data.cache_dir, settings.data.cache_ttl_minutes)
            if settings.data.cache_enabled
            else None
        )
        return StockDataLoader(
            source=cls._build_source(settings),
            cache=cache,
            default_period=settings.data.period,
            default_interval=settings.data.interval,
        )

    @staticmethod
    def _build_analyst(settings: Settings) -> MarketAnalyst:
        provider = build_provider(
            model=settings.ai.model,
            max_tokens=settings.ai.max_tokens,
            effort=settings.ai.effort,
        )
        return MarketAnalyst(provider)

    # ------------------------------------------------------------------ run
    def run(
        self,
        tickers: Sequence[str] | None = None,
        *,
        with_commentary: bool = True,
        with_backtest: bool = True,
        return_basis: str = "cumulative",
        use_cache: bool = True,
    ) -> AnalysisReport:
        """Execute the pipeline over ``tickers`` (defaults to the config universe).

        Args:
            tickers: Symbols to analyse; ``None`` uses ``settings.universe``.
            with_commentary: Generate AI commentary per asset.
            with_backtest: Run the SMA-crossover backtest per asset.
            return_basis: Ranking basis passed to :func:`compare_assets`.
            use_cache: Consult the on-disk price cache.
        """
        assets = self._resolve_assets(tickers)
        logger.info("Running pipeline for %d instruments", len(assets))
        fetch = self.loader.load_many(assets, use_cache=use_cache)

        bench_ticker, bench_close = self._resolve_benchmark(fetch.histories, use_cache)

        analyses: dict[str, AssetAnalysis] = {}
        for ticker, history in fetch.histories.items():
            # Don't compare the benchmark against itself (beta/alpha are trivial).
            asset_bench = None if ticker == bench_ticker else bench_close
            metrics = compute_metrics_from_settings(
                history,
                self.settings,
                benchmark_close=asset_bench,
                benchmark_ticker="" if asset_bench is None else (bench_ticker or ""),
            )
            backtest = None
            if with_backtest:
                backtest = backtest_sma_crossover(
                    history,
                    fast_window=min(self.settings.analytics.sma_windows),
                    slow_window=max(self.settings.analytics.sma_windows),
                    trading_days=self.settings.analytics.trading_days_per_year,
                )
            fundamentals = None
            if self.fundamentals_source is not None:
                try:
                    fundamentals = self.fundamentals_source.fetch(ticker)
                except Exception as exc:  # fundamentals are non-fatal
                    logger.error("Fundamentals failed for %s: %s", ticker, exc)
            analyses[ticker] = AssetAnalysis(
                history=history,
                metrics=metrics,
                backtest=backtest,
                fundamentals=fundamentals,
            )

        # AI commentary is by far the slowest step (a multi-second LLM call per
        # instrument). Run it concurrently across instruments so the total wait is
        # roughly one call rather than N sequential ones.
        if with_commentary and analyses:
            self._attach_commentary(analyses)

        comparison = (
            compare_assets([a.metrics for a in analyses.values()], return_basis=return_basis)
            if analyses
            else None
        )
        portfolio = None
        if self.settings.portfolio.enabled and len(fetch.histories) >= 2:
            portfolio = analyze_portfolio(
                fetch.histories,
                risk_free_rate=self.settings.analytics.risk_free_rate,
                trading_days=self.settings.analytics.trading_days_per_year,
                frontier_points=self.settings.portfolio.frontier_points,
            )
        alerts = scan_volatility_spikes(
            fetch.histories,
            window=self.settings.analytics.volatility_window,
            lookback=self.settings.alerts.volatility_lookback,
            zscore_threshold=self.settings.alerts.volatility_zscore_threshold,
            trading_days=self.settings.analytics.trading_days_per_year,
        )

        return AnalysisReport(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            ai_provider=self.analyst.provider.name,
            ai_model=self.analyst.provider.model or "n/a",
            assets=analyses,
            comparison=comparison,
            portfolio=portfolio,
            alerts=alerts,
            failures=fetch.failures,
            benchmark_ticker=bench_ticker,
            benchmark_close=bench_close,
        )

    # ------------------------------------------------------------------ helpers
    def _attach_commentary(self, analyses: dict[str, AssetAnalysis]) -> None:
        """Generate AI commentary for every instrument concurrently.

        Each call is an independent, network-bound LLM request, so running them
        in a thread pool collapses N sequential waits into roughly one. Failures
        are non-fatal per instrument (the asset simply gets no commentary).
        """

        def _one(ticker: str) -> tuple[str, MarketCommentary | None]:
            try:
                return ticker, self.analyst.analyze(analyses[ticker].metrics)
            except Exception as exc:  # commentary is non-fatal
                logger.error("Commentary failed for %s: %s", ticker, exc)
                return ticker, None

        max_workers = min(len(analyses), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for ticker, commentary in pool.map(_one, list(analyses)):
                analyses[ticker].commentary = commentary

    def _resolve_benchmark(
        self, histories: dict[str, PriceHistory], use_cache: bool
    ) -> tuple[str | None, pd.Series | None]:
        """Resolve the benchmark close series for beta/alpha, if enabled.

        Prefers a benchmark already present in the fetched set; otherwise loads it
        separately so beta/alpha work even when the benchmark isn't analysed.
        Returns ``(None, None)`` when disabled or unavailable (non-fatal).
        """
        bench_cfg = self.settings.benchmark
        if not bench_cfg.enabled:
            return None, None
        ticker = bench_cfg.ticker
        if ticker in histories:
            return ticker, histories[ticker].close
        try:
            history = self.loader.load(ticker, use_cache=use_cache)
            return ticker, history.close
        except Exception as exc:  # benchmark is non-fatal context
            logger.warning("Benchmark '%s' unavailable (%s); skipping beta/alpha", ticker, exc)
            return None, None

    def _resolve_assets(self, tickers: Sequence[str] | None) -> list[AssetSpec]:
        if not tickers:
            return list(self.settings.universe)
        resolved: list[AssetSpec] = []
        for t in tickers:
            spec = self.settings.asset(t)
            resolved.append(spec or AssetSpec(ticker=t))
        return resolved
