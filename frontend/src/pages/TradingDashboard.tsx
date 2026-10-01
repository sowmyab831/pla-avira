import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Search, RefreshCw, BarChart3, Newspaper, Award,
  ArrowUpCircle, ArrowDownCircle, Target,
} from 'lucide-react'
import config from '../config'

// ─── Types ───────────────────────────────────────────────────────────────────

interface WatchlistStock {
  symbol: string
  price: number | null
  change: number | null
  changePct: number | null
  loading: boolean
}

interface ForecastData {
  success: boolean
  symbol: string
  current_price: number
  week52_high: number
  week52_low: number
  overall_rating: string
  bull_horizons: number
  rsi: number
  macd_signal: string
  forecasts: Record<string, HorizonForecast>
  price_history: PricePoint[]
}

interface HorizonForecast {
  forecast: number[]
  low_band: number[]
  high_band: number[]
  direction: string
  magnitude_pct: number
  target_price: number
  upside_pct: number
  method: string
  rsi?: number
  macd?: string
}

interface PricePoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface Recommendation {
  symbol: string
  composite_score: number
  rating: string
  scores: Record<string, number>
  price: number | null
  target_price: number | null
  pe_ratio: number | null
  sector: string | null
  market_cap: number | null
  earnings_growth: number | null
}

interface NewsArticle {
  source: string
  title: string
  url: string
  published: string
  summary: string
}

// ─── Constants ───────────────────────────────────────────────────────────────

const DEFAULT_WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'V', 'AMD']
const HORIZONS = [
  { key: '1h', label: '1 Hour' },
  { key: '1d', label: '1 Day' },
  { key: '1w', label: '1 Week' },
  { key: '1m', label: '1 Month' },
  { key: '3m', label: '3 Months' },
  { key: '1y', label: '1 Year' },
]

const RATING_COLORS: Record<string, string> = {
  'STRONG BUY': 'text-emerald-400',
  'BUY': 'text-green-400',
  'HOLD': 'text-yellow-400',
  'SELL': 'text-red-400',
  'STRONG SELL': 'text-red-500',
}

const RATING_BG: Record<string, string> = {
  'STRONG BUY': 'bg-emerald-500/20 border-emerald-500/40',
  'BUY': 'bg-green-500/20 border-green-500/40',
  'HOLD': 'bg-yellow-500/20 border-yellow-500/40',
  'SELL': 'bg-red-500/20 border-red-500/40',
  'STRONG SELL': 'bg-red-600/20 border-red-600/40',
}

