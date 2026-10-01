"""Travel assistant models for flight search and deal finding."""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel


class FlightSegment(BaseModel):
    """Flight segment information."""
    departure_airport: str
    arrival_airport: str
    departure_time: datetime
    arrival_time: datetime
    airline: str
    flight_number: str
    duration_minutes: int
    aircraft: Optional[str] = None
    cabin_class: str = "economy"


class Flight(BaseModel):
    """Flight information."""
    flight_id: str
    segments: List[FlightSegment]
    total_duration_minutes: int
    stops: int
    price: float
    currency: str = "USD"
    booking_url: str
    source: str  # kayak, google_flights, skyscanner
    baggage_included: bool = False
    refundable: bool = False
    last_updated: datetime


class FlightSearchRequest(BaseModel):
    """Flight search request."""
    origin: str
    destination: str
    departure_date: date
    return_date: Optional[date] = None
    passengers: int = 1
    cabin_class: str = "economy"
    flexible_dates: bool = True
    max_stops: Optional[int] = None
    max_price: Optional[float] = None
    preferred_airlines: List[str] = []


class FlightDeal(BaseModel):
    """Flight deal with price prediction."""
    flight: Flight
    is_good_deal: bool
    deal_score: float  # 0-100
    price_vs_average: float  # percentage difference
    historical_low: float
    historical_high: float
    predicted_price_trend: str  # "rising", "falling", "stable"
    best_time_to_book: str
    recommendation: str


class Hotel(BaseModel):
    """Hotel information."""
    hotel_id: str
    name: str
    address: str
    city: str
    country: str
    rating: float
    review_count: int
    price_per_night: float
    total_price: float
    amenities: List[str]
    images: List[str]
    booking_url: str
    cancellation_policy: str


class TravelItinerary(BaseModel):
    """Complete travel itinerary."""
    itinerary_id: str
    user_id: str
    outbound_flight: Flight
    return_flight: Optional[Flight] = None
    hotels: List[Hotel] = []
    car_rental: Optional[dict] = None
    total_cost: float
    created_date: datetime
    trip_start_date: date
    trip_end_date: date
    destination: str
