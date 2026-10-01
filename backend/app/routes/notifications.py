"""
Notification API Routes
───────────────────────
Consent-based notification system. Nothing sends without explicit user approval.
"""
from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import UserDB
from app.routes.auth import get_current_user, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationPrefsUpdate(BaseModel):
    whatsapp_enabled: Optional[bool] = None
    whatsapp_number: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    telegram_chat_id: Optional[str] = None
    email_enabled: Optional[bool] = None
    email_address: Optional[str] = None
    push_enabled: Optional[bool] = None
    push_token: Optional[str] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    categories: Optional[dict] = None


class QueueNotificationRequest(BaseModel):
    category: str  # earnings_alerts, price_alerts, action_items, calendar_reminders
    title: str
    message: str
    channels: Optional[List[str]] = None  # whatsapp, email, push, in_app


class DigestRequest(BaseModel):
    earnings_days: int = 14
    watchlist: Optional[List[str]] = None  # optional custom symbol list
    channels: Optional[List[str]] = None
    auto_send: bool = False  # if True AND a channel is configured, send immediately


@router.get("/preferences")
async def get_preferences(current_user: UserDB = Depends(get_current_user)):
    """Get notification preferences for current user."""
    from app.services.notification_service import get_notification_prefs
    prefs = get_notification_prefs(current_user.user_id)
    return {"success": True, "preferences": prefs}


@router.put("/preferences")
async def update_preferences(
    body: NotificationPrefsUpdate,
    current_user: UserDB = Depends(get_current_user),
):
    """Update notification preferences. Explicit opt-in required for each channel."""
    from app.services.notification_service import update_notification_prefs
    updates = {k: v for k, v in body.dict().items() if v is not None}
    prefs = update_notification_prefs(current_user.user_id, updates)
    return {"success": True, "preferences": prefs}


@router.get("/pending")
async def get_pending(current_user: UserDB = Depends(get_current_user)):
    """Get notifications awaiting user approval."""
    from app.services.notification_service import get_pending_notifications
    pending = get_pending_notifications(current_user.user_id)
    return {"success": True, "count": len(pending), "pending": pending}


@router.post("/queue")
async def queue_notification(
    body: QueueNotificationRequest,
    current_user: UserDB = Depends(get_current_user),
):
    """
    Queue a notification for user approval.
    Nothing is sent until POST /approve/{approval_id} is called.
    """
    from app.services.notification_service import queue_notification as _queue
    result = _queue(
        user_id=current_user.user_id,
        category=body.category,
        title=body.title,
        message=body.message,
        channels=body.channels,
    )
    return {"success": True, **result}


