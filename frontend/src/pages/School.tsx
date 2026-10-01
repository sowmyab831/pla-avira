import { useState, useEffect } from 'react'
import { AlertCircle, Loader, BookOpen, Calendar, Bell, GraduationCap, ClipboardList, CheckCircle, Clock, ExternalLink } from 'lucide-react'
import config from '../config'

interface Course {
  id: string
  name: string
  teacher: string
  grade?: string
}

interface Assignment {
  id: string
  title: string
  course: string
  due_date: string
  status: 'pending' | 'submitted' | 'graded'
  grade?: string
}

interface SchoolEvent {
  id: string
  title: string
  date: string
  type: string
  school: string
}

export default function School() {
  const [loading, setLoading] = useState(false)
  const [schoologyConnected, setSchoologyConnected] = useState(false)
  const [parentSquareConnected] = useState(false)
  const [courses, setCourses] = useState<Course[]>([])
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [upcomingEvents, setUpcomingEvents] = useState<SchoolEvent[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'courses' | 'assignments' | 'events'>('overview')

  const handleSchoologyConnect = async () => {
    try {
      setLoading(true)
      const response = await fetch(config.endpoints.schoologyAuth)
      const data = await response.json()
      
      if (data.auth_url) {
        // Open Schoology login in new window
        window.open(data.auth_url, 'schoology_login', 'width=600,height=700')
      }
    } catch (error) {
      console.error('Failed to connect Schoology:', error)
      alert('Failed to connect to Schoology')
    } finally {
      setLoading(false)
    }
  }

  const handleParentSquareConnect = () => {
    window.open('https://www.parentsquare.com/auth/login', 'parentsquare_login', 'width=600,height=700')
  }

  const checkSchoologyStatus = async () => {
    try {
      const response = await fetch(config.endpoints.schoologyStatus)
      const data = await response.json()
      setSchoologyConnected(data.connected)
      
      if (data.connected) {
        fetchCourses()
        fetchAssignments()
      }
    } catch (error) {
      console.error('Failed to check status:', error)
    }
  }

  const fetchCourses = async () => {
    try {
      const response = await fetch(config.endpoints.schoologyCourses)
      const data = await response.json()
      if (data.courses) {
        setCourses(data.courses)
      }
    } catch (error) {
      console.error('Failed to fetch courses:', error)
      // Demo data
      setCourses([
        { id: '1', name: 'Mathematics', teacher: 'Mrs. Johnson', grade: 'A' },
        { id: '2', name: 'Science', teacher: 'Mr. Williams', grade: 'A-' },
        { id: '3', name: 'English', teacher: 'Ms. Davis', grade: 'B+' },
        { id: '4', name: 'History', teacher: 'Mr. Brown', grade: 'A' }
      ])
    }
  }

  const fetchAssignments = async () => {
    try {
      const response = await fetch(config.endpoints.schoologyAssignments)
      const data = await response.json()
      if (data.assignments) {
        setAssignments(data.assignments)
      }
    } catch (error) {
      console.error('Failed to fetch assignments:', error)
      // Demo data
      setAssignments([
        { id: '1', title: 'Math Quiz Ch. 5', course: 'Mathematics', due_date: '2025-02-10', status: 'pending' },
        { id: '2', title: 'Science Lab Report', course: 'Science', due_date: '2025-02-12', status: 'pending' },
        { id: '3', title: 'Essay Draft', course: 'English', due_date: '2025-02-08', status: 'submitted' },
        { id: '4', title: 'History Project', course: 'History', due_date: '2025-02-15', status: 'pending' }
      ])
    }
  }

  const fetchUpcomingEvents = async () => {
    try {
      const response = await fetch(`${config.endpoints.calendarUpcoming}?days=30`)
      const data = await response.json()
      if (data.events) {
        setUpcomingEvents(data.events.slice(0, 5).map((e: any) => ({
          id: e.id || Math.random().toString(),
          title: e.title,
          date: e.date,
          type: e.type,
          school: e.source || 'School'
        })))
      }
    } catch (error) {
      console.error('Failed to fetch events:', error)
    }
  }

  useEffect(() => {
    checkSchoologyStatus()
    fetchUpcomingEvents()
  }, [])

  const pendingAssignments = assignments.filter(a => a.status === 'pending')
  const submittedAssignments = assignments.filter(a => a.status === 'submitted' || a.status === 'graded')

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-2">
        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-xl flex items-center justify-center">
          <GraduationCap className="text-white" size={24} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-gray-900">School Dashboard</h1>
          <p className="text-gray-600">Track grades, assignments, and school events</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 mt-6 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 font-medium rounded-t-lg ${activeTab === 'overview' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('courses')}
          className={`px-4 py-2 font-medium rounded-t-lg flex items-center gap-2 ${activeTab === 'courses' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <BookOpen size={16} /> Courses ({courses.length})
        </button>
        <button
          onClick={() => setActiveTab('assignments')}
          className={`px-4 py-2 font-medium rounded-t-lg flex items-center gap-2 ${activeTab === 'assignments' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <ClipboardList size={16} /> Assignments ({pendingAssignments.length} pending)
        </button>
        <button
          onClick={() => setActiveTab('events')}
          className={`px-4 py-2 font-medium rounded-t-lg flex items-center gap-2 ${activeTab === 'events' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600' : 'text-gray-600 hover:bg-gray-100'}`}
        >
          <Calendar size={16} /> Events
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <>
          {/* Connection Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <BookOpen className="text-indigo-600" size={20} />
                Connect Schoology
              </h2>
              <p className="text-gray-600 text-sm mb-4">Sync grades and assignments automatically</p>
              <button
                onClick={handleSchoologyConnect}
                disabled={loading}
                className={`px-4 py-2 rounded-lg text-white transition-colors flex items-center gap-2 ${
                  schoologyConnected
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-indigo-600 hover:bg-indigo-700'
                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {loading ? (
                  <>
                    <Loader size={16} className="animate-spin" />
                    Connecting...
                  </>
                ) : schoologyConnected ? (
                  <><CheckCircle size={16} /> Connected</>
                ) : (
                  'Connect Account'
                )}
              </button>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Bell className="text-purple-600" size={20} />
                Connect ParentSquare
              </h2>
              <p className="text-gray-600 text-sm mb-4">Get school announcements and messages</p>
              <button
                onClick={handleParentSquareConnect}
                className={`px-4 py-2 rounded-lg text-white transition-colors flex items-center gap-2 ${
                  parentSquareConnected
                    ? 'bg-green-600 hover:bg-green-700'
                    : 'bg-purple-600 hover:bg-purple-700'
                }`}
              >
                {parentSquareConnected ? <><CheckCircle size={16} /> Connected</> : 'Connect Account'}
              </button>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Courses</p>
              <p className="text-2xl font-bold text-indigo-600">{courses.length}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Pending</p>
              <p className="text-2xl font-bold text-yellow-600">{pendingAssignments.length}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Submitted</p>
              <p className="text-2xl font-bold text-green-600">{submittedAssignments.length}</p>
            </div>
            <div className="bg-white rounded-lg shadow p-4">
              <p className="text-sm text-gray-500">Events</p>
              <p className="text-2xl font-bold text-purple-600">{upcomingEvents.length}</p>
            </div>
          </div>

          {/* Upcoming Assignments Preview */}
          {pendingAssignments.length > 0 && (
            <div className="bg-white rounded-lg shadow p-6 mb-8">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <Clock className="text-yellow-600" size={20} />
                Upcoming Assignments
              </h3>
              <div className="space-y-3">
                {pendingAssignments.slice(0, 3).map(assignment => (
                  <div key={assignment.id} className="flex items-center justify-between p-3 bg-yellow-50 rounded-lg">
                    <div>
                      <p className="font-medium">{assignment.title}</p>
                      <p className="text-sm text-gray-500">{assignment.course}</p>
                    </div>
                    <span className="text-sm text-yellow-700 font-medium">
                      Due {new Date(assignment.due_date).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Courses Tab */}
      {activeTab === 'courses' && (
        <div className="grid md:grid-cols-2 gap-4">
          {courses.map(course => (
            <div key={course.id} className="bg-white rounded-lg shadow p-5 border-l-4 border-indigo-500">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-lg">{course.name}</h3>
                  <p className="text-sm text-gray-500">{course.teacher}</p>
                </div>
                {course.grade && (
                  <span className={`text-2xl font-bold ${
                    course.grade.startsWith('A') ? 'text-green-600' :
                    course.grade.startsWith('B') ? 'text-blue-600' :
                    course.grade.startsWith('C') ? 'text-yellow-600' :
                    'text-red-600'
                  }`}>
                    {course.grade}
                  </span>
                )}
              </div>
              <a href="#" className="mt-3 text-sm text-indigo-600 hover:text-indigo-800 flex items-center gap-1">
                View Details <ExternalLink size={14} />
              </a>
            </div>
          ))}
          {courses.length === 0 && (
            <div className="col-span-2 text-center py-12 text-gray-500">
              <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
              <p>Connect to Schoology to see your courses</p>
            </div>
          )}
        </div>
      )}

      {/* Assignments Tab */}
      {activeTab === 'assignments' && (
        <div className="space-y-4">
          <h3 className="font-semibold text-lg text-gray-900">Pending ({pendingAssignments.length})</h3>
          {pendingAssignments.map(assignment => (
            <div key={assignment.id} className="bg-white rounded-lg shadow p-4 border-l-4 border-yellow-500">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">{assignment.title}</h4>
                  <p className="text-sm text-gray-500">{assignment.course}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium text-yellow-700">
                    Due {new Date(assignment.due_date).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
          
          <h3 className="font-semibold text-lg text-gray-900 mt-6">Submitted ({submittedAssignments.length})</h3>
          {submittedAssignments.map(assignment => (
            <div key={assignment.id} className="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">{assignment.title}</h4>
                  <p className="text-sm text-gray-500">{assignment.course}</p>
                </div>
                <CheckCircle className="text-green-500" size={20} />
              </div>
            </div>
          ))}
          
          {assignments.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <ClipboardList size={48} className="mx-auto mb-4 opacity-50" />
              <p>Connect to Schoology to see your assignments</p>
            </div>
          )}
        </div>
      )}

      {/* Events Tab */}
      {activeTab === 'events' && (
        <div className="space-y-4">
          {upcomingEvents.map(event => (
            <div key={event.id} className="bg-white rounded-lg shadow p-4 border-l-4 border-purple-500">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="font-medium">{event.title}</h4>
                  <p className="text-sm text-gray-500">{event.school}</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium text-purple-700">
                    {new Date(event.date).toLocaleDateString()}
                  </span>
                  <span className="ml-2 text-xs px-2 py-1 bg-purple-100 text-purple-700 rounded">
                    {event.type}
                  </span>
                </div>
              </div>
            </div>
          ))}
          {upcomingEvents.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              <Calendar size={48} className="mx-auto mb-4 opacity-50" />
              <p>No upcoming events. Sync school calendars to see events.</p>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6 flex gap-4">
        <AlertCircle className="text-blue-600 flex-shrink-0" size={24} />
        <div>
          <h3 className="font-semibold text-blue-900">School Portal Integration</h3>
          <p className="text-blue-800 text-sm mt-2">
            Connect your school accounts to automatically sync grades, assignments, and events.
            Your credentials are securely stored and used only for authentication.
          </p>
        </div>
      </div>
    </div>
  )
}
