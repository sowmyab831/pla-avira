"""
Ollama LLM Client - Multi-model routing for the Omni-PLA agent system.

Supports model-specific routing:
- DeepSeek-R1:32B  → Quant Agent (options Greeks, risk modeling)
- QWQ:32B          → Orchestrator Agent (task routing, agentic logic)
- Llama 3.3:70B    → Life Agent (nutrition, travel, shopping)
- Mistral 7B       → Policy Agent (fast news analysis, sentiment)
"""

import logging
import json
from typing import Optional, Dict, Any, AsyncGenerator
import httpx

from app.config import settings
from app.services.llm_client import cache_get, cache_key, cache_set, clamp_output_tokens

logger = logging.getLogger(__name__)

# Model registry: maps agent roles to available models
# These are overridden at runtime by settings.model_for_task()
MODEL_REGISTRY = {
    "quant": settings.ollama_finance_model,
    "finance": settings.ollama_finance_model,
    "orchestrator": settings.ollama_model,
    "life": settings.ollama_fast_model,
    "policy": settings.ollama_fast_model,
    "fast": settings.ollama_fast_model,
    "deep": settings.ollama_deep_model,
    "default": settings.ollama_model,
}


class OllamaClient:
    """
    Async Ollama client with retry, fallback, and streaming support.
    
    Usage:
        client = OllamaClient(model="deepseek-r1:32b")
        response = await client.generate("Explain Black-Scholes")
        
        # Or use role-based routing:
        client = OllamaClient.for_role("quant")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        timeout: int = 120,
    ):
        self.model = model or settings.ollama_model
        self.host = host or settings.ollama_host
        self.timeout = timeout
        self._fallback_models = settings.fallback_models

    @classmethod
    def for_role(cls, role: str) -> "OllamaClient":
        """Create a client configured for a specific agent role."""
        model = MODEL_REGISTRY.get(role, MODEL_REGISTRY["default"])
        return cls(model=model)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Generate a completion from Ollama."""
        max_tokens = clamp_output_tokens(max_tokens)
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        # Shared response cache (same store as services.llm_client)
        ck = cache_key(prompt, "legacy", system, temperature, max_tokens, json_mode, model=self.model)
        cached = cache_get(ck)
        if cached is not None:
            logger.debug("OllamaClient cache hit (model=%s)", self.model)
            return cached

        # Try primary model, then fallbacks
        models_to_try = [self.model] + [
            m for m in self._fallback_models if m != self.model
        ]

        last_error = None
        for model in models_to_try:
            payload["model"] = model
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.host}/api/generate",
                        json=payload,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        result = data.get("response", "")
                        if result:
                            cache_set(ck, result)
                        return result
                    else:
                        last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                        logger.warning(f"Ollama {model} returned {resp.status_code}, trying fallback")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Ollama {model} failed: {e}, trying fallback")

        logger.error(f"All Ollama models failed. Last error: {last_error}")
        return f"[LLM unavailable] {last_error}"

    async def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.host}/api/generate",
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

    async def chat(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        json_mode: bool = False,
    ) -> str:
        """Chat-style completion using Ollama's /api/chat endpoint."""
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.host}/api/chat",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "")
                else:
                    logger.error(f"Chat failed: {resp.status_code}")
                    return ""
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return ""

    async def embeddings(self, text: str) -> list[float]:
        """Generate embeddings for vector search."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.host}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding", [])
        except Exception as e:
            logger.error(f"Embeddings error: {e}")
        return []

    async def health_check(self) -> bool:
        """Check if Ollama is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.host}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models on this Ollama instance."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.host}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"List models error: {e}")
        return []
