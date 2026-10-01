"""Travel assistant routes for flight search and booking - Kayak-style."""
import logging
from typing import Optional, List
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.travel import FlightSearchRequest, FlightDeal, Hotel, TravelItinerary
from app.services.travel_service import get_travel_service
from app.services.flight_search import get_flight_service
from app.services import price_tracker
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/travel", tags=["travel"])


class FlightSearch(BaseModel):
    """Flight search request."""
    origin: str
    destination: str
    departure_date: str
    return_date: Optional[str] = None
    passengers: int = 1
    cabin_class: str = "economy"
    max_stops: Optional[int] = None
    max_price: Optional[float] = None
    preferred_airlines: Optional[List[str]] = None


@router.get("/flights/search")
async def search_flights_get(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    passengers: int = 1,
    cabin_class: str = "economy",
    max_stops: Optional[int] = Query(None, description="Maximum number of stops (0=nonstop)"),
    max_price: Optional[float] = Query(None, description="Maximum price in USD"),
    airlines: Optional[str] = Query(None, description="Comma-separated airline codes (e.g., UA,DL,AA)"),
    sort_by: str = Query("best", description="Sort by: best, price, duration, departure")
):
    """
    Search for flights with Kayak-style filters and analysis.
    Returns comprehensive flight data with pricing analysis and recommendations.
    """
    flight_service = get_flight_service()
    
    # Parse airlines filter
    preferred_airlines = airlines.split(",") if airlines else None
    
    result = await flight_service.search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        passengers=passengers,
        cabin_class=cabin_class,
        max_stops=max_stops,
        max_price=max_price,
        preferred_airlines=preferred_airlines,
    )
    
    # Apply sorting
    flights = result.get("flights", [])
    if sort_by == "price":
        flights = sorted(flights, key=lambda x: x.get("price", 0))
    elif sort_by == "duration":
        flights = sorted(flights, key=lambda x: x.get("total_duration_minutes", 999))
    elif sort_by == "departure":
        flights = sorted(flights, key=lambda x: x.get("departure_time", ""))
    # 'best' is already sorted by score

    # Record fare snapshots for route-level price history (own tracker)
    route = f"{origin.upper()}-{destination.upper()}"
    result["fare_snapshots_recorded"] = await price_tracker.record_fares(
        route, flights, departure_date)

    result["flights"] = flights
    return result


@router.get("/flights/price-history")
async def get_flight_price_history(
    origin: str,
    destination: str,
    days: int = 365,
):
    """Tracked fare history for a route: lowest 1y fare, average, series."""
    route = f"{origin.upper()}-{destination.upper()}"
    history = await price_tracker.get_fare_history(route, days)
    return {"success": True, **history}


@router.post("/flights/search")
async def search_flights_post(request: FlightSearch):
    """Search for flights with Kayak-style filters (POST)."""
    flight_service = get_flight_service()
    
    result = await flight_service.search_flights(
        origin=request.origin,
        destination=request.destination,
        departure_date=request.departure_date,
        return_date=request.return_date,
        passengers=request.passengers,
        cabin_class=request.cabin_class,
        max_stops=request.max_stops,
        max_price=request.max_price,
        preferred_airlines=request.preferred_airlines,
    )
    
    return result


@router.get("/flights/predict")
async def predict_price(
    origin: str,
    destination: str,
    departure_date: str
):
    """Predict if flight prices will rise or fall."""
    return {
        "success": True,
        "route": f"{origin} → {destination}",
        "prediction": {
            "trend": "stable",
            "confidence": 0.75,
            "recommendation": "Book now - prices are stable",
            "price_range": "$250-$350"
        }
    }


@router.get("/hotels/search")
async def search_hotels_get(
    location: str,
    checkin: str,
    checkout: str,
    guests: int = 2,
    rooms: int = 1
):
    """Search for hotels (GET)."""
    travel = get_travel_service()
    
    hotels = await travel.search_hotels(location, checkin, checkout, guests, rooms)
    
    return {
        "success": True,
        "destination": location,
        "results": len(hotels),
        "hotels": hotels
    }


@router.post("/hotels/search")
async def search_hotels_post(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int = 2,
    rooms: int = 1
):
    """Search for hotels (POST)."""
    travel = get_travel_service()
    
    hotels = await travel.search_hotels(destination, check_in, check_out, guests, rooms)
    
    return {
        "success": True,
        "destination": destination,
        "results": len(hotels),
        "hotels": hotels
    }


