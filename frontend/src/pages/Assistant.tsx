import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  ShoppingCart, 
  Plane, 
  MessageSquare, 
  Shield, 
  History,
  Trash2,
  Loader2,
  AlertTriangle,
  DollarSign,
  Clock,
  Star
} from 'lucide-react';
import { config } from '../config';
import { authenticatedFetch as fetch } from '../api/authenticatedFetch';
import { ModelSelector } from '../components/ModelSelector';
import { AIResponseBadge } from '../components/LlmBadge';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: string;
  results?: any[];
  metadata?: any;
  timestamp: string;
}

interface Session {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  preview: string;
}

const Assistant: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => 
    `session_${Date.now()}`
  );
  const [sessions, setSessions] = useState<Session[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  // Principal comes from the Bearer token server-side; user_id is only a legacy query param.
  const [userId] = useState(() => { try { return JSON.parse(localStorage.getItem('auth_user') || '{}').user_id || 'me' } catch { return 'me' } });
  const [modelKey, setModelKey] = useState<string>(() => sessionStorage.getItem('avira_conv_model') || '');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => { sessionStorage.setItem('avira_conv_model', modelKey) }, [modelKey]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      const response = await fetch(
        `${config.endpoints.assistantSessions}?user_id=${userId}`
      );
      const data = await response.json();
      if (data.success) {
        setSessions(data.sessions);
      }
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const loadSession = async (sid: string) => {
    try {
      const response = await fetch(
        `${config.endpoints.assistantSessions}/${sid}/load?user_id=${userId}`,
        { method: 'POST' }
      );
      const data = await response.json();
      if (data.success) {
        setSessionId(sid);
        // Convert context to messages
        const loadedMessages: Message[] = data.context.map((msg: any, idx: number) => ({
          id: `${sid}_${idx}`,
          role: msg.role,
          content: msg.masked_content || msg.content,
          timestamp: msg.timestamp,
        }));
        setMessages(loadedMessages);
        setShowSessions(false);
      }
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const deleteSession = async (sid: string) => {
    try {
      await fetch(
        `${config.endpoints.assistantSessions}/${sid}?user_id=${userId}`,
        { method: 'DELETE' }
      );
      loadSessions();
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    const draft = input;
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(config.endpoints.assistantChat, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: draft,
          session_id: sessionId,
          use_external_llm: false,
          model: modelKey || undefined,
        }),
      });

      if (response.status === 401) {
        setInput(draft);   // keep the draft; user needs to sign in again
        setMessages(prev => [...prev, { id: `msg_${Date.now()}_auth`, role: 'assistant', content: 'Your session expired. Please sign in again — your message is kept.', timestamp: new Date().toISOString() }]);
        return;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Request failed');

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_response`,
        role: 'assistant',
        content: data.response || 'No response',
        type: data.type,
        results: data.results,
        metadata: data.metadata,
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => [...prev, assistantMessage]);
      loadSessions(); // Refresh session list
    } catch (error) {
      console.error('Chat error:', error);
      setInput(draft);   // never lose the user's text on failure
      setMessages(prev => [...prev, {
        id: `msg_${Date.now()}_error`,
        role: 'assistant',
        content: 'Sorry, I encountered an error. Your message is kept in the box — please try again.',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = () => {
    setSessionId(`session_${Date.now()}`);
    setMessages([]);
  };

  const renderShoppingResults = (results: any[]) => (
    <div className="mt-3 space-y-3">
      {results.slice(0, 3).map((item, idx) => (
        <div key={idx} className="bg-white rounded-lg p-3 border border-gray-200 shadow-sm">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2 py-0.5 rounded">
                  #{item.rank}
                </span>
                <h4 className="font-medium text-gray-900 text-sm">{item.title}</h4>
              </div>
              <p className="text-gray-600 text-xs mt-1">{item.seller}</p>
            </div>
            <div className="text-right">
              <p className="text-lg font-bold text-green-600">${item.final_price?.toFixed(2)}</p>
              {item.original_price && item.original_price > item.price && (
                <p className="text-xs text-gray-400 line-through">${item.original_price?.toFixed(2)}</p>
              )}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {item.delivery_estimate}
            </span>
            <span className="flex items-center gap-1">
              <Star className="w-3 h-3 text-yellow-500" />
              {item.seller_rating}
            </span>
          </div>
          <p className="mt-2 text-xs text-blue-600 italic">{item.why}</p>
        </div>
      ))}
    </div>
  );

  const renderFlightResults = (results: any[], type: 'cheapest' | 'comfort') => (
    <div className="mt-2 space-y-2">
      <h5 className="text-xs font-semibold text-gray-700 uppercase">
        {type === 'cheapest' ? '💰 Cheapest' : '✨ Most Comfortable'}
      </h5>
      {results.slice(0, 3).map((flight, idx) => (
        <div key={idx} className="bg-white rounded-lg p-2 border border-gray-200 text-sm">
          <div className="flex justify-between items-center">
            <div>
              <span className="font-medium">{flight.airlines?.join(', ')}</span>
              <span className="text-gray-500 ml-2">{flight.total_duration_formatted}</span>
              <span className="text-gray-400 ml-2">
                {flight.layover_count === 0 ? 'Nonstop' : `${flight.layover_count} stop`}
              </span>
            </div>
            <div className="text-right">
              <span className="font-bold text-green-600">${flight.price?.toFixed(2)}</span>
              {type === 'comfort' && (
                <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">
                  {flight.comfort_score}/10
                </span>
              )}
            </div>
          </div>
          {flight.comfort_reason && (
            <p className="text-xs text-gray-500 mt-1">{flight.comfort_reason}</p>
          )}
        </div>
      ))}
    </div>
  );

  const renderMessage = (message: Message) => {
    const isUser = message.role === 'user';
    
    return (
      <div
        key={message.id}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div
          className={`max-w-[80%] rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-800'
          }`}
        >
          {/* Message type indicator */}
          {!isUser && message.type && message.type !== 'chat_response' && (
            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
              {message.type === 'shopping_result' && (
                <>
                  <ShoppingCart className="w-4 h-4 text-blue-600" />
                  <span className="text-xs font-medium text-blue-600">Shopping Results</span>
                </>
              )}
              {message.type === 'travel_result' && (
                <>
                  <Plane className="w-4 h-4 text-purple-600" />
                  <span className="text-xs font-medium text-purple-600">Flight Results</span>
                </>
              )}
            </div>
          )}
          
          {/* Message content */}
          <div className="whitespace-pre-wrap text-sm">
            {message.content}
          </div>
          
          {/* Structured results */}
          {message.type === 'shopping_result' && message.results && message.results.length > 0 && (
            renderShoppingResults(message.results)
          )}
          
          {message.type === 'travel_result' && message.metadata && (
            <div className="mt-3">
              {message.results && renderFlightResults(
                message.results.filter((r: any) => r.rank <= 3),
                'cheapest'
              )}
            </div>
          )}
          
          {/* Timestamp + model badge */}
          <div className={`flex flex-wrap items-center gap-2 text-xs mt-2 ${isUser ? 'text-blue-200' : 'text-gray-400'}`}>
            <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
            {!isUser && message.metadata?.ai && <AIResponseBadge meta={message.metadata.ai} />}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* Sessions Sidebar */}
      {showSessions && (
        <div className="w-64 bg-gray-50 border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h3 className="font-semibold text-gray-800">Chat History</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {sessions.map(session => (
              <div
                key={session.session_id}
                className={`p-3 rounded-lg mb-2 cursor-pointer hover:bg-gray-100 ${
                  session.session_id === sessionId ? 'bg-blue-50 border border-blue-200' : ''
                }`}
                onClick={() => loadSession(session.session_id)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-800 truncate">{session.preview || 'New conversation'}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {session.message_count} messages
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(session.session_id);
                    }}
                    className="p-1 hover:bg-red-100 rounded"
                  >
                    <Trash2 className="w-3 h-3 text-red-500" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSessions(!showSessions)}
              className="p-2 hover:bg-gray-100 rounded-lg"
            >
              <History className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h2 className="font-semibold text-gray-800">Avira Assistant</h2>
              <p className="text-xs text-gray-500">Shopping, Travel & More</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
              <Shield className="w-3 h-3" />
              Privacy Protected
            </span>
            <button
              onClick={startNewSession}
              className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
            >
              New Chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mb-4">
                <MessageSquare className="w-8 h-8 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">
                How can I help you today?
              </h3>
              <p className="text-gray-500 text-sm max-w-md mb-6">
                I can help you find products, compare prices, search flights, 
                and answer questions about your health, finances, and calendar.
              </p>
              <div className="grid grid-cols-2 gap-3 max-w-lg">
                <button
                  onClick={() => setInput('Find iPhone 16 Pro Max 256GB unlocked')}
                  className="p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 text-left"
                >
                  <ShoppingCart className="w-5 h-5 text-blue-600 mb-2" />
                  <p className="text-sm font-medium">Shop Products</p>
                  <p className="text-xs text-gray-500">Find & compare prices</p>
                </button>
                <button
                  onClick={() => setInput('Find flights from NYC to LA on Dec 25')}
                  className="p-3 bg-white rounded-lg border border-gray-200 hover:border-purple-300 text-left"
                >
                  <Plane className="w-5 h-5 text-purple-600 mb-2" />
                  <p className="text-sm font-medium">Book Travel</p>
                  <p className="text-xs text-gray-500">Search flights</p>
                </button>
                <button
                  onClick={() => setInput('What is my top spending this month?')}
                  className="p-3 bg-white rounded-lg border border-gray-200 hover:border-green-300 text-left"
                >
                  <DollarSign className="w-5 h-5 text-green-600 mb-2" />
                  <p className="text-sm font-medium">Finance</p>
                  <p className="text-xs text-gray-500">Track spending</p>
                </button>
                <button
                  onClick={() => setInput('How is my health report looking?')}
                  className="p-3 bg-white rounded-lg border border-gray-200 hover:border-red-300 text-left"
                >
                  <AlertTriangle className="w-5 h-5 text-red-600 mb-2" />
                  <p className="text-sm font-medium">Health</p>
                  <p className="text-xs text-gray-500">Lab results & alerts</p>
                </button>
              </div>
            </div>
          ) : (
            <>
              {messages.map(renderMessage)}
              {loading && (
                <div className="flex justify-start mb-4">
                  <div className="bg-gray-100 rounded-2xl px-4 py-3">
                    <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input */}
        <div className="bg-white border-t border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder="Ask me anything... (shopping, flights, health, finance)"
              className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 mt-2">
            <ModelSelector value={modelKey} onChange={setModelKey} />
            <p className="text-xs text-gray-400">
              Sensitive info is masked before any model sees it. Each answer shows which model produced it.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Assistant;
