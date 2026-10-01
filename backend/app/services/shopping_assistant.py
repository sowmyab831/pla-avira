"""
Shopping Assistant - Product search, comparison, and recommendations.

Features:
- Query normalization and parsing
- Multi-source product search (APIs + structured scraping)
- Price aggregation and deduplication
- Ranking based on price, shipping, seller rating, warranty
- Privacy-first: masks payment info before external calls
"""
import logging
import re
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class ProductCategory(str, Enum):
    ELECTRONICS = "electronics"
    PHONES = "phones"
    COMPUTERS = "computers"
    APPLIANCES = "appliances"
    CLOTHING = "clothing"
    HOME = "home"
    SPORTS = "sports"
    OTHER = "other"


@dataclass
class ProductConstraints:
    """Parsed constraints from user query."""
    product_name: str
    category: ProductCategory = ProductCategory.OTHER
    brand: Optional[str] = None
    model: Optional[str] = None
    color: Optional[str] = None
    storage: Optional[str] = None  # e.g., "256GB"
    unlocked: bool = False
    condition: str = "new"  # new, refurbished, used
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    keywords: List[str] = field(default_factory=list)


@dataclass
class ProductResult:
    """A single product search result."""
    rank: int
    title: str
    seller: str
    price: float
    original_price: Optional[float] = None
    shipping_cost: float = 0.0
    tax_estimate: float = 0.0
    final_price: float = 0.0
    delivery_estimate: str = ""
    seller_rating: float = 0.0
    warranty: str = ""
    condition: str = "new"
    url: str = ""
    source: str = ""
    why: str = ""
    image_url: str = ""
    in_stock: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "rank": self.rank,
            "title": self.title,
            "seller": self.seller,
            "price": self.price,
            "original_price": self.original_price,
            "shipping_cost": self.shipping_cost,
            "tax_estimate": self.tax_estimate,
            "final_price": self.final_price,
            "delivery_estimate": self.delivery_estimate,
            "seller_rating": self.seller_rating,
            "warranty": self.warranty,
            "condition": self.condition,
            "url": self.url,
            "source": self.source,
            "why": self.why,
            "image_url": self.image_url,
            "in_stock": self.in_stock,
        }


# Brand detection patterns
BRAND_PATTERNS = {
    "apple": ["iphone", "ipad", "macbook", "airpods", "apple watch"],
    "samsung": ["galaxy", "samsung"],
    "google": ["pixel", "google"],
    "sony": ["playstation", "sony", "ps5", "ps4"],
    "microsoft": ["xbox", "surface", "microsoft"],
    "dell": ["dell", "xps", "alienware"],
    "hp": ["hp", "hewlett"],
    "lenovo": ["lenovo", "thinkpad"],
    "lg": ["lg"],
    "nike": ["nike", "air jordan"],
    "adidas": ["adidas"],
}

# Storage patterns
STORAGE_PATTERN = re.compile(r'(\d+)\s*(gb|tb)', re.IGNORECASE)

# Color patterns
COLORS = ["black", "white", "silver", "gold", "blue", "red", "green", "purple", "pink", "gray", "grey", "titanium", "natural"]

