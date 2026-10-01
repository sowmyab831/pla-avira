import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, RefreshCw, Sparkles,
  Target, TrendingUp,
} from 'lucide-react'
import config from '../config'
import ForecastChart from '../components/ForecastChart'
import { LlmBadge, ModelStackPill } from '../components/LlmBadge'

const API = config.apiBase

const PRESET_SYMBOLS = [
  'NVDA', 'AAPL', 'MSFT', 'GOOGL', 'META', 'TSLA', 'AMZN', 'AMD',
  'AVGO', 'TSM', 'SMCI', 'PLTR', 'COIN', 'MSTR', 'QQQ', 'SPY',
]

const INTERVALS = ['5m', '15m', '30m', '60m'] as const

type Scope = 'day_trade' | 'long_term' | 'combined'

const fmtPct = (n?: number | null) =>
  n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`

const pctColor = (n?: number | null) =>
  n == null ? 'var(--text-muted)' : n >= 0 ? '#16a34a' : '#dc2626'

const Card = ({ title, right, children, pad = true }: any) => (
  <div className={`rounded-2xl border ${pad ? 'p-4' : ''} mb-4`}
       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
    {title && (
      <div className="flex items-center justify-between mb-3 px-4 pt-4"
           style={pad ? { padding: 0, margin: '0 0 .75rem 0' } : {}}>
        <h3 className="font-semibold text-sm uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
        {right}
      </div>
    )}
    {children}
  </div>
)

const Stat = ({ label, value, tone = 'neutral' }: { label: string; value: string; tone?: 'pos' | 'neg' | 'warn' | 'neutral' }) => {
  const colors: Record<string, string> = {
    pos: '#16a34a', neg: '#dc2626', warn: '#d97706', neutral: 'var(--text-primary)',
  }
  return (
    <div className="p-2 rounded-xl border" style={{ borderColor: 'var(--border-color)' }}>
      <div className="text-[10px] uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{label}</div>
      <div className="text-sm font-semibold" style={{ color: colors[tone] }}>{value}</div>
    </div>
  )
}

export default function Forecast() {
  const [symbol, setSymbol] = useState<string>(() => localStorage.getItem('forecast_symbol') || 'NVDA')
  const [interval, setInterval_] = useState<typeof INTERVALS[number]>('15m')
  const [scope, setScope] = useState<Scope>('combined')
  const [data, setData] = useState<any>(null)
  const [brief, setBrief] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [briefBusy, setBriefBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const endpoint = useMemo(() => {
    if (scope === 'day_trade')  return `${API}/api/forecast/day-trade/${symbol}?interval=${interval}`
    if (scope === 'long_term')  return `${API}/api/forecast/long-term/${symbol}`
    return `${API}/api/forecast/combined/${symbol}?interval=${interval}`
  }, [scope, symbol, interval])

  const authHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('auth_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  const load = async () => {
    setBusy(true); setErr(null)
    try {
      const r = await fetch(endpoint, { headers: authHeaders() })
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text().catch(() => 'request failed')}`)
      setData(await r.json())
    } catch (e: any) {
      setErr(e?.message || 'request failed')
    } finally {
      setBusy(false)
    }
  }

  const askLLM = async () => {
    setBriefBusy(true); setBrief(null)
    try {
      const r = await fetch(`${API}/api/forecast/explain/${symbol}?scope=${scope}`, { headers: authHeaders() })
      setBrief(await r.json())
    } catch (e: any) {
      setBrief({ llm_error: e?.message || 'llm failed' })
    } finally {
      setBriefBusy(false)
    }
  }

  useEffect(() => { localStorage.setItem('forecast_symbol', symbol) }, [symbol])
  useEffect(() => { load() /* eslint-disable-next-line */ }, [endpoint])

  const day = data?.day_trade ?? (scope === 'day_trade' ? data : null)
  const longT = data?.long_term ?? (scope === 'long_term' ? data : null)

  return (
    <div className="p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="text-indigo-500" /> Forecast & Trade Plan
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Day-trade intraday path · long-term 30/90/180-day targets · entry / stop / take-profit
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select value={symbol} onChange={e => setSymbol(e.target.value.toUpperCase())}
                  className="border rounded-lg px-2 py-1 text-sm" style={{ borderColor: 'var(--border-color)' }}>
            {PRESET_SYMBOLS.map(s => <option key={s}>{s}</option>)}
          </select>
          <input
            value={symbol}
            onChange={e => setSymbol(e.target.value.toUpperCase())}
            placeholder="symbol"
            className="border rounded-lg px-2 py-1 text-sm w-20 font-mono"
            style={{ borderColor: 'var(--border-color)' }}
          />
          <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border-color)' }}>
            {(['day_trade','long_term','combined'] as Scope[]).map(s => (
              <button key={s}
                      className={`text-xs px-2 py-1 ${scope === s ? 'bg-indigo-600 text-white' : ''}`}
                      onClick={() => setScope(s)}>
                {s === 'day_trade' ? 'Day' : s === 'long_term' ? 'Long' : 'Both'}
              </button>
            ))}
          </div>
          {scope !== 'long_term' && (
            <select value={interval} onChange={e => setInterval_(e.target.value as any)}
                    className="border rounded-lg px-2 py-1 text-sm" style={{ borderColor: 'var(--border-color)' }}>
              {INTERVALS.map(i => <option key={i}>{i}</option>)}
            </select>
          )}
          <button onClick={load} className="text-xs px-3 py-2 rounded-lg bg-indigo-600 text-white flex items-center gap-1">
            <RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </header>

      {err && (
        <div className="rounded-xl border-2 border-rose-300 bg-rose-50 p-3 text-sm text-rose-700 mb-4 flex items-center gap-2">
          <AlertTriangle size={16} /> {err}
        </div>
      )}

      {day && (scope === 'day_trade' || scope === 'combined') && (
        <DayTradePanel d={day} onExplain={askLLM} brief={brief} briefBusy={briefBusy} />
      )}

      {longT && (scope === 'long_term' || scope === 'combined') && (
        <LongTermPanel d={longT} onExplain={askLLM} brief={brief} briefBusy={briefBusy} />
      )}

      <Disclaimer />
    </div>
  )
}

