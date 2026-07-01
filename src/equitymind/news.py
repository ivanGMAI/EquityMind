"""News-headline sentiment analysis.

A lightweight, fully-offline sentiment scorer for financial headlines. It uses a
curated finance lexicon with simple negation handling, so it is deterministic (no
network, no model) and therefore testable and reproducible. The score feeds the
AI analyst's market-context reasoning — quantifying the *news backdrop* alongside
the price-based metrics — and is exposed to the agent as a tool.

Scores are in ``[-1, +1]`` (bearish → bullish); the label thresholds are
intentionally conservative so a thin or mixed news flow reads as *neutral*.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# Finance-oriented sentiment lexicon (lower-case stems matched on whole words).
_POSITIVE = {
    "beat",
    "beats",
    "surge",
    "surges",
    "surged",
    "rally",
    "rallies",
    "rallied",
    "gain",
    "gains",
    "gained",
    "jump",
    "jumps",
    "jumped",
    "soar",
    "soars",
    "soared",
    "rise",
    "rises",
    "rose",
    "record",
    "profit",
    "profits",
    "growth",
    "grow",
    "grows",
    "upgrade",
    "upgraded",
    "outperform",
    "outperforms",
    "bullish",
    "strong",
    "strength",
    "boost",
    "boosts",
    "boosted",
    "expand",
    "expansion",
    "positive",
    "optimism",
    "optimistic",
    "recovery",
    "recover",
    "rebound",
    "rebounds",
    "dividend",
    "buyback",
    "beat expectations",
    "tops",
    "top",
    "win",
    "wins",
    "approval",
    "approved",
    "high",
}
_NEGATIVE = {
    "miss",
    "misses",
    "missed",
    "plunge",
    "plunges",
    "plunged",
    "drop",
    "drops",
    "dropped",
    "fall",
    "falls",
    "fell",
    "slump",
    "slumps",
    "slumped",
    "decline",
    "declines",
    "declined",
    "loss",
    "losses",
    "cut",
    "cuts",
    "downgrade",
    "downgraded",
    "underperform",
    "bearish",
    "weak",
    "weakness",
    "warn",
    "warns",
    "warning",
    "fear",
    "fears",
    "concern",
    "concerns",
    "risk",
    "risks",
    "recession",
    "default",
    "defaults",
    "probe",
    "lawsuit",
    "fraud",
    "layoff",
    "layoffs",
    "bankruptcy",
    "sanction",
    "sanctions",
    "selloff",
    "sell-off",
    "crash",
    "crashes",
    "slowdown",
    "negative",
    "low",
}
# Words that invert the polarity of the next sentiment token.
_NEGATIONS = {"not", "no", "never", "without", "fails", "fail", "failed", "less"}

_TOKEN_RE = re.compile(r"[a-z][a-z'-]*")


@dataclass(slots=True)
class HeadlineScore:
    headline: str
    score: float
    label: str


@dataclass(slots=True)
class SentimentResult:
    """Aggregate sentiment across a set of headlines."""

    mean_score: float
    label: str
    positive: int
    negative: int
    neutral: int
    count: int
    headlines: list[HeadlineScore] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def classify(score: float, band: float = 0.15) -> str:
    """Map a score in ``[-1, 1]`` to bullish / neutral / bearish."""
    if score > band:
        return "bullish"
    if score < -band:
        return "bearish"
    return "neutral"


def score_text(text: str) -> float:
    """Sentiment of a single string in ``[-1, 1]`` (0.0 if no signal words)."""
    tokens = _TOKEN_RE.findall(text.lower())
    pos = neg = 0
    negate = False
    for tok in tokens:
        if tok in _NEGATIONS:
            negate = True
            continue
        polarity = 1 if tok in _POSITIVE else -1 if tok in _NEGATIVE else 0
        if polarity == 0:
            continue
        if negate:
            polarity = -polarity
            negate = False
        if polarity > 0:
            pos += 1
        else:
            neg += 1
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def analyze_headlines(headlines: list[str]) -> SentimentResult:
    """Score a list of headlines and aggregate into a :class:`SentimentResult`."""
    scored: list[HeadlineScore] = []
    pos = neg = neu = 0
    for h in headlines:
        s = round(score_text(h), 3)
        label = classify(s)
        scored.append(HeadlineScore(headline=h, score=s, label=label))
        if label == "bullish":
            pos += 1
        elif label == "bearish":
            neg += 1
        else:
            neu += 1
    mean = round(sum(hs.score for hs in scored) / len(scored), 3) if scored else 0.0
    return SentimentResult(
        mean_score=mean,
        label=classify(mean),
        positive=pos,
        negative=neg,
        neutral=neu,
        count=len(scored),
        headlines=scored,
    )
