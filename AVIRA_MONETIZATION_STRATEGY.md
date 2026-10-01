# AVIRA — Monetization Blueprint & Gap Analysis

*Last updated: May 16, 2026*

---

## Part 1: What You Have (Working Today)

### Infrastructure ✅
| Component | Status | Details |
|-----------|--------|---------|
| Backend (FastAPI) | ✅ Live | 221 API routes, K8s deployed, PostgreSQL + Redis + Qdrant + Meilisearch |
| Frontend (React/Vite) | ✅ Live | 18 pages, dark/light mode, responsive |
| Mobile (Expo/RN) | ✅ Built | Trading, Market Intel, Finance, Shopping, Calendar screens |
| Authentication | ✅ Live | JWT signup/login, bcrypt passwords, admin RBAC, PostgreSQL-backed |
| Subscription Backend | ✅ Live | 3 tiers (Free/$9.99/$29.99), Stripe stubs, usage tracking |
| Login + Signup UI | ✅ Live | Beautiful auth page with registration, password visibility toggle |
| Subscription UI | ✅ Live | 3-tier pricing page with FAQ, wired to backend |
| Local LLM (Ollama) | ✅ Live | qwen2.5:14b for finance, mistral:7b for fast, deepseek-r1:32b for deep |

### Features ✅
| Feature | Free Tier? | Premium? | Notes |
|---------|-----------|----------|-------|
| AI Assistant (chat) | 10/day | Unlimited | Ollama-powered, multi-model |
| Stock Analysis (22 sources) | Basic | Full | yfinance + SEC + FRED + RSS + social |
| Day Trading Scanner | 3 scans/day | Unlimited | RSI, MACD, Bollinger, VWAP, ATR, EMA |
| Paper Trading ($100k) | ✅ | ✅ | Paper only, no real money |
| Market Intelligence | Overview only | All 9 tabs | AI Boom, Influencers, SEC, Geopolitics |
| Price Alerts | 3 alerts | Unlimited | Above/below triggers |
| Earnings Calendar | ✅ | ✅ | yfinance earnings dates |
| Unusual Volume Scanner | ❌ | ✅ | 2x avg volume threshold |
| SEC Filings Deep Dive | ❌ | ✅ | Form 4, 13F, 8-K, 10-K, S-1 |
| Forecasting (5 horizons) | 1 stock | Unlimited | 1D/1W/1M/3M/1Y |
| Privacy Pipeline (OCR + PII) | 5 docs | Unlimited | Presidio NER + UUID masking |
| Shopping Search | ✅ | ✅ | Multi-retailer |
| Calendar + School Sync | ✅ | ✅ | Socrates, LN Charter, Google Sheets |
| Gmail Integration | ✅ | ✅ | Action items + appointments |
| Document Analysis | 5/day | Unlimited | OCR → classify → mask → LLM analyze |

---

## Part 2: What's MISSING to Monetize (The Gaps)

### 🔴 CRITICAL — Must Have Before Charging Money

#### 1. Stripe Payment Integration (1-2 days)
**Status:** Backend stubs exist but no real Stripe keys.
**What to do:**
1. Create Stripe account at https://stripe.com
2. Get API keys (test mode first, then live)
3. Create 2 Products + Prices in Stripe Dashboard:
   - Premium: $9.99/mo recurring
   - Enterprise: $29.99/mo recurring
4. Add keys to backend config:
   ```
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_PUBLISHABLE_KEY=pk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PREMIUM_PRICE_ID=price_...
   STRIPE_ENTERPRISE_PRICE_ID=price_...
   ```
5. Uncomment the Stripe code in `backend/app/routes/subscription.py` (lines 125-148)
6. Add `stripe` to `requirements.txt`
7. Set up Stripe webhook endpoint for subscription lifecycle events

**Legal note:** Stripe handles PCI compliance. You don't touch credit card numbers.

#### 2. Rate Limiting / Feature Gating Middleware (1 day)
**Status:** All endpoints are open — no enforcement of free vs. premium limits.
**What to do:**
Create a middleware that checks the user's subscription tier before allowing access:
```python
# Example: backend/app/middleware/subscription_gate.py
async def require_premium(current_user: UserDB = Depends(get_current_user)):
    if current_user.subscription_tier not in ("premium", "enterprise"):
        raise HTTPException(403, "Premium subscription required")
    return current_user
```
Apply to: trading/auto-scan, unusual-volume, full market-intel tabs, unlimited AI calls.

#### 3. `subscription_tier` Column on UserDB (30 min)
**Status:** The UserDB model has no `subscription_tier` field. The subscription routes use `getattr(current_user, 'subscription_tier', 'free')` which always returns 'free'.
**What to do:**
Add `subscription_tier = Column(String, default="free")` to the UserDB model and run an Alembic migration.

