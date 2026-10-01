"""Wishlist service: track wanted items, find deals, analyze price-drop potential."""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.services.llm_client import generate as llm_generate

logger = logging.getLogger(__name__)

WISHLIST_PATH = os.getenv("WISHLIST_PATH", "/data/documents/wishlist.json")

# Market knowledge base for popular items:
# msrp, all_time_low (observed street low), refresh_cycle_note
MARKET_DATA: Dict[str, Dict[str, Any]] = {
    "mac mini": {
        "msrp": 599.00, "all_time_low": 449.00, "typical_sale": 499.00,
        "refresh_note": "Apple refreshes Mac Mini roughly every 18-24 months (M4 launched Oct 2024). Best discounts: Black Friday, back-to-school, and right after a new chip generation launches.",
    },
    "macbook air": {
        "msrp": 999.00, "all_time_low": 749.00, "typical_sale": 849.00,
        "refresh_note": "MacBook Air refreshes annually (spring). Previous-gen models drop $150-250 at launch.",
    },
    "macbook pro": {
        "msrp": 1599.00, "all_time_low": 1299.00, "typical_sale": 1449.00,
        "refresh_note": "MacBook Pro refreshes annually (fall). Deepest cuts on prior-gen during Black Friday.",
    },
    "ipad": {
        "msrp": 349.00, "all_time_low": 269.00, "typical_sale": 299.00,
        "refresh_note": "Base iPad often hits $269-279 during Prime Day and Black Friday.",
    },
    "airpods pro": {
        "msrp": 249.00, "all_time_low": 168.00, "typical_sale": 189.00,
        "refresh_note": "AirPods Pro regularly discounted 20-30%; frequently at all-time lows during Prime Day/Black Friday.",
    },
    "apple watch": {
        "msrp": 399.00, "all_time_low": 299.00, "typical_sale": 329.00,
        "refresh_note": "Apple Watch refreshes every September; prior-gen drops sharply after announcement.",
    },
    "ps5": {
        "msrp": 499.99, "all_time_low": 399.99, "typical_sale": 449.99,
        "refresh_note": "Console discounts cluster around Black Friday and summer sales events.",
    },
    "nintendo switch 2": {
        "msrp": 449.99, "all_time_low": 429.99, "typical_sale": 449.99,
        "refresh_note": "New console; meaningful discounts unlikely within first 12-18 months.",
    },
    "sony wh-1000xm5": {
        "msrp": 399.99, "all_time_low": 279.99, "typical_sale": 329.99,
        "refresh_note": "Sony flagship headphones drop 25-30% when successor launches and during major sales.",
    },
    "dyson v15": {
        "msrp": 649.99, "all_time_low": 449.99, "typical_sale": 549.99,
        "refresh_note": "Dyson runs frequent 20-30% promos; owner-refurb units cheaper still.",
    },
}

# Months (1-12) with major US sale events
SALE_EVENTS = {
    7: "Prime Day (mid-July)",
    9: "Labor Day / back-to-school sales",
    11: "Black Friday / Cyber Monday (deepest discounts of the year)",
    12: "Holiday season sales",
}


