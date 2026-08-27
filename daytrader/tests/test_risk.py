from daytrader.config import AssetClass, BotConfig, Side
from daytrader.models import Signal
from daytrader.risk import RiskManager
from tests.conftest import long_signal, ts


def test_stock_uses_two_hundred_ticket_and_fifty_target():
    rm = RiskManager(BotConfig())
    order = rm.size(long_signal(100, 98), cash=25_000, open_positions=0, realized_day_pnl=0, day_trades=0)
    assert order.accepted
    assert order.quantity == 2
    assert abs(order.notional - 200) < 1e-9
    assert abs(order.reward_dollars - 50) < 1e-9
    assert abs(order.target - 125) < 1e-9
    assert order.risk_dollars <= 50.01


def test_short_size_mirrors_long():
    rm = RiskManager(BotConfig())
    sig = long_signal(100, 102)
    sig.side = Side.SHORT
    order = rm.size(sig, cash=25_000, open_positions=0, realized_day_pnl=0, day_trades=0)
    assert order.accepted
    assert order.quantity == 2
    assert abs(order.target - 75) < 1e-9


def test_rejects_when_one_share_exceeds_risk():
    rm = RiskManager(BotConfig())
    order = rm.size(long_signal(100, 40), cash=25_000, open_positions=0, realized_day_pnl=0, day_trades=0)
    assert not order.accepted
    assert "above" in (order.reject_reason or "")


def test_crypto_fractional_lot_caps_at_two_hundred():
    rm = RiskManager(BotConfig())
    sig = Signal(
        symbol="BTC-USD",
        asset_class=AssetClass.CRYPTO,
        side=Side.LONG,
        entry=64_000,
        stop=63_900,
        reason="test",
        ts=ts(),
        multiplier=1.0,
        lot_size=0.0001,
    )
    order = rm.size(sig, cash=100_000, open_positions=0, realized_day_pnl=0, day_trades=0)
    assert order.accepted
    assert order.notional <= 200.01
    assert abs(order.reward_dollars - 50) < 1e-9
    assert abs(order.quantity - 0.0031) < 1e-6


def test_option_contract_targets_fifty():
    rm = RiskManager(BotConfig())
    sig = Signal(
        symbol="SPY",
        asset_class=AssetClass.OPTION,
        side=Side.LONG,
        entry=0.50,
        stop=0.0,
        reason="test",
        ts=ts(),
        option_symbol="SPY C500",
        option_premium=0.50,
        multiplier=100,
        lot_size=1,
    )
    order = rm.size(sig, cash=25_000, open_positions=0, realized_day_pnl=0, day_trades=0)
    assert order.accepted
    assert order.notional <= 200.01
    assert abs(order.reward_dollars - 50) < 1e-9
    assert abs(order.target - 1.0) < 1e-9


def test_daily_loss_blocks_new_risk():
    rm = RiskManager(BotConfig(max_daily_loss=200))
    order = rm.size(long_signal(), cash=25_000, open_positions=0, realized_day_pnl=-200, day_trades=0)
    assert not order.accepted
    assert "daily loss" in order.reject_reason


def test_max_positions_blocks():
    rm = RiskManager(BotConfig(max_positions=2))
    order = rm.size(long_signal(), cash=25_000, open_positions=2, realized_day_pnl=0, day_trades=0)
    assert not order.accepted
