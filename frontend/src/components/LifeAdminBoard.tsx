import { useCallback, useEffect, useState } from 'react'
import client from '../api/client'

type Kind = 'bill' | 'subscription' | 'return' | 'warranty' | 'document' | 'maintenance' | 'school' | 'care' | 'task' | 'refund' | 'claim'
type Commitment = {
  id: string; title: string; kind: Kind; country: 'US' | 'IN'; currency: 'USD' | 'INR'; amount_minor: number | null
  due_date: string; timezone: string; recurrence: string; status: string; notes: string; reference_url: string | null
  version: number; urgency: string; days_until_due: number
}
const KINDS: Record<Kind, string> = { bill: 'Bill', subscription: 'Subscription renewal', return: 'Return deadline', warranty: 'Warranty expiry', document: 'Document expiry', maintenance: 'Home / vehicle service', school: 'School commitment', care: 'Care task', task: 'Other task', refund: 'Expected refund', claim: 'Warranty / insurance claim' }
const TEMPLATES: { kind: Kind; title: string; recurrence: string; hint: string }[] = [
  { kind: 'bill', title: 'Electricity bill', recurrence: 'monthly', hint: 'Keep the due date and amount in one place.' },
  { kind: 'subscription', title: 'Subscription review', recurrence: 'monthly', hint: 'Review whether to renew before the next charge.' },
  { kind: 'return', title: 'Return a purchase', recurrence: 'none', hint: 'Use the deadline confirmed by your merchant.' },
  { kind: 'document', title: 'Document renewal', recurrence: 'none', hint: 'Plan ahead for passport, insurance or registration expiry.' },
  { kind: 'maintenance', title: 'Appliance service', recurrence: 'yearly', hint: 'Track your next service and provider details.' },
  { kind: 'refund', title: 'Track an expected refund', recurrence: 'none', hint: 'Follow up if money has not arrived by the promised date.' },
  { kind: 'school', title: 'School form due', recurrence: 'none', hint: 'Remember forms, fees and family commitments.' },
]
const money = (amount: number, currency: string) => new Intl.NumberFormat(currency === 'INR' ? 'en-IN' : 'en-US', { style: 'currency', currency }).format(amount / 100)
const errorMessage = (error: any) => typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : 'Could not save this change. Check the fields and try again.'

