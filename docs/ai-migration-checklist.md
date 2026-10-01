# AI call-site inventory and gateway migration checklist

Generated 2026-09-28 from a source scan of `backend/app` (excluding `node_modules`,
virtualenvs and `__pycache__`). Re-run the scan before closing any row; the
repository changes frequently.

Legend — **Via**: how the call reaches a model today. **Actor**: whether an
authenticated principal is attached (`ctx` = via `llm_client.current_actor`
middleware, `explicit` = user id passed in code, `none` = anonymous).
**Cloud**: can this path send data off-box today? **Status**: `gateway` (routed
through `app.ai.gateway`), `facade` (goes through `llm_client.generate`, which
becomes a gateway facade in R1), `blocked` (cloud path disabled by flag),
`pending` (direct HTTP/SDK, not yet migrated).

| # | File | Modality | Task | Via | Actor | Cloud | Privacy policy | Status |
|---|------|----------|------|-----|-------|-------|----------------|--------|
| 1 | `services/llm_client.py` | text | shared client | Ollama `/api/generate` | ctx | no | scoped cache, output ceiling | facade |
| 2 | `integrations/ollama_client.py` | text/embed | legacy agent client | Ollama `/api/generate`,`/api/chat`,`/api/embeddings` | ctx | no | shares scoped cache, ceiling | facade (R1: delegate to gateway) |
| 3 | `router_ai.py` `_call_ollama` | text | assistant chat | `llm_client` | ctx | no | `mask_text` before | facade |
| 4 | `router_ai.py` `_call_external_llm` | text | assistant (masked) | **OpenAI HTTPS** | none | **yes** | masked only; no consent/budget | **blocked** (`AVIRA_AI_CLOUD=false`) → R1 gateway |
| 5 | `router_ai.py` `chat_stream` | text-stream | assistant SSE | Ollama `/api/generate` direct | ctx | no | `mask_text` | pending → R1 gateway stream |
| 6 | `router_assistant.py` `handle_general_chat` | text | multi-domain chat | Ollama `/api/chat` direct | **body `user_id`** | no | privacy_vault mask | pending → R1 gateway (actor from token) |
| 7 | `routes/bills.py` | text | bill extraction | Ollama `/api/generate` direct | ctx | no | none | pending |
| 8 | `services/smart_shopping.py` | text | query understanding | Ollama `/api/generate` direct | ctx | no | none | pending |
| 9 | `services/document_ocr.py` | OCR+text | doc classify/extract | pytesseract + Ollama direct | explicit | no | mask after OCR | pending |
| 10 | `services/document_pipeline.py` | text | doc analysis | `OllamaClient` | explicit | no | mask before LLM | facade |
| 11 | `services/llm_privacy_middleware.py` | text | wrapper | `OllamaClient` | ctx | no | masking wrapper (coverage partial) | facade |
| 12 | `agents/{life,orchestrator,policy,quant}_agent.py` | text | agent roles | `OllamaClient.for_role` | ctx | no | none | facade |
| 13 | `integrations/email_analyzer.py` | text | email action items | `llm_client` | explicit (job) | no | none | facade; background owner check R3 |
| 14 | `services/imap_radar.py` | text | inbox radar | `llm_client` | explicit (job) | no | none | facade; background owner check R3 |
| 15 | `services/intent_engine.py` | text | multi-intent parse | `llm_client` | ctx | no | none | facade |
| 16 | `routes/care.py` | text | care summaries | `llm_client` | ctx | no | none | facade |
| 17 | `routes/family_hub.py` | text | family insights | `llm_client` | ctx | no | none | facade |
| 18 | `routes/forecast.py` | text | forecast synthesis | `llm_client` | ctx | no | none | facade |
| 19 | `routes/maintenance.py` | text | maintenance advice | `llm_client` | ctx | no | none | facade |
| 20 | `routes/market_intel.py` | text | market digest | `llm_client` | ctx | no | none | facade |
| 21 | `routes/nexus.py` | OCR+text | receipt OCR, actions | pytesseract + `llm_client` | ctx | no | none | facade |
| 22 | `search.py` | embeddings | semantic search | `SentenceTransformer` (local) | n/a | no | local model | local-only (not gateway) |
| 23 | `routes/voice.py` | STT/TTS | voice | local Whisper; **ElevenLabs** if key | ctx | **yes (TTS)** | audio text sent to ElevenLabs | pending: gate TTS on cloud flag (R1) |
| 24 | `services/scheduler.py` (via 13/14 + trading tips) | text | background | indirect | explicit | no | — | R3 durable jobs |
| 25 | `config.py` | — | model routing | — | — | — | — | replaced by `app.ai.registry` in R1 |

## Release 0 state

- Every path that could send content off-box is now either behind
  `AVIRA_AI_CLOUD` (row 4) or flagged for R1 (row 23, ElevenLabs TTS).
- All Ollama paths share one output-token ceiling and a cache keyed by
  tenant/user/model/policy version.
- Autonomous trading loops are disabled by default; unattended real-money
  orders were removed from the scheduler.

## Release 1 exit criteria for this file

Every row is `gateway`, `local-only`, or has an explicit written exception. A
test (`test_ai_call_inventory.py`) greps the source for direct
`/api/generate|/api/chat|api.openai.com|api.anthropic.com` outside
`app/ai/providers/` and fails if a non-allowlisted file appears.
