import { useEffect, useState } from 'react'
import client from '../api/client'
import { subscriptionApi } from '../api/subscription'

type Market = { currency: string; provider: string; plans: { tier: string; amount_minor: number; interval: string; enabled: boolean }[] }
type BillingStatus = { tier: string; billing: { provider: string; country: string; status: string; tier: string } | null }
const LABELS: Record<string, string> = { free: 'Free', premium: 'Premium', enterprise: 'Family' }

export default function Subscription() {
  const [country, setCountry] = useState<'US' | 'IN'>('US')
  const [markets, setMarkets] = useState<Record<string, Market>>({})
  const [status, setStatus] = useState<BillingStatus | null>(null)
  const [usage, setUsage] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [key, setKey] = useState('')
  const [confirmCancel, setConfirmCancel] = useState(false)
  const load = async () => {
    const [c, s, u] = await Promise.all([client.get('/api/billing/catalog'), client.get('/api/billing/status'), subscriptionApi.usage()])
    setMarkets(c.data.markets); setStatus(s.data); setUsage(u)
    if (s.data.billing?.country) setCountry(s.data.billing.country)
  }
  useEffect(() => { load().catch(() => setMessage('Plans could not load. Please retry.')) }, [])
  const act = async (fn: () => Promise<void>) => {
    setBusy(true); setMessage('')
    try { await fn() } catch (e: any) { setMessage(typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : 'This request could not be completed. Please retry.') }
    finally { setBusy(false) }
  }
  const checkout = (tier: string) => act(async () => {
    const { data } = await client.post('/api/billing/checkout', { country, tier })
    const url = new URL(data.checkout_url)
    if (url.protocol !== 'https:' || !['checkout.stripe.com', 'rzp.io'].includes(url.hostname)) throw new Error('Unexpected checkout URL')
    window.location.assign(url.href)
  })
  const market = markets[country]
  return <div className="max-w-5xl mx-auto p-6 space-y-6" style={{ color: 'var(--text-primary)' }}>
    <header><h1 className="text-3xl font-bold">Plans for everyday life</h1><p className="mt-2" style={{ color: 'var(--text-muted)' }}>Choose your billing country. Manage household commitments, shopping and personal assistance in one place.</p></header>
    <div className="flex flex-wrap gap-4 items-center"><label>Billing country <select className="border rounded-lg p-2 bg-transparent ml-2" value={country} onChange={e => setCountry(e.target.value as 'US' | 'IN')}><option value="US">United States · USD</option><option value="IN">India · INR</option></select></label><button disabled={busy} className="underline" onClick={() => act(load)}>Refresh status</button></div>
    {message && <p role="status" className="rounded-xl border p-3">{message}</p>}
    <p className="text-sm">Current plan: <strong>{status ? LABELS[status.tier] || status.tier : 'Loading…'}</strong>{status?.billing && ` · ${status.billing.provider} · ${status.billing.status.replace(/_/g, ' ')}`}</p>
    <div className="grid md:grid-cols-3 gap-4">
      <article className="border rounded-2xl p-5" style={{ borderColor: 'var(--border-color)' }}><h2 className="font-bold text-xl">Free</h2><p className="text-3xl font-bold my-3">{country === 'IN' ? '₹0' : '$0'}</p><p>Household commitments and everyday planning, with limited AI and document usage.</p></article>
      {market?.plans.map(plan => <article key={plan.tier} className="border rounded-2xl p-5 space-y-3" style={{ borderColor: 'var(--border-color)' }}><h2 className="font-bold text-xl">{LABELS[plan.tier]}</h2>
        <p className="text-3xl font-bold">{new Intl.NumberFormat(country === 'IN' ? 'en-IN' : 'en-US', { style: 'currency', currency: market.currency }).format(plan.amount_minor / 100)}<span className="text-sm font-normal"> / month</span></p>
        <p>{plan.tier === 'premium' ? 'More connected accounts, household features and AI usage.' : 'Expanded family capacity and account limits. Enterprise contracts are scoped separately.'}</p>
        <p className="text-sm">{country === 'IN' ? 'Razorpay checkout · eligible cards and UPI mandates depend on merchant approval.' : 'Stripe checkout · available payment methods appear at checkout.'}</p>
        <button disabled={busy || !plan.enabled || status?.tier === plan.tier || !!status?.billing} onClick={() => checkout(plan.tier)} className="rounded-lg bg-indigo-600 text-white px-4 py-2 disabled:opacity-50">{status?.tier === plan.tier ? 'Current plan' : !plan.enabled ? 'Payments not yet enabled' : status?.billing ? 'Manage existing subscription' : 'Continue to secure checkout'}</button>
      </article>)}
    </div>
    <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Prices are for monthly plans; checkout confirms applicable taxes and payment terms. India mandates run for up to 120 monthly cycles. Paid access updates after provider verification, not simply after returning from checkout.</p>
    {status?.billing && <section className="border rounded-xl p-4 space-y-2"><h2 className="font-bold">Manage billing</h2><p className="text-sm">For incomplete checkout, payment-method changes, plan switches or refunds, contact your deployment administrator. Refresh after checkout to see verified status.</p>
      {!confirmCancel ? <button className="underline" onClick={() => setConfirmCancel(true)}>Cancel recurring subscription</button> : <div className="space-y-2"><p>Stop renewal at the end of the current paid period?</p><button disabled={busy} className="text-red-600 underline mr-4" onClick={() => act(async () => { const { data } = await client.post('/api/billing/cancel'); setMessage(data.message); setConfirmCancel(false); await load() })}>Confirm cancellation</button><button onClick={() => setConfirmCancel(false)}>Keep subscription</button></div>}
    </section>}
    {usage?.usage && <section><h2 className="text-xl font-bold mb-3">Usage in the last 24 hours</h2><div className="grid sm:grid-cols-3 gap-2">{Object.entries(usage.usage).map(([name, u]: [string, any]) => <div key={name} className="rounded-lg border p-3 text-sm"><strong>{name.replace(/_/g, ' ')}</strong><p>{u.used} used · {u.limit === -1 ? 'No plan limit; service capacity applies' : `${u.remaining} of ${u.limit} remaining`}</p></div>)}</div></section>}
    <details className="border rounded-xl p-4"><summary>Have an administrator-issued activation key?</summary><div className="mt-3 flex gap-2"><label className="grow">Activation key<input className="block w-full border rounded p-2 bg-transparent" value={key} onChange={e => setKey(e.target.value)} /></label><button disabled={busy || !key.trim()} onClick={() => act(async () => { const result = await subscriptionApi.activate(key); setKey(''); await load(); setMessage(result.message) })}>Activate</button></div><p className="text-xs mt-2">Available only when the deployment administrator explicitly enables activation keys.</p></details>
    <section className="rounded-xl border p-4"><h2 className="font-bold">For organizations</h2><p className="text-sm mt-2">Enterprise rollout requires tenant isolation, SSO, audit retention, regional hosting and a usage budget agreed for your organization. The Family plan does not promise these enterprise capabilities.</p></section>
  </div>
}
