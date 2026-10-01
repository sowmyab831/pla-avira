"""
Notification Service
────────────────────
Multi-channel notifications (WhatsApp, Email, Push) with user consent.

Channels:
  - WhatsApp via Twilio API (requires TWILIO_* env vars)
  - Email via Resend API (requires RESEND_API_KEY env var)
  - Push via Firebase Cloud Messaging (requires FCM credentials)

All notifications require explicit user opt-in per channel.
No notification is ever sent without user consent.
"""
from __future__ import annotations

import logging
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# In-memory store for notification preferences and queue
# Production: move to PostgreSQL
_NOTIFICATION_PREFS: Dict[str, Dict] = {}  # user_id -> preferences
_NOTIFICATION_LOG: List[Dict] = []  # audit log of sent notifications
_PENDING_APPROVALS: Dict[str, Dict] = {}  # approval_id -> pending notification

DATA_DIR = Path("/data/documents") if Path("/data/documents").exists() else Path("./data")
NOTIF_FILE = DATA_DIR / "notification_prefs.json"


def _load_prefs():
    global _NOTIFICATION_PREFS
    if NOTIF_FILE.exists():
        try:
            _NOTIFICATION_PREFS = json.loads(NOTIF_FILE.read_text())
        except Exception:
            pass


def _save_prefs():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        NOTIF_FILE.write_text(json.dumps(_NOTIFICATION_PREFS, indent=2))
    except Exception as e:
        logger.debug(f"Save notification prefs: {e}")


_load_prefs()


# ── User Preferences ────────────────────────────────────────────────────────

def get_notification_prefs(user_id: str) -> Dict:
    """Get user's notification preferences."""
    return _NOTIFICATION_PREFS.get(user_id, {
        "whatsapp_enabled": False,
        "whatsapp_number": None,
        "telegram_enabled": False,
        "telegram_chat_id": None,
        "email_enabled": False,
        "email_address": None,
        "push_enabled": False,
        "push_token": None,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
        "categories": {
            "earnings_alerts": True,
            "price_alerts": True,
            "action_items": True,
            "calendar_reminders": True,
            "market_alerts": False,
        },
    })


def update_notification_prefs(user_id: str, prefs: Dict) -> Dict:
    """Update user's notification preferences. Requires explicit opt-in."""
    current = get_notification_prefs(user_id)
    current.update(prefs)
    _NOTIFICATION_PREFS[user_id] = current
    _save_prefs()
    return current


# ── Notification Sending ─────────────────────────────────────────────────────

async def send_telegram(message: str, chat_id: Optional[str] = None) -> Dict:
    """Send a Telegram message via the bound bot chat."""
    from app.services import telegram_service
    if not telegram_service.is_configured():
        return {"success": False, "error": "Telegram not configured. Set TELEGRAM_BOT_TOKEN."}
    result = await telegram_service.send_message(message, chat_id=chat_id)
    ok = bool(result.get("ok"))
    _log_notification("telegram", chat_id or "bound", message, ok, result.get("error", "") or result.get("description", ""))
    return {"success": ok, **({} if ok else {"error": result.get("error") or result.get("description")})}


