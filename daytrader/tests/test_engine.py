from daytrader.config import AssetClass, BotConfig
from daytrader.engine import TradingEngine
from daytrader.feeds import ScenarioFeed


def test_scenario_books_fifty_dollar_trades():
    cfg = BotConfig(bar_interval_ms=1, slippage_bps=0.0)
    engine = TradingEngine(cfg)
    engine.run_bars(ScenarioFeed(cfg).bars())
    trades = engine.portfolio.closed
    assert trades, "expected the demo session to close trades"
    classes = {t.asset_class for t in trades}
    assert AssetClass.STOCK in classes
    assert AssetClass.OPTION in classes
    assert AssetClass.CRYPTO in classes
    assert AssetClass.METAL in classes
    # Target/stop exits should land near the $50 unit, slippage off.
    timed = [t for t in trades if t.exit_reason in {"target", "stop"}]
    assert timed
    for t in timed:
        assert abs(abs(t.pnl) - 50) < 6, (t.display_symbol, t.exit_reason, t.pnl)
        assert t.risk_dollars <= 50.01


def test_no_trade_exceeds_risk_cap():
    cfg = BotConfig(slippage_bps=0)
    engine = TradingEngine(cfg)
    engine.run_bars(ScenarioFeed(cfg).bars())
    for t in engine.portfolio.closed:
        assert t.risk_dollars <= cfg.risk_dollars + 0.05
        if t.exit_reason == "stop":
            assert t.pnl <= 0.5
        if t.exit_reason == "target":
            assert t.pnl >= 40


def test_disabled_crypto_never_trades():
    cfg = BotConfig(enabled_assets={"stock": True, "option": False, "crypto": False, "metal": False})
    engine = TradingEngine(cfg)
    engine.run_bars(ScenarioFeed(cfg).bars())
    assert all(t.asset_class is AssetClass.STOCK for t in engine.portfolio.closed)
    assert all(p.asset_class is AssetClass.STOCK for p in engine.portfolio.positions.values())


def test_daily_loss_halt():
    cfg = BotConfig(max_daily_loss=40, slippage_bps=0, max_positions=6)
    engine = TradingEngine(cfg)
    bars = list(ScenarioFeed(cfg).bars())
    tripped = False
    for bar in bars:
        if bar.ts.hour == 9 and bar.ts.minute >= 45 and not tripped:
            engine.portfolio.day_realized = -40.0
            tripped = True
        engine.on_bar(bar)
    assert any((r.get("reject_reason") or "") == "daily loss limit hit" for r in engine.rejects)


def test_equity_stays_near_cash_while_open():
    from daytrader.config import Side
    from daytrader.models import Position
    from daytrader.portfolio import Portfolio
    from datetime import datetime
    from zoneinfo import ZoneInfo

    cfg = BotConfig(starting_cash=50_000)
    book = Portfolio(cfg)
    pos = Position(
        id="x",
        symbol="SPY",
        display_symbol="SPY",
        asset_class=AssetClass.STOCK,
        side=Side.LONG,
        quantity=10,
        entry_price=500,
        stop=495,
        target=505,
        risk_dollars=50,
        reward_dollars=50,
        opened_at=datetime(2026, 8, 26, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        mark=500,
    )
    book.open_position(pos)
    assert abs(book.equity() - 50_000) < 1e-6
    pos.update_mark(505)
    assert abs(book.equity() - 50_050) < 1e-6


def test_equity_curve_moves_with_trades():
    cfg = BotConfig(slippage_bps=0)
    engine = TradingEngine(cfg)
    engine.run_bars(ScenarioFeed(cfg).bars())
    ys = [eq for _, eq in engine.portfolio.equity_curve]
    assert len(ys) < 200
    assert max(ys) - min(ys) > 20
    assert min(ys) > 49_000
