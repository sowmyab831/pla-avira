import { useEffect, useState } from 'react'
import { Send, MessageCircle, Mail, Bell, Smartphone, Save, Check } from 'lucide-react'
import { notificationsApi } from '../api/notifications'

type Prefs = {
  whatsapp_enabled?: boolean
  whatsapp_number?: string
  telegram_enabled?: boolean
  telegram_chat_id?: string
  email_enabled?: boolean
  email_address?: string
  push_enabled?: boolean
  push_token?: string
  quiet_hours_start?: string
  quiet_hours_end?: string
  categories?: Record<string, boolean>
}

const CATEGORIES = [
  { key: 'earnings_alerts', label: 'Earnings alerts', desc: 'Upcoming reports, previews, surprises' },
  { key: 'price_alerts', label: 'Price alerts', desc: 'Stocks on your watchlist hit your targets' },
  { key: 'action_items', label: 'Action items', desc: 'Bills, deadlines, appointments from inbox' },
  { key: 'calendar_reminders', label: 'Calendar reminders', desc: 'Family events, due dates, meetings' },
  { key: 'market_alerts', label: 'Market digests', desc: 'Morning brief and market updates' },
]

export default function Notifications() {
  const [prefs, setPrefs] = useState<Prefs | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [testing, setTesting] = useState<string | null>(null)
  const [telegramStatus, setTelegramStatus] = useState<any>(null)

  const load = async () => {
    setLoading(true)
    try {
      const p = await notificationsApi.getPrefs()
      const s = await notificationsApi.telegramStatus()
      setPrefs(p.preferences)
      setTelegramStatus(s)
    } catch (e: any) {
      setMessage(e?.response?.data?.detail || 'Failed to load preferences')
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const updateField = (key: keyof Prefs, value: any) => {
    setPrefs(prev => prev ? ({ ...prev, [key]: value }) : prev)
  }

  const toggleCategory = (key: string) => {
    setPrefs(prev => prev ? ({ ...prev, categories: { ...prev.categories, [key]: !prev.categories?.[key] } }) : prev)
  }

  const save = async () => {
    setSaving(true); setMessage('')
    try {
      await notificationsApi.updatePrefs(prefs)
      setMessage('Preferences saved ✅')
    } catch (e: any) { setMessage(e?.response?.data?.detail || 'Save failed') } finally { setSaving(false) }
  }

  const test = async (channel: string, fn: () => Promise<any>) => {
    setTesting(channel); setMessage('')
    try {
      const r = await fn()
      setMessage(`${channel} test sent ✅` + (r.id ? ` (${r.id.slice(0,10)}...)` : ''))
    } catch (e: any) { setMessage(`${channel} test failed: ${e?.response?.data?.detail || e.message}`) } finally { setTesting(null) }
  }

  if (loading) return <div className="p-8" style={{ color: 'var(--text-muted)' }}>Loading notification settings…</div>
  if (!prefs) return null

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}><Bell size={24} /> Notification Channels</h1>
        <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Choose where Avira sends alerts. Telegram is free — just create a bot with @BotFather and message it <code>/start</code>.</p>
      </div>

      {message && (
        <div className="rounded-xl px-4 py-3 text-sm flex items-start gap-2" style={{ background: message.includes('✅') ? '#10b98120' : '#f59e0b20', color: message.includes('✅') ? '#047857' : '#b45309' }}>
          <span className="mt-0.5">{message.includes('✅') ? <Check size={14} /> : '⚠️'}</span>
          {message}
        </div>
      )}

      {/* Telegram */}
      <section className="rounded-2xl p-5 space-y-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <div className="flex items-center gap-2">
          <MessageCircle size={20} style={{ color: '#229ED9' }} />
          <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Telegram <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#10b98120', color: '#047857' }}>free</span></h2>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Recommended. No Twilio or messaging fees. The bot token is set in the backend with <code>TELEGRAM_BOT_TOKEN</code>.</p>

        <div className="flex items-center gap-3">
          <input id="tg_enabled" type="checkbox" checked={!!prefs.telegram_enabled} onChange={e => updateField('telegram_enabled', e.target.checked)} className="w-4 h-4" />
          <label htmlFor="tg_enabled" className="text-sm" style={{ color: 'var(--text-primary)' }}>Enable Telegram alerts</label>
        </div>

        <div>
          <label className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Telegram chat ID</label>
          <div className="flex gap-2 mt-1">
            <input value={prefs.telegram_chat_id || ''} onChange={e => updateField('telegram_chat_id', e.target.value)} placeholder="123456789 or @username" className="flex-1 px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
            <button disabled={!prefs.telegram_chat_id || saving} onClick={async () => { try { await notificationsApi.telegramBind(prefs.telegram_chat_id || ''); setMessage('Chat bound ✅'); } catch (e: any) { setMessage(e?.response?.data?.detail || 'Bind failed') } }} className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: '#229ED9' }}>Bind</button>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Message your bot and call <code>/start</code>, then paste the chat ID here.</p>
        </div>

        <div className="text-xs p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
          Bot configured: <b style={{ color: telegramStatus?.configured ? '#22c55e' : '#ef4444' }}>{telegramStatus?.configured ? 'Yes' : 'No'}</b>
          {telegramStatus?.configured && <> · Chat bound: <b>{telegramStatus?.chat_bound ? 'Yes' : 'No'}</b></>}
        </div>

        <button disabled={!prefs.telegram_enabled || testing === 'telegram'} onClick={() => test('Telegram', notificationsApi.testTelegram)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-white disabled:opacity-40" style={{ background: '#229ED9' }}>
          <Send size={14} /> {testing === 'telegram' ? 'Sending…' : 'Send test Telegram message'}
        </button>
      </section>

      {/* WhatsApp */}
      <section className="rounded-2xl p-5 space-y-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', opacity: 0.85 }}>
        <div className="flex items-center gap-2">
          <Smartphone size={20} style={{ color: '#25D366' }} />
          <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>WhatsApp <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#f59e0b20', color: '#b45309' }}>paid — Twilio</span></h2>
        </div>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Requires a Twilio account and a paid WhatsApp sender. Use Telegram for a free alternative.</p>
        <div className="flex items-center gap-3">
          <input id="wa_enabled" type="checkbox" checked={!!prefs.whatsapp_enabled} onChange={e => updateField('whatsapp_enabled', e.target.checked)} className="w-4 h-4" />
          <label htmlFor="wa_enabled" className="text-sm" style={{ color: 'var(--text-primary)' }}>Enable WhatsApp alerts</label>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>WhatsApp number</label>
          <input value={prefs.whatsapp_number || ''} onChange={e => updateField('whatsapp_number', e.target.value)} placeholder="+1234567890" className="w-full px-3 py-2 rounded-lg text-sm mt-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
        </div>
        <button disabled={!prefs.whatsapp_enabled || testing === 'whatsapp'} onClick={() => test('WhatsApp', notificationsApi.testWhatsApp)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-white disabled:opacity-40" style={{ background: '#25D366' }}>
          <Send size={14} /> {testing === 'whatsapp' ? 'Sending…' : 'Send test WhatsApp message'}
        </button>
      </section>

      {/* Email */}
      <section className="rounded-2xl p-5 space-y-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', opacity: 0.85 }}>
        <div className="flex items-center gap-2">
          <Mail size={20} style={{ color: '#6366f1' }} />
          <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Email <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: '#f59e0b20', color: '#b45309' }}>Resend API key required</span></h2>
        </div>
        <div className="flex items-center gap-3">
          <input id="email_enabled" type="checkbox" checked={!!prefs.email_enabled} onChange={e => updateField('email_enabled', e.target.checked)} className="w-4 h-4" />
          <label htmlFor="email_enabled" className="text-sm" style={{ color: 'var(--text-primary)' }}>Enable email alerts</label>
        </div>
        <div>
          <label className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Email address</label>
          <input value={prefs.email_address || ''} onChange={e => updateField('email_address', e.target.value)} placeholder="you@example.com" className="w-full px-3 py-2 rounded-lg text-sm mt-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
        </div>
        <button disabled={!prefs.email_enabled || testing === 'email'} onClick={() => test('Email', notificationsApi.testEmail)} className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-white disabled:opacity-40" style={{ background: '#6366f1' }}>
          <Send size={14} /> {testing === 'email' ? 'Sending…' : 'Send test email'}
        </button>
      </section>

      {/* Categories + quiet hours */}
      <section className="rounded-2xl p-5 space-y-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Alert categories</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {CATEGORIES.map(c => (
            <label key={c.key} className="flex items-start gap-3 p-3 rounded-lg cursor-pointer" style={{ background: 'var(--bg-tertiary)' }}>
              <input type="checkbox" checked={!!prefs.categories?.[c.key]} onChange={() => toggleCategory(c.key)} className="mt-1" />
              <div>
                <div className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{c.label}</div>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{c.desc}</div>
              </div>
            </label>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4 pt-2">
          <div>
            <label className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Quiet hours start</label>
            <input type="time" value={prefs.quiet_hours_start || '22:00'} onChange={e => updateField('quiet_hours_start', e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm mt-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
          </div>
          <div>
            <label className="text-xs font-semibold uppercase" style={{ color: 'var(--text-muted)' }}>Quiet hours end</label>
            <input type="time" value={prefs.quiet_hours_end || '07:00'} onChange={e => updateField('quiet_hours_end', e.target.value)} className="w-full px-3 py-2 rounded-lg text-sm mt-1" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
          </div>
        </div>
      </section>

      <button onClick={save} disabled={saving} className="w-full py-3 rounded-xl font-semibold text-white flex items-center justify-center gap-2 disabled:opacity-40" style={{ background: '#4f46e5' }}>
        <Save size={18} /> {saving ? 'Saving…' : 'Save notification settings'}
      </button>
    </div>
  )
}
