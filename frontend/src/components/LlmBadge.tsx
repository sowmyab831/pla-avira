import { Cpu, Database, Lock, Sparkles } from 'lucide-react'

export interface LlmUsed {
  model: string
  provider?: string
  host?: string
  private?: boolean
  temperature?: number
  available?: boolean
}

/** Small chip that tells the user which LLM (and where) produced this view. */
export function LlmBadge({ llm, sources, compact }: {
  llm?: LlmUsed
  sources?: string[]
  compact?: boolean
}) {
  if (!llm && !sources?.length) return null
  return (
    <div
      className={`inline-flex items-center gap-2 px-2 py-1 rounded-lg border text-xs ${
        compact ? '' : 'shadow-sm'
      }`}
      style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}
      title={llm?.host || ''}
    >
      {llm && (
        <>
          <Sparkles size={12} className="text-indigo-500" />
          <span className="font-mono">{llm.model}</span>
          {llm.provider && <span className="opacity-60">· {llm.provider}</span>}
          {llm.private && (
            <span className="flex items-center gap-1 text-emerald-700">
              <Lock size={10} /> local
            </span>
          )}
          {llm.available === false && (
            <span className="text-amber-600">(fallback)</span>
          )}
        </>
      )}
      {sources?.length ? (
        <span className="flex items-center gap-1 opacity-70 ml-1">
          <Database size={12} /> {sources.slice(0, 3).join(', ')}
          {sources.length > 3 && <span>+{sources.length - 3}</span>}
        </span>
      ) : null}
    </div>
  )
}

/** Badge for gateway responses: actual provider/model, local vs cloud, fallback, cost. */
export function AIResponseBadge({ meta }: { meta?: import('../api/ai').AIMeta | null }) {
  if (!meta) return null
  if (meta.error) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[11px] bg-amber-50 text-amber-800 border border-amber-200" title={meta.error.message}>
        ⚠ {meta.error.code.replace(/_/g, ' ')}
      </span>
    )
  }
  if (!meta.model) return null
  const local = meta.locality === 'local'
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 px-2 py-0.5 rounded-lg text-[11px] border"
      style={{ borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
      title={`request ${meta.request_id || ''} · ${meta.latency_ms ?? '?'} ms · ${meta.usage?.input_tokens ?? '?'} in / ${meta.usage?.output_tokens ?? '?'} out tokens`}>
      <Sparkles size={11} className="text-indigo-500" />
      <span className="font-mono">{meta.model}</span>
      <span className="opacity-60">· {meta.provider}</span>
      {local ? <span className="flex items-center gap-0.5 text-emerald-700"><Lock size={10} /> local</span>
        : <span className="text-sky-700">cloud</span>}
      {meta.fallback_from && <span className="text-amber-700" title={`fell back from ${meta.fallback_from}: ${meta.fallback_reason || ''}`}>fallback</span>}
      {meta.mode && <span className="opacity-60">{meta.mode}</span>}
      {!local && meta.cost_micro_usd != null && (
        <span className="opacity-80">{meta.cost_final ? '' : '~'}${(meta.cost_micro_usd / 1_000_000).toFixed(4)}</span>
      )}
      {meta.cached && <span className="opacity-60">cached</span>}
    </span>
  )
}

export function ModelStackPill({ stack }: { stack?: string[] }) {
  if (!stack?.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {stack.map(s => (
        <span
          key={s}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono"
          style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
        >
          <Cpu size={9} />
          {s}
        </span>
      ))}
    </div>
  )
}
