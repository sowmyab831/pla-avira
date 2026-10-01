import { useState, useEffect, useCallback } from 'react'
import { Link2, Mail, CheckCircle2, Circle, Calendar, RefreshCw, Unplug, ExternalLink, AlertCircle, Clock } from 'lucide-react'
import client from '../api/client'

interface GmailStatus { connected: boolean; email: string | null; last_sync: string | null }
interface ActionItem { id: string; title: string; description: string; priority: string; is_completed: boolean; created_at: string }
interface Appointment { id: string; title: string; date_time: string; description: string; created_at: string }

export default function Integrations() {
  const [gmailStatus, setGmailStatus] = useState<GmailStatus | null>(null)
  const [actionItems, setActionItems] = useState<ActionItem[]>([])
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    const results = await Promise.allSettled([
      client.get('/api/integrations/gmail/status'),
      client.get('/api/integrations/action-items?status=all'),
      client.get('/api/integrations/appointments'),
    ])
    if (results[0].status === 'fulfilled') setGmailStatus(results[0].value.data)
    if (results[1].status === 'fulfilled') setActionItems(results[1].value.data.items ?? [])
    if (results[2].status === 'fulfilled') setAppointments(results[2].value.data.appointments ?? [])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const connectGmail = async () => {
    setConnecting(true)
    try {
      const r = await client.get('/api/integrations/gmail/auth')
      if (r.data.auth_url) window.open(r.data.auth_url, '_blank')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to start Gmail connection'
      alert(msg)
    }
    finally { setConnecting(false) }
  }

  const disconnectGmail = async () => {
    if (!confirm('Disconnect Gmail?')) return
    setDisconnecting(true)
    try {
      await client.post('/api/integrations/gmail/disconnect')
      setGmailStatus({ connected: false, email: null, last_sync: null })
      setActionItems([])
      setAppointments([])
    } catch { /* silent */ }
    finally { setDisconnecting(false) }
  }

  const completeItem = async (id: string) => {
    try {
      await client.post(`/api/integrations/action-items/${id}/complete`)
      setActionItems(prev => prev.map(i => i.id === id ? { ...i, is_completed: true } : i))
    } catch { /* silent */ }
  }

  const pending = actionItems.filter(i => !i.is_completed)
  const completed = actionItems.filter(i => i.is_completed)

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-xl flex items-center justify-center">
          <Link2 className="text-white" size={22} />
        </div>
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Integrations</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Connect services, view action items & appointments</p>
        </div>
        <button onClick={load} className="ml-auto p-2 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} style={{ color: 'var(--text-muted)' }} />
        </button>
      </div>

      {/* Gmail Connection Card */}
      <div className="rounded-2xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${gmailStatus?.connected ? 'bg-emerald-100' : 'bg-gray-100'}`}>
            <Mail size={24} className={gmailStatus?.connected ? 'text-emerald-600' : 'text-gray-400'} />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Gmail</h3>
            {gmailStatus?.connected ? (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                Connected · {gmailStatus.email || 'Email synced'}
                {gmailStatus.last_sync && <span> · Last sync {new Date(gmailStatus.last_sync).toLocaleTimeString()}</span>}
              </p>
            ) : (
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Connect to extract action items & appointments from your inbox</p>
            )}
          </div>
          {gmailStatus?.connected ? (
            <button onClick={disconnectGmail} disabled={disconnecting}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all"
              style={{ background: '#ef444415', color: '#ef4444' }}>
              <Unplug size={14} /> {disconnecting ? 'Disconnecting…' : 'Disconnect'}
            </button>
          ) : (
            <button onClick={connectGmail} disabled={connecting}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-blue-500 to-cyan-600 hover:shadow-lg transition-all disabled:opacity-50">
              <ExternalLink size={14} /> {connecting ? 'Connecting…' : 'Connect Gmail'}
            </button>
          )}
        </div>
      </div>

      {/* Action Items */}
      <div className="rounded-2xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <AlertCircle size={18} className="text-amber-500" /> Action Items
            {pending.length > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">{pending.length} pending</span>}
          </h2>
        </div>

        {actionItems.length === 0 ? (
          <div className="py-8 text-center">
            <Circle size={32} className="mx-auto mb-2" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {gmailStatus?.connected
                ? 'No action items extracted yet. Avira will find them from your emails.'
                : 'Connect Gmail to start extracting action items from your inbox.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {pending.map(item => (
              <div key={item.id} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                <button onClick={() => completeItem(item.id)} className="shrink-0 text-amber-500 hover:text-emerald-500 transition-colors">
                  <Circle size={18} />
                </button>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{item.title}</p>
                  {item.description && <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>{item.description}</p>}
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${item.priority === 'high' ? 'bg-red-100 text-red-700' : item.priority === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                  {item.priority}
                </span>
              </div>
            ))}
            {completed.length > 0 && (
              <details className="mt-3">
                <summary className="text-xs cursor-pointer font-medium" style={{ color: 'var(--text-muted)' }}>
                  {completed.length} completed
                </summary>
                <div className="mt-2 space-y-1">
                  {completed.map(item => (
                    <div key={item.id} className="flex items-center gap-3 p-2 rounded-lg opacity-60" style={{ background: 'var(--bg-tertiary)' }}>
                      <CheckCircle2 size={16} className="text-emerald-500 shrink-0" />
                      <span className="text-sm line-through truncate" style={{ color: 'var(--text-secondary)' }}>{item.title}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}
      </div>

      {/* Appointments */}
      <div className="rounded-2xl p-5" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
        <h2 className="font-semibold flex items-center gap-2 mb-4" style={{ color: 'var(--text-primary)' }}>
          <Calendar size={18} className="text-blue-500" /> Extracted Appointments
          {appointments.length > 0 && <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">{appointments.length}</span>}
        </h2>

        {appointments.length === 0 ? (
          <div className="py-8 text-center">
            <Clock size={32} className="mx-auto mb-2" style={{ color: 'var(--text-muted)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              {gmailStatus?.connected
                ? 'No appointments found yet. Avira scans emails for dates and meetings.'
                : 'Connect Gmail to auto-detect appointments from your inbox.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {appointments.map(appt => (
              <div key={appt.id} className="flex items-center gap-3 p-3 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0" style={{ background: 'var(--bg-secondary)' }}>
                  <Calendar size={16} style={{ color: 'var(--accent-primary)' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{appt.title}</p>
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {appt.date_time}
                    {appt.description && <span> · {appt.description.slice(0, 80)}</span>}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Future Integrations Tease */}
      <div className="grid sm:grid-cols-2 gap-4">
        {[
          { name: 'Google Calendar', desc: 'Sync events & reminders', icon: Calendar, color: 'text-blue-500', bgColor: 'bg-blue-50' },
          { name: 'Schoology / LMS', desc: 'Track assignments & grades', icon: AlertCircle, color: 'text-purple-500', bgColor: 'bg-purple-50' },
        ].map(svc => (
          <div key={svc.name} className="rounded-2xl p-4 flex items-center gap-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${svc.bgColor}`}>
              <svc.icon size={20} className={svc.color} />
            </div>
            <div className="flex-1">
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{svc.name}</p>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{svc.desc}</p>
            </div>
            <span className="text-[10px] px-2 py-1 rounded-full font-medium" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>Coming Soon</span>
          </div>
        ))}
      </div>
    </div>
  )
}