async def send_whatsapp(phone: str, message: str) -> Dict:
    """Send WhatsApp message via Twilio. Requires TWILIO_* env vars."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        return {"success": False, "error": "Twilio not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN."}

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data={
                    "From": from_number,
                    "To": f"whatsapp:{phone}",
                    "Body": message,
                },
                timeout=15,
            )
            if r.status_code in (200, 201):
                result = r.json()
                _log_notification("whatsapp", phone, message, True)
                return {"success": True, "sid": result.get("sid")}
            else:
                _log_notification("whatsapp", phone, message, False, r.text)
                return {"success": False, "error": r.text}
    except Exception as e:
        _log_notification("whatsapp", phone, message, False, str(e))
        return {"success": False, "error": str(e)}


async def send_email(to_email: str, subject: str, body: str) -> Dict:
    """Send email via local SMTP (Mailpit) by default; Resend if RESEND_API_KEY is set."""
    smtp_host = os.getenv("SMTP_HOST", "mailpit.pla.svc.cluster.local")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    from_email = os.getenv("RESEND_FROM_EMAIL", "avira@avira.local")
    api_key = os.getenv("RESEND_API_KEY")

    if not api_key:
        # Local SMTP path (Mailpit in-cluster mail server)
        try:
            import smtplib
            from email.message import EmailMessage
            msg = EmailMessage()
            msg["From"] = from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.set_content(body)
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
                s.send_message(msg)
            _log_notification("email", to_email, f"{subject}: {body[:100]}", True)
            return {"success": True, "via": "smtp", "server": smtp_host}
        except Exception as e:
            _log_notification("email", to_email, subject, False, str(e))
            return {"success": False, "error": str(e)}

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "text": body,
                },
                timeout=15,
            )
            if r.status_code in (200, 201):
                _log_notification("email", to_email, f"{subject}: {body[:100]}", True)
                return {"success": True, "id": r.json().get("id")}
            else:
                _log_notification("email", to_email, subject, False, r.text)
                return {"success": False, "error": r.text}
    except Exception as e:
        _log_notification("email", to_email, subject, False, str(e))
        return {"success": False, "error": str(e)}


# ── Consent-Based Notification Queue ─────────────────────────────────────────

def queue_notification(
    user_id: str,
    category: str,
    title: str,
    message: str,
    channels: Optional[List[str]] = None,
) -> Dict:
    """
    Queue a notification for user approval.
    Nothing is sent until the user explicitly approves.

    Returns an approval_id that the user/frontend must confirm.
    """
    import uuid
    approval_id = str(uuid.uuid4())[:8]

    prefs = get_notification_prefs(user_id)
    if channels is None:
        channels = []
        if prefs.get("telegram_enabled"):
            channels.append("telegram")
        if prefs.get("whatsapp_enabled"):
            channels.append("whatsapp")
        if prefs.get("email_enabled"):
            channels.append("email")
        if prefs.get("push_enabled"):
            channels.append("push")

    if not channels:
        channels = ["in_app"]  # fallback to in-app notification

    _PENDING_APPROVALS[approval_id] = {
        "approval_id": approval_id,
        "user_id": user_id,
        "category": category,
        "title": title,
        "message": message,
        "channels": channels,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_approval",
    }

    return {
        "approval_id": approval_id,
        "status": "pending_approval",
        "channels": channels,
        "message_preview": f"{title}: {message[:80]}...",
        "action_required": "Call POST /api/notifications/approve/{approval_id} to send",
    }


async def approve_and_send(approval_id: str, user_id: str) -> Dict:
    """Only the owner can approve once. Report actual adapter outcomes."""
    pending = _PENDING_APPROVALS.get(approval_id)
    if not pending or pending.get("user_id") != user_id:
        return {"success": False, "error": "Approval not found or expired"}
    if pending["status"] != "pending_approval":
        return {"success": False, "error": "Notification is no longer pending"}
    prefs = get_notification_prefs(user_id)
    results = {}
    pending["status"] = "sending"
    for channel in set(pending["channels"]):
        try:
            if channel == "telegram" and prefs.get("telegram_enabled") and prefs.get("telegram_chat_id"):
                results[channel] = await send_telegram(f"{pending['title']}\n\n{pending['message']}", chat_id=prefs["telegram_chat_id"])
            elif channel == "whatsapp" and prefs.get("whatsapp_enabled") and prefs.get("whatsapp_number"):
                results[channel] = await send_whatsapp(prefs["whatsapp_number"], f"{pending['title']}\n\n{pending['message']}")
            elif channel == "email" and prefs.get("email_enabled") and prefs.get("email_address"):
                results[channel] = await send_email(prefs["email_address"], f"Avira: {pending['title']}", pending["message"])
            elif channel == "in_app":
                results[channel] = {"success": True, "note": "Displayed in app"}
            else:
                results[channel] = {"success": False, "error": "Channel is unavailable or no longer enabled"}
        except Exception:
            logger.warning("Notification adapter failed for channel %s", channel)
            results[channel] = {"success": False, "error": "Delivery failed"}
    success = bool(results) and all(r.get("success") for r in results.values())
    pending["status"] = "sent" if success else "failed"
    pending["sent_at"] = datetime.now(timezone.utc).isoformat() if success else None
    pending["results"] = results
    return {"success": success, "results": results, "error": None if success else "Some delivery channels failed or are unavailable"}


def reject_notification(approval_id: str, user_id: str) -> Dict:
    """User rejects a queued notification."""
    pending = _PENDING_APPROVALS.get(approval_id)
    if not pending or pending.get("user_id") != user_id:
        return {"success": False, "error": "Approval not found"}
    if pending["status"] != "pending_approval":
        return {"success": False, "error": "Notification is no longer pending"}
    pending["status"] = "rejected"
    return {"success": True, "status": "rejected"}


def get_pending_notifications(user_id: str) -> List[Dict]:
    """Get all pending notifications awaiting user approval."""
    return [
        n for n in _PENDING_APPROVALS.values()
        if n["user_id"] == user_id and n["status"] == "pending_approval"
    ]


# ── Audit Log ────────────────────────────────────────────────────────────────

def _log_notification(channel: str, recipient: str, message: str, success: bool, error: str = ""):
    _NOTIFICATION_LOG.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "recipient": recipient[:20] + "...",
        "message_preview": message[:50],
        "success": success,
        "error": error[:100] if error else "",
    })
    # Keep last 500 entries
    if len(_NOTIFICATION_LOG) > 500:
        _NOTIFICATION_LOG.pop(0)


def get_notification_log(limit: int = 50) -> List[Dict]:
    """Get recent notification audit log."""
    return _NOTIFICATION_LOG[-limit:]
