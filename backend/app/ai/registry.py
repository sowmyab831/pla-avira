"""Provider/model catalog and capability matrix.

The seed below is the curated starting catalog. Model IDs and prices were read
from official documentation on 2026-09-28 (see docs/ai-model-catalog-sources.md).
Prices are integer micro-USD per 1M tokens. `None` means "not verified": the
budget layer refuses managed (platform-funded) routing to such a model until an
administrator records a price. Discovery endpoints (`/v1/models`) may be used to
*check* availability but never add rows automatically.

Only the local Ollama entries are `active` by default because they can be
verified against the running server. Hosted entries are `candidate` until a
connection test succeeds and an admin enables them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Optional

from app.ai.schemas import Capability as C, Locality, Profile

SOURCES_VERIFIED_AT = "2026-09-28"

PROVIDER_META: dict[str, dict] = {
    "ollama":    {"label": "Local (Ollama)", "locality": Locality.LOCAL, "env": None,
                  "docs": "https://docs.ollama.com/api/introduction"},
    "openai":    {"label": "OpenAI", "locality": Locality.CLOUD, "env": "OPENAI_API_KEY",
                  "docs": "https://developers.openai.com/api/docs/models"},
    "anthropic": {"label": "Anthropic Claude", "locality": Locality.CLOUD, "env": "ANTHROPIC_API_KEY",
                  "docs": "https://platform.claude.com/docs/en/about-claude/models/overview"},
    "gemini":    {"label": "Google Gemini", "locality": Locality.CLOUD, "env": "GEMINI_API_KEY",
                  "docs": "https://ai.google.dev/gemini-api/docs/models"},
    "moonshot":  {"label": "Moonshot Kimi", "locality": Locality.CLOUD, "env": "MOONSHOT_API_KEY",
                  "docs": "https://platform.kimi.ai/docs/models"},
    "deepseek":  {"label": "DeepSeek", "locality": Locality.CLOUD, "env": "DEEPSEEK_API_KEY",
                  "docs": "https://api-docs.deepseek.com/"},
    "xai":       {"label": "xAI Grok", "locality": Locality.CLOUD, "env": "XAI_API_KEY",
                  "docs": "https://docs.x.ai/developers/models"},
    "mistral":   {"label": "Mistral", "locality": Locality.CLOUD, "env": "MISTRAL_API_KEY",
                  "docs": "https://docs.mistral.ai/models/overview"},
    "compat":    {"label": "OpenAI-compatible (admin allowlisted)", "locality": Locality.CLOUD, "env": None,
                  "docs": ""},
}

_TEXT = {C.TEXT, C.STREAMING}
_TOOLS = _TEXT | {C.TOOLS, C.JSON_SCHEMA}
_FULL = _TOOLS | {C.VISION}


@dataclass
class ModelSpec:
    provider: str
    model_id: str
    display_name: str
    capabilities: set[C]
    tier: Profile
    context_window: Optional[int] = None
    input_micro_per_1m: Optional[int] = None
    output_micro_per_1m: Optional[int] = None
    cached_input_micro_per_1m: Optional[int] = None
    lifecycle: str = "candidate"          # candidate | active | deprecated | retired
    source_url: str = ""
    price_version: Optional[str] = None
    notes: str = ""

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"

    @property
    def locality(self) -> Locality:
        return PROVIDER_META[self.provider]["locality"]

    @property
    def price_known(self) -> bool:
        return self.input_micro_per_1m is not None and self.output_micro_per_1m is not None

    def to_dict(self) -> dict:
        return {
            "key": self.key, "provider": self.provider, "model_id": self.model_id,
            "display_name": self.display_name, "capabilities": sorted(c.value for c in self.capabilities),
            "tier": self.tier.value, "context_window": self.context_window,
            "locality": self.locality.value, "lifecycle": self.lifecycle,
            "price_known": self.price_known, "price_version": self.price_version,
            "price": None if not self.price_known else {
                "input_per_1m_micro_usd": self.input_micro_per_1m,
                "output_per_1m_micro_usd": self.output_micro_per_1m,
                "cached_input_per_1m_micro_usd": self.cached_input_micro_per_1m,
            },
            "source_url": self.source_url, "notes": self.notes,
        }


def _usd(dollars: float) -> int:
    return int(round(dollars * 1_000_000))


# ── Seed catalog ───────────────────────────────────────────────────────────
SEED: list[ModelSpec] = [
    # Local — verified against the running Ollama server at startup
    ModelSpec("ollama", "qwen3:14b", "Qwen3 14B (local, deep)", _TEXT | {C.JSON_SCHEMA, C.REASONING},
              Profile.QUALITY, 32768, 0, 0, 0, "active", PROVIDER_META["ollama"]["docs"], "local-0",
              "Hybrid thinking model; `think` disabled by default for latency."),
    ModelSpec("ollama", "qwen2.5:14b", "Qwen2.5 14B (local, finance)", _TEXT | {C.JSON_SCHEMA},
              Profile.BALANCED, 32768, 0, 0, 0, "active", PROVIDER_META["ollama"]["docs"], "local-0"),
    ModelSpec("ollama", "mistral:7b-instruct", "Mistral 7B Instruct (local, fast)", _TEXT | {C.JSON_SCHEMA},
              Profile.ECONOMY, 32768, 0, 0, 0, "active", PROVIDER_META["ollama"]["docs"], "local-0"),

    # OpenAI — IDs from developers.openai.com/api/docs/models (2026-09-28); prices not recorded → managed routing blocked
    ModelSpec("openai", "gpt-6-astra", "GPT-6 Astra", _FULL | {C.REASONING}, Profile.QUALITY, None,
              source_url="https://developers.openai.com/api/docs/models"),
    ModelSpec("openai", "gpt-5.6-sol", "GPT-5.6 Sol", _FULL | {C.REASONING}, Profile.QUALITY, None,
              source_url="https://developers.openai.com/api/docs/models"),
    ModelSpec("openai", "gpt-5.6-terra", "GPT-5.6 Terra", _FULL, Profile.BALANCED, None,
              source_url="https://developers.openai.com/api/docs/models"),
    ModelSpec("openai", "gpt-5.6-luna", "GPT-5.6 Luna", _FULL, Profile.ECONOMY, None,
              source_url="https://developers.openai.com/api/docs/models"),

    # Anthropic — IDs + prices from platform.claude.com models overview (2026-09-28)
    ModelSpec("anthropic", "claude-fable-5-1", "Claude Fable 5.1", _FULL | {C.REASONING}, Profile.QUALITY, 1_000_000,
              _usd(10), _usd(50), _usd(0.25), source_url=PROVIDER_META["anthropic"]["docs"], price_version="anthropic-2026-09"),
    ModelSpec("anthropic", "claude-opus-5", "Claude Opus 5", _FULL | {C.REASONING}, Profile.QUALITY, 1_000_000,
              _usd(5), _usd(25), None, source_url=PROVIDER_META["anthropic"]["docs"], price_version="anthropic-2026-09"),
    ModelSpec("anthropic", "claude-sonnet-5", "Claude Sonnet 5", _FULL | {C.REASONING}, Profile.BALANCED, 1_000_000,
              _usd(2), _usd(10), None, source_url=PROVIDER_META["anthropic"]["docs"], price_version="anthropic-2026-09"),
    ModelSpec("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", _FULL, Profile.ECONOMY, 200_000,
              _usd(1), _usd(5), None, source_url=PROVIDER_META["anthropic"]["docs"], price_version="anthropic-2026-09",
              notes="Retirement not sooner than 2026-10-15; re-verify before enabling."),

    # Gemini — IDs from ai.google.dev (2026-09-28); prices not recorded
    ModelSpec("gemini", "gemini-3.8-flash", "Gemini 3.8 Flash", _FULL, Profile.BALANCED, None,
              source_url=PROVIDER_META["gemini"]["docs"]),
    ModelSpec("gemini", "gemini-3.5-flash-lite", "Gemini 3.5 Flash-Lite", _FULL, Profile.ECONOMY, None,
              source_url=PROVIDER_META["gemini"]["docs"]),
    ModelSpec("gemini", "gemini-3.1-pro-preview", "Gemini 3.1 Pro (preview)", _FULL | {C.REASONING}, Profile.QUALITY, None,
              source_url=PROVIDER_META["gemini"]["docs"], notes="Preview lifecycle."),

    # Moonshot — kimi-k2 series discontinued 2026-05-25; current IDs from platform.kimi.ai/docs/models
    ModelSpec("moonshot", "kimi-k3", "Kimi K3", _FULL | {C.REASONING}, Profile.QUALITY, None,
              source_url=PROVIDER_META["moonshot"]["docs"], notes="Check `supports_reasoning` via /v1/models."),
    ModelSpec("moonshot", "kimi-k2.6", "Kimi K2.6", _FULL | {C.REASONING}, Profile.BALANCED, 256_000,
              source_url=PROVIDER_META["moonshot"]["docs"]),

    # DeepSeek — `deepseek-chat`/`deepseek-reasoner` retire 2026-07-24; current IDs from api-docs.deepseek.com
    ModelSpec("deepseek", "deepseek-flash", "DeepSeek Flash (V4.1)", _TOOLS | {C.REASONING}, Profile.ECONOMY, None,
              source_url=PROVIDER_META["deepseek"]["docs"]),
    ModelSpec("deepseek", "deepseek-v4-pro", "DeepSeek V4 Pro", _TOOLS | {C.REASONING}, Profile.QUALITY, None,
              source_url=PROVIDER_META["deepseek"]["docs"]),

    # xAI — IDs + prices (<200k prompt tier) from docs.x.ai/developers/models (2026-09-28)
    ModelSpec("xai", "grok-4.6", "Grok 4.6", _FULL | {C.REASONING}, Profile.QUALITY, 500_000,
              _usd(2), _usd(6), _usd(0.5), source_url=PROVIDER_META["xai"]["docs"], price_version="xai-2026-09",
              notes="Long-context (≥200k) surcharge doubles input/output; estimator applies 2x above threshold."),
    ModelSpec("xai", "grok-4.3", "Grok 4.3", _FULL | {C.REASONING}, Profile.BALANCED, 1_000_000,
              _usd(1.25), _usd(2.5), _usd(0.2), source_url=PROVIDER_META["xai"]["docs"], price_version="xai-2026-09"),

    # Mistral — aliases from docs.mistral.ai/models/overview; prices not recorded
    ModelSpec("mistral", "mistral-medium-latest", "Mistral Medium 3.5", _TOOLS | {C.VISION}, Profile.BALANCED, None,
              source_url=PROVIDER_META["mistral"]["docs"]),
    ModelSpec("mistral", "mistral-small-latest", "Mistral Small 4", _TOOLS | {C.VISION}, Profile.ECONOMY, None,
              source_url=PROVIDER_META["mistral"]["docs"]),
    ModelSpec("mistral", "mistral-large-latest", "Mistral Large 3", _TOOLS | {C.VISION}, Profile.QUALITY, None,
              source_url=PROVIDER_META["mistral"]["docs"]),
]


class Registry:
    """In-memory view of the catalog. `load_overrides` merges DB rows (admin edits)."""

    def __init__(self, seed: Iterable[ModelSpec] = SEED):
        self._models: dict[str, ModelSpec] = {m.key: m for m in seed}
        self._installed_local: set[str] | None = None
        self._installed_checked_at: Optional[datetime] = None

    # ── lookup ──
    def get(self, provider: str, model_id: str) -> Optional[ModelSpec]:
        return self._models.get(f"{provider}:{model_id}")

    def all(self) -> list[ModelSpec]:
        return list(self._models.values())

    def for_provider(self, provider: str) -> list[ModelSpec]:
        return [m for m in self._models.values() if m.provider == provider]

    def upsert(self, spec: ModelSpec) -> None:
        self._models[spec.key] = spec

    def apply_db_rows(self, rows) -> None:
        """Merge admin-maintained rows (enablement, lifecycle, prices)."""
        for r in rows:
            spec = self.get(r.provider, r.model_id)
            price = r.price_micro_usd or {}
            merged = ModelSpec(
                provider=r.provider, model_id=r.model_id, display_name=r.display_name or (spec.display_name if spec else r.model_id),
                capabilities={C(c) for c in (r.capabilities or [])} or (spec.capabilities if spec else _TEXT),
                tier=Profile(r.tier) if r.tier else (spec.tier if spec else Profile.BALANCED),
                context_window=r.context_window or (spec.context_window if spec else None),
                input_micro_per_1m=price.get("input_per_1m") if price else (spec.input_micro_per_1m if spec else None),
                output_micro_per_1m=price.get("output_per_1m") if price else (spec.output_micro_per_1m if spec else None),
                cached_input_micro_per_1m=price.get("cached_input_per_1m") if price else (spec.cached_input_micro_per_1m if spec else None),
                lifecycle=("active" if r.enabled else (r.lifecycle or "candidate")),
                source_url=r.source_url or (spec.source_url if spec else ""),
                price_version=r.price_version or (spec.price_version if spec else None),
                notes=r.notes or (spec.notes if spec else ""),
            )
            self._models[merged.key] = merged

    # ── local availability ──
    def set_installed_local(self, names: Iterable[str]) -> None:
        self._installed_local = set(names)
        self._installed_checked_at = datetime.utcnow()

    def local_installed(self, model_id: str) -> Optional[bool]:
        """True/False when known, None when Ollama has not been probed."""
        if self._installed_local is None:
            return None
        return model_id in self._installed_local or any(n.split(":")[0] == model_id for n in self._installed_local)

    # ── selection helpers ──
    def profile_default(self, profile: Profile, *, local_only: bool, allowed_providers: set[str]) -> Optional[ModelSpec]:
        candidates = [m for m in self._models.values()
                      if m.lifecycle == "active" and m.tier == profile and m.provider in allowed_providers
                      and (not local_only or m.locality == Locality.LOCAL)]
        # Prefer local when available; deterministic order by provider name then id
        candidates.sort(key=lambda m: (m.locality != Locality.LOCAL, m.provider, m.model_id))
        return candidates[0] if candidates else None

    def supports(self, spec: ModelSpec, required: set[C]) -> tuple[bool, set[C]]:
        missing = set(required) - spec.capabilities
        return (not missing, missing)


_registry: Registry | None = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry


def reset_registry_for_tests() -> None:
    global _registry
    _registry = None
