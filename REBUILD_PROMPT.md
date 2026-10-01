# Avira PLA - Complete Rebuild Prompt

## Project Overview
Build a **Personal Life Assistant (PLA)** application - an enterprise-grade, AI-powered platform that simplifies daily activities including investment portfolio management, smart shopping, travel planning, nutrition tracking, and news aggregation. The app must be production-ready with real-time data, GPU-accelerated AI analysis, and support for both US and Indian markets.

---

## Core Requirements

### 1. Platform Support
- **Web Application** (React + TypeScript)
- **iOS Mobile App** (React Native + Expo SDK 54)
- **Android Mobile App** (React Native + Expo SDK 54)
- **Backend API** (FastAPI + Python)
- **Deployment** (Kubernetes for services, Mac host for GPU workloads)

### 2. Key Features

#### A. Investment Portfolio & Analysis
**Must Have:**
- Real-time stock price tracking (US & Indian markets)
- Comprehensive technical analysis (RSI, MACD, Elliott Wave, Support/Resistance)
- AI-powered stock recommendations with confidence scores
- Options trading strategies (Covered Call, Cash-Secured Put, Long Call)
- Interactive price charts with 30-day history
- Portfolio holdings management (add/remove stocks)
- Detailed AI analysis (minimum 1,800+ characters)
- Investment Assistant chatbot with context-aware responses
- Real-time analysis feed showing data sources

**Stock Symbol Detection:**
- Prioritize investment queries over shopping
- Detect all-caps words (2-5 letters) as stock symbols
- Investment keywords: stock, option, invest, call, put, trade, buy, sell

**Options Trading:**
- 3+ strategies with Greeks (Delta, Gamma, Theta, Vega)
- Insider trading tracking
- Institutional holdings data
- Earnings calendar
- Best approach recommendations

#### B. News & Markets
**Must Have:**
- **Knowledge Pill** - Daily market brief with:
  - 5 key takeaways
  - Top gainers/losers with reasons
  - Sector performance
  - Action items
  
- **Reuters** - Financial news headlines with market impact
- **TheHackerNews** - Cybersecurity threats affecting sectors
- **Financial News** - Global, USA, India regions
- **Tech News** - Innovations, disruptions, AI breakthroughs
- **Market Influencers** - Track statements from:
  - Elon Musk (Tesla CEO)
  - Jerome Powell (Fed Chair)
  - Donald Trump (US President)
  - Warren Buffett (Berkshire Hathaway CEO)
  - Include recent statements, affected stocks, market impact
  
- **Indian Market** - NSE/BSE indices:
  - Nifty 50, Sensex, Bank Nifty
  - Government decisions (Budget, PLI schemes, Digital India)
  - Affected stocks (L&T, TCS, Infosys, Tata Steel, etc.)
  
- **Investment Firms** - Track activity from:
  - Berkshire Hathaway (top holdings, recent buys/sells)
  - BlackRock (AI/tech focus)
  - Vanguard (passive indexing)

#### C. Smart Shopping
**Must Have:**
- Product search with realistic pricing ($20-40 range)
- Multiple retailers (Amazon, Walmart, Target, Best Buy)
- Price comparison
- Product ratings and reviews
- Real-time availability

#### D. Travel Planning
**Must Have:**
- Flight search with realistic pricing (distance-based)
- Multiple airlines (Delta, United, American, Southwest)
- Cabin classes (Economy, Premium Economy, Business, First)
- Hotel recommendations
- Itinerary planning
- AI-powered travel suggestions

#### E. Nutrition Tracking
**Must Have:**
- Meal logging
- Calorie tracking
- Nutritional analysis
- Dietary recommendations

#### F. User Management
**Must Have:**
- JWT authentication
- User registration/login
- Subscription tiers (Free, Premium, Enterprise)
- Profile management

---

## Technical Stack

### Frontend (Web)
```
- React 18+
- TypeScript
- Vite (build tool)
- TailwindCSS (styling)
- Lucide React (icons)
- Recharts (charts)
- React Router (navigation)
```

