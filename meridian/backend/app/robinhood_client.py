"""
Meridian — Robinhood Client

Wraps robin_stocks for authenticated trading operations.
Supports: login, portfolio, quotes, orders (market/limit), and position management.

Security: Credentials stored in environment variables, never in code.
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Lazy import — robin_stocks is optional dependency
_rs = None


def _get_rs():
    global _rs
    if _rs is None:
        try:
            import robin_stocks.robinhood as rs
            _rs = rs
        except ImportError:
            raise RuntimeError("robin_stocks not installed. Run: pip install robin_stocks")
    return _rs


class RobinhoodClient:
    def __init__(self):
        self.logged_in = False
        self.username = os.environ.get("ROBINHOOD_USERNAME", "")
        self.password = os.environ.get("ROBINHOOD_PASSWORD", "")
        self.mfa_code = os.environ.get("ROBINHOOD_MFA", "")

    def login(self, mfa_code: str = "") -> Dict:
        """Authenticate with Robinhood. Supports MFA via TOTP."""
        rs = _get_rs()
        try:
            code = mfa_code or self.mfa_code
            if code:
                result = rs.login(self.username, self.password, mfa_code=code)
            else:
                result = rs.login(self.username, self.password)

            self.logged_in = True
            logger.info("Robinhood login successful")
            return {"success": True, "message": "Logged in"}
        except Exception as e:
            logger.error(f"Robinhood login failed: {e}")
            return {"success": False, "error": str(e)}

    def logout(self):
        rs = _get_rs()
        rs.logout()
        self.logged_in = False

    def get_portfolio(self) -> Dict:
        """Get current portfolio holdings and total value."""
        rs = _get_rs()
        try:
            holdings = rs.build_holdings()
            profile = rs.load_portfolio_profile()

            positions = []
            total_value = 0
            total_gain = 0

            for symbol, data in holdings.items():
                price = float(data.get("price", 0))
                qty = float(data.get("quantity", 0))
                avg_cost = float(data.get("average_buy_price", 0))
                equity = float(data.get("equity", 0))
                pnl = float(data.get("equity_change", 0))
                pnl_pct = float(data.get("percent_change", 0))

                positions.append({
                    "symbol": symbol,
                    "quantity": qty,
                    "avg_cost": round(avg_cost, 2),
                    "current_price": round(price, 2),
                    "equity": round(equity, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                })
                total_value += equity
                total_gain += pnl

            return {
                "success": True,
                "total_equity": round(total_value, 2),
                "total_gain": round(total_gain, 2),
                "cash": float(profile.get("withdrawable_amount", 0)),
                "buying_power": float(profile.get("excess_margin", 0)),
                "positions": positions,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Portfolio error: {e}")
            return {"success": False, "error": str(e)}

    def get_quote(self, symbol: str) -> Dict:
        """Get real-time quote for a symbol."""
        rs = _get_rs()
        try:
            quote = rs.get_latest_price(symbol, includeExtendedHours=True)
            fundamentals = rs.get_fundamentals(symbol)[0] if rs.get_fundamentals(symbol) else {}

            return {
                "symbol": symbol,
                "price": float(quote[0]) if quote else 0,
                "pe_ratio": fundamentals.get("pe_ratio"),
                "market_cap": fundamentals.get("market_cap"),
                "high_52w": fundamentals.get("high_52_weeks"),
                "low_52w": fundamentals.get("low_52_weeks"),
                "volume": fundamentals.get("volume"),
            }
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def buy_market(self, symbol: str, quantity: float, dollar_amount: float = 0) -> Dict:
        """Place a market buy order. Use quantity OR dollar_amount."""
        rs = _get_rs()
        try:
            if dollar_amount > 0:
                order = rs.order_buy_fractional_by_price(symbol, dollar_amount)
            else:
                order = rs.order_buy_market(symbol, quantity)

            return {
                "success": True,
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": "buy",
                "type": "market",
                "quantity": quantity or f"${dollar_amount}",
                "state": order.get("state", ""),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Buy order failed: {e}")
            return {"success": False, "error": str(e)}

    def sell_market(self, symbol: str, quantity: float, dollar_amount: float = 0) -> Dict:
        """Place a market sell order."""
        rs = _get_rs()
        try:
            if dollar_amount > 0:
                order = rs.order_sell_fractional_by_price(symbol, dollar_amount)
            else:
                order = rs.order_sell_market(symbol, quantity)

            return {
                "success": True,
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": "sell",
                "type": "market",
                "quantity": quantity or f"${dollar_amount}",
                "state": order.get("state", ""),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Sell order failed: {e}")
            return {"success": False, "error": str(e)}

    def buy_limit(self, symbol: str, quantity: float, limit_price: float) -> Dict:
        """Place a limit buy order."""
        rs = _get_rs()
        try:
            order = rs.order_buy_limit(symbol, quantity, limit_price)
            return {
                "success": True,
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": "buy",
                "type": "limit",
                "quantity": quantity,
                "limit_price": limit_price,
                "state": order.get("state", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def sell_limit(self, symbol: str, quantity: float, limit_price: float) -> Dict:
        """Place a limit sell order."""
        rs = _get_rs()
        try:
            order = rs.order_sell_limit(symbol, quantity, limit_price)
            return {
                "success": True,
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "side": "sell",
                "type": "limit",
                "quantity": quantity,
                "limit_price": limit_price,
                "state": order.get("state", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_stop_loss(self, symbol: str, quantity: float, stop_price: float) -> Dict:
        """Place a stop-loss sell order."""
        rs = _get_rs()
        try:
            order = rs.order_sell_stop_loss(symbol, quantity, stop_price)
            return {
                "success": True,
                "order_id": order.get("id", ""),
                "symbol": symbol,
                "type": "stop_loss",
                "stop_price": stop_price,
                "state": order.get("state", ""),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_order(self, order_id: str) -> Dict:
        """Cancel a pending order."""
        rs = _get_rs()
        try:
            result = rs.cancel_stock_order(order_id)
            return {"success": True, "order_id": order_id, "cancelled": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_open_orders(self) -> List[Dict]:
        """Get all open/pending orders."""
        rs = _get_rs()
        try:
            orders = rs.get_all_open_stock_orders()
            return [
                {
                    "order_id": o.get("id", ""),
                    "symbol": o.get("instrument", ""),
                    "side": o.get("side", ""),
                    "type": o.get("type", ""),
                    "quantity": o.get("quantity", ""),
                    "price": o.get("price", ""),
                    "state": o.get("state", ""),
                }
                for o in orders
            ]
        except Exception as e:
            return []
