"""Command-line interface for EquityMind.

Examples:
    equitymind run                       # analyse the config universe, write report
    equitymind run --pptx --xlsx         # also export a PowerPoint deck + Excel workbook
    equitymind run --pptx --xlsx --notify  # export and push a Telegram digest (scheduled use)
    equitymind run AAPL MSFT --no-ai     # ad-hoc tickers, skip LLM commentary
    equitymind run --period 6mo --json   # print machine-readable JSON
    equitymind list                      # show the configured universe
    equitymind clear-cache               # wipe the on-disk price cache
    equitymind option -S 100 -K 100 -T 1 -r 0.05 --vol 0.2   # price + Greeks
    equitymind option -S 100 -K 100 -T 1 -r 0.05 --price 10.45  # implied vol
    equitymind forward -S 100 -T 0.5 -r 0.05 --futures 103   # fair value + basis
    equitymind ask "Which asset has the best Sharpe and price a 3M ATM call on it"
    equitymind sentiment "Profit surges to record" "Shares plunge on fraud probe"
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .config import get_settings
from .data.cache import PriceCache
from .logging_config import configure_logging, get_logger
from .pipeline import AnalysisReport, IntelligencePipeline
from .reporting.report_generator import ReportGenerator

logger = get_logger(__name__)


def _report_to_json(report: AnalysisReport) -> dict:
    return {
        "generated_at": report.generated_at,
        "ai_provider": report.ai_provider,
        "ai_model": report.ai_model,
        "assets": {
            ticker: {
                "metrics": a.metrics.to_payload(),
                "commentary": a.commentary.to_dict() if a.commentary else None,
                "backtest": a.backtest.to_dict() if a.backtest else None,
                "fundamentals": a.fundamentals.to_payload() if a.fundamentals else None,
            }
            for ticker, a in report.assets.items()
        },
        "comparison": report.comparison.to_payload() if report.comparison else None,
        "portfolio": report.portfolio.to_dict() if report.portfolio else None,
        "alerts": [al.to_dict() for al in report.alerts],
        "failures": report.failures,
    }


def _print_summary(report: AnalysisReport) -> None:
    print(f"\nEquityMind — {report.generated_at}")
    print(f"AI provider: {report.ai_provider} ({report.ai_model})")
    if report.comparison and report.comparison.entries:
        print("\nRanking (reward/risk):")
        for e in report.comparison.entries:
            ret = "n/a" if e.return_pct is None else f"{e.return_pct:+.2f}%"
            ratio = "n/a" if e.reward_risk_ratio is None else f"{e.reward_risk_ratio}"
            print(
                f"  {e.rank}. {e.ticker:<8} return={ret:<9} "
                f"vol={e.annualized_volatility_pct:.1f}% risk={e.risk_score} "
                f"R/R={ratio} [{e.trend}]"
            )
    if report.portfolio is not None:
        p = report.portfolio
        print(f"\nPortfolio (avg correlation {p.average_correlation:+.2f}, {p.observations} obs):")
        for alloc in p.allocations.values():
            ret = (
                "n/a" if alloc.expected_return_pct is None else f"{alloc.expected_return_pct:+.1f}%"
            )
            shp = "n/a" if alloc.sharpe is None else f"{alloc.sharpe}"
            print(
                f"  {alloc.label:<26} return={ret:<8} vol={alloc.volatility_pct:.1f}% Sharpe={shp}"
            )
    if report.alerts:
        print("\nAlerts:")
        for a in report.alerts:
            print(f"  [{a.severity.upper()}] {a.message}")
    if report.failures:
        print("\nFailed to load:")
        for t, r in report.failures.items():
            print(f"  {t}: {r}")


def _cmd_run(args: argparse.Namespace) -> int:
    settings = get_settings(args.config)
    if args.period:
        settings.data.period = args.period
    if args.interval:
        settings.data.interval = args.interval

    pipeline = IntelligencePipeline(settings)
    report = pipeline.run(
        tickers=args.tickers or None,
        with_commentary=not args.no_ai,
        with_backtest=not args.no_backtest,
        return_basis=args.return_basis,
    )

    if args.json:
        print(json.dumps(_report_to_json(report), indent=2, default=str))
        return 0

    _print_summary(report)

    out_dir = settings.reporting.output_dir
    if not args.no_report:
        gen = ReportGenerator(out_dir)
        path = gen.write_report(report, include_charts=settings.reporting.include_charts)
        print(f"\nMarkdown report: {path}")
    if args.pptx or settings.reporting.export_pptx:
        from .reporting.powerpoint import PowerPointGenerator

        path = PowerPointGenerator(out_dir).write_deck(
            report, include_charts=settings.reporting.include_charts
        )
        print(f"PowerPoint deck: {path}")
    if args.xlsx or settings.reporting.export_xlsx:
        from .reporting.excel import ExcelGenerator

        path = ExcelGenerator(out_dir).write_workbook(report)
        print(f"Excel workbook: {path}")
    if args.notify:
        from .notifications import notify_report

        ok = notify_report(report)
        print("Telegram notification: " + ("sent" if ok else "skipped/failed"))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    settings = get_settings(args.config)
    print("Configured universe:")
    for a in settings.universe:
        print(f"  {a.ticker:<10} {a.asset_class:<8} {a.name}")
    return 0


def _cmd_clear_cache(args: argparse.Namespace) -> int:
    settings = get_settings(args.config)
    cache = PriceCache(settings.data.cache_dir, settings.data.cache_ttl_minutes)
    removed = cache.clear()
    print(f"Removed {removed} cache file(s) from {settings.data.cache_dir}")
    return 0


def _cmd_option(args: argparse.Namespace) -> int:
    from .derivatives import black_scholes as bs

    option_type = "put" if args.put else "call"
    if args.price is not None:
        iv = bs.implied_volatility(
            args.price,
            args.spot,
            args.strike,
            args.expiry,
            args.rate,
            option_type=option_type,
            q=args.yield_,
        )
        result = {
            "mode": "implied_volatility",
            "option_type": option_type,
            "market_price": args.price,
            "implied_volatility": None if iv is None else round(iv, 6),
            "implied_volatility_pct": None if iv is None else round(iv * 100.0, 2),
        }
    else:
        if args.vol is None:
            print(
                "error: provide --vol to price, or --price to solve for implied volatility",
                file=sys.stderr,
            )
            return 2
        q = bs.price_and_greeks(
            args.spot,
            args.strike,
            args.expiry,
            args.rate,
            args.vol,
            option_type=option_type,
            q=args.yield_,
        )
        result = {"mode": "price", **q.to_dict()}

    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    print(
        f"\nEuropean {option_type.upper()}  S={args.spot} K={args.strike} "
        f"T={args.expiry}y r={args.rate:.4f} q={args.yield_:.4f}"
    )
    if result["mode"] == "implied_volatility":
        iv = result["implied_volatility_pct"]
        print(f"Market price: {args.price}")
        print("Implied volatility: " + ("no solution" if iv is None else f"{iv:.2f}%"))
        return 0
    print(f"Price : {result['price']:.4f}")
    print(f"Delta : {result['delta']:+.4f}")
    print(f"Gamma : {result['gamma']:+.6f}")
    print(f"Vega  : {result['vega']:.4f}   (per 1% vol: {result['vega_per_pct']:.4f})")
    print(f"Theta : {result['theta']:.4f}/yr  (per day: {result['theta_per_day']:.4f})")
    print(f"Rho   : {result['rho']:.4f}   (per 1% rate: {result['rho_per_pct']:.4f})")
    return 0


def _cmd_fundamentals(args: argparse.Namespace) -> int:
    from .data.fundamentals import fetch_fundamentals

    rows = []
    for ticker in args.tickers:
        f = fetch_fundamentals(ticker)
        if f is not None:
            rows.append(f.to_payload())
        else:
            print(f"  {ticker}: no fundamentals available", file=sys.stderr)

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    for r in rows:
        print(f"\n{r['ticker']} — {r.get('name') or ''}")
        print(f"  Sector/Industry : {r.get('sector')} / {r.get('industry')}")
        mc = r.get("market_cap")
        print(
            f"  Market cap      : {'n/a' if mc is None else f'{mc:,.0f}'} {r.get('currency') or ''}"
        )
        print(f"  P/E (trail/fwd) : {r.get('trailing_pe')} / {r.get('forward_pe')}")
        print(f"  P/B             : {r.get('price_to_book')}")
        print(f"  EPS             : {r.get('eps')}")
        print(f"  Dividend yield  : {r.get('dividend_yield_pct')}%")
        print(
            f"  ROE / margin    : {r.get('return_on_equity_pct')}% / {r.get('profit_margin_pct')}%"
        )
        print(f"  Beta            : {r.get('beta')}")
    return 0 if rows else 1


def _cmd_sentiment(args: argparse.Namespace) -> int:
    from .news import analyze_headlines

    result = analyze_headlines(args.headlines)
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return 0
    print(f"\nNews sentiment: {result.label.upper()} (mean {result.mean_score:+.2f})")
    print(f"  bullish {result.positive} · neutral {result.neutral} · bearish {result.negative}")
    for hs in result.headlines:
        print(f"  [{hs.label:<7} {hs.score:+.2f}] {hs.headline}")
    return 0


def _cmd_ask(args: argparse.Namespace) -> int:
    if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("EQUITYMIND_LLM_PROVIDER") == "anthropic"):
        print(
            "The AI agent needs an Anthropic API key. Set ANTHROPIC_API_KEY in your "
            "environment (see .env.example) and try again.",
            file=sys.stderr,
        )
        return 2

    from .agent import build_agent

    settings = get_settings(args.config)
    if args.period:
        settings.data.period = args.period

    # Build the analysis context the agent reasons over (no LLM commentary needed).
    pipeline = IntelligencePipeline(settings)
    report = pipeline.run(
        tickers=args.tickers or None,
        with_commentary=False,
        with_backtest=False,
    )

    question = " ".join(args.question)
    agent = build_agent(report, model=settings.ai.model, max_steps=args.max_steps)
    result = agent.ask(question)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
        return 0
    print(f"\nQ: {question}\n")
    print(result.answer)
    if args.show_steps and result.steps:
        print("\nTool calls:")
        for s in result.steps:
            print(f"  · {s.tool}({json.dumps(s.arguments, default=str)})")
    return 0


def _cmd_forward(args: argparse.Namespace) -> int:
    from .derivatives import forwards

    quote = forwards.analyze_forward(
        args.spot,
        args.expiry,
        args.rate,
        income_yield=args.yield_,
        observed_futures=args.futures,
    )
    if args.json:
        print(json.dumps(quote.to_dict(), indent=2, default=str))
        return 0
    print(
        f"\nForward/futures  S={args.spot} T={args.expiry}y r={args.rate:.4f} q={args.yield_:.4f}"
    )
    print(f"Fair forward price: {quote.fair_forward:.4f}")
    print(f"Fair basis (fair − spot): {quote.fair_basis:+.4f}")
    if args.futures is not None:
        print(f"Observed futures: {args.futures}")
        print(f"Basis (observed − spot): {quote.basis:+.4f}")
        carry = quote.implied_carry
        print("Implied carry: " + ("n/a" if carry is None else f"{carry * 100:.2f}%"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="equitymind", description="AI Market Intelligence System")
    parser.add_argument("--config", help="Path to config YAML", default=None)
    parser.add_argument("--log-level", default=None, help="DEBUG / INFO / WARNING / ERROR")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the analysis pipeline")
    run.add_argument("tickers", nargs="*", help="Tickers (default: config universe)")
    run.add_argument("--period", help="Override data period (e.g. 6mo, 1y)")
    run.add_argument("--interval", help="Override bar interval (e.g. 1d)")
    run.add_argument("--return-basis", default="cumulative", help="'cumulative' or e.g. '30d'")
    run.add_argument("--no-ai", action="store_true", help="Skip LLM commentary")
    run.add_argument("--no-backtest", action="store_true", help="Skip trend backtest")
    run.add_argument("--no-report", action="store_true", help="Don't write a markdown report")
    run.add_argument("--pptx", action="store_true", help="Also export a PowerPoint deck")
    run.add_argument("--xlsx", action="store_true", help="Also export an Excel workbook")
    run.add_argument(
        "--notify", action="store_true", help="Send a Telegram digest (needs credentials)"
    )
    run.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    run.set_defaults(func=_cmd_run)

    lst = sub.add_parser("list", help="List the configured universe")
    lst.set_defaults(func=_cmd_list)

    clr = sub.add_parser("clear-cache", help="Delete cached price data")
    clr.set_defaults(func=_cmd_clear_cache)

    opt = sub.add_parser("option", help="Black–Scholes option price + Greeks (or implied vol)")
    opt.add_argument("--spot", "-S", type=float, required=True, help="Underlying spot price")
    opt.add_argument("--strike", "-K", type=float, required=True, help="Strike price")
    opt.add_argument("--expiry", "-T", type=float, required=True, help="Time to expiry in years")
    opt.add_argument("--rate", "-r", type=float, default=0.0, help="Risk-free rate (e.g. 0.05)")
    opt.add_argument("--vol", type=float, default=None, help="Annualised volatility (e.g. 0.2)")
    opt.add_argument("--yield", dest="yield_", type=float, default=0.0, help="Dividend/carry yield")
    opt.add_argument("--put", action="store_true", help="Price a put (default: call)")
    opt.add_argument("--price", type=float, default=None, help="Market price → solve implied vol")
    opt.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    opt.set_defaults(func=_cmd_option)

    fun = sub.add_parser(
        "fundamentals", help="Fetch fundamentals (P/E, EPS, sector...) for tickers"
    )
    fun.add_argument("tickers", nargs="+", help="One or more tickers")
    fun.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    fun.set_defaults(func=_cmd_fundamentals)

    ask = sub.add_parser("ask", help="Ask the tool-using AI agent about the analysed universe")
    ask.add_argument("question", nargs="+", help="Natural-language question")
    ask.add_argument(
        "--tickers", nargs="*", help="Instruments to analyse (default: config universe)"
    )
    ask.add_argument("--period", help="Override data period (e.g. 6mo, 1y)")
    ask.add_argument("--max-steps", type=int, default=8, help="Max agent tool-call steps")
    ask.add_argument("--show-steps", action="store_true", help="Print the tool-call trace")
    ask.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    ask.set_defaults(func=_cmd_ask)

    sen = sub.add_parser("sentiment", help="Score the sentiment of news headlines")
    sen.add_argument("headlines", nargs="+", help="One or more headlines (quote each)")
    sen.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    sen.set_defaults(func=_cmd_sentiment)

    fwd = sub.add_parser("forward", help="Forward/futures fair value, basis and implied carry")
    fwd.add_argument("--spot", "-S", type=float, required=True, help="Underlying spot price")
    fwd.add_argument("--expiry", "-T", type=float, required=True, help="Time to delivery in years")
    fwd.add_argument("--rate", "-r", type=float, default=0.0, help="Financing rate (e.g. 0.05)")
    fwd.add_argument(
        "--yield",
        dest="yield_",
        type=float,
        default=0.0,
        help="Income yield (dividend/foreign rate)",
    )
    fwd.add_argument(
        "--futures", type=float, default=None, help="Observed futures price for basis/carry"
    )
    fwd.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    fwd.set_defaults(func=_cmd_forward)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
