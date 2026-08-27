from datetime import timedelta

from daytrader.config import AssetClass, BotConfig, Side
from daytrader.indicators import atr, opening_range, vwap
from daytrader.strategy import OpeningRangeStrategy
from tests.conftest import bar, ts


def _range_then(close, **kwargs):
    cfg = BotConfig()
    strat = OpeningRangeStrategy(cfg)
    t0 = ts(9, 30)
    bars = []
    prices = [500.0, 501.2, 499.4, close]
    for i, px in enumerate(prices):
        t = t0 + timedelta(minutes=5 * i)
        vol = 3_000_000 if i == 3 else 400_000
        b = bar(
            close=px,
            open_=prices[i - 1] if i else px,
            high=px * 1.0004,
            low=px * 0.9996,
            volume=vol,
            t=t,
            **kwargs,
        )
        bars.append(b)
        signals = strat.on_bar(b)
    return signals, bars


def test_opening_range_long_breakout():
    signals, _ = _range_then(503.0)
    longs = [s for s in signals if s.side is Side.LONG and s.asset_class is AssetClass.STOCK]
    assert longs
    assert longs[0].entry == 503.0
    assert longs[0].stop < longs[0].entry


def test_opening_range_ignores_inside_bar():
    signals, _ = _range_then(500.02)
    stocks = [s for s in signals if s.asset_class is AssetClass.STOCK]
    assert stocks == []


def test_option_signal_from_equity_underlying():
    signals, _ = _range_then(503.0)
    opts = [s for s in signals if s.asset_class is AssetClass.OPTION]
    assert opts
    assert opts[0].option_symbol.startswith("SPY")
    assert opts[0].entry * opts[0].multiplier <= 200.01


def test_only_one_equity_signal_per_session():
    cfg = BotConfig()
    strat = OpeningRangeStrategy(cfg)
    t0 = ts(9, 30)
    last = []
    prices = [500.0, 501.3, 499.2, 504.0, 505.0, 506.0, 507.0, 508.0]
    for i, px in enumerate(prices):
        b = bar(close=px, high=px * 1.001, low=px * 0.999, volume=3_000_000, t=t0 + timedelta(minutes=5 * i))
        last = strat.on_bar(b)
    stocks = [s for s in last if s.asset_class is AssetClass.STOCK]
    assert stocks == []


def test_atr_and_vwap():
    t0 = ts()
    bars = [
        bar(close=100 + i, high=101 + i, low=99 + i, open_=100 + i, volume=1000, t=t0 + timedelta(minutes=i))
        for i in range(16)
    ]
    assert atr(bars, 14) is not None
    assert vwap(bars) > 100
    lo, hi = opening_range(bars, 3)
    assert lo <= hi
