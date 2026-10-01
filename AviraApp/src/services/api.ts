/**
 * API Service for Avira Mobile App
 * Connects to backend via DuckDNS or localhost
 */
import axios, { AxiosInstance } from 'axios';
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
  private client: AxiosInstance;
  private baseUrl: string;
  private userId: string = 'mobile-user';
  private sessionId: string = '';

  constructor() {
    this.baseUrl = CONFIG.PRODUCTION_API;
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.initSession();
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
    this.client.defaults.baseURL = url;
  }

  async setUserId(userId: string) {
    this.userId = userId;
    await AsyncStorage.setItem('userId', userId);
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await this.client.get('/health');
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  }

  // Test connection to different endpoints
  async testConnection(): Promise<{ url: string; success: boolean }> {
    const urls = [CONFIG.PRODUCTION_API, CONFIG.DIRECT_IP_API, CONFIG.LOCAL_API];
    
    for (const url of urls) {
      try {
        const response = await axios.get(`${url}/health`, { timeout: 5000 });
        if (response.data.status === 'healthy') {
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
    const response = await this.client.post('/api/assistant/chat', {
      message,
      session_id: this.sessionId,
      user_id: this.userId,
      use_external_llm: useExternalLlm,
    });
    return response.data;
  }

  async getSessions(): Promise<Session[]> {
    const response = await this.client.get(`/api/assistant/sessions?user_id=${this.userId}`);
    return response.data.sessions;
  }

  async loadSession(sessionId: string): Promise<SessionContext> {
    const response = await this.client.post(
      `/api/assistant/sessions/${sessionId}/load?user_id=${this.userId}`
    );
    this.sessionId = sessionId;
    await AsyncStorage.setItem('sessionId', sessionId);
    return response.data;
  }

  async deleteSession(sessionId: string): Promise<void> {
    await this.client.delete(`/api/assistant/sessions/${sessionId}?user_id=${this.userId}`);
  }

  async newSession(): Promise<string> {
    this.sessionId = `mobile_${Date.now()}`;
    await AsyncStorage.setItem('sessionId', this.sessionId);
    return this.sessionId;
  }

  // ============ Privacy API ============

  async checkPrivacy(text: string): Promise<PrivacyCheckResult> {
    const response = await this.client.post('/api/assistant/privacy/check', {
      text,
      user_id: this.userId,
    });
    return response.data;
  }

  async maskText(text: string): Promise<MaskResult> {
    const response = await this.client.post('/api/assistant/privacy/mask', {
      text,
      user_id: this.userId,
      session_id: this.sessionId,
    });
    return response.data;
  }

  // ============ Finance API ============

  async getFinanceSummary(): Promise<FinanceSummary> {
    const response = await this.client.get('/api/finance/summary');
    return response.data;
  }

  async uploadStatement(formData: FormData): Promise<any> {
    const response = await this.client.post('/api/finance/upload-statement', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  // ============ Health API ============

  async getHealthReport(): Promise<HealthReport> {
    const response = await this.client.get('/api/health/report');
    return response.data;
  }

  async uploadLabResults(formData: FormData): Promise<any> {
    const response = await this.client.post('/api/health/upload-lab-results', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  // ============ Calendar API ============

  async getUpcomingEvents(days: number = 30): Promise<CalendarEvent[]> {
    const response = await this.client.get(`/api/calendar/upcoming?days=${days}`);
    return response.data.events;
  }

  async getHolidays(year?: number): Promise<CalendarEvent[]> {
    const y = year || new Date().getFullYear();
    const response = await this.client.get(`/api/calendar/holidays?year=${y}`);
    return response.data.holidays;
  }

  async createEvent(event: Partial<CalendarEvent>): Promise<CalendarEvent> {
    const response = await this.client.post('/api/calendar/events', event);
    return response.data;
  }

  // ============ Bills API ============

  async getBillsSummary(): Promise<BillsSummary> {
    const response = await this.client.get('/api/bills/summary');
    return response.data;
  }

  async getSpendingHabits(): Promise<SpendingHabits> {
    const response = await this.client.get('/api/bills/spending-habits');
    return response.data;
  }

  // ============ Trading API ============

  async getStockForecast(symbol: string): Promise<any> {
    const response = await this.client.get(`/api/portfolio/stocks/${symbol}/forecast`);
    return response.data;
  }

  async getIntradayTargets(symbol: string): Promise<any> {
    const response = await this.client.get(`/api/portfolio/stocks/${symbol}/intraday-targets`);
    return response.data;
  }

  async getMarketNews(symbol?: string): Promise<any> {
    const url = symbol
      ? `/api/portfolio/market/news?symbol=${symbol}`
      : '/api/portfolio/market/news';
    const response = await this.client.get(url);
    return response.data;
  }

  async getMarketMacro(): Promise<any> {
    const response = await this.client.get('/api/portfolio/market/macro');
    return response.data;
  }

  async getTopRecommendations(count: number = 10): Promise<any> {
    const response = await this.client.get(`/api/portfolio/market/recommendations?count=${count}`);
    return response.data;
  }

  async getHistoricalPrices(symbol: string, period: string = '1m'): Promise<any> {
    const response = await this.client.get(`/api/portfolio/stocks/${symbol}/historical?period=${period}`);
    return response.data;
  }

  // ============ Earnings & Digest (public, read-only) ============

  async getUpcomingEarnings(days: number = 30): Promise<any> {
    const response = await this.client.get(`/api/public/market/earnings/upcoming?days=${days}`);
    return response.data;
  }

  async getMarketDigest(earningsDays: number = 14): Promise<{ title: string; message: string; data: any }> {
    const response = await this.client.get(`/api/public/market/digest?earnings_days=${earningsDays}`);
    return response.data;
  }

  async getWatchDigest(symbols: string[], days: number = 30): Promise<{ title: string; message: string; data: any }> {
    const response = await this.client.get(
      `/api/public/market/digest/watch?symbols=${encodeURIComponent(symbols.join(','))}&days=${days}`
    );
    return response.data;
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
