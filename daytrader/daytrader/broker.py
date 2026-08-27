from __future__ import annotations

from datetime import datetime

from daytrader.config import AssetClass, BotConfig, Side
from daytrader.models import Bar, Position, SizedOrder, _id


class PaperBroker:
    """Immediate fills at the signal price plus slippage. No live routing."""

    def __init__(self, cfg: BotConfig):
        self.cfg = cfg

    def fill_entry(self, order: SizedOrder, ts: datetime) -> Position | None:
        if not order.accepted:
            return None
        slip = self.cfg.slippage_bps / 10_000.0
        if order.signal.side is Side.LONG:
            px = order.entry * (1 + slip)
        else:
            px = order.entry * (1 - slip)
        stop, target = self._reanchor(order, px)
        return Position(
            id=_id(),
            symbol=order.signal.symbol,
            display_symbol=order.display_symbol,
            asset_class=order.signal.asset_class,
            side=order.signal.side,
            quantity=order.quantity,
            entry_price=px,
            stop=stop,
            target=target,
            risk_dollars=order.risk_dollars,
            reward_dollars=order.reward_dollars,
            opened_at=ts,
            multiplier=order.signal.multiplier,
            mark=px,
        )

    def _reanchor(self, order: SizedOrder, fill: float) -> tuple[float, float]:
        """Keep dollar risk/reward after slippage by shifting stop/target the same distance."""
        stop_dist = abs(order.entry - order.stop)
        tgt_dist = abs(order.target - order.entry)
        if order.signal.side is Side.LONG:
            return fill - stop_dist, fill + tgt_dist
        return fill + stop_dist, fill - tgt_dist

    def exit_price(self, pos: Position, bar: Bar, reason: str) -> float:
        slip = self.cfg.slippage_bps / 10_000.0
        if pos.asset_class is AssetClass.OPTION:
            px = pos.mark
            if reason == "target":
                px = pos.target
            elif reason == "stop":
                px = max(pos.stop, 0.0)
            if pos.side is Side.LONG:
                return max(0.0, px * (1 - slip))
            return px * (1 + slip)

        if reason == "target":
            px = pos.target
        elif reason == "stop":
            px = pos.stop
        else:
            px = pos.mark if pos.mark else bar.close
        if pos.side is Side.LONG:
            return px * (1 - slip)
        return px * (1 + slip)


def manage_position(pos: Position, bar: Bar) -> str | None:
    """Return an exit reason if the bar tags stop or target. Stop is checked first."""
    if pos.asset_class is AssetClass.OPTION:
        # Options are marked separately; engine calls manage_option.
        return None
    if pos.side is Side.LONG:
        if bar.low <= pos.stop:
            return "stop"
        if bar.high >= pos.target:
            return "target"
    else:
        if bar.high >= pos.stop:
            return "stop"
        if bar.low <= pos.target:
            return "target"
    return None


def manage_option(pos: Position) -> str | None:
    if pos.mark <= pos.stop + 1e-9:
        return "stop"
    if pos.mark >= pos.target - 1e-9:
        return "target"
    return None
