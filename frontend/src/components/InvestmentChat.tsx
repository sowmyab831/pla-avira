import { useState, useEffect, useRef } from 'react'
import { Send, TrendingUp } from 'lucide-react'
import config from '../config'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface InvestmentChatProps {
  portfolioContext?: {
    holdings: any[]
    total_value: number
    gain_loss: number
    [key: string]: any
  }
}

export default function InvestmentChat({ portfolioContext }: InvestmentChatProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      // Detect stock symbols - all caps words 1-5 letters, or mentions of "stock", "option", "invest"
      const isInvestmentQuery = /\b[A-Z]{1,5}\b|stock|option|invest|buy|sell|trade|portfolio|shares/i.test(input)
      const symbolMatch = input.match(/\b[A-Z]{2,5}\b/)
      const symbol = symbolMatch ? symbolMatch[0] : null

      // Build investment-specific context
      let context: any = {
        ...portfolioContext,
        query_type: isInvestmentQuery ? 'investment' : 'general',
        investment_context: {
          current_date: new Date().toISOString().split('T')[0],
          market_hours: 'US Market Hours: 9:30 AM - 4:00 PM ET',
          instruction: 'You are an investment advisor. Focus on stocks, options, and market analysis. Do NOT suggest shopping products. If user asks about a stock symbol (all caps), provide stock analysis, not product recommendations.'
        }
      }

      // If user mentions a stock symbol, get comprehensive analysis
      if (symbol && isInvestmentQuery) {
        try {
          const [stockResponse, optionsResponse] = await Promise.all([
            fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/comprehensive`),
            fetch(`${config.apiBase}/api/portfolio/stocks/${symbol}/options`)
          ])
          
          const stockData = await stockResponse.json()
          const optionsData = await optionsResponse.json()
          
          if (stockData.success) {
            context.mentioned_stock = {
              symbol,
              price: stockData.current_price || stockData.price_data?.current_price,
              change_percent: stockData.change_percent || stockData.price_data?.change_percent,
              recommendation: stockData.ai_recommendation?.rating,
              analysis: stockData.ai_recommendation?.analysis,
              technical: stockData.technical_analysis,
              options_available: optionsData.success,
              options_strategy: optionsData.options?.recommended_strategy
            }
          }
        } catch (error) {
          console.error('Failed to fetch stock data:', error)
        }
      }

      // Send to assistant API with investment context
      const sessionId = `investment-${Date.now()}`
      const response = await fetch(`${config.apiBase}/api/assistant/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
          user_id: 'default',
          use_external_llm: false,
          context: context
        })
      })

      const data = await response.json()
      
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.response || data.metadata?.error || 'I apologize, I could not process your request.',
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50">
        <div className="flex items-center gap-2">
          <TrendingUp className="text-blue-600" size={20} />
          <h3 className="font-semibold text-gray-900">Investment Assistant</h3>
        </div>
        <p className="text-xs text-gray-600 mt-1">Ask about your portfolio or any stock</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <TrendingUp size={48} className="mx-auto mb-4 text-gray-300" />
            <p className="text-sm">Ask me anything about your investments!</p>
            <div className="mt-4 space-y-2 text-xs text-left max-w-xs mx-auto">
              <p className="text-gray-400">Try asking:</p>
              <p className="text-gray-600">"Should I buy AAPL?"</p>
              <p className="text-gray-600">"How is my portfolio performing?"</p>
              <p className="text-gray-600">"What's the outlook for TSLA?"</p>
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'}`}>
                {new Date(msg.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-3">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about stocks or your portfolio..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={loading}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={20} />
          </button>
        </div>
      </div>
    </div>
  )
}
