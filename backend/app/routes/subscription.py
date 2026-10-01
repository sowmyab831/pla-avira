"""
Subscription and Payment Management Routes
Stripe integration for premium features
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

import os

from app.database import get_session, UserDB
from app.routes.auth import get_current_user, require_admin
from app.middleware.subscription_gate import TIER_LIMITS, usage_snapshot, reset_usage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Test activation keys (no Stripe needed). Override via env for non-dev deployments.
# Format: AVIRA-<TIER>-<CODE>
TEST_ACTIVATION_KEYS = {
    value.strip().upper(): tier
    for tier in ("premium", "enterprise", "free")
    if (value := os.getenv(f"AVIRA_TEST_KEY_{tier.upper()}"))
} if os.getenv("AVIRA_ENABLE_ACTIVATION_KEYS", "false").lower() == "true" else {}
STRIPE_ENABLED = bool(os.getenv("STRIPE_SECRET_KEY"))

router = APIRouter(prefix="/api/subscription", tags=["subscription"])
logger = logging.getLogger(__name__)

# Subscription tiers
SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "price": 0,
        "price_annual": 0,
        "price_inr": 0,
        "price_inr_annual": 0,
        "features": {
            "ai_calls_per_day": 10,
            "stock_analysis": True,
            "basic_charts": True,
            "document_ocr": 5,
            "shopping_search": True,
            "travel_search": True,
            "markets": ["US"],
            "deep_metrics": False,
            "price_watches": 3,
            "maintenance_hub": "basic",   # home checklist only
            "family_members": 3,
        }
    },
    "premium": {
        "name": "Premium",
        "price": 9.99,
        "price_annual": 99.0,          # ~2 months free
        "price_inr": 499,
        "price_inr_annual": 4999,
        "price_id": "price_premium_monthly",
        "features": {
            "ai_calls_per_day": -1,  # Unlimited (fair use)
            "stock_analysis": True,
            "advanced_charts": True,
            "elliott_wave": True,
            "document_ocr": -1,  # Unlimited
            "shopping_search": True,
            "travel_search": True,
            "priority_support": True,
            "markets": ["US", "IN"],
            "deep_metrics": True,
            "options_metrics": True,
            "price_watches": -1,
            "price_drop_alerts": True,
            "maintenance_hub": "full",   # home + vehicle + appliances + alerts
            "family_members": 10,
        }
    },
    "enterprise": {
        "name": "Family / Enterprise",
        "price": 19.99,
        "price_annual": 199.0,
        "price_inr": 999,
        "price_inr_annual": 9999,
        "price_id": "price_enterprise_monthly",
        "features": {
            "ai_calls_per_day": -1,
            "stock_analysis": True,
            "advanced_charts": True,
            "elliott_wave": True,
            "document_ocr": -1,
            "shopping_search": True,
            "travel_search": True,
            "priority_support": True,
            "markets": ["US", "IN"],
            "deep_metrics": True,
            "options_metrics": True,
            "price_watches": -1,
            "price_drop_alerts": True,
            "maintenance_hub": "full",
            "multi_user": True,
            "family_members": -1,
            "family_oversight": True,
            "api_access": True,
            "custom_integrations": True,
        }
    }
}


class SubscriptionStatus(BaseModel):
    tier: str
    status: str
    features: dict
    expires_at: Optional[str] = None
    stripe_subscription_id: Optional[str] = None


@router.get("/tiers")
async def get_subscription_tiers():
    """Get available subscription tiers and pricing."""
    return {
        "success": True,
        "tiers": SUBSCRIPTION_TIERS
    }


@router.get("/status")
async def get_subscription_status(
    current_user: UserDB = Depends(get_current_user)
):
    """Get current user's subscription status."""
    user_tier = current_user.subscription_tier or 'free'
    
    return {
        "tier": user_tier,
        "status": "active",
        "role": current_user.role,
        "features": SUBSCRIPTION_TIERS.get(user_tier, SUBSCRIPTION_TIERS["free"])["features"],
        "limits": TIER_LIMITS.get(user_tier, TIER_LIMITS["free"]),
        "expires_at": None,
        "stripe_subscription_id": current_user.stripe_subscription_id,
        "payments": "stripe" if STRIPE_ENABLED else "activation_key",
    }


@router.post("/create-checkout-session")
async def create_checkout_session(tier: str, country: str = "US", current_user: UserDB = Depends(get_current_user),
                                  db: AsyncSession = Depends(get_session)):
    from app.routes.billing import checkout, CheckoutIn
    if tier not in ("premium", "enterprise") or country not in ("US", "IN"):
        raise HTTPException(400, "Invalid market or plan")
    return await checkout(CheckoutIn(tier=tier, country=country), current_user, db)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_session)):
    from app.routes.billing import webhook
    return await webhook("stripe", request, db)


