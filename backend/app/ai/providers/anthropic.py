"""Anthropic Messages API adapter (system prompt is top-level; SSE event types)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from app.ai.credentials import ResolvedCredential
from app.ai.providers.base import ProviderAdapter, ToolAccumulator, http_client
from app.ai.schemas import (AIError, AIRequest, AIResponse, ErrorCode, FinishReason, Locality, StreamEvent, ToolProposal,
                            Usage)

API_VERSION = "2023-06-01"


class AnthropicAdapter(ProviderAdapter):
    name = "anthropic"
    base_url = "https://api.anthropic.com/v1"

    def _headers(self, key: str) -> dict[str, str]:
        return {"x-api-key": key, "anthropic-version": API_VERSION, "Content-Type": "application/json"}

    def _payload(self, req: AIRequest, model: str, stream: bool) -> dict[str, Any]:
        system = "\n\n".join(m.content for m in req.messages if m.role == "system")
        msgs = []
        for m in req.messages:
            if m.role == "system":
                continue
            if m.role == "tool":
                msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": m.tool_call_id or "", "content": m.content}]})
            else:
                msgs.append({"role": m.role, "content": m.content})
        p: dict[str, Any] = {"model": model, "messages": msgs, "max_tokens": req.max_output_tokens or 1024,
                             "temperature": req.temperature, "stream": stream}
        if system:
            p["system"] = system
        if req.tools:
            p["tools"] = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in req.tools]
        if req.json_schema:
            # Anthropic has no response_format; enforce via a tool with the schema and force its use.
            p["tools"] = (p.get("tools") or []) + [{"name": "avira_output", "description": "Return the structured answer.", "input_schema": req.json_schema if req.json_schema.get("type") else {"type": "object"}}]
            p["tool_choice"] = {"type": "tool", "name": "avira_output"}
        return p

    def _usage(self, u: Optional[dict]) -> Usage:
        if not u:
            return Usage(estimated=True)
        return Usage(input_tokens=int(u.get("input_tokens") or 0), output_tokens=int(u.get("output_tokens") or 0),
                     cached_input_tokens=int(u.get("cache_read_input_tokens") or 0), estimated=False)

    async def complete(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AIResponse:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        data = await self._post_json(f"{self.base_url}/messages", headers=self._headers(key),
                                     payload=self._payload(req, model, False), timeout_s=timeout_s, model=model)
        text_parts, tools, structured = [], [], None
        for block in data.get("content") or []:
            if block.get("type") == "text":
                text_parts.append(block.get("text") or "")
            elif block.get("type") == "tool_use":
                if block.get("name") == "avira_output" and req.json_schema:
                    structured = block.get("input")
                else:
                    tools.append(ToolProposal(id=block.get("id") or "", name=block.get("name") or "", arguments=block.get("input") or {},
                                              raw_arguments=json.dumps(block.get("input") or {})))
        stop = data.get("stop_reason")
        if stop == "refusal":
            raise AIError(ErrorCode.SAFETY_REFUSAL, "The provider declined to answer this request", provider=self.name, model=model, http_status=422)
        text = "".join(text_parts) or (json.dumps(structured) if structured is not None else "")
        return AIResponse(request_id=req.request_id, provider=self.name, model=data.get("model") or model, locality=self.locality,
                          text=text, structured=structured, tool_proposals=tools,
                          finish=FinishReason.TOOL if tools else self._finish(stop), usage=self._usage(data.get("usage")),
                          latency_ms=self._now_ms() - t0)

    async def stream(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AsyncIterator[StreamEvent]:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        yield StreamEvent("started", {"provider": self.name, "model": model})
        acc = ToolAccumulator()
        block_names: dict[int, tuple[str, str]] = {}
        parts: list[str] = []
        usage = Usage(estimated=True)
        finish = FinishReason.STOP
        actual_model = model
        async for line in self._sse_lines(f"{self.base_url}/messages", headers=self._headers(key),
                                          payload=self._payload(req, model, True), timeout_s=timeout_s, model=model):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            if t == "message_start":
                m = d.get("message") or {}
                actual_model = m.get("model") or actual_model
                usage = self._usage(m.get("usage"))
            elif t == "content_block_start":
                cb = d.get("content_block") or {}
                if cb.get("type") == "tool_use":
                    block_names[d.get("index", 0)] = (cb.get("id") or str(d.get("index")), cb.get("name") or "")
            elif t == "content_block_delta":
                delta = d.get("delta") or {}
                if delta.get("type") == "text_delta":
                    parts.append(delta.get("text") or "")
                    yield StreamEvent("text_delta", delta.get("text") or "")
                elif delta.get("type") == "input_json_delta":
                    tid, name = block_names.get(d.get("index", 0), (str(d.get("index")), ""))
                    acc.add(tid, name, delta.get("partial_json") or "")
            elif t == "message_delta":
                dd = d.get("delta") or {}
                if dd.get("stop_reason"):
                    finish = self._finish(dd["stop_reason"])
                u = d.get("usage") or {}
                if u.get("output_tokens") is not None:
                    usage.output_tokens = int(u["output_tokens"])
                    usage.estimated = False
            elif t == "error":
                raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, "Anthropic stream error", provider=self.name, model=model, http_status=502)
        tools = acc.proposals()
        for tp in tools:
            yield StreamEvent("tool_proposal", tp)
        yield StreamEvent("usage", usage)
        yield StreamEvent("completed", AIResponse(request_id=req.request_id, provider=self.name, model=actual_model, locality=self.locality,
                                                  text="".join(parts), tool_proposals=tools,
                                                  finish=FinishReason.TOOL if tools else finish, usage=usage,
                                                  latency_ms=self._now_ms() - t0))

    async def list_models(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> list[str]:
        key = self._require_key(cred, "-")
        try:
            async with http_client(timeout_s) as client:
                r = await client.get(f"{self.base_url}/models", headers=self._headers(key))
            if r.status_code >= 400:
                raise self._map_http_error(r.status_code, r.text, "-")
            return [m.get("id", "") for m in r.json().get("data", [])]
        except AIError:
            raise
        except Exception as e:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"anthropic discovery failed: {type(e).__name__}", provider=self.name, http_status=503)

    async def test_connection(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> dict[str, Any]:
        try:
            models = await self.list_models(cred, timeout_s=timeout_s)
            return {"ok": True, "detail": f"Authenticated; {len(models)} model(s) visible", "models": models[:50]}
        except AIError as e:
            return {"ok": False, "detail": e.message, "code": e.code.value}
