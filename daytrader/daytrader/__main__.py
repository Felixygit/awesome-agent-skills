from __future__ import annotations

import argparse
import json
import sys

import uvicorn

from daytrader.config import load_config
from daytrader.engine import TradingEngine
from daytrader.feeds import ScenarioFeed
from daytrader.live import load_paper_feed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="r50",
        description="R50 paper day trader — $50 risk / $50 target. Never places live orders.",
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

    args = parser.parse_args(argv)
    cfg = load_config(args.config) if args.config else load_config()

    if args.cmd == "serve":
        from daytrader.dashboard.app import create_app

        host = args.host or cfg.dashboard_host
        port = args.port or cfg.dashboard_port
        app = create_app(cfg, mode=args.mode, autostart=not args.no_autostart)
        print(f"R50 paper desk on http://{host}:{port}  (mode={args.mode})")
        print("Paper trading only. $50 is a cap/target, not a guaranteed payout.")
        uvicorn.run(app, host=host, port=port, log_level="info")
        return 0

    if args.cmd == "backtest":
        engine = TradingEngine(cfg)
        if args.mode == "paper":
            bars, label = load_paper_feed(cfg)
            engine.mode = label
        else:
            bars = ScenarioFeed(cfg).bars()
            engine.mode = "demo"
        engine.run_bars(bars)
        stats = engine.portfolio.to_dict()
        print(json.dumps({"mode": engine.mode, "portfolio": stats, "trades": [t.to_dict() for t in engine.portfolio.closed]}, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
