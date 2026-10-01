import { useState, useEffect } from 'react'
import { TrendingUp, DollarSign, BarChart3, Bell, ExternalLink, Globe } from 'lucide-react'
import config from '../config'
import InvestmentChat from '../components/InvestmentChat'
import InteractiveStockChart from '../components/InteractiveStockChart'

interface Holding {
  symbol: string
  shares: number
  average_cost: number
  current_price?: number
  current_value?: number
  gain_loss?: number
  gain_loss_percent?: number
  change_percent?: number
}

export default function Portfolio() {
  const [symbol, setSymbol] = useState('')
  const [shares, setShares] = useState('')
  const [entryPrice, setEntryPrice] = useState('')
  const [loading, setLoading] = useState(false)
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [totalValue, setTotalValue] = useState(0)
  const [totalGainLoss, setTotalGainLoss] = useState(0)
  const [selectedStock, setSelectedStock] = useState<string | null>(null)
  const [stockInsights, setStockInsights] = useState<any>(null)
  const [insightsLoading, setInsightsLoading] = useState(false)
  const [analysisMode] = useState<'stock' | 'options'>('stock')
  const [, setOptionsData] = useState<any>(null)
  const [, setAnalysisSteps] = useState<string[]>([])

  // Dual-market: US / India
  const [region, setRegion] = useState<'US' | 'IN'>('US')
  const [marketIndices, setMarketIndices] = useState<any[]>([])
  const [marketStatus, setMarketStatus] = useState<any>(null)
  const [deepMetrics, setDeepMetrics] = useState<any>(null)
  const [deepMetricsLoading, setDeepMetricsLoading] = useState(false)

  useEffect(() => {
    fetchHoldings()
  }, [])

  useEffect(() => {
    fetchMarketOverview(region)
  }, [region])

  const fetchMarketOverview = async (r: 'US' | 'IN') => {
    try {
      const [idxRes, statusRes] = await Promise.all([
        fetch(`${config.apiBase}/api/portfolio/market/indices?region=${r}`),
        fetch(`${config.apiBase}/api/portfolio/market/status?region=${r}`),
      ])
      const [idxData, statusData] = await Promise.all([idxRes.json(), statusRes.json()])
      if (idxData.success) setMarketIndices(idxData.indices || [])
      if (statusData.success) setMarketStatus(statusData)
    } catch (error) {
      console.error('Market overview fetch error:', error)
    }
  }

  const fetchDeepMetrics = async (stockSymbol: string) => {
    try {
      setDeepMetricsLoading(true)
      setDeepMetrics(null)
      const res = await fetch(`${config.apiBase}/api/portfolio/stocks/${stockSymbol}/deep-metrics?region=${region}`)
      const data = await res.json()
      if (data.success) setDeepMetrics(data)
    } catch (error) {
      console.error('Deep metrics fetch error:', error)
    } finally {
      setDeepMetricsLoading(false)
    }
  }

  const fetchHoldings = async () => {
    try {
      const response = await fetch(`${config.apiBase}/api/portfolio/holdings?user_id=default`)
      const data = await response.json()
      if (data.success) {
        setHoldings(data.holdings || [])
        
        // Calculate totals
        const total = data.holdings.reduce((sum: number, h: Holding) => sum + (h.current_value || 0), 0)
        const gainLoss = data.holdings.reduce((sum: number, h: Holding) => sum + (h.gain_loss || 0), 0)
        setTotalValue(total)
        setTotalGainLoss(gainLoss)
      }
    } catch (error) {
      console.error('Failed to fetch holdings:', error)
    }
  }

  const handleAddStock = async () => {
    if (!symbol || !shares || !entryPrice) {
      alert('Please enter symbol, shares, and entry price')
      return
    }

    try {
      setLoading(true)
      const response = await fetch(`${config.apiBase}/api/portfolio/holdings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default',
          symbol: symbol.toUpperCase(),
          shares: parseFloat(shares),
          average_cost: parseFloat(entryPrice),
          purchase_date: new Date().toISOString().split('T')[0]
        })
      })
      const data = await response.json()
      if (data.success) {
        alert(`Added ${shares} shares of ${symbol.toUpperCase()} @ $${entryPrice}`)
        setSymbol('')
        setShares('')
        setEntryPrice('')
        await fetchHoldings()
      } else {
        alert('Failed to add stock: ' + (data.message || 'Unknown error'))
      }
    } catch (error) {
      console.error('Failed to add stock:', error)
      alert('Failed to add stock')
    } finally {
      setLoading(false)
    }
  }

  const [analysisProgress, setAnalysisProgress] = useState<string>('')

  const fetchStockInsights = async (stockSymbol: string) => {
    try {
      setInsightsLoading(true)
      setStockInsights(null)
      setOptionsData(null)
      setAnalysisSteps([])
      setAnalysisProgress('Initiating analysis...')
      
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 300000) // 5 minute timeout
      
      // Real-time progress updates showing actual data sources
      const progressSteps = [
        '📊 Fetching real-time stock data from Yahoo Finance...',
        '📰 Gathering latest financial news and sentiment...',
        '💬 Analyzing social media sentiment (Twitter, Reddit, StockTwits)...',
        '📈 Calculating technical indicators (RSI, MA, Support/Resistance)...',
        '🏢 Checking insider trading activity (SEC Form 4 filings)...',
        '🏦 Analyzing institutional holdings (13F filings)...',
        '📅 Fetching earnings calendar and estimates...',
        '📉 Analyzing options chain and Greeks...',
        '🤖 Running AI analysis with mistral:7b LLM...',
        '✨ Generating investment recommendations...'
      ]
      
      let stepIndex = 0
      const progressInterval = setInterval(() => {
        if (stepIndex < progressSteps.length) {
          setAnalysisProgress(progressSteps[stepIndex])
          setAnalysisSteps(prev => [...prev, progressSteps[stepIndex]])
          stepIndex++
        }
      }, 2000)
      
      // Fetch both stock and options analysis
      const [stockResponse, optionsResponse] = await Promise.all([
        fetch(`${config.apiBase}/api/portfolio/stocks/${stockSymbol}/comprehensive`, { signal: controller.signal }),
        analysisMode === 'options' ? fetch(`${config.apiBase}/api/portfolio/stocks/${stockSymbol}/options`, { signal: controller.signal }) : Promise.resolve(null)
      ])
      
      clearTimeout(timeoutId)
      clearInterval(progressInterval)
      setAnalysisProgress('Finalizing results...')
      
      if (!stockResponse.ok) {
        throw new Error(`HTTP ${stockResponse.status}: ${stockResponse.statusText}`)
      }
      
      const data = await stockResponse.json()
      console.log('Stock insights response:', data)
      
      if (data.success) {
        setStockInsights(data)
        setAnalysisProgress('✅ Analysis complete!')
        
        // Fetch options data if in options mode
        if (analysisMode === 'options' && optionsResponse) {
          const optionsData = await optionsResponse.json()
          if (optionsData.success) {
            setOptionsData(optionsData)
          }
        }
        
        setTimeout(() => setAnalysisProgress(''), 2000)
      } else {
        throw new Error(data.error || 'Failed to load stock insights')
      }
    } catch (error: any) {
      console.error('Failed to fetch insights:', error)
      const errorMsg = error.name === 'AbortError' 
        ? 'Analysis timed out after 5 minutes. Please try again.' 
        : error.message || 'Error loading stock insights'
      
      setStockInsights({
        success: false,
        error: errorMsg,
        symbol: stockSymbol,
        current_price: 0,
        change_percent: 0
      })
      setAnalysisProgress('')
    } finally {
      setInsightsLoading(false)
    }
  }

  const handleStockClick = (stockSymbol: string) => {
    setSelectedStock(stockSymbol)
    fetchStockInsights(stockSymbol)
  }
  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
            <TrendingUp className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Investment Portfolio</h1>
            <p className="text-gray-600">Track your stocks with AI-powered insights</p>
          </div>
        </div>
        {/* US / India market toggle */}
        <div className="flex items-center gap-2 mt-4">
          <Globe size={16} className="text-gray-500" />
          <div className="flex bg-gray-100 rounded-lg p-1">
            {(['US', 'IN'] as const).map(r => (
              <button
                key={r}
                onClick={() => setRegion(r)}
                className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                  region === r ? 'bg-white shadow text-indigo-700' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {r === 'US' ? '🇺🇸 US' : '🇮🇳 India'}
              </button>
            ))}
          </div>
          {marketStatus && (
            <span className={`text-xs font-medium px-2 py-1 rounded ${marketStatus.is_open ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>
              {marketStatus.is_open ? '● Market Open' : '○ Market Closed'} · {marketStatus.currency}
            </span>
          )}
        </div>
      </div>

      {/* Market indices strip */}
      {marketIndices.length > 0 && (
        <div className="flex gap-4 mb-8 overflow-x-auto pb-2">
          {marketIndices.map((idx: any, i: number) => (
            <div key={idx.symbol || i} className="bg-white px-5 py-3 rounded-xl border border-gray-200 min-w-[160px] flex-shrink-0">
              <p className="text-xs text-gray-500 font-medium">{idx.name || idx.symbol}</p>
              <p className="text-lg font-bold text-gray-900">
                {idx.price != null ? idx.price.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'}
              </p>
              {idx.change_percent != null && (
                <p className={`text-xs font-semibold ${idx.change_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {idx.change_percent >= 0 ? '+' : ''}{idx.change_percent.toFixed(2)}%
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Portfolio Summary */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <DollarSign className="text-green-600 mb-2" size={24} />
          <p className="text-3xl font-bold">${totalValue.toFixed(2)}</p>
          <p className="text-sm text-gray-600">Total Value</p>
          <p className={`text-sm mt-1 ${totalGainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalGainLoss >= 0 ? '+' : ''}{totalGainLoss.toFixed(2)} ({totalValue > 0 ? ((totalGainLoss / totalValue) * 100).toFixed(2) : '0.00'}%)
          </p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <BarChart3 className="text-blue-600 mb-2" size={24} />
          <p className="text-3xl font-bold">{holdings.length}</p>
          <p className="text-sm text-gray-600">Holdings</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Bell className="text-orange-600 mb-2" size={24} />
          <p className="text-3xl font-bold">0</p>
          <p className="text-sm text-gray-600">Active Alerts</p>
        </div>
      </div>

      {/* Add Stock */}
      <div className="bg-white p-8 rounded-xl border border-gray-200 mb-8">
        <h2 className="text-xl font-semibold mb-6">Add Stock to Portfolio</h2>
        <div className="grid md:grid-cols-4 gap-4">
          <input
            type="text"
            placeholder="Symbol (e.g., AAPL)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleAddStock()}
            className="px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
          />
          <input
            type="number"
            placeholder="Shares"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleAddStock()}
            className="px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
          />
          <input
            type="number"
            placeholder="Entry Price ($)"
            value={entryPrice}
            onChange={(e) => setEntryPrice(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleAddStock()}
            step="0.01"
            className="px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
          />
          <button 
            onClick={handleAddStock}
            disabled={loading}
            className="bg-gradient-to-r from-green-500 to-emerald-600 text-white py-3 rounded-lg font-semibold hover:shadow-lg transition-shadow disabled:opacity-50"
          >
            {loading ? 'Adding...' : 'Add Stock'}
          </button>
        </div>
      </div>

      {/* Holdings List */}
      {holdings.length > 0 && (
        <div className="bg-white p-8 rounded-xl border border-gray-200 mb-8">
          <h2 className="text-xl font-semibold mb-6">Your Holdings</h2>
          <div className="space-y-4">
            {holdings.map((holding, index) => (
              <div 
                key={index} 
                onClick={() => handleStockClick(holding.symbol)}
                className="p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow cursor-pointer hover:border-blue-400"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">{holding.symbol}</h3>
                    <p className="text-sm text-gray-600">{holding.shares} shares</p>
                  </div>
                  <div className="text-right">
                    <p className="text-lg font-semibold">${holding.current_price?.toFixed(2) || '0.00'}</p>
                    <p className={`text-sm ${(holding.change_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {(holding.change_percent || 0) >= 0 ? '+' : ''}{holding.change_percent?.toFixed(2) || '0.00'}%
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-gray-600">Value</p>
                    <p className="font-semibold">${holding.current_value?.toFixed(2) || '0.00'}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Avg Cost</p>
                    <p className="font-semibold">${holding.average_cost?.toFixed(2) || '0.00'}</p>
                  </div>
                  <div>
                    <p className="text-gray-600">Gain/Loss</p>
                    <p className={`font-semibold ${(holding.gain_loss || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {(holding.gain_loss || 0) >= 0 ? '+' : ''}${holding.gain_loss?.toFixed(2) || '0.00'}
                      ({(holding.gain_loss_percent || 0) >= 0 ? '+' : ''}{holding.gain_loss_percent?.toFixed(2) || '0.00'}%)
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Sources */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-8 rounded-xl border border-blue-200 mb-8">
        <h2 className="text-xl font-semibold mb-4 text-blue-900">📚 Data Sources & Analysis</h2>
        <p className="text-blue-800 mb-4">Our AI-powered recommendations are based on data from multiple trusted sources:</p>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-white p-4 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <ExternalLink size={16} /> Real-Time Market Data
            </h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Yahoo Finance API - Live quotes & prices</li>
              <li>• Trading volume & market cap</li>
              <li>• Historical price data</li>
            </ul>
          </div>
          <div className="bg-white p-4 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <ExternalLink size={16} /> News & Sentiment
            </h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Yahoo Finance News Feed</li>
              <li>• AI sentiment analysis</li>
              <li>• Market trend detection</li>
            </ul>
          </div>
          <div className="bg-white p-4 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <ExternalLink size={16} /> AI Analysis
            </h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Llama 3.2 (3B) Language Model</li>
              <li>• Technical indicator analysis</li>
              <li>• Price target calculations</li>
            </ul>
          </div>
          <div className="bg-white p-4 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
              <ExternalLink size={16} /> Recommended Resources
            </h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• TradingView - Charts & analysis</li>
              <li>• Finviz - Stock screener</li>
              <li>• Seeking Alpha - Research</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Stock Insights Modal */}
      {selectedStock && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => { setSelectedStock(null); setDeepMetrics(null) }}>
          <div className="bg-white rounded-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-6 border-b border-gray-200 flex justify-between items-center sticky top-0 bg-white">
              <h2 className="text-2xl font-bold">{selectedStock} - AI Insights</h2>
              <button onClick={() => setSelectedStock(null)} className="text-gray-500 hover:text-gray-700 text-2xl">&times;</button>
            </div>
            <div className="p-6">
              {insightsLoading ? (
                <div className="text-center py-12">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="mt-4 text-gray-600 font-semibold">Loading AI analysis...</p>
                  {analysisProgress && (
                    <div className="mt-6 max-w-md mx-auto">
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p className="text-sm text-blue-800 flex items-center gap-2">
                          <span className="animate-pulse">⚡</span>
                          {analysisProgress}
                        </p>
                      </div>
                      <p className="text-xs text-gray-500 mt-3">
                        This may take up to 5 minutes for comprehensive analysis
                      </p>
                    </div>
                  )}
                </div>
              ) : stockInsights ? (
                <>
                  <div className="space-y-6">
                  {/* Price Info */}
                  <div className="grid md:grid-cols-4 gap-4">
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <p className="text-sm text-gray-600">Current Price</p>
                      <p className="text-2xl font-bold">${stockInsights.current_price?.toFixed(2) || stockInsights.price_data?.current_price?.toFixed(2) || '0.00'}</p>
                      <p className="text-xs text-gray-500 mt-1">Source: Yahoo Finance</p>
                    </div>
                    <div className="bg-green-50 p-4 rounded-lg">
                      <p className="text-sm text-gray-600">Day Change</p>
                      <p className={`text-2xl font-bold ${(stockInsights.change_percent || stockInsights.price_data?.change_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {(stockInsights.change_percent || stockInsights.price_data?.change_percent || 0) >= 0 ? '+' : ''}{(stockInsights.change_percent || stockInsights.price_data?.change_percent)?.toFixed(2) || '0.00'}%
                      </p>
                    </div>
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <p className="text-sm text-gray-600">Recommendation</p>
                      <p className="text-2xl font-bold capitalize">{stockInsights.recommendation || stockInsights.ai_recommendation?.rating || 'hold'}</p>
                    </div>
                    <div className="bg-orange-50 p-4 rounded-lg">
                      <p className="text-sm text-gray-600">52W Range</p>
                      <p className="text-sm font-semibold">
                        ${stockInsights.price_data?.['52_week_low']?.toFixed(2) || '0'} - ${stockInsights.price_data?.['52_week_high']?.toFixed(2) || '0'}
                      </p>
                    </div>
                  </div>

                  {/* Interactive Stock Chart */}
                  <div className="mb-6">
                    <InteractiveStockChart 
                      symbol={selectedStock} 
                      technicalData={stockInsights.technical_analysis}
                    />
                  </div>

                  {/* Elliott Wave & Technical Charts */}
                  {stockInsights.technical_analysis && (
                    <div className="bg-gradient-to-br from-indigo-50 to-purple-50 p-6 rounded-lg border border-indigo-200">
                      <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                        📈 Elliott Wave & Technical Analysis
                      </h3>
                      <div className="grid md:grid-cols-2 gap-6">
                        {/* Elliott Wave Pattern */}
                        <div className="bg-white p-4 rounded-lg">
                          <h4 className="font-semibold text-indigo-900 mb-3">Elliott Wave Pattern</h4>
                          {stockInsights.technical_analysis.abc_pattern ? (
                            <div className="space-y-2 text-sm">
                              <p><span className="text-gray-600">Pattern:</span> <span className="font-semibold capitalize">{stockInsights.technical_analysis.abc_pattern.pattern?.replace(/_/g, ' ')}</span></p>
                              {stockInsights.technical_analysis.abc_pattern.point_a && (
                                <p><span className="text-gray-600">Wave A:</span> <span className="font-semibold">${stockInsights.technical_analysis.abc_pattern.point_a?.toFixed(2)}</span></p>
                              )}
                              {stockInsights.technical_analysis.abc_pattern.point_b && (
                                <p><span className="text-gray-600">Wave B:</span> <span className="font-semibold">${stockInsights.technical_analysis.abc_pattern.point_b?.toFixed(2)}</span></p>
                              )}
                              {stockInsights.technical_analysis.abc_pattern.point_c && (
                                <p><span className="text-gray-600">Wave C:</span> <span className="font-semibold">${stockInsights.technical_analysis.abc_pattern.point_c?.toFixed(2)}</span></p>
                              )}
                              {stockInsights.technical_analysis.abc_pattern.projection && (
                                <p><span className="text-gray-600">Projection:</span> <span className="font-semibold text-green-600">${stockInsights.technical_analysis.abc_pattern.projection?.toFixed(2)}</span></p>
                              )}
                            </div>
                          ) : (
                            <p className="text-gray-500 text-sm">Insufficient data for Elliott Wave analysis</p>
                          )}
                        </div>
                        
                        {/* Key Indicators */}
                        <div className="bg-white p-4 rounded-lg">
                          <h4 className="font-semibold text-indigo-900 mb-3">Key Indicators</h4>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600">RSI (14)</span>
                              <span className={`font-semibold ${stockInsights.technical_analysis.rsi > 70 ? 'text-red-600' : stockInsights.technical_analysis.rsi < 30 ? 'text-green-600' : 'text-gray-900'}`}>
                                {stockInsights.technical_analysis.rsi?.toFixed(1)} {stockInsights.technical_analysis.rsi > 70 ? '(Overbought)' : stockInsights.technical_analysis.rsi < 30 ? '(Oversold)' : ''}
                              </span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">SMA 20</span>
                              <span className="font-semibold">${stockInsights.technical_analysis.sma_20?.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">SMA 50</span>
                              <span className="font-semibold">${stockInsights.technical_analysis.sma_50?.toFixed(2)}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Trend</span>
                              <span className={`font-semibold capitalize ${stockInsights.technical_analysis.trend === 'bullish' ? 'text-green-600' : 'text-red-600'}`}>
                                {stockInsights.technical_analysis.trend}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      {/* Support & Resistance */}
                      <div className="mt-4 grid md:grid-cols-2 gap-4">
                        <div className="bg-green-100 p-3 rounded-lg">
                          <p className="text-sm text-green-800 font-semibold">Support Levels</p>
                          <p className="text-lg font-bold text-green-700">
                            ${stockInsights.technical_analysis.next_support?.toFixed(2) || 'N/A'}
                          </p>
                          {stockInsights.technical_analysis.support_levels?.slice(0, 2).map((level: number, i: number) => (
                            <span key={i} className="text-xs text-green-600 mr-2">${level?.toFixed(2)}</span>
                          ))}
                        </div>
                        <div className="bg-red-100 p-3 rounded-lg">
                          <p className="text-sm text-red-800 font-semibold">Resistance Levels</p>
                          <p className="text-lg font-bold text-red-700">
                            ${stockInsights.technical_analysis.next_resistance?.toFixed(2) || 'N/A'}
                          </p>
                          {stockInsights.technical_analysis.resistance_levels?.slice(0, 2).map((level: number, i: number) => (
                            <span key={i} className="text-xs text-red-600 mr-2">${level?.toFixed(2)}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Deep Metrics — deterministic scorecard (no AI) */}
                  <div className="bg-white p-6 rounded-lg border border-gray-200">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold text-lg">📐 Deep Metrics <span className="text-xs font-normal text-gray-500">deterministic · no AI</span></h3>
                      {!deepMetrics && !deepMetricsLoading && (
                        <button
                          onClick={() => fetchDeepMetrics(selectedStock)}
                          className="px-4 py-2 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700"
                        >
                          Load Scorecard
                        </button>
                      )}
                    </div>
                    {deepMetricsLoading && (
                      <div className="text-center py-6">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
                        <p className="text-sm text-gray-500 mt-2">Computing metrics...</p>
                      </div>
                    )}
                    {deepMetrics && (
                      <div className="grid md:grid-cols-3 gap-4">
                        {(['fundamentals', 'price_structure', 'options'] as const).map(group => {
                          const data = deepMetrics[group]
                          if (!data) return null
                          const entries = Object.entries(data).filter(([, v]) => typeof v === 'number' || typeof v === 'string').slice(0, 12)
                          return (
                            <div key={group} className="bg-gray-50 p-4 rounded-lg">
                              <h4 className="font-semibold text-sm text-gray-700 mb-2 capitalize">{group.replace(/_/g, ' ')}</h4>
                              <div className="space-y-1 text-xs">
                                {entries.map(([k, v]) => (
                                  <div key={k} className="flex justify-between">
                                    <span className="text-gray-500">{k.replace(/_/g, ' ')}</span>
                                    <span className="font-semibold text-gray-800">
                                      {typeof v === 'number' ? (Math.abs(v) < 10 ? v.toFixed(2) : v.toLocaleString(undefined, { maximumFractionDigits: 0 })) : String(v)}
                                    </span>
                                  </div>
                                ))}
                                {entries.length === 0 && <p className="text-gray-400">n/a</p>}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* AI Analysis */}
                  {stockInsights.analysis && (
                    <div className="bg-gray-50 p-6 rounded-lg">
                      <h3 className="font-semibold text-lg mb-3">🤖 AI Analysis</h3>
                      <p className="text-gray-700 whitespace-pre-wrap">{stockInsights.analysis}</p>
                    </div>
                  )}

                  {/* Recent News */}
                  {stockInsights.top_news && stockInsights.top_news.length > 0 && (
                    <div>
                      <h3 className="font-semibold text-lg mb-3">📰 Recent News</h3>
                      <div className="space-y-3">
                        {stockInsights.top_news.map((news: any, idx: number) => (
                          <div key={idx} className="border border-gray-200 p-4 rounded-lg hover:shadow-md transition-shadow">
                            <h4 className="font-semibold text-blue-600 mb-1">{news.title}</h4>
                            <p className="text-sm text-gray-600">{news.summary || 'No summary available'}</p>
                            <div className="flex items-center gap-4 mt-2">
                              <span className={`text-xs px-2 py-1 rounded ${news.sentiment === 'positive' ? 'bg-green-100 text-green-700' : news.sentiment === 'negative' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`}>
                                {news.sentiment || 'neutral'}
                              </span>
                              {news.link && (
                                <a href={news.link} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline">
                                  Read more →
                                </a>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Data Sources */}
                  <div className="bg-gradient-to-br from-slate-50 to-gray-100 p-6 rounded-lg border border-gray-200">
                    <h3 className="font-semibold text-lg mb-4">📚 Data Sources Used</h3>
                    <div className="grid md:grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="font-semibold text-gray-700 mb-2">📊 Market Data</p>
                        <ul className="space-y-1 text-gray-600">
                          <li>• Yahoo Finance (Real-time)</li>
                          <li>• Google Finance</li>
                          <li>• TradingView</li>
                        </ul>
                      </div>
                      <div>
                        <p className="font-semibold text-gray-700 mb-2">💬 Social Sentiment</p>
                        <ul className="space-y-1 text-gray-600">
                          <li>• Twitter/X</li>
                          <li>• Reddit (r/wallstreetbets)</li>
                          <li>• StockTwits</li>
                        </ul>
                      </div>
                      <div>
                        <p className="font-semibold text-gray-700 mb-2">📰 News & Analysis</p>
                        <ul className="space-y-1 text-gray-600">
                          <li>• Yahoo Finance News</li>
                          <li>• Seeking Alpha</li>
                          <li>• CNBC, Bloomberg</li>
                        </ul>
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <p className="text-xs text-gray-500">
                        ⚠️ <strong>Disclaimer:</strong> This analysis is for informational purposes only and does not constitute financial advice. 
                        Always verify with multiple sources and consult a licensed financial advisor before making investment decisions.
                      </p>
                    </div>
                  </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-12 text-gray-600">
                  <p>Failed to load insights. Please try again.</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Content with Chat Sidebar */}
      <div className="grid lg:grid-cols-3 gap-6">
        {/* Features - Left Side */}
        <div className="lg:col-span-2 space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-gradient-to-br from-blue-50 to-cyan-50 p-6 rounded-xl border border-blue-200">
          <h3 className="font-semibold text-lg mb-2 text-blue-900">📊 Sentiment Analysis</h3>
          <p className="text-blue-700 text-sm mb-3">
            Track social media sentiment from Twitter and Reddit
          </p>
          <ul className="space-y-1 text-sm text-blue-800">
            <li>• Real-time mentions tracking</li>
            <li>• Bullish/bearish sentiment</li>
            <li>• Trending stocks</li>
          </ul>
        </div>

        <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-6 rounded-xl border border-purple-200">
          <h3 className="font-semibold text-lg mb-2 text-purple-900">🔔 Smart Alerts</h3>
          <p className="text-purple-700 text-sm mb-3">
            Get notified about important events
          </p>
          <ul className="space-y-1 text-sm text-purple-800">
            <li>• Price movements</li>
            <li>• Earnings announcements</li>
            <li>• News alerts</li>
          </ul>
          </div>
          </div>
        </div>

        {/* Investment Assistant Chat - Right Sidebar */}
        <div className="lg:col-span-1">
          <div className="sticky top-4 h-[600px]">
            <InvestmentChat 
              portfolioContext={{
                holdings,
                total_value: totalValue,
                gain_loss: totalGainLoss
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
