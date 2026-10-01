import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, BarChart2, LineChart, CandlestickChart, Activity } from 'lucide-react'
import config from '../config'

interface StockChartProps {
  symbol: string
  technicalData?: {
    sma_20?: number
    sma_50?: number
    rsi?: number
    support_levels?: number[]
    resistance_levels?: number[]
    abc_pattern?: {
      pattern?: string
      point_a?: number
      point_b?: number
      point_c?: number
      projection?: number
    }
  }
}

interface PricePoint {
  timestamp: number
  date: string
  price: number
  open?: number
  high?: number
  low?: number
  close?: number
  volume?: number
}

type ChartType = 'line' | 'candle' | 'area' | 'elliott'

export default function StockChart({ symbol, technicalData }: StockChartProps) {
  const [period, setPeriod] = useState('1m')
  const [chartType, setChartType] = useState<ChartType>('area')
  const [showIndicators, setShowIndicators] = useState(true)
  const [data, setData] = useState<PricePoint[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchChartData()
  }, [symbol, period])

  const fetchChartData = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/historical?period=${period}`)
      const result = await response.json()
      
      if (result.success) {
        setData(result.prices || [])
      } else {
        setError(result.error || 'Failed to load chart data')
      }
    } catch (err) {
      setError('Failed to fetch chart data')
      console.error('Chart error:', err)
    } finally {
      setLoading(false)
    }
  }

  const getChartPoints = () => {
    if (data.length === 0) return ''
    
    const maxPrice = Math.max(...data.map(d => d.price))
    const minPrice = Math.min(...data.map(d => d.price))
    const priceRange = maxPrice - minPrice || 1
    
    const width = 100
    const height = 60
    
    return data.map((point, i) => {
      const x = (i / (data.length - 1)) * width
      const y = height - ((point.price - minPrice) / priceRange) * height
      return `${x},${y}`
    }).join(' ')
  }

  const getPriceChange = () => {
    if (data.length < 2) return { value: 0, percent: 0 }
    
    const firstPrice = data[0].price
    const lastPrice = data[data.length - 1].price
    const change = lastPrice - firstPrice
    const percent = (change / firstPrice) * 100
    
    return { value: change, percent }
  }

  const change = getPriceChange()
  const isPositive = change.value >= 0

  // Calculate support/resistance lines for chart
  const getSupportResistanceLines = () => {
    if (!technicalData || data.length === 0) return null
    
    const maxPrice = Math.max(...data.map(d => d.price))
    const minPrice = Math.min(...data.map(d => d.price))
    const priceRange = maxPrice - minPrice || 1
    const height = 60
    
    const lines: JSX.Element[] = []
    
    // Support levels
    technicalData.support_levels?.slice(0, 2).forEach((level, i) => {
      if (level >= minPrice && level <= maxPrice) {
        const y = height - ((level - minPrice) / priceRange) * height
        lines.push(
          <line key={`support-${i}`} x1="0" y1={y} x2="100" y2={y} stroke="#10b981" strokeWidth="0.3" strokeDasharray="2,2" />
        )
      }
    })
    
    // Resistance levels
    technicalData.resistance_levels?.slice(0, 2).forEach((level, i) => {
      if (level >= minPrice && level <= maxPrice) {
        const y = height - ((level - minPrice) / priceRange) * height
        lines.push(
          <line key={`resistance-${i}`} x1="0" y1={y} x2="100" y2={y} stroke="#ef4444" strokeWidth="0.3" strokeDasharray="2,2" />
        )
      }
    })
    
    // SMA lines
    if (technicalData.sma_20 && technicalData.sma_20 >= minPrice && technicalData.sma_20 <= maxPrice) {
      const y = height - ((technicalData.sma_20 - minPrice) / priceRange) * height
      lines.push(
        <line key="sma20" x1="0" y1={y} x2="100" y2={y} stroke="#3b82f6" strokeWidth="0.3" strokeDasharray="4,2" />
      )
    }
    
    if (technicalData.sma_50 && technicalData.sma_50 >= minPrice && technicalData.sma_50 <= maxPrice) {
      const y = height - ((technicalData.sma_50 - minPrice) / priceRange) * height
      lines.push(
        <line key="sma50" x1="0" y1={y} x2="100" y2={y} stroke="#8b5cf6" strokeWidth="0.3" strokeDasharray="4,2" />
      )
    }
    
    return lines
  }
  
  // Elliott Wave points
  const getElliottWavePoints = () => {
    if (!technicalData?.abc_pattern || data.length === 0) return null
    
    const { point_a, point_b, point_c, projection } = technicalData.abc_pattern
    if (!point_a || !point_b || !point_c) return null
    
    const maxPrice = Math.max(...data.map(d => d.price), point_a, point_b, point_c, projection || 0)
    const minPrice = Math.min(...data.map(d => d.price), point_a, point_b, point_c)
    const priceRange = maxPrice - minPrice || 1
    const height = 60
    
    const yA = height - ((point_a - minPrice) / priceRange) * height
    const yB = height - ((point_b - minPrice) / priceRange) * height
    const yC = height - ((point_c - minPrice) / priceRange) * height
    const yProj = projection ? height - ((projection - minPrice) / priceRange) * height : yC
    
    return (
      <g>
        <polyline 
          points={`20,${yA} 50,${yB} 80,${yC} ${projection ? `100,${yProj}` : ''}`}
          fill="none"
          stroke="#8b5cf6"
          strokeWidth="0.8"
          strokeDasharray="3,2"
        />
        <circle cx="20" cy={yA} r="2" fill="#ef4444" />
        <circle cx="50" cy={yB} r="2" fill="#f59e0b" />
        <circle cx="80" cy={yC} r="2" fill="#10b981" />
        {projection && <circle cx="100" cy={yProj} r="2" fill="#8b5cf6" />}
        <text x="18" y={yA - 3} fontSize="4" fill="#ef4444">A</text>
        <text x="48" y={yB - 3} fontSize="4" fill="#f59e0b">B</text>
        <text x="78" y={yC - 3} fontSize="4" fill="#10b981">C</text>
        {projection && <text x="96" y={yProj - 3} fontSize="4" fill="#8b5cf6">P</text>}
      </g>
    )
  }

  return (
    <div className="bg-white rounded-lg p-4 border border-gray-200">
      {/* Header with controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 className="font-semibold text-gray-900">{symbol} Price Chart</h3>
        <div className="flex flex-wrap gap-2">
          {/* Chart type selector */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setChartType('area')}
              className={`p-1.5 rounded ${chartType === 'area' ? 'bg-white shadow' : 'hover:bg-gray-200'}`}
              title="Area Chart"
            >
              <Activity size={14} />
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`p-1.5 rounded ${chartType === 'line' ? 'bg-white shadow' : 'hover:bg-gray-200'}`}
              title="Line Chart"
            >
              <LineChart size={14} />
            </button>
            <button
              onClick={() => setChartType('candle')}
              className={`p-1.5 rounded ${chartType === 'candle' ? 'bg-white shadow' : 'hover:bg-gray-200'}`}
              title="Candlestick"
            >
              <CandlestickChart size={14} />
            </button>
            <button
              onClick={() => setChartType('elliott')}
              className={`p-1.5 rounded ${chartType === 'elliott' ? 'bg-white shadow' : 'hover:bg-gray-200'}`}
              title="Elliott Wave"
            >
              <BarChart2 size={14} />
            </button>
          </div>
          
          {/* Period selector */}
          <div className="flex gap-1">
            {['1d', '1w', '1m', '3m', '1y'].map(p => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-2 py-1 text-xs rounded ${
                  period === p
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {p}
              </button>
            ))}
          </div>
          
          {/* Indicators toggle */}
          <button
            onClick={() => setShowIndicators(!showIndicators)}
            className={`px-2 py-1 text-xs rounded ${showIndicators ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600'}`}
          >
            Indicators
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {error && (
        <div className="text-center text-red-600 py-8 text-sm">{error}</div>
      )}

      {!loading && !error && data.length > 0 && (
        <>
          <div className="mb-3">
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold">${data[data.length - 1].price.toFixed(2)}</span>
              <div className={`flex items-center gap-1 ${isPositive ? 'text-green-600' : 'text-red-600'}`}>
                {isPositive ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                <span className="text-sm font-medium">
                  {isPositive ? '+' : ''}{change.value.toFixed(2)} ({change.percent.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>

          {/* Main Chart */}
          <svg viewBox="0 0 100 60" className="w-full h-48" preserveAspectRatio="none">
            <defs>
              <linearGradient id={`gradient-${symbol}`} x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0.3" />
                <stop offset="100%" stopColor={isPositive ? '#10b981' : '#ef4444'} stopOpacity="0.05" />
              </linearGradient>
            </defs>
            
            {/* Support/Resistance lines */}
            {showIndicators && getSupportResistanceLines()}
            
            {/* Area fill */}
            {(chartType === 'area' || chartType === 'elliott') && (
              <polyline
                points={`0,60 ${getChartPoints()} 100,60`}
                fill={`url(#gradient-${symbol})`}
              />
            )}
            
            {/* Price line */}
            <polyline
              points={getChartPoints()}
              fill="none"
              stroke={isPositive ? '#10b981' : '#ef4444'}
              strokeWidth={chartType === 'line' ? '0.8' : '0.5'}
            />
            
            {/* Elliott Wave overlay */}
            {chartType === 'elliott' && getElliottWavePoints()}
          </svg>

          {/* Time labels */}
          <div className="flex justify-between text-xs text-gray-500 mt-2">
            <span>{new Date(data[0].date).toLocaleDateString()}</span>
            <span>{new Date(data[data.length - 1].date).toLocaleDateString()}</span>
            {technicalData?.abc_pattern?.projection && (
              <span className="text-purple-600 font-medium">→ Projection</span>
            )}
          </div>
          
          {/* Future Projection Card */}
          {technicalData?.abc_pattern?.projection && (
            <div className="mt-3 p-3 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-sm text-purple-700 font-medium">📈 AI Price Projection</span>
                  <p className="text-xs text-purple-600 mt-1">Based on Elliott Wave & Technical Analysis</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-purple-700">${technicalData.abc_pattern.projection.toFixed(2)}</div>
                  <div className={`text-sm ${technicalData.abc_pattern.projection > data[data.length - 1].price ? 'text-green-600' : 'text-red-600'}`}>
                    {technicalData.abc_pattern.projection > data[data.length - 1].price ? '↑' : '↓'} 
                    {((technicalData.abc_pattern.projection - data[data.length - 1].price) / data[data.length - 1].price * 100).toFixed(1)}% from current
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* Legend */}
          {showIndicators && technicalData && (
            <div className="flex flex-wrap gap-4 mt-3 pt-3 border-t border-gray-100 text-xs">
              {technicalData.sma_20 && (
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-blue-500"></div>
                  <span className="text-gray-600">SMA 20: ${technicalData.sma_20.toFixed(2)}</span>
                </div>
              )}
              {technicalData.sma_50 && (
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-purple-500"></div>
                  <span className="text-gray-600">SMA 50: ${technicalData.sma_50.toFixed(2)}</span>
                </div>
              )}
              {technicalData.rsi && (
                <div className="flex items-center gap-1">
                  <span className={`font-semibold ${technicalData.rsi > 70 ? 'text-red-600' : technicalData.rsi < 30 ? 'text-green-600' : 'text-gray-700'}`}>
                    RSI: {technicalData.rsi.toFixed(1)}
                  </span>
                </div>
              )}
              {technicalData.support_levels?.[0] && (
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-green-500" style={{ borderStyle: 'dashed' }}></div>
                  <span className="text-green-600">Support: ${technicalData.support_levels[0].toFixed(2)}</span>
                </div>
              )}
              {technicalData.resistance_levels?.[0] && (
                <div className="flex items-center gap-1">
                  <div className="w-3 h-0.5 bg-red-500" style={{ borderStyle: 'dashed' }}></div>
                  <span className="text-red-600">Resistance: ${technicalData.resistance_levels[0].toFixed(2)}</span>
                </div>
              )}
            </div>
          )}
          
          {/* Elliott Wave Info */}
          {chartType === 'elliott' && technicalData?.abc_pattern && (
            <div className="mt-3 p-3 bg-purple-50 rounded-lg">
              <h4 className="font-semibold text-purple-900 text-sm mb-2">Elliott Wave Analysis</h4>
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div>
                  <span className="text-gray-600">Pattern:</span>
                  <span className="font-semibold ml-1 capitalize">{technicalData.abc_pattern.pattern?.replace(/_/g, ' ')}</span>
                </div>
                {technicalData.abc_pattern.point_a && (
                  <div>
                    <span className="text-red-600">A:</span>
                    <span className="font-semibold ml-1">${technicalData.abc_pattern.point_a.toFixed(2)}</span>
                  </div>
                )}
                {technicalData.abc_pattern.point_b && (
                  <div>
                    <span className="text-yellow-600">B:</span>
                    <span className="font-semibold ml-1">${technicalData.abc_pattern.point_b.toFixed(2)}</span>
                  </div>
                )}
                {technicalData.abc_pattern.point_c && (
                  <div>
                    <span className="text-green-600">C:</span>
                    <span className="font-semibold ml-1">${technicalData.abc_pattern.point_c.toFixed(2)}</span>
                  </div>
                )}
                {technicalData.abc_pattern.projection && (
                  <div className="col-span-4 mt-1 pt-1 border-t border-purple-200">
                    <span className="text-purple-600">Projected Target:</span>
                    <span className="font-bold ml-1 text-purple-700">${technicalData.abc_pattern.projection.toFixed(2)}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {!loading && !error && data.length === 0 && (
        <div className="text-center text-gray-500 py-8 text-sm">No chart data available</div>
      )}
    </div>
  )
}
