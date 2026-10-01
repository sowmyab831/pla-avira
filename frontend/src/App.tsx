import { useState, useEffect, useCallback, lazy, Suspense, useRef } from 'react'
import { Menu, X, Home, DollarSign, Heart, BookOpen, Calendar as CalendarIcon, ShoppingCart, Plane, UtensilsCrossed, Users, TrendingUp, CheckSquare, Sparkles, Moon, Sun, Newspaper, BarChart3, Brain, Zap, LogOut, Crown, Bell, Mail, Activity, Sunrise, Shield, Wrench, ChevronDown, Search, Command, Link2 } from 'lucide-react'
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Finance = lazy(() => import('./pages/Finance'))
const Health = lazy(() => import('./pages/Health'))
const School = lazy(() => import('./pages/School'))
const Calendar = lazy(() => import('./pages/Calendar'))
const Assistant = lazy(() => import('./pages/Assistant'))
const Shopping = lazy(() => import('./pages/Shopping'))
const Travel = lazy(() => import('./pages/Travel'))
const Grocery = lazy(() => import('./pages/Grocery'))
const Nutrition = lazy(() => import('./pages/Nutrition'))
const Family = lazy(() => import('./pages/Family'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Tasks = lazy(() => import('./pages/Tasks'))
const News = lazy(() => import('./pages/News'))
const TradingDashboard = lazy(() => import('./pages/TradingDashboard'))
const MarketIntelligence = lazy(() => import('./pages/MarketIntelligence'))
const Forecast = lazy(() => import('./pages/Forecast'))
const DayTrader = lazy(() => import('./pages/DayTrader'))
import Login from './pages/Login'
const Subscription = lazy(() => import('./pages/Subscription'))
const EarningsIntelligence = lazy(() => import('./pages/EarningsIntelligence'))
const ActionCenter = lazy(() => import('./pages/ActionCenter'))
const Today = lazy(() => import('./pages/Today'))
const Radar = lazy(() => import('./pages/Radar'))
const Care = lazy(() => import('./pages/Care'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const Notifications = lazy(() => import('./pages/Notifications'))
const Maintenance = lazy(() => import('./pages/Maintenance'))
const Integrations = lazy(() => import('./pages/Integrations'))
const AISettings = lazy(() => import('./pages/AISettings'))
import AviraOrb from './components/AviraOrb'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

type Page = 'dashboard' | 'today' | 'radar' | 'care' | 'assistant' | 'finance' | 'health' | 'school' | 'calendar' | 'shopping' | 'travel' | 'grocery' | 'nutrition' | 'family' | 'portfolio' | 'tasks' | 'news' | 'trading' | 'market_intel' | 'forecast' | 'day_trader' | 'earnings_intel' | 'action_center' | 'subscription' | 'admin' | 'notifications' | 'maintenance' | 'integrations' | 'ai_settings'

interface AuthUser {
  username: string
  user_id: string
  role: string
}

interface NavItem { id: string; label: string; icon: any }
interface NavGroup { key: string; label: string; icon: any; items: NavItem[] }

const NAV_GROUPS: NavGroup[] = [
  {
    key: 'command', label: 'Command Center', icon: Sparkles,
    items: [
      { id: 'dashboard', label: 'Home', icon: Home },
      { id: 'today', label: 'Today', icon: Sunrise },
      { id: 'assistant', label: 'Ask Avira', icon: Sparkles },
      { id: 'action_center', label: 'Action Center', icon: CheckSquare },
      { id: 'radar', label: 'Inbox Radar', icon: Mail },
      { id: 'notifications', label: 'Notifications', icon: Bell },
      { id: 'tasks', label: 'Tasks', icon: CheckSquare },
    ],
  },
  {
    key: 'life', label: 'Life Management', icon: Heart,
    items: [
      { id: 'calendar', label: 'Calendar', icon: CalendarIcon },
      { id: 'health', label: 'Health', icon: Heart },
      { id: 'care', label: 'Care', icon: Activity },
      { id: 'grocery', label: 'Meals & Recipes', icon: UtensilsCrossed },
      { id: 'nutrition', label: 'Nutrition', icon: UtensilsCrossed },
      { id: 'shopping', label: 'Shopping', icon: ShoppingCart },
      { id: 'travel', label: 'Travel', icon: Plane },
      { id: 'family', label: 'Family', icon: Users },
      { id: 'school', label: 'School', icon: BookOpen },
      { id: 'maintenance', label: 'Home Maint.', icon: Wrench },
      { id: 'integrations', label: 'Integrations', icon: Link2 },
      { id: 'ai_settings', label: 'AI & Privacy', icon: Shield },
    ],
  },
  {
    key: 'money', label: 'Money & Markets', icon: TrendingUp,
    items: [
      { id: 'finance', label: 'Money', icon: DollarSign },
      { id: 'portfolio', label: 'Portfolio', icon: TrendingUp },
      { id: 'trading', label: 'Trading', icon: BarChart3 },
      { id: 'market_intel', label: 'Market Intel', icon: Brain },
      { id: 'news', label: 'News', icon: Newspaper },
      { id: 'forecast', label: 'Forecast', icon: TrendingUp },
      { id: 'day_trader', label: 'Day Trader', icon: Zap },
      { id: 'earnings_intel', label: 'Earnings Intel', icon: BarChart3 },
    ],
  },
]

const ALL_PAGES: Page[] = ['dashboard', 'today', 'radar', 'care', 'assistant', 'finance', 'health', 'school', 'calendar', 'shopping', 'travel', 'grocery', 'nutrition', 'family', 'portfolio', 'tasks', 'news', 'trading', 'market_intel', 'forecast', 'day_trader', 'earnings_intel', 'action_center', 'subscription', 'admin', 'notifications', 'maintenance', 'integrations', 'ai_settings']

function groupForPage(page: Page): string | null {
  for (const g of NAV_GROUPS) if (g.items.some(i => i.id === page)) return g.key
  return null
}

function App() {
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem('auth_token'))
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => {
    try { return JSON.parse(localStorage.getItem('auth_user') || 'null') } catch { return null }
  })
  const [currentPage, setCurrentPage] = useState<Page>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') return window.innerWidth >= 768
    return true
  })
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme')
    return saved === 'dark'
  })

  // Collapsible groups — auto-expand the group containing the current page
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {}
    NAV_GROUPS.forEach(g => { init[g.key] = g.key === 'command' })
    return init
  })

  // Command Palette state
  const [cmdOpen, setCmdOpen] = useState(false)
  const [cmdQuery, setCmdQuery] = useState('')
  const cmdRef = useRef<HTMLInputElement>(null)

  const toggleGroup = useCallback((key: string) => {
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }))
  }, [])

  useEffect(() => {
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.removeAttribute('data-theme')
      localStorage.setItem('theme', 'light')
    }
  }, [darkMode])

  useEffect(() => {
    const getPageFromHash = (): Page => {
      const hash = window.location.hash.slice(1)
      return ALL_PAGES.includes(hash as Page) ? (hash as Page) : 'dashboard'
    }

    setCurrentPage(getPageFromHash())

    const handleHashChange = () => {
      setCurrentPage(getPageFromHash())
    }

    window.addEventListener('hashchange', handleHashChange)
    return () => window.removeEventListener('hashchange', handleHashChange)
  }, [])

  // Auto-expand the group containing the active page
  useEffect(() => {
    const gk = groupForPage(currentPage)
    if (gk) setExpandedGroups(prev => ({ ...prev, [gk]: true }))
  }, [currentPage])

  // Cmd+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCmdOpen(o => !o)
        setCmdQuery('')
      }
      if (e.key === 'Escape') setCmdOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (cmdOpen && cmdRef.current) cmdRef.current.focus()
  }, [cmdOpen])

  const allNavItems = NAV_GROUPS.flatMap(g => g.items)
  const cmdFiltered = cmdQuery.trim()
    ? allNavItems.filter(i => i.label.toLowerCase().includes(cmdQuery.toLowerCase()))
    : allNavItems

  const navigateTo = useCallback((id: string) => {
    window.location.hash = id
    setCurrentPage(id as Page)
    setCmdOpen(false)
    setCmdQuery('')
    if (window.innerWidth < 768) setSidebarOpen(false)
  }, [])

  const handleLogin = useCallback((token: string, user: AuthUser) => {
    setAuthToken(token)
    setAuthUser(user)
  }, [])

  const handleLogout = useCallback(() => {
    setAuthToken(null)
    setAuthUser(null)
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
  }, [])

  if (!authToken || !authUser) {
    return <Login onLogin={handleLogin} />
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard': return <Dashboard />
      case 'today': return <Today />
      case 'radar': return <Radar />
      case 'care': return <Care />
      case 'assistant': return <Assistant />
      case 'finance': return <Finance />
      case 'health': return <Health />
      case 'school': return <School />
      case 'calendar': return <Calendar />
      case 'shopping': return <Shopping />
      case 'travel': return <Travel />
      case 'grocery': return <Grocery />
      case 'nutrition': return <Nutrition />
      case 'family': return <Family />
      case 'portfolio': return <Portfolio />
      case 'tasks': return <Tasks />
      case 'news': return <News />
      case 'trading': return <TradingDashboard />
      case 'market_intel': return <MarketIntelligence />
      case 'forecast': return <Forecast />
      case 'day_trader': return <DayTrader />
      case 'earnings_intel': return <EarningsIntelligence />
      case 'action_center': return <ActionCenter />
      case 'subscription': return <Subscription />
      case 'notifications': return <Notifications />
      case 'admin': return <AdminDashboard />
      case 'maintenance': return <Maintenance />
      case 'integrations': return <Integrations />
      case 'ai_settings': return <AISettings />
      default: return <Dashboard />
    }
  }

  const isAdmin = authUser.role === 'admin'

  return (
    <div className="flex h-screen" style={{ background: 'var(--bg-primary)' }}>
      {/* Command Palette Overlay */}
      {cmdOpen && (
        <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]" onClick={() => setCmdOpen(false)}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div className="relative w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }} onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-3 px-4 py-3 border-b" style={{ borderColor: 'var(--border-color)' }}>
              <Search size={18} style={{ color: 'var(--text-muted)' }} />
              <input ref={cmdRef} value={cmdQuery} onChange={e => setCmdQuery(e.target.value)} placeholder="Search pages, actions…" className="flex-1 bg-transparent outline-none text-sm" style={{ color: 'var(--text-primary)' }}
                onKeyDown={e => {
                  if (e.key === 'Enter' && cmdFiltered.length > 0) navigateTo(cmdFiltered[0].id)
                }}
              />
              <kbd className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>ESC</kbd>
            </div>
            <ul className="max-h-72 overflow-y-auto py-2">
              {cmdFiltered.map(item => {
                const Icon = item.icon
                return (
                  <li key={item.id}>
                    <button onClick={() => navigateTo(item.id)} className="w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-indigo-50 dark:hover:bg-indigo-900/20" style={{ color: 'var(--text-primary)' }}>
                      <Icon size={16} style={{ color: 'var(--text-muted)' }} />
                      {item.label}
                      {currentPage === item.id && <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700">Active</span>}
                    </button>
                  </li>
                )
              })}
              {cmdFiltered.length === 0 && <li className="px-4 py-6 text-center text-sm" style={{ color: 'var(--text-muted)' }}>No matches</li>}
            </ul>
          </div>
        </div>
      )}

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          className="md:hidden fixed inset-0 bg-black/40 z-30"
          aria-hidden="true"
        />
      )}
      {/* Mobile hamburger */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="md:hidden fixed top-3 left-3 z-40 p-2 rounded-lg shadow-md"
          style={{ background: 'var(--bg-secondary)', color: 'var(--text-primary)' }}
          aria-label="Open menu"
        >
          <Menu size={20} />
        </button>
      )}
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? 'w-64' : 'w-20'
        } sidebar transition-all duration-300 flex flex-col fixed md:relative inset-y-0 left-0 z-40 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* Logo */}
        <div className="p-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-color)' }}>
          {sidebarOpen && (
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Sparkles className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-xl font-bold gradient-text">Avira</h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Hi, {authUser.username}</p>
            </div>
          </div>
        )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
            style={{ color: 'var(--text-secondary)' }}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Quick Search Bar */}
        {sidebarOpen && (
          <button onClick={() => setCmdOpen(true)} className="mx-3 mt-3 flex items-center gap-2 px-3 py-2 rounded-xl text-xs transition-all" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)', border: '1px solid var(--border-color)' }}>
            <Search size={14} /> <span className="flex-1 text-left">Search…</span>
            <kbd className="text-[10px] px-1 py-0.5 rounded" style={{ background: 'var(--bg-secondary)' }}>
              <Command size={10} className="inline" />K
            </kbd>
          </button>
        )}

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_GROUPS.map(group => {
            const GroupIcon = group.icon
            const isExpanded = expandedGroups[group.key] ?? false
            const hasActive = group.items.some(i => i.id === currentPage)
            return (
              <div key={group.key}>
                {/* Group header */}
                <button
                  onClick={() => sidebarOpen ? toggleGroup(group.key) : navigateTo(group.items[0].id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all ${hasActive && !isExpanded ? 'ring-1 ring-indigo-400/30' : ''}`}
                  style={{ color: hasActive ? 'var(--accent-primary)' : 'var(--text-muted)' }}
                >
                  <GroupIcon size={16} />
                  {sidebarOpen && (
                    <>
                      <span className="flex-1 text-left">{group.label}</span>
                      <ChevronDown size={14} className={`transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                    </>
                  )}
                </button>
                {/* Group items */}
                {sidebarOpen && isExpanded && (
                  <div className="ml-3 pl-3 mt-1 mb-2 space-y-0.5" style={{ borderLeft: '2px solid var(--border-color)' }}>
                    {group.items.map(item => {
                      const Icon = item.icon
                      const isActive = currentPage === item.id
                      return (
                        <button
                          key={item.id}
                          onClick={() => navigateTo(item.id)}
                          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${isActive ? 'font-semibold' : ''}`}
                          style={{
                            background: isActive ? 'var(--accent-primary)' : 'transparent',
                            color: isActive ? '#fff' : 'var(--text-secondary)',
                          }}
                        >
                          <Icon size={16} />
                          <span>{item.label}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}

          {/* Bottom nav items: settings/admin */}
          <div className="pt-3 mt-2 space-y-0.5" style={{ borderTop: '1px solid var(--border-color)' }}>
            <button onClick={() => navigateTo('subscription')} className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${currentPage === 'subscription' ? 'font-semibold' : ''}`}
              style={{ background: currentPage === 'subscription' ? 'var(--accent-primary)' : 'transparent', color: currentPage === 'subscription' ? '#fff' : 'var(--text-secondary)' }}>
              <Crown size={16} /> {sidebarOpen && 'Subscription'}
            </button>
            {isAdmin && (
              <button onClick={() => navigateTo('admin')} className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all ${currentPage === 'admin' ? 'font-semibold' : ''}`}
                style={{ background: currentPage === 'admin' ? 'var(--accent-primary)' : 'transparent', color: currentPage === 'admin' ? '#fff' : 'var(--text-secondary)' }}>
                <Shield size={16} /> {sidebarOpen && 'Admin'}
              </button>
            )}
          </div>
        </nav>

        {/* Footer */}
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--border-color)' }}>
          {sidebarOpen ? (
            <>
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-sm"
                style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}
              >
                {darkMode ? <Sun size={16} /> : <Moon size={16} />}
                <span>{darkMode ? 'Light Mode' : 'Dark Mode'}</span>
              </button>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex-1 flex items-center gap-2 px-3 py-1.5 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-[10px] font-bold text-white">
                    {authUser.username.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-xs font-medium truncate" style={{ color: 'var(--text-primary)' }}>{authUser.username}</span>
                </div>
                <button
                  onClick={handleLogout}
                  className="p-2 rounded-lg transition-all hover:shadow-md"
                  style={{ background: '#ef444415', color: '#ef4444' }}
                  aria-label="Sign out"
                >
                  <LogOut size={14} />
                </button>
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <button onClick={() => setDarkMode(!darkMode)} className="w-full flex justify-center p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)' }}>
                {darkMode ? <Sun size={16} /> : <Moon size={16} />}
              </button>
              <button onClick={handleLogout} className="w-full flex justify-center p-2 rounded-lg" style={{ background: '#ef444415', color: '#ef4444' }} aria-label="Sign out">
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="card m-4 h-[calc(100vh-2rem)] overflow-auto">
          <ErrorBoundary key={currentPage}>
            <Suspense fallback={<div className="p-6" role="status">Loading…</div>}>{renderPage()}</Suspense>
          </ErrorBoundary>
        </div>
      </div>

      {/* Global Avira voice orb */}
      <AviraOrb />
    </div>
  )
}

export default App
