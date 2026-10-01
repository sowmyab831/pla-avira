"""Adapter base: shared HTTP client, error normalization, streaming helpers."""
from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

import httpx

from app.ai.credentials import ResolvedCredential, redact
from app.ai.schemas import (AIError, AIRequest, AIResponse, Capability, ErrorCode, FinishReason, Locality,
                            StreamEvent, ToolProposal, Usage)
from app.ai.ssrf import CONNECT_TIMEOUT_S, MAX_RESPONSE_BYTES

_test_transport: Optional[httpx.AsyncBaseTransport] = None


def set_transport_for_tests(transport: Optional[httpx.AsyncBaseTransport]) -> None:
    """Tests inject a MockTransport so no adapter can reach the network."""
    global _test_transport
    _test_transport = transport


def http_client(timeout_s: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_s, connect=CONNECT_TIMEOUT_S),
        transport=_test_transport,
        follow_redirects=False,           # never follow redirects to arbitrary hosts
        verify=True,
    )


class ProviderAdapter(ABC):
    name: str = "base"
    locality: Locality = Locality.CLOUD
    supports_stream: bool = True

    # ── to implement ──
    @abstractmethod
    async def complete(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AIResponse: ...

    async def stream(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AsyncIterator[StreamEvent]:
        """Default: emulate streaming with a single completion."""
        yield StreamEvent("started", {"provider": self.name, "model": model})
        resp = await self.complete(req, model, cred, timeout_s=timeout_s)
        if resp.text:
            yield StreamEvent("text_delta", resp.text)
        for tp in resp.tool_proposals:
            yield StreamEvent("tool_proposal", tp)
        yield StreamEvent("usage", resp.usage)
        yield StreamEvent("completed", resp)

    async def test_connection(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> dict[str, Any]:
        """Synthetic, cheap probe. Returns {ok, detail} with sanitized detail."""
        raise NotImplementedError

    async def list_models(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> list[str]:
        """Discovery only — informs availability, never adds catalog rows."""
        return []

    # ── helpers ──
    def _require_key(self, cred: ResolvedCredential, model: str) -> str:
        if not cred.api_key:
            raise AIError(ErrorCode.MISSING_KEY, f"No API key configured for {self.name}",
                          provider=self.name, model=model, http_status=402)
        return cred.api_key

    def _map_http_error(self, status: int, body_text: str, model: str) -> AIError:
        detail = redact(body_text)
        if status in (401, 403):
            return AIError(ErrorCode.INVALID_KEY, f"{self.name} rejected the credential", provider=self.name, model=model, http_status=401)
        if status == 404:
            return AIError(ErrorCode.UNSUPPORTED_MODEL, f"{self.name} does not know model '{model}'", provider=self.name, model=model)
        if status == 429:
            return AIError(ErrorCode.RATE_LIMITED, f"{self.name} rate limited the request", retryable=True, provider=self.name, model=model, http_status=429)
        if status == 402:
            return AIError(ErrorCode.QUOTA_EXHAUSTED, f"{self.name} reports the account is out of credit", provider=self.name, model=model, http_status=402)
        if 500 <= status < 600:
            return AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} is unavailable ({status})", retryable=True, provider=self.name, model=model, http_status=503)
        return AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} error {status}: {detail[:80]}", provider=self.name, model=model, http_status=502)

    async def _post_json(self, url: str, *, headers: dict, payload: dict, timeout_s: float, model: str) -> dict:
        try:
            async with http_client(timeout_s) as client:
                r = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise AIError(ErrorCode.TIMEOUT, f"{self.name} timed out", retryable=True, provider=self.name, model=model, http_status=504)
        except httpx.HTTPError as e:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} unreachable: {type(e).__name__}", retryable=True, provider=self.name, model=model, http_status=503)
        if r.status_code >= 400:
            raise self._map_http_error(r.status_code, r.text, model)
        if len(r.content) > MAX_RESPONSE_BYTES:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} response too large", provider=self.name, model=model, http_status=502)
        try:
            return r.json()
        except ValueError:
            raise AIError(ErrorCode.MALFORMED_OUTPUT, f"{self.name} returned non-JSON", provider=self.name, model=model, http_status=502)

    async def _sse_lines(self, url: str, *, headers: dict, payload: dict, timeout_s: float, model: str) -> AsyncIterator[str]:
        """Yield `data:` payloads from an SSE/NDJSON stream with size/time limits."""
        received = 0
        try:
            async with http_client(timeout_s) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as r:
                    if r.status_code >= 400:
                        body = (await r.aread()).decode(errors="ignore")
                        raise self._map_http_error(r.status_code, body, model)
                    async for line in r.aiter_lines():
                        received += len(line)
                        if received > MAX_RESPONSE_BYTES:
                            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, "stream too large", provider=self.name, model=model)
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if line.startswith("data:"):
                            line = line[5:].strip()
                        if line == "[DONE]":
                            return
                        yield line
        except httpx.TimeoutException:
            raise AIError(ErrorCode.TIMEOUT, f"{self.name} stream timed out", retryable=False, provider=self.name, model=model, http_status=504)
        except httpx.HTTPError as e:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} stream failed: {type(e).__name__}", provider=self.name, model=model, http_status=503)

    @staticmethod
    def _finish(reason: Optional[str]) -> FinishReason:
        r = (reason or "").lower()
        if r in ("stop", "end_turn", "stop_sequence", "done"):
            return FinishReason.STOP
        if r in ("length", "max_tokens", "max_output_tokens"):
            return FinishReason.LENGTH
        if r in ("tool_calls", "tool_use", "function_call"):
            return FinishReason.TOOL
        if r in ("content_filter", "safety", "refusal"):
            return FinishReason.CONTENT_FILTER
        return FinishReason.STOP

    @staticmethod
    def _parse_tool_args(raw: str) -> tuple[dict, bool]:
        """Return (args, complete). Fragmented JSON is reported incomplete, never guessed."""
        if not raw:
            return {}, True
        try:
            v = json.loads(raw)
            return (v if isinstance(v, dict) else {"value": v}), True
        except ValueError:
            return {}, False

    @staticmethod
    def _now_ms() -> int:
        return int(time.monotonic() * 1000)


class ToolAccumulator:
    """Assemble fragmented streamed tool-call arguments by index/id."""

    def __init__(self):
        self._parts: dict[str, dict] = {}

    def add(self, key: str, name: Optional[str], fragment: str) -> None:
        p = self._parts.setdefault(key, {"name": name or "", "args": ""})
        if name:
            p["name"] = name
        p["args"] += fragment or ""

    def proposals(self) -> list[ToolProposal]:
        out = []
        for key, p in self._parts.items():
            args, complete = ProviderAdapter._parse_tool_args(p["args"])
            out.append(ToolProposal(id=key, name=p["name"], arguments=args, raw_arguments=p["args"], complete=complete))
        return out
