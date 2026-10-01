import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Brain,
  ChevronRight,
  Clock,
  Cpu,
  ExternalLink,
  FileText,
  Flame,
  Globe,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react'
import config from '../config'
import { LlmBadge } from '../components/LlmBadge'

type Tab =
  | 'overview'
  | 'ai_boom'
  | 'influencers'
  | 'geopolitics'
  | 'big_money'
  | 'sec_filings'
  | 'tech'
  | 'resources'
  | 'synthesis'

const TABS: { id: Tab; label: string; icon: any }[] = [
  { id: 'overview',    label: 'Overview',        icon: Activity },
  { id: 'ai_boom',     label: 'AI Boom',         icon: Cpu },
  { id: 'synthesis',   label: 'AI Brief',        icon: Brain },
  { id: 'influencers', label: 'Influencers',     icon: Users },
  { id: 'geopolitics', label: 'War & Geo',       icon: Globe },
  { id: 'big_money',   label: 'Big Money',       icon: Flame },
  { id: 'sec_filings', label: 'SEC Filings',     icon: FileText },
  { id: 'tech',        label: 'Tech & Innov.',   icon: Zap },
  { id: 'resources',   label: 'Resources',       icon: Sparkles },
]

const API = config.apiBase

const fmtPct = (n?: number | null) =>
  n == null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(2)}%`

const pctColor = (n?: number | null) =>
  n == null ? 'var(--text-muted)' : n >= 0 ? '#16a34a' : '#dc2626'

const Card = ({ title, right, children }: any) => (
  <div className="rounded-2xl border p-4 mb-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
    <div className="flex items-center justify-between mb-3">
      <h3 className="font-semibold text-sm uppercase tracking-wide" style={{ color: 'var(--text-secondary)' }}>{title}</h3>
      {right}
    </div>
    {children}
  </div>
)

const Pill = ({ label, tone = 'neutral' }: { label: string; tone?: 'pos' | 'neg' | 'neutral' | 'warn' }) => {
  const colors: Record<string, string> = {
    pos:     'bg-emerald-100 text-emerald-700',
    neg:     'bg-rose-100 text-rose-700',
    warn:    'bg-amber-100 text-amber-700',
    neutral: 'bg-slate-100 text-slate-700',
  }
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${colors[tone]}`}>{label}</span>
}

function regimeTone(regime?: string): 'pos' | 'neg' | 'warn' | 'neutral' {
  if (!regime) return 'neutral'
  if (regime === 'expansion' || regime === 'blow-off-top') return 'pos'
  if (regime === 'cooling' || regime === 'correction') return 'neg'
  return 'neutral'
}

