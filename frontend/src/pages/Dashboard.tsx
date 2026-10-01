import { useState, useEffect, useRef } from 'react'
import { Sparkles, Calendar, ShoppingCart, Plane, TrendingUp, Heart, CheckSquare, ArrowUpRight, ArrowDownRight, Clock, Zap, Brain, UtensilsCrossed, Wrench, Send, Plus, Check } from 'lucide-react'
import client from '../api/client'

interface MarketIndex { price: number; chg_1d_pct: number; chg_5d_pct: number }
interface CalEvent { title: string; date: string; time?: string }
interface Task { id: string; title: string; status: string; priority: string }

export default function Dashboard() {
  const [market, setMarket] = useState<Record<string, MarketIndex> | null>(null)
  const [events, setEvents] = useState<CalEvent[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  // Quick Capture
  const [captureText, setCaptureText] = useState('')
  const [captureCategory, setCaptureCategory] = useState<'task' | 'chore' | 'habit'>('task')
  const [captureSending, setCaptureSending] = useState(false)
  const [captureSuccess, setCaptureSuccess] = useState(false)
  const captureRef = useRef<HTMLInputElement>(null)

  const handleCapture = async () => {
    const text = captureText.trim()
    if (!text || captureSending) return
    setCaptureSending(true)
    try {
      const user = JSON.parse(localStorage.getItem('auth_user') || '{}')
      await client.post('/api/tasks', {
        user_id: user.user_id || 'default',
        title: text,
        category: captureCategory,
      })
      setCaptureText('')
      setCaptureSuccess(true)
      setTimeout(() => setCaptureSuccess(false), 2000)
      // Refresh task list
      const r = await client.get('/api/tasks')
      const raw = r.data.tasks ?? []
      setTasks(raw.filter((t: Task) => t.status !== 'completed').slice(0, 5))
    } catch { /* silent */ }
    finally { setCaptureSending(false) }
  }

  useEffect(() => {
    const load = async () => {
      const results = await Promise.allSettled([
        client.get('/api/market-intel/overview'),
        client.get('/api/calendar/upcoming'),
        client.get('/api/tasks'),
      ])
      if (results[0].status === 'fulfilled') setMarket(results[0].value.data.indices)
      if (results[1].status === 'fulfilled') setEvents(results[1].value.data.events?.slice(0, 5) ?? [])
      if (results[2].status === 'fulfilled') {
        const raw = results[2].value.data.tasks ?? []
        setTasks(raw.filter((t: Task) => t.status !== 'completed').slice(0, 5))
      }
      setLoading(false)
    }
    load()
  }, [])

  const greeting = () => {
    const h = new Date().getHours()
    if (h < 12) return 'Good morning'
    if (h < 17) return 'Good afternoon'
    return 'Good evening'
  }

  const quickActions = [
    { icon: Sparkles, label: 'Ask Avira', color: 'from-indigo-500 to-purple-600', href: '#assistant' },
    { icon: Calendar, label: 'Calendar', color: 'from-blue-500 to-cyan-500', href: '#calendar' },
    { icon: ShoppingCart, label: 'Shopping', color: 'from-emerald-500 to-teal-500', href: '#shopping' },
    { icon: Plane, label: 'Travel', color: 'from-orange-500 to-amber-500', href: '#travel' },
    { icon: TrendingUp, label: 'Investments', color: 'from-violet-500 to-purple-500', href: '#portfolio' },
    { icon: Heart, label: 'Health', color: 'from-rose-500 to-pink-500', href: '#health' },
    { icon: Brain, label: 'Market Intel', color: 'from-cyan-500 to-blue-600', href: '#market_intel' },
    { icon: UtensilsCrossed, label: 'Meals', color: 'from-lime-500 to-green-600', href: '#grocery' },
  ]

  const fmtPct = (v: number) => {
    const sign = v >= 0 ? '+' : ''
    return `${sign}${v.toFixed(2)}%`
  }

  const indexLabel: Record<string, string> = {
    '^GSPC': 'S&P 500',
    '^IXIC': 'Nasdaq',
    '^DJI': 'Dow Jones',
  }

  return (
    <div className="p-6 md:p-8 fade-in max-w-7xl mx-auto">
      {/* Hero */}
      <div className="mb-8">
        <div className="flex items-center gap-4 mb-1">
          <div className="w-14 h-14 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
            <Sparkles className="text-white" size={28} />
          </div>
          <div>
            <h1 className="text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>{greeting()}</h1>
            <p style={{ color: 'var(--text-muted)' }}>
              {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
        </div>
      </div>

      {/* Quick Capture */}
      <div className="mb-6 p-4 rounded-2xl border" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all ${captureSuccess ? 'bg-emerald-500' : 'bg-gradient-to-br from-indigo-500 to-purple-600'}`}>
            {captureSuccess ? <Check className="text-white" size={18} /> : <Plus className="text-white" size={18} />}
          </div>
          <input
            ref={captureRef}
            value={captureText}
            onChange={e => setCaptureText(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleCapture() }}
            placeholder={captureSuccess ? 'Captured!' : 'Quick capture — type a task, reminder, or note…'}
            className="flex-1 bg-transparent outline-none text-sm"
            style={{ color: 'var(--text-primary)' }}
          />
          <div className="flex items-center gap-1.5 shrink-0">
            {(['task', 'chore', 'habit'] as const).map(cat => (
              <button key={cat} onClick={() => setCaptureCategory(cat)}
                className="px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all capitalize"
                style={{
                  background: captureCategory === cat ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                  color: captureCategory === cat ? '#fff' : 'var(--text-muted)',
                }}>
                {cat}
              </button>
            ))}
          </div>
          <button onClick={handleCapture} disabled={!captureText.trim() || captureSending}
            className="p-2 rounded-xl transition-all disabled:opacity-30"
            style={{ background: 'var(--accent-primary)', color: '#fff' }}>
            <Send size={16} />
          </button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="text-sm font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-muted)' }}>Quick Actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {quickActions.map((action) => {
            const Icon = action.icon
            return (
              <a key={action.label} href={action.href}
                className="group p-3 rounded-xl border hover:shadow-lg transition-all duration-300 text-center"
                style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
                <div className={`w-10 h-10 mx-auto bg-gradient-to-br ${action.color} rounded-xl flex items-center justify-center mb-2 group-hover:scale-110 transition-transform shadow-md`}>
                  <Icon className="text-white" size={20} />
                </div>
                <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>{action.label}</span>
              </a>
            )
          })}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">

        {/* Markets — live data */}
        <div className="lg:col-span-2 p-5 rounded-xl border" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <TrendingUp size={20} className="text-violet-500" /> Markets
            </h2>
            <a href="#market_intel" className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>Full dashboard →</a>
          </div>
          {loading ? (
            <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-7 w-7 border-b-2 border-indigo-500" /></div>
          ) : market ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {['^GSPC', '^IXIC', '^DJI'].map(sym => {
                const d = market[sym]
                if (!d) return null
                const up = d.chg_1d_pct >= 0
                return (
                  <div key={sym} className="rounded-xl p-4" style={{ background: 'var(--bg-tertiary)' }}>
                    <p className="text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>{indexLabel[sym] || sym}</p>
                    <p className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                      {d.price.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                    </p>
                    <div className="flex items-center gap-1 mt-1">
                      {up ? <ArrowUpRight size={14} className="text-emerald-500" /> : <ArrowDownRight size={14} className="text-red-500" />}
                      <span className={`text-xs font-semibold ${up ? 'text-emerald-500' : 'text-red-500'}`}>{fmtPct(d.chg_1d_pct)}</span>
                      <span className="text-xs ml-1" style={{ color: 'var(--text-muted)' }}>today</span>
                    </div>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>5d {fmtPct(d.chg_5d_pct)}</p>
                  </div>
                )
              })}
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Market data unavailable</p>
          )}
        </div>

        {/* Upcoming Events */}
        <div className="p-5 rounded-xl border" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <Calendar size={20} className="text-blue-500" /> Upcoming
            </h2>
            <a href="#calendar" className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>Calendar →</a>
          </div>
          {events.length > 0 ? (
            <div className="space-y-3">
              {events.map((ev, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: 'var(--bg-tertiary)' }}>
                    <Clock size={14} style={{ color: 'var(--text-muted)' }} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{ev.title}</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{ev.date}{ev.time ? ` · ${ev.time}` : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm py-4" style={{ color: 'var(--text-muted)' }}>No upcoming events — <a href="#calendar" style={{ color: 'var(--accent-primary)' }}>add one</a></p>
          )}
        </div>
      </div>

      {/* Second Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">

        {/* Tasks */}
        <div className="p-5 rounded-xl border" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
              <CheckSquare size={20} className="text-amber-500" /> Tasks
            </h2>
            <a href="#tasks" className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>All tasks →</a>
          </div>
          {tasks.length > 0 ? (
            <div className="space-y-2">
              {tasks.map(t => (
                <div key={t.id} className="flex items-center gap-3 p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  <span className={`w-2 h-2 rounded-full flex-shrink-0 ${t.priority === 'high' ? 'bg-red-500' : t.priority === 'medium' ? 'bg-amber-500' : 'bg-blue-400'}`} />
                  <span className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{t.title}</span>
                  <span className="ml-auto text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--card-bg)', color: 'var(--text-muted)' }}>{t.status}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm py-4" style={{ color: 'var(--text-muted)' }}>All clear! <a href="#tasks" style={{ color: 'var(--accent-primary)' }}>Create a task</a></p>
          )}
        </div>

        {/* Quick Links */}
        <div className="p-5 rounded-xl border" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Zap size={20} className="text-indigo-500" /> Explore
          </h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Shopping Deals', href: '#shopping', icon: ShoppingCart, color: 'text-emerald-500' },
              { label: 'Health Records', href: '#health', icon: Heart, color: 'text-rose-500' },
              { label: 'Maintenance', href: '#maintenance', icon: Wrench, color: 'text-orange-500' },
              { label: 'Meal Planning', href: '#grocery', icon: UtensilsCrossed, color: 'text-lime-600' },
            ].map(link => {
              const Icon = link.icon
              return (
                <a key={link.label} href={link.href}
                  className="flex items-center gap-2 p-3 rounded-lg hover:shadow-sm transition-all"
                  style={{ background: 'var(--bg-tertiary)' }}>
                  <Icon size={16} className={link.color} />
                  <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{link.label}</span>
                </a>
              )
            })}
          </div>
        </div>
      </div>

      {/* Privacy Notice */}
      <div className="p-5 rounded-xl border border-l-4 border-l-indigo-500 flex gap-4" style={{ background: 'var(--card-bg)', borderColor: 'var(--card-border)' }}>
        <div className="w-9 h-9 bg-indigo-100 rounded-xl flex items-center justify-center flex-shrink-0">
          <Zap className="text-indigo-600" size={18} />
        </div>
        <div>
          <h3 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>Privacy First</h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
            All data is processed locally. PII/PHI/PCI is automatically masked before any external API calls.
          </p>
        </div>
      </div>
    </div>
  )
}
