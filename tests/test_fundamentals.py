from __future__ import annotations

from equitymind.data.fundamentals import (
    Fundamentals,
    FundamentalsSource,
    _num,
    fetch_fundamentals,
)

_INFO = {
    "longName": "Sberbank",
    "currency": "RUB",
    "sector": "Financial Services",
    "industry": "Banks—Regional",
    "marketCap": 6_500_000_000_000,
    "trailingPE": 4.2,
    "forwardPE": 3.8,
    "priceToBook": 0.9,
    "trailingEps": 60.5,
    "dividendYield": 0.11,
    "returnOnEquity": 0.24,
    "profitMargins": 0.33,
    "beta": 1.1,
}


def test_num_coercion():
    assert _num(3) == 3.0
    assert _num("4.5") == 4.5
    assert _num(None) is None
    assert _num("") is None
    assert _num("n/a") is None
    assert _num(True) is None  # bools are not meaningful numbers


def test_from_info_parses_fields():
    f = Fundamentals.from_info("sber", _INFO)
    assert f.ticker == "SBER"  # upper-cased
    assert f.name == "Sberbank"
    assert f.sector == "Financial Services"
    assert f.trailing_pe == 4.2
    assert f.market_cap == 6_500_000_000_000
    assert f.beta == 1.1


def test_to_payload_expresses_percentages():
    payload = Fundamentals.from_info("SBER", _INFO).to_payload()
    assert payload["dividend_yield_pct"] == 11.0
    assert payload["return_on_equity_pct"] == 24.0
    assert payload["profit_margin_pct"] == 33.0
    assert payload["trailing_pe"] == 4.2


def test_from_info_tolerates_missing_keys():
    f = Fundamentals.from_info("XYZ", {"shortName": "Xyz Co"})
    assert f.name == "Xyz Co"
    assert f.trailing_pe is None
    assert f.market_cap is None


def test_fetch_fundamentals_with_injected_source():
    class FakeSource(FundamentalsSource):
        name = "fake"

        def fetch(self, ticker):
            return Fundamentals.from_info(ticker, _INFO)

    f = fetch_fundamentals("SBER", FakeSource())
    assert f is not None
    assert f.sector == "Financial Services"