#### 4. Terms of Service + Privacy Policy Pages (1 day)
**Status:** None exist.
**What you need:**
- **Terms of Service** — "Paper trading only, not financial advice, no liability."
- **Privacy Policy** — "Data processed locally, no third-party sharing." This is your #1 selling point.
- **Disclaimer** — "AVIRA is an educational tool. Signals are not investment advice."
- Can use a generator like Termly.io or hire a lawyer ($200-500 for templates).
- **Required by:** App Store, Google Play, Stripe, and CCPA/GDPR.

#### 5. Email Sending (Transactional) (2-3 hours)
**Status:** No email sending capability.
**What you need:**
- Welcome email on signup
- Password reset flow
- Subscription confirmation / receipt
- Price alert notifications
- **Recommended:** Resend.com (free 3k emails/mo) or SendGrid (free 100/day)

### 🟡 IMPORTANT — Needed for Growth

#### 6. Landing Page / Marketing Site (1-2 days)
**Status:** The app goes straight to login. No public-facing marketing page.
**What you need:**
- Hero section with screenshots
- Feature comparison grid
- Pricing table (mirrors the in-app subscription page)
- "Start Free" CTA → signup
- SEO meta tags for Google
- **Options:** Deploy a separate Next.js/Astro site, or add a public landing route to the existing frontend.

#### 7. App Store Deployment (1-2 weeks)
**Status:** Mobile app built but not published.
**What you need:**
- **Apple Developer Account:** $99/year
- **Google Play Console:** $25 one-time
- Build with EAS (`eas build --platform all`)
- App Store review takes 1-3 days (Apple), 1-7 days (Google)
- **In-App Purchases:** Apple takes 30% of subscriptions (15% after year 1). Consider using Stripe for web-only subscriptions to avoid the "Apple tax."

#### 8. Analytics / Telemetry (few hours)
**Status:** No usage tracking at all.
**What you need:**
- PostHog (free, self-hosted) or Mixpanel (free tier)
- Track: signups, page views, scan frequency, conversion to paid
- Essential for knowing what features to build next

#### 9. Onboarding Flow (1 day)
**Status:** New users land on a blank dashboard.
**What you need:**
- Welcome modal: "Here's what Avira can do"
- Guided tour: "Try scanning NVDA" → "Check Market Intel" → "Set a price alert"
- Default watchlist pre-populated
- First-scan experience that shows value immediately

### 🟢 NICE TO HAVE — Accelerates Revenue

| Feature | Effort | Revenue Impact |
|---------|--------|----------------|
| **Broker referral (Alpaca/Webull)** | 2 days | $50-200/referral |
| **Affiliate links in Shopping** | 1 day | 2-5% commission per purchase |
| **Daily AI Market Brief email** | 1 day | Content marketing + premium upsell |
| **Discord community** | 2 hours | User retention + word of mouth |
| **Push notifications (Firebase)** | 1 day | Engagement + alert monetization |
| **Backtesting engine** | 3-5 days | Premium differentiator |
| **Crypto scanner (CoinGecko)** | 1 day | Expand TAM |
| **Social leaderboard** | 2 days | Viral growth |

---

## Part 3: Legal & Compliance

### What You CAN Do Without Registration
- ✅ **Paper trading** — No SEC/FINRA registration needed
- ✅ **General market data display** — Public data (prices, SEC filings, news)
- ✅ **AI-generated analysis** — Falls under "publisher exemption" if not personalized
- ✅ **Educational content** — "Learn to trade" courses, tutorials
- ✅ **SaaS subscription** — Selling access to a software tool

### What Requires Caution
- ⚠️ **"Buy AAPL" signals** — If personalized, may require Investment Adviser registration (SEC/state)
- ⚠️ **Real trade execution** — Must go through registered broker-dealer (Alpaca, IBKR handle this)
- ⚠️ **Managing other people's money** — Requires RIA registration
- ⚠️ **Crypto signals** — Regulatory landscape is murky; add disclaimers

### Safe Harbor: What to Put on Every Page
```
"AVIRA is an educational and research tool. Nothing displayed constitutes
investment advice, a recommendation, or solicitation to buy or sell securities.
Past performance does not guarantee future results. Paper trading uses
simulated money only. Always consult a licensed financial advisor."
```

### Required Legal Documents
1. **Terms of Service** — Liability limitation, acceptable use, subscription terms
2. **Privacy Policy** — Data collection (none!), local processing, no third-party sharing
3. **Cookie Policy** — You only use localStorage for auth tokens (minimal)
4. **DMCA Policy** — If users can post content
5. **Refund Policy** — Stripe requires this. Suggest: "Cancel anytime, no refunds for partial months"

