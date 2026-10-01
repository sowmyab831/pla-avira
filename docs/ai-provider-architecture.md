# AI Provider Architecture

One entry point for every model call: `app.ai.gateway.Gateway`.
Nothing else may call a provider SDK or Ollama directly for chat completions.

```
request → guard → policy.decide → credential → capability check →
          budget.reserve → adapter.complete/stream → validate →
          budget.settle → audit
```

## Components (`backend/app/ai/`)

| File | Responsibility |
|---|---|
| `schemas.py` | Provider-neutral `AIRequest`/`AIResponse`/`Usage`/`StreamEvent`, `AIError` + `ErrorCode`, enums (`Mode`, `Profile`, `DataClass`, `Locality`, `Capability`) |
| `registry.py` | Model catalog (`ModelSpec`): capabilities, tier, context window, micro-USD prices, lifecycle, source URL. Seed merged with admin DB overrides (`ai_model_catalog`). Local install state probed from Ollama at startup |
| `policy.py` | `decide(req, policy, registry)` — precedence: deployment flags → org policy → user consent → data-class cap → capability → (budget later) → explicit selection → per-task pref → user default → auto profile → platform default |
| `credentials.py` | Resolves keys: user (BYOK) → org → platform env. Fernet-encrypted at rest (`AVIRA_VAULT_KEY`); secrets are never logged or returned |
| `budget.py` | `BudgetLedger`: integer micro-USD. `reserve()` holds 150% estimate with row locks (Postgres `FOR UPDATE`; process lock fallback on SQLite). `settle()` converts to spend / `pending` / `released`. Idempotent on `ai_usage_events.idempotency_key` |
| `gateway.py` | Orchestration: bounded retries (429/5xx backoff), pinned-vs-fallback rules, one schema-repair attempt for JSON output, stream-disconnect → `pending` (never silently refunded) |
| `ssrf.py` | Blocks requests to private/link-local/loopback hosts for custom `compat` endpoints |
| `prompts.py` | Domain system prompts (investing, shopping, health, finance, travel…) with grounding/no-diagnosis guardrails |
| `providers/` | `base.py` adapter contract + `ollama`, `anthropic`, `gemini`, `openai_compat` (covers OpenAI, Moonshot, DeepSeek, xAI, Mistral, and admin-allowlisted compat endpoints) |

## Tables (`app/models/ai.py`)

`ai_connections` (encrypted keys, owner=user/org/platform), `ai_model_catalog`
(admin overrides), `ai_preferences` (per-user + per-org policy), 
`ai_budget_accounts` (per-user/org/platform monthly limits + spent),
`ai_usage_events` (reserve→settle ledger, idempotent), `ai_audit_events`
(allow/deny/error decisions).

## Hard rules

- **Local-only default.** `AVIRA_AI_CLOUD=false` ⇒ every cloud selection fails
  with `CONSENT_REQUIRED`. User `mode=local_only` or `cloud_allowed=false` is
  equally binding. Org policy can only tighten user policy, never loosen it.
- **Pinned selections don't wander.** An explicit `provider:model` choice never
  falls back unless the request opts in (`allow_fallback`) and the candidate is
  capability-compatible and passes the same hard limits.
- **`SENSITIVE` data** (health, documents with PII) can only go cloud when the
  user's `max_data_class_cloud` explicitly allows it; default cap is `MASKED`.
- **Output ceiling.** `max_output_tokens` is clamped to `AVIRA_MAX_OUTPUT_TOKENS`
  server-side; client values can only lower it.
- **No silent refunds.** Disconnects mid-stream settle as `pending`, not
  `released` — usage may have been billed by the provider.
- **Actor required.** Every request carries an `ActorContext` (JWT principal via
  `llm_client.current_actor`, or `is_background=True` for jobs). No anonymous calls.

## API (`/api/ai`, all JWT-authenticated)

`GET /catalog` — providers, models, capabilities, prices, install state
`GET|PUT /preferences` — mode, profile, default model, per-task, fallbacks
`GET|POST|PUT|DELETE /connections[/id]` + `POST /connections/{id}/test` — BYOK keys
`GET /usage` — period spend vs budget; `POST /estimate` — dry-run pricing
`PUT /admin/catalog` — org/model overrides (admin only)

## Legacy facade

`services/llm_client.chat()` remains for old call sites but routes through the
same cache (scoped: policy version + tenant/user + provider/model + task), the
same output ceiling, and the same concurrency semaphore. New code must call
`Gateway.complete()`/`stream()` directly — see `docs/ai-migration-checklist.md`.
