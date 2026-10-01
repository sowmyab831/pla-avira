import { useCallback, useEffect, useState } from 'react'
import { Pill, Timer, Activity, Plus, Check, X, Trash2, Dumbbell, Sparkles, Flame } from 'lucide-react'
import { careApi } from '../api/nexus'
import { Section, Empty } from './Today'

const METRICS = [
  { key: 'weight', label: 'Weight', unit: 'lb' }, { key: 'bp_sys', label: 'BP systolic', unit: 'mmHg' }, { key: 'bp_dia', label: 'BP diastolic', unit: 'mmHg' },
  { key: 'glucose', label: 'Glucose', unit: 'mg/dL' }, { key: 'steps', label: 'Steps', unit: 'steps' }, { key: 'sleep_h', label: 'Sleep', unit: 'h' }, { key: 'hr', label: 'Resting HR', unit: 'bpm' },
]

export default function Care() {
  const [meds, setMeds] = useState<any[]>([])
  const [adh, setAdh] = useState<any>(null)
  const [fast, setFast] = useState<any>(null)
  const [bio, setBio] = useState<any>({ series: {}, trends: {} })
  const [ci, setCi] = useState<any>({ today: [], streaks: {} })
  const [wk, setWk] = useState<any>(null)
  const [ins, setIns] = useState<{ insights: string[]; habit: string } | null>(null)
  const [medForm, setMedForm] = useState({ name: '', dose: '', times: '08:00', with_food: 'any' })
  const [showMed, setShowMed] = useState(false)
  const [bioForm, setBioForm] = useState({ metric: 'weight', value: '' })
  const [fastForm, setFastForm] = useState({ protocol: '16:8', eating_start: '12:00', eating_end: '20:00' })

  const load = useCallback(async () => {
    const [m, a, f, b, c, w] = await Promise.all([careApi.meds(), careApi.adherence(), careApi.fasting(), careApi.biometrics(), careApi.checkins(), careApi.microWorkout(5)])
    setMeds(m); setAdh(a); setFast(f); setBio(b); setCi(c); setWk(w.workout)
  }, [])
  useEffect(() => { load() }, [load])

  const addMed = async () => {
    await careApi.addMed({ name: medForm.name, dose: medForm.dose || null, times: medForm.times.split(',').map(s => s.trim()).filter(Boolean), with_food: medForm.with_food })
    setMedForm({ name: '', dose: '', times: '08:00', with_food: 'any' }); setShowMed(false); await load()
  }
  const addBio = async () => {
    if (!bioForm.value) return
    const m = METRICS.find(x => x.key === bioForm.metric)!
    await careApi.addBiometric(bioForm.metric, parseFloat(bioForm.value), m.unit); setBioForm({ ...bioForm, value: '' }); await load()
  }
  const done = (kind: string) => ci.today?.some((t: any) => t.kind === kind && t.value === 'yes')

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><Activity /> Care</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Meds, fasting, vitals and one-tap habits. Say “took my lisinopril, weighed 180” to Avira and it lands here.</p>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        {/* Medications */}
        <Section title="Medications" icon={<Pill size={18} />} action={<button onClick={() => setShowMed(s => !s)} className="text-xs px-3 py-1.5 rounded-lg flex items-center gap-1 text-white" style={{ background: '#4f46e5' }}><Plus size={12} /> Add</button>}>
          {showMed && (
            <div className="grid grid-cols-2 gap-2 mb-3 p-3 rounded-2xl" style={{ background: 'var(--bg-tertiary)' }}>
              <input placeholder="Name" value={medForm.name} onChange={e => setMedForm({ ...medForm, name: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }} />
              <input placeholder="Dose (10mg)" value={medForm.dose} onChange={e => setMedForm({ ...medForm, dose: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }} />
              <input placeholder="Times: 08:00, 20:00" value={medForm.times} onChange={e => setMedForm({ ...medForm, times: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }} />
              <select value={medForm.with_food} onChange={e => setMedForm({ ...medForm, with_food: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
                {['any', 'before', 'with', 'after'].map(o => <option key={o} value={o}>{o} food</option>)}
              </select>
              <button onClick={addMed} disabled={!medForm.name} className="col-span-2 py-2 rounded-lg text-white text-sm disabled:opacity-40" style={{ background: '#4f46e5' }}>Save</button>
            </div>
          )}
          {meds.length === 0 ? <Empty text="No medications yet." /> : (
            <ul className="space-y-2">
              {meds.map(m => {
                const a = adh?.medications?.find((x: any) => x.id === m.id)
                return (
                  <li key={m.id} className="flex items-center gap-3 rounded-2xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{m.name} <span className="font-normal" style={{ color: 'var(--text-muted)' }}>{m.dose}</span></p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{(m.times || []).join(', ')}{m.with_food && m.with_food !== 'any' ? ` · ${m.with_food} food` : ''}{a?.adherence_pct != null ? ` · ${a.adherence_pct}% last 30d` : ''}</p>
                    </div>
                    {m.taken_today ? <span className="text-xs px-2 py-1 rounded-lg bg-emerald-100 text-emerald-700 flex items-center gap-1"><Check size={12} /> taken</span> : (
                      <div className="flex gap-1">
                        <button onClick={async () => { await careApi.logMed(m.id, true); await load() }} className="px-2.5 py-1.5 rounded-lg text-white text-xs bg-emerald-600">Took it</button>
                        <button onClick={async () => { await careApi.logMed(m.id, false); await load() }} className="px-2.5 py-1.5 rounded-lg text-xs" style={{ background: 'var(--bg-secondary)', color: 'var(--text-secondary)' }}>Skip</button>
                      </div>
                    )}
                    <button onClick={async () => { await careApi.deleteMed(m.id); await load() }} className="p-1.5 text-rose-400"><Trash2 size={14} /></button>
                  </li>
                )
              })}
            </ul>
          )}
        </Section>

        {/* Fasting */}
        <Section title="Fasting" icon={<Timer size={18} />}>
          {fast?.window ? (
            <div>
              <div className="flex items-center justify-between rounded-2xl p-4" style={{ background: fast.now?.state === 'fasting' ? '#4f46e520' : '#10b98120' }}>
                <div>
                  <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{fast.window.protocol}</p>
                  <p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{fast.now?.state === 'fasting' ? 'Fasting' : 'Eating window'} <span className="text-sm font-normal" style={{ color: 'var(--text-muted)' }}>until {fast.now?.next_change}</span></p>
                </div>
                <div className="text-right"><p className="text-2xl font-bold flex items-center gap-1" style={{ color: 'var(--accent-primary)' }}><Flame size={20} /> {fast.streak_days}</p><p className="text-xs" style={{ color: 'var(--text-muted)' }}>day streak</p></div>
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={async () => { await careApi.logFast(true); await load() }} className="flex-1 py-2 rounded-xl text-white text-sm bg-emerald-600">Kept today's fast</button>
                <button onClick={async () => { await careApi.logFast(false); await load() }} className="flex-1 py-2 rounded-xl text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>Broke it (no judgement)</button>
              </div>
              <div className="flex gap-1 mt-3 flex-wrap">
                {fast.logs.slice(0, 21).reverse().map((l: any) => <span key={l.day} title={l.day} className={`w-4 h-4 rounded ${l.kept ? 'bg-emerald-500' : 'bg-rose-300'}`} />)}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2">
              <select value={fastForm.protocol} onChange={e => setFastForm({ ...fastForm, protocol: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>{['16:8', '18:6', '14:10', '20:4', 'OMAD'].map(p => <option key={p}>{p}</option>)}</select>
              <input type="time" value={fastForm.eating_start} onChange={e => setFastForm({ ...fastForm, eating_start: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
              <input type="time" value={fastForm.eating_end} onChange={e => setFastForm({ ...fastForm, eating_end: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
              <button onClick={async () => { await careApi.setFasting(fastForm); await load() }} className="col-span-3 py-2 rounded-lg text-white text-sm" style={{ background: '#4f46e5' }}>Start tracking</button>
            </div>
          )}
        </Section>

        {/* Biometrics */}
        <Section title="Vitals" icon={<Activity size={18} />}>
          <div className="flex gap-2 mb-3">
            <select value={bioForm.metric} onChange={e => setBioForm({ ...bioForm, metric: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>{METRICS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}</select>
            <input type="number" placeholder="value" value={bioForm.value} onChange={e => setBioForm({ ...bioForm, value: e.target.value })} onKeyDown={e => e.key === 'Enter' && addBio()} className="flex-1 px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
            <button onClick={addBio} className="px-3 py-2 rounded-lg text-white text-sm" style={{ background: '#4f46e5' }}>Log</button>
          </div>
          {Object.keys(bio.series).length === 0 ? <Empty text="Log a weight or BP to see trends." /> : (
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(bio.series).map(([k, pts]: any) => {
                const t = bio.trends[k]; const m = METRICS.find(x => x.key === k)
                const vals = pts.map((p: any) => p.v); const min = Math.min(...vals), max = Math.max(...vals)
                return (
                  <div key={k} className="rounded-2xl p-3" style={{ background: 'var(--bg-tertiary)' }}>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{m?.label || k}</p>
                    <p className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>{pts[pts.length - 1].v} <span className="text-xs font-normal">{pts[pts.length - 1].unit}</span>{t && <span className={`text-xs ml-2 ${t.delta < 0 ? 'text-emerald-600' : t.delta > 0 ? 'text-amber-600' : ''}`}>{t.delta > 0 ? '+' : ''}{t.delta}</span>}</p>
                    <svg viewBox="0 0 100 24" className="w-full h-6 mt-1"><polyline fill="none" stroke="#6366f1" strokeWidth="2" points={pts.map((p: any, i: number) => `${(i / Math.max(pts.length - 1, 1)) * 100},${max === min ? 12 : 22 - ((p.v - min) / (max - min)) * 20}`).join(' ')} /></svg>
                  </div>
                )
              })}
            </div>
          )}
        </Section>

        {/* Check-ins + micro-workout */}
        <Section title="Today's habits" icon={<Dumbbell size={18} />}>
          <div className="grid grid-cols-2 gap-2">
            {[{ k: 'workout', l: 'Moved my body' }, { k: 'water', l: 'Hit water goal' }, { k: 'stretch', l: 'Stretched' }, { k: 'sleep', l: 'Slept well' }].map(h => (
              <button key={h.k} onClick={async () => { await careApi.checkin(h.k, done(h.k) ? 'no' : 'yes'); await load() }}
                      className={`rounded-2xl p-3 text-left text-sm flex items-center justify-between ${done(h.k) ? 'text-white' : ''}`}
                      style={{ background: done(h.k) ? '#10b981' : 'var(--bg-tertiary)', color: done(h.k) ? '#fff' : 'var(--text-primary)' }}>
                <span>{h.l}</span>
                <span className="text-xs opacity-80">{done(h.k) ? <Check size={16} /> : `${ci.streaks?.[h.k] || 0}🔥`}</span>
              </button>
            ))}
          </div>
          {wk && (
            <div className="mt-3 rounded-2xl p-4" style={{ background: 'linear-gradient(135deg,#4f46e520,#7c3aed20)' }}>
              <p className="text-xs uppercase tracking-wide" style={{ color: 'var(--text-muted)' }}>{wk.minutes}-minute micro-workout</p>
              <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>{wk.title}</p>
              <ul className="text-sm mt-1 list-disc list-inside" style={{ color: 'var(--text-secondary)' }}>{wk.moves.map((m: string) => <li key={m}>{m}</li>)}</ul>
              <button onClick={async () => { await careApi.checkin('workout', 'yes'); await load() }} className="mt-2 text-xs px-3 py-1.5 rounded-lg text-white bg-emerald-600">Done — log it</button>
            </div>
          )}
          <button onClick={async () => setIns(await careApi.insights())} className="mt-3 w-full py-2 rounded-xl text-sm flex items-center justify-center gap-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--accent-primary)' }}><Sparkles size={14} /> Weekly insight from Avira</button>
          {ins && (
            <div className="mt-2 text-sm space-y-1" style={{ color: 'var(--text-secondary)' }}>
              {ins.insights.map((s, i) => <p key={i}>• {s}</p>)}
              <p className="font-medium mt-1" style={{ color: 'var(--text-primary)' }}>Try: {ins.habit}</p>
            </div>
          )}
        </Section>
      </div>
      <p className="text-xs text-center" style={{ color: 'var(--text-muted)' }}><X size={10} className="inline" /> Not medical advice. Data stays on your device.</p>
    </div>
  )
}
