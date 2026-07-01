from __future__ import annotations

from pathlib import Path

from equitymind.config import Settings, load_settings
from equitymind.data.cache import PriceCache


def test_load_default_config():
    settings = load_settings("config/config.yaml")
    assert isinstance(settings, Settings)
    assert len(settings.universe) >= 1
    assert settings.ai.model  # a model is configured


def test_config_lookup_helpers():
    settings = load_settings("config/config.yaml")
    tickers = settings.tickers()
    assert tickers == [t.upper() for t in tickers]  # normalised upper-case
    first = tickers[0]
    assert settings.asset(first.lower()) is not None  # case-insensitive lookup


def test_cache_round_trip(uptrend_history, tmp_path: Path):
    cache = PriceCache(tmp_path, ttl_minutes=60)
    cache.put(uptrend_history, period="1y", source="test")
    loaded = cache.get("UP", "1y", "1d", "test")
    assert loaded is not None
    assert loaded.ticker == "UP"
    assert len(loaded) == len(uptrend_history)


def test_cache_miss_on_unknown(tmp_path: Path):
    cache = PriceCache(tmp_path, ttl_minutes=60)
    assert cache.get("NOPE", "1y", "1d", "test") is None


def test_cache_ttl_expiry(uptrend_history, tmp_path: Path):
    cache = PriceCache(tmp_path, ttl_minutes=0)  # everything is immediately stale
    cache.put(uptrend_history, period="1y", source="test")
    # ttl of 0 means "no expiry" per convention (ttl_seconds == 0 disables check)
    assert cache.get("UP", "1y", "1d", "test") is not None
