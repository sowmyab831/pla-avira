"""Provider adapters. Each translates the canonical AIRequest into the provider's
wire format and normalizes the result. No adapter is ever called directly by
routes; the gateway owns policy, budget and audit."""
from __future__ import annotations

from app.ai.providers.base import ProviderAdapter, set_transport_for_tests
from app.ai.providers.anthropic import AnthropicAdapter
from app.ai.providers.gemini import GeminiAdapter
from app.ai.providers.ollama import OllamaAdapter
from app.ai.providers.openai_compat import (CompatAdapter, DeepSeekAdapter, MistralAdapter, MoonshotAdapter,
                                            OpenAIAdapter, XAIAdapter)

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    "ollama": OllamaAdapter,
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
    "moonshot": MoonshotAdapter,
    "deepseek": DeepSeekAdapter,
    "xai": XAIAdapter,
    "mistral": MistralAdapter,
    "compat": CompatAdapter,
}


def adapter_for(provider: str) -> ProviderAdapter:
    cls = ADAPTERS.get(provider)
    if cls is None:
        raise KeyError(provider)
    return cls()


__all__ = ["ADAPTERS", "adapter_for", "ProviderAdapter", "set_transport_for_tests"]
