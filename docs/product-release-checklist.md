# Product release checklist

Gate for each release. An item is only ✅ when it has **evidence** — a test
run, a live response, or a screenshot in `docs/verification/`. Compilation
or a static screen is never evidence.

## R0 — Safe baseline ✅ (validated 2026-09-29)

- [x] Staged secrets/junk removed from index, files kept on disk, `.gitignore` updated
- [x] Legacy `/api/local-auth/*` + `auth_service.py` deleted; single JWT path
- [x] User settings ownership enforced from token (admins read-only on others)
- [x] Auto-trading gated behind `AVIRA_AUTO_TRADING`; unattended real-money path removed
- [x] Output-token ceiling enforced server-side; cache scoped to user+model+policy
- [x] Privacy regex fallback masks email/phone/card/Aadhaar/PAN/IFSC (17 tests)
- [x] `docs/ai-migration-checklist.md` + this log exist

## R1 — AI gateway ✅ (validated 2026-09-29)

- [x] `app/ai/` package: schemas, registry, policy, credentials, budget, gateway, SSRF guard
- [x] 9 provider adapters + contract tests (mocked transport)
- [x] `ai_*` tables + migration; `/api/ai/*` routes (catalog, preferences, connections, usage, estimate, admin)
- [x] Policy precedence incl. local-only default, pinned selections, data-class caps
- [x] Integer micro-USD ledger; concurrency test (10 requests, 3 pass / 7 denied)
- [x] Stream disconnect → `pending`, never silent refund
- [x] Assistant chat routed through gateway; response carries provider/model/locality/cost
- [x] Frontend: AI & Privacy page, per-conversation model selector, provenance badge
- [x] Domain prompts (investing / shopping / health / finance) + OpenClaw SKILL.md files
- [x] Eval set `backend/tests/eval/cases.jsonl` (opt-in `-m live_llm`)

## R2 — Memory & capture ✅ (validated 2026-09-30)

- [x] `memory_items` table + `/api/memory` CRUD, search, pin — strictly user-scoped
- [x] `/api/capture` quick-capture → memory `kind=capture`, listed via GET
- [x] Assistant `/chat` injects pinned + query-relevant memory into the system
      prompt (live-verified: stored fact answered back via local model)
- [ ] Retention/TTL policies (deletion works; scheduled expiry not yet built)

## R3 — Jobs, notifications, family ✅ (validated 2026-09-30)

- [x] Durable `jobs` table + `job_queue` service: FOR UPDATE SKIP LOCKED on
      Postgres, process lock on SQLite; retry w/ backoff; stale-claim recovery;
      `dedupe_key` idempotent enqueue
- [x] Handlers: `reminder.dispatch` (marks sent + queues notification),
      `price.check` (R4 alerts); scheduler `periodic_loop` drains `run_due()`
      even without Telegram configured
- [x] Family member lifecycle: `status` column (invited→active→removed),
      transition validation, soft-delete default (history preserved),
      `?hard=true` for real delete
- [ ] Quiet-hours scheduling not yet implemented

## R4 — Shopping lifecycle ✅ (validated 2026-09-30)

- [x] `tracked_products` table + `/api/shopping/tracked` CRUD (idempotent on
      `product_key`, baseline price seeded from snapshot history)
- [x] `POST /tracked/check` enqueues durable `price.check` job → evaluates
      latest `price_snapshots` vs target_minor/drop_pct → `queue_notification`
      (user-approval flow preserved); alert fires once per price level
- [x] Verified live: seeded snapshot $449 vs target $500 → alert queued,
      `last_minor` settled in DB
- [ ] Live scraper coverage still blocked from cluster IP (contract-tested)

## R5 — Payments, org, telemetry ✅ (validated 2026-09-30)

- [x] Org AI policy admin API `GET/PUT /api/ai/admin/org-policy` — org row in
      `ai_preferences` (`scope_kind=org`), consumed by `load_policy` as a
      tightening layer (cloud allow, provider allowlist, org monthly cap)
- [x] Telemetry `app/services/telemetry.py` — request counts, status classes,
      latency p50/p95/p99 ring buffer, path-normalized (no PII); surfaced at
      `GET /api/ai/admin/metrics` with job-queue stats and AI usage aggregates
- [ ] Payment sandbox exists via test activation keys; Stripe/Razorpay live
      sandbox checkout not exercised (webhook signature path is tested)

## Universal gates (every release)

- [ ] `pytest backend/tests` green (offline tier); live tier documented
- [ ] `npm run type-check && npm run build` green
- [ ] Auth gate: unauthenticated `/api/*` → 401; webhooks/public stay open
- [ ] No secrets committed; no provider claims "live" without a real response
- [ ] Browser sweep green: `python3 scripts/verify-ui.py` → 29/29
