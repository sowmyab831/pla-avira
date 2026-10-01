# AI cost & usage accounting

All money is **integer micro-USD** (1 USD = 1,000,000µ). No floats anywhere in
the ledger — this is what makes concurrent reservations safe to compare.

## Flow

```
reserve()   before the provider call: estimate_tokens(prompt) +
            max_output_tokens × model prices × 1.5 safety → row-locked hold
            on user + org + platform budget accounts (one transaction;
            SELECT … FOR UPDATE on Postgres, process lock on SQLite).
            Denied = QUOTA_EXHAUSTED, no provider call is made.
settle()    after the call: real usage → final cost (state=settled),
            or state=pending when usage is ambiguous (stream disconnect,
            provider error after partial output), or released when the
            call never produced output.
```

Every event writes one `ai_usage_events` row keyed by `idempotency_key`
(sha256 of request-id + model + attempt) — retries and fallbacks produce
separate rows, replays collapse to one.

## Pricing rules

- `price_micro(spec, usage)`: input×in-rate + output×out-rate +
  cached-input×cached-rate + reasoning-tokens×out-rate. xAI ≥200k-token
  prompts apply the documented 2× surcharge.
- `price_known=false` models (catalog entries without recorded prices) may
  serve **BYOK** traffic (metered as estimate, user owns the bill) but are
  refused for managed/platform-funded routing — unknown price is not $0.
- Ollama is local and free: usage is recorded, cost is 0.

## Budgets

`ai_budget_accounts` holds `period` (YYYY-MM), `limit_micro`,
`spent_micro`, `reserved_micro` per scope (user / org / platform).
`GET /api/ai/usage` returns the caller's period spend, reservations and
remaining headroom. `POST /api/ai/estimate` dry-runs pricing for a request
without calling a provider.

## Concurrency guarantee dedicated test

`test_ai_gateway.py::test_concurrent_requests_cannot_overspend` fires 10
parallel requests against the last dollar of a budget: exactly 3 succeed,
7 get `QUOTA_EXHAUSTED`, `spent + reserved ≤ limit` holds. A PostgreSQL
variant (`-m postgres`, `AVIRA_TEST_DATABASE_URL`) exercises the real
`FOR UPDATE` path; SQLite uses a per-loop mutex instead.
