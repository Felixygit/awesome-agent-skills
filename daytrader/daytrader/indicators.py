from __future__ import annotations

from daytrader.models import Bar


def true_range(bar: Bar, prev_close: float | None) -> float:
    if prev_close is None:
        return bar.high - bar.low
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


def atr(bars: list[Bar], period: int) -> float | None:
    if period <= 0 or len(bars) < period + 1:
        return None
    window = bars[-(period + 1) :]
    trs: list[float] = []
    for i, bar in enumerate(window):
        prev = window[i - 1].close if i else None
        if i == 0:
            continue
        trs.append(true_range(bar, prev))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def vwap(bars: list[Bar]) -> float | None:
    num = 0.0
    den = 0.0
    for bar in bars:
        typical = (bar.high + bar.low + bar.close) / 3.0
        vol = bar.volume if bar.volume > 0 else 1.0
        num += typical * vol
        den += vol
    if den <= 0:
        return None
    return num / den


def average_volume(bars: list[Bar], period: int) -> float | None:
    if period <= 0 or len(bars) < period:
        return None
    window = bars[-period:]
    return sum(b.volume for b in window) / period


def opening_range(bars: list[Bar], opening_bars: int) -> tuple[float, float] | None:
    if opening_bars <= 0 or len(bars) < opening_bars:
        return None
    window = bars[:opening_bars]
    return min(b.low for b in window), max(b.high for b in window)
