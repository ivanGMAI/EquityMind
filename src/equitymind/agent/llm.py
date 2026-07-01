"""LLM back-ends for the tool-using agent.

The agent talks to a model through a single :class:`AgentLLM` step function that,
given the running conversation and the available tool schemas, returns either a
set of tool calls or a final answer. Two implementations:

* :class:`AnthropicAgentLLM` — Claude with native tool use,
* :class:`ScriptedAgentLLM` — a deterministic, offline stand-in that replays a
  predefined sequence of tool calls and a final answer, so the whole agent loop
  is testable without any network.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)


class AgentError(RuntimeError):
    """Raised when the agent back-end cannot produce a step."""


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(slots=True)
class AgentResponse:
    """One turn from the model: tool calls to run, or a final text answer."""

    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str | None = None
    #: Opaque assistant message content to append to the running conversation
    #: (raw content blocks for Anthropic; a synthetic block for the mock).
    assistant_content: Any = None

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


class AgentLLM(ABC):
    """A model that can request tool calls and produce a final answer."""

    name: str = "abstract"
    model: str = ""

    @abstractmethod
    def respond(self, messages: list[dict], *, system: str, tools: list[dict]) -> AgentResponse:
        """Produce the next step given the conversation, system prompt and tools."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic / Claude (native tool use)
# ---------------------------------------------------------------------------
class AnthropicAgentLLM(AgentLLM):
    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        *,
        max_tokens: int = 4096,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key
        self._client: Any = None

    def _client_or_raise(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - env dependent
            raise AgentError("anthropic SDK not installed") from exc
        self._client = (
            anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        )
        return self._client

    def respond(self, messages: list[dict], *, system: str, tools: list[dict]) -> AgentResponse:
        client = self._client_or_raise()
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                tools=tools,
                messages=messages,
            )
        except Exception as exc:  # network / API errors
            raise AgentError(f"Anthropic request failed: {exc}") from exc

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )
            elif btype == "text":
                text_parts.append(block.text)

        return AgentResponse(
            tool_calls=tool_calls,
            text="\n".join(text_parts).strip() or None,
            assistant_content=response.content,
        )


# ---------------------------------------------------------------------------
# Scripted, offline stand-in (for tests / demos)
# ---------------------------------------------------------------------------
class ScriptedAgentLLM(AgentLLM):
    """Replays a fixed sequence of steps; ignores message content.

    ``steps`` is a list where each item is either ``("tool", name, arguments)`` to
    request a tool call, or ``("final", text)`` to end with an answer. Useful for
    exercising the agent loop deterministically without a model.
    """

    name = "scripted"
    model = "scripted"

    def __init__(self, steps: list[tuple]) -> None:
        self._steps = list(steps)
        self._i = 0

    def respond(self, messages: list[dict], *, system: str, tools: list[dict]) -> AgentResponse:
        if self._i >= len(self._steps):
            return AgentResponse(text="(no further steps)", assistant_content={"type": "text"})
        step = self._steps[self._i]
        self._i += 1
        kind = step[0]
        if kind == "tool":
            _, name, arguments = step
            call = ToolCall(id=f"call_{self._i}", name=name, arguments=dict(arguments))
            return AgentResponse(
                tool_calls=[call],
                assistant_content={"type": "tool_use", "name": name, "input": arguments},
            )
        if kind == "final":
            return AgentResponse(text=str(step[1]), assistant_content={"type": "text"})
        raise AgentError(f"unknown scripted step kind: {kind!r}")


def build_tool_result_message(results: list[tuple[str, dict]]) -> dict:
    """Build a user message carrying tool results, keyed by tool-use id."""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": call_id,
                "content": json.dumps(result, default=str),
            }
            for call_id, result in results
        ],
    }
