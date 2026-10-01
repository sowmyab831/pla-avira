"""Adapter contract tests. Every adapter is exercised through httpx.MockTransport:
no network, deterministic. Covers: text, streaming, tool fragments, malformed
JSON, 401/404/429/5xx mapping, refusal, and key redaction in errors."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.ai.credentials import ResolvedCredential
from app.ai.providers import ADAPTERS, adapter_for, set_transport_for_tests
from app.ai.schemas import AIError, AIRequest, ActorContext, ErrorCode, FinishReason, Message, ToolSpec

KEY = "sk-test-SECRETSECRETSECRET1234567890"
CRED = {p: ResolvedCredential(p, None if p == "ollama" else KEY, None, "platform", "platform", base_url="grp" if p == "compat" else None)
        for p in ADAPTERS}
REQ = lambda **kw: AIRequest(actor=ActorContext(user_id="u1"), task="assistant", messages=[Message("user", "hi")], max_output_tokens=32, **kw)


def _sse(*objs) -> bytes:
    return b"".join(f"data: {json.dumps(o)}\n\n".encode() for o in objs) + b"data: [DONE]\n\n"


def _ndjson(*objs) -> bytes:
    return b"".join((json.dumps(o) + "\n").encode() for o in objs)


# ── canned responses per provider ──

def ok_body(provider: str) -> dict:
    if provider == "ollama":
        return {"message": {"role": "assistant", "content": "hello"}, "done": True, "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 2}
    if provider == "anthropic":
        return {"model": "claude-x", "content": [{"type": "text", "text": "hello"}], "stop_reason": "end_turn", "usage": {"input_tokens": 5, "output_tokens": 2}}
    if provider == "gemini":
        return {"candidates": [{"content": {"parts": [{"text": "hello"}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}}
    return {"model": "m", "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}


def tool_body(provider: str) -> dict:
    if provider == "ollama":
        return {"message": {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "add_item", "arguments": {"name": "milk"}}}]}, "done": True}
    if provider == "anthropic":
        return {"content": [{"type": "tool_use", "id": "t1", "name": "add_item", "input": {"name": "milk"}}], "stop_reason": "tool_use", "usage": {"input_tokens": 1, "output_tokens": 1}}
    if provider == "gemini":
        return {"candidates": [{"content": {"parts": [{"functionCall": {"name": "add_item", "args": {"name": "milk"}}}]}, "finishReason": "STOP"}]}
    return {"choices": [{"message": {"tool_calls": [{"id": "t1", "function": {"name": "add_item", "arguments": "{\"name\": \"milk\"}"}}]}, "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def stream_body(provider: str) -> bytes:
    if provider == "ollama":
        return _ndjson({"message": {"content": "hel"}, "done": False}, {"message": {"content": "lo"}, "done": False},
                       {"message": {"content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 3, "eval_count": 2})
    if provider == "anthropic":
        return _sse({"type": "message_start", "message": {"model": "claude-x", "usage": {"input_tokens": 3}}},
                    {"type": "content_block_start", "index": 1, "content_block": {"type": "tool_use", "id": "t1", "name": "add_item"}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "hel"}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "lo"}},
                    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "{\"name\": "}},
                    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": "\"milk\"}"}},
                    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}})
    if provider == "gemini":
        return _sse({"candidates": [{"content": {"parts": [{"text": "hel"}]}}]},
                    {"candidates": [{"content": {"parts": [{"text": "lo"}]}, "finishReason": "STOP"}], "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 2}})
    return _sse({"choices": [{"delta": {"content": "hel"}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "t1", "function": {"name": "add_item", "arguments": "{\"na"}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "me\": \"milk\"}"}}]}, "finish_reason": "tool_calls"}]},
                {"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 2}})


def fragment_stream(provider: str) -> bytes:
    """Tool arguments cut mid-JSON; must be reported incomplete, never guessed."""
    if provider == "ollama":
        return _ndjson({"message": {"content": "", "tool_calls": [{"function": {"name": "pay", "arguments": "{\"amount\": 4"}}]}, "done": True})
    if provider == "anthropic":
        return _sse({"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "t1", "name": "pay"}},
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": "{\"amount\": 4"}},
                    {"type": "message_delta", "delta": {"stop_reason": "tool_use"}, "usage": {"output_tokens": 1}})
    if provider == "gemini":
        return _sse({"candidates": [{"content": {"parts": [{"text": ""}]}, "finishReason": "STOP"}]})
    return _sse({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "t1", "function": {"name": "pay", "arguments": "{\"amount\": 4"}}]}, "finish_reason": "tool_calls"}]})


@pytest.fixture(autouse=True)
def _compat_env(monkeypatch):
    monkeypatch.setattr("app.config.settings.ai_compat_endpoints", "grp=https://api.groq.com/openai/v1")
    monkeypatch.setattr("app.ai.ssrf.validate_outbound", lambda url, allow_internal=False: url.rstrip("/"))
    yield
    set_transport_for_tests(None)


def mock(handler):
    set_transport_for_tests(httpx.MockTransport(handler))


def run(coro):
    return asyncio.run(coro)


async def collect(agen):
    return [ev async for ev in agen]


PROVIDERS = sorted(ADAPTERS)


@pytest.mark.parametrize("provider", PROVIDERS)
def test_complete_text(provider):
    seen = {}
    def h(r: httpx.Request):
        seen["auth"] = r.headers.get("authorization") or r.headers.get("x-api-key") or r.headers.get("x-goog-api-key")
        seen["url"] = str(r.url)
        return httpx.Response(200, json=ok_body(provider))
    mock(h)
    resp = run(adapter_for(provider).complete(REQ(), "m", CRED[provider], timeout_s=5))
    assert resp.text == "hello" and resp.finish == FinishReason.STOP
    assert resp.usage.input_tokens == 5 and resp.usage.output_tokens == 2 and resp.usage.estimated is False
    if provider != "ollama":
        assert KEY in (seen["auth"] or ""), "key must be sent in a header"
        assert KEY not in seen["url"], "key must never be in the URL"


@pytest.mark.parametrize("provider", PROVIDERS)
def test_complete_tool_proposal(provider):
    mock(lambda r: httpx.Response(200, json=tool_body(provider)))
    resp = run(adapter_for(provider).complete(REQ(tools=[ToolSpec("add_item", "d", {"type": "object"})]), "m", CRED[provider], timeout_s=5))
    assert resp.finish == FinishReason.TOOL
    assert resp.tool_proposals and resp.tool_proposals[0].name == "add_item"
    assert resp.tool_proposals[0].arguments == {"name": "milk"} and resp.tool_proposals[0].complete


@pytest.mark.parametrize("provider", PROVIDERS)
def test_stream_events_and_tool_assembly(provider):
    mock(lambda r: httpx.Response(200, content=stream_body(provider), headers={"content-type": "text/event-stream"}))
    events = run(collect(adapter_for(provider).stream(REQ(), "m", CRED[provider], timeout_s=5)))
    types = [e.type for e in events]
    assert types[0] == "started" and types[-1] == "completed" and "usage" in types
    assert "".join(e.data for e in events if e.type == "text_delta") == "hello"
    final = events[-1].data
    assert final.text == "hello"
    if provider in ("anthropic",) or provider not in ("ollama", "gemini"):
        tp = [e.data for e in events if e.type == "tool_proposal"]
        assert tp and tp[0].arguments == {"name": "milk"} and tp[0].complete


@pytest.mark.parametrize("provider", [p for p in PROVIDERS if p != "gemini"])
def test_fragmented_tool_args_reported_incomplete(provider):
    mock(lambda r: httpx.Response(200, content=fragment_stream(provider), headers={"content-type": "text/event-stream"}))
    events = run(collect(adapter_for(provider).stream(REQ(), "m", CRED[provider], timeout_s=5)))
    tp = [e.data for e in events if e.type == "tool_proposal"]
    assert tp and tp[0].complete is False and tp[0].arguments == {}


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("status,code,retryable", [(401, ErrorCode.INVALID_KEY, False), (404, ErrorCode.UNSUPPORTED_MODEL, False),
                                                   (429, ErrorCode.RATE_LIMITED, True), (503, ErrorCode.PROVIDER_UNAVAILABLE, True)])
def test_http_error_mapping_and_redaction(provider, status, code, retryable):
    mock(lambda r: httpx.Response(status, text=f"boom for {KEY} Bearer {KEY}"))
    with pytest.raises(AIError) as ei:
        run(adapter_for(provider).complete(REQ(), "m", CRED[provider], timeout_s=5))
    e = ei.value
    assert e.code == code and e.retryable is retryable
    assert KEY not in e.message and KEY not in json.dumps(e.to_dict())


@pytest.mark.parametrize("provider", PROVIDERS)
def test_non_json_body_is_malformed_not_empty_success(provider):
    mock(lambda r: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(AIError) as ei:
        run(adapter_for(provider).complete(REQ(), "m", CRED[provider], timeout_s=5))
    assert ei.value.code == ErrorCode.MALFORMED_OUTPUT


@pytest.mark.parametrize("provider", [p for p in PROVIDERS if p != "ollama"])
def test_missing_key_is_typed_error(provider):
    mock(lambda r: httpx.Response(200, json=ok_body(provider)))
    with pytest.raises(AIError) as ei:
        run(adapter_for(provider).complete(REQ(), "m", ResolvedCredential(provider, None, None, "platform", "platform", base_url="grp"), timeout_s=5))
    assert ei.value.code == ErrorCode.MISSING_KEY


@pytest.mark.parametrize("provider", PROVIDERS)
def test_timeout_maps_to_timeout(provider):
    def h(r):
        raise httpx.ReadTimeout("slow", request=r)
    mock(h)
    with pytest.raises(AIError) as ei:
        run(adapter_for(provider).complete(REQ(), "m", CRED[provider], timeout_s=1))
    assert ei.value.code == ErrorCode.TIMEOUT


def test_anthropic_refusal_and_openai_refusal():
    mock(lambda r: httpx.Response(200, json={"content": [], "stop_reason": "refusal", "usage": {}}))
    with pytest.raises(AIError) as ei:
        run(adapter_for("anthropic").complete(REQ(), "m", CRED["anthropic"], timeout_s=5))
    assert ei.value.code == ErrorCode.SAFETY_REFUSAL
    mock(lambda r: httpx.Response(200, json={"choices": [{"message": {"refusal": "no"}, "finish_reason": "stop"}]}))
    with pytest.raises(AIError) as ei:
        run(adapter_for("openai").complete(REQ(), "m", CRED["openai"], timeout_s=5))
    assert ei.value.code == ErrorCode.SAFETY_REFUSAL


def test_compat_requires_allowlisted_endpoint():
    mock(lambda r: httpx.Response(200, json=ok_body("compat")))
    bad = ResolvedCredential("compat", KEY, None, "platform", "platform", base_url="not-allowlisted")
    with pytest.raises(Exception):
        run(adapter_for("compat").complete(REQ(), "m", bad, timeout_s=5))


def test_openai_uses_max_completion_tokens_and_anthropic_system_top_level():
    seen = {}
    def h(r):
        seen[r.url.host] = json.loads(r.content)
        return httpx.Response(200, json=ok_body("openai" if "openai" in r.url.host else "anthropic"))
    mock(h)
    req = AIRequest(actor=ActorContext(user_id="u"), task="x", messages=[Message("system", "SYS"), Message("user", "hi")], max_output_tokens=7)
    run(adapter_for("openai").complete(req, "m", CRED["openai"], timeout_s=5))
    run(adapter_for("anthropic").complete(req, "m", CRED["anthropic"], timeout_s=5))
    oa = seen["api.openai.com"]; an = seen["api.anthropic.com"]
    assert oa["max_completion_tokens"] == 7 and "max_tokens" not in oa
    assert an["system"] == "SYS" and all(m["role"] != "system" for m in an["messages"])


@pytest.mark.parametrize("provider", [p for p in PROVIDERS if p != "ollama"])
def test_test_connection_reports_truthful_state(provider):
    mock(lambda r: httpx.Response(401, text="bad key"))
    out = run(adapter_for(provider).test_connection(CRED[provider]))
    assert out["ok"] is False and out.get("code") == "invalid_key"
    mock(lambda r: httpx.Response(200, json={"data": [{"id": "m1"}], "models": [{"name": "models/m1"}]}))
    out = run(adapter_for(provider).test_connection(CRED[provider]))
    assert out["ok"] is True
