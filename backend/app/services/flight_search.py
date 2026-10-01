"""
Advanced Flight Search Service - Kayak-style
Provides real-time flight search with multiple providers and AI features
"""
import logging
import httpx
import asyncio
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json

logger = logging.getLogger(__name__)

@dataclass
class FlightSegment:
    """Individual flight segment"""
    airline: str
    airline_code: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    duration_minutes: int
    aircraft: str = ""
    cabin_class: str = "economy"

@dataclass
class FlightOffer:
    """Complete flight offer with all details"""
    id: str
    price: float
    currency: str
    segments: List[Dict]
    total_duration_minutes: int
    stops: int
    airlines: List[str]
    departure_time: str
    arrival_time: str
    booking_url: str
    source: str
    baggage: str
    amenities: List[str]
    layovers: List[Dict] = None
    price_breakdown: Dict = None
    fare_class: str = "economy"
    refundable: bool = False
    score: float = 0.0  # Deal score

class FlightSearchService:
    """
    Enterprise flight search with multiple providers:
    - SerpAPI (Google Flights)
    - Amadeus API
    - Fallback mock data
    """
    
    def __init__(self):
        self.serpapi_key = os.getenv("SERPAPI_KEY", "")
        self.amadeus_key = os.getenv("AMADEUS_API_KEY", "")
        self.amadeus_secret = os.getenv("AMADEUS_API_SECRET", "")
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        
        # Airline data
        self.airlines = {
            "UA": {"name": "United Airlines", "logo": "united.png"},
            "DL": {"name": "Delta Air Lines", "logo": "delta.png"},
            "AA": {"name": "American Airlines", "logo": "american.png"},
            "WN": {"name": "Southwest Airlines", "logo": "southwest.png"},
            "B6": {"name": "JetBlue Airways", "logo": "jetblue.png"},
            "AS": {"name": "Alaska Airlines", "logo": "alaska.png"},
            "NK": {"name": "Spirit Airlines", "logo": "spirit.png"},
            "F9": {"name": "Frontier Airlines", "logo": "frontier.png"},
            "HA": {"name": "Hawaiian Airlines", "logo": "hawaiian.png"},
            "SY": {"name": "Sun Country Airlines", "logo": "suncountry.png"},
        }
        
        # Airport codes to cities
        self.airports = {
            "JFK": "New York", "LAX": "Los Angeles", "ORD": "Chicago",
            "DFW": "Dallas", "DEN": "Denver", "SFO": "San Francisco",
            "SEA": "Seattle", "ATL": "Atlanta", "BOS": "Boston",
            "MIA": "Miami", "PHX": "Phoenix", "IAH": "Houston",
            "LAS": "Las Vegas", "MCO": "Orlando", "CLT": "Charlotte",
            "EWR": "Newark", "MSP": "Minneapolis", "DTW": "Detroit",
            "PHL": "Philadelphia", "LGA": "New York LaGuardia",
        }
    
    async def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: int = 1,
        cabin_class: str = "economy",
        max_stops: Optional[int] = None,
        max_price: Optional[float] = None,
        preferred_airlines: Optional[List[str]] = None,
        departure_time_range: Optional[tuple] = None,  # (start_hour, end_hour)
    ) -> Dict[str, Any]:
        """
        Search for flights with comprehensive filtering like Kayak
        """
        origin = origin.upper()[:3]
        destination = destination.upper()[:3]
        
        # Try real APIs first
        flights = []
        sources: List[str] = []
        api_status: List[Dict] = []
        real_count = 0
        
        # Try SerpAPI (Google Flights)
        if self.serpapi_key:
            try:
                serpapi_flights = await self.search_serpapi(
                    origin, destination, departure_date, return_date, passengers, cabin_class
                )
                flights.extend(serpapi_flights)
                logger.info(f"SerpAPI returned {len(serpapi_flights)} flights")
                real_count += len(serpapi_flights)
                if serpapi_flights:
                    sources.append("SerpAPI/Google Flights")
            except Exception as e:
                logger.error(f"SerpAPI error: {e}")
                api_status.append({"provider": "SerpAPI", "status": "error", "detail": str(e)[:200]})
        
        # Try Amadeus API
        if self.amadeus_key and self.amadeus_secret:
            try:
                amadeus_flights = await self.search_amadeus(
                    origin, destination, departure_date, return_date, passengers, cabin_class
                )
                flights.extend(amadeus_flights)
                logger.info(f"Amadeus returned {len(amadeus_flights)} flights")
                real_count += len(amadeus_flights)
                if amadeus_flights:
                    sources.append("Amadeus")
            except Exception as e:
                logger.error(f"Amadeus error: {e}")
                api_status.append({"provider": "Amadeus", "status": "error", "detail": str(e)[:200]})
        
        # Add realistic fallback data only when no real providers returned flights
        if not flights:
            api_status.append({"provider": "Avira Estimator", "status": "fallback", "detail": "No live API keys configured. Showing realistic price estimates."})
            for f in self._generate_realistic_flights(origin, destination, departure_date, return_date, passengers, cabin_class):
                f["source"] = "estimate"
                flights.append(f)
            sources.append("Avira Estimator")
        
        # Apply filters
        filtered_flights = self._apply_filters(
            flights, max_stops, max_price, preferred_airlines, departure_time_range
        )
        
        # Sort by price and score
        filtered_flights = self._score_and_sort_flights(filtered_flights)
        
        # Get price analysis
        price_analysis = self._analyze_prices(filtered_flights)
        
        # Build response like Kayak
        return {
            "success": True,
            "search": {
                "origin": origin,
                "origin_city": self.airports.get(origin, origin),
                "destination": destination,
                "destination_city": self.airports.get(destination, destination),
                "departure_date": departure_date,
                "return_date": return_date,
                "passengers": passengers,
                "cabin_class": cabin_class,
            },
            "results_count": len(filtered_flights),
            "flights": filtered_flights[:20],
            "price_analysis": price_analysis,
            "filters": {
                "available_airlines": list(set(f["airlines"][0] for f in filtered_flights if f.get("airlines"))),
                "price_range": {
                    "min": min(f["price"] for f in filtered_flights) if filtered_flights else 0,
                    "max": max(f["price"] for f in filtered_flights) if filtered_flights else 0,
                },
                "stops_available": list(set(f["stops"] for f in filtered_flights)),
            },
            "recommendations": self._get_recommendations(filtered_flights),
            "data_source": sources[0] if len(sources) == 1 else sources if sources else "estimate",
            "api_status": api_status if api_status else [{"provider": "Avira Estimator", "status": "ok", "detail": "Using realistic estimates. Add SERPAPI_KEY or AMADEUS_API_KEY to backend env for live prices."}],
        }
    
    async def search_serpapi(
        self, origin: str, destination: str, departure_date: str,
        return_date: Optional[str], passengers: int, cabin_class: str
    ) -> List[Dict]:
        """Search using SerpAPI Google Flights"""
        try:
            params = {
                "engine": "google_flights",
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": departure_date,
                "currency": "USD",
                "hl": "en",
                "api_key": self.serpapi_key,
            }
            
            if return_date:
                params["return_date"] = return_date
                params["type"] = "1"  # Round trip
            else:
                params["type"] = "2"  # One way
            
            # Map cabin class
            cabin_map = {"economy": "1", "premium_economy": "2", "business": "3", "first": "4"}
            params["travel_class"] = cabin_map.get(cabin_class.lower(), "1")
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get("https://serpapi.com/search", params=params)
                
                if response.status_code != 200:
                    return []
                
                data = response.json()
                flights = []
                
                # Parse best flights
                for flight in data.get("best_flights", []) + data.get("other_flights", []):
                    try:
                        segments = []
                        total_duration = 0
                        
                        for leg in flight.get("flights", []):
                            segments.append({
                                "airline": leg.get("airline", ""),
                                "airline_code": leg.get("airline_logo", "").split("/")[-1].split(".")[0].upper() if leg.get("airline_logo") else "",
                                "flight_number": leg.get("flight_number", ""),
                                "departure_airport": leg.get("departure_airport", {}).get("id", ""),
                                "arrival_airport": leg.get("arrival_airport", {}).get("id", ""),
                                "departure_time": leg.get("departure_airport", {}).get("time", ""),
                                "arrival_time": leg.get("arrival_airport", {}).get("time", ""),
                                "duration_minutes": leg.get("duration", 0),
                                "aircraft": leg.get("airplane", ""),
                            })
                            total_duration += leg.get("duration", 0)
                        
                        price = flight.get("price", 0)
                        if isinstance(price, str):
                            price = float(price.replace("$", "").replace(",", ""))
                        
                        flights.append({
                            "id": f"SERP{len(flights)+1}",
                            "price": price,
                            "currency": "USD",
                            "segments": segments,
                            "total_duration_minutes": total_duration,
                            "stops": len(segments) - 1,
                            "airlines": [s["airline"] for s in segments],
                            "departure_time": segments[0]["departure_time"] if segments else "",
                            "arrival_time": segments[-1]["arrival_time"] if segments else "",
                            "booking_url": flight.get("booking_token", "https://www.google.com/flights"),
                            "source": "Google Flights",
                            "baggage": "Check airline policy",
                            "amenities": [],
                            "layovers": flight.get("layovers", []),
                        })
                    except Exception as e:
                        logger.warning(f"Error parsing SerpAPI flight: {e}")
                        continue
                
                return flights
                
        except Exception as e:
            logger.error(f"SerpAPI search error: {e}")
            return []
    
    async def search_amadeus(
        self, origin: str, destination: str, departure_date: str,
        return_date: Optional[str], passengers: int, cabin_class: str
    ) -> List[Dict]:
        """Search using Amadeus API"""
        try:
            # Get access token
            async with httpx.AsyncClient(timeout=10.0) as client:
                auth_response = await client.post(
                    "https://api.amadeus.com/v1/security/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.amadeus_key,
                        "client_secret": self.amadeus_secret,
                    }
                )
                
                if auth_response.status_code != 200:
                    return []
                
                token = auth_response.json().get("access_token")
                
                # Search flights
                params = {
                    "originLocationCode": origin,
                    "destinationLocationCode": destination,
                    "departureDate": departure_date,
                    "adults": passengers,
                    "currencyCode": "USD",
                    "max": 20,
                }
                
                if return_date:
                    params["returnDate"] = return_date
                
                cabin_map = {"economy": "ECONOMY", "premium_economy": "PREMIUM_ECONOMY", 
                            "business": "BUSINESS", "first": "FIRST"}
                params["travelClass"] = cabin_map.get(cabin_class.lower(), "ECONOMY")
                
                search_response = await client.get(
                    "https://api.amadeus.com/v2/shopping/flight-offers",
                    params=params,
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if search_response.status_code != 200:
                    return []
                
                data = search_response.json()
                flights = []
                
                for offer in data.get("data", []):
                    try:
                        segments = []
                        total_duration = 0
                        
                        for itinerary in offer.get("itineraries", []):
                            for segment in itinerary.get("segments", []):
                                duration_str = segment.get("duration", "PT0H0M")
                                hours = int(duration_str.split("H")[0].replace("PT", "")) if "H" in duration_str else 0
                                minutes = int(duration_str.split("H")[-1].replace("M", "")) if "M" in duration_str else 0
                                duration_mins = hours * 60 + minutes
                                
                                segments.append({
                                    "airline": segment.get("carrierCode", ""),
                                    "airline_code": segment.get("carrierCode", ""),
                                    "flight_number": f"{segment.get('carrierCode', '')}{segment.get('number', '')}",
                                    "departure_airport": segment.get("departure", {}).get("iataCode", ""),
                                    "arrival_airport": segment.get("arrival", {}).get("iataCode", ""),
                                    "departure_time": segment.get("departure", {}).get("at", ""),
                                    "arrival_time": segment.get("arrival", {}).get("at", ""),
                                    "duration_minutes": duration_mins,
                                    "aircraft": segment.get("aircraft", {}).get("code", ""),
                                })
                                total_duration += duration_mins
                        
                        price = float(offer.get("price", {}).get("total", 0))
                        
                        flights.append({
                            "id": offer.get("id", f"AMAD{len(flights)+1}"),
                            "price": price,
                            "currency": offer.get("price", {}).get("currency", "USD"),
                            "segments": segments,
                            "total_duration_minutes": total_duration,
                            "stops": len(segments) - 1,
                            "airlines": list(set(s["airline"] for s in segments)),
                            "departure_time": segments[0]["departure_time"] if segments else "",
                            "arrival_time": segments[-1]["arrival_time"] if segments else "",
                            "booking_url": "https://www.amadeus.com",
                            "source": "Amadeus",
                            "baggage": "1 carry-on included",
                            "amenities": [],
                        })
                    except Exception as e:
                        logger.warning(f"Error parsing Amadeus flight: {e}")
                        continue
                
                return flights
                
        except Exception as e:
            logger.error(f"Amadeus search error: {e}")
            return []
    
    def _generate_realistic_flights(
        self, origin: str, destination: str, departure_date: str,
        return_date: Optional[str], passengers: int, cabin_class: str
    ) -> List[Dict]:
        """Generate realistic flight data with proper pricing"""
        import random
        
        # Base prices by distance (miles)
        route_distances = {
            # US Domestic
            ("JFK", "LAX"): 2475, ("LAX", "JFK"): 2475,
            ("SFO", "JFK"): 2586, ("JFK", "SFO"): 2586,
            ("ORD", "LAX"): 1745, ("LAX", "ORD"): 1745,
            ("ATL", "LAX"): 1947, ("LAX", "ATL"): 1947,
            ("DFW", "JFK"): 1391, ("JFK", "DFW"): 1391,
            ("DEN", "MIA"): 1727, ("MIA", "DEN"): 1727,
            ("CLT", "JFK"): 541, ("JFK", "CLT"): 541,
            ("CLT", "ATL"): 227, ("ATL", "CLT"): 227,
            ("CLT", "MIA"): 647, ("MIA", "CLT"): 647,
            ("CLT", "ORD"): 599, ("ORD", "CLT"): 599,
            ("CLT", "LAX"): 2125, ("LAX", "CLT"): 2125,
            ("CLT", "SFO"): 2296, ("SFO", "CLT"): 2296,
            ("CLT", "DEN"): 1339, ("DEN", "CLT"): 1339,
            ("RDU", "JFK"): 427, ("JFK", "RDU"): 427,
            # US to India
            ("CLT", "HYD"): 8750, ("HYD", "CLT"): 8750,
            ("CLT", "DEL"): 8400, ("DEL", "CLT"): 8400,
            ("CLT", "BOM"): 8600, ("BOM", "CLT"): 8600,
            ("CLT", "BLR"): 8800, ("BLR", "CLT"): 8800,
            ("CLT", "MAA"): 8900, ("MAA", "CLT"): 8900,
            ("JFK", "DEL"): 7310, ("DEL", "JFK"): 7310,
            ("JFK", "BOM"): 7800, ("BOM", "JFK"): 7800,
            ("JFK", "HYD"): 8200, ("HYD", "JFK"): 8200,
            ("RDU", "HYD"): 8500, ("HYD", "RDU"): 8500,
            # US to Europe
            ("JFK", "LHR"): 3459, ("LHR", "JFK"): 3459,
            ("JFK", "CDG"): 3635, ("CDG", "JFK"): 3635,
            ("CLT", "LHR"): 3770, ("LHR", "CLT"): 3770,
            # US to Asia
            ("JFK", "NRT"): 6756, ("NRT", "JFK"): 6756,
            ("LAX", "NRT"): 5451, ("NRT", "LAX"): 5451,
            ("SFO", "HKG"): 6927, ("HKG", "SFO"): 6927,
        }
        
        # Classify international airports to estimate unknown distances
        intl_airports = {
            "HYD", "DEL", "BOM", "BLR", "MAA", "CCU",  # India
            "LHR", "CDG", "FRA", "AMS", "FCO",  # Europe
            "NRT", "HND", "ICN", "PVG", "HKG", "SIN", "BKK",  # Asia
            "DXB", "DOH", "AUH",  # Middle East
        }
        
        distance = route_distances.get((origin, destination))
        if distance is None:
            # Estimate: if either airport is international, assume long-haul
            if origin in intl_airports or destination in intl_airports:
                distance = 8000  # Default international
            else:
                distance = 1200  # Default domestic
        
        # Distance-based pricing calibrated to real market fares.
        # Long-haul intl (e.g. CLT-HYD): round-trip economy $1,100-$1,600;
        # one-way is ~60% of round-trip (never half).
        is_round_trip = bool(return_date)
        if distance > 5000:  # International long-haul
            rt_base = 900 + (distance * 0.055)   # CLT-HYD (8750mi) => ~$1,380 RT
            base_price = rt_base if is_round_trip else rt_base * 0.60
        elif distance > 3000:  # Transatlantic
            rt_base = 550 + (distance * 0.09)
            base_price = rt_base if is_round_trip else rt_base * 0.60
        else:  # Domestic: compute one-way, round trip ~1.9x
            if distance > 1500:  # Cross-country
                base_price = 120 + (distance * 0.07)
            elif distance > 500:  # Regional
                base_price = 80 + (distance * 0.09)
            else:  # Short-haul
                base_price = 60 + (distance * 0.12)
            if is_round_trip:
                base_price *= 1.9
        
        # Cabin class multipliers
        cabin_mult = {"economy": 1.0, "premium_economy": 1.6, "business": 3.2, "first": 5.5}
        mult = cabin_mult.get(cabin_class.lower(), 1.0)
        
        # Flight duration based on distance
        base_duration = int(distance / 500 * 60)  # ~500mph average
        
        flights = []
        
        # Choose airline templates based on route type
        is_international = distance > 5000
        
        if is_international:
            # hub = realistic connection airport for the carrier
            flight_templates = [
                {"airline": "Air India", "code": "AI", "price_adj": 0.85, "quality": 0.75, "hub": "DEL"},
                {"airline": "Emirates", "code": "EK", "price_adj": 1.20, "quality": 0.95, "hub": "DXB"},
                {"airline": "Qatar Airways", "code": "QR", "price_adj": 1.15, "quality": 0.93, "hub": "DOH"},
                {"airline": "Etihad Airways", "code": "EY", "price_adj": 1.05, "quality": 0.90, "hub": "AUH"},
                {"airline": "United Airlines", "code": "UA", "price_adj": 1.0, "quality": 0.85, "hub": "EWR"},
                {"airline": "Delta Air Lines", "code": "DL", "price_adj": 1.05, "quality": 0.88, "hub": "JFK"},
                {"airline": "American Airlines", "code": "AA", "price_adj": 0.98, "quality": 0.82, "hub": "JFK"},
                {"airline": "Lufthansa", "code": "LH", "price_adj": 1.10, "quality": 0.90, "hub": "FRA"},
                {"airline": "British Airways", "code": "BA", "price_adj": 1.08, "quality": 0.88, "hub": "LHR"},
            ]
        else:
            flight_templates = [
                {"airline": "United Airlines", "code": "UA", "price_adj": 1.0, "quality": 0.85},
                {"airline": "Delta Air Lines", "code": "DL", "price_adj": 1.05, "quality": 0.88},
                {"airline": "American Airlines", "code": "AA", "price_adj": 0.98, "quality": 0.82},
                {"airline": "Southwest Airlines", "code": "WN", "price_adj": 0.85, "quality": 0.78, "stops": 0},
                {"airline": "JetBlue Airways", "code": "B6", "price_adj": 0.92, "quality": 0.84},
                {"airline": "Alaska Airlines", "code": "AS", "price_adj": 0.95, "quality": 0.86},
                {"airline": "Spirit Airlines", "code": "NK", "price_adj": 0.75, "quality": 0.65},
                {"airline": "Frontier Airlines", "code": "F9", "price_adj": 0.72, "quality": 0.62},
            ]
        
        departure_times = ["06:00", "08:30", "10:15", "12:45", "14:30", "16:00", "18:30", "20:00", "22:15"]
        
        for i, template in enumerate(flight_templates):
            for j, dep_time in enumerate(departure_times[:3]):  # 3 times per airline
                if is_international:
                    # No nonstops on ultra long-haul secondary routes (e.g. CLT-HYD)
                    stops = template.get("stops", random.choice([1, 1, 1, 2]))
                else:
                    stops = template.get("stops", random.choice([0, 0, 0, 1, 1, 2]))
                
                # Price varies by time and stops
                time_adj = 1.0 + (0.1 if "08" in dep_time or "18" in dep_time else -0.05)
                stops_adj = 1.0 - ((stops - (1 if is_international else 0)) * 0.10)
                
                price = round(base_price * mult * template["price_adj"] * time_adj * stops_adj + random.uniform(-20, 40), 2)
                
                # Duration increases with stops (intl layovers 1.5-4h)
                layover_minutes = stops * (random.randint(90, 240) if is_international else random.randint(45, 120))
                duration = base_duration + layover_minutes
                
                # Parse departure time; arrivals can roll into next days
                dep_hour, dep_min = map(int, dep_time.split(":"))
                total_arrival_minutes = dep_hour * 60 + dep_min + duration
                arr_days = total_arrival_minutes // 1440
                arr_hour = (total_arrival_minutes % 1440) // 60
                arr_min = total_arrival_minutes % 60
                arrival_time = f"{arr_hour:02d}:{arr_min:02d}"
                from datetime import datetime as _dt, timedelta as _td
                arrival_date = (_dt.strptime(departure_date, "%Y-%m-%d") + _td(days=arr_days)).strftime("%Y-%m-%d")
                
                # Build segments
                segments = [{
                    "airline": template["airline"],
                    "airline_code": template["code"],
                    "flight_number": f"{template['code']}{100 + i*10 + j}",
                    "departure_airport": origin,
                    "arrival_airport": destination if stops == 0 else "ORD",
                    "departure_time": f"{departure_date}T{dep_time}:00",
                    "arrival_time": f"{departure_date}T{arrival_time}:00",
                    "duration_minutes": duration if stops == 0 else duration // 2,
                    "aircraft": random.choice(["Boeing 737-800", "Airbus A320", "Boeing 737 MAX 8", "Airbus A321"]),
                }]
                
                if stops > 0:
                    # Add connecting segment via a realistic hub for this carrier
                    if is_international:
                        layover_airport = template.get("hub", "DOH")
                        conn_aircraft = ["Boeing 777-300ER", "Airbus A350-900", "Boeing 787-9"]
                    else:
                        layover_airport = random.choice(["ORD", "DFW", "ATL", "DEN"])
                        conn_aircraft = ["Boeing 737-800", "Airbus A320"]
                    conn_duration = duration // 2
                    segments[0]["arrival_airport"] = layover_airport
                    segments.append({
                        "airline": template["airline"],
                        "airline_code": template["code"],
                        "flight_number": f"{template['code']}{200 + i*10 + j}",
                        "departure_airport": layover_airport,
                        "arrival_airport": destination,
                        "departure_time": f"{departure_date}T{(dep_hour + duration//120 + 1) % 24:02d}:30:00",
                        "arrival_time": f"{arrival_date}T{arr_hour:02d}:{arr_min:02d}:00",
                        "duration_minutes": conn_duration,
                        "aircraft": random.choice(conn_aircraft),
                    })
                
                layovers = []
                if stops > 0:
                    layovers.append({
                        "airport": layover_airport,
                        "city": self.airports.get(layover_airport, layover_airport),
                        "duration_minutes": random.randint(90, 240) if is_international else random.randint(45, 150),
                    })
                
                flights.append({
                    "id": f"FL{len(flights)+1:04d}",
                    "price": price,
                    "currency": "USD",
                    "segments": segments,
                    "total_duration_minutes": duration,
                    "stops": stops,
                    "airlines": [template["airline"]],
                    "airline_codes": [template["code"]],
                    "departure_time": f"{departure_date}T{dep_time}:00",
                    "arrival_time": f"{arrival_date}T{arrival_time}:00",
                    "trip_type": "round_trip" if is_round_trip else "one_way",
                    "booking_url": f"https://www.{template['airline'].lower().replace(' ', '')}.com/book",
                    "source": "Estimate",
                    "baggage": "1 carry-on" if template["code"] in ["NK", "F9"] else "1 carry-on + 1 checked",
                    "amenities": self._get_amenities(template["code"]),
                    "layovers": layovers,
                    "quality_score": template["quality"],
                    "fare_class": cabin_class,
                    "refundable": random.choice([True, False, False]),
                })
        
        return flights
    
    def _get_amenities(self, airline_code: str) -> List[str]:
        """Get amenities by airline"""
        amenities_map = {
            "UA": ["WiFi", "Power outlets", "Entertainment", "Meals on long flights"],
            "DL": ["WiFi", "Power outlets", "Entertainment", "Snacks", "Premium cabin"],
            "AA": ["WiFi", "Entertainment", "Power outlets"],
            "WN": ["WiFi", "No change fees", "2 free checked bags"],
            "B6": ["WiFi", "Live TV", "Extra legroom available", "Snacks"],
            "AS": ["WiFi", "Power outlets", "Premium class"],
            "NK": ["WiFi (paid)", "Snacks (paid)"],
            "F9": ["WiFi (paid)"],
        }
        return amenities_map.get(airline_code, ["WiFi"])
    
    def _apply_filters(
        self, flights: List[Dict], max_stops: Optional[int],
        max_price: Optional[float], preferred_airlines: Optional[List[str]],
        departure_time_range: Optional[tuple]
    ) -> List[Dict]:
        """Apply Kayak-style filters"""
        filtered = flights
        
        if max_stops is not None:
            filtered = [f for f in filtered if f.get("stops", 0) <= max_stops]
        
        if max_price is not None:
            filtered = [f for f in filtered if f.get("price", 0) <= max_price]
        
        if preferred_airlines:
            filtered = [f for f in filtered if any(
                airline in f.get("airlines", []) or airline in f.get("airline_codes", [])
                for airline in preferred_airlines
            )]
        
        if departure_time_range:
            start_hour, end_hour = departure_time_range
            def in_range(flight):
                try:
                    dep_time = flight.get("departure_time", "")
                    if "T" in dep_time:
                        hour = int(dep_time.split("T")[1].split(":")[0])
                        return start_hour <= hour <= end_hour
                except:
                    pass
                return True
            filtered = [f for f in filtered if in_range(f)]
        
        return filtered
    
    def _score_and_sort_flights(self, flights: List[Dict]) -> List[Dict]:
        """Score flights like Kayak and sort"""
        if not flights:
            return flights
        
        prices = [f["price"] for f in flights]
        min_price, max_price = min(prices), max(prices)
        price_range = max_price - min_price if max_price > min_price else 1
        
        durations = [f.get("total_duration_minutes", 300) for f in flights]
        min_dur, max_dur = min(durations), max(durations)
        dur_range = max_dur - min_dur if max_dur > min_dur else 1
        
        for flight in flights:
            # Price score (lower is better) - 40% weight
            price_score = 1 - ((flight["price"] - min_price) / price_range)
            
            # Duration score (shorter is better) - 30% weight
            duration = flight.get("total_duration_minutes", 300)
            duration_score = 1 - ((duration - min_dur) / dur_range)
            
            # Stops score (fewer is better) - 20% weight
            stops_score = 1 - (flight.get("stops", 0) / 3)
            
            # Quality score - 10% weight
            quality_score = flight.get("quality_score", 0.7)
            
            # Combined score
            flight["score"] = round(
                (price_score * 0.4) + (duration_score * 0.3) + 
                (stops_score * 0.2) + (quality_score * 0.1), 2
            ) * 10
            
            # Add deal badge
            if flight["price"] == min_price:
                flight["deal_badge"] = "Best Price"
            elif flight.get("stops", 0) == 0 and duration == min_dur:
                flight["deal_badge"] = "Fastest"
            elif flight["score"] >= 8:
                flight["deal_badge"] = "Best Value"
        
        return sorted(flights, key=lambda x: (-x.get("score", 0), x["price"]))
    
    def _analyze_prices(self, flights: List[Dict]) -> Dict:
        """Analyze prices like Kayak"""
        if not flights:
            return {"average": 0, "min": 0, "max": 0, "recommendation": "No flights found"}
        
        prices = [f["price"] for f in flights]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        # Price trend recommendation
        if min_price < avg_price * 0.8:
            recommendation = "Great deal available! Book now."
        elif min_price < avg_price * 0.95:
            recommendation = "Good prices available. Consider booking soon."
        else:
            recommendation = "Prices are average. Consider flexible dates."
        
        return {
            "average": round(avg_price, 2),
            "min": round(min_price, 2),
            "max": round(max_price, 2),
            "median": round(sorted(prices)[len(prices)//2], 2),
            "recommendation": recommendation,
            "price_trend": "stable",
            "best_time_to_book": "2-3 weeks before departure",
        }
    
    def _get_recommendations(self, flights: List[Dict]) -> List[Dict]:
        """Get smart recommendations"""
        if not flights:
            return []
        
        recommendations = []
        
        # Best overall
        best_overall = max(flights, key=lambda x: x.get("score", 0))
        recommendations.append({
            "type": "best_overall",
            "title": "Best Overall",
            "flight_id": best_overall["id"],
            "reason": f"Best combination of price (${best_overall['price']}) and convenience",
        })
        
        # Cheapest
        cheapest = min(flights, key=lambda x: x["price"])
        if cheapest["id"] != best_overall["id"]:
            recommendations.append({
                "type": "cheapest",
                "title": "Lowest Price",
                "flight_id": cheapest["id"],
                "reason": f"Save ${round(best_overall['price'] - cheapest['price'], 2)} compared to best overall",
            })
        
        # Fastest nonstop
        nonstops = [f for f in flights if f.get("stops", 1) == 0]
        if nonstops:
            fastest = min(nonstops, key=lambda x: x.get("total_duration_minutes", 999))
            if fastest["id"] not in [r["flight_id"] for r in recommendations]:
                recommendations.append({
                    "type": "fastest",
                    "title": "Fastest Nonstop",
                    "flight_id": fastest["id"],
                    "reason": f"Direct flight in {fastest['total_duration_minutes']//60}h {fastest['total_duration_minutes']%60}m",
                })
        
        return recommendations


# Singleton
_flight_service: Optional[FlightSearchService] = None

def get_flight_service() -> FlightSearchService:
    global _flight_service
    if _flight_service is None:
        _flight_service = FlightSearchService()
    return _flight_service
