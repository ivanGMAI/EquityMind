from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from equitymind.data import moex
from equitymind.data.base import DataSourceError
from equitymind.data.csv_source import CSVSource, load_csv_file


def _candles_payload(rows, *, index=0, total=None, pagesize=100):
    total = len(rows) if total is None else total
    return {
        "candles": {
            "columns": ["open", "close", "high", "low", "value", "volume", "begin", "end"],
            "data": rows,
        },
        "candles.cursor": {
            "columns": ["INDEX", "TOTAL", "PAGESIZE"],
            "data": [[index, total, pagesize]],
        },
    }


def _row(day, o, c, h, low, vol):
    ts = f"2024-01-{day:02d} 00:00:00"
    return [o, c, h, low, 1e9, vol, ts, ts]


# ---- MOEX -------------------------------------------------------------------
def test_moex_parse_candles():
    payload = _candles_payload(
        [_row(3, 250, 255, 256, 249, 1000), _row(4, 255, 251, 257, 250, 1200)]
    )
    df = moex._parse_candles(payload)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert list(df["close"]) == [255.0, 251.0]
    assert isinstance(df.index, pd.DatetimeIndex)


def test_moex_period_and_interval_mapping():
    ref = date(2024, 7, 1)
    assert moex._period_to_from("6mo", ref) == "2024-01-03"
    assert moex._period_to_from("1y", ref) == "2023-07-02"
    assert moex._interval_to_code("1d") == 24
    assert moex._interval_to_code("1h") == 60
    assert moex._interval_to_code("unknown") == 24  # defaults to daily


def test_moex_cursor_parsing():
    payload = _candles_payload([_row(3, 1, 2, 3, 0.5, 1)], index=0, total=10, pagesize=5)
    assert moex._cursor_needs_more(payload) == (0, 10, 5)


def test_moex_fetch_single_page(monkeypatch):
    payload = _candles_payload([_row(3, 250, 255, 256, 249, 1000)], index=0, total=1, pagesize=100)
    monkeypatch.setattr(moex, "_http_get_json", lambda url, **kw: payload)
    hist = moex.MoexSource().fetch("SBER", period="1y", interval="1d")
    assert hist.ticker == "SBER"
    assert hist.currency == "RUB"
    assert hist.last_price == 255.0


def test_moex_fetch_paginates(monkeypatch):
    page1 = _candles_payload(
        [_row(3, 1, 2, 3, 0.5, 1), _row(4, 2, 3, 4, 1.5, 1)], index=0, total=3, pagesize=2
    )
    page2 = _candles_payload([_row(5, 3, 4, 5, 2.5, 1)], index=2, total=3, pagesize=2)
    pages = iter([page1, page2])
    monkeypatch.setattr(moex, "_http_get_json", lambda url, **kw: next(pages))
    hist = moex.MoexSource().fetch("GAZP", period="1y", interval="1d")
    assert len(hist) == 3  # both pages aggregated
    assert hist.last_price == 4.0


def test_moex_fetch_empty_raises(monkeypatch):
    monkeypatch.setattr(moex, "_http_get_json", lambda url, **kw: _candles_payload([]))
    with pytest.raises(DataSourceError):
        moex.MoexSource().fetch("NOPE", period="1y", interval="1d")


# ---- CSV --------------------------------------------------------------------
def _write_csv(path, header):
    path.write_text(
        f"{header}\n2024-01-02,10,10.5,9.5,10.2,100\n2024-01-03,11,11.5,10.5,11.1,200\n",
        encoding="utf-8",
    )


def test_csv_standard_headers(tmp_path):
    f = tmp_path / "AAA.csv"
    _write_csv(f, "Date,Open,High,Low,Close,Volume")
    hist = load_csv_file(f, ticker="AAA")
    assert list(hist.close) == [10.2, 11.1]
    assert hist.ticker == "AAA"


def test_csv_flexible_headers(tmp_path):
    f = tmp_path / "BBB.csv"
    _write_csv(f, "TRADEDATE,Open,High,Low,Adj Close,Volume")
    hist = load_csv_file(f, ticker="BBB")
    assert list(hist.close) == [10.2, 11.1]


def test_csv_missing_close_raises(tmp_path):
    f = tmp_path / "CCC.csv"
    f.write_text("Date,Open,High,Low,Volume\n2024-01-02,1,2,0.5,100\n", encoding="utf-8")
    with pytest.raises(DataSourceError):
        load_csv_file(f, ticker="CCC")


def test_csv_source_reads_named_file(tmp_path):
    _write_csv(tmp_path / "SBER.csv", "Date,Open,High,Low,Close,Volume")
    hist = CSVSource(tmp_path, currency="RUB").fetch("SBER", period="max", interval="1d")
    assert hist.currency == "RUB"
    assert len(hist) == 2


def test_csv_source_missing_file_raises(tmp_path):
    with pytest.raises(DataSourceError):
        CSVSource(tmp_path).fetch("GONE", period="1y", interval="1d")
