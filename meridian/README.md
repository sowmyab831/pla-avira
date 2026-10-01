# Meridian — AI-Powered Trading Autopilot

**Buy dips. Sell highs. Powered by Avira AI.**

Meridian connects to your Robinhood account and uses the PLA Avira deep analysis engine (Elliott Wave, sentiment, institutional tracking, technicals) to generate trade signals and optionally auto-execute them.

## Architecture

```
Meridian App (FastAPI :8100)
    ↓
PLA Avira Deep Analysis (localhost:30000)
    ├── Elliott Wave patterns
    ├── Technical indicators (RSI, MACD, Bollinger)
    ├── Market sentiment (Reddit, Yahoo, Fear/Greed)
    ├── Institutional tracking (13F, insider trades)
    └── AI synthesis (DeepSeek-R1:32B)
    ↓
Trade Signal → Robinhood API (robin_stocks)
    ↓
Execute: Market/Limit orders with stop-loss + take-profit
```

## Trading Modes

| Mode | Behavior |
|------|----------|
| `manual` | Signals only — you approve every trade |
| `semi_auto` | Auto-executes low-risk signals, manual for high-risk |
| `autopilot` | Full auto (requires explicit opt-in) |

## Quick Start

```bash
cd meridian/backend
pip install -r requirements.txt
uvicorn app.main:app --port 8100
```

## API Endpoints

### Auth
- `POST /auth/login` — Login to Robinhood (username, password, mfa_code)
- `POST /auth/logout` — Logout

### Portfolio
- `GET /portfolio` — Current holdings + P&L
- `GET /quote/{symbol}` — Real-time quote

### Orders
- `POST /orders/buy` — Buy (market or limit)
- `POST /orders/sell` — Sell (market or limit)
- `GET /orders/open` — Open orders
- `DELETE /orders/{id}` — Cancel order

### Autopilot
- `POST /autopilot/evaluate` — Evaluate watchlist → trade signals
- `POST /autopilot/mode` — Set mode (manual/semi_auto/autopilot)
- `POST /autopilot/execute` — Execute a signal
- `GET /autopilot/stats` — Performance stats
- `GET /autopilot/history` — Trade history

## Risk Management

- **Position sizing**: Max 10% of portfolio per stock, 2% risk per trade
- **Stop-loss**: Automatic at -5% (configurable)
- **Take-profit**: Automatic at +15% (configurable)
- **Daily limit**: Max 10 trades per day
- **AI validation**: Every trade is cross-checked against PLA deep analysis

## Example: Evaluate Watchlist

```bash
curl -X POST http://localhost:8100/autopilot/evaluate \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL"]}'
```

Response:
```json
{
  "signals": [
    {
      "symbol": "NVDA",
      "signal": "buy",
      "confidence": 72,
      "risk": "medium",
      "reasons": ["RSI oversold (28)", "MACD bullish crossover", "Institutional accumulation"],
      "suggested_quantity": 5.2,
      "stop_loss_price": 118.75,
      "take_profit_price": 143.75
    }
  ]
}
```
