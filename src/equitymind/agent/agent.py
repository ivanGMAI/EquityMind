"""The tool-using analysis agent.

:class:`AnalysisAgent` runs the classic agentic loop: the model is given a
question plus the available tool schemas; it decides which tools to call; the
agent executes them against the real analytics and feeds the results back; the
loop repeats until the model produces a final, grounded answer. Every tool call
is recorded so the reasoning is fully auditable.

The agent is deliberately constrained to the same compliance stance as the rest
of the system — it explains and quantifies, it never advises or predicts prices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .llm import AgentLLM, build_tool_result_message
from .tools import ToolRegistry, build_tools

if TYPE_CHECKING:  # avoid an import cycle; only needed for type hints
    from ..pipeline import AnalysisReport

logger = get_logger(__name__)

AGENT_SYSTEM_PROMPT = """\
You are a quantitative market-analysis assistant for a bank's global-markets desk. \
You answer questions about the instruments under analysis and about derivatives by \
CALLING THE PROVIDED TOOLS and reasoning on their numeric results — never invent \
figures. Prefer tools over recollection: look up metrics, the ranking, the \
portfolio, or price an option, then explain.

Compliance (hard rules): do NOT give investment advice (no buy/sell/hold), do NOT \
predict prices or imply targets. Describe and explain what the data shows, note \
uncertainty, and be concise and well-structured. When you have enough information, \
give a clear final answer grounded in the tool outputs.

Answer in the language of the user's question (in Russian for a Russian question)."""


@dataclass(slots=True)
class AgentTrace:
    """One executed tool call and its result."""

    tool: str
    arguments: dict
    result: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class AgentResult:
    """The agent's final answer plus the tool-call trace behind it."""

    question: str
    answer: str
    provider: str
    model: str
    steps: list[AgentTrace] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "provider": self.provider,
            "model": self.model,
            "steps": [s.to_dict() for s in self.steps],
        }


class AnalysisAgent:
    """Drive a tool-using conversation to answer a market-analysis question."""

    def __init__(
        self,
        llm: AgentLLM,
        *,
        report: AnalysisReport | None = None,
        registry: ToolRegistry | None = None,
        max_steps: int = 8,
    ) -> None:
        self.llm = llm
        self.registry = registry or build_tools(report)
        self.max_steps = max_steps

    def ask(self, question: str) -> AgentResult:
        """Answer ``question``, calling tools as needed (bounded by ``max_steps``)."""
        messages: list[dict] = [{"role": "user", "content": question}]
        tools = self.registry.schemas()
        trace: list[AgentTrace] = []

        for _ in range(self.max_steps):
            resp = self.llm.respond(messages, system=AGENT_SYSTEM_PROMPT, tools=tools)
            messages.append({"role": "assistant", "content": resp.assistant_content})
            if resp.is_final:
                return self._result(question, resp.text or "", trace)

            results: list[tuple[str, dict]] = []
            for call in resp.tool_calls:
                logger.info("Agent tool call: %s(%s)", call.name, call.arguments)
                result = self.registry.execute(call.name, call.arguments)
                trace.append(AgentTrace(tool=call.name, arguments=call.arguments, result=result))
                results.append((call.id, result))
            messages.append(build_tool_result_message(results))

        return self._result(question, "(agent stopped: reached the step limit)", trace)

    def _result(self, question: str, answer: str, trace: list[AgentTrace]) -> AgentResult:
        return AgentResult(
            question=question,
            answer=answer,
            provider=self.llm.name,
            model=self.llm.model,
            steps=trace,
        )
