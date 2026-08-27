from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from daytrader.broker import PaperBroker, manage_option, manage_position
from daytrader.config import AssetClass, BotConfig, Side
from daytrader.market_hours import can_enter, should_flatten
from daytrader.models import Bar, EngineEvent, Position, Signal
from daytrader.portfolio import Portfolio
from daytrader.risk import RiskManager
from daytrader.storage import Store
from daytrader.strategy import OpeningRangeStrategy


class TradingEngine:
    def __init__(self, cfg: BotConfig, store: Store | None = None):
        self.cfg = cfg
        self.store = store
        self.portfolio = Portfolio(cfg)
        self.risk = RiskManager(cfg)
        self.strategy = OpeningRangeStrategy(cfg)
        self.broker = PaperBroker(cfg)
        self.running = False
        self.paused = False
        self.mode = "demo"
        self.last_ts: datetime | None = None
        self.quotes: dict[str, dict] = {}
        self.signals: list[dict] = []
        self.rejects: list[dict] = []
        self.events: list[EngineEvent] = []
        self.bars_processed = 0
        self._option_underlying: dict[str, float] = {}

    def log(self, message: str, level: str = "info", ts: datetime | None = None) -> None:
        event = EngineEvent(ts=ts or self.last_ts or datetime.utcnow(), level=level, message=message)
        self.events.append(event)
        if len(self.events) > 300:
            self.events = self.events[-200:]
        if self.store:
            self.store.save_event(event)

    def reset(self) -> None:
        self.portfolio = Portfolio(self.cfg)
        self.strategy.reset()
        self.signals.clear()
        self.rejects.clear()
        self.events.clear()
        self.quotes.clear()
        self.bars_processed = 0
        self.last_ts = None
        self._option_underlying.clear()
        self.log("Engine reset. Paper book is flat.", "info")

    def on_bar(self, bar: Bar) -> None:
        if self.paused:
            return
        self.bars_processed += 1
        self.last_ts = bar.ts
        self.portfolio.reset_day_if_needed(bar.ts)
        self.quotes[bar.symbol] = {
            "symbol": bar.symbol,
            "asset_class": bar.asset_class.value,
            "price": bar.close,
            "ts": bar.ts.isoformat(),
            "volume": bar.volume,
        }
        if bar.asset_class is not AssetClass.OPTION:
            self._option_underlying[bar.symbol] = bar.close
        self._mark_from_bar(bar)
        self._manage_open(bar)

        if should_flatten(bar.ts, bar.asset_class, self.cfg):
            self._flatten_asset(bar.asset_class, bar, "eod-flatten")

        for signal in self.strategy.on_bar(bar):
            self.signals.append(signal.to_dict())
            self.signals = self.signals[-50:]
            if not can_enter(bar.ts, signal.asset_class, self.cfg):
                continue
            if self._occupied(signal):
                continue
            order = self.risk.size(
                signal,
                cash=self.portfolio.cash,
                open_positions=self.portfolio.open_count,
                realized_day_pnl=self.portfolio.day_realized,
                day_trades=self.portfolio.day_trades,
            )
            if not order.accepted:
                self.rejects.append(order.to_dict())
                self.rejects = self.rejects[-40:]
                self.log(
                    f"Rejected {order.display_symbol}: {order.reject_reason}",
                    "warn",
                    bar.ts,
                )
                continue
            pos = self.broker.fill_entry(order, bar.ts)
            if pos is None:
                continue
            if signal.asset_class is AssetClass.OPTION:
                pos.underlying_entry = self._option_underlying.get(signal.symbol, bar.close)
                pos.delta = signal.delta
            self.portfolio.open_position(pos)
            self.log(
                f"OPEN {pos.side.value.upper()} {pos.display_symbol} "
                f"qty {pos.quantity:g} @ {pos.entry_price:.4f} "
                f"stop {pos.stop:.4f} target {pos.target:.4f} "
                f"risk ${pos.risk_dollars:.2f} / target ${pos.reward_dollars:.2f}",
                "trade",
                bar.ts,
            )
        self.portfolio.snapshot(bar.ts)

    def run_bars(self, bars: Iterable[Bar]) -> None:
        self.running = True
        for bar in bars:
            if not self.running:
                break
            self.on_bar(bar)
        self.running = False

    def stop(self) -> None:
        self.running = False
        self.paused = True
        self.log("Engine paused.")

    def resume(self) -> None:
        self.paused = False
        self.running = True
        self.log("Engine resumed.")

    def _occupied(self, signal: Signal) -> bool:
        display = signal.option_symbol or signal.symbol
        for pos in self.portfolio.positions.values():
            if pos.display_symbol == display:
                return True
            if (
                signal.asset_class is not AssetClass.OPTION
                and pos.asset_class is signal.asset_class
                and pos.symbol == signal.symbol
            ):
                return True
        return False

    def _mark_from_bar(self, bar: Bar) -> None:
        for pos in list(self.portfolio.positions.values()):
            if pos.asset_class is AssetClass.OPTION:
                if pos.symbol != bar.symbol or bar.asset_class is AssetClass.OPTION:
                    continue
                under = bar.close
                entry_under = pos.underlying_entry or under
                delta = pos.delta or 0.5
                signed = 1.0 if pos.side is Side.LONG else -1.0
                # Long put still uses Side.LONG on the contract; delta sign follows put vs call.
                parts = pos.display_symbol.split()
                if len(parts) >= 2 and parts[1].startswith("P"):
                    delta = -abs(delta)
                mark = max(0.0, pos.entry_price + signed * delta * (under - entry_under))
                pos.update_mark(mark)
            elif pos.symbol == bar.symbol:
                pos.update_mark(bar.close)

    def _manage_open(self, bar: Bar) -> None:
        for pos in list(self.portfolio.positions.values()):
            reason = None
            if pos.asset_class is AssetClass.OPTION:
                if pos.symbol == bar.symbol:
                    reason = manage_option(pos)
            elif pos.symbol == bar.symbol:
                reason = manage_position(pos, bar)
            if reason:
                self._close(pos, bar, reason)

    def _flatten_asset(self, asset: AssetClass, bar: Bar, reason: str) -> None:
        for pos in list(self.portfolio.positions.values()):
            if pos.asset_class is asset and pos.symbol == bar.symbol:
                self._close(pos, bar, reason)

    def _close(self, pos: Position, bar: Bar, reason: str) -> None:
        px = self.broker.exit_price(pos, bar, reason)
        trade = self.portfolio.close_position(
            pos, px, bar.ts, reason, fees=self.cfg.commission_per_fill
        )
        if self.store:
            self.store.save_trade(trade)
        self.log(
            f"CLOSE {pos.display_symbol} {reason} @ {px:.4f} PnL ${trade.pnl:.2f}",
            "trade",
            bar.ts,
        )

    def state(self) -> dict:
        curve = [
            {"ts": ts.isoformat(), "equity": round(eq, 2)}
            for ts, eq in self.portfolio.equity_curve[-240:]
        ]
        return {
            "mode": self.mode,
            "running": self.running and not self.paused,
            "paused": self.paused,
            "bars_processed": self.bars_processed,
            "last_ts": self.last_ts.isoformat() if self.last_ts else None,
            "risk_dollars": self.cfg.risk_dollars,
            "reward_dollars": self.cfg.reward_dollars,
            "max_daily_loss": self.cfg.max_daily_loss,
            "enabled_assets": dict(self.cfg.enabled_assets),
            "portfolio": self.portfolio.to_dict(),
            "positions": [p.to_dict() for p in self.portfolio.positions.values()],
            "trades": [t.to_dict() for t in self.portfolio.closed[-80:]],
            "quotes": list(self.quotes.values()),
            "signals": self.signals[-20:],
            "rejects": self.rejects[-20:],
            "events": [e.to_dict() for e in self.events[-40:]],
            "equity_curve": curve,
            "disclaimer": (
                "Paper trading only. $50 is a target and a risk cap, not a guarantee. "
                "Past or simulated results are not future performance."
            ),
        }
