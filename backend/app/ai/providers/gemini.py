"""Google Gemini `generateContent` / `streamGenerateContent` adapter.

Gemini takes the key as a header (`x-goog-api-key`), never in the URL, so it is
not leaked through access logs.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from app.ai.credentials import ResolvedCredential
from app.ai.providers.base import ProviderAdapter, http_client
from app.ai.schemas import (AIError, AIRequest, AIResponse, ErrorCode, FinishReason, Locality, StreamEvent, ToolProposal,
                            Usage)


class GeminiAdapter(ProviderAdapter):
    name = "gemini"
    base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _headers(self, key: str) -> dict[str, str]:
        return {"x-goog-api-key": key, "Content-Type": "application/json"}

    def _payload(self, req: AIRequest, model: str) -> dict[str, Any]:
        system = "\n\n".join(m.content for m in req.messages if m.role == "system")
        contents = []
        for m in req.messages:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            if m.role == "tool":
                contents.append({"role": "user", "parts": [{"functionResponse": {"name": m.name or "tool", "response": {"content": m.content}}}]})
            else:
                contents.append({"role": role, "parts": [{"text": m.content}]})
        gen: dict[str, Any] = {"temperature": req.temperature, "maxOutputTokens": req.max_output_tokens or 1024}
        if req.json_schema:
            gen["responseMimeType"] = "application/json"
            if req.json_schema.get("type"):
                gen["responseSchema"] = req.json_schema
        p: dict[str, Any] = {"contents": contents, "generationConfig": gen}
        if system:
            p["systemInstruction"] = {"parts": [{"text": system}]}
        if req.tools:
            p["tools"] = [{"functionDeclarations": [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in req.tools]}]
        return p

    def _usage(self, u: Optional[dict]) -> Usage:
        if not u:
            return Usage(estimated=True)
        return Usage(input_tokens=int(u.get("promptTokenCount") or 0), output_tokens=int(u.get("candidatesTokenCount") or 0),
                     cached_input_tokens=int(u.get("cachedContentTokenCount") or 0),
                     reasoning_tokens=int(u.get("thoughtsTokenCount") or 0), estimated=False)

    def _parse_candidate(self, cand: dict, model: str) -> tuple[str, list[ToolProposal], FinishReason]:
        fr = cand.get("finishReason")
        if fr in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
            raise AIError(ErrorCode.SAFETY_REFUSAL, "The provider declined to answer this request", provider=self.name, model=model, http_status=422)
        text_parts, tools = [], []
        for i, part in enumerate((cand.get("content") or {}).get("parts") or []):
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                tools.append(ToolProposal(id=str(i), name=fc.get("name", ""), arguments=fc.get("args") or {}, raw_arguments=json.dumps(fc.get("args") or {})))
        finish = FinishReason.TOOL if tools else self._finish({"STOP": "stop", "MAX_TOKENS": "length"}.get(fr or "", "stop"))
        return "".join(text_parts), tools, finish

    async def complete(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AIResponse:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        data = await self._post_json(f"{self.base_url}/models/{model}:generateContent", headers=self._headers(key),
                                     payload=self._payload(req, model), timeout_s=timeout_s, model=model)
        cands = data.get("candidates") or []
        if not cands:
            if (data.get("promptFeedback") or {}).get("blockReason"):
                raise AIError(ErrorCode.SAFETY_REFUSAL, "The provider blocked this prompt", provider=self.name, model=model, http_status=422)
            raise AIError(ErrorCode.MALFORMED_OUTPUT, "gemini returned no candidates", provider=self.name, model=model, http_status=502)
        text, tools, finish = self._parse_candidate(cands[0], model)
        return AIResponse(request_id=req.request_id, provider=self.name, model=data.get("modelVersion") or model, locality=self.locality,
                          text=text, tool_proposals=tools, finish=finish, usage=self._usage(data.get("usageMetadata")),
                          latency_ms=self._now_ms() - t0)

    async def stream(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AsyncIterator[StreamEvent]:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        yield StreamEvent("started", {"provider": self.name, "model": model})
        parts: list[str] = []
        tools: list[ToolProposal] = []
        usage = Usage(estimated=True)
        finish = FinishReason.STOP
        async for line in self._sse_lines(f"{self.base_url}/models/{model}:streamGenerateContent?alt=sse", headers=self._headers(key),
                                          payload=self._payload(req, model), timeout_s=timeout_s, model=model):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("usageMetadata"):
                usage = self._usage(d["usageMetadata"])
            for cand in d.get("candidates") or []:
                text, t, f = self._parse_candidate(cand, model)
                if text:
                    parts.append(text)
                    yield StreamEvent("text_delta", text)
                tools.extend(t)
                if cand.get("finishReason"):
                    finish = f
        for tp in tools:
            yield StreamEvent("tool_proposal", tp)
        yield StreamEvent("usage", usage)
        yield StreamEvent("completed", AIResponse(request_id=req.request_id, provider=self.name, model=model, locality=self.locality,
                                                  text="".join(parts), tool_proposals=tools,
                                                  finish=FinishReason.TOOL if tools else finish, usage=usage,
                                                  latency_ms=self._now_ms() - t0))

    async def list_models(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> list[str]:
        key = self._require_key(cred, "-")
        try:
            async with http_client(timeout_s) as client:
                r = await client.get(f"{self.base_url}/models?pageSize=200", headers=self._headers(key))
            if r.status_code >= 400:
                raise self._map_http_error(r.status_code, r.text, "-")
            return [(m.get("name") or "").removeprefix("models/") for m in r.json().get("models", [])]
        except AIError:
            raise
        except Exception as e:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"gemini discovery failed: {type(e).__name__}", provider=self.name, http_status=503)

    async def test_connection(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> dict[str, Any]:
        try:
            models = await self.list_models(cred, timeout_s=timeout_s)
            return {"ok": True, "detail": f"Authenticated; {len(models)} model(s) visible", "models": models[:50]}
        except AIError as e:
            return {"ok": False, "detail": e.message, "code": e.code.value}
