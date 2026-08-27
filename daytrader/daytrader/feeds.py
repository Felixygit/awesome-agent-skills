from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from daytrader.config import AssetClass, BotConfig
from daytrader.models import Bar

ET = ZoneInfo("America/New_York")


class Feed(ABC):
    @abstractmethod
    def bars(self) -> Iterable[Bar]:
        raise NotImplementedError


def session_times(day: datetime, minutes: int = 5) -> list[datetime]:
    start = day.replace(hour=9, minute=30, second=0, microsecond=0, tzinfo=ET)
    end = day.replace(hour=16, minute=0, second=0, microsecond=0, tzinfo=ET)
    out: list[datetime] = []
    t = start
    while t < end:
        out.append(t)
        t += timedelta(minutes=minutes)
    return out


def _path(start: float, returns: list[float], n: int) -> list[float]:
    px = start
    out: list[float] = []
    for i in range(n):
        r = returns[i] if i < len(returns) else 0.0
        px = px * (1 + r)
        out.append(px)
    return out


def _chop(start: float, n: int, seed: float = 0.00015) -> list[float]:
    """Stay inside a tight range so ORB does not fire."""
    rets = []
    for i in range(n):
        rets.append(seed if i % 2 == 0 else -seed)
    return _path(start, rets, n)


class ScenarioFeed(Feed):
    """One designed setup per asset class so the $50/$50 book is easy to inspect."""

    def __init__(self, cfg: BotConfig, day: datetime | None = None):
        self.cfg = cfg
        self.day = day or datetime(2026, 8, 26, tzinfo=ET)

    def bars(self) -> Iterable[Bar]:
        times = session_times(self.day, self.cfg.bar_minutes)
        n = len(times)
        series: dict[tuple[str, AssetClass], list[float]] = {
            ("SPY", AssetClass.STOCK): _long_breakout(500.0, n),
            ("QQQ", AssetClass.STOCK): _failed_breakout(430.0, n),
            ("AAPL", AssetClass.STOCK): _chop(227.0, n, 0.00012),
            ("NVDA", AssetClass.STOCK): _chop(118.0, n, 0.00018),
            ("TSLA", AssetClass.STOCK): _chop(248.0, n, 0.0002),
            ("AMD", AssetClass.STOCK): _chop(141.0, n, 0.00016),
            ("MSFT", AssetClass.STOCK): _chop(415.0, n, 0.0001),
            ("GLD", AssetClass.METAL): _short_breakout(190.0, n),
            ("SLV", AssetClass.METAL): _chop(27.4, n, 0.00014),
            ("BTC-USD", AssetClass.CRYPTO): _long_breakout(64_000.0, n),
            ("ETH-USD", AssetClass.CRYPTO): _chop(4_200.0, n, 0.00025),
            ("SOL-USD", AssetClass.CRYPTO): _chop(148.0, n, 0.0003),
        }
        prev: dict[tuple[str, AssetClass], float] = {}
        enabled = {(s, a) for s, a in self.cfg.all_symbols}
        # Option underlyings still need stock bars even if we only trade the option.
        for symbol in self.cfg.symbols_for(AssetClass.OPTION):
            enabled.add((symbol, AssetClass.STOCK))
        for i, ts in enumerate(times):
            for key, path in series.items():
                if key not in enabled:
                    continue
                symbol, asset = key
                close = path[i]
                p = prev.get(key, close)
                vol = 3_000_000.0 if i == self.cfg.opening_bars else 450_000.0
                wick = 0.0006
                high = max(p, close) * (1 + wick)
                low = min(p, close) * (1 - wick)
                if i > self.cfg.opening_bars:
                    # Let stops/targets print through the bar without needing a close print.
                    high = max(high, close)
                    low = min(low, close)
                yield Bar(symbol, asset, ts, p, high, low, close, vol)
                prev[key] = close


def _opening() -> list[float]:
    return [0.0018, -0.0015, 0.0004]


def _long_breakout(start: float, n: int) -> list[float]:
    rets = _opening() + [0.0045] + [0.0022] * 12
    return _path(start, rets, n)


def _short_breakout(start: float, n: int) -> list[float]:
    rets = _opening() + [-0.0045] + [-0.0022] * 12
    return _path(start, rets, n)


def _failed_breakout(start: float, n: int) -> list[float]:
    rets = _opening() + [0.0045] + [0.0003, -0.0005, -0.0012, -0.012, -0.004, -0.002]
    return _path(start, rets, n)
