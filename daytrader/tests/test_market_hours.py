from datetime import datetime
from zoneinfo import ZoneInfo

from daytrader.config import AssetClass, BotConfig
from daytrader.market_hours import can_enter, cash_session_open, should_flatten

ET = ZoneInfo("America/New_York")
cfg = BotConfig()


def test_cash_hours():
    open_ts = datetime(2026, 8, 26, 10, 0, tzinfo=ET)
    closed = datetime(2026, 8, 26, 18, 0, tzinfo=ET)
    weekend = datetime(2026, 8, 22, 11, 0, tzinfo=ET)
    assert cash_session_open(open_ts)
    assert not cash_session_open(closed)
    assert not cash_session_open(weekend)


def test_crypto_follows_cash_hours():
    night = datetime(2026, 8, 26, 22, 0, tzinfo=ET)
    assert not can_enter(night, AssetClass.CRYPTO, cfg)
    assert should_flatten(night, AssetClass.CRYPTO, cfg)


def test_stocks_flatten_before_close():
    late = datetime(2026, 8, 26, 15, 56, tzinfo=ET)
    assert should_flatten(late, AssetClass.STOCK, cfg)
    assert should_flatten(late, AssetClass.METAL, cfg)
    assert should_flatten(late, AssetClass.OPTION, cfg)
    assert not can_enter(late, AssetClass.STOCK, cfg)


def test_need_opening_range_before_entry():
    too_early = datetime(2026, 8, 26, 9, 35, tzinfo=ET)
    assert cash_session_open(too_early)
    assert not can_enter(too_early, AssetClass.STOCK, cfg)


def test_hourly_bars_flatten_on_15_hour_bar():
    hourly = BotConfig(bar_minutes=60)
    fifteen = datetime(2026, 8, 26, 15, 30, tzinfo=ET)
    fourteen = datetime(2026, 8, 26, 14, 30, tzinfo=ET)
    assert should_flatten(fifteen, AssetClass.STOCK, hourly)
    assert not can_enter(fifteen, AssetClass.STOCK, hourly)
    assert not should_flatten(fourteen, AssetClass.STOCK, hourly)