export default function MarketIntelligence() {
  const [tab, setTab] = useState<Tab>('overview')
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const endpoint = useMemo(() => {
    switch (tab) {
      case 'overview':    return `${API}/api/market-intel/snapshot`
      case 'ai_boom':     return `${API}/api/market-intel/ai-boom`
      case 'influencers': return `${API}/api/market-intel/influencers`
      case 'geopolitics': return `${API}/api/market-intel/geopolitics`
      case 'big_money':   return `${API}/api/market-intel/big-money`
      case 'sec_filings': return `${API}/api/market-intel/sec-filings`
      case 'tech':        return `${API}/api/market-intel/tech-breakthroughs`
      case 'resources':   return `${API}/api/market-intel/resources`
      case 'synthesis':   return `${API}/api/market-intel/synthesis?focus=general`
    }
  }, [tab])

  const load = async () => {
    setLoading(true); setErr(null)
    try {
      const r = await fetch(endpoint, { headers: { 'Cache-Control': 'no-cache' } })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
    } catch (e: any) {
      const msg = e?.message || 'Request failed'
      setErr(msg === 'Failed to fetch'
        ? `Cannot reach the backend at ${API} — check that it is running and that you are still signed in`
        : msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() /* eslint-disable-next-line */ }, [endpoint])
  useEffect(() => {
    if (!autoRefresh) return
    const interval = tab === 'synthesis' ? 120_000 : 60_000
    const id = setInterval(load, interval)
    return () => clearInterval(id)
    // eslint-disable-next-line
  }, [autoRefresh, endpoint, tab])

  return (
    <div className="p-6">
      <header className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Brain className="text-indigo-500" /> Market Intelligence
          </h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Influencers · Geopolitics · Big-money flow · Tech · AI Boom · Resources — fused with the local LLM
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(v => !v)}
            className={`text-xs px-3 py-2 rounded-lg border ${autoRefresh ? 'bg-emerald-50 border-emerald-300 text-emerald-700' : ''}`}
          >
            {autoRefresh ? 'Auto-refresh: ON' : 'Auto-refresh: OFF'}
          </button>
          <button onClick={load} className="text-xs px-3 py-2 rounded-lg bg-indigo-600 text-white flex items-center gap-1">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </header>

      {/* Tab strip */}
      <div className="flex flex-wrap gap-2 mb-5">
        {TABS.map(t => {
          const Icon = t.icon
          const active = tab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 text-sm px-3 py-2 rounded-xl border transition ${
                active
                  ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white border-transparent shadow'
                  : 'hover:bg-slate-50'
              }`}
              style={!active ? { borderColor: 'var(--border-color)', color: 'var(--text-secondary)' } : {}}
            >
              <Icon size={14} />
              {t.label}
            </button>
          )
        })}
      </div>

      {err && (
        <div className="rounded-xl border-2 border-rose-300 bg-rose-50 p-3 text-sm text-rose-700 mb-4 flex items-center gap-2">
          <AlertTriangle size={16} /> {err} — endpoint: <code className="text-xs">{endpoint}</code>
        </div>
      )}

      {loading && !data && (
        <div className="text-sm" style={{ color: 'var(--text-muted)' }}>Loading…</div>
      )}

      {data && tab === 'overview'    && <OverviewTab d={data} />}
      {data && tab === 'ai_boom'     && <AIBoomTab d={data} />}
      {data && tab === 'influencers' && <InfluencersTab d={data} />}
      {data && tab === 'geopolitics' && <GeopoliticsTab d={data} />}
      {data && tab === 'big_money'   && <BigMoneyTab d={data} />}
      {data && tab === 'sec_filings' && <SecFilingsTab d={data} />}
      {data && tab === 'tech'        && <FeedListTab d={data} title="Tech & Medical Breakthroughs" />}
      {data && tab === 'resources'   && <FeedListTab d={data} title="Energy / Minerals / Rare-Earth" />}
      {data && tab === 'synthesis'   && <SynthesisTab d={data} />}
    </div>
  )
}

/* ── Tab views ──────────────────────────────────────────────────────────── */

function OverviewTab({ d }: { d: any }) {
  const ov = d.market_overview || {}
  const ai = d.ai_boom || {}
  const geo = d.geopolitics || {}
  const big = d.big_money_flow?.summary || {}
  const inf = d.influencers?.influencers || []

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-4">
        <Card
          title="Market Pulse"
          right={<Pill label={ai.regime || 'unknown'} tone={regimeTone(ai.regime)} />}
        >
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(ov.indices || {}).map(([k, v]: any) => (
              <div key={k} className="p-3 rounded-xl border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{k.replace('^', '')}</div>
                <div className="text-lg font-semibold">{v?.price ?? '—'}</div>
                <div className="text-xs" style={{ color: pctColor(v?.chg_1d_pct) }}>{fmtPct(v?.chg_1d_pct)} 1d · {fmtPct(v?.chg_30d_pct)} 30d</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 mt-3">
            {Object.entries(ov.macro || {}).map(([k, v]: any) => (
              <div key={k} className="p-2 rounded-lg border text-xs" style={{ borderColor: 'var(--border-color)' }}>
                <div className="uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{k}</div>
                <div className="font-semibold">{v?.price ?? '—'}</div>
                <div style={{ color: pctColor(v?.chg_1d_pct) }}>{fmtPct(v?.chg_1d_pct)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Sector Rotation (30d)">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {Object.entries(ov.sectors || {}).map(([name, v]: any) => (
              <div key={name} className="p-2 rounded-lg border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{name}</div>
                <div className="text-sm font-semibold" style={{ color: pctColor(v?.chg_30d_pct) }}>{fmtPct(v?.chg_30d_pct)}</div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Top Influencer Pulse">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {inf.slice(0, 8).map((p: any) => (
              <div key={p.handle} className="p-2 rounded-lg border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="flex items-center justify-between">
                  <div className="text-sm font-medium">{p.name}</div>
                  <Pill label={p.signal} tone={p.signal === 'bullish' ? 'pos' : p.signal === 'bearish' ? 'neg' : 'neutral'} />
                </div>
                <div className="text-xs truncate mt-1" style={{ color: 'var(--text-muted)' }}>
                  {p.items?.[0]?.title || '—'}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="AI Boom Index" right={<Pill label={ai.regime || '—'} tone={regimeTone(ai.regime)} />}>
          <div className="text-3xl font-bold">{ai.ai_boom_score ?? '—'}</div>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            30d {fmtPct(ai.overall_avg_30d_pct)} · 90d {fmtPct(ai.overall_avg_90d_pct)}
          </div>
          <div className="mt-3 text-xs">
            <div className="font-semibold mb-1">Leaders</div>
            {(ai.leaders || []).slice(0, 5).map((l: any) => (
              <div key={l.symbol} className="flex justify-between"><span>{l.symbol}</span><span style={{ color: pctColor(l.chg_30d_pct) }}>{fmtPct(l.chg_30d_pct)}</span></div>
            ))}
          </div>
        </Card>

        <Card title="Geopolitics" right={<Pill label={geo.risk_level || 'unknown'} tone={geo.risk_level === 'elevated' ? 'neg' : geo.risk_level === 'moderate' ? 'warn' : 'pos'} />}>
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            {(geo.headline_count || 0)} headlines · avg sentiment {geo.avg_sentiment ?? '—'}
          </div>
          <ul className="text-xs mt-2 space-y-1 list-disc list-inside">
            {(geo.items || []).slice(0, 4).map((it: any, i: number) => (
              <li key={i} className="truncate"><a href={it.url} target="_blank" rel="noreferrer" className="hover:underline">{it.title}</a></li>
            ))}
          </ul>
        </Card>

        <Card title="Big Money (24h)">
          <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
            <div>Insider (Form 4): <b>{big.insider_filings_24h ?? 0}</b></div>
            <div>Institutional (13F): <b>{big.institutional_filings_24h ?? 0}</b></div>
            <div>Activist (13D/13G): <b>{big.activist_filings_24h ?? 0}</b></div>
          </div>
        </Card>
      </div>
    </div>
  )
}

function AIBoomTab({ d }: { d: any }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card title="Composite Score">
          <div className="text-4xl font-bold">{d.ai_boom_score ?? '—'}</div>
          <Pill label={d.regime || '—'} tone={regimeTone(d.regime)} />
        </Card>
        <Card title="Avg 30d">
          <div className="text-3xl font-semibold" style={{ color: pctColor(d.overall_avg_30d_pct) }}>{fmtPct(d.overall_avg_30d_pct)}</div>
        </Card>
        <Card title="Avg 90d">
          <div className="text-3xl font-semibold" style={{ color: pctColor(d.overall_avg_90d_pct) }}>{fmtPct(d.overall_avg_90d_pct)}</div>
        </Card>
      </div>

      <Card title="Categories">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {Object.entries(d.categories || {}).map(([cat, info]: any) => (
            <div key={cat} className="p-3 rounded-xl border" style={{ borderColor: 'var(--border-color)' }}>
              <div className="flex items-center justify-between mb-1">
                <div className="font-semibold capitalize">{cat.replace(/_/g, ' ')}</div>
                <Pill label={`30d ${fmtPct(info.avg_30d_pct)}`} tone={info.avg_30d_pct >= 0 ? 'pos' : 'neg'} />
              </div>
              <div className="grid grid-cols-3 gap-1 mt-1">
                {(info.tickers || []).map((t: any) => (
                  <div key={t.symbol} className="p-1 rounded text-xs flex justify-between" style={{ background: 'var(--bg-tertiary)' }}>
                    <span className="font-mono">{t.symbol}</span>
                    <span style={{ color: pctColor(t.chg_30d_pct) }}>{fmtPct(t.chg_30d_pct)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Leaders (30d)" right={<TrendingUp size={14} className="text-emerald-600" />}>
          <ul className="text-sm">
            {(d.leaders || []).map((t: any) => (
              <li key={t.symbol} className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-color)' }}>
                <span className="font-mono">{t.symbol}</span>
                <span style={{ color: pctColor(t.chg_30d_pct) }}>{fmtPct(t.chg_30d_pct)}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Laggards (30d)" right={<TrendingDown size={14} className="text-rose-600" />}>
          <ul className="text-sm">
            {(d.laggards || []).map((t: any) => (
              <li key={t.symbol} className="flex justify-between py-1 border-b" style={{ borderColor: 'var(--border-color)' }}>
                <span className="font-mono">{t.symbol}</span>
                <span style={{ color: pctColor(t.chg_30d_pct) }}>{fmtPct(t.chg_30d_pct)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}

function InfluencersTab({ d }: { d: any }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {(d.influencers || []).map((p: any) => (
        <Card
          key={p.handle}
          title={`${p.name}  ·  @${p.handle}`}
          right={<Pill label={p.signal} tone={p.signal === 'bullish' ? 'pos' : p.signal === 'bearish' ? 'neg' : 'neutral'} />}
        >
          <div className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
            {p.category} · avg sentiment {p.avg_sentiment}
          </div>
          <ul className="text-sm space-y-1">
            {(p.items || []).slice(0, 5).map((it: any, i: number) => (
              <li key={i} className="flex items-start gap-1">
                <ChevronRight size={14} className="mt-1 shrink-0" />
                <a href={it.url} target="_blank" rel="noreferrer" className="hover:underline truncate">{it.title}</a>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}

function GeopoliticsTab({ d }: { d: any }) {
  return (
    <Card
      title={`${d.headline_count || 0} headlines · risk: ${d.risk_level}`}
      right={<Pill label={d.risk_level} tone={d.risk_level === 'elevated' ? 'neg' : d.risk_level === 'moderate' ? 'warn' : 'pos'} />}
    >
      <ul className="space-y-2 text-sm">
        {(d.items || []).map((it: any, i: number) => (
          <li key={i} className="p-2 rounded-lg border flex items-start justify-between gap-3" style={{ borderColor: 'var(--border-color)' }}>
            <div className="flex-1">
              <a href={it.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{it.title}</a>
              <div className="text-xs flex gap-2" style={{ color: 'var(--text-muted)' }}>
                <span>{it.source}</span>
                {it.is_conflict && <Pill label="conflict" tone="neg" />}
                <Clock size={12} className="mt-0.5" /><span>{it.published?.slice(0, 16)}</span>
              </div>
            </div>
            <ExternalLink size={14} className="opacity-60 shrink-0" />
          </li>
        ))}
      </ul>
    </Card>
  )
}

function BigMoneyTab({ d }: { d: any }) {
  const groups = [
    { title: 'Insider (Form 4)',    items: d.insider_form4 || [] },
    { title: 'Institutional (13F)', items: d.institutional_13f || [] },
    { title: 'Activist (13D/13G)',  items: d.activist_13d_13g || [] },
  ]
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {groups.map(g => (
        <Card key={g.title} title={`${g.title} · ${g.items.length}`}>
          <ul className="text-sm space-y-1 max-h-[480px] overflow-auto">
            {g.items.map((it: any, i: number) => (
              <li key={i} className="border-b py-1" style={{ borderColor: 'var(--border-color)' }}>
                <a href={it.link} target="_blank" rel="noreferrer" className="hover:underline">{it.title}</a>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{it.published?.slice(0, 16)}</div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}

function FeedListTab({ d, title }: { d: any; title: string }) {
  return (
    <Card title={`${title} · ${d.count || (d.items || []).length} items`}>
      <ul className="space-y-2">
        {(d.items || []).map((it: any, i: number) => (
          <li key={i} className="p-2 rounded-lg border flex items-start gap-3" style={{ borderColor: 'var(--border-color)' }}>
            <div className="flex-1">
              <a href={it.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{it.title}</a>
              <div className="text-xs flex gap-2 mt-1" style={{ color: 'var(--text-muted)' }}>
                <span>{it.source}</span>
                <Clock size={12} className="mt-0.5" /><span>{it.published?.slice(0, 16)}</span>
                <Pill
                  label={it.sentiment > 0.2 ? 'pos' : it.sentiment < -0.2 ? 'neg' : 'neu'}
                  tone={it.sentiment > 0.2 ? 'pos' : it.sentiment < -0.2 ? 'neg' : 'neutral'}
                />
              </div>
            </div>
            <ExternalLink size={14} className="opacity-60 shrink-0" />
          </li>
        ))}
      </ul>
    </Card>
  )
}

function SecFilingsTab({ d }: { d: any }) {
  const byForm = d.by_form || {}
  const totals = d.totals || {}
  const formTypes = Object.keys(byForm).filter(k => (byForm[k] || []).length > 0)
  const formColors: Record<string, string> = {
    '4': '#3b82f6', '13F-HR': '#8b5cf6', '8-K': '#f59e0b', '10-K': '#16a34a',
    '10-Q': '#06b6d4', 'S-1': '#ec4899', 'DEF 14A': '#6366f1', 'SC 13D': '#dc2626', 'SC 13G': '#ea580c',
  }
  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex flex-wrap gap-3">
        {Object.entries(totals).map(([form, count]) => (
          <div key={form} className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold border" style={{ borderColor: formColors[form] || 'var(--border-color)', color: formColors[form] || 'var(--text-secondary)' }}>
            <FileText size={12} />
            {form}: {String(count)}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {formTypes.map(ft => (
          <Card key={ft} title={`${ft} Filings · ${(byForm[ft] || []).length}`}>
            <ul className="text-sm space-y-1 max-h-[400px] overflow-auto">
              {(byForm[ft] || []).map((it: any, i: number) => (
                <li key={i} className="border-b py-1.5" style={{ borderColor: 'var(--border-color)' }}>
                  <a href={it.link} target="_blank" rel="noreferrer" className="hover:underline flex items-start gap-1">
                    <FileText size={12} className="mt-1 shrink-0" style={{ color: formColors[ft] || 'var(--text-muted)' }} />
                    <span>{it.title}</span>
                  </a>
                  <div className="text-xs flex items-center gap-1 ml-4" style={{ color: 'var(--text-muted)' }}>
                    <Clock size={10} /> {it.published?.slice(0, 16)}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
      {formTypes.length === 0 && (
        <Card title="No Recent Filings">
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>SEC EDGAR returned no filings for this period. Try refreshing.</p>
        </Card>
      )}
    </div>
  )
}

function SynthesisTab({ d }: { d: any }) {
  const b = d.brief || d.fallback_brief || {}
  return (
    <div className="space-y-4">
      <Card
        title="AI Brief"
        right={
          <LlmBadge
            llm={{
              model: d.model || 'fallback',
              provider: 'ollama (local)',
              private: true,
              available: !d.llm_error,
            }}
            sources={['Yahoo Finance', 'SEC EDGAR', 'Reuters', 'Reddit', 'Hacker News']}
            compact
          />
        }
      >
        <div className="text-lg font-semibold mb-1">{b.one_line_summary || '—'}</div>
        <Pill label={b.market_regime || 'mixed'} tone={b.market_regime === 'risk-on' ? 'pos' : b.market_regime === 'risk-off' ? 'neg' : 'neutral'} />
        {d.llm_error && <div className="text-xs text-amber-700 mt-2">LLM unavailable: {d.llm_error}. Showing fallback.</div>}
      </Card>

      {b.top_3_themes && (
        <Card title="Top Themes">
          <ul className="space-y-2">
            {b.top_3_themes.map((t: any, i: number) => (
              <li key={i} className="p-2 rounded-lg border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="font-semibold">{t.theme}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{t.why_it_matters}</div>
                {t.evidence && <div className="text-xs mt-1">Evidence: {Array.isArray(t.evidence) ? t.evidence.join(' · ') : t.evidence}</div>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Bullish Setups">
          <ul className="space-y-2 text-sm">
            {(b.bullish_setups || []).map((s: any, i: number) => (
              <li key={i} className="p-2 rounded-lg border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="font-mono font-bold">{s.symbol}</div>
                <div className="text-xs">{s.thesis}</div>
                {s.catalysts && <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Catalysts: {Array.isArray(s.catalysts) ? s.catalysts.join(', ') : s.catalysts}</div>}
                {s.risk && <div className="text-xs text-rose-600">Risk: {s.risk}</div>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Bearish Setups">
          <ul className="space-y-2 text-sm">
            {(b.bearish_setups || []).map((s: any, i: number) => (
              <li key={i} className="p-2 rounded-lg border" style={{ borderColor: 'var(--border-color)' }}>
                <div className="font-mono font-bold">{s.symbol}</div>
                <div className="text-xs">{s.thesis}</div>
                {s.catalysts && <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Catalysts: {Array.isArray(s.catalysts) ? s.catalysts.join(', ') : s.catalysts}</div>}
                {s.risk && <div className="text-xs text-rose-600">Risk: {s.risk}</div>}
              </li>
            ))}
          </ul>
        </Card>
      </div>

      {b.watch_today && (
        <Card title="Watch Today">
          <div className="flex flex-wrap gap-2">
            {b.watch_today.map((s: string) => (
              <span key={s} className="px-2 py-1 rounded-lg bg-indigo-100 text-indigo-700 font-mono text-sm">{s}</span>
            ))}
          </div>
        </Card>
      )}

      {b.risk_warnings && (
        <Card title="Risk Warnings" right={<AlertTriangle size={14} className="text-amber-600" />}>
          <ul className="text-sm list-disc list-inside">
            {b.risk_warnings.map((w: string, i: number) => <li key={i}>{w}</li>)}
          </ul>
        </Card>
      )}
    </div>
  )
}
