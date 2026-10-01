"""
Query Classifier Service
Intelligently classifies user queries to route to appropriate services
"""
import re
from typing import Dict, Any, List


class QueryClassifier:
    """Classifies user queries into different categories for proper routing."""
    
    # Investment-related keywords
    INVESTMENT_KEYWORDS = [
        'stock', 'ticker', 'etf', 'invest', 'portfolio', 'buy', 'sell', 'hold',
        'share', 'market', 'trading', 'dividend', 'earnings', 'price target',
        'analyst', 'bull', 'bear', 'elliott', 'wave', 'technical analysis',
        'fundamental', 'valuation', 'p/e ratio', 'market cap', 'volume',
        'resistance', 'support', 'trend', 'chart', 'candlestick', 'macd',
        'rsi', 'moving average', 'bollinger', 'nasdaq', 'dow', 'sp500',
        's&p 500', 'nyse', 'exchange', 'broker', 'brokerage', 'ipo',
        'mutual fund', 'index fund', 'bond', 'treasury', 'yield', 'return',
        'roi', 'capital gain', 'asset allocation', 'diversification'
    ]
    
    # Shopping-related keywords
    SHOPPING_KEYWORDS = [
        'buy online', 'purchase', 'deal', 'discount', 'coupon', 'price',
        'cheap', 'affordable', 'best price', 'where to buy', 'shopping',
        'product', 'item', 'amazon', 'walmart', 'target', 'ebay',
        'slickdeals', 'sale', 'offer', 'promo', 'free shipping',
        'delivery', 'in stock', 'out of stock', 'review', 'rating',
        'compare prices', 'best deal', 'lowest price', 'electronics',
        'appliance', 'gadget', 'laptop', 'phone', 'tv', 'camera',
        # Common product nouns — a query naming a product is shopping even
        # when it also mentions a use case like 'for flights'
        'headphone', 'earbud', 'earphone', 'airpods', 'speaker', 'soundbar',
        'microphone', 'mic', 'webcam', 'keyboard', 'mouse', 'monitor',
        'charger', 'cable', 'adapter', 'hub', 'dock', 'ssd', 'hard drive',
        'tablet', 'ipad', 'kindle', 'watch', 'smartwatch', 'fitness tracker',
        'backpack', 'suitcase', 'luggage', 'neck pillow', 'power bank',
        'blender', 'air fryer', 'vacuum', 'coffee maker', 'espresso',
        'mattress', 'pillow', 'chair', 'desk', 'lamp', 'router',
        'drone', 'console', 'controller', 'gpu', 'graphics card',
        'sneakers', 'shoes', 'jacket', 'backpack', 'tent', 'cooler'
    ]

    # Travel-related keywords
    TRAVEL_KEYWORDS = [
        'flight', 'airline', 'airport', 'ticket', 'booking', 'hotel',
        'travel', 'trip', 'vacation', 'destination', 'itinerary',
        'departure', 'arrival', 'layover', 'direct flight', 'round trip',
        'one way', 'baggage', 'seat', 'upgrade', 'miles', 'points',
        'rental car', 'cruise', 'resort', 'accommodation'
    ]

    # Patterns that indicate the user wants to BOOK travel (not buy a product
    # for a trip). e.g. "flights to Boston", "fly to NYC", "book a hotel".
    TRAVEL_INTENT_PATTERN = re.compile(
        r'\b(flights?|fly|flying|tickets?)\s+(to|from)\b'
        r'|\b(book|reserve|find|get|search|show)\s+(me\s+)?(a\s+|an\s+)?(cheap\s+)?(flights?|hotels?|tickets?|rental cars?)\b'
        r'|\b(hotel|hotels|stay|stays|accommodation)\s+(in|at|near)\b'
        r'|\btrip\s+to\b|\btravel(ing|ling)?\s+to\b|\bvisit(ing)?\s+[a-z]'
    )

    # Pattern for a product being bought FOR a travel use case:
    # "headphones for flights", "luggage for my trip", "mic for travel"
    PRODUCT_FOR_TRAVEL_PATTERN = re.compile(
        r'\bfor\s+(a\s+|an\s+|my\s+|the\s+|our\s+)?'
        r'(flight|flights|trip|trips|travel|travels|traveling|travelling|'
        r'vacation|vacations|cruise|cruises|holiday|holidays|commute|'
        r'road\s*trip|business\s*trip|plane|airplane|long\s*flight)\b'
    )

    # Stock ticker pattern (1-5 uppercase letters)
    TICKER_PATTERN = re.compile(r'\b[A-Z]{1,5}\b')
    
    @classmethod
    def classify_query(cls, query: str) -> Dict[str, Any]:
        """
        Classify a user query into appropriate category.
        
        Returns:
            Dict with 'category', 'confidence', and 'reasoning'
        """
        query_lower = query.lower()
        
        # Check for stock ticker symbols
        # Uppercase product acronyms/currencies are not evidence of stock intent.
        excluded = {"I", "A", "AN", "TV", "USB", "INR", "USD", "US", "IN", "LED", "OLED", "AC", "CPU", "GPU", "RAM", "SSD", "JFK", "LAX"}
        has_ticker = any(t not in excluded for t in cls.TICKER_PATTERN.findall(query))
        
        # Count keyword matches
        investment_score = sum(1 for kw in cls.INVESTMENT_KEYWORDS if kw in query_lower)
        shopping_score = sum(1 for kw in cls.SHOPPING_KEYWORDS if kw in query_lower)
        travel_score = sum(1 for kw in cls.TRAVEL_KEYWORDS if kw in query_lower)

        # Boost investment score if ticker detected
        explicit_finance = bool(re.search(r"\b(stock|stocks|shares|etf|invest|investment|portfolio|trading|ticker)\b", query_lower))
        if shopping_score > 0 and not explicit_finance:
            investment_score = 0
        if has_ticker and (explicit_finance or (shopping_score == 0 and travel_score == 0)):
            investment_score += 3

        # ── Use-case vs. intent disambiguation ────────────────────────────
        # "headphones under $100 for flights" → shopping (flights = use case)
        # "flights to Boston" / "book a hotel" → travel (booking intent)
        product_for_travel = bool(cls.PRODUCT_FOR_TRAVEL_PATTERN.search(query_lower))
        travel_booking_intent = bool(cls.TRAVEL_INTENT_PATTERN.search(query_lower))

        if product_for_travel and not travel_booking_intent:
            # The travel words are a use case, not the request — discount them
            travel_score = 0
            if shopping_score == 0:
                shopping_score = 1  # 'X for flights' implies buying X

        # Determine category
        scores = {
            'investment': investment_score,
            'shopping': shopping_score,
            'travel': travel_score
        }

        max_score = max(scores.values())

        if max_score == 0:
            return {
                'category': 'general',
                'confidence': 0.5,
                'reasoning': 'No specific keywords detected'
            }

        category = max(scores, key=scores.get)
        confidence = min(max_score / 5.0, 1.0)  # Normalize to 0-1

        # Additional context-based rules
        if 'should i buy' in query_lower or 'should i invest' in query_lower:
            if explicit_finance or (has_ticker and shopping_score == 0):
                category = 'investment'
                confidence = 0.95

        if 'where can i buy' in query_lower or 'best price for' in query_lower:
            if not has_ticker:
                category = 'shopping'
                confidence = 0.9

        # Explicit travel booking intent wins over incidental product words
        if travel_booking_intent and not product_for_travel:
            category = 'travel'
            confidence = max(confidence, 0.85)
        
        reasoning = cls._generate_reasoning(query, category, has_ticker, scores)
        
        return {
            'category': category,
            'confidence': confidence,
            'reasoning': reasoning,
            'scores': scores
        }
    
    @classmethod
    def _generate_reasoning(cls, query: str, category: str, has_ticker: bool, scores: Dict) -> str:
        """Generate human-readable reasoning for classification."""
        reasons = []
        
        if has_ticker:
            reasons.append("Detected stock ticker symbol")
        
        if scores['investment'] > 0:
            reasons.append(f"Found {scores['investment']} investment-related keywords")
        
        if scores['shopping'] > 0:
            reasons.append(f"Found {scores['shopping']} shopping-related keywords")
        
        if scores['travel'] > 0:
            reasons.append(f"Found {scores['travel']} travel-related keywords")
        
        if not reasons:
            return "General query with no specific category indicators"
        
        return f"Classified as '{category}': " + "; ".join(reasons)
    
    @classmethod
    def get_routing_instructions(cls, category: str) -> str:
        """Get routing instructions for the AI based on category."""
        instructions = {
            'investment': """
You are a financial investment advisor. The user is asking about stocks, ETFs, or investment decisions.
- Provide stock analysis, market insights, and investment recommendations
- Use technical and fundamental analysis
- Reference price data, charts, and market trends
- DO NOT provide shopping links or product comparisons
- Focus on financial markets, not consumer products
""",
            'shopping': """
You are a smart shopping assistant. The user is looking to purchase a product.
- Find the best deals and prices across retailers
- Compare products and provide shopping recommendations
- Include links to actual product pages
- DO NOT provide stock investment advice
- Focus on consumer products, not financial instruments
""",
            'travel': """
You are a travel assistant. The user is asking about flights, hotels, or travel plans.
- Provide flight options, hotel recommendations, and travel advice
- Include pricing, schedules, and booking information
- DO NOT provide investment or shopping advice
- Focus on travel planning and logistics
""",
            'general': """
You are a helpful AI assistant. Answer the user's question clearly and concisely.
- Provide accurate, relevant information
- Be conversational and friendly
- If the query seems specific to investment, shopping, or travel, clarify with the user
"""
        }
        
        return instructions.get(category, instructions['general'])


# Global instance
query_classifier = QueryClassifier()
