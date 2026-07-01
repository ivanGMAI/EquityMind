"""Markdown report generation.

Turns a completed :class:`~equitymind.pipeline.AnalysisReport` into a structured
markdown desk note: an executive ranking table, volatility alerts, then a
per-instrument section with the key metrics, the AI commentary, an optional
price chart, and an optional trend backtest — closing with a compliance
disclaimer.

Markdown (not PDF) is the primary format: it renders everywhere, diffs cleanly,
and converts to PDF/HTML with any standard tool. Charts are written as PNG files
and linked relatively so the report is self-contained in its output directory.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from ..ai.prompts import DISCLAIMER
from ..logging_config import get_logger
from . import charts

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from ..pipeline import AnalysisReport, AssetAnalysis

logger = get_logger(__name__)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _fmt_num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.2f}"


def _fmt_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_loss(value: float | None) -> str:
    """Format a VaR/CVaR loss magnitude (stored positive) without a +/- sign."""
    return "n/a" if value is None else f"{value:.2f}%"


class ReportGenerator:
    """Render :class:`AnalysisReport` objects to markdown files."""

    def __init__(self, output_dir: str | Path = "reports") -> None:
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------ public
    def write_report(
        self,
        report: AnalysisReport,
        *,
        filename: str | None = None,
        include_charts: bool = True,
    ) -> Path:
        """Render and persist the report; returns the markdown file path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        chart_paths: dict[str, str] = {}

        if include_charts:
            chart_dir = self.output_dir / f"charts_{stamp}"
            chart_paths = self._render_charts(report, chart_dir)

        markdown = self.generate_markdown(report, chart_paths=chart_paths)
        out_path = self.output_dir / (filename or f"market_intelligence_{stamp}.md")
        out_path.write_text(markdown, encoding="utf-8")
        logger.info("Report written to %s", out_path)
        return out_path

    def generate_markdown(
        self, report: AnalysisReport, *, chart_paths: dict[str, str] | None = None
    ) -> str:
        """Render the report to a markdown string (no file I/O)."""
        chart_paths = chart_paths or {}
        parts: list[str] = []
        parts.append(self._header(report))
        parts.append(self._ranking_section(report))
        parts.append(self._portfolio_section(report))
        parts.append(self._alerts_section(report))
        for ticker, analysis in report.assets.items():
            parts.append(self._asset_section(analysis, chart_paths.get(ticker)))
        if report.failures:
            parts.append(self._failures_section(report.failures))
        parts.append(self._footer())
        return "\n\n".join(p for p in parts if p)

    # ------------------------------------------------------------------ charts
    def _render_charts(self, report: AnalysisReport, chart_dir: Path) -> dict[str, str]:
        paths: dict[str, str] = {}
        for ticker, analysis in report.assets.items():
            try:
                fig = charts.price_chart(analysis.history)
                png = charts.save_figure(fig, chart_dir / f"{ticker}_price.png")
                # store path relative to the markdown file's directory
                paths[ticker] = str(png.relative_to(self.output_dir))
            except Exception as exc:  # pragma: no cover - chart is optional
                logger.warning("Chart failed for %s: %s", ticker, exc)
        if len(report.assets) > 1:
            try:
                histories = {t: a.history for t, a in report.assets.items()}
                fig = charts.comparison_chart(histories)
                png = charts.save_figure(fig, chart_dir / "comparison.png")
                paths["__comparison__"] = str(png.relative_to(self.output_dir))
            except Exception as exc:  # pragma: no cover
                logger.warning("Comparison chart failed: %s", exc)
        return paths

    # ------------------------------------------------------------------ sections
    @staticmethod
    def _header(report: AnalysisReport) -> str:
        return (
            "# EquityMind — Market Intelligence Report\n\n"
            f"**Generated:** {report.generated_at}  \n"
            f"**Instruments analysed:** {len(report.assets)}  \n"
            f"**AI provider:** {report.ai_provider} ({report.ai_model})"
        )

    @staticmethod
    def _ranking_section(report: AnalysisReport) -> str:
        comp = report.comparison
        if comp is None or not comp.entries:
            return ""
        lines = [
            "## Cross-Asset Ranking",
            "",
            f"Ranked by reward-to-risk ratio (return / annualised volatility, "
            f"basis: {comp.return_basis}).",
            "",
            "| Rank | Ticker | Return | Ann. Vol | Risk (0-100) | Reward/Risk | Trend |",
            "| ---: | :----- | -----: | -------: | -----------: | ----------: | :---- |",
        ]
        for e in comp.entries:
            lines.append(
                f"| {e.rank} | {e.ticker} | {_fmt_pct(e.return_pct)} | "
                f"{_fmt_pct(e.annualized_volatility_pct)} | "
                f"{e.risk_score if e.risk_score is not None else 'n/a'} | "
                f"{e.reward_risk_ratio if e.reward_risk_ratio is not None else 'n/a'} | "
                f"{e.trend} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _portfolio_section(report: AnalysisReport) -> str:
        p = report.portfolio
        if p is None or not p.allocations:
            return ""
        tickers = p.tickers
        lines = [
            "## Portfolio Analytics",
            "",
            f"Cross-asset view over {len(tickers)} instruments "
            f"({p.observations} overlapping observations). Average pairwise "
            f"correlation: **{p.average_correlation:+.2f}**. Figures are annualised; "
            f"risk-free rate {p.risk_free_rate * 100:.1f}%.",
            "",
            "### Correlation matrix",
            "",
            "| | " + " | ".join(tickers) + " |",
            "| :-- " + "| --: " * len(tickers) + "|",
        ]
        for row in tickers:
            cells = " | ".join(f"{p.correlation[row][col]:+.2f}" for col in tickers)
            lines.append(f"| **{row}** | {cells} |")

        lines += [
            "",
            "### Reference allocations",
            "",
            "| Allocation | Exp. return | Volatility | Sharpe | Weights |",
            "| :--------- | ----------: | ---------: | -----: | :------ |",
        ]
        for alloc in p.allocations.values():
            weights = ", ".join(f"{t} {w:.0f}%" for t, w in alloc.weights.items())
            lines.append(
                f"| {alloc.label} | {_fmt_pct(alloc.expected_return_pct)} | "
                f"{_fmt_pct(alloc.volatility_pct)} | {_fmt_ratio(alloc.sharpe)} | {weights} |"
            )
        lines += [
            "",
            "> Minimum-variance and maximum-Sharpe (tangency) weights are the "
            "unconstrained mean-variance solutions and may imply short positions; "
            "risk-parity weights are long-only. Expected returns use historical "
            "sample means and are not forecasts.",
        ]
        return "\n".join(lines)

    @staticmethod
    def _alerts_section(report: AnalysisReport) -> str:
        if not report.alerts:
            return "## Alerts\n\nNo volatility spikes detected in the current window."
        lines = ["## Alerts", ""]
        for a in report.alerts:
            icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}.get(a.severity, "•")
            lines.append(f"- {icon} **{a.severity.upper()}** — {a.message}")
        return "\n".join(lines)

    def _asset_section(self, analysis: AssetAnalysis, chart_path: str | None) -> str:
        m = analysis.metrics
        payload = m.to_payload()
        rets = payload["returns_pct"]
        vol = payload["volatility"]
        risk = payload["risk"]
        trend = payload["trend"]
        perf = payload.get("performance", {})
        tail = payload.get("tail_risk", {})
        bench = payload.get("benchmark")

        lines = [
            f"## {m.ticker} — {m.name}",
            "",
            f"*{m.asset_class.title()} · {payload['window']['start']} → "
            f"{payload['window']['end']} · {payload['window']['bars']} bars · "
            f"last {m.currency} {_fmt_num(m.last_price)}*",
            "",
            "| Metric | Value |",
            "| :----- | ----: |",
            f"| 1-day return | {_fmt_pct(rets.get('1d'))} |",
            f"| 7-day return | {_fmt_pct(rets.get('7d'))} |",
            f"| 30-day return | {_fmt_pct(rets.get('30d'))} |",
            f"| Cumulative return | {_fmt_pct(payload['cumulative_return_pct'])} |",
            f"| Annualised return (CAGR) | {_fmt_pct(perf.get('annualized_return_pct'))} |",
            f"| Annualised volatility | {_fmt_pct(vol.get('annualized_pct'))} |",
            f"| Sharpe ratio | {_fmt_ratio(perf.get('sharpe'))} |",
            f"| Sortino ratio | {_fmt_ratio(perf.get('sortino'))} |",
            f"| Calmar ratio | {_fmt_ratio(perf.get('calmar'))} |",
            f"| Max drawdown | {_fmt_pct(risk.get('max_drawdown_pct'))} |",
            f"| VaR {tail.get('confidence_pct', 95)}% ({tail.get('horizon_days', 1)}d, hist/param) | "
            f"{_fmt_loss(tail.get('historical_var_pct'))} / {_fmt_loss(tail.get('parametric_var_pct'))} |",
            f"| CVaR {tail.get('confidence_pct', 95)}% ({tail.get('horizon_days', 1)}d, hist/param) | "
            f"{_fmt_loss(tail.get('historical_cvar_pct'))} / {_fmt_loss(tail.get('parametric_cvar_pct'))} |",
            f"| Trend | {trend.get('classification')} |",
            f"| Risk score | {risk.get('score')}/100 ({risk.get('band')}) |",
        ]
        if bench:
            lines.append(
                f"| vs {bench.get('benchmark')} (β / α / ρ) | "
                f"{_fmt_ratio(bench.get('beta'))} / {_fmt_pct(bench.get('alpha_annual_pct'))} / "
                f"{_fmt_ratio(bench.get('correlation'))} |"
            )
        lines.append("")

        if analysis.fundamentals is not None:
            lines += self._fundamentals_block(analysis.fundamentals)

        if chart_path:
            lines += [f"![{m.ticker} price chart]({chart_path})", ""]

        commentary = analysis.commentary
        if commentary is not None:
            lines += [
                "### AI Analyst Commentary",
                "",
                f"*Source: {commentary.provider} ({commentary.model})*",
                "",
                "**Summary**",
                "",
                commentary.summary,
                "",
                "**Trend explanation**",
                "",
                commentary.trend_explanation,
                "",
                "**Risk analysis**",
                "",
                commentary.risk_analysis,
                "",
                "**Key signals**",
                "",
            ]
            lines += [f"- {s}" for s in commentary.key_signals]
            if commentary.compliance_flags:
                lines += [
                    "",
                    f"> ⚠️ Compliance flags raised on generation: "
                    f"{', '.join(commentary.compliance_flags)}",
                ]

        bt = analysis.backtest
        if bt is not None:
            lines += [
                "",
                "### Trend Backtest",
                "",
                f"*{bt.strategy}*",
                "",
                "| Metric | Value |",
                "| :----- | ----: |",
                f"| Strategy return | {_fmt_pct(bt.total_return_pct)} |",
                f"| Buy & hold return | {_fmt_pct(bt.buy_and_hold_return_pct)} |",
                f"| Excess return | {_fmt_pct(bt.excess_return_pct)} |",
                f"| Trades | {bt.n_trades} |",
                f"| Win rate | {_fmt_pct(bt.win_rate_pct) if bt.win_rate_pct is not None else 'n/a'} |",
                f"| Time in market | {bt.exposure_pct:.1f}% |",
                f"| Max drawdown | {_fmt_pct(bt.max_drawdown_pct)} |",
                f"| Sharpe-like | {bt.sharpe_like if bt.sharpe_like is not None else 'n/a'} |",
                "",
                "> " + " ".join(bt.caveats),
            ]

        return "\n".join(lines)

    @staticmethod
    def _fundamentals_block(fundamentals) -> list[str]:
        f = fundamentals.to_payload()
        mc = f.get("market_cap")
        mc_txt = "n/a" if mc is None else f"{mc:,.0f} {f.get('currency') or ''}".strip()
        return [
            "**Fundamentals**",
            "",
            "| Field | Value | Field | Value |",
            "| :---- | ----: | :---- | ----: |",
            f"| Sector | {f.get('sector') or 'n/a'} | Industry | {f.get('industry') or 'n/a'} |",
            f"| Market cap | {mc_txt} | P/E (trail) | {_fmt_ratio(f.get('trailing_pe'))} |",
            f"| P/E (fwd) | {_fmt_ratio(f.get('forward_pe'))} | P/B | {_fmt_ratio(f.get('price_to_book'))} |",
            f"| EPS | {_fmt_ratio(f.get('eps'))} | Dividend yield | {_fmt_pct(f.get('dividend_yield_pct'))} |",
            f"| ROE | {_fmt_pct(f.get('return_on_equity_pct'))} | Profit margin | {_fmt_pct(f.get('profit_margin_pct'))} |",
            "",
        ]

    @staticmethod
    def _failures_section(failures: dict[str, str]) -> str:
        lines = ["## Data Issues", ""]
        for ticker, reason in failures.items():
            lines.append(f"- **{ticker}**: {reason}")
        return "\n".join(lines)

    @staticmethod
    def _footer() -> str:
        return (
            "---\n\n"
            f"> _{DISCLAIMER}_\n\n"
            "> Figures are derived from historical market data and are "
            "backward-looking. Past behaviour does not guarantee future results."
        )
