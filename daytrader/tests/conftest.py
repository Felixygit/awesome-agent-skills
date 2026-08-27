from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from daytrader.config import AssetClass, BotConfig, Side
from daytrader.models import Bar, Signal

ET = ZoneInfo("America/New_York")


def ts(h=10, m=0):
    return datetime(2026, 8, 26, h, m, tzinfo=ET)


def bar(symbol="SPY", asset=AssetClass.STOCK, close=500.0, high=None, low=None, open_=None, volume=1_000_000, t=None):
    o = open_ if open_ is not None else close
    return Bar(
        symbol=symbol,
        asset_class=asset,
        ts=t or ts(),
        open=o,
        high=high if high is not None else close,
        low=low if low is not None else close,
        close=close,
        volume=volume,
    )


def long_signal(entry=100.0, stop=98.0, asset=AssetClass.STOCK, symbol="SPY"):
    return Signal(
        symbol=symbol,
        asset_class=asset,
        side=Side.LONG,
        entry=entry,
        stop=stop,
        reason="test",
        ts=ts(),
        multiplier=1.0,
        lot_size=1.0 if asset is not AssetClass.CRYPTO else 0.0001,
    )
