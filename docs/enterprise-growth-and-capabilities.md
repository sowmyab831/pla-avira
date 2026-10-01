# Avira: capabilities, payments, growth and enterprise economics

Updated September 22, 2026. This document distinguishes code implemented in this change from future capabilities. No live payment account, cloud service or merchant onboarding was activated.

## Where demand is strongest

US household price pressure is a well-supported problem: the Federal Reserve's May 2026 report says price increases remained the most common financial concern in its 2025 survey. This supports prioritizing budgeting follow-through and trustworthy purchase decisions, but does not establish willingness to pay for Avira. [Federal Reserve report](https://www.federalreserve.gov/publications/2026-economic-well-being-of-us-households-in-2025-overall-financial-well-being.htm).

India's 2024 Time Use Survey shows a substantial and unequal burden of unpaid domestic work: among participants aged six and above, women spent an average 289 minutes daily on unpaid domestic services, compared with 88 minutes for men. This supports shared household administration and task coordination as product hypotheses. It does not prove an app alone will redistribute that work. [MoSPI factsheet](https://www.mospi.gov.in/sites/default/files/publication_reports/TUS_Factsheet_25022025.pdf).

Start with three promises: help me avoid missing commitments, help me keep track of money, and help me make an informed purchase. Validate adoption with households in each country before expanding acquisition spending.

## Capabilities delivered in the current source change

| Capability | What works in code | Important boundary |
|---|---|---|
| Household commitments inside Today | Create/edit bills, renewals, return deadlines, warranties, document expiry, maintenance, school, care and other tasks | Manual capture; due items appear in app; no new background delivery is promised |
| Refund and claim tracker | Expected amount, follow-up date, notes/provider link, separate INR/USD totals and user-reported completion | Does not prove a refund is owed, file a claim, dispute a charge or inspect bank accounts |
| Recurring commitments | Weekly/monthly/yearly, preserves month-end anchor, optimistic version checks and completion history | Advances one period, allowing overdue periods to be reconciled deliberately |
| Owned wishlist | Authenticated database records, USD/INR target prices, ownership checks and honest unavailable-price-history response | Legacy global JSON data is preserved but not automatically assigned to users |
| Regional subscription billing | Stripe/USD and Razorpay/INR hosted checkout adapters, signatures, event deduplication, current-provider-state reconciliation, cancellation request | Requires approved accounts/configuration and full provider sandbox qualification before live use |
| Trust fixes | Selective action approval, accurate failed/partial states, locked confirmation records, verified private/member ownership, owner-only notification approval | Member partitions must map to an owned FamilyMemberDB record; unmapped legacy partitions remain denied; not an enterprise security certification |
| Shopping integrity | Removed generated fallback offers and static coupons/cashback; structured verified offer-bound discounts only | Existing scraping is not equivalent to fully qualified live retailer APIs; unknown totals remain estimates |
| Regional input improvements | Product acronyms no longer bias shopping into stocks; kg/g/litre units recognized; four-digit USD amounts no longer truncated; electric-product promos not automatically bills | Full INR receipt/date pipeline remains unfinished |
| Lower frontend cost | Pages loaded on demand; initial production JS about 239 KB versus 1,146 KB before this change | All pages still consume bandwidth when visited; numbers are build artifacts, not measured user latency |
| AI budget guard | Newer shared Ollama client: input/output ceiling, 2 concurrent requests by default, bounded wait/timeout | Per-process only; older AI clients and distributed budgets remain work |

## Additional high-value capabilities

These are proposed next work, not all enabled by this patch.

| Order | Capability | Concrete user outcome | Data/integration and quality gate | Revenue potential hypothesis |
|---|---|---|---|---|
| 1 | Document-to-action inbox | Photograph a receipt or school notice → review extracted amount/date → create a linked commitment | Source attachment, exact locale parsing, duplicate detection, explicit approval for uncertain extraction | Connected import and family plan retention |
| 2 | Money recovery assistant | Track refunds, warranties, reimbursements and duplicate-charge candidates through resolution | Expand the manual tracker with evidence matching and user-reviewed drafts; never auto-dispute | Demonstrable recovered value, tracked separately from estimates |
| 3 | Renewal and price-rise review | Spot a recurring price increase and open the correct cancellation page | Opt-in statements/email; merchant identity; show uncertainty and confirmation of cancellation | Paid monitoring, reducing unwanted renewals |
| 4 | Family handoffs | “Who is doing this?” assignment, acknowledgement, role-based visibility and escalation | Shared membership with consent; revoke access; distinguish private from shared records | Family subscriptions; caregiver coordination |
| 5 | Pantry-to-meal-to-basket | Use ingredients before expiry and generate a reviewed grocery list | Units, servings, household preferences/allergies, pantry corrections and serviceable merchants | Weekly engagement and disclosed affiliate value |
| 6 | Payment-request scam checks | Explain mismatched domains, suspicious urgency and unexpected payees | Read-only link/text checks; no promise to identify every scam; no transfer or PIN collection | Trust and retention; avoid fear-based upselling |
| 7 | Life-event checklists | Moving house, starting school, new baby, elder care, job change | Localized templates with sources; user-owned due dates; no eligibility decisions | Short activation journey and template discovery |
| 8 | Caregiver coordination | Refill schedule, appointments and acknowledged care tasks | Consent, accurate prescribed instructions and tested reminders; no autonomous dosage advice | Caregiver/family plans |
| 9 | Benefits/document organizer | Keep claim documents and expiry reminders together | Region-specific sources, minimal sensitive data, user-reviewed submissions | Employer distribution only with private household records isolated |
| 10 | Multilingual capture | Indian English, Hindi/code-switching, selected regional language pilots | Number/name/date accuracy benchmark; correction UI; no critical actions on low-confidence speech | Reach beyond English-only early adopters |
| 11 | Calendar export and sync | Accepted commitments become calendar entries | OAuth renewal, timezone/DST, all-day dates, update/delete reconciliation and idempotency | Daily utility; retention |
| 12 | Enterprise administration | Tenant-level policy, seats, usage budgets, SSO and audit export | Tenant boundary tests, least privilege, provisioning/deprovisioning, retention and incident drills | Contract revenue with explicit support costs |

