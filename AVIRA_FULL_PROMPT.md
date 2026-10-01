# AVIRA — Full Application Prompt

> Copy this prompt into any AI assistant or use it to onboard developers, investors, or collaborators.

---

## What Is AVIRA?

AVIRA (AI Virtual Intelligent Research Assistant) is a **privacy-first, locally-hosted AI personal life assistant** that combines financial intelligence, life management, and document privacy into a single platform. Every piece of data stays on the user's own machine — no cloud, no third-party data sharing. AI inference runs locally via Ollama LLMs.

It is a full-stack production application with:
- **Python/FastAPI backend** (221+ API endpoints)
- **React/Vite web frontend** (21 pages, responsive, dark/light mode)
- **React Native mobile app** (Expo, iOS + Android)
- **Kubernetes deployment** (OrbStack/K3s, 7 microservices)
- **Local LLM inference** (Ollama — qwen2.5:14b, mistral:7b, deepseek-r1:32b)
- **Meridian options trading bot** (XGBoost + Robinhood integration)
- **OpenClaw multi-channel gateway** (WhatsApp, Telegram, iMessage, Slack, Discord, Voice)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy (async), Pydantic |
| **Frontend** | React 18, Vite, TypeScript, Lucide icons, CSS variables (custom design system) |
| **Mobile** | React Native (Expo), TypeScript |
| **Database** | PostgreSQL (users, portfolios, documents, settings) |
| **Cache** | Redis |
| **Vector DB** | Qdrant (document embeddings, semantic search) |
| **Search** | MeiliSearch (full-text search) |
| **LLM** | Ollama — qwen2.5:14b (finance), mistral:7b-instruct (fast), deepseek-r1:32b (deep reasoning), nomic-embed-text (embeddings) |
| **ML** | XGBoost (stock prediction), scikit-learn, yfinance |
| **Orchestration** | Kubernetes (K3s via OrbStack), Docker, Helm-ready |
| **Auth** | JWT (bcrypt passwords), RBAC (admin/user), PostgreSQL-backed |
| **Payments** | Stripe (stubbed, ready to activate) |
| **Privacy** | Presidio NER, custom PII regex, UUID entity masking |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTS                                  │
│  React Web (Vite)  │  React Native (Expo)  │  OpenClaw Gateway  │
│  :30001             │  iOS / Android         │  WhatsApp/Telegram │
└────────┬────────────┴───────────┬────────────┴──────┬───────────┘
         │                        │                    │
         ▼                        ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (:30000)                      │
│  221+ API endpoints across 24 route modules                     │
│  Auth (JWT/RBAC) │ Subscription gating │ Rate limiting          │
├─────────────────────────────────────────────────────────────────┤
│                      SERVICES LAYER                             │
│  46 service modules — finance, trading, privacy, AI, shopping   │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│PostgreSQL│  Redis   │  Qdrant  │MeiliSearch│ Ollama LLMs        │
│  :5432   │  :6379   │  :6333   │  :7700    │ :11434             │
└──────────┴──────────┴──────────┴──────────┴─────────────────────┘
         All running in K8s namespace "pla" on local machine
