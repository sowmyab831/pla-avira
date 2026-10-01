"""
Telegram Inbound Handler
────────────────────────
Turns inbound Telegram messages into actions. Supports slash commands plus
free-form questions that are routed to the Avira assistant so the user can
chat with the agent from anywhere.

Commands:
  /start              Bind this chat for alerts + show welcome
  /help               List commands
  /tips               On-demand day-trade tips (top buys/sells right now)
  /stock SYMBOL       Quick technical read on a symbol
  /portfolio          Paper trading portfolio summary
  /enable <feature>   Turn on: tips | email | price | exits
  /disable <feature>  Turn off a feature
  /status             Show bot + feature status

Anything else is treated as a question for the assistant.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.services import telegram_service

logger = logging.getLogger(__name__)

_FEATURE_ALIASES = {
    "tips": "day_trade_tips",
    "day_trade_tips": "day_trade_tips",
    "email": "email_alerts",
    "email_alerts": "email_alerts",
    "price": "price_alerts",
    "price_alerts": "price_alerts",
    "exits": "trade_exits",
    "trade_exits": "trade_exits",
}

_DISCLAIMER = "\n\n_AI-generated research, not financial advice._"


async def handle_update(update: Dict[str, Any]) -> None:
    """Process a single Telegram update."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    try:
        if text.startswith("/"):
            await _handle_command(chat_id, text)
        else:
            await _handle_question(chat_id, text)
    except Exception as e:  # noqa: BLE001
        logger.error("telegram inbound handling failed: %s", e, exc_info=True)
        await telegram_service.send_message(
            "Sorry, something went wrong handling that. Please try again.",
            chat_id=chat_id,
        )


async def _handle_command(chat_id: str, text: str) -> None:
    parts = text.split()
    cmd = parts[0].lower().lstrip("/").split("@")[0]  # strip /cmd@BotName
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "start":
        telegram_service.bind_chat(chat_id)
        await telegram_service.send_message(
            "*Welcome to Avira.* \U0001f44b\n\n"
            "This chat is now connected. I can:\n"
            "• Send day-trade tips (buy/sell) when enabled\n"
            "• Alert you on price targets & trade exits\n"
            "• Flag action items from your email\n"
            "• Answer any question — just type it\n\n"
            "Try `/tips`, `/stock NVDA`, `/portfolio`, or `/help`.",
            chat_id=chat_id,
        )
        return

    if cmd == "help":
        await telegram_service.send_message(
            "*Commands*\n"
            "`/tips` — day-trade tips now\n"
            "`/stock SYMBOL` — quick technical read\n"
            "`/portfolio` — paper portfolio summary\n"
            "`/enable tips|email|price|exits`\n"
            "`/disable tips|email|price|exits`\n"
            "`/status` — bot + feature status\n\n"
            "Or just ask me anything in plain English.",
            chat_id=chat_id,
        )
        return

    if cmd == "status":
        cfg = telegram_service.get_config()
        feats = cfg.get("features", {})
        bound = "yes" if cfg["chat_bound"] else "no"
        lines = ["*Avira bot status*", f"Chat bound: {bound}", "", "*Features*"]
        for k, v in feats.items():
            mark = "\u2705" if v else "\u2b1c"
            lines.append(f"{mark} {k}")
        lines.append(f"\nTips min confidence: {cfg.get('tips_min_confidence')}%")
        await telegram_service.send_message("\n".join(lines), chat_id=chat_id)
        return

    if cmd in ("enable", "disable"):
        feature = _FEATURE_ALIASES.get(arg.lower())
        if not feature:
            await telegram_service.send_message(
                "Usage: `/enable tips|email|price|exits`", chat_id=chat_id
            )
            return
        telegram_service.bind_chat(chat_id)  # ensure bound
        telegram_service.update_features({feature: cmd == "enable"})
        await telegram_service.send_message(
            f"{'Enabled' if cmd == 'enable' else 'Disabled'} *{feature}*.", chat_id=chat_id
        )
        return

    if cmd == "tips":
        await _send_tips(chat_id)
        return

    if cmd == "stock":
        if not arg:
            await telegram_service.send_message("Usage: `/stock NVDA`", chat_id=chat_id)
            return
        await _send_stock(chat_id, arg.upper())
        return

    if cmd == "portfolio":
        await _send_portfolio(chat_id)
        return

    await telegram_service.send_message(
        "Unknown command. Try `/help`.", chat_id=chat_id
    )


