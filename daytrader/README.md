# R50 Day Trader

Paper desk that **uses at most $200 per ticket**, **targets $50 profit**, and runs **every weekday 09:30–16:00 America/New_York**.

It does **not** send live broker orders. $50 is a target, not a guarantee. A $200 stock ticket needs a 25% day move to make $50; options are the realistic path for that payoff. Every fill is journaled so you can research a live strategy later.

## Session

- Weekdays only
- Start 09:30 ET (opening-range bars first)
- Flatten 15:55 ET, session ends 16:00 ET
- Stocks, options, crypto, and metals all follow those cash hours
- `python -m daytrader run-daily` waits overnight and runs each session

```bash
cd daytrader
pip install -r requirements.txt
python -m daytrader serve --mode demo          # replay a 09:30–16:00 session
python -m daytrader run-daily                  # idle until the next weekday open
python -m pytest -q
```

Dashboard: [http://127.0.0.1:8000](http://127.0.0.1:8000). Download the journal from `/api/journal.csv`.

## Ticket math

| Rule | Default |
| --- | --- |
| Capital per trade | **$200** max notional / debit |
| Profit target | **$50** |
| Max loss | **$50** |
| Session | 09:30–16:00 ET weekdays |
| Starting paper cash | $50,000 |
| Max daily loss | $200 |

Size = min($200 / price, $50 / stop distance). Target is always +$50 from the fill.

## Research journal

Each closed trade is appended to `data/journal/trades.csv` and `data/journal/YYYY-MM-DD.json`. SQLite also stores entries, exits, rejects, and engine events.

Recorded fields include:

- entry/exit timestamps, hold time, bars held, session date, weekday, minutes from the open
- symbol, class, side, qty, ticket size, stop, target, fills
- PnL, % of ticket, R-multiple, fees, slippage
- MAE / MFE (worst/best unrealized while in the trade)
- setup context: opening-range high/low, VWAP, ATR, volume, range %, delta, reason

Use that tape to decide which setups are worth wiring to a live broker.

## Honest limits

- Not financial advice. Stops can gap.
- Paper only. No Alpaca/IBKR live routing.
- Options are a delta overlay, not an exchange chain.
- NYSE holidays are not skipped yet (weekends are).
- A $200 cash-equity ticket making $50 in one day is a 25% move; the journal will show when that target is unrealistic.

## Layout

```
daytrader/strategy.py   opening-range breakout
daytrader/risk.py       $200 ticket / $50 target sizer
daytrader/schedule.py   09:30–16:00 ET clock
daytrader/journal.py    CSV + daily JSON
daytrader/engine.py     paper matching + MAE/MFE
```
