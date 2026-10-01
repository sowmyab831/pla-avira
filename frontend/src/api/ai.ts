import client from './client'

export type Locality = 'local' | 'cloud'
export type Mode = 'auto' | 'choose' | 'local_only'
export type Profile = 'economy' | 'balanced' | 'quality'

export interface CatalogModel {
  key: string
  provider: string
  provider_label: string
  model_id: string
  display_name: string
  capabilities: string[]
  tier: Profile
  context_window: number | null
  locality: Locality
  lifecycle: string
  price_known: boolean
  price: { input_per_1m_micro_usd: number; output_per_1m_micro_usd: number; cached_input_per_1m_micro_usd: number | null } | null
  selectable: boolean
  disabled_reason: string | null
  configured: boolean
  source_url: string
  notes: string
}

export interface Catalog {
  verified_at: string
  cloud_enabled: boolean
  byok_enabled: boolean
  providers: Record<string, { label: string; locality: Locality; docs: string; configured: boolean }>
  models: CatalogModel[]
}

export interface Preferences {
  mode: Mode
  profile: Profile
  default_provider: string | null
  default_model: string | null
  per_task: Record<string, { provider: string; model: string }>
  fallback_providers: string[]
  cloud_allowed: boolean
  max_data_class_cloud: 'public' | 'masked' | 'personal' | 'sensitive'
  detail_level: 'brief' | 'normal' | 'detailed'
  monthly_cap_micro_usd: number | null
  version: number
  effective_cloud?: boolean
}

export interface Connection {
  id: string
  provider: string
  label: string
  owner_kind: 'user' | 'org' | 'platform'
  secret_hint: string | null
  status: 'untested' | 'ok' | 'invalid' | 'revoked' | 'configured'
  last_checked_at: string | null
  last_error: string | null
  endpoint_ref: string | null
  editable: boolean
  billed_to: string
}

export interface Usage {
  period: string
  accounts: { funding: 'platform' | 'byok'; limit_micro_usd: number | null; spent_micro_usd: number; reserved_micro_usd: number; pending_micro_usd: number; remaining_micro_usd: number | null }[]
  by_task: Record<string, { requests: number; micro_usd: number; funding: string }>
  by_provider: Record<string, { requests: number; micro_usd: number; funding: string }>
  requests_with_unknown_cost: number
  note: string
  resets_on: string
}

/** Metadata the gateway attaches to every answer (drives the response badge). */
export interface AIMeta {
  request_id?: string
  provider?: string
  model?: string
  locality?: Locality
  mode?: string
  fallback_from?: string | null
  fallback_reason?: string | null
  finish?: string
  usage?: { input_tokens: number; output_tokens: number; estimated: boolean }
  cost_micro_usd?: number
  cost_final?: boolean
  latency_ms?: number
  cached?: boolean
  error?: { code: string; message: string; retryable: boolean }
}

export const aiApi = {
  catalog: (task?: string) => client.get<Catalog>('/api/ai/catalog', { params: task ? { task } : {} }).then(r => r.data),
  getPreferences: () => client.get<Preferences>('/api/ai/preferences').then(r => r.data),
  putPreferences: (p: Preferences) => client.put('/api/ai/preferences', p).then(r => r.data as { success: boolean; version: number }),
  connections: () => client.get<{ connections: Connection[]; byok_enabled: boolean; compat_endpoints: string[] }>('/api/ai/connections').then(r => r.data),
  addConnection: (body: { provider: string; api_key: string; label?: string; owner_kind?: string; endpoint_ref?: string }) =>
    client.post<Connection>('/api/ai/connections', body).then(r => r.data),
  testConnection: (id: string) => client.post(`/api/ai/connections/${id}/test`).then(r => r.data as { ok: boolean; detail: string; checked_at: string; models_visible: number }),
  replaceConnection: (id: string, api_key: string, label?: string) => client.put<Connection>(`/api/ai/connections/${id}`, { api_key, label }).then(r => r.data),
  revokeConnection: (id: string) => client.delete(`/api/ai/connections/${id}`),
  usage: (period?: string) => client.get<Usage>('/api/ai/usage', { params: period ? { period } : {} }).then(r => r.data),
  estimate: (provider: string, model: string, prompt_chars: number, max_output_tokens = 1024) =>
    client.post('/api/ai/estimate', { provider, model, prompt_chars, max_output_tokens }).then(r => r.data),
}

export const usd = (micro: number | null | undefined) =>
  micro == null ? '—' : `$${(micro / 1_000_000).toFixed(micro < 10_000 ? 4 : 2)}`
