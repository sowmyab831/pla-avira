import { useState, useRef, useEffect } from 'react'
import { authenticatedFetch } from '../api/authenticatedFetch'
import { MessageCircle, X, Send, Minimize2, Maximize2, Plus, History, ChevronLeft, Edit2, Trash2 } from 'lucide-react'
import config from '../config'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ChatSession {
  session_id: string
  title: string
  created_at: string
  updated_at: string
  message_count: number
}

export default function AviraAssistant() {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  // Session management
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [showSessions, setShowSessions] = useState(false)
  const [editingSession, setEditingSession] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Load sessions on mount
  useEffect(() => {
    if (isOpen) {
      loadSessions()
    }
  }, [isOpen])

  // Load sessions from localStorage (for demo) or API
  const loadSessions = () => {
    const saved = localStorage.getItem('avira_sessions')
    if (saved) {
      const parsed = JSON.parse(saved)
      setSessions(parsed.sessions || [])
      if (parsed.currentSessionId) {
        setCurrentSessionId(parsed.currentSessionId)
        loadSessionMessages(parsed.currentSessionId)
      }
    }
  }

  // Save sessions to localStorage
  const saveSessions = (newSessions: ChatSession[], sessionId: string | null) => {
    localStorage.setItem('avira_sessions', JSON.stringify({
      sessions: newSessions,
      currentSessionId: sessionId
    }))
  }

  // Load messages for a session
  const loadSessionMessages = (sessionId: string) => {
    const saved = localStorage.getItem(`avira_messages_${sessionId}`)
    if (saved) {
      setMessages(JSON.parse(saved))
    } else {
      setMessages([])
    }
  }

  // Save messages for current session
  const saveSessionMessages = (sessionId: string, msgs: Message[]) => {
    localStorage.setItem(`avira_messages_${sessionId}`, JSON.stringify(msgs))
  }

  // Create new session
  const createNewSession = () => {
    const sessionId = `session_${Date.now()}`
    const newSession: ChatSession = {
      session_id: sessionId,
      title: `Chat ${new Date().toLocaleDateString()}`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      message_count: 0
    }
    const newSessions = [newSession, ...sessions]
    setSessions(newSessions)
    setCurrentSessionId(sessionId)
    setMessages([])
    saveSessions(newSessions, sessionId)
    setShowSessions(false)
  }

  // Switch to a session
  const switchSession = (sessionId: string) => {
    setCurrentSessionId(sessionId)
    loadSessionMessages(sessionId)
    saveSessions(sessions, sessionId)
    setShowSessions(false)
  }

  // Rename session
  const renameSession = (sessionId: string, newTitle: string) => {
    const updated = sessions.map(s => 
      s.session_id === sessionId ? { ...s, title: newTitle } : s
    )
    setSessions(updated)
    saveSessions(updated, currentSessionId)
    setEditingSession(null)
  }

  // Delete session
  const deleteSession = (sessionId: string) => {
    const updated = sessions.filter(s => s.session_id !== sessionId)
    setSessions(updated)
    localStorage.removeItem(`avira_messages_${sessionId}`)
    if (currentSessionId === sessionId) {
      if (updated.length > 0) {
        switchSession(updated[0].session_id)
      } else {
        setCurrentSessionId(null)
        setMessages([])
      }
    }
    saveSessions(updated, updated.length > 0 ? updated[0].session_id : null)
  }

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    // Auto-create session if none exists
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = `session_${Date.now()}`
      const newSession: ChatSession = {
        session_id: sessionId,
        title: input.substring(0, 30) + (input.length > 30 ? '...' : ''),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        message_count: 0
      }
      const newSessions = [newSession, ...sessions]
      setSessions(newSessions)
      setCurrentSessionId(sessionId)
      saveSessions(newSessions, sessionId)
    }

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    const newMessages = [...messages, userMessage]
    setMessages(newMessages)
    setInput('')
    setLoading(true)

    try {
      const response = await authenticatedFetch(`${config.apiBase}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
          model: sessionStorage.getItem('avira_conv_model') || undefined,
          use_external_llm: false
        })
      })

      const data = await response.json()
      
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response || 'I apologize, I could not process your request.',
        timestamp: new Date().toISOString()
      }

      const finalMessages = [...newMessages, assistantMessage]
      setMessages(finalMessages)
      saveSessionMessages(sessionId, finalMessages)
      
      // Update session message count
      const updatedSessions = sessions.map(s => 
        s.session_id === sessionId 
          ? { ...s, message_count: finalMessages.length, updated_at: new Date().toISOString() }
          : s
      )
      setSessions(updatedSessions)
      saveSessions(updatedSessions, sessionId)
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      }
      const finalMessages = [...newMessages, errorMessage]
      setMessages(finalMessages)
      saveSessionMessages(sessionId, finalMessages)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
    // Shift+Enter will naturally create a newline in textarea
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full shadow-lg hover:shadow-xl transition-all flex items-center justify-center text-white z-50"
        aria-label="Open Avira Assistant"
      >
        <MessageCircle size={24} />
      </button>
    )
  }

  return (
    <div className={`fixed bottom-6 right-6 bg-white rounded-2xl shadow-2xl z-50 transition-all ${
      isMinimized ? 'w-80 h-16' : 'w-96 h-[600px]'
    }`}>
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-500 to-purple-600 text-white p-4 rounded-t-2xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          {showSessions ? (
            <button onClick={() => setShowSessions(false)} className="hover:bg-white/20 p-1.5 rounded-lg">
              <ChevronLeft size={20} />
            </button>
          ) : (
            <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center">
              <MessageCircle size={20} />
            </div>
          )}
          <div>
            <h3 className="font-semibold">{showSessions ? 'Chat History' : 'Avira Assistant'}</h3>
            <p className="text-xs text-white/80">{showSessions ? `${sessions.length} conversations` : 'Always here to help'}</p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {!showSessions && (
            <>
              <button
                onClick={createNewSession}
                className="hover:bg-white/20 p-1.5 rounded-lg transition-colors"
                title="New Chat"
              >
                <Plus size={18} />
              </button>
              <button
                onClick={() => setShowSessions(true)}
                className="hover:bg-white/20 p-1.5 rounded-lg transition-colors"
                title="Chat History"
              >
                <History size={18} />
              </button>
            </>
          )}
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="hover:bg-white/20 p-1.5 rounded-lg transition-colors"
          >
            {isMinimized ? <Maximize2 size={18} /> : <Minimize2 size={18} />}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="hover:bg-white/20 p-1.5 rounded-lg transition-colors"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Session List */}
          {showSessions ? (
            <div className="h-[calc(100%-80px)] overflow-y-auto p-4 space-y-2">
              {sessions.length === 0 ? (
                <div className="text-center text-gray-500 mt-20">
                  <History size={48} className="mx-auto mb-4 text-gray-300" />
                  <p className="text-sm">No chat history yet</p>
                  <button
                    onClick={createNewSession}
                    className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                  >
                    Start New Chat
                  </button>
                </div>
              ) : (
                sessions.map(session => (
                  <div
                    key={session.session_id}
                    className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                      currentSessionId === session.session_id
                        ? 'bg-purple-50 border-purple-300'
                        : 'bg-white border-gray-200 hover:bg-gray-50'
                    }`}
                  >
                    {editingSession === session.session_id ? (
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onBlur={() => renameSession(session.session_id, editTitle)}
                        onKeyPress={(e) => e.key === 'Enter' && renameSession(session.session_id, editTitle)}
                        className="w-full px-2 py-1 border rounded"
                        autoFocus
                      />
                    ) : (
                      <div onClick={() => switchSession(session.session_id)}>
                        <div className="flex items-center justify-between">
                          <p className="font-medium text-sm truncate flex-1">{session.title}</p>
                          <div className="flex gap-1">
                            <button
                              onClick={(e) => { e.stopPropagation(); setEditingSession(session.session_id); setEditTitle(session.title); }}
                              className="p-1 hover:bg-gray-200 rounded"
                            >
                              <Edit2 size={12} />
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); deleteSession(session.session_id); }}
                              className="p-1 hover:bg-red-100 text-red-500 rounded"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {session.message_count} messages • {new Date(session.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          ) : (
          <>
          {/* Messages */}
          <div className="h-[calc(100%-140px)] overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 mt-20">
                <MessageCircle size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-sm">Ask me anything!</p>
                <p className="text-xs mt-2">I can help with:</p>
                <ul className="text-xs mt-2 space-y-1">
                  <li>• Portfolio analysis</li>
                  <li>• Task management</li>
                  <li>• Travel planning</li>
                  <li>• Shopping deals</li>
                  <li>• Health tracking</li>
                </ul>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-white/70' : 'text-gray-500'}`}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl px-4 py-2">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your message... (Shift+Enter for new line)"
                className="flex-1 px-4 py-2 border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none min-h-[40px] max-h-[120px]"
                disabled={loading}
                rows={1}
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                className="bg-gradient-to-br from-blue-500 to-purple-600 text-white p-2 rounded-xl hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed self-end"
              >
                <Send size={20} />
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-1">Press Enter to send, Shift+Enter for new line</p>
          </div>
          </>
          )}
        </>
      )}
    </div>
  )
}
