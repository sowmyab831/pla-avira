# Provider support matrix

Adapter contract: `complete()`, `stream()`, `list_models()` (where the provider
supports it), normalized `Usage`, normalized `AIError`. Contract tests:
`backend/tests/test_ai_adapters.py` (mocked transport, all providers).

| Provider | Adapter | Streaming | JSON schema | Tools | Vision | Reasoning | Model list | Price data | Live-tested |
|---|---|---|---|---|---|---|---|---|---|
| Ollama (local) | `ollama.py` | ✓ | ✓ (`format`) | — | — | ✓ (qwen3) | ✓ probed at startup | n/a (free, local) | ✓ |
| OpenAI | `openai_compat.py` | ✓ | ✓ | ✓ | ✓ | ✓ | static catalog | not yet recorded | mocked only |
| Anthropic | `anthropic.py` | ✓ | ✓ | ✓ | ✓ | ✓ | static catalog | ✓ recorded | mocked only |
| Google Gemini | `gemini.py` | ✓ | ✓ (`responseSchema`) | ✓ | ✓ | ✓ | static catalog | not yet recorded | mocked only |
| Moonshot Kimi | `openai_compat.py` | ✓ | ✓ | ✓ | ✓ | ✓ | static catalog | not yet recorded | mocked only |
| DeepSeek | `openai_compat.py` | ✓ | ✓ | ✓ | — | ✓ | static catalog | not yet recorded | mocked only |
| xAI | `openai_compat.py` | ✓ | ✓ | ✓ | ✓ | ✓ | static catalog | ✓ recorded | mocked only |
| Mistral | `openai_compat.py` | ✓ | ✓ | ✓ | ✓ | — | static catalog | not yet recorded | mocked only |
| OpenAI-compat (custom) | `openai_compat.py` | ✓ | ✓ | ✓ | varies | varies | provider `/models` | unknown → BYOK only | mocked only |

Notes

- "Live-tested ✓" only applies to Ollama: the three installed models are probed
  from the running server at startup (`GET /api/tags`) and answer real requests.
- Hosted providers are **contract-tested with mocked transports** only. They are
  unreachable at runtime until `AVIRA_AI_CLOUD=true` AND a credential exists —
  managed routing also requires recorded prices (see `ai-cost-and-usage.md`).
- `compat` endpoints are admin-allowlisted hosts (`AVIRA_AI_COMPAT_ENDPOINTS`)
  and pass through the SSRF guard; credentials are always user/org supplied.
- Capability flags come from official docs as of the catalog date; a model's
  `source_url` in `GET /api/ai/catalog` points at the page it was read from.
