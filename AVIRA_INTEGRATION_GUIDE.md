# Avira — Complete Integration Guide

## Architecture Overview

```
Browser (React :5173)  ←──→  K8s Backend (FastAPI :30000)  ←──→  Ollama LLM (:11434)
Mobile (React Native)  ←──→         ↕   '[:]'             yfinance (real-time)                  Metal GPU (M4)
                              22 data sources
                              SEC EDGAR, FRED, RSS
                              Reddit, Stocktwits
```

---

## 1. Email Integration (via OpenClaw)

### Setup

```bash
# 1. Create Google Cloud project, enable Gmail API
# 2. Download OAuth credentials
cp client_secret.json backend/credentials/

# 3. Set environment
export GMAIL_CLIENT_ID="your-id.apps.googleusercontent.com"
export GMAIL_CLIENT_SECRET="your-secret"
export GMAIL_REDIRECT_URI="http://localhost:30000/api/integrations/gmail/callback"

# 4. Authenticate
curl http://localhost:30000/api/integrations/gmail/auth
# → Opens browser for OAuth consent
```

### OpenClaw Commands

```bash
pla emails                    # List unread emails
pla emails --analyze          # Extract action items via LLM
pla emails --action-items     # Show pending tasks
```

### What Gets Extracted

| Type | Example |
|------|---------|
| Reply needed | "Reply to John about the meeting" |
| Appointment | "Doctor appt March 25 at 2pm" |
| Deadline | "Submit report by Friday" |
| Payment | "Pay electric bill - due March 30" |
| Follow-up | "Follow up with recruiter next week" |

### API Endpoints

```
GET  /api/integrations/gmail/auth          → OAuth URL
GET  /api/integrations/gmail/callback      → OAuth callback
GET  /api/integrations/gmail/emails        → Fetch unread
POST /api/integrations/gmail/analyze       → LLM analysis
GET  /api/integrations/action-items        → Extracted tasks
GET  /api/integrations/appointments        → Calendar items
```

---

## 2. Stock Watchlist & Forecasting

### Add to Watchlist

In the Trading Dashboard, type any ticker in the search bar (e.g., `PLTR`) and press Enter. It auto-adds to your watchlist with live price updates every 30 seconds.

### Forecast Horizons

| Horizon | Method | Best For |
|---------|--------|----------|
| **1 Hour** | EMA momentum + ATR channel (intraday data) | Options day traders |
| **1 Day** | EMA momentum + ATR channel | Swing traders |
| **1 Week** | EMA momentum + ATR channel | Swing traders |
| **1 Month** | Linear regression + MACD momentum | Position traders |
| **3 Month** | Linear regression + MACD momentum | Medium-term investors |
| **1 Year** | Trend decomposition + Seasonal FFT + Mean reversion | Long-term investors |

### API

```bash
# Multi-horizon forecast
curl http://localhost:30000/api/portfolio/stocks/AAPL/forecast

# Intraday options targets (pivots, CALL/PUT entry/stop/targets)
curl http://localhost:30000/api/portfolio/stocks/AAPL/intraday-targets

# Historical prices (real-time via yfinance)
curl http://localhost:30000/api/portfolio/stocks/AAPL/historical?period=1m
```

### Options Trader Targets

Each stock provides:
- **Pivot Points**: Classic, Woodie, Camarilla
- **CALL Setup**: Entry (breakout above resistance), Stop Loss, Target 1, Target 2, Risk/Reward
- **PUT Setup**: Entry (breakdown below support), Stop Loss, Target 1, Target 2, Risk/Reward
- **Expected Daily Range**: ATR-based high/low range
- **Detected Patterns**: Double top/bottom, MACD signals, RSI divergence, cup & handle

---

## 3. Top 20 Stock Recommendations

### How It Works

1. **100-stock universe** scanned (mega-cap to mid-cap, all sectors)
2. **22 data sources** queried per stock
3. **5 scoring dimensions** (0-100 each):
   - **Technical (25%)**: RSI, MACD, SMA crossover, momentum
   - **Fundamental (25%)**: P/E, earnings growth, profit margins, revenue growth
   - **Sentiment (15%)**: Stocktwits, Reddit WSB, analyst consensus, insider activity
   - **Value (20%)**: 52-week range position, analyst target gap, dividend yield
   - **Macro (15%)**: VIX, Fear & Greed Index, Put/Call ratio
4. Weighted composite score → ranked → top 20 returned

### Data Sources (22)

