"""
AI-Powered Smart Shopping Service
Finds the best value with coupons, discounts, cashback, and retailer benefits
Uses local LLM (Ollama) for intelligent recommendations
"""
import logging
import httpx
import asyncio
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)

class SmartShoppingService:
    """
    AI-powered shopping assistant that:
    - Searches multiple retailers for product prices
    - Finds active coupons and promo codes
    - Analyzes cashback opportunities
    - Compares retailer benefits (returns, warranty, shipping)
    - Uses AI to recommend the best overall value
    """
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.ollama_url = "http://localhost:11434/api/generate"
        
        # Retailer data with benefits
        self.retailers = {
            "amazon": {
                "name": "Amazon",
                "benefits": ["Free 2-day shipping (Prime)", "Easy returns (30 days)", "Price match guarantee", "Subscribe & Save discounts"],
                "cashback_partners": ["Rakuten (up to 5%)", "TopCashback (up to 6%)"],
                "typical_coupons": ["$10 off $50+", "15% off select items", "Lightning deals"],
                "search_url": "https://www.amazon.com/s?k=",
            },
            "walmart": {
                "name": "Walmart", 
                "benefits": ["Free shipping ($35+)", "Price match policy", "Store pickup available", "90-day returns"],
                "cashback_partners": ["Rakuten (up to 4%)", "Ibotta (varies)"],
                "typical_coupons": ["Rollback prices", "$10 off grocery $50+", "Flash deals"],
                "search_url": "https://www.walmart.com/search?q=",
            },
            "bestbuy": {
                "name": "Best Buy",
                "benefits": ["Price match guarantee", "Free shipping ($35+)", "Extended warranty options", "Geek Squad support", "15-day returns (45 for members)"],
                "cashback_partners": ["Rakuten (up to 2%)", "TopCashback (up to 3%)"],
                "typical_coupons": ["Open-box deals (15-30% off)", "Student discounts", "Member deals"],
                "search_url": "https://www.bestbuy.com/site/searchpage.jsp?st=",
            },
            "target": {
                "name": "Target",
                "benefits": ["5% off with RedCard", "Free shipping ($35+)", "Easy returns (90 days)", "Same-day delivery"],
                "cashback_partners": ["Rakuten (up to 2%)", "Ibotta (varies)"],
                "typical_coupons": ["Circle offers", "Gift card deals", "Weekly ad specials"],
                "search_url": "https://www.target.com/s?searchTerm=",
            },
            "costco": {
                "name": "Costco",
                "benefits": ["Bulk pricing", "Extended warranty (2yr electronics)", "Generous returns", "Price adjustment within 30 days"],
                "cashback_partners": ["Executive membership (2% back)"],
                "typical_coupons": ["Monthly member deals", "Warehouse instant savings"],
                "search_url": "https://www.costco.com/CatalogSearch?keyword=",
            },
            "newegg": {
                "name": "Newegg",
                "benefits": ["Tech-focused selection", "Combo deals", "Open-box specials", "EggPoints rewards"],
                "cashback_partners": ["Rakuten (up to 3%)", "TopCashback (up to 4%)"],
                "typical_coupons": ["Shell Shocker deals", "Promo codes at checkout"],
                "search_url": "https://www.newegg.com/p/pl?d=",
            },
        }
        
        # Coupon sources
        self.coupon_sources = [
            "RetailMeNot", "Honey", "Coupons.com", "SlickDeals", 
            "CouponCabin", "Groupon", "Brad's Deals"
        ]

    async def smart_search(self, query: str, budget: Optional[float] = None) -> Dict[str, Any]:
        """
        Perform intelligent product search with full value analysis
        """
        logger.info(f"Smart shopping search for: {query}")
        
        # Search all sources in parallel
        tasks = [
            self._search_retailer_prices(query),
            self._find_coupons(query),
            self._get_cashback_rates(query),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = results[0] if not isinstance(results[0], Exception) else []
        coupons = results[1] if not isinstance(results[1], Exception) else []
        cashback = results[2] if not isinstance(results[2], Exception) else {}
        
        # Calculate true costs with all discounts
        analyzed_options = self._calculate_true_costs(prices, coupons, cashback)
        
        # Get AI recommendation
        ai_recommendation = await self._get_ai_recommendation(query, analyzed_options, budget)
        
        # Build comprehensive response
        return {
            "success": True,
            "query": query,
            "search_time": datetime.now().isoformat(),
            "products": analyzed_options[:10],
            "best_value": analyzed_options[0] if analyzed_options else None,
            "coupons_found": coupons,
            "cashback_options": cashback,
            "ai_recommendation": ai_recommendation,
            "total_options": len(analyzed_options),
            "potential_savings": self._calculate_total_savings(analyzed_options),
        }

    async def _search_retailer_prices(self, query: str) -> List[Dict]:
        """Search multiple retailers for product prices"""
        products = []
        
        # Try real scraping first - prioritize actual data
        scrape_tasks = [
            self._scrape_slickdeals(query),
            self._scrape_google_shopping(query),
            self._scrape_amazon(query),
            self._scrape_walmart(query),
        ]
        
        scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        for result in scrape_results:
            if isinstance(result, list) and len(result) > 0:
                products.extend(result)
                logger.info(f"Added {len(result)} products from scraping")
        
        # Provider outages produce an honest empty result, never fabricated offers.
        return products

    async def _scrape_slickdeals(self, query: str) -> List[Dict]:
        """Scrape SlickDeals for current deals"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://slickdeals.net/newsearch.php?q={query.replace(' ', '+')}&searcharea=deals&searchin=first"
                response = await client.get(url, headers={"User-Agent": self.user_agent})
                
                if response.status_code != 200:
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                products = []
                
                # Parse deal cards
                for deal in soup.select('.dealCard, .fpGridBox')[:5]:
                    try:
                        title_elem = deal.select_one('.dealTitle a, .itemTitle a')
                        price_elem = deal.select_one('.dealPrice, .itemPrice')
                        store_elem = deal.select_one('.storeName, .itemStore')
                        
                        if title_elem and price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0
                            
                            products.append({
                                "id": f"slickdeals_{len(products)}",
                                "name": title_elem.get_text(strip=True)[:100],
                                "retailer": store_elem.get_text(strip=True) if store_elem else "Various",
                                "retailer_id": "slickdeals",
                                "price": price,
                                "url": "https://slickdeals.net" + title_elem.get('href', ''),
                                "source": "SlickDeals",
                                "is_deal": True,
                                "deal_score": "Hot Deal",
                            })
                    except Exception as e:
                        continue
                
                return products
        except Exception as e:
            logger.warning(f"SlickDeals scrape error: {e}")
            return []

    async def _scrape_amazon(self, query: str) -> List[Dict]:
        """Scrape Amazon search results"""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
                response = await client.get(url, headers={"User-Agent": self.user_agent})
                
                if response.status_code != 200:
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                products = []
                
                for item in soup.select('[data-component-type="s-search-result"]')[:5]:
                    try:
                        title_elem = item.select_one('h2 a span')
                        price_elem = item.select_one('.a-price-whole')
                        rating_elem = item.select_one('.a-icon-star-small span')
                        reviews_elem = item.select_one('[aria-label*="ratings"]')
                        
                        if title_elem and price_elem:
                            price_text = price_elem.get_text(strip=True).replace(',', '')
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0
                            
                            if price > 0:
                                products.append({
                                    "id": f"amazon_{len(products)}",
                                    "name": title_elem.get_text(strip=True)[:100],
                                    "retailer": "Amazon",
                                    "retailer_id": "amazon",
                                    "price": price,
                                    "url": "https://www.amazon.com" + item.select_one('h2 a')['href'] if item.select_one('h2 a') else f"https://www.amazon.com/s?k={query}",
                                    "rating": float(rating_elem.get_text(strip=True).split()[0]) if rating_elem else 4.0,
                                    "reviews": int(re.sub(r'[^\d]', '', reviews_elem.get_text())) if reviews_elem else 0,
                                    "source": "Amazon (Scraped)",
                                    "in_stock": True,
                                    "benefits": self.retailers["amazon"]["benefits"],
                                })
                    except Exception as e:
                        continue
                
                logger.info(f"Scraped {len(products)} products from Amazon")
                return products
        except Exception as e:
            logger.warning(f"Amazon scrape error: {e}")
            return []
    
    async def _scrape_walmart(self, query: str) -> List[Dict]:
        """Scrape Walmart search results"""
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                url = f"https://www.walmart.com/search?q={query.replace(' ', '+')}"
                response = await client.get(url, headers={"User-Agent": self.user_agent})
                
                if response.status_code != 200:
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                products = []
                
                for item in soup.select('[data-item-id]')[:5]:
                    try:
                        title_elem = item.select_one('[data-automation-id="product-title"]')
                        price_elem = item.select_one('[data-automation-id="product-price"] span')
                        
                        if title_elem and price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0
                            
                            if price > 0:
                                products.append({
                                    "id": f"walmart_{len(products)}",
                                    "name": title_elem.get_text(strip=True)[:100],
                                    "retailer": "Walmart",
                                    "retailer_id": "walmart",
                                    "price": price,
                                    "url": f"https://www.walmart.com/search?q={query}",
                                    "source": "Walmart (Scraped)",
                                    "in_stock": True,
                                    "benefits": self.retailers["walmart"]["benefits"],
                                })
                    except Exception as e:
                        continue
                
                logger.info(f"Scraped {len(products)} products from Walmart")
                return products
        except Exception as e:
            logger.warning(f"Walmart scrape error: {e}")
            return []
    
    async def _scrape_google_shopping(self, query: str) -> List[Dict]:
        """Scrape Google Shopping results"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://www.google.com/search?tbm=shop&q={query.replace(' ', '+')}"
                response = await client.get(url, headers={"User-Agent": self.user_agent})
                
                if response.status_code != 200:
                    return []
                
                soup = BeautifulSoup(response.text, 'html.parser')
                products = []
                
                # Parse shopping results
                for item in soup.select('.sh-dgr__content, .sh-dlr__list-result')[:5]:
                    try:
                        title_elem = item.select_one('.tAxDx, h3')
                        price_elem = item.select_one('.a8Pemb, .kHxwFf')
                        store_elem = item.select_one('.aULzUe, .IuHnof')
                        
                        if title_elem and price_elem:
                            price_text = price_elem.get_text(strip=True)
                            price = float(re.sub(r'[^\d.]', '', price_text)) if price_text else 0
                            
                            products.append({
                                "id": f"google_{len(products)}",
                                "name": title_elem.get_text(strip=True)[:100],
                                "retailer": store_elem.get_text(strip=True) if store_elem else "Various",
                                "retailer_id": "google_shopping",
                                "price": price,
                                "url": f"https://www.google.com/search?tbm=shop&q={query}",
                                "source": "Google Shopping",
                            })
                    except Exception:
                        continue
                
                return products
        except Exception as e:
            logger.warning(f"Google Shopping scrape error: {e}")
            return []

    async def _find_coupons(self, query: str) -> List[Dict]:
        """Return only provider-verified coupons; no coupon feed configured."""
        return []

    async def _get_cashback_rates(self, query: str) -> Dict[str, List[Dict]]:
        """No live rewards feed is configured; do not advertise invented rates."""
        return {}

    def _calculate_true_costs(self, products: List[Dict], coupons: List[Dict], cashback: Dict) -> List[Dict]:
        """Rank observed subtotals. Rewards and unknown tax are not cash savings."""
        from decimal import Decimal, InvalidOperation
        analyzed = []
        for product in products:
            try:
                price = Decimal(str(product.get("price")))
                if not price.is_finite() or price <= 0:
                    continue
                raw_shipping = product.get("shipping")
                shipping = Decimal("0") if str(raw_shipping).lower() == "free" else Decimal(str(raw_shipping))
                if not shipping.is_finite() or shipping < 0:
                    shipping = None
            except (InvalidOperation, TypeError, ValueError):
                try:
                    price = Decimal(str(product.get("price")))
                    if not price.is_finite() or price <= 0:
                        continue
                except (InvalidOperation, TypeError, ValueError):
                    continue
                shipping = None
            # A discount needs structured value, verified eligibility and exact offer binding.
            best, savings = None, Decimal("0")
            for coupon in coupons:
                if not (coupon.get("verified") is True and coupon.get("eligible") is True
                        and product.get("id") and coupon.get("product_id") == product.get("id")):
                    continue
                try:
                    value = Decimal(str(coupon.get("value")))
                    if not value.is_finite() or value < 0:
                        continue
                    amount = price * value / 100 if coupon.get("type") == "percent" else value if coupon.get("type") == "fixed" else Decimal("0")
                    amount = min(price, amount)
                    if amount > savings:
                        best, savings = coupon, amount
                except (InvalidOperation, TypeError, ValueError):
                    continue
            subtotal = price + (shipping or Decimal("0")) - savings
            analyzed.append({**product, "base_price": float(price), "shipping_cost": float(shipping) if shipping is not None else None,
                "coupon_savings": float(savings), "best_coupon": best, "cashback_rate": "0%", "cashback_savings": 0,
                "cashback_source": None, "true_cost": float(subtotal.quantize(Decimal("0.01"))),
                "price_complete": False, "price_note": "Observed subtotal; confirm tax, shipping and availability with merchant",
                "total_savings": float(savings), "value_score": self._calculate_value_score(product, float(subtotal), float(savings))})
        return sorted(analyzed, key=lambda p: p["true_cost"])

    def _calculate_value_score(self, product: Dict, true_cost: float, savings: float) -> float:
        """Calculate overall value score (0-100)"""
        score = 50  # Base score
        
        # Price factor (lower is better)
        if true_cost < 100:
            score += 15
        elif true_cost < 250:
            score += 10
        elif true_cost < 500:
            score += 5
        
        # Savings factor
        if savings > 50:
            score += 20
        elif savings > 20:
            score += 15
        elif savings > 10:
            score += 10
        elif savings > 0:
            score += 5
        
        # Benefits factor
        benefits = product.get("benefits", [])
        if "Free" in str(benefits):
            score += 5
        if "return" in str(benefits).lower():
            score += 5
        if "warranty" in str(benefits).lower():
            score += 5
        
        # Rating factor
        rating = product.get("rating", 0)
        if rating >= 4.5:
            score += 10
        elif rating >= 4.0:
            score += 5
        
        return min(100, score)

    async def _get_ai_recommendation(self, query: str, options: List[Dict], budget: Optional[float]) -> Dict:
        """Get AI-powered recommendation using local LLM"""
        if not options:
            return {"recommendation": "No products found", "reasoning": ""}
        
        best_option = options[0]
        
        # Build prompt for AI analysis
        options_summary = []
        for i, opt in enumerate(options[:5]):
            options_summary.append(f"""
{i+1}. {opt['retailer']}: ${opt['true_cost']:.2f} (List: ${opt['base_price']:.2f})
   - Savings: ${opt['total_savings']:.2f} (Coupon: ${opt['coupon_savings']:.2f}, Cashback: ${opt['cashback_savings']:.2f})
   - Benefits: {', '.join(opt.get('benefits', [])[:3])}
   - Value Score: {opt['value_score']}/100
""")
        
        prompt = f"""As a shopping expert, analyze these options for buying "{query}" and recommend the best value:

{chr(10).join(options_summary)}

{"Budget limit: $" + str(budget) if budget else "No budget limit specified."}

Provide a brief recommendation (2-3 sentences) on which retailer offers the best overall value considering price, savings, and benefits. Focus on actionable advice."""

        try:
            ai_text = (await llm_generate(
                prompt, task="shopping", temperature=0.3,
                max_tokens=200, timeout=30,
            )).strip()

            if ai_text:
                return {
                    "best_retailer": best_option["retailer"],
                    "best_price": best_option["true_cost"],
                    "recommendation": ai_text,
                    "confidence": "high" if best_option["value_score"] > 70 else "medium",
                    "action_items": [
                        f"Use {best_option.get('cashback_source', 'Rakuten')} for {best_option.get('cashback_rate', '0%')} cashback",
                        f"Apply coupon: {best_option.get('best_coupon', {}).get('code', 'Check retailer site')}",
                        f"Total savings potential: ${best_option['total_savings']:.2f}",
                    ]
                }
        except Exception as e:
            logger.warning(f"AI recommendation error: {e}")
        
        # Fallback recommendation without AI
        return {
            "best_retailer": best_option["retailer"],
            "best_price": best_option["true_cost"],
            "recommendation": f"Best value is at {best_option['retailer']} for ${best_option['true_cost']:.2f} after all discounts. You can save ${best_option['total_savings']:.2f} using available coupons and cashback.",
            "confidence": "medium",
            "action_items": [
                f"Use {best_option.get('cashback_source', 'Rakuten')} for cashback",
                f"Check for coupon codes before checkout",
                f"Compare with other retailers for price match",
            ]
        }

    # Product catalog: (keywords, price). Checked in order — most specific first.
    # Prices reflect typical US street prices (2026).
    PRODUCT_CATALOG = [
        # Apple — specific models first
        (["mac mini m4 pro"], 1399.00),
        (["mac mini"], 599.00),
        (["mac studio"], 1999.00),
        (["macbook pro 16"], 2499.00),
        (["macbook pro 14", "macbook pro"], 1599.00),
        (["macbook air 15"], 1199.00),
        (["macbook air"], 999.00),
        (["imac"], 1299.00),
        (["ipad pro"], 999.00),
        (["ipad air"], 599.00),
        (["ipad mini"], 499.00),
        (["ipad"], 349.00),
        (["iphone 17 pro max", "iphone pro max"], 1199.00),
        (["iphone 17 pro", "iphone pro"], 999.00),
        (["iphone 17", "iphone 16"], 799.00),
        (["iphone se"], 429.00),
        (["iphone"], 799.00),
        (["apple watch ultra"], 799.00),
        (["apple watch"], 399.00),
        (["airpods max"], 549.00),
        (["airpods pro"], 249.00),
        (["airpods"], 129.00),
        (["apple tv"], 129.00),
        (["homepod mini"], 99.00),
        (["homepod"], 299.00),
        # Other electronics
        (["ps5 pro", "playstation 5 pro"], 699.99),
        (["ps5", "playstation 5", "playstation"], 499.99),
        (["xbox series x"], 499.99),
        (["xbox series s"], 299.99),
        (["nintendo switch 2"], 449.99),
        (["nintendo switch"], 299.99),
        (["steam deck"], 399.00),
        (["meta quest 3"], 499.99),
        (["kindle paperwhite"], 159.99),
        (["kindle"], 109.99),
        (["galaxy s25 ultra", "galaxy ultra"], 1299.99),
        (["galaxy s25", "samsung galaxy"], 799.99),
        (["pixel 10 pro", "pixel pro"], 999.00),
        (["pixel"], 699.00),
        (["sony wh-1000xm6", "sony wh-1000xm5", "sony headphones"], 399.99),
        (["bose quietcomfort"], 349.00),
        (["gopro"], 399.99),
        (["dji drone", "dji mini"], 759.00),
        (["roomba", "robot vacuum"], 549.99),
        (["dyson vacuum", "dyson v15"], 649.99),
        (["dyson airwrap"], 599.99),
        (["instant pot"], 99.95),
        (["air fryer"], 119.99),
        (["espresso machine", "breville"], 699.95),
        (["vitamix", "blender"], 349.95),
        (["stand mixer", "kitchenaid"], 449.99),
        # Accessories — MUST precede the generic device entries below so
        # 'laptop stand' / 'phone case' price the accessory, not the device
        (["phone case", "case for", "screen protector"], 24.99),
        (["usb microphone", "usb mic", "condenser microphone"], 129.99),
        (["microphone", "mic"], 99.99),
        (["webcam"], 79.99),
        (["headset", "gaming headset"], 89.99),
        (["usb hub", "usb-c hub", "docking station", "dock"], 89.99),
        (["charger", "charging cable", "power adapter"], 29.99),
        (["mouse pad", "desk mat"], 24.99),
        (["laptop stand", "monitor stand"], 49.99),
        (["cable", "adapter"], 19.99),
        (["external ssd", "external hard drive", "ssd"], 119.99),
        (["ram", "memory"], 89.99),
        # Generic categories
        (["gaming laptop"], 1499.99),
        (["laptop", "computer", "notebook"], 899.99),
        (["desktop pc", "desktop"], 999.99),
        (["smartphone", "phone"], 699.99),
        (["headphones", "earbuds"], 149.99),
        (["oled tv"], 1299.99),
        (["tv", "television"], 499.99),
        (["4k monitor", "ultrawide monitor"], 449.99),
        (["monitor"], 299.99),
        (["tablet"], 399.99),
        (["smartwatch", "watch"], 299.99),
        (["camera"], 449.99),
        (["soundbar"], 249.99),
        (["speaker"], 199.99),
        (["printer", "scanner"], 179.99),
        (["mechanical keyboard"], 129.99),
        (["keyboard", "mouse"], 79.99),
        (["office chair", "gaming chair"], 349.99),
        (["standing desk"], 449.99),
        (["chair", "desk"], 299.99),
        (["mattress", "bed"], 699.99),
        # Groceries and beverages
        (["coconut water", "juice", "soda", "sparkling water"], 12.99),
        (["water"], 8.99),
        (["milk", "yogurt", "cheese"], 5.99),
        (["bread", "cereal", "pasta"], 4.99),
        (["chicken", "beef", "meat"], 8.99),
        (["coffee", "tea"], 14.99),
    ]

    def _estimate_base_price(self, query: str) -> float:
        """Estimate a realistic base price via specificity-ordered catalog lookup.

        Strips trailing context like 'for mac mini' / 'for iphone' so accessory
        queries price the accessory, not the device it pairs with.
        """
        query_lower = query.lower().strip()
        # 'X for <device>' — the product is X, not the device
        m = re.match(r"^(.*?)\s+for\s+(?:my\s+|the\s+|a\s+|an\s+)?(.+)$", query_lower)
        if m and m.group(1).strip():
            query_lower = m.group(1).strip()
        for keywords, price in self.PRODUCT_CATALOG:
            # Word-boundary match: 'microphone' must not hit the 'phone' entry
            if any(re.search(r"\b" + re.escape(kw) + r"\b", query_lower) for kw in keywords):
                return price
        return 49.99  # Default for unrecognized items

    def _get_category_base_price(self, query: str) -> float:
        """
        Get realistic base price for food/grocery items with quality tiers.
        Returns 0 if not a recognized food category (falls back to _estimate_base_price).
        
        Dirty Dozen items are priced at organic tier by default.
        """
        q = query.lower()

        # Dirty Dozen (EWG) — ALWAYS organic pricing
        dirty_dozen = [
            "strawberries", "spinach", "kale", "peaches", "pears",
            "nectarines", "apples", "grapes", "bell peppers",
            "cherries", "blueberries", "green beans",
        ]

        # Meat & poultry pricing (per lb or per package)
        if "organic chicken" in q:
            return 28.99  # ~$7/lb × 4lb pack, organic
        elif "chicken breast" in q:
            return 12.99 if "organic" not in q else 24.99
        elif "chicken" in q:
            return 8.99 if "organic" not in q else 22.99
        elif "organic beef" in q or "grass fed beef" in q:
            return 32.99
        elif "beef" in q or "steak" in q:
            return 15.99
        elif "salmon" in q or "fish" in q:
            return 14.99 if "wild" not in q else 24.99
        elif "turkey" in q:
            return 9.99 if "organic" not in q else 18.99

        # Check Dirty Dozen — force organic pricing
        for item in dirty_dozen:
            if item in q:
                return self._organic_price(item)

        # Dairy
        if "organic milk" in q:
            return 7.99
        elif "milk" in q:
            return 4.99
        elif "organic eggs" in q or "pasture" in q:
            return 8.99
        elif "eggs" in q:
            return 4.49
        elif "cheese" in q:
            return 6.99
        elif "yogurt" in q:
            return 5.99 if "organic" not in q else 8.49

        # Produce
        if "organic" in q:
            return 6.99  # Generic organic produce
        elif any(w in q for w in ["fruit", "vegetable", "salad", "lettuce"]):
            return 4.99

        # Pantry
        if "rice" in q or "quinoa" in q:
            return 5.99 if "organic" not in q else 8.99
        elif "olive oil" in q:
            return 12.99
        elif "bread" in q:
            return 4.99 if "organic" not in q else 6.99

        return 0  # Not a food item — use _estimate_base_price

    def _organic_price(self, item: str) -> float:
        """Organic pricing for Dirty Dozen items."""
        prices = {
            "strawberries": 7.99, "spinach": 5.99, "kale": 4.99,
            "peaches": 6.99, "pears": 5.99, "nectarines": 6.99,
            "apples": 5.99, "grapes": 7.99, "bell peppers": 5.49,
            "cherries": 9.99, "blueberries": 7.99, "green beans": 4.99,
        }
        return prices.get(item, 5.99)

    def _get_shipping_cost(self, retailer_id: str, price: float) -> str:
        """Get shipping cost/info for retailer"""
        if retailer_id in ["amazon"]:
            return "Free with Prime" if price > 25 else "$5.99"
        elif retailer_id in ["walmart", "target", "bestbuy"]:
            return "Free" if price > 35 else "$5.99"
        elif retailer_id == "costco":
            return "Varies by item"
        else:
            return "Free" if price > 50 else "$4.99"

    def _get_delivery_estimate(self, retailer_id: str) -> str:
        """Get delivery estimate for retailer"""
        estimates = {
            "amazon": "1-2 days (Prime)",
            "walmart": "2-3 days",
            "bestbuy": "2-5 days",
            "target": "2-4 days",
            "costco": "3-7 days",
            "newegg": "3-5 days",
        }
        return estimates.get(retailer_id, "3-7 days")

    def _calculate_total_savings(self, options: List[Dict]) -> Dict:
        """Calculate potential savings summary"""
        if not options:
            return {"max_savings": 0, "avg_savings": 0}
        
        savings = [opt.get("total_savings", 0) for opt in options]
        return {
            "max_savings": round(max(savings), 2),
            "avg_savings": round(sum(savings) / len(savings), 2),
            "best_deal_retailer": options[0]["retailer"] if options else None,
        }


# Singleton instance
_smart_shopping_service = None

def get_smart_shopping_service() -> SmartShoppingService:
    global _smart_shopping_service
    if _smart_shopping_service is None:
        _smart_shopping_service = SmartShoppingService()
    return _smart_shopping_service