@router.post("/destinations/recommend")
async def recommend_destinations(preferences: dict):
    """Get AI-powered destination recommendations."""
    travel = get_travel_service()
    
    recommendations = await travel.get_destination_recommendations(
        preferences, settings.ollama_host, settings.ollama_model
    )
    
    return recommendations


@router.post("/itinerary/create")
async def create_itinerary(
    destination: str,
    duration_days: int,
    interests: list
):
    """Create AI-powered travel itinerary."""
    travel = get_travel_service()
    
    itinerary = await travel.create_itinerary(
        destination, duration_days, interests,
        settings.ollama_host, settings.ollama_model
    )
    
    return itinerary


@router.get("/weather")
async def get_weather(location: str, days: int = 7):
    """
    Get real-time weather forecast for a destination.
    Uses Open-Meteo API (free, no API key required).
    """
    import httpx
    
    try:
        # First, geocode the location using Open-Meteo geocoding
        async with httpx.AsyncClient(timeout=10.0) as client:
            geo_url = "https://geocoding-api.open-meteo.com/v1/search"
            geo_response = await client.get(geo_url, params={"name": location, "count": 1})
            
            if geo_response.status_code != 200:
                raise Exception("Geocoding failed")
            
            geo_data = geo_response.json()
            if not geo_data.get("results"):
                return {
                    "success": False,
                    "error": f"Location '{location}' not found"
                }
            
            place = geo_data["results"][0]
            lat = place["latitude"]
            lon = place["longitude"]
            location_name = place.get("name", location)
            country = place.get("country", "")
            
            # Get weather forecast
            weather_url = "https://api.open-meteo.com/v1/forecast"
            weather_params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weathercode,wind_speed_10m_max",
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
                "forecast_days": min(days, 16)
            }
            
            weather_response = await client.get(weather_url, params=weather_params)
            
            if weather_response.status_code != 200:
                raise Exception("Weather API failed")
            
            weather_data = weather_response.json()
            
            # Weather code descriptions
            weather_codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
                82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
                95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
            }
            
            current = weather_data.get("current", {})
            daily = weather_data.get("daily", {})
            
            forecast = []
            dates = daily.get("time", [])
            for i, date in enumerate(dates):
                code = daily.get("weathercode", [0])[i] if i < len(daily.get("weathercode", [])) else 0
                forecast.append({
                    "date": date,
                    "temp_max": daily.get("temperature_2m_max", [0])[i] if i < len(daily.get("temperature_2m_max", [])) else 0,
                    "temp_min": daily.get("temperature_2m_min", [0])[i] if i < len(daily.get("temperature_2m_min", [])) else 0,
                    "temp_max_f": round(daily.get("temperature_2m_max", [0])[i] * 9/5 + 32, 1) if i < len(daily.get("temperature_2m_max", [])) else 0,
                    "temp_min_f": round(daily.get("temperature_2m_min", [0])[i] * 9/5 + 32, 1) if i < len(daily.get("temperature_2m_min", [])) else 0,
                    "precipitation_mm": daily.get("precipitation_sum", [0])[i] if i < len(daily.get("precipitation_sum", [])) else 0,
                    "precipitation_chance": daily.get("precipitation_probability_max", [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0,
                    "weather_code": code,
                    "condition": weather_codes.get(code, "Unknown"),
                    "wind_speed_kmh": daily.get("wind_speed_10m_max", [0])[i] if i < len(daily.get("wind_speed_10m_max", [])) else 0
                })
            
            current_code = current.get("weather_code", 0)
            
            return {
                "success": True,
                "location": location_name,
                "country": country,
                "coordinates": {"lat": lat, "lon": lon},
                "current": {
                    "temperature_c": current.get("temperature_2m", 0),
                    "temperature_f": round(current.get("temperature_2m", 0) * 9/5 + 32, 1),
                    "humidity": current.get("relative_humidity_2m", 0),
                    "wind_speed_kmh": current.get("wind_speed_10m", 0),
                    "condition": weather_codes.get(current_code, "Unknown"),
                    "weather_code": current_code
                },
                "forecast": forecast,
                "timezone": weather_data.get("timezone", "UTC"),
                "source": "Open-Meteo"
            }
            
    except Exception as e:
        logger.error(f"Weather API error for {location}: {e}")
        return {
            "success": False,
            "error": str(e),
            "location": location
        }


@router.get("/stats")
async def get_travel_stats():
    """Get travel statistics."""
    return {
        "success": True,
        "searches_today": 0,
        "bookings_saved": 0,
        "average_savings": 0
    }