| # | Source | Data |
|---|--------|------|
| 1 | Yahoo Finance | Price, fundamentals, earnings, analyst target |
| 2 | SEC EDGAR Form 4 | Insider trading filings |
| 3 | FRED | GDP, unemployment, CPI, Fed funds rate |
| 4 | US Treasury | Yield curve |
| 5 | CBOE VIX | Volatility index |
| 6 | Yahoo Finance RSS | News |
| 7 | Reuters RSS | News |
| 8 | MarketWatch RSS | News |
| 9 | CNBC RSS | News |
| 10 | WSJ RSS | News |
| 11 | Seeking Alpha RSS | Analysis |
| 12 | Barron's RSS | Analysis |
| 13 | Bloomberg RSS | News |
| 14 | IBD RSS | News |
| 15 | Finviz | Screener metrics, technicals |
| 16 | Stocktwits | Social sentiment (bull/bear ratio) |
| 17 | Reddit r/wallstreetbets | Social sentiment, mentions |
| 18 | CNN Fear & Greed | Market sentiment index |
| 19 | CBOE Put/Call Ratio | Options sentiment |
| 20 | SEC 13F | Institutional holdings |
| 21 | Analyst Consensus | Ratings via yfinance |
| 22 | Earnings Calendar | Upcoming earnings dates |

### API

```bash
# Get top 20 recommendations (takes ~30-60s first time, cached 5min)
curl http://localhost:30000/api/portfolio/market/recommendations?count=20

# Get all 22-source data for a single stock
curl http://localhost:30000/api/portfolio/stocks/AAPL/aggregated-data

# Macro dashboard (VIX, Fear & Greed, Put/Call, FRED, Treasury)
curl http://localhost:30000/api/portfolio/market/macro
```

---

## 4. Deals & Shopping

### Deal Sources

| Source | Type |
|--------|------|
| SlickDeals (frontpage + popular) | RSS deals |
| DealNews | RSS deals |
| Ben's Bargains | RSS deals |
| Reddit r/deals | Community deals |
| Reddit r/buildapcsales | Tech deals |
| Reddit r/frugal | Savings tips |
| Reddit r/GameDeals | Gaming deals |

### API

```bash
# Latest deals from all sources
curl http://localhost:30000/api/portfolio/deals/latest

# Search deals by keyword
curl "http://localhost:30000/api/portfolio/deals/latest?query=laptop"

# Check watchlist items for deals
curl -X POST http://localhost:30000/api/portfolio/deals/watchlist-check \
  -H "Content-Type: application/json" \
  -d '["AirPods Pro", "PS5", "4K TV"]'

# Credit card + points recommendations
curl "http://localhost:30000/api/portfolio/deals/credit-cards?category=travel"
```

### Credit Card Points Strategy

| Card | Best For | Earn Rate |
|------|----------|-----------|
| Chase Sapphire Reserve | Travel + Dining | 3x, 1.5cpp portal |
| Amex Platinum | Flights + Lounges | 5x flights |
| Capital One Venture X | Everything | 2x flat, 10x portal |
| Citi Strata Premier | Wide categories | 3x travel/gas/grocery |

### Flight Points Tips

- Transfer Chase UR → Hyatt (best hotel value, 1:1)
- Transfer Amex MR → ANA for Star Alliance (55k RT Japan biz)
- Turkish Miles for United domestic: 7.5k one-way
- Use point.me to search all programs at once

---

## 5. Running the App

### Browser

```bash
cd frontend && npm run dev
# → http://localhost:5173
# Navigate to "Trading" in sidebar for investment dashboard
```

### Mobile (iOS)

```bash
cd AviraApp
npx react-native run-ios --simulator="iPhone 17 Pro"
# Trading tab in bottom navigation
```

### Backend (K8s)

```bash
docker build -t pla-backend:latest -f backend/Dockerfile backend/
kubectl rollout restart deployment/backend -n pla
```

### LLM (Ollama)

```bash
# Check status
curl http://localhost:11434/api/version

# Current model + GPU usage
curl http://localhost:11434/api/ps

# Primary model: deepseek-r1:32b (best for financial analysis)
# Fallback: qwen2.5:14b (100% GPU, 18.8 tok/s)
# Fast: mistral:7b-instruct (100% GPU, 37 tok/s)
```

---

## 6. OpenClaw Integration

### Stock Alerts via OpenClaw

```bash
# Add to pla CLI
pla stock AAPL              # Full analysis
pla stock AAPL --forecast   # Multi-horizon forecast
pla stock AAPL --targets    # Intraday options targets
pla stock-picks             # Top 20 recommendations
pla stock-watch AAPL NVDA   # Add to watchlist
```

### Deal Alerts via OpenClaw

```bash
pla deals                   # Latest deals
pla deals --search "laptop" # Search deals
pla deals --watchlist       # Check watchlist items
pla cards travel            # Credit card recommendations
```

### Email via OpenClaw

```bash
pla emails                  # Unread emails
pla emails --analyze        # Extract action items
pla emails --tasks          # Show pending tasks
```
