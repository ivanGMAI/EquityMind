"""LLM provider abstraction for the market analyst.

Two providers implement a single interface so the analyst is agnostic to the
backend:

* :class:`AnthropicProvider` — calls Claude (default ``claude-opus-4-8``) with
  structured outputs so the response is guaranteed to match the commentary
  schema.
* :class:`MockProvider` — a deterministic, offline, rule-based generator that
  produces professional-sounding (advice-free) commentary directly from the
  metrics. It lets the whole pipeline run with no API key, in tests, or when
  the network is unavailable.

:func:`build_provider` resolves which one to use from the environment.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a valid commentary payload."""


class LLMProvider(ABC):
    """Interface for commentary generators."""

    #: Stable identifier surfaced in output metadata.
    name: str = "abstract"
    model: str = ""

    @abstractmethod
    def generate_commentary(
        self,
        payload: dict[str, Any],
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Return a dict with keys: summary, trend_explanation, risk_analysis,
        key_signals.

        Args:
            payload: The raw metrics payload (used by rule-based providers).
            system: System prompt (used by LLM providers).
            user: Rendered user prompt (used by LLM providers).
            schema: JSON schema the output must satisfy.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic / Claude
# ---------------------------------------------------------------------------
class AnthropicProvider(LLMProvider):
    """Claude-backed provider using structured outputs.

    Uses adaptive thinking with a configurable effort level for analytical
    quality, and ``output_config.format`` to guarantee schema-valid JSON.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        *,
        max_tokens: int = 2000,
        effort: str = "medium",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        # Leave head-room above the JSON so adaptive thinking never truncates
        # the structured answer; well under the non-streaming timeout budget.
        self.max_tokens = max(max_tokens, 4096)
        self.effort = effort
        self._api_key = api_key
        self._client: Any = None  # lazily constructed

    def _client_or_raise(self):
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ProviderError("anthropic SDK not installed") from exc
        # A bare client resolves ANTHROPIC_API_KEY (or an `ant auth login`
        # profile) from the environment; only pass a key if injected explicitly.
        self._client = (
            anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        )
        return self._client

    def generate_commentary(
        self,
        payload: dict[str, Any],
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        client = self._client_or_raise()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                thinking={"type": "adaptive"},
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # network / API errors
            raise ProviderError(f"Anthropic request failed: {exc}") from exc

        if getattr(response, "stop_reason", None) == "refusal":
            raise ProviderError("Model refused to generate commentary")

        # With structured outputs the first text block is schema-valid JSON;
        # thinking blocks (if any) precede it, so filter by type.
        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            None,
        )
        if not text:
            raise ProviderError("Empty response from model")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Model returned non-JSON output: {exc}") from exc

        logger.info("Generated commentary for %s via %s", payload.get("ticker"), self.model)
        return data


# ---------------------------------------------------------------------------
# Offline rule-based mock
# ---------------------------------------------------------------------------
class MockProvider(LLMProvider):
    """Deterministic, offline commentary generator.

    Produces grounded, advice-free prose straight from the metrics so the system
    is fully functional without any API key. Not a substitute for the LLM's
    nuance, but useful for demos, tests and air-gapped environments.
    """

    name = "mock"
    model = "rule-based"

    def generate_commentary(
        self,
        payload: dict[str, Any],
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        ticker = payload.get("ticker", "The instrument")
        name = payload.get("name") or ticker
        returns = payload.get("returns_pct", {})
        cum = payload.get("cumulative_return_pct")
        vol = payload.get("volatility", {})
        trend = payload.get("trend", {})
        risk = payload.get("risk", {})
        window = payload.get("window", {})
        indicators = payload.get("indicators", {})
        perf = payload.get("performance", {})
        tail = payload.get("tail_risk", {})
        bench = payload.get("benchmark")

        r1 = returns.get("1d")
        r7 = returns.get("7d")
        r30 = returns.get("30d")
        ann_vol = vol.get("annualized_pct")
        classification = trend.get("classification", "undetermined")
        score = risk.get("score")
        band = risk.get("band")
        mdd = risk.get("max_drawdown_pct")

        summary = (
            f"{name} ({ticker}) closed the window at "
            f"{payload.get('currency', '')} {payload.get('last_price')}, "
            f"a {self._fmt(cum)} move over {window.get('bars', 'the')} bars "
            f"({window.get('start')} to {window.get('end')}). "
            f"Shorter-horizon returns stand at {self._fmt(r1)} (1d), "
            f"{self._fmt(r7)} (7d) and {self._fmt(r30)} (30d)."
        )

        trend_explanation = (
            f"The trend model classifies {ticker} as {classification}. "
            + (trend.get("rationale") or "")
        ).strip()
        if trend.get("slow_ma_slope_pct") is not None:
            trend_explanation += (
                f" The slow moving average is sloping {self._fmt(trend.get('slow_ma_slope_pct'))} "
                "over its recent window."
            )

        sharpe = perf.get("sharpe")
        var_pct = tail.get("historical_var_pct")
        cvar_pct = tail.get("historical_cvar_pct")
        conf = tail.get("confidence_pct", 95)
        horizon = tail.get("horizon_days", 1)
        risk_analysis = (
            f"Annualised volatility is {self._fmt(ann_vol)} and the deepest "
            f"peak-to-trough drawdown in the window was {self._fmt(mdd)}. "
            f"On a risk-adjusted basis the Sharpe ratio is "
            f"{self._num(sharpe)} and the Sortino ratio {self._num(perf.get('sortino'))}. "
            f"Historical {conf:g}% {horizon}-day Value-at-Risk is {self._fmt(var_pct)} "
            f"with expected shortfall (CVaR) of {self._fmt(cvar_pct)}. "
            f"The composite risk score is {score}/100 ({band}). "
            "These are backward-looking, sample-dependent estimates; a short or "
            "unusually calm window can understate tail risk, and volatility "
            "clusters, so recent readings may not persist."
        )
        if bench:
            risk_analysis += (
                f" Relative to {bench.get('benchmark')}, beta is "
                f"{self._num(bench.get('beta'))} and the correlation of daily "
                f"returns is {self._num(bench.get('correlation'))}."
            )

        key_signals = []
        if classification != "undetermined":
            key_signals.append(f"Trend regime: {classification}.")
        if ann_vol is not None:
            key_signals.append(f"Annualised volatility {self._fmt(ann_vol)}.")
        rsi_key = next((k for k in indicators if k.startswith("rsi")), None)
        if rsi_key and indicators.get(rsi_key) is not None:
            rsi_val = indicators[rsi_key]
            zone = "overbought" if rsi_val >= 70 else "oversold" if rsi_val <= 30 else "neutral"
            key_signals.append(f"RSI at {rsi_val:.0f} ({zone}).")
        if score is not None:
            key_signals.append(f"Composite risk {score}/100 ({band}).")
        if sharpe is not None:
            key_signals.append(f"Sharpe ratio {self._num(sharpe)}.")
        if var_pct is not None:
            key_signals.append(f"Historical {conf:g}% VaR {self._fmt(var_pct)}.")
        if bench and bench.get("beta") is not None:
            key_signals.append(f"Beta to {bench.get('benchmark')} {self._num(bench.get('beta'))}.")
        if r30 is not None:
            key_signals.append(f"30-day return {self._fmt(r30)}.")

        return {
            "summary": summary,
            "trend_explanation": trend_explanation or "Trend undetermined from the sample.",
            "risk_analysis": risk_analysis,
            "key_signals": key_signals or ["Insufficient data for signal extraction."],
        }

    @staticmethod
    def _fmt(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:+.2f}%" if isinstance(value, (int, float)) else str(value)

    @staticmethod
    def _num(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:.2f}" if isinstance(value, (int, float)) else str(value)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
def build_provider(
    *,
    model: str = "claude-opus-4-8",
    max_tokens: int = 2000,
    effort: str = "medium",
    prefer: str | None = None,
) -> LLMProvider:
    """Resolve the provider to use.

    Resolution order:
        1. Explicit ``prefer`` argument or ``EQUITYMIND_LLM_PROVIDER`` env var
           (``"anthropic"`` / ``"mock"``).
        2. ``AnthropicProvider`` if an ``ANTHROPIC_API_KEY`` is present.
        3. ``MockProvider`` otherwise.
    """
    choice = (prefer or os.getenv("EQUITYMIND_LLM_PROVIDER") or "").strip().lower()

    if choice == "mock":
        logger.info("Using MockProvider (forced)")
        return MockProvider()
    if choice == "anthropic":
        logger.info("Using AnthropicProvider (forced): %s", model)
        return AnthropicProvider(model=model, max_tokens=max_tokens, effort=effort)

    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Using AnthropicProvider: %s", model)
        return AnthropicProvider(model=model, max_tokens=max_tokens, effort=effort)

    logger.warning(
        "ANTHROPIC_API_KEY not set — falling back to offline MockProvider. "
        "Set the key (or EQUITYMIND_LLM_PROVIDER=anthropic) for LLM commentary."
    )
    return MockProvider()
