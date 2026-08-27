from datetime import datetime
from zoneinfo import ZoneInfo

from daytrader.schedule import next_session_open, session_phase, session_status

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
