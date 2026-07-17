"""LLM back-ends for the tool-using agent.

The agent talks to a model through a single :class:`AgentLLM` step function that,
given the running conversation and the available tool schemas, returns either a
set of tool calls or a final answer. Two implementations:

* :class:`AnthropicAgentLLM` — Claude with native tool use,
* :class:`OpenRouterAgentLLM` — any OpenRouter-served model via OpenAI-style
  function calling (for ``sk-or-...`` keys),
* :class:`ScriptedAgentLLM` — a deterministic, offline stand-in that replays a
  predefined sequence of tool calls and a final answer, so the whole agent loop
  is testable without any network.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..ai import openrouter
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
# OpenRouter (OpenAI-style function calling)
# ---------------------------------------------------------------------------
class OpenRouterAgentLLM(AgentLLM):
    """OpenRouter-backed agent step function.

    The agent loop keeps the conversation in Anthropic-style blocks; this class
    converts messages and tool schemas to the OpenAI chat format on the way out
    and normalises tool calls on the way back, so the loop itself stays
    backend-agnostic.
    """

    name = "openrouter"

    def __init__(
        self,
        model: str | None = None,
        *,
        max_tokens: int = 4096,
        api_key: str | None = None,
    ) -> None:
        self.model = openrouter.resolve_model(model)
        self.max_tokens = max_tokens
        self._api_key = api_key

    def respond(self, messages: list[dict], *, system: str, tools: list[dict]) -> AgentResponse:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, *self._to_openai(messages)],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ],
        }
        try:
            data = openrouter.chat_completion(body, api_key=self._api_key)
        except openrouter.OpenRouterError as exc:
            raise AgentError(f"OpenRouter request failed: {exc}") from exc

        message = openrouter.first_message(data)
        tool_calls: list[ToolCall] = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                raise AgentError(f"model returned malformed tool arguments: {exc}") from exc
            tool_calls.append(
                ToolCall(
                    id=call.get("id") or f"call_{len(tool_calls)}",
                    name=function.get("name", ""),
                    arguments=arguments,
                )
            )

        return AgentResponse(
            tool_calls=tool_calls,
            text=openrouter.message_text(message).strip() or None,
            assistant_content=message,
        )

    @staticmethod
    def _to_openai(messages: list[dict]) -> list[dict]:
        """Convert the loop's Anthropic-style history to OpenAI chat messages."""
        converted: list[dict] = []
        for msg in messages:
            role, content = msg["role"], msg["content"]
            if role == "assistant" and isinstance(content, dict):
                # Our own previous turn: unwrap the stored OpenAI message.
                converted.append(
                    {
                        "role": "assistant",
                        "content": content.get("content") or "",
                        **(
                            {"tool_calls": content["tool_calls"]}
                            if content.get("tool_calls")
                            else {}
                        ),
                    }
                )
            elif role == "user" and isinstance(content, list):
                # Anthropic-style tool_result blocks -> OpenAI "tool" messages.
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        converted.append(
                            {
                                "role": "tool",
                                "tool_call_id": block["tool_use_id"],
                                "content": block["content"],
                            }
                        )
            else:
                converted.append({"role": role, "content": content})
        return converted


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
