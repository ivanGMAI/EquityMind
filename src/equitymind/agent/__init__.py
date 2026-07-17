"""Tool-using AI agent: reasons on the real analytics via function calling.

The per-instrument :mod:`equitymind.ai` analyst writes a static commentary from a
fixed metrics brief; this package goes further — the model is given *tools* and
decides which analytics to invoke (metrics, ranking, portfolio, option pricing,
news sentiment), grounding its answer in live calculations.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .agent import AGENT_SYSTEM_PROMPT, AgentResult, AgentTrace, AnalysisAgent
from .llm import (
    AgentError,
    AgentLLM,
    AgentResponse,
    AnthropicAgentLLM,
    OpenRouterAgentLLM,
    ScriptedAgentLLM,
    ToolCall,
)
from .tools import Tool, ToolRegistry, build_tools

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from ..pipeline import AnalysisReport

__all__ = [
    "AnalysisAgent",
    "AgentResult",
    "AgentTrace",
    "AGENT_SYSTEM_PROMPT",
    "AgentLLM",
    "AnthropicAgentLLM",
    "OpenRouterAgentLLM",
    "ScriptedAgentLLM",
    "AgentError",
    "AgentResponse",
    "ToolCall",
    "Tool",
    "ToolRegistry",
    "build_tools",
    "build_agent",
]


def build_agent(
    report: AnalysisReport | None = None,
    *,
    model: str = "claude-opus-4-8",
    llm: AgentLLM | None = None,
    max_steps: int = 8,
) -> AnalysisAgent:
    """Construct an agent bound to an analysis report.

    Backend resolution mirrors :func:`equitymind.ai.build_provider`: an explicit
    ``EQUITYMIND_LLM_PROVIDER`` wins; otherwise Anthropic when its key is set,
    then OpenRouter when only an ``OPENROUTER_API_KEY`` is available.
    """
    if llm is None:
        # The same env override that steers commentary model selection (config
        # applies it to ai.model) must reach the agent too.
        model = os.getenv("EQUITYMIND_LLM_MODEL") or model
        choice = (os.getenv("EQUITYMIND_LLM_PROVIDER") or "").strip().lower()
        use_openrouter = choice == "openrouter" or (
            choice != "anthropic"
            and not os.getenv("ANTHROPIC_API_KEY")
            and bool(os.getenv("OPENROUTER_API_KEY"))
        )
        llm = OpenRouterAgentLLM(model=model) if use_openrouter else AnthropicAgentLLM(model=model)
    return AnalysisAgent(llm, report=report, max_steps=max_steps)