/* ── Day-trade panel ─────────────────────────────────────────────────────── */

function DayTradePanel({ d, onExplain, brief, briefBusy }: any) {
  if (d?.error) {
    return (
      <Card title="Day Trade">
        <div className="text-sm text-rose-700">Error: {d.error}</div>
      </Card>
    )
  }
  const tone = d.direction === 'LONG' ? 'pos' : d.direction === 'SHORT' ? 'neg' : 'neutral'
  return (
    <Card
      title={`Day Trade · ${d.symbol} · ${d.interval}`}
      right={
        <div className="flex items-center gap-2">
          {d.degraded && <span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">degraded</span>}
          <ModelStackPill stack={d.model_stack} />
        </div>
      }
    >
      <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 mb-3">
        <Stat label="Last"           value={String(d.last_price ?? '—')} />
        <Stat label="Direction"      value={d.direction ?? '—'} tone={tone as any} />
        <Stat label="Confidence"     value={d.confidence_pct ? `${d.confidence_pct}%` : '—'} />
        <Stat label="Vol (day)"      value={d.volatility_pct ? `${d.volatility_pct}%` : '—'} />
        <Stat label="Support"        value={String(d.support ?? '—')} />
        <Stat label="Resistance"     value={String(d.resistance ?? '—')} />
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
        <Stat label="Entry"        value={String(d.entry ?? '—')} />
        <Stat label="Stop-Loss"    value={String(d.stop_loss ?? '—')} tone="neg" />
        <Stat label="Target 1"     value={String(d.take_profit_1 ?? '—')} tone="pos" />
        <Stat label="Target 2"     value={String(d.take_profit_2 ?? '—')} tone="pos" />
        <Stat label="Risk/Reward"  value={String(d.risk_reward ?? '—')} />
      </div>

      <ForecastChart
        history={d.history || []}
        forecast={d.points || []}
        lastPrice={d.last_price}
        entry={d.entry}
        stop={d.stop_loss}
        target1={d.take_profit_1}
        target2={d.take_profit_2}
        height={320}
      />

      <div className="text-xs mt-2 italic" style={{ color: 'var(--text-muted)' }}>
        {d.rationale}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button onClick={onExplain} disabled={briefBusy}
                className="text-xs px-3 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white flex items-center gap-1">
          <Sparkles size={12} /> {briefBusy ? 'thinking...' : 'Explain with AI'}
        </button>
      </div>
      {brief && <LlmExplainer brief={brief} />}
    </Card>
  )
}

/* ── Long-term panel ──────────────────────────────────────────────────────── */

function LongTermPanel({ d, onExplain, brief, briefBusy }: any) {
  if (d?.error) {
    return (
      <Card title="Long Term">
        <div className="text-sm text-rose-700">Error: {d.error}</div>
      </Card>
    )
  }
  const st = d.swing_trade || {}
  const fc = d.forecasts || {}
  const horizons = [
    { k: '30d',  info: fc['30d'] },
    { k: '90d',  info: fc['90d'] },
    { k: '180d', info: fc['180d'] },
  ]

  return (
    <Card
      title={`Long Term · ${d.symbol}`}
      right={<ModelStackPill stack={d.model_stack} />}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        {horizons.map(({ k, info }) => (
          <div key={k} className="p-3 rounded-xl border" style={{ borderColor: 'var(--border-color)' }}>
            <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{k} horizon</div>
            <div className="flex items-baseline gap-2">
              <div className="text-xl font-bold">{info?.target_price ?? '—'}</div>
              <div className="text-sm font-semibold" style={{ color: pctColor(info?.expected_return_pct) }}>
                {fmtPct(info?.expected_return_pct)}
              </div>
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Band {info?.band_low} – {info?.band_high}
            </div>
            <div className="text-xs mt-1">
              P(up) = <b>{((info?.probability_up || 0) * 100).toFixed(1)}%</b>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3">
        <Stat label="Last"         value={String(d.last_price ?? '—')} />
        <Stat label="Swing Action" value={st.direction ?? '—'}
              tone={st.direction === 'BUY' ? 'pos' : st.direction === 'SELL' ? 'neg' : 'neutral'} />
        <Stat label="Entry"        value={String(st.entry ?? '—')} />
        <Stat label="Stop"         value={String(st.stop_loss ?? '—')} tone="neg" />
        <Stat label="Target / R:R" value={`${st.take_profit_1 ?? '—'} / ${st.risk_reward ?? '—'}`} tone="pos" />
      </div>

      <ForecastChart
        history={d.history || []}
        forecast={d.path || []}
        lastPrice={d.last_price}
        entry={st.entry}
        stop={st.stop_loss}
        target1={st.take_profit_1}
        target2={st.take_profit_2}
        height={340}
      />

      <div className="text-xs mt-2 italic" style={{ color: 'var(--text-muted)' }}>
        {d.rationale}
      </div>

      {d.xgb && (
        <div className="text-xs mt-2 p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
          <b>ML tilt applied</b>: XGBoost p(up next day) = {d.xgb.p_up_next_day}
          · test AUC {d.xgb.test_auc ?? '—'} · trained on {d.xgb.period ?? '2y'}
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button onClick={onExplain} disabled={briefBusy}
                className="text-xs px-3 py-2 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white flex items-center gap-1">
          <Sparkles size={12} /> {briefBusy ? 'thinking...' : 'Explain with AI'}
        </button>
      </div>
      {brief && <LlmExplainer brief={brief} />}
    </Card>
  )
}

/* ── LLM-explained brief ─────────────────────────────────────────────────── */

function LlmExplainer({ brief }: any) {
  const b = brief?.brief || brief?.fallback_brief || {}
  return (
    <div className="mt-3 p-3 rounded-xl border" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-xs font-semibold uppercase tracking-wide">AI Brief</div>
        <LlmBadge llm={brief?.llm_used} compact />
      </div>
      {brief?.llm_error && (
        <div className="text-xs text-amber-700 mb-2">LLM unavailable: {brief.llm_error} — showing fallback.</div>
      )}
      {b.summary && <div className="text-sm mb-2">{b.summary}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {b.bull_case && (
          <div className="p-2 rounded-lg bg-emerald-50 text-sm">
            <div className="font-semibold text-emerald-700 flex items-center gap-1"><ArrowUpRight size={12} /> Bull case</div>
            <div>{b.bull_case}</div>
          </div>
        )}
        {b.bear_case && (
          <div className="p-2 rounded-lg bg-rose-50 text-sm">
            <div className="font-semibold text-rose-700 flex items-center gap-1"><ArrowDownRight size={12} /> Bear case</div>
            <div>{b.bear_case}</div>
          </div>
        )}
      </div>
      {b.trade_plan && (
        <div className="mt-2 text-sm p-2 rounded-lg bg-indigo-50">
          <div className="font-semibold text-indigo-700 flex items-center gap-1"><Target size={12} /> Trade plan</div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-1 text-xs">
            <div><b>action</b>: {b.trade_plan.action ?? '—'}</div>
            <div><b>entry</b>: {b.trade_plan.entry ?? '—'}</div>
            <div><b>stop</b>: {b.trade_plan.stop ?? '—'}</div>
            <div><b>tp1</b>: {b.trade_plan.target_1 ?? '—'}</div>
            <div><b>tp2</b>: {b.trade_plan.target_2 ?? '—'}</div>
          </div>
          {b.trade_plan.position_size_pct != null && (
            <div className="text-xs mt-1">size: {b.trade_plan.position_size_pct}% of portfolio</div>
          )}
        </div>
      )}
      {b.confidence_label && (
        <div className="mt-2 text-xs" style={{ color: 'var(--text-muted)' }}>
          Confidence: <b>{b.confidence_label}</b>
        </div>
      )}
      {b.disclaimer && (
        <div className="mt-2 text-xs italic" style={{ color: 'var(--text-muted)' }}>{b.disclaimer}</div>
      )}
    </div>
  )
}

function Disclaimer() {
  return (
    <div className="mt-6 p-3 rounded-xl border text-xs" style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}>
      <b>Not financial advice.</b> Forecasts are statistical tilts — daily directional models rarely exceed ~55–60% accuracy. Always verify with your own research and never risk more than you can afford to lose. Past performance ≠ future returns.
    </div>
  )
}
