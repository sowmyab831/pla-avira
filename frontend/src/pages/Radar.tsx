import { useCallback, useEffect, useState } from 'react'
import { Mail, Plus, RefreshCw, Trash2, ExternalLink, Check, Clock, X, Copy, ShieldCheck, Sparkles } from 'lucide-react'
import { radarApi, RadarSignal } from '../api/nexus'
import { Section, Empty } from './Today'

const CATS = ['bill', 'appointment', 'school', 'action', 'renewal', 'travel', 'refund', 'delivery']
const CAT_ICON: Record<string, string> = { bill: '💳', appointment: '🩺', school: '🎒', delivery: '📦', renewal: '🔁', travel: '✈️', refund: '💵', action: '⚠️', other: '✉️' }
const PRIO: Record<string, string> = { high: '#ef4444', medium: '#f59e0b', low: '#94a3b8' }

const DEMO = [
  { from: 'billing@duke-energy.com', subject: 'Your Duke Energy bill is ready: $142.17 due Sep 15', snippet: 'Pay by 09/15/2026 to avoid a late fee.' },
  { from: 'noreply@patelpediatrics.com', subject: 'Appointment confirmation - Dr. Patel, Sept 10 at 2:30 PM', snippet: 'Bring your insurance card.' },
  { from: 'office@lincolnelementary.org', subject: 'Permission slip needed: field trip Friday', snippet: 'Please sign and return the form by Thursday.' },
  { from: 'membership@costco.com', subject: 'Your Costco membership expires on 10/01/2026', snippet: 'Renew today to keep your benefits.' },
  { from: 'deals@retailer.com', subject: '50% off everything this weekend', snippet: 'Unsubscribe' },
]

