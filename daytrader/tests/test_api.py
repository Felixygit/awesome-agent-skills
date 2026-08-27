from pathlib import Path

from fastapi.testclient import TestClient

from daytrader.config import BotConfig
from daytrader.dashboard.app import create_app
from daytrader.engine import TradingEngine
from daytrader.feeds import ScenarioFeed


def test_health_and_state(tmp_path: Path):
    cfg = BotConfig(data_dir=tmp_path, bar_interval_ms=1)
    app = create_app(cfg, mode="demo", autostart=False)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ok"] is True
        page = client.get("/")
        assert page.status_code == 200
        assert "R50" in page.text
        state = client.get("/api/state").json()
        assert state["risk_dollars"] == 50
        assert state["capital_per_trade"] == 200
        assert state["session"]["session_open"] == "09:30"
        assert "Paper trading only" in state["disclaimer"]


def test_replay_journal_and_pause(tmp_path: Path):
    cfg = BotConfig(data_dir=tmp_path, bar_interval_ms=1)
    app = create_app(cfg, mode="demo", autostart=False)
    with TestClient(app) as client:
        from daytrader.dashboard import app as dash

        for bar in list(ScenarioFeed(cfg).bars())[:40]:
            dash.runner.engine.on_bar(bar)
        state = client.get("/api/state").json()
        assert state["bars_processed"] == 40
        assert client.post("/api/pause").json()["paused"] is True
        patched = client.post(
            "/api/risk",
            json={
                "risk_dollars": 50,
                "reward_dollars": 50,
                "capital_per_trade": 200,
                "max_daily_loss": 150,
            },
        )
        assert patched.json()["capital_per_trade"] == 200
        flags = client.post("/api/assets", json={"crypto": False}).json()
        assert flags["enabled_assets"]["crypto"] is False
        journal = client.get("/api/journal").json()
        assert "trades" in journal


def test_journal_csv_after_session(tmp_path: Path):
    cfg = BotConfig(data_dir=tmp_path, slippage_bps=0)
    engine = TradingEngine(cfg)
    engine.run_bars(ScenarioFeed(cfg).bars())
    rows = engine.journal.all_trades()
    assert rows
    assert "opened_at" in rows[0]
    assert "closed_at" in rows[0]
    assert "mae" in rows[0]
    assert "mfe" in rows[0]
    assert "or_high" in rows[0]
