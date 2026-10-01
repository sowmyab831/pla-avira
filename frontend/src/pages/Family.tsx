import { useState, useEffect } from 'react'
import { Users, Heart, Calendar, TrendingUp, Smile, Plus, X, Shield, DollarSign, Activity, Trash2 } from 'lucide-react'
import config from '../config'
import { familyApi } from '../api/nexus'

interface FamilyMember {
  kid_id: string
  name: string
  age: number
  grade?: string
  school?: string
  interests?: string[]
}

interface AddMemberForm {
  name: string
  date_of_birth: string
  age: number
  grade: string
  school: string
  interests: string
  strengths: string
  personality_traits: string
  learning_style: string
}

interface CheckInForm {
  member_id: string
  mood: string
  mood_score: number
  stress_level: number
  energy_level: number
  notes: string
  needs_support: boolean
}

export default function Family() {
  const [members, setMembers] = useState<FamilyMember[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddModal, setShowAddModal] = useState(false)
  const [showCheckInModal, setShowCheckInModal] = useState(false)
  const [addForm, setAddForm] = useState<AddMemberForm>({
    name: '',
    date_of_birth: '',
    age: 0,
    grade: '',
    school: '',
    interests: '',
    strengths: '',
    personality_traits: '',
    learning_style: 'Visual'
  })
  const [checkInForm, setCheckInForm] = useState<CheckInForm>({
    member_id: '',
    mood: 'happy',
    mood_score: 5,
    stress_level: 5,
    energy_level: 5,
    notes: '',
    needs_support: false
  })
  const [oversight, setOversight] = useState<any[]>([])
  const [oversightError, setOversightError] = useState('')
  const [hubForm, setHubForm] = useState({ name: '', role: 'child', birthdate: '' })
  const [showHubForm, setShowHubForm] = useState(false)

  useEffect(() => {
    fetchFamilyData()
    loadOversight()
  }, [])

  const loadOversight = async () => {
    try {
      const d = await familyApi.oversight()
      setOversight(d.members || [])
      setOversightError('')
    } catch (e: any) {
      const detail = e?.response?.data
      const inner = typeof detail?.detail === 'object' ? detail.detail : detail
      const msg = typeof inner === 'object' ? (inner.error || inner.message || 'Oversight unavailable') : (inner || 'Oversight requires sign-in')
      setOversightError(String(msg))
    }
  }

  const addHubMember = async () => {
    if (!hubForm.name.trim()) return
    try {
      await familyApi.addMember({
        name: hubForm.name.trim(),
        role: hubForm.role,
        birthdate: hubForm.birthdate || undefined,
      })
      setHubForm({ name: '', role: 'child', birthdate: '' })
      setShowHubForm(false)
      loadOversight()
    } catch (e: any) {
      const detail = e?.response?.data
      const inner = typeof detail?.detail === 'object' ? detail.detail : detail
      const msg = typeof inner === 'object' ? (inner.error || inner.message || 'Failed to add member') : 'Failed to add member'
      alert(String(msg))
    }
  }

  const removeHubMember = async (id: string) => {
    if (!confirm('Remove this family profile? Their uploaded health/finance data stays stored under their profile.')) return
    try {
      await familyApi.removeMember(id)
      loadOversight()
    } catch {
      alert('Failed to remove member')
    }
  }

  const fetchFamilyData = async () => {
    try {
      setLoading(true)
      const response = await fetch(`${config.apiBase}/api/family/kids?family_id=default`)
      const data = await response.json()
      
      if (data.success) {
        setMembers(data.kids || [])
      }
    } catch (error) {
      console.error('Failed to fetch family data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAddMember = async () => {
    try {
      const memberData = {
        kid_id: `kid_${Date.now()}`,
        family_id: 'default',
        name: addForm.name,
        date_of_birth: addForm.date_of_birth,
        age: addForm.age,
        grade: addForm.grade,
        school: addForm.school,
        interests: addForm.interests.split(',').map(i => i.trim()),
        strengths: addForm.strengths.split(',').map(s => s.trim()),
        areas_for_growth: [],
        personality_traits: addForm.personality_traits.split(',').map(p => p.trim()),
        learning_style: addForm.learning_style
      }

      const response = await fetch(`${config.apiBase}/api/family/kids`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(memberData)
      })

      const data = await response.json()
      if (data.success) {
        fetchFamilyData()
        setShowAddModal(false)
        setAddForm({
          name: '',
          date_of_birth: '',
          age: 0,
          grade: '',
          school: '',
          interests: '',
          strengths: '',
          personality_traits: '',
          learning_style: 'Visual'
        })
      }
    } catch (error) {
      console.error('Failed to add family member:', error)
    }
  }

  const handleCheckIn = async () => {
    try {
      const checkInData = {
        checkin_id: `checkin_${Date.now()}`,
        member_id: checkInForm.member_id,
        date: new Date().toISOString().split('T')[0],
        mood: checkInForm.mood,
        mood_score: checkInForm.mood_score,
        stress_level: checkInForm.stress_level,
        energy_level: checkInForm.energy_level,
        notes: checkInForm.notes,
        needs_support: checkInForm.needs_support,
        support_type: checkInForm.needs_support ? 'emotional' : null
      }

      const response = await fetch(`${config.apiBase}/api/family/checkin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(checkInData)
      })

      const data = await response.json()
      if (data.success) {
        alert('Check-in recorded successfully!')
        setShowCheckInModal(false)
        setCheckInForm({
          member_id: '',
          mood: 'happy',
          mood_score: 5,
          stress_level: 5,
          energy_level: 5,
          notes: '',
          needs_support: false
        })
      }
    } catch (error) {
      console.error('Failed to record check-in:', error)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 bg-gradient-to-br from-pink-500 to-rose-600 rounded-xl flex items-center justify-center">
            <Users className="text-white" size={24} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Family Dashboard</h1>
            <p className="text-gray-600">Manage your family's activities and wellbeing</p>
          </div>
        </div>
      </div>

      {/* Family Oversight — per-member health & finance wellbeing (Enterprise) */}
      <div className="mb-8 bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Shield className="text-indigo-600" size={20} />
            <h2 className="text-xl font-semibold text-gray-900">Family Oversight</h2>
            <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">Enterprise</span>
          </div>
          <button
            onClick={() => setShowHubForm(v => !v)}
            className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700"
          >
            <Plus size={14} /> Add Profile
          </button>
        </div>
        <p className="text-sm text-gray-500 mb-4">
          Each family profile gets its own directory for health &amp; finance uploads. Select a profile on the Health or Finance page to manage their data.
        </p>

        {showHubForm && (
          <div className="flex flex-wrap items-end gap-3 mb-4 p-4 bg-gray-50 rounded-lg">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Name</label>
              <input value={hubForm.name} onChange={e => setHubForm(f => ({ ...f, name: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" placeholder="e.g. Emma" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Role</label>
              <select value={hubForm.role} onChange={e => setHubForm(f => ({ ...f, role: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
                <option value="child">Child</option>
                <option value="partner">Partner</option>
                <option value="parent">Parent</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Birthdate</label>
              <input type="date" value={hubForm.birthdate} onChange={e => setHubForm(f => ({ ...f, birthdate: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm" />
            </div>
            <button onClick={addHubMember} className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-sm hover:bg-indigo-700">Save</button>
          </div>
        )}

        {oversightError && (
          <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">{oversightError}</p>
        )}

        {!oversightError && oversight.length === 0 && (
          <p className="text-sm text-gray-500">No family profiles yet — add one to start tracking their health &amp; finances separately.</p>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          {oversight.map((m: any) => (
            <div key={m.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{m.name}</h3>
                  <p className="text-xs text-gray-500">{m.role}{m.age != null ? ` • age ${m.age}` : ''}</p>
                </div>
                <button onClick={() => removeHubMember(m.id)} className="text-gray-400 hover:text-red-500" title="Remove profile">
                  <Trash2 size={16} />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="bg-green-50 rounded-lg p-3">
                  <div className="flex items-center gap-1 text-green-700 font-medium mb-1">
                    <DollarSign size={14} /> Finance
                  </div>
                  {m.finance.reports > 0 ? (
                    <>
                      <p className="text-gray-800 font-semibold">${m.finance.total_spent.toFixed(2)} spent</p>
                      <p className="text-xs text-gray-500">{m.finance.transaction_count} txns • {m.finance.reports} report{m.finance.reports !== 1 ? 's' : ''}</p>
                      {Object.keys(m.finance.top_categories || {}).length > 0 && (
                        <p className="text-xs text-gray-500 mt-1">Top: {Object.entries(m.finance.top_categories).slice(0, 2).map(([k]) => k).join(', ')}</p>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-gray-500">No statements uploaded</p>
                  )}
                </div>
                <div className="bg-rose-50 rounded-lg p-3">
                  <div className="flex items-center gap-1 text-rose-700 font-medium mb-1">
                    <Activity size={14} /> Health
                  </div>
                  {m.health.reports > 0 ? (
                    <>
                      <p className="text-gray-800 font-semibold">{m.health.reports} report{m.health.reports !== 1 ? 's' : ''}</p>
                      <p className="text-xs text-gray-500">
                        {m.health.abnormal_results} abnormal{m.health.alerts > 0 ? ` • ${m.health.alerts} alerts` : ''}
                      </p>
                      {m.health.alert_messages?.slice(0, 2).map((msg: string, i: number) => (
                        <p key={i} className="text-xs text-red-600 mt-1 truncate" title={msg}>{msg}</p>
                      ))}
                    </>
                  ) : (
                    <p className="text-xs text-gray-500">No health records</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-pink-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading family data...</p>
        </div>
      ) : (
        <>
          {/* Family Members */}
          <div className="grid md:grid-cols-3 gap-6 mb-8">
            {members.map((member) => (
              <div key={member.kid_id} className="bg-white p-6 rounded-xl border border-gray-200 hover:shadow-lg transition-shadow">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-xl">👧</span>
                  </div>
                  <div>
                    <h3 className="font-semibold">{member.name}</h3>
                    <p className="text-sm text-gray-600">Age {member.age} • {member.grade || 'Student'}</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  {member.school && (
                    <div className="flex items-center gap-2">
                      <Calendar className="text-blue-600" size={16} />
                      <span>{member.school}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <Smile className="text-green-600" size={16} />
                    <span>Mood: Happy (8/10)</span>
                  </div>
                </div>
              </div>
            ))}

            <button 
              onClick={() => setShowAddModal(true)}
              className="bg-gradient-to-br from-gray-50 to-gray-100 p-6 rounded-xl border-2 border-dashed border-gray-300 hover:border-blue-500 transition-colors flex flex-col items-center justify-center"
            >
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-3">
                <Plus className="text-blue-600" size={24} />
              </div>
              <span className="font-medium text-gray-700">Add Family Member</span>
            </button>
          </div>
        </>
      )}

      {/* Quick Stats */}
      <div className="grid md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Calendar className="text-blue-600 mb-2" size={24} />
          <p className="text-2xl font-bold">5</p>
          <p className="text-sm text-gray-600">Activities this week</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Heart className="text-red-600 mb-2" size={24} />
          <p className="text-2xl font-bold">8.5</p>
          <p className="text-sm text-gray-600">Avg happiness score</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <TrendingUp className="text-green-600 mb-2" size={24} />
          <p className="text-2xl font-bold">12</p>
          <p className="text-sm text-gray-600">Milestones achieved</p>
        </div>

        <div className="bg-white p-6 rounded-xl border border-gray-200">
          <Smile className="text-yellow-600 mb-2" size={24} />
          <p className="text-2xl font-bold">All Good</p>
          <p className="text-sm text-gray-600">Family wellbeing</p>
        </div>
      </div>

      {/* Emotional Check-ins */}
      <div className="bg-gradient-to-r from-purple-50 to-pink-50 p-8 rounded-xl border border-purple-200">
        <h3 className="text-xl font-semibold text-purple-900 mb-4">💜 Daily Check-ins</h3>
        <p className="text-purple-700 mb-4">
          Keep track of everyone's emotional wellbeing with daily mood check-ins.
        </p>
        <button 
          onClick={() => setShowCheckInModal(true)}
          className="bg-purple-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-purple-700 transition-colors"
        >
          Start Check-in
        </button>
      </div>

      {/* Add Member Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Add Family Member</h2>
              <button onClick={() => setShowAddModal(false)} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Name *</label>
                <input
                  type="text"
                  value={addForm.name}
                  onChange={(e) => setAddForm({...addForm, name: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter name"
                />
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Date of Birth *</label>
                  <input
                    type="date"
                    value={addForm.date_of_birth}
                    onChange={(e) => {
                      const dob = e.target.value
                      const birthDate = new Date(dob)
                      const today = new Date()
                      let age = today.getFullYear() - birthDate.getFullYear()
                      const monthDiff = today.getMonth() - birthDate.getMonth()
                      if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
                        age--
                      }
                      setAddForm({...addForm, date_of_birth: dob, age})
                    }}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Age</label>
                  <input
                    type="number"
                    value={addForm.age}
                    readOnly
                    className="w-full px-4 py-2 border rounded-lg bg-gray-50"
                  />
                </div>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Grade</label>
                  <input
                    type="text"
                    value={addForm.grade}
                    onChange={(e) => setAddForm({...addForm, grade: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., 5th Grade"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">School</label>
                  <input
                    type="text"
                    value={addForm.school}
                    onChange={(e) => setAddForm({...addForm, school: e.target.value})}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., Socrates Academy"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Interests (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.interests}
                  onChange={(e) => setAddForm({...addForm, interests: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Soccer, Art, Reading"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Strengths (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.strengths}
                  onChange={(e) => setAddForm({...addForm, strengths: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Creative, Athletic"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Personality Traits (comma-separated)</label>
                <input
                  type="text"
                  value={addForm.personality_traits}
                  onChange={(e) => setAddForm({...addForm, personality_traits: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Outgoing, Curious"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Learning Style</label>
                <select
                  value={addForm.learning_style}
                  onChange={(e) => setAddForm({...addForm, learning_style: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                >
                  <option value="Visual">Visual</option>
                  <option value="Auditory">Auditory</option>
                  <option value="Kinesthetic">Kinesthetic</option>
                  <option value="Reading/Writing">Reading/Writing</option>
                </select>
              </div>
              <div className="flex gap-4 mt-6">
                <button
                  onClick={handleAddMember}
                  className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700"
                >
                  Add Member
                </button>
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 bg-gray-200 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Check-in Modal */}
      {showCheckInModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">Emotional Check-in</h2>
              <button onClick={() => setShowCheckInModal(false)} className="text-gray-500 hover:text-gray-700">
                <X size={24} />
              </button>
            </div>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium mb-2">Family Member *</label>
                <select
                  value={checkInForm.member_id}
                  onChange={(e) => setCheckInForm({...checkInForm, member_id: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                >
                  <option value="">Select a family member</option>
                  {members.map(member => (
                    <option key={member.kid_id} value={member.kid_id}>{member.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Mood</label>
                <select
                  value={checkInForm.mood}
                  onChange={(e) => setCheckInForm({...checkInForm, mood: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                >
                  <option value="happy">😊 Happy</option>
                  <option value="sad">😢 Sad</option>
                  <option value="stressed">😰 Stressed</option>
                  <option value="anxious">😟 Anxious</option>
                  <option value="excited">🤩 Excited</option>
                  <option value="tired">😴 Tired</option>
                  <option value="angry">😠 Angry</option>
                  <option value="calm">😌 Calm</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Mood Score: {checkInForm.mood_score}/10</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={checkInForm.mood_score}
                  onChange={(e) => setCheckInForm({...checkInForm, mood_score: parseInt(e.target.value)})}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Stress Level: {checkInForm.stress_level}/10</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={checkInForm.stress_level}
                  onChange={(e) => setCheckInForm({...checkInForm, stress_level: parseInt(e.target.value)})}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Energy Level: {checkInForm.energy_level}/10</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={checkInForm.energy_level}
                  onChange={(e) => setCheckInForm({...checkInForm, energy_level: parseInt(e.target.value)})}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2">Notes</label>
                <textarea
                  value={checkInForm.notes}
                  onChange={(e) => setCheckInForm({...checkInForm, notes: e.target.value})}
                  className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500"
                  rows={4}
                  placeholder="How are you feeling today? Any concerns?"
                />
              </div>
              <div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={checkInForm.needs_support}
                    onChange={(e) => setCheckInForm({...checkInForm, needs_support: e.target.checked})}
                    className="w-4 h-4"
                  />
                  <span className="text-sm font-medium">I need support</span>
                </label>
              </div>
              <div className="flex gap-4 mt-6">
                <button
                  onClick={handleCheckIn}
                  disabled={!checkInForm.member_id}
                  className="flex-1 bg-purple-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Submit Check-in
                </button>
                <button
                  onClick={() => setShowCheckInModal(false)}
                  className="flex-1 bg-gray-200 text-gray-700 px-6 py-3 rounded-lg font-medium hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
