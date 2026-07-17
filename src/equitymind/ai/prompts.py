"""Prompt templates and the structured-output schema for the AI analyst.

The system prompt is the primary guardrail: it fixes the persona (a compliance-
aware sell-side analyst), constrains the model to the supplied numbers, and
forbids investment advice. The JSON schema then constrains the *shape* of the
response so downstream code can rely on four well-defined fields.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# System prompt — persona + hard constraints.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are a professional financial market analyst writing an internal desk note \
for a quantitative research team at a bank. Your job is descriptive and \
explanatory market commentary, in the measured, precise register of a sell-side \
research analyst.

STRICT RULES — these are compliance requirements, not stylistic preferences:
1. You DO NOT give investment advice. Never tell the reader to buy, sell, hold, \
   accumulate, trim, enter, exit, or otherwise transact. Do not use the words \
   "buy", "sell", or "hold" as recommendations.
2. You DO NOT make price predictions or forecasts, and you do not imply a \
   target price or expected return.
3. You describe and explain what the DATA shows. Every claim must be grounded \
   in the metrics provided in the user message. Do not invent numbers, news, \
   fundamentals, or events that are not in the data.
4. You explicitly acknowledge risks, limitations, and uncertainty. Note when \
   the sample window is short or a signal is ambiguous.
5. Tone: objective, concise, professional. No hype, no emojis, no hedging \
   filler. Use the instrument's own figures to support each point.
6. LANGUAGE: write the entire commentary in RUSSIAN. Use standard Russian \
   financial terminology; tickers and established metric names (Sharpe, VaR, \
   RSI) may stay in Latin script.

You will be given the instrument's computed quantitative metrics as JSON. \
Produce structured commentary in the required output format. The commentary is \
educational market analysis only and must not be construed as financial advice.\
"""

# ---------------------------------------------------------------------------
# Structured-output JSON schema (Anthropic `output_config.format`).
# ---------------------------------------------------------------------------
COMMENTARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-4 sentence overview of the instrument's recent "
            "market behaviour, grounded in the metrics.",
        },
        "trend_explanation": {
            "type": "string",
            "description": "Explanation of the price trend and what is driving "
            "the classification (moving-average relationships, momentum).",
        },
        "risk_analysis": {
            "type": "string",
            "description": "Assessment of volatility, drawdown, risk-adjusted "
            "performance (Sharpe/Sortino/Calmar), tail risk (VaR/CVaR), any "
            "benchmark beta/correlation, and the composite risk score — including "
            "uncertainty and caveats.",
        },
        "key_signals": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-5 short, factual bullet-point observations.",
        },
    },
    "required": ["summary", "trend_explanation", "risk_analysis", "key_signals"],
    "additionalProperties": False,
}

DISCLAIMER = (
    "Комментарий сгенерирован автоматически на основе количественных индикаторов "
    "и носит учебно-аналитический характер. Это не инвестиционная рекомендация, "
    "не совет и не предложение совершать сделки с какими-либо инструментами."
)


def build_user_prompt(payload: dict[str, Any]) -> str:
    """Render the per-asset metrics payload into the analyst's user message."""
    metrics_json = json.dumps(payload, indent=2, default=str)
    ticker = payload.get("ticker", "the instrument")
    return (
        f"Analyse {ticker} using ONLY the quantitative metrics below. Percentages "
        f"are already expressed in percent (e.g. 3.5 means 3.5%).\n\n"
        f"```json\n{metrics_json}\n```\n\n"
        "Write the desk note in the required structured format, in RUSSIAN. "
        "Ground every statement in these figures, explain what is driving the "
        "trend, and assess the risk honestly — reference the risk-adjusted "
        "ratios (Sharpe/Sortino/Calmar), the tail-risk figures (VaR/CVaR) and, "
        "where present, the benchmark beta and correlation, noting uncertainty. "
        "Then list the key signals. Do not give investment advice or price "
        "targets."
    )
