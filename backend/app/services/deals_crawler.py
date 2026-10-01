"""
Deals Crawler — aggregates best deals from multiple sources.

Sources:
 1. SlickDeals RSS (frontpage + popular)
 2. DealNews RSS
 3. Ben's Bargains RSS
 4. Woot deals
 5. Reddit r/deals, r/buildapcsales, r/frugal
 6. Credit card points optimization (static knowledge base)

Also supports watchlist monitoring — checks if any item on the user's
watchlist has a new deal matching keywords.
"""
from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
_TIMEOUT = httpx.Timeout(12.0, connect=5.0)

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}
CACHE_TTL = 900


def _cached(key: str) -> Optional[Any]:
    if key in _cache and (datetime.now().timestamp() - _cache_ts.get(key, 0)) < CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key: str, val: Any):
    _cache[key] = val
    _cache_ts[key] = datetime.now().timestamp()


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

DEAL_FEEDS = {
    "SlickDeals Frontpage": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    "SlickDeals Popular": "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1",
    "DealNews Editors' Choice": "https://www.dealnews.com/rss/features/editors-choice/",
    "DealNews Today": "https://www.dealnews.com/rss/features/todays-edition/",
    "Amazon Price Drops (camelcamelcamel)": "https://camelcamelcamel.com/top_drops/feed",
}

REDDIT_DEAL_SUBS = [
    "deals", "buildapcsales", "frugal", "GameDeals",
]


async def _fetch_rss_deals(name: str, url: str, client: httpx.AsyncClient) -> List[Dict]:
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        atom = False
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            atom = True
        deals = []
        A = "{http://www.w3.org/2005/Atom}"
        for item in items[:15]:
            if atom:
                title = (item.findtext(f"{A}title") or "").strip()
                link_el = item.find(f"{A}link")
                link = (link_el.get("href") if link_el is not None else "") or ""
                desc = re.sub(r"<[^>]+>", "", item.findtext(f"{A}content") or item.findtext(f"{A}summary") or "")[:300].strip()
                pub = (item.findtext(f"{A}updated") or item.findtext(f"{A}published") or "").strip()
            else:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "")[:300].strip()
                pub = (item.findtext("pubDate") or "").strip()
            # Try to extract price from title
            price_match = re.search(r'\$[\d,]+\.?\d*', title)
            price = price_match.group(0) if price_match else None
            deals.append({
                "source": name,
                "title": title,
                "url": link,
                "description": desc,
                "published": pub,
                "price": price,
            })
        return deals
    except Exception as e:
        logger.warning(f"RSS deal fetch error {name}: {e}")
        return []


async def _fetch_reddit_deals(client: httpx.AsyncClient) -> List[Dict]:
    """Reddit blocks unauthenticated .json; the Atom .rss endpoint is open."""
    results = await asyncio.gather(
        *[_fetch_rss_deals(f"Reddit r/{sub}", f"https://www.reddit.com/r/{sub}/hot.rss?limit=10", client) for sub in REDDIT_DEAL_SUBS],
        return_exceptions=True,
    )
    deals: List[Dict] = []
    for r in results:
        if isinstance(r, list):
            deals.extend(d for d in r if not d["title"].lower().startswith(("daily", "weekly", "megathread", "[meta]")))
    return deals


# ── Credit Card Points Knowledge Base ─────────────────────────────────────────