@router.post("/approve/{approval_id}")
async def approve_notification(
    approval_id: str,
    current_user: UserDB = Depends(get_current_user),
):
    """Explicitly approve and send a queued notification."""
    from app.services.notification_service import approve_and_send
    result = await approve_and_send(approval_id, current_user.user_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Failed to send"))
    return result


@router.post("/reject/{approval_id}")
async def reject_notification(
    approval_id: str,
    current_user: UserDB = Depends(get_current_user),
):
    """Reject a queued notification (will not be sent)."""
    from app.services.notification_service import reject_notification
    result = reject_notification(approval_id, current_user.user_id)
    return result


@router.get("/log")
async def notification_log(
    limit: int = 50,
    current_user: UserDB = Depends(require_admin),
):
    """Get notification audit log."""
    from app.services.notification_service import get_notification_log
    log = get_notification_log(limit)
    return {"success": True, "count": len(log), "log": log}


@router.post("/test/whatsapp")
async def test_whatsapp(
    current_user: UserDB = Depends(get_current_user),
):
    """
    Send a test WhatsApp message to verify configuration.
    Requires whatsapp_enabled=true and whatsapp_number set in preferences.
    """
    from app.services.notification_service import get_notification_prefs, send_whatsapp
    prefs = get_notification_prefs(current_user.user_id)
    if not prefs.get("whatsapp_enabled") or not prefs.get("whatsapp_number"):
        raise HTTPException(400, "WhatsApp not enabled or number not set. Update preferences first.")
    result = await send_whatsapp(
        prefs["whatsapp_number"],
        "✅ Avira WhatsApp integration is working! You'll receive alerts here."
    )
    return result


@router.post("/test/email")
async def test_email(
    current_user: UserDB = Depends(get_current_user),
):
    """Send a test email to verify configuration."""
    from app.services.notification_service import get_notification_prefs, send_email
    prefs = get_notification_prefs(current_user.user_id)
    if not prefs.get("email_enabled") or not prefs.get("email_address"):
        raise HTTPException(400, "Email not enabled or address not set. Update preferences first.")
    result = await send_email(
        prefs["email_address"],
        "Avira Test Notification",
        "✅ Avira email notifications are working! You'll receive alerts here."
    )
    return result


@router.post("/test/telegram")
async def test_telegram(
    current_user: UserDB = Depends(get_current_user),
):
    """Send a test Telegram message to verify the channel is working.

    Telegram is free — you only need a bot token (from @BotFather) and a
    bound chat. No paid WhatsApp/Twilio credits required.
    """
    from app.services.notification_service import get_notification_prefs, send_telegram
    prefs = get_notification_prefs(current_user.user_id)
    if not prefs.get("telegram_enabled"):
        raise HTTPException(400, "Telegram not enabled. Update notification preferences first.")
    chat_id = prefs.get("telegram_chat_id")
    if not chat_id:
        raise HTTPException(400, "No Telegram chat bound. Message your bot and send /start, then update preferences or use /api/telegram/bind.")
    result = await send_telegram(
        "✅ *Avira Telegram notifications are working.*\n\nThis is a test from your Avira app. You'll receive alerts here.\n\n_Research, not financial advice._",
        chat_id=chat_id,
    )
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Send failed"))
    return result


# ── Market / Earnings Digest ─────────────────────────────────────────────────

@router.get("/digest/preview")
async def digest_preview(
    earnings_days: int = 14,
    current_user: UserDB = Depends(get_current_user),
):
    """
    Build and return a market + earnings digest WITHOUT sending.
    Lets the user review before opting to deliver via WhatsApp/email.
    """
    from app.services.market_digest import build_market_digest
    digest = await build_market_digest(earnings_days=earnings_days)
    return {"success": True, **digest}


@router.post("/digest/send")
async def digest_send(
    body: DigestRequest,
    current_user: UserDB = Depends(get_current_user),
):
    """
    Build a market/earnings digest and queue it for delivery.

    Governance: by default this only QUEUES the digest (pending approval).
    Set auto_send=true to deliver immediately to configured channels —
    this still requires the user to have explicitly opted into a channel.
    """
    from app.services.market_digest import (
        build_market_digest,
        build_earnings_watchlist_digest,
    )
    from app.services.notification_service import (
        queue_notification,
        approve_and_send,
        get_notification_prefs,
    )

    if body.watchlist:
        digest = await build_earnings_watchlist_digest(body.watchlist, days=body.earnings_days)
    else:
        digest = await build_market_digest(earnings_days=body.earnings_days)

    queued = queue_notification(
        user_id=current_user.user_id,
        category="market_alerts",
        title=digest["title"],
        message=digest["message"],
        channels=body.channels,
    )

    if body.auto_send:
        prefs = get_notification_prefs(current_user.user_id)
        has_channel = (
            prefs.get("whatsapp_enabled") or
            prefs.get("telegram_enabled") or
            prefs.get("email_enabled") or
            prefs.get("push_enabled")
        )
        if not has_channel:
            raise HTTPException(
                400,
                "auto_send requested but no channel configured. "
                "Enable Telegram, WhatsApp, email or push in preferences first.",
            )
        sent = await approve_and_send(queued["approval_id"], current_user.user_id)
        return {"success": True, "digest": digest, "queued": queued, "sent": sent}

    return {"success": True, "digest": digest, "queued": queued}
