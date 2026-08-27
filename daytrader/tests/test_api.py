from pathlib import Path

from fastapi.testclient import TestClient

from daytrader.config import BotConfig
from daytrader.dashboard.app import create_app
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
        assert "Paper trading only" in state["disclaimer"]


def test_replay_and_pause(tmp_path: Path):
    cfg = BotConfig(data_dir=tmp_path, bar_interval_ms=1)
    app = create_app(cfg, mode="demo", autostart=False)
    with TestClient(app) as client:
        engine = client.app  # noqa
        from daytrader.dashboard import app as dash

        for bar in list(ScenarioFeed(cfg).bars())[:40]:
            dash.runner.engine.on_bar(bar)
        state = client.get("/api/state").json()
        assert state["bars_processed"] == 40
        assert client.post("/api/pause").json()["paused"] is True
        patched = client.post("/api/risk", json={"risk_dollars": 50, "reward_dollars": 50, "max_daily_loss": 150})
        assert patched.json()["max_daily_loss"] == 150
        flags = client.post("/api/assets", json={"crypto": False}).json()
        assert flags["enabled_assets"]["crypto"] is False
