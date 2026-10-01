import { StyleSheet, Text, View, ScrollView, TouchableOpacity, TextInput, Modal, ActivityIndicator, Platform, Alert, Dimensions, Linking, Image } from "react-native";
import { SafeAreaView } from 'react-native-safe-area-context';
import { useState, useEffect, useCallback } from "react";
import Slider from '@react-native-community/slider';
import * as ImagePicker from 'expo-image-picker';
import DateTimePicker from '@react-native-community/datetimepicker';
import Constants from 'expo-constants';

type TabType = 'home' | 'assistant' | 'finance' | 'health' | 'school' | 'shopping' | 'travel' | 'nutrition' | 'calendar' | 'portfolio' | 'documents' | 'settings' | 'trading' | 'market_intel' | 'family' | 'maintenance' | 'money_hub' | 'life_hub' | 'profile_hub';

// 5-hub navigation: every feature reachable in ≤ 2 taps
const HUB_TABS: Record<string, TabType[]> = {
  money_hub: ['finance', 'portfolio', 'trading', 'market_intel', 'shopping', 'travel'],
  life_hub: ['health', 'family', 'school', 'nutrition', 'calendar', 'documents', 'maintenance'],
  profile_hub: ['settings'],
};
const tabToHub = (tab: TabType): TabType => {
  for (const [hub, tabs] of Object.entries(HUB_TABS)) {
    if (tabs.includes(tab)) return hub as TabType;
  }
  return tab;
};

// API Base URL - auto-detect for simulator vs physical device
const getApiBase = () => {
  // In dev, derive the host machine's IP from the Metro/Expo dev server URL.
  // Works for simulators, emulators, and physical devices on the same network.
  const hostUri = Constants.expoConfig?.hostUri;
  if (hostUri) {
    const host = hostUri.split(':')[0];
    if (host) return `http://${host}:30000`;
  }
  // Fallbacks when no dev server info is available (e.g. release builds)
  if (Platform.OS === 'ios') {
    return 'http://localhost:30000';
  }
  if (Platform.OS === 'android') {
    return 'http://10.0.2.2:30000';
  }
  return (Constants.expoConfig?.extra?.apiUrl as string) || 'http://localhost:30000';
};

const API_BASE = getApiBase();

// Fetch with timeout helper - increased timeout for AI operations
const fetchWithTimeout = async (url: string, options: RequestInit = {}, timeout = 30000): Promise<Response> => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    clearTimeout(id);
    return response;
  } catch (error) {
    clearTimeout(id);
    throw error;
  }
};

