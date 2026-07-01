from __future__ import annotations

from equitymind.config import AssetSpec, Settings
from equitymind.data.csv_source import CSVSource
from equitymind.data.moex import MoexSource
from equitymind.data.stock_data_loader import YFinanceSource
from equitymind.pipeline import IntelligencePipeline


def _settings(**data_kwargs) -> Settings:
    s = Settings(universe=[AssetSpec(ticker="AAA")])
    for k, v in data_kwargs.items():
        setattr(s.data, k, v)
    return s


def test_build_source_defaults_to_yfinance():
    assert isinstance(IntelligencePipeline._build_source(_settings()), YFinanceSource)


def test_build_source_moex():
    src = IntelligencePipeline._build_source(_settings(source="moex", currency="RUB"))
    assert isinstance(src, MoexSource)
    assert src.currency == "RUB"


def test_build_source_csv():
    src = IntelligencePipeline._build_source(_settings(source="csv", csv_dir="mydata"))
    assert isinstance(src, CSVSource)
    assert str(src.data_dir) == "mydata"


def test_fundamentals_source_off_by_default():
    settings = _settings()
    pipe = IntelligencePipeline(
        settings,
        loader=object(),
        analyst=object(),  # loaders unused for this check
    )
    assert pipe.fundamentals_source is None


def test_fundamentals_source_enabled_when_configured():
    settings = _settings(include_fundamentals=True)
    pipe = IntelligencePipeline(settings, loader=object(), analyst=object())
    assert pipe.fundamentals_source is not None
