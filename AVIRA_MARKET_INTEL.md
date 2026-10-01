# AVIRA Market Intelligence — What was built this session

> Goal: turn AVIRA into a real research + trading intelligence platform with
> a dedicated Market Intelligence page, AI Boom tracking, multi-source signal
> aggregation, an LLM-synthesized brief, and a per-ticker XGBoost predictor
> trained on 2 years of data — plus tidy `avira-start` / `avira-stop` ops.

---

## 1. New ops scripts (`scripts/`)

| Script | What it does |
|---|---|
| `avira-start.sh`  | Boots OrbStack, scales `pla` namespace pods up, ensures Ollama is running, starts the Meridian options bot on `:8200`, and serves the trading-alerts dashboard on `:8201`. |
| `avira-stop.sh`   | Stops local services. Flags: `--scale-pods` (scale K8s deployments to 0), `--stop-ollama`, `--stop-orb`, or `--all`. |
| `avira-status.sh` | Prints OrbStack + K8s pod state + URL health + installed Ollama models. |
| `avira-models.sh` | Audits Ollama models. With `--apply` it removes anything not in the recommended list and pulls what's missing. |
| `avira-redeploy-backend.sh` | `docker build` the backend and `kubectl rollout restart` the K8s deployment so K8s picks up the new market-intel routes. |

```bash
# typical day
./scripts/avira-start.sh                # bring everything up
./scripts/avira-status.sh               # see what's healthy
./scripts/avira-stop.sh --scale-pods    # free up local CPU/memory
./scripts/avira-stop.sh --all           # plus stop Ollama + OrbStack
```

---

## 2. Curated Ollama model registry

`avira-models.sh` keeps:

- **`qwen2.5:14b`** — primary finance reasoner (≈9 GB, 100% Metal GPU)
- **`mistral:7b-instruct`** — fast assistant + classifier (≈4 GB, 100% GPU)
- **`deepseek-r1:32b`** — on-demand deep reasoner (≈20 GB, partial GPU)
- **`nomic-embed-text`** — embeddings for RAG (≈300 MB)

It removes everything else (e.g. `qwq:32b` is essentially a slower duplicate
of `deepseek-r1:32b`). Run it with `--apply` after audit to actually prune
and pull.

---

## 3. Backend service: multi-source market intelligence

`backend/app/services/market_intelligence.py` aggregates **without paid keys**:

| Signal | Sources |
|---|---|
| `influencer_signals`   | Trump (Truth Social RSS) + Yahoo News mentions for Musk, Cramer, Cathie Wood, Ackman, Burry, Buffett, Powell, Yellen, Saylor, Cook, Nadella, Pichai, Huang… |
| `geopolitics_war`      | Reuters World, BBC World, Al Jazeera, Defense News, Bloomberg Politics — with conflict regex + risk level |
| `big_money_flow`       | SEC EDGAR `getcurrent` Form 4 (insiders), 13F-HR (institutions), SC 13D/13G (activists) |
| `sec_filings`          | 8-K, 10-K, 10-Q, S-1, DEF 14A, 4, 13F-HR, SC 13D/13G |
| `tech_breakthroughs`   | Hacker News, ArsTechnica, MIT Tech Review, TechCrunch, FDA Press, Nature, ScienceDaily Med, ArXiv cs.AI |
| `resource_discoveries` | Mining.com, OilPrice, Rigzone, Reuters Commodities |
| `earnings_adherence`   | yfinance earnings history — actual vs estimate, last 5y, beat-rate verdict |
| `ai_boom_index`        | Composite momentum index across compute_chips · semi_equipment · hyperscalers · ai_software · data_networking · energy_grid · defense_geopol · rare_earth_miners |
| `market_overview`      | ^GSPC / ^IXIC / ^DJI · VIX · DXY · 10y · gold · WTI · 11 sector ETFs (XLK, XLE, …) |

Built-in 5-minute in-process cache prevents hammering free sources.

### REST routes (`/api/market-intel/*`)

