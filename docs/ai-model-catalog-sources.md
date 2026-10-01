# Model catalog sources

Every entry in the seed catalog (`app/ai/registry.py::SEED`) records the page
its identifiers were read from. Catalog verified **2026-09-28** — re-verify IDs,
lifecycle and prices before enabling a hosted provider; several vendors retire
or rename models aggressively.

| Provider | Source of truth | Catalog notes |
|---|---|---|
| Ollama | https://docs.ollama.com/api/introduction + local `GET /api/tags` | Installed set probed at startup: qwen3:14b, qwen2.5:14b, mistral:7b-instruct |
| OpenAI | https://developers.openai.com/api/docs/models | gpt-6-astra, gpt-5.6-sol/terra/luna; prices not yet recorded → managed routing blocked |
| Anthropic | https://platform.claude.com/docs/en/about-claude/models/overview | fable-5-1, opus-5, sonnet-5, haiku-4.5; prices recorded (`anthropic-2026-09`) |
| Google Gemini | https://ai.google.dev/gemini-api/docs/models | 3.8-flash, 3.5-flash-lite, 3.1-pro-preview; preview lifecycle flagged |
| Moonshot | https://platform.kimi.ai/docs/models | kimi-k3, kimi-k2.6; k2 series discontinued 2026-05-25 — do not re-add |
| DeepSeek | https://api-docs.deepseek.com/ | deepseek-flash (V4.1), deepseek-v4-pro; chat/reasoner IDs retired 2026-07-24 |
| xAI | https://docs.x.ai/developers/models | grok-4.6, grok-4.3; prices recorded (`xai-2026-09`); ≥200k prompt surcharge ×2 |
| Mistral | https://docs.mistral.ai/models/overview | medium/small/large `*-latest` aliases |

## Refresh procedure

1. Open the provider's model page (`source_url` on each `ModelSpec`).
2. Diff `GET /api/ai/catalog` against current IDs — mark removed IDs
   `deprecated` → `retired` via `PUT /api/ai/admin/catalog` rather than
   deleting rows (history/audit reference them).
3. Record `price_version` (e.g. `vendor-YYYY-MM`) whenever prices are updated;
   `price_known=false` models can't serve managed (platform-funded) traffic.
4. Re-run `pytest backend/tests/test_ai_adapters.py` after editing the seed.
