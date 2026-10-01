import { useMemo } from 'react'
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

interface Point {
  t: string
  price?: number | null
  upper?: number | null
  lower?: number | null
}

interface Props {
  history: Point[]
  forecast: Point[]
  entry?: number | null
  stop?: number | null
  target1?: number | null
  target2?: number | null
  lastPrice?: number | null
  title?: string
  height?: number
}

/**
 * Dual-series chart: historical price (solid line) joined to forecasted path
 * (dashed line) with a shaded confidence band, plus horizontal reference lines
 * for entry, stop-loss, and take-profit levels.
 */
export default function ForecastChart({
  history, forecast, entry, stop, target1, target2, lastPrice, title, height = 320,
}: Props) {
  const merged = useMemo(() => {
    const h = history.map(p => ({ t: p.t, hist: p.price ?? null }))
    const f = forecast.map(p => ({
      t: p.t,
      fcst: p.price ?? null,
      band_upper: p.upper ?? null,
      band_lower: p.lower ?? null,
    }))
    // Bridge the join so the two lines visually connect.
    if (h.length && f.length && lastPrice != null) {
      f.unshift({ t: h[h.length - 1].t, fcst: lastPrice, band_upper: lastPrice, band_lower: lastPrice })
    }
    return [...h, ...f]
  }, [history, forecast, lastPrice])

  const allVals = useMemo(() => {
    const xs: number[] = []
    merged.forEach(m => {
      const anyM = m as any
      ;['hist', 'fcst', 'band_upper', 'band_lower'].forEach(k => {
        if (anyM[k] != null) xs.push(anyM[k])
      })
    })
    ;[entry, stop, target1, target2].forEach(v => { if (v != null) xs.push(v as number) })
    return xs
  }, [merged, entry, stop, target1, target2])

  const domain = useMemo<[number, number]>(() => {
    if (!allVals.length) return [0, 1]
    const mn = Math.min(...allVals)
    const mx = Math.max(...allVals)
    const pad = (mx - mn) * 0.08 || mx * 0.02
    return [mn - pad, mx + pad]
  }, [allVals])

  return (
    <div>
      {title && <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{title}</div>}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={merged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="fcBand" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#6366f1" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={30}
                 tickFormatter={(t) => String(t).slice(5, 16)} />
          <YAxis domain={domain} tick={{ fontSize: 10 }} width={55}
                 tickFormatter={(v) => Number(v).toFixed(2)} />
          <Tooltip
            labelFormatter={(t) => String(t).slice(0, 16)}
            formatter={(v: any, name: string) => [Number(v).toFixed(2), name]}
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
          />

          {/* Confidence band on the forecast */}
          <Area type="monotone" dataKey="band_upper" stroke="none" fill="url(#fcBand)" isAnimationActive={false} />
          <Area type="monotone" dataKey="band_lower" stroke="none" fill="#ffffff" isAnimationActive={false} />

          {/* History line (solid) */}
          <Line type="monotone" dataKey="hist" stroke="#0ea5e9" strokeWidth={2} dot={false}
                connectNulls name="history" isAnimationActive={false} />
          {/* Forecast line (dashed) */}
          <Line type="monotone" dataKey="fcst" stroke="#6366f1" strokeWidth={2}
                strokeDasharray="6 3" dot={false} connectNulls name="forecast" isAnimationActive={false} />

          {entry != null && (
            <ReferenceLine y={entry} stroke="#64748b" strokeDasharray="3 3"
                           label={{ value: `Entry ${entry}`, fontSize: 10, fill: '#64748b', position: 'insideRight' }} />
          )}
          {stop != null && (
            <ReferenceLine y={stop} stroke="#dc2626" strokeDasharray="3 3"
                           label={{ value: `Stop ${stop}`, fontSize: 10, fill: '#dc2626', position: 'insideRight' }} />
          )}
          {target1 != null && (
            <ReferenceLine y={target1} stroke="#16a34a" strokeDasharray="3 3"
                           label={{ value: `TP1 ${target1}`, fontSize: 10, fill: '#16a34a', position: 'insideRight' }} />
          )}
          {target2 != null && (
            <ReferenceLine y={target2} stroke="#16a34a" strokeDasharray="3 3"
                           label={{ value: `TP2 ${target2}`, fontSize: 10, fill: '#16a34a', position: 'insideRight' }} />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
