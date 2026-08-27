# R50 Day Trader

Paper day-trading bot that **targets $50 profit** and **caps risk at $50** per trade across **stocks, options, crypto, and metals**.

This is a simulator with a live dashboard. It does **not** send orders to a broker. No strategy can guarantee $50 per trade — the engine sizes each setup so a stop is ~$50 and a target is ~$50. You still lose when the stop hits.

## What it does

- Opening-range breakout on 5-minute bars (volume filter, ATR stop cap)
- Position size = `$50 / (entry − stop)` so 1R ≈ $50
- Take-profit placed at +1R (~$50)
- Long options are defined-risk: debit ≤ $50, target 2× premium
- Crypto uses fractional size; metals trade as `GLD` / `SLV`
- Daily loss halt, max positions, end-of-day flatten (cash session)
- Dark desk UI with blotter, quotes, equity curve, and risk controls

## Quick start

```bash
cd daytrader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m daytrader serve --mode demo
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Demo mode replays a designed session so you can watch $50 winners and losers print with markets closed.

```bash
python -m daytrader backtest --mode demo
python -m pytest -q
```

`--mode paper` pulls public Yahoo / Binance bars when the network allows, then paper-trades them. If quotes are unavailable it falls back to the demo session.

## Risk model

| Input | Default |
| --- | --- |
| Risk per trade | $50 |
| Target per trade | $50 |
| Starting paper cash | $50,000 |
| Max positions | 6 |
| Max daily loss | $200 |
| Slippage | 2 bps |

Edit `config.yaml` or use the Risk budget panel. Asset-class toggles are on the same panel.

## Honest limits

- **Not financial advice.** You can lose money, including more than $50 if a gap jumps the stop (the simulator assumes the stop prints).
- **Paper only.** There is no Alpaca/IBKR live gate on purpose.
- **Options** are a delta overlay, not an options chain from an exchange.
- **Pattern day trader** rules still apply if you ever wire this to a US stock broker.
- Win rate of ORB is not 100%. A 1:1 system needs >50% wins after costs to grow.

## Layout

```
daytrader/           package
dashboard/           FastAPI + static desk UI
feeds.py             demo session
live.py              optional public quotes
engine.py            paper matching engine
risk.py              $50 / $50 sizer
```
