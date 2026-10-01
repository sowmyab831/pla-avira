import { useState } from 'react'
import { Sparkles, Eye, EyeOff, LogIn, UserPlus, Mail, Lock, User } from 'lucide-react'
import config from '../config'

interface LoginProps {
  onLogin: (token: string, user: { username: string; user_id: string; role: string }) => void
}

export default function Login({ onLogin }: LoginProps) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const url = mode === 'login'
        ? `${config.apiBase}/api/auth/login`
        : `${config.apiBase}/api/auth/signup`

      const body = mode === 'login'
        ? { username, password }
        : { username, email, password }

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      const data = await res.json()

      if (!res.ok) {
        setError(data.detail || 'Authentication failed')
        setLoading(false)
        return
      }

      if (data.access_token) {
        localStorage.setItem('auth_token', data.access_token)
        localStorage.setItem('auth_user', JSON.stringify({
          username: data.username,
          user_id: data.user_id,
          role: data.role,
        }))
        onLogin(data.access_token, {
          username: data.username,
          user_id: data.user_id,
          role: data.role,
        })
      } else {
        setError('Invalid response from server')
      }
    } catch (err) {
      setError('Connection failed. Is the backend running?')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 30%, #4338ca 60%, #6366f1 100%)' }}>
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 backdrop-blur-xl rounded-2xl mb-4 border border-white/20">
            <Sparkles className="text-white" size={32} />
          </div>
          <h1 className="text-3xl font-bold text-white">Avira</h1>
          <p className="text-indigo-200 mt-1">Your Private AI Life Assistant</p>
        </div>

        {/* Card */}
        <div className="bg-white/10 backdrop-blur-xl rounded-2xl p-8 border border-white/20 shadow-2xl">
          {/* Tab Toggle */}
          <div className="flex rounded-xl bg-white/10 p-1 mb-6">
            <button
              onClick={() => { setMode('login'); setError('') }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${mode === 'login' ? 'bg-white text-indigo-700 shadow-md' : 'text-white/70 hover:text-white'}`}
            >
              <LogIn size={14} className="inline mr-1.5 -mt-0.5" />Sign In
            </button>
            <button
              onClick={() => { setMode('signup'); setError('') }}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${mode === 'signup' ? 'bg-white text-indigo-700 shadow-md' : 'text-white/70 hover:text-white'}`}
            >
              <UserPlus size={14} className="inline mr-1.5 -mt-0.5" />Sign Up
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-400/30 rounded-xl text-red-200 text-sm text-center">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div className="relative">
              <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-indigo-300" />
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={e => setUsername(e.target.value)}
                required
                className="w-full pl-10 pr-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-indigo-300/60 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"
              />
            </div>

            {/* Email (signup only) */}
            {mode === 'signup' && (
              <div className="relative">
                <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-indigo-300" />
                <input
                  type="email"
                  placeholder="Email address"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  className="w-full pl-10 pr-4 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-indigo-300/60 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"
                />
              </div>
            )}

            {/* Password */}
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-indigo-300" />
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="Password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full pl-10 pr-12 py-3 bg-white/10 border border-white/20 rounded-xl text-white placeholder-indigo-300/60 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent transition-all"
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-indigo-300 hover:text-white transition-colors">
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-semibold rounded-xl hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg shadow-indigo-500/25 disabled:opacity-50"
            >
              {loading ? '...' : mode === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </form>

          {/* Features Preview */}
          <div className="mt-6 pt-6 border-t border-white/10">
            <p className="text-xs text-indigo-300 text-center mb-3">What you get with Avira</p>
            <div className="grid grid-cols-2 gap-2 text-xs text-white/70">
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> AI Market Scanner
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> Paper Trading
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> Privacy-First AI
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> 22 Data Sources
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> SEC Filings Tracker
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-green-400">✓</span> Influencer Signals
              </div>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-indigo-300/50 mt-4">
          🔒 Your data stays on your device. No cloud. No tracking.
        </p>
      </div>
    </div>
  )
}
