import client from './client'

export interface NexusAction {
  domain: string
  action: string
  params: Record<string, any>
  safe: boolean
  status?: 'pending' | 'applied' | 'undone' | 'failed' | 'skipped'
  result?: Record<string, any> | null
  error?: string
}

export interface NexusEvent {
  id: string
  source: string
  type: string
  summary: string | null
  payload: Record<string, any> | null
  actions: NexusAction[]
  status: 'proposed' | 'applied' | 'undone' | 'rejected'
  auto_applied: boolean
  created_at: string | null
  applied_at: string | null
  undone_at: string | null
}

export interface IngestResult {
  actions: NexusAction[]
  unparsed: string[]
  reply: string
  event: NexusEvent | null
  transcript?: string
  audio_b64?: string
  audio_mime?: string
}

export interface Brief {
  date: string
  greeting: string
  spoken: string
  events: { id: string; title: string; at: string; location?: string; kind: string }[]
  reminders: { id: string; title: string; at: string; kind: string }[]
  medications: { id: string; name: string; dose?: string; times: string[]; taken_today: boolean }[]
  fasting: { protocol: string; state: string; next_change: string } | null
  radar: RadarSignal[]
  expiring: { id: string; name: string; expires_on: string }[]
  shopping_open: number
  pending_confirmations: number
  month_spend: number
  chores: { id: string; title: string; who: string | null; done: boolean }[]
}

export interface RadarSignal {
  id: string
  account_id?: string
  category: string
  subject: string
  sender_name?: string
  sender_domain?: string
  received_at?: string | null
  amount: number | null
  due_date: string | null
  priority: 'high' | 'medium' | 'low'
  deep_link: string | null
  suggested_reply?: string | null
  status?: string
  nexus_event_id?: string | null
}

export const nexusApi = {
  ingest: (text: string, opts: { source?: string; auto_apply?: boolean; dry_run?: boolean; use_llm?: boolean } = {}) =>
    client.post<IngestResult>('/api/nexus/ingest', { text, source: 'text', auto_apply: true, ...opts }).then(r => r.data),
  events: (status?: string) => client.get<{ events: NexusEvent[] }>('/api/nexus/events', { params: { status } }).then(r => r.data.events),
  confirm: (id: string, action_indexes?: number[]) => client.post<NexusEvent>(`/api/nexus/events/${id}/confirm`, { action_indexes }).then(r => r.data),
  reject: (id: string) => client.post<NexusEvent>(`/api/nexus/events/${id}/reject`).then(r => r.data),
  undo: (id: string) => client.post<NexusEvent>(`/api/nexus/events/${id}/undo`).then(r => r.data),
  brief: () => client.get<Brief>('/api/nexus/brief').then(r => r.data),
  receiptText: (text: string, store?: string) => client.post('/api/nexus/receipt', { text, store }).then(r => r.data),
  receiptUpload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return client.post('/api/nexus/receipt/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
  },
  mealIdeas: () => client.get<{ ideas: { title: string; uses: string[]; missing: string[]; minutes: number }[] }>('/api/nexus/meal-ideas').then(r => r.data.ideas),
}

export const radarApi = {
  providers: () => client.get('/api/radar/providers').then(r => r.data.providers as Record<string, { host: string; help: string }>),
  accounts: () => client.get('/api/radar/accounts').then(r => r.data.accounts as { id: string; email: string; provider: string; last_sync: string | null }[]),
  addAccount: (body: { email: string; app_password: string; provider: string; imap_host?: string }) => client.post('/api/radar/accounts', body).then(r => r.data),
  removeAccount: (id: string) => client.delete(`/api/radar/accounts/${id}`).then(r => r.data),
  sync: (days = 14) => client.post('/api/radar/sync', null, { params: { days } }).then(r => r.data),
  signals: (status = 'open') => client.get<{ signals: RadarSignal[]; counts: Record<string, number> }>('/api/radar/signals', { params: { status } }).then(r => r.data),
  update: (id: string, status: string, snooze_days = 3) => client.patch(`/api/radar/signals/${id}`, { status, snooze_days }).then(r => r.data),
  demo: (emails: { from: string; subject: string; snippet?: string }[]) => client.post('/api/radar/demo', { emails }).then(r => r.data),
}

