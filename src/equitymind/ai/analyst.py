"""The market analyst: metrics in, structured commentary out.

:class:`MarketAnalyst` orchestrates prompt construction, provider invocation,
schema validation and compliance guardrails. It is provider-agnostic (Claude or
the offline mock) and always returns a validated :class:`MarketCommentary`,
falling back to the mock provider if the primary provider errors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from ..analytics.metrics import AssetMetrics
from ..logging_config import get_logger
from . import guardrails
from .prompts import COMMENTARY_SCHEMA, DISCLAIMER, SYSTEM_PROMPT, build_user_prompt
from .providers import LLMProvider, MockProvider, ProviderError, build_provider

logger = get_logger(__name__)

_REQUIRED_FIELDS = ("summary", "trend_explanation", "risk_analysis", "key_signals")


@dataclass(slots=True)
class MarketCommentary:
    """Structured, advice-free commentary for a single instrument."""

    ticker: str
    summary: str
    trend_explanation: str
    risk_analysis: str
    key_signals: list[str]
    provider: str
    model: str
    disclaimer: str = DISCLAIMER
    compliance_flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class MarketAnalyst:
    """Generate structured commentary from :class:`AssetMetrics`."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        *,
        strict_compliance: bool = False,
        fallback_to_mock: bool = True,
    ) -> None:
        """
        Args:
            provider: LLM provider. Defaults to :func:`build_provider` resolution.
            strict_compliance: If ``True``, raise when advice language is
                detected; otherwise flag it and continue.
            fallback_to_mock: If the primary provider errors, retry with the
                offline :class:`MockProvider` instead of raising.
        """
        self.provider = provider or build_provider()
        self.strict_compliance = strict_compliance
        self.fallback_to_mock = fallback_to_mock

    # ------------------------------------------------------------------ public
    def analyze(self, metrics: AssetMetrics) -> MarketCommentary:
        """Produce commentary for one instrument's metrics."""
        payload = metrics.to_payload()
        user_prompt = build_user_prompt(payload)

        provider = self.provider
        try:
            data = provider.generate_commentary(
                payload, system=SYSTEM_PROMPT, user=user_prompt, schema=COMMENTARY_SCHEMA
            )
        except ProviderError as exc:
            if not self.fallback_to_mock or isinstance(provider, MockProvider):
                raise
            logger.warning("Provider '%s' failed (%s); falling back to mock", provider.name, exc)
            provider = MockProvider()
            data = provider.generate_commentary(
                payload, system=SYSTEM_PROMPT, user=user_prompt, schema=COMMENTARY_SCHEMA
            )

        return self._finalise(metrics.ticker, data, provider)

    def analyze_many(self, metrics: list[AssetMetrics]) -> dict[str, MarketCommentary]:
        """Generate commentary for several instruments, keyed by ticker."""
        out: dict[str, MarketCommentary] = {}
        for m in metrics:
            try:
                out[m.ticker] = self.analyze(m)
            except Exception as exc:  # pragma: no cover - defensive per-asset
                logger.error("Commentary failed for %s: %s", m.ticker, exc)
        return out

    # ------------------------------------------------------------------ internal
    def _finalise(self, ticker: str, data: dict, provider: LLMProvider) -> MarketCommentary:
        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise ProviderError(f"Commentary missing fields: {missing}")

        signals = data["key_signals"]
        if isinstance(signals, str):
            signals = [signals]

        flags = self._check_compliance(ticker, data)

        return MarketCommentary(
            ticker=ticker,
            summary=str(data["summary"]).strip(),
            trend_explanation=str(data["trend_explanation"]).strip(),
            risk_analysis=str(data["risk_analysis"]).strip(),
            key_signals=[str(s).strip() for s in signals],
            provider=provider.name,
            model=provider.model,
            compliance_flags=flags,
        )

    def _check_compliance(self, ticker: str, data: dict) -> list[str]:
        blob = " ".join(
            str(data.get(f, ""))
            if not isinstance(data.get(f), list)
            else " ".join(map(str, data.get(f, [])))
            for f in _REQUIRED_FIELDS
        )
        violations = guardrails.find_advice_violations(blob)
        if violations:
            msg = f"{ticker}: advice-like phrasing detected: {violations}"
            if self.strict_compliance:
                raise ProviderError(msg)
            logger.warning(msg)
        return violations
