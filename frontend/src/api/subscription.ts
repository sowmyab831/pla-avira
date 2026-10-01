import client from './client'

export const subscriptionApi = {
  status: () => client.get('/api/subscription/status').then(r => r.data),
  usage: () => client.get('/api/subscription/usage').then(r => r.data),
  activate: (key: string) => client.post('/api/subscription/activate', { key }).then(r => r.data),
  adminUsers: () => client.get('/api/subscription/admin/users').then(r => r.data),
  setTier: (userId: string, tier: string) => client.patch(`/api/subscription/admin/users/${userId}/tier`, { tier }).then(r => r.data),
  resetUsage: (userId: string) => client.post(`/api/subscription/admin/users/${userId}/reset-usage`).then(r => r.data),
  createUser: (body: any) => client.post('/api/subscription/admin/users', body).then(r => r.data),
}
