"""
Intelligent Stock Trading Assistant Service

Features:
- Real-time stock data from multiple sources
- Market sentiment analysis
- Buy/Sell ratings with AI analysis
- Options trading recommendations
- Daily stock picks (short-term, long-term)
- News aggregation and analysis
"""
import logging
import httpx
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)


class Rating(str, Enum):
    """Stock rating."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class TimeHorizon(str, Enum):
    """Investment time horizon."""
    DAY_TRADE = "day_trade"
    SHORT_TERM = "short_term"  # 1-4 weeks
    MEDIUM_TERM = "medium_term"  # 1-6 months
    LONG_TERM = "long_term"  # 6+ months


class StockIntelligence:
    """Intelligent stock analysis and recommendations."""
    
    def __init__(self):
        self.alpha_vantage_key = "demo"  # Replace with real API key
        self.finnhub_key = "demo"  # Replace with real API key
    
    async def get_historical_prices(self, symbol: str, period: str = "1m", interval: str = "1d") -> Dict[str, Any]:
        """
        Get historical price data for charts with OHLC candlestick data.
        Uses yfinance for reliable real-time data.

        Periods: 1d, 1w, 1m, 3m, 1y, 5y
        Intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
        """
        import asyncio
        return await asyncio.to_thread(self._fetch_historical_yf, symbol, period, interval)

    def _fetch_historical_yf(self, symbol: str, period: str, interval: str) -> Dict[str, Any]:
        """Synchronous yfinance fetch (run in thread pool)."""
        try:
            import yfinance as yf

            period_map = {
                "1d": "1d", "1w": "5d", "1m": "1mo",
                "3m": "3mo", "1y": "1y", "5y": "5y",
            }
            interval_map = {
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
                "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk",
            }
            yf_period = period_map.get(period, "1mo")
            yf_interval = interval_map.get(interval, "1d")

            # yfinance restriction: 1m data only available for last 7 days
            if yf_interval == "1m" and yf_period not in ("1d", "5d"):
                yf_interval = "5m"

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=yf_period, interval=yf_interval)

            if df.empty:
                logger.warning(f"yfinance returned empty data for {symbol}, using mock")
                return self._generate_mock_historical(symbol, period, interval)

            prices = []
            for ts, row in df.iterrows():
                prices.append({
                    "timestamp": int(ts.timestamp()),
                    "date": ts.isoformat(),
                    "price": round(float(row["Close"]), 2),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]) if row["Volume"] else 0,
                })

            logger.info(f"yfinance: {len(prices)} points for {symbol} ({period}/{interval})")
            return {
                "success": True,
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "data_points": len(prices),
                "prices": prices,
            }
        except Exception as e:
            logger.error(f"yfinance error for {symbol}: {e}")
            return self._generate_mock_historical(symbol, period, interval)
    
    def _generate_mock_historical(self, symbol: str, period: str, interval: str = "1d") -> Dict[str, Any]:
        """Generate realistic mock historical data with OHLC."""
        import random
        import hashlib
        
        # Use symbol hash for consistent base price
        symbol_hash = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
        base_price = 50 + (symbol_hash % 450)  # Price between 50-500
        
        # Calculate number of points and time delta based on period and interval
        interval_to_delta = {
            "1m": timedelta(minutes=1),
            "5m": timedelta(minutes=5),
            "15m": timedelta(minutes=15),
            "30m": timedelta(minutes=30),
            "1h": timedelta(hours=1),
            "4h": timedelta(hours=4),
            "1d": timedelta(days=1),
            "1w": timedelta(weeks=1)
        }
        
        period_to_points = {
            "1d": {"1m": 390, "5m": 78, "15m": 26, "30m": 13, "1h": 7, "1d": 1},
            "1w": {"5m": 390, "15m": 130, "30m": 65, "1h": 35, "4h": 10, "1d": 5},
            "1m": {"15m": 500, "30m": 250, "1h": 150, "4h": 40, "1d": 22},
            "3m": {"1h": 450, "4h": 115, "1d": 65, "1w": 13},
            "1y": {"1d": 252, "1w": 52},
            "5y": {"1d": 1260, "1w": 260}
        }
        
        delta = interval_to_delta.get(interval, timedelta(days=1))
        num_points = period_to_points.get(period, {}).get(interval, 50)
        
        prices = []
        current_price = base_price
        now = datetime.now()
        
        # Generate price movements with some trend
        trend = random.choice([-0.0005, 0, 0.0005, 0.001])
        volatility = 0.015 if interval in ["1m", "5m", "15m"] else 0.025
        
        for i in range(num_points):
            timestamp = now - delta * (num_points - i - 1)
            
            # Generate OHLC data
            open_price = current_price
            change = random.gauss(trend, volatility)
            close_price = max(1, current_price * (1 + change))
            
            # High and low within the candle
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility * 0.5)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility * 0.5)))
            
            prices.append({
                "timestamp": int(timestamp.timestamp()),
                "date": timestamp.isoformat(),
                "price": round(close_price, 2),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": random.randint(100000, 10000000)
            })
            
            current_price = close_price
        
        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "data_points": len(prices),
            "prices": prices,
            "mock_data": True
        }
        
    async def get_real_time_quote(self, symbol: str) -> Dict[str, Any]:
        """Get real-time stock quote from multiple sources."""
        try:
            # Try Yahoo Finance (free, no API key needed)
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                params = {
                    "interval": "1d",
                    "range": "1d"
                }
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("chart", {}).get("result", [{}])[0]
                    meta = result.get("meta", {})
                    
                    # Get current price
                    current_price = meta.get("regularMarketPrice")
                    previous_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
                    
                    # If no current price, try to get from indicators
                    if not current_price:
                        indicators = result.get("indicators", {}).get("quote", [{}])[0]
                        closes = indicators.get("close", [])
                        if closes:
                            current_price = closes[-1] if closes[-1] else closes[-2] if len(closes) > 1 else 0
                    
                    if not current_price:
                        current_price = previous_close
                    
                    change = current_price - previous_close if previous_close else 0
                    change_percent = (change / previous_close * 100) if previous_close else 0
                    
                    logger.info(f"Fetched {symbol}: ${current_price:.2f}")
                    
                    return {
                        "symbol": symbol,
                        "price": float(current_price) if current_price else 0,
                        "change": float(change),
                        "change_percent": float(change_percent),
                        "volume": meta.get("regularMarketVolume", 0),
                        "market_cap": meta.get("marketCap", 0),
                        "high": meta.get("regularMarketDayHigh", current_price),
                        "low": meta.get("regularMarketDayLow", current_price),
                        "open": meta.get("regularMarketOpen", previous_close),
                        "previous_close": float(previous_close) if previous_close else 0,
                        "timestamp": datetime.now().isoformat(),
                        "source": "yahoo_finance"
                    }
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
        
        # Fallback to mock data with realistic prices
        mock_prices = {
            "AAPL": 178.50, "MSFT": 380.00, "GOOGL": 140.50, "AMZN": 155.00,
            "TSLA": 245.00, "NVDA": 495.00, "META": 385.00, "AMD": 145.00,
            "SLV": 24.50, "GLD": 185.00, "SPY": 475.00, "QQQ": 395.00
        }
        base_price = mock_prices.get(symbol.upper(), 100.00)
        
        return {
            "symbol": symbol,
            "price": base_price,
            "change": base_price * 0.015,
            "change_percent": 1.5,
            "volume": 50000000,
            "market_cap": 2500000000000,
            "high": base_price * 1.02,
            "low": base_price * 0.98,
            "open": 149.00,
            "previous_close": 147.50,
            "timestamp": datetime.now().isoformat(),
            "source": "mock"
        }
    
    async def get_stock_news(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get latest news for a stock."""
        try:
            # Yahoo Finance news
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://query1.finance.yahoo.com/v1/finance/search"
                params = {"q": symbol, "quotesCount": 1, "newsCount": limit}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    news_items = data.get("news", [])
                    
                    return [{
                        "title": item.get("title", ""),
                        "publisher": item.get("publisher", ""),
                        "link": item.get("link", ""),
                        "published_at": datetime.fromtimestamp(item.get("providerPublishTime", 0)).isoformat(),
                        "summary": item.get("summary", "")[:200],
                        "sentiment": self._analyze_headline_sentiment(item.get("title", ""))
                    } for item in news_items[:limit]]
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
        
        return []
    
    def _analyze_headline_sentiment(self, headline: str) -> str:
        """Simple sentiment analysis of news headline."""
        positive_words = ["surge", "gain", "profit", "beat", "growth", "up", "rise", "bullish", "strong"]
        negative_words = ["fall", "drop", "loss", "miss", "decline", "down", "crash", "bearish", "weak"]
        
        headline_lower = headline.lower()
        positive_count = sum(1 for word in positive_words if word in headline_lower)
        negative_count = sum(1 for word in negative_words if word in headline_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        return "neutral"
    
    async def analyze_stock_with_llm(
        self,
        symbol: str,
        quote: Dict[str, Any],
        news: List[Dict[str, Any]],
        ollama_host: str,
        ollama_model: str
    ) -> Dict[str, Any]:
        """Use LLM to analyze stock and provide recommendations."""
        
        # Prepare context for LLM
        news_summary = "\n".join([
            f"- {item['title']} ({item['sentiment']})"
            for item in news[:5]
        ])
        
        prompt = f"""Analyze {symbol} stock and provide investment recommendations.

Current Data:
- Price: ${quote['price']:.2f}
- Change: {quote['change_percent']:.2f}%
- Volume: {quote['volume']:,}
- 52-week High: ${quote['high']:.2f}
- 52-week Low: ${quote['low']:.2f}

Recent News:
{news_summary}

Provide:
1. Overall Rating (Strong Buy/Buy/Hold/Sell/Strong Sell)
2. Short-term outlook (1-4 weeks)
3. Long-term outlook (6+ months)
4. Key factors to watch
5. Risk level (Low/Medium/High)

Be concise and actionable."""

        try:
            analysis = await llm_generate(
                prompt, task="finance", temperature=0.3, timeout=30,
            )

            if analysis:
                # Parse LLM response to extract rating
                rating = self._extract_rating(analysis)

                return {
                    "symbol": symbol,
                    "rating": rating,
                    "analysis": analysis,
                    "confidence": self._calculate_confidence(quote, news),
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error analyzing {symbol} with LLM: {e}")
        
        # Fallback to rule-based analysis
        return self._rule_based_analysis(symbol, quote, news)
    
    def _extract_rating(self, analysis: str) -> str:
        """Extract rating from LLM analysis."""
        analysis_lower = analysis.lower()
        
        if "strong buy" in analysis_lower:
            return Rating.STRONG_BUY
        elif "strong sell" in analysis_lower:
            return Rating.STRONG_SELL
        elif "buy" in analysis_lower:
            return Rating.BUY
        elif "sell" in analysis_lower:
            return Rating.SELL
        else:
            return Rating.HOLD
    
    def _calculate_confidence(self, quote: Dict[str, Any], news: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on data quality."""
        confidence = 0.5
        
        # More volume = higher confidence
        if quote.get("volume", 0) > 10000000:
            confidence += 0.2
        
        # Recent news = higher confidence
        if len(news) > 5:
            confidence += 0.2
        
        # Positive sentiment = higher confidence
        positive_news = sum(1 for item in news if item.get("sentiment") == "positive")
        if positive_news > len(news) / 2:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _rule_based_analysis(self, symbol: str, quote: Dict[str, Any], news: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback rule-based analysis."""
        change_percent = quote.get("change_percent", 0)
        
        # Simple momentum-based rating
        if change_percent > 3:
            rating = Rating.BUY
            analysis = f"{symbol} showing strong upward momentum (+{change_percent:.2f}%). Consider buying on pullbacks."
        elif change_percent > 1:
            rating = Rating.HOLD
            analysis = f"{symbol} showing positive momentum. Monitor for entry points."
        elif change_percent < -3:
            rating = Rating.SELL
            analysis = f"{symbol} showing weakness (-{change_percent:.2f}%). Consider reducing position."
        else:
            rating = Rating.HOLD
            analysis = f"{symbol} trading sideways. Wait for clearer signals."
        
        return {
            "symbol": symbol,
            "rating": rating,
            "analysis": analysis,
            "confidence": 0.6,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_options_recommendations(self, symbol: str) -> Dict[str, Any]:
        """Analyze options trading opportunities."""
        quote = await self.get_real_time_quote(symbol)
        
        # Calculate potential option strategies
        current_price = quote["price"]
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "strategies": [
                {
                    "type": "covered_call",
                    "description": f"Sell call option at ${current_price * 1.05:.2f} strike",
                    "premium_estimate": current_price * 0.02,
                    "risk_level": "low",
                    "time_horizon": TimeHorizon.SHORT_TERM
                },
                {
                    "type": "cash_secured_put",
                    "description": f"Sell put option at ${current_price * 0.95:.2f} strike",
                    "premium_estimate": current_price * 0.025,
                    "risk_level": "medium",
                    "time_horizon": TimeHorizon.SHORT_TERM
                },
                {
                    "type": "long_call",
                    "description": f"Buy call option at ${current_price * 1.02:.2f} strike",
                    "cost_estimate": current_price * 0.03,
                    "risk_level": "high",
                    "time_horizon": TimeHorizon.SHORT_TERM
                }
            ],
            "recommended_strategy": "covered_call" if quote["change_percent"] > 0 else "cash_secured_put",
            "iv_rank": "medium",  # Would need real options data
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_daily_picks(self, ollama_host: str, ollama_model: str) -> Dict[str, Any]:
        """Get daily stock recommendations."""
        # Popular stocks to analyze
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "AMD"]
        
        picks = {
            "day_trade": [],
            "short_term": [],
            "long_term": []
        }
        
        for symbol in symbols[:6]:  # Analyze top 6
            try:
                quote = await self.get_real_time_quote(symbol)
                news = await self.get_stock_news(symbol, limit=5)
                analysis = await self.analyze_stock_with_llm(symbol, quote, news, ollama_host, ollama_model)
                
                stock_data = {
                    "symbol": symbol,
                    "price": quote["price"],
                    "change_percent": quote["change_percent"],
                    "rating": analysis["rating"],
                    "analysis": analysis["analysis"][:200],
                    "confidence": analysis["confidence"]
                }
                
                # Categorize based on volatility and rating
                if abs(quote["change_percent"]) > 2 and analysis["rating"] in [Rating.BUY, Rating.STRONG_BUY]:
                    picks["day_trade"].append(stock_data)
                elif analysis["rating"] in [Rating.BUY, Rating.STRONG_BUY]:
                    if quote["change_percent"] > 1:
                        picks["short_term"].append(stock_data)
                    else:
                        picks["long_term"].append(stock_data)
            except Exception as e:
                logger.error(f"Error analyzing {symbol}: {e}")
        
        # Sort by confidence
        for category in picks:
            picks[category] = sorted(picks[category], key=lambda x: x["confidence"], reverse=True)[:3]
        
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "picks": picks,
            "market_summary": "Market showing mixed signals. Focus on quality stocks with strong fundamentals.",
            "timestamp": datetime.now().isoformat()
        }


# Singleton instance
_stock_intelligence: Optional[StockIntelligence] = None


def get_stock_intelligence() -> StockIntelligence:
    """Get stock intelligence service instance."""
    global _stock_intelligence
    if _stock_intelligence is None:
        _stock_intelligence = StockIntelligence()
    return _stock_intelligence
