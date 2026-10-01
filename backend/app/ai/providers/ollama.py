"""Local Ollama adapter (`/api/chat`, NDJSON streaming, `/api/tags` discovery)."""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

from app.ai.credentials import ResolvedCredential
from app.ai.providers.base import ProviderAdapter, ToolAccumulator, http_client
from app.ai.schemas import (AIError, AIRequest, AIResponse, ErrorCode, FinishReason, Locality, StreamEvent, ToolProposal,
                            Usage)
from app.ai.ssrf import ollama_base_url


class OllamaAdapter(ProviderAdapter):
    name = "ollama"
    locality = Locality.LOCAL

    def _payload(self, req: AIRequest, model: str, stream: bool) -> dict[str, Any]:
        msgs = [{"role": m.role, "content": m.content} for m in req.messages]
        p: dict[str, Any] = {
            "model": model, "messages": msgs, "stream": stream,
            "options": {"temperature": req.temperature, "num_predict": req.max_output_tokens or 1024},
        }
        if req.json_schema:
            p["format"] = req.json_schema if isinstance(req.json_schema, dict) and req.json_schema.get("type") else "json"
        if req.tools:
            p["tools"] = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}} for t in req.tools]
        if model.startswith("qwen3"):
            p["think"] = False
        return p

    def _usage(self, d: dict) -> Usage:
        return Usage(input_tokens=int(d.get("prompt_eval_count") or 0), output_tokens=int(d.get("eval_count") or 0),
                     estimated=not ("eval_count" in d))

    def _tools(self, msg: dict) -> list[ToolProposal]:
        out = []
        for i, tc in enumerate(msg.get("tool_calls") or []):
            fn = tc.get("function") or {}
            args = fn.get("arguments")
            if isinstance(args, dict):
                out.append(ToolProposal(id=str(i), name=fn.get("name", ""), arguments=args, raw_arguments=json.dumps(args)))
            else:
                parsed, complete = self._parse_tool_args(str(args or ""))
                out.append(ToolProposal(id=str(i), name=fn.get("name", ""), arguments=parsed, raw_arguments=str(args or ""), complete=complete))
        return out

    async def complete(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AIResponse:
        t0 = self._now_ms()
        data = await self._post_json(f"{ollama_base_url()}/api/chat", headers={}, payload=self._payload(req, model, False),
                                     timeout_s=timeout_s, model=model)
        msg = data.get("message") or {}
        text = msg.get("content") or ""
        tools = self._tools(msg)
        return AIResponse(request_id=req.request_id, provider=self.name, model=model, locality=self.locality, text=text,
                          tool_proposals=tools, finish=FinishReason.TOOL if tools else self._finish(data.get("done_reason")),
                          usage=self._usage(data), cost_micro_usd=0, cost_final=True, price_version="local-0",
                          latency_ms=self._now_ms() - t0)

    async def stream(self, req: AIRequest, model: str, cred: ResolvedCredential, *, timeout_s: float) -> AsyncIterator[StreamEvent]:
        t0 = self._now_ms()
        yield StreamEvent("started", {"provider": self.name, "model": model})
        acc = ToolAccumulator()
        text_parts: list[str] = []
        usage = Usage()
        finish = FinishReason.STOP
        async for line in self._sse_lines(f"{ollama_base_url()}/api/chat", headers={}, payload=self._payload(req, model, True),
                                          timeout_s=timeout_s, model=model):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") or {}
            if msg.get("content"):
                text_parts.append(msg["content"])
                yield StreamEvent("text_delta", msg["content"])
            for i, tc in enumerate(msg.get("tool_calls") or []):
                fn = tc.get("function") or {}
                args = fn.get("arguments")
                acc.add(str(i), fn.get("name"), json.dumps(args) if isinstance(args, dict) else str(args or ""))
            if d.get("done"):
                usage = self._usage(d)
                finish = self._finish(d.get("done_reason"))
        tools = acc.proposals()
        for tp in tools:
            yield StreamEvent("tool_proposal", tp)
        yield StreamEvent("usage", usage)
        yield StreamEvent("completed", AIResponse(request_id=req.request_id, provider=self.name, model=model, locality=self.locality,
                                                  text="".join(text_parts), tool_proposals=tools,
                                                  finish=FinishReason.TOOL if tools else finish, usage=usage, cost_micro_usd=0,
                                                  cost_final=True, price_version="local-0", latency_ms=self._now_ms() - t0))

    async def list_models(self, cred: ResolvedCredential, *, timeout_s: float = 10) -> list[str]:
        try:
            async with http_client(timeout_s) as client:
                r = await client.get(f"{ollama_base_url()}/api/tags")
                r.raise_for_status()
                return [m.get("name", "") for m in r.json().get("models", [])]
        except Exception:
            return []

    async def test_connection(self, cred: ResolvedCredential, *, timeout_s: float = 10) -> dict[str, Any]:
        models = await self.list_models(cred, timeout_s=timeout_s)
        if not models:
            return {"ok": False, "detail": "Ollama is not reachable or has no models installed"}
        return {"ok": True, "detail": f"{len(models)} local model(s) installed", "models": models}
