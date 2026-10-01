import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Check, Cpu, Cloud, KeyRound, Lock, RefreshCw, Save, Search, Trash2, Wallet, X } from 'lucide-react'
import { aiApi, Catalog, CatalogModel, Connection, Mode, Preferences, Profile, Usage, usd } from '../api/ai'

const PROFILES: { key: Profile; label: string; blurb: string }[] = [
  { key: 'economy', label: 'Economy', blurb: 'Smallest capable model. Fastest, cheapest. Good for lists, extraction, quick questions.' },
  { key: 'balanced', label: 'Balanced', blurb: 'Default. Mid-size model for everyday planning, money and shopping questions.' },
  { key: 'quality', label: 'Quality', blurb: 'Largest permitted model. Slower; use for research and complex reasoning.' },
]

const TASKS = ['assistant', 'finance', 'stock', 'shopping', 'health', 'travel', 'extract']

const card: React.CSSProperties = { background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }
const muted: React.CSSProperties = { color: 'var(--text-muted)' }

export default function AISettings() {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [prefs, setPrefs] = useState<Preferences | null>(null)
  const [conns, setConns] = useState<Connection[]>([])
  const [byok, setByok] = useState(false)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [c, p, k, u] = await Promise.all([aiApi.catalog(), aiApi.getPreferences(), aiApi.connections(), aiApi.usage()])
      setCatalog(c); setPrefs(p); setConns(k.connections); setByok(k.byok_enabled); setUsage(u)
    } catch (e: any) {
      setMsg({ kind: 'err', text: e?.response?.data?.detail?.message || e?.response?.data?.detail || 'Could not load AI settings' })
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const models = useMemo(() => {
    if (!catalog) return []
    const s = q.trim().toLowerCase()
    return catalog.models.filter(m => !s || m.display_name.toLowerCase().includes(s) || m.provider_label.toLowerCase().includes(s) || m.model_id.includes(s))
  }, [catalog, q])

  const save = async () => {
    if (!prefs) return
    setSaving(true); setMsg(null)
    try {
      const r = await aiApi.putPreferences(prefs)
      setPrefs({ ...prefs, version: r.version })
      setMsg({ kind: 'ok', text: 'Saved. Applies to your next request.' })
      const c = await aiApi.catalog(); setCatalog(c)
    } catch (e: any) {
      const d = e?.response?.data?.detail
      setMsg({ kind: 'err', text: e?.response?.status === 409 ? 'Changed elsewhere — reloading.' : (typeof d === 'string' ? d : d?.message || 'Save failed') })
      if (e?.response?.status === 409) load()
    } finally { setSaving(false) }
  }

  if (loading || !prefs || !catalog) return <div className="p-6" style={muted}>Loading AI settings…</div>

  const setMode = (mode: Mode) => setPrefs({ ...prefs, mode, cloud_allowed: mode === 'local_only' ? false : prefs.cloud_allowed })
  const choose = (m: CatalogModel) => setPrefs({ ...prefs, mode: 'choose', default_provider: m.provider, default_model: m.model_id })
  const cloudBlocked = !catalog.cloud_enabled

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>AI &amp; Privacy</h1>
        <p className="text-sm mt-1" style={muted}>
          Choose where your questions are processed. Everything runs on this machine unless you turn on cloud processing.
        </p>
      </header>

      {msg && (
        <div role="status" className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm ${msg.kind === 'ok' ? 'bg-emerald-50 text-emerald-800' : 'bg-red-50 text-red-800'}`}>
          {msg.kind === 'ok' ? <Check size={16} /> : <AlertTriangle size={16} />} {msg.text}
        </div>
      )}

      {/* Mode */}
      <section className="rounded-2xl p-4 space-y-3" style={card} aria-labelledby="mode-h">
        <h2 id="mode-h" className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><Cpu size={18} /> Mode</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" role="radiogroup" aria-label="Processing mode">
          {([['local_only', 'Local only', 'Nothing leaves this machine. Uses installed Ollama models.'],
            ['auto', 'Auto', 'Avira picks a model per task from what you permit below.'],
            ['choose', 'Choose a model', 'Pin one model for everything.']] as [Mode, string, string][]).map(([k, label, blurb]) => (
            <button key={k} role="radio" aria-checked={prefs.mode === k} onClick={() => setMode(k)}
              className={`text-left p-3 rounded-xl border transition focus:outline-none focus:ring-2 focus:ring-indigo-400 ${prefs.mode === k ? 'border-indigo-500 ring-1 ring-indigo-300' : ''}`}
              style={{ borderColor: prefs.mode === k ? undefined : 'var(--border-color)', background: 'var(--bg-tertiary)' }}>
              <div className="font-medium text-sm flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                {k === 'local_only' && <Lock size={14} className="text-emerald-600" />}{label}
              </div>
              <div className="text-xs mt-1" style={muted}>{blurb}</div>
            </button>
          ))}
        </div>

        {prefs.mode === 'auto' && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2" role="radiogroup" aria-label="Auto profile">
            {PROFILES.map(p => (
              <button key={p.key} role="radio" aria-checked={prefs.profile === p.key} onClick={() => setPrefs({ ...prefs, profile: p.key })}
                className={`text-left p-3 rounded-xl border focus:outline-none focus:ring-2 focus:ring-indigo-400 ${prefs.profile === p.key ? 'border-indigo-500' : ''}`}
                style={{ borderColor: prefs.profile === p.key ? undefined : 'var(--border-color)' }}>
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{p.label}</div>
                <div className="text-xs mt-1" style={muted}>{p.blurb}</div>
              </button>
            ))}
          </div>
        )}

        <label className={`flex items-start gap-3 pt-2 text-sm ${prefs.mode === 'local_only' || cloudBlocked ? 'opacity-60' : ''}`} style={{ color: 'var(--text-primary)' }}>
          <input type="checkbox" className="mt-1" disabled={prefs.mode === 'local_only' || cloudBlocked} checked={prefs.cloud_allowed}
            onChange={e => setPrefs({ ...prefs, cloud_allowed: e.target.checked })} />
          <span>
            <span className="font-medium flex items-center gap-1"><Cloud size={14} /> Allow cloud processing</span>
            <span className="block text-xs" style={muted}>
              {cloudBlocked ? 'Disabled on this deployment by the administrator.' :
                'Hosted providers may process your questions. Sensitive documents (health, bank statements) stay local unless you raise the limit below.'}
            </span>
          </span>
        </label>

        {prefs.cloud_allowed && !cloudBlocked && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <label className="block">
              <span style={muted}>Most sensitive data allowed in the cloud</span>
              <select className="mt-1 w-full rounded-lg px-2 py-1.5" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}
                value={prefs.max_data_class_cloud} onChange={e => setPrefs({ ...prefs, max_data_class_cloud: e.target.value as any })}>
                <option value="public">Public only (no personal content)</option>
                <option value="masked">Masked (identifiers removed) — recommended</option>
                <option value="personal">Personal notes and lists</option>
                <option value="sensitive">Health and financial documents</option>
              </select>
            </label>
            <label className="block">
              <span style={muted}>Monthly spending cap (Avira allowance)</span>
              <input type="number" min={0} step={0.5} className="mt-1 w-full rounded-lg px-2 py-1.5" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}
                value={prefs.monthly_cap_micro_usd == null ? '' : prefs.monthly_cap_micro_usd / 1_000_000}
                placeholder="No cap set"
                onChange={e => setPrefs({ ...prefs, monthly_cap_micro_usd: e.target.value === '' ? null : Math.round(Number(e.target.value) * 1_000_000) })} />
              <span className="text-xs" style={muted}>USD. Manual tools keep working after the cap is reached.</span>
            </label>
            <label className="flex items-center gap-2 sm:col-span-2">
              <input type="checkbox" checked={prefs.fallback_providers.includes('ollama')}
                onChange={e => setPrefs({ ...prefs, fallback_providers: e.target.checked ? Array.from(new Set([...prefs.fallback_providers, 'ollama'])) : prefs.fallback_providers.filter(p => p !== 'ollama') })} />
              <span style={{ color: 'var(--text-primary)' }}>If my chosen provider is down, fall back to a <b>local</b> model (never another cloud provider)</span>
            </label>
          </div>
        )}
      </section>

      {/* Model picker */}
      <section className="rounded-2xl p-4 space-y-3" style={card} aria-labelledby="models-h">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 id="models-h" className="font-semibold" style={{ color: 'var(--text-primary)' }}>Models</h2>
          <div className="flex items-center gap-2 px-2 py-1 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <Search size={14} style={muted} />
            <input aria-label="Search models" value={q} onChange={e => setQ(e.target.value)} placeholder="Search…" className="bg-transparent outline-none text-sm w-40" style={{ color: 'var(--text-primary)' }} />
          </div>
        </div>
        <p className="text-xs" style={muted}>Catalog verified against provider documentation on {catalog.verified_at}. Prices are per 1M tokens; “unknown” blocks managed use until an administrator records one.</p>
        <ul className="divide-y" style={{ borderColor: 'var(--border-color)' }}>
          {models.map(m => {
            const selected = prefs.mode === 'choose' && prefs.default_provider === m.provider && prefs.default_model === m.model_id
            return (
              <li key={m.key} className="py-2 flex flex-col sm:flex-row sm:items-center gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-sm">
                    {m.locality === 'local' ? <Lock size={13} className="text-emerald-600" aria-label="local" /> : <Cloud size={13} className="text-sky-600" aria-label="cloud" />}
                    <span className="font-medium truncate" style={{ color: 'var(--text-primary)' }}>{m.display_name}</span>
                    <span className="text-xs" style={muted}>· {m.provider_label}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}>{m.tier}</span>
                  </div>
                  <div className="text-xs mt-0.5 flex flex-wrap gap-x-3" style={muted}>
                    <span>{m.capabilities.join(' · ')}</span>
                    <span>{m.locality === 'local' ? 'free (local)' : m.price ? `in ${usd(m.price.input_per_1m_micro_usd)} / out ${usd(m.price.output_per_1m_micro_usd)}` : 'price unknown'}</span>
                  </div>
                  {!m.selectable && <div className="text-xs mt-0.5 text-amber-700">{m.disabled_reason}</div>}
                </div>
                <button disabled={!m.selectable} onClick={() => choose(m)} aria-pressed={selected}
                  className={`text-xs px-3 py-1.5 rounded-lg border focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-40 ${selected ? 'bg-indigo-600 text-white border-indigo-600' : ''}`}
                  style={selected ? {} : { borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}>
                  {selected ? 'Default' : 'Use as default'}
                </button>
              </li>
            )
          })}
        </ul>

        <details className="text-sm">
          <summary className="cursor-pointer" style={{ color: 'var(--text-secondary)' }}>Per-task overrides (optional)</summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
            {TASKS.map(t => (
              <label key={t} className="flex items-center gap-2">
                <span className="w-24 capitalize" style={muted}>{t}</span>
                <select className="flex-1 rounded-lg px-2 py-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}
                  value={prefs.per_task[t] ? `${prefs.per_task[t].provider}:${prefs.per_task[t].model}` : ''}
                  onChange={e => {
                    const pt = { ...prefs.per_task }
                    if (!e.target.value) delete pt[t]
                    else { const [provider, model] = e.target.value.split(/:(.+)/); pt[t] = { provider, model } }
                    setPrefs({ ...prefs, per_task: pt })
                  }}>
                  <option value="">Follow mode</option>
                  {catalog.models.filter(m => m.selectable).map(m => <option key={m.key} value={m.key}>{m.display_name}</option>)}
                </select>
              </label>
            ))}
          </div>
        </details>

        <div className="flex items-center gap-3 pt-2">
          <button onClick={save} disabled={saving} className="flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:opacity-60">
            <Save size={16} /> {saving ? 'Saving…' : 'Save preferences'}
          </button>
          <label className="text-sm flex items-center gap-2" style={muted}>
            Detail
            <select value={prefs.detail_level} onChange={e => setPrefs({ ...prefs, detail_level: e.target.value as any })} className="rounded-lg px-2 py-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
              <option value="brief">Brief</option><option value="normal">Normal</option><option value="detailed">Detailed</option>
            </select>
          </label>
        </div>
      </section>

      <Connections conns={conns} byok={byok} providers={catalog.providers} onChange={load} setMsg={setMsg} />
      <UsagePanel usage={usage} />
    </div>
  )
}

function Connections({ conns, byok, providers, onChange, setMsg }: {
  conns: Connection[]; byok: boolean; providers: Catalog['providers']; onChange: () => void
  setMsg: (m: { kind: 'ok' | 'err'; text: string } | null) => void
}) {
  const [provider, setProvider] = useState('openai')
  const [key, setKey] = useState('')
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, string>>({})

  const add = async () => {
    setBusy('add'); setMsg(null)
    try {
      await aiApi.addConnection({ provider, api_key: key, label })
      setKey(''); setLabel('')      // password field cleared after save
      setMsg({ kind: 'ok', text: 'Key saved and encrypted. Run “Test” to verify it.' })
      onChange()
    } catch (e: any) {
      const d = e?.response?.data?.detail
      setMsg({ kind: 'err', text: typeof d === 'string' ? d : (Array.isArray(d) ? d[0]?.msg : d?.message) || 'Could not save key' })
    } finally { setBusy(null) }
  }
  const test = async (id: string) => {
    setBusy(id)
    try {
      const r = await aiApi.testConnection(id)
      setTestResult(t => ({ ...t, [id]: r.ok ? `OK · ${r.models_visible} models visible` : `Failed: ${r.detail}` }))
      onChange()
    } catch (e: any) { setTestResult(t => ({ ...t, [id]: 'Test failed' })) } finally { setBusy(null) }
  }
  const revoke = async (id: string) => {
    if (!confirm('Revoke this key? Avira will stop using it immediately.')) return
    setBusy(id)
    try { await aiApi.revokeConnection(id); onChange() } finally { setBusy(null) }
  }

  return (
    <section className="rounded-2xl p-4 space-y-3" style={card} aria-labelledby="conn-h">
      <h2 id="conn-h" className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><KeyRound size={18} /> Credentials</h2>
      <p className="text-xs" style={muted}>Keys are write-only: encrypted on save, never shown again, never sent to your browser. Testing a key lists the provider's models and may incur a negligible charge.</p>
      <ul className="space-y-2">
        {conns.length === 0 && <li className="text-sm" style={muted}>No connections. Local models need no key.</li>}
        {conns.map(c => (
          <li key={c.id} className="flex flex-col sm:flex-row sm:items-center gap-2 p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
            <div className="flex-1 text-sm min-w-0">
              <div className="flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <span className="font-medium">{providers[c.provider]?.label || c.provider}</span>
                {c.label && <span style={muted}>· {c.label}</span>}
                {c.secret_hint && <span className="font-mono text-xs" style={muted}>{c.secret_hint}</span>}
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c.status === 'ok' ? 'bg-emerald-100 text-emerald-800' : c.status === 'invalid' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}`}>{c.status}</span>
              </div>
              <div className="text-xs" style={muted}>
                Billed to: {c.billed_to}{c.last_checked_at ? ` · checked ${new Date(c.last_checked_at).toLocaleString()}` : ''}{c.last_error ? ` · ${c.last_error}` : ''}
                {testResult[c.id] ? ` · ${testResult[c.id]}` : ''}
              </div>
            </div>
            {c.editable && (
              <div className="flex gap-1">
                <button onClick={() => test(c.id)} disabled={busy === c.id} aria-label="Test connection" className="p-2 rounded-lg border focus:ring-2 focus:ring-indigo-400" style={{ borderColor: 'var(--border-color)', color: 'var(--text-primary)' }}><RefreshCw size={14} /></button>
                <button onClick={() => revoke(c.id)} disabled={busy === c.id} aria-label="Revoke connection" className="p-2 rounded-lg border text-red-600 focus:ring-2 focus:ring-red-400" style={{ borderColor: 'var(--border-color)' }}><Trash2 size={14} /></button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {byok ? (
        <form onSubmit={e => { e.preventDefault(); add() }} className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end pt-2">
          <label className="text-xs" style={muted}>Provider
            <select value={provider} onChange={e => setProvider(e.target.value)} className="mt-1 w-full rounded-lg px-2 py-1.5" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
              {Object.entries(providers).filter(([k]) => k !== 'ollama' && k !== 'compat').map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
            </select>
          </label>
          <label className="text-xs sm:col-span-2" style={muted}>API key
            <input type="password" autoComplete="off" required minLength={8} value={key} onChange={e => setKey(e.target.value)} className="mt-1 w-full rounded-lg px-2 py-1.5 font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
          </label>
          <button type="submit" disabled={busy === 'add' || key.length < 8} className="px-3 py-2 rounded-xl bg-indigo-600 text-white text-sm disabled:opacity-50 focus:ring-2 focus:ring-indigo-400">Add key</button>
          <p className="text-xs sm:col-span-4" style={muted}>Bring-your-own-key calls are billed to <b>your</b> provider account. Avira meters them as estimates and cannot cap use of that key outside Avira.</p>
        </form>
      ) : (
        <p className="text-xs" style={muted}>Bringing your own key is not enabled on this deployment. Hosted models use the Avira allowance when configured by the administrator.</p>
      )}
    </section>
  )
}

function UsagePanel({ usage }: { usage: Usage | null }) {
  if (!usage) return null
  const plat = usage.accounts.find(a => a.funding === 'platform')
  const byok = usage.accounts.find(a => a.funding === 'byok')
  const Row = ({ label, a }: { label: string; a?: Usage['accounts'][number] }) => (
    <div className="p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
      <div className="text-xs" style={muted}>{label}</div>
      {a ? (
        <div className="text-sm mt-1" style={{ color: 'var(--text-primary)' }}>
          Spent {usd(a.spent_micro_usd)}{a.limit_micro_usd != null && <> of {usd(a.limit_micro_usd)} · remaining {usd(a.remaining_micro_usd)}</>}
          {a.reserved_micro_usd > 0 && <span style={muted}> · {usd(a.reserved_micro_usd)} reserved</span>}
          {a.pending_micro_usd > 0 && <span className="text-amber-700"> · {usd(a.pending_micro_usd)} pending reconciliation</span>}
        </div>
      ) : <div className="text-sm mt-1" style={muted}>No usage this period</div>}
    </div>
  )
  return (
    <section className="rounded-2xl p-4 space-y-3" style={card} aria-labelledby="usage-h">
      <h2 id="usage-h" className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><Wallet size={18} /> Usage · {usage.period}</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <Row label="Avira allowance (platform-funded)" a={plat} />
        <Row label="Your own keys (estimates)" a={byok} />
      </div>
      {Object.keys(usage.by_task).length > 0 && (
        <table className="w-full text-xs">
          <thead><tr style={muted}><th className="text-left py-1">Task</th><th className="text-right">Requests</th><th className="text-right">Cost</th></tr></thead>
          <tbody>{Object.entries(usage.by_task).map(([t, v]) => <tr key={t} style={{ color: 'var(--text-primary)' }}><td className="py-1 capitalize">{t}</td><td className="text-right">{v.requests}</td><td className="text-right">{usd(v.micro_usd)}</td></tr>)}</tbody>
        </table>
      )}
      <p className="text-xs" style={muted}>{usage.note}{usage.requests_with_unknown_cost ? ` ${usage.requests_with_unknown_cost} request(s) have unknown cost.` : ''} Resets {usage.resets_on}.</p>
    </section>
  )
}

export { X }
