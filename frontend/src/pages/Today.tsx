import LifeAdminBoard from '../components/LifeAdminBoard'
import { useCallback, useEffect, useState } from 'react'
import { Check, X, Undo2, Volume2, RefreshCw, Mail, Pill, Timer, Leaf, ShoppingCart, CalendarClock, Bell, ExternalLink, Sparkles, ChevronRight } from 'lucide-react'
import { nexusApi, careApi, Brief, NexusEvent } from '../api/nexus'
import { useAviraVoice } from '../hooks/useAviraVoice'

const PRIO: Record<string, string> = { high: '#ef4444', medium: '#f59e0b', low: '#94a3b8' }
const CAT_ICON: Record<string, string> = { bill: '💳', appointment: '🩺', school: '🎒', delivery: '📦', renewal: '🔁', travel: '✈️', refund: '💵', action: '⚠️' }

export default function Today() {
  const [brief, setBrief] = useState<Brief | null>(null)
  const [pending, setPending] = useState<NexusEvent[]>([])
  const [history, setHistory] = useState<NexusEvent[]>([])
  const [prompts, setPrompts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const voice = useAviraVoice()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [b, p, h, pr] = await Promise.all([nexusApi.brief(), nexusApi.events('proposed'), nexusApi.events(), careApi.dueNow()])
      setBrief(b); setPending(p); setHistory(h.filter(e => e.status !== 'proposed').slice(0, 12)); setPrompts(pr)
    } catch { /* Independent household board remains available when briefing fails. */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const act = async (fn: () => Promise<any>) => { await fn(); await load() }

  const answerPrompt = async (p: any, yes: boolean) => {
    if (p.type === 'med') await careApi.logMed(p.id, yes)
    else if (p.type === 'fasting') await careApi.logFast(yes)
    else if (p.type === 'checkin') await careApi.checkin(p.kind, yes ? 'yes' : 'no')
    await load()
  }

  if (loading && !brief) return <div className="p-8 text-sm" style={{ color: 'var(--text-muted)' }}>Pulling your day together…</div>
  if (!brief) return <div className="p-6"><LifeAdminBoard /></div>

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Hero brief */}
      <div className="rounded-3xl p-6 text-white relative overflow-hidden" style={{ background: 'linear-gradient(135deg,#312e81,#4f46e5 55%,#7c3aed)' }}>
        <div className="absolute -right-10 -top-10 w-56 h-56 rounded-full opacity-20" style={{ background: '#c4b5fd' }} />
        <div className="flex items-start justify-between gap-4 relative">
          <div>
            <p className="text-sm text-white/70">{new Date(brief.date).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</p>
            <h1 className="text-2xl font-bold mt-1">{brief.greeting}</h1>
            <p className="mt-2 text-white/90 max-w-2xl">{brief.spoken.replace(brief.greeting, '').trim()}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <button onClick={() => voice.speak(brief.spoken)} className="p-3 rounded-2xl bg-white/15 hover:bg-white/25" title="Have Avira read it"><Volume2 size={18} /></button>
            <button onClick={load} className="p-3 rounded-2xl bg-white/15 hover:bg-white/25" title="Refresh"><RefreshCw size={18} className={loading ? 'animate-spin' : ''} /></button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-5 relative">
          <Stat icon={<CalendarClock size={16} />} label="Today" value={`${brief.events.length} events`} />
          <Stat icon={<Pill size={16} />} label="Meds due" value={`${brief.medications.filter(m => !m.taken_today).length}`} />
          <Stat icon={<Mail size={16} />} label="Inbox radar" value={`${brief.radar.length} open`} />
          <Stat icon={<ShoppingCart size={16} />} label="Shopping" value={`${brief.shopping_open} items`} />
          <Stat icon={<Leaf size={16} />} label="Spent (mo)" value={`$${brief.month_spend.toLocaleString(undefined, { maximumFractionDigits: 0 })}`} />
        </div>
      </div>

      <LifeAdminBoard />

      {/* One-tap check-ins */}
      {prompts.length > 0 && (
        <Section title="Quick check-ins" icon={<Timer size={18} />} hint="Yes or no. That's it.">
          <div className="grid md:grid-cols-2 gap-3">
            {prompts.map((p, i) => (
              <div key={i} className="flex items-center justify-between gap-3 rounded-2xl p-4" style={{ background: 'var(--bg-tertiary)' }}>
                <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.title}</p>
                <div className="flex gap-2 shrink-0">
                  <button onClick={() => answerPrompt(p, true)} className="px-3 py-1.5 rounded-xl text-white text-sm bg-emerald-600 hover:bg-emerald-700 flex items-center gap-1"><Check size={14} /> Yes</button>
                  <button onClick={() => answerPrompt(p, false)} className="px-3 py-1.5 rounded-xl text-sm flex items-center gap-1" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}><X size={14} /> No</button>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Pending confirmations */}
      {pending.length > 0 && (
        <Section title={`Waiting for your OK (${pending.length})`} icon={<Sparkles size={18} />} hint="Avira found these; nothing is written until you say so.">
          <div className="space-y-3">
            {pending.map(ev => (
              <div key={ev.id} className="rounded-2xl p-4" style={{ background: 'var(--bg-tertiary)' }}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{ev.source} · {ev.type}</p>
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{ev.summary}</p>
                    <ul className="mt-2 space-y-1">
                      {ev.actions.map((a, i) => (
                        <li key={i} className="text-xs flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
                          <ChevronRight size={12} /> <span className="font-semibold" style={{ color: 'var(--accent-primary)' }}>{a.domain}.{a.action}</span>
                          <span className="truncate">{JSON.stringify(a.params).slice(0, 110)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button onClick={() => act(() => nexusApi.confirm(ev.id))} className="px-3 py-1.5 rounded-xl text-white text-sm bg-emerald-600 hover:bg-emerald-700 flex items-center gap-1"><Check size={14} /> Do it</button>
                    <button onClick={() => act(() => nexusApi.reject(ev.id))} className="px-3 py-1.5 rounded-xl text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}>Skip</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Radar */}
        <Section title="Life Admin Radar" icon={<Mail size={18} />} hint="From your inbox — metadata only, opens in your mail app." action={<a href="#radar" className="text-xs font-medium" style={{ color: 'var(--accent-primary)' }}>Manage →</a>}>
          {brief.radar.length === 0 ? <Empty text="Nothing urgent in the inbox. Lovely." /> : (
            <ul className="space-y-2">
              {brief.radar.map(s => (
                <li key={s.id} className="flex items-center gap-3 rounded-xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                  <span className="text-lg">{CAT_ICON[s.category] || '✉️'}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{s.subject}</p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      {s.category}{s.amount ? ` · $${s.amount.toFixed(2)}` : ''}{s.due_date ? ` · due ${new Date(s.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}` : ''}
                    </p>
                  </div>
                  <span className="w-2 h-2 rounded-full" style={{ background: PRIO[s.priority] }} />
                  {s.deep_link && <a href={s.deep_link} target="_blank" rel="noreferrer" className="p-1.5 rounded-lg" style={{ color: 'var(--accent-primary)' }} title="Open in mail"><ExternalLink size={14} /></a>}
                </li>
              ))}
            </ul>
          )}
        </Section>

        {/* Today's schedule + reminders */}
        <Section title="Schedule & reminders" icon={<Bell size={18} />}>
          {brief.events.length + brief.reminders.length === 0 ? <Empty text="Clear runway today." /> : (
            <ul className="space-y-2">
              {brief.events.map(e => (
                <li key={e.id} className="flex items-center gap-3 rounded-xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                  <span className="text-xs font-semibold w-16" style={{ color: 'var(--accent-primary)' }}>{new Date(e.at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</span>
                  <div className="min-w-0"><p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{e.title}</p>{e.location && <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{e.location}</p>}</div>
                </li>
              ))}
              {brief.reminders.map(r => (
                <li key={r.id} className="flex items-center gap-3 rounded-xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                  <span className="text-xs font-semibold w-16" style={{ color: '#f59e0b' }}>{new Date(r.at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</span>
                  <p className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>🔔 {r.title}</p>
                </li>
              ))}
            </ul>
          )}
          {brief.expiring.length > 0 && (
            <p className="text-xs mt-3 rounded-xl p-2" style={{ background: '#f59e0b20', color: '#b45309' }}>Use soon: {brief.expiring.map(p => p.name).join(', ')}</p>
          )}
        </Section>
      </div>

      {/* History */}
      <Section title="What Avira did" icon={<Undo2 size={18} />} hint="Everything is reversible.">
        {history.length === 0 ? <Empty text="No actions yet. Tap the orb and say something." /> : (
          <ul className="divide-y" style={{ borderColor: 'var(--border-color)' }}>
            {history.map(ev => (
              <li key={ev.id} className="py-3 flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full ${ev.status === 'applied' ? 'bg-emerald-500' : ev.status === 'undone' ? 'bg-gray-400' : 'bg-rose-400'}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm truncate" style={{ color: 'var(--text-primary)' }}>{ev.summary}</p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{ev.actions.length} action{ev.actions.length !== 1 ? 's' : ''} · {ev.source} · {ev.created_at ? new Date(ev.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}{ev.auto_applied ? ' · auto' : ''}</p>
                </div>
                {ev.status === 'applied' && ev.actions.some(a => a.status === 'applied') && (
                  <button onClick={() => act(() => nexusApi.undo(ev.id))} className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}><Undo2 size={12} /> Undo</button>
                )}
                {ev.status === 'undone' && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>undone</span>}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  )
}

function Stat({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white/10 p-3">
      <div className="flex items-center gap-2 text-white/70 text-xs">{icon}{label}</div>
      <p className="text-lg font-semibold mt-1">{value}</p>
    </div>
  )
}

export function Section({ title, icon, hint, action, children }: { title: string; icon?: React.ReactNode; hint?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-3xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h2 className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>{icon}{title}</h2>
          {hint && <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{hint}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

export function Empty({ text }: { text: string }) {
  return <p className="text-sm py-6 text-center" style={{ color: 'var(--text-muted)' }}>{text}</p>
}
