import { useEffect, useRef, useState } from 'react'
import { TrendingUp, TrendingDown, Minus, Pencil, Trash2 } from 'lucide-react'
import config from '../config'

interface ChartProps {
  symbol: string
  data: any[]
}

export default function AdvancedStockChart({ symbol }: ChartProps) {
  const [period, setPeriod] = useState('1M')
  const [chartData, setChartData] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [drawMode, setDrawMode] = useState<string | null>(null)
  const [drawings, setDrawings] = useState<any[]>([])
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [currentDrawing, setCurrentDrawing] = useState<any>(null)

  useEffect(() => {
    if (symbol) {
      fetchChartData()
    }
  }, [symbol, period])

  useEffect(() => {
    if (chartData.length > 0 && canvasRef.current) {
      drawChart()
    }
  }, [chartData, drawings])

  const fetchChartData = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/history?period=${period}`)
      const result = await response.json()
      if (result.success && result.data) {
        setChartData(result.data)
      }
    } catch (error) {
      console.error('Failed to fetch chart data:', error)
    } finally {
      setLoading(false)
    }
  }

  const drawChart = () => {
    const canvas = canvasRef.current
    if (!canvas || chartData.length === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    // Clear canvas
    ctx.clearRect(0, 0, width, height)

    // Calculate price range
    const prices = chartData.map(d => d.close)
    const maxPrice = Math.max(...prices)
    const minPrice = Math.min(...prices)
    const priceRange = maxPrice - minPrice
    const padding = 40

    // Draw grid
    ctx.strokeStyle = '#e5e7eb'
    ctx.lineWidth = 1
    for (let i = 0; i <= 5; i++) {
      const y = padding + (height - 2 * padding) * (i / 5)
      ctx.beginPath()
      ctx.moveTo(padding, y)
      ctx.lineTo(width - padding, y)
      ctx.stroke()

      // Price labels
      const price = maxPrice - (priceRange * i / 5)
      ctx.fillStyle = '#6b7280'
      ctx.font = '12px sans-serif'
      ctx.fillText(`$${price.toFixed(2)}`, 5, y + 4)
    }

    // Draw candlesticks
    const candleWidth = (width - 2 * padding) / chartData.length
    chartData.forEach((d, i) => {
      const x = padding + i * candleWidth
      const openY = padding + (height - 2 * padding) * (1 - (d.open - minPrice) / priceRange)
      const closeY = padding + (height - 2 * padding) * (1 - (d.close - minPrice) / priceRange)
      const highY = padding + (height - 2 * padding) * (1 - (d.high - minPrice) / priceRange)
      const lowY = padding + (height - 2 * padding) * (1 - (d.low - minPrice) / priceRange)

      const isGreen = d.close >= d.open

      // Draw wick
      ctx.strokeStyle = isGreen ? '#10b981' : '#ef4444'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(x + candleWidth / 2, highY)
      ctx.lineTo(x + candleWidth / 2, lowY)
      ctx.stroke()

      // Draw body
      ctx.fillStyle = isGreen ? '#10b981' : '#ef4444'
      const bodyHeight = Math.abs(closeY - openY)
      ctx.fillRect(x + 2, Math.min(openY, closeY), candleWidth - 4, bodyHeight || 1)
    })

    // Draw user drawings
    drawings.forEach(drawing => {
      drawShape(ctx, drawing, width, height, padding, minPrice, priceRange)
    })

    // Draw current drawing
    if (currentDrawing) {
      drawShape(ctx, currentDrawing, width, height, padding, minPrice, priceRange)
    }
  }

  const drawShape = (ctx: CanvasRenderingContext2D, drawing: any, width: number, _height: number, padding: number, _minPrice: number, _priceRange: number) => {
    ctx.strokeStyle = drawing.color || '#3b82f6'
    ctx.lineWidth = 2

    if (drawing.type === 'line' || drawing.type === 'trendline') {
      ctx.beginPath()
      ctx.moveTo(drawing.startX, drawing.startY)
      ctx.lineTo(drawing.endX, drawing.endY)
      ctx.stroke()
    } else if (drawing.type === 'elliotwave') {
      // Draw Elliott Wave pattern (5 waves up, 3 waves down)
      ctx.beginPath()
      const points = drawing.points || []
      if (points.length > 0) {
        ctx.moveTo(points[0].x, points[0].y)
        points.forEach((p: any) => ctx.lineTo(p.x, p.y))
        ctx.stroke()
      }
    } else if (drawing.type === 'fibonacci') {
      // Draw Fibonacci retracement levels
      const levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
      levels.forEach(level => {
        const y = drawing.startY + (drawing.endY - drawing.startY) * level
        ctx.beginPath()
        ctx.moveTo(padding, y)
        ctx.lineTo(width - padding, y)
        ctx.stroke()
        ctx.fillStyle = '#3b82f6'
        ctx.font = '10px sans-serif'
        ctx.fillText(`${(level * 100).toFixed(1)}%`, width - padding + 5, y + 4)
      })
    } else if (drawing.type === 'rectangle') {
      ctx.strokeRect(
        drawing.startX,
        drawing.startY,
        drawing.endX - drawing.startX,
        drawing.endY - drawing.startY
      )
    }
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawMode) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setIsDrawing(true)
    setCurrentDrawing({
      type: drawMode,
      startX: x,
      startY: y,
      endX: x,
      endY: y,
      points: [{ x, y }],
      color: '#3b82f6'
    })
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !currentDrawing) return

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    if (currentDrawing.type === 'elliotwave') {
      setCurrentDrawing({
        ...currentDrawing,
        points: [...currentDrawing.points, { x, y }]
      })
    } else {
      setCurrentDrawing({
        ...currentDrawing,
        endX: x,
        endY: y
      })
    }
  }

  const handleMouseUp = () => {
    if (currentDrawing) {
      setDrawings([...drawings, currentDrawing])
      setCurrentDrawing(null)
    }
    setIsDrawing(false)
  }

  const clearDrawings = () => {
    setDrawings([])
    setCurrentDrawing(null)
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">{symbol} - Advanced Chart</h3>
        <div className="flex gap-2">
          {['1D', '1W', '1M', '3M', '1Y', '5Y'].map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded ${
                period === p
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Drawing Tools */}
      <div className="flex gap-2 mb-4 p-3 bg-gray-50 rounded">
        <button
          onClick={() => setDrawMode(drawMode === 'line' ? null : 'line')}
          className={`px-3 py-2 rounded flex items-center gap-2 ${
            drawMode === 'line' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-100'
          }`}
          title="Draw Trend Line"
        >
          <Minus size={16} />
          Trend Line
        </button>
        <button
          onClick={() => setDrawMode(drawMode === 'elliotwave' ? null : 'elliotwave')}
          className={`px-3 py-2 rounded flex items-center gap-2 ${
            drawMode === 'elliotwave' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-100'
          }`}
          title="Draw Elliott Wave"
        >
          <TrendingUp size={16} />
          Elliott Wave
        </button>
        <button
          onClick={() => setDrawMode(drawMode === 'fibonacci' ? null : 'fibonacci')}
          className={`px-3 py-2 rounded flex items-center gap-2 ${
            drawMode === 'fibonacci' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-100'
          }`}
          title="Fibonacci Retracement"
        >
          <TrendingDown size={16} />
          Fibonacci
        </button>
        <button
          onClick={() => setDrawMode(drawMode === 'rectangle' ? null : 'rectangle')}
          className={`px-3 py-2 rounded flex items-center gap-2 ${
            drawMode === 'rectangle' ? 'bg-blue-600 text-white' : 'bg-white hover:bg-gray-100'
          }`}
          title="Draw Rectangle"
        >
          <Pencil size={16} />
          Rectangle
        </button>
        <button
          onClick={clearDrawings}
          className="px-3 py-2 rounded flex items-center gap-2 bg-red-100 hover:bg-red-200 text-red-700"
          title="Clear All Drawings"
        >
          <Trash2 size={16} />
          Clear
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-96">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="relative">
          <canvas
            ref={canvasRef}
            width={1000}
            height={500}
            className="w-full border border-gray-200 rounded cursor-crosshair"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          />
          {drawMode && (
            <div className="absolute top-2 left-2 bg-blue-100 text-blue-800 px-3 py-1 rounded text-sm">
              Drawing: {drawMode === 'elliotwave' ? 'Elliott Wave' : drawMode === 'fibonacci' ? 'Fibonacci' : drawMode}
            </div>
          )}
        </div>
      )}

      <div className="mt-4 text-sm text-gray-600">
        <p><strong>Drawing Tools:</strong></p>
        <ul className="list-disc list-inside mt-2 space-y-1">
          <li><strong>Trend Line:</strong> Click and drag to draw support/resistance lines</li>
          <li><strong>Elliott Wave:</strong> Click multiple points to draw wave patterns (5 impulse + 3 corrective)</li>
          <li><strong>Fibonacci:</strong> Click and drag to draw retracement levels (23.6%, 38.2%, 50%, 61.8%, 78.6%)</li>
          <li><strong>Rectangle:</strong> Draw price channels and consolidation zones</li>
        </ul>
      </div>
    </div>
  )
}
