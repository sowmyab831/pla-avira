import { authenticatedFetch } from '../api/authenticatedFetch'
import React, { useState, useRef, useEffect } from 'react'
import { Upload, AlertTriangle, Activity, FileText, User, Scale, Ruler, Target, Heart, Stethoscope, ThumbsUp, CheckCircle, TrendingUp, Calendar } from 'lucide-react'
import config from '../config'
import ProfileSwitcher, { getActiveProfile, Profile } from '../components/ProfileSwitcher'

interface LabResult {
  test_name: string
  value: number
  unit: string
  reference_range: string
  is_abnormal: boolean
  date: string
}

interface HealthAlert {
  alert_type: string
  test_name: string
  value: number
  threshold: number
  message: string
}

interface HealthReport {
  lab_results: LabResult[]
  alerts: HealthAlert[]
  last_updated: string
}

interface UserProfile {
  age: string
  weight: string
  weightUnit: 'lbs' | 'kg'
  height: string
  heightFt: string
  heightIn: string
  gender: string
  goals: string[]
}

interface SpecialistRecommendation {
  specialty: string
  reason: string
  urgency: 'routine' | 'soon' | 'urgent'
  tests: string[]
}

export default function Health() {
  const [uploading, setUploading] = useState(false)
  const [report, setReport] = useState<HealthReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [userProfile, setUserProfile] = useState<UserProfile>({
    age: '',
    weight: '',
    weightUnit: 'lbs',
    height: '',
    heightFt: '',
    heightIn: '',
    gender: '',
    goals: []
  })
  const [showProfileForm, setShowProfileForm] = useState(true)
  const [specialists, setSpecialists] = useState<SpecialistRecommendation[]>([])
  const [healthSummary, setHealthSummary] = useState('')
  const [docAnalysis, setDocAnalysis] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [selectedHistory, setSelectedHistory] = useState<any | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [timeline, setTimeline] = useState<any>(null)
  const [aiSummary, setAiSummary] = useState<any>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [profile, setProfile] = useState<Profile>(getActiveProfile())
  const cameraInputRef = useRef<HTMLInputElement>(null)

  // Load profile from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('healthProfile')
    if (saved) {
      const parsed = JSON.parse(saved)
      const heightInches = parseFloat(parsed.height || '0')
      setUserProfile({
        ...parsed,
        weightUnit: parsed.weightUnit || 'lbs',
        heightFt: parsed.heightFt || Math.floor(heightInches / 12).toString(),
        heightIn: parsed.heightIn || Math.round(heightInches % 12).toString(),
      })
      setShowProfileForm(false)
    }
  }, [])

  // Save profile to localStorage
  const saveProfile = () => {
    localStorage.setItem('healthProfile', JSON.stringify(userProfile))
    setShowProfileForm(false)
  }

  // Load chronological health timeline and AI summary
  const loadTimelineAndSummary = async () => {
    setSummaryLoading(true)
    try {
      const uid = encodeURIComponent(profile.userId)
      const [tRes, sRes] = await Promise.all([
        authenticatedFetch(`${config.endpoints.healthTimeline}?user_id=${uid}`),
        authenticatedFetch(`${config.endpoints.healthSummary}?user_id=${uid}`),
      ])
      const tData = await tRes.json()
      const sData = await sRes.json()
      if (tData.success) {
        setTimeline(tData)
        setHistory(tData.reports || [])
      }
      if (sData.success) {
        setAiSummary(sData)
      }
    } catch (err) {
      console.error('Failed to load health timeline/summary:', err)
    } finally {
      setSummaryLoading(false)
    }
  }

  const deleteHealthDocument = async (id: string) => {
    if (!confirm('Delete this health document and its analysis?')) return
    try {
      const res = await authenticatedFetch(`${config.apiBase}/api/health/documents/${id}?user_id=${encodeURIComponent(profile.userId)}`, {
        method: 'DELETE'
      })
      if (!res.ok) throw new Error('Delete failed')
      setHistory(prev => prev.filter(d => d.id !== id))
      if (selectedHistory?.id === id) setSelectedHistory(null)
      setSelectedIds(prev => { const next = new Set(prev); next.delete(id); return next })
    } catch (err) {
      console.error('Failed to delete health document:', err)
      alert('Delete failed')
    }
  }

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === history.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(history.map(d => d.id)))
    }
  }

  const deleteSelected = async () => {
    if (selectedIds.size === 0) return
    if (!confirm(`Delete ${selectedIds.size} selected document${selectedIds.size > 1 ? 's' : ''} and their analysis?`)) return
    setBulkDeleting(true)
    const ids = Array.from(selectedIds)
    const failed: string[] = []
    for (const id of ids) {
      try {
        const res = await authenticatedFetch(`${config.apiBase}/api/health/documents/${id}?user_id=${encodeURIComponent(profile.userId)}`, {
          method: 'DELETE'
        })
        if (!res.ok) failed.push(id)
      } catch {
        failed.push(id)
      }
    }
    setHistory(prev => prev.filter(d => !selectedIds.has(d.id) || failed.includes(d.id)))
    if (selectedHistory && selectedIds.has(selectedHistory.id) && !failed.includes(selectedHistory.id)) {
      setSelectedHistory(null)
    }
    setSelectedIds(new Set(failed))
    setBulkDeleting(false)
    if (failed.length > 0) alert(`${failed.length} document(s) could not be deleted`)
  }

  useEffect(() => {
    loadTimelineAndSummary()
    setSelectedHistory(null)
    setReport(null)
    setDocAnalysis(null)
  }, [profile.userId])

  // Generate specialist recommendations based on alerts
  useEffect(() => {
    if (report?.alerts && report.alerts.length > 0) {
      const recs: SpecialistRecommendation[] = []
      
      report.alerts.forEach(alert => {
        const testLower = alert.test_name.toLowerCase()
        
        if (testLower.includes('cholesterol') || testLower.includes('ldl') || testLower.includes('hdl') || testLower.includes('triglyceride')) {
          if (!recs.find(r => r.specialty === 'Cardiologist')) {
            recs.push({
              specialty: 'Cardiologist',
              reason: 'Your lipid panel results suggest a cardiovascular health evaluation would be beneficial.',
              urgency: alert.alert_type === 'critical' ? 'urgent' : 'soon',
              tests: ['Cholesterol', 'LDL', 'HDL', 'Triglycerides']
            })
          }
        }
        
        if (testLower.includes('glucose') || testLower.includes('a1c') || testLower.includes('hba1c')) {
          if (!recs.find(r => r.specialty === 'Endocrinologist')) {
            recs.push({
              specialty: 'Endocrinologist',
              reason: 'Your blood sugar levels indicate you may benefit from metabolic health screening.',
              urgency: alert.alert_type === 'critical' ? 'urgent' : 'soon',
              tests: ['Glucose', 'HbA1c']
            })
          }
        }
        
        if (testLower.includes('tsh') || testLower.includes('t3') || testLower.includes('t4') || testLower.includes('thyroid')) {
          if (!recs.find(r => r.specialty === 'Endocrinologist')) {
            recs.push({
              specialty: 'Endocrinologist',
              reason: 'Your thyroid markers suggest further evaluation would be helpful.',
              urgency: 'soon',
              tests: ['TSH', 'T3', 'T4']
            })
          }
        }
        
        if (testLower.includes('creatinine') || testLower.includes('bun') || testLower.includes('gfr')) {
          if (!recs.find(r => r.specialty === 'Nephrologist')) {
            recs.push({
              specialty: 'Nephrologist',
              reason: 'Your kidney function markers indicate a kidney health evaluation may be beneficial.',
              urgency: alert.alert_type === 'critical' ? 'urgent' : 'routine',
              tests: ['Creatinine', 'BUN', 'GFR']
            })
          }
        }

        if (testLower.includes('ast') || testLower.includes('alt') || testLower.includes('bilirubin')) {
          if (!recs.find(r => r.specialty === 'Hepatologist/Gastroenterologist')) {
            recs.push({
              specialty: 'Hepatologist/Gastroenterologist',
              reason: 'Your liver function tests suggest a liver health evaluation could be helpful.',
              urgency: alert.alert_type === 'critical' ? 'soon' : 'routine',
              tests: ['AST', 'ALT', 'Bilirubin']
            })
          }
        }
      })
      
      setSpecialists(recs)
      
      // Generate positive summary
      const normalCount = report.lab_results.filter(r => !r.is_abnormal).length
      const totalCount = report.lab_results.length
      const normalPercent = Math.round((normalCount / totalCount) * 100)
      
      if (normalPercent >= 90) {
        setHealthSummary(`Great news! ${normalPercent}% of your lab results are within normal ranges. Your overall health picture looks excellent. Keep up the great work with your healthy lifestyle!`)
      } else if (normalPercent >= 70) {
        setHealthSummary(`Good progress! ${normalPercent}% of your lab results are within normal ranges. While there are a few areas to focus on, your health foundation is solid. With some targeted improvements, you'll be doing even better.`)
      } else {
        setHealthSummary(`Your results show ${normalPercent}% within normal ranges. Don't worry - knowledge is power! Working with your healthcare team on the areas below can help you improve these numbers. Many people see significant improvements with lifestyle changes.`)
      }
    }
  }, [report])

  const healthGoals = [
    'Weight Management',
    'Build Muscle',
    'Improve Energy',
    'Better Sleep',
    'Heart Health',
    'Manage Diabetes',
    'Reduce Stress',
    'Improve Fitness'
  ]

  const toggleGoal = (goal: string) => {
    setUserProfile(prev => ({
      ...prev,
      goals: prev.goals.includes(goal)
        ? prev.goals.filter(g => g !== goal)
        : [...prev.goals, goal]
    }))
  }

  const calculateBMI = () => {
    if (userProfile.height && userProfile.weight) {
      const heightM = parseFloat(userProfile.height) * 0.0254 // inches to meters
      const weightKg = userProfile.weightUnit === 'kg'
        ? parseFloat(userProfile.weight)
        : parseFloat(userProfile.weight) * 0.453592
      return (weightKg / (heightM * heightM)).toFixed(1)
    }
    return null
  }

  const getBMICategory = (bmi: number) => {
    if (bmi < 18.5) return { label: 'Underweight', color: 'text-yellow-600' }
    if (bmi < 25) return { label: 'Healthy', color: 'text-green-600' }
    if (bmi < 30) return { label: 'Overweight', color: 'text-yellow-600' }
    return { label: 'Obese', color: 'text-red-600' }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return

    for (const file of Array.from(files)) {
      if (!file.name.endsWith('.pdf')) {
        setError('Please upload PDF files only')
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

      const response = await authenticatedFetch(`${config.endpoints.healthUploadLabResults}?user_id=${encodeURIComponent(profile.userId)}`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Upload failed')
      }

      const data = await response.json()
      setReport(data)
      setDocAnalysis(data.analysis)
      await loadTimelineAndSummary()
      alert(`Parsed ${data.lab_results.length} lab results with ${data.alerts.length} alerts`)
    } catch (err: any) {
      console.error('Failed to upload lab results:', err)
      setError(err.message || 'Failed to upload lab results')
    } finally {
      setUploading(false)
    }
  }

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    try {
      setUploading(true)
      setError(null)
      const formData = new FormData()
      formData.append('file', file)

      const response = await authenticatedFetch(`${config.apiBase}/api/health/upload-image?user_id=${encodeURIComponent(profile.userId)}`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errData = await response.json()
        throw new Error(errData.detail || 'Upload failed')
      }

      const data = await response.json()
      setDocAnalysis(data)
      await loadTimelineAndSummary()
      alert('Document analyzed! See results below.')
    } catch (err: any) {
      console.error('Failed to upload image:', err)
      setError(err.message || 'Failed to upload image')
    } finally {
      setUploading(false)
    }
  }

  const getAlertColor = (type: string) => {
    switch (type) {
      case 'critical': return 'bg-red-100 border-red-500 text-red-900'
      case 'high': return 'bg-orange-100 border-orange-500 text-orange-900'
      case 'low': return 'bg-yellow-100 border-yellow-500 text-yellow-900'
      default: return 'bg-gray-100 border-gray-500 text-gray-900'
    }
  }

  const bmi = calculateBMI()
  const bmiCategory = bmi ? getBMICategory(parseFloat(bmi)) : null

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-teal-600 rounded-xl flex items-center justify-center">
          <Heart className="text-white" size={24} />
        </div>
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-gray-900">Health Dashboard</h1>
          <p className="text-gray-600">Track your health journey with personalized insights</p>
        </div>
        <ProfileSwitcher onChange={setProfile} />
      </div>

      {/* User Profile Section */}
      {showProfileForm ? (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <User className="text-blue-600" size={24} />
            Your Health Profile
          </h2>
          <div className="grid md:grid-cols-4 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Age</label>
              <input
                type="number"
                placeholder="35"
                value={userProfile.age}
                onChange={(e) => setUserProfile({ ...userProfile, age: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <Scale size={14} /> Weight
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="160"
                  value={userProfile.weight}
                  onChange={(e) => setUserProfile({ ...userProfile, weight: e.target.value })}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
                <select
                  value={userProfile.weightUnit}
                  onChange={(e) => {
                    const unit = e.target.value as 'lbs' | 'kg'
                    const value = parseFloat(userProfile.weight || '0')
                    const converted = unit === 'kg'
                      ? (value * 0.453592).toFixed(1)
                      : (value / 0.453592).toFixed(1)
                    setUserProfile({ ...userProfile, weight: String(parseFloat(converted)), weightUnit: unit })
                  }}
                  className="px-3 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                >
                  <option value="lbs">lbs</option>
                  <option value="kg">kg</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
                <Ruler size={14} /> Height
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="5"
                  value={userProfile.heightFt}
                  onChange={(e) => {
                    const ft = e.target.value
                    const inches = (parseFloat(ft || '0') * 12 + parseFloat(userProfile.heightIn || '0')).toString()
                    setUserProfile({ ...userProfile, heightFt: ft, height: inches })
                  }}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
                <span className="self-center text-gray-600">ft</span>
                <input
                  type="number"
                  placeholder="8"
                  value={userProfile.heightIn}
                  onChange={(e) => {
                    const ins = e.target.value
                    const inches = (parseFloat(userProfile.heightFt || '0') * 12 + parseFloat(ins || '0')).toString()
                    setUserProfile({ ...userProfile, heightIn: ins, height: inches })
                  }}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
                />
                <span className="self-center text-gray-600">in</span>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Gender</label>
              <select
                value={userProfile.gender}
                onChange={(e) => setUserProfile({ ...userProfile, gender: e.target.value })}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-blue-500 focus:outline-none"
              >
                <option value="">Select...</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2 flex items-center gap-1">
              <Target size={14} /> Health Goals
            </label>
            <div className="flex flex-wrap gap-2">
              {healthGoals.map(goal => (
                <button
                  key={goal}
                  onClick={() => toggleGoal(goal)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                    userProfile.goals.includes(goal)
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {userProfile.goals.includes(goal) && <CheckCircle size={14} className="inline mr-1" />}
                  {goal}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={saveProfile}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            Save Profile
          </button>
        </div>
      ) : (
        <div className="mt-8 bg-gradient-to-r from-green-50 to-teal-50 rounded-lg p-6 border border-green-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div className="text-center">
                <p className="text-xs text-gray-500">Age</p>
                <p className="text-xl font-bold text-gray-900">{userProfile.age} yrs</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-500">Weight</p>
                <p className="text-xl font-bold text-gray-900">{userProfile.weight} {userProfile.weightUnit}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-gray-500">Height</p>
                <p className="text-xl font-bold text-gray-900">{userProfile.heightFt}'{userProfile.heightIn}"</p>
              </div>
              {bmi && (
                <div className="text-center">
                  <p className="text-xs text-gray-500">BMI</p>
                  <p className={`text-xl font-bold ${bmiCategory?.color}`}>{bmi} ({bmiCategory?.label})</p>
                </div>
              )}
            </div>
            <button
              onClick={() => setShowProfileForm(true)}
              className="text-green-600 hover:text-green-800 text-sm"
            >
              Edit Profile
            </button>
          </div>
          {userProfile.goals.length > 0 && (
            <div className="mt-3 pt-3 border-t border-green-200">
              <p className="text-xs text-gray-500 mb-1">Goals:</p>
              <div className="flex gap-2 flex-wrap">
                {userProfile.goals.map(g => (
                  <span key={g} className="px-2 py-1 bg-green-100 text-green-700 rounded text-xs">{g}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Upload Section */}
      <div className="mt-8 bg-white rounded-lg shadow p-8">
        <div className="flex flex-col items-center justify-center py-8">
          <Upload className="text-gray-400 mb-4" size={48} />
          <h2 className="text-xl font-semibold text-gray-900">Upload Medical Document</h2>
          <p className="text-gray-600 mt-2">Photo or PDF — lab reports, doctor's notes, prescriptions, etc.</p>
          <div className="flex gap-3 mt-6">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {uploading ? 'Analyzing...' : 'Upload PDF(s)'}
            </button>
            <button
              onClick={() => cameraInputRef.current?.click()}
              disabled={uploading}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {uploading ? 'Analyzing...' : '📷 Take Photo'}
            </button>
          </div>
          <input
            type="file"
            ref={fileInputRef}
            accept=".pdf"
            multiple
            onChange={handleUpload}
            className="hidden"
          />
          <input
            type="file"
            ref={cameraInputRef}
            accept="image/*"
            capture="environment"
            onChange={handleImageUpload}
            className="hidden"
          />
          {error && (
            <p className="mt-4 text-red-600">{error}</p>
          )}
        </div>
      </div>

      {/* AI Health Summary */}
      {(summaryLoading || aiSummary) && (
        <div className="mt-8 bg-gradient-to-r from-indigo-50 to-blue-50 rounded-lg p-6 border border-indigo-200">
          <div className="flex items-start gap-4">
            <Stethoscope className="text-indigo-600 flex-shrink-0" size={32} />
            <div className="w-full">
              <h3 className="font-semibold text-indigo-900 text-lg">Health Summary & Recommendations</h3>
              {summaryLoading ? (
                <p className="text-indigo-800 mt-2">Generating summary...</p>
              ) : (
                <>
                  {aiSummary?.structured?.health_status && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-sm font-medium text-indigo-900">Overall status:</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                        aiSummary.structured.health_status === 'Good' ? 'bg-green-100 text-green-700' :
                        aiSummary.structured.health_status === 'Fair' ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {aiSummary.structured.health_status}
                      </span>
                    </div>
                  )}
                  {aiSummary?.summary && (
                    <pre className="bg-white/70 p-4 rounded-lg text-sm whitespace-pre-wrap mt-3 text-indigo-900">
                      {aiSummary.summary}
                    </pre>
                  )}
                  {aiSummary?.structured?.recommended_doctors?.length > 0 && (
                    <div className="mt-3">
                      <span className="text-sm font-medium text-indigo-900">Recommended specialists:</span>
                      <div className="flex gap-2 flex-wrap mt-1">
                        {aiSummary.structured.recommended_doctors.map((doc: string, idx: number) => (
                          <span key={idx} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                            {doc}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {aiSummary?.disclaimer && (
                    <p className="text-xs text-indigo-700 mt-3 italic">{aiSummary.disclaimer}</p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Upload History */}
      {history.length > 0 && (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
              <Calendar className="text-blue-600" size={20} />
              Upload Timeline
            </h2>
            {selectedIds.size > 0 && (
              <button
                onClick={deleteSelected}
                disabled={bulkDeleting}
                className="text-xs px-3 py-1.5 rounded-lg bg-red-600 text-white font-semibold hover:bg-red-700 disabled:opacity-50"
              >
                {bulkDeleting ? 'Deleting…' : `Delete selected (${selectedIds.size})`}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
            <input
              type="checkbox"
              checked={history.length > 0 && selectedIds.size === history.length}
              onChange={toggleSelectAll}
              className="rounded border-gray-300"
            />
            <span>Select all</span>
          </div>
          <ul className="space-y-2">
            {history.map((doc, idx) => (
              <li key={idx} className="text-sm text-gray-600 border-b border-gray-100 pb-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(doc.id)}
                    onChange={() => toggleSelect(doc.id)}
                    className="rounded border-gray-300 flex-shrink-0"
                  />
                  <button
                    onClick={() => setSelectedHistory(selectedHistory?.id === doc.id ? null : doc)}
                    className="text-left hover:text-blue-600 flex-1 min-w-0 truncate"
                  >
                    {doc.report_date || doc.uploaded_at?.slice(0, 10)} — {doc.filename} — {doc.lab_results?.length || 0} results
                    {doc.alerts?.length > 0 && <span className="ml-2 text-red-600">({doc.alerts.length} alerts)</span>}
                  </button>
                </div>
                <button
                  onClick={() => deleteHealthDocument(doc.id)}
                  className="text-red-500 hover:text-red-700 text-xs px-2 py-1 rounded border border-red-200 flex-shrink-0"
                  title="Delete"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
          {selectedHistory && (
            <div className="mt-6 border-t border-gray-100 pt-4">
              <h3 className="font-semibold text-gray-900 mb-2">{selectedHistory.filename}</h3>
              {selectedHistory.lab_results?.length > 0 && (
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left">Test</th>
                      <th className="px-4 py-2 text-left">Value</th>
                      <th className="px-4 py-2 text-left">Reference</th>
                      <th className="px-4 py-2 text-left">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {selectedHistory.lab_results.map((r: any, i: number) => (
                      <tr key={i} className={r.is_abnormal ? 'bg-red-50' : ''}>
                        <td className="px-4 py-2">{r.test_name}</td>
                        <td className="px-4 py-2">{r.value} {r.unit}</td>
                        <td className="px-4 py-2 text-gray-500">{r.reference_range}</td>
                        <td className="px-4 py-2">{r.is_abnormal ? 'Abnormal' : 'Normal'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {selectedHistory.alerts?.length > 0 && (
                <div className="mt-4 space-y-2">
                  {selectedHistory.alerts.map((a: any, i: number) => (
                    <div key={i} className="p-3 bg-red-50 border-l-4 border-red-400 text-sm">
                      <span className="font-semibold">{a.test_name}</span> — {a.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Lab Result Trends */}
      {timeline?.trends && Object.keys(timeline.trends).length > 0 && (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="text-green-600" size={24} />
            Lab Result Trends
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">Test</th>
                  <th className="px-4 py-2 text-left">Latest Value</th>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-left">Trend</th>
                  <th className="px-4 py-2 text-left">Reference</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {Object.entries(timeline.trends).map(([testName, series]: [string, any]) => {
                  const sorted = [...(series as any[])].sort((a: any, b: any) => a.date.localeCompare(b.date))
                  const latest = sorted[sorted.length - 1]
                  const prev = sorted[sorted.length - 2]
                  return (
                    <tr key={testName} className={latest.is_abnormal ? 'bg-red-50' : ''}>
                      <td className="px-4 py-2 font-medium">{testName}</td>
                      <td className="px-4 py-2">{latest.value} {latest.unit}</td>
                      <td className="px-4 py-2 text-gray-500">{latest.date}</td>
                      <td className="px-4 py-2">
                        {prev ? (
                          <span className={`text-xs px-2 py-1 rounded ${
                            latest.direction === 'increasing' ? 'bg-yellow-100 text-yellow-700' :
                            latest.direction === 'decreasing' ? 'bg-blue-100 text-blue-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {latest.direction === 'increasing' ? '↑ Rising' :
                             latest.direction === 'decreasing' ? '↓ Falling' :
                             '→ Stable'} ({prev.value})
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded">First reading</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{latest.reference_range || '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Document Analysis Results */}
      {docAnalysis && (
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Stethoscope className="text-purple-600" size={24} />
            AI Document Analysis
          </h2>
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
            <p className="text-sm text-yellow-800">
              <strong>Disclaimer:</strong> This is AI-generated analysis for informational purposes only.
              Always consult licensed healthcare professionals for diagnosis and treatment.
            </p>
          </div>
          <div className="space-y-4">
            {docAnalysis.analysis?.structured?.health_status && (
              <div className="flex items-center gap-3">
                <span className="font-medium">Status:</span>
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                  docAnalysis.analysis.structured.health_status === 'Good' ? 'bg-green-100 text-green-700' :
                  docAnalysis.analysis.structured.health_status === 'Fair' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {docAnalysis.analysis.structured.health_status}
                </span>
              </div>
            )}
            {docAnalysis.analysis?.analysis && (
              <div className="prose max-w-none">
                <pre className="bg-gray-50 p-4 rounded-lg text-sm whitespace-pre-wrap">
                  {docAnalysis.analysis.analysis}
                </pre>
              </div>
            )}
            {docAnalysis.analysis?.structured?.recommended_doctors && (
              <div>
                <h3 className="font-semibold text-gray-900 mb-2">Recommended Specialists</h3>
                <div className="flex gap-2 flex-wrap">
                  {docAnalysis.analysis.structured.recommended_doctors.map((doc: string, idx: number) => (
                    <span key={idx} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                      {doc}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Positive Health Summary */}
      {healthSummary && (
        <div className="mt-8 bg-gradient-to-r from-blue-50 to-green-50 rounded-lg p-6 border border-blue-200">
          <div className="flex items-start gap-4">
            <ThumbsUp className="text-blue-600 flex-shrink-0" size={32} />
            <div>
              <h3 className="font-semibold text-blue-900 text-lg">Your Health Summary</h3>
              <p className="text-blue-800 mt-2">{healthSummary}</p>
            </div>
          </div>
        </div>
      )}

      {/* Health Alerts */}
      {report && report.alerts.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Health Alerts</h2>
          <div className="space-y-4">
            {report.alerts.map((alert, idx) => (
              <div key={idx} className={`p-4 rounded-lg border-l-4 ${getAlertColor(alert.alert_type)}`}>
                <div className="flex items-center gap-2">
                  <AlertTriangle size={20} />
                  <span className="font-semibold">{alert.test_name}</span>
                  <span className="text-sm px-2 py-1 bg-white bg-opacity-50 rounded uppercase">
                    {alert.alert_type}
                  </span>
                </div>
                <p className="mt-2">{alert.message}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lab Results */}
      {report && report.lab_results.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Lab Results</h2>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Test</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reference</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {report.lab_results.map((result, idx) => (
                  <tr key={idx} className={result.is_abnormal ? 'bg-red-50' : ''}>
                    <td className="px-6 py-4 whitespace-nowrap font-medium">{result.test_name}</td>
                    <td className="px-6 py-4 whitespace-nowrap">{result.value} {result.unit}</td>
                    <td className="px-6 py-4 whitespace-nowrap text-gray-500">{result.reference_range}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {result.is_abnormal ? (
                        <span className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded">Abnormal</span>
                      ) : (
                        <span className="px-2 py-1 text-xs bg-green-100 text-green-800 rounded">Normal</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Lab Results</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{report?.lab_results.length || 0}</p>
            </div>
            <FileText className="text-blue-600" size={32} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Alerts</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{report?.alerts.length || 0}</p>
            </div>
            <AlertTriangle className="text-orange-600" size={32} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Last Updated</p>
              <p className="text-lg font-bold text-gray-900 mt-1">
                {report ? new Date(report.last_updated).toLocaleDateString() : 'Never'}
              </p>
            </div>
            <Activity className="text-green-600" size={32} />
          </div>
        </div>
      </div>

      {/* Specialist Recommendations */}
      {specialists.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Stethoscope className="text-purple-600" size={24} />
            Recommended Specialists
          </h2>
          <p className="text-gray-600 mb-4">
            Based on your lab results, here are some specialists who may help you on your health journey:
          </p>
          <div className="grid md:grid-cols-2 gap-4">
            {specialists.map((spec, idx) => (
              <div
                key={idx}
                className={`bg-white rounded-lg shadow p-5 border-l-4 ${
                  spec.urgency === 'urgent' ? 'border-red-500' :
                  spec.urgency === 'soon' ? 'border-yellow-500' :
                  'border-green-500'
                }`}
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="font-semibold text-lg text-gray-900">{spec.specialty}</h3>
                  <span className={`text-xs px-2 py-1 rounded ${
                    spec.urgency === 'urgent' ? 'bg-red-100 text-red-700' :
                    spec.urgency === 'soon' ? 'bg-yellow-100 text-yellow-700' :
                    'bg-green-100 text-green-700'
                  }`}>
                    {spec.urgency === 'urgent' ? 'Schedule Soon' : 
                     spec.urgency === 'soon' ? 'Schedule Within Month' : 
                     'Routine Visit'}
                  </span>
                </div>
                <p className="text-gray-600 text-sm mb-3">{spec.reason}</p>
                <div className="flex gap-2 flex-wrap">
                  {spec.tests.map((test, i) => (
                    <span key={i} className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                      {test}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Positive Encouragement when no alerts */}
      {report && report.alerts.length === 0 && (
        <div className="mt-8 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg p-6 border border-green-200">
          <div className="flex items-start gap-4">
            <ThumbsUp className="text-green-600 flex-shrink-0" size={32} />
            <div>
              <h3 className="font-semibold text-green-900 text-lg">Excellent Health!</h3>
              <p className="text-green-800 mt-2">
                All your lab results are within normal ranges. Keep up the great work maintaining your health! 
                Continue with your healthy habits and schedule regular check-ups to stay on track.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* HIPAA Notice */}
      <div className="mt-8 bg-yellow-50 border border-yellow-200 rounded-lg p-6 flex gap-4">
        <AlertTriangle className="text-yellow-600 flex-shrink-0" size={24} />
        <div>
          <h3 className="font-semibold text-yellow-900">Privacy & HIPAA Notice</h3>
          <p className="text-yellow-800 text-sm mt-2">
            Your health data is processed locally and encrypted. All recommendations are AI-generated suggestions 
            and should not replace professional medical advice. Always consult with your healthcare provider 
            before making any health decisions.
          </p>
        </div>
      </div>
    </div>
  )
}
