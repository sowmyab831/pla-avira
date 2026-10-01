"""
Subscription Gating Middleware

Use these dependencies to protect premium endpoints:
  - require_premium: blocks free-tier users
  - require_enterprise: blocks free + premium users
  - check_rate_limit: enforces per-tier rate limits
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserDB, get_session
from app.routes.auth import get_current_user

logger = logging.getLogger(__name__)

# In-memory rate limit store: {user_id: [(timestamp, endpoint), ...]}
_rate_store: Dict[str, list] = defaultdict(list)

# Tier limits per rolling 24-hour window
TIER_LIMITS = {
    "free": {
        "scan": 3,           # 3 stock scans per day
        "ai_chat": 10,      # 10 AI messages per day
        "alerts": 3,        # 3 price alerts max
        "documents": 5,     # 5 document scans per day
        "forecast": 1,      # 1 forecast per day
        "voice": 30,        # 30 voice/text multi-intent commands per day
        "radar_sync": 4,    # 4 inbox radar syncs per day
        "receipt": 5,       # 5 receipt scans per day
        "email_accounts": 1,
        "family_members": 3,
    },
    "premium": {
        "scan": -1,          # unlimited
        "ai_chat": -1,
        "alerts": 50,
        "documents": -1,
        "forecast": -1,
        "voice": -1,
        "radar_sync": 48,
        "receipt": -1,
        "email_accounts": 3,
        "family_members": 10,
    },
    "enterprise": {
        "scan": -1,
        "ai_chat": -1,
        "alerts": -1,
        "documents": -1,
        "forecast": -1,
        "voice": -1,
        "radar_sync": -1,
        "receipt": -1,
        "email_accounts": -1,
        "family_members": -1,
    },
}


def usage_snapshot(user: UserDB) -> Dict[str, Dict[str, int]]:
    """Rolling-24h usage vs limit for every rate-limited category."""
    tier = getattr(user, "subscription_tier", "free") or "free"
    is_admin = getattr(user, "role", "") == "admin"
    limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    now = time.time()
    out: Dict[str, Dict[str, int]] = {}
    for cat, limit in limits.items():
        if cat in ("email_accounts", "family_members"):
            continue
        bucket = f"{user.user_id}:{cat}"
        stamps = [t for t in _rate_store.get(bucket, []) if now - t < 86400]
        eff_limit = -1 if is_admin else limit
        out[cat] = {
            "used": len(stamps),
            "limit": eff_limit,
            "remaining": -1 if eff_limit == -1 else max(eff_limit - len(stamps), 0),
            "resets_in_seconds": int(86400 - (now - stamps[0])) if stamps else 0,
        }
    return out


def reset_usage(user_id: str) -> int:
    """Clear rolling counters for a user. Returns number of buckets cleared."""
    keys = [k for k in _rate_store if k.startswith(f"{user_id}:")]
    for k in keys:
        _rate_store.pop(k, None)
    return len(keys)


def tier_limit(user: UserDB, category: str) -> int:
    """Static (non-rolling) limit for a tier, e.g. max email accounts. -1 = unlimited."""
    if getattr(user, "role", "") == "admin":
        return -1
    tier = getattr(user, "subscription_tier", "free") or "free"
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(category, 0)


async def require_premium(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """Block access for free-tier users."""
    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    if tier not in ("premium", "enterprise", "admin"):
        if current_user.role == "admin":
            return current_user
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Premium subscription required",
                "current_tier": tier,
                "upgrade_url": "/subscription",
            }
        )
    return current_user


async def require_enterprise(current_user: UserDB = Depends(get_current_user)) -> UserDB:
    """Block access for non-enterprise users (admins allowed for testing/ops)."""
    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    if tier != "enterprise" and getattr(current_user, 'role', '') != 'admin':
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Enterprise subscription required",
                "current_tier": tier,
                "upgrade_url": "/subscription",
            }
        )
    return current_user


_optional_bearer = HTTPBearer(auto_error=False)


def soft_rate_limit(endpoint_category: str):
    """Tier-aware limit that also works for anonymous callers.

    Authenticated → per-user tier limit. Anonymous → free-tier limit keyed by
    client IP. Use on legacy endpoints the web UI calls without a token.
    """
    async def _check(request: Request,
                     credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
                     db: AsyncSession = Depends(get_session)):
        tier, key, is_admin = "free", f"ip:{request.client.host if request.client else 'unknown'}", False
        if credentials:
            try:
                user = await get_current_user(credentials, db)
                tier = getattr(user, "subscription_tier", "free") or "free"
                key = user.user_id
                is_admin = user.role == "admin"
            except HTTPException:
                pass
        if is_admin:
            return
        limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(endpoint_category, 10)
        if limit == -1:
            return
        now = time.time()
        bucket = f"{key}:{endpoint_category}"
        _rate_store[bucket] = [t for t in _rate_store[bucket] if now - t < 86400]
        if len(_rate_store[bucket]) >= limit:
            raise HTTPException(status_code=429, detail={
                "error": f"Daily limit reached: {limit} {endpoint_category} on {tier} tier",
                "current_tier": tier, "limit": limit, "upgrade_url": "/subscription",
                "resets_in_seconds": int(86400 - (now - _rate_store[bucket][0])),
            })
        _rate_store[bucket].append(now)

    return _check


def check_rate_limit(endpoint_category: str):
    """
    Returns a dependency that checks rate limits per tier.
    
    Usage:
        @router.get("/scan/{symbol}", dependencies=[Depends(check_rate_limit("scan"))])
        async def scan_stock(symbol: str, user: UserDB = Depends(get_current_user)):
            ...
    """
    async def _check(current_user: UserDB = Depends(get_current_user)):
        tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
        if current_user.role == "admin":
            return current_user

        limits = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
        limit = limits.get(endpoint_category, 10)

        if limit == -1:
            return current_user  # unlimited

        # Clean old entries (older than 24h)
        now = time.time()
        user_key = f"{current_user.user_id}:{endpoint_category}"
        _rate_store[user_key] = [t for t in _rate_store[user_key] if now - t < 86400]

        if len(_rate_store[user_key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": f"Rate limit exceeded: {limit} {endpoint_category} calls/day on {tier} tier",
                    "current_tier": tier,
                    "limit": limit,
                    "used": len(_rate_store[user_key]),
                    "upgrade_url": "/subscription",
                    "resets_in_seconds": int(86400 - (now - _rate_store[user_key][0])),
                }
            )

        _rate_store[user_key].append(now)
        return current_user

    return _check
