"""Outbound notifications for automated (scheduled) runs.

Supports the "прикладная автоматизация бизнес-процессов" workflow: after a
scheduled pipeline run, push a short plain-text digest of the ranking, alerts and
best/worst performers to a Telegram chat. Uses only the standard library
(``urllib``) so there is no extra dependency, and degrades gracefully — a missing
token or a network error is logged and returns ``False`` rather than raising, so
notification failure never breaks the analysis run.

Credentials are read from the environment when not passed explicitly:

* ``EQUITYMIND_TELEGRAM_TOKEN``   — bot token
* ``EQUITYMIND_TELEGRAM_CHAT_ID`` — target chat id
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from .logging_config import get_logger

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from .pipeline import AnalysisReport

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def build_digest(report: AnalysisReport, *, max_rows: int = 8) -> str:
    """Compose a compact plain-text summary of a report for messaging."""
    lines = [f"EquityMind — {report.generated_at}"]
    comp = report.comparison
    if comp is not None and comp.entries:
        lines.append("")
        lines.append(f"Ranking (reward/risk, {comp.return_basis}):")
        for e in comp.entries[:max_rows]:
            ret = "n/a" if e.return_pct is None else f"{e.return_pct:+.1f}%"
            rr = "n/a" if e.reward_risk_ratio is None else f"{e.reward_risk_ratio}"
            lines.append(
                f"  {e.rank}. {e.ticker}  {ret}  vol {e.annualized_volatility_pct:.0f}%  R/R {rr}  [{e.trend}]"
            )
    if report.portfolio is not None:
        p = report.portfolio
        ms = p.allocations.get("max_sharpe")
        if ms is not None:
            lines.append("")
            lines.append(
                f"Max-Sharpe portfolio: return {ms.expected_return_pct:+.1f}%, vol {ms.volatility_pct:.1f}%, Sharpe {ms.sharpe}"
            )
    if report.alerts:
        lines.append("")
        lines.append("Alerts:")
        for a in report.alerts:
            lines.append(f"  [{a.severity.upper()}] {a.message}")
    if report.failures:
        lines.append("")
        lines.append(f"Failed to load: {', '.join(report.failures)}")
    return "\n".join(lines)


def _http_post_json(url: str, payload: dict, *, timeout: float = 10.0) -> dict:
    """POST a JSON body and return the decoded JSON response (isolated for tests)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed API host
        return json.loads(resp.read().decode("utf-8"))


def send_telegram_message(
    text: str,
    *,
    token: str | None = None,
    chat_id: str | None = None,
    timeout: float = 10.0,
) -> bool:
    """Send ``text`` to a Telegram chat. Returns ``True`` on success.

    Credentials fall back to the environment. Any missing credential or transport
    error is logged and yields ``False`` (never raises).
    """
    token = token or os.getenv("EQUITYMIND_TELEGRAM_TOKEN")
    chat_id = chat_id or os.getenv("EQUITYMIND_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.warning(
            "Telegram credentials not set (EQUITYMIND_TELEGRAM_TOKEN / "
            "EQUITYMIND_TELEGRAM_CHAT_ID); skipping notification."
        )
        return False
    url = _TELEGRAM_API.format(token=token)
    try:
        result = _http_post_json(
            url,
            {"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=timeout,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.error("Telegram notification failed: %s", exc)
        return False
    ok = bool(result.get("ok"))
    if not ok:
        logger.error("Telegram API rejected the message: %s", result)
    return ok


def notify_report(
    report: AnalysisReport,
    *,
    token: str | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send a digest of ``report`` to Telegram. Returns ``True`` on success."""
    return send_telegram_message(build_digest(report), token=token, chat_id=chat_id)
