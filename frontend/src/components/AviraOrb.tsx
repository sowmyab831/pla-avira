import { useCallback, useEffect, useRef, useState } from 'react'
import { Mic, MicOff, Send, X, Check, Undo2, Volume2, VolumeX, Sparkles, ShieldCheck } from 'lucide-react'
import { nexusApi, IngestResult, NexusEvent, NexusAction } from '../api/nexus'
import { useAviraVoice } from '../hooks/useAviraVoice'

interface Turn {
  role: 'user' | 'avira'
  text: string
  event?: NexusEvent | null
  actions?: NexusAction[]
  ts: number
}

const DOMAIN_LABEL: Record<string, string> = {
  shopping: 'Shopping', pantry: 'Pantry', reminder: 'Reminder', calendar: 'Calendar', tasks: 'Task',
  health: 'Health', family: 'Family', finance: 'Money',
}

function describe(a: NexusAction): string {
  const p = a.params || {}
  const k = `${a.domain}.${a.action}`
  switch (k) {
    case 'shopping.add_items': return (p.items || []).map((i: any) => i.name).join(', ')
    case 'pantry.add_items': return `${(p.items || []).length} items`
    case 'pantry.consume': return `used: ${(p.items || []).join(', ')}`
    case 'reminder.add': return `${p.title} · ${fmt(p.due_at)}`
    case 'calendar.add_event': return `${p.title} · ${fmt(p.starts_at)}${p.member_name ? ` · ${p.member_name}` : ''}`
    case 'tasks.add': return p.title
    case 'health.log_biometric': return `${p.metric} ${p.value}${p.unit ? ' ' + p.unit : ''}`
    case 'health.log_medication': return `${p.name} ${p.taken === false ? 'skipped' : 'taken'}`
    case 'health.add_medication': return `${p.name} at ${(p.times || []).join(', ')}`
    case 'health.checkin': return `${p.kind}: ${p.value}`
    case 'health.log_fasting': return p.kept === false ? 'fast broken' : 'fast kept'
    case 'family.add_chore': return `${p.title} → ${p.member_name || 'family'}`
    case 'family.add_milestone': return `${p.member_name}: ${p.title}`
    case 'finance.add_transaction': return `$${Number(p.amount).toFixed(2)} at ${p.merchant}`
    default: return k
  }
}

