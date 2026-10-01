"""The AI gateway: single entry point for every model call.

    complete(req)  → AIResponse
    stream(req)    → async iterator of StreamEvent

Sequence: policy → credential → capability → budget reserve → provider →
validate → settle → audit. Provider errors are normalized; fallback happens
only when permitted by the Decision; visible partial output is never retried
as if nothing was sent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, AsyncIterator, Callable, Optional

from sqlalchemy import select

from app.ai import budget as budget_mod
from app.ai.credentials import ResolvedCredential, credential_from_row, platform_credential
from app.ai.policy import Decision, UserPolicy, decide
from app.ai.providers import adapter_for
from app.ai.registry import ModelSpec, Registry, get_registry
from app.ai.schemas import (ActorContext, AIError, AIRequest, AIResponse, DataClass, ErrorCode, Locality, Mode, Profile,
                            StreamEvent, Usage)
from app.config import settings
from app.models.ai import AIAuditEventDB, AIConnectionDB, AIPreferenceDB
from app.services import llm_client as facade

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = facade._MAX_INPUT_CHARS
RETRY_BACKOFF_S = (0.5, 1.5)          # bounded retry for 429/transient 5xx
DEFAULT_TIMEOUT_S = 60.0


# ── policy loading ─────────────────────────────────────────────────────────

async def load_policy(db, actor: ActorContext) -> UserPolicy:
    pol = UserPolicy()
    if db is None:
        return pol
    rows = (await db.execute(select(AIPreferenceDB).where(
        ((AIPreferenceDB.scope_kind == "user") & (AIPreferenceDB.scope_id == actor.user_id)) |
        ((AIPreferenceDB.scope_kind == "org") & (AIPreferenceDB.scope_id == (actor.tenant_id or "__none__")))))).scalars().all()
    org = next((r for r in rows if r.scope_kind == "org"), None)
    user = next((r for r in rows if r.scope_kind == "user"), None)
    if org:
        pol.org_cloud_allowed = bool(org.cloud_allowed)
        allowed = (org.per_task or {}).get("__allowed_providers__")
        pol.org_allowed_providers = set(allowed) if allowed else None
    if user:
        pol.mode = Mode(user.mode)
        pol.profile = Profile(user.profile)
        pol.default_provider, pol.default_model = user.default_provider, user.default_model
        pol.per_task = {k: v for k, v in (user.per_task or {}).items() if not k.startswith("__")}
        pol.fallback_providers = list(user.fallback_providers or [])
        pol.cloud_allowed = bool(user.cloud_allowed)
        pol.max_data_class_cloud = DataClass(user.max_data_class_cloud)
        pol.detail_level = user.detail_level
    return pol


# ── credential resolution ──────────────────────────────────────────────────

async def resolve_credential(db, actor: ActorContext, spec: ModelSpec, *, connection_id: Optional[str] = None) -> ResolvedCredential:
    if spec.provider == "ollama":
        return platform_credential("ollama")
    if db is not None:
        q = select(AIConnectionDB).where(AIConnectionDB.provider == spec.provider, AIConnectionDB.status != "revoked")
        rows = (await db.execute(q)).scalars().all()
        visible = [r for r in rows if (r.owner_kind == "user" and r.owner_id == actor.user_id)
                   or (r.owner_kind == "org" and actor.tenant_id and r.owner_id == actor.tenant_id)
                   or r.owner_kind == "platform"]
        if connection_id:
            row = next((r for r in visible if r.id == connection_id), None)
            if row is None:
                raise AIError(ErrorCode.POLICY_DENIED, "That connection is not available to you", provider=spec.provider, http_status=403)
            return credential_from_row(row, funding="byok" if row.owner_kind == "user" else "platform")
        if settings.ai_byok_enabled:
            row = next((r for r in visible if r.owner_kind == "user"), None)
            if row:
                return credential_from_row(row, funding="byok")
        row = next((r for r in visible if r.owner_kind == "org"), None) or next((r for r in visible if r.owner_kind == "platform"), None)
        if row and row.secret_ciphertext:
            return credential_from_row(row, funding="platform")
    return platform_credential(spec.provider)


# ── audit ──────────────────────────────────────────────────────────────────

async def audit(db, actor: ActorContext, action: str, *, target: str | None = None, decision: str | None = None,
                reason: str | None = None, request_id: str | None = None) -> None:
    if db is None:
        return
    try:
        db.add(AIAuditEventDB(actor_id=actor.user_id, tenant_id=actor.tenant_id, action=action, target=target,
                              decision=decision, reason=(reason or "")[:200], request_id=request_id))
        await db.commit()
    except Exception:  # audit must never break the request
        logger.debug("audit write failed", exc_info=True)


# ── structured output ──────────────────────────────────────────────────────

def normalize_schema(schema: dict) -> dict:
    """Make sure every required key has a property entry so constrained decoders
    (Ollama `format`, OpenAI json_schema, Gemini responseSchema) emit them."""
    if not schema or schema.get("type") not in (None, "object"):
        return schema
    props = dict(schema.get("properties") or {})
    for k in schema.get("required") or []:
        props.setdefault(k, {})
    out = dict(schema)
    out["type"] = "object"
    out["properties"] = props
    return out


def _validate_structured(resp: AIResponse, schema: dict) -> tuple[bool, Any]:
    payload = resp.structured if resp.structured is not None else facade.extract_json(resp.text)
    if payload is None:
        return False, None
    required = schema.get("required") or []
    if isinstance(payload, dict) and all(k in payload for k in required):
        props = schema.get("properties") or {}
        for k, spec in props.items():
            if k in payload and spec.get("type") == "number" and not isinstance(payload[k], (int, float)):
                return False, payload
        return True, payload
    if not isinstance(payload, dict) and schema.get("type") == "array" and isinstance(payload, list):
        return True, payload
    return False, payload


# ── gateway ────────────────────────────────────────────────────────────────

class Gateway:
    def __init__(self, db=None, *, registry: Registry | None = None, is_sqlite: bool = False):
        self.db = db
        self.registry = registry or get_registry()
        self.ledger = budget_mod.BudgetLedger(db, is_sqlite=is_sqlite) if db is not None else None

    # ── public ──
    async def complete(self, req: AIRequest) -> AIResponse:
        self._guard_input(req)
        pol = await load_policy(self.db, req.actor)
        decision = decide(req, pol, self.registry)
        candidates = [decision.primary] + decision.fallbacks
        last_err: Optional[AIError] = None
        fallback_from: Optional[str] = None
        for i, spec in enumerate(candidates):
            attempt_reason = None if i == 0 else (last_err.code.value if last_err else "fallback")
            try:
                resp = await self._invoke(req, spec, decision, attempt=i + 1, fallback_from=fallback_from, fallback_reason=attempt_reason)
                return resp
            except AIError as e:
                last_err = e
                await audit(self.db, req.actor, "invoke.error", target=spec.key, decision="deny" if not e.retryable else "retry",
                            reason=e.code.value, request_id=req.request_id)
                if not self._may_fallback(e, decision):
                    raise
                fallback_from = spec.key
                continue
        assert last_err is not None
        raise last_err

    async def stream(self, req: AIRequest) -> AsyncIterator[StreamEvent]:
        self._guard_input(req)
        pol = await load_policy(self.db, req.actor)
        decision = decide(req, pol, self.registry)
        spec = decision.primary
        cred = await resolve_credential(self.db, req.actor, spec)
        if spec.locality == Locality.CLOUD and not cred.configured:
            raise AIError(ErrorCode.MISSING_KEY, f"No credential configured for {spec.provider}", provider=spec.provider, model=spec.model_id, http_status=402)
        max_out = facade.clamp_output_tokens(req.max_output_tokens)
        req.max_output_tokens = max_out
        res = await self._reserve(req, spec, cred, attempt=1)
        adapter = adapter_for(spec.provider)
        t0 = time.monotonic()
        emitted = False
        final: Optional[AIResponse] = None
        try:
            async for ev in adapter.stream(req, spec.model_id, cred, timeout_s=self._timeout(req)):
                if ev.type == "text_delta":
                    emitted = True
                if ev.type == "completed":
                    final = ev.data
                    final.mode = decision.mode
                    final.usage = final.usage or Usage()
                    if res:
                        cost, is_final = await self.ledger.settle(res, req.actor, spec, final.usage,
                                                                 latency_ms=int((time.monotonic() - t0) * 1000))
                        final.cost_micro_usd, final.cost_final = cost, is_final
                    final.price_version = spec.price_version
                    ev = StreamEvent("completed", final)
                yield ev
        except (asyncio.CancelledError, GeneratorExit):
            if res:
                await self.ledger.settle(res, req.actor, spec, Usage(estimated=True), latency_ms=int((time.monotonic() - t0) * 1000),
                                         state="pending")   # possibly billed → pending, not refunded
            raise
        except AIError as e:
            if res:
                # after visible partial output the usage is ambiguous → pending; before any output → release
                await self.ledger.settle(res, req.actor, spec, Usage(estimated=True), latency_ms=int((time.monotonic() - t0) * 1000),
                                         state="pending" if emitted else "released")
            yield StreamEvent("error", e.to_dict())
            return

    # ── internals ──
    def _guard_input(self, req: AIRequest) -> None:
        if req.json_schema:
            req.json_schema = normalize_schema(req.json_schema)
        if req.prompt_chars > MAX_INPUT_CHARS:
            raise AIError(ErrorCode.INPUT_TOO_LARGE, f"Input exceeds {MAX_INPUT_CHARS} characters", http_status=413)
        if req.actor is None or not req.actor.user_id:
            raise AIError(ErrorCode.POLICY_DENIED, "An authenticated actor is required", http_status=401)
        if not settings.ai_gateway_enabled:
            raise AIError(ErrorCode.PROVIDER_UNAVAILABLE, "AI gateway is disabled", http_status=503)

    def _timeout(self, req: AIRequest) -> float:
        return min(req.deadline_s or DEFAULT_TIMEOUT_S, float(settings.ollama_timeout))

    @staticmethod
    def _may_fallback(e: AIError, decision: Decision) -> bool:
        if not decision.fallbacks:
            return False
        # Never fall back on policy/consent/auth/safety/quota problems.
        if e.code in (ErrorCode.POLICY_DENIED, ErrorCode.CONSENT_REQUIRED, ErrorCode.SAFETY_REFUSAL,
                      ErrorCode.QUOTA_EXHAUSTED, ErrorCode.INPUT_TOO_LARGE, ErrorCode.INVALID_KEY):
            return False
        return e.code in (ErrorCode.PROVIDER_UNAVAILABLE, ErrorCode.RATE_LIMITED, ErrorCode.TIMEOUT,
                          ErrorCode.LOCAL_MODEL_MISSING, ErrorCode.MISSING_KEY)

    def _idem(self, req: AIRequest, spec: ModelSpec, attempt: int) -> str:
        base = req.idempotency_key or req.request_id
        return hashlib.sha256(f"{base}|{spec.key}|{attempt}".encode()).hexdigest()[:48]

    async def _reserve(self, req: AIRequest, spec: ModelSpec, cred: ResolvedCredential, *, attempt: int,
                       fallback_from: Optional[str] = None):
        if self.ledger is None:
            return None
        return await self.ledger.reserve(req.actor, spec, task=req.task, request_id=req.request_id,
                                         idempotency_key=self._idem(req, spec, attempt), prompt_chars=req.prompt_chars,
                                         max_output_tokens=req.max_output_tokens or 1024, funding=cred.funding,
                                         connection_id=cred.connection_id, attempt=attempt, fallback_from=fallback_from)

    async def _invoke(self, req: AIRequest, spec: ModelSpec, decision: Decision, *, attempt: int,
                      fallback_from: Optional[str], fallback_reason: Optional[str]) -> AIResponse:
        cred = await resolve_credential(self.db, req.actor, spec)
        if spec.locality == Locality.CLOUD and not cred.configured:
            raise AIError(ErrorCode.MISSING_KEY, f"No credential configured for {spec.provider}", provider=spec.provider, model=spec.model_id, http_status=402)
        req.max_output_tokens = facade.clamp_output_tokens(req.max_output_tokens)
        res = await self._reserve(req, spec, cred, attempt=attempt, fallback_from=fallback_from)
        adapter = adapter_for(spec.provider)
        t0 = time.monotonic()
        resp: Optional[AIResponse] = None
        try:
            for i, backoff in enumerate((0.0,) + RETRY_BACKOFF_S):
                if backoff:
                    await asyncio.sleep(backoff)
                try:
                    resp = await adapter.complete(req, spec.model_id, cred, timeout_s=self._timeout(req))
                    break
                except AIError as e:
                    if e.retryable and i < len(RETRY_BACKOFF_S):
                        continue
                    raise
            assert resp is not None
            if req.json_schema:
                ok, payload = _validate_structured(resp, req.json_schema)
                if not ok:
                    # one budgeted repair attempt
                    repair = AIRequest(actor=req.actor, task=req.task, messages=req.messages + [
                        facade_message("assistant", resp.text[:4000]),
                        facade_message("user", "Your previous answer was not valid JSON for the required schema. "
                                               "Return ONLY a JSON object matching the schema. No prose.")],
                        data_class=req.data_class, required=req.required, selection=req.selection, temperature=0.0,
                        max_output_tokens=req.max_output_tokens, json_schema=req.json_schema, request_id=req.request_id + "-repair",
                        cacheable=False)
                    resp2 = await adapter.complete(repair, spec.model_id, cred, timeout_s=self._timeout(req))
                    ok, payload = _validate_structured(resp2, req.json_schema)
                    resp.usage.input_tokens += resp2.usage.input_tokens
                    resp.usage.output_tokens += resp2.usage.output_tokens
                    resp.text = resp2.text
                    if not ok:
                        raise AIError(ErrorCode.MALFORMED_OUTPUT, "Model output did not match the required schema",
                                      provider=spec.provider, model=spec.model_id, http_status=422)
                resp.structured = payload
        except AIError:
            if res:
                await self.ledger.release(res, req.actor, spec)
            raise
        latency = int((time.monotonic() - t0) * 1000)
        resp.latency_ms = latency
        resp.mode = decision.mode
        resp.fallback_from, resp.fallback_reason = fallback_from, fallback_reason
        resp.price_version = spec.price_version
        if res:
            cost, final = await self.ledger.settle(res, req.actor, spec, resp.usage, latency_ms=latency)
            resp.cost_micro_usd, resp.cost_final = cost, final
        await audit(self.db, req.actor, "invoke.ok", target=spec.key, decision="allow", reason=decision.reason, request_id=req.request_id)
        return resp


def facade_message(role: str, content: str):
    from app.ai.schemas import Message
    return Message(role=role, content=content)


# ── convenience for routes/services ────────────────────────────────────────

def actor_from_context(user_id: Optional[str] = None) -> ActorContext:
    """Build an ActorContext from the request contextvar, or an explicit id for background jobs."""
    ctx = facade.current_actor.get()
    if ctx and ctx.get("user_id"):
        return ActorContext(user_id=ctx["user_id"], tenant_id=ctx.get("tenant_id"), role=ctx.get("role", "user"))
    if user_id:
        return ActorContext(user_id=user_id, is_background=True)
    raise AIError(ErrorCode.POLICY_DENIED, "No authenticated actor for this AI request", http_status=401)


def actor_from_user(user, *, is_background: bool = False) -> ActorContext:
    return ActorContext(user_id=user.user_id, tenant_id=getattr(user, "tenant_id", None), role=getattr(user, "role", "user"),
                        is_background=is_background)
