"""
Compliance & Risk Management Module

Legal Framework:
 - Personal automated trading is LEGAL (SEC Rule 15a-1 does not apply to individuals)
 - No broker-dealer registration needed for personal accounts
 - Pattern Day Trader (PDT) rule: 4+ day trades in 5 business days with < $25k = restricted
 - Options require appropriate approval level (Level 2+ for buying calls/puts)

License Audit (all dependencies are permissive):
 - yfinance: Apache 2.0
 - robin_stocks: MIT
 - FastAPI: MIT
 - uvicorn: BSD
 - numpy: BSD
 - pandas: BSD
 - httpx: BSD
 - React: MIT
 - React Native: MIT
 - Tailwind CSS: MIT
 - Ollama: MIT

Robinhood API Note:
 - robin_stocks uses Robinhood's unofficial API (no official public API exists)
 - Robinhood ToS §15 restricts "automated means" but enforcement is inconsistent
 - Recommendation: Use reasonable request rates (1 req/sec max), don't scrape bulk data
 - If Robinhood blocks access, switch to a broker with official API (Alpaca, TD Ameritrade)

Disclaimer:
 This software is for EDUCATIONAL and PERSONAL USE only.
 It does NOT constitute financial advice. Trading options carries
 significant risk of loss, including total loss of investment.
 Past performance does not guarantee future results.
 The developer assumes no liability for trading losses.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ─── Pattern Day Trader (PDT) Rule Tracker ────────────────────────────────────

@dataclass
class DayTrade:
    symbol: str
    buy_date: date
    sell_date: date
    profit: float


class PDTTracker:
    """
    Tracks day trades to prevent PDT violation.
    
    Rule: If account < $25,000 and you make 4+ day trades in a rolling
    5 business day window, the account gets flagged/restricted.
    
    A "day trade" = buying and selling the same security on the same day.
    """
    
    PDT_THRESHOLD = 25000.0  # Account value below which PDT applies
    MAX_DAY_TRADES = 3       # Stay under 4 to avoid flagging
    WINDOW_DAYS = 5          # Rolling 5 business day window
    
    def __init__(self):
        self.day_trades: List[DayTrade] = []
        self.account_value = 1000.0
    
    def record_day_trade(self, symbol: str, profit: float):
        """Record a same-day buy+sell as a day trade."""
        today = date.today()
        self.day_trades.append(DayTrade(
            symbol=symbol, buy_date=today, sell_date=today, profit=profit
        ))
        logger.warning(f"PDT: Day trade recorded ({symbol}). Count in window: {self.day_trades_in_window}")
    
    @property
    def day_trades_in_window(self) -> int:
        """Count day trades in the rolling 5 business day window."""
        cutoff = date.today() - timedelta(days=7)  # ~5 business days
        return sum(1 for t in self.day_trades if t.sell_date >= cutoff)
    
    @property
    def pdt_at_risk(self) -> bool:
        """True if one more day trade would trigger PDT flag."""
        return (
            self.account_value < self.PDT_THRESHOLD
            and self.day_trades_in_window >= self.MAX_DAY_TRADES
        )
    
    def can_day_trade(self) -> tuple[bool, str]:
        """Check if we can make another day trade safely."""
        if self.account_value >= self.PDT_THRESHOLD:
            return True, "Account above $25k — PDT rule does not apply"
        
        trades_used = self.day_trades_in_window
        remaining = self.MAX_DAY_TRADES - trades_used
        
        if remaining <= 0:
            return False, f"PDT LIMIT REACHED: {trades_used}/3 day trades used in 5-day window. Cannot day trade until window resets."
        
        return True, f"OK: {trades_used}/{self.MAX_DAY_TRADES} day trades used ({remaining} remaining)"
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "account_value": self.account_value,
            "pdt_applies": self.account_value < self.PDT_THRESHOLD,
            "day_trades_in_window": self.day_trades_in_window,
            "max_allowed": self.MAX_DAY_TRADES,
            "remaining": max(0, self.MAX_DAY_TRADES - self.day_trades_in_window),
            "at_risk": self.pdt_at_risk,
            "recommendation": "Hold positions overnight to avoid day trade count" if self.day_trades_in_window >= 2 else "OK",
        }


# ─── Risk Disclosure ──────────────────────────────────────────────────────────

RISK_DISCLOSURE = """
═══════════════════════════════════════════════════════════
  AVIRA OPTIONS TRADING BOT — RISK DISCLOSURE
═══════════════════════════════════════════════════════════

1. OPTIONS RISK: Buying call options can result in 100% loss
   of the premium paid. Options are leveraged instruments.

2. PAPER TRADING: This POC uses PAPER TRADING (simulated).
   No real money is at risk during the proof of concept phase.

3. PDT RULE: With < $25,000 in account, you are limited to
   3 day trades per 5 business days. The bot tracks this.

4. NO GUARANTEE: Past performance and backtests do NOT
   guarantee future results. Markets can be irrational.

5. PERSONAL USE: This tool is for personal portfolio
   management. It is NOT investment advice.

6. LIVE TRADING: Before connecting to Robinhood with real
   money, you MUST:
   - Complete the 1-week paper trading POC
   - Verify the bot's win rate exceeds 50%
   - Understand that you could lose your entire $1,000
   - Have options trading approval (Level 2+)
   - Accept all financial risk personally

═══════════════════════════════════════════════════════════
"""


# ─── License Audit ────────────────────────────────────────────────────────────

LICENSE_AUDIT = {
    "all_permissive": True,
    "gpl_contamination": False,
    "dependencies": [
        {"name": "yfinance", "license": "Apache-2.0", "status": "✅ OK"},
        {"name": "robin_stocks", "license": "MIT", "status": "✅ OK"},
        {"name": "FastAPI", "license": "MIT", "status": "✅ OK"},
        {"name": "uvicorn", "license": "BSD-3-Clause", "status": "✅ OK"},
        {"name": "numpy", "license": "BSD-3-Clause", "status": "✅ OK"},
        {"name": "pandas", "license": "BSD-3-Clause", "status": "✅ OK"},
        {"name": "httpx", "license": "BSD-3-Clause", "status": "✅ OK"},
        {"name": "pydantic", "license": "MIT", "status": "✅ OK"},
        {"name": "React", "license": "MIT", "status": "✅ OK"},
        {"name": "React Native", "license": "MIT", "status": "✅ OK"},
        {"name": "Tailwind CSS", "license": "MIT", "status": "✅ OK"},
        {"name": "Ollama", "license": "MIT", "status": "✅ OK"},
        {"name": "OpenClaw", "license": "Apache-2.0", "status": "✅ OK"},
        {"name": "Vite", "license": "MIT", "status": "✅ OK"},
        {"name": "Lucide Icons", "license": "ISC", "status": "✅ OK"},
    ],
    "summary": "All dependencies use permissive licenses (Apache-2.0, MIT, BSD, ISC). No GPL/AGPL/copyleft contamination. Safe for commercial and personal use.",
}


# ─── Singleton ────────────────────────────────────────────────────────────────

_pdt_tracker: PDTTracker | None = None


def get_pdt_tracker() -> PDTTracker:
    global _pdt_tracker
    if _pdt_tracker is None:
        _pdt_tracker = PDTTracker()
    return _pdt_tracker
