import { useState, useEffect } from 'react'
import { Wrench, Home as HomeIcon, Car, CheckCircle2, Circle, AlertTriangle, Plus, Trash2 } from 'lucide-react'
import config from '../config'

interface ChecklistItem {
  template_id: string
  category: string
  task: string
  season: string
  interval_months: number
  why?: string
  status: string
  last_done?: string | null
  next_due?: string | null
  overdue: boolean
}

interface Appliance {
  id?: string
  name?: string
  appliance_type?: string
  age_years?: number
  lifespan_pct?: number
  warranty_until?: string
  alerts?: string[]
}

interface Repair {
  id?: string
  title?: string
  description?: string
  date?: string
  created_at?: string
  cost?: number
  vendor?: string
}

const authHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('auth_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export default function Maintenance() {
  const [tab, setTab] = useState<'checklist' | 'appliances' | 'repairs'>('checklist')
  const [category, setCategory] = useState<'home' | 'vehicle'>('home')
  const [items, setItems] = useState<ChecklistItem[]>([])
  const [progress, setProgress] = useState<{ total: number; done: number; overdue: number } | null>(null)
  const [appliances, setAppliances] = useState<Appliance[]>([])
  const [repairs, setRepairs] = useState<Repair[]>([])
  const [loading, setLoading] = useState(false)

  // Add-appliance form
  const [showAddAppliance, setShowAddAppliance] = useState(false)
  const [newAppliance, setNewAppliance] = useState({ name: '', appliance_type: 'refrigerator', purchase_date: '' })

  // Add-repair form
  const [showAddRepair, setShowAddRepair] = useState(false)
  const [newRepair, setNewRepair] = useState({ title: '', cost: '', vendor: '', date: '' })

  useEffect(() => {
    fetchChecklist()
    fetchAppliances()
    fetchRepairs()
  }, [])

  useEffect(() => {
    fetchChecklist()
  }, [category])

  const fetchChecklist = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${config.apiBase}/api/maintenance/checklist?category=${category}`, { headers: authHeaders() })
      const data = await res.json()
      if (data.success) {
        setItems(data.items || [])
        setProgress(data.progress || null)
      }
    } catch (e) {
      console.error('Checklist fetch error:', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchAppliances = async () => {
    try {
      const res = await fetch(`${config.apiBase}/api/maintenance/appliances`, { headers: authHeaders() })
      const data = await res.json()
      if (data.success) setAppliances(data.appliances || data.items || [])
    } catch (e) {
      console.error('Appliances fetch error:', e)
    }
  }

  const fetchRepairs = async () => {
    try {
      const res = await fetch(`${config.apiBase}/api/maintenance/repairs`, { headers: authHeaders() })
      const data = await res.json()
      if (data.success) setRepairs(data.repairs || data.items || [])
    } catch (e) {
      console.error('Repairs fetch error:', e)
    }
  }

  const markDone = async (templateId: string) => {
    try {
      await fetch(`${config.apiBase}/api/maintenance/checklist/${templateId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ status: 'done' }),
      })
      fetchChecklist()
    } catch (e) {
      console.error('Mark done error:', e)
    }
  }

  const addAppliance = async () => {
    if (!newAppliance.name) return
    try {
      await fetch(`${config.apiBase}/api/maintenance/appliances`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          name: newAppliance.name,
          appliance_type: newAppliance.appliance_type,
          purchase_date: newAppliance.purchase_date || null,
        }),
      })
      setShowAddAppliance(false)
      setNewAppliance({ name: '', appliance_type: 'refrigerator', purchase_date: '' })
      fetchAppliances()
    } catch (e) {
      console.error('Add appliance error:', e)
    }
  }

  const deleteAppliance = async (id?: string) => {
    if (!id) return
    try {
      await fetch(`${config.apiBase}/api/maintenance/appliances/${id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      fetchAppliances()
    } catch (e) {
      console.error('Delete appliance error:', e)
    }
  }

  const addRepair = async () => {
    if (!newRepair.title) return
    try {
      await fetch(`${config.apiBase}/api/maintenance/repairs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          title: newRepair.title,
          cost: newRepair.cost ? parseFloat(newRepair.cost) : null,
          vendor: newRepair.vendor || null,
          date: newRepair.date || null,
        }),
      })
      setShowAddRepair(false)
      setNewRepair({ title: '', cost: '', vendor: '', date: '' })
      fetchRepairs()
    } catch (e) {
      console.error('Add repair error:', e)
    }
  }

  const tabs = [
    { id: 'checklist' as const, label: 'Checklist', icon: CheckCircle2 },
    { id: 'appliances' as const, label: 'Appliances', icon: Wrench },
    { id: 'repairs' as const, label: 'Repair Log', icon: AlertTriangle },
  ]

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-amber-500 to-orange-600 rounded-xl flex items-center justify-center">
            <Wrench className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Maintenance Hub</h1>
            <p className="text-gray-600">Home & vehicle care, appliances, and repair history</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {tabs.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                tab === t.id ? 'bg-amber-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:border-amber-300'
              }`}
            >
              <Icon size={16} /> {t.label}
            </button>
          )
        })}
      </div>

      {/* Checklist tab */}
      {tab === 'checklist' && (
        <div>
          <div className="flex items-center gap-4 mb-4">
            <div className="flex bg-gray-100 rounded-lg p-1">
              {([{ id: 'home' as const, label: 'Home', icon: HomeIcon }, { id: 'vehicle' as const, label: 'Vehicle', icon: Car }]).map(c => {
                const Icon = c.icon
                return (
                  <button
                    key={c.id}
                    onClick={() => setCategory(c.id)}
                    className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                      category === c.id ? 'bg-white shadow text-amber-700' : 'text-gray-500'
                    }`}
                  >
                    <Icon size={14} /> {c.label}
                  </button>
                )
              })}
            </div>
            {progress && (
              <span className="text-sm text-gray-500">
                {progress.done}/{progress.total} done
                {progress.overdue > 0 && <span className="text-red-600 font-semibold"> · {progress.overdue} overdue</span>}
              </span>
            )}
          </div>

          {loading && <p className="text-gray-500 py-8 text-center">Loading checklist...</p>}

          <div className="space-y-3">
            {items.map(item => (
              <div key={item.template_id} className={`bg-white p-4 rounded-xl border flex items-start gap-4 ${item.overdue ? 'border-red-300' : 'border-gray-200'}`}>
                <button onClick={() => markDone(item.template_id)} className="mt-0.5 flex-shrink-0">
                  {item.status === 'done'
                    ? <CheckCircle2 size={22} className="text-green-600" />
                    : item.overdue
                      ? <AlertTriangle size={22} className="text-red-500" />
                      : <Circle size={22} className="text-gray-300 hover:text-amber-500" />}
                </button>
                <div className="flex-1">
                  <p className={`font-semibold ${item.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-900'}`}>{item.task}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {item.season} · every {item.interval_months}mo
                    {item.next_due && ` · due ${item.next_due}`}
                    {item.last_done && ` · last done ${item.last_done}`}
                  </p>
                  {item.why && <p className="text-xs text-gray-400 mt-1">{item.why}</p>}
                </div>
              </div>
            ))}
            {!loading && items.length === 0 && (
              <p className="text-gray-500 text-center py-8">No checklist items for this category.</p>
            )}
          </div>
        </div>
      )}

      {/* Appliances tab */}
      {tab === 'appliances' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Registered Appliances</h2>
            <button
              onClick={() => setShowAddAppliance(!showAddAppliance)}
              className="flex items-center gap-1.5 px-4 py-2 bg-amber-500 text-white text-sm font-semibold rounded-lg hover:bg-amber-600"
            >
              <Plus size={16} /> Add Appliance
            </button>
          </div>

          {showAddAppliance && (
            <div className="bg-white p-4 rounded-xl border border-amber-200 mb-4 grid md:grid-cols-4 gap-3">
              <input
                type="text" placeholder="Name (e.g. Kitchen Fridge)" value={newAppliance.name}
                onChange={e => setNewAppliance({ ...newAppliance, name: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <select
                value={newAppliance.appliance_type}
                onChange={e => setNewAppliance({ ...newAppliance, appliance_type: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                {['refrigerator', 'washer', 'dryer', 'dishwasher', 'oven', 'hvac', 'water_heater', 'other'].map(t => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                ))}
              </select>
              <input
                type="date" value={newAppliance.purchase_date}
                onChange={e => setNewAppliance({ ...newAppliance, purchase_date: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <button onClick={addAppliance} className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700">
                Save
              </button>
            </div>
          )}

          <div className="space-y-3">
            {appliances.map((a, i) => (
              <div key={a.id || i} className="bg-white p-4 rounded-xl border border-gray-200 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{a.name || a.appliance_type}</p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {a.age_years != null && `${a.age_years} yrs old`}
                    {a.lifespan_pct != null && ` · ${a.lifespan_pct}% of expected lifespan`}
                    {a.warranty_until && ` · warranty until ${a.warranty_until}`}
                  </p>
                  {a.alerts && a.alerts.length > 0 && (
                    <p className="text-xs text-amber-600 font-medium mt-1">{a.alerts.join(' · ')}</p>
                  )}
                </div>
                {a.id && (
                  <button onClick={() => deleteAppliance(a.id)} className="text-gray-400 hover:text-red-500 p-2">
                    <Trash2 size={16} />
                  </button>
                )}
              </div>
            ))}
            {appliances.length === 0 && (
              <p className="text-gray-500 text-center py-8">No appliances registered. Add one to track warranty & lifespan.</p>
            )}
          </div>
        </div>
      )}

      {/* Repairs tab */}
      {tab === 'repairs' && (
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Repair History</h2>
            <button
              onClick={() => setShowAddRepair(!showAddRepair)}
              className="flex items-center gap-1.5 px-4 py-2 bg-amber-500 text-white text-sm font-semibold rounded-lg hover:bg-amber-600"
            >
              <Plus size={16} /> Log Repair
            </button>
          </div>

          {showAddRepair && (
            <div className="bg-white p-4 rounded-xl border border-amber-200 mb-4 grid md:grid-cols-5 gap-3">
              <input
                type="text" placeholder="Repair (e.g. HVAC compressor)" value={newRepair.title}
                onChange={e => setNewRepair({ ...newRepair, title: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm md:col-span-2"
              />
              <input
                type="number" placeholder="Cost ($)" value={newRepair.cost}
                onChange={e => setNewRepair({ ...newRepair, cost: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <input
                type="text" placeholder="Vendor" value={newRepair.vendor}
                onChange={e => setNewRepair({ ...newRepair, vendor: e.target.value })}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              />
              <button onClick={addRepair} className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-lg hover:bg-green-700">
                Save
              </button>
            </div>
          )}

          <div className="space-y-3">
            {repairs.map((r, i) => (
              <div key={r.id || i} className="bg-white p-4 rounded-xl border border-gray-200">
                <p className="font-semibold text-gray-900">{r.title || r.description}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  {r.date || r.created_at || ''}
                  {r.cost != null && ` · $${r.cost}`}
                  {r.vendor && ` · ${r.vendor}`}
                </p>
              </div>
            ))}
            {repairs.length === 0 && (
              <p className="text-gray-500 text-center py-8">No repairs logged yet. Log one to build your service history.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
