from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager
from itertools import groupby
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from daytrader.config import AssetClass, BotConfig, load_config
from daytrader.engine import TradingEngine
from daytrader.feeds import ScenarioFeed
from daytrader.live import load_paper_feed
from daytrader.storage import Store

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE = PACKAGE_DIR / "templates" / "index.html"
STATIC = PACKAGE_DIR / "static"


class EngineRunner:
    def __init__(self, cfg: BotConfig, mode: str = "demo"):
        self.cfg = cfg
        self.mode = mode
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = TradingEngine(cfg, store=Store(cfg.data_dir / "r50.sqlite"))
        self.engine.mode = mode
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.engine.paused = False
        self.engine.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        if self.mode == "paper":
            bars, label = load_paper_feed(self.cfg)
            self.engine.mode = label
        else:
            bars = ScenarioFeed(self.cfg).bars()
            self.engine.mode = "demo"
        self.engine.log(f"Starting {self.engine.mode} session.", "info")
        interval = max(self.cfg.bar_interval_ms, 1) / 1000.0
        for _ts, group in groupby(bars, key=lambda b: b.ts):
            if self._stop.is_set():
                break
            while self.engine.paused and not self._stop.is_set():
                time.sleep(0.05)
            with self._lock:
                for bar in group:
                    self.engine.on_bar(bar)
            time.sleep(interval)
        self.engine.running = False
        self.engine.log("Session complete. Book left as-is for review.", "info")

    def pause(self) -> None:
        self.engine.stop()

    def resume(self) -> None:
        if not self._thread or not self._thread.is_alive():
            self.start()
            return
        self.engine.resume()

    def replay(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            self.engine.reset()
        self.start()


runner: EngineRunner | None = None


class AssetFlags(BaseModel):
    stock: bool | None = None
    option: bool | None = None
    crypto: bool | None = None
    metal: bool | None = None


class RiskPatch(BaseModel):
    risk_dollars: float | None = Field(default=None, gt=0, le=500)
    reward_dollars: float | None = Field(default=None, gt=0, le=500)
    max_daily_loss: float | None = Field(default=None, gt=0, le=10_000)


def create_app(cfg: BotConfig | None = None, mode: str = "demo", autostart: bool = True) -> FastAPI:
    global runner
    cfg = cfg or load_config()
    local = EngineRunner(cfg, mode=mode)
    runner = local

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if autostart:
            local.start()
        yield
        local._stop.set()
        local.engine.running = False

    app = FastAPI(title="R50 Day Trader", version="0.1.0", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return TEMPLATE.read_text(encoding="utf-8")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "mode": runner.engine.mode}

    @app.get("/api/state")
    def state() -> dict:
        return runner.engine.state()

    @app.post("/api/pause")
    def pause() -> dict:
        runner.pause()
        return {"ok": True, "paused": True}

    @app.post("/api/resume")
    def resume() -> dict:
        runner.resume()
        return {"ok": True, "paused": False}

    @app.post("/api/replay")
    def replay() -> dict:
        runner.replay()
        return {"ok": True, "mode": runner.engine.mode}

    @app.post("/api/assets")
    def assets(flags: AssetFlags) -> dict:
        payload = flags.model_dump(exclude_none=True)
        for key, value in payload.items():
            runner.cfg.enabled_assets[key] = bool(value)
        return {"ok": True, "enabled_assets": runner.cfg.enabled_assets}

    @app.post("/api/risk")
    def risk(patch: RiskPatch) -> dict:
        if patch.risk_dollars is not None:
            runner.cfg.risk_dollars = float(patch.risk_dollars)
        if patch.reward_dollars is not None:
            runner.cfg.reward_dollars = float(patch.reward_dollars)
        if patch.max_daily_loss is not None:
            runner.cfg.max_daily_loss = float(patch.max_daily_loss)
        return {
            "ok": True,
            "risk_dollars": runner.cfg.risk_dollars,
            "reward_dollars": runner.cfg.reward_dollars,
            "max_daily_loss": runner.cfg.max_daily_loss,
        }

    @app.post("/api/flatten")
    def flatten() -> dict:
        engine = runner.engine
        if engine.last_ts is None:
            raise HTTPException(400, "No session to flatten")
        from daytrader.models import Bar

        dummy = Bar("FLAT", AssetClass.STOCK, engine.last_ts, 0, 0, 0, 0, 0)
        for pos in list(engine.portfolio.positions.values()):
            engine._close(pos, dummy, "manual-flatten")
        engine.log("Manual flatten: all positions closed.", "warn", engine.last_ts)
        return {"ok": True}

    return app
