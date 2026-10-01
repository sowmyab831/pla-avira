"""
Trading Routes — Day Trading Scanner + Paper Trading Engine
============================================================

Endpoints:
  GET  /api/trading/scan               — Scan market for signals
  GET  /api/trading/scan/{symbol}      — Scan single symbol
  POST /api/trading/auto-scan          — Auto-scan + optional auto-trade
  GET  /api/trading/portfolio           — Portfolio summary
  POST /api/trading/execute             — Execute a paper trade
  POST /api/trading/reset               — Reset paper portfolio
  GET  /api/trading/history             — Scan history
  GET  /api/trading/watchlist           — Current watchlist
  POST /api/trading/watchlist           — Update watchlist
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.middleware.subscription_gate import soft_rate_limit
from pydantic import BaseModel

from dataclasses import asdict

from app.services.day_trading_scanner import (
    DEFAULT_WATCHLIST,
    auto_scan_and_trade,
    execute_paper_trade,
    get_portfolio_summary,
    get_scan_history,
    load_portfolio,
    reset_portfolio,
    scan_market,
    scan_single,
)
from app.services.watchlist_alerts import (
    check_alerts,
    create_alert,
    delete_alert,
    get_earnings_calendar,
    load_alerts,
    scan_unusual_volume,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trading", tags=["trading"])


# ── Models ────────────────────────────────────────────────────────────────────

class TradeRequest(BaseModel):
    symbol: str
    action: str = "BUY"  # BUY or SELL
    quantity: Optional[int] = None
    user_id: Optional[str] = "default"


class AutoScanRequest(BaseModel):
    symbols: Optional[List[str]] = None
    auto_execute: bool = False
    min_confidence: int = 60
    user_id: Optional[str] = "default"
    max_buys: Optional[int] = 3
    max_sells: Optional[int] = None


class WatchlistRequest(BaseModel):
    symbols: List[str]


# ── User-customizable watchlist (in-memory, persists with portfolio) ─────────

_custom_watchlist: List[str] = list(DEFAULT_WATCHLIST)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/scan", dependencies=[Depends(soft_rate_limit("scan"))])
async def scan(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols"),
    period: str = Query("5d", description="Period: 1d, 5d, 1mo"),
    interval: str = Query("15m", description="Interval: 1m, 5m, 15m, 1h, 1d"),
    user_id: str = Query("default", description="User ID for paper trading"),
):
    """Scan market for trading signals."""
    try:
        sym_list = symbols.split(",") if symbols else _custom_watchlist
        results = await scan_market(sym_list, period=period, interval=interval)
        return {
            "scanned": len(results),
            "buy_signals": sum(1 for r in results if r.signal.value in ("STRONG_BUY", "BUY")),
            "sell_signals": sum(1 for r in results if r.signal.value in ("STRONG_SELL", "SELL")),
            "signals": [
                {
                    "symbol": r.symbol,
                    "price": r.price,
                    "signal": r.signal.value,
                    "confidence": r.confidence,
                    "reasons": r.reasons,
                    "indicators": r.indicators,
                    "entry": r.entry_price,
                    "stop_loss": r.stop_loss,
                    "take_profit_1": r.take_profit_1,
                    "take_profit_2": r.take_profit_2,
                    "risk_reward": r.risk_reward,
                    "timestamp": r.timestamp,
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.error("scan failed: %s", e)
        raise HTTPException(500, str(e))


@router.get("/scan/{symbol}", dependencies=[Depends(soft_rate_limit("scan"))])
async def scan_symbol(symbol: str):
    """Scan a single symbol for detailed signal."""
    try:
        result = await scan_single(symbol.upper())
        return {
            "symbol": result.symbol,
            "price": result.price,
            "signal": result.signal.value,
            "confidence": result.confidence,
            "reasons": result.reasons,
            "indicators": result.indicators,
            "entry": result.entry_price,
            "stop_loss": result.stop_loss,
            "take_profit_1": result.take_profit_1,
            "take_profit_2": result.take_profit_2,
            "risk_reward": result.risk_reward,
            "timestamp": result.timestamp,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/auto-scan")
async def auto_scan(req: AutoScanRequest):
    """Run autonomous scan and optionally auto-execute paper trades."""
    try:
        return await auto_scan_and_trade(
            symbols=req.symbols or _custom_watchlist,
            auto_execute=req.auto_execute,
            min_confidence=req.min_confidence,
            user_id=req.user_id or "default",
            max_buys=req.max_buys,
            max_sells=req.max_sells,
        )
    except Exception as e:
        logger.error("auto-scan failed: %s", e)
        raise HTTPException(500, str(e))


@router.get("/portfolio")
async def portfolio(user_id: str = Query("default", description="User ID for paper trading")):
    """Get paper trading portfolio summary."""
    try:
        return get_portfolio_summary(user_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/execute")
async def execute_trade(req: TradeRequest):
    """Execute a paper trade (BUY or SELL)."""
    try:
        scan = await scan_single(req.symbol.upper())
        trade = execute_paper_trade(req.symbol.upper(), req.action.upper(), scan, req.quantity, user_id=req.user_id or "default")
        return {
            "status": "executed",
            "trade": {
                "id": trade.id,
                "symbol": trade.symbol,
                "action": trade.action,
                "entry_price": trade.entry_price,
                "quantity": trade.quantity,
                "stop_loss": trade.stop_loss,
                "take_profit": trade.take_profit,
                "reason": trade.reason_entry,
            },
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/reset")
async def reset(user_id: str = Query("default", description="User ID for paper trading")):
    """Reset paper portfolio to initial state ($100k)."""
    return reset_portfolio(user_id)


@router.get("/history")
async def history(limit: int = Query(20, description="Max scan history entries")):
    """Get scan history."""
    return {"history": get_scan_history(limit)}


@router.get("/watchlist")
async def get_watchlist():
    """Get current watchlist."""
    return {"symbols": _custom_watchlist}


@router.post("/watchlist")
async def set_watchlist(req: WatchlistRequest):
    """Update watchlist."""
    global _custom_watchlist
    _custom_watchlist = [s.upper() for s in req.symbols]
    return {"symbols": _custom_watchlist, "count": len(_custom_watchlist)}


# ── Price Alerts ──────────────────────────────────────────────────────────────

class AlertRequest(BaseModel):
    symbol: str
    condition: str = "above"  # above or below
    target_price: float


@router.get("/alerts")
async def get_alerts():
    """Get all price alerts."""
    alerts = load_alerts()
    return {"alerts": [asdict(a) for a in alerts]}


@router.post("/alerts")
async def add_alert(req: AlertRequest):
    """Create a price alert."""
    alert = create_alert(req.symbol, req.condition, req.target_price)
    return {"status": "created", "alert": asdict(alert)}


@router.delete("/alerts/{alert_id}")
async def remove_alert(alert_id: str):
    """Delete a price alert."""
    if delete_alert(alert_id):
        return {"status": "deleted"}
    raise HTTPException(404, "Alert not found")


@router.post("/alerts/check")
async def check_price_alerts():
    """Check all alerts against current prices."""
    triggered = await check_alerts()
    return {"triggered": triggered, "count": len(triggered)}


# ── Earnings Calendar ─────────────────────────────────────────────────────────

@router.get("/earnings")
async def earnings(
    symbols: Optional[str] = Query(None, description="Comma-separated symbols"),
):
    """Get upcoming earnings dates."""
    sym_list = symbols.split(",") if symbols else _custom_watchlist
    return await get_earnings_calendar(sym_list)


# ── Unusual Volume ────────────────────────────────────────────────────────────

@router.get("/unusual-volume")
async def unusual_volume(
    threshold: float = Query(2.0, description="Volume ratio threshold"),
):
    """Scan for stocks with unusual volume."""
    results = await scan_unusual_volume(_custom_watchlist, threshold)
    return {"count": len(results), "stocks": results}


# ── Robinhood Real Trading ────────────────────────────────────────────────────

from app.integrations.robinhood import (
    RobinhoodCredentials,
    TradeOrder,
    get_robinhood_client,
)

_trading_mode: Dict[str, Any] = {
    "mode": "paper",  # paper | real
    "auto_trades_enabled": False,
    "max_auto_trades_per_day": 5,
    "today_auto_trades": 0,
    "last_trade_date": "",
    "risk_per_trade_pct": 2.0,
    "max_position_pct": 10.0,
}

class TradingModeUpdate(BaseModel):
    mode: Optional[str] = None  # paper | real
    auto_trades_enabled: Optional[bool] = None
    max_auto_trades_per_day: Optional[int] = None
    risk_per_trade_pct: Optional[float] = None
    max_position_pct: Optional[float] = None


@router.get("/robinhood/status")
async def robinhood_status():
    """Check Robinhood connection status."""
    client = get_robinhood_client()
    return {
        "logged_in": client.logged_in,
        "account_id": client.account_id,
        "trading_mode": _trading_mode,
    }


@router.post("/robinhood/login")
async def robinhood_login(creds: RobinhoodCredentials):
    """Login to Robinhood."""
    client = get_robinhood_client()
    result = await client.login(creds.username, creds.password, creds.mfa_code)
    return result


@router.post("/robinhood/logout")
async def robinhood_logout():
    """Logout from Robinhood."""
    client = get_robinhood_client()
    client.logout()
    return {"success": True}


@router.get("/robinhood/portfolio")
async def robinhood_portfolio():
    """Get real Robinhood portfolio."""
    client = get_robinhood_client()
    if not client.logged_in:
        raise HTTPException(401, "Not logged in to Robinhood")
    return await client.get_portfolio()


@router.post("/robinhood/order")
async def robinhood_order(order: TradeOrder):
    """Place a real order on Robinhood."""
    if _trading_mode["mode"] != "real":
        raise HTTPException(400, "Trading mode is set to PAPER. Switch to REAL mode first.")
    client = get_robinhood_client()
    if not client.logged_in:
        raise HTTPException(401, "Not logged in to Robinhood")
    return await client.place_order(order)


@router.get("/robinhood/orders")
async def robinhood_orders():
    """Get open orders from Robinhood."""
    client = get_robinhood_client()
    if not client.logged_in:
        raise HTTPException(401, "Not logged in to Robinhood")
    return {"orders": await client.get_open_orders()}


@router.delete("/robinhood/orders/{order_id}")
async def robinhood_cancel(order_id: str):
    """Cancel an open Robinhood order."""
    client = get_robinhood_client()
    if not client.logged_in:
        raise HTTPException(401, "Not logged in to Robinhood")
    return await client.cancel_order(order_id)


# ── Trading Mode & Auto-Trade Config ──────────────────────────────────────────

@router.get("/mode")
async def get_trading_mode():
    """Get current trading mode (paper vs real) and auto-trade settings."""
    return {"success": True, "mode": _trading_mode}


@router.put("/mode")
async def update_trading_mode(update: TradingModeUpdate):
    """Update trading mode and auto-trade settings."""
    if update.mode is not None:
        if update.mode not in ("paper", "real"):
            raise HTTPException(400, "mode must be 'paper' or 'real'")
        _trading_mode["mode"] = update.mode
    if update.auto_trades_enabled is not None:
        _trading_mode["auto_trades_enabled"] = update.auto_trades_enabled
    if update.max_auto_trades_per_day is not None:
        _trading_mode["max_auto_trades_per_day"] = update.max_auto_trades_per_day
    if update.risk_per_trade_pct is not None:
        _trading_mode["risk_per_trade_pct"] = update.risk_per_trade_pct
    if update.max_position_pct is not None:
        _trading_mode["max_position_pct"] = update.max_position_pct
    return {"success": True, "mode": _trading_mode}


# ── Potential Earnings (Paper Trading Backtest) ─────────────────────────────

@router.post("/backtest")
async def run_backtest(
    days: int = Query(30, description="Number of days to backtest"),
    initial_capital: float = Query(100_000, description="Starting capital"),
):
    """
    Run a paper-trading backtest over historical data to estimate potential earnings.

    Uses expected-value modeling: each BUY signal's confidence is treated as the
    win probability. Winning trades exit at take-profit; losing trades exit at
    stop-loss. This avoids an unrealistic 100% win rate and gives an honest
    risk-adjusted projection of potential earnings.
    """
    from app.services.day_trading_scanner import scan_market
    try:
        # Use a wider lookback so daily-interval scans have enough candles
        # to generate signals even for short backtest windows.
        period_days = max(days, 30)
        results = await scan_market(_custom_watchlist, period=f"{period_days}d", interval="1d")

        capital = initial_capital
        trades = []
        wins = 0
        for signal in results:
            if signal.signal.value not in ("STRONG_BUY", "BUY") or signal.entry_price <= 0:
                continue

            qty = int(capital * 0.05 / signal.entry_price)  # 5% position sizing
            if qty <= 0:
                continue

            entry = signal.entry_price
            tp = signal.take_profit_1
            sl = signal.stop_loss if signal.stop_loss > 0 else entry * 0.97
            gain_pct = (tp - entry) / entry
            loss_pct = (sl - entry) / entry  # negative
            p_win = max(0.0, min(1.0, signal.confidence / 100.0))

            # Expected (risk-adjusted) P&L for this trade
            expected_pct = p_win * gain_pct + (1 - p_win) * loss_pct
            pnl = qty * entry * expected_pct
            capital += pnl
            is_win = expected_pct > 0
            if is_win:
                wins += 1

            trades.append({
                "symbol": signal.symbol,
                "entry": round(entry, 2),
                "take_profit": round(tp, 2),
                "stop_loss": round(sl, 2),
                "qty": qty,
                "win_probability": round(p_win * 100, 1),
                "expected_pnl": round(pnl, 2),
                "expected_pnl_pct": round(expected_pct * 100, 2),
            })

        total_return = capital - initial_capital
        return {
            "success": True,
            "days": days,
            "initial_capital": initial_capital,
            "final_capital": round(capital, 2),
            "total_return": round(total_return, 2),
            "total_return_pct": round(total_return / initial_capital * 100, 2),
            "trades_executed": len(trades),
            "winning_trades": wins,
            "win_rate": round(wins / len(trades) * 100, 1) if trades else 0.0,
            "methodology": "expected-value (confidence-weighted TP/SL)",
            "trades": trades[:50],
        }
    except Exception as e:
        logger.error("backtest failed: %s", e)
        raise HTTPException(500, str(e))
