import { useEffect, useState } from 'react'
import { Cloud, Lock, Settings2 } from 'lucide-react'
import { aiApi, Catalog } from '../api/ai'

/**
 * Per-conversation model override. Empty value = follow the user's saved preferences.
 * Only models the policy currently permits are selectable; disabled ones show why.
 */
export function ModelSelector({ value, onChange, task }: { value: string; onChange: (key: string) => void; task?: string }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  useEffect(() => { aiApi.catalog(task).then(setCatalog).catch(() => setCatalog(null)) }, [task])
  if (!catalog) return null
  const selected = catalog.models.find(m => m.key === value)
  return (
    <label className="inline-flex items-center gap-2 text-xs" style={{ color: 'var(--text-secondary)' }} title="Model for this conversation only">
      <Settings2 size={13} />
      <span className="sr-only">Model for this conversation</span>
      <select value={value} onChange={e => onChange(e.target.value)} className="rounded-lg px-2 py-1 max-w-[220px]"
        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}>
        <option value="">Use my default</option>
        {catalog.models.map(m => (
          <option key={m.key} value={m.key} disabled={!m.selectable} title={m.disabled_reason || ''}>
            {m.locality === 'local' ? '🔒 ' : '☁ '}{m.display_name}{m.selectable ? '' : ' — unavailable'}
          </option>
        ))}
      </select>
      {selected && (selected.locality === 'local'
        ? <span className="flex items-center gap-1 text-emerald-700"><Lock size={11} /> local</span>
        : <span className="flex items-center gap-1 text-sky-700"><Cloud size={11} /> cloud</span>)}
      <span className="opacity-60">this conversation</span>
    </label>
  )
}
