"""
Pulse by Zerodha news scraper for Indian market
"""

import httpx
from bs4 import BeautifulSoup
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PulseScraper:
    """
    Scrape news from Pulse by Zerodha (https://pulse.zerodha.com/)
    """
    
    def __init__(self):
        self.url = "https://pulse.zerodha.com/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36"
        }
    
    async def fetch_latest_news(self, limit: int = 20) -> List[Dict]:
        """
        Fetch latest news from Pulse
        
        Returns:
            List of news items with headline, URL, metadata
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.url, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Pulse scraper failed: HTTP {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, "html.parser")
            news_items = []
            
            # Pulse uses <li> tags with class 'item' for news blocks
            articles = soup.find_all("li", class_="item", limit=limit)
            
            for item in articles:
                try:
                    # Extract headline
                    headline_tag = item.find("h2")
                    headline = headline_tag.text.strip() if headline_tag else ""
                    
                    # Extract link
                    link_tag = item.find("a")
                    link = link_tag["href"] if link_tag and "href" in link_tag.attrs else ""
                    
                    # Make link absolute if relative
                    if link and not link.startswith("http"):
                        link = f"https://pulse.zerodha.com{link}"
                    
                    # Extract metadata (time and source)
                    meta_tag = item.find("div", class_="meta")
                    metadata = meta_tag.text.strip() if meta_tag else ""
                    
                    # Extract source from metadata
                    source = self._extract_source(metadata)
                    
                    # Extract time from metadata
                    time_posted = self._extract_time(metadata)
                    
                    if headline:
                        news_items.append({
                            "headline": headline,
                            "url": link,
                            "source": source,
                            "time_posted": time_posted,
                            "metadata": metadata,
                            "fetched_at": datetime.now().isoformat()
                        })
                
                except Exception as e:
                    logger.warning(f"Failed to parse news item: {e}")
                    continue
            
            logger.info(f"Fetched {len(news_items)} news items from Pulse")
            return news_items
        
        except Exception as e:
            logger.error(f"Pulse scraping error: {e}")
            return []
    
    def _extract_source(self, metadata: str) -> str:
        """
        Extract source from metadata string
        Example: "2 hours ago — Economic Times"
        """
        if "—" in metadata:
            parts = metadata.split("—")
            if len(parts) > 1:
                return parts[1].strip()
        
        # Common sources
        sources = [
            "Economic Times", "Moneycontrol", "Business Standard",
            "Livemint", "NDTV Profit", "Bloomberg Quint"
        ]
        
        for source in sources:
            if source.lower() in metadata.lower():
                return source
        
        return "Unknown"
    
    def _extract_time(self, metadata: str) -> str:
        """
        Extract time from metadata string
        Example: "2 hours ago — Economic Times"
        """
        if "—" in metadata:
            parts = metadata.split("—")
            if len(parts) > 0:
                return parts[0].strip()
        
        return metadata.strip()
    
    async def fetch_by_category(self, category: str = "markets") -> List[Dict]:
        """
        Fetch news by category
        
        Categories: markets, economy, policy, corporate
        """
        category_url = f"{self.url}category/{category}"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(category_url, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Category fetch failed: HTTP {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.content, "html.parser")
            news_items = []
            
            articles = soup.find_all("li", class_="item")
            
            for item in articles:
                try:
                    headline_tag = item.find("h2")
                    headline = headline_tag.text.strip() if headline_tag else ""
                    
                    link_tag = item.find("a")
                    link = link_tag["href"] if link_tag and "href" in link_tag.attrs else ""
                    
                    if link and not link.startswith("http"):
                        link = f"https://pulse.zerodha.com{link}"
                    
                    meta_tag = item.find("div", class_="meta")
                    metadata = meta_tag.text.strip() if meta_tag else ""
                    
                    if headline:
                        news_items.append({
                            "headline": headline,
                            "url": link,
                            "category": category,
                            "source": self._extract_source(metadata),
                            "time_posted": self._extract_time(metadata),
                            "fetched_at": datetime.now().isoformat()
                        })
                
                except Exception as e:
                    logger.warning(f"Failed to parse category item: {e}")
                    continue
            
            return news_items
        
        except Exception as e:
            logger.error(f"Category scraping error: {e}")
            return []
    
    async def search_keyword(self, keyword: str) -> List[Dict]:
        """
        Search for news containing specific keyword
        """
        all_news = await self.fetch_latest_news(limit=50)
        
        # Filter by keyword
        filtered = [
            item for item in all_news
            if keyword.lower() in item["headline"].lower()
        ]
        
        return filtered