CREDIT_CARD_POINTS = {
    "travel": [
        {
            "card": "Chase Sapphire Reserve",
            "earn": "3x on travel & dining",
            "value": "1.5 cpp via portal",
            "annual_fee": "$550",
            "best_for": "Premium travel, lounge access, travel insurance",
            "transfer_partners": "United, Hyatt, Southwest, British Airways, Air France",
        },
        {
            "card": "Amex Platinum",
            "earn": "5x on flights, hotels via Amex Travel",
            "value": "1.5-2 cpp via transfers",
            "annual_fee": "$695",
            "best_for": "Airline lounges, luxury travel, hotel status",
            "transfer_partners": "Delta, JetBlue, Hilton, Marriott, ANA, Singapore",
        },
        {
            "card": "Capital One Venture X",
            "earn": "2x everything, 10x hotels/cars via portal",
            "value": "1-1.5 cpp",
            "annual_fee": "$395",
            "best_for": "Simple earning, Priority Pass, $300 travel credit",
            "transfer_partners": "Turkish, Avianca, Wyndham, Air Canada",
        },
        {
            "card": "Citi Strata Premier",
            "earn": "3x on travel, gas, groceries, dining, EV",
            "value": "1-1.5 cpp",
            "annual_fee": "$95",
            "best_for": "Best mid-tier card, wide bonus categories",
            "transfer_partners": "Turkish, Singapore, JetBlue, Avianca",
        },
    ],
    "cashback": [
        {
            "card": "Citi Double Cash",
            "earn": "2% on everything",
            "value": "2% flat",
            "annual_fee": "$0",
            "best_for": "Simple no-hassle cashback",
        },
        {
            "card": "Chase Freedom Unlimited",
            "earn": "1.5% + 3% dining/drugstore + 5% travel via portal",
            "value": "1.5-5%",
            "annual_fee": "$0",
            "best_for": "Pairs well with Sapphire for boosted redemption",
        },
        {
            "card": "Amex Blue Cash Preferred",
            "earn": "6% groceries, 6% streaming, 3% transit, 3% gas",
            "value": "Up to 6%",
            "annual_fee": "$95",
            "best_for": "Families with high grocery spend",
        },
    ],
    "flight_tips": [
        "Transfer Chase UR to Hyatt (best hotel value, 1:1)",
        "Transfer Amex MR to ANA for Star Alliance awards (sweet spot: 55k RT to Japan biz)",
        "Turkish Miles for United domestic: 7.5k one-way",
        "Book Southwest via Chase portal at 1.5 cpp with Sapphire Reserve",
        "Capital One transfer to Turkish for Star Alliance awards",
        "Citi TYP to Turkish for 7.5k domestic one-way on United",
        "Always check Google Flights for cash price before using points",
        "Use point.me to search all programs at once",
    ],
}


# ── Main Functions ────────────────────────────────────────────────────────────

async def get_latest_deals(query: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch latest deals from all sources. Optionally filter by query keyword.
    """
    ck = f"deals:{query or 'all'}"
    c = _cached(ck)
    if c:
        return c

    all_deals: List[Dict] = []
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        # RSS feeds
        rss_tasks = [_fetch_rss_deals(n, u, client) for n, u in DEAL_FEEDS.items()]
        reddit_task = _fetch_reddit_deals(client)

        results = await asyncio.gather(*rss_tasks, reddit_task, return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                all_deals.extend(r)

    # Filter by query
    if query:
        q_lower = query.lower()
        keywords = q_lower.split()
        all_deals = [d for d in all_deals if any(kw in d.get("title", "").lower() for kw in keywords)]

    # Sort by score (Reddit) then recency
    all_deals.sort(key=lambda d: d.get("score", 0), reverse=True)

    # Deduplicate by title similarity
    seen = set()
    unique = []
    for d in all_deals:
        key = d["title"].lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(d)

    result = {
        "success": True,
        "total_deals": len(unique),
        "sources": list(DEAL_FEEDS.keys()) + [f"Reddit r/{s}" for s in REDDIT_DEAL_SUBS],
        "source_count": len(DEAL_FEEDS) + len(REDDIT_DEAL_SUBS),
        "query": query,
        "deals": unique[:50],
    }
    _set_cache(ck, result)
    return result


async def check_watchlist_deals(watchlist_items: List[str]) -> Dict[str, Any]:
    """
    Check if any watchlist items have matching deals.
    """
    all_deals = await get_latest_deals()
    matches: Dict[str, List[Dict]] = {}

    for item in watchlist_items:
        item_lower = item.lower()
        keywords = item_lower.split()
        item_matches = []
        for deal in all_deals.get("deals", []):
            title_lower = deal.get("title", "").lower()
            if any(kw in title_lower for kw in keywords):
                item_matches.append(deal)
        if item_matches:
            matches[item] = item_matches[:5]

    return {
        "success": True,
        "watchlist_items": len(watchlist_items),
        "items_with_deals": len(matches),
        "matches": matches,
    }


def get_credit_card_recommendations(category: str = "travel") -> Dict[str, Any]:
    """
    Get credit card + points recommendations for a category.
    """
    cards = CREDIT_CARD_POINTS.get(category, CREDIT_CARD_POINTS.get("travel", []))
    tips = CREDIT_CARD_POINTS.get("flight_tips", [])

    return {
        "success": True,
        "category": category,
        "cards": cards,
        "flight_tips": tips if category == "travel" else [],
    }
