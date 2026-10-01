"""
Base Crawler Framework
Abstract base for all property listing crawlers.
Handles rate limiting, retries, session management, and error handling.
"""
import asyncio
import random
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


@dataclass
class CrawlResult:
    source: str
    listings: List[Dict]
    total_found: int
    pages_crawled: int
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0
    crawled_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CrawlConfig:
    max_pages: int = 50
    delay_min: float = 2.0
    delay_max: float = 5.0
    timeout: int = 30
    max_retries: int = 3
    concurrent_requests: int = 2
    proxy: Optional[str] = None
    city: str = "hyderabad"
    areas: List[str] = field(default_factory=lambda: [
        "gachibowli", "kokapet", "financial-district", "kondapur",
        "madhapur", "jubilee-hills", "hitech-city", "narsingi", "tellapur",
    ])


class BaseCrawler(ABC):
    """Abstract base class for property listing crawlers."""

    USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]

    def __init__(self, config: Optional[CrawlConfig] = None):
        self.config = config or CrawlConfig()
        self.session: Optional[httpx.AsyncClient] = None
        self._request_count = 0
        self._start_time = 0

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of this crawler source."""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Base URL for the listing site."""
        pass

    @abstractmethod
    async def build_search_url(self, area: str, page: int, **filters) -> str:
        """Build search URL for given area and page."""
        pass

    @abstractmethod
    async def parse_listing_page(self, html: str) -> List[Dict]:
        """Parse a listing page and extract property data."""
        pass

    @abstractmethod
    async def parse_detail_page(self, html: str, url: str) -> Dict:
        """Parse a property detail page."""
        pass

    async def crawl(self, **filters) -> CrawlResult:
        """Execute the crawl across all configured areas."""
        self._start_time = time.time()
        all_listings = []
        errors = []
        pages_crawled = 0

        async with httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
            headers=self._get_headers(),
        ) as client:
            self.session = client

            for area in self.config.areas:
                try:
                    area_listings, area_pages = await self._crawl_area(area, **filters)
                    all_listings.extend(area_listings)
                    pages_crawled += area_pages
                    logger.info(
                        "area_crawled",
                        source=self.source_name,
                        area=area,
                        listings=len(area_listings),
                        pages=area_pages,
                    )
                except Exception as e:
                    error_msg = f"Error crawling {area}: {str(e)}"
                    errors.append(error_msg)
                    logger.error("crawl_error", source=self.source_name, area=area, error=str(e))

        duration = time.time() - self._start_time

        return CrawlResult(
            source=self.source_name,
            listings=all_listings,
            total_found=len(all_listings),
            pages_crawled=pages_crawled,
            errors=errors,
            duration_seconds=round(duration, 2),
        )

    async def _crawl_area(self, area: str, **filters) -> tuple:
        """Crawl all pages for a specific area."""
        listings = []
        page = 1

        while page <= self.config.max_pages:
            url = await self.build_search_url(area, page, **filters)
            html = await self._fetch_page(url)

            if not html:
                break

            page_listings = await self.parse_listing_page(html)

            if not page_listings:
                break

            listings.extend(page_listings)
            page += 1

            # Rate limiting
            await self._rate_limit()

        return listings, page - 1

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with retries and rate limiting."""
        try:
            response = await self.session.get(url, headers=self._get_headers())
            self._request_count += 1

            if response.status_code == 200:
                return response.text
            elif response.status_code == 429:
                # Rate limited - wait longer
                await asyncio.sleep(random.uniform(10, 30))
                raise Exception("Rate limited")
            elif response.status_code in (403, 503):
                logger.warning("blocked", source=self.source_name, url=url, status=response.status_code)
                return None
            else:
                logger.warning("http_error", source=self.source_name, url=url, status=response.status_code)
                return None
        except httpx.TimeoutException:
            logger.warning("timeout", source=self.source_name, url=url)
            return None

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        delay = random.uniform(self.config.delay_min, self.config.delay_max)
        await asyncio.sleep(delay)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with random user agent."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
