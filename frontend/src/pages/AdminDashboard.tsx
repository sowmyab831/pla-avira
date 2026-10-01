import { useCallback, useEffect, useState } from 'react'
import { Crown, Users, RefreshCw, Plus, ShieldCheck, Key, Activity } from 'lucide-react'
import { subscriptionApi } from '../api/subscription'
import client from '../api/client'

type Tab = 'users' | 'health'

export default function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('users')
  const [data, setData] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '', tier: 'free', role: 'user' })
  const [health, setHealth] = useState<any>(null)
  const [healthLoading, setHealthLoading] = useState(false)

  const load = useCallback(async () => { setLoading(true); setMsg(''); try { setData(await subscriptionApi.adminUsers()) } catch (e: any) { setMsg(e?.response?.data?.detail || 'Failed to load'); } finally { setLoading(false) } }, [])
  useEffect(() => { load() }, [load])

  const loadHealth = useCallback(async () => {
    setHealthLoading(true)
    try {
      const r = await client.get('/health')
      setHealth(r.data)
    } catch { setHealth(null) }
    finally { setHealthLoading(false) }
  }, [])
  useEffect(() => { if (tab === 'health') loadHealth() }, [tab, loadHealth])

  const setTier = async (id: string, tier: string) => { setMsg(''); try { const r = await subscriptionApi.setTier(id, tier); setMsg(`Updated ${r.user_id} to ${r.tier}`); load() } catch (e: any) { setMsg(String(e?.response?.data?.detail || 'Error')) } }
  const reset = async (id: string) => { setMsg(''); try { const r = await subscriptionApi.resetUsage(id); setMsg(`Reset ${r.buckets_cleared} usage buckets`); load() } catch (e: any) { setMsg(String(e?.response?.data?.detail || 'Error')) } }
  const create = async () => { setMsg(''); try { const r = await subscriptionApi.createUser(newUser); setMsg(`Created ${r.username} (${r.user_id})`); setNewUser({ username: '', email: '', password: '', tier: 'free', role: 'user' }); load() } catch (e: any) { setMsg(String(e?.response?.data?.detail || 'Error')) } }

  if (loading && !data) return <div className="p-8 text-sm" style={{ color: 'var(--text-muted)' }}>Loading admin panel…</div>
  if (!data) return (
    <div className="p-8 space-y-3">
      <div className="rounded-xl border-2 border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">
        {msg || 'Failed to load admin data. Check that you are signed in with an admin account.'}
      </div>
      <button onClick={load} className="text-xs px-3 py-2 rounded-lg bg-indigo-600 text-white flex items-center gap-1">
        <RefreshCw size={14} /> Retry
      </button>
    </div>
  )

  const tabs: { id: Tab; label: string; icon: any }[] = [
    { id: 'users', label: 'Users & Keys', icon: Users },
    { id: 'health', label: 'System Health', icon: Activity },
  ]

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3">
        <ShieldCheck size={28} style={{ color: 'var(--accent-primary)' }} />
        <div>
          <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Admin Dashboard</h1>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Manage users, tiers, usage and system health.</p>
        </div>
        <button onClick={tab === 'health' ? loadHealth : load} className="ml-auto p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}><RefreshCw size={16} /></button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
        {tabs.map(t => {
          const Icon = t.icon
          return (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${tab === t.id ? 'shadow-sm' : ''}`}
              style={{ background: tab === t.id ? 'var(--card-bg)' : 'transparent', color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)' }}>
              <Icon size={16} /> {t.label}
            </button>
          )
        })}
      </div>

      {msg && <div className="rounded-xl px-4 py-2 text-sm" style={{ background: msg.includes('Updated') || msg.includes('Created') || msg.includes('Reset') ? '#10b98120' : '#f59e0b20', color: msg.includes('Updated') || msg.includes('Created') || msg.includes('Reset') ? '#047857' : '#b45309' }}>{msg}</div>}

      {/* ========== Users & Keys Tab ========== */}
      {tab === 'users' && (
        <>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="rounded-2xl p-5 space-y-3" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
              <h2 className="font-semibold flex items-center gap-2"><Key size={18} /> Test Activation Keys</h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Users can redeem these at Subscription → Enter key.</p>
              <div className="space-y-2 text-sm">
                {Object.entries(data.activation_keys).map(([tier, key]: any) => (
                  <div key={tier} className="flex items-center justify-between gap-2 p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                    <span className="font-semibold capitalize"><Crown size={14} className="inline mr-1" />{tier}</span>
                    <code className="text-xs px-2 py-1 rounded bg-black/10 select-all">{key}</code>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-2xl p-5 space-y-3" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
              <h2 className="font-semibold flex items-center gap-2"><Plus size={18} /> Create Test Account</h2>
              <div className="grid grid-cols-2 gap-2">
                <input value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} placeholder="username" className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
                <input value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} placeholder="email" className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
                <input value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} placeholder="password" className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }} />
                <select value={newUser.tier} onChange={e => setNewUser({ ...newUser, tier: e.target.value })} className="px-3 py-2 rounded-lg text-sm" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
                  {data.tiers.map((t: string) => <option key={t}>{t}</option>)}
                </select>
              </div>
              <button onClick={create} disabled={!newUser.username || !newUser.email || !newUser.password} className="w-full py-2 rounded-lg text-white text-sm disabled:opacity-40" style={{ background: '#4f46e5' }}>Create Account</button>
            </div>
          </div>

          <div className="rounded-2xl overflow-hidden" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
            <div className="p-4 flex items-center gap-2 border-b" style={{ borderColor: 'var(--border-color)' }}><Users size={18} /> <h2 className="font-semibold">Users</h2></div>
            <table className="w-full text-sm">
              <thead style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
                <tr>
                  <th className="text-left px-4 py-2">User</th>
                  <th className="text-left px-4 py-2">Tier</th>
                  <th className="text-left px-4 py-2">Role</th>
                  <th className="text-left px-4 py-2">Created</th>
                  <th className="text-left px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((u: any) => (
                  <tr key={u.user_id} className="border-t" style={{ borderColor: 'var(--border-color)' }}>
                    <td className="px-4 py-3">
                      <p style={{ color: 'var(--text-primary)' }}>{u.username}</p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{u.email}</p>
                      <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-muted)' }}>{u.user_id}</p>
                    </td>
                    <td className="px-4 py-3">
                      <select value={u.tier} onChange={e => setTier(u.user_id, e.target.value)} className="px-2 py-1 rounded-lg text-xs" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
                        {data.tiers.map((t: string) => <option key={t}>{t}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-3" style={{ color: 'var(--text-secondary)' }}>{u.role}</td>
                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>{u.created_at ? new Date(u.created_at).toLocaleDateString() : ''}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => reset(u.user_id)} className="text-xs px-2 py-1 rounded-lg" style={{ background: 'var(--bg-tertiary)', color: 'var(--accent-primary)' }}>Reset usage</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ========== System Health Tab ========== */}
      {tab === 'health' && (
        <div className="rounded-2xl p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
          <div className="flex items-center gap-2 mb-5">
            <Activity size={20} style={{ color: 'var(--accent-primary)' }} />
            <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Infrastructure Status</h2>
          </div>
          {healthLoading ? (
            <div className="flex justify-center py-10"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" /></div>
          ) : health ? (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { label: 'Database (Postgres)', key: 'postgres', desc: 'Primary data store' },
                { label: 'Cache (Redis)', key: 'redis', desc: 'Session & rate-limit cache' },
                { label: 'Vector DB (Qdrant)', key: 'qdrant', desc: 'Embedding search' },
                { label: 'Search (Meili)', key: 'meili', desc: 'Full-text search index' },
                { label: 'AI Engine (Ollama)', key: 'ollama', desc: 'Local LLM inference' },
              ].map(svc => {
                const ok = health[svc.key]
                return (
                  <div key={svc.key} className="p-4 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{svc.label}</span>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                        {ok ? '● Online' : '● Offline'}
                      </span>
                    </div>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{svc.desc}</p>
                  </div>
                )
              })}
              {health.uptime && (
                <div className="p-4 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>Uptime</span>
                  <p className="text-lg font-bold mt-1" style={{ color: 'var(--text-primary)' }}>{health.uptime}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-red-500">Failed to reach health endpoint. Is the backend running?</p>
          )}
        </div>
      )}
    </div>
  )
}
