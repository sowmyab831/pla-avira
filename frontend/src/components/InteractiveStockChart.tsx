import { useState, useEffect, useRef, useCallback } from 'react'
import { TrendingUp, TrendingDown, ZoomIn, ZoomOut, ChevronLeft, ChevronRight, RefreshCw, Maximize2, Minimize2, ChevronDown, Target, AlertTriangle, ArrowUpCircle, ArrowDownCircle, Activity } from 'lucide-react'
import config from '../config'

// Chart Pattern definitions with explanations
const CHART_PATTERNS = [
  {
    id: 'elliott_impulse',
    name: '5-Wave Impulse (Elliott)',
    description: 'Identifies the overall market direction (5 waves in direction of trend) to trade in line with the major market move.',
    howToRead: 'Look for 5 distinct waves: Wave 1 starts the trend, Wave 2 retraces, Wave 3 is the strongest move, Wave 4 is a smaller correction, Wave 5 completes the pattern. Enter on Wave 2 or 4 corrections.',
    signal: 'bullish'
  },
  {
    id: 'elliott_abc',
    name: '3-Wave Correction (A-B-C)',
    description: 'Used to identify the end of a pullback in an uptrend (or rally in a downtrend) to enter the market at a lower risk point.',
    howToRead: 'Wave A starts the correction, Wave B partially retraces A, Wave C completes the correction. Look to enter when Wave C completes near support levels.',
    signal: 'reversal'
  },
  {
    id: 'head_shoulders',
    name: 'Head and Shoulders',
    description: 'Highly reliable pattern indicating a potential bearish reversal after an uptrend. Easiest to spot by identifying a peak, a higher peak, and a lower peak.',
    howToRead: 'Left shoulder forms first, then head (higher peak), then right shoulder (similar to left). Neckline connects the lows. Break below neckline confirms reversal.',
    signal: 'bearish'
  },
  {
    id: 'double_top',
    name: 'Double Top/Bottom',
    description: 'An "M" shape (top) or "W" shape (bottom) that indicates a strong reversal point after two failed attempts to break a support or resistance level.',
    howToRead: 'Double Top: Two peaks at similar levels with a valley between. Sell when price breaks below the valley. Double Bottom: Opposite - two valleys with a peak between. Buy when price breaks above the peak.',
    signal: 'reversal'
  },
  {
    id: 'cup_handle',
    name: 'Cup and Handle',
    description: 'A bullish pattern indicating a period of consolidation (the handle) before an uptrend continues, frequently seen as a reliable, high-profit opportunity.',
    howToRead: 'The cup forms a rounded bottom over weeks/months. The handle is a small pullback (flag-like). Buy when price breaks above the handle resistance with increased volume.',
    signal: 'bullish'
  },
  {
    id: 'flag_pennant',
    name: 'Flag and Pennant',
    description: 'Identifies a short-term pause (consolidation) after a sharp price move (the "flagpole") before the trend resumes. These are low-risk, high-reward continuation setups.',
    howToRead: 'Flag: Parallel channel sloping against the trend. Pennant: Small symmetrical triangle. Enter when price breaks out in the direction of the original move.',
    signal: 'continuation'
  },
  {
    id: 'ascending_triangle',
    name: 'Ascending Triangle',
    description: 'A horizontal resistance line matched with rising lows. It signals a bullish continuation where buyers are gaining strength.',
    howToRead: 'Flat top resistance with higher lows forming the ascending trendline. Volume typically decreases during formation. Buy on breakout above resistance.',
    signal: 'bullish'
  },
  {
    id: 'descending_triangle',
    name: 'Descending Triangle',
    description: 'A horizontal support line matched with falling highs. It signals a bearish continuation where sellers are gaining control.',
    howToRead: 'Flat bottom support with lower highs forming the descending trendline. Sell/short when price breaks below support with volume confirmation.',
    signal: 'bearish'
  },
  {
    id: 'falling_wedge',
    name: 'Falling Wedge',
    description: 'A pattern where price tightens between two downwardly sloping lines, usually signaling a bullish breakout.',
    howToRead: 'Both trendlines slope down but converge. Despite falling prices, buying pressure increases. Enter long when price breaks above the upper trendline.',
    signal: 'bullish'
  },
  {
    id: 'higher_highs',
    name: 'Higher Highs/Higher Lows',
    description: 'The most fundamental chart to read for trend identification, where an ascending staircase of prices confirms a steady uptrend.',
    howToRead: 'Each peak is higher than the previous peak (higher highs). Each valley is higher than the previous valley (higher lows). Trend remains valid until this pattern breaks.',
    signal: 'bullish'
  }
]

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
  open: number
  high: number
  low: number
  close: number
  volume: number
}

interface ChartDimensions {
  width: number
  height: number
  padding: { top: number; right: number; bottom: number; left: number }
}

type ChartType = 'line' | 'candle' | 'area'
type TimeInterval = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w'

const INTERVALS: { value: TimeInterval; label: string }[] = [
  { value: '1m', label: '1M' },
  { value: '5m', label: '5M' },
  { value: '15m', label: '15M' },
  { value: '30m', label: '30M' },
  { value: '1h', label: '1H' },
  { value: '4h', label: '4H' },
  { value: '1d', label: '1D' },
  { value: '1w', label: '1W' },
]

const PERIODS = [
  { value: '1d', label: '1D' },
  { value: '1w', label: '1W' },
  { value: '1m', label: '1M' },
  { value: '3m', label: '3M' },
  { value: '1y', label: '1Y' },
  { value: '5y', label: '5Y' },
]

