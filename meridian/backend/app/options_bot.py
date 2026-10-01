"""
AI Options Trading Bot — Paper Trading POC

Strategy: Call options on high-momentum stocks
Starting capital: $1,000
Max trades/day: 10
Focus: Weekly/short-term call options on SPY, QQQ, AAPL, TSLA, NVDA, META

Signal Sources:
 1. Technical Analysis (RSI, MACD, Bollinger, momentum)
 2. Options Flow (unusual volume, IV rank, Greeks)
 3. News Sentiment (RSS, financial news)
 4. Social Media (Trump posts, X/Twitter market handles)
 5. Chart Patterns (breakout detection, support/resistance)

Entry Rules:
 - Buy calls when multiple signals align bullish
 - Prefer ATM or slightly OTM calls (delta 0.3-0.6)
 - Target 20-50% gains, stop at -30% loss
 - Hold 1-3 days max (theta decay management)

Risk Management:
 - Max 10% of portfolio per trade
 - Max 3 open positions simultaneously
 - Daily loss limit: -5% of portfolio
 - Auto-close before expiry if < 2 days left
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ─── Configuration ────────────────────────────────────────────────────────────

class BotConfig:
    STARTING_CAPITAL = 1000.0
    MAX_TRADES_PER_DAY = 50
    MAX_POSITION_PCT = 0.15          # 15% of portfolio per trade
    MAX_OPEN_POSITIONS = 10
    DAILY_LOSS_LIMIT_PCT = -0.10     # Stop trading if down 10% in a day
    TARGET_GAIN_PCT = 0.20           # Take profit at +20% (faster exit)
    STOP_LOSS_PCT = -0.25            # Cut loss at -25%
    MIN_DAYS_TO_EXPIRY = 2           # Allow closer expiry for day trades
    CLOSE_BEFORE_EXPIRY_DAYS = 1     # Auto-close if < 1 day to expiry
    PREFERRED_DELTA_MIN = 0.20       # Slightly wider delta range
    PREFERRED_DELTA_MAX = 0.70       # Allow higher delta (more ITM)
    SIGNAL_THRESHOLD = 15            # Lower threshold = more day-trade candidates
    WATCHLIST = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "META", "AMZN", "MSFT", "AMD", "GOOGL",
                 "SHOP", "SLV", "PLTR", "COIN", "MSTR", "SOFI", "RIVN", "ARM", "SMCI", "MARA"]
    MARKET_UNIVERSE = [
        "SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "TSLA", "META", "AMZN", "GOOGL", "AMD",
        "NFLX", "AVGO", "CRM", "ADBE", "SHOP", "PLTR", "COIN", "MSTR", "SMCI", "ARM", "SOFI", "RIVN",
        "MARA", "RIOT", "HOOD", "UBER", "SNOW", "PANW", "CRWD", "NET", "DDOG", "BABA", "NIO", "XPEV",
        "SLV", "GLD", "USO", "TLT", "XLE", "XLK", "XLF", "ARKK"
    ]
    SCAN_INTERVAL_SECONDS = 5        # Day trading: scan every 5 seconds
    USE_LLM = True                   # Use LLM for trade decision synthesis

    @classmethod
    def add_ticker(cls, symbol: str):
        sym = symbol.upper().strip()
        if sym and sym not in cls.WATCHLIST:
            cls.WATCHLIST.append(sym)
            return True
        return False

    @classmethod
    def remove_ticker(cls, symbol: str):
        sym = symbol.upper().strip()
        if sym in cls.WATCHLIST:
            cls.WATCHLIST.remove(sym)
            return True
        return False


class TradeAction(str, Enum):
    BUY_CALL = "BUY_CALL"
    SELL_CALL = "SELL_CALL"
    HOLD = "HOLD"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    EXPIRED = "expired"


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class OptionContract:
    symbol: str
    strike: float
    expiry: str           # ISO date
    option_type: str      # "call" or "put"
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    iv: float             # Implied volatility
    delta: float
    gamma: float
    theta: float
    vega: float

    @property
    def mid_price(self) -> float:
        return round((self.bid + self.ask) / 2, 2)

    @property
    def spread_pct(self) -> float:
        if self.mid_price == 0:
            return 100.0
        return round((self.ask - self.bid) / self.mid_price * 100, 1)


@dataclass
class Trade:
    id: str
    timestamp: str
    symbol: str
    action: TradeAction
    contract: OptionContract
    quantity: int
    entry_price: float
    current_price: float = 0.0
    exit_price: float = 0.0
    exit_timestamp: str = ""
    status: TradeStatus = TradeStatus.OPEN
    pnl: float = 0.0
    pnl_pct: float = 0.0
    signal_reasons: List[str] = field(default_factory=list)

    def update_pnl(self, current_mid: float):
        self.current_price = current_mid
        self.pnl = round((current_mid - self.entry_price) * self.quantity * 100, 2)
        self.pnl_pct = round((current_mid - self.entry_price) / self.entry_price * 100, 1) if self.entry_price > 0 else 0


@dataclass 
class Signal:
    symbol: str
    action: TradeAction
    confidence: float        # 0-1
    reasons: List[str]
    suggested_strike: float = 0.0
    suggested_expiry: str = ""
    timestamp: str = ""


# ─── Technical Analysis ───────────────────────────────────────────────────────

def _rsi(closes: List[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [max(d, 0) for d in deltas[-period:]]
    losses = [abs(min(d, 0)) for d in deltas[-period:]]
    avg_gain = float(np.mean(gains)) if gains else 0
    avg_loss = float(np.mean(losses)) if losses else 1e-9
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    return round(100 - 100 / (1 + rs), 2)


def _macd(closes: List[float]) -> Dict[str, float]:
    if len(closes) < 26:
        return {"macd": 0, "signal": 0, "histogram": 0}
    
    def ema(data, span):
        k = 2 / (span + 1)
        result = [data[0]]
        for v in data[1:]:
            result.append(v * k + result[-1] * (1 - k))
        return result
    
    fast = ema(closes, 12)
    slow = ema(closes, 26)
    macd_line = [f - s for f, s in zip(fast, slow)]
    signal_line = ema(macd_line[-9:], 9)
    histogram = macd_line[-1] - signal_line[-1]
    
    return {
        "macd": round(macd_line[-1], 4),
        "signal": round(signal_line[-1], 4),
        "histogram": round(histogram, 4),
    }


def _bollinger(closes: List[float], period: int = 20) -> Dict[str, float]:
    if len(closes) < period:
        return {"upper": closes[-1] * 1.02, "middle": closes[-1], "lower": closes[-1] * 0.98}
    window = closes[-period:]
    middle = float(np.mean(window))
    std = float(np.std(window))
    return {
        "upper": round(middle + 2 * std, 2),
        "middle": round(middle, 2),
        "lower": round(middle - 2 * std, 2),
    }


def _momentum(closes: List[float], periods: List[int] = [5, 10, 20]) -> Dict[str, float]:
    result = {}
    for p in periods:
        if len(closes) > p:
            result[f"mom_{p}"] = round((closes[-1] - closes[-p]) / closes[-p] * 100, 2)
        else:
            result[f"mom_{p}"] = 0.0
    return result


def _volume_spike(volumes: List[int], threshold: float = 2.0) -> bool:
    if len(volumes) < 20:
        return False
    avg_vol = float(np.mean(volumes[-20:-1]))
    return volumes[-1] > avg_vol * threshold if avg_vol > 0 else False


# ─── Signal Generation ────────────────────────────────────────────────────────

def generate_entry_signal(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[int],
    news_sentiment: float = 0.0,   # -1 to +1
    social_sentiment: float = 0.0, # -1 to +1
) -> Optional[Signal]:
    """
    Generate a BUY_CALL signal when multiple indicators align bullish.
    
    Scoring (0-100):
      Technical (40%): RSI, MACD, Bollinger, momentum
      Volume (15%): Unusual volume confirms moves
      News (20%): Breaking positive news
      Social (15%): Positive social sentiment  
      Chart (10%): Near support, breakout pattern
    """
    if len(closes) < 26:
        return None

    current = closes[-1]
    rsi = _rsi(closes)
    macd = _macd(closes)
    boll = _bollinger(closes)
    mom = _momentum(closes)
    vol_spike = _volume_spike(volumes)

    score = 0.0
    reasons = []

    # ── Technical Score (max 40) ──
    # RSI: Oversold bounce (< 35) or momentum continuation (50-65)
    if rsi < 30:
        score += 12
        reasons.append(f"RSI oversold ({rsi}) - bounce expected")
    elif 30 <= rsi < 45:
        score += 8
        reasons.append(f"RSI recovering ({rsi})")
    elif 45 <= rsi <= 65:
        score += 5
        reasons.append(f"RSI healthy momentum ({rsi})")
    elif rsi > 75:
        score -= 10
        reasons.append(f"RSI overbought ({rsi}) - CAUTION")

    # MACD: Bullish crossover or positive histogram
    if macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
        score += 10
        reasons.append("MACD bullish crossover")
    elif macd["histogram"] > 0:
        score += 5
        reasons.append("MACD positive histogram")
    elif macd["histogram"] < 0:
        score -= 5

    # Bollinger: Near lower band = potential buy
    if current <= boll["lower"] * 1.01:
        score += 10
        reasons.append(f"Price at lower Bollinger (${boll['lower']:.2f})")
    elif current <= boll["middle"]:
        score += 3

    # Momentum: Short-term momentum positive
    if mom.get("mom_5", 0) > 1.5:
        score += 8
        reasons.append(f"Strong 5-day momentum (+{mom['mom_5']}%)")
    elif mom.get("mom_5", 0) > 0.5:
        score += 4

    # ── Volume Score (max 15) ──
    if vol_spike:
        score += 15
        reasons.append("Unusual volume spike (>2x avg)")
    elif len(volumes) > 5 and volumes[-1] > float(np.mean(volumes[-5:])) * 1.3:
        score += 7
        reasons.append("Above-average volume")

    # ── News Sentiment (max 20) ──
    if news_sentiment > 0.5:
        score += 20
        reasons.append(f"Strong positive news sentiment ({news_sentiment:.2f})")
    elif news_sentiment > 0.2:
        score += 10
        reasons.append(f"Positive news ({news_sentiment:.2f})")
    elif news_sentiment < -0.3:
        score -= 15
        reasons.append(f"Negative news sentiment ({news_sentiment:.2f})")

    # ── Social Sentiment (max 15) ──
    if social_sentiment > 0.5:
        score += 15
        reasons.append(f"Strong bullish social buzz ({social_sentiment:.2f})")
    elif social_sentiment > 0.2:
        score += 8
        reasons.append(f"Positive social sentiment ({social_sentiment:.2f})")
    elif social_sentiment < -0.3:
        score -= 10

    # ── Chart Pattern (max 10) ──
    # Simple breakout detection: price breaking above recent high
    if len(highs) > 10:
        recent_high = max(highs[-10:-1])
        if current > recent_high:
            score += 10
            reasons.append(f"Breakout above ${recent_high:.2f}")
        elif current > recent_high * 0.98:
            score += 5
            reasons.append("Testing resistance")

    # ── Decision ──
    confidence = min(max(score / 100.0, 0), 1.0)
    
    if score >= BotConfig.SIGNAL_THRESHOLD:
        return Signal(
            symbol="",  # filled by caller
            action=TradeAction.BUY_CALL,
            confidence=confidence,
            reasons=reasons,
            timestamp=datetime.now().isoformat(),
        )
    return None


def llm_refine_signal(symbol: str, data: Dict[str, Any], signal: Signal) -> Signal:
    if not BotConfig.USE_LLM:
        return signal
    try:
        prompt = {
            "task": "Act as a cautious options day-trading assistant. Return JSON only.",
            "symbol": symbol,
            "current_price": data.get("current_price"),
            "rsi": data.get("rsi"),
            "macd": data.get("macd"),
            "momentum": data.get("momentum"),
            "bot_signal": {"action": signal.action, "confidence": signal.confidence, "reasons": signal.reasons},
            "instruction": "Return {\"approve\":true/false,\"confidence\":0-1,\"reason\":\"short\"}. Approve only if the trade has a clear bullish edge."
        }
        payload = json.dumps({
            "model": "qwen2.5:14b",
            "prompt": json.dumps(prompt),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.1, "num_predict": 160},
        }).encode("utf-8")
        req = urllib.request.Request("http://localhost:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8")).get("response", "{}")
            verdict = json.loads(raw)
        if verdict.get("approve") is False:
            return Signal(symbol=symbol, action=TradeAction.HOLD, confidence=0, reasons=[f"LLM rejected: {verdict.get('reason', 'weak edge')}"])
        signal.confidence = max(signal.confidence, float(verdict.get("confidence", signal.confidence)))
        signal.reasons.insert(0, f"LLM qwen2.5 approval: {verdict.get('reason', 'edge confirmed')}")
    except Exception as e:
        signal.reasons.insert(0, f"LLM unavailable, technical-only decision ({type(e).__name__})")
    return signal


def generate_exit_signal(trade: Trade, closes: List[float]) -> Optional[Signal]:
    """Check if we should exit an open position."""
    reasons = []
    
    # Take profit
    if trade.pnl_pct >= BotConfig.TARGET_GAIN_PCT * 100:
        reasons.append(f"Take profit hit ({trade.pnl_pct:+.1f}%)")
        return Signal(symbol=trade.symbol, action=TradeAction.SELL_CALL,
                     confidence=0.95, reasons=reasons, timestamp=datetime.now().isoformat())
    
    # Stop loss
    if trade.pnl_pct <= BotConfig.STOP_LOSS_PCT * 100:
        reasons.append(f"Stop loss hit ({trade.pnl_pct:+.1f}%)")
        return Signal(symbol=trade.symbol, action=TradeAction.SELL_CALL,
                     confidence=0.99, reasons=reasons, timestamp=datetime.now().isoformat())
    
    # Expiry protection
    try:
        exp_date = datetime.fromisoformat(trade.contract.expiry)
        days_left = (exp_date - datetime.now()).days
        if days_left <= BotConfig.CLOSE_BEFORE_EXPIRY_DAYS:
            reasons.append(f"Expiry protection ({days_left} days left)")
            return Signal(symbol=trade.symbol, action=TradeAction.SELL_CALL,
                         confidence=0.90, reasons=reasons, timestamp=datetime.now().isoformat())
    except Exception:
        pass
    
    # Technical exit: RSI overbought + losing momentum
    if len(closes) >= 14:
        rsi = _rsi(closes)
        if rsi > 75 and trade.pnl_pct > 10:
            reasons.append(f"RSI overbought ({rsi}) with +{trade.pnl_pct:.1f}% gain - lock profits")
            return Signal(symbol=trade.symbol, action=TradeAction.SELL_CALL,
                         confidence=0.75, reasons=reasons, timestamp=datetime.now().isoformat())
    
    return None


# ─── Options Chain Analysis ───────────────────────────────────────────────────

def select_best_contract(
    symbol: str, 
    current_price: float, 
    options_chain: List[Dict],
) -> Optional[OptionContract]:
    """
    Select the best call option contract for entry.
    Criteria: ATM/slightly OTM, good delta, reasonable spread, enough liquidity.
    """
    candidates = []
    
    for opt in options_chain:
        strike = opt.get("strike", 0)
        delta = opt.get("delta", 0)
        volume = opt.get("volume", 0)
        open_interest = opt.get("openInterest", 0)
        bid = opt.get("bid", 0)
        ask = opt.get("ask", 0)
        iv = opt.get("impliedVolatility", 0)
        last = opt.get("lastPrice", 0)
        expiry = opt.get("expiry", "")
        
        # Filter criteria
        if delta < BotConfig.PREFERRED_DELTA_MIN or delta > BotConfig.PREFERRED_DELTA_MAX:
            continue
        if volume < 10:  # Need some liquidity
            continue
        if bid <= 0 or ask <= 0:
            continue
        mid = (bid + ask) / 2
        spread_pct = (ask - bid) / mid * 100 if mid > 0 else 100
        if spread_pct > 15:  # Spread too wide
            continue
        
        # Score the contract
        score = 0
        # Prefer delta around 0.4-0.5 (good leverage)
        score += 10 - abs(delta - 0.45) * 20
        # Prefer higher volume
        score += min(volume / 100, 5)
        # Prefer lower spread
        score += max(0, 10 - spread_pct)
        # Prefer moderate IV (not too expensive)
        if 0.2 < iv < 0.6:
            score += 5
        
        candidates.append((score, OptionContract(
            symbol=symbol,
            strike=strike,
            expiry=expiry,
            option_type="call",
            bid=bid,
            ask=ask,
            last=last,
            volume=volume,
            open_interest=open_interest,
            iv=iv,
            delta=delta,
            gamma=opt.get("gamma", 0),
            theta=opt.get("theta", 0),
            vega=opt.get("vega", 0),
        )))
    
    if not candidates:
        return None
    
    # Return highest-scored contract
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1] if candidates else None


def build_paper_contract(symbol: str, current_price: float) -> OptionContract:
    strike = round(current_price)
    expiry = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    premium = max(round(current_price * 0.015, 2), 0.25)
    return OptionContract(
        symbol=symbol,
        strike=strike,
        expiry=expiry,
        option_type="call",
        bid=round(premium * 0.95, 2),
        ask=round(premium * 1.05, 2),
        last=premium,
        volume=999,
        open_interest=999,
        iv=0.35,
        delta=0.45,
        gamma=0.05,
        theta=-0.04,
        vega=0.10,
    )


# ─── Paper Trading Engine ─────────────────────────────────────────────────────

class PaperTradingBot:
    """
    Paper trading bot that simulates options trading with real market data.
    No real money is used — all trades are simulated.
    """
    
    def __init__(self):
        self.capital = BotConfig.STARTING_CAPITAL
        self.starting_capital = BotConfig.STARTING_CAPITAL
        self.positions: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.trade_log: List[Dict] = []
        self.daily_trades_count = 0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        self.total_trades = 0
        self.winning_trades = 0
        self.is_running = False
        self.signals_history: List[Signal] = []
        self.news_feed: List[Dict] = []
        self.social_feed: List[Dict] = []
    
    @property
    def total_pnl(self) -> float:
        open_pnl = sum(t.pnl for t in self.positions)
        closed_pnl = sum(t.pnl for t in self.closed_trades)
        return round(open_pnl + closed_pnl, 2)
    
    @property
    def total_return_pct(self) -> float:
        return round(self.total_pnl / self.starting_capital * 100, 2)
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return round(self.winning_trades / self.total_trades * 100, 1)
    
    @property 
    def portfolio_value(self) -> float:
        open_value = sum(t.current_price * t.quantity * 100 for t in self.positions)
        return round(self.capital + open_value, 2)
    
    def _reset_daily(self):
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trades_count = 0
            self.daily_pnl = 0.0
            self.last_reset_date = today
    
    def can_trade(self) -> Tuple[bool, str]:
        """Check if we can make another trade."""
        self._reset_daily()
        
        if self.daily_trades_count >= BotConfig.MAX_TRADES_PER_DAY:
            return False, f"Daily trade limit reached ({BotConfig.MAX_TRADES_PER_DAY})"
        
        if len(self.positions) >= BotConfig.MAX_OPEN_POSITIONS:
            return False, f"Max open positions reached ({BotConfig.MAX_OPEN_POSITIONS})"
        
        if self.daily_pnl / self.starting_capital <= BotConfig.DAILY_LOSS_LIMIT_PCT:
            return False, f"Daily loss limit hit ({self.daily_pnl:.2f})"
        
        if self.capital < 50:  # Need at least $50 to trade
            return False, "Insufficient capital"
        
        return True, "OK"
    
    def execute_buy(self, signal: Signal, contract: OptionContract) -> Optional[Trade]:
        """Execute a paper buy order."""
        can, reason = self.can_trade()
        if not can:
            logger.info(f"Cannot trade: {reason}")
            return None
        
        # Position sizing: max 10% of portfolio
        max_spend = self.portfolio_value * BotConfig.MAX_POSITION_PCT
        price = contract.mid_price
        if price <= 0:
            return None
        
        # Options are in lots of 100 shares
        cost_per_contract = price * 100
        quantity = max(1, int(max_spend / cost_per_contract))
        total_cost = quantity * cost_per_contract
        
        if total_cost > self.capital:
            quantity = max(1, int(self.capital / cost_per_contract))
            total_cost = quantity * cost_per_contract
        
        if total_cost > self.capital:
            return None
        
        # Execute
        self.capital -= total_cost
        trade = Trade(
            id=f"T{self.total_trades + 1:04d}",
            timestamp=datetime.now().isoformat(),
            symbol=signal.symbol,
            action=TradeAction.BUY_CALL,
            contract=contract,
            quantity=quantity,
            entry_price=price,
            current_price=price,
            signal_reasons=signal.reasons,
        )
        self.positions.append(trade)
        self.daily_trades_count += 1
        self.total_trades += 1
        
        self.trade_log.append({
            "time": trade.timestamp,
            "action": "BUY",
            "symbol": signal.symbol,
            "strike": contract.strike,
            "expiry": contract.expiry,
            "price": price,
            "qty": quantity,
            "cost": total_cost,
            "reasons": signal.reasons[:3],
        })
        
        logger.info(f"📈 BUY {quantity}x {signal.symbol} ${contract.strike}C exp:{contract.expiry} @ ${price:.2f} (cost: ${total_cost:.2f})")
        return trade
    
    def execute_sell(self, trade: Trade, current_price: float) -> float:
        """Execute a paper sell order."""
        trade.exit_price = current_price
        trade.exit_timestamp = datetime.now().isoformat()
        trade.status = TradeStatus.CLOSED
        trade.update_pnl(current_price)
        
        # Return capital + P&L
        proceeds = current_price * trade.quantity * 100
        self.capital += proceeds
        self.daily_pnl += trade.pnl
        
        if trade.pnl > 0:
            self.winning_trades += 1
        
        # Move to closed
        self.positions.remove(trade)
        self.closed_trades.append(trade)
        
        self.trade_log.append({
            "time": trade.exit_timestamp,
            "action": "SELL",
            "symbol": trade.symbol,
            "strike": trade.contract.strike,
            "expiry": trade.contract.expiry,
            "price": current_price,
            "qty": trade.quantity,
            "proceeds": proceeds,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
        })
        
        emoji = "💰" if trade.pnl > 0 else "📉"
        logger.info(f"{emoji} SELL {trade.symbol} ${trade.contract.strike}C @ ${current_price:.2f} P&L: ${trade.pnl:+.2f} ({trade.pnl_pct:+.1f}%)")
        return trade.pnl
    
    def get_status(self) -> Dict[str, Any]:
        """Get bot status summary."""
        return {
            "running": self.is_running,
            "capital": round(self.capital, 2),
            "portfolio_value": self.portfolio_value,
            "total_pnl": self.total_pnl,
            "total_return_pct": self.total_return_pct,
            "starting_capital": self.starting_capital,
            "open_positions": len(self.positions),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "win_rate": self.win_rate,
            "daily_trades": self.daily_trades_count,
            "daily_pnl": round(self.daily_pnl, 2),
            "positions": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "strike": t.contract.strike,
                    "expiry": t.contract.expiry,
                    "entry_price": t.entry_price,
                    "current_price": t.current_price,
                    "quantity": t.quantity,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "reasons": t.signal_reasons[:3],
                }
                for t in self.positions
            ],
            "recent_trades": self.trade_log[-10:],
            "recent_signals": [
                {"symbol": s.symbol, "action": s.action, "confidence": s.confidence, "reasons": s.reasons[:2]}
                for s in self.signals_history[-5:]
            ],
        }


# ─── Market Data Fetcher ──────────────────────────────────────────────────────

def fetch_stock_data(symbol: str) -> Dict[str, Any]:
    """Fetch real-time stock data + options chain from yfinance."""
    try:
        import yfinance as yf
        
        ticker = yf.Ticker(symbol)
        
        hist = ticker.history(period="5d", interval="5m")
        if hist.empty:
            hist = ticker.history(period="1mo", interval="1d")
        if hist.empty:
            return {"error": f"No data for {symbol}"}
        
        closes = [float(x) for x in hist["Close"].tolist()]
        highs = [float(x) for x in hist["High"].tolist()]
        lows = [float(x) for x in hist["Low"].tolist()]
        volumes = [int(x) for x in hist["Volume"].tolist()]
        current_price = closes[-1]
        
        # Options chain — get nearest weekly expiry
        options_data = []
        try:
            expirations = ticker.options
            if expirations:
                # Pick expiry 5-14 days out
                target_exp = None
                for exp in expirations[:5]:
                    exp_date = datetime.strptime(exp, "%Y-%m-%d")
                    days_out = (exp_date - datetime.now()).days
                    if BotConfig.MIN_DAYS_TO_EXPIRY <= days_out <= 14:
                        target_exp = exp
                        break
                
                if not target_exp and expirations:
                    target_exp = expirations[0]
                
                if target_exp:
                    chain = ticker.option_chain(target_exp)
                    calls = chain.calls
                    for _, row in calls.iterrows():
                        strike = float(row.get("strike", 0))
                        # Only near-the-money strikes
                        if abs(strike - current_price) / current_price > 0.10:
                            continue
                        options_data.append({
                            "strike": strike,
                            "expiry": target_exp,
                            "bid": float(row.get("bid", 0)),
                            "ask": float(row.get("ask", 0)),
                            "lastPrice": float(row.get("lastPrice", 0)),
                            "volume": int(row.get("volume", 0) or 0),
                            "openInterest": int(row.get("openInterest", 0) or 0),
                            "impliedVolatility": float(row.get("impliedVolatility", 0) or 0),
                            "delta": float(row.get("delta", 0.4) if "delta" in row.index else 0.4),
                            "gamma": float(row.get("gamma", 0.05) if "gamma" in row.index else 0.05),
                            "theta": float(row.get("theta", -0.05) if "theta" in row.index else -0.05),
                            "vega": float(row.get("vega", 0.1) if "vega" in row.index else 0.1),
                        })
        except Exception as e:
            logger.warning(f"Options chain error for {symbol}: {e}")
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "closes": closes,
            "highs": highs,
            "lows": lows,
            "volumes": volumes,
            "options_chain": options_data,
            "rsi": _rsi(closes),
            "macd": _macd(closes),
            "momentum": _momentum(closes),
        }
    except Exception as e:
        logger.error(f"Data fetch error for {symbol}: {e}")
        return {"error": str(e)}


def discover_market_candidates(limit: int = 15) -> List[str]:
    scored = []
    for symbol in BotConfig.MARKET_UNIVERSE:
        data = fetch_stock_data(symbol)
        if "error" in data:
            continue
        momentum = data.get("momentum", {})
        volumes = data.get("volumes", [])
        vol_score = 0.0
        if len(volumes) > 5:
            avg = float(np.mean(volumes[-6:-1])) or 1.0
            vol_score = min(volumes[-1] / avg, 5.0)
        score = abs(momentum.get("mom_5", 0)) + max(momentum.get("mom_10", 0), 0) + vol_score
        scored.append((score, symbol))
    scored.sort(reverse=True)
    return [symbol for _, symbol in scored[:limit]]


# ─── Singleton Bot Instance ───────────────────────────────────────────────────

_bot_instance: Optional[PaperTradingBot] = None


def get_bot() -> PaperTradingBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = PaperTradingBot()
    return _bot_instance


def scan_and_trade() -> Dict[str, Any]:
    """
    Main trading loop iteration:
    1. Scan watchlist for entry signals
    2. Check open positions for exit signals
    3. Execute trades
    
    Returns summary of actions taken.
    """
    bot = get_bot()
    actions = []
    
    # Check exits first
    for trade in list(bot.positions):
        data = fetch_stock_data(trade.symbol)
        if "error" in data:
            continue
        
        # Update current price from options
        for opt in data.get("options_chain", []):
            if abs(opt["strike"] - trade.contract.strike) < 0.01:
                mid = (opt["bid"] + opt["ask"]) / 2
                if mid > 0:
                    trade.update_pnl(mid)
                break
        
        exit_signal = generate_exit_signal(trade, data.get("closes", []))
        if exit_signal:
            pnl = bot.execute_sell(trade, trade.current_price or trade.entry_price)
            actions.append({"action": "SELL", "symbol": trade.symbol, "pnl": pnl, "reasons": exit_signal.reasons})
    
    # Check entries
    can_trade, reason = bot.can_trade()
    if can_trade:
        candidate_symbols = list(dict.fromkeys(BotConfig.WATCHLIST + discover_market_candidates(limit=15)))
        for symbol in candidate_symbols:
            if not can_trade:
                break
            
            data = fetch_stock_data(symbol)
            if "error" in data:
                continue
            
            signal = generate_entry_signal(
                closes=data["closes"],
                highs=data["highs"],
                lows=data["lows"],
                volumes=data["volumes"],
                news_sentiment=0.0,   # TODO: integrate news
                social_sentiment=0.0, # TODO: integrate social
            )
            
            if signal:
                signal.symbol = symbol
                signal = llm_refine_signal(symbol, data, signal)
            
            if signal and signal.action == TradeAction.BUY_CALL and signal.confidence >= 0.25:
                bot.signals_history.append(signal)
                
                # Select best contract
                contract = select_best_contract(symbol, data["current_price"], data["options_chain"])
                if not contract:
                    contract = build_paper_contract(symbol, data["current_price"])
                    signal.reasons.append("Paper fallback contract used because live chain was unavailable/illiquid")
                if contract:
                    trade = bot.execute_buy(signal, contract)
                    if trade:
                        actions.append({
                            "action": "BUY",
                            "symbol": symbol,
                            "price": trade.entry_price,
                            "strike": contract.strike,
                            "expiry": contract.expiry,
                            "reasons": signal.reasons[:3],
                        })
                        can_trade, _ = bot.can_trade()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "actions_taken": len(actions),
        "actions": actions,
        "bot_status": bot.get_status(),
    }
