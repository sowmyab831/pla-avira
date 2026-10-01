# AI Usage Audit

Policy: **AI only where it earns its keep** — research, summarization, OCR
extraction, and open-ended chat. Anything that can be answered deterministically
(prices, metrics, checklists, verdicts, schedules) must NOT call the LLM.

All LLM calls go through `app/services/llm_client.py` (Ollama, local).
`generate_json()` returns `None` when the model is unavailable — every caller
must have a deterministic fallback.

## Call-site inventory

| File | Calls | Purpose | Verdict |
|---|---|---|---|
| `services/document_ocr.py` | 3 | Extract structured fields from scanned docs | KEEP — OCR needs a model |
| `routes/nexus.py` | 3 | Nexus assistant orchestration | KEEP — open-ended chat |
| `services/travel_service.py` | 2 | Trip research / itinerary suggestions | KEEP — research task |
| `services/nutrition_service.py` | 2 | Meal analysis from free text | KEEP — extraction |
| `services/intent_engine.py` | 2 | Classify user voice/chat intent | REVIEW — could be rules for common intents |
| `services/imap_radar.py` | 2 | Summarize/classify inbox items | KEEP — summarization |
| `services/health_analyzer.py` | 2 | Lab-result interpretation | KEEP — PHI-masked, research |
| `routes/maintenance.py` | 2 | Repair research (`/maintenance/research`) | KEEP — opt-in research only |
| `routes/family_hub.py` | 2 | Family assistant answers | KEEP — open-ended |
| `routes/care.py` | 2 | Care-plan suggestions | KEEP — research |
| `services/wishlist_service.py` | 1 | Wishlist item enrichment | REVIEW — prefer catalog lookup |
| `services/stock_intelligence.py` | 1 | Narrative stock summary | REVIEW — deep-metrics endpoint is deterministic; keep narrative opt-in |
| `services/smart_shopping.py` | 1 | Product recommendation text | REVIEW — verdict is now deterministic in `price_tracker.py` |
| `services/options_trading.py` | 1 | Options strategy narrative | REVIEW — metrics are deterministic in `options_metrics.py` |
| `services/financial_planner.py` | 1 | Plan narrative | KEEP — synthesis |
| `services/finance_analyzer.py` | 1 | Transaction categorization assist | REVIEW — rules cover common merchants |
| `services/earnings_intelligence.py` | 1 | Earnings-call summary | KEEP — summarization |
| `services/advanced_stock_analyzer.py` | 1 | Deep-dive narrative | KEEP — opt-in |
| `routes/nutrition_enhanced.py` | 1 | Enhanced meal analysis | KEEP |
| `routes/market_intel.py` | 1 | Market briefing | KEEP — research |
| `routes/forecast.py` | 1 | Forecast narrative | REVIEW — numbers are deterministic |
| `routes/bills.py` | 1 | Bill extraction from docs | KEEP — extraction |
| `routes/assistant.py` | 1 | General assistant | KEEP |

## Deterministic-by-default (no LLM)

- `services/price_tracker.py` — buy/wait verdict, 1-year low, drop stats
- `services/fundamental_metrics.py` — Piotroski F, Altman Z, growth/valuation
- `services/options_metrics.py` — IV rank, skew, put/call, max pain
- `services/price_metrics.py` — momentum, drawdown, beta, breadth
- `services/market_region.py` / `nse_client.py` — quotes, indices, movers
- `routes/maintenance.py` — checklist templates, reminders (LLM only on `/research`)
- `routes/shopping.py` — price history + verdict (LLM only for free-text product research)
- `routes/travel.py` — fare snapshots/history

## Rules for new code

1. If the answer is computable from data we already have, compute it — no LLM.
2. LLM calls must be behind an explicit user action or a `?deep=true`-style opt-in.
3. Every LLM call needs a deterministic fallback when `generate_json` returns `None`.
4. Health/finance payloads must pass through `llm_privacy_middleware` before any
   external model call.
