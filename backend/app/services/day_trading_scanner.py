"""
Day Trading Scanner & Paper Trading Engine
============================================

Autonomous market scanner that:
1. Scans a watchlist universe for intraday opportunities
2. Generates buy/sell signals from technical indicators (RSI, MACD, VWAP, Bollinger)
3. Manages a paper trading portfolio with P&L tracking
4. Keeps a trade journal with entry/exit reasoning

All trades are PAPER only — no real broker integration.
Uses yfinance for price data (free, no API key).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "AVGO", "TSM", "PLTR", "ARM", "SMCI", "MRVL", "CRM", "SNOW",
    "NFLX", "SPY", "QQQ", "COIN", "MSTR", "SOFI", "RIVN", "NIO",
]

SCAN_UNIVERSE_EXTENDED = [
    *DEFAULT_WATCHLIST,
    "ORCL", "ANET", "CRWD", "NET", "MU", "QCOM", "INTC", "BA",
    "JPM", "GS", "V", "MA", "UNH", "LLY", "PFE", "XOM", "CVX",
]

# Paper trading config
INITIAL_CAPITAL = 100_000.0
MAX_POSITION_PCT = 0.075  # 7.5% of portfolio per trade
MAX_OPEN_POSITIONS = 15
DEFAULT_STOP_LOSS_PCT = 0.02  # 2% stop loss
DEFAULT_TAKE_PROFIT_PCT = 0.04  # 4% take profit (2:1 R/R)


class SignalType(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TradeStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED_OUT = "STOPPED_OUT"
    TAKE_PROFIT = "TAKE_PROFIT"


@dataclass
class ScanResult:
    symbol: str
    price: float
    signal: SignalType
    confidence: float  # 0-100
    reasons: List[str]
    indicators: Dict[str, Any]
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class PaperTrade:
    id: str
    symbol: str
    action: str  # BUY or SELL
    entry_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    entry_time: str
    status: str = "OPEN"
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    reason_entry: str = ""
    reason_exit: str = ""
    signals_at_entry: List[str] = field(default_factory=list)


@dataclass
class Portfolio:
    cash: float = INITIAL_CAPITAL
    initial_capital: float = INITIAL_CAPITAL
    trades: List[PaperTrade] = field(default_factory=list)
    trade_counter: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def open_trades(self) -> List[PaperTrade]:
        return [t for t in self.trades if t.status == "OPEN"]

    @property
    def closed_trades(self) -> List[PaperTrade]:
        return [t for t in self.trades if t.status != "OPEN"]

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.closed_trades)

    @property
    def win_rate(self) -> float:
        closed = self.closed_trades
        if not closed:
            return 0.0
        wins = sum(1 for t in closed if t.pnl > 0)
        return round(wins / len(closed) * 100, 1)

    @property
    def portfolio_value(self) -> float:
        return self.cash + sum(
            t.entry_price * t.quantity for t in self.open_trades
        )


# ─────────────────────────────────────────────────────────────────────────────
# Persistence (JSON file — simple but effective)
# ─────────────────────────────────────────────────────────────────────────────

_DATA_DIR = Path(os.environ.get("AVIRA_DATA_DIR", "/tmp/avira_trading"))
_DATA_DIR.mkdir(parents=True, exist_ok=True)


def _portfolio_path(user_id: str = "default") -> Path:
    return _DATA_DIR / f"paper_portfolio_{user_id}.json"


def _journal_path() -> Path:
    return _DATA_DIR / "trade_journal.json"


def _scan_history_path() -> Path:
    return _DATA_DIR / "scan_history.json"


def load_portfolio(user_id: str = "default") -> Portfolio:
    p = _portfolio_path(user_id)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            trades = [PaperTrade(**t) for t in data.get("trades", [])]
            return Portfolio(
                cash=data.get("cash", INITIAL_CAPITAL),
                initial_capital=data.get("initial_capital", INITIAL_CAPITAL),
                trades=trades,
                trade_counter=data.get("trade_counter", 0),
                created_at=data.get("created_at", ""),
            )
        except Exception as e:
            logger.warning("Failed to load portfolio for %s: %s", user_id, e)
    return Portfolio()


def save_portfolio(p: Portfolio, user_id: str = "default") -> None:
    data = {
        "cash": p.cash,
        "initial_capital": p.initial_capital,
        "trade_counter": p.trade_counter,
        "created_at": p.created_at,
        "trades": [asdict(t) for t in p.trades],
    }
    _portfolio_path(user_id).write_text(json.dumps(data, indent=2, default=str))


def save_scan_results(results: List[ScanResult]) -> None:
    history = []
    hp = _scan_history_path()
    if hp.exists():
        try:
            history = json.loads(hp.read_text())
        except Exception:
            pass
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "count": len(results),
        "signals": [asdict(r) for r in results if r.signal in (SignalType.STRONG_BUY, SignalType.BUY, SignalType.SELL, SignalType.STRONG_SELL)],
    }
    history.append(entry)
    # Keep last 100 scans
    history = history[-100:]
    hp.write_text(json.dumps(history, indent=2, default=str))


def get_scan_history(limit: int = 20) -> List[Dict]:
    hp = _scan_history_path()
    if hp.exists():
        try:
            history = json.loads(hp.read_text())
            return history[-limit:]
        except Exception:
            pass
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Technical indicator calculations
# ─────────────────────────────────────────────────────────────────────────────

def _rsi(prices: np.ndarray, period: int = 14) -> float:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _macd(prices: np.ndarray) -> Tuple[float, float, float]:
    """MACD line, signal line, histogram."""
    if len(prices) < 26:
        return 0.0, 0.0, 0.0

    def ema(data, span):
        alpha = 2 / (span + 1)
        result = np.zeros_like(data, dtype=float)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd_line = ema12 - ema26
    signal = ema(macd_line[-9:], 9) if len(macd_line) >= 9 else np.array([0.0])
    hist = macd_line[-1] - signal[-1]
    return round(float(macd_line[-1]), 4), round(float(signal[-1]), 4), round(float(hist), 4)


def _bollinger(prices: np.ndarray, period: int = 20, std_mult: float = 2.0) -> Tuple[float, float, float]:
    """Bollinger Bands: lower, middle, upper."""
    if len(prices) < period:
        mid = float(prices[-1]) if len(prices) > 0 else 0.0
        return mid * 0.98, mid, mid * 1.02
    window = prices[-period:]
    mid = float(np.mean(window))
    std = float(np.std(window))
    return round(mid - std_mult * std, 2), round(mid, 2), round(mid + std_mult * std, 2)


def _vwap(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, volumes: np.ndarray) -> float:
    """Volume Weighted Average Price."""
    if len(closes) == 0 or np.sum(volumes) == 0:
        return float(closes[-1]) if len(closes) > 0 else 0.0
    typical = (highs + lows + closes) / 3
    return round(float(np.sum(typical * volumes) / np.sum(volumes)), 2)


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    """Average True Range."""
    if len(closes) < 2:
        return 0.0
    tr_values = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)
    if not tr_values:
        return 0.0
    return round(float(np.mean(tr_values[-period:])), 4)


def _ema_val(prices: np.ndarray, span: int) -> float:
    """Current EMA value."""
    if len(prices) < 2:
        return float(prices[-1]) if len(prices) > 0 else 0.0
    alpha = 2 / (span + 1)
    val = float(prices[0])
    for p in prices[1:]:
        val = alpha * float(p) + (1 - alpha) * val
    return round(val, 4)


# ─────────────────────────────────────────────────────────────────────────────
# Signal generation
# ─────────────────────────────────────────────────────────────────────────────

def _generate_signal(
    symbol: str,
    closes: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    volumes: np.ndarray,
) -> ScanResult:
    """Generate trading signal from price data using multiple indicators."""
    price = float(closes[-1])
    reasons = []
    score = 0  # -100 to +100

    # 1. RSI
    rsi = _rsi(closes)
    if rsi < 30:
        score += 25
        reasons.append(f"RSI oversold ({rsi})")
    elif rsi < 40:
        score += 10
        reasons.append(f"RSI approaching oversold ({rsi})")
    elif rsi > 70:
        score -= 25
        reasons.append(f"RSI overbought ({rsi})")
    elif rsi > 60:
        score -= 10
        reasons.append(f"RSI approaching overbought ({rsi})")

    # 2. MACD
    macd_line, signal_line, histogram = _macd(closes)
    if histogram > 0 and macd_line > signal_line:
        score += 20
        reasons.append("MACD bullish crossover")
    elif histogram < 0 and macd_line < signal_line:
        score -= 20
        reasons.append("MACD bearish crossover")

    # 3. Bollinger Bands
    bb_lower, bb_mid, bb_upper = _bollinger(closes)
    bb_pct = (price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
    if price <= bb_lower * 1.005:
        score += 20
        reasons.append(f"Price at lower Bollinger Band (${bb_lower:.2f})")
    elif price >= bb_upper * 0.995:
        score -= 20
        reasons.append(f"Price at upper Bollinger Band (${bb_upper:.2f})")

    # 4. VWAP
    vwap = _vwap(highs, lows, closes, volumes)
    if price > vwap * 1.01:
        score += 10
        reasons.append(f"Price above VWAP (${vwap:.2f})")
    elif price < vwap * 0.99:
        score -= 5
        reasons.append(f"Price below VWAP (${vwap:.2f})")

    # 5. EMA trend
    ema9 = _ema_val(closes, 9)
    ema21 = _ema_val(closes, 21)
    ema50 = _ema_val(closes, 50) if len(closes) >= 50 else ema21
    if ema9 > ema21 > ema50:
        score += 15
        reasons.append("EMA stack bullish (9>21>50)")
    elif ema9 < ema21 < ema50:
        score -= 15
        reasons.append("EMA stack bearish (9<21<50)")

    # 6. Volume spike
    if len(volumes) >= 20:
        avg_vol = float(np.mean(volumes[-20:]))
        curr_vol = float(volumes[-1])
        if avg_vol > 0 and curr_vol > avg_vol * 1.5:
            vol_mult = curr_vol / avg_vol
            if score > 0:
                score += 10
            else:
                score -= 10
            reasons.append(f"Volume spike {vol_mult:.1f}x average")

    # 7. ATR for position sizing
    atr = _atr(highs, lows, closes)

    # Determine signal
    if score >= 50:
        signal = SignalType.STRONG_BUY
    elif score >= 20:
        signal = SignalType.BUY
    elif score <= -50:
        signal = SignalType.STRONG_SELL
    elif score <= -20:
        signal = SignalType.SELL
    else:
        signal = SignalType.HOLD

    confidence = min(100, abs(score))

    # Entry / stop / targets
    entry = price
    if signal in (SignalType.STRONG_BUY, SignalType.BUY):
        stop = round(entry - max(atr * 1.5, entry * DEFAULT_STOP_LOSS_PCT), 2)
        tp1 = round(entry + (entry - stop) * 2, 2)  # 2:1 R/R
        tp2 = round(entry + (entry - stop) * 3, 2)  # 3:1 R/R
    elif signal in (SignalType.STRONG_SELL, SignalType.SELL):
        stop = round(entry + max(atr * 1.5, entry * DEFAULT_STOP_LOSS_PCT), 2)
        tp1 = round(entry - (stop - entry) * 2, 2)
        tp2 = round(entry - (stop - entry) * 3, 2)
    else:
        stop = round(entry - atr * 1.5, 2)
        tp1 = round(entry + atr * 2, 2)
        tp2 = round(entry + atr * 3, 2)

    risk = abs(entry - stop)
    reward = abs(tp1 - entry)
    rr = round(reward / risk, 2) if risk > 0 else 0.0

    return ScanResult(
        symbol=symbol,
        price=price,
        signal=signal,
        confidence=confidence,
        reasons=reasons,
        indicators={
            "rsi": rsi,
            "macd_line": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": histogram,
            "bollinger_lower": bb_lower,
            "bollinger_mid": bb_mid,
            "bollinger_upper": bb_upper,
            "bollinger_pct": round(bb_pct, 3),
            "vwap": vwap,
            "ema_9": ema9,
            "ema_21": ema21,
            "atr": atr,
            "score": score,
        },
        entry_price=entry,
        stop_loss=stop,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Market Scanner (uses yfinance)
# ─────────────────────────────────────────────────────────────────────────────

_scan_cache: Dict[str, Tuple[float, Any]] = {}
_SCAN_TTL = 120  # 2 min cache


async def scan_market(symbols: Optional[List[str]] = None, period: str = "5d", interval: str = "15m") -> List[ScanResult]:
    """Scan a list of symbols and return trading signals, sorted by confidence."""
    symbols = symbols or DEFAULT_WATCHLIST

    def _do_scan():
        import yfinance as yf
        results = []
        for sym in symbols:
            try:
                tk = yf.Ticker(sym)
                df = tk.history(period=period, interval=interval)
                if df.empty or len(df) < 20:
                    continue
                closes = df["Close"].values.astype(float)
                highs = df["High"].values.astype(float)
                lows = df["Low"].values.astype(float)
                volumes = df["Volume"].values.astype(float)
                result = _generate_signal(sym, closes, highs, lows, volumes)
                results.append(result)
            except Exception as e:
                logger.debug("scan failed for %s: %s", sym, e)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    cache_key = f"scan:{','.join(sorted(symbols))}:{period}:{interval}"
    now = time.time()
    if cache_key in _scan_cache:
        ts, cached = _scan_cache[cache_key]
        if now - ts < _SCAN_TTL:
            return cached

    results = await asyncio.get_event_loop().run_in_executor(None, _do_scan)
    _scan_cache[cache_key] = (now, results)
    save_scan_results(results)
    return results


async def scan_single(symbol: str) -> ScanResult:
    """Scan a single symbol and return its signal."""
    results = await scan_market([symbol])
    if results:
        return results[0]
    raise ValueError(f"Could not scan {symbol}")


# ─────────────────────────────────────────────────────────────────────────────
# Paper Trading Engine
# ─────────────────────────────────────────────────────────────────────────────

def execute_paper_trade(symbol: str, action: str, scan: ScanResult, quantity: Optional[int] = None, user_id: str = "default") -> PaperTrade:
    """Execute a paper trade based on scan result."""
    portfolio = load_portfolio(user_id)

    if action == "BUY":
        # Calculate position size
        max_spend = portfolio.cash * MAX_POSITION_PCT
        price = scan.entry_price
        if quantity is None:
            quantity = int(max_spend / price) if price > 0 else 0
        if quantity <= 0:
            raise ValueError("Insufficient capital for trade")
        cost = price * quantity
        if cost > portfolio.cash:
            raise ValueError(f"Cost ${cost:.2f} exceeds available cash ${portfolio.cash:.2f}")
        if len(portfolio.open_trades) >= MAX_OPEN_POSITIONS:
            raise ValueError(f"Max {MAX_OPEN_POSITIONS} open positions reached")

        portfolio.trade_counter += 1
        trade = PaperTrade(
            id=f"PT-{portfolio.trade_counter:04d}",
            symbol=symbol,
            action="BUY",
            entry_price=price,
            quantity=quantity,
            stop_loss=scan.stop_loss,
            take_profit=scan.take_profit_1,
            entry_time=datetime.now(timezone.utc).isoformat(),
            reason_entry="; ".join(scan.reasons[:3]),
            signals_at_entry=[f"{scan.signal.value} conf={scan.confidence}%"],
        )
        portfolio.cash -= cost
        portfolio.trades.append(trade)
        save_portfolio(portfolio, user_id)
        return trade

    elif action == "SELL":
        # Find open position for this symbol
        open_pos = [t for t in portfolio.open_trades if t.symbol == symbol]
        if not open_pos:
            raise ValueError(f"No open position for {symbol}")
        trade = open_pos[0]
        trade.exit_price = scan.price
        trade.exit_time = datetime.now(timezone.utc).isoformat()
        trade.pnl = round((trade.exit_price - trade.entry_price) * trade.quantity, 2)
        trade.pnl_pct = round((trade.exit_price - trade.entry_price) / trade.entry_price * 100, 2)
        trade.status = "CLOSED"
        trade.reason_exit = "; ".join(scan.reasons[:3])
        portfolio.cash += trade.exit_price * trade.quantity
        save_portfolio(portfolio, user_id)
        return trade

    raise ValueError(f"Unknown action: {action}")


def check_stops_and_targets(user_id: str = "default") -> List[Dict[str, Any]]:
    """Check all open positions against current prices for stop-loss/take-profit hits."""
    portfolio = load_portfolio(user_id)
    if not portfolio.open_trades:
        return []

    import yfinance as yf
    triggered = []

    for trade in portfolio.open_trades:
        try:
            tk = yf.Ticker(trade.symbol)
            info = tk.fast_info
            current_price = float(getattr(info, 'last_price', 0) or 0)
            if current_price <= 0:
                hist = tk.history(period="1d")
                if not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])

            if current_price <= 0:
                continue

            if current_price <= trade.stop_loss:
                trade.exit_price = current_price
                trade.exit_time = datetime.now(timezone.utc).isoformat()
                trade.pnl = round((current_price - trade.entry_price) * trade.quantity, 2)
                trade.pnl_pct = round((current_price - trade.entry_price) / trade.entry_price * 100, 2)
                trade.status = "STOPPED_OUT"
                trade.reason_exit = f"Stop loss triggered at ${current_price:.2f}"
                portfolio.cash += current_price * trade.quantity
                triggered.append({"trade_id": trade.id, "symbol": trade.symbol, "type": "STOP_LOSS", "price": current_price, "pnl": trade.pnl})

            elif current_price >= trade.take_profit:
                trade.exit_price = current_price
                trade.exit_time = datetime.now(timezone.utc).isoformat()
                trade.pnl = round((current_price - trade.entry_price) * trade.quantity, 2)
                trade.pnl_pct = round((current_price - trade.entry_price) / trade.entry_price * 100, 2)
                trade.status = "TAKE_PROFIT"
                trade.reason_exit = f"Take profit hit at ${current_price:.2f}"
                portfolio.cash += current_price * trade.quantity
                triggered.append({"trade_id": trade.id, "symbol": trade.symbol, "type": "TAKE_PROFIT", "price": current_price, "pnl": trade.pnl})

        except Exception as e:
            logger.debug("stop check failed for %s: %s", trade.symbol, e)

    if triggered:
        save_portfolio(portfolio, user_id)
    return triggered


def get_portfolio_summary(user_id: str = "default") -> Dict[str, Any]:
    """Return current portfolio state with P&L."""
    p = load_portfolio(user_id)

    # Get current prices for open positions
    open_positions = []
    unrealized_pnl = 0.0
    for t in p.open_trades:
        try:
            import yfinance as yf
            tk = yf.Ticker(t.symbol)
            hist = tk.history(period="1d")
            current_price = float(hist["Close"].iloc[-1]) if not hist.empty else t.entry_price
        except Exception:
            current_price = t.entry_price

        upnl = round((current_price - t.entry_price) * t.quantity, 2)
        unrealized_pnl += upnl
        open_positions.append({
            **asdict(t),
            "current_price": current_price,
            "unrealized_pnl": upnl,
            "unrealized_pnl_pct": round((current_price - t.entry_price) / t.entry_price * 100, 2) if t.entry_price > 0 else 0,
        })

    return {
        "cash": round(p.cash, 2),
        "initial_capital": p.initial_capital,
        "portfolio_value": round(p.portfolio_value + unrealized_pnl, 2),
        "total_return_pct": round((p.portfolio_value + unrealized_pnl - p.initial_capital) / p.initial_capital * 100, 2),
        "realized_pnl": round(p.total_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "win_rate": p.win_rate,
        "total_trades": len(p.trades),
        "open_positions": open_positions,
        "closed_trades": [asdict(t) for t in p.closed_trades[-20:]],
        "created_at": p.created_at,
    }


def reset_portfolio(user_id: str = "default") -> Dict[str, Any]:
    """Reset paper portfolio to initial state."""
    p = Portfolio()
    save_portfolio(p, user_id)
    return {"status": "reset", "cash": p.cash, "user_id": user_id}


# ─────────────────────────────────────────────────────────────────────────────
# Auto-scanner: run full scan + auto-execute signals above threshold
# ─────────────────────────────────────────────────────────────────────────────

async def auto_scan_and_trade(
    symbols: Optional[List[str]] = None,
    auto_execute: bool = False,
    min_confidence: int = 60,
    user_id: str = "default",
    max_buys: Optional[int] = 3,
    max_sells: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Full autonomous scan + optional auto-trade for a specific user.
    If auto_execute=True, will paper-trade STRONG_BUY signals above min_confidence.
    Also checks existing positions for stop/TP triggers.
    """
    results = await scan_market(symbols)

    # Check stops/targets on open positions
    triggered = await asyncio.get_event_loop().run_in_executor(None, check_stops_and_targets, user_id)

    # Filter actionable signals
    buys = [r for r in results if r.signal in (SignalType.STRONG_BUY, SignalType.BUY) and r.confidence >= min_confidence]
    sells = [r for r in results if r.signal in (SignalType.STRONG_SELL, SignalType.SELL) and r.confidence >= min_confidence]

    executed_trades = []
    if auto_execute:
        portfolio = load_portfolio(user_id)
        # Auto-buy strong signals
        buy_slice = buys[:max_buys] if max_buys is not None else buys
        for scan in buy_slice:
            if len(portfolio.open_trades) >= MAX_OPEN_POSITIONS:
                break
            # Skip if already have position
            if any(t.symbol == scan.symbol for t in portfolio.open_trades):
                continue
            try:
                trade = execute_paper_trade(scan.symbol, "BUY", scan, user_id=user_id)
                executed_trades.append(asdict(trade))
                portfolio = load_portfolio(user_id)  # Refresh
            except Exception as e:
                logger.debug("auto-trade %s failed for %s: %s", scan.symbol, user_id, e)

        # Auto-sell if we have position and signal is sell
        sell_slice = sells[:max_sells] if max_sells is not None else sells
        for scan in sell_slice:
            if any(t.symbol == scan.symbol for t in portfolio.open_trades):
                try:
                    trade = execute_paper_trade(scan.symbol, "SELL", scan, user_id=user_id)
                    executed_trades.append(asdict(trade))
                except Exception as e:
                    logger.debug("auto-sell %s failed for %s: %s", scan.symbol, user_id, e)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scanned": len(results),
        "buy_signals": len(buys),
        "sell_signals": len(sells),
        "top_buys": [asdict(r) for r in buys[:5]],
        "top_sells": [asdict(r) for r in sells[:5]],
        "all_signals": [asdict(r) for r in results],
        "triggered_stops": triggered,
        "executed_trades": executed_trades,
        "auto_execute": auto_execute,
    }