export default function Page() {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [showAllFeatures, setShowAllFeatures] = useState(false);
  const [chatMessage, setChatMessage] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState<{role: string, content: string}[]>([
    { role: 'assistant', content: 'Hello! I\'m Avira, your personal AI assistant. How can I help you today?' }
  ]);
  
  // Data states
  const [portfolioData, setPortfolioData] = useState<any>(null);
  const [calendarEvents, setCalendarEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Travel states
  const [travelFrom, setTravelFrom] = useState('');
  const [travelTo, setTravelTo] = useState('');
  const [travelDate, setTravelDate] = useState('');
  const [travelReturnDate, setTravelReturnDate] = useState('');
  const [flights, setFlights] = useState<any[]>([]);
  const [travelLoading, setTravelLoading] = useState(false);
  // Date picker states
  const [showDeparturePicker, setShowDeparturePicker] = useState(false);
  const [showReturnPicker, setShowReturnPicker] = useState(false);
  const [departureDate, setDepartureDate] = useState(new Date());
  const [returnDate, setReturnDate] = useState(new Date(Date.now() + 7 * 24 * 60 * 60 * 1000));
  
  // Shopping states
  const [shoppingQuery, setShoppingQuery] = useState('');
  const [shoppingResults, setShoppingResults] = useState<any[]>([]);
  const [shoppingAiRec, setShoppingAiRec] = useState<any>(null);
  const [shoppingCoupons, setShoppingCoupons] = useState<any[]>([]);
  const [groceryList, setGroceryList] = useState<{name: string, checked: boolean}[]>([
    { name: 'Milk', checked: false },
    { name: 'Eggs', checked: false },
    { name: 'Bread', checked: false },
    { name: 'Apples', checked: false },
    { name: 'Chicken', checked: false }
  ]);
  const [shoppingLoading, setShoppingLoading] = useState(false);
  const [newGroceryItem, setNewGroceryItem] = useState('');
  const [minPrice, setMinPrice] = useState(0);
  const [maxPrice, setMaxPrice] = useState(1000);
  
  // Weather states
  const [weather, setWeather] = useState<any>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  
  // Stock analysis states
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const [stockAnalysis, setStockAnalysis] = useState<any>(null);
  const [stockLoading, setStockLoading] = useState(false);
  
  // Calendar states
  const [newEventTitle, setNewEventTitle] = useState('');
  const [newEventDate, setNewEventDate] = useState('');
  const [showAddEvent, setShowAddEvent] = useState(false);
  
  // Nutrition states
  const [mealPlan, setMealPlan] = useState<string[]>([]);
  const [nutritionLoading, setNutritionLoading] = useState(false);
  
  // Authentication states
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  // Forgot/reset password flow
  const [forgotMode, setForgotMode] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetMessage, setResetMessage] = useState('');
  
  // Feature settings
  const [featureSettings, setFeatureSettings] = useState({
    show_investing: true,
    show_travel: true,
    show_shopping: true,
    show_weather: true,
    show_health: true,
    show_calendar: true,
    show_documents: true,
  });
  
  // Stock detail modal
  const [showStockModal, setShowStockModal] = useState(false);
  const [selectedStockData, setSelectedStockData] = useState<any>(null);
  const [stockChartData, setStockChartData] = useState<any[]>([]);
  
  // Stock management states
  const [showAddStockModal, setShowAddStockModal] = useState(false);
  const [showSellModal, setShowSellModal] = useState(false);
  const [newStockSymbol, setNewStockSymbol] = useState('');
  const [newStockShares, setNewStockShares] = useState('');
  const [newStockCost, setNewStockCost] = useState('');
  const [sellShares, setSellShares] = useState('');
  const [stockActionLoading, setStockActionLoading] = useState(false);
  
  // Document upload states
  const [documents, setDocuments] = useState<any[]>([]);
  const [documentLoading, setDocumentLoading] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState<any>(null);
  const [showDocumentResult, setShowDocumentResult] = useState(false);

  // Family profile states — each member's data lives under user_id 'member_<id>'
  const [familyProfiles, setFamilyProfiles] = useState<{id: string, name: string, userId: string, role: string, age?: number}[]>([]);
  const [activeProfile, setActiveProfile] = useState<{id: string, name: string, userId: string}>({ id: 'self', name: 'Myself', userId: 'default' });

  // Finance states (real data)
  const [financeSummary, setFinanceSummary] = useState<any>(null);
  const [financeHistory, setFinanceHistory] = useState<any[]>([]);
  const [recurringCharges, setRecurringCharges] = useState<any[]>([]);
  const [financeLoading, setFinanceLoading] = useState(false);

  // Health states (real data)
  const [healthSummaryData, setHealthSummaryData] = useState<any>(null);
  const [healthReports, setHealthReports] = useState<any[]>([]);
  const [healthLoading, setHealthLoading] = useState(false);

  // Family oversight states
  const [oversight, setOversight] = useState<any[]>([]);
  const [oversightError, setOversightError] = useState('');
  const [oversightLoading, setOversightLoading] = useState(false);
  const [newMemberName, setNewMemberName] = useState('');
  const [newMemberRole, setNewMemberRole] = useState('child');
  const [showAddMember, setShowAddMember] = useState(false);

  // Maintenance Hub states
  const [maintTab, setMaintTab] = useState<'checklist' | 'appliances' | 'repairs'>('checklist');
  const [maintCategory, setMaintCategory] = useState<'home' | 'vehicle'>('home');
  const [maintChecklist, setMaintChecklist] = useState<any[]>([]);
  const [maintProgress, setMaintProgress] = useState<any>(null);
  const [maintAppliances, setMaintAppliances] = useState<any[]>([]);
  const [maintRepairs, setMaintRepairs] = useState<any[]>([]);
  const [maintLoading, setMaintLoading] = useState(false);

  // Fetch data on tab change
  useEffect(() => {
    if (activeTab === 'portfolio') fetchPortfolio();
    if (activeTab === 'calendar') fetchCalendarEvents();
    if (activeTab === 'finance') fetchFinanceData();
    if (activeTab === 'health') fetchHealthData();
    if (activeTab === 'family') { fetchFamilyProfiles(); fetchOversight(); }
    if (activeTab === 'maintenance') fetchMaintenance();
  }, [activeTab]);

  // Reload finance/health when the active profile changes
  useEffect(() => {
    if (activeTab === 'finance') fetchFinanceData();
    if (activeTab === 'health') fetchHealthData();
  }, [activeProfile.userId]);

  // Load family profiles once logged in
  useEffect(() => {
    if (isLoggedIn && authToken) fetchFamilyProfiles();
  }, [isLoggedIn, authToken]);

  // Refetch checklist when home/vehicle category toggles
  useEffect(() => {
    if (activeTab === 'maintenance') fetchMaintenance();
  }, [maintCategory]);

  const fetchPortfolio = async () => {
    try {
      setLoading(true);
      const response = await fetchWithTimeout(`${API_BASE}/api/portfolio/holdings?user_id=default`);
      const data = await response.json();
      if (data.success) {
        // Calculate totals
        const holdings = data.holdings || [];
        const totalValue = holdings.reduce((sum: number, h: any) => sum + (h.current_value || 0), 0);
        const totalGain = holdings.reduce((sum: number, h: any) => sum + (h.gain_loss || 0), 0);
        setPortfolioData({
          ...data,
          total_value: totalValue,
          daily_change: totalGain,
          daily_change_percent: totalValue > 0 ? (totalGain / totalValue) * 100 : 0
        });
      }
    } catch (error) {
      console.error('Failed to fetch portfolio:', error);
      // Use demo data on error
      setPortfolioData({
        holdings: [
          { symbol: 'AAPL', name: 'Apple Inc.', current_value: 15420, change_percent: 1.2, current_price: 178.50 },
          { symbol: 'GOOGL', name: 'Alphabet', current_value: 12350, change_percent: 0.8, current_price: 140.50 },
          { symbol: 'MSFT', name: 'Microsoft', current_value: 10200, change_percent: 2.1, current_price: 380.00 }
        ],
        total_value: 37970,
        daily_change: 850,
        daily_change_percent: 2.2
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchCalendarEvents = async () => {
    try {
      setLoading(true);
      const response = await fetchWithTimeout(`${API_BASE}/api/calendar/upcoming?days=30`);
      const data = await response.json();
      if (data.events) setCalendarEvents(data.events);
    } catch (error) {
      console.error('Failed to fetch calendar:', error);
      // Use demo events
      setCalendarEvents([
        { title: 'Team Meeting', date: 'Today 2:00 PM', type: 'work' },
        { title: 'School Holiday', date: 'Feb 17', type: 'school' },
        { title: 'Doctor Appointment', date: 'Feb 20 10:00 AM', type: 'health' }
      ]);
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch weather for travel destination
  const fetchWeather = async (location: string) => {
    try {
      setWeatherLoading(true);
      const response = await fetchWithTimeout(`${API_BASE}/api/travel/weather?location=${encodeURIComponent(location)}&days=7`);
      const data = await response.json();
      if (data.success) {
        setWeather(data);
      }
    } catch (error) {
      console.error('Weather fetch error:', error);
    } finally {
      setWeatherLoading(false);
    }
  };
  
  // Fetch stock analysis
  const fetchStockAnalysis = async (symbol: string) => {
    try {
      setStockLoading(true);
      const response = await fetchWithTimeout(`${API_BASE}/api/portfolio/stocks/${symbol}/comprehensive`);
      const data = await response.json();
      if (data.success) {
        setStockAnalysis(data);
      }
    } catch (error) {
      console.error('Stock analysis error:', error);
    } finally {
      setStockLoading(false);
    }
  };

  // Maintenance Hub — checklist + appliances + repairs (deterministic backend)
  const fetchMaintenance = async () => {
    try {
      setMaintLoading(true);
      const headers: Record<string, string> = authToken ? { Authorization: `Bearer ${authToken}` } : {};
      const [cl, ap, rp] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/api/maintenance/checklist?category=${maintCategory}`, { headers }),
        fetchWithTimeout(`${API_BASE}/api/maintenance/appliances`, { headers }),
        fetchWithTimeout(`${API_BASE}/api/maintenance/repairs`, { headers }),
      ]);
      const [clData, apData, rpData] = await Promise.all([cl.json(), ap.json(), rp.json()]);
      if (clData.success) { setMaintChecklist(clData.items || []); setMaintProgress(clData.progress || null); }
      if (apData.success) setMaintAppliances(apData.appliances || apData.items || []);
      if (rpData.success) setMaintRepairs(rpData.repairs || rpData.items || []);
    } catch (error) {
      console.error('Maintenance fetch error:', error);
    } finally {
      setMaintLoading(false);
    }
  };

  const markMaintenanceDone = async (templateId: string) => {
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (authToken) headers.Authorization = `Bearer ${authToken}`;
      await fetchWithTimeout(`${API_BASE}/api/maintenance/checklist/${templateId}`, {
        method: 'POST', headers, body: JSON.stringify({ status: 'done' }),
      });
      fetchMaintenance();
    } catch (error) {
      console.error('Maintenance update error:', error);
    }
  };
  
  // Flight search states for Kayak-style UI
  const [flightFilters, setFlightFilters] = useState({ maxStops: 2, maxPrice: 1000, sortBy: 'best' });
  const [priceAnalysis, setPriceAnalysis] = useState<any>(null);
  const [flightRecommendations, setFlightRecommendations] = useState<any[]>([]);
  
  // Travel search - Kayak-style with filters
  const searchFlights = async () => {
    if (!travelFrom || !travelTo || !travelDate) {
      Alert.alert('Missing Info', 'Please enter origin, destination, and date');
      return;
    }
    
    // Validate date
    const selectedDate = new Date(travelDate);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (selectedDate < today) {
      Alert.alert('Invalid Date', 'Departure date cannot be in the past');
      return;
    }
    
    setTravelLoading(true);
    
    // Fetch weather for travel dates
    fetchWeatherForDates(travelTo, travelDate);
    
    try {
      // Use GET with query params for Kayak-style search
      const params = new URLSearchParams({
        origin: travelFrom.toUpperCase(),
        destination: travelTo.toUpperCase(),
        departure_date: travelDate,
        passengers: '1',
        cabin_class: 'economy',
        sort_by: flightFilters.sortBy,
      });
      if (travelReturnDate) params.append('return_date', travelReturnDate);
      if (flightFilters.maxStops < 2) params.append('max_stops', String(flightFilters.maxStops));
      if (flightFilters.maxPrice < 1000) params.append('max_price', String(flightFilters.maxPrice));
      
      const response = await fetchWithTimeout(`${API_BASE}/api/travel/flights/search?${params}`, {}, 20000);
      const data = await response.json();
      
      if (data.success && data.flights?.length > 0) {
        // Parse Kayak-style response
        setFlights(data.flights.map((f: any) => ({
          id: f.id,
          airline: f.airlines?.[0] || f.airline || 'Various Airlines',
          airlineCode: f.airline_codes?.[0] || '',
          price: f.price || 299,
          departure: formatFlightTime(f.departure_time),
          arrival: formatFlightTime(f.arrival_time),
          duration: formatDuration(f.total_duration_minutes),
          stops: f.stops === 0 ? 'Nonstop' : `${f.stops} stop${f.stops > 1 ? 's' : ''}`,
          stopsCount: f.stops || 0,
          layovers: f.layovers || [],
          booking_url: f.booking_url,
          baggage: f.baggage || '1 carry-on',
          amenities: f.amenities || [],
          score: f.score || 0,
          dealBadge: f.deal_badge,
        })));
        
        // Set price analysis and recommendations
        if (data.price_analysis) setPriceAnalysis(data.price_analysis);
        if (data.recommendations) setFlightRecommendations(data.recommendations);
      } else {
        showDemoFlights();
      }
    } catch (error) {
      console.error('Flight search error:', error);
      showDemoFlights();
    } finally {
      setTravelLoading(false);
    }
  };
  
  const showDemoFlights = () => {
    setFlights([
      { id: '1', airline: 'United Airlines', price: 287, departure: '8:00 AM', arrival: '4:30 PM', duration: '5h 30m', stops: 'Nonstop', stopsCount: 0, score: 8.5, dealBadge: 'Best Value' },
      { id: '2', airline: 'Delta Air Lines', price: 312, departure: '10:30 AM', arrival: '7:15 PM', duration: '5h 45m', stops: 'Nonstop', stopsCount: 0, score: 8.2 },
      { id: '3', airline: 'American Airlines', price: 245, departure: '2:00 PM', arrival: '10:45 PM', duration: '6h 45m', stops: '1 stop', stopsCount: 1, score: 7.8, dealBadge: 'Lowest Price' },
      { id: '4', airline: 'Southwest Airlines', price: 198, departure: '6:00 AM', arrival: '2:30 PM', duration: '5h 30m', stops: 'Nonstop', stopsCount: 0, score: 7.5, baggage: '2 free checked bags' },
    ]);
    setPriceAnalysis({ min: 198, max: 312, average: 260, recommendation: 'Good prices available' });
  };
  
  const formatFlightTime = (timeStr: string) => {
    if (!timeStr) return '';
    try {
      const date = new Date(timeStr);
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    } catch {
      return timeStr;
    }
  };
  
  const formatDuration = (minutes: number) => {
    if (!minutes) return '';
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };
  
  // Fetch weather for specific travel dates
  const fetchWeatherForDates = async (location: string, travelDate: string) => {
    try {
      setWeatherLoading(true);
      // Calculate days until travel
      const today = new Date();
      const travel = new Date(travelDate);
      const daysUntilTravel = Math.ceil((travel.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      const forecastDays = Math.min(16, Math.max(7, daysUntilTravel + 3)); // Get forecast covering travel dates
      
      const response = await fetchWithTimeout(`${API_BASE}/api/travel/weather?location=${encodeURIComponent(location)}&days=${forecastDays}`);
      const data = await response.json();
      
      if (data.success) {
        // Find weather for travel date
        const travelDateStr = travelDate;
        const travelForecast = data.forecast?.find((f: any) => f.date === travelDateStr);
        
        setWeather({
          ...data,
          travelDate: travelDateStr,
          travelForecast: travelForecast || data.forecast?.[daysUntilTravel] || null,
        });
      }
    } catch (error) {
      console.error('Weather fetch error:', error);
    } finally {
      setWeatherLoading(false);
    }
  };
  
  // Smart shopping search with AI recommendations
  const searchProducts = async () => {
    if (!shoppingQuery.trim()) return;
    setShoppingLoading(true);
    setShoppingAiRec(null);
    setShoppingCoupons([]);
    
    try {
      const url = `${API_BASE}/api/shopping/search?query=${encodeURIComponent(shoppingQuery)}&max_price=${maxPrice}`;
      const response = await fetchWithTimeout(url, {}, 20000);
      const data = await response.json();
      
      if (data.success && data.products?.length > 0) {
        setShoppingResults(data.products);
        setShoppingAiRec(data.ai_recommendation);
        setShoppingCoupons(data.coupons || []);
      } else {
        setShoppingResults([]);
        Alert.alert('No Results', 'No products found. Try a different search.');
      }
    } catch (error) {
      console.error('Shopping search error:', error);
      Alert.alert('Search Error', 'Could not search products. Please try again.');
      setShoppingResults([]);
    } finally {
      setShoppingLoading(false);
    }
  };
  
  // Toggle grocery item
  const toggleGroceryItem = (index: number) => {
    const updated = [...groceryList];
    updated[index].checked = !updated[index].checked;
    setGroceryList(updated);
  };
  
  // Add grocery item
  const addGroceryItem = () => {
    if (newGroceryItem.trim()) {
      setGroceryList([...groceryList, { name: newGroceryItem.trim(), checked: false }]);
      setNewGroceryItem('');
    }
  };
  
  // Add calendar event
  const addCalendarEvent = async () => {
    if (!newEventTitle || !newEventDate) {
      Alert.alert('Missing Info', 'Please provide event title and date');
      return;
    }
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/calendar/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newEventTitle,
          date: newEventDate,
          type: 'custom'
        })
      });
      if (response.ok) {
        Alert.alert('Success', 'Event added successfully');
        setNewEventTitle('');
        setNewEventDate('');
        setShowAddEvent(false);
        fetchCalendarEvents();
      }
    } catch (error) {
      console.error('Add event error:', error);
      // Add to local state on error
      setCalendarEvents([...calendarEvents, { title: newEventTitle, date: newEventDate, type: 'custom' }]);
      setNewEventTitle('');
      setNewEventDate('');
      setShowAddEvent(false);
      Alert.alert('Saved Locally', 'Event saved locally. Will sync when connected.');
    }
  };
  
  // Generate meal plan
  const generateMealPlan = async () => {
    setNutritionLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: 'Generate a healthy meal plan for today with breakfast, lunch, dinner and snacks. Keep it brief.',
          session_id: 'mobile_nutrition',
          user_id: 'mobile_user'
        })
      }, 20000);
      const data = await response.json();
      if (data.response) {
        const meals = data.response.split('\n').filter((m: string) => m.trim());
        setMealPlan(meals.slice(0, 6));
      }
    } catch (error) {
      console.error('Meal plan error:', error);
      setMealPlan([
        '🍳 Breakfast: Greek yogurt with granola and berries',
        '🥗 Lunch: Grilled chicken Caesar salad',
        '🍎 Snack: Apple slices with almond butter',
        '🍝 Dinner: Baked salmon with roasted vegetables'
      ]);
    } finally {
      setNutritionLoading(false);
    }
  };
  
  // Authentication functions
  const handleLogin = async () => {
    if (!loginUsername || !loginPassword) {
      Alert.alert('Missing Info', 'Please enter username and password');
      return;
    }
    setLoginLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      const data = await response.json();
      if (data.access_token) {
        setAuthToken(data.access_token);
        setCurrentUser({ username: data.username, role: data.role, user_id: data.user_id });
        setIsLoggedIn(true);
        setShowLoginModal(false);
        // Fetch user settings
        fetchUserSettings(data.user_id);
        Alert.alert('Welcome', `Logged in as ${data.username}`);
      } else {
        Alert.alert('Login Failed', data.detail || 'Invalid credentials');
      }
    } catch (error) {
      console.error('Login error:', error);
      Alert.alert('Connection Error', 'Could not connect to server');
    } finally {
      setLoginLoading(false);
    }
  };
  
  const handleLogout = () => {
    setIsLoggedIn(false);
    setAuthToken(null);
    setCurrentUser(null);
    Alert.alert('Logged Out', 'You have been logged out');
  };

  const handleForgotPassword = async () => {
    if (!loginUsername) {
      Alert.alert('Enter Username', 'Type your username or email first, then tap Forgot Password.');
      return;
    }
    setLoginLoading(true);
    setResetMessage('');
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username_or_email: loginUsername })
      });
      const data = await response.json();
      setResetSent(true);
      setResetMessage(data.message || 'If that account exists, a reset email was sent.');
    } catch (error) {
      setResetMessage('Could not reach server. Try again.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetToken || !newPassword) {
      Alert.alert('Missing Info', 'Enter the code from your email and a new password.');
      return;
    }
    setLoginLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken.trim(), new_password: newPassword })
      });
      const data = await response.json();
      if (data.success) {
        Alert.alert('Password Updated', 'You can now sign in with your new password.');
        setForgotMode(false);
        setResetSent(false);
        setResetToken('');
        setNewPassword('');
        setLoginPassword('');
      } else {
        Alert.alert('Reset Failed', data.detail || 'Invalid or expired code.');
      }
    } catch (error) {
      Alert.alert('Connection Error', 'Could not connect to server');
    } finally {
      setLoginLoading(false);
    }
  };
  
  const fetchUserSettings = async (userId: string) => {
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/settings/features/${userId}/sync`);
      const data = await response.json();
      if (data.success && data.features) {
        setFeatureSettings({
          show_investing: data.features.investing?.enabled ?? true,
          show_travel: data.features.travel?.enabled ?? true,
          show_shopping: data.features.shopping?.enabled ?? true,
          show_weather: data.features.weather?.enabled ?? true,
          show_health: data.features.health?.enabled ?? true,
          show_calendar: data.features.calendar?.enabled ?? true,
          show_documents: data.features.documents?.enabled ?? true,
        });
      }
    } catch (error) {
      console.error('Settings fetch error:', error);
    }
  };
  
  const toggleFeature = async (feature: string, enabled: boolean) => {
    const userId = currentUser?.user_id || 'default';
    setFeatureSettings(prev => ({ ...prev, [feature]: enabled }));
    try {
      await fetchWithTimeout(`${API_BASE}/api/settings/features/${userId}/toggle?feature=${feature}&enabled=${enabled}`, {
        method: 'POST'
      });
    } catch (error) {
      console.error('Toggle feature error:', error);
    }
  };
  
  // Stock detail modal - Robinhood style
  const openStockDetail = async (symbol: string) => {
    setSelectedStock(symbol);
    setShowStockModal(true);
    setStockLoading(true);
    
    try {
      // Fetch comprehensive stock data
      const [analysisRes, chartRes] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/api/portfolio/stocks/${symbol}/comprehensive`),
        fetchWithTimeout(`${API_BASE}/api/portfolio/stocks/${symbol}/chart?period=1M`)
      ]);
      
      const analysisData = await analysisRes.json();
      const chartData = await chartRes.json();
      
      if (analysisData.success) {
        setSelectedStockData(analysisData);
      }
      if (chartData.success && chartData.data) {
        setStockChartData(chartData.data);
      }
    } catch (error) {
      console.error('Stock detail error:', error);
      Alert.alert('Error', `Failed to load ${symbol} data. Please check your connection and try again.`);
      setShowStockModal(false);
    } finally {
      setStockLoading(false);
    }
  };
  
  // Stock management functions
  const addStock = async () => {
    if (!newStockSymbol.trim() || !newStockShares || !newStockCost) {
      Alert.alert('Missing Info', 'Please fill in all fields');
      return;
    }
    
    setStockActionLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/portfolio/holdings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default',
          symbol: newStockSymbol.toUpperCase(),
          shares: parseFloat(newStockShares),
          average_cost: parseFloat(newStockCost),
          purchase_date: new Date().toISOString().split('T')[0]
        })
      });
      const data = await response.json();
      if (data.success) {
        Alert.alert('Success', `Added ${newStockSymbol.toUpperCase()} to portfolio`);
        setShowAddStockModal(false);
        setNewStockSymbol('');
        setNewStockShares('');
        setNewStockCost('');
        fetchPortfolio();
      } else {
        Alert.alert('Error', data.message || 'Failed to add stock');
      }
    } catch (error) {
      console.error('Add stock error:', error);
      Alert.alert('Error', 'Failed to add stock');
    } finally {
      setStockActionLoading(false);
    }
  };
  
  const removeStock = async (symbol: string) => {
    Alert.alert(
      'Remove Stock',
      `Remove ${symbol} from your portfolio?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            setStockActionLoading(true);
            try {
              const response = await fetchWithTimeout(`${API_BASE}/api/portfolio/holdings/${symbol}?user_id=default`, {
                method: 'DELETE'
              });
              const data = await response.json();
              if (data.success) {
                Alert.alert('Removed', `${symbol} removed from portfolio`);
                fetchPortfolio();
              }
            } catch (error) {
              console.error('Remove stock error:', error);
              Alert.alert('Error', 'Failed to remove stock');
            } finally {
              setStockActionLoading(false);
            }
          }
        }
      ]
    );
  };
  
  const sellStock = async () => {
    if (!sellShares || !selectedStock) return;
    
    setStockActionLoading(true);
    try {
      const sellPrice = newStockCost ? parseFloat(newStockCost) : undefined;
      const response = await fetchWithTimeout(`${API_BASE}/api/portfolio/holdings/${selectedStock}/sell?user_id=default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          shares: parseFloat(sellShares),
          sell_price: sellPrice
        })
      });
      const data = await response.json();
      if (data.success) {
        const txn = data.transaction;
        Alert.alert(
          'Sale Complete',
          `Sold ${txn.shares_sold} shares of ${selectedStock}\n` +
          `Proceeds: $${txn.proceeds.toFixed(2)}\n` +
          `Realized ${txn.realized_gain >= 0 ? 'Gain' : 'Loss'}: $${Math.abs(txn.realized_gain).toFixed(2)}`
        );
        setShowSellModal(false);
        setSellShares('');
        setNewStockCost('');
        setShowStockModal(false);
        fetchPortfolio();
      } else {
        Alert.alert('Error', data.detail || 'Failed to sell stock');
      }
    } catch (error: any) {
      console.error('Sell stock error:', error);
      Alert.alert('Error', error.message || 'Failed to sell stock');
    } finally {
      setStockActionLoading(false);
    }
  };
  
  // Document upload functions
  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.8,
      base64: true,
    });
    
    if (!result.canceled && result.assets[0].base64) {
      uploadDocument(result.assets[0].base64, 'photo_upload.jpg');
    }
  };
  
  const takePhoto = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      Alert.alert('Permission Required', 'Camera permission is needed to take photos');
      return;
    }
    
    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: true,
      quality: 0.8,
      base64: true,
    });
    
    if (!result.canceled && result.assets[0].base64) {
      uploadDocument(result.assets[0].base64, 'camera_capture.jpg');
    }
  };
  
  const uploadDocument = async (base64Data: string, fileName: string) => {
    setDocumentLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/documents/upload-base64`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: base64Data,
          document_type: 'auto',
          file_name: fileName,
          user_id: currentUser?.user_id || 'default'
        })
      }, 60000);
      
      const data = await response.json();
      
      if (data.success) {
        setSelectedDocument(data);
        setShowDocumentResult(true);
        Alert.alert('Analysis Complete', `Document type: ${data.document_type}`);
        fetchDocuments();
      } else {
        Alert.alert('Analysis Failed', data.error || 'Could not analyze document');
      }
    } catch (error) {
      console.error('Document upload error:', error);
      Alert.alert('Upload Failed', 'Could not upload document. Please try again.');
    } finally {
      setDocumentLoading(false);
    }
  };
  
  const fetchDocuments = async () => {
    try {
      const userId = currentUser?.user_id || 'default';
      const response = await fetchWithTimeout(`${API_BASE}/api/documents/list?user_id=${userId}`);
      const data = await response.json();
      if (data.success) {
        setDocuments(data.documents || []);
      }
    } catch (error) {
      console.error('Fetch documents error:', error);
    }
  };

  // ── Family profiles & oversight ─────────────────────────────────────────
  const authHeaders = (): Record<string, string> => authToken ? { Authorization: `Bearer ${authToken}` } : {};

  const fetchFamilyProfiles = async () => {
    if (!authToken) return;
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/family-hub/members`, { headers: authHeaders() });
      const data = await response.json();
      const ms = (data.members || []).map((m: any) => ({
        id: m.id, name: m.name, userId: `member_${m.id}`, role: m.role, age: m.age,
      }));
      setFamilyProfiles(ms);
      // If the active profile was deleted, fall back to self
      if (activeProfile.id !== 'self' && !ms.some((m: any) => m.id === activeProfile.id)) {
        setActiveProfile({ id: 'self', name: 'Myself', userId: 'default' });
      }
    } catch (error) {
      console.error('Fetch family profiles error:', error);
    }
  };

  const fetchOversight = async () => {
    if (!authToken) { setOversightError('Sign in to view family oversight'); return; }
    setOversightLoading(true);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/family-hub/oversight`, { headers: authHeaders() });
      const data = await response.json();
      if (response.ok) {
        setOversight(data.members || []);
        setOversightError('');
      } else {
        setOversightError(data?.detail?.error || data?.error || 'Oversight requires the Enterprise plan');
      }
    } catch (error) {
      console.error('Oversight error:', error);
      setOversightError('Could not load family oversight');
    } finally {
      setOversightLoading(false);
    }
  };

  const addFamilyMember = async () => {
    if (!newMemberName.trim() || !authToken) return;
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/family-hub/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ name: newMemberName.trim(), role: newMemberRole }),
      });
      const data = await response.json();
      if (response.ok) {
        setNewMemberName('');
        setShowAddMember(false);
        fetchFamilyProfiles();
        fetchOversight();
      } else {
        Alert.alert('Error', data?.detail?.error || data?.detail || 'Failed to add member');
      }
    } catch (error) {
      Alert.alert('Error', 'Failed to add family member');
    }
  };

  const removeFamilyMember = async (id: string, name: string) => {
    Alert.alert('Remove Profile', `Remove ${name}? Their uploaded data stays stored under their profile.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove', style: 'destructive', onPress: async () => {
          try {
            await fetchWithTimeout(`${API_BASE}/api/family-hub/members/${id}`, {
              method: 'DELETE', headers: authHeaders(),
            });
            fetchFamilyProfiles();
            fetchOversight();
          } catch {
            Alert.alert('Error', 'Failed to remove member');
          }
        }
      }
    ]);
  };

  // ── Finance data (per active profile) ───────────────────────────────────
  const fetchFinanceData = async () => {
    setFinanceLoading(true);
    const uid = encodeURIComponent(activeProfile.userId);
    try {
      const [sumRes, histRes, recRes] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/api/finance/summary?user_id=${uid}`),
        fetchWithTimeout(`${API_BASE}/api/finance/history?user_id=${uid}`),
        fetchWithTimeout(`${API_BASE}/api/finance/recurring?user_id=${uid}`),
      ]);
      const [sum, hist, rec] = await Promise.all([sumRes.json(), histRes.json(), recRes.json()]);
      setFinanceSummary(sum);
      setFinanceHistory(hist.success ? (hist.history || []) : []);
      setRecurringCharges(rec.recurring || []);
    } catch (error) {
      console.error('Finance fetch error:', error);
    } finally {
      setFinanceLoading(false);
    }
  };

  // ── Health data (per active profile) ────────────────────────────────────
  const fetchHealthData = async () => {
    setHealthLoading(true);
    const uid = encodeURIComponent(activeProfile.userId);
    try {
      const [sumRes, tlRes] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/api/health/summary?user_id=${uid}`),
        fetchWithTimeout(`${API_BASE}/api/health/timeline?user_id=${uid}`),
      ]);
      const [sum, tl] = await Promise.all([sumRes.json(), tlRes.json()]);
      setHealthSummaryData(sum);
      setHealthReports(tl.success ? (tl.reports || []) : []);
    } catch (error) {
      console.error('Health fetch error:', error);
    } finally {
      setHealthLoading(false);
    }
  };

  // Profile chip selector shown on Finance/Health/Family tabs
  const renderProfileChips = () => (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.profileChips}>
      {[{ id: 'self', name: 'Myself', userId: 'default' }, ...familyProfiles].map(p => (
        <TouchableOpacity
          key={p.id}
          style={[styles.profileChip, activeProfile.id === p.id && styles.profileChipActive]}
          onPress={() => setActiveProfile({ id: p.id, name: p.name, userId: p.userId })}
        >
          <Text style={[styles.profileChipText, activeProfile.id === p.id && styles.profileChipTextActive]}>
            {p.id === 'self' ? '👤' : '👪'} {p.name}
          </Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );

  const QuickCard = ({ icon, title, value, subtitle, color, onPress }: any) => (
    <TouchableOpacity 
      style={[styles.quickCard, { borderLeftColor: color, borderLeftWidth: 4 }]}
      onPress={onPress}
    >
      <Text style={styles.cardIcon}>{icon}</Text>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardValue}>{value}</Text>
      <Text style={styles.cardSubtitle}>{subtitle}</Text>
    </TouchableOpacity>
  );

  const FeatureButton = ({ icon, title, tab, color }: { icon: string, title: string, tab: TabType, color: string }) => (
    <TouchableOpacity 
      style={[styles.featureButton, { backgroundColor: color + '15' }]}
      onPress={() => { setActiveTab(tab); setShowAllFeatures(false); }}
    >
      <Text style={styles.featureIcon}>{icon}</Text>
      <Text style={[styles.featureText, { color }]}>{title}</Text>
    </TouchableOpacity>
  );

  const sendMessage = async () => {
    if (!chatMessage.trim() || chatLoading) return;
    const userMsg = chatMessage;
    setChatHistory([...chatHistory, { role: 'user', content: userMsg }]);
    setChatMessage('');
    setChatLoading(true);
    
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg,
          session_id: `mobile_${Date.now()}`,
          user_id: 'mobile_user',
          use_external_llm: false
        })
      }, 30000);
      
      const data = await response.json();
      setChatHistory(prev => [...prev, { 
        role: 'assistant', 
        content: data.response || 'I apologize, I could not process your request.'
      }]);
    } catch (error) {
      console.error('Chat error:', error);
      setChatHistory(prev => [...prev, { 
        role: 'assistant', 
        content: 'I\'m currently offline but can help with basic queries. Try asking about weather, shopping deals, or general information!'
      }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Home Screen
  const renderHome = () => {
    const hour = new Date().getHours();
    const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
    const name = currentUser?.username || 'there';
    const finSpent = financeSummary?.total_spent;
    const healthAlerts = healthSummaryData?.alert_count ?? healthSummaryData?.alerts?.length ?? 0;
    return (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      {/* Header */}
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.greeting}>{greeting},</Text>
          <Text style={styles.title}>{name}</Text>
          <Text style={styles.tagline}>Your Personal Life Assistant</Text>
        </View>
        <View style={styles.connectionStatus}>
          <View style={styles.statusDot} />
          <Text style={styles.statusText}>{isLoggedIn ? 'Synced' : 'AI Ready'}</Text>
        </View>
      </View>

      {/* AI Assistant Card */}
      <TouchableOpacity style={styles.assistantCard} onPress={() => setActiveTab('assistant')}>
        <View style={styles.assistantIconContainer}>
          <Text style={styles.assistantIcon}>🤖</Text>
        </View>
        <View style={styles.assistantText}>
          <Text style={styles.assistantTitle}>AI Assistant</Text>
          <Text style={styles.assistantSubtitle}>
            Ask me anything - shopping, travel, health & more
          </Text>
        </View>
        <Text style={styles.chevron}>›</Text>
      </TouchableOpacity>

      {/* Quick Stats — real data */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Quick Overview</Text>
      </View>
      <View style={styles.quickCards}>
        <QuickCard icon="💰" title="Finance"
          value={finSpent != null ? `$${finSpent.toLocaleString(undefined, {maximumFractionDigits:0})}` : '—'}
          subtitle={finSpent != null ? `${financeSummary?.transaction_count ?? 0} transactions` : 'No data yet'}
          color="#10B981" onPress={() => setActiveTab('finance')} />
        <QuickCard icon="❤️" title="Health"
          value={healthReports.length > 0 ? `${healthReports.length} reports` : '—'}
          subtitle={healthAlerts > 0 ? `${healthAlerts} alerts` : 'No alerts'}
          color="#EF4444" onPress={() => setActiveTab('health')} />
        <QuickCard icon="👪" title="Family"
          value={familyProfiles.length > 0 ? `${familyProfiles.length}` : '—'}
          subtitle={familyProfiles.length > 0 ? 'profiles' : 'Add members'}
          color="#6366F1" onPress={() => setActiveTab('family')} />
        <QuickCard icon="📈" title="Portfolio" value="View" subtitle="Stocks & investing" color="#3B82F6" onPress={() => setActiveTab('portfolio')} />
      </View>

      {/* All Features */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>All Features</Text>
        <TouchableOpacity onPress={() => setShowAllFeatures(true)}>
          <Text style={styles.seeAll}>See All</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.featureGrid}>
        <FeatureButton icon="📈" title="Portfolio" tab="portfolio" color="#3B82F6" />
        <FeatureButton icon="🛒" title="Shopping" tab="shopping" color="#06B6D4" />
        <FeatureButton icon="✈️" title="Travel" tab="travel" color="#22C55E" />
        <FeatureButton icon="📅" title="Calendar" tab="calendar" color="#EF4444" />
      </View>
      <View style={styles.featureGrid}>
        <FeatureButton icon="🍎" title="Nutrition" tab="nutrition" color="#10B981" />
        <FeatureButton icon="🏫" title="School" tab="school" color="#6366F1" />
        <FeatureButton icon="👪" title="Family" tab="family" color="#8B5CF6" />
        <FeatureButton icon="📄" title="Documents" tab="documents" color="#64748B" />
      </View>

      {/* Privacy Notice */}
      <View style={styles.privacyNotice}>
        <Text style={styles.privacyIcon}>🔒</Text>
        <Text style={styles.privacyText}>
          Your data stays private. Local-first AI architecture.
        </Text>
      </View>
    </ScrollView>
    );
  };

  // AI Assistant Screen
  const renderAssistant = () => (
    <View style={styles.assistantScreen}>
      <View style={styles.chatHeader}>
        <TouchableOpacity onPress={() => setActiveTab('home')}>
          <Text style={styles.backButton}>‹ Back</Text>
        </TouchableOpacity>
        <Text style={styles.chatTitle}>AI Assistant</Text>
        <View style={{ width: 50 }} />
      </View>
      
      <ScrollView style={styles.chatMessages}>
        {chatHistory.map((msg, idx) => (
          <View key={idx} style={[styles.chatBubble, msg.role === 'user' ? styles.userBubble : styles.aiBubble]}>
            <Text style={[styles.chatText, msg.role === 'user' && styles.userText]}>{msg.content}</Text>
          </View>
        ))}
        {chatLoading && (
          <View style={[styles.chatBubble, styles.aiBubble]}>
            <ActivityIndicator size="small" color="#6366F1" />
          </View>
        )}
      </ScrollView>
      
      <View style={styles.chatInputContainer}>
        <TextInput
          style={styles.chatInput}
          placeholder="Ask me anything..."
          value={chatMessage}
          onChangeText={setChatMessage}
          onSubmitEditing={sendMessage}
          editable={!chatLoading}
        />
        <TouchableOpacity style={[styles.sendButton, chatLoading && { opacity: 0.5 }]} onPress={sendMessage} disabled={chatLoading}>
          <Text style={styles.sendIcon}>➤</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  // Feature Screen Template — back goes to the parent hub (≤2-tap nav)
  const renderFeatureScreen = (title: string, icon: string, color: string, content: React.ReactNode) => (
    <View style={styles.featureScreen}>
      <View style={[styles.featureHeader, { backgroundColor: color }]}>
        <TouchableOpacity onPress={() => setActiveTab(tabToHub(activeTab))}>
          <Text style={styles.backButtonWhite}>‹ Back</Text>
        </TouchableOpacity>
        <View style={styles.featureHeaderContent}>
          <Text style={styles.featureHeaderIcon}>{icon}</Text>
          <Text style={styles.featureHeaderTitle}>{title}</Text>
        </View>
        <View style={{ width: 50 }} />
      </View>
      <ScrollView style={styles.featureContent}>
        {content}
      </ScrollView>
    </View>
  );

  // Finance Screen — real data per active profile
  const renderFinance = () => renderFeatureScreen('Finance', '💰', '#10B981', (
    <View style={styles.screenPadding}>
      {renderProfileChips()}
      {financeLoading && <ActivityIndicator size="small" color="#10B981" style={{ marginVertical: 12 }} />}

      <View style={styles.statRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Total Spent</Text>
          <Text style={styles.statValue}>${(financeSummary?.total_spent ?? 0).toFixed(2)}</Text>
          <Text style={styles.statSubtext}>{financeSummary?.transaction_count ?? 0} transactions</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Statements</Text>
          <Text style={styles.statValue}>{financeHistory.length}</Text>
          <Text style={styles.statSubtext}>{activeProfile.name}</Text>
        </View>
      </View>

      {Object.keys(financeSummary?.top_categories || {}).length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>Top Categories</Text>
          {Object.entries(financeSummary.top_categories).slice(0, 5).map(([cat, amt]: any) => (
            <View key={cat} style={styles.listItem}>
              <Text style={styles.listItemText}>{cat}</Text>
              <Text style={styles.listItemDate}>${Number(amt).toFixed(2)}</Text>
            </View>
          ))}
        </>
      )}

      {recurringCharges.length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>🔄 Recurring Charges ({recurringCharges.length})</Text>
          {recurringCharges.slice(0, 10).map((r: any, i: number) => (
            <View key={i} style={styles.listItem}>
              <View style={{ flex: 1 }}>
                <Text style={styles.listItemText}>{r.merchant}</Text>
                <Text style={styles.statSubtext}>{r.count}x • ~${r.avg.toFixed(2)} each{r.likely_subscription ? ' • subscription' : ''}</Text>
              </View>
              <Text style={styles.listItemDate}>${r.total.toFixed(2)}</Text>
            </View>
          ))}
        </>
      )}

      {financeHistory.length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>Upload History</Text>
          {financeHistory.map((r: any, i: number) => (
            <View key={i} style={styles.listItem}>
              <View style={{ flex: 1 }}>
                <Text style={styles.listItemText}>{(r.uploaded_files || []).join(', ')}</Text>
                <Text style={styles.statSubtext}>{new Date(r.uploaded_at).toLocaleDateString()}</Text>
              </View>
              <Text style={styles.listItemDate}>${(r.summary?.total_spent ?? 0).toFixed(2)}</Text>
            </View>
          ))}
        </>
      )}

      {!financeLoading && !financeSummary?.transaction_count && (
        <View style={styles.tipCard}>
          <Text style={styles.tipIcon}>💡</Text>
          <Text style={styles.tipText}>No statements uploaded for {activeProfile.name} yet. Upload a CSV/PDF bank statement from the web app to see spending analysis here.</Text>
        </View>
      )}
    </View>
  ));

  // Health Screen — real data per active profile
  const renderHealth = () => renderFeatureScreen('Health', '❤️', '#EF4444', (
    <View style={styles.screenPadding}>
      {renderProfileChips()}
      {healthLoading && <ActivityIndicator size="small" color="#EF4444" style={{ marginVertical: 12 }} />}

      <View style={styles.statRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Reports</Text>
          <Text style={styles.statValue}>{healthReports.length}</Text>
          <Text style={styles.statSubtext}>{activeProfile.name}</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Alerts</Text>
          <Text style={[styles.statValue, { color: (healthSummaryData?.alert_count ?? 0) > 0 ? '#EF4444' : colors.text }]}>
            {healthSummaryData?.alert_count ?? healthSummaryData?.alerts?.length ?? 0}
          </Text>
          <Text style={styles.statSubtext}>{(healthSummaryData?.alert_count ?? 0) > 0 ? 'Needs attention' : 'All clear'}</Text>
        </View>
      </View>

      {healthSummaryData?.summary && (
        <>
          <Text style={styles.featureSectionTitle}>Health Summary</Text>
          <View style={styles.summaryCard}>
            <Text style={styles.summaryIcon}>👍</Text>
            <Text style={styles.summaryText}>{typeof healthSummaryData.summary === 'string' ? healthSummaryData.summary : JSON.stringify(healthSummaryData.summary)}</Text>
          </View>
        </>
      )}

      {healthReports.length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>Recent Reports</Text>
          {healthReports.slice(0, 10).map((r: any, i: number) => (
            <View key={i} style={styles.listItem}>
              <View style={{ flex: 1 }}>
                <Text style={styles.listItemText}>{r.filename || r.report_date || 'Health report'}</Text>
                <Text style={styles.statSubtext}>{r.lab_results?.length ?? 0} results{(r.alerts?.length ?? 0) > 0 ? ` • ${r.alerts.length} alerts` : ''}</Text>
              </View>
              <Text style={styles.listItemDate}>{(r.report_date || r.uploaded_at || '').slice(0, 10)}</Text>
            </View>
          ))}
        </>
      )}

      {!healthLoading && healthReports.length === 0 && (
        <View style={styles.summaryCard}>
          <Text style={styles.summaryIcon}>🏥</Text>
          <Text style={styles.summaryText}>No health records for {activeProfile.name} yet. Upload lab results from the web app to see them here.</Text>
        </View>
      )}
    </View>
  ));

  // Family Screen — profiles + head-of-family oversight (Enterprise)
  const renderFamily = () => renderFeatureScreen('Family', '👪', '#6366F1', (
    <View style={styles.screenPadding}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <Text style={styles.featureSectionTitle}>Family Profiles</Text>
        <TouchableOpacity onPress={() => setShowAddMember(v => !v)} style={styles.addMemberBtn}>
          <Text style={styles.addMemberBtnText}>+ Add</Text>
        </TouchableOpacity>
      </View>

      {showAddMember && (
        <View style={styles.addMemberCard}>
          <TextInput
            style={styles.loginInput}
            placeholder="Member name (e.g. Emma)"
            value={newMemberName}
            onChangeText={setNewMemberName}
          />
          <View style={{ flexDirection: 'row', marginBottom: 10 }}>
            {['child', 'partner', 'parent', 'other'].map(r => (
              <TouchableOpacity key={r} onPress={() => setNewMemberRole(r)}
                style={[styles.profileChip, newMemberRole === r && styles.profileChipActive, { marginRight: 8 }]}>
                <Text style={[styles.profileChipText, newMemberRole === r && styles.profileChipTextActive]}>{r}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TouchableOpacity style={styles.loginSubmit} onPress={addFamilyMember}>
            <Text style={styles.loginSubmitText}>Save Profile</Text>
          </TouchableOpacity>
        </View>
      )}

      {!isLoggedIn && (
        <View style={styles.tipCard}>
          <Text style={styles.tipIcon}>🔐</Text>
          <Text style={styles.tipText}>Sign in (Settings → Login) to manage family profiles and see oversight.</Text>
        </View>
      )}

      {oversightError ? (
        <View style={styles.tipCard}>
          <Text style={styles.tipIcon}>⚠️</Text>
          <Text style={styles.tipText}>{oversightError}</Text>
        </View>
      ) : null}

      {oversightLoading && <ActivityIndicator size="small" color="#6366F1" style={{ marginVertical: 12 }} />}

      {oversight.map((m: any) => (
        <View key={m.id} style={styles.memberCard}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <View>
              <Text style={styles.memberName}>{m.name}</Text>
              <Text style={styles.statSubtext}>{m.role}{m.age != null ? ` • age ${m.age}` : ''}</Text>
            </View>
            <TouchableOpacity onPress={() => removeFamilyMember(m.id, m.name)}>
              <Text style={{ color: colors.danger, fontSize: 13 }}>Remove</Text>
            </TouchableOpacity>
          </View>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <View style={[styles.memberStatBox, { backgroundColor: 'rgba(16,185,129,0.08)' }]}>
              <Text style={styles.memberStatTitle}>💰 Finance</Text>
              {m.finance?.reports > 0 ? (
                <>
                  <Text style={styles.memberStatValue}>${m.finance.total_spent.toFixed(2)}</Text>
                  <Text style={styles.statSubtext}>{m.finance.transaction_count} txns • {m.finance.reports} reports</Text>
                </>
              ) : (
                <Text style={styles.statSubtext}>No statements</Text>
              )}
            </View>
            <View style={[styles.memberStatBox, { backgroundColor: 'rgba(239,68,68,0.08)' }]}>
              <Text style={styles.memberStatTitle}>❤️ Health</Text>
              {m.health?.reports > 0 ? (
                <>
                  <Text style={styles.memberStatValue}>{m.health.reports} reports</Text>
                  <Text style={styles.statSubtext}>{m.health.abnormal_results} abnormal{m.health.alerts > 0 ? ` • ${m.health.alerts} alerts` : ''}</Text>
                </>
              ) : (
                <Text style={styles.statSubtext}>No records</Text>
              )}
            </View>
          </View>
          <TouchableOpacity
            style={{ marginTop: 10 }}
            onPress={() => { setActiveProfile({ id: m.id, name: m.name, userId: m.profile_user_id }); setActiveTab('finance'); }}
          >
            <Text style={{ color: colors.primary, fontSize: 13, fontWeight: '600' }}>View {m.name}'s finance →</Text>
          </TouchableOpacity>
        </View>
      ))}

      {isLoggedIn && !oversightError && oversight.length === 0 && !oversightLoading && (
        <Text style={{ color: colors.textMuted, fontSize: 14, marginTop: 8 }}>
          No family profiles yet — tap "+ Add" to create one. Each profile gets its own health &amp; finance directory.
        </Text>
      )}
    </View>
  ));

  // Shopping Screen with Price Slider
  const renderShopping = () => renderFeatureScreen('Shopping', '🛒', '#F59E0B', (
    <View style={styles.screenPadding}>
      <View style={styles.searchBar}>
        <Text style={styles.searchIcon}>🔍</Text>
        <TextInput 
          style={styles.searchInput} 
          placeholder="Search products..." 
          value={shoppingQuery}
          onChangeText={setShoppingQuery}
          onSubmitEditing={searchProducts}
        />
        <TouchableOpacity onPress={searchProducts} style={styles.searchButton}>
          <Text style={styles.searchButtonText}>Search</Text>
        </TouchableOpacity>
      </View>
      
      {/* Price Range Sliders */}
      <View style={styles.priceFilterCard}>
        <Text style={styles.priceFilterTitle}>💰 Price Range</Text>
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Min: ${minPrice}</Text>
          <Text style={styles.priceLabel}>Max: ${maxPrice}</Text>
        </View>
        <View style={styles.sliderContainer}>
          <Text style={styles.sliderLabel}>$0</Text>
          <Slider
            style={styles.slider}
            minimumValue={0}
            maximumValue={500}
            step={10}
            value={minPrice}
            onValueChange={setMinPrice}
            minimumTrackTintColor="#F59E0B"
            maximumTrackTintColor="#E5E7EB"
            thumbTintColor="#F59E0B"
          />
          <Text style={styles.sliderLabel}>$500</Text>
        </View>
        <View style={styles.sliderContainer}>
          <Text style={styles.sliderLabel}>$0</Text>
          <Slider
            style={styles.slider}
            minimumValue={0}
            maximumValue={1000}
            step={10}
            value={maxPrice}
            onValueChange={setMaxPrice}
            minimumTrackTintColor="#F59E0B"
            maximumTrackTintColor="#E5E7EB"
            thumbTintColor="#F59E0B"
          />
          <Text style={styles.sliderLabel}>$1000</Text>
        </View>
        <Text style={styles.priceRangeText}>Showing products ${minPrice} - ${maxPrice}</Text>
      </View>
      
      {shoppingLoading && <ActivityIndicator size="large" color="#F59E0B" style={{ marginVertical: 20 }} />}
      
      {/* AI Recommendation Card */}
      {shoppingAiRec && (
        <View style={styles.aiRecommendationCard}>
          <Text style={styles.aiRecTitle}>🤖 AI Recommendation</Text>
          <Text style={styles.aiRecBestRetailer}>
            Best Value: <Text style={styles.aiRecHighlight}>{shoppingAiRec.best_retailer}</Text> at ${shoppingAiRec.best_price?.toFixed(2)}
          </Text>
          <Text style={styles.aiRecText}>{shoppingAiRec.recommendation}</Text>
          {shoppingAiRec.action_items && (
            <View style={styles.aiRecActions}>
              {shoppingAiRec.action_items.map((action: string, i: number) => (
                <Text key={i} style={styles.aiRecAction}>✓ {action}</Text>
              ))}
            </View>
          )}
        </View>
      )}
      
      {shoppingResults.length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>🏪 Compare {shoppingResults.length} Retailers</Text>
          {shoppingResults.map((item, i) => (
            <View key={i} style={[styles.productCard, i === 0 && styles.bestDealCard]}>
              {i === 0 && <Text style={styles.bestDealBadge}>🏆 BEST VALUE</Text>}
              <View style={styles.productHeader}>
                <Text style={styles.productRetailer}>{item.retailer}</Text>
                {item.rating && (
                  <View style={styles.ratingBadge}>
                    <Text style={styles.ratingText}>⭐ {item.rating}</Text>
                  </View>
                )}
              </View>
              <View style={styles.priceRow}>
                <Text style={styles.productPrice}>${item.price?.toFixed(2)}</Text>
                {item.original_price && item.original_price > item.price && (
                  <Text style={styles.originalPrice}>${item.original_price?.toFixed(2)}</Text>
                )}
              </View>
              {item.savings > 0 && (
                <Text style={styles.savingsText}>💰 Save ${item.savings?.toFixed(2)} with coupons & cashback</Text>
              )}
              {item.cashback && item.cashback !== '0%' && (
                <Text style={styles.cashbackText}>💳 {item.cashback} cashback available</Text>
              )}
              <View style={styles.productMeta}>
                <Text style={styles.productShipping}>{item.shipping}</Text>
                {item.reviews > 0 && <Text style={styles.productReviews}>({item.reviews} reviews)</Text>}
              </View>
              {item.benefits && item.benefits.length > 0 && (
                <Text style={styles.benefitsText} numberOfLines={1}>
                  ✨ {item.benefits.slice(0, 2).join(' • ')}
                </Text>
              )}
              <TouchableOpacity style={styles.viewProductButton} onPress={() => item.url && Linking.openURL(item.url)}>
                <Text style={styles.viewProductText}>Shop at {item.retailer}</Text>
              </TouchableOpacity>
            </View>
          ))}
        </>
      )}
      
      <Text style={styles.featureSectionTitle}>Grocery List ({groceryList.filter(i => !i.checked).length} remaining)</Text>
      {groceryList.map((item, i) => (
        <TouchableOpacity key={i} style={styles.checklistItem} onPress={() => toggleGroceryItem(i)}>
          <View style={[styles.checkbox, item.checked && styles.checkboxChecked]}>
            {item.checked && <Text style={styles.checkmark}>✓</Text>}
          </View>
          <Text style={[styles.checklistText, item.checked && styles.checklistTextChecked]}>{item.name}</Text>
        </TouchableOpacity>
      ))}
      
      <View style={styles.addItemRow}>
        <TextInput 
          style={styles.addItemInput}
          placeholder="Add item..."
          value={newGroceryItem}
          onChangeText={setNewGroceryItem}
          onSubmitEditing={addGroceryItem}
        />
        <TouchableOpacity style={styles.addItemButton} onPress={addGroceryItem}>
          <Text style={styles.addItemButtonText}>+</Text>
        </TouchableOpacity>
      </View>
    </View>
  ));

  // Get weather icon based on code
  const getWeatherIcon = (code: number) => {
    if (code === 0) return '☀️';
    if (code <= 3) return '⛅';
    if (code <= 48) return '🌫️';
    if (code <= 55) return '🌧️';
    if (code <= 65) return '🌧️';
    if (code <= 77) return '❄️';
    if (code <= 82) return '🌧️';
    if (code >= 95) return '⛈️';
    return '☁️';
  };

  // Travel Screen - Kayak-style with filters and weather
  const renderTravel = () => renderFeatureScreen('Travel', '✈️', '#06B6D4', (
    <View style={styles.screenPadding}>
      {/* Search Form */}
      <View style={styles.tripPlanner}>
        <Text style={styles.tripPlannerTitle}>✈️ Search Flights</Text>
        <View style={styles.inputRow}>
          <TextInput 
            style={[styles.tripInput, { flex: 1, marginRight: 8 }]} 
            placeholder="From (JFK, LAX...)" 
            value={travelFrom}
            onChangeText={setTravelFrom}
            autoCapitalize="characters"
            maxLength={3}
          />
          <TextInput 
            style={[styles.tripInput, { flex: 1 }]} 
            placeholder="To (SFO, MIA...)" 
            value={travelTo}
            onChangeText={setTravelTo}
            autoCapitalize="characters"
            maxLength={3}
          />
        </View>
        <View style={styles.inputRow}>
          <TouchableOpacity 
            style={[styles.tripInput, styles.datePickerButton, { flex: 1, marginRight: 8 }]}
            onPress={() => setShowDeparturePicker(true)}
          >
            <Text style={travelDate ? styles.datePickerText : styles.datePickerPlaceholder}>
              {travelDate || '📅 Departure Date'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.tripInput, styles.datePickerButton, { flex: 1 }]}
            onPress={() => setShowReturnPicker(true)}
          >
            <Text style={travelReturnDate ? styles.datePickerText : styles.datePickerPlaceholder}>
              {travelReturnDate || '📅 Return (opt)'}
            </Text>
          </TouchableOpacity>
        </View>
        
        {/* Date Pickers */}
        {showDeparturePicker && (
          <DateTimePicker
            value={departureDate}
            mode="date"
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            minimumDate={new Date()}
            onChange={(event, date) => {
              setShowDeparturePicker(Platform.OS === 'ios');
              if (date) {
                setDepartureDate(date);
                setTravelDate(date.toISOString().split('T')[0]);
              }
            }}
          />
        )}
        {showReturnPicker && (
          <DateTimePicker
            value={returnDate}
            mode="date"
            display={Platform.OS === 'ios' ? 'spinner' : 'default'}
            minimumDate={departureDate}
            onChange={(event, date) => {
              setShowReturnPicker(Platform.OS === 'ios');
              if (date) {
                setReturnDate(date);
                setTravelReturnDate(date.toISOString().split('T')[0]);
              }
            }}
          />
        )}
        {Platform.OS === 'ios' && (showDeparturePicker || showReturnPicker) && (
          <TouchableOpacity 
            style={styles.datePickerDone}
            onPress={() => { setShowDeparturePicker(false); setShowReturnPicker(false); }}
          >
            <Text style={styles.datePickerDoneText}>Done</Text>
          </TouchableOpacity>
        )}
        
        {/* Filters */}
        <View style={styles.filtersRow}>
          <TouchableOpacity 
            style={[styles.filterChip, flightFilters.maxStops === 0 && styles.filterChipActive]}
            onPress={() => setFlightFilters({...flightFilters, maxStops: flightFilters.maxStops === 0 ? 2 : 0})}
          >
            <Text style={[styles.filterChipText, flightFilters.maxStops === 0 && styles.filterChipTextActive]}>Nonstop</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterChip, flightFilters.sortBy === 'price' && styles.filterChipActive]}
            onPress={() => setFlightFilters({...flightFilters, sortBy: flightFilters.sortBy === 'price' ? 'best' : 'price'})}
          >
            <Text style={[styles.filterChipText, flightFilters.sortBy === 'price' && styles.filterChipTextActive]}>Cheapest</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.filterChip, flightFilters.sortBy === 'duration' && styles.filterChipActive]}
            onPress={() => setFlightFilters({...flightFilters, sortBy: flightFilters.sortBy === 'duration' ? 'best' : 'duration'})}
          >
            <Text style={[styles.filterChipText, flightFilters.sortBy === 'duration' && styles.filterChipTextActive]}>Fastest</Text>
          </TouchableOpacity>
        </View>
        
        <TouchableOpacity style={styles.searchTripButton} onPress={searchFlights} disabled={travelLoading}>
          {travelLoading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.searchTripText}>🔍 Search Flights</Text>
          )}
        </TouchableOpacity>
      </View>
      
      {/* Price Analysis */}
      {priceAnalysis && (
        <View style={styles.priceAnalysisCard}>
          <Text style={styles.priceAnalysisTitle}>💰 Price Analysis</Text>
          <View style={styles.priceAnalysisRow}>
            <View style={styles.priceAnalysisItem}>
              <Text style={styles.priceAnalysisLabel}>Lowest</Text>
              <Text style={styles.priceAnalysisValue}>${priceAnalysis.min}</Text>
            </View>
            <View style={styles.priceAnalysisItem}>
              <Text style={styles.priceAnalysisLabel}>Average</Text>
              <Text style={styles.priceAnalysisValue}>${priceAnalysis.average}</Text>
            </View>
            <View style={styles.priceAnalysisItem}>
              <Text style={styles.priceAnalysisLabel}>Highest</Text>
              <Text style={styles.priceAnalysisValue}>${priceAnalysis.max}</Text>
            </View>
          </View>
          <Text style={styles.priceRecommendation}>💡 {priceAnalysis.recommendation}</Text>
        </View>
      )}
      
      {/* Weather for Travel Date */}
      {weather && weather.success && (
        <View style={styles.weatherCard}>
          <Text style={styles.weatherTitle}>🌤️ Weather at {weather.location}</Text>
          {weather.travelForecast ? (
            <View style={styles.travelWeather}>
              <Text style={styles.travelWeatherDate}>On your travel date ({weather.travelDate}):</Text>
              <View style={styles.weatherCurrent}>
                <Text style={styles.weatherIcon}>{getWeatherIcon(weather.travelForecast.weather_code)}</Text>
                <View>
                  <Text style={styles.weatherTemp}>{Math.round(weather.travelForecast.temp_max_f)}°F</Text>
                  <Text style={styles.weatherCondition}>{weather.travelForecast.condition}</Text>
                </View>
              </View>
            </View>
          ) : (
            <View style={styles.weatherCurrent}>
              <Text style={styles.weatherIcon}>{getWeatherIcon(weather.current?.weather_code || 0)}</Text>
              <View>
                <Text style={styles.weatherTemp}>{Math.round(weather.current?.temperature_f || 0)}°F</Text>
                <Text style={styles.weatherCondition}>{weather.current?.condition}</Text>
              </View>
            </View>
          )}
          {weather.forecast && weather.forecast.length > 0 && (
            <View style={styles.weatherForecast}>
              {weather.forecast.slice(0, 7).map((day: any, i: number) => (
                <View key={i} style={[styles.forecastDay, day.date === weather.travelDate && styles.forecastDayHighlight]}>
                  <Text style={styles.forecastDayName}>{new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' })}</Text>
                  <Text style={styles.forecastIcon}>{getWeatherIcon(day.weather_code)}</Text>
                  <Text style={styles.forecastTemp}>{Math.round(day.temp_max_f)}°</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      )}
      {weatherLoading && <ActivityIndicator size="small" color="#06B6D4" style={{ marginVertical: 12 }} />}
      
      {/* Flight Results */}
      {flights.length > 0 && (
        <>
          <Text style={styles.featureSectionTitle}>✈️ {flights.length} Flights Found</Text>
          {flights.map((flight: any, i: number) => (
            <View key={flight.id || i} style={[styles.flightCard, flight.dealBadge && styles.flightCardBestDeal]}>
              {flight.dealBadge && (
                <View style={styles.dealBadge}>
                  <Text style={styles.dealBadgeText}>⭐ {flight.dealBadge}</Text>
                </View>
              )}
              <View style={styles.flightHeader}>
                <View>
                  <Text style={styles.flightAirline}>{flight.airline}</Text>
                  {flight.baggage && <Text style={styles.flightBaggage}>🧳 {flight.baggage}</Text>}
                </View>
                <View style={styles.flightPriceContainer}>
                  <Text style={styles.flightPrice}>${flight.price}</Text>
                  {flight.score > 0 && <Text style={styles.flightScore}>Score: {flight.score.toFixed(1)}</Text>}
                </View>
              </View>
              <View style={styles.flightTimes}>
                <Text style={styles.flightTime}>{flight.departure} → {flight.arrival}</Text>
                <Text style={styles.flightDuration}>{flight.duration}</Text>
              </View>
              <View style={styles.flightDetails}>
                <Text style={[styles.flightStops, flight.stopsCount === 0 && styles.flightStopsNonstop]}>{flight.stops}</Text>
                {flight.layovers?.length > 0 && (
                  <Text style={styles.flightLayover}>via {flight.layovers[0].airport}</Text>
                )}
              </View>
              <TouchableOpacity style={styles.bookButton}>
                <Text style={styles.bookButtonText}>View Deal →</Text>
              </TouchableOpacity>
            </View>
          ))}
        </>
      )}
    </View>
  ));

  // School Screen
  const renderSchool = () => renderFeatureScreen('School', '🏫', '#6366F1', (
    <View style={styles.screenPadding}>
      <View style={styles.statRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Courses</Text>
          <Text style={styles.statValue}>4</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Pending</Text>
          <Text style={[styles.statValue, { color: '#F59E0B' }]}>3</Text>
        </View>
      </View>
      <Text style={styles.featureSectionTitle}>Upcoming Assignments</Text>
      {[
        { title: 'Math Quiz Ch. 5', course: 'Mathematics', due: 'Feb 10' },
        { title: 'Science Lab Report', course: 'Science', due: 'Feb 12' },
        { title: 'Essay Draft', course: 'English', due: 'Feb 14' }
      ].map((item, i) => (
        <View key={i} style={styles.assignmentCard}>
          <View style={styles.assignmentInfo}>
            <Text style={styles.assignmentTitle}>{item.title}</Text>
            <Text style={styles.assignmentCourse}>{item.course}</Text>
          </View>
          <Text style={styles.assignmentDue}>Due {item.due}</Text>
        </View>
      ))}
    </View>
  ));

  // Nutrition Screen
  const renderNutrition = () => renderFeatureScreen('Nutrition', '🍎', '#22C55E', (
    <View style={styles.screenPadding}>
      <View style={styles.statRow}>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Daily Protein</Text>
          <Text style={styles.statValue}>85g</Text>
          <Text style={styles.statSubtext}>of 120g goal</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statLabel}>Calories</Text>
          <Text style={styles.statValue}>1,850</Text>
          <Text style={styles.statSubtext}>of 2,200 goal</Text>
        </View>
      </View>
      <Text style={styles.featureSectionTitle}>Today's Meals</Text>
      {(mealPlan.length > 0 ? mealPlan : ['Breakfast: Oatmeal with berries', 'Lunch: Grilled chicken salad', 'Snack: Greek yogurt']).map((meal, i) => (
        <View key={i} style={styles.mealItem}>
          <Text style={styles.mealText}>{meal}</Text>
        </View>
      ))}
      <TouchableOpacity style={styles.generateMealButton} onPress={generateMealPlan} disabled={nutritionLoading}>
        {nutritionLoading ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : (
          <Text style={styles.generateMealText}>Generate AI Meal Plan</Text>
        )}
      </TouchableOpacity>
    </View>
  ));

  // Calendar Screen
  const renderCalendar = () => renderFeatureScreen('Calendar', '📅', '#8B5CF6', (
    <View style={styles.screenPadding}>
      <Text style={styles.featureSectionTitle}>Upcoming Events</Text>
      {loading ? (
        <ActivityIndicator size="large" color="#8B5CF6" style={{ marginTop: 20 }} />
      ) : calendarEvents.length > 0 ? (
        calendarEvents.map((event, i) => (
          <View key={i} style={[styles.eventCard, { borderLeftColor: event.type === 'work' ? '#3B82F6' : event.type === 'school' ? '#6366F1' : '#EF4444' }]}>
            <Text style={styles.eventTitle}>{event.title}</Text>
            <Text style={styles.eventDate}>{event.date} {event.time || ''}</Text>
          </View>
        ))
      ) : (
        [
          { title: 'Team Meeting', date: 'Today 2:00 PM', type: 'work' },
          { title: 'School Holiday', date: 'Feb 17', type: 'school' },
          { title: 'Doctor Appointment', date: 'Feb 20 10:00 AM', type: 'health' }
        ].map((event, i) => (
          <View key={i} style={[styles.eventCard, { borderLeftColor: event.type === 'work' ? '#3B82F6' : event.type === 'school' ? '#6366F1' : '#EF4444' }]}>
            <Text style={styles.eventTitle}>{event.title}</Text>
            <Text style={styles.eventDate}>{event.date}</Text>
          </View>
        ))
      )}
      
      {showAddEvent ? (
        <View style={styles.addEventForm}>
          <TextInput
            style={styles.eventInput}
            placeholder="Event title"
            value={newEventTitle}
            onChangeText={setNewEventTitle}
          />
          <TextInput
            style={styles.eventInput}
            placeholder="Date (YYYY-MM-DD)"
            value={newEventDate}
            onChangeText={setNewEventDate}
          />
          <View style={styles.eventFormButtons}>
            <TouchableOpacity style={styles.cancelButton} onPress={() => setShowAddEvent(false)}>
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.saveButton} onPress={addCalendarEvent}>
              <Text style={styles.saveButtonText}>Save</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <TouchableOpacity style={styles.addEventButton} onPress={() => setShowAddEvent(true)}>
          <Text style={styles.addEventText}>+ Add Event</Text>
        </TouchableOpacity>
      )}
    </View>
  ));

  // Portfolio Screen - with clickable stocks (Robinhood-style) + stock management
  const renderPortfolio = () => renderFeatureScreen('Portfolio', '📈', '#3B82F6', (
    <View style={styles.screenPadding}>
      {loading ? (
        <ActivityIndicator size="large" color="#3B82F6" style={{ marginTop: 20 }} />
      ) : (
        <>
          {/* Premium Portfolio Summary */}
          <View style={styles.premiumPortfolioSummary}>
            <View style={styles.premiumBadge}>
              <Text style={styles.premiumBadgeText}>⭐ PREMIUM</Text>
            </View>
            <Text style={styles.portfolioLabel}>Total Portfolio Value</Text>
            <Text style={styles.portfolioValue}>
              ${portfolioData?.total_value?.toLocaleString() || '45,230.50'}
            </Text>
            <Text style={[styles.portfolioChange, { color: (portfolioData?.daily_change || 0) >= 0 ? '#10B981' : '#EF4444' }]}>
              {portfolioData?.daily_change >= 0 ? '▲' : '▼'} $
              {Math.abs(portfolioData?.daily_change || 1085.20).toLocaleString()} 
              ({Math.abs(portfolioData?.daily_change_percent || 2.4).toFixed(2)}%) today
            </Text>
          </View>
          
          {/* Action Buttons */}
          <View style={styles.portfolioActions}>
            <TouchableOpacity style={styles.addStockButton} onPress={() => setShowAddStockModal(true)}>
              <Text style={styles.addStockButtonText}>+ Add Stock</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.refreshButton} onPress={fetchPortfolio}>
              <Text style={styles.refreshButtonText}>⟳ Refresh</Text>
            </TouchableOpacity>
          </View>
          
          <Text style={styles.featureSectionTitle}>📊 Holdings (Tap for AI Analysis)</Text>
          {(portfolioData?.holdings || [
            { symbol: 'AAPL', name: 'Apple Inc.', current_value: 15420, change_percent: 1.2, shares: 10 },
            { symbol: 'GOOGL', name: 'Alphabet', current_value: 12350, change_percent: 0.8, shares: 5 },
            { symbol: 'MSFT', name: 'Microsoft', current_value: 10200, change_percent: 2.1, shares: 8 },
          ]).map((stock: any, i: number) => (
            <View key={i} style={styles.enhancedStockCard}>
              <TouchableOpacity style={styles.stockCardMain} onPress={() => openStockDetail(stock.symbol)}>
                <View style={styles.stockLeft}>
                  <Text style={styles.stockSymbol}>{stock.symbol}</Text>
                  <Text style={styles.stockName}>{stock.name || `${stock.symbol} Inc.`}</Text>
                  <Text style={styles.stockShares}>{stock.shares || 0} shares</Text>
                </View>
                <View style={styles.stockRight}>
                  <Text style={styles.stockValue}>${(stock.current_value || stock.value || 0).toLocaleString()}</Text>
                  <Text style={[styles.stockChange, { color: (stock.change_percent || 0) >= 0 ? '#10B981' : '#EF4444' }]}>
                    {(stock.change_percent || 0) >= 0 ? '+' : ''}{(stock.change_percent || 0).toFixed(2)}%
                  </Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity style={styles.removeStockBtn} onPress={() => removeStock(stock.symbol)}>
                <Text style={styles.removeStockText}>✕</Text>
              </TouchableOpacity>
            </View>
          ))}
          
          {(portfolioData?.holdings?.length === 0) && (
            <View style={styles.emptyPortfolio}>
              <Text style={styles.emptyPortfolioIcon}>📈</Text>
              <Text style={styles.emptyPortfolioText}>No stocks in portfolio</Text>
              <Text style={styles.emptyPortfolioSubtext}>Tap "+ Add Stock" to get started</Text>
            </View>
          )}
        </>
      )}
    </View>
  ));
  
  // Documents Screen - Upload and analyze health/finance documents
  const renderDocuments = () => renderFeatureScreen('Documents', '📄', '#8B5CF6', (
    <View style={styles.screenPadding}>
      <Text style={styles.featureSectionTitle}>📸 Upload Document</Text>
      <Text style={styles.cardSubtitle}>Analyze health reports, bank statements, receipts</Text>
      
      <View style={styles.uploadButtons}>
        <TouchableOpacity style={styles.uploadButton} onPress={takePhoto} disabled={documentLoading}>
          <Text style={styles.uploadButtonIcon}>📷</Text>
          <Text style={styles.uploadButtonText}>Take Photo</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.uploadButton} onPress={pickImage} disabled={documentLoading}>
          <Text style={styles.uploadButtonIcon}>🖼️</Text>
          <Text style={styles.uploadButtonText}>From Gallery</Text>
        </TouchableOpacity>
      </View>
      
      {documentLoading && (
        <View style={styles.loadingCard}>
          <ActivityIndicator size="large" color="#8B5CF6" />
          <Text style={styles.loadingText}>Analyzing document...</Text>
        </View>
      )}
      
      <Text style={styles.featureSectionTitle}>📋 Recent Documents</Text>
      {documents.length > 0 ? (
        documents.map((doc, i) => (
          <View key={i} style={styles.documentCard}>
            <View style={styles.documentIcon}>
              <Text>{doc.document_type === 'health' ? '🏥' : doc.document_type === 'finance' ? '🏦' : '📄'}</Text>
            </View>
            <View style={styles.documentInfo}>
              <Text style={styles.documentName}>{doc.file_name}</Text>
              <Text style={styles.documentType}>{doc.document_type} • {doc.upload_date}</Text>
              {doc.summary && <Text style={styles.documentSummary} numberOfLines={2}>{doc.summary}</Text>}
            </View>
          </View>
        ))
      ) : (
        <Text style={styles.emptyText}>No documents uploaded yet</Text>
      )}
    </View>
  ));
  
  // Settings Screen - Feature toggles
  const renderSettings = () => renderFeatureScreen('Settings', '⚙️', '#64748B', (
    <View style={styles.screenPadding}>
      {/* Login Section */}
      <View style={styles.settingsSection}>
        <Text style={styles.featureSectionTitle}>👤 Account</Text>
        {isLoggedIn ? (
          <View style={styles.accountCard}>
            <Text style={styles.accountName}>{currentUser?.username}</Text>
            <Text style={styles.accountRole}>{currentUser?.role}</Text>
            <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
              <Text style={styles.logoutButtonText}>Logout</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity style={styles.loginButton} onPress={() => setShowLoginModal(true)}>
            <Text style={styles.loginButtonText}>🔐 Login</Text>
          </TouchableOpacity>
        )}
      </View>
      
      {/* Feature Toggles */}
      <View style={styles.settingsSection}>
        <Text style={styles.featureSectionTitle}>📱 Features</Text>
        <Text style={styles.settingsSubtext}>Toggle features on/off</Text>
        
        {[
          { key: 'show_investing', label: 'Investing', icon: '📈' },
          { key: 'show_travel', label: 'Travel', icon: '✈️' },
          { key: 'show_shopping', label: 'Shopping', icon: '🛒' },
          { key: 'show_health', label: 'Health', icon: '❤️' },
          { key: 'show_calendar', label: 'Calendar', icon: '📅' },
          { key: 'show_documents', label: 'Documents', icon: '📄' },
        ].map(({ key, label, icon }) => (
          <TouchableOpacity 
            key={key} 
            style={styles.toggleRow}
            onPress={() => toggleFeature(key, !featureSettings[key as keyof typeof featureSettings])}
          >
            <Text style={styles.toggleLabel}>{icon} {label}</Text>
            <View style={[styles.toggleSwitch, featureSettings[key as keyof typeof featureSettings] && styles.toggleSwitchActive]}>
              <View style={[styles.toggleKnob, featureSettings[key as keyof typeof featureSettings] && styles.toggleKnobActive]} />
            </View>
          </TouchableOpacity>
        ))}
      </View>
      
      <View style={styles.settingsSection}>
        <Text style={styles.featureSectionTitle}>ℹ️ About</Text>
        <Text style={styles.aboutText}>Avira Personal Life Assistant</Text>
        <Text style={styles.aboutVersion}>Version 1.0.0 • Enterprise Edition</Text>
      </View>
    </View>
  ));

  // All Features Modal
  const renderFeaturesModal = () => (
    <Modal visible={showAllFeatures} animationType="slide" transparent>
      <View style={styles.modalOverlay}>
        <View style={styles.modalContent}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>All Features</Text>
            <TouchableOpacity onPress={() => setShowAllFeatures(false)}>
              <Text style={styles.modalClose}>✕</Text>
            </TouchableOpacity>
          </View>
          <ScrollView style={styles.modalScroll}>
            <View style={styles.modalGrid}>
              <FeatureButton icon="🛒" title="Shopping" tab="shopping" color="#F59E0B" />
              <FeatureButton icon="✈️" title="Travel" tab="travel" color="#06B6D4" />
              <FeatureButton icon="🍎" title="Nutrition" tab="nutrition" color="#22C55E" />
              <FeatureButton icon="🏫" title="School" tab="school" color="#6366F1" />
              <FeatureButton icon="💰" title="Finance" tab="finance" color="#10B981" />
              <FeatureButton icon="❤️" title="Health" tab="health" color="#EF4444" />
              <FeatureButton icon="📅" title="Calendar" tab="calendar" color="#8B5CF6" />
              <FeatureButton icon="📈" title="Portfolio" tab="portfolio" color="#3B82F6" />
              <FeatureButton icon="📄" title="Documents" tab="documents" color="#8B5CF6" />
              <FeatureButton icon="👪" title="Family" tab="family" color="#6366F1" />
              <FeatureButton icon="⚙️" title="Settings" tab="settings" color="#64748B" />
              {/* Day Trader & Market Intel consolidated into Portfolio */}
            </View>
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
  
  // Login Modal
  const renderLoginModal = () => (
    <Modal visible={showLoginModal} animationType="fade" transparent>
      <View style={styles.loginModal}>
        <View style={styles.loginCard}>
          {!forgotMode ? (
            <>
              <Text style={styles.loginTitle}>🔐 Login</Text>
              <Text style={styles.loginSubtitle}>Sign in to sync your data</Text>

              <TextInput
                style={styles.loginInput}
                placeholder="Username"
                value={loginUsername}
                onChangeText={setLoginUsername}
                autoCapitalize="none"
              />
              <TextInput
                style={styles.loginInput}
                placeholder="Password"
                value={loginPassword}
                onChangeText={setLoginPassword}
                secureTextEntry
              />

              <TouchableOpacity style={styles.loginSubmit} onPress={handleLogin} disabled={loginLoading}>
                {loginLoading ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.loginSubmitText}>Sign In</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity onPress={() => { setForgotMode(true); setResetSent(false); setResetMessage(''); }}>
                <Text style={styles.forgotLink}>Forgot password?</Text>
              </TouchableOpacity>

              <TouchableOpacity style={styles.loginCancel} onPress={() => setShowLoginModal(false)}>
                <Text style={styles.loginCancelText}>Cancel</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.loginTitle}>🔑 Reset Password</Text>
              <Text style={styles.loginSubtitle}>
                {resetSent ? 'Enter the code from your email' : 'We\'ll email you a reset code'}
              </Text>

              {!resetSent ? (
                <>
                  <TextInput
                    style={styles.loginInput}
                    placeholder="Username or email"
                    value={loginUsername}
                    onChangeText={setLoginUsername}
                    autoCapitalize="none"
                  />
                  <TouchableOpacity style={styles.loginSubmit} onPress={handleForgotPassword} disabled={loginLoading}>
                    {loginLoading ? <ActivityIndicator size="small" color="#fff" /> : <Text style={styles.loginSubmitText}>Send Reset Code</Text>}
                  </TouchableOpacity>
                </>
              ) : (
                <>
                  {resetMessage ? <Text style={styles.resetInfo}>{resetMessage}</Text> : null}
                  <TextInput
                    style={styles.loginInput}
                    placeholder="Reset code"
                    value={resetToken}
                    onChangeText={setResetToken}
                    autoCapitalize="none"
                  />
                  <TextInput
                    style={styles.loginInput}
                    placeholder="New password (min 8 chars)"
                    value={newPassword}
                    onChangeText={setNewPassword}
                    secureTextEntry
                  />
                  <TouchableOpacity style={styles.loginSubmit} onPress={handleResetPassword} disabled={loginLoading}>
                    {loginLoading ? <ActivityIndicator size="small" color="#fff" /> : <Text style={styles.loginSubmitText}>Reset Password</Text>}
                  </TouchableOpacity>
                </>
              )}

              <TouchableOpacity style={styles.loginCancel} onPress={() => { setForgotMode(false); setResetSent(false); }}>
                <Text style={styles.loginCancelText}>Back to Sign In</Text>
              </TouchableOpacity>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
  
  // Stock Detail Modal - Robinhood style
  const renderStockModal = () => (
    <Modal visible={showStockModal} animationType="slide">
      <SafeAreaView style={styles.stockModal}>
        <View style={styles.stockModalHeader}>
          <TouchableOpacity onPress={() => setShowStockModal(false)}>
            <Text style={{ fontSize: 18, color: colors.primary }}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.stockModalSymbol}>{selectedStock}</Text>
          <View style={{ width: 50 }} />
        </View>
        
        <ScrollView>
          {stockLoading ? (
            <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 50 }} />
          ) : selectedStockData ? (
            <>
              <Text style={styles.stockModalPrice}>
                ${selectedStockData.current_price?.toFixed(2) || '0.00'}
              </Text>
              <Text style={[styles.stockModalChange, { color: (selectedStockData.change_percent || 0) >= 0 ? colors.success : colors.danger }]}>
                {(selectedStockData.change_percent || 0) >= 0 ? '+' : ''}{selectedStockData.change_percent?.toFixed(2) || '0.00'}%
              </Text>
              
              {/* Chart - Show actual data or placeholder */}
              <View style={styles.stockChartContainer}>
                {stockChartData && stockChartData.length > 0 ? (
                  <View style={{ padding: 16 }}>
                    <Text style={styles.stockChartTitle}>📈 Price Chart (30 Days)</Text>
                    <Text style={styles.stockChartSubtitle}>{stockChartData.length} data points</Text>
                    {/* Simple price visualization */}
                    <View style={{ flexDirection: 'row', alignItems: 'flex-end', height: 150, marginTop: 10 }}>
                      {stockChartData.slice(-30).map((point: any, i: number) => {
                        const maxPrice = Math.max(...stockChartData.slice(-30).map((p: any) => p.close || p.price || 0));
                        const minPrice = Math.min(...stockChartData.slice(-30).map((p: any) => p.close || p.price || 0));
                        const height = ((point.close || point.price || 0) - minPrice) / (maxPrice - minPrice) * 140;
                        return (
                          <View key={i} style={{ flex: 1, height: height || 10, backgroundColor: colors.primary, marginHorizontal: 1, borderRadius: 2 }} />
                        );
                      })}
                    </View>
                  </View>
                ) : (
                  <View>
                    <Text style={styles.stockChartPlaceholder}>📈 Price Chart</Text>
                    <Text style={styles.stockChartPlaceholder}>Loading chart data...</Text>
                  </View>
                )}
              </View>
              
              {/* Analysis Card */}
              <View style={styles.analysisCard}>
                <Text style={styles.analysisTitle}>📊 Technical Analysis</Text>
                
                <View style={styles.analysisRow}>
                  <Text style={styles.analysisLabel}>Trend</Text>
                  <Text style={[styles.analysisValue, { color: (selectedStockData.technical_analysis?.trend || selectedStockData.analysis?.trend) === 'bullish' ? colors.success : colors.danger }]}>
                    {(selectedStockData.technical_analysis?.trend || selectedStockData.analysis?.trend || 'Neutral').toUpperCase()}
                  </Text>
                </View>
                
                <View style={styles.analysisRow}>
                  <Text style={styles.analysisLabel}>Support</Text>
                  <Text style={styles.analysisValue}>${(selectedStockData.technical_analysis?.next_support || selectedStockData.analysis?.support || 0).toFixed(2)}</Text>
                </View>
                
                <View style={styles.analysisRow}>
                  <Text style={styles.analysisLabel}>Resistance</Text>
                  <Text style={styles.analysisValue}>${(selectedStockData.technical_analysis?.next_resistance || selectedStockData.analysis?.resistance || 0).toFixed(2)}</Text>
                </View>
                
                <View style={styles.analysisRow}>
                  <Text style={styles.analysisLabel}>RSI</Text>
                  <Text style={[styles.analysisValue, { color: (selectedStockData.technical_analysis?.rsi || 50) > 70 ? colors.danger : (selectedStockData.technical_analysis?.rsi || 50) < 30 ? colors.success : colors.text }]}>
                    {(selectedStockData.technical_analysis?.rsi || 50).toFixed(1)}
                  </Text>
                </View>
                
                {selectedStockData.analysis?.elliott_wave && (
                  <View style={styles.analysisRow}>
                    <Text style={styles.analysisLabel}>Elliott Wave</Text>
                    <Text style={styles.analysisValue}>
                      Wave {selectedStockData.analysis.elliott_wave.current_wave} ({selectedStockData.analysis.elliott_wave.trend})
                    </Text>
                  </View>
                )}
                
                <View style={[styles.recommendationBadge, { 
                  backgroundColor: selectedStockData.analysis?.recommendation === 'Buy' ? colors.success + '20' : 
                                  selectedStockData.analysis?.recommendation === 'Sell' ? colors.danger + '20' : colors.warning + '20'
                }]}>
                  <Text style={[styles.recommendationText, {
                    color: selectedStockData.analysis?.recommendation === 'Buy' ? colors.success : 
                           selectedStockData.analysis?.recommendation === 'Sell' ? colors.danger : colors.warning
                  }]}>
                    {selectedStockData.analysis?.recommendation || 'Hold'}
                  </Text>
                </View>
              </View>
              
              {/* AI Summary */}
              {(selectedStockData.ai_recommendation?.analysis || selectedStockData.ai_summary) && (
                <View style={styles.analysisCard}>
                  <Text style={styles.analysisTitle}>🤖 AI Analysis (Powered by mistral:7b)</Text>
                  <Text style={styles.aiSummary}>
                    {selectedStockData.ai_recommendation?.analysis || selectedStockData.ai_summary}
                  </Text>
                  {selectedStockData.ai_recommendation?.confidence && (
                    <Text style={styles.aiConfidence}>
                      Confidence: {(selectedStockData.ai_recommendation.confidence * 100).toFixed(0)}%
                    </Text>
                  )}
                </View>
              )}
              
              {/* Trade Actions */}
              <View style={styles.tradeActions}>
                <TouchableOpacity style={styles.sellButton} onPress={() => setShowSellModal(true)}>
                  <Text style={styles.sellButtonText}>Close Position</Text>
                </TouchableOpacity>
              </View>
              
              {/* Disclaimer */}
              <Text style={styles.disclaimer}>
                ⚠️ This analysis is for informational purposes only and should not be considered financial advice.
              </Text>
            </>
          ) : (
            <Text style={styles.emptyText}>No data available</Text>
          )}
        </ScrollView>
        
        {/* Sell Modal */}
        <Modal visible={showSellModal} transparent animationType="fade">
          <View style={styles.sellModalOverlay}>
            <View style={styles.sellModalContent}>
              <Text style={styles.sellModalTitle}>Close Position - {selectedStock}</Text>
              <Text style={styles.sellModalSubtitle}>Current Market Price: ${selectedStockData?.current_price?.toFixed(2) || '0.00'}</Text>
              <TextInput
                style={styles.sellInput}
                placeholder="Number of shares to close"
                keyboardType="numeric"
                value={sellShares}
                onChangeText={setSellShares}
              />
              <TextInput
                style={styles.sellInput}
                placeholder="Closing price per share (optional)"
                keyboardType="numeric"
                value={newStockCost}
                onChangeText={setNewStockCost}
              />
              <View style={styles.sellModalActions}>
                <TouchableOpacity style={styles.sellCancelBtn} onPress={() => { setShowSellModal(false); setSellShares(''); }}>
                  <Text style={styles.sellCancelText}>Cancel</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.sellConfirmBtn} onPress={sellStock} disabled={stockActionLoading}>
                  {stockActionLoading ? (
                    <ActivityIndicator size="small" color="#fff" />
                  ) : (
                    <Text style={styles.sellConfirmText}>Confirm Sale</Text>
                  )}
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      </SafeAreaView>
    </Modal>
  );
  
  // Add Stock Modal
  const renderAddStockModal = () => (
    <Modal visible={showAddStockModal} transparent animationType="fade">
      <View style={styles.sellModalOverlay}>
        <View style={styles.addStockModalContent}>
          <Text style={styles.sellModalTitle}>Add Stock to Portfolio</Text>
          <TextInput
            style={styles.sellInput}
            placeholder="Stock Symbol (e.g., AAPL)"
            autoCapitalize="characters"
            value={newStockSymbol}
            onChangeText={setNewStockSymbol}
            maxLength={5}
          />
          <TextInput
            style={styles.sellInput}
            placeholder="Number of Shares"
            keyboardType="numeric"
            value={newStockShares}
            onChangeText={setNewStockShares}
          />
          <TextInput
            style={styles.sellInput}
            placeholder="Average Cost per Share ($)"
            keyboardType="numeric"
            value={newStockCost}
            onChangeText={setNewStockCost}
          />
          <View style={styles.sellModalActions}>
            <TouchableOpacity style={styles.sellCancelBtn} onPress={() => { setShowAddStockModal(false); setNewStockSymbol(''); setNewStockShares(''); setNewStockCost(''); }}>
              <Text style={styles.sellCancelText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.addConfirmBtn} onPress={addStock} disabled={stockActionLoading}>
              {stockActionLoading ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.sellConfirmText}>Add Stock</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );

  // ── Trading Scanner Screen ──────────────────────────────────────────────
  const [scanResults, setScanResults] = useState<any>(null);
  const [tradingPortfolio, setTradingPortfolio] = useState<any>(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [tradingTab, setTradingTab] = useState<'scanner' | 'portfolio' | 'journal'>('scanner');

  const runScan = async (autoExec = false) => {
    setScanLoading(true);
    try {
      const r = await fetchWithTimeout(`${API_BASE}/api/trading/auto-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_execute: autoExec, min_confidence: 50 }),
      }, 60000);
      setScanResults(await r.json());
    } catch (e) { Alert.alert('Scan Failed', String(e)); }
    setScanLoading(false);
  };

  const loadTradingPortfolio = async () => {
    try {
      const r = await fetchWithTimeout(`${API_BASE}/api/trading/portfolio`);
      setTradingPortfolio(await r.json());
    } catch {}
  };

  const executeMobileTrade = async (symbol: string, action: string) => {
    try {
      const r = await fetchWithTimeout(`${API_BASE}/api/trading/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, action }),
      });
      if (r.ok) { Alert.alert('Trade Executed', `${action} ${symbol}`); loadTradingPortfolio(); }
      else { const e = await r.json(); Alert.alert('Failed', e.detail || 'Error'); }
    } catch (e) { Alert.alert('Error', String(e)); }
  };

  const renderTrading = () => {
    const signalColor = (s: string) => s === 'STRONG_BUY' || s === 'BUY' ? '#16a34a' : s === 'STRONG_SELL' || s === 'SELL' ? '#dc2626' : '#6b7280';
    const buys = (scanResults?.all_signals || []).filter((s: any) => s.signal === 'STRONG_BUY' || s.signal === 'BUY');
    const sells = (scanResults?.all_signals || []).filter((s: any) => s.signal === 'STRONG_SELL' || s.signal === 'SELL');

    return renderFeatureScreen('Day Trader', '⚡', '#F59E0B', (
      <>
        {/* Sub-tabs */}
        <View style={{ flexDirection: 'row', marginBottom: 16, gap: 8 }}>
          {(['scanner', 'portfolio', 'journal'] as const).map(t => (
            <TouchableOpacity key={t} onPress={() => { setTradingTab(t); if (t === 'portfolio') loadTradingPortfolio(); }}
              style={{ flex: 1, paddingVertical: 10, borderRadius: 12, backgroundColor: tradingTab === t ? '#F59E0B' : colors.bgCard, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
              <Text style={{ fontWeight: '600', color: tradingTab === t ? '#fff' : colors.text, fontSize: 13 }}>{t === 'scanner' ? '🔍 Scanner' : t === 'portfolio' ? '💼 Portfolio' : '📖 Journal'}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Scan button */}
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
          <TouchableOpacity onPress={() => runScan(false)} disabled={scanLoading}
            style={{ flex: 1, backgroundColor: '#3b82f6', paddingVertical: 14, borderRadius: 14, alignItems: 'center' }}>
            <Text style={{ color: '#fff', fontWeight: '700', fontSize: 15 }}>{scanLoading ? '⏳ Scanning...' : '▶ Scan Market'}</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => runScan(true)} disabled={scanLoading}
            style={{ flex: 1, backgroundColor: '#16a34a', paddingVertical: 14, borderRadius: 14, alignItems: 'center' }}>
            <Text style={{ color: '#fff', fontWeight: '700', fontSize: 15 }}>🤖 Auto Trade</Text>
          </TouchableOpacity>
        </View>

        {tradingTab === 'scanner' && (
          <>
            {scanResults && (
              <View style={{ flexDirection: 'row', gap: 12, marginBottom: 16 }}>
                <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 24, fontWeight: '700', color: '#16a34a' }}>{scanResults.buy_signals}</Text>
                  <Text style={{ fontSize: 11, color: colors.textMuted }}>Buy Signals</Text>
                </View>
                <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 24, fontWeight: '700', color: '#dc2626' }}>{scanResults.sell_signals}</Text>
                  <Text style={{ fontSize: 11, color: colors.textMuted }}>Sell Signals</Text>
                </View>
                <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                  <Text style={{ fontSize: 24, fontWeight: '700', color: colors.text }}>{scanResults.scanned}</Text>
                  <Text style={{ fontSize: 11, color: colors.textMuted }}>Scanned</Text>
                </View>
              </View>
            )}

            {buys.length > 0 && (
              <View style={{ marginBottom: 16 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#16a34a', marginBottom: 8 }}>📈 Buy Signals</Text>
                {buys.map((s: any) => (
                  <View key={s.symbol} style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                        <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{s.symbol}</Text>
                        <Text style={{ fontSize: 13, color: colors.textMuted }}>${s.price?.toFixed(2)}</Text>
                        <View style={{ backgroundColor: signalColor(s.signal) + '20', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}>
                          <Text style={{ fontSize: 11, fontWeight: '700', color: signalColor(s.signal) }}>{s.signal} {s.confidence}%</Text>
                        </View>
                      </View>
                      <TouchableOpacity onPress={() => executeMobileTrade(s.symbol, 'BUY')}
                        style={{ backgroundColor: '#16a34a', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 }}>
                        <Text style={{ color: '#fff', fontWeight: '700', fontSize: 12 }}>Buy</Text>
                      </TouchableOpacity>
                    </View>
                    <View style={{ flexDirection: 'row', gap: 12, marginTop: 8 }}>
                      <Text style={{ fontSize: 11, color: colors.textMuted }}>Entry: <Text style={{ fontWeight: '600' }}>${s.entry?.toFixed(2)}</Text></Text>
                      <Text style={{ fontSize: 11, color: '#dc2626' }}>Stop: ${s.stop_loss?.toFixed(2)}</Text>
                      <Text style={{ fontSize: 11, color: '#16a34a' }}>TP: ${s.take_profit_1?.toFixed(2)}</Text>
                      <Text style={{ fontSize: 11, color: colors.textMuted }}>R:R {s.risk_reward}</Text>
                    </View>
                    <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 4 }}>{(s.reasons || []).slice(0, 3).join(' · ')}</Text>
                  </View>
                ))}
              </View>
            )}

            {sells.length > 0 && (
              <View style={{ marginBottom: 16 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: '#dc2626', marginBottom: 8 }}>📉 Sell Signals</Text>
                {sells.map((s: any) => (
                  <View key={s.symbol} style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                      <Text style={{ fontSize: 18, fontWeight: '800', color: colors.text }}>{s.symbol}</Text>
                      <Text style={{ fontSize: 13, color: colors.textMuted }}>${s.price?.toFixed(2)}</Text>
                      <View style={{ backgroundColor: '#dc262620', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 }}>
                        <Text style={{ fontSize: 11, fontWeight: '700', color: '#dc2626' }}>{s.signal} {s.confidence}%</Text>
                      </View>
                    </View>
                    <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 6 }}>{(s.reasons || []).slice(0, 3).join(' · ')}</Text>
                  </View>
                ))}
              </View>
            )}

            {!scanResults && !scanLoading && (
              <View style={{ alignItems: 'center', paddingVertical: 40 }}>
                <Text style={{ fontSize: 40, marginBottom: 12 }}>🔍</Text>
                <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>Tap "Scan Market" to begin</Text>
                <Text style={{ fontSize: 13, color: colors.textMuted, marginTop: 4 }}>Scans 24 stocks for buy/sell signals</Text>
              </View>
            )}
          </>
        )}

        {tradingTab === 'portfolio' && tradingPortfolio && (
          <>
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
              <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 11, color: colors.textMuted }}>Portfolio Value</Text>
                <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>${tradingPortfolio.portfolio_value?.toLocaleString()}</Text>
              </View>
              <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 11, color: colors.textMuted }}>Win Rate</Text>
                <Text style={{ fontSize: 20, fontWeight: '800', color: colors.text }}>{tradingPortfolio.win_rate}%</Text>
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: 8, marginBottom: 16 }}>
              <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 11, color: colors.textMuted }}>Realized P&L</Text>
                <Text style={{ fontSize: 18, fontWeight: '700', color: tradingPortfolio.realized_pnl >= 0 ? '#16a34a' : '#dc2626' }}>${tradingPortfolio.realized_pnl?.toFixed(2)}</Text>
              </View>
              <View style={{ flex: 1, backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 11, color: colors.textMuted }}>Cash</Text>
                <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>${tradingPortfolio.cash?.toLocaleString()}</Text>
              </View>
            </View>

            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Open Positions ({tradingPortfolio.open_positions?.length || 0})</Text>
            {(tradingPortfolio.open_positions || []).map((t: any) => (
              <View key={t.id} style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View>
                    <Text style={{ fontSize: 16, fontWeight: '800' }}>{t.symbol}</Text>
                    <Text style={{ fontSize: 11, color: colors.textMuted }}>{t.quantity} shares @ ${t.entry_price?.toFixed(2)}</Text>
                  </View>
                  <View style={{ alignItems: 'flex-end' }}>
                    <Text style={{ fontSize: 14, fontWeight: '700', color: t.unrealized_pnl >= 0 ? '#16a34a' : '#dc2626' }}>
                      ${t.unrealized_pnl?.toFixed(2)} ({t.unrealized_pnl_pct >= 0 ? '+' : ''}{t.unrealized_pnl_pct?.toFixed(1)}%)
                    </Text>
                    <TouchableOpacity onPress={() => executeMobileTrade(t.symbol, 'SELL')}
                      style={{ backgroundColor: '#dc2626', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, marginTop: 4 }}>
                      <Text style={{ color: '#fff', fontWeight: '700', fontSize: 11 }}>Sell</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              </View>
            ))}
            {(tradingPortfolio.open_positions || []).length === 0 && (
              <Text style={{ textAlign: 'center', color: colors.textMuted, paddingVertical: 20 }}>No open positions. Scan for signals to start.</Text>
            )}
          </>
        )}

        {tradingTab === 'journal' && tradingPortfolio && (
          <>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Closed Trades ({tradingPortfolio.closed_trades?.length || 0})</Text>
            {[...(tradingPortfolio.closed_trades || [])].reverse().map((t: any) => (
              <View key={t.id} style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Text style={{ fontSize: 15, fontWeight: '800' }}>{t.symbol}</Text>
                    <View style={{ backgroundColor: t.status === 'TAKE_PROFIT' ? '#16a34a20' : t.status === 'STOPPED_OUT' ? '#dc262620' : '#3b82f620', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6 }}>
                      <Text style={{ fontSize: 10, fontWeight: '700', color: t.status === 'TAKE_PROFIT' ? '#16a34a' : t.status === 'STOPPED_OUT' ? '#dc2626' : '#3b82f6' }}>{t.status}</Text>
                    </View>
                  </View>
                  <Text style={{ fontWeight: '700', color: t.pnl >= 0 ? '#16a34a' : '#dc2626' }}>${t.pnl?.toFixed(2)}</Text>
                </View>
                <Text style={{ fontSize: 11, color: colors.textMuted, marginTop: 4 }}>Entry: ${t.entry_price?.toFixed(2)} → Exit: ${t.exit_price?.toFixed(2)}</Text>
                <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 2 }}>{t.reason_entry}</Text>
              </View>
            ))}
            {(tradingPortfolio.closed_trades || []).length === 0 && (
              <Text style={{ textAlign: 'center', color: colors.textMuted, paddingVertical: 20 }}>No closed trades yet.</Text>
            )}
          </>
        )}
      </>
    ));
  };

  // ── Market Intel Screen ────────────────────────────────────────────────
  const [intelData, setIntelData] = useState<any>(null);
  const [intelTab, setIntelTab] = useState<'overview' | 'ai_boom' | 'influencers' | 'big_money'>('overview');
  const [intelLoading, setIntelLoading] = useState(false);

  const loadIntel = async (tab: string) => {
    setIntelLoading(true);
    const ep = tab === 'overview' ? 'snapshot' : tab === 'ai_boom' ? 'ai-boom' : tab === 'influencers' ? 'influencers' : 'big-money';
    try {
      const r = await fetchWithTimeout(`${API_BASE}/api/market-intel/${ep}`, {}, 30000);
      setIntelData(await r.json());
    } catch {}
    setIntelLoading(false);
  };

  useEffect(() => {
    if (activeTab === 'market_intel') loadIntel(intelTab);
    if (activeTab === 'trading') { loadTradingPortfolio(); }
  }, [activeTab, intelTab]);

  const renderMarketIntel = () => (
    renderFeatureScreen('Market Intel', '🧠', '#8B5CF6', (
      <>
        {/* Sub-tabs */}
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {([
              { id: 'overview', label: '📊 Overview' },
              { id: 'ai_boom', label: '🤖 AI Boom' },
              { id: 'influencers', label: '👥 Influencers' },
              { id: 'big_money', label: '💰 Big Money' },
            ] as const).map(t => (
              <TouchableOpacity key={t.id} onPress={() => setIntelTab(t.id)}
                style={{ paddingHorizontal: 16, paddingVertical: 10, borderRadius: 12, backgroundColor: intelTab === t.id ? '#8B5CF6' : colors.bgCard, borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontWeight: '600', color: intelTab === t.id ? '#fff' : colors.text, fontSize: 13 }}>{t.label}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>

        {intelLoading && <ActivityIndicator size="large" color="#8B5CF6" style={{ marginVertical: 30 }} />}

        {!intelLoading && intelData && intelTab === 'overview' && (
          <>
            {/* Market overview cards */}
            {intelData.market_overview && (
              <View style={{ marginBottom: 16 }}>
                <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Market Indices</Text>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
                  {(intelData.market_overview.indices || []).map((idx: any) => (
                    <View key={idx.symbol} style={{ width: '48%', backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, borderWidth: 1, borderColor: colors.border }}>
                      <Text style={{ fontSize: 12, color: colors.textMuted }}>{idx.name || idx.symbol}</Text>
                      <Text style={{ fontSize: 18, fontWeight: '700', color: colors.text }}>{idx.price?.toLocaleString()}</Text>
                      <Text style={{ fontSize: 13, fontWeight: '600', color: (idx.change_pct || 0) >= 0 ? '#16a34a' : '#dc2626' }}>
                        {(idx.change_pct || 0) >= 0 ? '+' : ''}{idx.change_pct?.toFixed(2)}%
                      </Text>
                    </View>
                  ))}
                </View>
              </View>
            )}
            {intelData.ai_boom && (
              <View style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 13, color: colors.textMuted }}>AI Boom Score</Text>
                <Text style={{ fontSize: 28, fontWeight: '800', color: '#8B5CF6' }}>{intelData.ai_boom.ai_boom_score}</Text>
                <Text style={{ fontSize: 13, color: colors.textMuted }}>Regime: {intelData.ai_boom.regime}</Text>
              </View>
            )}
          </>
        )}

        {!intelLoading && intelData && intelTab === 'ai_boom' && (
          <>
            <View style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border, alignItems: 'center' }}>
              <Text style={{ fontSize: 36, fontWeight: '900', color: '#8B5CF6' }}>{intelData.ai_boom_score}</Text>
              <Text style={{ fontSize: 14, color: colors.textMuted }}>Regime: <Text style={{ fontWeight: '700' }}>{intelData.regime}</Text></Text>
            </View>
            {Object.entries(intelData.categories || {}).map(([cat, info]: [string, any]) => (
              <View key={cat} style={{ backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: colors.text }}>{cat.replace(/_/g, ' ')}</Text>
                  <Text style={{ fontSize: 13, fontWeight: '700', color: (info.avg_30d_pct || 0) >= 0 ? '#16a34a' : '#dc2626' }}>
                    {(info.avg_30d_pct || 0) >= 0 ? '+' : ''}{info.avg_30d_pct?.toFixed(1)}%
                  </Text>
                </View>
              </View>
            ))}
          </>
        )}

        {!intelLoading && intelData && intelTab === 'influencers' && (
          <>
            {(intelData.influencers || []).map((p: any) => (
              <View key={p.handle} style={{ backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <View>
                    <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text }}>{p.name}</Text>
                    <Text style={{ fontSize: 11, color: colors.textMuted }}>@{p.handle} · {p.category}</Text>
                  </View>
                  <View style={{ backgroundColor: p.signal === 'bullish' ? '#16a34a20' : p.signal === 'bearish' ? '#dc262620' : colors.bgCardLight, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8 }}>
                    <Text style={{ fontSize: 11, fontWeight: '700', color: p.signal === 'bullish' ? '#16a34a' : p.signal === 'bearish' ? '#dc2626' : colors.textMuted }}>{p.signal}</Text>
                  </View>
                </View>
                {(p.items || []).slice(0, 3).map((it: any, i: number) => (
                  <TouchableOpacity key={i} onPress={() => it.url && Linking.openURL(it.url)} style={{ marginTop: 6 }}>
                    <Text style={{ fontSize: 12, color: colors.primary }} numberOfLines={2}>{it.title}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            ))}
          </>
        )}

        {!intelLoading && intelData && intelTab === 'big_money' && (
          <>
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8 }}>Insider (Form 4): {intelData.summary?.insider_filings_24h || 0}</Text>
            {(intelData.insider_form4 || []).slice(0, 10).map((it: any, i: number) => (
              <TouchableOpacity key={i} onPress={() => it.link && Linking.openURL(it.link)}
                style={{ backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 12, color: colors.text }} numberOfLines={2}>{it.title}</Text>
                <Text style={{ fontSize: 10, color: colors.textMuted, marginTop: 2 }}>{it.published?.slice(0, 16)}</Text>
              </TouchableOpacity>
            ))}
            <Text style={{ fontSize: 15, fontWeight: '700', color: colors.text, marginBottom: 8, marginTop: 16 }}>Institutional (13F): {intelData.summary?.institutional_filings_24h || 0}</Text>
            {(intelData.institutional_13f || []).slice(0, 10).map((it: any, i: number) => (
              <TouchableOpacity key={i} onPress={() => it.link && Linking.openURL(it.link)}
                style={{ backgroundColor: colors.bgCard, borderRadius: 12, padding: 12, marginBottom: 6, borderWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: 12, color: colors.text }} numberOfLines={2}>{it.title}</Text>
                <Text style={{ fontSize: 10, color: colors.textMuted, marginTop: 2 }}>{it.published?.slice(0, 16)}</Text>
              </TouchableOpacity>
            ))}
          </>
        )}

        {!intelLoading && !intelData && (
          <View style={{ alignItems: 'center', paddingVertical: 40 }}>
            <Text style={{ fontSize: 40, marginBottom: 12 }}>🧠</Text>
            <Text style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>Loading market intelligence...</Text>
          </View>
        )}
      </>
    ))
  );

  // ── Hub landing screens ──────────────────────────────────────────────────
  const HubCard = ({ icon, title, subtitle, tab, color }: { icon: string, title: string, subtitle: string, tab: TabType, color: string }) => (
    <TouchableOpacity style={[styles.quickCard, { width: '48%' }]} onPress={() => setActiveTab(tab)}>
      <View style={{ width: 40, height: 40, borderRadius: 12, backgroundColor: color + '18', justifyContent: 'center', alignItems: 'center', marginBottom: 8 }}>
        <Text style={{ fontSize: 20 }}>{icon}</Text>
      </View>
      <Text style={{ fontSize: 15, fontWeight: '600', color: colors.text }}>{title}</Text>
      <Text style={styles.cardSubtitle}>{subtitle}</Text>
    </TouchableOpacity>
  );

  const renderHubScreen = (title: string, subtitle: string, color: string, cards: {icon: string, title: string, subtitle: string, tab: TabType, color: string}[]) => (
    <ScrollView contentContainerStyle={styles.scrollContent}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.greeting}>{subtitle}</Text>
          <Text style={styles.title}>{title}</Text>
        </View>
      </View>
      <View style={styles.quickCards}>
        {cards.map(c => <HubCard key={c.tab} {...c} />)}
      </View>
    </ScrollView>
  );

  const renderMoneyHub = () => renderHubScreen('Money', 'Finances & investing', '#10B981', [
    { icon: '💰', title: 'Finance', subtitle: 'Spending & budgets', tab: 'finance', color: '#10B981' },
    { icon: '📈', title: 'Portfolio', subtitle: 'US & India markets', tab: 'portfolio', color: '#3B82F6' },
    { icon: '⚡', title: 'Day Trader', subtitle: 'Scanner & journal', tab: 'trading', color: '#F59E0B' },
    { icon: '🧠', title: 'Market Intel', subtitle: 'Trends & big money', tab: 'market_intel', color: '#8B5CF6' },
    { icon: '🛒', title: 'Shopping', subtitle: 'Price tracking & deals', tab: 'shopping', color: '#06B6D4' },
    { icon: '✈️', title: 'Travel', subtitle: 'Fares & price history', tab: 'travel', color: '#22C55E' },
  ]);

  const renderLifeHub = () => renderHubScreen('Life', 'Health, family & home', '#EF4444', [
    { icon: '❤️', title: 'Health', subtitle: 'Reports & insights', tab: 'health', color: '#EF4444' },
    { icon: '👪', title: 'Family', subtitle: 'Profiles & oversight', tab: 'family', color: '#6366F1' },
    { icon: '🏫', title: 'School', subtitle: 'Kids & schedules', tab: 'school', color: '#8B5CF6' },
    { icon: '🍎', title: 'Nutrition', subtitle: 'Meal planning', tab: 'nutrition', color: '#22C55E' },
    { icon: '📅', title: 'Calendar', subtitle: 'Events & reminders', tab: 'calendar', color: '#F59E0B' },
    { icon: '📄', title: 'Documents', subtitle: 'Upload & analyze', tab: 'documents', color: '#64748B' },
    { icon: '🔧', title: 'Maintenance', subtitle: 'Home & vehicle care', tab: 'maintenance', color: '#D97706' },
  ]);

  const renderProfileHub = () => renderHubScreen('Profile', 'Account & preferences', '#64748B', [
    { icon: '⚙️', title: 'Settings', subtitle: 'Features & privacy', tab: 'settings', color: '#64748B' },
  ]);

  // ── Maintenance Hub screen ───────────────────────────────────────────────
  const renderMaintenance = () => renderFeatureScreen('Maintenance', '🔧', '#D97706', (
    <View style={styles.screenPadding}>
      {/* Sub-tab switcher */}
      <View style={{ flexDirection: 'row', marginBottom: 12 }}>
        {(['checklist', 'appliances', 'repairs'] as const).map(t => (
          <TouchableOpacity key={t} onPress={() => setMaintTab(t)}
            style={{ flex: 1, paddingVertical: 10, borderRadius: 12, marginHorizontal: 2, backgroundColor: maintTab === t ? '#D97706' : colors.bgCard, alignItems: 'center', borderWidth: 1, borderColor: colors.border }}>
            <Text style={{ fontWeight: '600', fontSize: 12, color: maintTab === t ? '#fff' : colors.text }}>
              {t === 'checklist' ? '✅ Checklist' : t === 'appliances' ? '🔌 Appliances' : '🛠 Repairs'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {maintTab === 'checklist' && (
        <>
          {/* Home / Vehicle toggle */}
          <View style={{ flexDirection: 'row', marginBottom: 12 }}>
            {(['home', 'vehicle'] as const).map(c => (
              <TouchableOpacity key={c} onPress={() => { setMaintCategory(c); }}
                style={{ flex: 1, paddingVertical: 8, borderRadius: 10, marginHorizontal: 2, backgroundColor: maintCategory === c ? colors.bgCardLight : 'transparent', alignItems: 'center' }}>
                <Text style={{ fontWeight: '600', fontSize: 13, color: maintCategory === c ? colors.text : colors.textDim }}>
                  {c === 'home' ? '🏠 Home' : '🚗 Vehicle'}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {maintProgress && (
            <Text style={{ fontSize: 13, color: colors.textMuted, marginBottom: 10 }}>
              {maintProgress.done}/{maintProgress.total} done{maintProgress.overdue > 0 ? ` · ${maintProgress.overdue} overdue` : ''}
            </Text>
          )}
          {maintLoading && <ActivityIndicator size="small" color="#D97706" style={{ marginVertical: 12 }} />}
          {maintChecklist.map((item: any) => (
            <View key={item.template_id} style={[styles.taskCard, { marginBottom: 10, flexDirection: 'row', alignItems: 'center' }]}>
              <View style={{ flex: 1 }}>
                <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{item.task}</Text>
                <Text style={{ fontSize: 12, color: colors.textMuted, marginTop: 2 }}>
                  {item.season} · every {item.interval_months}mo
                  {item.next_due ? ` · due ${item.next_due}` : ''}
                </Text>
                {item.why ? <Text style={{ fontSize: 11, color: colors.textDim, marginTop: 2 }}>{item.why}</Text> : null}
              </View>
              <TouchableOpacity
                onPress={() => markMaintenanceDone(item.template_id)}
                style={{ width: 34, height: 34, borderRadius: 17, marginLeft: 8, justifyContent: 'center', alignItems: 'center', backgroundColor: item.status === 'done' ? '#10B981' : item.overdue ? '#FEE2E2' : colors.bgCardLight, borderWidth: 1, borderColor: item.overdue ? '#EF4444' : colors.border }}>
                <Text style={{ fontSize: 16 }}>{item.status === 'done' ? '✓' : item.overdue ? '!' : '○'}</Text>
              </TouchableOpacity>
            </View>
          ))}
          {!maintLoading && maintChecklist.length === 0 && (
            <Text style={{ color: colors.textMuted, textAlign: 'center', marginTop: 24 }}>No checklist items yet.</Text>
          )}
        </>
      )}

      {maintTab === 'appliances' && (
        <>
          {maintAppliances.map((a: any, i: number) => (
            <View key={a.id || i} style={[styles.taskCard, { marginBottom: 10 }]}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{a.name || a.appliance_type}</Text>
              <Text style={{ fontSize: 12, color: colors.textMuted, marginTop: 2 }}>
                {a.age_years != null ? `${a.age_years} yrs old` : 'age unknown'}
                {a.lifespan_pct != null ? ` · ${a.lifespan_pct}% of lifespan` : ''}
                {a.warranty_until ? ` · warranty to ${a.warranty_until}` : ''}
              </Text>
            </View>
          ))}
          {maintAppliances.length === 0 && (
            <Text style={{ color: colors.textMuted, textAlign: 'center', marginTop: 24 }}>
              Register appliances to track warranty & lifespan.
            </Text>
          )}
        </>
      )}

      {maintTab === 'repairs' && (
        <>
          {maintRepairs.map((r: any, i: number) => (
            <View key={r.id || i} style={[styles.taskCard, { marginBottom: 10 }]}>
              <Text style={{ fontSize: 14, fontWeight: '600', color: colors.text }}>{r.title || r.description}</Text>
              <Text style={{ fontSize: 12, color: colors.textMuted, marginTop: 2 }}>
                {r.date || r.created_at || ''}{r.cost != null ? ` · $${r.cost}` : ''}{r.vendor ? ` · ${r.vendor}` : ''}
              </Text>
            </View>
          ))}
          {maintRepairs.length === 0 && (
            <Text style={{ color: colors.textMuted, textAlign: 'center', marginTop: 24 }}>
              Log repairs to build a service history.
            </Text>
          )}
        </>
      )}
    </View>
  ));

  // Render active screen
  const renderScreen = () => {
    switch (activeTab) {
      case 'assistant': return renderAssistant();
      case 'finance': return renderFinance();
      case 'health': return renderHealth();
      case 'shopping': return renderShopping();
      case 'travel': return renderTravel();
      case 'school': return renderSchool();
      case 'nutrition': return renderNutrition();
      case 'calendar': return renderCalendar();
      case 'portfolio': return renderPortfolio();
      case 'documents': return renderDocuments();
      case 'settings': return renderSettings();
      case 'trading': return renderTrading();
      case 'market_intel': return renderMarketIntel();
      case 'family': return renderFamily();
      case 'maintenance': return renderMaintenance();
      case 'money_hub': return renderMoneyHub();
      case 'life_hub': return renderLifeHub();
      case 'profile_hub': return renderProfileHub();
      default: return renderHome();
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {renderScreen()}
      {renderFeaturesModal()}
      {renderLoginModal()}
      {renderStockModal()}
      {renderAddStockModal()}

      {/* Bottom Navigation — 5 hubs: Home | Money | Assistant | Life | Profile */}
      {activeTab !== 'assistant' && (
        <View style={styles.bottomNav}>
          {([
            { hub: 'home' as TabType, icon: '🏠', label: 'Home' },
            { hub: 'money_hub' as TabType, icon: '💰', label: 'Money' },
            { hub: 'assistant' as TabType, icon: '🤖', label: 'Assistant' },
            { hub: 'life_hub' as TabType, icon: '🌿', label: 'Life' },
            { hub: 'profile_hub' as TabType, icon: '👤', label: 'Profile' },
          ]).map(item => {
            const active = tabToHub(activeTab) === item.hub;
            return (
              <TouchableOpacity key={item.hub} style={styles.navItem} onPress={() => setActiveTab(item.hub)}>
                <Text style={[styles.navIcon, active && styles.navActive]}>{item.icon}</Text>
                <Text style={[styles.navText, active && styles.navTextActive]}>{item.label}</Text>
              </TouchableOpacity>
            );
          })}
        </View>
      )}
    </SafeAreaView>
  );
}

// Light theme colors (default)
const colors = {
  bg: '#f4f6fb',
  bgCard: '#ffffff',
  bgCardLight: '#eef1f8',
  primary: '#4f46e5',
  primaryLight: '#818cf8',
  accent: '#7c3aed',
  success: '#059669',
  warning: '#d97706',
  danger: '#dc2626',
  text: '#0f172a',
  textMuted: '#475569',
  textDim: '#94a3b8',
  border: '#e6e9f2',
};

// Shared card elevation — soft modern shadow used across all cards
const cardShadow = {
  shadowColor: '#1e293b',
  shadowOffset: { width: 0, height: 2 },
  shadowOpacity: 0.06,
  shadowRadius: 8,
  elevation: 2,
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scrollContent: { padding: 16, paddingBottom: 100 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24, marginTop: 10 },
  greeting: { fontSize: 14, color: colors.textMuted },
  title: { fontSize: 32, fontWeight: "bold", color: colors.text },
  tagline: { fontSize: 14, color: colors.primary, marginTop: 2 },
  connectionStatus: { flexDirection: "row", alignItems: "center", backgroundColor: colors.bgCard, paddingHorizontal: 12, paddingVertical: 6, borderRadius: 20, borderWidth: 1, borderColor: colors.border },
  statusDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success, marginRight: 6 },
  statusText: { fontSize: 12, color: colors.textMuted },
  assistantCard: { backgroundColor: colors.bgCard, borderRadius: 20, padding: 20, flexDirection: "row", alignItems: "center", marginBottom: 24, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  assistantIconContainer: { width: 52, height: 52, borderRadius: 16, backgroundColor: colors.primary, justifyContent: "center", alignItems: "center", marginRight: 16 },
  assistantIcon: { fontSize: 28 },
  assistantText: { flex: 1 },
  assistantTitle: { fontSize: 18, fontWeight: "600", color: colors.text },
  assistantSubtitle: { fontSize: 14, color: colors.textMuted, marginTop: 2 },
  chevron: { fontSize: 24, color: colors.textDim },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "600", color: colors.text },
  seeAll: { fontSize: 14, color: colors.primary },
  quickCards: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", marginBottom: 24 },
  quickCard: { width: "48%", backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  cardIcon: { fontSize: 24, marginBottom: 8 },
  cardTitle: { fontSize: 12, color: colors.textMuted },
  cardValue: { fontSize: 20, fontWeight: "700", color: colors.text, marginTop: 4 },
  cardSubtitle: { fontSize: 12, color: colors.textDim, marginTop: 2 },
  featureGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", marginBottom: 24 },
  featureButton: { width: "23%", padding: 12, borderRadius: 16, alignItems: "center", marginBottom: 8, backgroundColor: colors.bgCardLight },
  featureIcon: { fontSize: 24, marginBottom: 4 },
  featureText: { fontSize: 11, fontWeight: "500", color: colors.text },
  taskCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 24, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  taskItem: { flexDirection: "row", alignItems: "center", paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  taskDot: { width: 10, height: 10, borderRadius: 5, marginRight: 12 },
  taskContent: { flex: 1 },
  taskTitle: { fontSize: 14, fontWeight: "500", color: colors.text },
  taskTime: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  privacyNotice: { backgroundColor: 'rgba(16, 185, 129, 0.15)', borderRadius: 16, padding: 16, flexDirection: "row", alignItems: "center", borderWidth: 1, borderColor: 'rgba(16, 185, 129, 0.3)' },
  privacyIcon: { fontSize: 20, marginRight: 12 },
  privacyText: { fontSize: 13, color: colors.success, flex: 1 },
  bottomNav: { position: "absolute", bottom: 0, left: 0, right: 0, backgroundColor: colors.bgCard, flexDirection: "row", justifyContent: "space-around", paddingVertical: 12, paddingBottom: 28, borderTopWidth: 1, borderTopColor: colors.border },
  navItem: { alignItems: "center" },
  navIcon: { fontSize: 24, opacity: 0.5 },
  navActive: { opacity: 1 },
  navText: { fontSize: 11, color: colors.textDim, marginTop: 4 },
  navTextActive: { color: colors.primary },
  // Chat/Assistant styles
  assistantScreen: { flex: 1, backgroundColor: colors.bg },
  chatHeader: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
  backButton: { fontSize: 18, color: colors.primary, fontWeight: "600" },
  backButtonWhite: { fontSize: 18, color: colors.text, fontWeight: "600" },
  chatTitle: { fontSize: 18, fontWeight: "600", color: colors.text },
  chatMessages: { flex: 1, padding: 16 },
  chatBubble: { maxWidth: "80%", padding: 14, borderRadius: 20, marginBottom: 12 },
  aiBubble: { backgroundColor: colors.bgCard, alignSelf: "flex-start", borderBottomLeftRadius: 4 },
  userBubble: { backgroundColor: colors.primary, alignSelf: "flex-end", borderBottomRightRadius: 4 },
  chatText: { fontSize: 14, color: colors.text, lineHeight: 20 },
  userText: { color: colors.text },
  chatInputContainer: { flexDirection: "row", padding: 16, borderTopWidth: 1, borderTopColor: colors.border, backgroundColor: colors.bgCard },
  chatInput: { flex: 1, backgroundColor: colors.bgCardLight, borderRadius: 24, paddingHorizontal: 16, paddingVertical: 12, fontSize: 14, color: colors.text },
  sendButton: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.primary, justifyContent: "center", alignItems: "center", marginLeft: 8 },
  sendIcon: { fontSize: 18, color: colors.text },
  // Feature screen styles
  featureScreen: { flex: 1, backgroundColor: colors.bg },
  featureHeader: { padding: 20, paddingTop: 16, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  featureHeaderContent: { flexDirection: "row", alignItems: "center" },
  featureHeaderIcon: { fontSize: 28, marginRight: 10 },
  featureHeaderTitle: { fontSize: 22, fontWeight: "700", color: colors.text },
  featureContent: { flex: 1 },
  screenPadding: { padding: 16 },
  featureSectionTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginTop: 16, marginBottom: 12 },
  aiConfidence: { fontSize: 12, color: colors.textMuted, marginTop: 8, fontStyle: "italic" },
  stockChartTitle: { fontSize: 16, fontWeight: "700", color: colors.text, marginBottom: 4 },
  stockChartSubtitle: { fontSize: 12, color: colors.textMuted },
  // Stats
  statRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
  statBox: { flex: 1, backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginHorizontal: 4, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  statLabel: { fontSize: 12, color: colors.textMuted },
  statValue: { fontSize: 24, fontWeight: "700", color: colors.text, marginTop: 4 },
  statSubtext: { fontSize: 11, color: colors.textDim, marginTop: 2 },
  // List items
  listItem: { flexDirection: "row", justifyContent: "space-between", backgroundColor: colors.bgCard, padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  listItemText: { fontSize: 14, color: colors.text },
  listItemDate: { fontSize: 12, color: colors.textMuted },
  // Tips
  tipCard: { backgroundColor: 'rgba(245, 158, 11, 0.15)', borderRadius: 16, padding: 16, flexDirection: "row", alignItems: "flex-start", borderWidth: 1, borderColor: 'rgba(245, 158, 11, 0.3)' },
  tipIcon: { fontSize: 20, marginRight: 12 },
  tipText: { flex: 1, fontSize: 14, color: colors.warning, lineHeight: 20 },
  // Summary card
  summaryCard: { backgroundColor: 'rgba(16, 185, 129, 0.15)', borderRadius: 16, padding: 16, flexDirection: "row", alignItems: "flex-start", borderWidth: 1, borderColor: 'rgba(16, 185, 129, 0.3)' },
  summaryIcon: { fontSize: 24, marginRight: 12 },
  summaryText: { flex: 1, fontSize: 14, color: colors.success, lineHeight: 20 },
  // Appointments
  appointmentCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, flexDirection: "row", alignItems: "center", borderWidth: 1, borderColor: colors.border },
  appointmentDate: { fontSize: 16, fontWeight: "700", color: colors.primary, marginRight: 16 },
  appointmentDetails: { flex: 1 },
  appointmentTitle: { fontSize: 14, fontWeight: "600", color: colors.text },
  appointmentDoctor: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  // Search
  searchBar: { flexDirection: "row", alignItems: "center", backgroundColor: colors.bgCard, borderRadius: 16, padding: 12, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  searchIcon: { fontSize: 18, marginRight: 8 },
  searchInput: { flex: 1, fontSize: 14, color: colors.text },
  // Checklist
  checklistItem: { flexDirection: "row", alignItems: "center", backgroundColor: colors.bgCard, padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  checkbox: { width: 22, height: 22, borderRadius: 6, borderWidth: 2, borderColor: colors.textDim, marginRight: 12, justifyContent: "center", alignItems: "center" },
  checklistText: { fontSize: 14, color: colors.text },
  // Deals
  dealCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border },
  dealBadge: { fontSize: 10, fontWeight: "700", color: colors.text, backgroundColor: colors.danger, paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6, alignSelf: "flex-start", marginBottom: 8 },
  dealTitle: { fontSize: 16, fontWeight: "600", color: colors.text },
  dealStore: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  // Trip planner
  tripPlanner: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  tripPlannerTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  tripInput: { backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 14, marginBottom: 10, fontSize: 14, color: colors.text, borderWidth: 1, borderColor: colors.border },
  searchTripButton: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center", marginTop: 8 },
  searchTripText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  tripCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, borderWidth: 1, borderColor: colors.border },
  tripDestination: { fontSize: 18, fontWeight: "600", color: colors.text },
  tripDates: { fontSize: 14, color: colors.textMuted, marginTop: 4 },
  tripStatus: { fontSize: 12, color: colors.success, fontWeight: "600", marginTop: 8 },
  // Assignments
  assignmentCard: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: colors.bgCard, padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  assignmentInfo: { flex: 1 },
  assignmentTitle: { fontSize: 14, fontWeight: "500", color: colors.text },
  assignmentCourse: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  assignmentDue: { fontSize: 12, color: colors.warning, fontWeight: "600" },
  // Meals
  mealItem: { backgroundColor: colors.bgCard, padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  mealText: { fontSize: 14, color: colors.text },
  generateMealButton: { backgroundColor: colors.success, borderRadius: 12, padding: 16, alignItems: "center", marginTop: 16 },
  generateMealText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  // Events
  eventCard: { backgroundColor: colors.bgCard, borderLeftWidth: 4, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  eventTitle: { fontSize: 14, fontWeight: "500", color: colors.text },
  eventDate: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  addEventButton: { backgroundColor: colors.accent, borderRadius: 12, padding: 16, alignItems: "center", marginTop: 16 },
  addEventText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  // Portfolio - Premium UI
  portfolioSummary: { backgroundColor: colors.bgCard, borderRadius: 20, padding: 24, alignItems: "center", marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  premiumPortfolioSummary: { backgroundColor: colors.bgCard, borderRadius: 24, padding: 28, alignItems: "center", marginBottom: 16, borderWidth: 2, borderColor: colors.primary + "50", shadowColor: colors.primary, shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.15, shadowRadius: 12 },
  premiumBadge: { backgroundColor: colors.warning + "20", paddingHorizontal: 12, paddingVertical: 4, borderRadius: 20, marginBottom: 8 },
  premiumBadgeText: { fontSize: 10, fontWeight: "700", color: colors.warning },
  portfolioLabel: { fontSize: 12, color: colors.textMuted, textTransform: "uppercase", letterSpacing: 1 },
  portfolioValue: { fontSize: 40, fontWeight: "800", color: colors.text, marginTop: 8 },
  portfolioChange: { fontSize: 16, fontWeight: "600", marginTop: 8 },
  portfolioActions: { flexDirection: "row", justifyContent: "space-between", marginBottom: 16, gap: 12 },
  addStockButton: { flex: 1, backgroundColor: colors.primary, borderRadius: 14, padding: 14, alignItems: "center" },
  addStockButtonText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  refreshButton: { flex: 1, backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, alignItems: "center", borderWidth: 1, borderColor: colors.border },
  refreshButtonText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  enhancedStockCard: { flexDirection: "row", alignItems: "center", backgroundColor: colors.bgCard, borderRadius: 16, marginBottom: 10, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  stockCardMain: { flex: 1, flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 16 },
  stockLeft: { flex: 1 },
  stockRight: { alignItems: "flex-end" },
  stockCard: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: colors.bgCard, padding: 16, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  stockSymbol: { fontSize: 18, fontWeight: "800", color: colors.text },
  stockName: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  stockShares: { fontSize: 11, color: colors.textDim, marginTop: 4 },
  stockValues: { alignItems: "flex-end" },
  stockValue: { fontSize: 16, fontWeight: "700", color: colors.text },
  stockChange: { fontSize: 13, fontWeight: "600", marginTop: 2 },
  removeStockBtn: { backgroundColor: colors.danger + "20", padding: 16, justifyContent: "center", alignItems: "center" },
  removeStockText: { color: colors.danger, fontSize: 16, fontWeight: "700" },
  emptyPortfolio: { alignItems: "center", padding: 40, backgroundColor: colors.bgCard, borderRadius: 20, borderWidth: 1, borderColor: colors.border },
  emptyPortfolioIcon: { fontSize: 48, marginBottom: 16 },
  emptyPortfolioText: { fontSize: 18, fontWeight: "600", color: colors.text },
  emptyPortfolioSubtext: { fontSize: 14, color: colors.textMuted, marginTop: 8 },
  // Trade actions and sell modal
  tradeActions: { padding: 20, gap: 12 },
  sellButton: { backgroundColor: colors.danger, borderRadius: 14, padding: 16, alignItems: "center" },
  sellButtonText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  disclaimer: { fontSize: 11, color: colors.textDim, textAlign: "center", padding: 16, fontStyle: "italic" },
  sellModalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.8)", justifyContent: "center", alignItems: "center", padding: 20 },
  sellModalContent: { backgroundColor: colors.bgCard, borderRadius: 24, padding: 24, width: "100%", maxWidth: 400 },
  addStockModalContent: { backgroundColor: colors.bgCard, borderRadius: 24, padding: 24, width: "100%", maxWidth: 400 },
  sellModalTitle: { fontSize: 20, fontWeight: "700", color: colors.text, textAlign: "center", marginBottom: 8 },
  sellModalSubtitle: { fontSize: 14, color: colors.textMuted, textAlign: "center", marginBottom: 16 },
  sellInput: { backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 16, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, marginBottom: 12 },
  sellModalActions: { flexDirection: "row", gap: 12, marginTop: 8 },
  sellCancelBtn: { flex: 1, backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 14, alignItems: "center" },
  sellCancelText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  sellConfirmBtn: { flex: 1, backgroundColor: colors.danger, borderRadius: 12, padding: 14, alignItems: "center" },
  addConfirmBtn: { flex: 1, backgroundColor: colors.success, borderRadius: 12, padding: 14, alignItems: "center" },
  sellConfirmText: { color: "#fff", fontWeight: "700", fontSize: 14 },
  // Modal
  modalOverlay: { flex: 1, backgroundColor: "rgba(0,0,0,0.7)", justifyContent: "flex-end" },
  modalContent: { backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: "70%", borderWidth: 1, borderColor: colors.border },
  modalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, borderBottomWidth: 1, borderBottomColor: colors.border },
  modalTitle: { fontSize: 18, fontWeight: "600", color: colors.text },
  modalClose: { fontSize: 24, color: colors.textMuted },
  modalScroll: { padding: 16 },
  modalGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" },
  // Shopping - search button and products
  searchButton: { backgroundColor: colors.primary, borderRadius: 12, paddingHorizontal: 20, paddingVertical: 12, marginLeft: 8 },
  searchButtonText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  productCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 10, borderWidth: 1, borderColor: colors.border },
  productName: { fontSize: 14, fontWeight: "600", color: colors.text },
  productPrice: { fontSize: 18, fontWeight: "700", color: colors.success, marginTop: 4 },
  productStore: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  // Checkbox checked state
  checkboxChecked: { backgroundColor: colors.success, borderColor: colors.success },
  checkmark: { color: colors.text, fontSize: 14, fontWeight: "700" },
  checklistTextChecked: { textDecorationLine: "line-through", color: colors.textDim },
  // Add grocery item
  addItemRow: { flexDirection: "row", alignItems: "center", marginTop: 12 },
  addItemInput: { flex: 1, backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, fontSize: 14, color: colors.text, borderWidth: 1, borderColor: colors.border },
  addItemButton: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.primary, justifyContent: "center", alignItems: "center", marginLeft: 8 },
  addItemButtonText: { color: colors.text, fontSize: 24, fontWeight: "600" },
  // Flight cards
  flightCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  flightHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  flightAirline: { fontSize: 16, fontWeight: "600", color: colors.text },
  flightPrice: { fontSize: 20, fontWeight: "700", color: colors.primary },
  flightTimes: { flexDirection: "row", justifyContent: "space-between", marginBottom: 12 },
  flightTime: { fontSize: 14, color: colors.text },
  flightDuration: { fontSize: 12, color: colors.textMuted },
  bookButton: { backgroundColor: colors.primary, borderRadius: 12, padding: 14, alignItems: "center" },
  bookButtonText: { color: colors.text, fontWeight: "600", fontSize: 14 },
  // Price filter styles
  priceFilterCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  priceFilterTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  priceRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
  priceLabel: { fontSize: 14, fontWeight: "500", color: colors.primary },
  sliderContainer: { flexDirection: "row", alignItems: "center", marginVertical: 4 },
  sliderLabel: { fontSize: 12, color: colors.textMuted, width: 40 },
  slider: { flex: 1, height: 40 },
  priceRangeText: { fontSize: 12, color: colors.textMuted, textAlign: "center", marginTop: 8 },
  // Product card enhancements
  productHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" },
  productMeta: { flexDirection: "row", alignItems: "center", marginTop: 4 },
  productReviews: { fontSize: 11, color: colors.textDim, marginLeft: 8 },
  ratingBadge: { backgroundColor: colors.warning + "20", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 8 },
  ratingText: { fontSize: 12, color: colors.warning, fontWeight: "600" },
  viewProductButton: { backgroundColor: colors.primary, borderRadius: 10, padding: 12, alignItems: "center", marginTop: 10 },
  viewProductText: { color: "#fff", fontWeight: "600", fontSize: 13 },
  // Weather card styles
  weatherCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  weatherTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  weatherCurrent: { flexDirection: "row", alignItems: "center", marginBottom: 12 },
  weatherIcon: { fontSize: 48, marginRight: 16 },
  weatherTemp: { fontSize: 32, fontWeight: "700", color: colors.text },
  weatherCondition: { fontSize: 14, color: colors.textMuted },
  weatherLocation: { fontSize: 14, color: colors.primary, fontWeight: "500" },
  weatherForecast: { flexDirection: "row", justifyContent: "space-between", marginTop: 12, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.border },
  forecastDay: { alignItems: "center" },
  forecastDayName: { fontSize: 11, color: colors.textMuted },
  forecastIcon: { fontSize: 20, marginVertical: 4 },
  forecastTemp: { fontSize: 12, fontWeight: "600", color: colors.text },
  // Flight stops badge
  flightStops: { fontSize: 11, color: colors.success, fontWeight: "500", backgroundColor: colors.success + "20", paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, alignSelf: "flex-start", marginTop: 4 },
  flightStopsNonstop: { color: colors.success, backgroundColor: colors.success + "20" },
  // Calendar add event form
  addEventForm: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginTop: 16, borderWidth: 1, borderColor: colors.border },
  eventInput: { backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 14, marginBottom: 12, fontSize: 14, color: colors.text, borderWidth: 1, borderColor: colors.border },
  eventFormButtons: { flexDirection: "row", justifyContent: "flex-end", gap: 12 },
  cancelButton: { paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, backgroundColor: colors.bgCardLight },
  cancelButtonText: { color: colors.text, fontWeight: "600" },
  saveButton: { paddingHorizontal: 20, paddingVertical: 12, borderRadius: 12, backgroundColor: colors.accent },
  saveButtonText: { color: colors.text, fontWeight: "600" },
  // Kayak-style travel UI
  inputRow: { flexDirection: "row", marginBottom: 10 },
  filtersRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 12 },
  filterChip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20, backgroundColor: colors.bgCardLight, borderWidth: 1, borderColor: colors.border },
  filterChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  filterChipText: { fontSize: 12, color: colors.text, fontWeight: "500" },
  filterChipTextActive: { color: "#fff" },
  // Price analysis card
  priceAnalysisCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.success + "40" },
  priceAnalysisTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  priceAnalysisRow: { flexDirection: "row", justifyContent: "space-around", marginBottom: 12 },
  priceAnalysisItem: { alignItems: "center" },
  priceAnalysisLabel: { fontSize: 11, color: colors.textMuted },
  priceAnalysisValue: { fontSize: 18, fontWeight: "700", color: colors.success, marginTop: 2 },
  priceRecommendation: { fontSize: 12, color: colors.primary, textAlign: "center", fontStyle: "italic" },
  // Date picker styles
  datePickerButton: { justifyContent: "center" },
  datePickerText: { fontSize: 14, color: colors.text },
  datePickerPlaceholder: { fontSize: 14, color: colors.textMuted },
  datePickerDone: { backgroundColor: colors.primary, borderRadius: 10, padding: 12, alignItems: "center", marginTop: 8 },
  datePickerDoneText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  // Travel weather
  travelWeather: { marginBottom: 8 },
  travelWeatherDate: { fontSize: 12, color: colors.primary, fontWeight: "600", marginBottom: 8 },
  forecastDayHighlight: { backgroundColor: colors.primary + "20", borderRadius: 8, padding: 4 },
  // Enhanced flight card
  flightCardBestDeal: { borderColor: colors.success, borderWidth: 2 },
  dealBadgeText: { fontSize: 11, color: colors.warning, fontWeight: "700" },
  flightBaggage: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
  flightPriceContainer: { alignItems: "flex-end" },
  flightScore: { fontSize: 10, color: colors.textMuted, marginTop: 2 },
  flightDetails: { flexDirection: "row", alignItems: "center", gap: 12, marginBottom: 12 },
  flightLayover: { fontSize: 11, color: colors.textDim },
  // Document upload styles
  uploadButtons: { flexDirection: "row", justifyContent: "space-around", marginVertical: 16 },
  uploadButton: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 20, alignItems: "center", width: "45%", borderWidth: 1, borderColor: colors.border },
  uploadButtonIcon: { fontSize: 32, marginBottom: 8 },
  uploadButtonText: { fontSize: 14, fontWeight: "600", color: colors.text },
  loadingCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 24, alignItems: "center", marginVertical: 16 },
  loadingText: { fontSize: 14, color: colors.textMuted, marginTop: 12 },
  documentCard: { flexDirection: "row", backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  documentIcon: { width: 44, height: 44, borderRadius: 10, backgroundColor: colors.bgCardLight, justifyContent: "center", alignItems: "center", marginRight: 12 },
  documentInfo: { flex: 1 },
  documentName: { fontSize: 14, fontWeight: "600", color: colors.text },
  documentType: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
  documentSummary: { fontSize: 12, color: colors.textDim, marginTop: 4 },
  emptyText: { fontSize: 14, color: colors.textMuted, textAlign: "center", paddingVertical: 20 },
  // Settings styles
  settingsSection: { marginBottom: 24 },
  settingsSubtext: { fontSize: 12, color: colors.textMuted, marginBottom: 12 },
  accountCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 20, borderWidth: 1, borderColor: colors.border },
  accountName: { fontSize: 18, fontWeight: "700", color: colors.text },
  accountRole: { fontSize: 14, color: colors.primary, marginTop: 4, textTransform: "capitalize" },
  logoutButton: { backgroundColor: colors.danger, borderRadius: 10, padding: 12, alignItems: "center", marginTop: 16 },
  logoutButtonText: { color: "#fff", fontWeight: "600", fontSize: 14 },
  loginButton: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center" },
  loginButtonText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  toggleRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", backgroundColor: colors.bgCard, padding: 14, borderRadius: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  toggleLabel: { fontSize: 14, fontWeight: "500", color: colors.text },
  toggleSwitch: { width: 50, height: 28, borderRadius: 14, backgroundColor: colors.bgCardLight, padding: 2, justifyContent: "center" },
  toggleSwitchActive: { backgroundColor: colors.success },
  toggleKnob: { width: 24, height: 24, borderRadius: 12, backgroundColor: "#fff" },
  toggleKnobActive: { alignSelf: "flex-end" },
  aboutText: { fontSize: 16, fontWeight: "600", color: colors.text },
  aboutVersion: { fontSize: 12, color: colors.textMuted, marginTop: 4 },
  // Login modal styles
  loginModal: { flex: 1, backgroundColor: "rgba(0,0,0,0.8)", justifyContent: "center", padding: 20 },
  loginCard: { backgroundColor: colors.bg, borderRadius: 20, padding: 24 },
  loginTitle: { fontSize: 24, fontWeight: "700", color: colors.text, textAlign: "center", marginBottom: 8 },
  loginSubtitle: { fontSize: 14, color: colors.textMuted, textAlign: "center", marginBottom: 24 },
  loginInput: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 16, fontSize: 16, color: colors.text, marginBottom: 12, borderWidth: 1, borderColor: colors.border },
  loginSubmit: { backgroundColor: colors.primary, borderRadius: 12, padding: 16, alignItems: "center", marginTop: 8 },
  loginSubmitText: { color: "#fff", fontWeight: "600", fontSize: 16 },
  forgotLink: { color: colors.primary, fontSize: 14, fontWeight: "600", textAlign: "center", marginTop: 14 },
  resetInfo: { fontSize: 13, color: colors.success, marginBottom: 12, textAlign: "center" },
  loginCancel: { padding: 16, alignItems: "center" },
  loginCancelText: { color: colors.textMuted, fontSize: 14 },
  // Stock modal styles
  stockModal: { flex: 1, backgroundColor: colors.bg },
  stockModalHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", padding: 20, borderBottomWidth: 1, borderBottomColor: colors.border },
  stockModalSymbol: { fontSize: 24, fontWeight: "700", color: colors.text },
  stockModalPrice: { fontSize: 32, fontWeight: "700", color: colors.text, marginTop: 20, textAlign: "center" },
  stockModalChange: { fontSize: 18, textAlign: "center", marginTop: 8 },
  stockChartContainer: { height: 200, backgroundColor: colors.bgCard, marginVertical: 20, borderRadius: 12, justifyContent: "center", alignItems: "center" },
  stockChartPlaceholder: { fontSize: 14, color: colors.textMuted },
  analysisCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, margin: 16, borderWidth: 1, borderColor: colors.border },
  analysisTitle: { fontSize: 16, fontWeight: "600", color: colors.text, marginBottom: 12 },
  analysisRow: { flexDirection: "row", justifyContent: "space-between", marginBottom: 8 },
  analysisLabel: { fontSize: 14, color: colors.textMuted },
  analysisValue: { fontSize: 14, fontWeight: "600", color: colors.text },
  aiSummary: { fontSize: 14, color: colors.text, lineHeight: 20, marginTop: 8 },
  recommendationBadge: { alignSelf: "flex-start", paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, marginTop: 12 },
  recommendationText: { fontSize: 14, fontWeight: "600" },
  // AI Shopping recommendation styles
  aiRecommendationCard: { backgroundColor: colors.success + "15", borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.success + "40" },
  aiRecTitle: { fontSize: 16, fontWeight: "700", color: colors.success, marginBottom: 8 },
  aiRecBestRetailer: { fontSize: 14, color: colors.text, marginBottom: 8 },
  aiRecHighlight: { fontWeight: "700", color: colors.success },
  aiRecText: { fontSize: 13, color: colors.textMuted, lineHeight: 20, marginBottom: 8 },
  aiRecActions: { marginTop: 8 },
  aiRecAction: { fontSize: 12, color: colors.success, marginBottom: 4 },
  // Smart shopping card styles
  bestDealCard: { borderColor: colors.success, borderWidth: 2 },
  bestDealBadge: { fontSize: 11, fontWeight: "700", color: colors.success, marginBottom: 8 },
  productRetailer: { fontSize: 16, fontWeight: "700", color: colors.text },
  originalPrice: { fontSize: 14, color: colors.textMuted, textDecorationLine: "line-through", marginLeft: 8 },
  savingsText: { fontSize: 12, color: colors.success, fontWeight: "600", marginTop: 4 },
  cashbackText: { fontSize: 12, color: colors.primary, marginTop: 2 },
  productShipping: { fontSize: 12, color: colors.textMuted },
  benefitsText: { fontSize: 11, color: colors.textDim, marginTop: 4, fontStyle: "italic" },
  // Family profiles & oversight
  profileChips: { flexDirection: "row", marginBottom: 12 },
  profileChip: { backgroundColor: colors.bgCard, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8, marginRight: 8, borderWidth: 1, borderColor: colors.border },
  profileChipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  profileChipText: { fontSize: 13, color: colors.textMuted, fontWeight: "500" },
  profileChipTextActive: { color: "#fff" },
  addMemberBtn: { backgroundColor: colors.primary, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 7 },
  addMemberBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  addMemberCard: { backgroundColor: colors.bgCardLight, borderRadius: 16, padding: 16, marginBottom: 16, borderWidth: 1, borderColor: colors.border },
  memberCard: { backgroundColor: colors.bgCard, borderRadius: 16, padding: 16, marginBottom: 12, borderWidth: 1, borderColor: colors.border, ...cardShadow },
  memberName: { fontSize: 16, fontWeight: "700", color: colors.text },
  memberStatBox: { flex: 1, borderRadius: 12, padding: 12 },
  memberStatTitle: { fontSize: 12, fontWeight: "600", color: colors.textMuted, marginBottom: 4 },
  memberStatValue: { fontSize: 18, fontWeight: "700", color: colors.text },
});
