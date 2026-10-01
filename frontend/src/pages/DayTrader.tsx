import { useEffect, useState, useCallback } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  BarChart3,
  CircleDollarSign,
  Clock,
  Eye,
  Play,
  RefreshCw,
  RotateCcw,
  Scan,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
  Zap,
} from 'lucide-react'
import config from '../config'

const API = config.apiBase

// ── Helpers ──────────────────────────────────────────────────────────────────

const pctColor = (n: number) => (n >= 0 ? '#16a34a' : '#dc2626')
const fmtUSD = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`

const signalColor: Record<string, string> = {
  STRONG_BUY: '#16a34a',
  BUY: '#22c55e',
  HOLD: '#a3a3a3',
  SELL: '#f87171',
  STRONG_SELL: '#dc2626',
}

const signalIcon: Record<string, any> = {
  STRONG_BUY: TrendingUp,
  BUY: ArrowUp,
  HOLD: Activity,
  SELL: ArrowDown,
  STRONG_SELL: TrendingDown,
}

// ── Card Component ───────────────────────────────────────────────────────────

function Card({ title, icon: Icon, right, children, className = '' }: any) {
  return (
    <div className={`rounded-2xl border p-4 ${className}`} style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && <Icon size={16} style={{ color: 'var(--text-muted)' }} />}
          <h3 className="font-semibold text-sm uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
        </div>
        {right}
      </div>
      {children}
    </div>
  )
}

// ── Signal Badge ─────────────────────────────────────────────────────────────

function SignalBadge({ signal, confidence }: { signal: string; confidence: number }) {
  const SIcon = signalIcon[signal] || Activity
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-bold" style={{ background: `${signalColor[signal] || '#888'}20`, color: signalColor[signal] || '#888' }}>
      <SIcon size={12} />
      {signal.replace('_', ' ')} {confidence}%
    </div>
  )
}


function TelegramAlertToggle() {
  const [cfg, setCfg] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/telegram/status`)
      const d = await r.json()
      setCfg(d)
    } catch {}
  }, [])

  const toggleFeature = async (key: string, val: boolean) => {
    setLoading(true)
    try {
      await fetch(`${API}/api/telegram/features`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: val }),
      })
      await load()
    } catch {}
    setLoading(false)
  }

  const sendTest = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/telegram/test`, { method: 'POST' })
      if (!r.ok) throw new Error('Test failed')
      alert('Test message sent! Check Telegram.')
    } catch {
      alert('Test failed. Make sure you sent /start to the bot first.')
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  if (!cfg?.configured) return (
    <Card title="Telegram Alerts" icon={Zap}>
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Telegram bot not configured. Set TELEGRAM_BOT_TOKEN on the backend to enable alerts.
      </p>
    </Card>
  )

  const features = cfg?.features || {}
  return (
    <Card title="Telegram Alerts" icon={Zap}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {cfg.chat_bound ? (
            <span style={{ color: '#16a34a' }}>Connected</span>
          ) : (
            <span>Not bound — message the bot and send /start</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {[
            { key: 'day_trade_tips', label: 'Day-trade tips' },
            { key: 'email_alerts', label: 'Email alerts' },
            { key: 'price_alerts', label: 'Price alerts' },
            { key: 'trade_exits', label: 'Trade exits' },
          ].map((f) => (
            <button
              key={f.key}
              onClick={() => toggleFeature(f.key, !features[f.key])}
              disabled={loading}
              className="px-2 py-1 rounded-lg text-xs font-medium border transition-colors"
              style={{
                borderColor: features[f.key] ? '#16a34a' : 'var(--border-color)',
                background: features[f.key] ? '#16a34a20' : 'var(--bg-tertiary)',
                color: features[f.key] ? '#16a34a' : 'var(--text-muted)',
              }}
            >
              {features[f.key] ? '✓' : '○'} {f.label}
            </button>
          ))}
          <button
            onClick={sendTest}
            disabled={loading}
            className="px-2 py-1 rounded-lg text-xs font-medium border"
            style={{ borderColor: 'var(--border-color)', color: 'var(--text-secondary)' }}
          >
            Test
          </button>
        </div>
      </div>
    </Card>
  )
}

// ── Trading Mode Card ────────────────────────────────────────────────────────

function TradingModeCard() {
  const [mode, setMode] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/trading/mode`)
      const d = await r.json()
      setMode(d.mode)
    } catch {}
  }, [])

  const toggleMode = async () => {
    if (!mode) return
    const newMode = mode.mode === 'paper' ? 'real' : 'paper'
    setLoading(true)
    try {
      await fetch(`${API}/api/trading/mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: newMode }),
      })
      await load()
    } catch {}
    setLoading(false)
  }

  const toggleAuto = async () => {
    if (!mode) return
    setLoading(true)
    try {
      await fetch(`${API}/api/trading/mode`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_trades_enabled: !mode.auto_trades_enabled }),
      })
      await load()
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  if (!mode) return null

  const isPaper = mode.mode === 'paper'
  return (
    <Card title="Trading Mode" icon={ShieldCheck}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className="px-2 py-1 rounded-full text-xs font-bold"
            style={{
              background: isPaper ? '#3b82f620' : '#dc262620',
              color: isPaper ? '#3b82f6' : '#dc2626',
            }}
          >
            {isPaper ? 'PAPER' : 'REAL'}
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {isPaper ? 'Simulated trades' : 'Live Robinhood account'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleMode}
            disabled={loading}
            className="px-3 py-1 rounded-lg text-xs font-medium border"
            style={{ borderColor: 'var(--border-color)', color: 'var(--text-secondary)' }}
          >
            Switch to {isPaper ? 'Real' : 'Paper'}
          </button>
          <button
            onClick={toggleAuto}
            disabled={loading}
            className="px-3 py-1 rounded-lg text-xs font-medium border transition-colors"
            style={{
              borderColor: mode.auto_trades_enabled ? '#16a34a' : 'var(--border-color)',
              background: mode.auto_trades_enabled ? '#16a34a20' : 'var(--bg-tertiary)',
              color: mode.auto_trades_enabled ? '#16a34a' : 'var(--text-muted)',
            }}
          >
            {mode.auto_trades_enabled ? '✓ Auto 5/day ON' : '○ Auto 5/day OFF'}
          </button>
        </div>
      </div>
      <div className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
        Max {mode.max_auto_trades_per_day} trades/day · Risk {mode.risk_per_trade_pct}%/trade · Position {mode.max_position_pct}%
      </div>
    </Card>
  )
}

// ── Backtest / Potential Earnings ────────────────────────────────────────────

function BacktestCard() {
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const run = async () => {
    setLoading(true)
    try {
      const r = await fetch(`${API}/api/trading/backtest?days=30&initial_capital=100000`, { method: 'POST' })
      const d = await r.json()
      setResult(d)
    } catch {}
    setLoading(false)
  }

  return (
    <Card title="Potential Earnings (30-day backtest)" icon={BarChart3}>
      <div className="flex items-center gap-3 mb-3">
        <button
          onClick={run}
          disabled={loading}
          className="px-3 py-1 rounded-lg text-xs font-medium text-white"
          style={{ background: loading ? '#6b7280' : '#3b82f6' }}
        >
          {loading ? 'Running...' : 'Run Backtest'}
        </button>
      </div>
      {result && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="text-center p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Initial</div>
            <div className="font-bold">{fmtUSD(result.initial_capital)}</div>
          </div>
          <div className="text-center p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Final</div>
            <div className="font-bold">{fmtUSD(result.final_capital)}</div>
          </div>
          <div className="text-center p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Return</div>
            <div className="font-bold" style={{ color: pctColor(result.total_return_pct) }}>
              {result.total_return_pct >= 0 ? '+' : ''}{result.total_return_pct}%
            </div>
          </div>
          <div className="text-center p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Trades</div>
            <div className="font-bold">{result.trades_executed}</div>
          </div>
        </div>
      )}
    </Card>
  )
}

type TabType = 'scanner' | 'portfolio' | 'journal'

// ── Main Page ────────────────────────────────────────────────────────────────

export default function DayTrader() {
  const [tab, setTab] = useState<TabType>('scanner')
  const [scanData, setScanData] = useState<any>(null)
  const [portfolio, setPortfolio] = useState<any>(null)
  const [scanning, setScanning] = useState(false)
  const [autoMode, setAutoMode] = useState(false)
  const [detail, setDetail] = useState<any>(null)
  const [executing, setExecuting] = useState<string | null>(null)
  const [error, setError] = useState('')

  const runScan = useCallback(async (autoExec = false) => {
    setScanning(true)
    setError('')
    try {
      const res = await fetch(`${API}/api/trading/auto-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto_execute: autoExec, min_confidence: 50, user_id: 'testuser01' }),
      })
      const data = await res.json()
      setScanData(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }, [])

  const loadPortfolio = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/trading/portfolio?user_id=testuser01`)
      setPortfolio(await res.json())
    } catch {}
  }, [])

  const executeTrade = async (symbol: string, action: string) => {
    setExecuting(symbol)
    try {
      const res = await fetch(`${API}/api/trading/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, action, user_id: 'testuser01' }),
      })
      if (!res.ok) {
        const err = await res.json()
        setError(err.detail || 'Trade failed')
        return
      }
      await loadPortfolio()
      setError('')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setExecuting(null)
    }
  }

  const resetPortfolio = async () => {
    if (!confirm('Reset paper portfolio to $100,000?')) return
    await fetch(`${API}/api/trading/reset?user_id=testuser01`, { method: 'POST' })
    await loadPortfolio()
  }

  useEffect(() => {
    runScan(false)
    loadPortfolio()
  }, [])

  // Auto-scan every 2 minutes if autoMode
  useEffect(() => {
    if (!autoMode) return
    const iv = setInterval(() => runScan(true), 120_000)
    return () => clearInterval(iv)
  }, [autoMode])

  const tabs = [
    { id: 'scanner', label: 'Scanner', icon: Scan },
    { id: 'portfolio', label: 'Portfolio', icon: Wallet },
    { id: 'journal', label: 'Trade Journal', icon: BarChart3 },
  ]

  const allSignals = scanData?.all_signals || []
  const buySignals = allSignals.filter((s: any) => s.signal === 'STRONG_BUY' || s.signal === 'BUY')
  const sellSignals = allSignals.filter((s: any) => s.signal === 'STRONG_SELL' || s.signal === 'SELL')

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Zap className="text-amber-500" /> Day Trading Assistant
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Autonomous scanner · Paper trading · Signal intelligence
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => runScan(autoMode)}
            disabled={scanning}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-medium text-white"
            style={{ background: scanning ? '#6b7280' : '#3b82f6' }}
          >
            {scanning ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
            {scanning ? 'Scanning...' : 'Scan Now'}
          </button>
          <button
            onClick={() => { setAutoMode(!autoMode); if (!autoMode) runScan(true) }}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-sm font-medium border"
            style={{
              borderColor: autoMode ? '#16a34a' : 'var(--border-color)',
              background: autoMode ? '#16a34a20' : 'var(--bg-tertiary)',
              color: autoMode ? '#16a34a' : 'var(--text-secondary)',
            }}
          >
            <ShieldCheck size={14} />
            {autoMode ? 'Auto ON' : 'Auto OFF'}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl text-sm flex items-center gap-2" style={{ background: '#dc262620', color: '#dc2626' }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Telegram Alerts */}
      <TelegramAlertToggle />

      {/* Trading Mode Toggle */}
      <TradingModeCard />

      {/* Potential Earnings Backtest */}
      <BacktestCard />

      {/* Quick Stats */}
      {portfolio && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Portfolio', value: fmtUSD(portfolio.portfolio_value), icon: Wallet },
            { label: 'Cash', value: fmtUSD(portfolio.cash), icon: CircleDollarSign },
            { label: 'Total Return', value: fmtPct(portfolio.total_return_pct), color: pctColor(portfolio.total_return_pct), icon: TrendingUp },
            { label: 'Win Rate', value: `${portfolio.win_rate}%`, icon: Target },
            { label: 'Open Positions', value: `${portfolio.open_positions?.length || 0}`, icon: Eye },
          ].map((s, i) => (
            <div key={i} className="rounded-xl border p-3 text-center" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
              <s.icon size={16} className="mx-auto mb-1" style={{ color: 'var(--text-muted)' }} />
              <div className="text-lg font-bold" style={{ color: s.color || 'var(--text-primary)' }}>{s.value}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id as TabType)}
            className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition"
            style={{
              background: tab === t.id ? 'var(--bg-secondary)' : 'transparent',
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              boxShadow: tab === t.id ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
            }}
          >
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      {/* Scanner Tab */}
      {tab === 'scanner' && (
        <div className="space-y-4">
          {/* Summary bar */}
          {scanData && (
            <div className="flex flex-wrap gap-3 text-sm">
              <span style={{ color: 'var(--text-muted)' }}>Scanned: <b>{scanData.scanned}</b></span>
              <span style={{ color: '#16a34a' }}>Buy signals: <b>{scanData.buy_signals}</b></span>
              <span style={{ color: '#dc2626' }}>Sell signals: <b>{scanData.sell_signals}</b></span>
              {scanData.executed_trades?.length > 0 && (
                <span style={{ color: '#3b82f6' }}>Auto-executed: <b>{scanData.executed_trades.length}</b></span>
              )}
              {scanData.triggered_stops?.length > 0 && (
                <span style={{ color: '#f59e0b' }}>Stops triggered: <b>{scanData.triggered_stops.length}</b></span>
              )}
            </div>
          )}

          {/* Buy Signals */}
          {buySignals.length > 0 && (
            <Card title="Buy Signals" icon={TrendingUp}>
              <div className="space-y-2">
                {buySignals.map((s: any) => (
                  <div
                    key={s.symbol}
                    className="flex flex-col md:flex-row md:items-center justify-between gap-2 p-3 rounded-xl border cursor-pointer hover:opacity-90 transition"
                    style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}
                    onClick={() => setDetail(detail?.symbol === s.symbol ? null : s)}
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold text-lg" style={{ color: 'var(--text-primary)' }}>{s.symbol}</span>
                      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>${s.price?.toFixed(2)}</span>
                      <SignalBadge signal={s.signal} confidence={s.confidence} />
                    </div>
                    <div className="flex items-center gap-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                      <span>Entry: <b>${s.entry?.toFixed(2)}</b></span>
                      <span>Stop: <b style={{ color: '#dc2626' }}>${s.stop_loss?.toFixed(2)}</b></span>
                      <span>TP: <b style={{ color: '#16a34a' }}>${s.take_profit_1?.toFixed(2)}</b></span>
                      <span>R:R <b>{s.risk_reward}</b></span>
                      <button
                        onClick={(e) => { e.stopPropagation(); executeTrade(s.symbol, 'BUY') }}
                        disabled={executing === s.symbol}
                        className="ml-2 px-3 py-1 rounded-lg text-white text-xs font-bold"
                        style={{ background: '#16a34a' }}
                      >
                        {executing === s.symbol ? '...' : 'Paper Buy'}
                      </button>
                    </div>
                    {detail?.symbol === s.symbol && (
                      <div className="w-full mt-2 pt-2 border-t text-xs space-y-1" style={{ borderColor: 'var(--border-color)' }}>
                        <div><b>Reasons:</b> {s.reasons?.join(' · ')}</div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-1">
                          {Object.entries(s.indicators || {}).map(([k, v]) => (
                            <span key={k} style={{ color: 'var(--text-muted)' }}>{k}: <b>{typeof v === 'number' ? (v as number).toFixed(2) : String(v)}</b></span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Sell Signals */}
          {sellSignals.length > 0 && (
            <Card title="Sell Signals" icon={TrendingDown}>
              <div className="space-y-2">
                {sellSignals.map((s: any) => (
                  <div
                    key={s.symbol}
                    className="flex flex-col md:flex-row md:items-center justify-between gap-2 p-3 rounded-xl border"
                    style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold" style={{ color: 'var(--text-primary)' }}>{s.symbol}</span>
                      <span className="text-sm" style={{ color: 'var(--text-muted)' }}>${s.price?.toFixed(2)}</span>
                      <SignalBadge signal={s.signal} confidence={s.confidence} />
                    </div>
                    <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {s.reasons?.slice(0, 2).join(' · ')}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Hold / Neutral */}
          <Card title="All Scanned" icon={Activity}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: 'var(--text-muted)' }}>
                    <th className="text-left py-1">Symbol</th>
                    <th className="text-right py-1">Price</th>
                    <th className="text-center py-1">Signal</th>
                    <th className="text-right py-1">RSI</th>
                    <th className="text-right py-1">MACD</th>
                    <th className="text-right py-1">BB%</th>
                    <th className="text-right py-1">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {allSignals.map((s: any) => (
                    <tr key={s.symbol} className="border-t" style={{ borderColor: 'var(--border-color)' }}>
                      <td className="font-mono font-bold py-1.5">{s.symbol}</td>
                      <td className="text-right">${s.price?.toFixed(2)}</td>
                      <td className="text-center"><SignalBadge signal={s.signal} confidence={s.confidence} /></td>
                      <td className="text-right">{s.indicators?.rsi?.toFixed(1)}</td>
                      <td className="text-right" style={{ color: (s.indicators?.macd_histogram || 0) >= 0 ? '#16a34a' : '#dc2626' }}>
                        {s.indicators?.macd_histogram?.toFixed(3)}
                      </td>
                      <td className="text-right">{((s.indicators?.bollinger_pct || 0) * 100).toFixed(0)}%</td>
                      <td className="text-right font-bold" style={{ color: (s.indicators?.score || 0) >= 0 ? '#16a34a' : '#dc2626' }}>
                        {s.indicators?.score}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* Portfolio Tab */}
      {tab === 'portfolio' && portfolio && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={resetPortfolio}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border"
              style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
            >
              <RotateCcw size={12} /> Reset Portfolio
            </button>
          </div>

          {/* Open Positions */}
          <Card title={`Open Positions (${portfolio.open_positions?.length || 0})`} icon={Eye}>
            {portfolio.open_positions?.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No open positions. Scan for signals to start trading.</p>
            ) : (
              <div className="space-y-2">
                {portfolio.open_positions?.map((t: any) => (
                  <div key={t.id} className="flex flex-col md:flex-row md:items-center justify-between p-3 rounded-xl border gap-2" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}>
                    <div>
                      <span className="font-mono font-bold text-lg">{t.symbol}</span>
                      <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>{t.quantity} shares @ ${t.entry_price?.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span>Now: <b>${t.current_price?.toFixed(2)}</b></span>
                      <span style={{ color: pctColor(t.unrealized_pnl) }}>
                        {fmtUSD(t.unrealized_pnl)} ({fmtPct(t.unrealized_pnl_pct)})
                      </span>
                      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>SL: ${t.stop_loss?.toFixed(2)} · TP: ${t.take_profit?.toFixed(2)}</span>
                      <button
                        onClick={() => executeTrade(t.symbol, 'SELL')}
                        className="px-3 py-1 rounded-lg text-white text-xs font-bold"
                        style={{ background: '#dc2626' }}
                      >
                        Sell
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* P&L Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card title="Realized P&L" icon={CircleDollarSign}>
              <div className="text-2xl font-bold" style={{ color: pctColor(portfolio.realized_pnl) }}>
                {fmtUSD(portfolio.realized_pnl)}
              </div>
            </Card>
            <Card title="Unrealized P&L" icon={Activity}>
              <div className="text-2xl font-bold" style={{ color: pctColor(portfolio.unrealized_pnl) }}>
                {fmtUSD(portfolio.unrealized_pnl)}
              </div>
            </Card>
            <Card title="Win Rate" icon={Target}>
              <div className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {portfolio.win_rate}%
              </div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{portfolio.total_trades} total trades</div>
            </Card>
          </div>
        </div>
      )}

      {/* Journal Tab */}
      {tab === 'journal' && portfolio && (
        <Card title="Trade Journal" icon={BarChart3}>
          {portfolio.closed_trades?.length === 0 ? (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No closed trades yet.</p>
          ) : (
            <div className="space-y-2">
              {[...portfolio.closed_trades].reverse().map((t: any) => (
                <div key={t.id} className="p-3 rounded-xl border" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}>
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                    <div className="flex items-center gap-3">
                      <span className="font-mono font-bold">{t.symbol}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full" style={{
                        background: t.status === 'TAKE_PROFIT' ? '#16a34a20' : t.status === 'STOPPED_OUT' ? '#dc262620' : '#3b82f620',
                        color: t.status === 'TAKE_PROFIT' ? '#16a34a' : t.status === 'STOPPED_OUT' ? '#dc2626' : '#3b82f6',
                      }}>
                        {t.status}
                      </span>
                      <span style={{ color: pctColor(t.pnl) }} className="font-bold">{fmtUSD(t.pnl)} ({fmtPct(t.pnl_pct)})</span>
                    </div>
                    <div className="text-xs flex items-center gap-2" style={{ color: 'var(--text-muted)' }}>
                      <Clock size={12} />
                      <span>{t.entry_time?.slice(0, 16)} → {t.exit_time?.slice(0, 16)}</span>
                    </div>
                  </div>
                  <div className="text-xs mt-1 space-y-0.5" style={{ color: 'var(--text-muted)' }}>
                    <div>Entry: ${t.entry_price?.toFixed(2)} × {t.quantity} → Exit: ${t.exit_price?.toFixed(2)}</div>
                    <div>Entry reason: {t.reason_entry}</div>
                    <div>Exit reason: {t.reason_exit}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  )
}
