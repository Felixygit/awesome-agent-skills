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
            "reason": self.signal.reason,
            "reject_reason": self.reject_reason,
            "accepted": self.accepted,
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

    def update_mark(self, price: float) -> None:
        self.mark = price
        signed = 1.0 if self.side is Side.LONG else -1.0
        self.unrealized = signed * (price - self.entry_price) * self.quantity * self.multiplier

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
            "opened_at": self.opened_at.isoformat(),
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "display_symbol": self.display_symbol,
            "asset_class": self.asset_class.value,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": round(self.entry_price, 6),
            "exit_price": round(self.exit_price, 6),
            "pnl": round(self.pnl, 2),
            "fees": round(self.fees, 2),
            "opened_at": self.opened_at.isoformat(),
            "closed_at": self.closed_at.isoformat(),
            "exit_reason": self.exit_reason,
            "risk_dollars": round(self.risk_dollars, 2),
            "reward_dollars": round(self.reward_dollars, 2),
        }


@dataclass
class EngineEvent:
    ts: datetime
    level: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"ts": self.ts.isoformat(), "level": self.level, "message": self.message}
