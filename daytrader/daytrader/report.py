from __future__ import annotations

from collections import defaultdict


def trade_summary(
    trades: list[dict],
    equity_curve: list[tuple] | None = None,
    max_drawdown: float | None = None,
) -> dict:
    wins = [t for t in trades if float(t.get("pnl") or 0) > 0]
    losses = [t for t in trades if float(t.get("pnl") or 0) < 0]
    flats = [t for t in trades if float(t.get("pnl") or 0) == 0]
    pnl = sum(float(t.get("pnl") or 0) for t in trades)
    by_month: dict[str, list[dict]] = defaultdict(list)
    by_class: dict[str, list[dict]] = defaultdict(list)
    by_reason: dict[str, list[dict]] = defaultdict(list)
    for t in trades:
        day = str(t.get("session_date") or "")[:7]
        by_month[day].append(t)
        by_class[str(t.get("asset_class") or "")].append(t)
        by_reason[str(t.get("exit_reason") or "")].append(t)

    def bucket(rows: list[dict]) -> dict:
        w = [r for r in rows if float(r.get("pnl") or 0) > 0]
        l = [r for r in rows if float(r.get("pnl") or 0) < 0]
        p = sum(float(r.get("pnl") or 0) for r in rows)
        wr = (len(w) / len(rows)) if rows else 0.0
        return {
            "trades": len(rows),
            "wins": len(w),
            "losses": len(l),
            "win_rate": round(wr, 3),
            "win_rate_pct": round(wr * 100, 1),
            "pnl": round(p, 2),
        }

    dd = 0.0 if max_drawdown is None else float(max_drawdown)
    if equity_curve:
        peak = equity_curve[0][1]
        curve_dd = 0.0
        for _, eq in equity_curve:
            peak = max(peak, eq)
            curve_dd = min(curve_dd, eq - peak)
        # Prefer the tracked drawdown when the curve was truncated.
        dd = min(dd, curve_dd) if max_drawdown is not None else curve_dd

    win_rate = (len(wins) / len(trades)) if trades else 0.0
    return {
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len(flats),
        "win_rate": round(win_rate, 3),
        "win_rate_pct": round(win_rate * 100, 1),
        "pnl": round(pnl, 2),
        "avg_win": round(sum(float(t["pnl"]) for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(float(t["pnl"]) for t in losses) / len(losses), 2) if losses else 0.0,
        "max_drawdown": round(dd, 2),
        "by_month": {k: bucket(v) for k, v in sorted(by_month.items())},
        "by_asset_class": {k: bucket(v) for k, v in sorted(by_class.items())},
        "by_exit": {k: bucket(v) for k, v in sorted(by_reason.items())},
    }
