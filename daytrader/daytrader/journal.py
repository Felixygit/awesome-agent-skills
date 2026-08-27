"""Persistent research journal: entries, exits, setup context, MAE/MFE."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from threading import Lock

from daytrader.models import Trade

TRADE_FIELDS = [
    "id",
    "session_date",
    "day_of_week",
    "minutes_from_open",
    "symbol",
    "display_symbol",
    "asset_class",
    "side",
    "strategy",
    "setup_reason",
    "quantity",
    "multiplier",
    "capital_used",
    "notional",
    "entry_price",
    "exit_price",
    "stop",
    "target",
    "opened_at",
    "closed_at",
    "hold_seconds",
    "bars_held",
    "exit_reason",
    "pnl",
    "pnl_pct_capital",
    "r_multiple",
    "fees",
    "slippage_entry",
    "slippage_exit",
    "mae",
    "mfe",
    "mae_price",
    "mfe_price",
    "risk_dollars",
    "reward_dollars",
    "or_high",
    "or_low",
    "vwap",
    "atr",
    "volume",
    "volume_avg",
    "range_pct",
    "delta",
    "underlying_entry",
    "signal_id",
]


class Journal:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.root / "trades.csv"
        self._lock = Lock()

    def record_trade(self, trade: Trade) -> None:
        row = trade.to_dict()
        with self._lock:
            new_file = not self.csv_path.exists()
            with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=TRADE_FIELDS, extrasaction="ignore")
                if new_file:
                    writer.writeheader()
                writer.writerow({k: row.get(k, "") for k in TRADE_FIELDS})
            day = row.get("session_date") or "unknown"
            day_path = self.root / f"{day}.json"
            payload = {"session_date": day, "trades": []}
            if day_path.exists():
                try:
                    payload = json.loads(day_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    payload = {"session_date": day, "trades": []}
            trades = list(payload.get("trades") or [])
            trades.append(row)
            payload["trades"] = trades
            payload["trade_count"] = len(trades)
            payload["realized_pnl"] = round(sum(float(t.get("pnl") or 0) for t in trades), 2)
            wins = [t for t in trades if float(t.get("pnl") or 0) > 0]
            payload["wins"] = len(wins)
            payload["losses"] = len(trades) - len(wins)
            day_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def write_session(self, session_date: str, extra: dict) -> None:
        day_path = self.root / f"{session_date}.json"
        with self._lock:
            payload = extra
            if day_path.exists():
                try:
                    existing = json.loads(day_path.read_text(encoding="utf-8"))
                    existing.update(extra)
                    payload = existing
                except json.JSONDecodeError:
                    payload = extra
            payload["session_date"] = session_date
            day_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def all_trades(self) -> list[dict]:
        if not self.csv_path.exists():
            return []
        with self._lock, self.csv_path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
