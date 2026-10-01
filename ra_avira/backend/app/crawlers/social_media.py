"""
Social Media Property Discovery Engine
Monitors Instagram, YouTube, Telegram, and Twitter for property listings.
Uses Whisper for transcription, LLM for extraction.
"""
import re
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import httpx
import structlog

logger = structlog.get_logger()


@dataclass
class SocialMediaListing:
    platform: str
    source_type: str  # reel, post, video, message
    source_url: str
    source_id: str
    author: str
    content: str
    transcription: Optional[str]
    extracted_data: Dict
    media_urls: List[str]
    sentiment_score: float
    urgency_score: float
    fake_probability: float
    crawled_at: datetime


class SocialMediaCrawler:
    """Discovers property listings from social media platforms."""

    # Keywords to identify property-related content
    PROPERTY_KEYWORDS_EN = [
        "flat for sale", "apartment for sale", "villa for sale",
        "bhk", "sqft", "sq ft", "property", "real estate",
        "gachibowli", "kokapet", "kondapur", "madhapur",
        "financial district", "hitech city", "narsingi", "tellapur",
        "hyderabad property", "hyd flat", "hyd apartment",
        "crore", "lakh", "per sqft",
    ]

    PROPERTY_KEYWORDS_TE = [
        "ఫ్లాట్ అమ్మకం", "అపార్ట్మెంట్", "విల్లా",
        "గచ్చిబౌలి", "కోకాపేట", "కొండాపూర్",
        "హైదరాబాద్", "కోటి", "లక్ష",
    ]

    # YouTube channels known for Hyderabad property content
    YOUTUBE_CHANNELS = [
        "PropertyPistol",
        "Hyderabad Real Estate",
        "99acres Hyderabad",
        "NoBroker Hyderabad",
        "India Property Dekho",
    ]

    # Telegram groups for Hyderabad property
    TELEGRAM_GROUPS = [
        "hyderabad_properties",
        "hyd_real_estate",
        "kokapet_properties",
        "gachibowli_flats",
    ]

    async def crawl_youtube(self, api_key: str, max_results: int = 50) -> List[SocialMediaListing]:
        """Crawl YouTube for Hyderabad property videos."""
        listings = []
        
        search_queries = [
            "Hyderabad apartment for sale 2024",
            "Kokapet villa price",
            "Gachibowli flat walkthrough",
            "Hyderabad property investment",
            "Financial District apartment tour",
        ]

        async with httpx.AsyncClient() as client:
            for query in search_queries:
                try:
                    url = "https://www.googleapis.com/youtube/v3/search"
                    params = {
                        "part": "snippet",
                        "q": query,
                        "key": api_key,
                        "maxResults": 10,
                        "type": "video",
                        "order": "date",
                        "regionCode": "IN",
                    }
                    response = await client.get(url, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for item in data.get("items", []):
                            listing = self._parse_youtube_result(item)
                            if listing:
                                listings.append(listing)
                except Exception as e:
                    logger.error("youtube_crawl_error", query=query, error=str(e))

        return listings

    async def crawl_telegram(self, bot_token: str) -> List[SocialMediaListing]:
        """Crawl Telegram groups for property posts."""
        listings = []
        
        # In production, use Telethon or pyrogram for full group access
        # This is a simplified version using Bot API
        async with httpx.AsyncClient() as client:
            for group in self.TELEGRAM_GROUPS:
                try:
                    # Note: Bot API has limitations, production should use MTProto
                    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        data = response.json()
                        for update in data.get("result", []):
                            message = update.get("message", {})
                            text = message.get("text", "")
                            
                            if self._is_property_related(text):
                                listing = self._parse_telegram_message(message, group)
                                if listing:
                                    listings.append(listing)
                except Exception as e:
                    logger.error("telegram_crawl_error", group=group, error=str(e))

        return listings

    async def extract_from_transcription(self, transcription: str) -> Dict:
        """Extract property details from video/audio transcription using LLM."""
        # Pattern-based extraction (fallback when LLM not available)
        extracted = {}

        # Price extraction
        price_patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:crore|cr)",
            r"(\d+(?:\.\d+)?)\s*(?:lakh|lac)",
            r"(?:price|cost|budget).*?(\d[\d,]+)",
        ]
        for pattern in price_patterns:
            match = re.search(pattern, transcription, re.IGNORECASE)
            if match:
                extracted["price_mentioned"] = match.group(0)
                break

        # Area/Location extraction
        locations = [
            "gachibowli", "kokapet", "financial district", "kondapur",
            "madhapur", "jubilee hills", "hitech city", "narsingi",
            "tellapur", "banjara hills", "kukatpally", "miyapur",
        ]
        for loc in locations:
            if loc in transcription.lower():
                extracted.setdefault("locations", []).append(loc)

        # BHK extraction
        bhk_match = re.search(r"(\d)\s*(?:bhk|bed)", transcription, re.IGNORECASE)
        if bhk_match:
            extracted["bedrooms"] = int(bhk_match.group(1))

        # Sqft extraction
        sqft_match = re.search(r"(\d[\d,]+)\s*(?:sq\.?\s*ft|sqft|sft)", transcription, re.IGNORECASE)
        if sqft_match:
            extracted["area_sqft"] = int(sqft_match.group(1).replace(",", ""))

        # Property type
        if any(w in transcription.lower() for w in ["villa", "independent house", "duplex"]):
            extracted["property_type"] = "villa"
        elif any(w in transcription.lower() for w in ["flat", "apartment", "apt"]):
            extracted["property_type"] = "apartment"
        elif any(w in transcription.lower() for w in ["plot", "land", "site"]):
            extracted["property_type"] = "plot"

        # Builder extraction
        builder_patterns = [
            r"(?:by|from|builder)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)",
            r"([A-Z][a-zA-Z]+)\s+(?:builders?|constructions?|infra|projects?)",
        ]
        for pattern in builder_patterns:
            match = re.search(pattern, transcription)
            if match:
                extracted["builder"] = match.group(1)
                break

        # Urgency detection
        urgency_words = ["urgent", "last", "limited", "hurry", "today only", "closing"]
        urgency_count = sum(1 for w in urgency_words if w in transcription.lower())
        extracted["urgency_score"] = min(1.0, urgency_count * 0.3)

        return extracted

    def calculate_fake_probability(self, listing_data: Dict) -> float:
        """Calculate probability that a social media listing is fake."""
        score = 0.0

        # No price mentioned
        if not listing_data.get("price_mentioned"):
            score += 0.1

        # High urgency language
        if listing_data.get("urgency_score", 0) > 0.6:
            score += 0.2

        # Unrealistic claims
        content = listing_data.get("content", "").lower()
        fake_signals = [
            "guaranteed returns",
            "100% appreciation",
            "below market",
            "distress sale",
            "no broker",  # often used to attract, but may still involve broker
        ]
        for signal in fake_signals:
            if signal in content:
                score += 0.15

        # No location specifics
        if not listing_data.get("locations"):
            score += 0.1

        # Anonymous / new account
        if listing_data.get("author_is_new", False):
            score += 0.15

        return min(1.0, score)

    def _is_property_related(self, text: str) -> bool:
        """Check if text is property-related."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.PROPERTY_KEYWORDS_EN + self.PROPERTY_KEYWORDS_TE)

    def _parse_youtube_result(self, item: Dict) -> Optional[SocialMediaListing]:
        """Parse YouTube search result into SocialMediaListing."""
        try:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            
            title = snippet.get("title", "")
            description = snippet.get("description", "")
            
            if not self._is_property_related(f"{title} {description}"):
                return None

            return SocialMediaListing(
                platform="youtube",
                source_type="video",
                source_url=f"https://www.youtube.com/watch?v={video_id}",
                source_id=video_id,
                author=snippet.get("channelTitle", ""),
                content=f"{title}\n{description}",
                transcription=None,  # Requires separate Whisper processing
                extracted_data={},
                media_urls=[snippet.get("thumbnails", {}).get("high", {}).get("url", "")],
                sentiment_score=0.5,
                urgency_score=0.0,
                fake_probability=0.0,
                crawled_at=datetime.utcnow(),
            )
        except Exception:
            return None

    def _parse_telegram_message(self, message: Dict, group: str) -> Optional[SocialMediaListing]:
        """Parse Telegram message into SocialMediaListing."""
        try:
            text = message.get("text", "")
            if not text:
                return None

            return SocialMediaListing(
                platform="telegram",
                source_type="message",
                source_url=f"https://t.me/{group}/{message.get('message_id', '')}",
                source_id=str(message.get("message_id", "")),
                author=message.get("from", {}).get("username", "unknown"),
                content=text,
                transcription=None,
                extracted_data={},
                media_urls=[],
                sentiment_score=0.5,
                urgency_score=0.0,
                fake_probability=0.0,
                crawled_at=datetime.utcnow(),
            )
        except Exception:
            return None


social_media_crawler = SocialMediaCrawler()
