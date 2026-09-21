from datetime import datetime
from zoneinfo import ZoneInfo

from daytrader.config import AssetClass
from daytrader.models import Bar
from daytrader.schedule import (
    filter_bars_in_range,
    lookback_bounds,
    next_session_open,
    session_phase,
    session_status,
    week_bounds,
)

ET = ZoneInfo("America/New_York")


def test_weekday_open_phase():
    now = datetime(2026, 8, 26, 10, 15, tzinfo=ET)
    assert session_phase(now) == "open"
    st = session_status(now)
    assert st["in_session"] is True
    assert st["session_open"] == "09:30"
    assert st["session_close"] == "16:00"


def test_preopen_and_next_open():
    now = datetime(2026, 8, 26, 8, 0, tzinfo=ET)
    assert session_phase(now) == "preopen"
    nxt = next_session_open(now)
    assert nxt.hour == 9 and nxt.minute == 30
    assert nxt.date() == now.date()


def test_weekend_skips_to_monday():
    sat = datetime(2026, 8, 22, 11, 0, tzinfo=ET)
    assert session_phase(sat) == "weekend"
    nxt = next_session_open(sat)
    assert nxt.strftime("%A") == "Monday"
    assert nxt.hour == 9 and nxt.minute == 30


def test_after_close_goes_to_next_weekday():
    after = datetime(2026, 8, 26, 17, 0, tzinfo=ET)
    assert session_phase(after) == "closed"
    nxt = next_session_open(after)
    assert nxt.date() == datetime(2026, 8, 27).date()


def test_week_bounds_monday_through_now():
    now = datetime(2026, 9, 9, 20, 3, tzinfo=ET)
    start, end = week_bounds(now)
    assert start == datetime(2026, 9, 7, 0, 0, tzinfo=ET)
    assert end == now


def test_filter_bars_keeps_this_week_only():
    start, end = week_bounds(datetime(2026, 9, 9, 16, 0, tzinfo=ET))
    bars = [
        Bar("SPY", AssetClass.STOCK, datetime(2026, 9, 4, 10, 0, tzinfo=ET), 1, 1, 1, 1, 1),
        Bar("SPY", AssetClass.STOCK, datetime(2026, 9, 8, 10, 0, tzinfo=ET), 1, 1, 1, 1, 1),
        Bar("SPY", AssetClass.STOCK, datetime(2026, 9, 9, 15, 55, tzinfo=ET), 1, 1, 1, 1, 1),
    ]
    kept = filter_bars_in_range(bars, start, end)
    assert [to_et_date(b.ts) for b in kept] == ["2026-09-08", "2026-09-09"]


def to_et_date(ts):
    return ts.astimezone(ET).strftime("%Y-%m-%d")


def test_lookback_bounds_365_days():
    now = datetime(2026, 9, 9, 20, 0, tzinfo=ET)
    start, end = lookback_bounds(now, days=365)
    assert end == now
    assert start.date().isoformat() == "2025-09-09"
