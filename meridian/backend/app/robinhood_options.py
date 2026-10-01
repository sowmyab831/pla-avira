"""
Robinhood Options Integration — Placeholder for Live Trading

Library: robin_stocks (MIT License)
Source: https://github.com/jmfernandes/robin_stocks
PyPI: pip install robin_stocks

This module provides a bridge between the paper trading bot and
live Robinhood execution. It is DISABLED by default and requires
explicit opt-in + successful paper trading POC.

Prerequisites before enabling live trading:
 1. Complete 1-week paper trading POC with positive returns
 2. Set ROBINHOOD_LIVE_TRADING=true in environment
 3. Set ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD
 4. Have Level 2+ options approval on Robinhood
 5. Understand and accept all financial risks
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Safety flag — live trading DISABLED by default
LIVE_TRADING_ENABLED = os.environ.get("ROBINHOOD_LIVE_TRADING", "false").lower() == "true"


class RobinhoodOptionsClient:
    """
    Robinhood options trading client.
    
    Uses robin_stocks (MIT license) for API access.
    PAPER MODE by default — set ROBINHOOD_LIVE_TRADING=true to enable.
    """
    
    def __init__(self):
        self.logged_in = False
        self.paper_mode = not LIVE_TRADING_ENABLED
        self.username = os.environ.get("ROBINHOOD_USERNAME", "")
        self.password = os.environ.get("ROBINHOOD_PASSWORD", "")
        self._rs = None
    
    def _get_robin_stocks(self):
        """Lazy import robin_stocks."""
        if self._rs is None:
            try:
                import robin_stocks.robinhood as rs
                self._rs = rs
            except ImportError:
                logger.error("robin_stocks not installed. Run: pip install robin_stocks")
                return None
        return self._rs
    
    def login(self, mfa_code: str = "") -> Dict[str, Any]:
        """
        Authenticate with Robinhood.
        
        Requires: ROBINHOOD_USERNAME, ROBINHOOD_PASSWORD env vars.
        Optional: MFA code for 2FA accounts.
        """
        if self.paper_mode:
            return {
                "success": True,
                "mode": "PAPER",
                "message": "Paper mode — no real Robinhood connection. Set ROBINHOOD_LIVE_TRADING=true to enable.",
            }
        
        rs = self._get_robin_stocks()
        if not rs:
            return {"success": False, "error": "robin_stocks not installed"}
        
        if not self.username or not self.password:
            return {"success": False, "error": "ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD env vars required"}
        
        try:
            if mfa_code:
                rs.login(self.username, self.password, mfa_code=mfa_code)
            else:
                rs.login(self.username, self.password)
            self.logged_in = True
            logger.info("Robinhood login successful (LIVE MODE)")
            return {"success": True, "mode": "LIVE", "message": "Connected to Robinhood"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def logout(self):
        if not self.paper_mode and self._rs:
            self._rs.logout()
        self.logged_in = False
    
    def get_options_positions(self) -> List[Dict]:
        """Get current options positions from Robinhood."""
        if self.paper_mode:
            return []  # Paper mode uses internal tracking
        
        rs = self._get_robin_stocks()
        if not rs or not self.logged_in:
            return []
        
        try:
            positions = rs.options.get_open_option_positions()
            return positions or []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def buy_call_option(
        self,
        symbol: str,
        strike: float,
        expiry: str,
        quantity: int = 1,
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Buy a call option on Robinhood.
        
        In paper mode: returns simulated execution.
        In live mode: submits real order to Robinhood.
        """
        if self.paper_mode:
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"PAPER-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "symbol": symbol,
                "strike": strike,
                "expiry": expiry,
                "quantity": quantity,
                "limit_price": limit_price,
                "message": "Paper trade executed (no real money)",
            }
        
        rs = self._get_robin_stocks()
        if not rs or not self.logged_in:
            return {"success": False, "error": "Not logged in to Robinhood"}
        
        try:
            if limit_price:
                order = rs.orders.order_buy_option_limit(
                    "open", "debit", limit_price, symbol,
                    quantity, expiry, strike, "call"
                )
            else:
                order = rs.orders.order_buy_option_limit(
                    "open", "debit", limit_price or 0, symbol,
                    quantity, expiry, strike, "call"
                )
            
            logger.info(f"LIVE ORDER: BUY {quantity}x {symbol} ${strike}C exp:{expiry}")
            return {"success": True, "mode": "LIVE", "order": order}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"success": False, "error": str(e)}
    
    def sell_call_option(
        self,
        symbol: str,
        strike: float,
        expiry: str,
        quantity: int = 1,
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Sell (close) a call option position."""
        if self.paper_mode:
            return {
                "success": True,
                "mode": "PAPER",
                "order_id": f"PAPER-SELL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "symbol": symbol,
                "strike": strike,
                "expiry": expiry,
                "quantity": quantity,
                "message": "Paper sell executed (no real money)",
            }
        
        rs = self._get_robin_stocks()
        if not rs or not self.logged_in:
            return {"success": False, "error": "Not logged in"}
        
        try:
            order = rs.orders.order_sell_option_limit(
                "close", "credit", limit_price or 0, symbol,
                quantity, expiry, strike, "call"
            )
            logger.info(f"LIVE ORDER: SELL {quantity}x {symbol} ${strike}C exp:{expiry}")
            return {"success": True, "mode": "LIVE", "order": order}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get Robinhood account info (buying power, portfolio value)."""
        if self.paper_mode:
            return {
                "mode": "PAPER",
                "buying_power": 1000.0,
                "portfolio_value": 1000.0,
                "options_level": "Level 2 (assumed)",
            }
        
        rs = self._get_robin_stocks()
        if not rs or not self.logged_in:
            return {"error": "Not logged in"}
        
        try:
            profile = rs.profiles.load_account_profile()
            return {
                "mode": "LIVE",
                "buying_power": float(profile.get("buying_power", 0)),
                "portfolio_value": float(profile.get("portfolio_value", 0)),
                "options_level": profile.get("option_level", "Unknown"),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "paper_mode": self.paper_mode,
            "logged_in": self.logged_in,
            "live_trading_enabled": LIVE_TRADING_ENABLED,
            "username_configured": bool(self.username),
            "safety_note": "PAPER MODE — no real money at risk" if self.paper_mode else "⚠️ LIVE MODE — real money!",
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

_client: Optional[RobinhoodOptionsClient] = None


def get_robinhood_client() -> RobinhoodOptionsClient:
    global _client
    if _client is None:
        _client = RobinhoodOptionsClient()
    return _client
