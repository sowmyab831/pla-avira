"""Chat-Completions-shaped adapters: OpenAI, Moonshot, DeepSeek, xAI, Mistral,
and admin-allowlisted OpenAI-compatible endpoints.

The wire shape is similar but NOT identical; each subclass overrides the hooks
where the provider diverges (JSON-schema syntax, reasoning controls, streaming
usage chunks, model discovery). Base URLs are constants — never user input —
except `CompatAdapter`, which resolves an admin-allowlisted name via ssrf.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional

from app.ai.credentials import ResolvedCredential
from app.ai.providers.base import ProviderAdapter, ToolAccumulator, http_client
from app.ai.schemas import (AIError, AIRequest, AIResponse, ErrorCode, FinishReason, Locality, StreamEvent, ToolProposal,
                            Usage)
from app.ai.ssrf import resolve_compat_endpoint


class ChatCompletionsAdapter(ProviderAdapter):
    name = "openai"
    base_url = "https://api.openai.com/v1"
    supports_usage_in_stream = True     # `stream_options: {include_usage: true}`
    json_schema_style = "response_format"  # or "json_object" for providers without schema support

    # ── hooks ──
    def _base(self, cred: ResolvedCredential) -> str:
        return self.base_url

    def _headers(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _extra_payload(self, req: AIRequest, model: str) -> dict[str, Any]:
        return {}

    def _payload(self, req: AIRequest, model: str, stream: bool) -> dict[str, Any]:
        p: dict[str, Any] = {
            "model": model,
            "messages": [self._msg(m) for m in req.messages],
            "temperature": req.temperature,
            "max_tokens": req.max_output_tokens or 1024,
            "stream": stream,
        }
        if stream and self.supports_usage_in_stream:
            p["stream_options"] = {"include_usage": True}
        if req.json_schema:
            if self.json_schema_style == "response_format" and req.json_schema.get("type"):
                p["response_format"] = {"type": "json_schema", "json_schema": {"name": "avira_output", "schema": req.json_schema, "strict": False}}
            else:
                p["response_format"] = {"type": "json_object"}
        if req.tools:
            p["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in req.tools]
            p["tool_choice"] = "auto"
        p.update(self._extra_payload(req, model))
        return p

    @staticmethod
    def _msg(m) -> dict[str, Any]:
        d: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.name:
            d["name"] = m.name
        if m.tool_call_id:
            d["tool_call_id"] = m.tool_call_id
        return d

    def _usage(self, u: Optional[dict]) -> Usage:
        if not u:
            return Usage(estimated=True)
        details = u.get("prompt_tokens_details") or {}
        cdetails = u.get("completion_tokens_details") or {}
        return Usage(input_tokens=int(u.get("prompt_tokens") or 0), output_tokens=int(u.get("completion_tokens") or 0),
                     cached_input_tokens=int(details.get("cached_tokens") or u.get("prompt_cache_hit_tokens") or 0),
                     reasoning_tokens=int(cdetails.get("reasoning_tokens") or 0), estimated=False)

    def _tools(self, msg: dict) -> list[ToolProposal]:
        out = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            args, complete = self._parse_tool_args(fn.get("arguments") or "")
            out.append(ToolProposal(id=tc.get("id") or "", name=fn.get("name", ""), arguments=args,
                                    raw_arguments=fn.get("arguments") or "", complete=complete))
        return out

    # ── contract ──
    async def complete(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AIResponse:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        data = await self._post_json(f"{self._base(cred)}/chat/completions", headers=self._headers(key),
                                     payload=self._payload(req, model, False), timeout_s=timeout_s, model=model)
        choices = data.get("choices") or []
        if not choices:
            raise AIError(ErrorCode.MALFORMED_OUTPUT, f"{self.name} returned no choices", provider=self.name, model=model, http_status=502)
        ch = choices[0]
        msg = ch.get("message") or {}
        if msg.get("refusal"):
            raise AIError(ErrorCode.SAFETY_REFUSAL, "The provider declined to answer this request", provider=self.name, model=model, http_status=422)
        tools = self._tools(msg)
        return AIResponse(request_id=req.request_id, provider=self.name, model=data.get("model") or model, locality=self.locality,
                          text=msg.get("content") or "", tool_proposals=tools,
                          finish=FinishReason.TOOL if tools else self._finish(ch.get("finish_reason")),
                          usage=self._usage(data.get("usage")), latency_ms=self._now_ms() - t0)

    async def stream(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AsyncIterator[StreamEvent]:
        key = self._require_key(cred, model)
        t0 = self._now_ms()
        yield StreamEvent("started", {"provider": self.name, "model": model})
        acc = ToolAccumulator()
        parts: list[str] = []
        usage = Usage(estimated=True)
        finish = FinishReason.STOP
        actual_model = model
        async for line in self._sse_lines(f"{self._base(cred)}/chat/completions", headers=self._headers(key),
                                          payload=self._payload(req, model, True), timeout_s=timeout_s, model=model):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            actual_model = d.get("model") or actual_model
            if d.get("usage"):
                usage = self._usage(d["usage"])
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    parts.append(delta["content"])
                    yield StreamEvent("text_delta", delta["content"])
                for tc in delta.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    acc.add(str(tc.get("index", tc.get("id", 0))), fn.get("name"), fn.get("arguments") or "")
                if ch.get("finish_reason"):
                    finish = self._finish(ch["finish_reason"])
        tools = acc.proposals()
        for tp in tools:
            yield StreamEvent("tool_proposal", tp)
        yield StreamEvent("usage", usage)
        yield StreamEvent("completed", AIResponse(request_id=req.request_id, provider=self.name, model=actual_model,
                                                  locality=self.locality, text="".join(parts), tool_proposals=tools,
                                                  finish=FinishReason.TOOL if tools else finish, usage=usage,
                                                  latency_ms=self._now_ms() - t0))

    async def list_models(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> list[str]:
        key = self._require_key(cred, "-")
        try:
            async with http_client(timeout_s) as client:
                r = await client.get(f"{self._base(cred)}/models", headers=self._headers(key))
            if r.status_code >= 400:
                raise self._map_http_error(r.status_code, r.text, "-")
            return [m.get("id", "") for m in r.json().get("data", [])]
        except AIError:
            raise
        except Exception as e:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, f"{self.name} discovery failed: {type(e).__name__}", provider=self.name, http_status=503)

    async def test_connection(self, cred: ResolvedCredential, *, timeout_s: float = 15) -> dict[str, Any]:
        """Cheapest authenticated call: list models. May be free; a completion probe is opt-in."""
        try:
            models = await self.list_models(cred, timeout_s=timeout_s)
            return {"ok": True, "detail": f"Authenticated; {len(models)} model(s) visible", "models": models[:50]}
        except AIError as e:
            return {"ok": False, "detail": e.message, "code": e.code.value}


class OpenAIAdapter(ChatCompletionsAdapter):
    name = "openai"
    base_url = "https://api.openai.com/v1"

    def _extra_payload(self, req: AIRequest, model: str) -> dict[str, Any]:
        # GPT-5.x/6 reasoning families reject `temperature`/`max_tokens` on the chat surface in favour of
        # `max_completion_tokens`; keep both compatible by preferring the newer key.
        out: dict[str, Any] = {"max_completion_tokens": req.max_output_tokens or 1024}
        return out

    def _payload(self, req: AIRequest, model: str, stream: bool) -> dict[str, Any]:
        p = super()._payload(req, model, stream)
        p.pop("max_tokens", None)
        return p


class MoonshotAdapter(ChatCompletionsAdapter):
    """Kimi: api.moonshot.ai (keys from platform.kimi.ai are not interchangeable with .com)."""
    name = "moonshot"
    base_url = "https://api.moonshot.ai/v1"
    json_schema_style = "json_object"

    def _extra_payload(self, req: AIRequest, model: str) -> dict[str, Any]:
        # Kimi documents `thinking` control for reasoning-capable models; keep it off unless the task asks.
        return {"thinking": {"type": "enabled" if req.task in ("deep", "reasoning", "research") else "disabled"}}


class DeepSeekAdapter(ChatCompletionsAdapter):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    json_schema_style = "json_object"

    def _extra_payload(self, req: AIRequest, model: str) -> dict[str, Any]:
        deep = req.task in ("deep", "reasoning", "research")
        out: dict[str, Any] = {"thinking": {"type": "enabled" if deep else "disabled"}}
        if deep:
            out["reasoning_effort"] = "high"
        return out

    def _usage(self, u: Optional[dict]) -> Usage:
        usage = super()._usage(u)
        if u and u.get("prompt_cache_hit_tokens") is not None:
            usage.cached_input_tokens = int(u["prompt_cache_hit_tokens"])
        return usage


class XAIAdapter(ChatCompletionsAdapter):
    name = "xai"
    base_url = "https://api.x.ai/v1"


class MistralAdapter(ChatCompletionsAdapter):
    name = "mistral"
    base_url = "https://api.mistral.ai/v1"
    supports_usage_in_stream = False

    def _payload(self, req: AIRequest, model: str, stream: bool) -> dict[str, Any]:
        p = super()._payload(req, model, stream)
        p.pop("stream_options", None)
        if req.json_schema and req.json_schema.get("type"):
            p["response_format"] = {"type": "json_schema", "json_schema": {"name": "avira_output", "schema": req.json_schema, "strict": False}}
        return p


class CompatAdapter(ChatCompletionsAdapter):
    """Admin-allowlisted OpenAI-compatible endpoint (Groq, Together, Fireworks, OpenRouter, hosted Llama/Qwen…)."""
    name = "compat"
    json_schema_style = "json_object"
    supports_usage_in_stream = False

    def _base(self, cred: ResolvedCredential) -> str:
        if not cred.base_url:
            raise AIError(ErrorCode.POLICY_DENIED, "No allowlisted endpoint bound to this connection", provider=self.name, http_status=403)
        return resolve_compat_endpoint(cred.base_url)
