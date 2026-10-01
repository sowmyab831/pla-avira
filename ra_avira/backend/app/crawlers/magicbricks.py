"""
MagicBricks Crawler
Crawls property listings from magicbricks.com for Hyderabad.
"""
import re
import json
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from app.crawlers.base_crawler import BaseCrawler, CrawlConfig


class MagicBricksCrawler(BaseCrawler):
    """Crawler for MagicBricks property listings."""

    @property
    def source_name(self) -> str:
        return "magicbricks"

    @property
    def base_url(self) -> str:
        return "https://www.magicbricks.com"

    async def build_search_url(self, area: str, page: int, **filters) -> str:
        """Build MagicBricks search URL."""
        property_type = filters.get("property_type", "residential")
        transaction = filters.get("transaction", "buy")
        
        # MagicBricks URL pattern
        url = f"{self.base_url}/property-for-sale/residential-real-estate"
        url += f"?bedroom=&proptype=Multistorey-Apartment,Builder-Floor-Apartment,Penthouse,Studio-Apartment,Residential-House,Villa"
        url += f"&cityName=Hyderabad"
        url += f"&BudgetMin=&BudgetMax="
        url += f"&locality={area.replace('-', '+')}"
        
        if page > 1:
            url += f"&page={page}"
        
        return url

    async def parse_listing_page(self, html: str) -> List[Dict]:
        """Parse MagicBricks search results page."""
        listings = []
        soup = BeautifulSoup(html, "html.parser")

        # Try to find JSON-LD structured data first
        scripts = soup.find_all("script", type="application/ld+json")
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type") == "Product":
                            listing = self._extract_from_jsonld(item)
                            if listing:
                                listings.append(listing)
            except (json.JSONDecodeError, TypeError):
                continue

        # Fallback: Parse HTML cards
        if not listings:
            cards = soup.find_all("div", class_=re.compile(r"mb-srp__card"))
            for card in cards:
                listing = self._extract_from_card(card)
                if listing:
                    listings.append(listing)

        return listings

    async def parse_detail_page(self, html: str, url: str) -> Dict:
        """Parse MagicBricks property detail page."""
        soup = BeautifulSoup(html, "html.parser")
        data = {}

        # Title
        title_el = soup.find("h1")
        if title_el:
            data["title"] = title_el.get_text(strip=True)

        # Price
        price_el = soup.find("div", class_=re.compile(r"price"))
        if price_el:
            data["price"] = price_el.get_text(strip=True)

        # Details section
        details = soup.find_all("div", class_=re.compile(r"detail"))
        for detail in details:
            text = detail.get_text(strip=True).lower()
            if "sqft" in text or "sq.ft" in text:
                data["area"] = text
            elif "bhk" in text:
                match = re.search(r"(\d+)\s*bhk", text)
                if match:
                    data["bedrooms"] = int(match.group(1))

        # Amenities
        amenity_els = soup.find_all("div", class_=re.compile(r"amenity"))
        data["amenities"] = [a.get_text(strip=True) for a in amenity_els]

        # Images
        img_els = soup.find_all("img", class_=re.compile(r"property"))
        data["images"] = [img.get("src") for img in img_els if img.get("src")]

        # RERA
        rera_el = soup.find(string=re.compile(r"RERA", re.I))
        if rera_el:
            rera_match = re.search(r"[A-Z]{2}/\d+/\d+/\d+", rera_el.parent.get_text())
            if rera_match:
                data["rera_id"] = rera_match.group()

        data["url"] = url
        data["source"] = "magicbricks"
        return data

    def _extract_from_jsonld(self, item: Dict) -> Optional[Dict]:
        """Extract property data from JSON-LD structured data."""
        try:
            offers = item.get("offers", {})
            return {
                "title": item.get("name", ""),
                "price": offers.get("price", "0"),
                "description": item.get("description", ""),
                "url": item.get("url", ""),
                "images": [item.get("image", "")],
                "id": item.get("sku", ""),
                "source": "magicbricks",
            }
        except Exception:
            return None

    def _extract_from_card(self, card) -> Optional[Dict]:
        """Extract property data from HTML card element."""
        try:
            data = {}

            # Title & link
            title_el = card.find("h2") or card.find("a", class_=re.compile(r"title"))
            if title_el:
                data["title"] = title_el.get_text(strip=True)
                link = title_el.find("a")
                if link:
                    data["url"] = self.base_url + link.get("href", "")

            # Price
            price_el = card.find("div", class_=re.compile(r"price"))
            if price_el:
                data["price"] = price_el.get_text(strip=True)

            # Area
            area_el = card.find("div", class_=re.compile(r"area|size"))
            if area_el:
                data["superArea"] = area_el.get_text(strip=True)

            # BHK
            bhk_el = card.find("div", class_=re.compile(r"bhk|bed"))
            if bhk_el:
                match = re.search(r"(\d+)", bhk_el.get_text())
                if match:
                    data["bedrooms"] = int(match.group(1))

            # Location
            loc_el = card.find("div", class_=re.compile(r"locality|location"))
            if loc_el:
                data["locality"] = loc_el.get_text(strip=True)

            # Images
            img_el = card.find("img")
            if img_el and img_el.get("src"):
                data["images"] = [img_el["src"]]

            data["source"] = "magicbricks"
            return data if data.get("title") else None
        except Exception:
            return None