### Mobile App
```
- React Native
- Expo SDK 54
- React 19.1.0
- TypeScript
- Expo Router
- React Native Reanimated 3.16.4
- React Native Gesture Handler 2.20.2
```

### Backend
```
- FastAPI (Python 3.11+)
- PostgreSQL (database)
- Redis (caching)
- Qdrant (vector database)
- MeiliSearch (search engine)
- Ollama (GPU-accelerated LLM - mistral:7b-instruct)
- JWT authentication
- CORS enabled
```

### Deployment
```
- Kubernetes (K8s) for containerized services
- Docker (multi-platform: linux/arm64, linux/amd64)
- Mac host for GPU workloads (Ollama)
- NodePort services (30000-32767 range)
```

---

## Data Sources & APIs

### Stock Market Data
**Primary Source:** Yahoo Finance (yfinance Python library)
```python
import yfinance as yf

# Real-time stock data
ticker = yf.Ticker("AAPL")
info = ticker.info
history = ticker.history(period="1mo")

# Technical indicators
# Calculate RSI, MACD, SMA, EMA
```

**Indian Market:**
- NSE (National Stock Exchange)
- BSE (Bombay Stock Exchange)
- Symbols: RELIANCE.NS, TCS.NS, INFY.NS, etc.

**US Market:**
- NYSE, NASDAQ
- Symbols: AAPL, MSFT, GOOGL, TSLA, SHOP, etc.

### News Sources
**Reuters:**
- URL: https://www.reuters.com/markets/us
- Scrape headlines, summaries, market impact
- Categories: monetary_policy, earnings, geopolitical

**TheHackerNews:**
- URL: https://thehackernews.com
- Cybersecurity threats
- Affected sectors: Technology, Finance

**Financial News:**
- Economic Times (India): https://economictimes.indiatimes.com
- Moneycontrol (India): https://www.moneycontrol.com
- Business Standard (India): https://www.business-standard.com
- Yahoo Finance News
- Seeking Alpha
- CNBC, Bloomberg

**Tech News:**
- TechCrunch
- The Verge
- Ars Technica
- Trending topics: AI, Quantum Computing, Renewable Energy, Space Tech, Biotech

### Market Influencers
**Track via:**
- Twitter/X API (for Elon Musk)
- WhiteHouse.gov (Presidential statements)
- FOMC Press Conferences (Fed Chair)
- SEC 13F Filings (Warren Buffett/Berkshire)
- Official press releases

### Institutional Data
**Sources:**
- OpenInsider (insider trading)
- Dataroma (hedge fund holdings)
- SEC EDGAR (13F, 10-K, 10-Q filings)
- Unusual Whales (options flow)

### Shopping Data
**Scrape from:**
- Amazon Product API
- Walmart API
- Target API
- Best Buy API
- Google Shopping

### Travel Data
**Flight APIs:**
- Amadeus API
- Skyscanner API
- Google Flights
- Airline direct APIs (Delta, United, American, Southwest)

**Hotel APIs:**
- Booking.com API
- Expedia API
- Hotels.com API

### AI/LLM
**Ollama (Local GPU):**
- Model: mistral:7b-instruct
- Host: Mac with GPU acceleration
- API: http://localhost:11434
- Use for: Stock analysis, investment recommendations, chat assistant

---

## Backend Architecture

### API Routes Structure
```
/api/auth/*          - Authentication (login, register, token refresh)
/api/portfolio/*     - Stock portfolio management
  - /holdings        - Get/add/remove holdings
  - /stocks/{symbol}/comprehensive - Detailed stock analysis
  - /stocks/{symbol}/options - Options trading strategies
  - /stocks/{symbol}/chart - Historical price data
  
/api/assistant/*     - AI chatbot
  - /chat            - Multi-modal assistant with intent detection
  
/api/news/*          - News aggregation
  - /knowledge-pill  - Daily market brief
  - /financial/daily - Financial news (global/usa/india)
  - /tech/daily      - Tech innovations
  - /reuters         - Reuters headlines
  - /hackernews      - Cybersecurity news
  - /influencers     - Market influencers tracking
  - /india/market    - Indian market news
  - /investment-firms - Top investment firms activity
  
/api/shopping/*      - Smart shopping
  - /search          - Product search
  - /compare         - Price comparison
  
/api/travel/*        - Travel planning
  - /flights/search  - Flight search
  - /hotels/search   - Hotel search
  
/api/nutrition/*     - Nutrition tracking
  - /meals           - Meal logging
  - /analysis        - Nutritional analysis
  
/api/subscription/*  - Subscription management
  - /plans           - Available plans
  - /subscribe       - Subscribe to plan
```

