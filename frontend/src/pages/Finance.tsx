import { authenticatedFetch } from '../api/authenticatedFetch'
import React, { useState, useRef, useEffect } from 'react'
import { Upload, TrendingDown, DollarSign, CreditCard, AlertTriangle, ShoppingCart, Zap, Car, Utensils, Lightbulb, PiggyBank, TrendingUp, BarChart3, Target, CheckCircle } from 'lucide-react'
import config from '../config'
import ProfileSwitcher, { getActiveProfile, Profile } from '../components/ProfileSwitcher'

interface Transaction {
  date: string
  description: string
  amount: number
  category: string
  is_flagged: boolean
}

interface ExpenseReport {
  total_spent: number
  transaction_count: number
  top_categories: Record<string, number>
  flagged_transactions: Transaction[]
}

interface FinanceData {
  transactions: Transaction[]
  summary: ExpenseReport
}

interface SavingsTip {
  id: string
  category: string
  title: string
  description: string
  potential_savings: number
  difficulty: 'easy' | 'medium' | 'hard'
  applied: boolean
}

export default function Finance() {
  const [uploading, setUploading] = useState(false)
  const [data, setData] = useState<FinanceData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [savingsTips, setSavingsTips] = useState<SavingsTip[]>([])
  const [monthlyBudget, setMonthlyBudget] = useState('')
  const [savingsGoal, setSavingsGoal] = useState('')
  const [history, setHistory] = useState<any[]>([])
  const [selectedHistory, setSelectedHistory] = useState<any | null>(null)
  const [profile, setProfile] = useState<Profile>(getActiveProfile())

  // Load finance upload history for the active profile
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const res = await authenticatedFetch(`${config.apiBase}/api/finance/history?user_id=${encodeURIComponent(profile.userId)}`)
        const data = await res.json()
        if (data.success && Array.isArray(data.history)) {
          setHistory(data.history)
        } else {
          setHistory([])
        }
      } catch (err) {
        console.error('Failed to load finance history:', err)
      }
    }
    loadHistory()
    setSelectedHistory(null)
    setData(null)
  }, [profile.userId])

  // Generate savings tips based on spending data
  useEffect(() => {
    if (data?.summary.top_categories) {
      const tips: SavingsTip[] = []
      const categories = data.summary.top_categories

      if (categories['Entertainment'] && categories['Entertainment'] > 100) {
        tips.push({
          id: '1',
          category: 'Entertainment',
          title: 'Reduce streaming subscriptions',
          description: 'Consider bundling or sharing streaming services. Cancel unused subscriptions.',
          potential_savings: Math.round(categories['Entertainment'] * 0.3),
          difficulty: 'easy',
          applied: false
        })
      }

      if (categories['Dining'] && categories['Dining'] > 200) {
        tips.push({
          id: '2',
          category: 'Dining',
          title: 'Meal prep more often',
          description: 'Cooking at home 3 more days per week can save significantly on dining expenses.',
          potential_savings: Math.round(categories['Dining'] * 0.4),
          difficulty: 'medium',
          applied: false
        })
      }

      if (categories['Groceries'] && categories['Groceries'] > 400) {
        tips.push({
          id: '3',
          category: 'Groceries',
          title: 'Use store brands & coupons',
          description: 'Switch to store brands for staples and use digital coupons to save 15-20%.',
          potential_savings: Math.round(categories['Groceries'] * 0.15),
          difficulty: 'easy',
          applied: false
        })
      }

      if (categories['Utilities'] && categories['Utilities'] > 150) {
        tips.push({
          id: '4',
          category: 'Utilities',
          title: 'Energy efficiency improvements',
          description: 'Adjust thermostat, use LED bulbs, and unplug devices to reduce utility bills.',
          potential_savings: Math.round(categories['Utilities'] * 0.1),
          difficulty: 'easy',
          applied: false
        })
      }

      if (data.summary.total_spent > 2000) {
        tips.push({
          id: '5',
          category: 'General',
          title: 'Set up automatic savings',
          description: 'Transfer 10% of income to savings automatically on payday.',
          potential_savings: Math.round(data.summary.total_spent * 0.1),
          difficulty: 'easy',
          applied: false
        })
      }

      tips.push({
        id: '6',
        category: 'General',
        title: 'Review recurring subscriptions',
        description: 'Audit all recurring charges and cancel services you no longer use.',
        potential_savings: 50,
        difficulty: 'easy',
        applied: false
      })

      setSavingsTips(tips)
    }
  }, [data])

  const toggleTipApplied = (id: string) => {
    setSavingsTips(tips => tips.map(tip => 
      tip.id === id ? { ...tip, applied: !tip.applied } : tip
    ))
  }

  const deleteReport = async (id: string) => {
    if (!confirm('Delete this report and its uploaded files?')) return
    try {
      const res = await authenticatedFetch(`${config.apiBase}/api/finance/history/${id}?user_id=${encodeURIComponent(profile.userId)}`, {
        method: 'DELETE'
      })
      if (!res.ok) throw new Error('Delete failed')
      setHistory(prev => prev.filter(r => r.id !== id))
      if (selectedHistory?.id === id) setSelectedHistory(null)
    } catch (err) {
      console.error('Failed to delete finance report:', err)
      alert('Delete failed')
    }
  }

  const totalPotentialSavings = savingsTips.reduce((sum, tip) => sum + tip.potential_savings, 0)
  const appliedSavings = savingsTips.filter(t => t.applied).reduce((sum, tip) => sum + tip.potential_savings, 0)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      if (!file.name.endsWith('.pdf') && !file.name.endsWith('.csv')) {
        setError('Please upload PDF or CSV files only')
        return
      }
    }

    try {
      setUploading(true)
      setError(null)
      const formData = new FormData()
      for (const file of Array.from(files)) {
        formData.append('files', file)
      }

      const response = await authenticatedFetch(`${config.endpoints.financeUploadStatement}?user_id=${encodeURIComponent(profile.userId)}`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Upload failed')
      }

      const result = await response.json()
      setData(result)
      alert(`Parsed ${result.transactions.length} transactions totaling $${result.summary.total_spent.toFixed(2)}`)
    } catch (err: any) {
      console.error('Failed to upload statements:', err)
      setError(err.message || 'Failed to upload statements')
    } finally {
      setUploading(false)
    }
  }

  const getCategoryIcon = (category: string) => {
    switch (category.toLowerCase()) {
      case 'groceries': return <ShoppingCart size={16} />
      case 'utilities': return <Zap size={16} />
      case 'transport': return <Car size={16} />
      case 'entertainment': return <Utensils size={16} />
      default: return <DollarSign size={16} />
    }
  }

  const getCategoryColor = (category: string) => {
    const colors: Record<string, string> = {
      'Groceries': 'bg-green-100 text-green-800',
      'Utilities': 'bg-yellow-100 text-yellow-800',
      'Healthcare': 'bg-red-100 text-red-800',
      'Entertainment': 'bg-purple-100 text-purple-800',
      'Transport': 'bg-blue-100 text-blue-800',
      'Other': 'bg-gray-100 text-gray-800'
    }
    return colors[category] || colors['Other']
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Finance</h1>
          <p className="text-gray-600 mt-2">Track expenses, analyze spending patterns, manage utilities</p>
        </div>
        <ProfileSwitcher onChange={setProfile} />
      </div>

      {/* Upload Section */}
      <div className="mt-8 bg-white rounded-lg shadow p-8">
        <div className="flex flex-col items-center justify-center py-8">
          <Upload className="text-gray-400 mb-4" size={48} />
          <h2 className="text-xl font-semibold text-gray-900">Upload Bank Statements</h2>
          <p className="text-gray-600 mt-2">CSV or PDF format - We'll categorize your transactions</p>
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf,.csv"
            multiple
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="mt-6 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : 'Choose File(s)'}
          </button>
          {error && (
            <p className="mt-4 text-red-600">{error}</p>
          )}
        </div>
      </div>

      {/* Upload History */}
      {history.length > 0 && (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Upload History</h2>
          <ul className="space-y-2">
            {history.map((report, idx) => (
              <li key={idx} className="text-sm text-gray-600 border-b border-gray-100 pb-2 flex items-center justify-between gap-2">
                <button
                    onClick={() => setSelectedHistory(selectedHistory?.id === report.id ? null : report)}
                    className="text-left hover:text-blue-600 flex-1"
                  >
                    {report.uploaded_files?.join(', ')} — {new Date(report.uploaded_at).toLocaleString()} — ${report.summary?.total_spent?.toFixed(2)}
                </button>
                <button
                  onClick={() => deleteReport(report.id)}
                  className="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded border border-red-200"
                  title="Delete"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
          {selectedHistory && (
            <div className="mt-6 border-t border-gray-100 pt-4">
              <h3 className="font-semibold text-gray-900 mb-2">
                {selectedHistory.uploaded_files?.join(', ')}
              </h3>
              {selectedHistory.summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-xs text-gray-500">Total Spent</p>
                    <p className="font-semibold">${selectedHistory.summary.total_spent?.toFixed(2)}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-xs text-gray-500">Transactions</p>
                    <p className="font-semibold">{selectedHistory.summary.transaction_count}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-xs text-gray-500">Flagged</p>
                    <p className="font-semibold">{selectedHistory.summary.flagged_transactions?.length || 0}</p>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <p className="text-xs text-gray-500">Categories</p>
                    <p className="font-semibold">{Object.keys(selectedHistory.summary.top_categories || {}).length}</p>
                  </div>
                </div>
              )}
              {selectedHistory.transactions?.length > 0 && (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">Date</th>
                      <th className="px-4 py-2 text-left">Description</th>
                      <th className="px-4 py-2 text-left">Category</th>
                      <th className="px-4 py-2 text-left">Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selectedHistory.transactions.map((t: any, i: number) => (
                      <tr key={i} className={t.is_flagged ? 'bg-red-50' : ''}>
                        <td className="px-4 py-2">{t.date}</td>
                        <td className="px-4 py-2">{t.description}</td>
                        <td className="px-4 py-2">{t.category}</td>
                        <td className="px-4 py-2">${t.amount?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}

      {/* Summary Stats */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Total Spent</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                ${data?.summary.total_spent.toFixed(2) || '0.00'}
              </p>
            </div>
            <TrendingDown className="text-red-600" size={32} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Transactions</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {data?.summary.transaction_count || 0}
              </p>
            </div>
            <CreditCard className="text-blue-600" size={32} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Flagged</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {data?.summary.flagged_transactions.length || 0}
              </p>
            </div>
            <AlertTriangle className="text-orange-600" size={32} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Categories</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {data?.summary.top_categories ? Object.keys(data.summary.top_categories).length : 0}
              </p>
            </div>
            <ShoppingCart className="text-green-600" size={32} />
          </div>
        </div>
      </div>

      {/* Top Categories */}
      {data?.summary.top_categories && Object.keys(data.summary.top_categories).length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Spending by Category</h2>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="space-y-4">
              {Object.entries(data.summary.top_categories).map(([category, amount]) => (
                <div key={category} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`p-2 rounded-lg ${getCategoryColor(category)}`}>
                      {getCategoryIcon(category)}
                    </span>
                    <span className="font-medium">{category}</span>
                  </div>
                  <span className="font-bold">${amount.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Flagged Transactions */}
      {data?.summary.flagged_transactions && data.summary.flagged_transactions.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Large Transactions (Flagged)</h2>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.summary.flagged_transactions.map((txn, idx) => (
                  <tr key={idx} className="bg-orange-50">
                    <td className="px-6 py-4 whitespace-nowrap">{txn.date}</td>
                    <td className="px-6 py-4">{txn.description}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded ${getCategoryColor(txn.category)}`}>
                        {txn.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-red-600">${txn.amount.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* All Transactions */}
      {data?.transactions && data.transactions.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">All Transactions</h2>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Category</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {data.transactions.slice(0, 20).map((txn, idx) => (
                  <tr key={idx} className={txn.is_flagged ? 'bg-orange-50' : ''}>
                    <td className="px-6 py-4 whitespace-nowrap">{txn.date}</td>
                    <td className="px-6 py-4">{txn.description}</td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs rounded ${getCategoryColor(txn.category)}`}>
                        {txn.category}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right font-medium">${txn.amount.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.transactions.length > 20 && (
              <div className="px-6 py-4 bg-gray-50 text-center text-gray-600">
                Showing 20 of {data.transactions.length} transactions
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Savings Recommendations */}
      {savingsTips.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <Lightbulb className="text-yellow-500" size={24} />
              AI Savings Recommendations
            </h2>
            <div className="bg-green-100 text-green-800 px-4 py-2 rounded-lg">
              <span className="text-sm">Potential Monthly Savings: </span>
              <span className="font-bold">${totalPotentialSavings}</span>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            {savingsTips.map((tip) => (
              <div 
                key={tip.id}
                className={`bg-white rounded-lg shadow p-5 border-l-4 ${
                  tip.applied ? 'border-green-500 bg-green-50' : 'border-yellow-500'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`text-xs px-2 py-1 rounded ${
                        tip.difficulty === 'easy' ? 'bg-green-100 text-green-700' :
                        tip.difficulty === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {tip.difficulty}
                      </span>
                      <span className="text-xs text-gray-500">{tip.category}</span>
                    </div>
                    <h3 className="font-semibold text-gray-900">{tip.title}</h3>
                    <p className="text-sm text-gray-600 mt-1">{tip.description}</p>
                    <p className="text-lg font-bold text-green-600 mt-2">
                      Save ~${tip.potential_savings}/month
                    </p>
                  </div>
                  <button
                    onClick={() => toggleTipApplied(tip.id)}
                    className={`ml-4 p-2 rounded-full ${
                      tip.applied ? 'bg-green-500 text-white' : 'bg-gray-200 text-gray-500'
                    }`}
                  >
                    <CheckCircle size={20} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {appliedSavings > 0 && (
            <div className="mt-4 bg-green-100 border border-green-300 rounded-lg p-4 flex items-center gap-3">
              <PiggyBank className="text-green-600" size={32} />
              <div>
                <p className="font-semibold text-green-800">Great progress!</p>
                <p className="text-green-700">
                  You've committed to saving <strong>${appliedSavings}/month</strong> by applying these tips.
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Budget Goals Section */}
      <div className="mt-8 bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Target className="text-blue-600" size={24} />
          Set Your Financial Goals
        </h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Monthly Budget</label>
            <div className="relative">
              <DollarSign className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="number"
                placeholder="3000"
                value={monthlyBudget}
                onChange={(e) => setMonthlyBudget(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Monthly Savings Goal</label>
            <div className="relative">
              <PiggyBank className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="number"
                placeholder="500"
                value={savingsGoal}
                onChange={(e) => setSavingsGoal(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {monthlyBudget && data?.summary.total_spent && (
          <div className="mt-4 p-4 rounded-lg bg-gray-50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-600">Budget Usage</span>
              <span className="text-sm font-medium">
                ${data.summary.total_spent.toFixed(0)} / ${monthlyBudget}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-3">
              <div 
                className={`h-3 rounded-full ${
                  (data.summary.total_spent / parseFloat(monthlyBudget)) > 1 ? 'bg-red-500' :
                  (data.summary.total_spent / parseFloat(monthlyBudget)) > 0.8 ? 'bg-yellow-500' :
                  'bg-green-500'
                }`}
                style={{ width: `${Math.min((data.summary.total_spent / parseFloat(monthlyBudget)) * 100, 100)}%` }}
              />
            </div>
            {(data.summary.total_spent / parseFloat(monthlyBudget)) > 1 && (
              <p className="text-sm text-red-600 mt-2 flex items-center gap-1">
                <AlertTriangle size={14} />
                You're ${(data.summary.total_spent - parseFloat(monthlyBudget)).toFixed(2)} over budget!
              </p>
            )}
          </div>
        )}
      </div>

      {/* Spending Trends */}
      {data && (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <BarChart3 className="text-purple-600" size={24} />
            Spending Insights
          </h2>
          <div className="grid md:grid-cols-3 gap-4">
            <div className="p-4 bg-purple-50 rounded-lg">
              <p className="text-sm text-purple-700">Average Transaction</p>
              <p className="text-2xl font-bold text-purple-900">
                ${(data.summary.total_spent / data.summary.transaction_count).toFixed(2)}
              </p>
            </div>
            <div className="p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">Largest Category</p>
              <p className="text-2xl font-bold text-blue-900">
                {Object.entries(data.summary.top_categories).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'}
              </p>
            </div>
            <div className="p-4 bg-green-50 rounded-lg">
              <p className="text-sm text-green-700">Potential Savings</p>
              <p className="text-2xl font-bold text-green-900 flex items-center gap-1">
                <TrendingUp size={20} /> ${totalPotentialSavings}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900">Tips for Better Tracking</h3>
        <ul className="mt-2 text-blue-800 text-sm space-y-1">
          <li>• Upload statements monthly to track spending trends</li>
          <li>• Large transactions (&gt;$500) are automatically flagged for review</li>
          <li>• Categories are auto-detected based on merchant names</li>
          <li>• Supports CSV exports from most banks and PDF statements</li>
          <li>• Use the AI recommendations to identify savings opportunities</li>
        </ul>
      </div>
    </div>
  )
}