@router.post("/cancel")
async def cancel_subscription(current_user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    from app.routes.billing import cancel
    return await cancel(current_user, db)


@router.get("/usage")
async def get_usage_stats(
    current_user: UserDB = Depends(get_current_user)
):
    """Get user's API usage statistics for current billing period."""
    # In production, this would track:
    # - AI calls made
    # - Documents processed
    # - API requests
    # - Storage used
    
    tier = getattr(current_user, 'subscription_tier', 'free') or 'free'
    return {
        "success": True,
        "user_id": current_user.user_id,
        "tier": tier,
        "role": current_user.role,
        "window": "rolling 24h",
        "usage": usage_snapshot(current_user),
        "static_limits": {k: TIER_LIMITS.get(tier, TIER_LIMITS["free"])[k] for k in ("email_accounts", "family_members")},
    }


class ActivateRequest(BaseModel):
    key: str


@router.post("/activate")
async def activate_with_key(
    body: ActivateRequest,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Redeem an activation key to change tier (used for testing / offline sales)."""
    key = body.key.strip().upper()
    tier = TEST_ACTIVATION_KEYS.get(key)
    if not tier:
        raise HTTPException(status_code=400, detail="That activation key isn't valid.")
    user = await db.get(UserDB, current_user.user_id)
    user.subscription_tier = tier
    user.updated_at = datetime.utcnow()
    await db.commit()
    reset_usage(user.user_id)
    logger.info(f"Activation key redeemed by {user.username} -> {tier}")
    return {"success": True, "tier": tier, "message": f"You're on {SUBSCRIPTION_TIERS[tier]['name']} now."}


# ── Admin ────────────────────────────────────────────────────────────────────

@router.get("/admin/users")
async def admin_list_users(admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    res = await db.execute(select(UserDB).order_by(UserDB.created_at.desc()))
    users = res.scalars().all()
    return {
        "success": True,
        "count": len(users),
        "users": [
            {
                "user_id": u.user_id, "username": u.username, "email": u.email, "role": u.role,
                "is_active": u.is_active, "tier": u.subscription_tier or "free",
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "usage": usage_snapshot(u),
            }
            for u in users
        ],
        "tiers": list(SUBSCRIPTION_TIERS.keys()),
        "limits": TIER_LIMITS,
        "activation_keys": {v: k for k, v in TEST_ACTIVATION_KEYS.items()},
    }


class TierUpdate(BaseModel):
    tier: str


@router.patch("/admin/users/{user_id}/tier")
async def admin_set_tier(user_id: str, body: TierUpdate, admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    if body.tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(400, "Invalid tier")
    user = await db.get(UserDB, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.subscription_tier = body.tier
    user.updated_at = datetime.utcnow()
    await db.commit()
    reset_usage(user_id)
    logger.info(f"Admin {admin.username} set {user.username} -> {body.tier}")
    return {"success": True, "user_id": user_id, "tier": body.tier}


@router.post("/admin/users/{user_id}/reset-usage")
async def admin_reset_usage(user_id: str, admin: UserDB = Depends(require_admin)):
    return {"success": True, "buckets_cleared": reset_usage(user_id)}


class AdminUserCreate(BaseModel):
    username: str
    email: str
    password: str
    tier: str = "free"
    role: str = "user"


@router.post("/admin/users")
async def admin_create_user(body: AdminUserCreate, admin: UserDB = Depends(require_admin), db: AsyncSession = Depends(get_session)):
    from app.routes.auth import hash_password
    import uuid
    if body.tier not in SUBSCRIPTION_TIERS or body.role not in ("admin", "user"):
        raise HTTPException(400, "Invalid tier or role")
    exists = await db.execute(select(UserDB).where((UserDB.username == body.username) | (UserDB.email == body.email)))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "Username or email already exists")
    u = UserDB(user_id=f"user_{uuid.uuid4().hex[:12]}", username=body.username, email=body.email,
               password_hash=hash_password(body.password), role=body.role, is_active=True, subscription_tier=body.tier)
    db.add(u)
    await db.commit()
    return {"success": True, "user_id": u.user_id, "username": u.username, "tier": u.subscription_tier, "role": u.role}


@router.post("/upgrade")
async def upgrade_subscription(
    tier: str,
    current_user: UserDB = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Self-service tier change. Only admins may do this directly; others must pay or redeem a key."""
    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(status_code=400, detail="Invalid tier")
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail={"error": "Use /api/subscription/activate with a key, or ask an admin.", "upgrade_url": "/subscription"})
    user = await db.get(UserDB, current_user.user_id)
    user.subscription_tier = tier
    await db.commit()
    logger.info(f"Upgraded {current_user.username} to {tier} tier")
    return {"success": True, "message": f"Upgraded to {tier} tier", "tier": tier, "features": SUBSCRIPTION_TIERS[tier]["features"]}
