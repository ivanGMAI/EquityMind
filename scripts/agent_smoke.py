"""Smoke test for the tool-using agent against the live LLM backend.

Runs a minimal pipeline (2 MOEX tickers, no AI commentary) and asks the agent
one question, printing the model, the tool-call trace and the answer. Uses
whatever LLM backend the environment resolves to — handy for verifying a new
key/model/base URL without touching the API server.

Usage:
    python scripts/agent_smoke.py ["Свой вопрос агенту"]
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from equitymind.agent import build_agent  # noqa: E402
from equitymind.config import get_settings  # noqa: E402
from equitymind.pipeline import IntelligencePipeline  # noqa: E402


def main() -> None:
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "У какого актива лучший коэффициент Шарпа? Ответь одним предложением."
    )
    settings = get_settings()
    settings.data.source = "moex"
    settings.data.period = "1mo"
    settings.benchmark.ticker = "IMOEX"

    print("Running minimal pipeline (SBER, GAZP)…")
    report = IntelligencePipeline(settings).run(
        tickers=["SBER", "GAZP"], with_commentary=False, with_backtest=False
    )

    print("Asking the agent…")
    result = build_agent(report).ask(question)
    print(f"\nMODEL: {result.provider} / {result.model}")
    print(f"TOOL CALLS: {[t.tool for t in result.steps]}")
    print(f"\nANSWER:\n{result.answer}")


if __name__ == "__main__":
    main()
