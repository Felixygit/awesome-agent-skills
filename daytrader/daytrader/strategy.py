from __future__ import annotations

from datetime import datetime

from daytrader.config import AssetClass, BotConfig, Side
from daytrader.indicators import atr, average_volume, opening_range, vwap
from daytrader.market_hours import to_et
from daytrader.models import Bar, Signal


class DaySession:
    """One symbol's bars for a single session (or rolling crypto window)."""

    def __init__(self, symbol: str, asset: AssetClass, session_date: str):
        self.symbol = symbol
        self.asset = asset
        self.session_date = session_date
        self.bars: list[Bar] = []
        self.fired = False
        self.option_fired = False

    def add(self, bar: Bar) -> None:
        self.bars.append(bar)


def session_key(ts: datetime, asset: AssetClass) -> str:
    return to_et(ts).strftime("%Y-%m-%d")


class OpeningRangeStrategy:
    """Break the opening range, stop at the other side, target sized to $50 by RiskManager."""

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.sessions: dict[tuple[str, AssetClass, str], DaySession] = {}

    def reset(self) -> None:
        self.sessions.clear()

    def on_bar(self, bar: Bar) -> list[Signal]:
        key = (bar.symbol, bar.asset_class, session_key(bar.ts, bar.asset_class))
        session = self.sessions.get(key)
        if session is None:
            session = DaySession(bar.symbol, bar.asset_class, key[2])
            self.sessions[key] = session
        session.add(bar)

        signals: list[Signal] = []
        eq_signal = self._evaluate_equity_or_crypto(session, bar)
        if eq_signal:
            signals.append(eq_signal)
            session.fired = True
            if (
                bar.asset_class is AssetClass.STOCK
                and self.cfg.is_enabled(AssetClass.OPTION)
                and bar.symbol in self.cfg.symbols_for(AssetClass.OPTION)
                and not session.option_fired
            ):
                opt = self._option_from_equity(eq_signal, bar)
                if opt:
                    signals.append(opt)
                    session.option_fired = True
        return signals

    def _evaluate_equity_or_crypto(self, session: DaySession, bar: Bar) -> Signal | None:
        if session.fired:
            return None
        if bar.asset_class is AssetClass.OPTION:
            return None
        bars = session.bars
        n = self.cfg.opening_bars
        if len(bars) < n + 1:
            return None
        rng = opening_range(bars, n)
        if rng is None:
            return None
        lo, hi = rng
        mid = (lo + hi) / 2.0
        if mid <= 0 or (hi - lo) / mid < self.cfg.min_range_pct:
            return None

        vol_avg = average_volume(bars[:-1], min(len(bars) - 1, 8))
        if vol_avg and bar.volume < vol_avg * self.cfg.volume_mult:
            return None

        side: Side | None = None
        stop: float | None = None
        reason = ""
        if bar.close > hi:
            side = Side.LONG
            stop = lo
            reason = f"opening-range breakout above {hi:.4f}"
        elif bar.close < lo:
            side = Side.SHORT
            stop = hi
            reason = f"opening-range breakdown below {lo:.4f}"
        else:
            return None

        stop = _structure_stop(bar.close, stop, side, atr(bars, min(self.cfg.atr_period, max(2, len(bars) - 1))), self.cfg)

        vw = vwap(bars)
        if vw:
            reason = f"{reason}; VWAP {vw:.4f}"

        atr_val = atr(bars, min(self.cfg.atr_period, max(2, len(bars) - 1)))
        vol_now = bar.volume
        setup = {
            "or_high": hi,
            "or_low": lo,
            "vwap": vw,
            "atr": atr_val,
            "volume": vol_now,
            "volume_avg": vol_avg,
            "range_pct": (hi - lo) / mid if mid else None,
            "minutes_from_open": _minutes_from_open(bar.ts),
            "day_of_week": to_et(bar.ts).strftime("%A"),
            "session_date": to_et(bar.ts).strftime("%Y-%m-%d"),
            "bar_open": bar.open,
            "bar_high": bar.high,
            "bar_low": bar.low,
            "bar_close": bar.close,
        }
        return Signal(
            symbol=bar.symbol,
            asset_class=bar.asset_class,
            side=side,
            entry=bar.close,
            stop=stop,
            reason=reason,
            ts=bar.ts,
            multiplier=1.0,
            lot_size=_lot_size(bar.asset_class),
            setup=setup,
        )

    def _option_from_equity(self, equity: Signal, bar: Bar) -> Signal | None:
        delta = self.cfg.option_assumed_delta
        if not (self.cfg.option_min_delta <= delta <= self.cfg.option_max_delta):
            return None
        stub = max(bar.close * 0.004, 0.10)
        max_premium = self.cfg.capital_per_trade / self.cfg.option_multiplier
        premium = min(stub, max_premium)
        if premium <= 0:
            return None
        # 25% premium stop so $200 ticket risks $50 when fully sized.
        stop = premium * (1.0 - self.cfg.risk_dollars / self.cfg.capital_per_trade)
        stop = max(stop, 0.0)
        right = "C" if equity.side is Side.LONG else "P"
        strike = round(bar.close)
        occ = f"{bar.symbol} {right}{strike}"
        setup = dict(equity.setup)
        setup.update({"option_right": right, "strike": strike, "delta": delta, "premium_model": stub})
        return Signal(
            symbol=bar.symbol,
            asset_class=AssetClass.OPTION,
            side=Side.LONG,
            entry=premium,
            stop=stop,
            reason=f"defined-risk {occ} from {equity.reason}",
            ts=bar.ts,
            option_symbol=occ,
            option_premium=premium,
            delta=delta,
            multiplier=float(self.cfg.option_multiplier),
            lot_size=1.0,
            setup=setup,
        )


def _lot_size(asset: AssetClass) -> float:
    if asset is AssetClass.OPTION:
        return 1.0
    return 0.0001


def _minutes_from_open(ts: datetime) -> float:
    local = to_et(ts)
    open_ts = local.replace(hour=9, minute=30, second=0, microsecond=0)
    return (local - open_ts).total_seconds() / 60.0


def _structure_stop(entry: float, stop: float, side: Side, atr_val: float | None, cfg: BotConfig) -> float:
    """Keep a tradable stop: not inside 15 bps, not wider than 1.5 ATR when ATR exists."""
    min_dist = max(entry * 0.0015, 1e-6)
    if side is Side.LONG:
        dist = entry - stop
        if dist < min_dist:
            stop = entry - min_dist
        if atr_val and atr_val > 0:
            cap = cfg.atr_stop_mult * 1.5 * atr_val
            if entry - stop > cap > min_dist:
                stop = entry - cap
        if stop >= entry:
            stop = entry - min_dist
    else:
        dist = stop - entry
        if dist < min_dist:
            stop = entry + min_dist
        if atr_val and atr_val > 0:
            cap = cfg.atr_stop_mult * 1.5 * atr_val
            if stop - entry > cap > min_dist:
                stop = entry + cap
        if stop <= entry:
            stop = entry + min_dist
    return stop
