"""
Background Scheduler
────────────────────
Runs two long-lived asyncio tasks started from the FastAPI lifespan:

  1. inbound_poll_loop  — long-polls Telegram getUpdates and dispatches each
                          message to the inbound handler (two-way chat).
  2. periodic_loop      — on a timer, runs:
                            • price-alert checks            → push triggered
                            • paper stop-loss/take-profit   → push exits
                            • day-trade tips (market hours) → push top setups
                            • email action items            → push new items

All pushes respect the per-feature opt-ins stored in telegram_service.
The scheduler is a no-op (logs and exits) when no bot token is configured.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.services import telegram_service, telegram_bot, job_queue

logger = logging.getLogger(__name__)

_tasks: list[asyncio.Task] = []

# De-dup state so we don't spam the same item repeatedly.
_pushed_tips: dict[str, float] = {}      # f"{sym}:{signal}" -> ts
_pushed_alerts: set[str] = set()         # alert_id
_pushed_email_items: set[str] = set()    # action item id
_TIP_COOLDOWN_SEC = 3 * 3600             # don't repeat the same tip within 3h

# Periodic cadence
_PERIODIC_INTERVAL = 300                 # 5 min
_TIPS_INTERVAL = 1800                    # 30 min
_last_tips_run = 0.0

# Auto-trade state
_AUTO_TRADE_INTERVAL = 900               # 15 min between auto-trade checks
_last_auto_trade_run = 0.0
_today_auto_trades: int = 0
_last_auto_trade_date: str = ""


def _is_us_market_hours() -> bool:
    """Rough US equity market hours check (Mon-Fri, ~13:30-20:00 UTC).

    Ignores DST/holidays — close enough for tip cadence; yfinance still
    returns the latest available bar outside RTH.
    """
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:  # Sat/Sun
        return False
    minutes = now.hour * 60 + now.minute
    return 13 * 60 + 0 <= minutes <= 20 * 60 + 30


# ── Periodic jobs ────────────────────────────────────────────────────────────

async def _run_price_alerts() -> None:
    if not telegram_service.feature_enabled("price_alerts"):
        return
    from app.services.watchlist_alerts import check_alerts
    triggered = await check_alerts()
    for t in triggered:
        if t["alert_id"] in _pushed_alerts:
            continue
        _pushed_alerts.add(t["alert_id"])
        await telegram_service.send_message(f"\U0001f6a8 *Price Alert*\n{t['message']}")


async def _run_trade_exits() -> None:
    if not telegram_service.feature_enabled("trade_exits"):
        return
    from app.services.day_trading_scanner import check_stops_and_targets
    triggered = await asyncio.get_event_loop().run_in_executor(None, check_stops_and_targets)
    for t in triggered:
        emoji = "\U0001f7e2" if t["type"] == "TAKE_PROFIT" else "\U0001f534"
        await telegram_service.send_message(
            f"{emoji} *{t['type'].replace('_', ' ').title()}* — {t['symbol']} "
            f"@ ${t['price']:.2f} (P&L ${t['pnl']:,.2f})"
        )


async def _run_day_trade_tips(force: bool = False) -> None:
    global _last_tips_run
    if not telegram_service.feature_enabled("day_trade_tips"):
        return
    if not force and not _is_us_market_hours():
        return
    import time as _t
    now = _t.time()
    if not force and now - _last_tips_run < _TIPS_INTERVAL:
        return
    _last_tips_run = now

    from app.services.day_trading_scanner import auto_scan_and_trade
    cfg = telegram_service.get_config()
    min_conf = cfg.get("tips_min_confidence", 65)
    scan = await auto_scan_and_trade(auto_execute=False, min_confidence=min_conf)

    # Filter out tips we already pushed recently.
    fresh_buys, fresh_sells = [], []
    for b in scan.get("top_buys", []):
        key = f"{b['symbol']}:BUY"
        if b.get("confidence", 0) >= min_conf and (now - _pushed_tips.get(key, 0)) > _TIP_COOLDOWN_SEC:
            _pushed_tips[key] = now
            fresh_buys.append(b)
    for s in scan.get("top_sells", []):
        key = f"{s['symbol']}:SELL"
        if s.get("confidence", 0) >= min_conf and (now - _pushed_tips.get(key, 0)) > _TIP_COOLDOWN_SEC:
            _pushed_tips[key] = now
            fresh_sells.append(s)

    if not fresh_buys and not fresh_sells:
        return
    msg = telegram_bot.format_tips({"top_buys": fresh_buys, "top_sells": fresh_sells}, min_conf)
    if msg:
        await telegram_service.send_message(msg)


async def _run_email_alerts() -> None:
    if not telegram_service.feature_enabled("email_alerts"):
        return
    try:
        from app.router_integrations import action_items
    except Exception:
        return
    for item_id, item in list(action_items.items()):
        if item_id in _pushed_email_items:
            continue
        if isinstance(item, dict) and item.get("status") == "completed":
            continue
        _pushed_email_items.add(item_id)
        title = item.get("title") if isinstance(item, dict) else str(item)
        detail = item.get("description", "") if isinstance(item, dict) else ""
        await telegram_service.send_message(
            f"\U0001f4e7 *Email action item*\n{title}\n{detail}".strip()
        )


# Dedicated testuser01 auto-trade loop state
_last_testuser01_run = 0.0


async def _run_testuser01_auto_trades() -> None:
    """Auto-execute paper buy/sell for the testuser01 demo account."""
    global _last_testuser01_run

    if not settings.auto_trading_enabled or not _is_us_market_hours():
        return

    import time as _t
    now = _t.time()
    if now - _last_testuser01_run < _AUTO_TRADE_INTERVAL:
        return
    _last_testuser01_run = now

    from app.services.day_trading_scanner import auto_scan_and_trade
    try:
        result = await auto_scan_and_trade(auto_execute=True, min_confidence=60, user_id="testuser01")
        executed = result.get("executed_trades", [])
        if executed:
            logger.info("testuser01 auto-trade executed: %s", [t["symbol"] for t in executed])
    except Exception as e:
        logger.warning("testuser01 auto-trade error: %s", e)


async def _run_auto_trades() -> None:
    """Auto-execute up to 5 day trades per day during market hours."""
    global _last_auto_trade_run, _today_auto_trades, _last_auto_trade_date

    # Autonomous trading is opt-in per deployment (AVIRA_AUTO_TRADING=true).
    if not settings.auto_trading_enabled or not _is_us_market_hours():
        return

    import time as _t
    now = _t.time()
    if now - _last_auto_trade_run < _AUTO_TRADE_INTERVAL:
        return
    _last_auto_trade_run = now

    # Reset daily counter at market open
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if today_str != _last_auto_trade_date:
        _today_auto_trades = 0
        _last_auto_trade_date = today_str

    # Check if auto-trades enabled
    from app.routes.trading import _trading_mode
    if not _trading_mode.get("auto_trades_enabled", False):
        return

    max_trades = _trading_mode.get("max_auto_trades_per_day", 5)
    if _today_auto_trades >= max_trades:
        return

    # Scan for signals
    from app.services.day_trading_scanner import auto_scan_and_trade, execute_paper_trade, scan_single
    try:
        scan = await auto_scan_and_trade(auto_execute=False, min_confidence=65)
        top_buys = scan.get("top_buys", [])
        if not top_buys:
            return

        # Execute top signal
        best = top_buys[0]
        symbol = best["symbol"]
        mode = _trading_mode.get("mode", "paper")

        if mode == "paper":
            result = scan_single(symbol.upper()) if hasattr(scan_single, '__call__') else await scan_single(symbol.upper())
            trade = execute_paper_trade(symbol.upper(), "BUY", result)
            _today_auto_trades += 1
            await telegram_service.send_message(
                f"\U0001f4c8 *Auto Trade #{_today_auto_trades}* (Paper)\n"
                f"Bought {trade.quantity} {symbol} @ ${trade.entry_price:.2f}\n"
                f"SL: ${trade.stop_loss:.2f}  TP: ${trade.take_profit:.2f}"
            )
        else:
            # Real-money orders are never placed from a background task.
            # A concrete order must be approved by the user through the
            # Nexus action flow; the scheduler only reports the signal.
            logger.warning("auto-trade: real mode requested for %s but unattended real orders are disabled", symbol)
            await telegram_service.send_message(
                f"\u26a0\ufe0f Signal for {symbol} (confidence {best.get('confidence', '?')}). "
                "Unattended real-money orders are disabled; review it in the app to act."
            )
    except Exception as e:
        logger.error("auto-trade error: %s", e, exc_info=True)


async def periodic_loop() -> None:
    logger.info("scheduler: periodic loop started")
    while True:
        try:
            await _run_price_alerts()
            await _run_trade_exits()
            await _run_day_trade_tips()
            await _run_email_alerts()
            await _run_auto_trades()
            await _run_testuser01_auto_trades()
            # Durable jobs (reminders, price checks) — run regardless of
            # per-feature config; failures are recorded on the job row.
            try:
                stats = await job_queue.run_due(limit=25)
                if stats.get("claimed"):
                    logger.info("scheduler: job queue %s", stats)
            except Exception as e:  # noqa: BLE001
                logger.error("scheduler job-queue error: %s", e, exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("scheduler periodic error: %s", e, exc_info=True)
        await asyncio.sleep(_PERIODIC_INTERVAL)


# ── Inbound polling ──────────────────────────────────────────────────────────

async def inbound_poll_loop() -> None:
    logger.info("scheduler: telegram inbound poll loop started")
    while True:
        try:
            updates = await telegram_service.get_updates(timeout=30)
            for update in updates:
                await telegram_bot.handle_update(update)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error("scheduler inbound error: %s", e, exc_info=True)
            await asyncio.sleep(5)


# ── Lifecycle ────────────────────────────────────────────────────────────────

def start() -> None:
    """Start scheduler tasks (called from FastAPI lifespan)."""
    if not settings.scheduler_enabled:
        logger.info("scheduler: disabled via SCHEDULER_ENABLED=false")
        return
    loop = asyncio.get_event_loop()
    _tasks.append(loop.create_task(periodic_loop()))
    if telegram_service.is_configured():
        _tasks.append(loop.create_task(inbound_poll_loop()))
    else:
        logger.info("scheduler: no TELEGRAM_BOT_TOKEN — inbound disabled (periodic loop still runs)")
    logger.info("scheduler: started %d tasks", len(_tasks))


async def stop() -> None:
    for t in _tasks:
        t.cancel()
    for t in _tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
    _tasks.clear()
    logger.info("scheduler: stopped")