export default function Radar() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [providers, setProviders] = useState<Record<string, { host: string; help: string }>>({})
  const [signals, setSignals] = useState<RadarSignal[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [filter, setFilter] = useState<string>('all')
  const [status, setStatus] = useState<'open' | 'done' | 'all'>('open')
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ provider: 'gmail', email: '', app_password: '', imap_host: '' })
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    const [a, p, s] = await Promise.all([radarApi.accounts(), radarApi.providers(), radarApi.signals(status)])
    setAccounts(a); setProviders(p); setSignals(s.signals); setCounts(s.counts)
  }, [status])
  useEffect(() => { load() }, [load])

  const addAccount = async () => {
    setBusy(true); setMsg(null)
    try {
      await radarApi.addAccount({ ...form, imap_host: form.imap_host || undefined })
      setAdding(false); setForm({ provider: 'gmail', email: '', app_password: '', imap_host: '' })
      setMsg('Inbox connected. Syncing…')
      await radarApi.sync(14)
      await load()
      setMsg('Synced.')
    } catch (e: any) {
      const d = e?.response?.data?.detail
      setMsg(typeof d === 'string' ? d : d?.error || 'Could not connect.')
    } finally { setBusy(false) }
  }

  const sync = async () => {
    setBusy(true); setMsg(null)
    try { const r = await radarApi.sync(14); setMsg(r.report.map((x: any) => x.error ? `${x.account}: ${x.error}` : `${x.account}: ${x.scanned} scanned, ${x.new_signals} new`).join(' · ')); await load() }
    catch (e: any) { setMsg(e?.response?.data?.detail?.error || e?.response?.data?.detail || 'Sync failed') }
    finally { setBusy(false) }
  }

  const demo = async () => { setBusy(true); try { await radarApi.demo(DEMO); await load(); setMsg('Loaded 5 sample emails (1 promo filtered out).') } finally { setBusy(false) } }

  const update = async (id: string, st: string) => { await radarApi.update(id, st); await load() }

  const visible = signals.filter(s => filter === 'all' || s.category === filter)

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><Mail /> Life Admin Radar</h1>
          <p className="text-sm mt-1 flex items-center gap-1" style={{ color: 'var(--text-muted)' }}><ShieldCheck size={14} /> Header-only scanning. Bodies never stored; PII masked; each item deep-links back to your mail app.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={sync} disabled={busy || accounts.length === 0} className="px-3 py-2 rounded-xl text-sm flex items-center gap-1 disabled:opacity-40" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}><RefreshCw size={14} className={busy ? 'animate-spin' : ''} /> Sync</button>
          <button onClick={() => setAdding(true)} className="px-3 py-2 rounded-xl text-sm text-white flex items-center gap-1" style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}><Plus size={14} /> Connect inbox</button>
        </div>
      </div>
      {msg && <p className="text-sm rounded-xl px-4 py-2" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{msg}</p>}

      {adding && (
        <Section title="Connect an inbox" hint="Uses an app password over IMAP — no Google OAuth review, nothing shared with third parties.">
          <div className="grid md:grid-cols-2 gap-3">
            <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className="px-3 py-2 rounded-xl" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
              {Object.keys(providers).map(p => <option key={p} value={p}>{p}</option>)}
            </select>
            <input placeholder="you@gmail.com" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} className="px-3 py-2 rounded-xl" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
            <input type="password" placeholder="App password (16 chars)" value={form.app_password} onChange={e => setForm({ ...form, app_password: e.target.value })} className="px-3 py-2 rounded-xl" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
            {form.provider === 'custom' && <input placeholder="imap.example.com" value={form.imap_host} onChange={e => setForm({ ...form, imap_host: e.target.value })} className="px-3 py-2 rounded-xl" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />}
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>Where to get it: {providers[form.provider]?.help}</p>
          <div className="flex gap-2 mt-3">
            <button onClick={addAccount} disabled={busy || !form.email || !form.app_password} className="px-4 py-2 rounded-xl text-white text-sm disabled:opacity-40" style={{ background: '#4f46e5' }}>{busy ? 'Connecting…' : 'Connect & scan'}</button>
            <button onClick={() => setAdding(false)} className="px-4 py-2 rounded-xl text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>Cancel</button>
          </div>
        </Section>
      )}

      <div className="grid lg:grid-cols-[1fr_3fr] gap-6">
        <div className="space-y-4">
          <Section title="Inboxes">
            {accounts.length === 0 ? (
              <div className="text-center py-4">
                <Empty text="No inbox connected yet." />
                <button onClick={demo} disabled={busy} className="text-xs px-3 py-2 rounded-xl flex items-center gap-1 mx-auto" style={{ background: 'var(--bg-tertiary)', color: 'var(--accent-primary)' }}><Sparkles size={12} /> Try with sample emails</button>
              </div>
            ) : accounts.map(a => (
              <div key={a.id} className="flex items-center justify-between py-2 text-sm">
                <div><p className="font-medium" style={{ color: 'var(--text-primary)' }}>{a.email}</p><p className="text-xs" style={{ color: 'var(--text-muted)' }}>{a.provider} · {a.last_sync ? `synced ${new Date(a.last_sync).toLocaleString()}` : 'never synced'}</p></div>
                <button onClick={async () => { await radarApi.removeAccount(a.id); await load() }} className="p-1.5 rounded-lg text-rose-500"><Trash2 size={14} /></button>
              </div>
            ))}
          </Section>
          <Section title="Categories">
            <ul className="space-y-1">
              <li><button onClick={() => setFilter('all')} className={`w-full text-left text-sm px-3 py-1.5 rounded-lg ${filter === 'all' ? 'font-semibold' : ''}`} style={{ color: 'var(--text-primary)', background: filter === 'all' ? 'var(--bg-tertiary)' : 'transparent' }}>All <span className="float-right" style={{ color: 'var(--text-muted)' }}>{signals.length}</span></button></li>
              {CATS.map(c => (
                <li key={c}><button onClick={() => setFilter(c)} className={`w-full text-left text-sm px-3 py-1.5 rounded-lg ${filter === c ? 'font-semibold' : ''}`} style={{ color: 'var(--text-primary)', background: filter === c ? 'var(--bg-tertiary)' : 'transparent' }}>{CAT_ICON[c]} {c} <span className="float-right" style={{ color: 'var(--text-muted)' }}>{counts[c] || 0}</span></button></li>
              ))}
            </ul>
          </Section>
        </div>

        <Section title="Signals" action={
          <div className="flex gap-1 text-xs">
            {(['open', 'done', 'all'] as const).map(s => <button key={s} onClick={() => setStatus(s)} className={`px-2.5 py-1 rounded-lg ${status === s ? 'text-white' : ''}`} style={{ background: status === s ? '#4f46e5' : 'var(--bg-tertiary)', color: status === s ? '#fff' : 'var(--text-secondary)' }}>{s}</button>)}
          </div>}>
          {visible.length === 0 ? <Empty text="Nothing here. Inbox zero, radar zero." /> : (
            <ul className="space-y-2">
              {visible.map(s => (
                <li key={s.id} className="rounded-2xl p-4" style={{ background: 'var(--bg-tertiary)' }}>
                  <div className="flex items-start gap-3">
                    <span className="text-xl">{CAT_ICON[s.category] || '✉️'}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: PRIO[s.priority] }} />
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{s.subject}</p>
                      </div>
                      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                        {s.sender_name || s.sender_domain}{s.amount ? ` · $${s.amount.toFixed(2)}` : ''}{s.due_date ? ` · due ${new Date(s.due_date).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}` : ''}{s.nexus_event_id ? ' · added to Nexus' : ''}
                      </p>
                      {s.suggested_reply && (
                        <div className="mt-2 text-xs rounded-lg p-2 flex items-start gap-2" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>
                          <span className="flex-1">Suggested reply: “{s.suggested_reply}”</span>
                          <button onClick={() => navigator.clipboard.writeText(s.suggested_reply!)} className="p-1 rounded" title="Copy"><Copy size={12} /></button>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-1 shrink-0">
                      {s.deep_link && <a href={s.deep_link} target="_blank" rel="noreferrer" className="p-2 rounded-lg" style={{ background: 'var(--bg-secondary)', color: 'var(--accent-primary)' }} title="Open in mail"><ExternalLink size={14} /></a>}
                      {s.status === 'open' && <>
                        <button onClick={() => update(s.id, 'done')} className="p-2 rounded-lg text-emerald-600" style={{ background: 'var(--bg-secondary)' }} title="Done"><Check size={14} /></button>
                        <button onClick={() => update(s.id, 'snoozed')} className="p-2 rounded-lg" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }} title="Snooze 3 days"><Clock size={14} /></button>
                        <button onClick={() => update(s.id, 'dismissed')} className="p-2 rounded-lg" style={{ background: 'var(--bg-secondary)', color: 'var(--text-muted)' }} title="Dismiss"><X size={14} /></button>
                      </>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  )
}