### Database Schema
**Users Table:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Holdings Table:**
```sql
CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    symbol VARCHAR(10) NOT NULL,
    shares DECIMAL(10, 4) NOT NULL,
    cost_basis DECIMAL(10, 2) NOT NULL,
    purchase_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Chat History Table:**
```sql
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    message TEXT NOT NULL,
    response TEXT NOT NULL,
    intent VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## AI Analysis Logic

### Stock Analysis Prompt
```python
prompt = f"""
Analyze {symbol} stock with the following data:

CURRENT PRICE: ${current_price}
CHANGE: {change_percent}%
TREND: {trend}

TECHNICAL INDICATORS:
- RSI: {rsi} (Oversold < 30, Overbought > 70)
- SMA 20: ${sma_20}
- SMA 50: ${sma_50}
- Support: ${support}
- Resistance: ${resistance}
- Elliott Wave: {wave_pattern}

MARKET SENTIMENT:
- Social Media: {social_sentiment}
- News Sentiment: {news_sentiment}

MACROECONOMIC FACTORS:
- Fed Policy: {fed_policy}
- Sector Performance: {sector_performance}

Provide:
1. INVESTMENT RATING (BUY/HOLD/SELL)
2. PRICE TARGETS (1-month, 3-month, 6-month)
3. RISK ASSESSMENT (Low/Medium/High)
4. KEY FACTORS ANALYZED
5. ENTRY/EXIT STRATEGY

Analysis must be detailed (minimum 1,800 characters).
"""
```

### Options Trading Analysis
```python
prompt = f"""
Analyze options strategies for {symbol}:

CURRENT PRICE: ${current_price}
VOLATILITY: {implied_volatility}%
EARNINGS DATE: {earnings_date}

AVAILABLE STRATEGIES:
1. Covered Call (Income generation)
2. Cash-Secured Put (Entry strategy)
3. Long Call (Bullish play)

INSIDER ACTIVITY:
{insider_trades}

INSTITUTIONAL HOLDINGS:
{institutional_holdings}

Recommend best strategy with:
- Strike prices
- Expiration dates
- Expected returns
- Risk/reward ratio
"""
```

### Investment Assistant Intent Detection
```python
# Priority order:
1. Finance/Investment (stock, option, invest, call, put, trade)
   - Detect all-caps symbols (2-5 letters)
   - Fetch stock + options data
   - Provide investment context

2. Shopping (buy, purchase, product, price)
   - Search products
   - Compare prices

3. Travel (flight, hotel, trip, vacation)
   - Search flights/hotels
   - Plan itinerary

4. Nutrition (meal, calories, diet, nutrition)
   - Log meals
   - Analyze nutrition

5. General (fallback to Ollama LLM)
```

---

## UI/UX Requirements

### Web Application
**Navigation:**
- Sidebar with tabs:
  - Dashboard
  - Portfolio
  - News & Markets
  - Shopping
  - Travel
  - Nutrition
  - Settings

**Portfolio Page:**
- Holdings list with current prices
- Add/remove stock modal
- Stock detail modal with:
  - Interactive price chart (30-day history)
  - Technical analysis (RSI, trend, support/resistance)
  - AI recommendation with confidence
  - Options strategies
- Investment Assistant chat sidebar
- Real-time analysis feed