export default function LifeAdminBoard() {
  const [items, setItems] = useState<Commitment[]>([])
  const [totals, setTotals] = useState({ USD: 0, INR: 0 })
  const [recovery, setRecovery] = useState({ USD: 0, INR: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Commitment | null>(null)
  const [title, setTitle] = useState('')
  const [kind, setKind] = useState<Kind>('bill')
  const [country, setCountry] = useState<'US' | 'IN'>('US')
  const [amount, setAmount] = useState('')
  const [due, setDue] = useState('')
  const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/New_York')
  const [recurrence, setRecurrence] = useState('none')
  const [notes, setNotes] = useState('')
  const [url, setUrl] = useState('')
  const [showCompleted, setShowCompleted] = useState(false)
  const load = useCallback(async () => {
    try {
      const { data } = await client.get('/api/life-admin/commitments')
      setItems(data.items); setTotals(data.due_within_30_days_minor); setRecovery(data.pending_recovery_minor || { USD: 0, INR: 0 })
    } catch { setError('Household commitments could not load. Please retry.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => { void load() }, [load])
  const start = (template?: typeof TEMPLATES[number], item?: Commitment) => {
    setEditing(item || null); setTitle(item?.title || template?.title || '')
    setKind(item?.kind || template?.kind || 'bill'); setAmount(item?.amount_minor != null ? (item.amount_minor / 100).toFixed(2) : '')
    setDue(item?.due_date || ''); setRecurrence(item?.recurrence || template?.recurrence || 'none')
    setNotes(item?.notes || ''); setUrl(item?.reference_url || '')
    if (item) { setCountry(item.country); setTimezone(item.timezone) }
    setShowForm(true); setError('')
  }
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setError('')
    if (amount && !/^\d+(\.\d{1,2})?$/.test(amount)) { setError('Enter an amount with at most two decimal places.'); return }
    const body = { title, kind, country, currency: country === 'IN' ? 'INR' : 'USD', amount_minor: amount ? Math.round(Number(amount) * 100) : null,
      due_date: due, timezone, recurrence, notes, reference_url: url || null }
    setBusy(true)
    try {
      if (editing) await client.put(`/api/life-admin/commitments/${editing.id}?version=${editing.version}`, body)
      else await client.post('/api/life-admin/commitments', body)
      setShowForm(false); await load()
    } catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  const complete = async (item: Commitment) => {
    setBusy(true); setError('')
    try { await client.post(`/api/life-admin/commitments/${item.id}/complete`, { version: item.version }); await load() }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  const inputClass = 'w-full rounded-lg border p-2 bg-transparent mt-1'
  return <section className="rounded-2xl border p-5 space-y-4" style={{ borderColor: 'var(--border-color)', background: 'var(--bg-card)', color: 'var(--text-primary)' }} aria-labelledby="life-admin-title">
    <div className="flex justify-between gap-3 flex-wrap"><div><h2 id="life-admin-title" className="text-xl font-bold">Your household, handled</h2>
      <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Bills, renewals and deadlines. Due items appear here when you open Today.</p></div>
      <button onClick={() => start()} className="rounded-xl bg-indigo-600 px-4 py-2 text-white">Add commitment</button></div>
    <div className="grid sm:grid-cols-3 gap-2">{TEMPLATES.map(t => <button key={t.kind} onClick={() => start(t)} className="border rounded-xl p-3 text-left" style={{ borderColor: 'var(--border-color)' }}><span className="font-medium text-sm">{t.title}</span><span className="block text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{t.hint}</span></button>)}</div>
    <div className="text-sm">Bills and renewals due within 30 days, including overdue: <strong>{money(totals.USD, 'USD')}</strong> · <strong>{money(totals.INR, 'INR')}</strong>. Currencies are kept separate.</div>
    <p className="text-sm">Expected refunds and claims: <strong>{money(recovery.USD, 'USD')}</strong> · <strong>{money(recovery.INR, 'INR')}</strong>. Amounts are entered by you and are not guaranteed recoveries.</p>
    {error && <div role="alert" className="text-red-600 text-sm">{error} <button type="button" className="underline" onClick={() => { setError(''); void load() }}>Reload</button></div>}
    {showForm && <form onSubmit={save} className="border rounded-xl p-4 space-y-3" style={{ borderColor: 'var(--border-color)' }}>
      <h3 className="font-semibold">{editing ? 'Edit commitment' : 'New commitment'}</h3>
      <div className="grid sm:grid-cols-2 gap-3 text-sm">
        <label>Title<input required maxLength={180} className={inputClass} value={title} onChange={e => setTitle(e.target.value)} /></label>
        <label>Type<select className={inputClass} value={kind} onChange={e => setKind(e.target.value as Kind)}>{Object.entries(KINDS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}</select></label>
        <label>Country / currency<select className={inputClass} value={country} onChange={e => { const c = e.target.value as 'US' | 'IN'; setCountry(c); setTimezone(c === 'IN' ? 'Asia/Kolkata' : 'America/New_York') }}><option value="US">United States · USD</option><option value="IN">India · INR</option></select></label>
        <label>Amount ({country === 'IN' ? 'INR' : 'USD'}, optional)<input className={inputClass} inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} /></label>
        <label>Due date<input type="date" required className={inputClass} value={due} onChange={e => setDue(e.target.value)} /></label>
        <label>Repeat<select className={inputClass} value={recurrence} onChange={e => setRecurrence(e.target.value)}><option value="none">Does not repeat</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option></select></label>
        <label>Timezone<input required className={inputClass} value={timezone} onChange={e => setTimezone(e.target.value)} /></label>
        <label>Provider or document link (optional)<input type="url" placeholder="https://" className={inputClass} value={url} onChange={e => setUrl(e.target.value)} /></label>
      </div>
      <label className="block text-sm">Notes<textarea maxLength={2000} className={inputClass} value={notes} onChange={e => setNotes(e.target.value)} /></label>
      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Use dates and terms confirmed by your provider. Opening a provider link does not pay a bill or cancel a subscription.</p>
      <div className="flex gap-3"><button disabled={busy} className="bg-indigo-600 text-white rounded-lg px-4 py-2">{busy ? 'Saving…' : 'Save'}</button><button type="button" onClick={() => setShowForm(false)}>Cancel</button></div>
    </form>}
    <label className="text-sm flex gap-2"><input type="checkbox" checked={showCompleted} onChange={e => setShowCompleted(e.target.checked)} />Show completed</label>
    {loading ? <p role="status">Loading commitments…</p> : <div className="space-y-2">
      {items.filter(i => showCompleted || i.status === 'open').map(item => <article key={item.id} className="border rounded-xl p-3 flex flex-wrap justify-between gap-3" style={{ borderColor: 'var(--border-color)' }}>
        <div><h3 className="font-semibold">{item.title}</h3><p className="text-sm">{KINDS[item.kind]} · {item.due_date} · {item.timezone} {item.amount_minor != null && `· ${money(item.amount_minor, item.currency)}`}</p>
          <p className={`text-xs mt-1 ${item.urgency === 'overdue' && item.status === 'open' ? 'text-red-600' : ''}`}>{item.status === 'completed' ? 'Completed — reported by you' : item.urgency.replace('_', ' ')} · {item.recurrence === 'none' ? 'One time' : `Repeats ${item.recurrence}`}</p>
          {item.notes && <p className="text-sm mt-1 whitespace-pre-wrap">{item.notes}</p>}
          {item.reference_url && <a className="text-sm underline" href={item.reference_url} target="_blank" rel="noopener noreferrer">Open your saved provider link</a>}</div>
        {item.status === 'open' && <div className="flex gap-3 items-center text-sm"><button disabled={busy} className="underline" onClick={() => start(undefined, item)}>Edit</button><button disabled={busy} className="rounded-lg bg-emerald-700 px-3 py-2 text-white" onClick={() => complete(item)}>{item.kind === 'bill' ? 'I have paid this' : item.kind === 'refund' ? 'I received the refund' : 'Mark completed'}</button></div>}
      </article>)}
      {items.filter(i => showCompleted || i.status === 'open').length === 0 && <p className="text-sm py-3">No open commitments. Start with an upcoming bill or deadline.</p>}
    </div>}
    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Recurring items advance one period when you confirm completion. This workspace records your confirmation; it does not execute payments or send background reminders.</p>
  </section>
}
