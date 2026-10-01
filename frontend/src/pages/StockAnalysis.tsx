import { useState } from 'react'
import { TrendingUp, AlertTriangle, Calendar, BarChart3, Activity, Globe, MessageSquare } from 'lucide-react'
import config from '../config'

interface ComprehensiveAnalysis {
  symbol: string
  disclaimer: string
  price_data: any
  technical_analysis: any
  social_sentiment: any
  news_analysis: any
  market_calendar: any
  ai_recommendation: any
  data_sources_used: any[]
  analysis_timestamp: string
}

export default function StockAnalysis() {
  const [symbol, setSymbol] = useState('')
  const [loading, setLoading] = useState(false)
  const [analysis, setAnalysis] = useState<ComprehensiveAnalysis | null>(null)

  const analyzeStock = async () => {
    if (!symbol) return

    try {
      setLoading(true)
      const response = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol.toUpperCase()}/comprehensive`)
      const data = await response.json()
      
      if (data.success) {
        setAnalysis(data.analysis)
      }
    } catch (error) {
      console.error('Failed to analyze stock:', error)
      alert('Failed to analyze stock')
    } finally {
      setLoading(false)
    }
  }

  const getRatingColor = (rating: string) => {
    const colors: any = {
      'strong_buy': 'bg-green-600',
      'buy': 'bg-green-500',
      'hold': 'bg-yellow-500',
      'sell': 'bg-red-500',
      'strong_sell': 'bg-red-600'
    }
    return colors[rating] || 'bg-gray-500'
  }

  const getRatingText = (rating: string) => {
    return rating.replace('_', ' ').toUpperCase()
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <Activity className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Advanced Stock Analysis</h1>
            <p className="text-gray-600">AI-powered comprehensive stock analysis with multiple data sources</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white p-6 rounded-xl border border-gray-200 mb-8">
        <div className="flex gap-4">
          <input
            type="text"
            placeholder="Enter stock symbol (e.g., AAPL, TSLA, SLV)"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && analyzeStock()}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:border-purple-500 focus:outline-none"
          />
          <button
            onClick={analyzeStock}
            disabled={loading || !symbol}
            className="bg-gradient-to-r from-purple-500 to-indigo-600 text-white px-8 py-3 rounded-lg font-semibold hover:shadow-lg transition-shadow disabled:opacity-50"
          >
            {loading ? 'Analyzing...' : 'Analyze'}
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      {analysis && (
        <div className="bg-red-50 border-l-4 border-red-500 p-6 rounded-lg mb-8">
          <div className="flex items-start gap-3">
            <AlertTriangle className="text-red-600 flex-shrink-0 mt-1" size={24} />
            <div>
              <h3 className="font-bold text-red-900 mb-2">⚠️ INVESTMENT DISCLAIMER</h3>
              <p className="text-red-800 text-sm">{analysis.disclaimer}</p>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <div className="space-y-6">
          {/* Price Data */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <TrendingUp size={24} className="text-green-600" />
              Price Data
            </h2>
            <div className="grid md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600">Current Price</p>
                <p className="text-2xl font-bold">${analysis.price_data.current_price?.toFixed(2) || '0.00'}</p>
                <p className={`text-sm ${analysis.price_data.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {analysis.price_data.change >= 0 ? '+' : ''}{analysis.price_data.change_percent?.toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Volume</p>
                <p className="text-lg font-semibold">{analysis.price_data.volume?.toLocaleString() || '0'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">52W High</p>
                <p className="text-lg font-semibold">${analysis.price_data['52_week_high']?.toFixed(2) || '0.00'}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">52W Low</p>
                <p className="text-lg font-semibold">${analysis.price_data['52_week_low']?.toFixed(2) || '0.00'}</p>
              </div>
            </div>
          </div>

          {/* Technical Analysis */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <BarChart3 size={24} className="text-blue-600" />
              Technical Analysis
            </h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h3 className="font-semibold mb-3">Indicators</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Trend:</span>
                    <span className={`font-semibold ${analysis.technical_analysis.trend === 'bullish' ? 'text-green-600' : 'text-red-600'}`}>
                      {analysis.technical_analysis.trend?.toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">RSI:</span>
                    <span className="font-semibold">{analysis.technical_analysis.rsi}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">SMA 20:</span>
                    <span className="font-semibold">${analysis.technical_analysis.sma_20}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">SMA 50:</span>
                    <span className="font-semibold">${analysis.technical_analysis.sma_50}</span>
                  </div>
                </div>
              </div>
              <div>
                <h3 className="font-semibold mb-3">Support & Resistance</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Next Support:</span>
                    <span className="font-semibold text-green-600">${analysis.technical_analysis.next_support?.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Next Resistance:</span>
                    <span className="font-semibold text-red-600">${analysis.technical_analysis.next_resistance?.toFixed(2)}</span>
                  </div>
                  {analysis.technical_analysis.abc_pattern?.pattern === 'abc_detected' && (
                    <div className="mt-3 p-3 bg-blue-50 rounded-lg">
                      <p className="text-sm font-semibold text-blue-900">ABC Pattern Detected</p>
                      <p className="text-xs text-blue-700">Projection: ${analysis.technical_analysis.abc_pattern.projection?.toFixed(2)}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Social Sentiment */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <MessageSquare size={24} className="text-purple-600" />
              Social Sentiment
            </h2>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <p className="text-sm text-gray-600 mb-1">Overall Sentiment</p>
                <p className="text-2xl font-bold text-purple-900">{analysis.social_sentiment.overall_sentiment?.toUpperCase()}</p>
                <p className="text-sm text-purple-700">Score: {(analysis.social_sentiment.sentiment_score * 100).toFixed(0)}%</p>
              </div>
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <p className="text-sm text-gray-600 mb-1">Twitter Mentions</p>
                <p className="text-2xl font-bold text-blue-900">{analysis.social_sentiment.twitter_mentions?.toLocaleString()}</p>
                <p className="text-sm text-blue-700">{analysis.social_sentiment.twitter_sentiment}</p>
              </div>
              <div className="text-center p-4 bg-orange-50 rounded-lg">
                <p className="text-sm text-gray-600 mb-1">Reddit Mentions</p>
                <p className="text-2xl font-bold text-orange-900">{analysis.social_sentiment.reddit_mentions?.toLocaleString()}</p>
                <p className="text-sm text-orange-700">{analysis.social_sentiment.reddit_sentiment}</p>
              </div>
            </div>
          </div>

          {/* News Analysis */}
          {analysis.news_analysis.recent_news && (
            <div className="bg-white p-6 rounded-xl border border-gray-200">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Globe size={24} className="text-indigo-600" />
                Recent News
              </h2>
              <div className="space-y-3">
                {analysis.news_analysis.recent_news.map((news: any, idx: number) => (
                  <div key={idx} className="p-3 border-l-4 border-gray-300 bg-gray-50 rounded">
                    <p className="font-semibold text-sm">{news.title}</p>
                    <div className="flex justify-between items-center mt-2">
                      <span className="text-xs text-gray-600">{news.publisher}</span>
                      <span className={`text-xs px-2 py-1 rounded ${
                        news.sentiment === 'positive' ? 'bg-green-100 text-green-800' :
                        news.sentiment === 'negative' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {news.sentiment}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Market Calendar */}
          {analysis.market_calendar.upcoming_events && (
            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-6 rounded-lg">
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Calendar size={24} className="text-yellow-600" />
                Upcoming Market Events
              </h2>
              <p className="text-sm text-yellow-800 mb-4">{analysis.market_calendar.warning}</p>
              <div className="space-y-2">
                {analysis.market_calendar.upcoming_events.map((event: any, idx: number) => (
                  <div key={idx} className="flex justify-between items-center p-3 bg-white rounded">
                    <div>
                      <p className="font-semibold">{event.event}</p>
                      <p className="text-sm text-gray-600">{event.impact}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold">{event.date}</p>
                      <span className={`text-xs px-2 py-1 rounded ${
                        event.importance === 'high' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {event.importance}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Recommendation */}
          <div className="bg-gradient-to-br from-purple-50 to-indigo-50 p-6 rounded-xl border border-purple-200">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <Activity size={24} className="text-purple-600" />
              AI Recommendation
            </h2>
            <div className="mb-4">
              <span className={`${getRatingColor(analysis.ai_recommendation.rating)} text-white px-4 py-2 rounded-lg font-bold text-lg`}>
                {getRatingText(analysis.ai_recommendation.rating)}
              </span>
              <span className="ml-3 text-sm text-gray-600">
                Confidence: {(analysis.ai_recommendation.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <div className="bg-white p-4 rounded-lg mb-4">
              <p className="text-gray-800 whitespace-pre-line">{analysis.ai_recommendation.analysis}</p>
            </div>
            <div>
              <p className="text-sm font-semibold text-purple-900 mb-2">Factors Considered:</p>
              <ul className="text-sm text-purple-800 space-y-1">
                {analysis.ai_recommendation.factors_considered?.map((factor: string, idx: number) => (
                  <li key={idx}>• {factor}</li>
                ))}
              </ul>
            </div>
          </div>

          {/* Data Sources */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h2 className="text-xl font-bold mb-4">📊 Data Sources Used</h2>
            <div className="grid md:grid-cols-3 gap-3">
              {analysis.data_sources_used.map((source: any, idx: number) => (
                <a
                  key={idx}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-3 border border-gray-200 rounded-lg hover:shadow-md transition-shadow"
                >
                  <p className="font-semibold text-sm">{source.name}</p>
                  <p className="text-xs text-gray-600">{source.type}</p>
                </a>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
