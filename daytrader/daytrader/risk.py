"""Size each ticket to ≤$200 capital, ≤$50 risk, and a $50 profit target."""

from __future__ import annotations

from math import floor, inf

from daytrader.config import AssetClass, BotConfig, Side
from daytrader.models import Signal, SizedOrder


class RiskManager:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg

    def size(
        self,
        signal: Signal,
        cash: float,
        open_positions: int,
        realized_day_pnl: float,
        day_trades: int,
        reserved_notional: float = 0.0,
    ) -> SizedOrder:
        display = signal.option_symbol or signal.symbol
        reject = self._precheck(
            signal, cash, open_positions, realized_day_pnl, day_trades
        )
        if reject:
            return self._rejected(signal, display, reject)

        entry = signal.entry
        stop = signal.stop
        multiplier = signal.multiplier
        lot = signal.lot_size if signal.lot_size > 0 else 1.0
        unit_cost = entry * multiplier
        if entry <= 0 or unit_cost <= 0:
            return self._rejected(signal, display, "invalid entry")

        per_unit = abs(entry - stop) * multiplier
        buying_power = max(0.0, min(cash - reserved_notional, self.cfg.capital_per_trade))
        max_by_capital = _floor_to_lot(buying_power / unit_cost, lot)
        if per_unit <= 1e-12:
            max_by_risk = inf
        else:
            max_by_risk = self.cfg.risk_dollars / per_unit
        qty = _floor_to_lot(min(max_by_capital, max_by_risk), lot)
        if qty <= 0:
            if max_by_capital <= 0:
                return self._rejected(signal, display, "not enough $200 ticket / cash to size")
            return self._rejected(
                signal,
                display,
                f"1 lot risks ${per_unit * lot:.2f}, above ${self.cfg.risk_dollars:.2f} cap",
            )

        actual_risk = qty * per_unit if per_unit < inf else 0.0
        if actual_risk > self.cfg.risk_dollars * self.cfg.max_risk_overshoot + 1e-9:
            return self._rejected(
                signal,
                display,
                f"sized risk ${actual_risk:.2f} exceeds ${self.cfg.risk_dollars:.2f}",
            )

        reward = self.cfg.reward_dollars
        reward_per_unit = reward / (qty * multiplier)
        if signal.side is Side.LONG:
            target = entry + reward_per_unit
            if actual_risk <= 0:
                stop = entry - reward_per_unit
        else:
            target = entry - reward_per_unit
            if actual_risk <= 0:
                stop = entry + reward_per_unit

        notional = qty * unit_cost
        if notional > self.cfg.capital_per_trade + 1e-6:
            return self._rejected(signal, display, "notional exceeds $200 ticket")

        return SizedOrder(
            signal=signal,
            quantity=qty,
            entry=entry,
            stop=stop,
            target=target,
            risk_dollars=actual_risk if actual_risk > 0 else min(reward, notional),
            reward_dollars=reward,
            notional=notional,
            display_symbol=display,
            capital_used=notional,
        )

    def _precheck(
        self,
        signal: Signal,
        cash: float,
        open_positions: int,
        realized_day_pnl: float,
        day_trades: int,
    ) -> str | None:
        if not self.cfg.is_enabled(signal.asset_class):
            return f"{signal.asset_class.value} trading disabled"
        if open_positions >= self.cfg.max_positions:
            return "max positions reached"
        if realized_day_pnl <= -self.cfg.max_daily_loss:
            return "daily loss limit hit"
        if day_trades >= self.cfg.max_daily_trades:
            return "daily trade cap hit"
        if cash <= 0:
            return "no cash"
        if signal.asset_class is AssetClass.OPTION and signal.option_premium is not None:
            debit = signal.option_premium * signal.multiplier * (signal.lot_size or 1)
            if debit > self.cfg.capital_per_trade + 1e-9:
                return "option debit exceeds $200 ticket"
        return None

    def _rejected(self, signal: Signal, display: str, reason: str) -> SizedOrder:
        return SizedOrder(
            signal=signal,
            quantity=0,
            entry=signal.entry,
            stop=signal.stop,
            target=signal.entry,
            risk_dollars=0,
            reward_dollars=0,
            notional=0,
            display_symbol=display,
            reject_reason=reason,
            capital_used=0,
        )


def _floor_to_lot(qty: float, lot: float) -> float:
    if lot <= 0 or qty <= 0:
        return 0.0
    units = floor((qty + 1e-12) / lot)
    return units * lot
