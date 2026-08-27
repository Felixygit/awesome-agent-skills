from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from daytrader.config import AssetClass, BotConfig
from daytrader.feeds import ScenarioFeed
from daytrader.models import Bar


def load_paper_feed(cfg: BotConfig) -> tuple[Iterable[Bar], str]:
    """Best-effort public quotes. Falls back to the built-in scenario if offline."""
    live: list[Bar] = []
    live.extend(_yahoo_bars(cfg, AssetClass.STOCK, cfg.symbols_for(AssetClass.STOCK)))
    live.extend(_yahoo_bars(cfg, AssetClass.METAL, cfg.symbols_for(AssetClass.METAL)))
    live.extend(_crypto_bars(cfg))
    if len(live) < 20:
        return ScenarioFeed(cfg).bars(), "demo-fallback"
    live.sort(key=lambda b: (b.ts, b.symbol))
    return live, "paper"


def _yahoo_bars(cfg: BotConfig, asset: AssetClass, symbols: list[str]) -> list[Bar]:
    if not symbols:
        return []
    try:
        import yfinance as yf  # type: ignore
    except ImportError:
        return []
    out: list[Bar] = []
    interval = f"{cfg.bar_minutes}m"
    for symbol in symbols:
        try:
            df = yf.download(symbol, period="5d", interval=interval, progress=False, auto_adjust=True)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        if getattr(df.columns, "nlevels", 1) > 1:
            df = df.xs(symbol, axis=1, level=-1)
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


def _crypto_bars(cfg: BotConfig) -> list[Bar]:
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
        return _yahoo_bars(cfg, AssetClass.CRYPTO, symbols)
    interval_map = {1: "1m", 5: "5m", 15: "15m", 60: "1h"}
    binance_interval = interval_map.get(cfg.bar_minutes, "5m")
    out: list[Bar] = []
    try:
        with httpx.Client(timeout=8.0) as client:
            for symbol in symbols:
                pair = mapping.get(symbol)
                if not pair:
                    continue
                resp = client.get(
                    "https://api.binance.com/api/v3/klines",
                    params={"symbol": pair, "interval": binance_interval, "limit": 200},
                )
                if resp.status_code != 200:
                    continue
                for row in resp.json():
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
    except Exception:
        return _yahoo_bars(cfg, AssetClass.CRYPTO, symbols)
    return out
