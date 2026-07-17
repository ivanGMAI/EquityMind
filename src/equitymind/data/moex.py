"""Moscow Exchange (MOEX) data source via the public ISS API.

Fetches end-of-day (or intraday) candles for Russian instruments — the natural
universe for a Sberbank Global Markets desk (``SBER``, ``GAZP``, ``LKOH``,
``IMOEX`` …) — from the free, key-less MOEX ISS API:

    https://iss.moex.com/iss/engines/stock/markets/shares/securities/SBER/candles.json

Only the standard library is used for HTTP so there is no extra dependency. The
network call is isolated in :func:`_http_get_json` (monkeypatch-friendly) and the
JSON→frame conversion in :func:`_parse_candles`, so the parsing/pagination logic
is fully testable offline.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

import pandas as pd

from ..logging_config import get_logger
from .base import DataSource, DataSourceError
from .models import PriceHistory

logger = get_logger(__name__)

_ISS_BASE = (
    "https://iss.moex.com/iss/engines/stock/markets/{market}/securities/{ticker}/candles.json"
)

# yfinance-style period aliases -> look-back in days.
_PERIOD_DAYS: dict[str, int] = {
    "1mo": 30,
    "3mo": 90,
    "6mo": 180,
    "1y": 365,
    "2y": 730,
    "3y": 1095,
    "5y": 1825,
    "10y": 3650,
    "max": 8000,
}
# yfinance-style interval -> MOEX candle interval code.
_INTERVAL_CODE: dict[str, int] = {
    "1m": 1,
    "10m": 10,
    "1h": 60,
    "1d": 24,
    "1wk": 7,
    "1w": 7,
    "1mo_bar": 31,
}


def _period_to_from(period: str, today: date | None = None) -> str:
    """Translate a period alias into a MOEX ``from`` date (ISO string)."""
    today = today or date.today()
    days = _PERIOD_DAYS.get(period.lower(), 365)
    return (today - timedelta(days=days)).isoformat()


def _interval_to_code(interval: str) -> int:
    return _INTERVAL_CODE.get(interval.lower(), 24)


def _http_get_json(url: str, *, timeout: float = 15.0) -> dict[str, Any]:
    """GET a URL and decode the JSON body (isolated for testability)."""
    req = urllib.request.Request(url, headers={"User-Agent": "EquityMind/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed API host
        return json.loads(resp.read().decode("utf-8"))


def _parse_candles(payload: dict[str, Any]) -> pd.DataFrame:
    """Convert one MOEX ``candles`` JSON page into a canonical OHLCV frame."""
    block = payload.get("candles", {})
    columns = [str(c).lower() for c in block.get("columns", [])]
    rows = block.get("data", [])
    if not rows:
        return pd.DataFrame()

    raw = pd.DataFrame(rows, columns=columns)
    # 'begin' is the candle start timestamp ("YYYY-MM-DD HH:MM:SS").
    raw["_date"] = pd.to_datetime(raw["begin"]).dt.tz_localize(None)
    frame = pd.DataFrame(
        {
            "open": pd.to_numeric(raw.get("open"), errors="coerce"),
            "high": pd.to_numeric(raw.get("high"), errors="coerce"),
            "low": pd.to_numeric(raw.get("low"), errors="coerce"),
            "close": pd.to_numeric(raw.get("close"), errors="coerce"),
            "volume": pd.to_numeric(raw.get("volume"), errors="coerce"),
        }
    )
    frame.index = raw["_date"]
    return frame.dropna(subset=["close"])


_ISS_SECURITIES = (
    "https://iss.moex.com/iss/engines/stock/markets/{market}/boards/{board}/securities.json"
    "?iss.only=securities&securities.columns=SECID,SHORTNAME"
)


def list_securities(market: str = "shares", board: str = "TQBR") -> list[dict[str, str]]:
    """List tradable instruments on a MOEX board as ``{ticker, name}`` dicts.

    TQBR is the main T+ equities board (~250 liquid Russian shares).
    """
    url = _ISS_SECURITIES.format(market=market, board=board)
    payload = _http_get_json(url)
    block = payload.get("securities", {})
    cols = [str(c).upper() for c in block.get("columns", [])]
    try:
        i_secid, i_name = cols.index("SECID"), cols.index("SHORTNAME")
    except ValueError as exc:
        raise DataSourceError(f"unexpected ISS securities columns: {cols}") from exc
    return [
        {"ticker": str(row[i_secid]), "name": str(row[i_name] or row[i_secid])}
        for row in block.get("data", [])
        if row[i_secid]
    ]


def _cursor_needs_more(payload: dict[str, Any]) -> tuple[int, int, int]:
    """Return (index, total, pagesize) from a ``candles.cursor`` block."""
    cur = payload.get("candles.cursor", {})
    cols = [str(c).upper() for c in cur.get("columns", [])]
    data = cur.get("data", [])
    if not data:
        return 0, 0, 0
    row = dict(zip(cols, data[0], strict=False))
    return int(row.get("INDEX", 0)), int(row.get("TOTAL", 0)), int(row.get("PAGESIZE", 0))


class MoexSource(DataSource):
    """OHLCV candles from the MOEX ISS API (Russian equities/indices)."""

    name = "moex"

    def __init__(self, *, market: str = "shares", currency: str = "RUB") -> None:
        self.market = market
        self.currency = currency

    def fetch(self, ticker: str, *, period: str, interval: str) -> PriceHistory:
        ticker = ticker.strip().upper()
        try:
            return self._fetch_market(ticker, self.market, period=period, interval=interval)
        except DataSourceError:
            # Indices (IMOEX, RTSI, …) live on the "index" market; fall back so a
            # shares-configured source can still resolve an index benchmark.
            if self.market == "index":
                raise
            return self._fetch_market(ticker, "index", period=period, interval=interval)

    def _fetch_market(
        self, ticker: str, market: str, *, period: str, interval: str
    ) -> PriceHistory:
        base = _ISS_BASE.format(market=market, ticker=ticker)
        params = {
            "from": _period_to_from(period),
            "till": date.today().isoformat(),
            "interval": _interval_to_code(interval),
        }
        logger.info("Fetching %s from MOEX (period=%s interval=%s)", ticker, period, interval)

        pages: list[pd.DataFrame] = []
        start = 0
        for _ in range(200):  # hard stop against a runaway cursor
            url = f"{base}?{urllib.parse.urlencode({**params, 'start': start})}"
            try:
                payload = _http_get_json(url)
            except Exception as exc:  # network / vendor errors
                raise DataSourceError(f"{ticker}: MOEX fetch failed ({exc})") from exc
            page = _parse_candles(payload)
            if not page.empty:
                pages.append(page)
            index, total, pagesize = _cursor_needs_more(payload)
            if pagesize == 0 or index + pagesize >= total or page.empty:
                break
            start = index + pagesize

        if not pages:
            raise DataSourceError(f"{ticker}: no data returned from MOEX (unknown symbol?)")

        frame = pd.concat(pages)
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        if frame.empty:
            raise DataSourceError(f"{ticker}: no usable rows from MOEX after parsing")

        return PriceHistory(ticker=ticker, frame=frame, interval=interval, currency=self.currency)
