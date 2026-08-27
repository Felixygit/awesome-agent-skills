from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ET = ZoneInfo("America/New_York")


class AssetClass(str, Enum):
    STOCK = "stock"
    OPTION = "option"
    CRYPTO = "crypto"
    METAL = "metal"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


class OrderStatus(str, Enum):
    FILLED = "filled"
    REJECTED = "rejected"


@dataclass
class BotConfig:
    risk_dollars: float = 50.0
    reward_dollars: float = 50.0
    starting_cash: float = 50_000.0
    max_positions: int = 6
    max_daily_loss: float = 200.0
    max_daily_trades: int = 12
    slippage_bps: float = 2.0
    commission_per_fill: float = 0.0
    flatten_minutes_before_close: int = 5
    enabled_assets: dict[str, bool] = field(
        default_factory=lambda: {
            "stock": True,
            "option": True,
            "crypto": True,
            "metal": True,
        }
    )
    watchlist: dict[str, list[str]] = field(
        default_factory=lambda: {
            "stock": ["SPY", "QQQ", "AAPL", "NVDA", "TSLA", "AMD", "MSFT"],
            "option": ["SPY", "QQQ"],
            "crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
            "metal": ["GLD", "SLV"],
        }
    )
    bar_minutes: int = 5
    opening_bars: int = 3
    min_range_pct: float = 0.001
    volume_mult: float = 1.15
    atr_period: int = 14
    atr_stop_mult: float = 1.0
    max_risk_overshoot: float = 1.0
    option_min_delta: float = 0.35
    option_max_delta: float = 0.65
    option_assumed_delta: float = 0.50
    option_multiplier: int = 100
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8000
    bar_interval_ms: int = 80
    data_dir: Path = field(default_factory=lambda: Path("data"))

    def is_enabled(self, asset: AssetClass | str) -> bool:
        key = asset.value if isinstance(asset, AssetClass) else asset
        return bool(self.enabled_assets.get(key, False))

    def symbols_for(self, asset: AssetClass) -> list[str]:
        return list(self.watchlist.get(asset.value, []))

    @property
    def all_symbols(self) -> list[tuple[str, AssetClass]]:
        out: list[tuple[str, AssetClass]] = []
        for asset in AssetClass:
            if not self.is_enabled(asset):
                continue
            for symbol in self.symbols_for(asset):
                out.append((symbol, asset))
        return out


def load_config(path: str | Path | None = None) -> BotConfig:
    cfg_path = Path(path) if path else _default_config_path()
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        loaded = yaml.safe_load(cfg_path.read_text()) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config at {cfg_path} must be a mapping")
        raw = loaded
    strategy = raw.get("strategy") or {}
    options = raw.get("options") or {}
    dashboard = raw.get("dashboard") or {}
    data_dir = Path(raw.get("data_dir") or (cfg_path.parent / "data"))
    enabled = dict(BotConfig().enabled_assets)
    enabled.update(raw.get("enabled_assets") or {})
    watch = dict(BotConfig().watchlist)
    watch.update(raw.get("watchlist") or {})
    return BotConfig(
        risk_dollars=float(raw.get("risk_dollars", 50.0)),
        reward_dollars=float(raw.get("reward_dollars", 50.0)),
        starting_cash=float(raw.get("starting_cash", 50_000.0)),
        max_positions=int(raw.get("max_positions", 6)),
        max_daily_loss=float(raw.get("max_daily_loss", 200.0)),
        max_daily_trades=int(raw.get("max_daily_trades", 12)),
        slippage_bps=float(raw.get("slippage_bps", 2.0)),
        commission_per_fill=float(raw.get("commission_per_fill", 0.0)),
        flatten_minutes_before_close=int(raw.get("flatten_minutes_before_close", 5)),
        enabled_assets=enabled,
        watchlist=watch,
        bar_minutes=int(strategy.get("bar_minutes", 5)),
        opening_bars=int(strategy.get("opening_bars", 3)),
        min_range_pct=float(strategy.get("min_range_pct", 0.001)),
        volume_mult=float(strategy.get("volume_mult", 1.15)),
        atr_period=int(strategy.get("atr_period", 14)),
        atr_stop_mult=float(strategy.get("atr_stop_mult", 1.0)),
        max_risk_overshoot=float(strategy.get("max_risk_overshoot", 1.0)),
        option_min_delta=float(options.get("min_delta", 0.35)),
        option_max_delta=float(options.get("max_delta", 0.65)),
        option_assumed_delta=float(options.get("assumed_delta", 0.50)),
        option_multiplier=int(options.get("multiplier", 100)),
        dashboard_host=str(dashboard.get("host", "0.0.0.0")),
        dashboard_port=int(dashboard.get("port", 8000)),
        bar_interval_ms=int(dashboard.get("bar_interval_ms", 80)),
        data_dir=data_dir,
    )


def _default_config_path() -> Path:
    here = Path(__file__).resolve().parent.parent
    return here / "config.yaml"


CASH_OPEN = time(9, 30)
CASH_CLOSE = time(16, 0)
