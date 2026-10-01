"""Travel intelligence service with flight search and deal finding."""
import logging
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
import asyncio

from app.models.travel import (
    Flight, FlightSegment, FlightSearchRequest, FlightDeal,
    Hotel, TravelItinerary
)

logger = logging.getLogger(__name__)


class TravelIntelligence:
    """Travel intelligence with flight search and price predictions."""
    
    def __init__(self):
        self.flight_cache: Dict[str, List[Flight]] = {}
        self.price_history: Dict[str, List[float]] = {}
        
    async def search_flights(self, request: FlightSearchRequest) -> List[FlightDeal]:
        """Search for flights with flexible dates and deal analysis."""
        all_flights = []
        
        # Search main date
        flights = await self._search_flights_for_date(
            request.origin,
            request.destination,
            request.departure_date,
            request.return_date,
            request.passengers,
            request.cabin_class
        )
        all_flights.extend(flights)
        
        # Search flexible dates if requested
        if request.flexible_dates:
            for days_offset in [-3, -2, -1, 1, 2, 3]:
                flex_departure = request.departure_date + timedelta(days=days_offset)
                flex_return = request.return_date + timedelta(days=days_offset) if request.return_date else None
                
                flex_flights = await self._search_flights_for_date(
                    request.origin,
                    request.destination,
                    flex_departure,
                    flex_return,
                    request.passengers,
                    request.cabin_class
                )
                all_flights.extend(flex_flights)
        
        # Filter by max stops
        if request.max_stops is not None:
            all_flights = [f for f in all_flights if f.stops <= request.max_stops]
        
        # Filter by max price
        if request.max_price:
            all_flights = [f for f in all_flights if f.price <= request.max_price]
        
        # Filter by preferred airlines
        if request.preferred_airlines:
            all_flights = [
                f for f in all_flights 
                if any(seg.airline in request.preferred_airlines for seg in f.segments)
            ]
        
        # Analyze deals
        flight_deals = []
        for flight in all_flights:
            deal = await self._analyze_flight_deal(flight, request.origin, request.destination)
            flight_deals.append(deal)
        
        # Sort by deal score
        flight_deals.sort(key=lambda d: d.deal_score, reverse=True)
        
        return flight_deals[:20]
    
    async def search_hotels(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        guests: int = 1
    ) -> List[Hotel]:
        """Search for hotels."""
        # TODO: Implement hotel search via Booking.com, Hotels.com, etc.
        return []
    
    async def create_itinerary(
        self,
        user_id: str,
        outbound_flight: Flight,
        return_flight: Optional[Flight],
        hotels: List[Hotel]
    ) -> TravelItinerary:
        """Create complete travel itinerary."""
        total_cost = outbound_flight.price
        if return_flight:
            total_cost += return_flight.price
        total_cost += sum(h.total_price for h in hotels)
        
        trip_start = outbound_flight.segments[0].departure_time.date()
        trip_end = return_flight.segments[-1].arrival_time.date() if return_flight else trip_start
        
        itinerary = TravelItinerary(
            itinerary_id=f"itin_{user_id}_{int(datetime.now().timestamp())}",
            user_id=user_id,
            outbound_flight=outbound_flight,
            return_flight=return_flight,
            hotels=hotels,
            total_cost=total_cost,
            created_date=datetime.now(),
            trip_start_date=trip_start,
            trip_end_date=trip_end,
            destination=outbound_flight.segments[-1].arrival_airport
        )
        
        return itinerary
    
    async def get_price_prediction(
        self,
        origin: str,
        destination: str,
        departure_date: date
    ) -> Dict[str, any]:
        """Predict if prices will rise or fall."""
        # Get historical prices
        route_key = f"{origin}_{destination}"
        history = self.price_history.get(route_key, [])
        
        if len(history) < 7:
            return {
                "prediction": "insufficient_data",
                "confidence": 0.0,
                "recommendation": "Book now if price is acceptable"
            }
        
        # Simple trend analysis
        recent_avg = sum(history[-7:]) / 7
        older_avg = sum(history[-14:-7]) / 7 if len(history) >= 14 else recent_avg
        
        trend = "rising" if recent_avg > older_avg * 1.05 else "falling" if recent_avg < older_avg * 0.95 else "stable"
        
        # Days until departure
        days_until = (departure_date - date.today()).days
        
        # Recommendation logic
        if trend == "rising" or days_until < 21:
            recommendation = "Book now - prices likely to increase"
            confidence = 0.7
        elif trend == "falling" and days_until > 60:
            recommendation = "Wait - prices may drop further"
            confidence = 0.6
        else:
            recommendation = "Monitor prices for a few more days"
            confidence = 0.5
        
        return {
            "prediction": trend,
            "confidence": confidence,
            "recommendation": recommendation,
            "current_average": recent_avg,
            "days_until_departure": days_until
        }
    
    # Private helper methods
    
    async def _search_flights_for_date(
        self,
        origin: str,
        destination: str,
        departure_date: date,
        return_date: Optional[date],
        passengers: int,
        cabin_class: str
    ) -> List[Flight]:
        """Search flights for specific date."""
        # TODO: Implement real flight search via Kayak, Google Flights, Skyscanner APIs
        # For now, return mock data
        
        cache_key = f"{origin}_{destination}_{departure_date}_{return_date}"
        if cache_key in self.flight_cache:
            return self.flight_cache[cache_key]
        
        # Mock flight data
        flights = []
        
        # Store in cache
        self.flight_cache[cache_key] = flights
        
        return flights
    
    async def _analyze_flight_deal(
        self,
        flight: Flight,
        origin: str,
        destination: str
    ) -> FlightDeal:
        """Analyze if flight is a good deal."""
        route_key = f"{origin}_{destination}"
        
        # Get historical prices
        history = self.price_history.get(route_key, [])
        
        if not history:
            # No historical data
            return FlightDeal(
                flight=flight,
                is_good_deal=False,
                deal_score=50.0,
                price_vs_average=0.0,
                historical_low=flight.price,
                historical_high=flight.price,
                predicted_price_trend="unknown",
                best_time_to_book="now",
                recommendation="No historical data available"
            )
        
        avg_price = sum(history) / len(history)
        low_price = min(history)
        high_price = max(history)
        
        price_vs_avg = ((flight.price - avg_price) / avg_price) * 100
        
        # Calculate deal score
        deal_score = 50.0
        if flight.price <= low_price * 1.1:
            deal_score = 90.0
        elif flight.price <= avg_price * 0.9:
            deal_score = 75.0
        elif flight.price <= avg_price:
            deal_score = 60.0
        elif flight.price >= avg_price * 1.2:
            deal_score = 30.0
        
        # Adjust for stops
        if flight.stops == 0:
            deal_score += 10
        elif flight.stops > 1:
            deal_score -= 10
        
        is_good_deal = deal_score >= 70.0
        
        # Predict trend
        recent_prices = history[-7:] if len(history) >= 7 else history
        recent_avg = sum(recent_prices) / len(recent_prices)
        trend = "rising" if recent_avg > avg_price else "falling" if recent_avg < avg_price else "stable"
        
        # Generate recommendation
        if is_good_deal:
            recommendation = f"Excellent deal! ${flight.price:.2f} is {abs(price_vs_avg):.0f}% below average"
        elif flight.price <= avg_price:
            recommendation = f"Good price at ${flight.price:.2f}, close to average"
        else:
            recommendation = f"Price is {price_vs_avg:.0f}% above average. Consider waiting."
        
        return FlightDeal(
            flight=flight,
            is_good_deal=is_good_deal,
            deal_score=deal_score,
            price_vs_average=price_vs_avg,
            historical_low=low_price,
            historical_high=high_price,
            predicted_price_trend=trend,
            best_time_to_book="now" if is_good_deal else "monitor",
            recommendation=recommendation
        )


# Singleton instance
_travel_intelligence: Optional[TravelIntelligence] = None


def get_travel_intelligence() -> TravelIntelligence:
    """Get travel intelligence singleton."""
    global _travel_intelligence
    if _travel_intelligence is None:
        _travel_intelligence = TravelIntelligence()
    return _travel_intelligence
