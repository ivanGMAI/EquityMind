"""OpenRouter provider + agent backend (transport mocked, no network)."""

from __future__ import annotations

import copy
import json

import pytest

from equitymind.agent import build_agent
from equitymind.agent.llm import AnthropicAgentLLM, OpenRouterAgentLLM
from equitymind.ai import openrouter
from equitymind.ai.providers import (
    MockProvider,
    OpenRouterProvider,
    ProviderError,
    build_provider,
)

COMMENTARY = {
    "summary": "s",
    "trend_explanation": "t",
    "risk_analysis": "r",
    "key_signals": ["k"],
}
SCHEMA = {"type": "object"}


def _response(message: dict) -> dict:
    return {"choices": [{"message": message}]}


@pytest.fixture()
def clean_env(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "EQUITYMIND_LLM_PROVIDER"):
        monkeypatch.delenv(var, raising=False)


# ------------------------------------------------------------------ transport
def test_resolve_model_maps_non_slug_ids():
    assert openrouter.resolve_model("claude-opus-4-8") == openrouter.DEFAULT_MODEL
    assert openrouter.resolve_model(None) == openrouter.DEFAULT_MODEL
    assert openrouter.resolve_model("deepseek/deepseek-chat") == "deepseek/deepseek-chat"


def test_resolve_api_key_requires_key(clean_env):
    with pytest.raises(openrouter.OpenRouterError):
        openrouter.resolve_api_key()


# ------------------------------------------------------------------ provider
def test_provider_parses_plain_json(monkeypatch):
    monkeypatch.setattr(
        openrouter,
        "chat_completion",
        lambda body, **kw: _response({"content": json.dumps(COMMENTARY)}),
    )
    provider = OpenRouterProvider(model="anthropic/claude-sonnet-4.5")
    out = provider.generate_commentary({"ticker": "SBER"}, system="s", user="u", schema=SCHEMA)
    assert out == COMMENTARY


def test_provider_parses_fenced_json(monkeypatch):
    fenced = f"```json\n{json.dumps(COMMENTARY)}\n```"
    monkeypatch.setattr(
        openrouter, "chat_completion", lambda body, **kw: _response({"content": fenced})
    )
    out = OpenRouterProvider().generate_commentary({}, system="s", user="u", schema=SCHEMA)
    assert out == COMMENTARY


def test_provider_retries_without_response_format_on_400(monkeypatch):
    bodies: list[dict] = []

    def fake(body, **kw):
        bodies.append(copy.deepcopy(body))
        if len(bodies) == 1:
            raise openrouter.OpenRouterError("HTTP 400: response_format unsupported")
        return _response({"content": json.dumps(COMMENTARY)})

    monkeypatch.setattr(openrouter, "chat_completion", fake)
    out = OpenRouterProvider().generate_commentary({}, system="s", user="u", schema=SCHEMA)
    assert out == COMMENTARY
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]
    assert "JSON object" in bodies[1]["messages"][1]["content"]


def test_provider_raises_on_non_json(monkeypatch):
    monkeypatch.setattr(
        openrouter, "chat_completion", lambda body, **kw: _response({"content": "no json here"})
    )
    with pytest.raises(ProviderError):
        OpenRouterProvider().generate_commentary({}, system="s", user="u", schema=SCHEMA)


def test_build_provider_env_resolution(clean_env, monkeypatch):
    assert isinstance(build_provider(), MockProvider)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    assert isinstance(build_provider(), OpenRouterProvider)
    assert isinstance(build_provider(prefer="mock"), MockProvider)
    forced = build_provider(prefer="openrouter", model="deepseek/deepseek-chat")
    assert isinstance(forced, OpenRouterProvider)
    assert forced.model == "deepseek/deepseek-chat"


# ------------------------------------------------------------------ agent
def test_agent_llm_converts_history_and_parses_tool_calls(monkeypatch):
    captured: list[dict] = []

    def fake(body, **kw):
        captured.append(body)
        return _response(
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {"name": "get_metrics", "arguments": '{"ticker": "SBER"}'},
                    }
                ],
            }
        )

    monkeypatch.setattr(openrouter, "chat_completion", fake)
    llm = OpenRouterAgentLLM(model="anthropic/claude-sonnet-4.5")

    history = [
        {"role": "user", "content": "How risky is SBER?"},
        {"role": "assistant", "content": {"content": "", "tool_calls": [{"id": "call_0"}]}},
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "call_0", "content": "{}"}],
        },
    ]
    tools = [{"name": "get_metrics", "description": "d", "input_schema": SCHEMA}]
    resp = llm.respond(history, system="sys", tools=tools)

    assert [c.name for c in resp.tool_calls] == ["get_metrics"]
    assert resp.tool_calls[0].arguments == {"ticker": "SBER"}
    assert not resp.is_final

    body = captured[0]
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert body["messages"][3]["tool_call_id"] == "call_0"
    assert body["tools"][0] == {
        "type": "function",
        "function": {"name": "get_metrics", "description": "d", "parameters": SCHEMA},
    }


def test_agent_llm_final_answer(monkeypatch):
    monkeypatch.setattr(
        openrouter, "chat_completion", lambda body, **kw: _response({"content": "Final answer."})
    )
    resp = OpenRouterAgentLLM().respond([{"role": "user", "content": "q"}], system="s", tools=[])
    assert resp.is_final
    assert resp.text == "Final answer."


def test_build_agent_backend_selection(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
    assert isinstance(build_agent().llm, OpenRouterAgentLLM)
    monkeypatch.setenv("EQUITYMIND_LLM_PROVIDER", "anthropic")
    assert isinstance(build_agent().llm, AnthropicAgentLLM)
