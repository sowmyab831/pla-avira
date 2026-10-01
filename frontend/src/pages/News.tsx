import { useState, useEffect } from 'react'
import { Newspaper, TrendingUp, Calendar, ExternalLink } from 'lucide-react'
import config from '../config'

export default function News() {
  const [activeTab, setActiveTab] = useState<'knowledge' | 'financial' | 'tech' | 'influencers'>('knowledge')
  const [knowledgePill, setKnowledgePill] = useState<any>(null)
  const [financialNews, setFinancialNews] = useState<any>(null)
  const [techNews, setTechNews] = useState<any>(null)
  const [presidentialNews, setPresidentialNews] = useState<any>(null)
  const [, setLoading] = useState(false)
  const [region, setRegion] = useState('global')

  useEffect(() => {
    fetchKnowledgePill()
    fetchFinancialNews('global')
    fetchTechNews()
    fetchPresidentialNews()
  }, [])

  const fetchKnowledgePill = async () => {
    try {
      const response = await fetch(`${config.apiBase}/api/news/knowledge-pill`)
      const data = await response.json()
      if (data.success) {
        setKnowledgePill(data)
      }
    } catch (error) {
      console.error('Failed to fetch knowledge pill:', error)
    }
  }

  const fetchFinancialNews = async (selectedRegion: string) => {
    try {
      setLoading(true)
      const response = await fetch(`${config.apiBase}/api/news/financial/daily?region=${selectedRegion}`)
      const data = await response.json()
      if (data.success) {
        setFinancialNews(data)
      }
    } catch (error) {
      console.error('Failed to fetch financial news:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchTechNews = async () => {
    try {
      const response = await fetch(`${config.apiBase}/api/news/tech/daily`)
      const data = await response.json()
      if (data.success) {
        setTechNews(data)
      }
    } catch (error) {
      console.error('Failed to fetch tech news:', error)
    }
  }

  const fetchPresidentialNews = async () => {
    try {
      const response = await fetch(`${config.apiBase}/api/news/market-influencers`)
      const data = await response.json()
      if (data.success) {
        setPresidentialNews(data)
      }
    } catch (error) {
      console.error('Failed to fetch market influencers:', error)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
            <Newspaper className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">News & Markets</h1>
            <p className="text-gray-600">Stay updated with daily market brief and tech innovations</p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mb-8 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('knowledge')}
          className={`px-6 py-3 font-semibold transition-colors border-b-2 ${
            activeTab === 'knowledge'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          💊 Knowledge Pill
        </button>
        <button
          onClick={() => setActiveTab('financial')}
          className={`px-6 py-3 font-semibold transition-colors border-b-2 ${
            activeTab === 'financial'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          📈 Financial News
        </button>
        <button
          onClick={() => setActiveTab('tech')}
          className={`px-6 py-3 font-semibold transition-colors border-b-2 ${
            activeTab === 'tech'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          💻 Tech News
        </button>
        <button
          onClick={() => setActiveTab('influencers')}
          className={`px-6 py-3 font-semibold transition-colors border-b-2 ${
            activeTab === 'influencers'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-600 hover:text-gray-900'
          }`}
        >
          👥 Market Influencers
        </button>
      </div>

      {/* Knowledge Pill Tab */}
      {activeTab === 'knowledge' && knowledgePill && (
        <div className="space-y-6">
          {/* Daily Brief */}
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-8 rounded-xl border border-blue-200">
            <h2 className="text-2xl font-bold text-blue-900 mb-4">{knowledgePill.pill_of_the_day?.title}</h2>
            <p className="text-blue-800 mb-6">{knowledgePill.pill_of_the_day?.summary}</p>
            
            <div className="space-y-3">
              <h3 className="font-semibold text-blue-900">Key Takeaways:</h3>
              {knowledgePill.pill_of_the_day?.key_takeaways?.map((takeaway: string, i: number) => (
                <div key={i} className="bg-white p-4 rounded-lg border border-blue-200">
                  <p className="text-blue-800">{takeaway}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Market Movers */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-white p-6 rounded-xl border border-gray-200">
              <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                <TrendingUp className="text-green-600" size={20} />
                Top Gainers
              </h3>
              <div className="space-y-3">
                {knowledgePill.market_movers?.top_gainers?.map((stock: any, i: number) => (
                  <div key={i} className="flex justify-between items-center p-3 bg-green-50 rounded-lg">
                    <div>
                      <p className="font-bold text-gray-900">{stock.symbol}</p>
                      <p className="text-sm text-gray-600">{stock.reason}</p>
                    </div>
                    <p className="text-lg font-bold text-green-600">{stock.change}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white p-6 rounded-xl border border-gray-200">
              <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
                <TrendingUp className="text-red-600 transform rotate-180" size={20} />
                Top Losers
              </h3>
              <div className="space-y-3">
                {knowledgePill.market_movers?.top_losers?.map((stock: any, i: number) => (
                  <div key={i} className="flex justify-between items-center p-3 bg-red-50 rounded-lg">
                    <div>
                      <p className="font-bold text-gray-900">{stock.symbol}</p>
                      <p className="text-sm text-gray-600">{stock.reason}</p>
                    </div>
                    <p className="text-lg font-bold text-red-600">{stock.change}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sector Performance */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h3 className="font-semibold text-lg mb-4">Sector Performance</h3>
            <div className="grid md:grid-cols-5 gap-4">
              {Object.entries(knowledgePill.sector_performance || {}).map(([sector, performance]: [string, any]) => (
                <div key={sector} className="text-center p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-600 capitalize mb-2">{sector}</p>
                  <p className={`text-xl font-bold ${performance.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                    {performance}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Action Items */}
          <div className="bg-yellow-50 p-6 rounded-xl border border-yellow-200">
            <h3 className="font-semibold text-lg mb-4 text-yellow-900">📋 Action Items for Today</h3>
            <div className="space-y-2">
              {knowledgePill.action_items?.map((item: string, i: number) => (
                <div key={i} className="flex items-start gap-2">
                  <span className="text-yellow-600">•</span>
                  <p className="text-yellow-900">{item}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Financial News Tab */}
      {activeTab === 'financial' && (
        <div className="space-y-6">
          {/* Region Selector */}
          <div className="flex gap-2">
            {['global', 'usa', 'india'].map((r) => (
              <button
                key={r}
                onClick={() => { setRegion(r); fetchFinancialNews(r); }}
                className={`px-4 py-2 rounded-lg font-medium ${
                  region === r
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {r === 'global' ? '🌍 Global' : r === 'usa' ? '🇺🇸 USA' : '🇮🇳 India'}
              </button>
            ))}
          </div>

          {financialNews && (
            <>
              {/* Market Summary */}
              <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-6 rounded-xl border border-green-200">
                <h3 className="font-semibold text-lg mb-2 text-green-900">Market Summary</h3>
                <p className="text-green-800 capitalize">Overall Sentiment: <span className="font-bold">{financialNews.market_summary?.overall_sentiment}</span></p>
                <div className="mt-4">
                  <p className="text-sm text-green-800 mb-2">Key Themes:</p>
                  <div className="flex flex-wrap gap-2">
                    {financialNews.market_summary?.key_themes?.map((theme: string, i: number) => (
                      <span key={i} className="px-3 py-1 bg-white rounded-full text-sm text-green-700">{theme}</span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Headlines */}
              <div className="space-y-4">
                {financialNews.headlines?.map((headline: any, i: number) => (
                  <div key={i} className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="font-bold text-lg text-gray-900 mb-2">{headline.title}</h3>
                        <p className="text-gray-600 mb-3">{headline.summary}</p>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-gray-500">{headline.source}</span>
                          <span className={`px-2 py-1 rounded ${
                            headline.impact === 'bullish' ? 'bg-green-100 text-green-700' :
                            headline.impact === 'bearish' ? 'bg-red-100 text-red-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {headline.impact}
                          </span>
                          <span className="text-gray-400">{headline.timestamp}</span>
                        </div>
                      </div>
                      <a
                        href={headline.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-700"
                      >
                        <ExternalLink size={20} />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Tech News Tab */}
      {activeTab === 'tech' && techNews && (
        <div className="space-y-6">
          {/* Trending Topics */}
          <div className="bg-gradient-to-br from-purple-50 to-pink-50 p-6 rounded-xl border border-purple-200">
            <h3 className="font-semibold text-lg mb-4 text-purple-900">🔥 Trending Topics</h3>
            <div className="flex flex-wrap gap-2">
              {techNews.trending_topics?.map((topic: string, i: number) => (
                <span key={i} className="px-4 py-2 bg-white rounded-full text-purple-700 font-medium">{topic}</span>
              ))}
            </div>
          </div>

          {/* Headlines */}
          <div className="space-y-4">
            {techNews.headlines?.map((headline: any, i: number) => (
              <div key={i} className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="font-bold text-lg text-gray-900 mb-2">{headline.title}</h3>
                    <p className="text-gray-600 mb-3">{headline.summary}</p>
                    <div className="flex items-center gap-4 text-sm flex-wrap">
                      <span className="text-gray-500">{headline.source}</span>
                      <span className="px-2 py-1 bg-purple-100 text-purple-700 rounded">{headline.category}</span>
                      {headline.companies_affected?.map((symbol: string, j: number) => (
                        <span key={j} className="px-2 py-1 bg-blue-100 text-blue-700 rounded font-mono">{symbol}</span>
                      ))}
                    </div>
                  </div>
                  <a
                    href={headline.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-700"
                  >
                    <ExternalLink size={20} />
                  </a>
                </div>
              </div>
            ))}
          </div>

          {/* Upcoming Events */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h3 className="font-semibold text-lg mb-4 flex items-center gap-2">
              <Calendar className="text-indigo-600" size={20} />
              Upcoming Tech Events
            </h3>
            <div className="space-y-3">
              {techNews.upcoming_events?.map((event: any, i: number) => (
                <div key={i} className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="font-semibold text-gray-900">{event.event}</p>
                    <p className="text-sm text-gray-600">{event.significance}</p>
                  </div>
                  <span className="text-sm text-gray-500">{event.date}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Market Influencers Tab */}
      {activeTab === 'influencers' && presidentialNews && (
        <div className="space-y-6">
          {/* Recent Statements */}
          <div className="space-y-4">
            {presidentialNews.recent_statements?.map((statement: any, i: number) => (
              <div key={i} className="bg-white p-6 rounded-xl border border-gray-200">
                <h3 className="font-bold text-lg text-gray-900 mb-2">{statement.statement}</h3>
                <p className="text-gray-600 mb-4">{statement.summary}</p>
                
                {/* Market Impact */}
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-semibold text-blue-900 mb-3">Market Impact:</h4>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-blue-800 mb-2">Sectors Benefiting:</p>
                      <div className="flex flex-wrap gap-2">
                        {statement.market_impact?.sectors_benefiting?.map((sector: string, j: number) => (
                          <span key={j} className="px-2 py-1 bg-green-100 text-green-700 rounded text-sm">{sector}</span>
                        ))}
                      </div>
                    </div>
                    <div>
                      <p className="text-sm text-blue-800 mb-2">Affected Stocks:</p>
                      <div className="flex flex-wrap gap-2">
                        {statement.market_impact?.affected_stocks?.map((symbol: string, j: number) => (
                          <span key={j} className="px-2 py-1 bg-blue-100 text-blue-700 rounded font-mono text-sm">{symbol}</span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <p className="mt-3 text-sm text-blue-800">
                    <span className="font-semibold">Market Reaction:</span> {statement.market_impact?.market_reaction}
                  </p>
                </div>
                
                <div className="mt-4 flex items-center gap-4 text-sm text-gray-500">
                  <span>{statement.source}</span>
                  <span>{statement.date}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Upcoming Events */}
          <div className="bg-white p-6 rounded-xl border border-gray-200">
            <h3 className="font-semibold text-lg mb-4">Upcoming Policy Events</h3>
            <div className="space-y-3">
              {presidentialNews.upcoming_events?.map((event: any, i: number) => (
                <div key={i} className="p-4 bg-gray-50 rounded-lg">
                  <p className="font-semibold text-gray-900">{event.event}</p>
                  <p className="text-sm text-gray-600 mt-1">Expected Topics: {event.expected_topics?.join(', ')}</p>
                  <p className="text-sm text-blue-600 mt-2">💡 {event.market_watch}</p>
                  <span className="text-xs text-gray-500">{event.date}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
