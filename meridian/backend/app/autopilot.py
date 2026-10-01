"""
Meridian Autopilot Trading Engine

Strategies:
- Mean Reversion: Buy on dips (RSI < 30, price below lower Bollinger)
- Momentum: Ride trends, sell on exhaustion (RSI > 70, bearish divergence)
- AI Signal: Use PLA deep analysis verdict for entry/exit decisions
- Risk Management: Position sizing, stop-losses, max drawdown limits

The engine evaluates each position every cycle and generates trade signals.
It can run in MANUAL mode (suggestions only) or AUTOPILOT mode (auto-execute).
"""

import asyncio
import httpx
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class TradingMode(str, Enum):
    MANUAL = "manual"          # Generate signals only, human approves
    SEMI_AUTO = "semi_auto"    # Auto-execute low-risk, manual for high-risk
    AUTOPILOT = "autopilot"    # Full auto (requires explicit opt-in)


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _calculate_position_size(
    buying_power: float,
    risk_per_trade_pct: float = 2.0,
    stop_loss_pct: float = 5.0,
    price: float = 0,
) -> float:
    """Kelly-inspired position sizing. Risk X% of portfolio per trade."""
    risk_amount = buying_power * (risk_per_trade_pct / 100)
    if stop_loss_pct > 0 and price > 0:
        shares = risk_amount / (price * stop_loss_pct / 100)
        return max(round(shares, 4), 0.01)  # Fractional shares OK
    return round(risk_amount / price, 4) if price > 0 else 0


