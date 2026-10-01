import { useState, useEffect } from 'react'
import { ShoppingCart, Search, TrendingDown, Star, ExternalLink, Plus, Trash2, RefreshCw, Apple, Package, Loader2, CheckCircle, AlertCircle, MessageCircle, Send, Sparkles, Zap, CreditCard, Tag, Heart, Clock } from 'lucide-react'
import config from '../config'
import client from '../api/client'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  options?: string[]
  searchReady?: boolean
  refinedQuery?: {
    product: string
    budget?: string
    features?: string[]
    brand?: string
    useCase?: string
  }
}

interface Product {
  name: string
  price: number
  original_price?: number
  rating: number
  reviews: number
  url: string
  image_url?: string
  source: string
  in_stock: boolean
}

interface ListItem {
  id: string
  name: string
  quantity: number
  unit: string
  category: string
  checked: boolean
  priceEstimate?: number
  lastPrice?: number
}

interface PriceCheck {
  item: string
  // Retailer search links only — no fabricated prices until a real
  // price source is wired in. `price` stays optional for that future.
  prices: { store: string; price?: number; url: string }[]
  bestDeal?: string
}

export default function Shopping() {
  const [activeTab, setActiveTab] = useState<'search' | 'grocery' | 'shopping' | 'deals' | 'wishlist'>('deals')
  const [wishlist, setWishlist] = useState<any[]>([])
  const [wishlistLoading, setWishlistLoading] = useState(false)
  const [newWishItem, setNewWishItem] = useState('')
  const [newWishTarget, setNewWishTarget] = useState('')
  const [wishAnalysis, setWishAnalysis] = useState<Record<string, any>>({})
  const [analyzingId, setAnalyzingId] = useState<string | null>(null)

  const [wishlistError, setWishlistError] = useState('')
  const [wishCurrency, setWishCurrency] = useState<'USD' | 'INR'>('USD')
  const fetchWishlist = async () => {
    setWishlistLoading(true); setWishlistError('')
    try { const { data } = await client.get('/api/shopping/wishlist'); setWishlist(data.items || []) }
    catch { setWishlistError('Wishlist could not load. Please retry.') }
    finally { setWishlistLoading(false) }
  }
  const addWishItem = async () => {
    if (!newWishItem.trim()) return
    setWishlistError('')
    try {
      await client.post('/api/shopping/wishlist', { name: newWishItem.trim(), currency: wishCurrency,
        target_price: newWishTarget ? Number(newWishTarget) : null })
      setNewWishItem(''); setNewWishTarget(''); await fetchWishlist()
    } catch { setWishlistError('Could not save this item. Check its target price and try again.') }
  }
  const removeWishItem = async (id: string) => {
    try { await client.delete(`/api/shopping/wishlist/${id}`); setWishlist(prev => prev.filter(w => w.id !== id)) }
    catch { setWishlistError('Could not remove this item. Please retry.') }
  }
  const deepAnalyzeWish = async (id: string) => {
    setAnalyzingId(id)
    try { const { data } = await client.get(`/api/shopping/wishlist/${id}/analysis`); setWishAnalysis(prev => ({ ...prev, [id]: data.analysis })) }
    catch { setWishlistError('Analysis is unavailable. Please retry.') }
    finally { setAnalyzingId(null) }
  }

  useEffect(() => {
    if (activeTab === 'wishlist') fetchWishlist()
  }, [activeTab])
  const [deals, setDeals] = useState<any[]>([])
  const [dealsLoading, setDealsLoading] = useState(false)
  const [dealSearch, setDealSearch] = useState('')
  const [creditCards, setCreditCards] = useState<any>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState('')

  const fetchDeals = async (query?: string) => {
    setDealsLoading(true)
    try {
      const url = query
        ? `${config.apiBase}/api/portfolio/deals/latest?query=${encodeURIComponent(query)}`
        : `${config.apiBase}/api/portfolio/deals/latest`
      const res = await fetch(url)
      const data = await res.json()
      if (data.success) setDeals(data.deals || [])
    } catch (e) { console.error('Deals error:', e) }
    setDealsLoading(false)
  }

  const fetchCreditCards = async () => {
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/deals/credit-cards?category=travel`)
      const data = await res.json()
      if (data.success) setCreditCards(data)
    } catch {}
  }

  useEffect(() => { fetchDeals(); fetchCreditCards() }, [])

  // Grocery List State
  const [groceryList, setGroceryList] = useState<ListItem[]>([])
  const [newGroceryItem, setNewGroceryItem] = useState('')
  const [groceryQuantity, setGroceryQuantity] = useState('1')

  // Shopping List State
  const [shoppingList, setShoppingList] = useState<ListItem[]>([])
  const [newShoppingItem, setNewShoppingItem] = useState('')
  const [shoppingQuantity, setShoppingQuantity] = useState('1')

  // Price Check State
  const [priceChecks, setPriceChecks] = useState<PriceCheck[]>([])
  const [checkingPrices, setCheckingPrices] = useState(false)

  // AI Search State
  const [searchPreferences, setSearchPreferences] = useState({
    maxPrice: '',
    minRating: '4.0',
    preferredStores: [] as string[],
    lookingFor: '' // e.g., "best value", "premium", "budget"
  })

  // AI Conversation State
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [isAIMode, setIsAIMode] = useState(true)
  const [conversationStep, setConversationStep] = useState(0)
  const [refinedSearch, setRefinedSearch] = useState<{
    product: string
    budget?: string
    features?: string[]
    brand?: string
    useCase?: string
  } | null>(null)

  // Parse constraints the user already stated so we don't re-ask them.
  const parseStatedConstraints = (query: string) => {
    const q = query.toLowerCase()
    let budget: string | undefined
    const m = q.match(/(?:under|below|less than|max(?:imum)?|up to|within|budget(?:\s+of)?)\s*\$?\s*(\d[\d,]*)/)
      || q.match(/\$\s*(\d[\d,]*)\s*(?:or less|max|budget|limit)/)
    if (m) budget = m[1].replace(/,/g, '')

    let useCase: string | undefined
    const u = q.match(/\bfor\s+((?!under\b|below\b|less\b|around\b|about\b|\$)[a-z0-9][a-z0-9\s\-]{1,40}?)(?=\s+(?:under|below|less|around|about|with|that|which|and|or)\b|[,.!?]|$)/)
    if (u) useCase = u[1].trim()

    return { budget, useCase }
  }

  // AI conversation logic
  const startAIConversation = (query: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: query,
      timestamp: new Date()
    }
    setChatMessages([userMsg])

    // Honor budget/use-case already stated in the query — skip those steps.
    const { budget, useCase } = parseStatedConstraints(query)
    const seed: typeof refinedSearch = { product: query, budget, useCase }
    setRefinedSearch(seed)
    if (budget) setSearchPreferences(prev => ({ ...prev, maxPrice: budget }))

    // Step 1 asks budget, step 2 asks use case, step 3 asks brand.
    const nextStep = !budget ? 1 : !useCase ? 2 : 3
    setConversationStep(nextStep)

    setTimeout(() => {
      const aiResponse = generateAIResponse(query, nextStep)
      setChatMessages(prev => [...prev, aiResponse])
    }, 500)
  }

  const generateAIResponse = (query: string, step: number): ChatMessage => {
    const lowerQuery = query.toLowerCase()

    // Detect product category
    const isElectronics = /projector|laptop|tv|phone|tablet|camera|headphone|speaker|monitor/.test(lowerQuery)
    const isAppliance = /washer|dryer|refrigerator|microwave|oven|dishwasher|vacuum/.test(lowerQuery)

    if (step === 1) {
      // Ask about budget
      return {
        id: Date.now().toString(),
        role: 'assistant',
        content: `I'd be happy to help you find the perfect ${query}! To narrow down the best options for you, what's your budget range?`,
        timestamp: new Date(),
        options: ['Under $100', '$100-$300', '$300-$500', '$500-$1000', 'Over $1000', 'No budget limit']
      }
    } else if (step === 2) {
      // Ask about use case
      if (isElectronics) {
        return {
          id: Date.now().toString(),
          role: 'assistant',
          content: 'What will you primarily use this for?',
          timestamp: new Date(),
          options: ['Home entertainment', 'Work/Office', 'Gaming', 'Outdoor/Travel', 'Professional use', 'Gift']
        }
      } else if (isAppliance) {
        return {
          id: Date.now().toString(),
          role: 'assistant',
          content: 'What size/capacity do you need?',
          timestamp: new Date(),
          options: ['Compact/Small', 'Medium/Standard', 'Large/Family-size', 'Not sure']
        }
      } else {
        return {
          id: Date.now().toString(),
          role: 'assistant',
          content: 'What features are most important to you?',
          timestamp: new Date(),
          options: ['Best value', 'Top rated', 'Premium quality', 'Budget friendly', 'Latest model']
        }
      }
    } else if (step === 3) {
      // Ask about brand preference — free text allowed via the chat input
      return {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Do you have any brand preferences? Pick one, or type a specific brand name.',
        timestamp: new Date(),
        options: ['No preference', 'Top brands only', 'Open to lesser-known brands for value']
      }
    } else {
      // Ready to search
      return {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Perfect! I've refined your search based on your preferences. Ready to find the best ${refinedSearch?.product || query} options for you!`,
        timestamp: new Date(),
        searchReady: true,
        refinedQuery: refinedSearch || { product: query }
      }
    }
  }

  const handleChatResponse = (response: string) => {
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: response,
      timestamp: new Date()
    }
    setChatMessages(prev => [...prev, userMsg])

    // Update refined search based on conversation
    const newStep = conversationStep + 1
    setConversationStep(newStep)

    // Parse budget from response — accept typed amounts too ("$150", "150")
    if (conversationStep === 1) {
      let maxPrice = ''
      if (response.includes('Under $100')) maxPrice = '100'
      else if (response.includes('$100-$300')) maxPrice = '300'
      else if (response.includes('$300-$500')) maxPrice = '500'
      else if (response.includes('$500-$1000')) maxPrice = '1000'
      else if (response.includes('Over $1000')) maxPrice = '5000'
      else if (!response.includes('No budget')) {
        const typed = response.replace(/,/g, '').match(/\$?\s*(\d+)/)
        if (typed) maxPrice = typed[1]
      }

      setRefinedSearch(prev => ({ ...prev, product: searchQuery, budget: maxPrice }))
      setSearchPreferences(prev => ({ ...prev, maxPrice }))
    } else if (conversationStep === 2) {
      setRefinedSearch(prev => ({ ...prev!, useCase: response }))
    } else if (conversationStep === 3) {
      // Free-text brand names are stored verbatim; canned options map to filters
      const brand = ['No preference', 'Top brands only', 'Open to lesser-known brands for value'].includes(response)
        ? response
        : response.trim()
      setRefinedSearch(prev => ({ ...prev!, brand }))
    }

    // Generate next AI response
    setTimeout(() => {
      const aiResponse = generateAIResponse(searchQuery, newStep)
      setChatMessages(prev => [...prev, aiResponse])
    }, 500)
  }

  const executeRefinedSearch = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${config.apiBase}/api/shopping/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: refinedSearch?.product || searchQuery,
          max_price: searchPreferences.maxPrice ? parseFloat(searchPreferences.maxPrice) : 5000,
          min_rating: parseFloat(searchPreferences.minRating),
          preferred_stores: searchPreferences.preferredStores,
          search_type: searchPreferences.lookingFor,
          use_case: refinedSearch?.useCase,
          brand_preference: refinedSearch?.brand
        })
      })
      const data = await response.json()
      if (data.success && Array.isArray(data.products) && data.products.length > 0) {
        setProducts(data.products)
        setError('')
      } else {
        setProducts([])
        setError(`No products found for "${refinedSearch?.product || searchQuery}". Try broadening the budget or removing filters.`)
      }
    } catch (error) {
      console.error('Search failed:', error)
      setError('Search failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const resetConversation = () => {
    setChatMessages([])
    setConversationStep(0)
    setRefinedSearch(null)
    setSearchQuery('')
    setProducts([])
  }

  // Load lists from localStorage
  useEffect(() => {
    const savedGrocery = localStorage.getItem('groceryList')
    const savedShopping = localStorage.getItem('shoppingList')
    if (savedGrocery) setGroceryList(JSON.parse(savedGrocery))
    if (savedShopping) setShoppingList(JSON.parse(savedShopping))
  }, [])

  // Save lists to localStorage
  useEffect(() => {
    localStorage.setItem('groceryList', JSON.stringify(groceryList))
  }, [groceryList])

  useEffect(() => {
    localStorage.setItem('shoppingList', JSON.stringify(shoppingList))
  }, [shoppingList])

  const stores = ['Amazon', 'Walmart', 'Target', 'Best Buy', 'Costco', 'Home Depot']

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setError('Please enter a search query')
      return
    }

    try {
      setLoading(true)
      setError('')
      const response = await fetch(`${config.apiBase}/api/shopping/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          max_price: searchPreferences.maxPrice ? parseFloat(searchPreferences.maxPrice) : 5000,
          min_rating: parseFloat(searchPreferences.minRating),
          preferred_stores: searchPreferences.preferredStores,
          search_type: searchPreferences.lookingFor
        })
      })
      const data = await response.json()
      if (data.success && Array.isArray(data.products) && data.products.length > 0) {
        setProducts(data.products)
        setError('')
      } else {
        setProducts([])
        setError(`No products found for "${searchQuery}". Try a broader term or raise the max price.`)
      }
    } catch (error) {
      console.error('Search failed:', error)
      setError('Search failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const clampQuantity = (raw: string): number => {
    const n = parseInt(raw, 10)
    if (isNaN(n) || n < 1) return 1
    return Math.min(n, 999)
  }

  const addToGroceryList = () => {
    const name = newGroceryItem.trim()
    if (!name || name.length > 120) return
    const newItem: ListItem = {
      id: Date.now().toString(),
      name,
      quantity: clampQuantity(groceryQuantity),
      unit: 'items',
      category: 'General',
      checked: false
    }
    setGroceryList([...groceryList, newItem])
    setNewGroceryItem('')
    setGroceryQuantity('1')
  }

  const addToShoppingList = () => {
    const name = newShoppingItem.trim()
    if (!name || name.length > 120) return
    const newItem: ListItem = {
      id: Date.now().toString(),
      name,
      quantity: clampQuantity(shoppingQuantity),
      unit: 'items',
      category: 'General',
      checked: false
    }
    setShoppingList([...shoppingList, newItem])
    setNewShoppingItem('')
    setShoppingQuantity('1')
  }

  const toggleItem = (list: 'grocery' | 'shopping', id: string) => {
    if (list === 'grocery') {
      setGroceryList(groceryList.map(item =>
        item.id === id ? { ...item, checked: !item.checked } : item
      ))
    } else {
      setShoppingList(shoppingList.map(item =>
        item.id === id ? { ...item, checked: !item.checked } : item
      ))
    }
  }

  const removeItem = (list: 'grocery' | 'shopping', id: string) => {
    if (list === 'grocery') {
      setGroceryList(groceryList.filter(item => item.id !== id))
    } else {
      setShoppingList(shoppingList.filter(item => item.id !== id))
    }
  }

  const clearChecked = (list: 'grocery' | 'shopping') => {
    if (list === 'grocery') {
      setGroceryList(groceryList.filter(item => !item.checked))
    } else {
      setShoppingList(shoppingList.filter(item => !item.checked))
    }
  }

  const checkPrices = async (list: 'grocery' | 'shopping') => {
    setCheckingPrices(true)
    const items = list === 'grocery' ? groceryList : shoppingList
    const uncheckedItems = items.filter(item => !item.checked)

    // No verified grocery price feed yet — provide plainly labeled retailer
    // search links instead of fabricated prices or a "Best" badge.
    const checks: PriceCheck[] = uncheckedItems.map(item => ({
      item: item.name,
      prices: [
        { store: 'Amazon', url: `https://amazon.com/s?k=${encodeURIComponent(item.name)}` },
        { store: 'Walmart', url: `https://walmart.com/search?q=${encodeURIComponent(item.name)}` },
        { store: 'Target', url: `https://target.com/s?searchTerm=${encodeURIComponent(item.name)}` }
      ]
    }))

    setPriceChecks(checks)
    setCheckingPrices(false)
  }

  // Strip HTML tags/entities from feed-sourced deal text before rendering
  const sanitizeDealText = (s: string): string =>
    (s || '')
      .replace(/<[^>]*>/g, ' ')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-pink-600 rounded-xl flex items-center justify-center">
            <ShoppingCart className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">AI Smart Shopping</h1>
            <p className="text-gray-600">Find deals, manage lists, and save money</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-8 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('search')}
          className={`px-6 py-3 font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
            activeTab === 'search'
              ? 'bg-purple-100 text-purple-700 border-b-2 border-purple-600'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Search size={18} /> Product Search
        </button>
        <button
          onClick={() => setActiveTab('grocery')}
          className={`px-6 py-3 font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
            activeTab === 'grocery'
              ? 'bg-green-100 text-green-700 border-b-2 border-green-600'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Apple size={18} /> Grocery List ({groceryList.length})
        </button>
        <button
          onClick={() => setActiveTab('shopping')}
          className={`px-6 py-3 font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
            activeTab === 'shopping'
              ? 'bg-blue-100 text-blue-700 border-b-2 border-blue-600'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Package size={18} /> Shopping List ({shoppingList.length})
        </button>
        <button
          onClick={() => setActiveTab('deals')}
          className={`px-6 py-3 font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
            activeTab === 'deals'
              ? 'bg-orange-100 text-orange-700 border-b-2 border-orange-600'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Zap size={18} /> Hot Deals ({deals.length})
        </button>
        <button
          onClick={() => setActiveTab('wishlist')}
          className={`px-6 py-3 font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
            activeTab === 'wishlist'
              ? 'bg-pink-100 text-pink-700 border-b-2 border-pink-600'
              : 'text-gray-600 hover:bg-gray-100'
          }`}
        >
          <Heart size={18} /> Wishlist ({wishlist.length})
        </button>
      </div>

      {/* Wishlist Tab */}
      {activeTab === 'wishlist' && (
        <div className="space-y-6">
          {wishlistError && <p role="alert" className="text-red-600">{wishlistError}</p>}
          <label>Wishlist currency <select value={wishCurrency} onChange={e => setWishCurrency(e.target.value as 'USD' | 'INR')} className="border rounded p-2"><option value="USD">USD</option><option value="INR">INR</option></select></label>
          {/* Add item */}
          <div className="flex gap-3">
            <input
              type="text"
              value={newWishItem}
              onChange={e => setNewWishItem(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addWishItem()}
              placeholder="Add item to wishlist (e.g. Mac Mini, AirPods Pro...)"
              className="flex-1 px-4 py-3 rounded-xl border border-gray-200 focus:border-pink-400 focus:ring-2 focus:ring-pink-100 outline-none"
            />
            <input
              type="number"
              value={newWishTarget}
              onChange={e => setNewWishTarget(e.target.value)}
              aria-label="Target price"
              min="0"
              step="0.01"
              placeholder={`Target ${wishCurrency === 'INR' ? '₹' : '$'}`}
              className="w-28 px-3 py-3 rounded-xl border border-gray-200 focus:border-pink-400 outline-none"
            />
            <button onClick={addWishItem} className="px-5 py-3 bg-pink-600 text-white rounded-xl font-semibold hover:bg-pink-700 flex items-center gap-2">
              <Plus size={16} /> Add
            </button>
            <button onClick={fetchWishlist} className="px-4 py-3 bg-gray-100 text-gray-600 rounded-xl hover:bg-gray-200">
              <RefreshCw size={16} className={wishlistLoading ? 'animate-spin' : ''} />
            </button>
          </div>

          {wishlist.length === 0 && !wishlistLoading && (
            <div className="text-center py-16 text-gray-500">
              <Heart size={40} className="mx-auto mb-3 text-pink-300" />
              <p className="font-medium">Your wishlist is empty</p>
              <p className="text-sm">Add items like “Mac Mini” to track deals and price-drop opportunities</p>
            </div>
          )}

          <div className="grid gap-4">
            {wishlist.map(item => {
              const a = item.analysis
              const deep = wishAnalysis[item.id]
              const scoreColor = a?.deal_score >= 85 ? 'text-green-600 bg-green-50' : a?.deal_score >= 60 ? 'text-emerald-600 bg-emerald-50' : a?.deal_score >= 30 ? 'text-amber-600 bg-amber-50' : 'text-red-600 bg-red-50'
              return (
                <div key={item.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-bold text-gray-900 text-lg capitalize">{item.name}</h3>
                      {item.target_price && (
                        <p className="text-sm text-gray-500">Target: {new Intl.NumberFormat(undefined, { style: 'currency', currency: item.currency || 'USD' }).format(item.target_price)}{a?.target_price_hit && <span className="ml-2 text-green-600 font-semibold">✓ Target hit!</span>}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {a && (
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${scoreColor}`}>
                          Deal score {a.deal_score}/100
                        </span>
                      )}
                      <button onClick={() => removeWishItem(item.id)} className="p-2 text-gray-400 hover:text-red-500">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>

                  {a && (
                    <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-gray-500">Current Price</p>
                        <p className="font-bold text-gray-900">${a.current_price?.toFixed(2)}</p>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-gray-500">All-Time Low</p>
                        <p className="font-bold text-green-700">${a.all_time_low?.toFixed(2)}</p>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-gray-500 flex items-center gap-1"><TrendingDown size={12} /> Drop Potential</p>
                        <p className="font-bold text-gray-900">{a.potential_further_drop_pct}%</p>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-3">
                        <p className="text-gray-500 flex items-center gap-1"><Clock size={12} /> Next Sale</p>
                        <p className="font-semibold text-gray-900 text-xs">{a.next_sale_event}</p>
                      </div>
                    </div>
                  )}

                  {a && (
                    <p className="mt-3 text-sm text-gray-700"><span className="font-semibold">Recommendation:</span> {a.recommendation}</p>
                  )}

                  <div className="mt-3 flex items-center gap-3">
                    <button
                      onClick={() => deepAnalyzeWish(item.id)}
                      disabled={analyzingId === item.id}
                      className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-semibold hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
                    >
                      {analyzingId === item.id ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                      Check price evidence
                    </button>
                    {a?.market_cycle_note && (
                      <p className="text-xs text-gray-500 flex-1">{a.market_cycle_note}</p>
                    )}
                  </div>

                  {deep?.ai_market_research && (
                    <div className="mt-3 bg-purple-50 border border-purple-100 rounded-lg p-4 text-sm text-gray-800 whitespace-pre-wrap">
                      {deep.ai_market_research}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Deals Tab */}
      {activeTab === 'deals' && (
        <div className="space-y-6">
          {/* Deal Search */}
          <div className="flex gap-3">
            <div className="flex-1 relative">
              <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={dealSearch}
                onChange={e => setDealSearch(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchDeals(dealSearch || undefined)}
                placeholder="Search deals (laptop, TV, headphones...)"
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:border-orange-400 focus:ring-2 focus:ring-orange-100 outline-none"
              />
            </div>
            <button onClick={() => fetchDeals(dealSearch || undefined)} className="px-5 py-3 bg-orange-600 text-white rounded-xl font-semibold hover:bg-orange-700 flex items-center gap-2">
              <Search size={16} /> Search
            </button>
            <button onClick={() => { setDealSearch(''); fetchDeals() }} className="px-4 py-3 bg-gray-100 text-gray-600 rounded-xl hover:bg-gray-200">
              <RefreshCw size={16} />
            </button>
          </div>

          {/* Credit Card Points */}
          {creditCards && (
            <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border border-indigo-200 p-5">
              <div className="flex items-center gap-2 mb-3">
                <CreditCard size={20} className="text-indigo-600" />
                <h3 className="font-bold text-indigo-800">Best Credit Cards for Deals & Travel</h3>
              </div>
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-3">
                {(creditCards.cards || []).map((card: any, i: number) => (
                  <div key={i} className="bg-white rounded-lg p-3 border border-indigo-100">
                    <div className="font-semibold text-sm text-gray-800">{card.card}</div>
                    <div className="text-xs text-indigo-600 font-medium mt-1">{card.earn}</div>
                    <div className="text-xs text-gray-500 mt-1">{card.best_for}</div>
                    <div className="text-xs text-gray-400 mt-1">Fee: {card.annual_fee}</div>
                  </div>
                ))}
              </div>
              {creditCards.flight_tips?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-indigo-200">
                  <div className="text-xs font-semibold text-indigo-700 mb-2">Points Pro Tips</div>
                  <div className="grid md:grid-cols-2 gap-1">
                    {creditCards.flight_tips.slice(0, 4).map((tip: string, i: number) => (
                      <div key={i} className="text-xs text-indigo-600 flex items-start gap-1">
                        <span className="text-indigo-400 mt-0.5">*</span> {tip}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Deals List */}
          {dealsLoading ? (
            <div className="text-center py-12">
              <Loader2 className="animate-spin mx-auto mb-3 text-orange-500" size={32} />
              <p className="text-gray-500">Crawling SlickDeals, DealNews, Reddit...</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-500">{deals.length} deals from 8 sources</span>
              </div>
              {deals.map((deal: any, i: number) => (
                <a
                  key={i}
                  href={deal.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-orange-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="font-semibold text-gray-800 line-clamp-2">{sanitizeDealText(deal.title)}</div>
                      {deal.description && <div className="text-sm text-gray-500 mt-1 line-clamp-2">{sanitizeDealText(deal.description)}</div>}
                    </div>
                    <div className="text-right shrink-0">
                      {deal.price && <div className="text-lg font-bold text-green-600">{deal.price}</div>}
                      <div className="flex items-center gap-1 mt-1">
                        <Tag size={12} className="text-orange-500" />
                        <span className="text-xs text-orange-600 font-medium">{deal.source}</span>
                      </div>
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        {deal.price ? 'Listed price' : 'Deal tip — price on site'}
                      </div>
                      {deal.score > 0 && <div className="text-xs text-gray-400 mt-0.5">{deal.score} upvotes</div>}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <ExternalLink size={12} className="text-blue-400" />
                    <span className="text-xs text-blue-500">View Deal</span>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Product Search Tab */}
      {activeTab === 'search' && (
        <>
          {/* Mode Toggle */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => { setIsAIMode(true); resetConversation(); }}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 ${isAIMode ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              <Sparkles size={16} /> AI Shopping Assistant
            </button>
            <button
              onClick={() => { setIsAIMode(false); resetConversation(); }}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 ${!isAIMode ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-700'}`}
            >
              <Search size={16} /> Quick Search
            </button>
          </div>

          {/* AI Conversation Mode */}
          {isAIMode && chatMessages.length === 0 && (
            <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-8 rounded-xl border border-purple-200 mb-8">
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-purple-600 rounded-full flex items-center justify-center mx-auto mb-4">
                  <MessageCircle className="text-white" size={32} />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">AI Shopping Assistant</h2>
                <p className="text-gray-600">Tell me what you're looking for and I'll help you find the perfect product</p>
              </div>
              <div className="relative">
                <input
                  type="text"
                  placeholder="I'm looking for a projector for my home theater..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && searchQuery.trim() && startAIConversation(searchQuery)}
                  className="w-full px-6 py-4 border-2 border-purple-300 rounded-xl focus:border-purple-500 focus:outline-none text-lg"
                />
                <button
                  onClick={() => searchQuery.trim() && startAIConversation(searchQuery)}
                  disabled={!searchQuery.trim()}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 bg-purple-600 text-white p-3 rounded-lg hover:bg-purple-700 disabled:opacity-50"
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
          )}

          {/* AI Conversation */}
          {isAIMode && chatMessages.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 mb-8 overflow-hidden">
              <div className="bg-purple-600 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <MessageCircle className="text-white" size={24} />
                  <span className="text-white font-semibold">Shopping Assistant</span>
                </div>
                <button onClick={resetConversation} className="text-white/80 hover:text-white text-sm">
                  Start New Search
                </button>
              </div>
              <div className="p-6 max-h-96 overflow-y-auto space-y-4">
                {chatMessages.map(msg => (
                  <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] p-4 rounded-xl ${
                      msg.role === 'user'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      <p>{msg.content}</p>
                      {msg.options && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {msg.options.map(opt => (
                            <button
                              key={opt}
                              onClick={() => handleChatResponse(opt)}
                              className="px-3 py-1.5 bg-white text-purple-700 rounded-full text-sm hover:bg-purple-50 border border-purple-200"
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      )}
                      {msg.searchReady && (
                        <button
                          onClick={executeRefinedSearch}
                          disabled={loading}
                          className="mt-4 w-full bg-green-600 text-white py-3 rounded-lg hover:bg-green-700 flex items-center justify-center gap-2"
                        >
                          {loading ? <><Loader2 className="animate-spin" size={16} /> Searching...</> : <><Search size={16} /> Find Products</>}
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {/* Free-text reply — needed for 'type a specific brand' etc. */}
              <div className="border-t border-gray-200 p-3 flex gap-2">
                <input
                  type="text"
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && chatInput.trim() && (handleChatResponse(chatInput.trim()), setChatInput(''))}
                  placeholder="Type your answer (e.g. a brand name, a budget)..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:border-purple-500 focus:outline-none text-sm"
                />
                <button
                  onClick={() => { if (chatInput.trim()) { handleChatResponse(chatInput.trim()); setChatInput('') } }}
                  disabled={!chatInput.trim()}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          )}

          {/* Quick Search Mode */}
          {!isAIMode && (
          <div className="bg-white p-6 rounded-xl border border-gray-200 mb-8">
            <div className="relative mb-4">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                placeholder="What are you looking for? (e.g., laptop, soundbar, projector...)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                className="w-full pl-12 pr-32 py-4 border-2 border-gray-200 rounded-xl focus:border-purple-500 focus:outline-none text-lg"
              />
              <button
                onClick={handleSearch}
                disabled={loading}
                className="absolute right-4 top-1/2 transform -translate-y-1/2 bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? <><Loader2 className="animate-spin" size={16} /> Searching...</> : 'Search'}
              </button>
            </div>

            {/* Search Filters */}
            <div className="grid md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Max Price</label>
                <input
                  type="number"
                  placeholder="Any"
                  value={searchPreferences.maxPrice}
                  onChange={(e) => setSearchPreferences({...searchPreferences, maxPrice: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Min Rating</label>
                <select
                  value={searchPreferences.minRating}
                  onChange={(e) => setSearchPreferences({...searchPreferences, minRating: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="3.0">3+ Stars</option>
                  <option value="3.5">3.5+ Stars</option>
                  <option value="4.0">4+ Stars</option>
                  <option value="4.5">4.5+ Stars</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Looking For</label>
                <select
                  value={searchPreferences.lookingFor}
                  onChange={(e) => setSearchPreferences({...searchPreferences, lookingFor: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">Any</option>
                  <option value="best_value">Best Value</option>
                  <option value="budget">Budget Friendly</option>
                  <option value="premium">Premium Quality</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Preferred Stores</label>
                <select
                  onChange={(e) => {
                    const store = e.target.value
                    if (store && !searchPreferences.preferredStores.includes(store)) {
                      setSearchPreferences({...searchPreferences, preferredStores: [...searchPreferences.preferredStores, store]})
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                >
                  <option value="">Add Store...</option>
                  {stores.map(store => (
                    <option key={store} value={store}>{store}</option>
                  ))}
                </select>
              </div>
            </div>

            {searchPreferences.preferredStores.length > 0 && (
              <div className="mt-3 flex gap-2 flex-wrap">
                {searchPreferences.preferredStores.map(store => (
                  <span key={store} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm flex items-center gap-1">
                    {store}
                    <button
                      onClick={() => setSearchPreferences({...searchPreferences, preferredStores: searchPreferences.preferredStores.filter(s => s !== store)})}
                      className="hover:text-purple-900"
                    >×</button>
                  </span>
                ))}
              </div>
            )}
          </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 flex items-center gap-2">
              <AlertCircle size={20} />
              {error}
            </div>
          )}

          {/* Product Results */}
          {products.length > 0 && (
            <div className="mb-8">
              <h2 className="text-2xl font-bold mb-4">Found {products.length} Products</h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {products.map((product, index) => (
                  <div key={index} className="bg-white rounded-xl border border-gray-200 overflow-hidden hover:shadow-lg transition-shadow">
                    {product.image_url && (
                      <div className="h-48 bg-gray-100 flex items-center justify-center">
                        <img src={product.image_url} alt={product.name} className="max-h-full max-w-full object-contain" />
                      </div>
                    )}
                    <div className="p-4">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-lg line-clamp-2 flex-1">{product.name}</h3>
                      </div>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs px-2 py-1 rounded bg-purple-100 text-purple-700 font-medium">
                          {(product as any).retailer || product.source}
                        </span>
                        <div className="flex items-center">
                          <Star className="text-yellow-400 fill-yellow-400" size={16} />
                          <span className="ml-1 text-sm font-medium">{product.rating}</span>
                        </div>
                        <span className="text-sm text-gray-500">({product.reviews})</span>
                      </div>
                      <div className="flex items-baseline gap-2 mb-3">
                        <span className="text-2xl font-bold text-green-600">${product.price.toFixed(2)}</span>
                        {product.original_price && product.original_price > product.price && (
                          <>
                            <span className="text-sm text-gray-500 line-through">${product.original_price.toFixed(2)}</span>
                            <span className="text-xs text-green-600 font-medium">Save ${(product.original_price - product.price).toFixed(2)}</span>
                          </>
                        )}
                      </div>
                      <div className="flex items-center justify-between mb-3">
                        <span className={`text-xs px-2 py-1 rounded ${product.in_stock ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                          {product.in_stock ? '✓ In Stock' : '✗ Out of Stock'}
                        </span>
                        {(product as any).source?.includes('Scraped') && (
                          <span className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">Real Price</span>
                        )}
                      </div>
                      <a
                        href={product.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-4 w-full bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 flex items-center justify-center gap-2"
                      >
                        View Product <ExternalLink size={16} />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Features when no search */}
          {products.length === 0 && !loading && (
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4">
                  <TrendingDown className="text-green-600" size={24} />
                </div>
                <h3 className="font-semibold text-lg mb-2">Price Tracking</h3>
                <p className="text-gray-600 text-sm">Track prices and get alerts when they drop</p>
              </div>
              <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                <div className="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center mb-4">
                  <Star className="text-yellow-600" size={24} />
                </div>
                <h3 className="font-semibold text-lg mb-2">Best Deals</h3>
                <p className="text-gray-600 text-sm">Curated deals from SlickDeals and more</p>
              </div>
              <div className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4">
                  <ExternalLink className="text-blue-600" size={24} />
                </div>
                <h3 className="font-semibold text-lg mb-2">Direct Links</h3>
                <p className="text-gray-600 text-sm">One-click access to purchase</p>
              </div>
            </div>
          )}
        </>
      )}

      {/* Grocery List Tab */}
      {activeTab === 'grocery' && (
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Apple className="text-green-600" size={24} /> Grocery List
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => checkPrices('grocery')}
                disabled={checkingPrices || groceryList.length === 0}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
              >
                {checkingPrices ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                Check Prices
              </button>
              <button
                onClick={() => clearChecked('grocery')}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 flex items-center gap-2"
              >
                <Trash2 size={16} /> Clear Checked
              </button>
            </div>
          </div>

          {/* Add Item Form */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              placeholder="Add grocery item (e.g., Milk, Bread, Eggs...)"
              value={newGroceryItem}
              onChange={(e) => setNewGroceryItem(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addToGroceryList()}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:border-green-500 focus:outline-none"
            />
            <input
              type="number"
              min="1"
              value={groceryQuantity}
              onChange={(e) => setGroceryQuantity(e.target.value)}
              className="w-20 px-3 py-3 border border-gray-300 rounded-lg"
            />
            <button
              onClick={addToGroceryList}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
            >
              <Plus size={18} /> Add
            </button>
          </div>

          {/* Grocery Items */}
          {groceryList.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Apple size={48} className="mx-auto mb-4 opacity-50" />
              <p>Your grocery list is empty. Add items above!</p>
            </div>
          ) : (
            <div className="space-y-2">
              {groceryList.map(item => (
                <div key={item.id} className={`flex items-center gap-4 p-4 rounded-lg border ${item.checked ? 'bg-gray-50 border-gray-200' : 'bg-white border-gray-200'}`}>
                  <button
                    onClick={() => toggleItem('grocery', item.id)}
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${item.checked ? 'bg-green-500 border-green-500' : 'border-gray-300'}`}
                  >
                    {item.checked && <CheckCircle size={16} className="text-white" />}
                  </button>
                  <span className={`flex-1 ${item.checked ? 'line-through text-gray-400' : ''}`}>
                    {item.name} <span className="text-gray-500">×{item.quantity}</span>
                  </span>
                  <button
                    onClick={() => removeItem('grocery', item.id)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Price Check Results */}
          {priceChecks.length > 0 && (
            <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
              <h3 className="font-semibold text-green-800 mb-3">💰 Price Comparison</h3>
              <div className="space-y-3">
                {priceChecks.map((check, idx) => (
                  <div key={idx} className="bg-white p-3 rounded-lg">
                    <p className="font-medium mb-2">{check.item}</p>
                    <div className="flex gap-2 flex-wrap">
                      {check.prices.map((p, i) => (
                        <a
                          key={i}
                          href={p.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="px-3 py-1 rounded text-sm bg-gray-100 text-gray-700 hover:bg-green-100 hover:text-green-700"
                        >
                          {p.store}{p.price != null ? `: $${p.price.toFixed(2)}` : ' — search prices'}
                        </a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Shopping List Tab */}
      {activeTab === 'shopping' && (
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2">
              <Package className="text-blue-600" size={24} /> Shopping List
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => checkPrices('shopping')}
                disabled={checkingPrices || shoppingList.length === 0}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {checkingPrices ? <Loader2 className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                Check Prices
              </button>
              <button
                onClick={() => clearChecked('shopping')}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 flex items-center gap-2"
              >
                <Trash2 size={16} /> Clear Checked
              </button>
            </div>
          </div>

          {/* Add Item Form */}
          <div className="flex gap-3 mb-6">
            <input
              type="text"
              placeholder="Add shopping item (e.g., Laptop, Headphones, Clothes...)"
              value={newShoppingItem}
              onChange={(e) => setNewShoppingItem(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addToShoppingList()}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
            />
            <input
              type="number"
              min="1"
              value={shoppingQuantity}
              onChange={(e) => setShoppingQuantity(e.target.value)}
              className="w-20 px-3 py-3 border border-gray-300 rounded-lg"
            />
            <button
              onClick={addToShoppingList}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
            >
              <Plus size={18} /> Add
            </button>
          </div>

          {/* Shopping Items */}
          {shoppingList.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Package size={48} className="mx-auto mb-4 opacity-50" />
              <p>Your shopping list is empty. Add items above!</p>
            </div>
          ) : (
            <div className="space-y-2">
              {shoppingList.map(item => (
                <div key={item.id} className={`flex items-center gap-4 p-4 rounded-lg border ${item.checked ? 'bg-gray-50 border-gray-200' : 'bg-white border-gray-200'}`}>
                  <button
                    onClick={() => toggleItem('shopping', item.id)}
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${item.checked ? 'bg-blue-500 border-blue-500' : 'border-gray-300'}`}
                  >
                    {item.checked && <CheckCircle size={16} className="text-white" />}
                  </button>
                  <span className={`flex-1 ${item.checked ? 'line-through text-gray-400' : ''}`}>
                    {item.name} <span className="text-gray-500">×{item.quantity}</span>
                  </span>
                  <button
                    onClick={() => removeItem('shopping', item.id)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