Use the same commitment/entity model for these features. Avoid adding twelve separate data silos. Start with manual recovery tracking and source-linked extraction, then automate one verified step at a time.

## US versus India payments

There are three different products here:

1. **Collect Avira subscription fees:** implemented provider adapters choose Stripe for US/USD and Razorpay for India/INR. Billing country is selected explicitly. Both routes require a merchant that is eligible for the provider and market.
2. **Help users manage household payments:** the new board records due amounts and links to user-supplied provider pages, then records user-reported completion. It does not execute payments or verify bank settlement.
3. **Connect bank or payment history:** future read-only integrations require customer consent and regional access agreements. A Razorpay merchant account does not give Avira access to a consumer's entire UPI history. A Stripe subscription integration does not link consumer bank history.

Stripe services in India are invitation-only; do not assume US integration can simply be copied to an Indian legal entity. [Stripe India availability](https://support.stripe.com/questions/india-faq?locale=en-GB). Razorpay documents recurring subscription creation and UPI AutoPay, subject to account and method availability. [Razorpay subscriptions API](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/), [UPI AutoPay](https://razorpay.com/upi-autopay/).

Current monthly catalog reuses the backend's prices: Premium $9.99 / ₹499; Family $19.99 / ₹999. The internal `enterprise` tier remains for compatibility but is labeled Family on this screen. These prices are hypotheses, not validated optimal pricing. Organization deployments need separate terms and costing; the Family plan does not include a newly implemented SSO or enterprise SLA.

### Payment launch checklist

- Confirm receiving business entity, supported settlement accounts, merchant approval, taxes and refund terms. These cannot be inferred from the customer's selected country.
- Populate the approved deployment secret store using `payments-and-launch.env.example`; never put real keys in source or chat. Keep activation keys disabled in production.
- Create exact monthly Stripe prices: USD 999 and 1999 minor units; Razorpay monthly plans: INR 49900 and 99900 minor units. API checks reject mismatched provider amount/currency/interval. India plans currently have a disclosed maximum of 120 monthly cycles.
- Apply `backend/migrations/20260921_life_admin_billing.sql` after backing up the database; it only adds tables/indexes. Existing local startup also registers these models with create_all. Do not run both migrations blindly in competing deploy jobs.
- Register HTTPS webhook endpoints `/api/billing/webhook/stripe` and `/api/billing/webhook/razorpay`. The legacy Stripe webhook URL delegates to the same verified handler.
- Test successful and failed payment, abandoned checkout, delayed delivery, duplicate delivery, tampered signatures, cancellation, expired checkout and provider timeouts with provider sandbox accounts.
- Grant access only from verified current provider state. Returning to the success URL never grants a plan. Event IDs are persisted to suppress replay; Stripe signatures also have a five-minute timestamp tolerance. [Stripe webhook guidance](https://docs.stripe.com/webhooks), [Razorpay validation](https://razorpay.com/docs/webhooks/validate-test/).
- Existing or ambiguous billing records block duplicate checkout. Incomplete/expired records currently require operator reconciliation; self-service plan switching, billing portal, automatic abandoned-session cleanup and refunds remain additional work.
- Qualify PostgreSQL concurrent delivery/confirmation behavior separately: SQLite tests exercise ownership and state, not PostgreSQL row-lock semantics.
- Add a scheduled provider reconciliation job and operational alerts before a broad paid launch. A missed webhook must not leave entitlements stale indefinitely.

No money was charged or refunded during this change. Live merchant credentials were neither inspected nor configured.

## Low running costs without pretending a laptop is an enterprise service

**Implemented now:** deterministic commitment/recovery workflows use zero model calls; the new shared model client caps input, output, concurrency and wait time; embedding-model loading is deferred until search/indexing is needed; initial frontend code is split by page. This reduces work but is not a complete account-level cost budget.

**Recommended pilot architecture:** CDN/static frontend; one containerized FastAPI service; PostgreSQL; a small durable worker for ingestion/reminders; object storage for documents only when needed. Keep search/vector indexing optional until demonstrated demand. Prefer a modular service over a Kubernetes fleet for an early commercial pilot, but do not rewrite the current infrastructure in place without backup and rollout testing.

Cloudflare's usage-based platform is one candidate for static delivery/edge work and supports CPU limits to constrain runaway compute. It is not a drop-in place to run the existing heavy Python backend. Compare actual workload and regional requirements before choosing a host. [Cloudflare pricing and resource controls](https://developers.cloudflare.com/workers/platform/pricing/).

**Model policy:** deterministic parsing/calculation first → small model for ambiguous extraction → larger model only for explicit complex work. Cache public catalog facts and reusable templates; do not share private response caches across users. Use document hashes and event IDs to avoid repeated OCR/inference. Batch non-urgent jobs. Never regenerate expensive market analysis just because a user opens Today.

**Needed before multi-tenant commercial scale:** durable per-user/per-tenant counters, enforceable token/currency budgets, request admission, queue backpressure, daily spend alerts, provider billing reconciliation, workload isolation and full migration of legacy model clients. Current in-memory subscription rate counters reset across workers/restarts and are not enterprise cost accounting.

**Hosting choice:** local Ollama has no per-call provider bill but still costs hardware, energy, maintenance and capacity. An always-on GPU can be wasteful at low utilization. Compare measured CPU/local model throughput with pay-per-use inference using the same held-out quality set. A device that sleeps cannot provide a continuous reminder SLA. This patch does not buy hosting or enable cloud inference.

## Returns and unit economics

Optimize contribution margin and retained useful outcomes, not feature count. Keep US and India revenue/cost cohorts separate; do not convert INR into USD without an explicit exchange-rate assumption.

Monthly contribution = net subscription revenue + disclosed affiliate contribution − gateway fees − model/OCR/provider charges − hosting allocation − storage/egress − support − refunds/fraud reserve.

Illustrative **planning scenario**, not a provider quote or forecast: at $9.99, assume $0.60 payment cost, $0.75 AI/OCR, $0.75 infrastructure, $1.00 support and $0.30 refund reserve. Contribution is $6.59 before sales, tax, overhead and salaries. A $20 acquisition cost would take about 3.0 paid months to recover at that contribution, assuming retention. Validate every input; do not present this as expected profit.

For India, construct the same equation in INR using actual domestic gateway terms and measured support/inference cost. Lower price needs smaller included usage or lower delivery cost; unlimited expensive AI can erase margin. Do not multiply a hypothetical price by an unvalidated user count and call it market revenue.

Packaging experiments: free manual board → individual connected imports/monitoring → family coordination → separately scoped organizations. Offer annual plans only after monthly retention and cancellation flows are proven. Affiliate links must be disclosed and must not bias product-fit ranking.

## Reach and launch experiments

1. Recruit an initial cohort in each market around one real problem: renewal reviews, refund follow-ups or family commitments. Measure completed outcomes and corrections before buying reach.
2. Make onboarding task-first: add one bill/return deadline, show its next step, then ask about connected imports. Avoid requesting all integrations before value is visible.
3. Ship a fast responsive web app first; route splitting is implemented. Installable PWA, offline account-scoped sync, app-store packaging and accessibility certification remain work.
4. Publish useful localized guides/templates for moves, appliance warranties and school preparation. Keep public content separate from private user routes. Test acquisition cost and activation per template, not raw traffic.
5. Build household invitations only after explicit sharing and revocation are proven. Referral incentives should reward retained activation and include anti-abuse checks; do not import/send to contacts automatically.
6. Pilot distribution through apartment communities, caregiver groups and employers. Obtain opt-in; employers receive aggregate adoption data only, never private household records.
7. Test language demand with native speakers before broad translation. Start with one Indian language and code-switching for the highest-frequency workflow.
8. Track activation, weekly completed outcomes, exact extraction errors, refund follow-up resolution, 4/8-week retention, support minutes, contribution margin and country-specific cancellation rates.

## Deployment state and remaining gates

Source changes and an additive migration are ready for review. The Docker daemon at the configured OrbStack socket was unavailable, so the running port-30001 deployment has not been upgraded. A synthetic localhost preview was used for component rendering; native date-input automation did not complete a reliable browser submission, so full browser CRUD is still an explicit test gate.

Do not market the whole application as enterprise-ready. Other audit findings remain: full legacy route authorization, account-scoped list convergence, locale-aware receipt/date parsing, quiet-hour scheduling, model/privacy policy consistency, real retailer coverage, document retention/export, full tenant isolation and SSO. Resolve these with scoped regression tests before a commercial launch.