class AutopilotEngine:
    def __init__(
        self,
        pla_api_url: str = "http://localhost:30000",
        mode: TradingMode = TradingMode.MANUAL,
        max_position_pct: float = 10.0,    # Max 10% of portfolio per stock
        risk_per_trade_pct: float = 2.0,   # Risk 2% per trade
        max_daily_trades: int = 10,
        stop_loss_pct: float = 5.0,
        take_profit_pct: float = 15.0,
    ):
        self.pla_api = pla_api_url
        self.mode = mode
        self.max_position_pct = max_position_pct
        self.risk_per_trade = risk_per_trade_pct
        self.max_daily_trades = max_daily_trades
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trade_log: List[Dict] = []
        self.daily_trade_count = 0
        self.last_reset = datetime.utcnow().date()

    def _reset_daily_counters(self):
        today = datetime.utcnow().date()
        if today != self.last_reset:
            self.daily_trade_count = 0
            self.last_reset = today

    async def _get_pla_analysis(self, symbol: str) -> Dict:
        """Fetch deep analysis from PLA backend."""
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    f"{self.pla_api}/api/portfolio/deep-analysis/{symbol}",
                    timeout=60,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.error(f"PLA analysis error for {symbol}: {e}")
        return {}

    def _evaluate_buy_signal(self, analysis: Dict, position: Optional[Dict] = None) -> Dict:
        """Evaluate if we should buy based on all signals."""
        signals = []
        score = 0  # -100 to +100

        # Already holding? Different logic
        if position:
            return {"signal": SignalType.HOLD, "reason": "Already holding position"}

        # Technical signals
        tech = analysis.get("technical_indicators", {})
        rsi_raw = tech.get("rsi", 50)
        macd = tech.get("macd", {})
        bollinger = tech.get("bollinger_bands", tech.get("bollinger", {}))

        rsi_val = rsi_raw.get("value", 50) if isinstance(rsi_raw, dict) else float(rsi_raw)
        if rsi_val < 30:
            score += 25
            signals.append(f"RSI oversold ({rsi_val:.0f})")
        elif rsi_val < 40:
            score += 10
            signals.append(f"RSI approaching oversold ({rsi_val:.0f})")
        elif rsi_val > 70:
            score -= 20
            signals.append(f"RSI overbought ({rsi_val:.0f})")

        macd_trend = macd.get("trend", macd.get("signal", "")) if isinstance(macd, dict) else ""
        if macd_trend == "bullish":
            score += 15
            signals.append("MACD bullish crossover")
        elif macd_trend == "bearish":
            score -= 15

        bb_pos = bollinger.get("position", bollinger.get("signal", "")) if isinstance(bollinger, dict) else ""
        if bb_pos in ("oversold", "below_lower"):
            score += 20
            signals.append("Price below lower Bollinger Band")

        # Elliott Wave
        elliott = analysis.get("elliott_wave", {})
        wave_pos = elliott.get("wave_position", {})
        if wave_pos.get("direction") == "bullish":
            score += 15
            signals.append(f"Elliott Wave bullish ({wave_pos.get('position', '')})")
        elif wave_pos.get("direction") == "bearish":
            score -= 15

        # Sentiment
        sentiment = analysis.get("market_sentiment", {})
        sent_score = sentiment.get("composite_score", 0)
        if sent_score > 0.2:
            score += 15
            signals.append(f"Positive sentiment ({sent_score:.2f})")
        elif sent_score < -0.2:
            score -= 15
            signals.append(f"Negative sentiment ({sent_score:.2f})")

        # Institutional
        inst = analysis.get("institutional_analysis", {})
        accum = inst.get("accumulation_signals", {})
        if accum.get("institutional_accumulation"):
            score += 20
            signals.append("Institutional accumulation detected")
        if accum.get("insider_buying"):
            score += 15
            signals.append("Insider buying detected")
        if accum.get("dump_risk"):
            score -= 30
            signals.append("⚠️ Dump risk: insider selling")

        # Analyst upside
        upside = inst.get("upside_potential_pct")
        if upside and upside > 20:
            score += 15
            signals.append(f"Analyst upside: {upside}%")
        elif upside and upside < -10:
            score -= 15

        # Weekly posture
        weekly = analysis.get("weekly_posture", {})
        posture = weekly.get("posture", "")
        if "bullish" in posture:
            score += 10
        elif "bearish" in posture:
            score -= 10

        # Decision
        if score >= 40:
            return {
                "signal": SignalType.BUY,
                "confidence": min(score, 100),
                "risk": RiskLevel.LOW if score >= 60 else RiskLevel.MEDIUM,
                "reasons": signals,
            }
        elif score >= 20:
            return {
                "signal": SignalType.BUY,
                "confidence": score,
                "risk": RiskLevel.MEDIUM,
                "reasons": signals,
            }
        else:
            return {
                "signal": SignalType.HOLD,
                "confidence": abs(score),
                "reasons": signals,
            }

    def _evaluate_sell_signal(self, analysis: Dict, position: Dict) -> Dict:
        """Evaluate if we should sell an existing position."""
        signals = []
        score = 0  # Positive = sell pressure

        pnl_pct = position.get("pnl_pct", 0)
        price = analysis.get("current_price", position.get("current_price", 0))

        # Take profit trigger
        if pnl_pct >= self.take_profit_pct:
            return {
                "signal": SignalType.TAKE_PROFIT,
                "confidence": 90,
                "risk": RiskLevel.LOW,
                "reasons": [f"Take profit target hit ({pnl_pct:.1f}% gain)"],
            }

        # Stop loss trigger
        if pnl_pct <= -self.stop_loss_pct:
            return {
                "signal": SignalType.STOP_LOSS,
                "confidence": 95,
                "risk": RiskLevel.HIGH,
                "reasons": [f"Stop loss triggered ({pnl_pct:.1f}% loss)"],
            }

        # Technical sell signals
        tech = analysis.get("technical_indicators", {})
        rsi_raw = tech.get("rsi", 50)
        rsi_val = rsi_raw.get("value", 50) if isinstance(rsi_raw, dict) else float(rsi_raw)
        if rsi_val > 75:
            score += 25
            signals.append(f"RSI overbought ({rsi_val:.0f})")

        macd = tech.get("macd", {})
        macd_trend = macd.get("trend", macd.get("signal", "")) if isinstance(macd, dict) else ""
        if macd_trend == "bearish":
            score += 20
            signals.append("MACD bearish crossover")

        bb = tech.get("bollinger_bands", tech.get("bollinger", {}))
        bb_pos = bb.get("position", bb.get("signal", "")) if isinstance(bb, dict) else ""
        if bb_pos in ("overbought", "above_upper"):
            score += 15

        # Sentiment turning negative
        sentiment = analysis.get("market_sentiment", {})
        if sentiment.get("composite_score", 0) < -0.3:
            score += 20
            signals.append("Sentiment turning negative")

        # Insider selling
        inst = analysis.get("institutional_analysis", {})
        if inst.get("accumulation_signals", {}).get("dump_risk"):
            score += 30
            signals.append("⚠️ Insider selling detected")

        # Weekly bearish
        weekly = analysis.get("weekly_posture", {})
        if "bearish" in weekly.get("posture", ""):
            score += 15
            signals.append(f"Weekly posture: {weekly.get('posture')}")

        if score >= 40:
            return {
                "signal": SignalType.SELL,
                "confidence": min(score, 100),
                "risk": RiskLevel.MEDIUM if score < 60 else RiskLevel.HIGH,
                "reasons": signals,
            }
        else:
            return {
                "signal": SignalType.HOLD,
                "confidence": 100 - score,
                "reasons": signals or ["No sell triggers active"],
            }

    async def evaluate_watchlist(
        self,
        symbols: List[str],
        portfolio: Dict,
    ) -> List[Dict]:
        """
        Evaluate a watchlist of symbols and generate trade signals.

        Args:
            symbols: List of ticker symbols to evaluate
            portfolio: Current portfolio from RobinhoodClient.get_portfolio()

        Returns:
            List of trade signals with confidence scores
        """
        self._reset_daily_counters()

        if self.daily_trade_count >= self.max_daily_trades:
            return [{"warning": f"Daily trade limit reached ({self.max_daily_trades})"}]

        holdings = {p["symbol"]: p for p in portfolio.get("positions", [])}
        buying_power = portfolio.get("buying_power", 0)

        trade_signals = []

        # Fetch analyses in parallel (max 5 concurrent)
        sem = asyncio.Semaphore(5)

        async def _analyze(symbol: str):
            async with sem:
                return symbol, await self._get_pla_analysis(symbol)

        tasks = [_analyze(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue

            symbol, analysis = result
            if not analysis or "error" in analysis:
                continue

            position = holdings.get(symbol)
            price = analysis.get("current_price", 0)

            if position:
                # Evaluate sell signal for existing position
                signal = self._evaluate_sell_signal(analysis, position)
            else:
                # Evaluate buy signal for new position
                signal = self._evaluate_buy_signal(analysis, position)

            if signal["signal"] != SignalType.HOLD:
                # Calculate position size for buys
                if signal["signal"] == SignalType.BUY and price > 0:
                    qty = _calculate_position_size(
                        buying_power, self.risk_per_trade, self.stop_loss_pct, price,
                    )
                    max_qty = (buying_power * self.max_position_pct / 100) / price
                    qty = min(qty, max_qty)
                    signal["suggested_quantity"] = round(qty, 4)
                    signal["estimated_cost"] = round(qty * price, 2)
                    signal["stop_loss_price"] = round(price * (1 - self.stop_loss_pct / 100), 2)
                    signal["take_profit_price"] = round(price * (1 + self.take_profit_pct / 100), 2)

                elif signal["signal"] in (SignalType.SELL, SignalType.TAKE_PROFIT, SignalType.STOP_LOSS):
                    if position:
                        signal["suggested_quantity"] = position.get("quantity", 0)
                        signal["estimated_proceeds"] = round(
                            position.get("quantity", 0) * price, 2
                        )

            signal["symbol"] = symbol
            signal["price"] = price
            signal["timestamp"] = datetime.utcnow().isoformat()
            signal["mode"] = self.mode.value

            trade_signals.append(signal)

        # Sort by confidence (highest first)
        trade_signals.sort(
            key=lambda x: x.get("confidence", 0), reverse=True,
        )

        return trade_signals

    def log_trade(self, trade: Dict):
        """Log an executed trade for tracking."""
        trade["executed_at"] = datetime.utcnow().isoformat()
        self.trade_log.append(trade)
        self.daily_trade_count += 1

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        return self.trade_log[-limit:]

    def get_stats(self) -> Dict:
        """Performance statistics."""
        if not self.trade_log:
            return {"total_trades": 0}

        buys = [t for t in self.trade_log if t.get("signal") == "buy"]
        sells = [t for t in self.trade_log if t.get("signal") in ("sell", "take_profit", "stop_loss")]

        return {
            "total_trades": len(self.trade_log),
            "buys": len(buys),
            "sells": len(sells),
            "daily_trades_today": self.daily_trade_count,
            "mode": self.mode.value,
        }
