"""AI & Privacy settings API.

Ownership is derived from the Bearer token. Secrets are write-only: they are
accepted on create/replace, encrypted, and never returned. Organization
connections are managed by org admins; platform connections by platform
admins; users only see what they may use.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import budget as budget_mod
from app.ai.credentials import ResolvedCredential, credential_from_row, encrypt_secret, platform_credential
from app.ai.gateway import actor_from_user, audit, load_policy
from app.ai.providers import ADAPTERS, adapter_for
from app.ai.registry import PROVIDER_META, SOURCES_VERIFIED_AT, get_registry
from app.ai.schemas import AIError, Capability, DataClass, Mode, Profile
from app.ai.ssrf import compat_endpoints
from app.config import settings
from app.database import UserDB, get_session
from app.models.ai import AIConnectionDB, AIModelCatalogDB, AIPreferenceDB, AIUsageEventDB
from app.routes.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

_PROVIDERS = set(ADAPTERS)


def _is_sqlite(db) -> bool:
    bind = getattr(getattr(db, "session", db), "bind", None) or getattr(getattr(db, "session", db), "get_bind", lambda: None)()
    return bool(bind is not None and getattr(bind, "dialect", None) is not None and bind.dialect.name == "sqlite")


def _err(e: AIError):
    return HTTPException(status_code=e.http_status, detail=e.to_dict())


# ── schemas ──

class PreferencesIn(BaseModel):
    mode: Mode = Mode.LOCAL_ONLY
    profile: Profile = Profile.BALANCED
    default_provider: Optional[str] = None
    default_model: Optional[str] = None
    per_task: dict[str, dict[str, str]] = Field(default_factory=dict)
    fallback_providers: list[str] = Field(default_factory=list)
    cloud_allowed: bool = False
    max_data_class_cloud: DataClass = DataClass.MASKED
    detail_level: str = "normal"
    monthly_cap_micro_usd: Optional[int] = Field(default=None, ge=0)
    version: int = 1

    @field_validator("default_provider", "fallback_providers")
    @classmethod
    def _known_provider(cls, v):
        vals = v if isinstance(v, list) else ([v] if v else [])
        bad = [p for p in vals if p not in _PROVIDERS]
        if bad:
            raise ValueError(f"unknown provider(s): {bad}")
        return v

    @field_validator("per_task")
    @classmethod
    def _per_task_shape(cls, v):
        for task, sel in v.items():
            if task.startswith("__"):
                raise ValueError("reserved task name")
            if set(sel) - {"provider", "model"} or sel.get("provider") not in _PROVIDERS:
                raise ValueError(f"invalid per-task selection for {task}")
        return v


class ConnectionIn(BaseModel):
    provider: str
    label: str = Field(default="", max_length=80)
    api_key: str = Field(min_length=8, max_length=512)
    owner_kind: str = "user"            # user | org | platform
    endpoint_ref: Optional[str] = None  # compat endpoints only

    @field_validator("provider")
    @classmethod
    def _p(cls, v):
        if v not in _PROVIDERS or v == "ollama":
            raise ValueError("unsupported provider")
        return v


class EstimateIn(BaseModel):
    provider: str
    model: str
    prompt_chars: int = Field(ge=0, le=200_000)
    max_output_tokens: int = Field(default=1024, ge=1, le=32_000)


# ── helpers ──

async def _visible_connections(db, user: UserDB) -> list[AIConnectionDB]:
    rows = (await db.execute(select(AIConnectionDB).where(AIConnectionDB.status != "revoked"))).scalars().all()
    tenant = getattr(user, "tenant_id", None)
    return [r for r in rows if (r.owner_kind == "user" and r.owner_id == user.user_id)
            or (r.owner_kind == "org" and tenant and r.owner_id == tenant)
            or r.owner_kind == "platform"]


def _conn_out(r: AIConnectionDB, *, editable: bool) -> dict[str, Any]:
    return {"id": r.id, "provider": r.provider, "label": r.label, "owner_kind": r.owner_kind,
            "secret_hint": f"…{r.secret_hint}" if r.secret_hint else None, "status": r.status,
            "last_checked_at": r.last_checked_at.isoformat() if r.last_checked_at else None,
            "last_error": r.last_error, "endpoint_ref": r.endpoint_ref, "editable": editable,
            "billed_to": "you" if r.owner_kind == "user" else ("your organization" if r.owner_kind == "org" else "Avira allowance")}


def _can_manage(user: UserDB, owner_kind: str, owner_id: str) -> bool:
    if owner_kind == "user":
        return owner_id == user.user_id and settings.ai_byok_enabled
    if owner_kind == "org":
        return getattr(user, "tenant_id", None) == owner_id and user.role in ("admin", "org_admin")
    return user.role == "admin"


# ── catalog ──

@router.get("/catalog")
async def catalog(task: Optional[str] = None, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    reg = get_registry()
    rows = (await db.execute(select(AIModelCatalogDB))).scalars().all()
    if rows:
        reg.apply_db_rows(rows)
    if reg.local_installed("qwen3:14b") is None:
        reg.set_installed_local(await adapter_for("ollama").list_models(platform_credential("ollama"), timeout_s=3))
    pol = await load_policy(db, actor_from_user(user))
    conns = await _visible_connections(db, user)
    configured = {"ollama"} | {c.provider for c in conns if c.secret_ciphertext} | {p for p in _PROVIDERS if platform_credential(p).api_key}
    cloud_ok = settings.ai_cloud_enabled and pol.org_cloud_allowed and pol.cloud_allowed
    out = []
    for m in sorted(reg.all(), key=lambda s: (s.locality.value != "local", s.provider, s.model_id)):
        d = m.to_dict()
        disabled_reason = None
        if m.locality.value == "cloud" and not cloud_ok:
            disabled_reason = "Cloud processing is off. Enable it under Mode to use hosted models."
        elif m.provider not in configured:
            disabled_reason = f"No credential configured for {PROVIDER_META[m.provider]['label']}."
        elif m.provider == "ollama" and reg.local_installed(m.model_id) is False:
            disabled_reason = "Not installed locally. Run `ollama pull " + m.model_id + "`."
        elif m.lifecycle == "candidate":
            disabled_reason = "Candidate: not yet enabled by an administrator after a successful connection test."
        elif m.lifecycle in ("deprecated", "retired"):
            disabled_reason = f"Model is {m.lifecycle}."
        elif task and task in ("extract", "intent") and Capability.JSON_SCHEMA not in m.capabilities:
            disabled_reason = "Task needs structured JSON output which this model does not support."
        d["selectable"] = disabled_reason is None
        d["disabled_reason"] = disabled_reason
        d["configured"] = m.provider in configured
        d["provider_label"] = PROVIDER_META[m.provider]["label"]
        out.append(d)
    return {"verified_at": SOURCES_VERIFIED_AT, "cloud_enabled": settings.ai_cloud_enabled, "byok_enabled": settings.ai_byok_enabled,
            "providers": {k: {"label": v["label"], "locality": v["locality"].value, "docs": v["docs"], "configured": k in configured}
                          for k, v in PROVIDER_META.items()},
            "models": out}


# ── preferences ──

@router.get("/preferences")
async def get_preferences(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = (await db.execute(select(AIPreferenceDB).where(AIPreferenceDB.scope_kind == "user", AIPreferenceDB.scope_id == user.user_id))).scalar_one_or_none()
    if not row:
        return PreferencesIn().model_dump() | {"effective_cloud": False}
    data = PreferencesIn(mode=row.mode, profile=row.profile, default_provider=row.default_provider, default_model=row.default_model,
                         per_task=row.per_task or {}, fallback_providers=row.fallback_providers or [], cloud_allowed=row.cloud_allowed,
                         max_data_class_cloud=row.max_data_class_cloud, detail_level=row.detail_level,
                         monthly_cap_micro_usd=row.monthly_cap_micro_usd, version=row.version).model_dump()
    data["effective_cloud"] = settings.ai_cloud_enabled and row.cloud_allowed
    return data


@router.put("/preferences")
async def put_preferences(body: PreferencesIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if body.mode == Mode.CHOOSE and not (body.default_provider and body.default_model):
        raise HTTPException(400, "Choose a default provider and model, or use Auto/Local only")
    if body.default_provider and body.default_model and not get_registry().get(body.default_provider, body.default_model):
        raise HTTPException(400, "Unknown model")
    if body.cloud_allowed and not settings.ai_cloud_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cloud processing is disabled on this deployment")
    row = (await db.execute(select(AIPreferenceDB).where(AIPreferenceDB.scope_kind == "user", AIPreferenceDB.scope_id == user.user_id))).scalar_one_or_none()
    if row and row.version != body.version:
        raise HTTPException(409, {"detail": "Preferences changed elsewhere; reload", "version": row.version})
    if not row:
        row = AIPreferenceDB(scope_kind="user", scope_id=user.user_id)
        db.add(row)
    for k in ("default_provider", "default_model", "per_task", "fallback_providers", "cloud_allowed", "detail_level", "monthly_cap_micro_usd"):
        setattr(row, k, getattr(body, k))
    row.mode, row.profile, row.max_data_class_cloud = body.mode.value, body.profile.value, body.max_data_class_cloud.value
    row.version = (row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    await db.commit()
    if body.monthly_cap_micro_usd is not None:
        await budget_mod.BudgetLedger(db, is_sqlite=_is_sqlite(db)).set_limit("user", user.user_id, body.monthly_cap_micro_usd)
    await audit(db, actor_from_user(user), "preferences.update", decision="allow", reason=f"mode={body.mode.value}")
    return {"success": True, "version": row.version}


# ── connections ──

@router.get("/connections")
async def list_connections(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    rows = await _visible_connections(db, user)
    out = [_conn_out(r, editable=_can_manage(user, r.owner_kind, r.owner_id)) for r in rows]
    for p in sorted(_PROVIDERS - {"ollama", "compat"}):
        if platform_credential(p).api_key and not any(r.provider == p and r.owner_kind == "platform" for r in rows):
            out.append({"id": f"env:{p}", "provider": p, "label": "Server-configured", "owner_kind": "platform", "secret_hint": None,
                        "status": "configured", "last_checked_at": None, "last_error": None, "endpoint_ref": None,
                        "editable": False, "billed_to": "Avira allowance"})
    return {"connections": out, "byok_enabled": settings.ai_byok_enabled, "compat_endpoints": sorted(compat_endpoints())}


@router.post("/connections", status_code=201)
async def create_connection(body: ConnectionIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    owner_id = {"user": user.user_id, "org": getattr(user, "tenant_id", None), "platform": "platform"}.get(body.owner_kind)
    if not owner_id or not _can_manage(user, body.owner_kind, owner_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You may not add this kind of connection")
    if body.provider == "compat":
        if not body.endpoint_ref or body.endpoint_ref not in compat_endpoints():
            raise HTTPException(400, "endpoint_ref must be an administrator-allowlisted endpoint name")
    if not settings.avira_vault_key:
        raise HTTPException(503, "AVIRA_VAULT_KEY is not configured; credentials cannot be stored")
    ct, hint, ver = encrypt_secret(body.api_key)
    row = AIConnectionDB(owner_kind=body.owner_kind, owner_id=owner_id, provider=body.provider, label=body.label,
                         endpoint_ref=body.endpoint_ref, secret_ciphertext=ct, secret_hint=hint, encryption_version=ver)
    db.add(row)
    await db.commit()
    await audit(db, actor_from_user(user), "connection.create", target=row.id, decision="allow", reason=body.provider)
    return _conn_out(row, editable=True)


async def _owned(db, user: UserDB, conn_id: str) -> AIConnectionDB:
    row = await db.get(AIConnectionDB, conn_id)
    if not row or row.status == "revoked" or not _can_manage(user, row.owner_kind, row.owner_id):
        raise HTTPException(404, "Connection not found")
    return row


@router.post("/connections/{conn_id}/test")
async def test_connection(conn_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    """Synthetic probe (model listing). May incur a negligible provider charge."""
    row = await _owned(db, user, conn_id)
    cred: ResolvedCredential = credential_from_row(row, funding="byok" if row.owner_kind == "user" else "platform")
    if row.provider == "compat":
        cred = ResolvedCredential(cred.provider, cred.api_key, cred.connection_id, cred.owner_kind, cred.funding, base_url=row.endpoint_ref)
    result = await adapter_for(row.provider).test_connection(cred)
    row.status = "ok" if result.get("ok") else "invalid"
    row.last_checked_at = datetime.utcnow()
    row.last_error = None if result.get("ok") else (result.get("detail") or "")[:200]
    await db.commit()
    await audit(db, actor_from_user(user), "connection.test", target=row.id, decision="allow" if result.get("ok") else "deny", reason=row.last_error)
    return {"ok": bool(result.get("ok")), "detail": result.get("detail"), "checked_at": row.last_checked_at.isoformat(),
            "models_visible": len(result.get("models") or [])}


class ReplaceIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=512)
    label: Optional[str] = Field(default=None, max_length=80)


@router.put("/connections/{conn_id}")
async def replace_connection(conn_id: str, body: ReplaceIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned(db, user, conn_id)
    row.secret_ciphertext, row.secret_hint, row.encryption_version = encrypt_secret(body.api_key)
    if body.label is not None:
        row.label = body.label
    row.status, row.last_error, row.updated_at = "untested", None, datetime.utcnow()
    await db.commit()
    await audit(db, actor_from_user(user), "connection.replace", target=row.id, decision="allow")
    return _conn_out(row, editable=True)


@router.delete("/connections/{conn_id}", status_code=204)
async def revoke_connection(conn_id: str, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    row = await _owned(db, user, conn_id)
    row.status, row.secret_ciphertext, row.secret_hint, row.revoked_at = "revoked", None, None, datetime.utcnow()
    await db.commit()
    from app.services import llm_client
    llm_client._response_cache.clear()   # a revoked key must not keep serving cached answers
    await audit(db, actor_from_user(user), "connection.revoke", target=row.id, decision="allow")
    return None


# ── usage / estimate ──

@router.get("/usage")
async def usage(period: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
                user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    actor = actor_from_user(user)
    ledger = budget_mod.BudgetLedger(db, is_sqlite=_is_sqlite(db))
    snap = await ledger.snapshot(actor, period)
    period = snap["period"]
    events = (await db.execute(select(AIUsageEventDB).where(AIUsageEventDB.user_id == user.user_id).order_by(AIUsageEventDB.created_at.desc()).limit(500))).scalars().all()
    by_task: dict[str, dict] = {}
    by_provider: dict[str, dict] = {}
    unknown = 0
    for e in events:
        if not e.created_at.strftime("%Y-%m") == period:
            continue
        amt = e.actual_micro_usd or 0
        if e.state == "settled" and e.actual_micro_usd is None:
            unknown += 1
        for bucket, key in ((by_task, e.task), (by_provider, f"{e.provider}:{e.model}")):
            b = bucket.setdefault(key, {"requests": 0, "micro_usd": 0, "funding": e.funding})
            b["requests"] += 1
            b["micro_usd"] += amt
    return {"period": period, "accounts": snap["accounts"], "by_task": by_task, "by_provider": by_provider,
            "requests_with_unknown_cost": unknown, "note": "Local models cost $0. Hosted costs are estimates until reconciled with provider invoices.",
            "resets_on": f"{period}-01 next month"}


@router.post("/estimate")
async def estimate(body: EstimateIn, user: UserDB = Depends(get_current_user)):
    spec = get_registry().get(body.provider, body.model)
    if not spec:
        raise HTTPException(404, "Unknown model")
    est = budget_mod.estimate_micro(spec, body.prompt_chars, body.max_output_tokens)
    return {"provider": body.provider, "model": body.model, "price_known": spec.price_known,
            "estimate_micro_usd": est, "note": None if spec.price_known else "No verified price; managed routing to this model is blocked."}


# ── admin ──

class CatalogRowIn(BaseModel):
    provider: str
    model_id: str
    display_name: Optional[str] = None
    enabled: bool = False
    lifecycle: str = "candidate"
    tier: Optional[str] = None
    price_micro_usd: Optional[dict[str, int]] = None
    price_version: Optional[str] = None
    source_url: Optional[str] = None
    notes: str = ""


@router.put("/admin/catalog", dependencies=[Depends(require_admin)])
async def admin_upsert_catalog(body: CatalogRowIn, admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    if body.provider not in _PROVIDERS:
        raise HTTPException(400, "unknown provider")
    row = (await db.execute(select(AIModelCatalogDB).where(AIModelCatalogDB.provider == body.provider, AIModelCatalogDB.model_id == body.model_id))).scalar_one_or_none()
    spec = get_registry().get(body.provider, body.model_id)
    if not row:
        row = AIModelCatalogDB(provider=body.provider, model_id=body.model_id, display_name=body.display_name or (spec.display_name if spec else body.model_id),
                               capabilities=sorted(c.value for c in spec.capabilities) if spec else ["text"])
        db.add(row)
    for k in ("enabled", "lifecycle", "price_micro_usd", "price_version", "source_url", "notes"):
        setattr(row, k, getattr(body, k))
    if body.display_name:
        row.display_name = body.display_name
    if body.tier:
        row.tier = body.tier
    row.verified_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    await db.commit()
    get_registry().apply_db_rows([row])
    await audit(db, actor_from_user(admin), "catalog.upsert", target=f"{body.provider}:{body.model_id}", decision="allow")
    return {"success": True}


# ── org policy + telemetry (R5) ──

class OrgPolicyIn(BaseModel):
    """Org-wide AI policy. Users can only narrow this, never widen it."""
    cloud_allowed: bool = False
    allowed_providers: Optional[list[str]] = None   # None = all permitted
    max_data_class_cloud: DataClass = DataClass.MASKED
    monthly_cap_micro_usd: Optional[int] = Field(default=None, ge=0)


@router.get("/admin/org-policy")
async def get_org_policy(admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    tenant = getattr(admin, "tenant_id", None) or "default"
    row = (await db.execute(select(AIPreferenceDB).where(
        AIPreferenceDB.scope_kind == "org", AIPreferenceDB.scope_id == tenant))).scalar_one_or_none()
    if not row:
        return {"tenant_id": tenant, "cloud_allowed": False, "allowed_providers": None,
                "max_data_class_cloud": DataClass.MASKED.value, "monthly_cap_micro_usd": None}
    return {"tenant_id": tenant, "cloud_allowed": row.cloud_allowed,
            "allowed_providers": (row.per_task or {}).get("__allowed_providers__"),
            "max_data_class_cloud": row.max_data_class_cloud,
            "monthly_cap_micro_usd": row.monthly_cap_micro_usd, "version": row.version}


@router.put("/admin/org-policy")
async def put_org_policy(body: OrgPolicyIn, admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    if body.cloud_allowed and not settings.ai_cloud_enabled:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cloud processing is disabled on this deployment")
    if body.allowed_providers is not None:
        bad = [p for p in body.allowed_providers if p not in _PROVIDERS]
        if bad:
            raise HTTPException(400, f"unknown providers: {', '.join(bad)}")
    tenant = getattr(admin, "tenant_id", None) or "default"
    row = (await db.execute(select(AIPreferenceDB).where(
        AIPreferenceDB.scope_kind == "org", AIPreferenceDB.scope_id == tenant))).scalar_one_or_none()
    if not row:
        row = AIPreferenceDB(scope_kind="org", scope_id=tenant)
        db.add(row)
    row.cloud_allowed = body.cloud_allowed
    row.max_data_class_cloud = body.max_data_class_cloud.value
    per_task = dict(row.per_task or {})
    if body.allowed_providers is not None:
        per_task["__allowed_providers__"] = body.allowed_providers
    else:
        per_task.pop("__allowed_providers__", None)
    row.per_task = per_task
    row.monthly_cap_micro_usd = body.monthly_cap_micro_usd
    row.version = (row.version or 0) + 1
    row.updated_at = datetime.utcnow()
    await db.commit()
    if body.monthly_cap_micro_usd is not None:
        await budget_mod.BudgetLedger(db, is_sqlite=_is_sqlite(db)).set_limit("org", tenant, body.monthly_cap_micro_usd)
    await audit(db, actor_from_user(admin), "org_policy.update", target=tenant, decision="allow",
                reason=f"cloud={body.cloud_allowed} providers={body.allowed_providers}")
    return {"success": True, "tenant_id": tenant, "version": row.version}


@router.get("/admin/metrics")
async def admin_metrics(admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    """Operational telemetry: request counters, latency, job queue, AI spend."""
    from app.services import telemetry, job_queue
    usage_rows = (await db.execute(
        select(AIUsageEventDB.state, AIUsageEventDB.provider)
    )).all()
    by_state: dict[str, int] = {}
    providers: set[str] = set()
    for st, prov in usage_rows:
        by_state[st] = by_state.get(st, 0) + 1
        providers.add(prov)
    return {
        "http": telemetry.snapshot(),
        "jobs": await job_queue.job_stats(),
        "ai_usage_events": {"total": len(usage_rows), "by_state": by_state, "providers_seen": sorted(providers)},
    }
