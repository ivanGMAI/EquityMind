"""Compliance guardrails for generated commentary.

The system prompt is the first line of defence against investment-advice
language; this module is the second. It scans generated text for recommendation
phrasing (imperative buy/sell/hold, "we recommend", price targets) so violations
can be logged, flagged, or — in strict mode — rejected. Defence in depth matters
here because advice-free output is a hard compliance requirement, not a nicety.
"""

from __future__ import annotations

import re

# Patterns that indicate a recommendation or forecast rather than description.
# Kept deliberately conservative to avoid false positives on descriptive prose
# such as "buyers stepped in" or "sellers dominated".
_ADVICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:we|i|you should|investors should)\s+(?:recommend|advise|suggest)\b", re.I),
    re.compile(r"\b(?:recommend|advise)\s+(?:buying|selling|holding|to buy|to sell)\b", re.I),
    re.compile(r"\byou should\s+(?:buy|sell|hold|accumulate|trim|exit|enter)\b", re.I),
    re.compile(
        r"\b(?:strong\s+)?(?:buy|sell|hold)\s+(?:rating|recommendation|signal|call)\b", re.I
    ),
    re.compile(r"\bprice target\b", re.I),
    re.compile(r"\b(?:will|expected to|likely to)\s+(?:rise|fall|reach|hit|climb|drop)\b", re.I),
    re.compile(r"\b(?:time to|now is the time to)\s+(?:buy|sell)\b", re.I),
    # Русские эквиваленты: комментарий генерируется на русском, поэтому
    # рекомендации и прогнозы отлавливаем и в русской формулировке.
    re.compile(
        r"\b(?:рекоменду(?:ем|ю|ется)|совету(?:ем|ю)|стоит|следует|пора)\s+"
        r"(?:куп(?:ить|ать)|прода(?:ть|вать)|держать|докупить|войти|выйти|зафиксировать)\b",
        re.I,
    ),
    re.compile(r"\b(?:покупайте|продавайте|держите|докупайте|фиксируйте)\b", re.I),
    re.compile(r"\bцелев(?:ая|ой)\s+цен\w*\b", re.I),
    re.compile(
        r"\b(?:вырастет|упад[её]т|достигнет|взлетит|обвалится|подорожает|подешевеет)\b", re.I
    ),
]


def find_advice_violations(text: str) -> list[str]:
    """Return the substrings that look like investment advice / forecasts."""
    hits: list[str] = []
    for pattern in _ADVICE_PATTERNS:
        hits.extend(m.group(0) for m in pattern.finditer(text or ""))
    return hits


def contains_advice(text: str) -> bool:
    return bool(find_advice_violations(text))
