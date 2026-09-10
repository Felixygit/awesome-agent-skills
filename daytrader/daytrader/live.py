from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from daytrader.config import AssetClass, BotConfig
from daytrader.feeds import ScenarioFeed
from daytrader.market_hours import to_et
from daytrader.models import Bar
from daytrader.schedule import filter_bars_in_range

ET = ZoneInfo("America/New_York")


def load_paper_feed(
    cfg: BotConfig,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[Bar], str]:
    """Public 5-minute quotes. Falls back to the built-in scenario if offline."""
    live: list[Bar] = []
    live.extend(_yahoo_bars(cfg, AssetClass.STOCK, cfg.symbols_for(AssetClass.STOCK), start, end))
    live.extend(_yahoo_bars(cfg, AssetClass.METAL, cfg.symbols_for(AssetClass.METAL), start, end))
    crypto = _yahoo_bars(cfg, AssetClass.CRYPTO, cfg.symbols_for(AssetClass.CRYPTO), start, end)
    if len(crypto) < 20:
        crypto = _crypto_bars(cfg, start, end)
    live.extend(crypto)
    if start is not None and end is not None:
        live = filter_bars_in_range(live, start, end)
    if len(live) < 20:
        return list(ScenarioFeed(cfg).bars()), "demo-fallback"
    live.sort(key=lambda b: (b.ts, b.symbol))
    return live, "paper"


def _yahoo_bars(
    cfg: BotConfig,
    asset: AssetClass,
    symbols: list[str],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Bar]:
    if not symbols:
        return []
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return []
    out: list[Bar] = []
    interval = f"{cfg.bar_minutes}m"
    kwargs: dict = {"interval": interval, "progress": False, "auto_adjust": True}
    if start is not None:
        start_et = to_et(start)
        end_et = to_et(end) if end is not None else datetime.now(ET)
        kwargs["start"] = start_et.date().isoformat()
        kwargs["end"] = (end_et.date() + timedelta(days=1)).isoformat()
    else:
        kwargs["period"] = "7d"
    for symbol in symbols:
        try:
            df = yf.download(symbol, **kwargs)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        if getattr(df.columns, "nlevels", 1) > 1:
            try:
                df = df.xs(symbol, axis=1, level=-1)
            except Exception:
                df = df.droplevel(-1, axis=1)
        for ts, row in df.iterrows():
            try:
                stamp = ts.to_pydatetime()
            except Exception:
                continue
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            try:
                out.append(
                    Bar(
                        symbol=symbol,
                        asset_class=asset,
                        ts=stamp,
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row.get("Volume") or 0.0),
                    )
                )
            except Exception:
                continue
    return out


def _crypto_bars(
    cfg: BotConfig,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Bar]:
    symbols = cfg.symbols_for(AssetClass.CRYPTO)
    if not symbols:
        return []
    mapping = {
        "BTC-USD": "BTCUSDT",
        "ETH-USD": "ETHUSDT",
        "SOL-USD": "SOLUSDT",
    }
    try:
        import httpx
    except ImportError:
        return []
    interval_map = {1: "1m", 5: "5m", 15: "15m", 60: "1h"}
    binance_interval = interval_map.get(cfg.bar_minutes, "5m")
    out: list[Bar] = []
    start_ms = int(start.timestamp() * 1000) if start else None
    end_ms = int(end.timestamp() * 1000) if end else None
    try:
        with httpx.Client(timeout=12.0) as client:
            for symbol in symbols:
                pair = mapping.get(symbol)
                if not pair:
                    continue
                cursor = start_ms
                pages = 0
                while pages < 20:
                    params = {"symbol": pair, "interval": binance_interval, "limit": 1000}
                    if cursor is not None:
                        params["startTime"] = cursor
                    if end_ms is not None:
                        params["endTime"] = end_ms
                    resp = client.get("https://api.binance.com/api/v3/klines", params=params)
                    if resp.status_code != 200:
                        break
                    rows = resp.json()
                    if not rows:
                        break
                    for row in rows:
                        ts = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
                        out.append(
                            Bar(
                                symbol=symbol,
                                asset_class=AssetClass.CRYPTO,
                                ts=ts,
                                open=float(row[1]),
                                high=float(row[2]),
                                low=float(row[3]),
                                close=float(row[4]),
                                volume=float(row[5]),
                            )
                        )
                    last_open = int(rows[-1][0])
                    pages += 1
                    if cursor is None or last_open <= cursor or len(rows) < 1000:
                        break
                    cursor = last_open + 1
                    if end_ms is not None and cursor >= end_ms:
                        break
    except Exception:
        return []
    return out
