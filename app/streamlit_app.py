"""EquityMind — Streamlit dashboard.

Run with:
    streamlit run app/streamlit_app.py

Provides asset selection, interactive charts, quantitative metrics, AI-generated
commentary, cross-asset comparison and one-click report export — a lightweight
front end over :class:`equitymind.pipeline.IntelligencePipeline`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the package importable when launched via `streamlit run` without install.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from equitymind.config import get_settings  # noqa: E402
from equitymind.derivatives import black_scholes as bs  # noqa: E402
from equitymind.derivatives import payoff as pf  # noqa: E402
from equitymind.pipeline import AnalysisReport, IntelligencePipeline  # noqa: E402
from equitymind.reporting import charts  # noqa: E402
from equitymind.reporting.report_generator import ReportGenerator  # noqa: E402

st.set_page_config(page_title="EquityMind", page_icon="📈", layout="wide")


@st.cache_resource
def _load_settings(config_path: str | None):
    return get_settings(config_path)


def _run_pipeline(
    settings, tickers, period, interval, with_ai, with_backtest, return_basis
) -> AnalysisReport:
    settings.data.period = period
    settings.data.interval = interval
    pipeline = IntelligencePipeline(settings)
    return pipeline.run(
        tickers=tickers or None,
        with_commentary=with_ai,
        with_backtest=with_backtest,
        return_basis=return_basis,
    )


def _sidebar(settings):
    st.sidebar.title("📈 EquityMind")
    st.sidebar.caption("AI Market Intelligence")

    universe = settings.tickers()
    selected = st.sidebar.multiselect(
        "Instruments", options=universe, default=universe[: min(4, len(universe))]
    )
    custom = st.sidebar.text_input("Add tickers (comma-separated)", "")
    if custom.strip():
        selected = selected + [t.strip().upper() for t in custom.split(",") if t.strip()]

    period = st.sidebar.selectbox(
        "History window", ["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], index=3
    )
    interval = st.sidebar.selectbox("Bar interval", ["1d", "1wk", "1mo"], index=0)
    return_basis = st.sidebar.selectbox("Ranking basis", ["cumulative", "30d", "7d", "1d"], index=0)

    with_ai = st.sidebar.checkbox("Generate AI commentary", value=True)
    with_backtest = st.sidebar.checkbox("Run trend backtest", value=True)

    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"AI backend: **{'Claude (' + settings.ai.model + ')' if has_key else 'offline mock'}**"
    )
    if not has_key:
        st.sidebar.info("Set ANTHROPIC_API_KEY for LLM-generated commentary.")

    run = st.sidebar.button("Run analysis", type="primary", use_container_width=True)
    return selected, period, interval, return_basis, with_ai, with_backtest, run


def _render_ranking(report: AnalysisReport) -> None:
    comp = report.comparison
    if comp is None or not comp.entries:
        return
    st.subheader("Cross-asset ranking")
    st.caption(f"Reward-to-risk ratio · basis: {comp.return_basis}")
    st.dataframe(comp.to_dataframe(), use_container_width=True, hide_index=True)


def _render_alerts(report: AnalysisReport) -> None:
    if not report.alerts:
        return
    st.subheader("⚠️ Alerts")
    for a in report.alerts:
        (st.error if a.severity == "critical" else st.warning)(a.message)


def _render_comparison_chart(report: AnalysisReport) -> None:
    if len(report.assets) < 2:
        return
    histories = {t: a.history for t, a in report.assets.items()}
    st.subheader("Relative performance")
    st.pyplot(charts.comparison_chart(histories), use_container_width=True)


def _render_agent(report: AnalysisReport) -> None:
    st.subheader("🤖 Ask the AI analyst")
    st.caption(
        "A tool-using agent reasons over the analysed instruments and derivatives — "
        "e.g. “Which asset has the best Sharpe, and price a 3-month ATM call on it at 25% vol.”"
    )
    question = st.text_input("Question", key="agent_q", label_visibility="collapsed")
    if not st.button("Ask", key="agent_btn"):
        return
    if not question.strip():
        st.warning("Enter a question.")
        return
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("EQUITYMIND_LLM_PROVIDER") == "anthropic"):
        st.info("Set ANTHROPIC_API_KEY to enable the AI agent.")
        return
    from equitymind.agent import build_agent

    with st.spinner("The agent is reasoning and calling tools…"):
        result = build_agent(report).ask(question)
    st.markdown(result.answer)
    if result.steps:
        with st.expander(f"Tool calls ({len(result.steps)})"):
            for s in result.steps:
                st.markdown(f"- `{s.tool}` — {s.arguments}")


def _render_portfolio(report: AnalysisReport) -> None:
    p = report.portfolio
    if p is None or not p.allocations:
        return
    st.subheader("Portfolio analytics")
    st.caption(
        f"{len(p.tickers)} instruments · {p.observations} overlapping obs · "
        f"avg pairwise correlation {p.average_correlation:+.2f} · "
        f"annualised, risk-free {p.risk_free_rate * 100:.1f}%"
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**Correlation matrix**")
        corr_df = pd.DataFrame(p.correlation).reindex(index=p.tickers, columns=p.tickers)
        st.dataframe(
            corr_df.style.background_gradient(cmap="RdYlGn_r", vmin=-1, vmax=1).format("{:+.2f}"),
            use_container_width=True,
        )
    with right:
        st.markdown("**Reference allocations**")
        rows = [
            {
                "Allocation": a.label,
                "Return %": a.expected_return_pct,
                "Vol %": a.volatility_pct,
                "Sharpe": a.sharpe,
            }
            for a in p.allocations.values()
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "Min-variance & max-Sharpe are unconstrained (may imply shorts); "
        "risk-parity is long-only. Expected returns are historical means, not forecasts."
    )


def _build_strategy(kind, S, K1, K2, T, r, sigma, q):
    """Return (legs, spot_entry) with premiums priced from Black–Scholes."""
    c1 = bs.bs_price(S, K1, T, r, sigma, option_type="call", q=q)
    p1 = bs.bs_price(S, K1, T, r, sigma, option_type="put", q=q)
    if kind == "Long call":
        return pf.long_call(K1, c1)
    if kind == "Long put":
        return pf.long_put(K1, p1)
    if kind == "Straddle":
        return pf.straddle(K1, c1, p1)
    if kind == "Covered call":
        return pf.covered_call(S, K1, c1)
    if kind == "Protective put":
        return pf.protective_put(S, K1, p1)
    if kind == "Bull call spread":
        c2 = bs.bs_price(S, K2, T, r, sigma, option_type="call", q=q)
        return pf.bull_call_spread(K1, K2, c1, c2)
    return pf.long_call(K1, c1)


def _net_greeks(legs, S, T, r, sigma, q):
    net = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0}
    for leg in legs:
        if leg.kind == "underlying":
            net["delta"] += leg.quantity
            continue
        gq = bs.price_and_greeks(S, leg.strike, T, r, sigma, option_type=leg.kind, q=q)
        net["delta"] += leg.quantity * gq.delta
        net["gamma"] += leg.quantity * gq.gamma
        net["vega"] += leg.quantity * gq.vega_per_pct
        net["theta"] += leg.quantity * gq.theta_per_day
    return net


def _render_options_lab(settings) -> None:
    st.caption("European Black–Scholes pricing, Greeks and strategy payoff at expiry.")
    c = st.columns(6)
    kind = c[0].selectbox(
        "Strategy",
        ["Long call", "Long put", "Straddle", "Covered call", "Protective put", "Bull call spread"],
    )
    S = c[1].number_input("Spot", value=100.0, min_value=0.01, step=1.0)
    K1 = c[2].number_input("Strike", value=100.0, min_value=0.01, step=1.0)
    K2 = c[3].number_input(
        "Upper strike",
        value=110.0,
        min_value=0.01,
        step=1.0,
        disabled=(kind != "Bull call spread"),
    )
    T = c[4].number_input("Expiry (yrs)", value=0.5, min_value=0.001, step=0.25)
    sigma = c[5].number_input("Vol σ", value=0.25, min_value=0.001, step=0.05)
    c2 = st.columns(6)
    r = c2[0].number_input("Rate r", value=settings.analytics.risk_free_rate, step=0.01)
    q = c2[1].number_input("Yield q", value=0.0, step=0.01)

    legs = _build_strategy(kind, S, K1, K2, T, r, sigma, q)
    spots = np.linspace(0.5 * S, 1.5 * S, 400)
    summ = pf.strategy_summary(legs, spots)
    greeks = _net_greeks(legs, S, T, r, sigma, q)

    m = st.columns(4)
    m[0].metric("Net debit/credit", f"{summ.net_cost:+.2f}")
    mp = "∞" if summ.max_profit_unbounded else f"{summ.max_profit:+.2f}"
    ml = "-∞" if summ.max_loss_unbounded else f"{summ.max_loss:+.2f}"
    m[1].metric("Max profit", mp)
    m[2].metric("Max loss", ml)
    be = ", ".join(f"{b:.2f}" for b in summ.breakevens) or "—"
    m[3].metric("Break-even(s)", be)

    left, right = st.columns([3, 2])
    with left:
        st.pyplot(
            charts.payoff_diagram(
                spots,
                pf.strategy_pnl(legs, spots),
                breakevens=summ.breakevens,
                spot_marker=S,
                title=f"{kind} — payoff at expiry",
            ),
            use_container_width=True,
        )
    with right:
        st.markdown("**Net Greeks**")
        st.dataframe(
            pd.DataFrame(
                {
                    "greek": ["Delta", "Gamma", "Vega (per 1%)", "Theta (per day)"],
                    "value": [greeks["delta"], greeks["gamma"], greeks["vega"], greeks["theta"]],
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("**Legs**")
        st.dataframe(
            pd.DataFrame([leg.to_dict() for leg in legs]),
            use_container_width=True,
            hide_index=True,
        )


def _render_asset(analysis) -> None:
    m = analysis.metrics
    payload = m.to_payload()
    rets = payload["returns_pct"]
    risk = payload["risk"]
    perf = payload.get("performance", {})
    tail = payload.get("tail_risk", {})
    bench = payload.get("benchmark")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Last price", f"{m.currency} {m.last_price:,.2f}")
    c2.metric("30d return", f"{rets.get('30d', 0) or 0:+.2f}%")
    c3.metric("Ann. volatility", f"{payload['volatility']['annualized_pct'] or 0:.1f}%")
    c4.metric("Risk score", f"{risk['score']}/100", risk["band"])

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Sharpe", "n/a" if perf.get("sharpe") is None else f"{perf['sharpe']:.2f}")
    s2.metric("Sortino", "n/a" if perf.get("sortino") is None else f"{perf['sortino']:.2f}")
    conf = tail.get("confidence_pct", 95)
    s3.metric(
        f"VaR {conf:g}%",
        "n/a" if tail.get("historical_var_pct") is None else f"{tail['historical_var_pct']:.2f}%",
    )
    if bench and bench.get("beta") is not None:
        s4.metric(f"β vs {bench['benchmark']}", f"{bench['beta']:.2f}")
    else:
        s4.metric("β", "n/a")

    left, right = st.columns([3, 2])
    with left:
        st.pyplot(
            charts.price_chart(analysis.history, sma_windows=(20, 50)),
            use_container_width=True,
        )
    with right:
        st.markdown(f"**Trend:** `{payload['trend']['classification']}`")
        st.caption(payload["trend"]["rationale"])
        table = {
            "1d": rets.get("1d"),
            "7d": rets.get("7d"),
            "30d": rets.get("30d"),
            "Cumulative": payload["cumulative_return_pct"],
            "Ann. return (CAGR)": perf.get("annualized_return_pct"),
            "Max drawdown": risk.get("max_drawdown_pct"),
            f"CVaR {conf:g}% (hist)": tail.get("historical_cvar_pct"),
            f"α vs {bench['benchmark']}" if bench else "α": (
                bench.get("alpha_annual_pct") if bench else None
            ),
        }
        st.dataframe(
            pd.DataFrame({"metric": list(table), "value (%)": list(table.values())}),
            use_container_width=True,
            hide_index=True,
        )

    commentary = analysis.commentary
    if commentary is not None:
        st.markdown("#### 🧠 AI Analyst Commentary")
        st.caption(f"Source: {commentary.provider} ({commentary.model})")
        st.markdown(f"**Summary** — {commentary.summary}")
        st.markdown(f"**Trend explanation** — {commentary.trend_explanation}")
        st.markdown(f"**Risk analysis** — {commentary.risk_analysis}")
        st.markdown("**Key signals**")
        for s in commentary.key_signals:
            st.markdown(f"- {s}")
        if commentary.compliance_flags:
            st.warning(f"Compliance flags: {commentary.compliance_flags}")

    bt = analysis.backtest
    if bt is not None:
        with st.expander("Trend backtest (SMA crossover)"):
            st.dataframe(
                pd.DataFrame([bt.to_dict()]).T.rename(columns={0: "value"}),
                use_container_width=True,
            )


def main() -> None:
    config_path = os.getenv("EQUITYMIND_CONFIG")
    settings = _load_settings(config_path)
    selected, period, interval, return_basis, with_ai, with_backtest, run = _sidebar(settings)

    st.title("Market Intelligence Dashboard")
    st.caption("Quantitative analytics with advice-free, LLM-generated market commentary.")

    with st.expander("🧮 Options lab — Black–Scholes pricing & payoff", expanded=False):
        _render_options_lab(settings)

    if run:
        if not selected:
            st.warning("Select at least one instrument.")
            return
        with st.spinner("Fetching data and running analysis…"):
            report = _run_pipeline(
                settings, selected, period, interval, with_ai, with_backtest, return_basis
            )
        st.session_state["report"] = report

    report = st.session_state.get("report")
    if report is None:
        st.info("Configure instruments in the sidebar and click **Run analysis**.")
        return

    _render_ranking(report)
    _render_alerts(report)
    _render_comparison_chart(report)
    _render_portfolio(report)
    _render_agent(report)

    st.subheader("Per-instrument analysis")
    if report.assets:
        tabs = st.tabs(list(report.assets.keys()))
        for tab, (_ticker, analysis) in zip(tabs, report.assets.items(), strict=False):
            with tab:
                _render_asset(analysis)

    if report.failures:
        st.error(f"Failed to load: {report.failures}")

    st.markdown("---")
    st.subheader("Export")
    b1, b2, b3 = st.columns(3)
    charts_on = settings.reporting.include_charts
    out_dir = settings.reporting.output_dir

    with b1:
        if st.button("📄 Markdown", use_container_width=True):
            path = ReportGenerator(out_dir).write_report(report, include_charts=charts_on)
            st.download_button(
                "Download .md",
                data=Path(path).read_bytes(),
                file_name=Path(path).name,
                mime="text/markdown",
                use_container_width=True,
            )
    with b2:
        if st.button("📊 PowerPoint", use_container_width=True):
            from equitymind.reporting.powerpoint import PowerPointGenerator

            path = PowerPointGenerator(out_dir).write_deck(report, include_charts=charts_on)
            st.download_button(
                "Download .pptx",
                data=Path(path).read_bytes(),
                file_name=Path(path).name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                use_container_width=True,
            )
    with b3:
        if st.button("📈 Excel", use_container_width=True):
            from equitymind.reporting.excel import ExcelGenerator

            path = ExcelGenerator(out_dir).write_workbook(report)
            st.download_button(
                "Download .xlsx",
                data=Path(path).read_bytes(),
                file_name=Path(path).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    st.caption(
        "Educational market analysis only — not investment advice. Figures are backward-looking."
    )


if __name__ == "__main__":
    main()