### Entity Structure Recommendation
- **LLC** — Form a single-member LLC in your state ($50-500 filing fee)
- **EIN** — Get from IRS (free, instant online)
- **Business bank account** — Separate from personal
- **Stripe account** — Under the LLC name
- Estimated setup cost: **$100-300**

---

## Part 4: Revenue Model — From $0 to First Dollar

### Phase 1: Free Launch (Week 1-2)
- Deploy to a public URL (use your existing DuckDNS: aviraa.duckdns.org)
- Add SSL cert (Let's Encrypt, free)
- Post on r/algotrading, r/daytrading, r/stocks, r/SideProject
- Target: **100 signups**

### Phase 2: Stripe Integration (Week 3)
- Wire up real Stripe checkout
- Enable Premium tier ($9.99/mo)
- Add feature gates on scanner + market intel
- Target: **5 paying users = $50 MRR**

### Phase 3: Content Marketing (Week 4-8)
- Daily AI market brief (auto-generated from /api/market-intel/synthesis)
- Post on Twitter/X with AI-generated stock analysis screenshots
- YouTube: "I built an AI that scans stocks better than me" (this CRUSHES on YouTube)
- Target: **1,000 free users, 30 paid = $300 MRR**

### Phase 4: Mobile App (Month 2-3)
- Publish to App Store + Google Play
- Add push notifications for price alerts
- Web-only Stripe (avoid Apple's 30% cut)
- Target: **5,000 users, 150 paid = $1,500 MRR**

### Phase 5: Scale (Month 4-12)
- Add broker integration (Alpaca) → referral revenue
- Add affiliate links (Webull: $100+/referral)
- Add Enterprise tier with API access
- Hire a part-time content creator for YouTube/TikTok
- Target: **25,000 users, 1,000 paid = $10,000 MRR**

---

## Part 5: Pricing Strategy

### Recommended Pricing (Updated)

| Plan | Price | Annual | Target User |
|------|-------|--------|-------------|
| **Free** | $0 | $0 | Casual investor, tire-kickers |
| **Premium** | $9.99/mo | $99/yr (save 17%) | Active trader, 1-5 trades/week |
| **Enterprise** | $29.99/mo | $299/yr (save 17%) | Power user, API access, multi-user |

**Why $9.99 and not $19.99?**
- Lower barrier → higher conversion rate
- $9.99 is an impulse purchase for traders
- At 7% conversion: 1,000 free → 70 paid → $700 MRR
- At 3% conversion at $19.99: 1,000 free → 30 paid → $600 MRR
- The $9.99 also has better retention (less price sensitivity)

**Annual discount:**
- Offer 2 months free for annual billing
- Increases cash flow upfront
- Reduces churn (they committed for a year)

---

## Part 6: Technical Debt to Fix

| Issue | Severity | Fix |
|-------|----------|-----|
| Paper trading uses JSON files | Medium | Move to PostgreSQL (tables exist) |
| In-memory auth in `auth_service.py` | Low | Already have DB-backed auth in `routes/auth.py`; deprecate the in-memory one |
| No rate limiting | High | Add `slowapi` or custom middleware before monetizing |
| No email sending | High | Add Resend.com for transactional emails |
| No monitoring/alerting | Medium | Add Sentry (free tier) for error tracking |
| Secret key hardcoded | High | Move `SECRET_KEY` to K8s secret / env var |
| No HTTPS on backend | High | Add TLS termination via ingress or Caddy |
| Frontend apiBase hardcoded | Low | Already uses env detection |

---

## Part 7: Quick Wins (Do This Week)

1. **Add disclaimer banner to all trading pages** — 30 minutes, protects you legally
2. **Set up Stripe test mode** — 1 hour, validates the payment flow
3. **Add rate limiting** — 2 hours, prevents abuse of free tier
4. **Move SECRET_KEY to env** — 10 minutes, security best practice
5. **Add HTTPS** — 1 hour with Caddy reverse proxy
6. **Post on Reddit** — Free, immediate traffic
7. **Record a YouTube demo** — Free, best ROI marketing for dev tools

---

## Part 8: Revenue Streams Summary

| Stream | Time to First $ | Effort | Monthly Potential |
|--------|----------------|--------|-------------------|
| SaaS Subscriptions | 2-3 weeks | Medium | $500-10,000+ |
| Broker Referrals (Alpaca/Webull) | 1 month | Low | $200-5,000 |
| Shopping Affiliates | 2 weeks | Low | $50-500 |
| API Access (B2B) | 2-3 months | Medium | $500-5,000 |
| YouTube Content | 1 month | Medium | $100-2,000 (AdSense) |
| AI Newsletter | 2 weeks | Low | $100-1,000 (sponsorships) |
| White-Label Licensing | 3-6 months | High | $2,000-20,000 |

**Most realistic first revenue:** SaaS subscriptions + broker referrals = **$500-1,500/mo within 90 days** with focused execution.
