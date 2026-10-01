"""Authenticated checkout and signature-verified, reconciled entitlements."""
from datetime import datetime
from typing import Literal
import uuid
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session, UserDB
from app.models.life_admin import BillingAccountDB, BillingEventDB
from app.routes.auth import get_current_user
from app.services import billing

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutIn(BaseModel):
    country: Literal["US", "IN"]
    tier: Literal["premium", "enterprise"]


@router.get("/catalog")
async def catalog():
    return {"markets": {country: {"currency": billing.CURRENCIES[country], "provider": provider,
            "plans": [{"tier": tier, "amount_minor": amount, "interval": "month",
                       "enabled": billing.readiness(country, tier)} for tier, amount in billing.PRICES[country].items()]}
            for country, provider in billing.PROVIDERS.items()},
            "note": "Provider checkout confirms taxes and eligible payment methods. India mandates run for up to 120 monthly cycles."}


@router.get("/status")
async def status(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.user_id == user.user_id))).scalar_one_or_none()
    return {"tier": user.subscription_tier or "free", "billing": None if not account else {
        "provider": account.provider, "country": account.country, "status": account.status,
        "tier": account.tier, "updated_at": account.updated_at.isoformat()}}


@router.post("/checkout")
async def checkout(body: CheckoutIn, user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    if not billing.readiness(body.country, body.tier):
        raise HTTPException(503, "Payments are not configured for this market and plan. No charge was created.")
    # The user row lock also serializes the first checkout before an account exists.
    await db.execute(select(UserDB).where(UserDB.user_id == user.user_id).with_for_update())
    account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.user_id == user.user_id).with_for_update())).scalar_one_or_none()
    if account:
        if account.status == "checkout_pending" and account.country == body.country and account.tier == body.tier:
            return {"checkout_url": account.checkout_url, "provider": account.provider}
        raise HTTPException(409, "A billing record already exists. Manage the current subscription before starting another checkout.")
    account = BillingAccountDB(id=str(uuid.uuid4()), user_id=user.user_id, provider=billing.PROVIDERS[body.country],
                               country=body.country, tier=body.tier, status="creating")
    db.add(account)
    # Persist the request before calling a provider; an ambiguous failure must not create duplicate charges on retry.
    await db.commit()
    try:
        checkout_id, provider_id, url = await billing.create_checkout(account)
        if not billing.checkout_url_allowed(url, account.provider):
            raise ValueError("Provider returned an unexpected checkout destination")
        account.checkout_id, account.provider_id, account.checkout_url = checkout_id, provider_id, url
        account.status, account.updated_at = "checkout_pending", datetime.utcnow()
        await db.commit()
        return {"checkout_url": url, "provider": account.provider}
    except (billing.BillingUnavailable, ValueError) as error:
        account.status = "needs_review"
        await db.commit()
        raise HTTPException(503, str(error))
    except (httpx.HTTPError, KeyError):
        account.status = "needs_review"
        await db.commit()
        raise HTTPException(502, "Payment provider did not confirm checkout. Contact support before retrying.")


async def reconcile(db, account, provider_id=None):
    snapshot = await billing.subscription_snapshot(account, provider_id)
    account.provider_id = snapshot["id"]
    account.status = snapshot["status"]
    account.updated_at = datetime.utcnow()
    user = await db.get(UserDB, account.user_id)
    if user is None:
        raise ValueError("Account owner no longer exists")
    # A signed event alone is insufficient: current provider state and plan must match.
    user.subscription_tier = account.tier if snapshot["status"] == "active" else "free"
    if account.provider == "stripe":
        user.stripe_subscription_id = account.provider_id
    return snapshot


@router.post("/webhook/{provider}")
async def webhook(provider: Literal["stripe", "razorpay"], request: Request, db: AsyncSession = Depends(get_session)):
    body = await request.body()
    if len(body) > 1_000_000:
        raise HTTPException(413, "Payload too large")
    signature = request.headers.get("stripe-signature" if provider == "stripe" else "x-razorpay-signature", "")
    try:
        event = billing.verify_webhook(provider, body, signature)
    except billing.BillingUnavailable as e:
        raise HTTPException(503, str(e))
    except (ValueError, TypeError):
        raise HTTPException(400, "Invalid webhook")
    event_id = event.get("id") if provider == "stripe" else request.headers.get("x-razorpay-event-id")
    if not isinstance(event_id, str) or not event_id or len(event_id) > 255:
        raise HTTPException(400, "Missing event identifier")
    if provider == "stripe":
        obj = event.get("data", {}).get("object", {})
        event_type = event.get("type", "")
        if event_type == "checkout.session.completed":
            account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.checkout_id == obj.get("id"),
                              BillingAccountDB.provider == provider).with_for_update())).scalar_one_or_none()
            sub_id = obj.get("subscription")
        elif event_type.startswith("customer.subscription."):
            account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.id == (obj.get("metadata") or {}).get("avira_billing_id"),
                              BillingAccountDB.provider == provider).with_for_update())).scalar_one_or_none()
            sub_id = obj.get("id")
        else:
            return {"received": True, "ignored": True}
    else:
        if not str(event.get("event", "")).startswith("subscription."):
            return {"received": True, "ignored": True}
        obj = event.get("payload", {}).get("subscription", {}).get("entity", {})
        account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.provider_id == obj.get("id"),
                          BillingAccountDB.provider == provider).with_for_update())).scalar_one_or_none()
        sub_id = obj.get("id")
    if account is None:
        # Retry: the provider can deliver before checkout persistence finishes.
        raise HTTPException(409, "Billing record not ready for this event")
    duplicate = (await db.execute(select(BillingEventDB).where(BillingEventDB.provider == provider,
                                 BillingEventDB.event_id == event_id))).scalar_one_or_none()
    if duplicate:
        return {"received": True, "duplicate": True}
    if account.provider_id and account.provider_id != sub_id:
        raise HTTPException(400, "Subscription mismatch")
    try:
        await reconcile(db, account, sub_id)
    except (ValueError, KeyError):
        raise HTTPException(400, "Subscription verification failed")
    except httpx.HTTPError:
        raise HTTPException(503, "Provider verification temporarily unavailable")
    db.add(BillingEventDB(provider=provider, event_id=event_id))
    await db.commit()
    return {"received": True}


@router.post("/cancel")
async def cancel(user: UserDB = Depends(get_current_user), db: AsyncSession = Depends(get_session)):
    account = (await db.execute(select(BillingAccountDB).where(BillingAccountDB.user_id == user.user_id).with_for_update())).scalar_one_or_none()
    if not account or not account.provider_id:
        raise HTTPException(409, "No provider subscription is linked. Contact support for an incomplete checkout.")
    try:
        await billing.subscription_snapshot(account)
        if account.provider == "stripe":
            await billing.request("stripe", "POST", f"/subscriptions/{account.provider_id}",
                                  data={"cancel_at_period_end": "true"}, key=f"cancel-{account.id}")
        else:
            await billing.request("razorpay", "POST", f"/subscriptions/{account.provider_id}/cancel", data={"cancel_at_cycle_end": True})
        await reconcile(db, account)
        await db.commit()
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(502, "Cancellation was not confirmed. Check your provider or contact support.")
    return {"success": True, "message": "Provider confirmed cancellation at the end of the current billing period."}