async def _handle_question(chat_id: str, text: str) -> None:
    """Route a free-form question to the assistant and reply."""
    from app.router_assistant import chat as assistant_chat, AssistantRequest

    telegram_service.bind_chat(chat_id)  # first message binds the chat
    req = AssistantRequest(
        message=text,
        session_id=f"telegram:{chat_id}",
        user_id=f"telegram:{chat_id}",
    )
    resp = await assistant_chat(req)
    reply = resp.response or "I couldn't produce an answer for that."
    await telegram_service.send_message(reply, chat_id=chat_id)


# ── Shared formatters (also used by the scheduler) ───────────────────────────

def format_tips(scan: Dict[str, Any], min_conf: int) -> str:
    buys = [b for b in scan.get("top_buys", []) if b.get("confidence", 0) >= min_conf]
    sells = [s for s in scan.get("top_sells", []) if s.get("confidence", 0) >= min_conf]
    if not buys and not sells:
        return ""
    lines = ["*\U0001f4c8 Day-Trade Tips*"]
    for b in buys[:5]:
        lines.append(
            f"\n*BUY {b['symbol']}* @ ${b['entry_price']:.2f}  ({b['confidence']:.0f}%)\n"
            f"  Stop ${b['stop_loss']:.2f} · Target ${b['take_profit_1']:.2f} (R/R {b['risk_reward']})\n"
            f"  _{'; '.join(b.get('reasons', [])[:2])}_"
        )
    for s in sells[:5]:
        lines.append(
            f"\n*SELL {s['symbol']}* @ ${s['entry_price']:.2f}  ({s['confidence']:.0f}%)\n"
            f"  _{'; '.join(s.get('reasons', [])[:2])}_"
        )
    lines.append(_DISCLAIMER)
    return "\n".join(lines)


async def _send_tips(chat_id: str) -> None:
    from app.services.day_trading_scanner import auto_scan_and_trade
    cfg = telegram_service.get_config()
    min_conf = cfg.get("tips_min_confidence", 65)
    scan = await auto_scan_and_trade(auto_execute=False, min_confidence=min_conf)
    msg = format_tips(scan, min_conf)
    if not msg:
        msg = "No high-confidence day-trade setups right now. I'll keep watching."
    await telegram_service.send_message(msg, chat_id=chat_id)


async def _send_stock(chat_id: str, symbol: str) -> None:
    from app.services.day_trading_scanner import scan_single
    try:
        r = await scan_single(symbol)
    except Exception:
        await telegram_service.send_message(f"Couldn't scan {symbol}.", chat_id=chat_id)
        return
    ind = r.indicators
    msg = (
        f"*{r.symbol}* — ${r.price:.2f}\n"
        f"Signal: *{r.signal.value}* ({r.confidence:.0f}%)\n"
        f"RSI {ind.get('rsi')} · MACD {ind.get('macd_histogram')} · VWAP ${ind.get('vwap')}\n"
        f"Entry ${r.entry_price:.2f} · Stop ${r.stop_loss:.2f} · Target ${r.take_profit_1:.2f}\n"
        f"_{'; '.join(r.reasons[:3])}_{_DISCLAIMER}"
    )
    await telegram_service.send_message(msg, chat_id=chat_id)


async def _send_portfolio(chat_id: str) -> None:
    from app.services.day_trading_scanner import get_portfolio_summary
    p = get_portfolio_summary()
    lines = [
        "*\U0001f4bc Paper Portfolio*",
        f"Value: ${p['portfolio_value']:,.2f}  ({p['total_return_pct']:+.2f}%)",
        f"Cash: ${p['cash']:,.2f} · Win rate: {p['win_rate']}%",
        f"Realized P&L: ${p['realized_pnl']:,.2f} · Unrealized: ${p['unrealized_pnl']:,.2f}",
    ]
    if p["open_positions"]:
        lines.append("\n*Open positions*")
        for pos in p["open_positions"][:8]:
            lines.append(
                f"{pos['symbol']} x{pos['quantity']} @ ${pos['entry_price']:.2f} "
                f"→ ${pos['current_price']:.2f} ({pos['unrealized_pnl_pct']:+.1f}%)"
            )
    await telegram_service.send_message("\n".join(lines), chat_id=chat_id)
