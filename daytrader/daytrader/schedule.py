from __future__ import annotations

from datetime import datetime, timedelta

from daytrader.config import CASH_CLOSE, CASH_OPEN, BotConfig
from daytrader.market_hours import is_weekday, session_close, session_open, to_et

ET_OPEN = CASH_OPEN
ET_CLOSE = CASH_CLOSE


def in_cash_session(ts: datetime) -> bool:
    if not is_weekday(ts):
        return False
    local = to_et(ts)
    return session_open(ts) <= local < session_close(ts)


def session_phase(ts: datetime) -> str:
    local = to_et(ts)
    if not is_weekday(local):
        return "weekend"
    if local < session_open(local):
        return "preopen"
    if local < session_close(local):
        return "open"
    return "closed"


def next_session_open(ts: datetime) -> datetime:
    local = to_et(ts)
    candidate = session_open(local)
    if is_weekday(local) and local < candidate:
        return candidate
    day = local + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return session_open(day)


def seconds_until(ts: datetime, target: datetime) -> float:
    return max(0.0, (target - to_et(ts)).total_seconds())


def session_status(ts: datetime, cfg: BotConfig | None = None) -> dict:
    local = to_et(ts)
    phase = session_phase(local)
    nxt = next_session_open(local)
    close = session_close(local) if phase == "open" else None
    return {
        "phase": phase,
        "in_session": phase == "open",
        "now_et": local.isoformat(),
        "session_open": "09:30",
        "session_close": "16:00",
        "timezone": "America/New_York",
        "weekdays_only": True,
        "next_open": nxt.isoformat(),
        "next_close": close.isoformat() if close else None,
        "seconds_to_open": 0 if phase == "open" else seconds_until(local, nxt),
        "cash_hours_only": True if cfg is None else bool(cfg.cash_hours_only),
    }


def week_bounds(ts: datetime) -> tuple[datetime, datetime]:
    """Monday 00:00 ET through the later of now or that instant, capped at next Monday."""
    local = to_et(ts)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    next_monday = monday + timedelta(days=7)
    end = local if local < next_monday else next_monday
    return monday, end


def lookback_bounds(ts: datetime, days: int = 365) -> tuple[datetime, datetime]:
    local = to_et(ts)
    start = local - timedelta(days=days)
    return start, local


def filter_bars_in_range(bars, start: datetime, end: datetime):
    start_et = to_et(start)
    end_et = to_et(end)
    return [b for b in bars if start_et <= to_et(b.ts) < end_et]
