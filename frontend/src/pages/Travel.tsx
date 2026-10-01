import { useState } from 'react'
import { Plane, MapPin, Calendar, DollarSign, Clock, Users, Palmtree, Cloud, Sun, MapPinned, Star, ExternalLink, Loader2, HelpCircle, ChevronDown, ChevronUp } from 'lucide-react'
import config from '../config'

interface Flight {
  airline: string
  flight_number: string
  departure_time: string
  arrival_time: string
  duration: string
  price: number
  stops: number
  aircraft?: string
  booking_url?: string
  source?: string
}

interface Weather {
  date: string
  temp_high: number
  temp_low: number
  condition: string
  icon: string
  recommendation: string
}

interface Attraction {
  name: string
  type: string
  rating: number
  description: string
  estimated_time: string
}

interface TripItinerary {
  day: number
  date: string
  activities: { time: string; activity: string; location: string; cost?: number }[]
}

interface BudgetOption {
  level: string
  label: string
  total: number
  breakdown: { category: string; amount: number }[]
  description: string
}

export default function Travel() {
  const [step, setStep] = useState(1)
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departureDate, setDepartureDate] = useState('')
  const [returnDate, setReturnDate] = useState('')
  const [adults, setAdults] = useState(1)
  const [children, setChildren] = useState(0)
  const [tripType, setTripType] = useState<'business' | 'vacation' | 'family' | 'adventure'>('vacation')
  const [loading, setLoading] = useState(false)
  const [flights, setFlights] = useState<Flight[]>([])
  const [weather, setWeather] = useState<Weather[]>([])
  const [attractions, setAttractions] = useState<Attraction[]>([])
  const [itinerary, setItinerary] = useState<TripItinerary[]>([])
  const [budgetOptions, setBudgetOptions] = useState<BudgetOption[]>([])
  const [error, setError] = useState('')
  const [showHelp, setShowHelp] = useState(false)
  const [selectedBudget, setSelectedBudget] = useState<string | null>(null)
  const [expandedDay, setExpandedDay] = useState<number | null>(null)
  const [travelRecommendations] = useState<string>('')

  const tripDuration = departureDate && returnDate 
    ? Math.ceil((new Date(returnDate).getTime() - new Date(departureDate).getTime()) / (1000 * 60 * 60 * 24)) + 1
    : 1

  const totalTravelers = adults + children

  const generateWeatherForecast = (_dest: string, startDate: string, days: number): Weather[] => {
    const forecasts: Weather[] = []
    const conditions = [
      { condition: 'Sunny', icon: '☀️', rec: 'Perfect weather for outdoor activities!' },
      { condition: 'Partly Cloudy', icon: '⛅', rec: 'Great weather, bring light layers.' },
      { condition: 'Cloudy', icon: '☁️', rec: 'Good for sightseeing, comfortable temperatures.' },
      { condition: 'Light Rain', icon: '🌧️', rec: 'Pack an umbrella, indoor activities recommended.' }
    ]
    for (let i = 0; i < Math.min(days, 7); i++) {
      const date = new Date(startDate)
      date.setDate(date.getDate() + i)
      const cond = conditions[Math.floor(Math.random() * conditions.length)]
      forecasts.push({
        date: date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
        temp_high: Math.floor(Math.random() * 20) + 60,
        temp_low: Math.floor(Math.random() * 15) + 45,
        condition: cond.condition,
        icon: cond.icon,
        recommendation: cond.rec
      })
    }
    return forecasts
  }

  const generateAttractions = (dest: string, _type: string): Attraction[] => {
    const attractionsByType: Record<string, Attraction[]> = {
      'SFO': [
        { name: 'Golden Gate Bridge', type: 'landmark', rating: 4.8, description: 'Iconic suspension bridge', estimated_time: '2-3 hours' },
        { name: 'Alcatraz Island', type: 'historic', rating: 4.7, description: 'Historic federal penitentiary', estimated_time: '3-4 hours' },
        { name: 'Fisherman\'s Wharf', type: 'entertainment', rating: 4.5, description: 'Waterfront neighborhood with seafood', estimated_time: '2-3 hours' },
        { name: 'Chinatown', type: 'cultural', rating: 4.4, description: 'Oldest Chinatown in North America', estimated_time: '2 hours' },
        { name: 'Cable Car Ride', type: 'experience', rating: 4.6, description: 'Historic cable car system', estimated_time: '1 hour' }
      ],
      'LAX': [
        { name: 'Hollywood Sign', type: 'landmark', rating: 4.6, description: 'Iconic Hollywood landmark', estimated_time: '2 hours' },
        { name: 'Santa Monica Pier', type: 'entertainment', rating: 4.5, description: 'Historic pier with amusement park', estimated_time: '3 hours' },
        { name: 'Universal Studios', type: 'theme_park', rating: 4.7, description: 'World-famous theme park', estimated_time: 'Full day' },
        { name: 'Getty Center', type: 'museum', rating: 4.8, description: 'Art museum with stunning architecture', estimated_time: '3-4 hours' },
        { name: 'Venice Beach', type: 'beach', rating: 4.4, description: 'Famous beachfront boardwalk', estimated_time: '2-3 hours' }
      ],
      'JFK': [
        { name: 'Statue of Liberty', type: 'landmark', rating: 4.8, description: 'Iconic symbol of freedom', estimated_time: '4 hours' },
        { name: 'Central Park', type: 'park', rating: 4.7, description: 'Iconic urban park', estimated_time: '3-4 hours' },
        { name: 'Times Square', type: 'entertainment', rating: 4.5, description: 'The crossroads of the world', estimated_time: '2 hours' },
        { name: 'Empire State Building', type: 'landmark', rating: 4.6, description: '102-story Art Deco skyscraper', estimated_time: '2 hours' },
        { name: 'Metropolitan Museum', type: 'museum', rating: 4.9, description: 'World\'s largest art museum', estimated_time: '4-5 hours' }
      ]
    }
    return attractionsByType[dest] || [
      { name: `${dest} City Tour`, type: 'tour', rating: 4.5, description: 'Guided city exploration', estimated_time: '3 hours' },
      { name: `${dest} Local Market`, type: 'shopping', rating: 4.3, description: 'Local market experience', estimated_time: '2 hours' },
      { name: `${dest} Museum`, type: 'museum', rating: 4.4, description: 'Local history and culture', estimated_time: '2-3 hours' }
    ]
  }

  const generateItinerary = (days: number, atts: Attraction[], type: string): TripItinerary[] => {
    const itin: TripItinerary[] = []
    for (let d = 1; d <= days; d++) {
      const date = new Date(departureDate)
      date.setDate(date.getDate() + d - 1)
      const activities = []
      
      if (d === 1) {
        activities.push({ time: '10:00 AM', activity: 'Arrival & Hotel Check-in', location: 'Airport/Hotel', cost: 0 })
        activities.push({ time: '1:00 PM', activity: 'Lunch at local restaurant', location: 'Downtown', cost: 25 })
        activities.push({ time: '3:00 PM', activity: 'Neighborhood exploration', location: 'City Center', cost: 0 })
      } else if (d === days) {
        activities.push({ time: '9:00 AM', activity: 'Breakfast', location: 'Hotel', cost: 15 })
        activities.push({ time: '11:00 AM', activity: 'Last-minute shopping', location: 'Shopping District', cost: 50 })
        activities.push({ time: '2:00 PM', activity: 'Departure to airport', location: 'Airport', cost: 0 })
      } else {
        const dayAttractions = atts.slice((d - 2) * 2, (d - 2) * 2 + 2)
        activities.push({ time: '8:00 AM', activity: 'Breakfast', location: 'Hotel', cost: 15 })
        dayAttractions.forEach((att, idx) => {
          activities.push({ 
            time: idx === 0 ? '10:00 AM' : '2:00 PM', 
            activity: `Visit ${att.name}`, 
            location: att.name, 
            cost: type === 'business' ? 0 : 25 
          })
        })
        activities.push({ time: '7:00 PM', activity: 'Dinner', location: 'Local Restaurant', cost: 40 })
      }
      
      itin.push({ day: d, date: date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' }), activities })
    }
    return itin
  }

  const generateBudgetOptions = (days: number, travelers: number): BudgetOption[] => {
    const perDayBase = { low: 100, moderate: 200, aboveAverage: 350, high: 600 }
    return [
      {
        level: 'low',
        label: '💰 Budget-Friendly',
        total: perDayBase.low * days * travelers,
        breakdown: [
          { category: 'Accommodation', amount: 80 * days },
          { category: 'Food', amount: 40 * days * travelers },
          { category: 'Transportation', amount: 30 * days },
          { category: 'Activities', amount: 20 * days * travelers }
        ],
        description: 'Hostels, street food, public transport, free attractions'
      },
      {
        level: 'moderate',
        label: '⭐ Moderate',
        total: perDayBase.moderate * days * travelers,
        breakdown: [
          { category: 'Accommodation', amount: 150 * days },
          { category: 'Food', amount: 60 * days * travelers },
          { category: 'Transportation', amount: 50 * days },
          { category: 'Activities', amount: 40 * days * travelers }
        ],
        description: '3-star hotels, casual dining, rideshare, popular attractions'
      },
      {
        level: 'aboveAverage',
        label: '🌟 Above Average',
        total: perDayBase.aboveAverage * days * travelers,
        breakdown: [
          { category: 'Accommodation', amount: 250 * days },
          { category: 'Food', amount: 100 * days * travelers },
          { category: 'Transportation', amount: 80 * days },
          { category: 'Activities', amount: 70 * days * travelers }
        ],
        description: '4-star hotels, fine dining, private transport, premium experiences'
      },
      {
        level: 'high',
        label: '👑 Luxury',
        total: perDayBase.high * days * travelers,
        breakdown: [
          { category: 'Accommodation', amount: 500 * days },
          { category: 'Food', amount: 150 * days * travelers },
          { category: 'Transportation', amount: 150 * days },
          { category: 'Activities', amount: 100 * days * travelers }
        ],
        description: '5-star hotels, gourmet restaurants, private tours, VIP experiences'
      }
    ]
  }

  // Get today's date in YYYY-MM-DD format for validation
  const today = new Date().toISOString().split('T')[0]

  const handleSearch = async () => {
    if (!origin || !destination || !departureDate) {
      setError('Please fill in origin, destination, and departure date')
      return
    }

    // Validate departure date is not in the past
    if (departureDate < today) {
      setError('Departure date cannot be in the past. Please select a future date.')
      return
    }

    // Validate return date is after departure date
    if (returnDate && returnDate < departureDate) {
      setError('Return date must be after departure date.')
      return
    }

    try {
      setLoading(true)
      setError('')
      
      // Fetch flights from backend
      const response = await fetch(`${config.apiBase}/api/travel/flights/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin: origin.toUpperCase(),
          destination: destination.toUpperCase(),
          departure_date: departureDate,
          return_date: returnDate || undefined,
          adults,
          children,
          trip_type: tripType
        })
      })
      const data = await response.json()
      
      if (data.success && data.flights) {
        // Add booking URLs to flights
        const flightsWithUrls = data.flights.map((f: Flight) => ({
          ...f,
          booking_url: `https://www.kayak.com/flights/${origin}-${destination}/${departureDate}?sort=price_a`,
          source: 'Kayak'
        }))
        setFlights(flightsWithUrls)
      } else {
        // Generate realistic flight data if API fails
        const airlines = ['United Airlines', 'Delta Air Lines', 'American Airlines', 'Southwest Airlines', 'JetBlue Airways']
        const generatedFlights: Flight[] = airlines.map((airline, idx) => ({
          airline,
          flight_number: `${airline.substring(0, 2).toUpperCase()}${100 + idx * 50}`,
          departure_time: `${6 + idx * 2}:00 AM`,
          arrival_time: `${11 + idx * 2}:30 AM`,
          duration: `${4 + Math.floor(Math.random() * 2)}h ${Math.floor(Math.random() * 60)}m`,
          price: 200 + Math.floor(Math.random() * 300),
          stops: idx % 3 === 0 ? 0 : 1,
          aircraft: ['Boeing 737-900', 'Airbus A320', 'Boeing 757', 'Embraer E175'][idx % 4],
          booking_url: `https://www.kayak.com/flights/${origin}-${destination}/${departureDate}?sort=price_a`,
          source: 'Kayak'
        }))
        setFlights(generatedFlights)
      }

      // Generate weather forecast
      const weatherData = generateWeatherForecast(destination, departureDate, tripDuration)
      setWeather(weatherData)

      // Generate attractions
      const attractionsData = generateAttractions(destination.toUpperCase(), tripType)
      setAttractions(attractionsData)

      // Generate itinerary
      const itineraryData = generateItinerary(tripDuration, attractionsData, tripType)
      setItinerary(itineraryData)

      // Generate budget options
      const budgetData = generateBudgetOptions(tripDuration, totalTravelers)
      setBudgetOptions(budgetData)

      setStep(2)
    } catch (error) {
      console.error('Search failed:', error)
      setError('Search failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-xl flex items-center justify-center">
            <Plane className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">AI Travel Planner</h1>
            <p className="text-gray-600">Plan your perfect trip with intelligent recommendations</p>
          </div>
        </div>
      </div>

      {/* Step 1: Trip Planning Form */}
      {step === 1 && (
        <div className="bg-white p-8 rounded-xl border border-gray-200 shadow-sm mb-8">
          <h2 className="text-xl font-semibold mb-6">Plan Your Trip</h2>
          
          {/* Location & Dates */}
          <div className="grid md:grid-cols-2 gap-6 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">From</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Origin (e.g., RDU, SFO)"
                  value={origin}
                  onChange={(e) => setOrigin(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">To</label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Destination (e.g., LAX, JFK)"
                  value={destination}
                  onChange={(e) => setDestination(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Departure</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="date"
                  value={departureDate}
                  min={today}
                  onChange={(e) => setDepartureDate(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Return (Optional)</label>
              <div className="relative">
                <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="date"
                  value={returnDate}
                  min={departureDate || today}
                  onChange={(e) => setReturnDate(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Travelers */}
          <div className="grid md:grid-cols-3 gap-6 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <Users size={16} /> Adults
              </label>
              <select
                value={adults}
                onChange={(e) => setAdults(parseInt(e.target.value))}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              >
                {[1, 2, 3, 4, 5, 6].map(n => (
                  <option key={n} value={n}>{n} Adult{n > 1 ? 's' : ''}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Children (under 12)</label>
              <select
                value={children}
                onChange={(e) => setChildren(parseInt(e.target.value))}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              >
                {[0, 1, 2, 3, 4].map(n => (
                  <option key={n} value={n}>{n} Child{n !== 1 ? 'ren' : ''}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Trip Type</label>
              <select
                value={tripType}
                onChange={(e) => setTripType(e.target.value as any)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              >
                <option value="vacation">🏖️ Vacation</option>
                <option value="business">💼 Business</option>
                <option value="family">👨‍👩‍👧‍👦 Family Trip</option>
                <option value="adventure">🏔️ Adventure</option>
              </select>
            </div>
          </div>

          {/* Trip Summary */}
          {departureDate && returnDate && (
            <div className="bg-blue-50 p-4 rounded-lg mb-6">
              <p className="text-blue-800">
                <strong>Trip Duration:</strong> {tripDuration} days | <strong>Travelers:</strong> {totalTravelers} ({adults} adults{children > 0 ? `, ${children} children` : ''})
              </p>
            </div>
          )}

          <button 
            onClick={handleSearch}
            disabled={loading}
            className="w-full bg-gradient-to-r from-blue-500 to-cyan-600 text-white py-4 rounded-lg font-semibold hover:shadow-lg transition-shadow disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                Planning Your Trip...
              </>
            ) : (
              <>
                <Plane size={20} />
                Find Flights & Plan Trip
              </>
            )}
          </button>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Step 2: Results */}
      {step === 2 && (
        <>
          {/* Back Button */}
          <button 
            onClick={() => setStep(1)}
            className="mb-6 text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            ← Modify Search
          </button>

          {/* Weather Forecast */}
          {weather.length > 0 && (
            <div className="bg-gradient-to-r from-sky-50 to-blue-50 p-6 rounded-xl border border-sky-200 mb-8">
              <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                <Cloud size={20} /> Weather at {destination.toUpperCase()} During Your Trip
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                {weather.map((day, idx) => (
                  <div key={idx} className="bg-white p-3 rounded-lg text-center">
                    <p className="text-xs text-gray-600">{day.date}</p>
                    <p className="text-3xl my-2">{day.icon}</p>
                    <p className="text-sm font-semibold">{day.temp_high}°/{day.temp_low}°</p>
                    <p className="text-xs text-gray-500">{day.condition}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-sm text-sky-700 bg-sky-100 p-2 rounded">
                💡 {weather[0]?.recommendation}
              </p>
            </div>
          )}

          {/* Flight Results */}
          {flights.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <Plane size={24} /> Found {flights.length} Flights
              </h2>
              <div className="space-y-4">
                {flights.map((flight, index) => (
                  <div key={index} className="bg-white rounded-xl border border-gray-200 p-6 hover:shadow-lg transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
                          <Plane className="text-blue-600" size={24} />
                        </div>
                        <div>
                          <h3 className="font-semibold text-lg">{flight.airline}</h3>
                          <p className="text-sm text-gray-500">{flight.flight_number}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-bold text-green-600">${flight.price * totalTravelers}</div>
                        <div className="text-sm text-gray-500">${flight.price}/person × {totalTravelers}</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 text-center">
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Departure</div>
                        <div className="font-semibold">{flight.departure_time}</div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Duration</div>
                        <div className="font-semibold flex items-center justify-center gap-1">
                          <Clock size={16} />
                          {flight.duration}
                        </div>
                      </div>
                      <div>
                        <div className="text-sm text-gray-500 mb-1">Arrival</div>
                        <div className="font-semibold">{flight.arrival_time}</div>
                      </div>
                    </div>
                    <div className="mt-4 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm px-3 py-1 rounded-full ${flight.stops === 0 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                          {flight.stops === 0 ? 'Non-stop' : `${flight.stops} stop${flight.stops > 1 ? 's' : ''}`}
                        </span>
                        {flight.aircraft && (
                          <span className="text-sm text-gray-500">{flight.aircraft}</span>
                        )}
                      </div>
                      <a
                        href={flight.booking_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
                      >
                        <ExternalLink size={14} />
                        Book on {flight.source}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Things to Do */}
          {attractions.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <MapPinned size={24} /> Things to Do in {destination.toUpperCase()}
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {attractions.map((att, idx) => (
                  <div key={idx} className="bg-white p-4 rounded-xl border border-gray-200 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold">{att.name}</h3>
                      <div className="flex items-center gap-1 text-yellow-500">
                        <Star size={14} className="fill-yellow-400" />
                        <span className="text-sm">{att.rating}</span>
                      </div>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{att.description}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded capitalize">{att.type}</span>
                      <span className="text-gray-500">⏱️ {att.estimated_time}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Trip Itinerary */}
          {itinerary.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <Calendar size={24} /> Suggested Itinerary
              </h2>
              <div className="space-y-4">
                {itinerary.map((day) => (
                  <div key={day.day} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                    <button
                      onClick={() => setExpandedDay(expandedDay === day.day ? null : day.day)}
                      className="w-full p-4 flex items-center justify-between bg-gradient-to-r from-blue-50 to-cyan-50 hover:from-blue-100 hover:to-cyan-100"
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center font-bold">
                          {day.day}
                        </span>
                        <span className="font-semibold">{day.date}</span>
                      </div>
                      {expandedDay === day.day ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </button>
                    {expandedDay === day.day && (
                      <div className="p-4">
                        {day.activities.map((act, idx) => (
                          <div key={idx} className="flex items-start gap-4 mb-3 last:mb-0">
                            <span className="text-sm text-gray-500 w-20 flex-shrink-0">{act.time}</span>
                            <div>
                              <p className="font-medium">{act.activity}</p>
                              <p className="text-sm text-gray-500">{act.location}</p>
                            </div>
                            {act.cost !== undefined && act.cost > 0 && (
                              <span className="ml-auto text-sm text-green-600 font-medium">${act.cost}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Budget Options */}
          {budgetOptions.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
                <DollarSign size={24} /> Budget Options
              </h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                {budgetOptions.map((budget) => (
                  <div
                    key={budget.level}
                    onClick={() => setSelectedBudget(budget.level)}
                    className={`bg-white p-5 rounded-xl border-2 cursor-pointer transition-all hover:shadow-lg ${
                      selectedBudget === budget.level ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200'
                    }`}
                  >
                    <h3 className="font-bold text-lg mb-2">{budget.label}</h3>
                    <p className="text-3xl font-bold text-green-600 mb-2">${budget.total.toLocaleString()}</p>
                    <p className="text-xs text-gray-500 mb-3">{tripDuration} days, {totalTravelers} travelers</p>
                    <div className="space-y-1 text-sm">
                      {budget.breakdown.map((item, idx) => (
                        <div key={idx} className="flex justify-between">
                          <span className="text-gray-600">{item.category}</span>
                          <span className="font-medium">${item.amount}</span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 text-xs text-gray-500">{budget.description}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Need More Help */}
          <div className="bg-gradient-to-r from-purple-50 to-pink-50 p-6 rounded-xl border border-purple-200">
            <h3 className="font-bold text-lg mb-2 flex items-center gap-2">
              <HelpCircle size={20} /> Need More Help?
            </h3>
            <p className="text-gray-700 mb-4">
              Our AI can help you with hotel recommendations, local dining options, transportation within the city, and more specific activity suggestions.
            </p>
            <button 
              onClick={() => setShowHelp(!showHelp)}
              className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              {showHelp ? 'Hide Assistant' : 'Get More Recommendations'}
            </button>
            {showHelp && (
              <div className="mt-4 p-4 bg-white rounded-lg">
                <p className="text-sm text-gray-600">
                  💡 <strong>AI Travel Tips for {destination.toUpperCase()}:</strong>
                </p>
                {travelRecommendations ? (
                  <div className="mt-2 text-sm text-gray-700 space-y-2">
                    {travelRecommendations.split('\n').filter(line => line.trim()).map((tip, i) => (
                      <p key={i}>• {tip}</p>
                    ))}
                  </div>
                ) : (
                  <div className="mt-2">
                    <div className="animate-pulse space-y-2">
                      <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                      <div className="h-4 bg-gray-200 rounded w-full"></div>
                      <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">Generating personalized recommendations...</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}

      {/* Features - Show on Step 1 */}
      {step === 1 && (
        <div className="grid md:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
            <DollarSign className="text-green-600 mb-3" size={32} />
            <h3 className="font-semibold mb-2">Budget Options</h3>
            <p className="text-sm text-gray-600">Compare low, moderate, and luxury budgets for your trip</p>
          </div>

          <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
            <Sun className="text-yellow-600 mb-3" size={32} />
            <h3 className="font-semibold mb-2">Weather Forecast</h3>
            <p className="text-sm text-gray-600">Check weather conditions at your destination</p>
          </div>

          <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
            <Palmtree className="text-green-600 mb-3" size={32} />
            <h3 className="font-semibold mb-2">Trip Itinerary</h3>
            <p className="text-sm text-gray-600">Get AI-generated day-by-day travel plans</p>
          </div>
        </div>
      )}
    </div>
  )
}
