"""
Meridian — AI-Powered Trading Autopilot

FastAPI backend for the Meridian trading app.
Connects to Robinhood via robin_stocks and uses PLA Avira's
deep analysis engine for trade signal generation.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.robinhood_client import RobinhoodClient
from app.autopilot import AutopilotEngine, TradingMode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Meridian",
    description="AI-Powered Trading Autopilot — Buy dips, sell highs, powered by Avira AI",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons
_rh_client: Optional[RobinhoodClient] = None
_autopilot: Optional[AutopilotEngine] = None


def get_rh() -> RobinhoodClient:
    global _rh_client
    if _rh_client is None:
        _rh_client = RobinhoodClient()
    return _rh_client


def get_autopilot() -> AutopilotEngine:
    global _autopilot
    if _autopilot is None:
        _autopilot = AutopilotEngine()
    return _autopilot


# ── Models ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    mfa_code: str = ""

class OrderRequest(BaseModel):
    symbol: str
    quantity: float = 0
    dollar_amount: float = 0
    limit_price: float = 0

class WatchlistRequest(BaseModel):
    symbols: List[str]

class ModeRequest(BaseModel):
    mode: str  # manual, semi_auto, autopilot


# ── Auth ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    rh = get_rh()
    return {
        "status": "healthy",
        "app": "Meridian",
        "robinhood_connected": rh.logged_in,
        "autopilot_mode": get_autopilot().mode.value,
    }


@app.post("/auth/login")
async def login(req: LoginRequest):
    rh = get_rh()
    import os
    os.environ["ROBINHOOD_USERNAME"] = req.username
    os.environ["ROBINHOOD_PASSWORD"] = req.password
    rh.username = req.username
    rh.password = req.password
    result = rh.login(req.mfa_code)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Login failed"))
    return result


@app.post("/auth/logout")
async def logout():
    get_rh().logout()
    return {"success": True}


# ── Portfolio ─────────────────────────────────────────────

@app.get("/portfolio")
async def portfolio():
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in to Robinhood")
    return rh.get_portfolio()


@app.get("/quote/{symbol}")
async def quote(symbol: str):
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")
    return rh.get_quote(symbol.upper())


# ── Orders ────────────────────────────────────────────────

@app.post("/orders/buy")
async def buy(req: OrderRequest):
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")

    if req.limit_price > 0:
        result = rh.buy_limit(req.symbol.upper(), req.quantity, req.limit_price)
    else:
        result = rh.buy_market(req.symbol.upper(), req.quantity, req.dollar_amount)

    if result.get("success"):
        get_autopilot().log_trade({
            "signal": "buy", "symbol": req.symbol.upper(),
            "quantity": req.quantity, "source": "manual",
        })
    return result


@app.post("/orders/sell")
async def sell(req: OrderRequest):
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")

    if req.limit_price > 0:
        result = rh.sell_limit(req.symbol.upper(), req.quantity, req.limit_price)
    else:
        result = rh.sell_market(req.symbol.upper(), req.quantity, req.dollar_amount)

    if result.get("success"):
        get_autopilot().log_trade({
            "signal": "sell", "symbol": req.symbol.upper(),
            "quantity": req.quantity, "source": "manual",
        })
    return result


@app.get("/orders/open")
async def open_orders():
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"orders": rh.get_open_orders()}


@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")
    return rh.cancel_order(order_id)


# ── Autopilot ─────────────────────────────────────────────

@app.post("/autopilot/evaluate")
async def evaluate_watchlist(req: WatchlistRequest):
    """Evaluate watchlist and generate trade signals using PLA AI."""
    rh = get_rh()
    engine = get_autopilot()

    # Get portfolio (or empty if not logged in)
    portfolio = rh.get_portfolio() if rh.logged_in else {"positions": [], "buying_power": 0}

    signals = await engine.evaluate_watchlist(req.symbols, portfolio)
    return {
        "success": True,
        "mode": engine.mode.value,
        "signals": signals,
        "portfolio_value": portfolio.get("total_equity", 0),
        "buying_power": portfolio.get("buying_power", 0),
    }


@app.post("/autopilot/mode")
async def set_mode(req: ModeRequest):
    """Set autopilot mode: manual, semi_auto, or autopilot."""
    engine = get_autopilot()
    try:
        engine.mode = TradingMode(req.mode)
        return {"success": True, "mode": engine.mode.value}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")


@app.get("/autopilot/stats")
async def autopilot_stats():
    return get_autopilot().get_stats()


@app.get("/autopilot/history")
async def trade_history(limit: int = 50):
    return {"trades": get_autopilot().get_trade_history(limit)}


@app.post("/autopilot/execute")
async def execute_signal(req: OrderRequest):
    """Execute a trade signal (requires Robinhood login)."""
    rh = get_rh()
    if not rh.logged_in:
        raise HTTPException(status_code=401, detail="Not logged in")

    engine = get_autopilot()
    if engine.mode == TradingMode.MANUAL:
        raise HTTPException(
            status_code=403,
            detail="Autopilot is in MANUAL mode. Switch to semi_auto or autopilot to auto-execute.",
        )

    # Execute the trade
    if req.quantity > 0:
        result = rh.buy_market(req.symbol.upper(), req.quantity)
    elif req.dollar_amount > 0:
        result = rh.buy_market(req.symbol.upper(), 0, req.dollar_amount)
    else:
        raise HTTPException(status_code=400, detail="Specify quantity or dollar_amount")

    if result.get("success"):
        engine.log_trade({
            "signal": "buy", "symbol": req.symbol.upper(),
            "quantity": req.quantity or f"${req.dollar_amount}",
            "source": "autopilot",
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# AI Options Trading Bot — Paper Trading POC
# ═══════════════════════════════════════════════════════════════════════════════

from app.options_bot import get_bot, scan_and_trade, fetch_stock_data, discover_market_candidates, BotConfig


@app.get("/api/options-bot/status")
async def options_bot_status():
    """Get current bot status: capital, P&L, open positions, trade history."""
    bot = get_bot()
    return bot.get_status()


@app.post("/api/options-bot/scan")
async def options_bot_scan():
    """
    Run one scan cycle: check exits, scan watchlist, execute paper trades.
    Call this every 60s during market hours for automated trading.
    """
    import asyncio
    result = await asyncio.to_thread(scan_and_trade)
    return result


@app.post("/api/options-bot/start")
async def options_bot_start():
    """Start the bot (sets running flag)."""
    bot = get_bot()
    bot.is_running = True
    return {"success": True, "message": "Options bot started (paper trading mode)", "status": bot.get_status()}


@app.post("/api/options-bot/stop")
async def options_bot_stop():
    """Stop the bot."""
    bot = get_bot()
    bot.is_running = False
    return {"success": True, "message": "Options bot stopped", "status": bot.get_status()}


@app.post("/api/options-bot/reset")
async def options_bot_reset():
    """Reset bot to starting state ($1000, no positions)."""
    from app.options_bot import _bot_instance
    import app.options_bot as ob
    ob._bot_instance = None
    bot = get_bot()
    return {"success": True, "message": "Bot reset to $1000", "status": bot.get_status()}


@app.get("/api/options-bot/signals/{symbol}")
async def options_bot_signals(symbol: str):
    """Get current trading signals for a specific symbol."""
    import asyncio
    from app.options_bot import generate_entry_signal

    data = await asyncio.to_thread(fetch_stock_data, symbol.upper())
    if "error" in data:
        return {"success": False, "error": data["error"]}

    signal = generate_entry_signal(
        closes=data["closes"],
        highs=data["highs"],
        lows=data["lows"],
        volumes=data["volumes"],
    )

    return {
        "symbol": symbol.upper(),
        "current_price": data["current_price"],
        "rsi": data["rsi"],
        "macd": data["macd"],
        "momentum": data["momentum"],
        "options_available": len(data.get("options_chain", [])),
        "signal": {
            "action": signal.action if signal else "HOLD",
            "confidence": signal.confidence if signal else 0,
            "reasons": signal.reasons if signal else ["No actionable signal"],
        } if signal else {"action": "HOLD", "confidence": 0, "reasons": ["No actionable signal"]},
    }


@app.get("/api/options-bot/watchlist")
async def options_bot_watchlist():
    """Get quick overview of all watchlist stocks."""
    return {"watchlist": BotConfig.WATCHLIST, "max_trades_per_day": BotConfig.MAX_TRADES_PER_DAY}


@app.get("/api/options-bot/market-candidates")
async def options_bot_market_candidates(limit: int = 15):
    """Discover high-momentum/high-volume market candidates beyond the user watchlist."""
    import asyncio
    candidates = await asyncio.to_thread(discover_market_candidates, limit)
    return {"candidates": candidates, "universe_size": len(BotConfig.MARKET_UNIVERSE)}


@app.post("/api/options-bot/watchlist/add")
async def options_bot_add_ticker(symbol: str):
    """Add a custom ticker to the watchlist."""
    added = BotConfig.add_ticker(symbol)
    return {
        "success": added,
        "symbol": symbol.upper(),
        "message": f"{symbol.upper()} added to watchlist" if added else f"{symbol.upper()} already in watchlist",
        "watchlist": BotConfig.WATCHLIST,
    }


@app.post("/api/options-bot/watchlist/remove")
async def options_bot_remove_ticker(symbol: str):
    """Remove a ticker from the watchlist."""
    removed = BotConfig.remove_ticker(symbol)
    return {
        "success": removed,
        "symbol": symbol.upper(),
        "message": f"{symbol.upper()} removed" if removed else f"{symbol.upper()} not found",
        "watchlist": BotConfig.WATCHLIST,
    }


@app.get("/api/options-bot/config")
async def options_bot_config():
    """Get bot configuration."""
    return {
        "starting_capital": BotConfig.STARTING_CAPITAL,
        "max_trades_per_day": BotConfig.MAX_TRADES_PER_DAY,
        "max_position_pct": BotConfig.MAX_POSITION_PCT,
        "max_open_positions": BotConfig.MAX_OPEN_POSITIONS,
        "target_gain_pct": BotConfig.TARGET_GAIN_PCT,
        "stop_loss_pct": BotConfig.STOP_LOSS_PCT,
        "watchlist": BotConfig.WATCHLIST,
        "market_universe": BotConfig.MARKET_UNIVERSE,
        "signal_threshold": BotConfig.SIGNAL_THRESHOLD,
        "scan_interval_seconds": BotConfig.SCAN_INTERVAL_SECONDS,
        "llm_enabled": BotConfig.USE_LLM,
        "preferred_delta": f"{BotConfig.PREFERRED_DELTA_MIN}-{BotConfig.PREFERRED_DELTA_MAX}",
        "mode": "PAPER TRADING (no real money)",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Compliance & Risk Management
# ═══════════════════════════════════════════════════════════════════════════════

from app.compliance import get_pdt_tracker, LICENSE_AUDIT, RISK_DISCLOSURE


@app.get("/api/compliance/pdt-status")
async def pdt_status():
    """Pattern Day Trader rule tracker status."""
    tracker = get_pdt_tracker()
    return tracker.get_status()


@app.get("/api/compliance/licenses")
async def license_audit():
    """Software license audit — verify all dependencies are permissive."""
    return LICENSE_AUDIT


@app.get("/api/compliance/risk-disclosure")
async def risk_disclosure():
    """Legal risk disclosure for options trading."""
    return {"disclosure": RISK_DISCLOSURE}


@app.get("/api/compliance/can-day-trade")
async def can_day_trade():
    """Check if another day trade is allowed under PDT rules."""
    tracker = get_pdt_tracker()
    allowed, reason = tracker.can_day_trade()
    return {"allowed": allowed, "reason": reason, "status": tracker.get_status()}


# ═══════════════════════════════════════════════════════════════════════════════
# Robinhood Integration (placeholder — PAPER MODE by default)
# ═══════════════════════════════════════════════════════════════════════════════

from app.robinhood_options import get_robinhood_client


@app.get("/api/robinhood/status")
async def robinhood_status():
    """Check Robinhood connection status and mode (paper vs live)."""
    client = get_robinhood_client()
    return client.get_status()


@app.post("/api/robinhood/login")
async def robinhood_login(mfa_code: str = ""):
    """
    Login to Robinhood.
    In PAPER mode (default): simulated login.
    In LIVE mode: requires ROBINHOOD_USERNAME + ROBINHOOD_PASSWORD env vars.
    """
    client = get_robinhood_client()
    return client.login(mfa_code)


@app.get("/api/robinhood/account")
async def robinhood_account():
    """Get Robinhood account info (buying power, portfolio value)."""
    client = get_robinhood_client()
    return client.get_account_info()


@app.post("/api/robinhood/buy-call")
async def robinhood_buy_call(symbol: str, strike: float, expiry: str, quantity: int = 1):
    """
    Buy a call option via Robinhood.
    PAPER MODE by default — no real money.
    Set ROBINHOOD_LIVE_TRADING=true to enable real execution.
    """
    client = get_robinhood_client()
    if not client.logged_in and not client.paper_mode:
        return {"success": False, "error": "Not logged in. Call /api/robinhood/login first."}
    return client.buy_call_option(symbol.upper(), strike, expiry, quantity)


@app.post("/api/robinhood/sell-call")
async def robinhood_sell_call(symbol: str, strike: float, expiry: str, quantity: int = 1):
    """Sell (close) a call option position via Robinhood."""
    client = get_robinhood_client()
    return client.sell_call_option(symbol.upper(), strike, expiry, quantity)
