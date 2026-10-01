"""Robinhood integration for real trading."""
import logging
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

# In-memory session store (replace with Redis/DB in production)
_robinhood_session: Dict[str, Any] = {}

class RobinhoodCredentials(BaseModel):
    username: str
    password: str
    mfa_code: Optional[str] = None

class TradeOrder(BaseModel):
    symbol: str
    side: str  # buy or sell
    quantity: float
    order_type: str = "market"  # market or limit
    limit_price: Optional[float] = None
    time_in_force: str = "gtc"  # gtc, day, ioc, fok

class RobinhoodClient:
    """Wrapper around Robinhood API via robin_stocks or direct API."""

    def __init__(self):
        self.token = None
        self.account_id = None
        self.logged_in = False

    def _load_from_env(self) -> bool:
        """Try to load token from environment or file."""
        token_file = os.path.expanduser("~/.avira/robinhood_token.json")
        if os.path.exists(token_file):
            import json
            try:
                with open(token_file) as f:
                    data = json.load(f)
                self.token = data.get("token")
                self.account_id = data.get("account_id")
                self.logged_in = bool(self.token)
                return self.logged_in
            except Exception as e:
                logger.warning(f"Failed to load Robinhood token: {e}")
        return False

    def save_token(self):
        """Persist token to file."""
        os.makedirs(os.path.expanduser("~/.avira"), exist_ok=True)
        token_file = os.path.expanduser("~/.avira/robinhood_token.json")
        import json
        with open(token_file, "w") as f:
            json.dump({"token": self.token, "account_id": self.account_id}, f)

    async def login(self, username: str, password: str, mfa_code: Optional[str] = None) -> Dict:
        """Login to Robinhood and get OAuth token."""
        try:
            # Use robin_stocks if available, otherwise direct API
            import robin_stocks.robinhood as r
            login_result = r.login(username, password, mfa_code=mfa_code, store_session=False)
            self.token = r.helper.request_get("https://api.robinhood.com/oauth2/token/", "results")
            # Get account info
            accounts = r.profiles.load_account_profile()
            self.account_id = accounts.get("url", "").split("/")[-2] if accounts else None
            self.logged_in = True
            self.save_token()
            return {"success": True, "account_id": self.account_id}
        except ImportError:
            # Fallback to direct API
            return await self._direct_login(username, password, mfa_code)
        except Exception as e:
            logger.error(f"Robinhood login failed: {e}")
            return {"success": False, "error": str(e)}

    async def _direct_login(self, username: str, password: str, mfa_code: Optional[str] = None) -> Dict:
        """Direct API login without robin_stocks."""
        url = "https://api.robinhood.com/oauth2/token/"
        payload = {
            "grant_type": "password",
            "client_id": "c82SH0WZOsabOXGP2sxqcj34FxkvfnWRZBKlBjFS",
            "device_token": "...",  # Would need proper device token
            "scope": "internal",
            "username": username,
            "password": password,
        }
        if mfa_code:
            payload["mfa_code"] = mfa_code

        async with httpx.AsyncClient() as client:
            r = await client.post(url, data=payload)
            if r.status_code == 200:
                data = r.json()
                self.token = data["access_token"]
                self.logged_in = True
                self.save_token()
                return {"success": True}
            elif r.status_code == 400 and "mfa_required" in r.text:
                return {"success": False, "mfa_required": True}
            else:
                return {"success": False, "error": r.text}

    async def get_quote(self, symbol: str) -> Dict:
        """Get real-time quote for a symbol."""
        try:
            import robin_stocks.robinhood as r
            quote = r.stocks.get_stock_quote_by_symbol(symbol.upper())
            return {
                "symbol": symbol,
                "price": float(quote["last_trade_price"]),
                "bid": float(quote.get("bid_price", 0)),
                "ask": float(quote.get("ask_price", 0)),
                "volume": int(quote.get("volume", 0)),
                "prev_close": float(quote.get("previous_close", 0)),
            }
        except Exception as e:
            logger.error(f"Quote error: {e}")
            return {"error": str(e)}

    async def get_portfolio(self) -> Dict:
        """Get current portfolio holdings."""
        try:
            import robin_stocks.robinhood as r
            positions = r.account.build_holdings()
            profile = r.profiles.load_account_profile()
            return {
                "cash": float(profile.get("portfolio_cash", 0)),
                "equity": float(profile.get("equity", 0)),
                "positions": [
                    {
                        "symbol": sym,
                        "quantity": float(p["quantity"]),
                        "avg_cost": float(p["average_buy_price"]),
                        "current_price": float(p["price"]),
                        "equity": float(p["equity"]),
                        "percent_change": float(p["percent_change"]),
                    }
                    for sym, p in positions.items()
                ],
            }
        except Exception as e:
            logger.error(f"Portfolio error: {e}")
            return {"error": str(e)}

    async def place_order(self, order: TradeOrder) -> Dict:
        """Place a buy or sell order."""
        try:
            import robin_stocks.robinhood as r
            symbol = order.symbol.upper()
            qty = order.quantity
            if order.side == "buy":
                if order.order_type == "market":
                    result = r.orders.order_buy_market(symbol, qty, timeInForce=order.time_in_force)
                else:
                    result = r.orders.order_buy_limit(symbol, qty, order.limit_price, timeInForce=order.time_in_force)
            else:
                if order.order_type == "market":
                    result = r.orders.order_sell_market(symbol, qty, timeInForce=order.time_in_force)
                else:
                    result = r.orders.order_sell_limit(symbol, qty, order.limit_price, timeInForce=order.time_in_force)
            return {"success": True, "order": result}
        except Exception as e:
            logger.error(f"Order error: {e}")
            return {"success": False, "error": str(e)}

    async def get_open_orders(self) -> List[Dict]:
        """Get list of open orders."""
        try:
            import robin_stocks.robinhood as r
            orders = r.orders.get_all_open_stock_orders()
            return [{"id": o["id"], "symbol": o["instrument"].split("/")[-2], "side": o["side"], "quantity": o["quantity"], "status": o["state"]} for o in orders]
        except Exception as e:
            logger.error(f"Open orders error: {e}")
            return []

    async def cancel_order(self, order_id: str) -> Dict:
        """Cancel an open order."""
        try:
            import robin_stocks.robinhood as r
            r.orders.cancel_stock_order(order_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def logout(self):
        """Logout and clear session."""
        try:
            import robin_stocks.robinhood as r
            r.logout()
        except:
            pass
        self.token = None
        self.logged_in = False
        token_file = os.path.expanduser("~/.avira/robinhood_token.json")
        if os.path.exists(token_file):
            os.remove(token_file)


_client: Optional[RobinhoodClient] = None

def get_robinhood_client() -> RobinhoodClient:
    global _client
    if _client is None:
        _client = RobinhoodClient()
        _client._load_from_env()
    return _client
