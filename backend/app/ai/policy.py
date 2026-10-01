"""Routing policy.

Precedence (hard limits first, then preferences):
  1. Deployment flags        (AVIRA_AI_CLOUD off → local only, always)
  2. Tenant/org policy       (allowed providers, cloud permission, data-class cap)
  3. User consent            (mode=local_only / cloud_allowed=false → local only)
  4. Data classification     (SENSITIVE never leaves unless explicitly allowed)
  5. Capability requirements (model must support what the task needs)
  6. Budget                  (checked later by budget.reserve — not here)
  ── then preferences ──
  7. Explicit request selection (conversation override)
  8. Per-task preference
  9. User default
 10. Auto profile (economy/balanced/quality) with deterministic rules
 11. Platform default (local)

Explicit choices are *pinned*: a provider failure never silently moves private
data to another provider unless the user opted into fallback and the candidate
is capability-compatible and permitted by the same hard limits.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.ai.registry import ModelSpec, Registry
from app.ai.schemas import AIError, AIRequest, Capability, DataClass, ErrorCode, Locality, Mode, Profile
from app.config import settings

_DATA_RANK = {DataClass.PUBLIC: 0, DataClass.MASKED: 1, DataClass.PERSONAL: 2, DataClass.SENSITIVE: 3}

# Deterministic auto-routing: task → profile. Arithmetic/scheduling never hits a model.
AUTO_TASK_PROFILE: dict[str, Profile] = {
    "fast": Profile.ECONOMY, "legacy": Profile.ECONOMY,
    "extract": Profile.ECONOMY, "classify": Profile.ECONOMY, "email": Profile.ECONOMY,
    "shopping": Profile.ECONOMY, "calendar": Profile.ECONOMY, "intent": Profile.ECONOMY,
    "assistant": Profile.BALANCED, "travel": Profile.BALANCED, "health": Profile.BALANCED,
    "finance": Profile.BALANCED, "stock": Profile.BALANCED, "analysis": Profile.BALANCED,
    "deep": Profile.QUALITY, "reasoning": Profile.QUALITY, "research": Profile.QUALITY,
}


@dataclass
class UserPolicy:
    """Effective preferences for one actor (user row merged over org row)."""
    mode: Mode = Mode.LOCAL_ONLY
    profile: Profile = Profile.BALANCED
    default_provider: Optional[str] = None
    default_model: Optional[str] = None
    per_task: dict[str, dict] = field(default_factory=dict)
    fallback_providers: list[str] = field(default_factory=list)
    cloud_allowed: bool = False
    max_data_class_cloud: DataClass = DataClass.MASKED
    # org-level
    org_allowed_providers: Optional[set[str]] = None   # None = all
    org_cloud_allowed: bool = True
    detail_level: str = "normal"


@dataclass
class Decision:
    primary: ModelSpec
    fallbacks: list[ModelSpec]
    local_only: bool
    mode: str
    reason: str
    pinned: bool


def _local_only(req: AIRequest, pol: UserPolicy) -> tuple[bool, str]:
    if not settings.ai_cloud_enabled:
        return True, "deployment:cloud_disabled"
    if not pol.org_cloud_allowed:
        return True, "org:cloud_denied"
    if pol.mode == Mode.LOCAL_ONLY or not pol.cloud_allowed:
        return True, "user:local_only"
    if _DATA_RANK[req.data_class] > _DATA_RANK[pol.max_data_class_cloud]:
        return True, f"data_class:{req.data_class.value}>{pol.max_data_class_cloud.value}"
    return False, "cloud_permitted"


def _allowed_providers(pol: UserPolicy, local_only: bool) -> set[str]:
    base = {"ollama"} if local_only else {"ollama", "openai", "anthropic", "gemini", "moonshot", "deepseek", "xai", "mistral", "compat"}
    if pol.org_allowed_providers is not None:
        base &= (pol.org_allowed_providers | {"ollama"})
    return base


def _check(spec: ModelSpec, req: AIRequest, reg: Registry, allowed: set[str], local_only: bool) -> None:
    if local_only and spec.locality != Locality.LOCAL:
        raise AIError(ErrorCode.CONSENT_REQUIRED, "Cloud processing is not enabled for this request",
                      provider=spec.provider, model=spec.model_id, http_status=403)
    if spec.provider not in allowed:
        raise AIError(ErrorCode.POLICY_DENIED, f"Provider '{spec.provider}' is not permitted by policy",
                      provider=spec.provider, model=spec.model_id, http_status=403)
    if spec.lifecycle not in ("active", "candidate"):
        raise AIError(ErrorCode.UNSUPPORTED_MODEL, f"Model '{spec.model_id}' is {spec.lifecycle}",
                      provider=spec.provider, model=spec.model_id)
    ok, missing = reg.supports(spec, req.required)
    if not ok:
        raise AIError(ErrorCode.CAPABILITY_MISSING,
                      f"Model '{spec.model_id}' lacks: {', '.join(sorted(c.value for c in missing))}",
                      provider=spec.provider, model=spec.model_id)
    if spec.provider == "ollama" and reg.local_installed(spec.model_id) is False:
        raise AIError(ErrorCode.LOCAL_MODEL_MISSING,
                      f"Local model '{spec.model_id}' is not installed. Install it explicitly with `ollama pull`.",
                      provider="ollama", model=spec.model_id, http_status=409)


def decide(req: AIRequest, pol: UserPolicy, reg: Registry) -> Decision:
    local_only, why = _local_only(req, pol)
    allowed = _allowed_providers(pol, local_only)
    sel = req.selection

    # 7. explicit request/conversation selection
    if sel.provider and sel.model:
        spec = reg.get(sel.provider, sel.model)
        if not spec:
            raise AIError(ErrorCode.UNSUPPORTED_MODEL, f"Unknown model {sel.provider}:{sel.model}",
                          provider=sel.provider, model=sel.model)
        _check(spec, req, reg, allowed, local_only)
        fb = _fallbacks(spec, req, pol, reg, allowed, local_only) if (sel.allow_fallback is True) else []
        return Decision(spec, fb, local_only, "choose", f"explicit:{why}", pinned=True)

    # 8. per-task preference
    task_pref = pol.per_task.get(req.task) or {}
    if task_pref.get("provider") and task_pref.get("model"):
        spec = reg.get(task_pref["provider"], task_pref["model"])
        if spec:
            try:
                _check(spec, req, reg, allowed, local_only)
                fb = _fallbacks(spec, req, pol, reg, allowed, local_only) if pol.fallback_providers else []
                return Decision(spec, fb, local_only, "choose", f"task_pref:{why}", pinned=True)
            except AIError:
                if pol.mode == Mode.CHOOSE:
                    raise

    # 9. user default (mode=choose)
    if pol.mode == Mode.CHOOSE and pol.default_provider and pol.default_model:
        spec = reg.get(pol.default_provider, pol.default_model)
        if not spec:
            raise AIError(ErrorCode.UNSUPPORTED_MODEL, "Your default model is no longer available",
                          provider=pol.default_provider, model=pol.default_model)
        _check(spec, req, reg, allowed, local_only)
        fb = _fallbacks(spec, req, pol, reg, allowed, local_only) if pol.fallback_providers else []
        return Decision(spec, fb, local_only, "choose", f"user_default:{why}", pinned=True)

    # 10. auto / local-only profile routing (task hint applies in both; explicit profile wins)
    profile = sel.profile or AUTO_TASK_PROFILE.get(req.task, pol.profile)
    if sel.profile is None and pol.profile == Profile.ECONOMY:
        profile = Profile.ECONOMY   # user asked for economy: never auto-escalate
    for candidate_profile in _profile_order(profile):
        spec = reg.profile_default(candidate_profile, local_only=local_only, allowed_providers=allowed)
        if spec:
            try:
                _check(spec, req, reg, allowed, local_only)
            except AIError:
                continue
            fb = _fallbacks(spec, req, pol, reg, allowed, local_only)
            mode = "local_only" if local_only else "auto"
            return Decision(spec, fb, local_only, mode, f"profile:{candidate_profile.value}:{why}", pinned=False)

    raise AIError(ErrorCode.LOCAL_MODEL_MISSING if local_only else ErrorCode.UNSUPPORTED_MODEL,
                  "No permitted model satisfies this request", http_status=409)


def _profile_order(p: Profile) -> list[Profile]:
    order = {Profile.ECONOMY: [Profile.ECONOMY, Profile.BALANCED, Profile.QUALITY],
             Profile.BALANCED: [Profile.BALANCED, Profile.ECONOMY, Profile.QUALITY],
             Profile.QUALITY: [Profile.QUALITY, Profile.BALANCED, Profile.ECONOMY]}
    return order[p]


def _fallbacks(primary: ModelSpec, req: AIRequest, pol: UserPolicy, reg: Registry,
               allowed: set[str], local_only: bool) -> list[ModelSpec]:
    """Capability-compatible, policy-permitted alternates. Local-only users only fall back locally."""
    out: list[ModelSpec] = []
    providers = ["ollama"] + [p for p in pol.fallback_providers if p != "ollama"]
    for prov in providers:
        if prov not in allowed:
            continue
        for spec in reg.for_provider(prov):
            if spec.key == primary.key or spec.lifecycle != "active":
                continue
            try:
                _check(spec, req, reg, allowed, local_only)
            except AIError:
                continue
            out.append(spec)
    # deterministic: same tier first, then cheaper
    out.sort(key=lambda s: (s.tier != primary.tier, s.input_micro_per_1m or 0))
    return out[:3]