export const careApi = {
  meds: () => client.get('/api/care/medications').then(r => r.data.medications as any[]),
  addMed: (body: any) => client.post('/api/care/medications', body).then(r => r.data),
  logMed: (id: string, taken: boolean) => client.post(`/api/care/medications/${id}/log`, { taken }).then(r => r.data),
  deleteMed: (id: string) => client.delete(`/api/care/medications/${id}`).then(r => r.data),
  adherence: () => client.get('/api/care/medications/adherence').then(r => r.data),
  fasting: () => client.get('/api/care/fasting').then(r => r.data),
  setFasting: (body: any) => client.post('/api/care/fasting', body).then(r => r.data),
  logFast: (kept: boolean) => client.post('/api/care/fasting/log', { kept }).then(r => r.data),
  biometrics: () => client.get('/api/care/biometrics').then(r => r.data as { series: Record<string, { t: string; v: number; unit?: string }[]>; trends: Record<string, any> }),
  addBiometric: (metric: string, value: number, unit?: string) => client.post('/api/care/biometrics', { metric, value, unit }).then(r => r.data),
  checkins: () => client.get('/api/care/checkins').then(r => r.data),
  checkin: (kind: string, value = 'yes') => client.post('/api/care/checkins', { kind, value }).then(r => r.data),
  dueNow: () => client.get('/api/care/due-now').then(r => r.data.prompts as any[]),
  microWorkout: (minutes = 5) => client.get('/api/care/micro-workout', { params: { minutes } }).then(r => r.data),
  insights: () => client.get('/api/care/insights').then(r => r.data as { insights: string[]; habit: string }),
}

export const pantryApi = {
  list: () => client.get('/api/pantry').then(r => r.data),
  add: (body: any) => client.post('/api/pantry', body).then(r => r.data),
  update: (id: string, body: any) => client.patch(`/api/pantry/${id}`, body).then(r => r.data),
  remove: (id: string) => client.delete(`/api/pantry/${id}`).then(r => r.data),
  receipts: () => client.get('/api/pantry/receipts').then(r => r.data.receipts as any[]),
  shopping: () => client.get('/api/pantry/shopping').then(r => r.data.items as any[]),
  addShopping: (name: string) => client.post('/api/pantry/shopping', { name }).then(r => r.data),
  toggleShopping: (id: string, checked: boolean) => client.patch(`/api/pantry/shopping/${id}`, { checked }).then(r => r.data),
  clearChecked: () => client.post('/api/pantry/shopping/clear-checked').then(r => r.data),
  transactions: (days = 30) => client.get('/api/pantry/transactions', { params: { days } }).then(r => r.data),
}

export const familyApi = {
  members: () => client.get('/api/family-hub/members').then(r => r.data),
  addMember: (body: any) => client.post('/api/family-hub/members', body).then(r => r.data),
  updateMember: (id: string, body: any) => client.patch(`/api/family-hub/members/${id}`, body).then(r => r.data),
  removeMember: (id: string) => client.delete(`/api/family-hub/members/${id}`).then(r => r.data),
  oversight: () => client.get('/api/family-hub/oversight').then(r => r.data),
  chores: () => client.get('/api/family-hub/chores').then(r => r.data),
  addChore: (body: any) => client.post('/api/family-hub/chores', body).then(r => r.data),
  choreDone: (id: string, undo = false) => client.post(`/api/family-hub/chores/${id}/done`, null, { params: { undo } }).then(r => r.data),
  calendar: (days = 14) => client.get('/api/family-hub/calendar', { params: { days } }).then(r => r.data.events as any[]),
  deleteEvent: (id: string) => client.delete(`/api/family-hub/calendar/${id}`).then(r => r.data),
  reminders: () => client.get('/api/family-hub/reminders').then(r => r.data.reminders as any[]),
  updateReminder: (id: string, body: any) => client.patch(`/api/family-hub/reminders/${id}`, body).then(r => r.data),
  milestones: () => client.get('/api/family-hub/milestones').then(r => r.data.milestones as any[]),
  babysitter: (hours = 6) => client.get('/api/family-hub/babysitter-sheet', { params: { hours } }).then(r => r.data),
  packing: (body: any) => client.post('/api/family-hub/packing-list', body).then(r => r.data),
  worksheet: (body: any) => client.post('/api/family-hub/worksheet', body).then(r => r.data),
}

export const voiceApi = {
  capabilities: () => client.get('/api/voice/capabilities').then(r => r.data as { server_stt: boolean; server_tts: boolean }),
  tts: async (text: string): Promise<Blob | null> => {
    const r = await client.post('/api/voice/tts', { text }, { responseType: 'blob', validateStatus: s => s === 200 || s === 204 })
    return r.status === 200 ? (r.data as Blob) : null
  },
}
