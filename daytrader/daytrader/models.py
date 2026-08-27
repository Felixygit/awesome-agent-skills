from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from daytrader.config import AssetClass, Side


def _id() -> str:
    return uuid4().hex[:12]


@dataclass(frozen=True)
class Bar:
    symbol: str
    asset_class: AssetClass
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["asset_class"] = self.asset_class.value
        d["ts"] = self.ts.isoformat()
        return d


@dataclass
class Signal:
    symbol: str
    asset_class: AssetClass
    side: Side
    entry: float
    stop: float
    reason: str
    ts: datetime
    option_symbol: str | None = None
    option_premium: float | None = None
    delta: float | None = None
    multiplier: float = 1.0
    lot_size: float = 1.0
    id: str = field(default_factory=_id)
    setup: dict[str, Any] = field(default_factory=dict)
    strategy: str = "opening-range-breakout"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "entry": self.entry,
            "stop": self.stop,
            "reason": self.reason,
            "ts": self.ts.isoformat(),
            "option_symbol": self.option_symbol,
            "option_premium": self.option_premium,
            "delta": self.delta,
            "multiplier": self.multiplier,
            "strategy": self.strategy,
            "setup": self.setup,
        }


@dataclass
class SizedOrder:
    signal: Signal
    quantity: float
    entry: float
    stop: float
    target: float
    risk_dollars: float
    reward_dollars: float
    notional: float
    display_symbol: str
    reject_reason: str | None = None
    capital_used: float = 0.0

    @property
    def accepted(self) -> bool:
        return self.reject_reason is None and self.quantity > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal.id,
            "symbol": self.display_symbol,
            "underlying": self.signal.symbol,
            "asset_class": self.signal.asset_class.value,
            "side": self.signal.side.value,
            "quantity": self.quantity,
            "entry": self.entry,
            "stop": self.stop,
            "target": self.target,
            "risk_dollars": round(self.risk_dollars, 2),
            "reward_dollars": round(self.reward_dollars, 2),
            "notional": round(self.notional, 2),
            "capital_used": round(self.capital_used, 2),
            "reason": self.signal.reason,
            "reject_reason": self.reject_reason,
            "accepted": self.accepted,
            "ts": self.signal.ts.isoformat(),
            "strategy": self.signal.strategy,
            "setup": self.signal.setup,
        }


@dataclass
class Position:
    id: str
    symbol: str
    display_symbol: str
    asset_class: AssetClass
    side: Side
    quantity: float
    entry_price: float
    stop: float
    target: float
    risk_dollars: float
    reward_dollars: float
    opened_at: datetime
    multiplier: float = 1.0
    mark: float = 0.0
    unrealized: float = 0.0
    underlying_entry: float | None = None
    delta: float | None = None
    capital_used: float = 0.0
    signal_id: str = ""
    strategy: str = "opening-range-breakout"
    entry_reason: str = ""
    setup: dict[str, Any] = field(default_factory=dict)
    mae: float = 0.0
    mfe: float = 0.0
    mae_price: float | None = None
    mfe_price: float | None = None
    bars_held: int = 0
    intended_entry: float = 0.0
    slippage_entry: float = 0.0

    def update_mark(self, price: float) -> None:
        self.mark = price
        signed = 1.0 if self.side is Side.LONG else -1.0
        self.unrealized = signed * (price - self.entry_price) * self.quantity * self.multiplier
        if self.unrealized < self.mae:
            self.mae = self.unrealized
            self.mae_price = price
        if self.unrealized > self.mfe:
            self.mfe = self.unrealized
            self.mfe_price = price

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "display_symbol": self.display_symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 6),
            "stop": round(self.stop, 6),
            "target": round(self.target, 6),
            "mark": round(self.mark, 6),
            "unrealized": round(self.unrealized, 2),
            "risk_dollars": round(self.risk_dollars, 2),
            "reward_dollars": round(self.reward_dollars, 2),
            "capital_used": round(self.capital_used, 2),
            "opened_at": self.opened_at.isoformat(),
            "mae": round(self.mae, 2),
            "mfe": round(self.mfe, 2),
            "bars_held": self.bars_held,
            "strategy": self.strategy,
            "setup": self.setup,
        }


@dataclass
class Trade:
    id: str
    symbol: str
    display_symbol: str
    asset_class: AssetClass
    side: Side
    quantity: float
    entry_price: float
    exit_price: float
    pnl: float
    fees: float
    opened_at: datetime
    closed_at: datetime
    exit_reason: str
    risk_dollars: float
    reward_dollars: float
    multiplier: float = 1.0
    capital_used: float = 0.0
    notional: float = 0.0
    stop: float = 0.0
    target: float = 0.0
    hold_seconds: float = 0.0
    bars_held: int = 0
    session_date: str = ""
    day_of_week: str = ""
    minutes_from_open: float | None = None
    pnl_pct_capital: float = 0.0
    r_multiple: float = 0.0
    slippage_entry: float = 0.0
    slippage_exit: float = 0.0
    mae: float = 0.0
    mfe: float = 0.0
    mae_price: float | None = None
    mfe_price: float | None = None
    strategy: str = "opening-range-breakout"
    setup_reason: str = ""
    signal_id: str = ""
    or_high: float | None = None
    or_low: float | None = None
    vwap: float | None = None
    atr: float | None = None
    volume: float | None = None
    volume_avg: float | None = None
    range_pct: float | None = None
    delta: float | None = None
    underlying_entry: float | None = None
    setup: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_date": self.session_date,
            "day_of_week": self.day_of_week,
            "minutes_from_open": self.minutes_from_open,
            "symbol": self.symbol,
            "display_symbol": self.display_symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "strategy": self.strategy,
            "setup_reason": self.setup_reason,
            "quantity": self.quantity,
            "multiplier": self.multiplier,
            "capital_used": round(self.capital_used, 2),
            "notional": round(self.notional, 2),
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "stop": round(self.stop, 6),
            "target": round(self.target, 6),
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat(),
            "hold_seconds": round(self.hold_seconds, 1),
            "bars_held": self.bars_held,
            "exit_reason": self.exit_reason,
            "pnl": round(self.pnl, 2),
            "pnl_pct_capital": round(self.pnl_pct_capital, 4),
            "r_multiple": round(self.r_multiple, 3),
            "fees": round(self.fees, 2),
            "slippage_entry": round(self.slippage_entry, 6),
            "slippage_exit": round(self.slippage_exit, 6),
            "mae": round(self.mae, 2),
            "mfe": round(self.mfe, 2),
            "mae_price": self.mae_price,
            "mfe_price": self.mfe_price,
            "risk_dollars": round(self.risk_dollars, 2),
            "reward_dollars": round(self.reward_dollars, 2),
            "or_high": self.or_high,
            "or_low": self.or_low,
            "vwap": self.vwap,
            "atr": self.atr,
            "volume": self.volume,
            "volume_avg": self.volume_avg,
            "range_pct": self.range_pct,
            "delta": self.delta,
            "underlying_entry": self.underlying_entry,
            "signal_id": self.signal_id,
            "setup": self.setup,
        }


@dataclass
class EngineEvent:
    ts: datetime
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts.isoformat(), "level": self.level, "message": self.message}