```
GET  /overview                  market indices, macro, sectors
GET  /ai-boom                   composite AI Boom index + leaders/laggards
GET  /influencers?limit_per=5   tracked personalities + sentiment
GET  /geopolitics               war/world headlines + risk level
GET  /big-money                 Form 4 + 13F + 13D/13G recents
GET  /sec-filings?forms=8-K,4   SEC filings by form
GET  /tech-breakthroughs        tech / medical / AI research
GET  /resources                 oil, minerals, rare-earth news
GET  /earnings/{symbol}?years=5 beat rate + history vs forecasts
GET  /snapshot                  one-shot bundle for the dashboard
GET  /synthesis?focus=ai_boom   LLM-synthesized brief (qwen2.5:14b)
```

`/synthesis` is the hero endpoint — sends a compact JSON snapshot to the local
finance model and asks for **strict-JSON**: `market_regime`, `top_3_themes`,
`bullish_setups`, `bearish_setups`, `watch_today`, `risk_warnings`,
`ai_boom_view`. Falls back gracefully if Ollama is offline.

---

## 4. Frontend: new "Market Intel" page

`frontend/src/pages/MarketIntelligence.tsx` — wired into the sidebar under
**Main**. Eight tabs:

1. **Overview** — Pulse, sector rotation, top influencers, AI Boom card, geo risk, big-money summary
2. **AI Boom** — composite score, regime, per-category 30/90d returns, leaders & laggards
3. **AI Brief** — LLM synthesis with themes, bullish/bearish setups, watchlist, risk warnings
4. **Influencers** — every tracked personality + their latest items + sentiment
5. **War & Geo** — feed with conflict pills + risk level
6. **Big Money** — Form 4, 13F, activist filings live from SEC
7. **Tech & Innov.** — Hacker News, MIT TR, FDA, ArXiv, Nature
8. **Resources** — oil, minerals, rare-earth feeds

Auto-refreshes every 60s (synthesis every 2 min). Toggle in the header.

> Sidebar entry uses the `Brain` icon. Hash route: `#market_intel`.

---

## 5. ML predictor — XGBoost trained on 2 years of OHLCV

`meridian/research/`:

- `train_xgboost.py` — pulls 2y daily bars per symbol via yfinance, builds 18
  technical features (returns, MACD, RSI, ATR%, Bollinger position, OBV
  z-score, realized vol, calendar), trains XGBoost with a time-ordered split,
  reports `train_acc / test_acc / test_auc / feature_importance`, and
  pickles to `meridian/research/models/{SYMBOL}.pkl`.
- `predict.py` — loads model + recent live data, returns next-day up-probability.
- `README.md` — usage + honest caveats (daily directional models rarely beat
  ~0.55–0.60 AUC; treat output as a *tilt*, not an oracle).

```bash
# train the AI-boom basket on 2 years of data
python -m meridian.research.train_xgboost --universe ai_boom

# predict next-day direction
python -m meridian.research.predict NVDA AMD AVGO
```

---

## 6. Verified working (live data, this session)

```
score = 23.13   regime = expansion
  compute_chips        30d=+52.72%  90d=+54.12%
  semi_equipment       30d=+23.13%  90d=+50.56%
  hyperscalers         30d=+27.34%  90d= +4.88%
  ai_software          30d= +5.15%  90d=-17.01%
  data_networking      30d=+22.44%  90d=+50.28%
  energy_grid          30d=+12.63%  90d=+33.88%
  defense_geopol       30d= -5.93%  90d= +1.36%
  rare_earth_miners    30d=+21.16%  90d=+24.62%
```

Influencers, geopolitics, tech, and SEC big-money endpoints all returned
real items with proper sentiment scoring and form-type filtering.

---

## 7. Compliance reminder

This is **research / paper-trading intelligence** — NOT financial advice and
NOT autonomous execution. Real-money trades require explicit user opt-in
(see `meridian/backend/app/compliance.py` and the disclosures in the trading
dashboard). Past performance ≠ future returns. No single signal — technical,
LLM, or ML — should be followed blindly.

---

## 8. Ship it

The code is in the repo. To make it live in your K8s pod:

```bash
./scripts/avira-redeploy-backend.sh    # builds + rolls deploy/backend
# then in the frontend pod (or local vite dev):
cd frontend && npm run dev             # navigate to "Market Intel"
```

That's the full delivery for this session.
