"""FastAPI server for EquityMind REST API.

Run with:
    uvicorn equitymind.api.server:app --host 0.0.0.0 --port 8000 --reload

Or use the convenience function:
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..logging_config import get_logger
from ..pipeline import IntelligencePipeline
from .models import (
    AgentRequest,
    AnalysisJob,
    AnalysisRequest,
    JobStatus,
    JobStatusResponse,
    JobSubmitResponse,
    OptionsRequest,
)

logger = get_logger(__name__)


# Global job store (in-memory; use Redis in production)
_jobs: dict[str, AnalysisJob] = {}

# Ticker catalog cache: source -> (fetched_at_monotonic, entries). MOEX's board
# listing changes rarely, so a day-long TTL avoids hammering the ISS API.
_catalog_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
_CATALOG_TTL_SECONDS = 86400

# Yahoo has no free "list everything" endpoint — offer a curated set of liquid
# US large caps, index/commodity ETFs and major crypto pairs.
_YFINANCE_CATALOG: list[dict[str, str]] = [
    {"ticker": t, "name": n}
    for t, n in [
        ("AAPL", "Apple"), ("MSFT", "Microsoft"), ("GOOGL", "Alphabet"),
        ("AMZN", "Amazon"), ("NVDA", "NVIDIA"), ("META", "Meta Platforms"),
        ("TSLA", "Tesla"), ("BRK-B", "Berkshire Hathaway"), ("JPM", "JPMorgan Chase"),
        ("V", "Visa"), ("MA", "Mastercard"), ("JNJ", "Johnson & Johnson"),
        ("WMT", "Walmart"), ("XOM", "Exxon Mobil"), ("CVX", "Chevron"),
        ("PG", "Procter & Gamble"), ("KO", "Coca-Cola"), ("PEP", "PepsiCo"),
        ("HD", "Home Depot"), ("BAC", "Bank of America"), ("GS", "Goldman Sachs"),
        ("MS", "Morgan Stanley"), ("NFLX", "Netflix"), ("AMD", "AMD"),
        ("INTC", "Intel"), ("CRM", "Salesforce"), ("ORCL", "Oracle"),
        ("ADBE", "Adobe"), ("AVGO", "Broadcom"), ("QCOM", "Qualcomm"),
        ("TXN", "Texas Instruments"), ("IBM", "IBM"), ("DIS", "Walt Disney"),
        ("MCD", "McDonald's"), ("NKE", "Nike"), ("PFE", "Pfizer"),
        ("ABBV", "AbbVie"), ("LLY", "Eli Lilly"), ("BA", "Boeing"),
        ("CAT", "Caterpillar"), ("GE", "GE Aerospace"), ("UBER", "Uber"),
        ("PYPL", "PayPal"), ("SPY", "S&P 500 ETF"), ("QQQ", "Nasdaq-100 ETF"),
        ("GLD", "Gold ETF"), ("BTC-USD", "Bitcoin"), ("ETH-USD", "Ethereum"),
    ]
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="EquityMind API",
        description="AI Market Intelligence System",
        version="0.1.0",
    )

    # Add CORS middleware for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, restrict to your domain
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

    @app.get("/api/tickers", tags=["catalog"])
    async def list_tickers(source: str = Query("moex")) -> dict[str, Any]:
        """Selectable ticker catalog: live MOEX board listing or curated Yahoo set."""
        if source == "yfinance":
            return {"source": source, "tickers": _YFINANCE_CATALOG}
        if source != "moex":
            raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

        cached = _catalog_cache.get(source)
        now = time.monotonic()
        if cached and now - cached[0] < _CATALOG_TTL_SECONDS:
            return {"source": source, "tickers": cached[1]}

        from ..data.moex import list_securities

        try:
            entries = await asyncio.to_thread(list_securities)
        except Exception as exc:
            if cached:  # stale cache beats an error page
                return {"source": source, "tickers": cached[1]}
            raise HTTPException(status_code=502, detail=f"MOEX ISS unavailable: {exc}") from exc

        entries.sort(key=lambda e: e["ticker"])
        _catalog_cache[source] = (now, entries)
        return {"source": source, "tickers": entries}

    @app.get("/api/prices", tags=["analysis"], response_model=None)
    async def get_prices(
        ticker: str = Query(..., description="Instrument symbol, e.g. IMOEX"),
        source: str = Query("moex", description="Data source: moex, yfinance, csv"),
        period: str = Query("1y", description="History window: 1mo…max"),
        interval: str = Query("1d"),
    ) -> Any:
        """Chart-ready price history for a single instrument (no full analysis).

        Powers the home-screen index chart with its own timeframe selector.
        """
        settings = get_settings()
        settings.data.source = source
        settings.data.period = period
        settings.data.interval = interval
        loader = IntelligencePipeline._build_loader(settings)
        try:
            history = await asyncio.to_thread(
                loader.load, ticker, period=period, interval=interval
            )
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Не удалось загрузить {ticker}: {exc}"
            ) from exc
        return {
            "ticker": history.ticker,
            "currency": history.currency,
            "history": _serialize_history(history, max_points=1000),
        }

    @app.post("/api/analyze", tags=["analysis"], response_model=JobSubmitResponse)
    async def submit_analysis(request: AnalysisRequest) -> JobSubmitResponse:
        """Submit a new analysis job.

        Returns a job_id that can be used to poll progress and retrieve results.
        """
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            job_id=job_id,
            status=JobStatus.QUEUED,
            progress=0.0,
            current_step="Инициализация...",
            request=request,
        )
        _jobs[job_id] = job

        # Start analysis in background
        asyncio.create_task(_run_analysis(job_id))

        logger.info("Analysis job submitted: %s (tickers=%s)", job_id, request.tickers)
        return JobSubmitResponse(
            job_id=job_id,
            status=JobStatus.QUEUED.value,
            message="Analysis started. Use /api/progress/{job_id} to track progress.",
        )

    @app.get("/api/progress/{job_id}", tags=["analysis"], response_model=JobStatusResponse)
    async def get_progress(job_id: str) -> JobStatusResponse:
        """Get the current progress of an analysis job."""
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status.value,
            progress=job.progress,
            current_step=job.current_step,
            error=job.error,
        )

    # NOTE: no response model on purpose — FastAPI would use it to FILTER the
    # payload, silently dropping keys it doesn't know (portfolio, benchmark…).
    @app.get("/api/result/{job_id}", tags=["analysis"], response_model=None)
    async def get_result(job_id: str) -> Any:
        """Get the result of a completed analysis job.

        Returns 404 if job not found, 202 if still running, or 200 with results.
        """
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        if job.status == JobStatus.RUNNING:
            return JSONResponse(
                status_code=202,
                content={"message": "Analysis still running", "progress": job.progress},
            )

        if job.status == JobStatus.FAILED:
            raise HTTPException(
                status_code=400,
                detail=f"Analysis failed: {job.error}",
            )

        if job.result is None:
            raise HTTPException(
                status_code=500,
                detail="Result is None (this should not happen)",
            )

        return job.result

    @app.post("/api/agent", tags=["agent"])
    async def ask_agent(request: AgentRequest) -> dict[str, Any]:
        """Ask the tool-using agent a question about a finished analysis.

        The agent calls real analytics tools (metrics, ranking, portfolio,
        option pricing) and grounds its answer in their outputs.
        """
        job = _jobs.get(request.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {request.job_id} not found")
        if job.status != JobStatus.DONE or job.report is None:
            raise HTTPException(
                status_code=409, detail="Analysis is not finished yet; ask again once it is done"
            )

        from ..agent import AgentError, build_agent

        question = request.question.strip()
        try:
            # The agent loop is blocking (LLM + tools) — keep the event loop free.
            result = await asyncio.to_thread(lambda: build_agent(job.report).ask(question))
        except AgentError as exc:
            raise HTTPException(status_code=502, detail=f"Agent failed: {exc}") from exc

        return {
            "answer": result.answer,
            "provider": result.provider,
            "model": result.model,
            "steps": [{"tool": s.tool, "arguments": s.arguments} for s in result.steps],
        }

    @app.post("/api/options", tags=["options"])
    async def price_options(request: OptionsRequest) -> dict[str, Any]:
        """Black-Scholes options lab: strategy payoff, summary and net greeks."""
        import numpy as np

        from ..derivatives import black_scholes as bs
        from ..derivatives import payoff as pf

        S, K1, K2 = request.spot, request.strike, request.strike2
        T, sigma = request.maturity_years, request.volatility
        r, q = request.rate, request.dividend_yield

        c1 = bs.bs_price(S, K1, T, r, sigma, option_type="call", q=q)
        p1 = bs.bs_price(S, K1, T, r, sigma, option_type="put", q=q)
        builders = {
            "long_call": lambda: pf.long_call(K1, c1),
            "long_put": lambda: pf.long_put(K1, p1),
            "straddle": lambda: pf.straddle(K1, c1, p1),
            "covered_call": lambda: pf.covered_call(S, K1, c1),
            "protective_put": lambda: pf.protective_put(S, K1, p1),
            "bull_call_spread": lambda: pf.bull_call_spread(
                K1, K2, c1, bs.bs_price(S, K2, T, r, sigma, option_type="call", q=q)
            ),
        }
        builder = builders.get(request.strategy)
        if builder is None:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown strategy '{request.strategy}'; one of: {sorted(builders)}",
            )
        legs = builder()

        spots = np.linspace(0.5 * S, 1.5 * S, 200)
        pnl = pf.strategy_pnl(legs, spots)
        summary = pf.strategy_summary(legs, spots)

        greeks = {"delta": 0.0, "gamma": 0.0, "vega_per_pct": 0.0, "theta_per_day": 0.0}
        for leg in legs:
            if leg.kind == "underlying":
                greeks["delta"] += leg.quantity
                continue
            gq = bs.price_and_greeks(S, leg.strike, T, r, sigma, option_type=leg.kind, q=q)
            greeks["delta"] += leg.quantity * gq.delta
            greeks["gamma"] += leg.quantity * gq.gamma
            greeks["vega_per_pct"] += leg.quantity * gq.vega_per_pct
            greeks["theta_per_day"] += leg.quantity * gq.theta_per_day

        return {
            "payoff": [
                {"spot": round(float(s), 4), "pnl": round(float(p), 4)}
                for s, p in zip(spots, pnl, strict=False)
            ],
            "summary": {
                "net_cost": round(summary.net_cost, 4),
                "max_profit": None if summary.max_profit_unbounded else round(summary.max_profit, 4),
                "max_loss": None if summary.max_loss_unbounded else round(summary.max_loss, 4),
                "breakevens": [round(float(b), 4) for b in summary.breakevens],
            },
            "greeks": {k: round(v, 6) for k, v in greeks.items()},
            "legs": [leg.to_dict() for leg in legs],
        }

    @app.get("/api/export/{job_id}/{fmt}", tags=["export"])
    async def export_report(job_id: str, fmt: str) -> Any:
        """Export a finished analysis as markdown / pptx / xlsx."""
        from fastapi.responses import FileResponse

        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        if job.status != JobStatus.DONE or job.report is None:
            raise HTTPException(status_code=409, detail="Analysis is not finished yet")

        settings = get_settings()
        out_dir = settings.reporting.output_dir
        charts_on = settings.reporting.include_charts

        def _generate() -> tuple[str, str]:
            if fmt == "markdown":
                from ..reporting.report_generator import ReportGenerator

                path = ReportGenerator(out_dir).write_report(job.report, include_charts=charts_on)
                return str(path), "text/markdown"
            if fmt == "pptx":
                from ..reporting.powerpoint import PowerPointGenerator

                path = PowerPointGenerator(out_dir).write_deck(job.report, include_charts=charts_on)
                return (
                    str(path),
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            if fmt == "xlsx":
                from ..reporting.excel import ExcelGenerator

                path = ExcelGenerator(out_dir).write_workbook(job.report)
                return (
                    str(path),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            raise HTTPException(
                status_code=422, detail=f"Unknown format '{fmt}'; one of: markdown, pptx, xlsx"
            )

        path, media_type = await asyncio.to_thread(_generate)
        return FileResponse(path, media_type=media_type, filename=Path(path).name)

    @app.get("/api/jobs", tags=["admin"])
    async def list_jobs(status: str | None = Query(None)) -> dict[str, Any]:
        """List all jobs (optionally filter by status). Admin endpoint."""
        jobs_data = [
            job.to_dict()
            for job in _jobs.values()
            if status is None or job.status.value == status
        ]
        return {
            "total": len(_jobs),
            "jobs": jobs_data,
        }

    @app.delete("/api/jobs/{job_id}", tags=["admin"])
    async def delete_job(job_id: str) -> dict[str, str]:
        """Delete a job from the store. Admin endpoint."""
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        del _jobs[job_id]
        return {"message": f"Job {job_id} deleted"}

    return app


async def _run_analysis(job_id: str) -> None:
    """Run the analysis pipeline in the background."""
    job = _jobs[job_id]
    req = job.request

    try:
        job.status = JobStatus.RUNNING
        job.progress = 0.05
        job.current_step = "Загружаю данные…"
        logger.info("Analysis started: %s", job_id)

        # Initialize pipeline
        settings = get_settings()
        settings.data.period = req.period
        settings.data.interval = req.interval
        settings.data.source = req.source
        settings.benchmark.ticker = "IMOEX" if req.source == "moex" else "SPY"

        pipeline = IntelligencePipeline(settings)

        # Run analysis (synchronous, blocking)
        job.progress = 0.1
        job.current_step = (
            "Считаю метрики и AI-комментарий…" if req.with_ai else "Считаю метрики…"
        )

        # pipeline.run() is synchronous; run it in a worker thread so the event
        # loop keeps serving /api/progress polls. The pipeline doesn't emit
        # sub-step progress (the AI commentary dominates and gives no signal), so
        # we creep the bar forward while we wait — it never reaches 0.9 until the
        # real work is actually done.
        task = asyncio.create_task(
            asyncio.to_thread(
                pipeline.run,
                tickers=req.tickers or None,
                with_commentary=req.with_ai,
                with_backtest=req.with_backtest,
                return_basis=req.return_basis,
            )
        )
        while not task.done():
            await asyncio.sleep(1.2)
            if job.progress < 0.85:
                job.progress = round(min(0.85, job.progress + 0.025), 3)
        report = await task

        job.progress = 0.9
        job.current_step = "Обрабатываю результаты…"

        # Keep the live report for the agent, then serialize for the API.
        job.report = report
        job.result = _serialize_report(report)
        job.progress = 1.0
        job.current_step = "Готово!"
        job.status = JobStatus.DONE

        logger.info("Analysis completed: %s", job_id)

    except Exception as exc:
        logger.error("Analysis failed: %s — %s", job_id, exc, exc_info=True)
        job.status = JobStatus.FAILED
        job.error = str(exc)
        job.progress = 0.0


def _serialize_history(history: Any, max_points: int = 1500) -> list[dict[str, Any]]:
    """Serialize a PriceHistory to chart-ready points with SMA overlays.

    Long histories are *evenly down-sampled* (not truncated) to ``max_points`` so
    an "all time" view spans the whole range while staying light enough for the
    browser to render smoothly (thousands of points freeze the chart).
    """
    import math

    from ..analytics.indicators import sma

    close_full = history.close
    sma20_full = sma(close_full, 20)
    sma50_full = sma(close_full, 50)

    if len(close_full) > max_points:
        step = len(close_full) // max_points + 1
        close = close_full.iloc[::step]
    else:
        close = close_full
    sma20 = sma20_full.reindex(close.index)
    sma50 = sma50_full.reindex(close.index)

    def _num(value: float) -> float | None:
        return None if value is None or math.isnan(value) else round(float(value), 4)

    return [
        {
            "date": ts.strftime("%Y-%m-%d"),
            "close": _num(c),
            "sma20": _num(s20),
            "sma50": _num(s50),
        }
        for ts, c, s20, s50 in zip(
            close.index, close.values, sma20.values, sma50.values, strict=False
        )
    ]


def _serialize_report(report: Any) -> dict[str, Any]:
    """Serialize AnalysisReport to JSON-safe dict."""
    from ..pipeline import AnalysisReport

    if not isinstance(report, AnalysisReport):
        raise TypeError(f"Expected AnalysisReport, got {type(report)}")

    # Serialize assets
    assets = {}
    for ticker, analysis in report.assets.items():
        asset_dict = {
            "ticker": ticker,
            "metrics": analysis.metrics.to_payload(),
            "history": _serialize_history(analysis.history),
        }
        if analysis.commentary:
            asset_dict["commentary"] = {
                "provider": analysis.commentary.provider,
                "model": analysis.commentary.model,
                "summary": analysis.commentary.summary,
                "trend_explanation": analysis.commentary.trend_explanation,
                "risk_analysis": analysis.commentary.risk_analysis,
                "key_signals": analysis.commentary.key_signals,
                "compliance_flags": analysis.commentary.compliance_flags,
            }
        if analysis.backtest:
            asset_dict["backtest"] = analysis.backtest.to_dict()
        assets[ticker] = asset_dict

    # Serialize comparison. RankingEntry carries volatility and reward/risk;
    # Sharpe lives in the per-asset performance metrics, so join it in here.
    comparison = []
    if report.comparison and report.comparison.entries:
        for entry in report.comparison.entries:
            asset_metrics = assets.get(entry.ticker, {}).get("metrics", {})
            sharpe = (asset_metrics.get("performance") or {}).get("sharpe")
            comparison.append(
                {
                    "ticker": entry.ticker,
                    "return_pct": entry.return_pct,
                    "volatility_pct": entry.annualized_volatility_pct,
                    "sharpe": sharpe,
                    "reward_risk_ratio": entry.reward_risk_ratio,
                    "trend": entry.trend,
                    "rank": entry.rank,
                }
            )

    # Serialize alerts
    alerts = [
        {
            "severity": alert.severity,
            "message": alert.message,
        }
        for alert in report.alerts
    ]

    # Serialize portfolio (correlation, allocations, efficient frontier).
    # Frontier points come back as annualised fractions — convert to percent so
    # they are directly comparable with the per-asset metrics.
    portfolio = None
    if report.portfolio is not None:
        portfolio = report.portfolio.to_dict()
        portfolio["frontier"] = [
            {
                "return_pct": round(p["return"] * 100.0, 2),
                "volatility_pct": round(p["volatility"] * 100.0, 2),
            }
            for p in portfolio.get("frontier", [])
        ]

    # Benchmark closes (IMOEX / SPY) for the relative-performance overlay.
    benchmark = None
    if report.benchmark_ticker and report.benchmark_close is not None:
        close = report.benchmark_close.iloc[-1500:]
        benchmark = {
            "ticker": report.benchmark_ticker,
            "history": [
                {"date": ts.strftime("%Y-%m-%d"), "close": round(float(v), 4)}
                for ts, v in close.items()
                if v == v  # drop NaN
            ],
        }

    return {
        "generated_at": report.generated_at,
        "ai_provider": report.ai_provider,
        "ai_model": report.ai_model,
        "assets": assets,
        "comparison": comparison,
        "portfolio": portfolio,
        "benchmark": benchmark,
        "alerts": alerts,
        "failures": report.failures,
    }


# Create app instance for direct import
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
