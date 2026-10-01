"""
Screener.in Client - Indian stock fundamentals and screening.

Provides fundamental analysis data for Indian stocks including
financials, ratios, and peer comparison from Screener.in.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCREENER_BASE = "https://www.screener.in"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


class ScreenerClient:
    """Async client for Screener.in Indian stock data."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    async def get_company(self, symbol: str) -> Dict[str, Any]:
        """Get company fundamentals from Screener.in."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{SCREENER_BASE}/company/{symbol}/consolidated/"
                resp = await client.get(url, headers=HEADERS)

                if resp.status_code != 200:
                    # Try standalone
                    url = f"{SCREENER_BASE}/company/{symbol}/"
                    resp = await client.get(url, headers=HEADERS)

                if resp.status_code != 200:
                    return {"symbol": symbol, "error": f"HTTP {resp.status_code}"}

                soup = BeautifulSoup(resp.text, "html.parser")
                return self._parse_company_page(symbol, soup)

        except Exception as e:
            logger.error(f"Screener error for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}

    def _parse_company_page(self, symbol: str, soup: BeautifulSoup) -> Dict[str, Any]:
        """Parse company page HTML into structured data."""
        result: Dict[str, Any] = {"symbol": symbol, "source": "screener.in"}

        # Company name
        name_elem = soup.find("h1")
        if name_elem:
            result["name"] = name_elem.get_text(strip=True)

        # Key ratios from the top section
        ratios_section = soup.find("div", id="top-ratios")
        if ratios_section:
            items = ratios_section.find_all("li")
            for item in items:
                name_span = item.find("span", class_="name")
                value_span = item.find("span", class_="number")
                if name_span and value_span:
                    key = name_span.get_text(strip=True).lower().replace(" ", "_").replace(".", "")
                    val = value_span.get_text(strip=True)
                    result[key] = val

        # Pros and cons
        for section_name in ["pros", "cons"]:
            section = soup.find("div", class_=section_name)
            if section:
                items = section.find_all("li")
                result[section_name] = [li.get_text(strip=True) for li in items]

        # Peer comparison
        peer_table = soup.find("table", class_="data-table")
        if peer_table:
            peers = []
            rows = peer_table.find_all("tr")[1:6]  # Top 5 peers
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    peers.append({
                        "name": cols[0].get_text(strip=True),
                        "cmp": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                        "pe": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    })
            result["peers"] = peers

        result["fetched_at"] = datetime.now().isoformat()
        return result

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Search for companies on Screener.in."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                url = f"{SCREENER_BASE}/api/company/search/"
                resp = await client.get(url, params={"q": query}, headers=HEADERS)

                if resp.status_code == 200:
                    data = resp.json()
                    return [
                        {"name": item.get("name", ""), "url": item.get("url", "")}
                        for item in data[:10]
                    ]
        except Exception as e:
            logger.error(f"Screener search error: {e}")
        return []
