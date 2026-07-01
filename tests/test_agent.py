from __future__ import annotations

from equitymind.agent.agent import AnalysisAgent
from equitymind.agent.llm import AgentLLM, AgentResponse, ScriptedAgentLLM, ToolCall
from equitymind.agent.tools import build_tools


# ---- tool registry ----------------------------------------------------------
def test_registry_lists_expected_tools():
    reg = build_tools(None)
    for name in (
        "list_instruments",
        "get_metrics",
        "get_ranking",
        "price_option",
        "news_sentiment",
    ):
        assert name in reg.names()


def test_unknown_tool_returns_error():
    assert "error" in build_tools(None).execute("does_not_exist", {})


def test_report_tools_error_without_context():
    reg = build_tools(None)
    assert "error" in reg.execute("list_instruments", {})
    assert "error" in reg.execute("get_ranking", {})


def test_pure_tools_work_without_report():
    reg = build_tools(None)
    quote = reg.execute(
        "price_option", {"spot": 100, "strike": 100, "years": 1, "rate": 0.05, "volatility": 0.2}
    )
    assert round(quote["price"], 2) == 10.45
    fwd = reg.execute("forward_price", {"spot": 100, "years": 1, "rate": 0.05})
    assert fwd["fair_forward"] > 100
    sent = reg.execute(
        "news_sentiment", {"headlines": ["profit surges", "shares plunge on losses"]}
    )
    assert "mean_score" in sent


def test_tool_execution_captures_exceptions():
    # Missing required argument -> TypeError captured, not raised.
    result = build_tools(None).execute("price_option", {"spot": 100})
    assert "error" in result


def test_report_tools_with_context(analysis_report):
    reg = build_tools(analysis_report)
    instruments = reg.execute("list_instruments", {})["instruments"]
    assert len(instruments) == len(analysis_report.assets)
    ranking = reg.execute("get_ranking", {})
    assert "ranking" in ranking
    a_ticker = next(iter(analysis_report.assets))
    metrics = reg.execute("get_metrics", {"ticker": a_ticker.lower()})  # case-insensitive
    assert metrics["ticker"] == a_ticker


# ---- agent loop -------------------------------------------------------------
def test_agent_final_only():
    agent = AnalysisAgent(ScriptedAgentLLM([("final", "Here is the answer.")]))
    result = agent.ask("hello?")
    assert result.answer == "Here is the answer."
    assert result.steps == []
    assert result.provider == "scripted"


def test_agent_runs_tools_then_answers(analysis_report):
    steps = [
        ("tool", "get_ranking", {}),
        (
            "tool",
            "price_option",
            {"spot": 100, "strike": 100, "years": 0.5, "rate": 0.05, "volatility": 0.25},
        ),
        ("final", "Ranking retrieved and option priced."),
    ]
    agent = AnalysisAgent(ScriptedAgentLLM(steps), report=analysis_report)
    result = agent.ask("rank and price")
    assert result.answer == "Ranking retrieved and option priced."
    assert [s.tool for s in result.steps] == ["get_ranking", "price_option"]
    assert "price" in result.steps[1].result


def test_agent_respects_step_limit():
    # A back-end that never finalises -> the loop must stop at max_steps.
    class AlwaysCalls(AgentLLM):
        name = "loop"
        model = "loop"

        def respond(self, messages, *, system, tools):
            return AgentResponse(
                tool_calls=[ToolCall(id="x", name="get_ranking", arguments={})],
                assistant_content={"type": "tool_use"},
            )

    agent = AnalysisAgent(AlwaysCalls(), max_steps=3)
    result = agent.ask("loop forever")
    assert len(result.steps) == 3
    assert "step limit" in result.answer


def test_agent_trace_serialises(analysis_report):
    agent = AnalysisAgent(
        ScriptedAgentLLM([("tool", "list_instruments", {}), ("final", "done")]),
        report=analysis_report,
    )
    d = agent.ask("what instruments?").to_dict()
    assert d["answer"] == "done"
    assert d["steps"][0]["tool"] == "list_instruments"