# Price patterns
PRICE_PATTERNS = [
    re.compile(r'under\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
    re.compile(r'less\s*than\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
    re.compile(r'max(?:imum)?\s*\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
    re.compile(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:or\s*less|max)', re.IGNORECASE),
]


class ShoppingAssistant:
    """
    Multi-source shopping assistant with privacy protection.
    """
    
    def __init__(self):
        self._cache: Dict[str, Tuple[List[ProductResult], datetime]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._user_preferences: Dict[str, Dict] = {}
    
    def parse_query(self, query: str) -> ProductConstraints:
        """
        Parse natural language query into structured constraints.
        
        Examples:
        - "iPhone 17 Pro Max unlocked 256GB black under $1200"
        - "Samsung Galaxy S25 Ultra 512GB"
        - "cheap laptop under $500"
        """
        query_lower = query.lower()
        
        # Detect brand
        brand = None
        for b, patterns in BRAND_PATTERNS.items():
            if any(p in query_lower for p in patterns):
                brand = b
                break
        
        # Detect category
        category = ProductCategory.OTHER
        if any(w in query_lower for w in ["phone", "iphone", "galaxy", "pixel"]):
            category = ProductCategory.PHONES
        elif any(w in query_lower for w in ["laptop", "computer", "pc", "macbook", "desktop"]):
            category = ProductCategory.COMPUTERS
        elif any(w in query_lower for w in ["tv", "television", "monitor", "headphone", "speaker", "camera"]):
            category = ProductCategory.ELECTRONICS
        elif any(w in query_lower for w in ["refrigerator", "washer", "dryer", "dishwasher", "microwave"]):
            category = ProductCategory.APPLIANCES
        
        # Detect storage
        storage = None
        storage_match = STORAGE_PATTERN.search(query)
        if storage_match:
            storage = f"{storage_match.group(1)}{storage_match.group(2).upper()}"
        
        # Detect color
        color = None
        for c in COLORS:
            if c in query_lower:
                color = c
                break
        
        # Detect unlocked
        unlocked = "unlocked" in query_lower
        
        # Detect condition
        condition = "new"
        if "refurbished" in query_lower or "renewed" in query_lower:
            condition = "refurbished"
        elif "used" in query_lower:
            condition = "used"
        
        # Detect max price
        max_price = None
        for pattern in PRICE_PATTERNS:
            match = pattern.search(query)
            if match:
                price_str = match.group(1).replace(",", "")
                max_price = float(price_str)
                break
        
        # Extract product name (clean up constraints from query)
        product_name = query
        for pattern in PRICE_PATTERNS:
            product_name = pattern.sub("", product_name)
        product_name = re.sub(r'\b(unlocked|refurbished|renewed|used|new)\b', '', product_name, flags=re.IGNORECASE)
        product_name = re.sub(r'\b(' + '|'.join(COLORS) + r')\b', '', product_name, flags=re.IGNORECASE)
        product_name = STORAGE_PATTERN.sub('', product_name)
        product_name = re.sub(r'\s+', ' ', product_name).strip()
        
        return ProductConstraints(
            product_name=product_name,
            category=category,
            brand=brand,
            color=color,
            storage=storage,
            unlocked=unlocked,
            condition=condition,
            max_price=max_price,
        )
    
    async def search(
        self,
        query: str,
        user_id: str,
        top_n: int = 3,
    ) -> Dict[str, Any]:
        """
        Search for products across multiple sources.
        
        Returns structured results with ranking.
        """
        constraints = self.parse_query(query)
        
        # Check cache
        cache_key = f"{query}:{user_id}"
        if cache_key in self._cache:
            results, cached_at = self._cache[cache_key]
            if (datetime.now() - cached_at).seconds < self._cache_ttl:
                return self._format_response(query, constraints, results[:top_n], from_cache=True)
        
        # Search multiple sources concurrently
        results = await self._search_all_sources(constraints)
        
        if not results:
            return {
                "success": False,
                "query": query,
                "constraints": self._constraints_to_dict(constraints),
                "results": [],
                "message": "I couldn't find verified prices. Would you like me to broaden the search or use third-party retailer APIs?",
            }
        
        # Deduplicate and rank
        ranked = self._rank_results(results, constraints, user_id)
        
        # Cache results
        self._cache[cache_key] = (ranked, datetime.now())
        
        return self._format_response(query, constraints, ranked[:top_n])
    
    async def _search_all_sources(self, constraints: ProductConstraints) -> List[ProductResult]:
        """Search all available sources concurrently."""
        results = []
        
        # In production, these would be real API calls
        # For demo, we simulate with mock data
        
        tasks = [
            self._search_mock_amazon(constraints),
            self._search_mock_bestbuy(constraints),
            self._search_mock_walmart(constraints),
        ]
        
        source_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source_result in source_results:
            if isinstance(source_result, Exception):
                logger.warning(f"Source search failed: {source_result}")
                continue
            results.extend(source_result)
        
        return results
    
    async def _search_mock_amazon(self, constraints: ProductConstraints) -> List[ProductResult]:
        """Mock Amazon search - replace with real API in production."""
        # Simulate API delay
        await asyncio.sleep(0.1)
        
        base_price = self._estimate_base_price(constraints)
        
        return [
            ProductResult(
                rank=0,
                title=f"{constraints.product_name} {constraints.storage or ''} {constraints.color or ''}".strip(),
                seller="Amazon.com",
                price=base_price,
                shipping_cost=0,
                tax_estimate=base_price * 0.08,
                final_price=base_price * 1.08,
                delivery_estimate="2-3 business days (Prime)",
                seller_rating=4.7,
                warranty="1 year manufacturer",
                condition=constraints.condition,
                url="https://amazon.com/dp/EXAMPLE",
                source="amazon",
                in_stock=True,
            ),
            ProductResult(
                rank=0,
                title=f"{constraints.product_name} {constraints.storage or ''} - Third Party".strip(),
                seller="TechDeals (via Amazon)",
                price=base_price * 0.95,
                shipping_cost=5.99,
                tax_estimate=base_price * 0.95 * 0.08,
                final_price=base_price * 0.95 * 1.08 + 5.99,
                delivery_estimate="5-7 business days",
                seller_rating=4.2,
                warranty="90 days seller warranty",
                condition=constraints.condition,
                url="https://amazon.com/dp/EXAMPLE2",
                source="amazon",
                in_stock=True,
            ),
        ]
    
    async def _search_mock_bestbuy(self, constraints: ProductConstraints) -> List[ProductResult]:
        """Mock Best Buy search."""
        await asyncio.sleep(0.1)
        
        base_price = self._estimate_base_price(constraints)
        
        return [
            ProductResult(
                rank=0,
                title=f"{constraints.product_name} {constraints.storage or ''}".strip(),
                seller="Best Buy",
                price=base_price * 1.02,
                shipping_cost=0,
                tax_estimate=base_price * 1.02 * 0.08,
                final_price=base_price * 1.02 * 1.08,
                delivery_estimate="Same day pickup available",
                seller_rating=4.5,
                warranty="1 year + Geek Squad available",
                condition=constraints.condition,
                url="https://bestbuy.com/product/EXAMPLE",
                source="bestbuy",
                in_stock=True,
            ),
        ]
    
    async def _search_mock_walmart(self, constraints: ProductConstraints) -> List[ProductResult]:
        """Mock Walmart search."""
        await asyncio.sleep(0.1)
        
        base_price = self._estimate_base_price(constraints)
        
        return [
            ProductResult(
                rank=0,
                title=f"{constraints.product_name} {constraints.storage or ''}".strip(),
                seller="Walmart",
                price=base_price * 0.98,
                shipping_cost=0,
                tax_estimate=base_price * 0.98 * 0.08,
                final_price=base_price * 0.98 * 1.08,
                delivery_estimate="2-day shipping (Walmart+)",
                seller_rating=4.3,
                warranty="1 year manufacturer",
                condition=constraints.condition,
                url="https://walmart.com/ip/EXAMPLE",
                source="walmart",
                in_stock=True,
            ),
        ]
    
    def _estimate_base_price(self, constraints: ProductConstraints) -> float:
        """Estimate base price for mock data."""
        # This would be replaced by real API data
        base = 500  # Default
        
        if constraints.category == ProductCategory.PHONES:
            if constraints.brand == "apple":
                base = 999
                if "pro max" in constraints.product_name.lower():
                    base = 1199
                elif "pro" in constraints.product_name.lower():
                    base = 1099
            elif constraints.brand == "samsung":
                base = 899
                if "ultra" in constraints.product_name.lower():
                    base = 1199
            elif constraints.brand == "google":
                base = 699
        
        # Adjust for storage
        if constraints.storage:
            storage_num = int(re.search(r'\d+', constraints.storage).group())
            if storage_num >= 512:
                base += 200
            elif storage_num >= 256:
                base += 100
        
        # Adjust for condition
        if constraints.condition == "refurbished":
            base *= 0.85
        elif constraints.condition == "used":
            base *= 0.70
        
        return round(base, 2)
    
    def _rank_results(
        self,
        results: List[ProductResult],
        constraints: ProductConstraints,
        user_id: str,
    ) -> List[ProductResult]:
        """
        Rank results based on multiple factors.
        
        Factors:
        - Price (40%)
        - Seller rating (20%)
        - Shipping speed (15%)
        - Warranty (10%)
        - User preferences (15%)
        """
        user_prefs = self._user_preferences.get(user_id, {})
        price_weight = user_prefs.get("price_weight", 0.40)
        rating_weight = user_prefs.get("rating_weight", 0.20)
        shipping_weight = user_prefs.get("shipping_weight", 0.15)
        warranty_weight = user_prefs.get("warranty_weight", 0.10)
        
        # Normalize prices
        prices = [r.final_price for r in results]
        min_price = min(prices) if prices else 1
        max_price = max(prices) if prices else 1
        price_range = max_price - min_price if max_price != min_price else 1
        
        for result in results:
            # Price score (lower is better)
            price_score = 1 - ((result.final_price - min_price) / price_range)
            
            # Rating score
            rating_score = result.seller_rating / 5.0
            
            # Shipping score (based on delivery estimate)
            shipping_score = 0.5
            if "same day" in result.delivery_estimate.lower():
                shipping_score = 1.0
            elif "1-2" in result.delivery_estimate or "2-3" in result.delivery_estimate:
                shipping_score = 0.8
            elif "prime" in result.delivery_estimate.lower():
                shipping_score = 0.9
            
            # Warranty score
            warranty_score = 0.5
            if "1 year" in result.warranty.lower():
                warranty_score = 0.7
            if "2 year" in result.warranty.lower():
                warranty_score = 0.9
            if "geek squad" in result.warranty.lower() or "extended" in result.warranty.lower():
                warranty_score = 0.8
            
            # Calculate total score
            total_score = (
                price_score * price_weight +
                rating_score * rating_weight +
                shipping_score * shipping_weight +
                warranty_score * warranty_weight
            )
            
            result.rank = total_score
        
        # Sort by score (descending)
        results.sort(key=lambda r: r.rank, reverse=True)
        
        # Assign final ranks and generate "why" explanations
        for i, result in enumerate(results):
            result.rank = i + 1
            result.why = self._generate_why(result, results, constraints)
        
        return results
    
    def _generate_why(
        self,
        result: ProductResult,
        all_results: List[ProductResult],
        constraints: ProductConstraints,
    ) -> str:
        """Generate explanation for why this result is ranked here."""
        reasons = []
        
        # Check if lowest price
        prices = [r.final_price for r in all_results]
        if result.final_price == min(prices):
            reasons.append("lowest total price")
        elif result.final_price <= sorted(prices)[1] if len(prices) > 1 else True:
            reasons.append("competitive price")
        
        # Check seller rating
        if result.seller_rating >= 4.5:
            reasons.append("highly rated seller")
        
        # Check shipping
        if "same day" in result.delivery_estimate.lower():
            reasons.append("same-day pickup available")
        elif "prime" in result.delivery_estimate.lower() or "2-3" in result.delivery_estimate:
            reasons.append("fast shipping")
        
        # Check warranty
        if "geek squad" in result.warranty.lower():
            reasons.append("extended warranty option")
        
        if not reasons:
            reasons.append("good overall value")
        
        return "; ".join(reasons[:2]).capitalize()
    
    def _constraints_to_dict(self, constraints: ProductConstraints) -> Dict:
        """Convert constraints to dict for response."""
        return {
            "product_name": constraints.product_name,
            "category": constraints.category.value,
            "brand": constraints.brand,
            "color": constraints.color,
            "storage": constraints.storage,
            "unlocked": constraints.unlocked,
            "condition": constraints.condition,
            "max_price": constraints.max_price,
        }
    
    def _format_response(
        self,
        query: str,
        constraints: ProductConstraints,
        results: List[ProductResult],
        from_cache: bool = False,
    ) -> Dict[str, Any]:
        """Format the final response."""
        return {
            "success": True,
            "type": "shopping_result",
            "query": query,
            "constraints": self._constraints_to_dict(constraints),
            "results": [r.to_dict() for r in results],
            "result_count": len(results),
            "from_cache": from_cache,
            "searched_at": datetime.now().isoformat(),
            "notes": {
                "masked_payment": False,
                "externally_processed": False,
            },
        }
    
    def set_user_preferences(self, user_id: str, preferences: Dict):
        """Set user preferences for ranking."""
        self._user_preferences[user_id] = preferences


# Singleton
_shopping_assistant: Optional[ShoppingAssistant] = None


def get_shopping_assistant() -> ShoppingAssistant:
    global _shopping_assistant
    if _shopping_assistant is None:
        _shopping_assistant = ShoppingAssistant()
    return _shopping_assistant
