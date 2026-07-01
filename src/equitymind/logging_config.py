"""Centralised logging configuration.

A single :func:`configure_logging` call sets up a consistent, timestamped format
across every module. Library code never calls ``logging.basicConfig`` itself; it
only requests loggers via :func:`get_logger`, so applications remain in control
of handlers and levels.
"""

from __future__ import annotations

import logging
import os

_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(level: str | None = None, *, force: bool = False) -> None:
    """Initialise root logging once for the whole process.

    Args:
        level: Log level name (e.g. ``"INFO"``). Falls back to the
            ``EQUITYMIND_LOG_LEVEL`` environment variable, then ``"INFO"``.
        force: Re-apply configuration even if it was already set up.
    """
    global _configured
    if _configured and not force:
        return

    resolved = (level or os.getenv("EQUITYMIND_LOG_LEVEL") or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format=_DEFAULT_FORMAT,
        datefmt=_DATE_FORMAT,
        force=force,
    )
    # yfinance / urllib3 are noisy at DEBUG; keep them at WARNING.
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger, configuring logging on first use."""
    configure_logging()
    return logging.getLogger(name)
