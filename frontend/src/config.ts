// API Configuration
// In production (K8s), the backend is on port 30000
// Use the same hostname as the frontend but with port 30000
// For local Vite dev, set VITE_API_BASE (e.g. http://localhost:30002)
const API_BASE = import.meta.env.VITE_API_BASE || (typeof window !== 'undefined'
  ? `${window.location.protocol}//${window.location.hostname}:30000`
  : 'http://localhost:30000');

export const config = {
  apiBase: API_BASE,
  duckdns: {
    domain: 'aviraa.duckdns.org',
    ip: '65.188.101.168',
  },
  endpoints: {
    // Health check
    health: `${API_BASE}/health`,
    
    // Calendar
    calendarEvents: `${API_BASE}/api/calendar/events`,
    calendarUpcoming: `${API_BASE}/api/calendar/upcoming`,
    calendarUploadPdf: `${API_BASE}/api/calendar/upload-pdf`,
    calendarUploadCsv: `${API_BASE}/api/calendar/upload-csv`,
    calendarActionableItem: `${API_BASE}/api/calendar/actionable-item`,
    calendarActionableItems: `${API_BASE}/api/calendar/actionable-items`,
    calendarAppointment: `${API_BASE}/api/calendar/appointment`,
    calendarAppointments: `${API_BASE}/api/calendar/appointments`,
    calendarSyncAllSchools: `${API_BASE}/api/calendar/sync-all-schools`,
    calendarSchools: `${API_BASE}/api/calendar/schools`,
    calendarHolidays: `${API_BASE}/api/calendar/holidays`,
    calendarLoadUsHolidays: `${API_BASE}/api/calendar/load-us-holidays`,
    
    // School
    schoologyAuth: `${API_BASE}/api/school/schoology/auth`,
    schoologyStatus: `${API_BASE}/api/school/schoology/status`,
    schoologyCourses: `${API_BASE}/api/school/schoology/courses`,
    schoologyAssignments: `${API_BASE}/api/school/schoology/assignments`,
    
    // Health (lab results)
    healthUploadLabResults: `${API_BASE}/api/health/upload-lab-results`,
    healthReport: `${API_BASE}/api/health/report`,
    healthTimeline: `${API_BASE}/api/health/timeline`,
    healthSummary: `${API_BASE}/api/health/summary`,
    
    // Finance
    financeUploadStatement: `${API_BASE}/api/finance/upload-statement`,
    financeSummary: `${API_BASE}/api/finance/summary`,
    
    // Bills
    billsUpload: `${API_BASE}/api/bills/upload`,
    billsList: `${API_BASE}/api/bills`,
    billsSummary: `${API_BASE}/api/bills/summary`,
    billsSpendingHabits: `${API_BASE}/api/bills/spending-habits`,
    
    // Gmail
    gmailAuth: `${API_BASE}/api/integrations/gmail/auth`,
    gmailStatus: `${API_BASE}/api/integrations/gmail/status`,
    gmailEmails: `${API_BASE}/api/integrations/gmail/emails`,
    actionItems: `${API_BASE}/api/integrations/action-items`,
    appointments: `${API_BASE}/api/integrations/appointments`,
    
    // Multi-Modal Assistant
    assistantChat: `${API_BASE}/api/assistant/chat`,
    assistantSessions: `${API_BASE}/api/assistant/sessions`,
    assistantPrivacyCheck: `${API_BASE}/api/assistant/privacy/check`,
    assistantPrivacyMask: `${API_BASE}/api/assistant/privacy/mask`,
    assistantStats: `${API_BASE}/api/assistant/stats`,
    
    // Legacy Chat
    chat: `${API_BASE}/api/chat`,
  }
}

export default config
