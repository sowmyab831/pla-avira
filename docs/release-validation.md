# Release validation log

Reproducible commands, results and open blockers per release. Historical rows
are not proof of current correctness; re-run before relying on them.

## Commands

```sh
# Backend (from repository root)
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend backend/venv/bin/python -m pytest -q -p no:cacheprovider --disable-warnings backend/tests

# PostgreSQL-only tests (row locks / concurrency)
AVIRA_TEST_DATABASE_URL=postgresql+asyncpg://pla_user:***@localhost:5432/pla_test \
  PYTHONPATH=backend backend/venv/bin/python -m pytest -q -m postgres backend/tests

# Opt-in live local-LLM tests (Ollama must be running)
AVIRA_LIVE_LLM_TESTS=1 PYTHONPATH=backend backend/venv/bin/python -m pytest -q -m live_llm backend/tests

# Frontend
cd frontend && npm run type-check && npm run build
```

## Baseline — 2026-09-28 (before Release 0 changes)

| Check | Result | Notes |
|---|---|---|
| Full backend suite | **100 passed / 23 failed** | 17 in `test_api_endpoints.py` require a live server on :30000 (k8s down); 2 `test_market_intel` shape asserts; **4 `test_privacy_pipeline` masking failures = real defect** |
| Ollama | reachable | `qwen3:14b`, `qwen2.5:14b`, `mistral:7b-instruct` installed |
| Port 30001 / 30000 | unreachable | OrbStack k8s not running |
| Git index | 347 staged files incl. `TELEGRAM_BOT_TOKEN`, `.avira-logs/`; `.venv-native/` (52k files), `mobileapp/node_modules/` (20k), `backend/credentials.json` tracked in HEAD | recorded in `docs/baseline/git-status-20260928.txt` |

## Release 0 — safe, reproducible baseline

### Changes
- Git hygiene: unstaged `TELEGRAM_BOT_TOKEN`, `.avira-logs/`, `backend/data/notification_prefs.json`; `git rm --cached` for `.venv-native/`, `mobileapp/node_modules/`, `backend/credentials.json` (files kept on disk); `.gitignore` extended. `TELEGRAM_BOT_TOKEN` was staged but **never committed** to any ref, so rotation is recommended but not forced. `backend/credentials.json` is a placeholder (`YOUR_CLIENT_ID`).
- Removed legacy in-memory auth (`/api/local-auth/*`, `services/auth_service.py`) and its hardcoded default user. Single principal source: `routes/auth.get_current_user`.
- `routes/user_settings.py`: ownership enforced from the token; `me` alias; admins read-only on others; 403 on cross-user writes.
- `main.py`: actor-context middleware publishes the token principal on `llm_client.current_actor`.
- `llm_client.py`: output-token ceiling is a hard cap; cache key includes policy version, tenant/user, provider/model. Legacy `OllamaClient` uses the same clamp/key.
- `config.py`: flags `AVIRA_AI_GATEWAY`, `AVIRA_AI_MODEL_SETTINGS`, `AVIRA_AI_CLOUD` (off), `AVIRA_AI_BYOK` (off), `AVIRA_AUTO_TRADING` (off), `AVIRA_PAYMENTS_LIVE` (off); provider key fields for all R1 providers.
- `scheduler.py`: auto-trade loops gated on `AVIRA_AUTO_TRADING`; the unattended **real-money Robinhood order path was removed** (signal is reported for in-app approval instead).
- `router_ai._call_external_llm`: OpenAI call blocked unless `AVIRA_AI_CLOUD=true`.
- `privacy_masking.py`: baseline regex patterns for email, US/India phone, card, Aadhaar, PAN, IFSC so masking works without Presidio/spaCy.
- Tests: `tests/conftest.py` (shared SQLite harness, `postgres`/`live_llm` markers), `test_settings_ownership.py`, `test_release0_guards.py`.
- Docs: `docs/ai-migration-checklist.md` (25 call sites).

### Results
| Check | Result |
|---|---|
| `test_settings_ownership.py` + `test_release0_guards.py` | 20 passed |
| `test_privacy_pipeline.py` | 17 passed (was 13/17) |
| `test_life_admin_billing.py` (regression) | passed |
| App boots with no cloud keys | verified via import + route table test |

### Open
- `test_api_endpoints.py` still needs a live server; converted to skip-unless-`AVIRA_LIVE_API_URL` in R1.
- Presidio/spaCy fail to import in the py3.14 venv (pydantic v1 `REGEX` ConfigError). NER-based masking (names, orgs) remains unavailable; regex baseline covers structured identifiers only. Fix: pin a compatible spaCy/presidio or move to py3.11 image.
- `router_assistant.chat` still trusts a body `user_id` — migrated in R1 with the gateway.

## Release 1 — AI gateway + platform hardening — 2026-09-29

### Changes
- `app/ai/`: schemas, registry (seed catalog, 9 providers), policy engine,
  encrypted credentials, micro-USD budget ledger, gateway with bounded
  retry/fallback + schema repair, SSRF guard, domain prompts.
