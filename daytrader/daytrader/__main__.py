from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from daytrader.config import load_config
from daytrader.engine import TradingEngine
from daytrader.feeds import ScenarioFeed
from daytrader.live import load_paper_feed
from daytrader.report import trade_summary
from daytrader.schedule import (
    lookback_bounds,
    next_session_open,
    seconds_until,
    session_phase,
    week_bounds,
)
from daytrader.storage import Store

ET = ZoneInfo("America/New_York")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="r50",
        description="R50 paper day trader — $200 ticket, $50 target, 09:30–16:00 ET. No live orders.",
    )
    parser.add_argument("--config", help="Path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run the dashboard + paper engine")
    serve.add_argument("--mode", choices=["demo", "paper"], default="demo")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--no-autostart", action="store_true")

    back = sub.add_parser("backtest", help="Run one session and print stats")
    back.add_argument("--mode", choices=["demo", "paper"], default="demo")
    back.add_argument(
        "--week",
        action="store_true",
        help="Replay this calendar week (Monday 00:00 ET through now) on public 5-minute bars",
    )
    back.add_argument(
        "--year",
        action="store_true",
        help="Replay the last 365 days on public 1-hour bars (5-minute Yahoo history only covers ~60 days)",
    )

    daily = sub.add_parser(
        "run-daily",
        help="Wait for each weekday 09:30 ET session, trade until 16:00, journal the book",
    )

    args = parser.parse_args(argv)
    cfg = load_config(args.config) if args.config else load_config()

    if args.cmd == "serve":
        import uvicorn
        from daytrader.dashboard.app import create_app

        host = args.host or cfg.dashboard_host
        port = args.port or cfg.dashboard_port
        app = create_app(cfg, mode=args.mode, autostart=not args.no_autostart)
        print(f"R50 paper desk on http://{host}:{port}  (mode={args.mode})")
        print("Paper only. $200 max per ticket. $50 target. Session 09:30–16:00 ET.")
        uvicorn.run(app, host=host, port=port, log_level="info")
        return 0

    if args.cmd == "backtest":
        compact = False
        if args.year:
            cfg.bar_minutes = 60
            cfg.opening_bars = 1
            start, end = lookback_bounds(datetime.now(ET), days=365)
            bars, label = load_paper_feed(cfg, start=start, end=end)
            if label == "demo-fallback":
                print(
                    "Failed to load public 1-hour bars for the last 365 days; refusing demo fallback.",
                    file=sys.stderr,
                )
                return 1
            mode = f"{label}-year-1h"
            window = {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "interval": "1h",
                "note": "Yahoo 5-minute history is ~60 days; year replay uses 1-hour bars and a 1-hour opening range.",
            }
            compact = True
        elif args.week:
            start, end = week_bounds(datetime.now(ET))
            bars, label = load_paper_feed(cfg, start=start, end=end)
            mode = f"{label}-week"
            window = {"start": start.isoformat(), "end": end.isoformat(), "interval": "5m"}
        elif args.mode == "paper":
            bars, label = load_paper_feed(cfg)
            mode = label
            window = None
        else:
            bars = ScenarioFeed(cfg).bars()
            mode = "demo"
            window = None
        engine = TradingEngine(cfg, store=Store(cfg.data_dir / "r50.sqlite"))
        engine.mode = mode
        bars = list(bars)
        bar_counts: dict[str, int] = {}
        for bar in bars:
            bar_counts[bar.symbol] = bar_counts.get(bar.symbol, 0) + 1
        engine.run_bars(bars)
        trades = []
        for trade in engine.portfolio.closed:
            row = trade.to_dict()
            row["pnl"] = trade.pnl
            trades.append(row)
        payload = {
            "mode": engine.mode,
            "window": window,
            "bars": len(bars),
            "bars_by_symbol": bar_counts,
            "portfolio": engine.portfolio.to_dict(),
            "summary": trade_summary(
                trades,
                engine.portfolio.equity_curve,
                engine.portfolio.max_drawdown,
            ),
            "journal": str(engine.journal.csv_path),
        }
        if not compact:
            payload["trades"] = trades
        print(json.dumps(payload, indent=2))
        return 0

    if args.cmd == "run-daily":
        cfg.wait_for_session = True
        print("R50 daily loop. Weekdays 09:30–16:00 America/New_York. Ctrl+C to stop.")
        while True:
            now = datetime.now(ET)
            phase = session_phase(now)
            if phase != "open":
                nxt = next_session_open(now)
                wait = min(seconds_until(now, nxt), 60.0)
                print(f"{now.isoformat()} {phase}; next open {nxt.isoformat()}; sleep {wait:.0f}s")
                time.sleep(max(wait, 1.0))
                continue
            engine = TradingEngine(cfg, store=Store(cfg.data_dir / "r50.sqlite"))
            bars, label = load_paper_feed(cfg)
            engine.mode = label
            engine.log(f"Cash session start {now.isoformat()}", "info", now)
            engine.run_bars(bars)
            print(json.dumps(engine.portfolio.to_dict()))
            while session_phase(datetime.now(ET)) == "open":
                time.sleep(30)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
