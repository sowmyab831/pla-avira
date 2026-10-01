"""AI gateway persistence: connections, catalog, preferences, budgets, usage, audit.

Additive tables only. No raw credential is ever stored — only a Fernet
ciphertext plus the wrapping-key version used to produce it.
"""
import uuid
from datetime import datetime

from sqlalchemy import (JSON, BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text,
                        UniqueConstraint)

from app.database import Base


def new_id():
    return str(uuid.uuid4())


class AIConnectionDB(Base):
    """A credential/endpoint the platform, an organization, or a user owns."""
    __tablename__ = "ai_connections"
    id = Column(String, primary_key=True, default=new_id)
    owner_kind = Column(String, nullable=False)              # platform | org | user
    owner_id = Column(String, nullable=False, index=True)    # "platform" | org id | user id
    provider = Column(String, nullable=False)
    label = Column(String(80), nullable=False, default="")
    endpoint_ref = Column(String, nullable=True)             # allowlisted endpoint name (compat) or null
    secret_ciphertext = Column(Text, nullable=True)          # Fernet; null for env-backed connections
    secret_hint = Column(String(12), nullable=True)          # last 4 chars, display only
    encryption_version = Column(String, nullable=False, default="v1")
    status = Column(String, nullable=False, default="untested")  # untested | ok | invalid | revoked
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(String(200), nullable=True)          # sanitized
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)
    __table_args__ = (Index("ix_ai_conn_owner_provider", "owner_kind", "owner_id", "provider"),)


class AIModelCatalogDB(Base):
    """Admin-maintained catalog. Discovery endpoints never add rows automatically."""
    __tablename__ = "ai_model_catalog"
    __table_args__ = (UniqueConstraint("provider", "model_id"),)
    id = Column(String, primary_key=True, default=new_id)
    provider = Column(String, nullable=False, index=True)
    model_id = Column(String, nullable=False)
    display_name = Column(String(120), nullable=False)
    capabilities = Column(JSON, nullable=False, default=list)
    lifecycle = Column(String, nullable=False, default="candidate")  # candidate | active | deprecated | retired
    tier = Column(String, nullable=False, default="balanced")        # economy | balanced | quality
    context_window = Column(Integer, nullable=True)
    source_url = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    price_version = Column(String, nullable=True)
    price_micro_usd = Column(JSON, nullable=True)   # {"input_per_1m":..., "output_per_1m":..., "cached_input_per_1m":...}
    enabled = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AIPreferenceDB(Base):
    __tablename__ = "ai_preferences"
    __table_args__ = (UniqueConstraint("scope_kind", "scope_id"),)
    id = Column(String, primary_key=True, default=new_id)
    scope_kind = Column(String, nullable=False)   # user | org
    scope_id = Column(String, nullable=False, index=True)
    mode = Column(String, nullable=False, default="local_only")
    profile = Column(String, nullable=False, default="balanced")
    default_provider = Column(String, nullable=True)
    default_model = Column(String, nullable=True)
    per_task = Column(JSON, nullable=False, default=dict)          # {"finance": {"provider":..,"model":..}}
    fallback_providers = Column(JSON, nullable=False, default=list)
    cloud_allowed = Column(Boolean, nullable=False, default=False)
    max_data_class_cloud = Column(String, nullable=False, default="masked")
    detail_level = Column(String, nullable=False, default="normal")
    monthly_cap_micro_usd = Column(BigInteger, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AIBudgetAccountDB(Base):
    """One row per (scope, period). Integer micro-USD; never floats."""
    __tablename__ = "ai_budget_accounts"
    __table_args__ = (UniqueConstraint("scope_kind", "scope_id", "period", "funding"),)
    id = Column(String, primary_key=True, default=new_id)
    scope_kind = Column(String, nullable=False)   # user | org | platform
    scope_id = Column(String, nullable=False, index=True)
    funding = Column(String, nullable=False, default="platform")   # platform | byok
    period = Column(String, nullable=False)                        # YYYY-MM
    limit_micro_usd = Column(BigInteger, nullable=True)            # null = unlimited (byok estimate only)
    reserved_micro_usd = Column(BigInteger, nullable=False, default=0)
    spent_micro_usd = Column(BigInteger, nullable=False, default=0)
    pending_micro_usd = Column(BigInteger, nullable=False, default=0)  # ambiguous/unreconciled
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AIUsageEventDB(Base):
    __tablename__ = "ai_usage_events"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id = Column(String, primary_key=True, default=new_id)
    request_id = Column(String, nullable=False, index=True)
    idempotency_key = Column(String, nullable=False)
    user_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True, index=True)
    task = Column(String, nullable=False)
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    locality = Column(String, nullable=False)
    funding = Column(String, nullable=False, default="platform")
    connection_id = Column(String, nullable=True)
    state = Column(String, nullable=False, default="reserved")  # reserved | settled | pending | released | failed
    reserved_micro_usd = Column(BigInteger, nullable=False, default=0)
    actual_micro_usd = Column(BigInteger, nullable=True)
    price_version = Column(String, nullable=True)
    usage = Column(JSON, nullable=False, default=dict)
    provider_request_id = Column(String, nullable=True)
    fallback_from = Column(String, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    settled_at = Column(DateTime, nullable=True)


class AIAuditEventDB(Base):
    """Policy decisions and connection lifecycle. No prompt bodies, no keys."""
    __tablename__ = "ai_audit_events"
    id = Column(String, primary_key=True, default=new_id)
    actor_id = Column(String, nullable=False, index=True)
    tenant_id = Column(String, nullable=True)
    action = Column(String, nullable=False)          # connection.create | connection.test | policy.deny | ...
    target = Column(String, nullable=True)           # connection id / provider:model
    decision = Column(String, nullable=True)         # allow | deny
    reason = Column(String(200), nullable=True)
    request_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
