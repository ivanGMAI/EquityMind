"""Analytical tools the AI agent can call (function calling).

Each :class:`Tool` wraps a *real* capability of the system — querying the current
analysis (metrics, ranking, portfolio), pricing derivatives, or scoring news
sentiment — behind a JSON schema the model can invoke. This is what turns the AI
from a text generator into an agent that *reasons on the actual numbers*: it
decides which tool to call, the tool runs the genuine calculation, and the result
is fed back for the next step.

Every tool is a pure function of its arguments plus the (in-memory) analysis
context, so the whole tool layer is deterministic and testable offline.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..derivatives import black_scholes as bs
from ..derivatives import forwards
from ..news import analyze_headlines

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from ..pipeline import AnalysisReport


@dataclass(slots=True)
class Tool:
    """A single callable capability exposed to the model."""

    name: str
    description: str
    input_schema: dict
    func: Callable[..., Any]

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    """A named collection of tools with schema export and safe execution."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def execute(self, name: str, arguments: dict) -> dict:
        """Run a tool by name; errors are captured and returned, never raised."""
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"unknown tool: {name}"}
        try:
            result = tool.func(**(arguments or {}))
        except Exception as exc:  # surfaced back to the model, not fatal
            return {"error": f"{type(exc).__name__}: {exc}"}
        return result if isinstance(result, dict) else {"result": result}


# ---------------------------------------------------------------------------
# Tool implementations (bound to an optional analysis context)
# ---------------------------------------------------------------------------
def _require_report(report: AnalysisReport | None) -> dict | None:
    if report is None or not report.assets:
        return {"error": "no analysis context available; run an analysis first"}
    return None


def build_tools(report: AnalysisReport | None = None) -> ToolRegistry:
    """Assemble the tool registry, binding report-query tools to ``report``."""

    def list_instruments() -> dict:
        err = _require_report(report)
        if err:
            return err
        assert report is not None
        return {
            "instruments": [
                {
                    "ticker": a.metrics.ticker,
                    "name": a.metrics.name,
                    "asset_class": a.metrics.asset_class,
                }
                for a in report.assets.values()
            ]
        }

    def get_metrics(ticker: str) -> dict:
        err = _require_report(report)
        if err:
            return err
        assert report is not None
        analysis = report.assets.get(ticker.strip().upper())
        if analysis is None:
            return {"error": f"{ticker} is not in the current analysis"}
        return analysis.metrics.to_payload()

    def get_ranking() -> dict:
        err = _require_report(report)
        if err:
            return err
        assert report is not None
        if report.comparison is None:
            return {"error": "no ranking available"}
        return report.comparison.to_payload()

    def get_portfolio() -> dict:
        err = _require_report(report)
        if err:
            return err
        assert report is not None
        if report.portfolio is None:
            return {"error": "no portfolio analytics available"}
        return report.portfolio.to_payload()

    def price_option(
        spot: float,
        strike: float,
        years: float,
        rate: float,
        volatility: float,
        option_type: str = "call",
        dividend_yield: float = 0.0,
    ) -> dict:
        quote = bs.price_and_greeks(
            spot, strike, years, rate, volatility, option_type=option_type, q=dividend_yield
        )
        return quote.to_dict()

    def implied_volatility(
        price: float,
        spot: float,
        strike: float,
        years: float,
        rate: float,
        option_type: str = "call",
        dividend_yield: float = 0.0,
    ) -> dict:
        iv = bs.implied_volatility(
            price, spot, strike, years, rate, option_type=option_type, q=dividend_yield
        )
        return {
            "implied_volatility": iv,
            "implied_volatility_pct": None if iv is None else round(iv * 100, 2),
        }

    def forward_price(spot: float, years: float, rate: float, income_yield: float = 0.0) -> dict:
        return forwards.analyze_forward(spot, years, rate, income_yield=income_yield).to_dict()

    def news_sentiment(headlines: list[str]) -> dict:
        return analyze_headlines(list(headlines)).to_dict()

    return ToolRegistry(
        [
            Tool(
                "list_instruments",
                "List the instruments in the current analysis (ticker, name, asset class).",
                {"type": "object", "properties": {}, "additionalProperties": False},
                list_instruments,
            ),
            Tool(
                "get_metrics",
                "Get the full quantitative metrics for one instrument: returns, volatility, "
                "Sharpe/Sortino/Calmar, VaR/CVaR, drawdown, trend, risk score and benchmark beta/alpha.",
                {
                    "type": "object",
                    "properties": {"ticker": {"type": "string"}},
                    "required": ["ticker"],
                },
                get_metrics,
            ),
            Tool(
                "get_ranking",
                "Get the cross-asset ranking by reward-to-risk ratio.",
                {"type": "object", "properties": {}, "additionalProperties": False},
                get_ranking,
            ),
            Tool(
                "get_portfolio",
                "Get portfolio analytics: correlation matrix and reference allocations "
                "(equal-weight, minimum-variance, maximum-Sharpe, risk-parity).",
                {"type": "object", "properties": {}, "additionalProperties": False},
                get_portfolio,
            ),
            Tool(
                "price_option",
                "Price a European option (Black-Scholes) and return its Greeks.",
                {
                    "type": "object",
                    "properties": {
                        "spot": {"type": "number"},
                        "strike": {"type": "number"},
                        "years": {"type": "number", "description": "time to expiry in years"},
                        "rate": {"type": "number", "description": "risk-free rate, e.g. 0.05"},
                        "volatility": {
                            "type": "number",
                            "description": "annualised vol, e.g. 0.25",
                        },
                        "option_type": {"type": "string", "enum": ["call", "put"]},
                        "dividend_yield": {"type": "number"},
                    },
                    "required": ["spot", "strike", "years", "rate", "volatility"],
                },
                price_option,
            ),
            Tool(
                "implied_volatility",
                "Solve for the Black-Scholes implied volatility given an option's market price.",
                {
                    "type": "object",
                    "properties": {
                        "price": {"type": "number"},
                        "spot": {"type": "number"},
                        "strike": {"type": "number"},
                        "years": {"type": "number"},
                        "rate": {"type": "number"},
                        "option_type": {"type": "string", "enum": ["call", "put"]},
                        "dividend_yield": {"type": "number"},
                    },
                    "required": ["price", "spot", "strike", "years", "rate"],
                },
                implied_volatility,
            ),
            Tool(
                "forward_price",
                "Compute the fair forward/futures price under cost-of-carry, with basis diagnostics.",
                {
                    "type": "object",
                    "properties": {
                        "spot": {"type": "number"},
                        "years": {"type": "number"},
                        "rate": {"type": "number"},
                        "income_yield": {"type": "number"},
                    },
                    "required": ["spot", "years", "rate"],
                },
                forward_price,
            ),
            Tool(
                "news_sentiment",
                "Score the sentiment (bullish/bearish) of a list of news headlines.",
                {
                    "type": "object",
                    "properties": {"headlines": {"type": "array", "items": {"type": "string"}}},
                    "required": ["headlines"],
                },
                news_sentiment,
            ),
        ]
    )