- `models/ai.py` (6 tables) + alembic migration; `routes/ai_settings.py`
  mounted under `/api/ai`; startup probes Ollama `/api/tags`.
- `router_assistant.py`: `/chat` is JWT-authenticated, ignores body `user_id`,
  routes through `Gateway.complete()` with domain prompts, returns real
  provider/model/locality/usage/cost metadata. Session/privacy/analyze routes
  scoped to the token principal (admin override allowed).
- `main.py`: auth-gate middleware — all `/api/*` need a valid Bearer except
  `/api/auth/*`, `/api/public/*`, `/api/telegram/webhook`,
  `/api/billing/webhook`. Telegram webhook honors `TELEGRAM_WEBHOOK_SECRET`.
- Frontend: global fetch wrapper injects the token for every API call and
  bounces to login on 401; `AISettings` page, `ModelSelector`, `LlmBadge`;
  `ErrorBoundary` keyed per page (a page crash no longer blanks the app);
  Family page normalizes 403 detail objects instead of rendering them.
- Portfolio API: `/stocks/{s}/chart` alias added (frontend + `pla` used it,
  it 404'd); strategy objects gained `name`; history route mapped
  `prices`→`data` (charts were silently empty).
- OpenClaw: `AGENTS.md` rewritten (grounded-only, currency-explicit,
  propose-don't-act); `skills/finance`, `skills/shopping`, new
  `skills/health`; `pla` CLI `ask` sends `session_id`.
- Tests: `test_ai_adapters` (108), `test_ai_gateway` (incl. 10-way budget
  race), `test_auth_gate`, `test_ai_eval` eval set (opt-in `live_llm`).

### Results
| Check | Result |
|---|---|
| Offline suite `pytest backend/tests` | **268 passed / 1 skipped / 17 live-gated** (was 100/23 failed) |
| `test_ai_adapters` + `test_ai_gateway` | 135 passed |
| `npm run type-check && npm run build` | clean, `index-DQvY9fs_.js` |
| K8s (OrbStack) | restored; backend+frontend redeployed `…2311`/`…2318` |
| `/health` | postgres/redis/qdrant/meili/ollama all true |
| Auth gate live | `/api/tasks` no token → 401; signed token → 200 |
| Gateway live | `chat` → ollama `qwen2.5:14b`, real usage+cost=0, `local_only` |
| UI sweep (`scripts/verify-ui.py`, admin) | **29/29 pages OK**, 0 console errors |
| UI sweep (free user, 7 pages) | 7/7 OK — `family` shows upgrade notice, no crash |
| Live API suite | 16/17 pass; shopping search = honest empty (retailers 301/302/blocked the pod IP — upstream, not a bug) |

### Open
- Shopping scraping is bot-blocked from the cluster IP; contract verified,
  live offers unverified.
- `testuser01` password reset to a known value for verification; role=admin,
  tier=premium. `verify_u1` is the ordinary-user fixture.

## Releases 2–5 (2026-09-30)

### What changed
- **R2 memory/capture**: `memory_items` table, `app/services/memory.py`,
  `/api/memory` + `/api/capture` routes, assistant `/chat` injects
  pinned+relevant memories into the system prompt.
- **R3 jobs/family**: `jobs` table, `app/services/job_queue.py` (SKIP LOCKED /
  lock fallback, backoff, stale-claim recovery, dedupe_key),
  `job_handlers.py` (`reminder.dispatch`, `price.check`), scheduler drains the
  queue regardless of Telegram config; `family_members.status` state machine
  with soft-delete.
- **R4 shopping**: `tracked_products` + `/api/shopping/tracked*` routes;
  `price.check` alerts on target/drop via `queue_notification`.
- **R5 org/telemetry**: `/api/ai/admin/org-policy` (GET/PUT),
  `app/services/telemetry.py` counters, `/api/ai/admin/metrics`.
- Migration `backend/migrations/20260930_ops.sql` applied to live Postgres.
- Frontend: Admin page shows errors instead of blank; MarketIntel explains
  unreachable-backend failures.
- Repo: `.venv-native/` (1.8GB, 52k files) stripped from the 4 unpushed
  commits via index-filter; `development` pushed (fast-forward).

### Results
| Check | Result |
|---|---|
| `tests/test_ops.py` | **14 passed** (memory scoping, dedupe, retry→dead, crash recovery, reminder dispatch, member lifecycle, tracked CRUD, price alerts incl. dedupe + snapshot path, org policy admin-only, metrics) |
| Full offline suite | **282 passed / 1 skipped / 38 marker-gated** |
| Live memory CRUD/search/capture | 200s, user-scoped |
| Live tracked product + price.check job | job `done`, `{"checked":1,"alerts":1}`, notification queued |
| Live assistant memory recall | "Ava pickup is at 3pm daily" answered via injected memory |
| `/api/ai/admin/metrics` + `org-policy` | live, admin-gated (403 for users) |
| K8s | `pla-backend:20260930-2318-86aa8eaf7`, `pla-frontend:20260930-2318-86aa8eaf7` |
