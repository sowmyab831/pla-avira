import client from './client'

export const notificationsApi = {
  getPrefs: () => client.get('/api/notifications/preferences').then(r => r.data),
  updatePrefs: (prefs: any) => client.put('/api/notifications/preferences', prefs).then(r => r.data),
  testTelegram: () => client.post('/api/notifications/test/telegram').then(r => r.data),
  testWhatsApp: () => client.post('/api/notifications/test/whatsapp').then(r => r.data),
  testEmail: () => client.post('/api/notifications/test/email').then(r => r.data),
  telegramStatus: () => client.get('/api/telegram/status').then(r => r.data),
  telegramBind: (chatId: string) => client.post('/api/telegram/bind', { chat_id: chatId }).then(r => r.data),
}
