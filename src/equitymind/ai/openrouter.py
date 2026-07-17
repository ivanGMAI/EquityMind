"""Minimal OpenRouter chat-completions client (stdlib only).

OpenRouter (https://openrouter.ai) exposes an OpenAI-compatible API that fronts
many models (Claude included) behind a single ``sk-or-...`` key. Both the
commentary provider and the tool-using agent talk to it through
:func:`chat_completion`; keeping the transport on ``urllib`` avoids an extra
SDK dependency, mirroring the MOEX and Telegram integrations.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

BASE_URL = "https://openrouter.ai/api/v1"
#: Used when the configured model id is not an OpenRouter slug (no ``vendor/``).
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"


class OpenRouterError(RuntimeError):
    """Raised when the OpenRouter API cannot produce a usable response."""


def resolve_api_key(api_key: str | None = None) -> str:
    key = api_key or os.getenv("OPENROUTER_API_KEY") or ""
    if not key:
        raise OpenRouterError("OPENROUTER_API_KEY is not set; export it or put it in .env")
    return key


def resolve_model(model: str | None) -> str:
    """Return ``model`` if it is an OpenRouter slug, else the default.

    OpenRouter ids are ``vendor/name`` (e.g. ``anthropic/claude-sonnet-4.5``);
    bare Anthropic ids from the YAML config would be rejected, so they fall
    back to :data:`DEFAULT_MODEL`.
    """
    if model and "/" in model:
        return model
    return DEFAULT_MODEL


def chat_completion(
    body: dict[str, Any],
    *,
    api_key: str | None = None,
    timeout: float = 120.0,
    retries_on_429: int = 2,
    retry_delay: float = 3.0,
) -> dict[str, Any]:
    """POST ``body`` to ``/chat/completions`` and return the decoded JSON.

    Free-tier models are frequently rate-limited upstream (HTTP 429), so those
    responses are retried a couple of times before giving up.
    """
    request = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolve_api_key(api_key)}",
            "Content-Type": "application/json",
            "X-Title": "EquityMind",
        },
        method="POST",
    )
    for attempt in range(retries_on_429 + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # pragma: no cover - best-effort diagnostics
                detail = ""
            if exc.code == 429 and attempt < retries_on_429:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise OpenRouterError(f"HTTP {exc.code}: {detail or exc.reason}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise OpenRouterError(f"request failed: {exc}") from exc
        if "error" in data:
            raise OpenRouterError(f"API error: {data['error']}")
        return data
    raise OpenRouterError("unreachable")  # pragma: no cover - loop always returns/raises


def first_message(data: dict[str, Any]) -> dict[str, Any]:
    """Extract ``choices[0].message`` or raise :class:`OpenRouterError`."""
    choices = data.get("choices") or []
    message = choices[0].get("message") if choices else None
    if not isinstance(message, dict):
        raise OpenRouterError("response has no choices[0].message")
    return message


def message_text(message: dict[str, Any]) -> str:
    """Normalise ``message.content`` (string or content-part list) to text."""
    content = message.get("content")
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""
