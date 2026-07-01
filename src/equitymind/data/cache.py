"""On-disk caching layer for fetched price data.

Market data is expensive to fetch and rate-limited by the vendor, so identical
requests within a TTL window are served from a local parquet (or pickle) cache.
The cache is keyed by ``ticker:period:interval:source`` and stores the raw frame
plus lightweight metadata as a sidecar JSON file.

The layer degrades gracefully: any I/O or serialisation error is logged and
treated as a cache miss, never as a hard failure.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd

from ..logging_config import get_logger
from .models import PriceHistory

logger = get_logger(__name__)


class PriceCache:
    """TTL-bounded file cache for :class:`PriceHistory` objects."""

    def __init__(self, cache_dir: str | Path, ttl_minutes: int = 60) -> None:
        self.dir = Path(cache_dir)
        self.ttl_seconds = max(0, ttl_minutes) * 60
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ keys
    @staticmethod
    def _key(ticker: str, period: str, interval: str, source: str) -> str:
        raw = f"{source}:{ticker.upper()}:{period}:{interval}"
        digest = hashlib.sha1(raw.encode()).hexdigest()[:16]
        return f"{ticker.upper()}_{digest}"

    def _paths(self, key: str) -> tuple[Path, Path]:
        return self.dir / f"{key}.parquet", self.dir / f"{key}.meta.json"

    # ------------------------------------------------------------------ API
    def get(self, ticker: str, period: str, interval: str, source: str) -> PriceHistory | None:
        """Return a cached history if present and fresh, else ``None``."""
        key = self._key(ticker, period, interval, source)
        data_path, meta_path = self._paths(key)
        if not data_path.exists() or not meta_path.exists():
            return None

        try:
            meta = json.loads(meta_path.read_text())
            age = time.time() - meta.get("stored_at", 0)
            if self.ttl_seconds and age > self.ttl_seconds:
                logger.debug("Cache stale for %s (age %.0fs)", ticker, age)
                return None
            frame = pd.read_parquet(data_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cache read failed for %s: %s", ticker, exc)
            return None

        logger.debug("Cache hit for %s", ticker)
        return PriceHistory(
            ticker=meta.get("ticker", ticker.upper()),
            frame=frame,
            interval=meta.get("interval", interval),
            currency=meta.get("currency", "USD"),
            name=meta.get("name", ""),
            asset_class=meta.get("asset_class", "equity"),
        )

    def put(self, history: PriceHistory, period: str, source: str) -> None:
        """Persist a history to disk (best effort)."""
        key = self._key(history.ticker, period, history.interval, source)
        data_path, meta_path = self._paths(key)
        try:
            history.frame.to_parquet(data_path)
            meta = {
                "ticker": history.ticker,
                "interval": history.interval,
                "currency": history.currency,
                "name": history.name,
                "asset_class": history.asset_class,
                "period": period,
                "source": source,
                "stored_at": time.time(),
                "rows": len(history),
            }
            meta_path.write_text(json.dumps(meta, indent=2))
            logger.debug("Cached %s (%d rows)", history.ticker, len(history))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Cache write failed for %s: %s", history.ticker, exc)

    def clear(self) -> int:
        """Delete all cached entries. Returns the number of files removed."""
        removed = 0
        for f in self.dir.glob("*"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
        return removed
