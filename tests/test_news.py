from __future__ import annotations

from equitymind.news import analyze_headlines, classify, score_text


def test_score_positive_and_negative():
    assert score_text("Company beats expectations, profit surges to record high") > 0.5
    assert score_text("Shares plunge as company warns of losses and layoffs") < -0.5


def test_score_neutral_without_signal_words():
    assert score_text("The company held its annual general meeting today") == 0.0


def test_negation_flips_polarity():
    # "not rise" and "weak" -> net negative despite a positive word present.
    assert score_text("Revenue did not rise, growth is weak") < 0


def test_classify_bands():
    assert classify(0.5) == "bullish"
    assert classify(-0.5) == "bearish"
    assert classify(0.0) == "neutral"
    assert classify(0.1) == "neutral"  # inside the neutral band


def test_analyze_headlines_aggregates():
    result = analyze_headlines(
        [
            "Profit surges to record high",
            "Stock plunges on fraud probe",
            "Board approves buyback",
        ]
    )
    assert result.count == 3
    assert result.positive == 2
    assert result.negative == 1
    assert result.label == "bullish"
    assert len(result.headlines) == 3


def test_analyze_empty_is_neutral():
    result = analyze_headlines([])
    assert result.count == 0
    assert result.mean_score == 0.0
    assert result.label == "neutral"