class WishlistService:
    """Manage wishlist items with deal analysis and market research."""

    def __init__(self):
        self._items: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ── Persistence ────────────────────────────────────────────────────────────
    def _load(self):
        try:
            if os.path.exists(WISHLIST_PATH):
                with open(WISHLIST_PATH) as f:
                    self._items = json.load(f)
                logger.info(f"Loaded {len(self._items)} wishlist items")
        except Exception as e:
            logger.warning(f"Could not load wishlist: {e}")
            self._items = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(WISHLIST_PATH), exist_ok=True)
            with open(WISHLIST_PATH, "w") as f:
                json.dump(self._items, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist wishlist: {e}")

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def add_item(self, name: str, target_price: Optional[float] = None, notes: str = "") -> Dict[str, Any]:
        item_id = uuid.uuid4().hex[:10]
        item = {
            "id": item_id,
            "name": name.strip(),
            "target_price": target_price,
            "notes": notes,
            "added_at": datetime.now().isoformat(),
        }
        self._items[item_id] = item
        self._save()
        return item

    def remove_item(self, item_id: str) -> bool:
        if item_id in self._items:
            del self._items[item_id]
            self._save()
            return True
        return False

    def list_items(self) -> List[Dict[str, Any]]:
        return sorted(self._items.values(), key=lambda x: x["added_at"], reverse=True)

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self._items.get(item_id)

    # ── Deal analysis ──────────────────────────────────────────────────────────
    def _market_data_for(self, name: str) -> Optional[Dict[str, Any]]:
        q = name.lower()
        # Longest-key match first for specificity
        for key in sorted(MARKET_DATA, key=len, reverse=True):
            if key in q:
                return {"matched": key, **MARKET_DATA[key]}
        return None

    def analyze_item(self, item: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """Deterministic deal analysis: lowest price, drop potential, timing."""
        md = self._market_data_for(item["name"])
        if md:
            msrp = md["msrp"]
            all_time_low = md["all_time_low"]
            typical_sale = md["typical_sale"]
            refresh_note = md["refresh_note"]
        else:
            # Derive conservative estimates from current price
            msrp = current_price
            all_time_low = round(current_price * 0.78, 2)
            typical_sale = round(current_price * 0.88, 2)
            refresh_note = "No product-specific cycle data; most electronics see 10-25% cuts during Prime Day and Black Friday."

        discount_vs_msrp = round((1 - current_price / msrp) * 100, 1) if msrp else 0.0
        room_to_drop = round((1 - all_time_low / current_price) * 100, 1) if current_price else 0.0

        # Deal score: how close is today's price to the all-time low? (100 = at ATL)
        if current_price <= all_time_low:
            deal_score = 100.0
        else:
            span = max(msrp - all_time_low, 0.01)
            deal_score = round(max(0.0, min(100.0, (msrp - current_price) / span * 100)), 1)

        # Timing: months until next major sale event
        month = datetime.now().month
        upcoming = []
        for offset in range(0, 6):
            m = (month - 1 + offset) % 12 + 1
            if m in SALE_EVENTS:
                upcoming.append(SALE_EVENTS[m])
        next_sale = upcoming[0] if upcoming else "No major sale event in the next 6 months"

        if deal_score >= 85:
            verdict, action = "excellent_deal", "BUY NOW — price is at or near its all-time low."
        elif deal_score >= 60:
            verdict, action = "good_deal", f"Good price. If not urgent, waiting for {next_sale} could save ~{room_to_drop:.0f}% more."
        elif deal_score >= 30:
            verdict, action = "average_price", f"Average price. Recommend waiting for {next_sale}."
        else:
            verdict, action = "poor_deal", f"Near full MSRP. Strongly recommend waiting for {next_sale} — historical low is ${all_time_low:.2f}."

        target = item.get("target_price")
        target_hit = target is not None and current_price <= target

        return {
            "item": item["name"],
            "current_price": current_price,
            "msrp": msrp,
            "all_time_low": all_time_low,
            "typical_sale_price": typical_sale,
            "discount_vs_msrp_pct": discount_vs_msrp,
            "potential_further_drop_pct": room_to_drop,
            "deal_score": deal_score,
            "verdict": verdict,
            "recommendation": action,
            "target_price": target,
            "target_price_hit": target_hit,
            "next_sale_event": next_sale,
            "market_cycle_note": refresh_note,
            "analyzed_at": datetime.now().isoformat(),
        }

    async def ai_market_research(
        self, item_name: str, analysis: Dict[str, Any],
        ollama_host: str, ollama_model: str,
    ) -> str:
        """LLM-powered market research narrative (best-effort, fast fallback)."""
        prompt = f"""You are a consumer market analyst. Provide a concise deal analysis (max 150 words) for: {item_name}

DATA:
- Current price: ${analysis['current_price']:.2f}
- MSRP: ${analysis['msrp']:.2f}
- All-time low: ${analysis['all_time_low']:.2f}
- Deal score: {analysis['deal_score']}/100
- Next sale event: {analysis['next_sale_event']}
- Product cycle: {analysis['market_cycle_note']}

Cover: 1) Is this a good time to buy? 2) How much lower could it realistically go? 3) Specific timing advice."""
        try:
            text = (await llm_generate(
                prompt, task="shopping", temperature=0.4,
                max_tokens=600, timeout=90,
            )).strip()
            if text:
                return text
        except Exception as e:
            logger.warning(f"AI market research unavailable: {e}")
        return analysis["recommendation"]


_wishlist_service: Optional[WishlistService] = None


def get_wishlist_service() -> WishlistService:
    global _wishlist_service
    if _wishlist_service is None:
        _wishlist_service = WishlistService()
    return _wishlist_service