function fmt(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const today = new Date(); const tmr = new Date(); tmr.setDate(today.getDate() + 1)
  const day = d.toDateString() === today.toDateString() ? 'today' : d.toDateString() === tmr.toDateString() ? 'tomorrow' : d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  return `${day} ${d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
}

const SUGGESTIONS = [
  'Add milk and eggs to the list, remind me to call the dentist tomorrow at 4',
  'Took my vitamins, weighed 176, kept my fast',
  'Soccer practice for Maya Saturday at 10am',
  'Spent $42 at Costco',
]

export default function AviraOrb() {
  const [open, setOpen] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [mute, setMute] = useState(() => localStorage.getItem('avira_mute') === '1')
  const voice = useAviraVoice()
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, busy])
  useEffect(() => { localStorage.setItem('avira_mute', mute ? '1' : '0') }, [mute])

  // Keyboard: hold Space (when orb open and not typing) to talk
  useEffect(() => {
    if (!open) return
    const down = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !(e.target as HTMLElement)?.matches('input,textarea') && !voice.listening) {
        e.preventDefault(); startListening()
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', down)
    return () => window.removeEventListener('keydown', down)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, voice.listening])

  const send = useCallback(async (text: string, source: 'text' | 'voice' = 'text') => {
    const t = text.trim()
    if (!t || busy) return
    setTurns(prev => [...prev, { role: 'user', text: t, ts: Date.now() }])
    setInput('')
    setBusy(true)
    try {
      const res: IngestResult = await nexusApi.ingest(t, { source })
      setTurns(prev => [...prev, { role: 'avira', text: res.reply, event: res.event, actions: res.event?.actions || res.actions, ts: Date.now() }])
      if (!mute) voice.speak(res.reply)
    } catch (e: any) {
      const msg = e?.response?.data?.detail?.error || e?.response?.data?.detail || 'Something went sideways. Try once more?'
      setTurns(prev => [...prev, { role: 'avira', text: typeof msg === 'string' ? msg : JSON.stringify(msg), ts: Date.now() }])
    } finally {
      setBusy(false)
    }
  }, [busy, mute, voice])

  const startListening = useCallback(() => {
    voice.hush()
    const ok = voice.start((final) => send(final, 'voice'))
    if (!ok) setTurns(prev => [...prev, { role: 'avira', text: 'This browser has no speech recognition — Chrome or Safari will do nicely. You can still type.', ts: Date.now() }])
  }, [voice, send])

  const patchEvent = (ev: NexusEvent) =>
    setTurns(prev => prev.map(t => (t.event?.id === ev.id ? { ...t, event: ev, actions: ev.actions } : t)))

  const confirm = async (id: string) => { const ev = await nexusApi.confirm(id); patchEvent(ev); if (!mute) voice.speak('Done.') }
  const reject = async (id: string) => { const ev = await nexusApi.reject(id); patchEvent(ev) }
  const undo = async (id: string) => { const ev = await nexusApi.undo(id); patchEvent(ev); if (!mute) voice.speak('Undone.') }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 w-16 h-16 rounded-full shadow-2xl flex items-center justify-center text-white"
        style={{ background: 'radial-gradient(circle at 30% 30%, #7c3aed, #4f46e5 60%, #1e1b4b)' }}
        aria-label="Talk to Avira"
        title="Talk to Avira"
      >
        <span className="absolute inset-0 rounded-full animate-ping opacity-20" style={{ background: '#818cf8' }} />
        <Mic size={26} />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-[26rem] max-w-[calc(100vw-2rem)] h-[38rem] max-h-[calc(100vh-3rem)] rounded-3xl shadow-2xl flex flex-col overflow-hidden"
         style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
      {/* Header */}
      <div className="p-4 flex items-center justify-between text-white" style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}>
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center bg-white/20 ${voice.speaking ? 'animate-pulse' : ''}`}>
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="font-semibold leading-tight">Avira</h3>
            <p className="text-xs text-white/80">{voice.listening ? 'Listening…' : voice.speaking ? 'Speaking' : busy ? 'Thinking…' : 'Say it once. It lands everywhere.'}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => { setMute(m => !m); voice.hush() }} className="p-2 rounded-lg hover:bg-white/20" title={mute ? 'Unmute Avira' : 'Mute Avira'}>
            {mute ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <button onClick={() => { voice.hush(); voice.stop(); setOpen(false) }} className="p-2 rounded-lg hover:bg-white/20"><X size={18} /></button>
        </div>
      </div>

      {/* Transcript */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {turns.length === 0 && (
          <div className="text-center mt-6" style={{ color: 'var(--text-muted)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>Try one sentence with several things in it:</p>
            <div className="mt-3 space-y-2">
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => send(s)} className="block w-full text-left text-xs px-3 py-2 rounded-xl hover:opacity-80"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>“{s}”</button>
              ))}
            </div>
            <p className="text-xs mt-4 flex items-center justify-center gap-1"><ShieldCheck size={12} /> Processed on your local model. Nothing leaves your device.</p>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`flex ${t.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[88%] rounded-2xl px-4 py-2.5 ${t.role === 'user' ? 'text-white' : ''}`}
                 style={t.role === 'user' ? { background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' } : { background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
              <p className="text-sm whitespace-pre-wrap">{t.text}</p>
              {t.actions && t.actions.length > 0 && (
                <div className="mt-2 space-y-1">
                  {t.actions.map((a, j) => (
                    <div key={j} className="flex items-center gap-2 text-xs rounded-lg px-2 py-1"
                         style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                      <span className={`w-1.5 h-1.5 rounded-full ${a.status === 'applied' ? 'bg-emerald-500' : a.status === 'undone' ? 'bg-gray-400' : a.status === 'failed' ? 'bg-red-500' : 'bg-amber-400'}`} />
                      <span className="font-semibold" style={{ color: 'var(--accent-primary)' }}>{DOMAIN_LABEL[a.domain] || a.domain}</span>
                      <span className="truncate" style={{ color: 'var(--text-secondary)' }}>{describe(a)}</span>
                      {a.error && <span className="text-red-500 truncate" title={a.error}>!</span>}
                    </div>
                  ))}
                </div>
              )}
              {t.event && (
                <div className="mt-2 flex gap-2">
                  {t.event.status === 'proposed' && (
                    <>
                      <button onClick={() => confirm(t.event!.id)} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg text-white bg-emerald-600 hover:bg-emerald-700"><Check size={12} /> Do it</button>
                      <button onClick={() => reject(t.event!.id)} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}><X size={12} /> Skip</button>
                    </>
                  )}
                  {t.event.status === 'applied' && (
                    <button onClick={() => undo(t.event!.id)} className="flex items-center gap-1 text-xs px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)' }}><Undo2 size={12} /> Undo</button>
                  )}
                  {t.event.status === 'undone' && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Undone</span>}
                  {t.event.status === 'rejected' && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Skipped</span>}
                </div>
              )}
            </div>
          </div>
        ))}
        {voice.listening && voice.interim && (
          <div className="flex justify-end"><div className="max-w-[88%] rounded-2xl px-4 py-2 text-sm italic opacity-70 text-white" style={{ background: '#6366f1' }}>{voice.interim}</div></div>
        )}
        {busy && (
          <div className="flex justify-start"><div className="rounded-2xl px-4 py-2" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="flex gap-1">{[0, 1, 2].map(i => <div key={i} className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: `${i * 0.1}s` }} />)}</div>
          </div></div>
        )}
        <div ref={endRef} />
      </div>

      {/* Composer */}
      <div className="p-3 border-t flex items-center gap-2" style={{ borderColor: 'var(--border-color)' }}>
        <button
          onMouseDown={(e) => { e.preventDefault(); voice.listening ? voice.stop() : startListening() }}
          className={`w-12 h-12 rounded-full flex items-center justify-center text-white shrink-0 transition-all ${voice.listening ? 'scale-110 ring-4 ring-rose-300' : ''}`}
          style={{ background: voice.listening ? '#e11d48' : 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}
          title={voice.supported ? (voice.listening ? 'Stop' : 'Tap to talk (or hold Space)') : 'Speech recognition unavailable in this browser'}
        >
          {voice.listening ? <MicOff size={20} /> : <Mic size={20} />}
        </button>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') send(input) }}
          placeholder={voice.listening ? 'Listening…' : 'Or type: "add bread, remind me at 6 to call mum"'}
          className="flex-1 px-4 py-2.5 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}
          disabled={busy}
        />
        <button onClick={() => send(input)} disabled={busy || !input.trim()} className="p-2.5 rounded-xl text-white disabled:opacity-40" style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}>
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
