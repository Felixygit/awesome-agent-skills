from __future__ import annotations

from datetime import datetime

from daytrader.config import AssetClass, BotConfig
from daytrader.models import Position, Trade, _id


class Portfolio:
    def __init__(self, cfg: BotConfig):
        self.cfg = cfg
        self.cash = cfg.starting_cash
        self.starting_cash = cfg.starting_cash
        self.positions: dict[str, Position] = {}
        self.closed: list[Trade] = []
        self.realized_pnl = 0.0
        self.day_key: str | None = None
        self.day_realized = 0.0
        self.day_trades = 0
        self.equity_curve: list[tuple[datetime, float]] = []

    def reset_day_if_needed(self, ts: datetime) -> None:
        key = ts.strftime("%Y-%m-%d")
        if self.day_key != key:
            self.day_key = key
            self.day_realized = 0.0
            self.day_trades = 0

    @property
    def open_count(self) -> int:
        return len(self.positions)

    def has(self, symbol: str) -> bool:
        return symbol in self.positions or any(
            p.display_symbol == symbol or p.symbol == symbol for p in self.positions.values()
        )

    def get(self, symbol: str) -> Position | None:
        if symbol in self.positions:
            return self.positions[symbol]
        for pos in self.positions.values():
            if pos.symbol == symbol or pos.display_symbol == symbol:
                return pos
        return None

    def equity(self) -> float:
        # Cash is reduced by entry notional on open; add that inventory back plus UPL.
        inventory = 0.0
        for pos in self.positions.values():
            inventory += pos.quantity * pos.entry_price * pos.multiplier + pos.unrealized
        return self.cash + inventory

    def snapshot(self, ts: datetime) -> None:
        self.equity_curve.append((ts, self.equity()))
        if len(self.equity_curve) > 2_000:
            self.equity_curve = self.equity_curve[-1_500:]

    def open_position(self, pos: Position) -> None:
        cost = pos.quantity * pos.entry_price * pos.multiplier
        self.cash -= cost
        pos.mark = pos.entry_price
        pos.unrealized = 0.0
        self.positions[pos.id] = pos
        self.day_trades += 1

    def close_position(
        self,
        pos: Position,
        exit_price: float,
        ts: datetime,
        reason: str,
        fees: float = 0.0,
    ) -> Trade:
        signed = 1.0 if pos.side.value == "long" else -1.0
        proceeds = pos.quantity * exit_price * pos.multiplier
        entry_cost = pos.quantity * pos.entry_price * pos.multiplier
        pnl = signed * (proceeds - entry_cost) - fees
        self.cash += entry_cost + signed * (proceeds - entry_cost) - fees
        self.realized_pnl += pnl
        self.day_realized += pnl
        trade = Trade(
            id=_id(),
            symbol=pos.symbol,
            display_symbol=pos.display_symbol,
            asset_class=pos.asset_class,
            side=pos.side,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            fees=fees,
            opened_at=pos.opened_at,
            closed_at=ts,
            exit_reason=reason,
            risk_dollars=pos.risk_dollars,
            reward_dollars=pos.reward_dollars,
        )
        self.closed.append(trade)
        self.positions.pop(pos.id, None)
        return trade

    def mark_symbol(self, symbol: str, price: float, asset: AssetClass, option_marks: dict[str, float] | None = None) -> None:
        for pos in list(self.positions.values()):
            if pos.asset_class is AssetClass.OPTION:
                if option_marks and pos.display_symbol in option_marks:
                    pos.update_mark(option_marks[pos.display_symbol])
                elif pos.symbol == symbol:
                    # Delta overlay on the option premium.
                    delta = 0.50
                    signed_underlying = price  # caller should pass underlying last
                    # Keep last mark if we cannot map; engine updates option marks explicitly.
                    _ = (delta, signed_underlying)
                continue
            if pos.symbol == symbol:
                pos.update_mark(price)

    def to_dict(self) -> dict:
        wins = [t for t in self.closed if t.pnl > 0]
        losses = [t for t in self.closed if t.pnl < 0]
        return {
            "cash": round(self.cash, 2),
            "equity": round(self.equity(), 2),
            "starting_cash": self.starting_cash,
            "unrealized": round(sum(p.unrealized for p in self.positions.values()), 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "day_pnl": round(self.day_realized + sum(p.unrealized for p in self.positions.values()), 2),
            "day_realized": round(self.day_realized, 2),
            "day_trades": self.day_trades,
            "open_positions": self.open_count,
            "closed_trades": len(self.closed),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(self.closed), 3) if self.closed else 0.0,
            "avg_win": round(sum(t.pnl for t in wins) / len(wins), 2) if wins else 0.0,
            "avg_loss": round(sum(t.pnl for t in losses) / len(losses), 2) if losses else 0.0,
        }
