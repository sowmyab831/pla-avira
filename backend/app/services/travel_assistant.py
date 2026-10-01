"""
Travel Assistant - Flight search with comfort and price optimization.

Features:
- Multi-source flight search
- Cheapest and comfort-optimized options
- Layover analysis
- Privacy-first booking info handling
"""
import logging
import re
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


@dataclass
class FlightLeg:
    """A single flight leg."""
    airline: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    aircraft: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "airline": self.airline,
            "flight_number": self.flight_number,
            "departure_airport": self.departure_airport,
            "arrival_airport": self.arrival_airport,
            "departure_time": self.departure_time,
            "arrival_time": self.arrival_time,
            "duration_minutes": self.duration_minutes,
            "duration_formatted": f"{self.duration_minutes // 60}h {self.duration_minutes % 60}m",
            "aircraft": self.aircraft,
        }


@dataclass
class Layover:
    """Layover information."""
    airport: str
    duration_minutes: int
    
    def to_dict(self) -> Dict:
        return {
            "airport": self.airport,
            "duration_minutes": self.duration_minutes,
            "duration_formatted": f"{self.duration_minutes // 60}h {self.duration_minutes % 60}m",
        }


@dataclass
class FlightResult:
    """A complete flight itinerary."""
    rank: int
    price: float
    currency: str = "USD"
    total_duration_minutes: int = 0
    legs: List[FlightLeg] = field(default_factory=list)
    layovers: List[Layover] = field(default_factory=list)
    cabin_class: CabinClass = CabinClass.ECONOMY
    airlines: List[str] = field(default_factory=list)
    comfort_score: float = 0.0
    comfort_reason: str = ""
    booking_url: str = ""
    source: str = ""
    refundable: bool = False
    baggage_included: bool = True
    
    def to_dict(self) -> Dict:
        return {
            "rank": self.rank,
            "price": self.price,
            "currency": self.currency,
            "total_duration_minutes": self.total_duration_minutes,
            "total_duration_formatted": f"{self.total_duration_minutes // 60}h {self.total_duration_minutes % 60}m",
            "legs": [leg.to_dict() for leg in self.legs],
            "layovers": [l.to_dict() for l in self.layovers],
            "layover_count": len(self.layovers),
            "cabin_class": self.cabin_class.value,
            "airlines": self.airlines,
            "comfort_score": self.comfort_score,
            "comfort_reason": self.comfort_reason,
            "booking_url": self.booking_url,
            "source": self.source,
            "refundable": self.refundable,
            "baggage_included": self.baggage_included,
        }


@dataclass
class FlightSearchParams:
    """Parsed flight search parameters."""
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    cabin_class: CabinClass = CabinClass.ECONOMY
    max_layovers: int = 2
    max_layover_duration: int = 240  # minutes
    flexible_dates: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
            "return_date": self.return_date,
            "passengers": self.passengers,
            "cabin_class": self.cabin_class.value,
            "max_layovers": self.max_layovers,
            "max_layover_duration": self.max_layover_duration,
            "flexible_dates": self.flexible_dates,
            "trip_type": "round_trip" if self.return_date else "one_way",
        }


# Airport code mappings
AIRPORT_CODES = {
    "new york": "JFK", "nyc": "JFK", "jfk": "JFK", "laguardia": "LGA", "newark": "EWR",
    "los angeles": "LAX", "la": "LAX", "lax": "LAX",
    "chicago": "ORD", "ohare": "ORD", "ord": "ORD", "midway": "MDW",
    "san francisco": "SFO", "sf": "SFO", "sfo": "SFO",
    "miami": "MIA", "mia": "MIA",
    "dallas": "DFW", "dfw": "DFW",
    "atlanta": "ATL", "atl": "ATL",
    "boston": "BOS", "bos": "BOS",
    "seattle": "SEA", "sea": "SEA",
    "denver": "DEN", "den": "DEN",
    "charlotte": "CLT", "clt": "CLT",
    "london": "LHR", "heathrow": "LHR", "lhr": "LHR", "gatwick": "LGW",
    "paris": "CDG", "cdg": "CDG",
    "tokyo": "NRT", "narita": "NRT", "haneda": "HND",
    "dubai": "DXB", "dxb": "DXB",
    "singapore": "SIN", "sin": "SIN",
    "hong kong": "HKG", "hkg": "HKG",
    "sydney": "SYD", "syd": "SYD",
    "toronto": "YYZ", "yyz": "YYZ",
    "vancouver": "YVR", "yvr": "YVR",
    "cancun": "CUN", "cun": "CUN",
    "hawaii": "HNL", "honolulu": "HNL", "hnl": "HNL",
}