**News Page:**
- Tabs: Knowledge Pill, Financial, Tech, Market Influencers
- Card-based layout
- Color-coded impact (bullish/bearish/neutral)
- Affected stocks chips
- External links to sources

### Mobile App
**Design Requirements:**
- Modern, attractive UI (not basic)
- Smooth animations
- Gesture support
- Dark mode support
- Bottom tab navigation
- Pull-to-refresh
- Real-time data updates
- No demo data fallbacks

**Stock Modal:**
- Price chart visualization (bar chart)
- Technical analysis cards
- AI analysis with confidence badge
- Swipe gestures for navigation

---

## Deployment Configuration

### Kubernetes Manifests

**Backend Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: pla
spec:
  replicas: 1
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: pla-backend:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://pla_user:pla_password@postgres:5432/pla_db"
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: OLLAMA_BASE_URL
          value: "http://host.docker.internal:11434"
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: pla
spec:
  type: NodePort
  ports:
  - port: 8000
    targetPort: 8000
    nodePort: 30000
  selector:
    app: backend
```

**Frontend Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: pla
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: pla-frontend:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: pla
spec:
  type: NodePort
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30001
  selector:
    app: frontend
```

**PostgreSQL, Redis, Qdrant, MeiliSearch:**
- Similar deployment patterns
- Persistent volumes for data
- NodePort services for external access

### Ollama Setup (Mac Host)
```bash
# Install Ollama
brew install ollama

# Pull model
ollama pull mistral:7b-instruct

# Run with GPU acceleration
ollama serve

# API available at: http://localhost:11434
```

---

## Critical Implementation Details

### 1. Real-Time Stock Data
**NEVER use demo/fallback data**
```typescript
// Mobile app - MUST fail gracefully
try {
  const response = await fetch(`${API_BASE}/api/portfolio/stocks/${symbol}/comprehensive`);
  const data = await response.json();
  if (data.success) {
    setStockData(data);
  }
} catch (error) {
  Alert.alert('Error', `Failed to load ${symbol} data. Please check your connection.`);
  setShowModal(false);
  // DO NOT show demo data
}
```

### 2. Price Realism
**Shopping:**
- Products: $20-40 range
- Variation by category: Electronics (higher), Groceries (lower)

**Flights:**
- Distance-based pricing
- Short haul (< 500 miles): $80-250
- Medium haul (500-1500 miles): $150-400
- Long haul (> 1500 miles): $300-800
- Cabin class multipliers: Economy (1x), Premium (1.5x), Business (3x), First (5x)

### 3. AI Analysis Quality
**Minimum Requirements:**
- 1,800+ characters
- 250+ words
- Detailed reasoning
- Specific price targets
- Risk assessment
- Entry/exit strategy

### 4. Options Trading Display
**Must Show:**
- Strategy name (Covered Call, Cash-Secured Put, Long Call)
- Strike price
- Expiration date
- Expected return
- Risk/reward ratio
- Greeks (Delta, Gamma, Theta, Vega)
- Best approach recommendation

### 5. Mobile App Network Configuration
**API Base URL:**
```typescript
// iOS Simulator
const API_BASE = 'http://localhost:30000';

// Physical Device
const API_BASE = 'http://192.168.86.33:30000'; // Replace with your Mac IP
```

---

## Testing & Verification

### API Endpoints to Test
```bash
# Health check
curl http://localhost:30000/health

# Stock analysis
curl "http://localhost:30000/api/portfolio/stocks/AAPL/comprehensive"

# Options trading
curl "http://localhost:30000/api/portfolio/stocks/AAPL/options"

# News endpoints
curl "http://localhost:30000/api/news/knowledge-pill"
curl "http://localhost:30000/api/news/reuters"
curl "http://localhost:30000/api/news/influencers"
curl "http://localhost:30000/api/news/india/market"
curl "http://localhost:30000/api/news/investment-firms"

# Shopping
curl "http://localhost:30000/api/shopping/search?query=laptop"

# Travel
curl "http://localhost:30000/api/travel/flights/search?origin=JFK&destination=LAX&departure_date=2026-03-15"
```

