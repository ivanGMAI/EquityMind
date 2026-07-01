"""Tool-using AI agent: reasons on the real analytics via function calling.

The per-instrument :mod:`equitymind.ai` analyst writes a static commentary from a
fixed metrics brief; this package goes further — the model is given *tools* and
decides which analytics to invoke (metrics, ranking, portfolio, option pricing,
news sentiment), grounding its answer in live calculations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .agent import AGENT_SYSTEM_PROMPT, AgentResult, AgentTrace, AnalysisAgent
from .llm import (
    AgentError,
    AgentLLM,
    AgentResponse,
    AnthropicAgentLLM,
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
    """Construct an agent (Claude-backed by default) bound to an analysis report."""
    llm = llm or AnthropicAgentLLM(model=model)
    return AnalysisAgent(llm, report=report, max_steps=max_steps)
