from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import Lock

from daytrader.models import EngineEvent, Position, SizedOrder, Trade


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rejects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def save_trade(self, trade: Trade) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO trades(id, payload) VALUES (?, ?)",
                (trade.id, json.dumps(trade.to_dict())),
            )
            self._conn.commit()

    def save_entry(self, pos: Position) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entries(id, ts, payload) VALUES (?, ?, ?)",
                (pos.id, pos.opened_at.isoformat(), json.dumps(pos.to_dict())),
            )
            self._conn.commit()

    def save_reject(self, order: SizedOrder) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO rejects(ts, payload) VALUES (?, ?)",
                (order.signal.ts.isoformat(), json.dumps(order.to_dict())),
            )
            self._conn.commit()

    def save_event(self, event: EngineEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(ts, level, message) VALUES (?, ?, ?)",
                (event.ts.isoformat(), event.level, event.message),
            )
            self._conn.commit()

    def recent_events(self, limit: int = 80) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, level, message FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"ts": r[0], "level": r[1], "message": r[2]} for r in reversed(rows)]

    def all_trades(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM trades").fetchall()
        return [json.loads(r[0]) for r in rows]

    def all_entries(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM entries ORDER BY ts").fetchall()
        return [json.loads(r[0]) for r in rows]

    def all_rejects(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM rejects ORDER BY id").fetchall()
        return [json.loads(r[0]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
