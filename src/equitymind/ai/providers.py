"""LLM provider abstraction for the market analyst.

Three providers implement a single interface so the analyst is agnostic to the
backend:

* :class:`AnthropicProvider` — calls Claude (default ``claude-opus-4-8``) with
  structured outputs so the response is guaranteed to match the commentary
  schema.
* :class:`OpenRouterProvider` — same commentary through OpenRouter's
  OpenAI-compatible API, for ``sk-or-...`` keys.
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
from . import openrouter

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
# OpenRouter (OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------
class OpenRouterProvider(LLMProvider):
    """OpenRouter-backed provider for ``sk-or-...`` keys.

    Requests schema-constrained JSON via ``response_format``; models that
    reject or ignore it are handled by a single retry with the schema inlined
    into the prompt plus lenient JSON extraction.
    """

    name = "openrouter"

    def __init__(
        self,
        model: str | None = None,
        *,
        max_tokens: int = 900,
        api_key: str | None = None,
        timeout: float = 90.0,
    ) -> None:
        self.model = openrouter.resolve_model(model)
        # Keep the output budget modest: reasoning models spend tokens on hidden
        # reasoning, so a large budget balloons latency past the timeout. A few
        # hundred tokens is plenty for the short structured commentary.
        self.max_tokens = max(max_tokens, 256)
        self._api_key = api_key
        self._timeout = timeout

    def generate_commentary(
        self,
        payload: dict[str, Any],
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        # Schema is inlined into the prompt rather than sent as `response_format`:
        # reasoning models (e.g. GLM) return an EMPTY message when a strict
        # json_schema is combined with their hidden reasoning, so we ask for JSON
        # in words and extract it leniently. Reasoning is capped so a visible
        # answer is actually emitted instead of being all "thinking".
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "reasoning": {"max_tokens": 64},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"{user}\n\nReturn ONLY a JSON object matching this schema, "
                        f"with no surrounding prose:\n{json.dumps(schema)}"
                    ),
                },
            ],
        }
        try:
            data = openrouter.chat_completion(body, api_key=self._api_key, timeout=self._timeout)
        except openrouter.OpenRouterError as exc:
            raise ProviderError(f"OpenRouter request failed: {exc}") from exc

        text = openrouter.message_text(openrouter.first_message(data))
        if not text.strip():
            raise ProviderError("Empty response from model")
        result = self._extract_json(text)
        logger.info("Generated commentary for %s via %s", payload.get("ticker"), self.model)
        return result

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Parse JSON, tolerating markdown fences and surrounding prose."""
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.strip("`").strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
        try:
            return dict(json.loads(candidate))
        except json.JSONDecodeError:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start != -1 and end > start:
                try:
                    return dict(json.loads(candidate[start : end + 1]))
                except json.JSONDecodeError:
                    pass
            raise ProviderError(f"Model returned non-JSON output: {text[:200]!r}") from None


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
            f"{name} ({ticker}) завершил окно на отметке "
            f"{payload.get('currency', '')} {payload.get('last_price')}: "
            f"движение {self._fmt(cum)} за {window.get('bars', '—')} баров "
            f"({window.get('start')} — {window.get('end')}). "
            f"Доходности на коротких горизонтах: {self._fmt(r1)} (1д), "
            f"{self._fmt(r7)} (7д) и {self._fmt(r30)} (30д)."
        )

        trend_explanation = (
            f"Трендовая модель классифицирует {ticker} как {classification}. "
            + (trend.get("rationale") or "")
        ).strip()
        if trend.get("slow_ma_slope_pct") is not None:
            trend_explanation += (
                f" Наклон медленной скользящей средней за последнее окно — "
                f"{self._fmt(trend.get('slow_ma_slope_pct'))}."
            )

        sharpe = perf.get("sharpe")
        var_pct = tail.get("historical_var_pct")
        cvar_pct = tail.get("historical_cvar_pct")
        conf = tail.get("confidence_pct", 95)
        horizon = tail.get("horizon_days", 1)
        risk_analysis = (
            f"Годовая волатильность — {self._fmt(ann_vol)}, самая глубокая просадка "
            f"от пика до дна за окно — {self._fmt(mdd)}. "
            f"С поправкой на риск: коэффициент Шарпа {self._num(sharpe)}, "
            f"Сортино {self._num(perf.get('sortino'))}. "
            f"Исторический {conf:g}% VaR на {horizon} дн. — {self._fmt(var_pct)}, "
            f"ожидаемые потери в хвосте (CVaR) — {self._fmt(cvar_pct)}. "
            f"Композитный риск-скор — {score}/100 ({band}). "
            "Все оценки построены на прошлом и зависят от выборки: короткое или "
            "аномально спокойное окно занижает хвостовой риск, а волатильность "
            "кластеризуется, поэтому текущие значения могут не сохраниться."
        )
        if bench:
            risk_analysis += (
                f" Относительно {bench.get('benchmark')}: бета "
                f"{self._num(bench.get('beta'))}, корреляция дневных доходностей "
                f"{self._num(bench.get('correlation'))}."
            )

        key_signals = []
        if classification != "undetermined":
            key_signals.append(f"Трендовый режим: {classification}.")
        if ann_vol is not None:
            key_signals.append(f"Годовая волатильность {self._fmt(ann_vol)}.")
        rsi_key = next((k for k in indicators if k.startswith("rsi")), None)
        if rsi_key and indicators.get(rsi_key) is not None:
            rsi_val = indicators[rsi_key]
            zone = (
                "перекупленность"
                if rsi_val >= 70
                else "перепроданность"
                if rsi_val <= 30
                else "нейтрально"
            )
            key_signals.append(f"RSI {rsi_val:.0f} ({zone}).")
        if score is not None:
            key_signals.append(f"Композитный риск {score}/100 ({band}).")
        if sharpe is not None:
            key_signals.append(f"Коэффициент Шарпа {self._num(sharpe)}.")
        if var_pct is not None:
            key_signals.append(f"Исторический {conf:g}% VaR {self._fmt(var_pct)}.")
        if bench and bench.get("beta") is not None:
            key_signals.append(f"Бета к {bench.get('benchmark')} {self._num(bench.get('beta'))}.")
        if r30 is not None:
            key_signals.append(f"Доходность за 30 дней {self._fmt(r30)}.")

        return {
            "summary": summary,
            "trend_explanation": trend_explanation or "Тренд по данной выборке не определён.",
            "risk_analysis": risk_analysis,
            "key_signals": key_signals or ["Недостаточно данных для выделения сигналов."],
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
           (``"anthropic"`` / ``"openrouter"`` / ``"mock"``).
        2. ``AnthropicProvider`` if an ``ANTHROPIC_API_KEY`` is present.
        3. ``OpenRouterProvider`` if an ``OPENROUTER_API_KEY`` is present.
        4. ``MockProvider`` otherwise.
    """
    choice = (prefer or os.getenv("EQUITYMIND_LLM_PROVIDER") or "").strip().lower()

    if choice == "mock":
        logger.info("Using MockProvider (forced)")
        return MockProvider()
    if choice == "anthropic":
        logger.info("Using AnthropicProvider (forced): %s", model)
        return AnthropicProvider(model=model, max_tokens=max_tokens, effort=effort)
    if choice == "openrouter":
        provider = OpenRouterProvider(model=model, max_tokens=max_tokens)
        logger.info("Using OpenRouterProvider (forced): %s", provider.model)
        return provider

    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Using AnthropicProvider: %s", model)
        return AnthropicProvider(model=model, max_tokens=max_tokens, effort=effort)
    if os.getenv("OPENROUTER_API_KEY"):
        provider = OpenRouterProvider(model=model, max_tokens=max_tokens)
        logger.info("Using OpenRouterProvider: %s", provider.model)
        return provider

    logger.warning(
        "Neither ANTHROPIC_API_KEY nor OPENROUTER_API_KEY is set — falling back "
        "to the offline MockProvider. Set a key (or EQUITYMIND_LLM_PROVIDER) "
        "for LLM commentary."
    )
    return MockProvider()
