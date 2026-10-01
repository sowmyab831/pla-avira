"""Shopping assistant models for deal tracking and price history."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class PriceHistory(BaseModel):
    """Price history for a product."""
    date: datetime
    price: float
    source: str  # amazon, bestbuy, walmart, etc.
    url: str
    in_stock: bool = True


class Product(BaseModel):
    """Product information."""
    product_id: str
    name: str
    category: str
    brand: Optional[str] = None
    model: Optional[str] = None
    current_price: float
    lowest_price: float
    highest_price: float
    average_price: float
    price_history: List[PriceHistory] = []
    last_updated: datetime
    image_url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None


class Deal(BaseModel):
    """Deal information from SlickDeals, etc."""
    deal_id: str
    title: str
    description: str
    price: float
    original_price: Optional[float] = None
    discount_percentage: Optional[float] = None
    store: str
    url: str
    image_url: Optional[str] = None
    category: str
    posted_date: datetime
    expires_date: Optional[datetime] = None
    upvotes: int = 0
    comments_count: int = 0
    is_frontpage: bool = False


class ShoppingRequest(BaseModel):
    """User shopping request."""
    query: str
    category: Optional[str] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    preferred_stores: List[str] = []


class ShoppingRecommendation(BaseModel):
    """Shopping recommendation with deal intelligence."""
    product: Product
    current_deal: Optional[Deal] = None
    recommendation_score: float  # 0-100
    reasons: List[str]
    best_time_to_buy: str  # "now", "wait_for_sale", "black_friday", etc.
    predicted_next_sale_date: Optional[datetime] = None
    predicted_sale_price: Optional[float] = None
    purchase_url: str
    alternatives: List[Product] = []


class PriceAlert(BaseModel):
    """Price alert for a product."""
    alert_id: str
    user_id: str
    product_id: str
    target_price: float
    created_date: datetime
    is_active: bool = True
    notified: bool = False
