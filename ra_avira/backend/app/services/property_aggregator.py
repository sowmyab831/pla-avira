"""
Property Aggregation Service
Deduplicates listings, normalizes data, detects fake listings.
"""
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedProperty:
    title: str
    property_type: str
    transaction_type: str
    price: int
    price_per_sqft: int
    area_sqft: int
    carpet_area_sqft: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    floor_number: Optional[int]
    total_floors: Optional[int]
    facing: Optional[str]
    age_years: Optional[int]
    possession_status: Optional[str]
    furnishing: Optional[str]
    parking_count: int
    amenities: List[str]
    address: Optional[str]
    area_name: Optional[str]
    builder_name: Optional[str]
    project_name: Optional[str]
    rera_id: Optional[str]
    images: List[str]
    source: str
    source_url: str
    source_listing_id: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    raw_data: Dict


class PropertyAggregator:
    """Normalizes, deduplicates, and scores raw listings from multiple sources."""

    # Standard amenity mappings
    AMENITY_ALIASES = {
        "swimming pool": ["pool", "swimming", "swim pool"],
        "gym": ["gymnasium", "fitness center", "fitness"],
        "parking": ["car parking", "covered parking", "basement parking"],
        "clubhouse": ["club house", "community hall"],
        "power backup": ["generator", "dg backup", "power back up"],
        "security": ["24x7 security", "cctv", "gated community", "gated"],
        "children play area": ["kids play", "play area", "children park"],
        "garden": ["landscaped garden", "park", "green area"],
        "lift": ["elevator", "elevators"],
        "intercom": ["video intercom", "intercom facility"],
        "rain water harvesting": ["rwh", "rainwater"],
        "solar": ["solar panels", "solar power"],
        "ev charging": ["electric vehicle", "ev station"],
    }

    # Facing normalization
    FACING_MAP = {
        "e": "East", "east": "East",
        "w": "West", "west": "West",
        "n": "North", "north": "North",
        "s": "South", "south": "South",
        "ne": "NE", "north-east": "NE", "north east": "NE",
        "nw": "NW", "north-west": "NW", "north west": "NW",
        "se": "SE", "south-east": "SE", "south east": "SE",
        "sw": "SW", "south-west": "SW", "south west": "SW",
    }

    def normalize_listing(self, raw_data: Dict, source: str) -> NormalizedProperty:
        """Normalize a raw listing from any source into standard format."""
        if source == "magicbricks":
            return self._normalize_magicbricks(raw_data)
        elif source == "99acres":
            return self._normalize_99acres(raw_data)
        elif source == "nobroker":
            return self._normalize_nobroker(raw_data)
        elif source == "housing":
            return self._normalize_housing(raw_data)
        else:
            return self._normalize_generic(raw_data, source)

    def detect_duplicate(
        self,
        new_listing: NormalizedProperty,
        existing_listings: List[NormalizedProperty],
        threshold: float = 0.85,
    ) -> Optional[str]:
        """Detect if a listing is a duplicate of an existing one."""
        for existing in existing_listings:
            similarity = self._calculate_similarity(new_listing, existing)
            if similarity >= threshold:
                return existing.source_listing_id
        return None

    def detect_fake_listing(self, listing: NormalizedProperty) -> Tuple[bool, float, List[str]]:
        """Detect if a listing is likely fake. Returns (is_fake, probability, reasons)."""
        reasons = []
        fake_score = 0.0

        # 1. Price anomaly
        if listing.price_per_sqft > 0:
            if listing.price_per_sqft < 2000:
                fake_score += 0.4
                reasons.append("Price per sqft unrealistically low")
            elif listing.price_per_sqft > 50000 and listing.area_name not in ["jubilee_hills", "banjara_hills"]:
                fake_score += 0.3
                reasons.append("Price per sqft suspiciously high for area")

        # 2. No images or stock images
        if not listing.images:
            fake_score += 0.2
            reasons.append("No property images")
        elif len(listing.images) == 1:
            fake_score += 0.1
            reasons.append("Only single image provided")

        # 3. Missing critical info
        if not listing.address and not listing.project_name:
            fake_score += 0.15
            reasons.append("No address or project name")

        # 4. Suspicious title patterns
        suspicious_patterns = [
            r"urgent\s*sale",
            r"below\s*market",
            r"distress\s*sale",
            r"price\s*negotiable.*(?:call|whatsapp)",
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, listing.title.lower()):
                fake_score += 0.1
                reasons.append(f"Suspicious listing title pattern")
                break

        # 5. Unrealistic specs
        if listing.bedrooms and listing.area_sqft:
            sqft_per_bedroom = listing.area_sqft / listing.bedrooms
            if sqft_per_bedroom < 150:
                fake_score += 0.15
                reasons.append("Unrealistic room size for claimed BHK")
            elif sqft_per_bedroom > 2000:
                fake_score += 0.1
                reasons.append("Unusually large area for BHK count")

        is_fake = fake_score >= 0.5
        return is_fake, min(1.0, fake_score), reasons

    def calculate_image_hash(self, image_url: str) -> str:
        """Generate perceptual hash for duplicate image detection."""
        # In production, download image and use imagehash library
        return hashlib.md5(image_url.encode()).hexdigest()

    def normalize_price(self, price_text: str) -> int:
        """Convert price text to integer INR value."""
        price_text = price_text.lower().strip()
        price_text = price_text.replace(",", "").replace("₹", "").replace("rs", "").replace("inr", "").strip()

        multiplier = 1
        if "crore" in price_text or "cr" in price_text:
            multiplier = 10000000
            price_text = re.sub(r"(crore|cr)s?", "", price_text).strip()
        elif "lakh" in price_text or "lac" in price_text or "l" in price_text:
            multiplier = 100000
            price_text = re.sub(r"(lakh|lac|l)s?", "", price_text).strip()
        elif "k" in price_text:
            multiplier = 1000
            price_text = price_text.replace("k", "").strip()

        try:
            value = float(re.sub(r"[^\d.]", "", price_text))
            return int(value * multiplier)
        except (ValueError, TypeError):
            return 0

    def normalize_area(self, area_text: str) -> int:
        """Convert area text to sqft integer."""
        area_text = area_text.lower().strip()

        # Convert sq meters to sqft
        if "sq m" in area_text or "sqm" in area_text or "square meter" in area_text:
            area_text = re.sub(r"(sq\.?\s*m|sqm|square\s*meter)s?", "", area_text).strip()
            try:
                return int(float(re.sub(r"[^\d.]", "", area_text)) * 10.764)
            except ValueError:
                return 0

        # Convert sq yards to sqft
        if "sq yard" in area_text or "sqyd" in area_text or "gaj" in area_text:
            area_text = re.sub(r"(sq\.?\s*yard|sqyd|gaj)s?", "", area_text).strip()
            try:
                return int(float(re.sub(r"[^\d.]", "", area_text)) * 9)
            except ValueError:
                return 0

        # Already in sqft
        area_text = re.sub(r"(sq\.?\s*ft|sqft|square\s*feet|sft)", "", area_text).strip()
        try:
            return int(float(re.sub(r"[^\d.]", "", area_text)))
        except ValueError:
            return 0

    def normalize_amenities(self, raw_amenities: List[str]) -> List[str]:
        """Normalize amenity names to standard list."""
        normalized = set()
        for amenity in raw_amenities:
            amenity_lower = amenity.lower().strip()
            matched = False
            for standard, aliases in self.AMENITY_ALIASES.items():
                if amenity_lower in aliases or amenity_lower == standard:
                    normalized.add(standard)
                    matched = True
                    break
            if not matched:
                normalized.add(amenity_lower)
        return sorted(list(normalized))

    def normalize_facing(self, facing_text: str) -> Optional[str]:
        """Normalize facing direction."""
        if not facing_text:
            return None
        return self.FACING_MAP.get(facing_text.lower().strip())

    def _calculate_similarity(self, a: NormalizedProperty, b: NormalizedProperty) -> float:
        """Calculate similarity score between two listings."""
        score = 0.0
        weights_total = 0.0

        # Price similarity (30% weight)
        if a.price > 0 and b.price > 0:
            price_ratio = min(a.price, b.price) / max(a.price, b.price)
            if price_ratio > 0.95:
                score += 0.3
            elif price_ratio > 0.9:
                score += 0.2
            weights_total += 0.3

        # Area similarity (20%)
        if a.area_sqft > 0 and b.area_sqft > 0:
            area_ratio = min(a.area_sqft, b.area_sqft) / max(a.area_sqft, b.area_sqft)
            if area_ratio > 0.95:
                score += 0.2
            weights_total += 0.2

        # Same project/builder (20%)
        if a.project_name and b.project_name:
            if a.project_name.lower() == b.project_name.lower():
                score += 0.2
            weights_total += 0.2

        # Same area/locality (15%)
        if a.area_name and b.area_name:
            if a.area_name.lower() == b.area_name.lower():
                score += 0.15
            weights_total += 0.15

        # Same BHK (10%)
        if a.bedrooms and b.bedrooms:
            if a.bedrooms == b.bedrooms:
                score += 0.1
            weights_total += 0.1

        # Same floor (5%)
        if a.floor_number and b.floor_number:
            if a.floor_number == b.floor_number:
                score += 0.05
            weights_total += 0.05

        return score / weights_total if weights_total > 0 else 0.0

    def _normalize_magicbricks(self, data: Dict) -> NormalizedProperty:
        """Normalize MagicBricks listing format."""
        return NormalizedProperty(
            title=data.get("title", ""),
            property_type=self._map_property_type(data.get("propertyType", "")),
            transaction_type=data.get("transactionType", "sale").lower(),
            price=self.normalize_price(str(data.get("price", "0"))),
            price_per_sqft=self.normalize_price(str(data.get("pricePerSqft", "0"))),
            area_sqft=self.normalize_area(str(data.get("superArea", "0"))),
            carpet_area_sqft=self.normalize_area(str(data.get("carpetArea", "0"))) or None,
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            floor_number=data.get("floorNo"),
            total_floors=data.get("totalFloors"),
            facing=self.normalize_facing(data.get("facing", "")),
            age_years=data.get("age"),
            possession_status=data.get("possessionStatus", "").lower(),
            furnishing=data.get("furnishing", "").lower(),
            parking_count=data.get("parking", 0),
            amenities=self.normalize_amenities(data.get("amenities", [])),
            address=data.get("address"),
            area_name=data.get("locality"),
            builder_name=data.get("builderName"),
            project_name=data.get("projectName"),
            rera_id=data.get("reraId"),
            images=data.get("images", []),
            source="magicbricks",
            source_url=data.get("url", ""),
            source_listing_id=data.get("id"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            raw_data=data,
        )

    def _normalize_99acres(self, data: Dict) -> NormalizedProperty:
        """Normalize 99acres listing format."""
        return NormalizedProperty(
            title=data.get("title", ""),
            property_type=self._map_property_type(data.get("property_type", "")),
            transaction_type="sale",
            price=self.normalize_price(str(data.get("price", "0"))),
            price_per_sqft=self.normalize_price(str(data.get("rate_per_sqft", "0"))),
            area_sqft=self.normalize_area(str(data.get("area", "0"))),
            carpet_area_sqft=None,
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            floor_number=data.get("floor"),
            total_floors=data.get("total_floor"),
            facing=self.normalize_facing(data.get("facing", "")),
            age_years=data.get("property_age"),
            possession_status=data.get("availability", "").lower(),
            furnishing=data.get("furnishing_status", "").lower(),
            parking_count=data.get("parking", 0),
            amenities=self.normalize_amenities(data.get("amenities", [])),
            address=data.get("address"),
            area_name=data.get("locality_name"),
            builder_name=data.get("builder_name"),
            project_name=data.get("project_name"),
            rera_id=data.get("rera_id"),
            images=data.get("images", []),
            source="99acres",
            source_url=data.get("url", ""),
            source_listing_id=str(data.get("id", "")),
            latitude=data.get("lat"),
            longitude=data.get("lng"),
            raw_data=data,
        )

    def _normalize_nobroker(self, data: Dict) -> NormalizedProperty:
        """Normalize NoBroker listing format."""
        return NormalizedProperty(
            title=data.get("title", ""),
            property_type=self._map_property_type(data.get("type", "")),
            transaction_type="sale",
            price=self.normalize_price(str(data.get("rent", data.get("price", "0")))),
            price_per_sqft=0,
            area_sqft=self.normalize_area(str(data.get("propertySize", "0"))),
            carpet_area_sqft=None,
            bedrooms=data.get("bhk"),
            bathrooms=data.get("bathroom"),
            floor_number=data.get("floor"),
            total_floors=data.get("totalFloor"),
            facing=self.normalize_facing(data.get("facing", "")),
            age_years=data.get("age"),
            possession_status="ready",
            furnishing=data.get("furnishing", "").lower(),
            parking_count=data.get("parking", 0),
            amenities=self.normalize_amenities(data.get("gymAvailable", [])),
            address=data.get("street"),
            area_name=data.get("locality"),
            builder_name=None,
            project_name=data.get("society"),
            rera_id=None,
            images=data.get("photos", []),
            source="nobroker",
            source_url=data.get("detailUrl", ""),
            source_listing_id=data.get("id"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            raw_data=data,
        )

    def _normalize_housing(self, data: Dict) -> NormalizedProperty:
        """Normalize Housing.com listing format."""
        return NormalizedProperty(
            title=data.get("title", ""),
            property_type=self._map_property_type(data.get("category", "")),
            transaction_type="sale",
            price=self.normalize_price(str(data.get("price", "0"))),
            price_per_sqft=self.normalize_price(str(data.get("price_per_sqft", "0"))),
            area_sqft=self.normalize_area(str(data.get("super_area", "0"))),
            carpet_area_sqft=self.normalize_area(str(data.get("carpet_area", "0"))) or None,
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            floor_number=data.get("floor_number"),
            total_floors=data.get("total_floors"),
            facing=self.normalize_facing(data.get("facing", "")),
            age_years=data.get("age_of_property"),
            possession_status=data.get("possession", "").lower(),
            furnishing=data.get("furnishing_status", "").lower(),
            parking_count=data.get("covered_parking", 0),
            amenities=self.normalize_amenities(data.get("key_amenities", [])),
            address=data.get("address"),
            area_name=data.get("locality"),
            builder_name=data.get("builder_name"),
            project_name=data.get("project_name"),
            rera_id=data.get("rera_id"),
            images=data.get("images", []),
            source="housing",
            source_url=data.get("url", ""),
            source_listing_id=str(data.get("property_id", "")),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            raw_data=data,
        )

    def _normalize_generic(self, data: Dict, source: str) -> NormalizedProperty:
        """Generic normalization for unknown sources."""
        return NormalizedProperty(
            title=data.get("title", "Unknown Property"),
            property_type=self._map_property_type(data.get("property_type", data.get("type", "apartment"))),
            transaction_type=data.get("transaction_type", "sale"),
            price=self.normalize_price(str(data.get("price", "0"))),
            price_per_sqft=0,
            area_sqft=self.normalize_area(str(data.get("area", data.get("size", "0")))),
            carpet_area_sqft=None,
            bedrooms=data.get("bedrooms", data.get("bhk")),
            bathrooms=data.get("bathrooms"),
            floor_number=data.get("floor"),
            total_floors=data.get("total_floors"),
            facing=self.normalize_facing(data.get("facing", "")),
            age_years=data.get("age"),
            possession_status=data.get("possession", "ready"),
            furnishing=data.get("furnishing", "unfurnished"),
            parking_count=data.get("parking", 0),
            amenities=data.get("amenities", []),
            address=data.get("address"),
            area_name=data.get("area_name", data.get("locality")),
            builder_name=data.get("builder"),
            project_name=data.get("project"),
            rera_id=data.get("rera_id"),
            images=data.get("images", []),
            source=source,
            source_url=data.get("url", ""),
            source_listing_id=str(data.get("id", "")),
            latitude=data.get("latitude", data.get("lat")),
            longitude=data.get("longitude", data.get("lng")),
            raw_data=data,
        )

    def _map_property_type(self, raw_type: str) -> str:
        """Map various property type strings to standard types."""
        raw = raw_type.lower().strip()
        if any(w in raw for w in ["apartment", "flat", "condo"]):
            return "apartment"
        elif any(w in raw for w in ["villa", "independent house", "bungalow", "duplex"]):
            return "villa"
        elif any(w in raw for w in ["plot", "land", "site"]):
            return "plot"
        elif "penthouse" in raw:
            return "penthouse"
        return "apartment"


property_aggregator = PropertyAggregator()