function formatMarketCap(n: number | null): string {
  if (!n) return '—'
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n}`
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function TradingDashboard() {
  // State
  const [watchlist, setWatchlist] = useState<WatchlistStock[]>(
    DEFAULT_WATCHLIST.map(s => ({ symbol: s, price: null, change: null, changePct: null, loading: true }))
  )
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL')
  const [searchQuery, setSearchQuery] = useState('')
  const [activeHorizon, setActiveHorizon] = useState('1m')
  const [forecast, setForecast] = useState<ForecastData | null>(null)
  const [forecastLoading, setForecastLoading] = useState(false)
  const [recommendations, setRecommendations] = useState<Recommendation[]>([])
  const [recsLoading, setRecsLoading] = useState(false)
  const [news, setNews] = useState<NewsArticle[]>([])
  const [newsLoading, setNewsLoading] = useState(false)
  const [macro, setMacro] = useState<any>(null)
  const [activeTab, setActiveTab] = useState<'forecast' | 'news' | 'recommendations'>('forecast')
  const [intradayTargets, setIntradayTargets] = useState<any>(null)
  const [hoverInfo, setHoverInfo] = useState<{x: number, y: number, price: number, date: string} | null>(null)
  const chartRef = useRef<SVGSVGElement>(null)

  // ─── Data fetching ──────────────────────────────────────────────────────────

  const fetchWatchlistPrices = useCallback(async () => {
    const updated = await Promise.all(
      watchlist.map(async (stock) => {
        try {
          const res = await fetch(`${config.apiBase}/api/portfolio/stocks/${stock.symbol}/historical?period=1d&interval=1m`)
          const data = await res.json()
          if (data.success && data.prices?.length > 0) {
            const prices = data.prices
            const current = prices[prices.length - 1].close
            const first = prices[0].open
            return {
              ...stock,
              price: current,
              change: +(current - first).toFixed(2),
              changePct: +((current - first) / first * 100).toFixed(2),
              loading: false,
            }
          }
        } catch {}
        return { ...stock, loading: false }
      })
    )
    setWatchlist(updated)
  }, [watchlist.map(s => s.symbol).join(',')])

  const fetchForecast = useCallback(async (symbol: string) => {
    setForecastLoading(true)
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/forecast`)
      const data = await res.json()
      if (data.success) setForecast(data)
    } catch (e) { console.error('Forecast error:', e) }
    setForecastLoading(false)
  }, [])

  const fetchIntradayTargets = useCallback(async (symbol: string) => {
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/intraday-targets`)
      const data = await res.json()
      if (data.success) setIntradayTargets(data)
    } catch {}
  }, [])

  const fetchNews = useCallback(async (symbol?: string) => {
    setNewsLoading(true)
    try {
      const url = symbol
        ? `${config.apiBase}/api/portfolio/market/news?symbol=${symbol}`
        : `${config.apiBase}/api/portfolio/market/news`
      const res = await fetch(url)
      const data = await res.json()
      if (data.success) setNews(data.articles || [])
    } catch {}
    setNewsLoading(false)
  }, [])

  const fetchRecommendations = useCallback(async () => {
    setRecsLoading(true)
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/market/recommendations?count=20`)
      const data = await res.json()
      if (data.success) setRecommendations(data.top_recommendations || [])
    } catch (e) { console.error('Recs error:', e) }
    setRecsLoading(false)
  }, [])

  const fetchMacro = useCallback(async () => {
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/market/macro`)
      const data = await res.json()
      if (data.success) setMacro(data)
    } catch {}
  }, [])

  // ─── Effects ────────────────────────────────────────────────────────────────

  useEffect(() => {
    fetchWatchlistPrices()
    fetchMacro()
    fetchRecommendations()
    const timer = setInterval(fetchWatchlistPrices, 30000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    fetchForecast(selectedSymbol)
    fetchIntradayTargets(selectedSymbol)
    fetchNews(selectedSymbol)
  }, [selectedSymbol])

  // ─── Search handler ─────────────────────────────────────────────────────────

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    const sym = searchQuery.toUpperCase().trim()
    if (sym) {
      setSelectedSymbol(sym)
      if (!watchlist.find(s => s.symbol === sym)) {
        setWatchlist(prev => [...prev, { symbol: sym, price: null, change: null, changePct: null, loading: true }])
      }
      setSearchQuery('')
    }
  }

  // ─── Chart rendering ───────────────────────────────────────────────────────

  const renderForecastChart = () => {
    if (!forecast) return null
    const horizon = forecast.forecasts[activeHorizon]
    if (!horizon) return null

    const history = forecast.price_history || []
    const histCloses = history.map(p => p.close)
    const forecastPts = horizon.forecast
    const lowBand = horizon.low_band
    const highBand = horizon.high_band
    const allValues = [...histCloses, ...forecastPts, ...lowBand, ...highBand]

    if (allValues.length === 0) return null

    const minVal = Math.min(...allValues) * 0.995
    const maxVal = Math.max(...allValues) * 1.005
    const W = 900
    const H = 350
    const PAD = { top: 20, right: 60, bottom: 30, left: 60 }
    const chartW = W - PAD.left - PAD.right
    const chartH = H - PAD.top - PAD.bottom

    const totalPts = histCloses.length + forecastPts.length
    const xScale = (i: number) => PAD.left + (i / (totalPts - 1)) * chartW
    const yScale = (v: number) => PAD.top + (1 - (v - minVal) / (maxVal - minVal)) * chartH

    // History line
    const histPath = histCloses.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ')

    // Forecast line (starts from last history point)
    const fOffset = histCloses.length - 1
    const forecastPath = forecastPts.map((v, i) =>
      `${i === 0 ? 'M' : 'L'}${xScale(fOffset + i).toFixed(1)},${yScale(v).toFixed(1)}`
    ).join(' ')

    // Confidence band
    const bandTop = highBand.map((v, i) => `${xScale(fOffset + i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ')
    const bandBot = lowBand.map((v, i) => `${xScale(fOffset + i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ')
    const bandPath = `M${bandTop} L${bandBot.split(' ').reverse().join(' ')} Z`

    // Y-axis labels
    const yTicks = 5
    const yLabels = Array.from({ length: yTicks + 1 }, (_, i) => minVal + (maxVal - minVal) * (i / yTicks))

    // Divider line between history and forecast
    const divX = xScale(fOffset)

    const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
      const svg = chartRef.current
      if (!svg) return
      const rect = svg.getBoundingClientRect()
      const mouseX = ((e.clientX - rect.left) / rect.width) * W
      const idx = Math.round(((mouseX - PAD.left) / chartW) * (totalPts - 1))
      if (idx < 0 || idx >= totalPts) { setHoverInfo(null); return }
      let price: number, date: string
      if (idx < histCloses.length) {
        price = histCloses[idx]
        date = history[idx]?.date || ''
      } else {
        const fi = idx - histCloses.length + 1
        price = forecastPts[Math.min(fi, forecastPts.length - 1)]
        date = 'Forecast'
      }
      setHoverInfo({ x: xScale(idx), y: yScale(price), price, date })
    }

    return (
      <svg ref={chartRef} viewBox={`0 0 ${W} ${H}`} className="w-full h-auto cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverInfo(null)}
      >
        {/* Grid */}
        {yLabels.map((v, i) => (
          <g key={i}>
            <line x1={PAD.left} y1={yScale(v)} x2={W - PAD.right} y2={yScale(v)} stroke="#374151" strokeWidth="0.5" strokeDasharray="4,4" />
            <text x={PAD.left - 8} y={yScale(v) + 4} textAnchor="end" fill="#9CA3AF" fontSize="10">${v.toFixed(0)}</text>
          </g>
        ))}

        {/* Divider */}
        <line x1={divX} y1={PAD.top} x2={divX} y2={H - PAD.bottom} stroke="#6B7280" strokeWidth="1" strokeDasharray="6,3" />
        <text x={divX - 4} y={H - 8} textAnchor="end" fill="#9CA3AF" fontSize="9">History</text>
        <text x={divX + 4} y={H - 8} textAnchor="start" fill="#818CF8" fontSize="9">Forecast</text>

        {/* Confidence band */}
        <path d={bandPath} fill="#818CF8" fillOpacity="0.12" />

        {/* History line */}
        <path d={histPath} fill="none" stroke="#10B981" strokeWidth="2" />

        {/* Forecast line */}
        <path d={forecastPath} fill="none" stroke="#818CF8" strokeWidth="2.5" strokeDasharray="6,3" />

        {/* High/Low band lines */}
        {highBand.length > 1 && (
          <path
            d={highBand.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(fOffset + i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ')}
            fill="none" stroke="#818CF8" strokeWidth="0.8" strokeDasharray="3,3" opacity="0.5"
          />
        )}
        {lowBand.length > 1 && (
          <path
            d={lowBand.map((v, i) => `${i === 0 ? 'M' : 'L'}${xScale(fOffset + i).toFixed(1)},${yScale(v).toFixed(1)}`).join(' ')}
            fill="none" stroke="#818CF8" strokeWidth="0.8" strokeDasharray="3,3" opacity="0.5"
          />
        )}

        {/* Current price dot */}
        <circle cx={xScale(fOffset)} cy={yScale(histCloses[histCloses.length - 1])} r="4" fill="#10B981" />

        {/* Target price dot */}
        <circle cx={xScale(totalPts - 1)} cy={yScale(forecastPts[forecastPts.length - 1])} r="4" fill="#818CF8" />
        <text x={xScale(totalPts - 1) + 8} y={yScale(forecastPts[forecastPts.length - 1]) + 4} fill="#818CF8" fontSize="11" fontWeight="bold">
          ${forecastPts[forecastPts.length - 1].toFixed(2)}
        </text>

        {/* Current price label */}
        <text x={W - PAD.right + 8} y={yScale(histCloses[histCloses.length - 1]) + 4} fill="#10B981" fontSize="11" fontWeight="bold">
          ${histCloses[histCloses.length - 1].toFixed(2)}
        </text>

        {/* Hover crosshair + tooltip */}
        {hoverInfo && (
          <g>
            <line x1={hoverInfo.x} y1={PAD.top} x2={hoverInfo.x} y2={H - PAD.bottom}
              stroke="#6366F1" strokeWidth="1" strokeDasharray="3,3" opacity="0.7" />
            <line x1={PAD.left} y1={hoverInfo.y} x2={W - PAD.right} y2={hoverInfo.y}
              stroke="#6366F1" strokeWidth="0.5" strokeDasharray="3,3" opacity="0.4" />
            <circle cx={hoverInfo.x} cy={hoverInfo.y} r="5" fill="#6366F1" stroke="#fff" strokeWidth="2" />
            <rect x={Math.min(hoverInfo.x + 10, W - 130)} y={hoverInfo.y - 30}
              width="115" height="38" rx="6"
              fill="#1E1B4B" stroke="#6366F1" strokeWidth="1" opacity="0.95" />
            <text x={Math.min(hoverInfo.x + 18, W - 122)} y={hoverInfo.y - 14}
              fill="#E0E7FF" fontSize="13" fontWeight="bold">
              ${hoverInfo.price.toFixed(2)}
            </text>
            <text x={Math.min(hoverInfo.x + 18, W - 122)} y={hoverInfo.y + 2}
              fill="#9CA3AF" fontSize="9">
              {hoverInfo.date}
            </text>
          </g>
        )}

        {/* Invisible overlay for smooth mouse tracking */}
        <rect x={PAD.left} y={PAD.top} width={chartW} height={chartH}
          fill="transparent" />
      </svg>
    )
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  const activeForecast = forecast?.forecasts?.[activeHorizon]

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* ── Top Bar ── */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="text-indigo-400" size={24} />
            <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
              Avira Trading
            </h1>
          </div>

          {/* Macro indicators */}
          {macro && (
            <div className="flex items-center gap-4 ml-6 text-xs">
              {macro.vix?.vix && (
                <span className={`px-2 py-1 rounded ${macro.vix.vix > 20 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                  VIX {macro.vix.vix}
                </span>
              )}
              {macro.fear_greed?.score && (
                <span className={`px-2 py-1 rounded ${macro.fear_greed.score < 40 ? 'bg-red-500/20 text-red-400' : macro.fear_greed.score > 60 ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                  F&G {macro.fear_greed.score}
                </span>
              )}
              {macro.put_call_ratio?.ratio && (
                <span className="px-2 py-1 rounded bg-gray-800 text-gray-300">
                  P/C {macro.put_call_ratio.ratio}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Search */}
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search ticker..."
              className="bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 w-48"
            />
          </div>
        </form>
      </div>

      <div className="flex h-[calc(100vh-60px)]">
        {/* ── Left Sidebar: Watchlist ── */}
        <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
          <div className="p-3 border-b border-gray-800 flex items-center justify-between">
            <span className="text-sm font-semibold text-gray-300">Watchlist</span>
            <button onClick={fetchWatchlistPrices} className="text-gray-500 hover:text-gray-300">
              <RefreshCw size={14} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto">
            {watchlist.map(stock => (
              <button
                key={stock.symbol}
                onClick={() => setSelectedSymbol(stock.symbol)}
                className={`w-full px-4 py-3 flex items-center justify-between border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors ${
                  selectedSymbol === stock.symbol ? 'bg-indigo-500/10 border-l-2 border-l-indigo-500' : ''
                }`}
              >
                <div>
                  <div className="text-sm font-semibold text-white">{stock.symbol}</div>
                  <div className="text-xs text-gray-500">
                    {stock.price ? `$${stock.price.toFixed(2)}` : '...'}
                  </div>
                </div>
                {stock.changePct !== null && (
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                    stock.changePct >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {stock.changePct >= 0 ? '+' : ''}{stock.changePct}%
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* Tab switcher */}
          <div className="border-t border-gray-800 p-2 grid grid-cols-3 gap-1">
            {(['forecast', 'news', 'recommendations'] as const).map(tab => (
              <button
                key={tab}
                onClick={() => {
                  setActiveTab(tab)
                  if (tab === 'recommendations' && recommendations.length === 0) fetchRecommendations()
                  if (tab === 'news' && news.length === 0) fetchNews(selectedSymbol)
                }}
                className={`text-xs py-1.5 rounded font-medium transition-colors ${
                  activeTab === tab ? 'bg-indigo-600 text-white' : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {tab === 'forecast' ? 'Charts' : tab === 'news' ? 'News' : 'Top 20'}
              </button>
            ))}
          </div>
        </div>

        {/* ── Main Content ── */}
        <div className="flex-1 overflow-y-auto">
          {activeTab === 'forecast' && (
            <div className="p-6 space-y-6">
              {/* Stock Header */}
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-3xl font-bold">{selectedSymbol}</h2>
                  <div className="flex items-center gap-4 mt-1">
                    {forecast && (
                      <>
                        <span className="text-4xl font-bold text-white">${forecast.current_price.toFixed(2)}</span>
                        <span className={`text-lg font-bold ${activeForecast?.direction === 'UP' ? 'text-green-400' : 'text-red-400'}`}>
                          {activeForecast?.direction === 'UP' ? '+' : ''}{activeForecast?.upside_pct}%
                          <span className="text-sm text-gray-500 ml-1">projected</span>
                        </span>
                      </>
                    )}
                  </div>
                  {forecast && (
                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                      <span>52W: ${forecast.week52_low} — ${forecast.week52_high}</span>
                      <span>RSI: <span className={forecast.rsi > 70 ? 'text-red-400' : forecast.rsi < 30 ? 'text-green-400' : 'text-white'}>{forecast.rsi}</span></span>
                      <span>MACD: <span className={forecast.macd_signal?.includes('bullish') ? 'text-green-400' : 'text-red-400'}>{forecast.macd_signal}</span></span>
                    </div>
                  )}
                </div>

                {/* Overall Rating */}
                {forecast && (
                  <div className={`text-center px-5 py-3 rounded-xl border ${RATING_BG[forecast.overall_rating] || 'bg-gray-800'}`}>
                    <div className="text-xs text-gray-400 mb-1">AI Rating</div>
                    <div className={`text-xl font-black ${RATING_COLORS[forecast.overall_rating] || 'text-white'}`}>
                      {forecast.overall_rating}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">{forecast.bull_horizons}/6 bullish</div>
                  </div>
                )}
              </div>

              {/* Horizon Tabs */}
              <div className="flex items-center gap-2">
                {HORIZONS.map(h => (
                  <button
                    key={h.key}
                    onClick={() => setActiveHorizon(h.key)}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                      activeHorizon === h.key
                        ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                    }`}
                  >
                    {h.label}
                  </button>
                ))}
                <div className="flex-1" />
                <button onClick={() => fetchForecast(selectedSymbol)} className="text-gray-500 hover:text-gray-300 p-2">
                  <RefreshCw size={16} className={forecastLoading ? 'animate-spin' : ''} />
                </button>
              </div>

              {/* Chart */}
              <div className="bg-gray-900 rounded-2xl border border-gray-800 p-4">
                {forecastLoading ? (
                  <div className="h-80 flex items-center justify-center text-gray-500">
                    <RefreshCw className="animate-spin mr-2" size={20} /> Loading forecast...
                  </div>
                ) : forecast ? (
                  <>
                    {renderForecastChart()}
                    {/* Forecast details */}
                    {activeForecast && (
                      <div className="mt-4 grid grid-cols-5 gap-3">
                        <div className="bg-gray-800 rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500">Target</div>
                          <div className="text-lg font-bold text-indigo-400">${activeForecast.target_price}</div>
                        </div>
                        <div className="bg-gray-800 rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500">Direction</div>
                          <div className={`text-lg font-bold ${activeForecast.direction === 'UP' ? 'text-green-400' : 'text-red-400'}`}>
                            {activeForecast.direction === 'UP' ? '▲' : '▼'} {activeForecast.direction}
                          </div>
                        </div>
                        <div className="bg-gray-800 rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500">Magnitude</div>
                          <div className="text-lg font-bold text-white">{activeForecast.magnitude_pct}%</div>
                        </div>
                        <div className="bg-gray-800 rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500">Low Band</div>
                          <div className="text-lg font-bold text-red-400">${activeForecast.low_band[activeForecast.low_band.length - 1]}</div>
                        </div>
                        <div className="bg-gray-800 rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500">High Band</div>
                          <div className="text-lg font-bold text-green-400">${activeForecast.high_band[activeForecast.high_band.length - 1]}</div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="h-80 flex items-center justify-center text-gray-500">Select a stock to see forecasts</div>
                )}
              </div>

              {/* Method & Horizon Summary Cards */}
              {forecast && (
                <div className="grid grid-cols-6 gap-3">
                  {HORIZONS.map(h => {
                    const hf = forecast.forecasts[h.key]
                    if (!hf) return null
                    const isActive = activeHorizon === h.key
                    return (
                      <button
                        key={h.key}
                        onClick={() => setActiveHorizon(h.key)}
                        className={`p-4 rounded-xl border transition-all text-left ${
                          isActive ? 'bg-indigo-600/20 border-indigo-500' : 'bg-gray-900 border-gray-800 hover:border-gray-700'
                        }`}
                      >
                        <div className="text-xs text-gray-500 mb-1">{h.label}</div>
                        <div className={`text-xl font-bold ${hf.direction === 'UP' ? 'text-green-400' : 'text-red-400'}`}>
                          {hf.direction === 'UP' ? '+' : ''}{hf.upside_pct}%
                        </div>
                        <div className="text-xs text-gray-500 mt-1">${hf.target_price}</div>
                        <div className="text-[10px] text-gray-600 mt-2 line-clamp-1">{hf.method}</div>
                      </button>
                    )
                  })}
                </div>
              )}

              {/* Intraday Options Targets */}
              {intradayTargets?.trade_targets && (
                <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
                  <div className="bg-gradient-to-r from-indigo-900/50 to-purple-900/50 px-5 py-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Target size={16} className="text-yellow-400" />
                      <span className="font-bold text-sm">Options Day Trade Targets</span>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-gray-400">RSI: <span className="text-white font-bold">{intradayTargets.indicators?.rsi}</span></span>
                      <span className="text-gray-400">ATR: <span className="text-white font-bold">${intradayTargets.indicators?.atr}</span></span>
                      <span className={`px-2 py-0.5 rounded-full font-bold ${
                        intradayTargets.trade_targets.bias === 'bullish' ? 'bg-green-500/30 text-green-400' : 'bg-red-500/30 text-red-400'
                      }`}>{intradayTargets.trade_targets.bias?.toUpperCase()}</span>
                    </div>
                  </div>
                  <div className="grid md:grid-cols-2 divide-x divide-gray-800">
                    {/* Call */}
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <ArrowUpCircle size={16} className="text-green-400" />
                        <span className="font-bold text-green-400">CALL Setup</span>
                        <span className="text-xs bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">
                          R:R {intradayTargets.trade_targets.call_trade?.risk_reward}x
                        </span>
                      </div>
                      <div className="space-y-1.5 text-sm">
                        {['entry', 'stop_loss', 'target1', 'target2'].map(k => (
                          <div key={k} className="flex justify-between py-1 px-2 bg-gray-800/50 rounded">
                            <span className="text-gray-400 capitalize">{k.replace('_', ' ')}</span>
                            <span className={`font-bold ${k === 'stop_loss' ? 'text-red-400' : k.includes('target') ? 'text-blue-400' : 'text-green-400'}`}>
                              ${intradayTargets.trade_targets.call_trade?.[k]}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    {/* Put */}
                    <div className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <ArrowDownCircle size={16} className="text-red-400" />
                        <span className="font-bold text-red-400">PUT Setup</span>
                        <span className="text-xs bg-red-500/20 text-red-400 px-2 py-0.5 rounded-full">
                          R:R {intradayTargets.trade_targets.put_trade?.risk_reward}x
                        </span>
                      </div>
                      <div className="space-y-1.5 text-sm">
                        {['entry', 'stop_loss', 'target1', 'target2'].map(k => (
                          <div key={k} className="flex justify-between py-1 px-2 bg-gray-800/50 rounded">
                            <span className="text-gray-400 capitalize">{k.replace('_', ' ')}</span>
                            <span className={`font-bold ${k === 'stop_loss' ? 'text-red-400' : k.includes('target') ? 'text-blue-400' : 'text-red-400'}`}>
                              ${intradayTargets.trade_targets.put_trade?.[k]}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  {/* Pivots */}
                  <div className="border-t border-gray-800 p-3 flex flex-wrap gap-2 text-xs">
                    {['r3','r2','r1','pivot','s1','s2','s3'].map(key => {
                      const val = intradayTargets.pivot_points?.classic?.[key]
                      return val ? (
                        <span key={key} className={`px-2 py-1 rounded font-mono font-bold ${
                          key === 'pivot' ? 'bg-gray-700 text-white' :
                          key.startsWith('r') ? 'bg-red-500/20 text-red-400' :
                          'bg-green-500/20 text-green-400'
                        }`}>{key.toUpperCase()} ${val}</span>
                      ) : null
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── News Tab ── */}
          {activeTab === 'news' && (
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Newspaper size={20} className="text-indigo-400" /> Financial News
                </h2>
                <button onClick={() => fetchNews(selectedSymbol)} className="text-gray-500 hover:text-gray-300">
                  <RefreshCw size={16} className={newsLoading ? 'animate-spin' : ''} />
                </button>
              </div>
              {newsLoading ? (
                <div className="text-center py-20 text-gray-500">Loading news from 10+ sources...</div>
              ) : (
                <div className="space-y-3">
                  {news.slice(0, 30).map((article, i) => (
                    <a
                      key={i}
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-indigo-500/50 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="text-sm font-semibold text-white line-clamp-2">{article.title}</div>
                          <div className="text-xs text-gray-500 mt-1 line-clamp-2">{article.summary}</div>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-[10px] text-indigo-400 font-medium">{article.source}</div>
                          <div className="text-[10px] text-gray-600 mt-0.5">{article.published?.slice(0, 16)}</div>
                        </div>
                      </div>
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Recommendations Tab ── */}
          {activeTab === 'recommendations' && (
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold flex items-center gap-2">
                  <Award size={20} className="text-yellow-400" /> Top 20 Investment Picks
                </h2>
                <button onClick={fetchRecommendations} className="text-gray-500 hover:text-gray-300">
                  <RefreshCw size={16} className={recsLoading ? 'animate-spin' : ''} />
                </button>
              </div>

              <p className="text-sm text-gray-500 mb-4">
                Scored across 5 dimensions using 20+ data sources. 100-stock universe scanned: technical indicators, fundamentals, social sentiment (Reddit, Stocktwits), insider trading, analyst consensus, macro conditions.
              </p>

              {recsLoading ? (
                <div className="text-center py-20 text-gray-500">
                  <RefreshCw className="animate-spin mx-auto mb-3" size={24} />
                  Scanning 100 stocks across 20+ data sources...
                  <br /><span className="text-xs">This may take 30-60 seconds</span>
                </div>
              ) : (
                <div className="space-y-3">
                  {recommendations.map((rec, i) => (
                    <button
                      key={rec.symbol}
                      onClick={() => { setSelectedSymbol(rec.symbol); setActiveTab('forecast') }}
                      className="w-full bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-indigo-500/50 transition-colors text-left"
                    >
                      <div className="flex items-center gap-4">
                        {/* Rank */}
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-black text-lg ${
                          i < 3 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-800 text-gray-500'
                        }`}>
                          {i + 1}
                        </div>

                        {/* Info */}
                        <div className="flex-1">
                          <div className="flex items-center gap-3">
                            <span className="text-lg font-bold text-white">{rec.symbol}</span>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-bold border ${RATING_BG[rec.rating] || ''} ${RATING_COLORS[rec.rating] || ''}`}>
                              {rec.rating}
                            </span>
                            {rec.sector && <span className="text-xs text-gray-500">{rec.sector}</span>}
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                            <span>Price: ${rec.price?.toFixed(2) || '—'}</span>
                            <span>Target: ${rec.target_price?.toFixed(2) || '—'}</span>
                            <span>PE: {rec.pe_ratio?.toFixed(1) || '—'}</span>
                            <span>Cap: {formatMarketCap(rec.market_cap)}</span>
                          </div>
                        </div>

                        {/* Score */}
                        <div className="text-right">
                          <div className="text-2xl font-black text-indigo-400">{rec.composite_score}</div>
                          <div className="text-[10px] text-gray-500">/ 100</div>
                        </div>

                        {/* Score bars */}
                        <div className="w-32 space-y-1">
                          {Object.entries(rec.scores).map(([k, v]) => (
                            <div key={k} className="flex items-center gap-2">
                              <span className="text-[9px] text-gray-600 w-12 text-right">{k}</span>
                              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${v >= 65 ? 'bg-green-500' : v >= 45 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                  style={{ width: `${v}%` }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
