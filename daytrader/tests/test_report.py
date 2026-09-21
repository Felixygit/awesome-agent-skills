from datetime import datetime
from zoneinfo import ZoneInfo

from daytrader.report import trade_summary

ET = ZoneInfo("America/New_York")


def test_trade_summary_win_rate_and_drawdown():
    trades = [
        {"pnl": 50, "asset_class": "option", "exit_reason": "target", "session_date": "2026-01-05"},
        {"pnl": -50, "asset_class": "stock", "exit_reason": "stop", "session_date": "2026-01-06"},
        {"pnl": 10, "asset_class": "crypto", "exit_reason": "eod_flatten", "session_date": "2026-02-06"},
        {"pnl": -20, "asset_class": "metal", "exit_reason": "eod_flatten", "session_date": "2026-02-07"},
    ]
    start = datetime(2026, 1, 5, 10, 0, tzinfo=ET)
    curve = [
        (start, 50_050),
        (start, 50_000),
        (start, 50_010),
        (start, 49_990),
    ]
    s = trade_summary(trades, curve)
    assert s["trades"] == 4
    assert s["wins"] == 2
    assert s["losses"] == 2
    assert s["win_rate_pct"] == 50.0
    assert s["pnl"] == -10.0
    assert s["max_drawdown"] == -60.0
    assert s["by_asset_class"]["option"]["wins"] == 1
    assert s["by_exit"]["target"]["trades"] == 1
    assert "2026-01" in s["by_month"]
    assert "2026-02" in s["by_month"]


def test_trade_summary_uses_tracked_drawdown_when_deeper():
    trades = [{"pnl": 1, "asset_class": "stock", "exit_reason": "target", "session_date": "2026-03-01"}]
    curve = [(datetime(2026, 3, 1, tzinfo=ET), 50_000)]
    s = trade_summary(trades, curve, max_drawdown=-125.0)
    assert s["max_drawdown"] == -125.0
