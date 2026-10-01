/**
 * API Service for Avira Mobile App
 * Connects to backend via DuckDNS or localhost
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

// Configuration
const CONFIG = {
  // DuckDNS endpoint for external access
  PRODUCTION_API: 'http://aviraa.duckdns.org:30000',
  // Local development
  LOCAL_API: 'http://localhost:30000',
  // Direct IP fallback
  DIRECT_IP_API: 'http://65.188.101.168:30000',
};

class ApiService {
  private baseUrl: string;
  private userId: string = 'mobile-user';
  private sessionId: string = '';

  constructor() {
    this.baseUrl = CONFIG.PRODUCTION_API;
    this.initSession();
  }

  private async request(endpoint: string, options: RequestInit = {}): Promise<any> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  private async initSession() {
    try {
      let storedSession = await AsyncStorage.getItem('sessionId');
      if (!storedSession) {
        storedSession = `mobile_${Date.now()}`;
        await AsyncStorage.setItem('sessionId', storedSession);
      }
      this.sessionId = storedSession;

      const storedUserId = await AsyncStorage.getItem('userId');
      if (storedUserId) {
        this.userId = storedUserId;
      }
    } catch (error) {
      this.sessionId = `mobile_${Date.now()}`;
    }
  }

  setBaseUrl(url: string) {
    this.baseUrl = url;
  }

  async setUserId(userId: string) {
    this.userId = userId;
    await AsyncStorage.setItem('userId', userId);
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const data = await this.request('/health');
      return data.status === 'healthy';
    } catch {
      return false;
    }
  }

  // Test connection to different endpoints
  async testConnection(): Promise<{ url: string; success: boolean }> {
    const urls = [CONFIG.PRODUCTION_API, CONFIG.DIRECT_IP_API, CONFIG.LOCAL_API];
    
    for (const url of urls) {
      try {
        const response = await fetch(`${url}/health`, { 
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();
        if (data.status === 'healthy') {
          this.setBaseUrl(url);
          return { url, success: true };
        }
      } catch {
        continue;
      }
    }
    return { url: '', success: false };
  }

  // ============ Assistant API ============

  async chat(message: string, useExternalLlm: boolean = false): Promise<AssistantResponse> {
    return this.request('/api/assistant/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        session_id: this.sessionId,
        user_id: this.userId,
        use_external_llm: useExternalLlm,
      }),
    });
  }

  async getSessions(): Promise<Session[]> {
    const data = await this.request(`/api/assistant/sessions?user_id=${this.userId}`);
    return data.sessions;
  }

  async loadSession(sessionId: string): Promise<SessionContext> {
    const data = await this.request(
      `/api/assistant/sessions/${sessionId}/load?user_id=${this.userId}`,
      { method: 'POST' }
    );
    this.sessionId = sessionId;
    await AsyncStorage.setItem('sessionId', sessionId);
    return data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.request(`/api/assistant/sessions/${sessionId}?user_id=${this.userId}`, {
      method: 'DELETE',
    });
  }

  async newSession(): Promise<string> {
    this.sessionId = `mobile_${Date.now()}`;
    await AsyncStorage.setItem('sessionId', this.sessionId);
    return this.sessionId;
  }

  // ============ Privacy API ============

  async checkPrivacy(text: string): Promise<PrivacyCheckResult> {
    return this.request('/api/assistant/privacy/check', {
      method: 'POST',
      body: JSON.stringify({
        text,
        user_id: this.userId,
      }),
    });
  }

  async maskText(text: string): Promise<MaskResult> {
    return this.request('/api/assistant/privacy/mask', {
      method: 'POST',
      body: JSON.stringify({
        text,
        user_id: this.userId,
        session_id: this.sessionId,
      }),
    });
  }

  // ============ Finance API ============

  async getFinanceSummary(): Promise<FinanceSummary> {
    return this.request('/api/finance/summary');
  }

  async uploadStatement(formData: FormData): Promise<any> {
    const url = `${this.baseUrl}/api/finance/upload-statement`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  }

  // ============ Health API ============

  async getHealthReport(): Promise<HealthReport> {
    return this.request('/api/health/report');
  }

  async uploadLabResults(formData: FormData): Promise<any> {
    const url = `${this.baseUrl}/api/health/upload-lab-results`;
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    return response.json();
  }

  // ============ Calendar API ============

  async getUpcomingEvents(days: number = 30): Promise<CalendarEvent[]> {
    const data = await this.request(`/api/calendar/upcoming?days=${days}`);
    return data.events;
  }

  async getHolidays(year?: number): Promise<CalendarEvent[]> {
    const y = year || new Date().getFullYear();
    const data = await this.request(`/api/calendar/holidays?year=${y}`);
    return data.holidays;
  }

  async createEvent(event: Partial<CalendarEvent>): Promise<CalendarEvent> {
    return this.request('/api/calendar/events', {
      method: 'POST',
      body: JSON.stringify(event),
    });
  }

  // ============ Bills API ============

  async getBillsSummary(): Promise<BillsSummary> {
    return this.request('/api/bills/summary');
  }

  async getSpendingHabits(): Promise<SpendingHabits> {
    return this.request('/api/bills/spending-habits');
  }
}

// Types
export interface AssistantResponse {
  session_id: string;
  type: 'shopping_result' | 'travel_result' | 'chat_response' | 'error';
  query: string;
  response?: string;
  results?: any[];
  metadata?: Record<string, any>;
  notes?: Record<string, any>;
}

export interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

export interface SessionContext {
  session_id: string;
  message_count: number;
  context: Array<{
    role: string;
    content: string;
    masked_content?: string;
    timestamp: string;
  }>;
}

export interface PrivacyCheckResult {
  is_safe: boolean;
  detected_types: string[];
  recommendation: string;
}

export interface MaskResult {
  original_length: number;
  masked_text: string;
  is_safe: boolean;
  detections: Array<{
    type: string;
    token: string;
    partial: string;
    position: number;
  }>;
}

export interface FinanceSummary {
  total_income: number;
  total_expenses: number;
  balance: number;
  transactions: any[];
}

export interface HealthReport {
  reports: any[];
  lab_results: any[];
  alerts: any[];
}

export interface CalendarEvent {
  id: string;
  date: string;
  title: string;
  type: string;
  description?: string;
  time?: string;
}

export interface BillsSummary {
  total: number;
  by_category: Record<string, number>;
  bills: any[];
}

export interface SpendingHabits {
  analysis: string;
  suggestions: string[];
}

// Singleton instance
export const api = new ApiService();
export default api;
