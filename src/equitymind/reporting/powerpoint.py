"""PowerPoint (.pptx) deck export.

Turns an :class:`~equitymind.pipeline.AnalysisReport` into a presentation-ready
16:9 deck — the "подготовка презентационных материалов" workflow — with a title
slide, a cross-asset ranking table, a portfolio-allocation slide, one slide per
instrument (price chart + key metrics + AI commentary), and a closing compliance
disclaimer.

Charts are rendered to a temporary directory, embedded into the deck, and the
temp files are cleaned up once the presentation is saved, so the .pptx is fully
self-contained.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.presentation import Presentation as PresentationObj  # the class, for typing
from pptx.util import Inches, Pt

from ..ai.prompts import DISCLAIMER
from ..logging_config import get_logger
from . import charts

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from ..pipeline import AnalysisReport, AssetAnalysis

logger = get_logger(__name__)

_ACCENT = RGBColor(0x1F, 0x4E, 0x78)
_HEADER_TEXT = RGBColor(0xFF, 0xFF, 0xFF)
_SLIDE_W = Inches(13.333)
_SLIDE_H = Inches(7.5)


def _fmt_pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _fmt_ratio(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


class PowerPointGenerator:
    """Render :class:`AnalysisReport` objects to .pptx decks."""

    def __init__(self, output_dir: str | Path = "reports") -> None:
        self.output_dir = Path(output_dir)

    # ------------------------------------------------------------------ public
    def write_deck(
        self,
        report: AnalysisReport,
        *,
        filename: str | None = None,
        include_charts: bool = True,
    ) -> Path:
        """Build and persist the deck; returns the .pptx path."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_path = self.output_dir / (filename or f"market_intelligence_{stamp}.pptx")
        with tempfile.TemporaryDirectory() as tmp:
            chart_dir = Path(tmp) if include_charts else None
            prs = self.build_presentation(report, chart_dir=chart_dir)
            prs.save(str(out_path))  # images are embedded before the temp dir is cleaned
        logger.info("PowerPoint deck written to %s", out_path)
        return out_path

    def build_presentation(
        self, report: AnalysisReport, *, chart_dir: Path | None = None
    ) -> PresentationObj:
        """Assemble the deck in memory. If ``chart_dir`` is set, embed charts."""
        prs = Presentation()
        prs.slide_width = _SLIDE_W
        prs.slide_height = _SLIDE_H
        self._title_slide(prs, report)
        self._ranking_slide(prs, report)
        if report.portfolio is not None:
            self._portfolio_slide(prs, report)
        for analysis in report.assets.values():
            self._asset_slide(prs, analysis, chart_dir)
        self._disclaimer_slide(prs)
        return prs

    # ------------------------------------------------------------------ slides
    def _title_slide(self, prs: PresentationObj, report: AnalysisReport) -> None:
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        self._add_text(
            slide,
            "EquityMind",
            Inches(0.9),
            Inches(2.3),
            Inches(11.5),
            Inches(1.2),
            size=44,
            bold=True,
            color=_ACCENT,
        )
        self._add_text(
            slide,
            "Market Intelligence Report",
            Inches(0.9),
            Inches(3.4),
            Inches(11.5),
            Inches(0.8),
            size=26,
            color=RGBColor(0x40, 0x40, 0x40),
        )
        self._add_text(
            slide,
            f"Generated {report.generated_at}   ·   "
            f"AI: {report.ai_provider} ({report.ai_model})   ·   "
            f"{len(report.assets)} instruments",
            Inches(0.9),
            Inches(4.4),
            Inches(11.5),
            Inches(0.6),
            size=14,
            color=RGBColor(0x80, 0x80, 0x80),
        )

    def _ranking_slide(self, prs: PresentationObj, report: AnalysisReport) -> None:
        comp = report.comparison
        if comp is None or not comp.entries:
            return
        slide = self._content_slide(prs, "Cross-asset ranking")
        headers = ["Rank", "Ticker", "Return", "Ann. Vol", "Risk", "R/R", "Trend"]
        rows = [
            [
                str(e.rank),
                e.ticker,
                _fmt_pct(e.return_pct),
                _fmt_pct(e.annualized_volatility_pct),
                "n/a" if e.risk_score is None else f"{e.risk_score:.0f}",
                _fmt_ratio(e.reward_risk_ratio),
                e.trend,
            ]
            for e in comp.entries
        ]
        self._add_table(slide, headers, rows, top=Inches(1.4))

    def _portfolio_slide(self, prs: PresentationObj, report: AnalysisReport) -> None:
        p = report.portfolio
        assert p is not None
        slide = self._content_slide(prs, "Portfolio analytics")
        self._add_text(
            slide,
            f"{len(p.tickers)} instruments · {p.observations} obs · "
            f"avg correlation {p.average_correlation:+.2f} · rf {p.risk_free_rate * 100:.1f}%",
            Inches(0.6),
            Inches(1.2),
            Inches(12),
            Inches(0.4),
            size=13,
            color=RGBColor(0x80, 0x80, 0x80),
        )
        headers = ["Allocation", "Exp. return", "Volatility", "Sharpe"]
        rows = [
            [
                a.label,
                _fmt_pct(a.expected_return_pct),
                _fmt_pct(a.volatility_pct),
                _fmt_ratio(a.sharpe),
            ]
            for a in p.allocations.values()
        ]
        self._add_table(slide, headers, rows, top=Inches(1.8))

    def _asset_slide(
        self, prs: PresentationObj, analysis: AssetAnalysis, chart_dir: Path | None
    ) -> None:
        m = analysis.metrics
        p = m.to_payload()
        slide = self._content_slide(prs, f"{m.ticker} — {m.name}")

        # Left: price chart (if charts are enabled and rendering succeeds).
        if chart_dir is not None:
            try:
                fig = charts.price_chart(analysis.history)
                png = charts.save_figure(fig, chart_dir / f"{m.ticker}_price.png")
                slide.shapes.add_picture(str(png), Inches(0.5), Inches(1.5), width=Inches(7.2))
            except Exception as exc:  # pragma: no cover - chart is optional
                logger.warning("Chart failed for %s: %s", m.ticker, exc)

        # Right: key metrics as bullets.
        perf, tail = p.get("performance", {}), p.get("tail_risk", {})
        risk, vol = p["risk"], p["volatility"]
        bench = p.get("benchmark")
        bullets = [
            f"Trend: {p['trend']['classification']}   ·   Risk {risk.get('score')}/100 ({risk.get('band')})",
            f"Cumulative {_fmt_pct(p['cumulative_return_pct'])}   ·   CAGR {_fmt_pct(perf.get('annualized_return_pct'))}",
            f"Ann. vol {_fmt_pct(vol.get('annualized_pct'))}   ·   Max DD {_fmt_pct(risk.get('max_drawdown_pct'))}",
            f"Sharpe {_fmt_ratio(perf.get('sharpe'))}   ·   Sortino {_fmt_ratio(perf.get('sortino'))}   ·   Calmar {_fmt_ratio(perf.get('calmar'))}",
            f"VaR {tail.get('confidence_pct', 95):g}% {_fmt_pct(tail.get('historical_var_pct'))}   ·   CVaR {_fmt_pct(tail.get('historical_cvar_pct'))}",
        ]
        if bench:
            bullets.append(
                f"vs {bench.get('benchmark')}: β {_fmt_ratio(bench.get('beta'))} · "
                f"α {_fmt_pct(bench.get('alpha_annual_pct'))} · ρ {_fmt_ratio(bench.get('correlation'))}"
            )
        self._add_bullets(slide, bullets, Inches(8.0), Inches(1.5), Inches(4.9), Inches(2.6))

        commentary = analysis.commentary
        if commentary is not None:
            self._add_text(
                slide,
                "AI analyst summary",
                Inches(8.0),
                Inches(4.2),
                Inches(4.9),
                Inches(0.4),
                size=13,
                bold=True,
                color=_ACCENT,
            )
            self._add_text(
                slide,
                commentary.summary,
                Inches(8.0),
                Inches(4.6),
                Inches(4.9),
                Inches(2.4),
                size=11,
                color=RGBColor(0x40, 0x40, 0x40),
            )

    def _disclaimer_slide(self, prs: PresentationObj) -> None:
        slide = self._content_slide(prs, "Disclaimer")
        self._add_text(
            slide,
            f"{DISCLAIMER}\n\nFigures are derived from historical market data and are "
            "backward-looking. Past behaviour does not guarantee future results.",
            Inches(0.8),
            Inches(2.0),
            Inches(11.5),
            Inches(3.0),
            size=16,
            color=RGBColor(0x40, 0x40, 0x40),
        )

    # ------------------------------------------------------------------ helpers
    def _content_slide(self, prs: PresentationObj, title: str):
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
        self._add_text(
            slide,
            title,
            Inches(0.5),
            Inches(0.3),
            Inches(12.3),
            Inches(0.9),
            size=28,
            bold=True,
            color=_ACCENT,
        )
        return slide

    @staticmethod
    def _add_text(slide, text, left, top, width, height, *, size=18, bold=False, color=None):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        para = tf.paragraphs[0]
        run = para.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        if color is not None:
            run.font.color.rgb = color
        return box

    @staticmethod
    def _add_bullets(slide, bullets: list[str], left, top, width, height):
        box = slide.shapes.add_textbox(left, top, width, height)
        tf = box.text_frame
        tf.word_wrap = True
        for i, text in enumerate(bullets):
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = f"• {text}"
            para.font.size = Pt(12)
            para.space_after = Pt(6)

    def _add_table(self, slide, headers: list[str], rows: list[list[str]], *, top) -> None:
        n_rows, n_cols = len(rows) + 1, len(headers)
        left, width = Inches(0.5), Inches(12.3)
        height = Inches(0.4) * n_rows
        table = slide.shapes.add_table(n_rows, n_cols, left, top, width, height).table
        for c, h in enumerate(headers):
            cell = table.cell(0, c)
            cell.text = h
            para = cell.text_frame.paragraphs[0]
            para.font.bold = True
            para.font.size = Pt(12)
            para.font.color.rgb = _HEADER_TEXT
            cell.fill.solid()
            cell.fill.fore_color.rgb = _ACCENT
        for r, row in enumerate(rows, start=1):
            for c, value in enumerate(row):
                cell = table.cell(r, c)
                cell.text = str(value)
                cell.text_frame.paragraphs[0].font.size = Pt(11)
