from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from daytrader.config import CASH_CLOSE, CASH_OPEN, AssetClass, BotConfig

ET = ZoneInfo("America/New_York")


def to_et(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=ET)
    return ts.astimezone(ET)


def is_weekday(ts: datetime) -> bool:
    return to_et(ts).weekday() < 5


def session_open(ts: datetime) -> datetime:
    local = to_et(ts)
    return local.replace(hour=CASH_OPEN.hour, minute=CASH_OPEN.minute, second=0, microsecond=0)


def session_close(ts: datetime) -> datetime:
    local = to_et(ts)
    return local.replace(hour=CASH_CLOSE.hour, minute=CASH_CLOSE.minute, second=0, microsecond=0)


def cash_session_open(ts: datetime) -> bool:
    if not is_weekday(ts):
        return False
    local = to_et(ts)
    return session_open(ts) <= local < session_close(ts)


def uses_cash_hours(asset: AssetClass, cfg: BotConfig) -> bool:
    if not cfg.cash_hours_only:
        return asset is not AssetClass.CRYPTO
    return True


def should_flatten(ts: datetime, asset: AssetClass, cfg: BotConfig) -> bool:
    if not uses_cash_hours(asset, cfg) and asset is AssetClass.CRYPTO:
        return False
    if not is_weekday(ts):
        return True
    local = to_et(ts)
    cutoff = session_close(ts) - timedelta(minutes=cfg.flatten_minutes_before_close)
    return local >= cutoff


def can_enter(ts: datetime, asset: AssetClass, cfg: BotConfig) -> bool:
    if should_flatten(ts, asset, cfg):
        return False
    if not uses_cash_hours(asset, cfg) and asset is AssetClass.CRYPTO:
        return True
    local = to_et(ts)
    range_ready = session_open(ts) + timedelta(minutes=cfg.bar_minutes * cfg.opening_bars)
    return cash_session_open(ts) and local >= range_ready
