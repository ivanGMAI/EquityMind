from __future__ import annotations

from equitymind.ai import guardrails
from equitymind.ai.analyst import MarketAnalyst
from equitymind.ai.providers import MockProvider
from equitymind.analytics.metrics import compute_metrics


def test_mock_provider_offline_commentary(uptrend_history):
    metrics = compute_metrics(uptrend_history)
    analyst = MarketAnalyst(MockProvider())
    commentary = analyst.analyze(metrics)

    assert commentary.provider == "mock"
    assert commentary.summary
    assert commentary.trend_explanation
    assert commentary.risk_analysis
    assert len(commentary.key_signals) >= 1
    assert commentary.disclaimer


def test_mock_commentary_has_no_advice(uptrend_history, downtrend_history):
    analyst = MarketAnalyst(MockProvider(), strict_compliance=True)
    for hist in (uptrend_history, downtrend_history):
        commentary = analyst.analyze(compute_metrics(hist))
        # strict_compliance would have raised; also assert no flags.
        assert commentary.compliance_flags == []


def test_guardrails_flag_advice():
    assert guardrails.contains_advice("You should buy this stock now.")
    assert guardrails.contains_advice("We recommend selling immediately.")
    assert guardrails.contains_advice("Our price target is $200.")


def test_guardrails_allow_descriptive_language():
    text = (
        "Buyers stepped in near support while sellers dominated the open. "
        "Volatility rose and the trend turned bearish over the window."
    )
    assert not guardrails.contains_advice(text)


def test_analyze_many(uptrend_history, downtrend_history):
    analyst = MarketAnalyst(MockProvider())
    metrics = [compute_metrics(uptrend_history), compute_metrics(downtrend_history)]
    out = analyst.analyze_many(metrics)
    assert set(out) == {"UP", "DOWN"}