export default function InteractiveStockChart({ symbol, technicalData }: StockChartProps) {
  const [period, setPeriod] = useState('1m')
  const [interval, setChartInterval] = useState<TimeInterval>('1d')
  const [chartType, setChartType] = useState<ChartType>('candle')
  const [showIndicators, setShowIndicators] = useState(true)
  const [data, setData] = useState<PricePoint[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Interactive state
  const [viewStart, setViewStart] = useState(0)
  const [viewEnd, setViewEnd] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, viewStart: 0 })
  const [hoveredPoint, setHoveredPoint] = useState<PricePoint | null>(null)
  const [hoverPosition, setHoverPosition] = useState({ x: 0, y: 0 })
  
  // New features state
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [selectedPattern, setSelectedPattern] = useState(CHART_PATTERNS[0])
  const [showPatternDropdown, setShowPatternDropdown] = useState(false)
  const [scrollVelocity, setScrollVelocity] = useState(0)
  const [lastScrollTime, setLastScrollTime] = useState(0)
  const [intradayData, setIntradayData] = useState<any>(null)
  const [intradayLoading, setIntradayLoading] = useState(false)
  
  const chartRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const fullscreenRef = useRef<HTMLDivElement>(null)
  
  const VISIBLE_POINTS = 20
  const MIN_VISIBLE_POINTS = 10
  const MAX_VISIBLE_POINTS = 100
  
  // Dynamic dimensions based on fullscreen - use wider chart
  const [containerWidth, setContainerWidth] = useState(1200)
  
  // Measure container width for responsive chart
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const width = containerRef.current.offsetWidth || 1200
        setContainerWidth(Math.max(800, width))
      }
    }
    updateWidth()
    window.addEventListener('resize', updateWidth)
    return () => window.removeEventListener('resize', updateWidth)
  }, [])
  
  const dimensions: ChartDimensions = {
    width: isFullscreen ? Math.max(1400, containerWidth) : containerWidth,
    height: isFullscreen ? 600 : 450,
    padding: { top: 30, right: 80, bottom: 50, left: 80 }
  }
  
  // ESC key handler for fullscreen exit
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isFullscreen])
  
  // Smooth scrolling momentum effect (like Robinhood)
  useEffect(() => {
    if (Math.abs(scrollVelocity) < 0.5) return
    
    const animate = () => {
      setScrollVelocity(prev => {
        const newVelocity = prev * 0.92 // Friction
        if (Math.abs(newVelocity) < 0.5) return 0
        
        const step = Math.round(newVelocity)
        if (step !== 0) {
          setViewStart(current => {
            const visibleCount = viewEnd - current
            const newStart = Math.max(0, Math.min(data.length - visibleCount, current + step))
            setViewEnd(newStart + visibleCount)
            return newStart
          })
        }
        return newVelocity
      })
    }
    
    const frameId = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(frameId)
  }, [scrollVelocity, data.length, viewEnd])

  // Auto-select appropriate interval based on period
  useEffect(() => {
    const periodIntervalMap: Record<string, TimeInterval> = {
      '1d': '1m',
      '1w': '15m',
      '1m': '1d',
      '3m': '1d',
      '1y': '1d',
      '5y': '1w'
    }
    const autoInterval = periodIntervalMap[period] || '1d'
    if (interval !== autoInterval) {
      setChartInterval(autoInterval)
    }
  }, [period])

  useEffect(() => {
    fetchChartData()
  }, [symbol, period, interval])

  // Fetch intraday targets on mount + auto-refresh every 30s
  useEffect(() => {
    fetchIntradayTargets()
    const timer = setInterval(fetchIntradayTargets, 30000)
    return () => clearInterval(timer)
  }, [symbol])

  const fetchIntradayTargets = async () => {
    setIntradayLoading(true)
    try {
      const res = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/intraday-targets`)
      const json = await res.json()
      if (json.success) setIntradayData(json)
    } catch (e) {
      console.error('Intraday targets error:', e)
    } finally {
      setIntradayLoading(false)
    }
  }

  useEffect(() => {
    if (data.length > 0) {
      const end = data.length
      const start = Math.max(0, end - VISIBLE_POINTS)
      setViewStart(start)
      setViewEnd(end)
    }
  }, [data])

  const fetchChartData = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(
        `${config.apiBase}/api/portfolio/stocks/${symbol}/historical?period=${period}&interval=${interval}`
      )
      const result = await response.json()
      
      if (result.success && result.prices?.length > 0) {
        const prices = result.prices.map((p: any) => ({
          timestamp: p.timestamp || new Date(p.date).getTime(),
          date: p.date,
          price: p.close || p.price,
          open: p.open || p.price,
          high: p.high || p.price,
          low: p.low || p.price,
          close: p.close || p.price,
          volume: p.volume || 0
        }))
        setData(prices)
      } else {
        setError(result.error || 'No data available')
      }
    } catch (err) {
      setError('Failed to fetch chart data')
      console.error('Chart error:', err)
    } finally {
      setLoading(false)
    }
  }

  const visibleData = data.slice(viewStart, viewEnd)
  
  const getChartArea = () => ({
    x: dimensions.padding.left,
    y: dimensions.padding.top,
    width: dimensions.width - dimensions.padding.left - dimensions.padding.right,
    height: dimensions.height - dimensions.padding.top - dimensions.padding.bottom
  })

  const getPriceRange = useCallback(() => {
    if (visibleData.length === 0) return { min: 0, max: 100 }
    const prices = visibleData.flatMap(d => [d.high, d.low])
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const padding = (max - min) * 0.1
    return { min: min - padding, max: max + padding }
  }, [visibleData])

  const priceToY = useCallback((price: number) => {
    const { min, max } = getPriceRange()
    const area = getChartArea()
    return area.y + area.height - ((price - min) / (max - min)) * area.height
  }, [getPriceRange])

  const indexToX = useCallback((index: number) => {
    const area = getChartArea()
    const pointWidth = area.width / Math.max(visibleData.length - 1, 1)
    return area.x + index * pointWidth
  }, [visibleData.length])

  const xToIndex = useCallback((x: number) => {
    const area = getChartArea()
    const pointWidth = area.width / Math.max(visibleData.length - 1, 1)
    return Math.round((x - area.x) / pointWidth)
  }, [visibleData.length])

  // Mouse handlers for interactivity
  const handleMouseDown = (e: React.MouseEvent) => {
    if (!chartRef.current) return
    const rect = chartRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    setIsDragging(true)
    setDragStart({ x, viewStart })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!chartRef.current) return
    const rect = chartRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    
    if (isDragging) {
      const area = getChartArea()
      const pointWidth = area.width / Math.max(visibleData.length - 1, 1)
      const deltaPoints = Math.round((dragStart.x - x) / pointWidth)
      const newStart = Math.max(0, Math.min(data.length - (viewEnd - viewStart), dragStart.viewStart + deltaPoints))
      const visibleCount = viewEnd - viewStart
      setViewStart(newStart)
      setViewEnd(newStart + visibleCount)
    } else {
      // Hover detection
      const area = getChartArea()
      if (x >= area.x && x <= area.x + area.width && y >= area.y && y <= area.y + area.height) {
        const idx = xToIndex(x)
        if (idx >= 0 && idx < visibleData.length) {
          setHoveredPoint(visibleData[idx])
          setHoverPosition({ x, y })
        }
      } else {
        setHoveredPoint(null)
      }
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleMouseLeave = () => {
    setIsDragging(false)
    setHoveredPoint(null)
  }

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault()
    
    // Horizontal scroll (shift+wheel or trackpad horizontal) for panning like Robinhood
    if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
      const scrollAmount = e.shiftKey ? e.deltaY : e.deltaX
      const now = Date.now()
      const timeDelta = now - lastScrollTime
      setLastScrollTime(now)
      
      // Calculate velocity for momentum
      const velocity = scrollAmount / Math.max(timeDelta, 16) * 2
      setScrollVelocity(prev => prev * 0.5 + velocity)
      
      // Immediate scroll
      const step = Math.sign(scrollAmount) * Math.ceil(Math.abs(scrollAmount) / 50)
      const visibleCount = viewEnd - viewStart
      const newStart = Math.max(0, Math.min(data.length - visibleCount, viewStart + step))
      setViewStart(newStart)
      setViewEnd(newStart + visibleCount)
    } else {
      // Vertical scroll for zoom
      const delta = e.deltaY > 0 ? 2 : -2
      const currentVisible = viewEnd - viewStart
      const newVisible = Math.max(MIN_VISIBLE_POINTS, Math.min(MAX_VISIBLE_POINTS, currentVisible + delta))
      
      if (newVisible !== currentVisible) {
        const center = (viewStart + viewEnd) / 2
        const newStart = Math.max(0, Math.round(center - newVisible / 2))
        const newEnd = Math.min(data.length, newStart + newVisible)
        setViewStart(newStart)
        setViewEnd(newEnd)
      }
    }
  }
  
  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  // Navigation
  const panLeft = () => {
    const step = Math.max(1, Math.floor((viewEnd - viewStart) / 4))
    const newStart = Math.max(0, viewStart - step)
    const newEnd = newStart + (viewEnd - viewStart)
    setViewStart(newStart)
    setViewEnd(newEnd)
  }

  const panRight = () => {
    const step = Math.max(1, Math.floor((viewEnd - viewStart) / 4))
    const newEnd = Math.min(data.length, viewEnd + step)
    const newStart = newEnd - (viewEnd - viewStart)
    setViewStart(newStart)
    setViewEnd(newEnd)
  }

  const zoomIn = () => {
    const currentVisible = viewEnd - viewStart
    const newVisible = Math.max(MIN_VISIBLE_POINTS, currentVisible - 5)
    const center = (viewStart + viewEnd) / 2
    const newStart = Math.max(0, Math.round(center - newVisible / 2))
    const newEnd = Math.min(data.length, newStart + newVisible)
    setViewStart(newStart)
    setViewEnd(newEnd)
  }

  const zoomOut = () => {
    const currentVisible = viewEnd - viewStart
    const newVisible = Math.min(MAX_VISIBLE_POINTS, currentVisible + 5)
    const center = (viewStart + viewEnd) / 2
    const newStart = Math.max(0, Math.round(center - newVisible / 2))
    const newEnd = Math.min(data.length, newStart + newVisible)
    setViewStart(newStart)
    setViewEnd(newEnd)
  }

  // Render functions
  const renderGrid = () => {
    const area = getChartArea()
    const { min, max } = getPriceRange()
    const lines = []
    
    // Horizontal grid lines (price levels)
    const priceStep = (max - min) / 5
    for (let i = 0; i <= 5; i++) {
      const price = min + i * priceStep
      const y = priceToY(price)
      lines.push(
        <g key={`h-${i}`}>
          <line x1={area.x} y1={y} x2={area.x + area.width} y2={y} stroke="#e5e7eb" strokeWidth="1" />
          <text x={area.x - 5} y={y + 4} fontSize="10" fill="#6b7280" textAnchor="end">
            ${price.toFixed(2)}
          </text>
        </g>
      )
    }
    
    // Vertical grid lines (time labels) - show ~10 labels
    const step = Math.max(1, Math.floor(visibleData.length / 10))
    for (let i = 0; i < visibleData.length; i += step) {
      const x = indexToX(i)
      const point = visibleData[i]
      lines.push(
        <g key={`v-${i}`}>
          <line x1={x} y1={area.y} x2={x} y2={area.y + area.height} stroke="#f3f4f6" strokeWidth="1" />
          <text x={x} y={area.y + area.height + 15} fontSize="9" fill="#6b7280" textAnchor="middle">
            {formatDate(point.date, interval)}
          </text>
        </g>
      )
    }
    
    return lines
  }

  const formatDate = (dateStr: string, intv: TimeInterval) => {
    const date = new Date(dateStr)
    if (['1m', '5m', '15m', '30m', '1h', '4h'].includes(intv)) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  const renderCandlesticks = () => {
    const area = getChartArea()
    const candleWidth = Math.max(2, (area.width / visibleData.length) * 0.7)
    
    return visibleData.map((point, i) => {
      const x = indexToX(i)
      const openY = priceToY(point.open)
      const closeY = priceToY(point.close)
      const highY = priceToY(point.high)
      const lowY = priceToY(point.low)
      const isGreen = point.close >= point.open
      const color = isGreen ? '#10b981' : '#ef4444'
      
      return (
        <g key={i}>
          {/* Wick */}
          <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1" />
          {/* Body */}
          <rect
            x={x - candleWidth / 2}
            y={Math.min(openY, closeY)}
            width={candleWidth}
            height={Math.max(1, Math.abs(closeY - openY))}
            fill={isGreen ? color : color}
            stroke={color}
            strokeWidth="1"
          />
        </g>
      )
    })
  }

  const renderAreaChart = () => {
    if (visibleData.length === 0) return null
    
    const area = getChartArea()
    const points = visibleData.map((p, i) => `${indexToX(i)},${priceToY(p.close)}`).join(' ')
    const areaPoints = `${indexToX(0)},${area.y + area.height} ${points} ${indexToX(visibleData.length - 1)},${area.y + area.height}`
    
    const isPositive = visibleData[visibleData.length - 1].close >= visibleData[0].close
    const color = isPositive ? '#10b981' : '#ef4444'
    
    return (
      <g>
        <defs>
          <linearGradient id={`areaGradient-${symbol}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <polygon points={areaPoints} fill={`url(#areaGradient-${symbol})`} />
        <polyline points={points} fill="none" stroke={color} strokeWidth="2" />
      </g>
    )
  }

  const renderLineChart = () => {
    if (visibleData.length === 0) return null
    const points = visibleData.map((p, i) => `${indexToX(i)},${priceToY(p.close)}`).join(' ')
    const isPositive = visibleData[visibleData.length - 1].close >= visibleData[0].close
    return <polyline points={points} fill="none" stroke={isPositive ? '#10b981' : '#ef4444'} strokeWidth="2" />
  }

  // Calculate Simple Moving Average from visible data
  const calculateSMA = (period: number): number[] => {
    const smaValues: number[] = []
    for (let i = 0; i < visibleData.length; i++) {
      if (i < period - 1) {
        smaValues.push(visibleData[i].close)
      } else {
        let sum = 0
        for (let j = 0; j < period; j++) {
          sum += visibleData[i - j].close
        }
        smaValues.push(sum / period)
      }
    }
    return smaValues
  }

  // Detect Elliott Wave points (simplified - finds swing highs/lows)
  const detectWavePoints = (): { index: number; price: number; wave: number; type: 'high' | 'low' }[] => {
    if (visibleData.length < 10) return []
    
    const waves: { index: number; price: number; wave: number; type: 'high' | 'low' }[] = []
    const lookback = Math.max(3, Math.floor(visibleData.length / 15))
    
    // Find local highs and lows
    const extremes: { index: number; price: number; type: 'high' | 'low' }[] = []
    
    for (let i = lookback; i < visibleData.length - lookback; i++) {
      let isHigh = true
      let isLow = true
      const currentPrice = visibleData[i].close
      
      for (let j = 1; j <= lookback; j++) {
        if (visibleData[i - j].close >= currentPrice || visibleData[i + j].close >= currentPrice) {
          isHigh = false
        }
        if (visibleData[i - j].close <= currentPrice || visibleData[i + j].close <= currentPrice) {
          isLow = false
        }
      }
      
      if (isHigh) {
        extremes.push({ index: i, price: currentPrice, type: 'high' })
      } else if (isLow) {
        extremes.push({ index: i, price: currentPrice, type: 'low' })
      }
    }
    
    // Label as waves (alternating pattern)
    let waveNum = 1
    let lastType: 'high' | 'low' | null = null
    
    for (const extreme of extremes) {
      if (lastType !== extreme.type && waveNum <= 5) {
        waves.push({ ...extreme, wave: waveNum })
        waveNum++
        lastType = extreme.type
      }
    }
    
    return waves
  }

  const renderIndicators = () => {
    if (!showIndicators) return null
    const area = getChartArea()
    const elements = []
    
    // Calculate and render actual SMA lines across the chart
    const sma20Values = calculateSMA(5) // Use 5 for visible data (represents ~20 day)
    const sma50Values = calculateSMA(10) // Use 10 for visible data (represents ~50 day)
    
    // SMA 20 line (blue)
    if (sma20Values.length > 1) {
      const sma20Points = sma20Values.map((val, i) => `${indexToX(i)},${priceToY(val)}`).join(' ')
      elements.push(
        <g key="sma20-group">
          <polyline 
            points={sma20Points} 
            fill="none" 
            stroke="#3b82f6" 
            strokeWidth="2" 
            strokeDasharray="6,3"
            opacity="0.8"
          />
          <text x={indexToX(visibleData.length - 1) + 5} y={priceToY(sma20Values[sma20Values.length - 1])} 
            fontSize="10" fill="#3b82f6" fontWeight="bold">SMA20</text>
        </g>
      )
    }
    
    // SMA 50 line (purple)
    if (sma50Values.length > 1) {
      const sma50Points = sma50Values.map((val, i) => `${indexToX(i)},${priceToY(val)}`).join(' ')
      elements.push(
        <g key="sma50-group">
          <polyline 
            points={sma50Points} 
            fill="none" 
            stroke="#8b5cf6" 
            strokeWidth="2" 
            strokeDasharray="6,3"
            opacity="0.8"
          />
          <text x={indexToX(visibleData.length - 1) + 5} y={priceToY(sma50Values[sma50Values.length - 1]) + 12} 
            fontSize="10" fill="#8b5cf6" fontWeight="bold">SMA50</text>
        </g>
      )
    }
    
    // Support/Resistance levels from technical data
    if (technicalData?.support_levels) {
      technicalData.support_levels.slice(0, 2).forEach((level, i) => {
        const y = priceToY(level)
        if (y >= area.y && y <= area.y + area.height) {
          elements.push(
            <g key={`support-${i}`}>
              <line x1={area.x} y1={y} x2={area.x + area.width} y2={y}
                stroke="#10b981" strokeWidth="1.5" strokeDasharray="8,4" opacity="0.7" />
              <text x={area.x + 5} y={y - 4} fontSize="9" fill="#10b981" fontWeight="bold">
                Support ${level.toFixed(2)}
              </text>
            </g>
          )
        }
      })
    }
    
    if (technicalData?.resistance_levels) {
      technicalData.resistance_levels.slice(0, 2).forEach((level, i) => {
        const y = priceToY(level)
        if (y >= area.y && y <= area.y + area.height) {
          elements.push(
            <g key={`resistance-${i}`}>
              <line x1={area.x} y1={y} x2={area.x + area.width} y2={y}
                stroke="#ef4444" strokeWidth="1.5" strokeDasharray="8,4" opacity="0.7" />
              <text x={area.x + 5} y={y - 4} fontSize="9" fill="#ef4444" fontWeight="bold">
                Resistance ${level.toFixed(2)}
              </text>
            </g>
          )
        }
      })
    }
    
    // Elliott Wave annotations
    const wavePoints = detectWavePoints()
    wavePoints.forEach((wave, i) => {
      const x = indexToX(wave.index)
      const y = priceToY(wave.price)
      const isHigh = wave.type === 'high'
      const yOffset = isHigh ? -20 : 20
      
      elements.push(
        <g key={`wave-${i}`}>
          {/* Wave marker circle */}
          <circle cx={x} cy={y} r="6" fill={isHigh ? '#ef4444' : '#10b981'} stroke="white" strokeWidth="2" />
          {/* Wave number label */}
          <text 
            x={x} 
            y={y + yOffset} 
            fontSize="12" 
            fontWeight="bold" 
            fill={isHigh ? '#ef4444' : '#10b981'}
            textAnchor="middle"
          >
            Wave {wave.wave}
          </text>
          {/* Connecting line to label */}
          <line 
            x1={x} y1={y + (isHigh ? -8 : 8)} 
            x2={x} y2={y + yOffset - (isHigh ? 12 : -12)}
            stroke={isHigh ? '#ef4444' : '#10b981'} 
            strokeWidth="1" 
            strokeDasharray="2,2"
          />
        </g>
      )
    })
    
    return elements
  }

  const renderCrosshair = () => {
    if (!hoveredPoint) return null
    const area = getChartArea()
    const idx = visibleData.indexOf(hoveredPoint)
    if (idx === -1) return null
    
    const x = indexToX(idx)
    const y = priceToY(hoveredPoint.close)
    
    return (
      <g>
        <line x1={x} y1={area.y} x2={x} y2={area.y + area.height} stroke="#6b7280" strokeWidth="1" strokeDasharray="2,2" />
        <line x1={area.x} y1={y} x2={area.x + area.width} y2={y} stroke="#6b7280" strokeWidth="1" strokeDasharray="2,2" />
        <circle cx={x} cy={y} r="4" fill="#6366f1" />
      </g>
    )
  }

  // Calculate metrics
  const getMetrics = () => {
    if (visibleData.length < 2) return { change: 0, percent: 0, isPositive: true }
    const first = visibleData[0].close
    const last = visibleData[visibleData.length - 1].close
    const change = last - first
    const percent = (change / first) * 100
    return { change, percent, isPositive: change >= 0 }
  }

  const getBuySellRecommendation = () => {
    if (!technicalData && visibleData.length === 0) {
      return { signal: 'HOLD', confidence: 50, reason: 'Loading data...' }
    }
    
    // Use price data if technical data not available
    if (!technicalData) {
      const currentPrice = visibleData[visibleData.length - 1]?.close || 0
      const firstPrice = visibleData[0]?.close || currentPrice
      const change = firstPrice ? ((currentPrice - firstPrice) / firstPrice) * 100 : 0
      if (change > 5) return { signal: 'BUY', confidence: 65, reason: `Strong uptrend (+${change.toFixed(1)}%)` }
      if (change < -5) return { signal: 'SELL', confidence: 65, reason: `Strong downtrend (${change.toFixed(1)}%)` }
      return { signal: 'HOLD', confidence: 55, reason: 'Neutral trend' }
    }
    
    let score = 50
    const reasons = []
    
    // RSI analysis
    if (technicalData.rsi) {
      if (technicalData.rsi < 30) {
        score += 20
        reasons.push('RSI oversold')
      } else if (technicalData.rsi > 70) {
        score -= 20
        reasons.push('RSI overbought')
      }
    }
    
    // SMA crossover
    if (technicalData.sma_20 && technicalData.sma_50) {
      if (technicalData.sma_20 > technicalData.sma_50) {
        score += 15
        reasons.push('Bullish SMA crossover')
      } else {
        score -= 15
        reasons.push('Bearish SMA crossover')
      }
    }
    
    // Price vs support/resistance
    const currentPrice = visibleData[visibleData.length - 1]?.close || 0
    if (technicalData.support_levels?.[0] && currentPrice < technicalData.support_levels[0] * 1.05) {
      score += 10
      reasons.push('Near support')
    }
    if (technicalData.resistance_levels?.[0] && currentPrice > technicalData.resistance_levels[0] * 0.95) {
      score -= 10
      reasons.push('Near resistance')
    }
    
    // Projection
    if (technicalData.abc_pattern?.projection && currentPrice) {
      const projectionGain = ((technicalData.abc_pattern.projection - currentPrice) / currentPrice) * 100
      if (projectionGain > 10) {
        score += 15
        reasons.push(`${projectionGain.toFixed(1)}% upside projected`)
      } else if (projectionGain < -10) {
        score -= 15
        reasons.push(`${Math.abs(projectionGain).toFixed(1)}% downside projected`)
      }
    }
    
    let signal = 'HOLD'
    if (score >= 70) signal = 'STRONG BUY'
    else if (score >= 60) signal = 'BUY'
    else if (score <= 30) signal = 'STRONG SELL'
    else if (score <= 40) signal = 'SELL'
    
    return { signal, confidence: Math.min(100, Math.max(0, score)), reason: reasons.join(', ') || 'Neutral signals' }
  }

  const metrics = getMetrics()
  const recommendation = getBuySellRecommendation()

  const chartContent = (
    <div ref={fullscreenRef} className={`bg-white rounded-xl border border-gray-200 overflow-hidden ${isFullscreen ? 'fixed inset-4 z-50 shadow-2xl' : ''}`}>
      {/* Fullscreen overlay */}
      {isFullscreen && <div className="fixed inset-0 bg-black/50 -z-10" onClick={() => setIsFullscreen(false)} />}
      
      {/* Header */}
      <div className="p-4 border-b border-gray-100">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <h3 className="text-lg font-bold text-gray-900">{symbol}</h3>
            {visibleData.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold">${visibleData[visibleData.length - 1].close.toFixed(2)}</span>
                <div className={`flex items-center gap-1 px-2 py-1 rounded ${metrics.isPositive ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  {metrics.isPositive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  <span className="text-sm font-medium">
                    {metrics.isPositive ? '+' : ''}{metrics.change.toFixed(2)} ({metrics.percent.toFixed(2)}%)
                  </span>
                </div>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {/* Buy/Sell Signal */}
            <div className={`px-4 py-2 rounded-lg font-bold text-sm ${
              recommendation.signal.includes('BUY') ? 'bg-green-100 text-green-700 border border-green-300' :
              recommendation.signal.includes('SELL') ? 'bg-red-100 text-red-700 border border-red-300' :
              'bg-gray-100 text-gray-700 border border-gray-300'
            }`}>
              {recommendation.signal} ({recommendation.confidence}%)
            </div>
            
            {/* Fullscreen toggle */}
            <button
              onClick={toggleFullscreen}
              className="p-2 rounded-lg bg-gray-100 hover:bg-gray-200 transition-colors"
              title={isFullscreen ? 'Exit Fullscreen (ESC)' : 'Fullscreen'}
            >
              {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            </button>
          </div>
        </div>
        
        {/* Controls */}
        <div className="flex flex-wrap items-center gap-3 mt-3">
          {/* Chart Type */}
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            {(['area', 'line', 'candle'] as ChartType[]).map(type => (
              <button
                key={type}
                onClick={() => setChartType(type)}
                className={`px-3 py-1 text-xs rounded font-medium transition-all ${
                  chartType === type ? 'bg-white shadow text-gray-900' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </button>
            ))}
          </div>
          
          {/* Interval */}
          <div className="flex gap-1">
            {INTERVALS.map(int => (
              <button
                key={int.value}
                onClick={() => setChartInterval(int.value)}
                className={`px-2 py-1 text-xs rounded font-medium transition-all ${
                  interval === int.value ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {int.label}
              </button>
            ))}
          </div>
          
          {/* Period */}
          <div className="flex gap-1">
            {PERIODS.map(p => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-2 py-1 text-xs rounded font-medium transition-all ${
                  period === p.value ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          
          {/* Zoom/Pan */}
          <div className="flex gap-1 ml-auto">
            <button onClick={panLeft} className="p-1.5 rounded bg-gray-100 hover:bg-gray-200" title="Pan Left">
              <ChevronLeft size={16} />
            </button>
            <button onClick={zoomIn} className="p-1.5 rounded bg-gray-100 hover:bg-gray-200" title="Zoom In">
              <ZoomIn size={16} />
            </button>
            <button onClick={zoomOut} className="p-1.5 rounded bg-gray-100 hover:bg-gray-200" title="Zoom Out">
              <ZoomOut size={16} />
            </button>
            <button onClick={panRight} className="p-1.5 rounded bg-gray-100 hover:bg-gray-200" title="Pan Right">
              <ChevronRight size={16} />
            </button>
            <button onClick={fetchChartData} className="p-1.5 rounded bg-gray-100 hover:bg-gray-200" title="Refresh">
              <RefreshCw size={16} />
            </button>
          </div>
          
          {/* Indicators toggle */}
          <button
            onClick={() => setShowIndicators(!showIndicators)}
            className={`px-3 py-1 text-xs rounded font-medium ${showIndicators ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600'}`}
          >
            Indicators
          </button>
        </div>
      </div>

      {/* Chart Area */}
      <div ref={containerRef} className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        )}
        
        {error && (
          <div className="p-8 text-center text-red-600">{error}</div>
        )}
        
        {!loading && !error && visibleData.length > 0 && (
          <svg
            ref={chartRef}
            viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
            className="w-full cursor-crosshair"
            style={{ height: '400px' }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
            onWheel={handleWheel}
          >
            {renderGrid()}
            {renderIndicators()}
            {chartType === 'candle' && renderCandlesticks()}
            {chartType === 'area' && renderAreaChart()}
            {chartType === 'line' && renderLineChart()}
            {renderCrosshair()}
          </svg>
        )}
        
        {/* Hover tooltip */}
        {hoveredPoint && (
          <div
            className="absolute bg-gray-900 text-white text-xs p-2 rounded shadow-lg pointer-events-none z-20"
            style={{ left: hoverPosition.x + 10, top: hoverPosition.y - 60 }}
          >
            <div className="font-semibold">{new Date(hoveredPoint.date).toLocaleString()}</div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1 mt-1">
              <span className="text-gray-400">O:</span><span>${hoveredPoint.open.toFixed(2)}</span>
              <span className="text-gray-400">H:</span><span>${hoveredPoint.high.toFixed(2)}</span>
              <span className="text-gray-400">L:</span><span>${hoveredPoint.low.toFixed(2)}</span>
              <span className="text-gray-400">C:</span><span>${hoveredPoint.close.toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Info */}
      <div className="p-4 border-t border-gray-100 bg-gray-50">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Recommendation Details */}
          <div className="text-sm">
            <span className="text-gray-600">AI Signal: </span>
            <span className={`font-semibold ${
              recommendation.signal.includes('BUY') ? 'text-green-600' :
              recommendation.signal.includes('SELL') ? 'text-red-600' : 'text-gray-600'
            }`}>
              {recommendation.reason}
            </span>
          </div>
          
          {/* Technical Indicators */}
          {showIndicators && technicalData && (
            <div className="flex flex-wrap gap-4 text-xs">
              {technicalData.sma_20 && (
                <span className="text-blue-600">SMA20: ${technicalData.sma_20.toFixed(2)}</span>
              )}
              {technicalData.sma_50 && (
                <span className="text-purple-600">SMA50: ${technicalData.sma_50.toFixed(2)}</span>
              )}
              {technicalData.rsi && (
                <span className={technicalData.rsi > 70 ? 'text-red-600' : technicalData.rsi < 30 ? 'text-green-600' : 'text-gray-600'}>
                  RSI: {technicalData.rsi.toFixed(1)}
                </span>
              )}
            </div>
          )}
          
          {/* Data range */}
          <div className="text-xs text-gray-500">
            Showing {viewEnd - viewStart} of {data.length} data points
          </div>
        </div>
        
        {/* Future Projection */}
        {technicalData?.abc_pattern?.projection && visibleData.length > 0 && (
          <div className="mt-3 p-3 bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg border border-purple-200">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm text-purple-700 font-medium">📈 AI Price Target</span>
                <p className="text-xs text-purple-600">Based on Elliott Wave projection</p>
              </div>
              <div className="text-right">
                <div className="text-xl font-bold text-purple-700">${technicalData.abc_pattern.projection.toFixed(2)}</div>
                <div className={`text-sm ${technicalData.abc_pattern.projection > visibleData[visibleData.length - 1].close ? 'text-green-600' : 'text-red-600'}`}>
                  {technicalData.abc_pattern.projection > visibleData[visibleData.length - 1].close ? '↑' : '↓'} 
                  {Math.abs(((technicalData.abc_pattern.projection - visibleData[visibleData.length - 1].close) / visibleData[visibleData.length - 1].close) * 100).toFixed(1)}%
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* ── Detected Chart Patterns ── */}
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-800 flex items-center gap-1"><Activity size={14} /> Detected Patterns</span>
            {intradayLoading && <span className="text-xs text-gray-400 animate-pulse">Updating…</span>}
            {intradayData && <span className="text-xs text-gray-400">Live · {new Date(intradayData.timestamp).toLocaleTimeString()}</span>}
          </div>

          {intradayData?.patterns?.length > 0 ? (
            <div className="grid grid-cols-1 gap-2">
              {intradayData.patterns.map((p: any, i: number) => (
                <div key={i} className={`flex items-start justify-between p-3 rounded-lg border ${
                  p.signal === 'bullish' ? 'bg-green-50 border-green-200' :
                  p.signal === 'bearish' ? 'bg-red-50 border-red-200' :
                  'bg-yellow-50 border-yellow-200'
                }`}>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-bold uppercase tracking-wide ${
                        p.signal === 'bullish' ? 'text-green-700' :
                        p.signal === 'bearish' ? 'text-red-700' : 'text-yellow-700'
                      }`}>{p.pattern?.replace(/_/g, ' ')}</span>
                      <span className="text-xs text-gray-500">{Math.round((p.confidence || 0) * 100)}% conf</span>
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{p.description || ''}</p>
                    {p.target && <p className="text-xs font-semibold mt-1 text-purple-700">Target: ${p.target}</p>}
                    {p.neckline && <p className="text-xs text-gray-500">Neckline: ${p.neckline}</p>}
                  </div>
                  <span className={`ml-3 px-2 py-0.5 rounded-full text-xs font-semibold shrink-0 ${
                    p.signal === 'bullish' ? 'bg-green-200 text-green-800' :
                    p.signal === 'bearish' ? 'bg-red-200 text-red-800' :
                    'bg-yellow-200 text-yellow-800'
                  }`}>{p.signal?.toUpperCase()}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-semibold text-blue-800">📊 Pattern Library</span>
                <div className="relative">
                  <button
                    onClick={() => setShowPatternDropdown(!showPatternDropdown)}
                    className="flex items-center gap-1 px-3 py-1 text-xs bg-white rounded-lg border border-blue-300 hover:bg-blue-50"
                  >
                    {selectedPattern.name} <ChevronDown size={12} />
                  </button>
                  {showPatternDropdown && (
                    <div className="absolute top-full left-0 mt-1 w-64 bg-white rounded-lg shadow-xl border border-gray-200 z-30 max-h-64 overflow-y-auto">
                      {CHART_PATTERNS.map(pat => (
                        <button key={pat.id} onClick={() => { setSelectedPattern(pat); setShowPatternDropdown(false) }}
                          className={`w-full text-left px-3 py-2 text-xs hover:bg-blue-50 border-b border-gray-100 last:border-0 ${selectedPattern.id === pat.id ? 'bg-blue-50' : ''}`}>
                          <div className="font-medium">{pat.name}</div>
                          <div className={`text-xs ${pat.signal === 'bullish' ? 'text-green-600' : pat.signal === 'bearish' ? 'text-red-600' : 'text-yellow-600'}`}>{pat.signal} signal</div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <p className="text-xs text-gray-600 mb-1">{selectedPattern.description}</p>
              <p className="text-xs text-gray-500">{selectedPattern.howToRead}</p>
            </div>
          )}
        </div>

        {/* ── Options Trader Targets ── */}
        {intradayData?.trade_targets && (
          <div className="mt-4 rounded-xl border border-gray-200 overflow-hidden">
            <div className="bg-gradient-to-r from-gray-900 to-gray-800 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target size={16} className="text-yellow-400" />
                <span className="text-white font-bold text-sm">Options Trader — Today's Targets</span>
                <span className="text-xs text-gray-400">Live · auto-refresh 30s</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-300">RSI: <span className={`font-bold ${
                  (intradayData.indicators?.rsi || 50) > 70 ? 'text-red-400' :
                  (intradayData.indicators?.rsi || 50) < 30 ? 'text-green-400' : 'text-white'
                }`}>{intradayData.indicators?.rsi}</span></span>
                <span className="text-xs text-gray-300">ATR: <span className="font-bold text-white">${intradayData.indicators?.atr} ({intradayData.indicators?.atr_pct}%)</span></span>
                <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                  intradayData.trade_targets.bias === 'bullish' ? 'bg-green-500 text-white' :
                  intradayData.trade_targets.bias === 'bearish' ? 'bg-red-500 text-white' :
                  intradayData.trade_targets.bias?.includes('oversold') ? 'bg-green-600 text-white' :
                  intradayData.trade_targets.bias?.includes('overbought') ? 'bg-orange-500 text-white' :
                  'bg-gray-500 text-white'
                }`}>{intradayData.trade_targets.bias?.replace(/_/g, ' ').toUpperCase()}</span>
              </div>
            </div>

            {/* Expected Range */}
            <div className="bg-gray-800 px-4 py-2 flex items-center gap-6 text-xs">
              <span className="text-gray-400">Expected Range Today:</span>
              <span className="text-red-400 font-bold">▼ ${intradayData.trade_targets.expected_range_today?.low}</span>
              <span className="text-white font-bold">Now: ${intradayData.price?.current}</span>
              <span className="text-green-400 font-bold">▲ ${intradayData.trade_targets.expected_range_today?.high}</span>
              <span className="text-gray-400">(±{intradayData.trade_targets.expected_range_today?.range_pct}% / day)</span>
            </div>

            <div className="grid md:grid-cols-2 gap-0 divide-x divide-gray-100">
              {/* CALL Trade */}
              <div className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ArrowUpCircle size={18} className="text-green-600" />
                  <span className="font-bold text-green-700">CALL Trade Setup</span>
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">R:R {intradayData.trade_targets.call_trade?.risk_reward}x</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center py-1.5 px-3 bg-green-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Entry</span>
                    <span className="font-bold text-green-700 text-base">${intradayData.trade_targets.call_trade?.entry}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-red-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Stop Loss</span>
                    <span className="font-bold text-red-600">${intradayData.trade_targets.call_trade?.stop_loss}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-blue-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Target 1</span>
                    <span className="font-bold text-blue-700">${intradayData.trade_targets.call_trade?.target1}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-purple-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Target 2</span>
                    <span className="font-bold text-purple-700">${intradayData.trade_targets.call_trade?.target2}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{intradayData.trade_targets.call_trade?.note}</p>
                </div>
              </div>

              {/* PUT Trade */}
              <div className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <ArrowDownCircle size={18} className="text-red-600" />
                  <span className="font-bold text-red-700">PUT Trade Setup</span>
                  <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">R:R {intradayData.trade_targets.put_trade?.risk_reward}x</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center py-1.5 px-3 bg-red-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Entry</span>
                    <span className="font-bold text-red-700 text-base">${intradayData.trade_targets.put_trade?.entry}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-red-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Stop Loss</span>
                    <span className="font-bold text-red-600">${intradayData.trade_targets.put_trade?.stop_loss}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-blue-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Target 1</span>
                    <span className="font-bold text-blue-700">${intradayData.trade_targets.put_trade?.target1}</span>
                  </div>
                  <div className="flex justify-between items-center py-1.5 px-3 bg-purple-50 rounded-lg">
                    <span className="text-gray-600 font-medium">Target 2</span>
                    <span className="font-bold text-purple-700">${intradayData.trade_targets.put_trade?.target2}</span>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">{intradayData.trade_targets.put_trade?.note}</p>
                </div>
              </div>
            </div>

            {/* Pivot Points */}
            <div className="border-t border-gray-100 p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle size={14} className="text-orange-500" />
                <span className="text-sm font-semibold text-gray-700">Pivot Points (Classic)</span>
                <span className="text-xs text-gray-400">based on prior day OHLC</span>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                {['r3','r2','r1','pivot','s1','s2','s3'].map(key => {
                  const val = intradayData.pivot_points?.classic?.[key]
                  const isR = key.startsWith('r')
                  const isP = key === 'pivot'
                  return val ? (
                    <span key={key} className={`px-2 py-1 rounded font-mono font-semibold ${
                      isP ? 'bg-gray-200 text-gray-800' :
                      isR ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                    }`}>{key.toUpperCase()}: ${val}</span>
                  ) : null
                })}
              </div>
            </div>
          </div>
        )}
        
        {/* Fullscreen hint */}
        {isFullscreen && (
          <div className="mt-2 text-center text-xs text-gray-500">
            Press <kbd className="px-1.5 py-0.5 bg-gray-200 rounded text-gray-700 font-mono">ESC</kbd> to exit fullscreen
          </div>
        )}
      </div>
    </div>
  )
  
  return chartContent
}