# Airline comfort ratings
AIRLINE_COMFORT = {
    "Singapore Airlines": 9.2,
    "Qatar Airways": 9.0,
    "Emirates": 8.8,
    "ANA": 8.7,
    "Cathay Pacific": 8.5,
    "EVA Air": 8.4,
    "Japan Airlines": 8.3,
    "Korean Air": 8.2,
    "Delta": 7.5,
    "United": 7.2,
    "American": 7.0,
    "JetBlue": 7.8,
    "Southwest": 7.0,
    "Spirit": 5.5,
    "Frontier": 5.5,
    "Ryanair": 5.0,
}


class TravelAssistant:
    """
    Flight search with comfort and price optimization.
    """
    
    def __init__(self):
        self._cache: Dict[str, Tuple[Dict, datetime]] = {}
        self._cache_ttl = 600  # 10 minutes
    
    def parse_query(self, query: str) -> Optional[FlightSearchParams]:
        """
        Parse natural language flight query.
        
        Examples:
        - "flights from NYC to LA on Dec 20"
        - "round trip Boston to Miami Dec 25-30 for 2 passengers business class"
        """
        query_lower = query.lower()
        
        # Extract origin and destination
        origin = None
        destination = None
        
        # Pattern: "from X to Y"
        from_to_match = re.search(r'from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s+on|\s+for|\s+\d|$)', query_lower)
        if from_to_match:
            origin = self._resolve_airport(from_to_match.group(1).strip())
            destination = self._resolve_airport(from_to_match.group(2).strip())
        
        if not origin or not destination:
            return None
        
        # Extract dates
        departure_date = None
        return_date = None
        
        # Look for date patterns
        date_patterns = [
            r'(?:on|for|departing?)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?)',
            r'(\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?)',
            r'(dec(?:ember)?\s+\d{1,2})',
            r'(jan(?:uary)?\s+\d{1,2})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, query_lower)
            if match:
                departure_date = self._parse_date(match.group(1))
                break
        
        if not departure_date:
            # Default to tomorrow
            departure_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        # Check for round trip
        round_trip_match = re.search(r'(\d{1,2})[/-](\d{1,2})', query_lower)
        if "round trip" in query_lower or "return" in query_lower or round_trip_match:
            # Look for return date
            return_match = re.search(r'(?:return(?:ing)?|to)\s+(\w+\s+\d{1,2})', query_lower)
            if return_match:
                return_date = self._parse_date(return_match.group(1))
            elif round_trip_match:
                # Assume second number is return day
                return_date = departure_date[:8] + str(int(round_trip_match.group(2))).zfill(2)
        
        # Extract passengers
        passengers = 1
        pax_match = re.search(r'(\d+)\s*(?:passenger|pax|people|person|adult)', query_lower)
        if pax_match:
            passengers = int(pax_match.group(1))
        
        # Extract cabin class
        cabin_class = CabinClass.ECONOMY
        if "business" in query_lower:
            cabin_class = CabinClass.BUSINESS
        elif "first" in query_lower:
            cabin_class = CabinClass.FIRST
        elif "premium" in query_lower:
            cabin_class = CabinClass.PREMIUM_ECONOMY
        
        # Extract layover preferences
        max_layovers = 2
        if "nonstop" in query_lower or "direct" in query_lower:
            max_layovers = 0
        elif "1 stop" in query_lower or "one stop" in query_lower:
            max_layovers = 1
        
        return FlightSearchParams(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class,
            max_layovers=max_layovers,
        )
    
    async def search(
        self,
        query: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Search for flights and return both cheapest and comfort options.
        """
        params = self.parse_query(query)
        
        if not params:
            return {
                "success": False,
                "message": "Please provide origin, destination, and travel dates. Example: 'flights from NYC to LA on Dec 20'",
                "required_fields": ["origin", "destination", "departure_date"],
            }
        
        # Check cache
        cache_key = f"{params.origin}:{params.destination}:{params.departure_date}:{params.cabin_class.value}"
        if cache_key in self._cache:
            cached, cached_at = self._cache[cache_key]
            if (datetime.now() - cached_at).seconds < self._cache_ttl:
                return cached
        
        # Search for flights
        results = await self._search_flights(params)
        
        if not results:
            return {
                "success": False,
                "params": params.to_dict(),
                "message": "No flights found for this route and date. Try different dates or nearby airports.",
            }
        
        # Separate into cheapest and comfort options
        cheapest = self._get_cheapest(results, 3)
        comfort = self._get_most_comfortable(results, 3)
        
        response = {
            "success": True,
            "type": "travel_result",
            "query": query,
            "params": params.to_dict(),
            "cheapest_options": [f.to_dict() for f in cheapest],
            "comfort_options": [f.to_dict() for f in comfort],
            "total_results": len(results),
            "searched_at": datetime.now().isoformat(),
            "notes": {
                "masked_booking": False,
                "externally_processed": False,
            },
        }
        
        # Cache
        self._cache[cache_key] = (response, datetime.now())
        
        return response
    
    async def _search_flights(self, params: FlightSearchParams) -> List[FlightResult]:
        """Search for flights (mock implementation)."""
        # In production, this would call real flight APIs
        # (Amadeus, Skyscanner, Google Flights, etc.)
        
        await asyncio.sleep(0.2)  # Simulate API delay
        
        results = []
        
        # Generate mock flight options
        base_price = self._estimate_base_price(params)
        
        # Nonstop option
        if params.max_layovers >= 0:
            results.append(self._create_mock_flight(
                params, "Delta", base_price * 1.2, nonstop=True
            ))
            results.append(self._create_mock_flight(
                params, "United", base_price * 1.15, nonstop=True
            ))
        
        # 1-stop options
        if params.max_layovers >= 1:
            results.append(self._create_mock_flight(
                params, "American", base_price * 0.9, stops=1, layover_airport="DFW"
            ))
            results.append(self._create_mock_flight(
                params, "Delta", base_price * 0.85, stops=1, layover_airport="ATL"
            ))
        
        # Budget options
        if params.max_layovers >= 1:
            results.append(self._create_mock_flight(
                params, "Spirit", base_price * 0.6, stops=1, layover_airport="FLL"
            ))
            results.append(self._create_mock_flight(
                params, "Frontier", base_price * 0.55, stops=1, layover_airport="DEN"
            ))
        
        return results
    
    def _create_mock_flight(
        self,
        params: FlightSearchParams,
        airline: str,
        price: float,
        nonstop: bool = False,
        stops: int = 0,
        layover_airport: str = None,
    ) -> FlightResult:
        """Create a mock flight result."""
        legs = []
        layovers = []
        
        # Calculate duration based on route
        base_duration = self._estimate_duration(params.origin, params.destination)
        
        if nonstop:
            legs.append(FlightLeg(
                airline=airline,
                flight_number=f"{airline[:2].upper()}{100 + len(legs)}",
                departure_airport=params.origin,
                arrival_airport=params.destination,
                departure_time=f"{params.departure_date}T08:00:00",
                arrival_time=f"{params.departure_date}T{8 + base_duration // 60:02d}:{base_duration % 60:02d}:00",
                duration_minutes=base_duration,
            ))
            total_duration = base_duration
        else:
            # First leg
            leg1_duration = base_duration // 2
            legs.append(FlightLeg(
                airline=airline,
                flight_number=f"{airline[:2].upper()}{100}",
                departure_airport=params.origin,
                arrival_airport=layover_airport or "ORD",
                departure_time=f"{params.departure_date}T06:00:00",
                arrival_time=f"{params.departure_date}T{6 + leg1_duration // 60:02d}:{leg1_duration % 60:02d}:00",
                duration_minutes=leg1_duration,
            ))
            
            # Layover
            layover_duration = 90  # 1.5 hours
            layovers.append(Layover(
                airport=layover_airport or "ORD",
                duration_minutes=layover_duration,
            ))
            
            # Second leg
            leg2_duration = base_duration // 2 + 30
            legs.append(FlightLeg(
                airline=airline,
                flight_number=f"{airline[:2].upper()}{200}",
                departure_airport=layover_airport or "ORD",
                arrival_airport=params.destination,
                departure_time=f"{params.departure_date}T{8 + leg1_duration // 60 + 2:02d}:30:00",
                arrival_time=f"{params.departure_date}T{8 + leg1_duration // 60 + 2 + leg2_duration // 60:02d}:{leg2_duration % 60:02d}:00",
                duration_minutes=leg2_duration,
            ))
            
            total_duration = leg1_duration + layover_duration + leg2_duration
        
        # Calculate comfort score
        comfort_score = AIRLINE_COMFORT.get(airline, 7.0)
        if nonstop:
            comfort_score += 0.5
        if params.cabin_class == CabinClass.BUSINESS:
            comfort_score += 1.0
        elif params.cabin_class == CabinClass.FIRST:
            comfort_score += 1.5
        
        comfort_score = min(10.0, comfort_score)
        
        # Generate comfort reason
        comfort_reasons = []
        if nonstop:
            comfort_reasons.append("nonstop flight")
        if AIRLINE_COMFORT.get(airline, 7.0) >= 8.0:
            comfort_reasons.append("premium airline")
        if total_duration < 300:
            comfort_reasons.append("short flight time")
        
        return FlightResult(
            rank=0,
            price=round(price * params.passengers, 2),
            total_duration_minutes=total_duration,
            legs=legs,
            layovers=layovers,
            cabin_class=params.cabin_class,
            airlines=[airline],
            comfort_score=round(comfort_score, 1),
            comfort_reason="; ".join(comfort_reasons) if comfort_reasons else "standard service",
            booking_url=f"https://example.com/book/{airline.lower()}",
            source="mock_api",
            baggage_included=airline not in ["Spirit", "Frontier"],
        )
    
    def _estimate_base_price(self, params: FlightSearchParams) -> float:
        """Estimate base price for route."""
        # Very simplified pricing
        domestic_routes = {"JFK", "LAX", "ORD", "SFO", "MIA", "DFW", "ATL", "BOS", "SEA", "DEN", "CLT"}
        
        if params.origin in domestic_routes and params.destination in domestic_routes:
            base = 250
        else:
            base = 800  # International
        
        # Cabin class multiplier
        if params.cabin_class == CabinClass.PREMIUM_ECONOMY:
            base *= 1.5
        elif params.cabin_class == CabinClass.BUSINESS:
            base *= 3.0
        elif params.cabin_class == CabinClass.FIRST:
            base *= 5.0
        
        return base
    
    def _estimate_duration(self, origin: str, destination: str) -> int:
        """Estimate flight duration in minutes."""
        # Simplified duration estimation
        domestic_pairs = {
            ("JFK", "LAX"): 330,
            ("LAX", "JFK"): 300,
            ("JFK", "MIA"): 180,
            ("ORD", "LAX"): 240,
            ("SFO", "JFK"): 330,
            ("BOS", "MIA"): 200,
            ("SEA", "LAX"): 150,
            ("DEN", "JFK"): 240,
        }
        
        key = (origin, destination)
        if key in domestic_pairs:
            return domestic_pairs[key]
        
        # Default
        return 240
    
    def _get_cheapest(self, results: List[FlightResult], n: int) -> List[FlightResult]:
        """Get N cheapest options."""
        sorted_results = sorted(results, key=lambda r: r.price)
        for i, r in enumerate(sorted_results[:n]):
            r.rank = i + 1
        return sorted_results[:n]
    
    def _get_most_comfortable(self, results: List[FlightResult], n: int) -> List[FlightResult]:
        """Get N most comfortable options."""
        sorted_results = sorted(results, key=lambda r: r.comfort_score, reverse=True)
        for i, r in enumerate(sorted_results[:n]):
            r.rank = i + 1
        return sorted_results[:n]
    
    def _resolve_airport(self, location: str) -> Optional[str]:
        """Resolve location to airport code."""
        location_lower = location.lower().strip()
        
        # Direct code match
        if len(location_lower) == 3 and location_lower.upper() in AIRPORT_CODES.values():
            return location_lower.upper()
        
        # Name match
        if location_lower in AIRPORT_CODES:
            return AIRPORT_CODES[location_lower]
        
        # Partial match
        for name, code in AIRPORT_CODES.items():
            if name in location_lower or location_lower in name:
                return code
        
        return None
    
    def _parse_date(self, date_str: str) -> str:
        """Parse date string to YYYY-MM-DD format."""
        date_str = date_str.strip().lower()
        
        # Try common formats
        formats = [
            "%B %d",
            "%b %d",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%m-%d-%Y",
            "%Y-%m-%d",
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                    if parsed < datetime.now():
                        parsed = parsed.replace(year=datetime.now().year + 1)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # Default to tomorrow
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


# Singleton
_travel_assistant: Optional[TravelAssistant] = None


def get_travel_assistant() -> TravelAssistant:
    global _travel_assistant
    if _travel_assistant is None:
        _travel_assistant = TravelAssistant()
    return _travel_assistant
