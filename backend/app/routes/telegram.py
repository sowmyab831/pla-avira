"""
Telegram API Routes
───────────────────
Lets the frontend manage the Telegram bot: check status, bind a chat,
toggle features (day-trade tips, email alerts, etc.), send a test message,
trigger on-demand tips, and (optionally) receive updates via webhook.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.database import UserDB
from app.routes.auth import get_current_user
from app.services import telegram_service, telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class FeatureUpdate(BaseModel):
    day_trade_tips: Optional[bool] = None
    email_alerts: Optional[bool] = None
    price_alerts: Optional[bool] = None
    trade_exits: Optional[bool] = None
    tips_min_confidence: Optional[int] = None


class BindRequest(BaseModel):
    chat_id: str


@router.get("/status")
async def status():
    """Bot configuration + feature toggle status."""
    return {"success": True, **telegram_service.get_config()}


@router.put("/features")
async def update_features(body: FeatureUpdate):
    """Enable/disable outbound features and set tip confidence threshold."""
    feats = {k: v for k, v in body.dict().items() if v is not None and k != "tips_min_confidence"}
    if feats:
        telegram_service.update_features(feats)
    if body.tips_min_confidence is not None:
        telegram_service.set_tips_min_confidence(body.tips_min_confidence)
    return {"success": True, **telegram_service.get_config()}


@router.post("/bind")
async def bind(body: BindRequest, current_user: UserDB = Depends(get_current_user)):
    """Manually bind a chat id (alternative to messaging the bot /start)."""
    cfg = telegram_service.bind_chat(body.chat_id)
    # Also persist in the user-centric notification preferences
    from app.services.notification_service import update_notification_prefs
    update_notification_prefs(
        current_user.user_id,
        {"telegram_enabled": True, "telegram_chat_id": body.chat_id}
    )
    return {"success": True, **cfg}


@router.post("/test")
async def test():
    """Send a test message to the bound chat."""
    if not telegram_service.is_configured():
        raise HTTPException(400, "Telegram not configured. Set TELEGRAM_BOT_TOKEN.")
    if not telegram_service.get_bound_chat_id():
        raise HTTPException(400, "No chat bound. Message the bot and send /start, or use /bind.")
    result = await telegram_service.test_message()
    if not result.get("ok"):
        raise HTTPException(400, result.get("error") or result.get("description") or "Send failed")
    return {"success": True}


@router.post("/tips/send")
async def send_tips_now():
    """Push current day-trade tips to the bound chat on demand."""
    if not telegram_service.get_bound_chat_id():
        raise HTTPException(400, "No chat bound yet.")
    from app.services.day_trading_scanner import auto_scan_and_trade
    cfg = telegram_service.get_config()
    min_conf = cfg.get("tips_min_confidence", 65)
    scan = await auto_scan_and_trade(auto_execute=False, min_confidence=min_conf)
    msg = telegram_bot.format_tips(scan, min_conf) or "No high-confidence setups right now."
    sent = await telegram_service.send_message(msg)
    return {"success": bool(sent.get("ok")), "preview": msg}


@router.post("/webhook")
async def webhook(request: Request):
    """Optional inbound webhook (alternative to long-polling).

    Set it with Telegram's setWebhook pointing here, passing `secret_token`
    equal to TELEGRAM_WEBHOOK_SECRET. When that env var is configured,
    requests without the matching X-Telegram-Bot-Api-Secret-Token header are
    rejected so the endpoint can't be fed forged updates.
    """
    import secrets as _secrets
    from app.config import settings as _settings
    expected = _settings.telegram_webhook_secret
    if expected:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not _secrets.compare_digest(supplied, expected):
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}
    await telegram_bot.handle_update(update)
    return {"ok": True}
