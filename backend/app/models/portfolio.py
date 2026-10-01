"""Stock portfolio tracking and sentiment analysis models."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class Stock(BaseModel):
    """Stock information."""
    symbol: str
    name: str
    current_price: float
    previous_close: float
    day_change: float
    day_change_percent: float
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    last_updated: datetime


class PortfolioHolding(BaseModel):
    """User's stock holding."""
    holding_id: Optional[str] = None
    user_id: str
    symbol: str
    shares: float
    average_cost: float = 0.0
    current_price: float = 0.0
    total_value: float = 0.0
    total_cost: float = 0.0
    gain_loss: float = 0.0
    gain_loss_percent: float = 0.0
    purchase_date: Optional[date] = None
    last_updated: Optional[datetime] = None


class Portfolio(BaseModel):
    """User's portfolio."""
    portfolio_id: str
    user_id: str
    holdings: List[PortfolioHolding]
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_percent: float
    cash_balance: float
    last_updated: datetime


class StockNews(BaseModel):
    """Stock-related news."""
    news_id: str
    symbol: str
    title: str
    summary: str
    source: str
    url: str
    published_date: datetime
    sentiment: str  # positive, negative, neutral
    sentiment_score: float  # -1 to 1
    relevance_score: float  # 0 to 1


class SocialSentiment(BaseModel):
    """Social media sentiment for a stock."""
    symbol: str
    date: date
    twitter_mentions: int
    twitter_sentiment: float  # -1 to 1
    reddit_mentions: int
    reddit_sentiment: float
    overall_sentiment: float
    sentiment_trend: str  # rising, falling, stable
    bullish_percent: float
    bearish_percent: float


class EarningsDate(BaseModel):
    """Earnings announcement date."""
    symbol: str
    earnings_date: date
    estimated_eps: Optional[float] = None
    actual_eps: Optional[float] = None
    surprise_percent: Optional[float] = None
    has_announced: bool = False


class StockAlert(BaseModel):
    """Stock price or news alert."""
    alert_id: str
    user_id: str
    symbol: str
    alert_type: str  # price_above, price_below, news, earnings, sentiment
    condition: dict  # {type: "price", operator: ">", value: 150.0}
    is_active: bool = True
    created_date: datetime
    triggered_date: Optional[datetime] = None


class MarketSentiment(BaseModel):
    """Overall market sentiment."""
    date: date
    sp500_change: float
    nasdaq_change: float
    dow_change: float
    vix: float
    fear_greed_index: int  # 0-100
    overall_sentiment: str  # bullish, bearish, neutral
    top_trending_stocks: List[str]
    top_news_headlines: List[str]


class StockRecommendation(BaseModel):
    """AI-generated stock recommendation."""
    symbol: str
    recommendation: str  # buy, sell, hold
    confidence: float  # 0-100
    target_price: float
    reasons: List[str]
    risk_level: str  # low, medium, high
    time_horizon: str  # short, medium, long
    based_on: List[str]  # ["technical_analysis", "sentiment", "news", "earnings"]
    generated_date: datetime