### Expected Results
- Stock price: Real-time from Yahoo Finance
- AI analysis: 1,800+ characters
- Options: 3 strategies with recommendations
- News: Multiple sources with market impact
- Shopping: Realistic prices ($20-40)
- Flights: Distance-based pricing

---

## Future Enhancements (from Gemini Feedback)

### 1. Earnings Calendar Integration
- Track upcoming earnings dates
- Whisper numbers
- Historical beat/miss rates

### 2. Institutional Order Flow
- Dark pool activity
- Options flow (sweeps, blocks)
- Unusual options activity

### 3. Alternative Data Sources
- Web traffic (SimilarWeb)
- Credit card transactions
- Job postings (Glassdoor, Blind)
- App downloads

### 4. Sentiment Divergence Detection
- Reddit bullish vs institutions bearish
- Contrarian indicators

### 5. Volatility Gap Detection
- Intraday reversals
- Bollinger Bands
- Volatility clustering

### 6. Advanced Technical Analysis
- Fibonacci retracements
- Ichimoku Cloud
- Volume profile
- Order book analysis

---

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Web UI | http://localhost:30001 | Main web application |
| Backend API | http://localhost:30000 | REST API |
| Mobile App | exp://192.168.86.33:8081 | React Native app |
| Ollama | http://localhost:11434 | LLM inference |
| PostgreSQL | localhost:30432 | Database |
| Redis | localhost:30379 | Cache |
| Qdrant | localhost:30333 | Vector DB |
| MeiliSearch | localhost:30700 | Search engine |

---

## Success Criteria

✅ **Real-time data** - No demo fallbacks
✅ **Accurate pricing** - Realistic for all features
✅ **Detailed AI analysis** - 1,800+ characters
✅ **Options trading** - 3+ strategies with recommendations
✅ **Multi-market support** - US and Indian markets
✅ **News aggregation** - Multiple sources with impact analysis
✅ **Market influencers** - Track key personalities
✅ **Investment firms** - Monitor institutional activity
✅ **Modern UI** - Attractive, responsive, smooth animations
✅ **Production-ready** - Kubernetes deployment, health checks, error handling

---

## Build Commands

### Backend
```bash
cd backend
docker build --platform linux/arm64 -t pla-backend:latest .
kubectl apply -f k8s/backend-deployment.yaml
```

### Frontend
```bash
cd frontend
docker build --platform linux/arm64 -t pla-frontend:latest .
kubectl apply -f k8s/frontend-deployment.yaml
```

### Mobile App
```bash
cd mobileapp

npm install
npx expo start --no-dev
```

### Ollama (Mac Host)
```bash
ollama serve
ollama pull mistral:7b-instruct
```

---

## Environment Variables

### Backend (.env)
```
DATABASE_URL=postgresql://pla_user:pla_password@postgres:5432/pla_db
REDIS_URL=redis://redis:6379
OLLAMA_BASE_URL=http://host.docker.internal:11434
JWT_SECRET=your-secret-key-here
QDRANT_URL=http://qdrant:6333
MEILI_URL=http://meili:7700
```

### Frontend (.env)
```
VITE_API_BASE_URL=http://localhost:30000
```

### Mobile App
```typescript
const API_BASE = __DEV__ 
  ? 'http://localhost:30000'  // Simulator
  : 'http://192.168.86.33:30000';  // Device
```

---

## Summary

This is a comprehensive, production-grade Personal Life Assistant with:
- **Real-time investment analysis** powered by GPU-accelerated AI
- **Multi-market support** (US & Indian stock markets)
- **Comprehensive news aggregation** from Reuters, TheHackerNews, and market influencers
- **Smart shopping** with realistic pricing
- **Travel planning** with distance-based flight pricing
- **Options trading strategies** with institutional tracking
- **Modern, attractive UI** for web and mobile
- **Kubernetes deployment** with health monitoring
- **No demo data** - all real-time or graceful failures

The app is designed to be the **best possible investment and life assistant** for users, with accurate data, intelligent analysis, and beautiful UX.