```

---

## Complete Feature List

### 1. Authentication & Accounts
- **JWT-based auth** with bcrypt password hashing
- **Public self-registration** (`POST /api/auth/signup`) — returns JWT immediately
- **Admin login** (`POST /api/auth/login`) with RBAC roles (admin, user)
- **Local lightweight auth** (`/api/local-auth/*`) — in-memory, no DB dependency
- **Token refresh** and **verification** endpoints
- **User preferences** storage (watchlist, theme, notifications)
- **Admin panel**: list users, update roles, delete users

### 2. Subscription & Monetization
- **3-tier model**: Free ($0), Premium ($9.99/mo), Enterprise ($29.99/mo)
- **Subscription status** endpoint (`GET /api/subscription/status`)
- **Stripe checkout** (stubbed — uncomment + add keys to activate)
- **Webhook handler** for subscription lifecycle events
- **Rate limiting middleware** (`backend/app/middleware/subscription_gate.py`):
  - Free: 3 scans/day, 10 AI calls, 5 documents, 3 alerts
  - Premium: unlimited scans, AI, docs; 50 alerts
  - Enterprise: unlimited everything
- **`subscription_tier` column** on UserDB with auto-migration
- **Pricing page** in frontend (`Subscription.tsx`) with upgrade CTAs

### 3. Trading & Market Intelligence
- **Day Trading Scanner** — RSI, MACD, Bollinger Bands, VWAP, ATR, EMA crossovers. Scans any stock and returns BUY/SELL/HOLD with confidence score.
- **Multi-Horizon Forecasting** (1D / 1W / 1M / 3M / 1Y):
  - Short-term: EMA momentum + ATR channel
  - Medium-term: Linear regression + MACD
  - Long-term: Trend decomposition + seasonal FFT + mean reversion
  - Returns target price, confidence bands, direction, magnitude
- **Intraday Options Targets**:
  - Pivot points (Classic, Woodie, Camarilla)
  - ATR-based CALL and PUT entry/stop/target levels
  - Pattern detection: double top/bottom, higher-high/higher-low, flag, RSI divergence, MACD cross, cup & handle
- **Stock Recommendations Engine**:
  - 50-stock universe scanned across 5 dimensions (technical, fundamental, sentiment, value, macro)
  - Weighted composite scoring → top 10 ranked picks
- **Market Data Aggregator** (22 live sources):
  - Yahoo Finance (price, fundamentals, earnings)
  - SEC EDGAR (Form 4 insider trading)
  - FRED (GDP, unemployment, CPI, interest rates)
  - US Treasury (yield curve)
  - CBOE VIX (volatility)
  - 9 RSS news feeds (Yahoo, Reuters, MarketWatch, CNBC, WSJ, Seeking Alpha, Barrons, Bloomberg, IBD)
  - Finviz (screener metrics)
  - Stocktwits + Reddit r/wallstreetbets (social sentiment)
  - CNN Fear & Greed Index
  - Put/Call Ratio
  - SEC 13F (institutional holdings)
  - Analyst Consensus + Earnings Calendar (yfinance)
- **Market Intelligence Dashboard** (9 tabs):
  - **Overview**: S&P 500, NASDAQ, Dow, VIX, Dollar, 10Y yield, Gold, Oil + 11 sector ETFs
  - **AI Boom Index**: Custom composite of compute chips, semi equipment, hyperscalers, AI software, data networking, energy grid, defense/geopol, rare earth miners
  - **AI Brief**: Ollama qwen2.5:14b synthesizes market snapshot → themes, bullish/bearish setups, watch_today, risk_warnings
  - **Influencers**: 15 tracked personalities (Musk, Cramer, Cathie Wood, Ackman, Burry, Buffett, Powell, Yellen, Saylor, Cook, Nadella, Pichai, Huang, POTUS, Treasury Secretary) with RSS feeds + news sentiment
  - **Geopolitics**: Reuters, BBC, Al Jazeera, Defense News, Bloomberg Politics → conflict detection + risk_level scoring
  - **Big Money**: SEC EDGAR real-time Form 4, 13F-HR, SC 13D/13G filings
  - **SEC Filings**: 8-K, 10-K, 10-Q, S-1, DEF 14A
  - **Tech Breakthroughs**: Hacker News, Ars Technica, MIT Tech Review, TechCrunch, FDA, Nature, Science Daily, ArXiv cs.AI
  - **Resources**: Mining.com, OilPrice, Rigzone, Reuters Commodities
- **Watchlist Alerts**: Price above/below triggers with JSON persistence
- **Earnings Calendar**: Upcoming earnings dates for tracked stocks
- **Unusual Volume Scanner**: Flags stocks with 2x+ average volume
- **Elliott Wave Analysis**: Wave counting on price charts
- **Paper Trading**: $100k virtual portfolio with trade journal
- **Portfolio Analytics**: Holdings, P&L tracking, sector allocation

### 4. Meridian Options Trading Bot
- Separate FastAPI service (`:8200`)
- **XGBoost ML models** trained on 2-year daily OHLCV with 18 technical indicator features
- **Robinhood integration** (client + options trading)
- **Autopilot mode**: automated trade execution based on signals
- **Compliance module**: risk checks, position limits
- **Trading alerts dashboard** (static HTML, `:8201`)
- Pre-trained model universes: ai_boom, watchlist_default, mega cap

### 5. Privacy & Document Intelligence
- **Privacy Masking Pipeline** (Presidio NER + custom regex):
  - PII: Person names, email, phone, address, SSN, driver's license, passport
  - PCI: Credit cards, bank accounts, IBAN, routing numbers
  - HIPAA: Hospital names, medical record #, health plan ID, NPI, DEA
  - SOX: Account numbers, API keys, passwords
- **UUID Entity Masking**: Replaces PII with reversible UUIDs (audit-safe)
- **Document Pipeline**: Image/PDF → OCR → classify → mask PII → LLM analyze
- **Private LLM Middleware**: Automatically masks all prompts before sending to Ollama
- **Secure Document Endpoints**:
  - Upload (image OCR), text analysis, query, list, retrieve
  - Privacy check, audit log with stats

### 6. AI Assistant
- **Multi-model chat** with conversation history and session management
- **Ollama-powered** (qwen2.5:14b primary, mistral:7b fast, deepseek-r1:32b deep)
- **Query classification**: Automatically routes to finance, health, shopping, travel, etc.
- **Enhanced prompts** per domain (finance gets market context, health gets medical context)
- **Privacy-aware**: All prompts pass through masking middleware
- **Global floating assistant** available on every page (AviraAssistant component)

### 7. Finance & Bills
- **Bank statement upload & analysis** (CSV/PDF → categorize → spending insights)
- **Bill tracking**: Upload bills, auto-extract due dates, amounts, payees
- **Spending habits analysis**: Category breakdown, trends, anomalies
- **Financial summary dashboard**: Net worth, income vs. expenses, projections

### 8. Health & Wellness
- **Lab results upload & analysis** (PDF → OCR → extract biomarkers → AI interpretation)
- **Health report generation** with risk assessment
- **Nutrition tracking**: Food logging, macro/micro analysis, meal plans
- **Meal planner**: AI-generated weekly meal plans based on dietary preferences
- **Wellness service**: Activity tracking, sleep, stress management

### 9. Shopping Intelligence
- **Multi-retailer search**: Aggregates prices across retailers
- **Smart shopping assistant**: AI-powered product recommendations
- **Deal crawler**: Finds discounts, coupons, price drops
- **Shopping intelligence**: Price history, best-time-to-buy analysis
- **Dirty Dozen organic guide** integration

### 10. Travel
- **Flight search**: Multi-carrier search with price comparison
- **Travel assistant**: AI trip planning, itinerary generation
- **Travel intelligence**: Destination insights, weather, visa requirements

### 11. Calendar & School
- **Calendar management**: Create, view, filter events by type
- **School calendar sync** (3 sources):
  - Socrates Academy (PDF)
  - LN Charter (PDF)
  - Family Calendar (Google Sheets)
- **Event types**: Holiday, Break, Appointment, Assignment Due, Test, Custom (color-coded)
- **Schoology integration**: OAuth2 login, courses, assignments
- **US holidays auto-load**
- **20+ calendar API endpoints**

### 12. Gmail Integration
- **OAuth2 Gmail connection**: Read unread emails
- **AI email analysis** (qwen2.5:14b): Extract action items, appointments, priorities
- **Action items dashboard**: Track, complete, organize
- **Appointments extraction**: Auto-detect meeting dates

### 13. Family Management
- **Family member profiles**
- **Shared calendar events**
- **Task assignment and tracking**

### 14. News Aggregation
- **Multi-source financial news** (10+ RSS feeds)
- **News filtering** by symbol, category, source
- **Sentiment analysis** on headlines

### 15. Tasks
- **Task creation and management**
- **Priority levels and due dates**
- **Status tracking** (pending, in progress, completed)

---

## Frontend Pages (21 total)

| Page | File | Description |
|------|------|-------------|
| Login/Signup | `Login.tsx` | JWT auth with sign-in/sign-up toggle, glassmorphism UI |
| Dashboard | `Dashboard.tsx` | Home overview with widgets |
| Assistant | `Assistant.tsx` | AI chat interface |
| Finance | `Finance.tsx` | Bank statements, spending analysis |
| Health | `Health.tsx` | Lab results, health reports |
| Shopping | `Shopping.tsx` | Multi-retailer product search |
| Travel | `Travel.tsx` | Flight search, trip planning |
| Grocery | `Grocery.tsx` | Meal ingredients, grocery lists |
| Nutrition | `Nutrition.tsx` | Food logging, macro tracking |
| Family | `Family.tsx` | Family member management |
| Portfolio | `Portfolio.tsx` | Stock holdings, paper trades |
| Trading | `TradingDashboard.tsx` | Robinhood-style dark UI, watchlist, scanner, forecasts, news, recommendations |
| Market Intel | `MarketIntelligence.tsx` | 8-tab intelligence dashboard |
| Forecast | `Forecast.tsx` | Multi-horizon stock forecasting |
| Day Trader | `DayTrader.tsx` | Intraday options targets, pivot points |
| News | `News.tsx` | Aggregated financial news feed |
| School | `School.tsx` | Schoology integration, courses |
| Calendar | `Calendar.tsx` | Events, school sync, holidays |
| Tasks | `Tasks.tsx` | Task management |
| Subscription | `Subscription.tsx` | 3-tier pricing page with FAQ |
| Stock Analysis | `StockAnalysis.tsx` | Deep single-stock analysis |

**Components**: AviraAssistant (floating chat), InteractiveStockChart (53KB, full charting), AdvancedStockChart, ForecastChart, StockChart, InvestmentChat, LlmBadge, Chat

---

## Mobile App (React Native / Expo)

| Screen | Description |
|--------|-------------|
| HomeScreen | Dashboard with feature cards, quick actions |
| TradingScreen | Watchlist, scanner, forecasts, news, Top 10 picks |
| AssistantScreen | AI chat with Ollama |

**Services**: `api.ts` — full API client for backend communication

---

## OpenClaw Multi-Channel Gateway

Bridges AVIRA to messaging platforms:
- **Channels**: iOS, Android, macOS apps, WhatsApp, Telegram, iMessage, Signal, Slack, Discord, Voice Wake, WebChat
- **Bridge**: `pla` CLI (bash+curl) calls AVIRA backend REST API
- **Skills**: Finance, Shopping, Travel, Documents (privacy pipeline), Calendar, Email
- **Identity**: "Avira" personality defined in AGENTS.md + SOUL.md
- **LLM**: Ollama qwen2.5:14b via openclaw.json config

---

## Kubernetes Deployment

All services run in namespace `pla` on local K3s (via OrbStack):

| Service | K8s Resource | Port |
|---------|-------------|------|
| PostgreSQL | Deployment | 5432 |
| Redis | Deployment | 6379 |
| Qdrant | Deployment/StatefulSet | 6333 |
| MeiliSearch | Deployment | 7700 |
| Backend (FastAPI) | Deployment | 8000 → NodePort 30000 |
| Frontend (Nginx) | Deployment | 80 → NodePort 30001 |
| Ollama | External (localhost) | 11434 |
| Meridian Bot | External (localhost) | 8200 |
| Alerts Dashboard | Static HTTP | 8201 |

**Scripts** (in `scripts/`):
- `avira-start.sh` — Orchestrates OrbStack → K8s → Ollama → Meridian → Alerts Dashboard
- `avira-stop.sh` — Graceful shutdown of all services
- `avira-status.sh` — Health check of all components
- `avira-redeploy-backend.sh` — Docker build → K8s rollout (backend)
- `avira-redeploy-frontend.sh` — Docker build → K8s rollout (frontend)
- `avira-models.sh` — Manage Ollama model downloads
- `setup-duckdns.sh` — Dynamic DNS for external access (aviraa.duckdns.org)
- `deploy-gpu.sh` — GPU-accelerated deployment

---

## API Endpoint Summary (~221 routes)

| Module | Prefix | Key Endpoints |
|--------|--------|---------------|
| Auth | `/api/auth` | signup, login, me, users, roles, init-admin |
| Local Auth | `/api/local-auth` | login, register, verify, refresh, preferences |
| Subscription | `/api/subscription` | tiers, status, create-checkout-session, webhook, cancel |
| Trading | `/api/trading` | scan/{symbol}, watchlist, alerts, earnings, unusual-volume |
| Market Intel | `/api/market-intel` | overview, ai-boom, influencers, geopolitics, big-money, sec-filings, tech-breakthroughs, resources, earnings/{symbol}, snapshot, synthesis |
| Forecast | `/api/forecast` | long-term/{symbol}, models-used |
| Portfolio | `/api/portfolio` | holdings, trade, history, stocks/{symbol}/forecast, intraday-targets, aggregated-data, market/news, market/macro, market/recommendations |
| Documents | `/api/documents` | secure/upload, secure/text, secure/query, secure/list, privacy/check, privacy/audit |
| Finance | `/api/finance` | upload-statement, summary |
| Bills | `/api/bills` | upload, list, summary, spending-habits |
| Health | `/api/health` | upload-lab-results, report |
| Shopping | `/api/shopping` | search, deals, intelligence |
| Travel | `/api/travel` | flights, assistant, intelligence |
| Grocery | `/api/grocery` | meal-plan, ingredients |
| Nutrition | `/api/nutrition` | log, analysis, plan |
| Family | `/api/family` | members, tasks |
| Calendar | `/api/calendar` | events, upcoming, sync-school, sync-all-schools, holidays |
| School | `/api/school` | schoology/auth, courses, assignments |
| Tasks | `/api/tasks` | create, list, update, complete |
| News | `/api/news` | feed, by-symbol |
| Gmail | `/api/integrations/gmail` | auth, callback, emails, analyze, status, disconnect |
| Action Items | `/api/integrations` | action-items, appointments |
| Assistant | `/api/assistant` | chat, sessions, privacy/check, privacy/mask, stats |
| AI | `/api/ai` | chat, classify, models |
| User Settings | `/api/user-settings` | features, preferences |
| Home | `/api/home` | dashboard |
| Wellness | `/api/wellness` | status, activities |

---

## Data Flow Examples

### User Signs Up → Scans a Stock → Gets AI Brief
```
1. POST /api/auth/signup {username, email, password}
   → Creates user in PostgreSQL, returns JWT

2. GET /api/trading/scan/NVDA (Authorization: Bearer <token>)
   → Backend fetches yfinance data, computes RSI/MACD/Bollinger/VWAP/ATR/EMA
   → Returns: {signal: "BUY", price: 135.20, confidence: 72, indicators: {...}}

3. GET /api/market-intel/synthesis (Authorization: Bearer <token>)
   → Aggregates all 22 data sources into compact snapshot
   → Sends to Ollama qwen2.5:14b with strict-JSON prompt
   → Returns: {themes: [...], bullish_setups: [...], risk_warnings: [...]}
```

### User Uploads a Medical Document
```
1. POST /api/documents/secure/upload (file: lab_results.pdf)
   → OCR extracts text
   → Presidio NER detects: PERSON, SSN, HOSPITAL, MEDICAL_RECORD
   → Replaces each with UUID: "John Smith" → "[PERSON_a3f2b1c4]"
   → Classifies document type: "medical_lab_results"
   → Sends masked text to Ollama for analysis
   → Returns: {doc_uuid, classification, entities_masked: 8, analysis: "..."}
```

---

## Project Structure

```
pla-avira/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, 221+ routes
│   │   ├── config.py                  # Settings (env-based)
│   │   ├── database.py                # PostgreSQL + ORM models + migrations
│   │   ├── middleware/
│   │   │   └── subscription_gate.py   # Rate limiting + tier gating
│   │   ├── models/
│   │   │   ├── user.py                # UserDB (with subscription_tier)
│   │   │   └── email.py               # Email models
│   │   ├── routes/                    # 24 route modules
│   │   ├── services/                  # 46 service modules
│   │   ├── integrations/              # Gmail, Schoology, Ollama, yfinance
│   │   └── agents/                    # AI agent definitions
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx                    # Auth-gated main app with sidebar nav
│   │   ├── pages/                     # 21 page components
│   │   ├── components/                # 8 shared components
│   │   ├── api/client.ts              # Axios client with JWT interceptor
│   │   └── config.ts                  # API base URL config
│   ├── Dockerfile
│   └── package.json
├── AviraApp/                          # React Native mobile app
│   ├── App.tsx                        # Tab navigation (Home, Trading, Assistant)
│   └── src/screens/                   # 3 screens
├── meridian/                          # Options trading bot
│   ├── backend/app/
│   │   ├── options_bot.py             # Core trading logic
│   │   ├── autopilot.py               # Automated execution
│   │   ├── compliance.py              # Risk checks
│   │   └── robinhood_client.py        # Broker integration
│   └── research/                      # XGBoost training pipeline
├── openclaw/                          # Multi-channel gateway
│   ├── workspace/
│   │   ├── AGENTS.md                  # Avira identity
│   │   ├── tools/pla                  # CLI bridge to backend
│   │   └── skills/                    # Finance, Shopping, Travel, Docs, Calendar, Email
│   └── openclaw.json                  # Gateway config
├── k8s/                               # Kubernetes manifests (8 services)
├── scripts/                           # 14 operational scripts
├── mobileapp/                         # Alternative single-file mobile app
└── AVIRA_MONETIZATION_STRATEGY.md     # Business plan & gap analysis
```

---

## Key Numbers

| Metric | Count |
|--------|-------|
| API endpoints | 221+ |
| Route modules | 24 |
| Service modules | 46 |
| Frontend pages | 21 |
| Frontend components | 8 |
| Mobile screens | 3 |
| Data sources (market) | 22 |
| Tracked influencers | 15 |
| PII entity types detected | 18 |
| K8s services | 7+ |
| Ollama models | 4 |
| Lines of Python (backend) | ~15,000+ |
| Lines of TypeScript (frontend) | ~12,000+ |

---

## Monetization Model

| Plan | Price | Limits |
|------|-------|--------|
| Free | $0 | 3 scans/day, 10 AI calls, 5 docs, basic market overview |
| Premium | $9.99/mo | Unlimited scans + AI, full market intel, SEC filings, 50 alerts |
| Enterprise | $29.99/mo | Everything unlimited, API access, multi-user, auto-trading bot |

Stripe integration is stubbed and ready — just add API keys and uncomment ~20 lines of code.

---

## How to Run

```bash
# Start everything (OrbStack + K8s + Ollama + Meridian + Alerts)
./scripts/avira-start.sh

# Access
# Frontend:  http://localhost:30001 (login page)
# Backend:   http://localhost:30000 (API + /docs for Swagger)
# Meridian:  http://localhost:8200
# Alerts:    http://localhost:8201/trading-alerts.html
# Ollama:    http://localhost:11434

# Redeploy after code changes
./scripts/avira-redeploy-backend.sh
./scripts/avira-redeploy-frontend.sh

# Check status
./scripts/avira-status.sh

# Stop everything
./scripts/avira-stop.sh
```

---

*Built with privacy at the core. Your data never leaves your machine.*
