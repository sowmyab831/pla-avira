"""
Telegram Bot Service
────────────────────
Two-way Telegram integration for Avira:

  • Outbound  — push alerts (price alerts, day-trade tips, email action items,
                stop/take-profit hits, market digests).
  • Inbound   — long-poll getUpdates so the user can chat with the agent and
                ask any question; replies are produced by the assistant.

Configuration is persisted to disk so the bound chat_id and per-feature
opt-ins survive restarts. The bot token comes from settings (env
TELEGRAM_BOT_TOKEN, created via @BotFather).

Governance: outbound alerts only fire for features the user has explicitly
enabled. The inbound chat is opt-in by the act of messaging the bot.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}/{method}"

_DATA_DIR = Path("/data/documents") if Path("/data/documents").exists() else Path("./data")
_CONFIG_FILE = _DATA_DIR / "telegram_config.json"

# Telegram caps a single message at 4096 chars.
_MAX_LEN = 4000

_DEFAULT_CONFIG: Dict[str, Any] = {
    "chat_id": None,            # bound chat to deliver alerts to
    "bound_at": None,
    "features": {
        "day_trade_tips": False,   # push buy/sell tips during market hours
        "email_alerts": False,     # push email-derived action items
        "price_alerts": True,      # push triggered price alerts
        "trade_exits": True,       # push stop-loss / take-profit hits
    },
    "tips_min_confidence": 65,     # only push tips at/above this confidence
    "update_offset": 0,            # getUpdates pagination cursor
}

_config: Dict[str, Any] = {}


def _load() -> None:
    global _config
    if _CONFIG_FILE.exists():
        try:
            stored = json.loads(_CONFIG_FILE.read_text())
            _config = {**_DEFAULT_CONFIG, **stored}
            _config["features"] = {**_DEFAULT_CONFIG["features"], **stored.get("features", {})}
            return
        except Exception as e:  # noqa: BLE001
            logger.warning("telegram config load failed: %s", e)
    _config = json.loads(json.dumps(_DEFAULT_CONFIG))
    # Seed chat_id from env if provided.
    if settings.telegram_chat_id:
        _config["chat_id"] = str(settings.telegram_chat_id)


def _save() -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _CONFIG_FILE.write_text(json.dumps(_config, indent=2))
    except Exception as e:  # noqa: BLE001
        logger.debug("telegram config save failed: %s", e)


_load()


# ── Public config helpers ────────────────────────────────────────────────────

def is_configured() -> bool:
    """True when a bot token is available."""
    return bool(settings.telegram_bot_token)


def get_config() -> Dict[str, Any]:
    """Return the current bot config (without exposing the token)."""
    return {
        "configured": is_configured(),
        "chat_bound": bool(_config.get("chat_id")),
        "chat_id": _config.get("chat_id"),
        "bound_at": _config.get("bound_at"),
        "features": _config.get("features", {}),
        "tips_min_confidence": _config.get("tips_min_confidence", 65),
    }


def update_features(features: Dict[str, bool]) -> Dict[str, Any]:
    """Enable/disable specific outbound features."""
    current = _config.setdefault("features", {})
    for key, val in features.items():
        if key in _DEFAULT_CONFIG["features"]:
            current[key] = bool(val)
    _save()
    return get_config()


def set_tips_min_confidence(value: int) -> Dict[str, Any]:
    _config["tips_min_confidence"] = max(0, min(100, int(value)))
    _save()
    return get_config()


def bind_chat(chat_id: str) -> Dict[str, Any]:
    """Bind the chat that alerts are delivered to."""
    _config["chat_id"] = str(chat_id)
    _config["bound_at"] = datetime.now(timezone.utc).isoformat()
    _save()
    return get_config()


def feature_enabled(name: str) -> bool:
    return bool(_config.get("features", {}).get(name)) and bool(_config.get("chat_id"))


def get_bound_chat_id() -> Optional[str]:
    return _config.get("chat_id")


# ── Telegram API ─────────────────────────────────────────────────────────────

async def _call(method: str, payload: Dict[str, Any], timeout: float = 15.0) -> Dict[str, Any]:
    token = settings.telegram_bot_token
    if not token:
        return {"ok": False, "error": "Telegram bot token not configured (set TELEGRAM_BOT_TOKEN)."}
    url = API_BASE.format(token=token, method=method)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload)
            data = r.json()
            if not data.get("ok"):
                logger.warning("telegram %s failed: %s", method, data.get("description"))
            return data
    except Exception as e:  # noqa: BLE001
        logger.error("telegram %s error: %s", method, e)
        return {"ok": False, "error": str(e)}


def _chunk(text: str) -> List[str]:
    if len(text) <= _MAX_LEN:
        return [text]
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > _MAX_LEN:
            if cur:
                chunks.append(cur)
            # Hard-split a single oversized line.
            while len(line) > _MAX_LEN:
                chunks.append(line[:_MAX_LEN])
                line = line[_MAX_LEN:]
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        chunks.append(cur)
    return chunks


async def send_message(text: str, chat_id: Optional[str] = None, parse_mode: str = "Markdown") -> Dict[str, Any]:
    """Send a message to the given chat (defaults to the bound chat)."""
    target = chat_id or get_bound_chat_id()
    if not target:
        return {"ok": False, "error": "No chat bound. Message the bot and /start first."}

    last: Dict[str, Any] = {"ok": False, "error": "no content"}
    for chunk in _chunk(text):
        payload = {"chat_id": target, "text": chunk, "disable_web_page_preview": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        last = await _call("sendMessage", payload)
        # If Markdown parsing fails, retry once as plain text.
        if not last.get("ok") and parse_mode:
            payload.pop("parse_mode", None)
            last = await _call("sendMessage", payload)
    return last


async def get_updates(limit: int = 20, timeout: int = 0) -> List[Dict[str, Any]]:
    """Long-poll for inbound messages using the stored offset cursor."""
    offset = int(_config.get("update_offset", 0))
    data = await _call(
        "getUpdates",
        {"offset": offset, "limit": limit, "timeout": timeout},
        timeout=timeout + 10,
    )
    if not data.get("ok"):
        return []
    updates = data.get("result", [])
    if updates:
        # Advance cursor past the highest update_id we just consumed.
        _config["update_offset"] = updates[-1]["update_id"] + 1
        _save()
    return updates


async def test_message() -> Dict[str, Any]:
    return await send_message(
        "✅ *Avira Telegram is connected.*\nYou'll receive your enabled alerts here, "
        "and you can ask me anything anytime.\n\n_This is AI-generated research, not financial advice._"
    )
