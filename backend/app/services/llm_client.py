"""Thin async Ollama client with JSON extraction and graceful fallback.

Every new Nexus-era service goes through this so model routing, timeouts and
JSON parsing live in one place.
"""
from __future__ import annotations

import asyncio
import contextvars
import hashlib
import os
import json
import logging
import re
import time
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_LLM_CAPACITY = asyncio.Semaphore(max(1, int(os.getenv("AVIRA_LLM_CONCURRENCY", "2"))))
_MAX_INPUT_CHARS = max(1000, int(os.getenv("AVIRA_LLM_MAX_INPUT_CHARS", "24000")))
# Hard ceiling. Callers may ask for fewer tokens, never more.
_MAX_OUTPUT_TOKENS = max(128, int(os.getenv("AVIRA_LLM_MAX_OUTPUT_TOKENS", "1024")))
_CACHE_TTL = int(os.getenv("AVIRA_LLM_CACHE_TTL", "300"))  # 5 min default
_CACHE_MAX = 200
# Bump when prompt templates or policy semantics change so stale entries miss.
CACHE_POLICY_VERSION = "r0-2026-09-28"

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.S)

# ── Actor context ───────────────────────────────────────────────────
# Routes/background jobs set this so every LLM call is attributable to an
# authenticated principal. Absence means "anonymous local-only" and is what
# the AI gateway uses to refuse cloud processing.
current_actor: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar("avira_actor", default=None)


def set_actor(user_id: Optional[str], tenant_id: Optional[str] = None, role: str = "user") -> contextvars.Token:
    return current_actor.set({"user_id": user_id, "tenant_id": tenant_id, "role": role} if user_id else None)


def clamp_output_tokens(requested: Optional[int]) -> int:
    """Configured ceiling wins; browser/caller values cannot exceed it."""
    if not requested or requested <= 0:
        return _MAX_OUTPUT_TOKENS
    return min(int(requested), _MAX_OUTPUT_TOKENS)


# ── Response cache ──────────────────────────────────────────────────
_response_cache: dict[str, tuple[float, str]] = {}


def _cache_key(prompt: str, task: str, system: str | None, temperature: float,
               max_tokens: int | None = None, json_mode: bool = False,
               model: str | None = None, scope: str | None = None) -> str:
    """Scoped cache key: tenant/user, provider/model and policy version are part
    of the key so one user's response is never served to another."""
    actor = current_actor.get()
    scope = scope or (f"{actor.get('tenant_id') or '-'}:{actor.get('user_id')}" if actor else "anon")
    model = model or settings.model_for_task(task)
    raw = f"{CACHE_POLICY_VERSION}|{scope}|ollama:{model}|{task}|{temperature}|{max_tokens or ''}|{json_mode}|{system or ''}|{prompt}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_get(key: str) -> str | None:
    entry = _response_cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    if entry:
        _response_cache.pop(key, None)
    return None


def _cache_set(key: str, value: str) -> None:
    if len(_response_cache) >= _CACHE_MAX:
        oldest = min(_response_cache, key=lambda k: _response_cache[k][0])
        _response_cache.pop(oldest, None)
    _response_cache[key] = (time.time(), value)


# Public aliases so the legacy OllamaClient can share the same cache.
cache_key = _cache_key
cache_get = _cache_get
cache_set = _cache_set


def extract_json(text: str) -> Optional[Any]:
    """Pull the first JSON object/array out of an LLM response."""
    if not text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    m = _JSON_BLOCK.search(cleaned)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


async def generate(prompt: str, task: str = "fast", system: Optional[str] = None,
                   timeout: Optional[float] = None, temperature: float = 0.2,
                   max_tokens: Optional[int] = None, json_mode: bool = False,
                   user_id: Optional[str] = None) -> str:
    """Compatibility facade over the AI gateway.

    When an authenticated actor is present (request context or explicit
    `user_id` for background jobs) the call goes through `app.ai.gateway`
    (policy, budget, audit). Otherwise it stays local-only against Ollama.
    Results are cached for AVIRA_LLM_CACHE_TTL seconds (default 300).
    """
    if len(prompt) + len(system or "") > _MAX_INPUT_CHARS:
        logger.warning("LLM input exceeds configured budget")
        return ""

    model = settings.model_for_task(task)
    max_tokens = clamp_output_tokens(max_tokens)

    # Check cache first
    ck = _cache_key(prompt, task, system, temperature, max_tokens, json_mode, model=model)
    cached = _cache_get(ck)
    if cached is not None:
        logger.debug("LLM cache hit (task=%s)", task)
        return cached

    acquired = False
    try:
        await asyncio.wait_for(_LLM_CAPACITY.acquire(), timeout=2)
        acquired = True
        if settings.ai_gateway_enabled and current_actor.get():
            result = await _via_gateway(prompt, task, system, temperature, max_tokens, json_mode, timeout, user_id)
        else:
            result = await _via_ollama_direct(prompt, model, system, temperature, max_tokens, json_mode, timeout)
        if result:
            _cache_set(ck, result)
        return result
    except Exception:
        logger.warning("LLM unavailable or capacity exhausted (task=%s)", task, exc_info=logger.isEnabledFor(logging.DEBUG))
        return ""
    finally:
        if acquired:
            _LLM_CAPACITY.release()


async def _via_gateway(prompt, task, system, temperature, max_tokens, json_mode, timeout, user_id) -> str:
    """Route through app.ai.gateway with the request actor (policy/budget/audit apply).

    Legacy callers pass a free-text prompt; it is wrapped as a single user message.
    The gateway picks the model via the actor's policy, so `settings.model_for_task`
    is only a hint through the task name."""
    from app.ai.gateway import Gateway, actor_from_context
    from app.ai.schemas import AIRequest, Capability, DataClass, Message
    actor = actor_from_context(user_id)
    msgs = ([Message("system", system)] if system else []) + [Message("user", prompt)]
    req = AIRequest(actor=actor, task=task, messages=msgs, data_class=DataClass.PERSONAL,
                    required={Capability.TEXT} | ({Capability.JSON_SCHEMA} if json_mode else set()),
                    temperature=temperature, max_output_tokens=max_tokens,
                    json_schema={"type": "object"} if json_mode else None, deadline_s=timeout)
    resp = await Gateway(db=None).complete(req)
    return resp.text


async def _via_ollama_direct(prompt, model, system, temperature, max_tokens, json_mode, timeout) -> str:
    """Anonymous/local path (no actor): local Ollama only, never cloud."""
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"
    if system:
        payload["system"] = system
    if model.startswith("qwen3"):
        payload["think"] = False
    async with httpx.AsyncClient(timeout=min(timeout or settings.ollama_timeout, 60)) as client:
        resp = await client.post(f"{settings.ollama_host}/api/generate", json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")


async def generate_json(prompt: str, task: str = "fast", system: Optional[str] = None,
                        timeout: Optional[float] = None, user_id: Optional[str] = None) -> Optional[Any]:
    """Generate and parse JSON. Returns None when the model is unavailable."""
    raw = await generate(prompt, task=task, system=system, timeout=timeout, temperature=0.1, user_id=user_id)
    return extract_json(raw)
